"""TASK-028/T-52 — a troca de e-mail em `/accounts/email/`.

Demanda do quality-assurance. Nível integração: o formulário, a transação, `esquecer_tentativas`,
o envio com e sem teto, o `axes`, a sessão e os links já emitidos só se encontram numa requisição.

Recusas: senha errada ("Senha incorreta." e uma falha contada no `axes` do e-mail atual),
endereço em uso em outra caixa e o mesmo endereço. Nenhuma muda a conta.

Troca válida, com `next` hostil na query e no corpo: vai exatamente a
`{SPA_URL}/app/conta?aviso=email-trocado`. O endereço fica em minúsculas, a verificação zera,
`updated_at` avança, e `sub`, as duas sessões e os tokens ficam. A confirmação vai ao endereço
novo, e o aviso vai ao antigo, sem o endereço novo no corpo, mesmo com o teto do antigo
esgotado. O histórico de login do antigo some nas três tabelas, em duas caixas; o do novo
fica. `email_trocado` entra na trilha sem e-mail. O link de confirmação anterior passa a
`?email=invalido`, e o link de redefinição pendente vira "Link inválido": os dois derivam do
endereço.

Vermelho se a senha for conferida sem passar pelo `axes`, se o `next` for seguido, se a troca
mexer em `sub`, sessão ou token, se o aviso sofrer o teto, ou se o histórico do antigo ficar.
"""

from datetime import timedelta

from axes.models import AccessAttempt
from django.core import mail
from django.core.cache import cache
from django.contrib.auth.tokens import default_token_generator
from django.test import override_settings
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from accounts import confirmacao
from accounts.envio import chave_do_envio
from tests.paginas_helpers import (
    EMAIL,
    SENHA,
    PaginasDeContaTestCase,
    User,
    com_arroba,
    contagem_axes,
    eventos,
    semear_axes,
    vivos,
)

URL = "/accounts/email/"


class RecusasDaTrocaDeEmailTests(PaginasDeContaTestCase):
    def setUp(self):
        super().setUp()
        User.objects.create_user("outro@ex.com", SENHA)
        self.client.force_login(self.conta)

    def _recusada(self, linhas_esperadas=(), **dados):
        marca = self.trilha()
        resposta = self.postar(self.client, URL, dados)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(User.objects.get(pk=self.conta.pk).email, EMAIL)
        self.assertEqual(mail.outbox, [])
        # Só a falha de autenticação que o `axes` conta, quando há: nenhum evento de conta.
        self.assertEqual(eventos(marca()), list(linhas_esperadas))
        return resposta

    def test_senha_errada_recusa_e_o_axes_conta_uma_falha_no_e_mail_atual(self):
        antes = AccessAttempt.objects.filter(username=EMAIL).first()
        falhas_antes = antes.failures_since_start if antes else 0

        resposta = self._recusada(
            ["user_login_failed"], novo_email="novo@ex.com", senha="errada-errada-1"
        )

        self.assertContains(resposta, "Senha incorreta.")
        self.assertEqual(
            AccessAttempt.objects.get(username=EMAIL).failures_since_start, falhas_antes + 1
        )

    def test_endereco_em_uso_em_outra_caixa_e_recusado(self):
        resposta = self._recusada(novo_email="OUTRO@ex.com", senha=SENHA)

        self.assertContains(resposta, "Já existe uma conta com este e-mail.")

    def test_o_mesmo_endereco_e_recusado(self):
        resposta = self._recusada(novo_email="PESSOA@ex.com", senha=SENHA)

        self.assertContains(resposta, "Este já é o e-mail da conta.")


class TrocaValidaDeEmailTests(PaginasDeContaTestCase):
    def setUp(self):
        super().setUp()
        self.sessao1 = self.tokens_nas_duas()
        self.sessao2 = self.outra_sessao()
        # `update()`, para o estado de partida (verificado, `updated_at` antigo) não passar pelas
        # regras do `save()` que o caso observa.
        self.antigo_updated_at = timezone.now() - timedelta(days=3)
        User.objects.filter(pk=self.conta.pk).update(
            email_verified=True,
            email_verificado_em=timezone.now() - timedelta(days=5),
            updated_at=self.antigo_updated_at,
        )
        self.sub = User.objects.get(pk=self.conta.pk).sub
        for caixa, ip in ((EMAIL, "10.0.0.1"), ("Pessoa@Ex.com", "10.0.0.2")):
            semear_axes(caixa, ip)
        semear_axes("novo@ex.com", "10.0.0.3")
        self.novo_antes = contagem_axes("novo@ex.com")
        # Os links pendentes, depois de todo login do arranjo: o token de redefinição deriva
        # de `last_login`.
        conta = User.objects.get(pk=self.conta.pk)
        self.link_de_confirmacao = confirmacao.gerar(conta)
        uid = urlsafe_base64_encode(force_bytes(conta.pk))
        self.link_de_redefinicao = f"/accounts/reset/{uid}/{default_token_generator.make_token(conta)}/"
        self.marca = self.trilha()

    def _trocar(self, client=None, **extra):
        return self.postar(
            client or self.sessao1,
            f"{URL}?next=https://evil.com",
            {"novo_email": "Novo@Ex.com", "senha": SENHA, "next": "https://evil.com"},
            **extra,
        )

    def test_vai_a_spa_ignorando_o_next_e_deixa_a_conta_como_esperado(self):
        resposta = self._trocar()

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta["Location"], f"{self.spa}/app/conta?aviso=email-trocado")
        conta = User.objects.get(pk=self.conta.pk)
        self.assertEqual(conta.email, "novo@ex.com")
        self.assertFalse(conta.email_verified)
        self.assertIsNone(conta.email_verificado_em)
        self.assertGreater(conta.updated_at, self.antigo_updated_at)
        self.assertEqual(conta.sub, self.sub)

    def test_as_duas_sessoes_e_os_tokens_ficam(self):
        self._trocar()

        self.assertSessaoViva(self.sessao1)
        self.assertSessaoViva(self.sessao2)
        for aplicacao in (self.app1, self.app2):
            self.assertEqual(vivos(self.conta, aplicacao), (1, 1, 1))

    def test_confirmacao_ao_novo_e_aviso_ao_antigo_sem_o_endereco_novo(self):
        self._trocar()

        por_destino = {m.to[0]: m for m in mail.outbox}
        self.assertEqual(sorted(por_destino), ["novo@ex.com", EMAIL])
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(por_destino["novo@ex.com"].subject, "Boas-vindas: confirme o seu e-mail")
        aviso = por_destino[EMAIL]
        self.assertEqual(aviso.subject, "O e-mail da sua conta foi trocado")
        self.assertNotIn("novo@ex.com", aviso.body)
        self.assertNotIn("novo@ex.com", aviso.subject)

    def test_o_aviso_ao_antigo_sai_com_o_teto_das_confirmacoes_dele_esgotado(self):
        # Teto de um, e a chave do antigo já acima dele: o do novo ainda cabe, e o aviso corre
        # por outro contador.
        self.enterContext(override_settings(TETO_DE_ENVIOS_POR_DESTINATARIO=1))
        for endereco in (EMAIL, "novo@ex.com"):
            self.addCleanup(cache.delete, chave_do_envio(endereco))
        cache.set(chave_do_envio(EMAIL), 100, timeout=3600)

        self._trocar()

        self.assertCountEqual([m.to[0] for m in mail.outbox], ["novo@ex.com", EMAIL])

    def test_o_aviso_ao_antigo_nao_sai_com_o_teto_dos_avisos_esgotado_e_a_confirmacao_sai(self):
        """TASK-028/T-76 — com o teto dos avisos esgotado só a confirmação ao novo sai."""
        self.esgotar_teto_de_avisos(EMAIL)

        self._trocar()

        self.assertEqual([m.to[0] for m in mail.outbox], ["novo@ex.com"])

    def test_o_historico_do_antigo_some_nas_tres_tabelas_e_o_do_novo_fica(self):
        self._trocar()

        self.assertEqual(contagem_axes(EMAIL), (0, 0, 0))
        self.assertEqual(contagem_axes("novo@ex.com"), self.novo_antes)

    def test_a_trilha_so_ganha_email_trocado_e_sem_e_mail(self):
        self._trocar()

        linhas = self.marca()
        self.assertEqual(eventos(linhas), ["email_trocado"])
        self.assertEqual(com_arroba(linhas), [])

    def test_o_link_de_confirmacao_anterior_e_invalido(self):
        self._trocar()

        resposta = self.client.get("/api/conta/confirmar/", {"t": self.link_de_confirmacao})

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta["Location"], f"{self.spa}/?email=invalido")
        self.assertFalse(User.objects.get(pk=self.conta.pk).email_verified)

    def test_o_link_de_redefinicao_pendente_vira_link_invalido(self):
        self._trocar()

        resposta = self.client.get(self.link_de_redefinicao)

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "<h1>Link inválido</h1>")
