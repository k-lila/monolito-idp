"""TASK-028/T-45 e T-46 — a redefinição de senha pelo link do e-mail.

Demanda do quality-assurance. Nível integração: o link, o redirecionamento que tira o token da
barra, `FormularioDeRedefinicao`, `PaginaDeRedefinicao.form_valid` (revogação, desbloqueio, sinal
e aviso), o `axes` e a trilha só se encontram numa sequência de requisições.

T-45 percorre o caso completo. Tokens em app1 e app2, uma segunda sessão e o `axes` semeado nas
três tabelas, em duas caixas do mesmo endereço, vêm antes do pedido do link, que é o último passo
do arranjo: o token do Django deriva de `last_login`, e `emitir_tokens` faz login. O link sai
do e-mail do pedido, como sairia para a pessoa. Depois da redefinição: senha nova, tokens
zerados, trilha com `tokens_revogados` por Application e `senha_redefinida` e sem e-mail,
endereço confirmado, sessões caídas, ninguém autenticado por ter o link, e o `axes` sem
`AccessAttempt` e com o histórico intacto (`desbloquear`, e não `esquecer_tentativas`).

T-46 é a parte da redefinição do T-23: o link vale uma vez, vale uma hora (limite no segundo
3600) e o endereço do e-mail vem de `BASE_URL`, nunca do `Host` do pedido.

Vermelho ao tirar qualquer efeito de `form_valid`, ao trocar `desbloquear` por
`esquecer_tentativas`, ao ligar `post_reset_login`, ao deixar o token na barra, ou se o link do
e-mail passar a ser montado a partir do `Host`.
"""

import re
from datetime import datetime, timedelta
from unittest import mock

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator, default_token_generator
from django.core import mail
from django.test import Client, override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from tests.paginas_helpers import (
    EMAIL,
    NOVA,
    SENHA,
    PaginasDeContaTestCase,
    User,
    caminho_do_link,
    com_arroba,
    contagem_axes,
    eventos,
    link_do_email,
    semear_axes,
    vivos,
)

PEDIDO = "/accounts/password_reset/"
CONCLUIDA = "/accounts/reset/done/"


class _ComLink(PaginasDeContaTestCase):
    def pedir_link(self):
        """O link como a pessoa o recebe: do e-mail do pedido. Depois de todo login do arranjo."""
        antes = len(mail.outbox)
        self.postar(Client(), PEDIDO, {"email": EMAIL})
        (mensagem,) = mail.outbox[antes:]
        return caminho_do_link(link_do_email(mensagem))

    def link_direto(self):
        """O link montado direto do gerador, para os casos em que o teto cala o e-mail do pedido."""
        conta = User.objects.get(pk=self.conta.pk)
        uid = urlsafe_base64_encode(force_bytes(conta.pk))
        return f"/accounts/reset/{uid}/{default_token_generator.make_token(conta)}/"

    def redefinir(self, navegador, link):
        """Os dois passos do Django: o GET no link e o POST na URL sem o token."""
        passo1 = navegador.get(link)
        self.assertEqual(passo1.status_code, 302)
        return passo1, self.postar(
            navegador, passo1["Location"], {"new_password1": NOVA, "new_password2": NOVA}
        )


class RedefinicaoCompletaTests(_ComLink):
    def setUp(self):
        super().setUp()
        self.sessao1 = self.tokens_nas_duas()
        self.sessao2 = self.outra_sessao()
        for caixa, ip in ((EMAIL, "10.0.0.1"), ("Pessoa@Ex.com", "10.0.0.2")):
            semear_axes(caixa, ip)
        semear_axes("outro@ex.com", "10.0.0.3")
        self.outro_antes = contagem_axes("outro@ex.com")
        # Depois dos logins do arranjo: o `axes` grava um `AccessLog` em cada um.
        self.antes = contagem_axes(EMAIL)
        self.link = self.pedir_link()
        self.marca = self.trilha()
        mail.outbox.clear()

    def test_o_link_leva_a_uma_url_sem_o_token_e_o_post_conclui(self):
        navegador = Client()

        passo1, passo2 = self.redefinir(navegador, self.link)

        token = self.link.rstrip("/").rsplit("/", 1)[1]
        self.assertTrue(passo1["Location"].endswith("/set-password/"), passo1["Location"])
        self.assertNotIn(token, passo1["Location"])
        self.assertEqual(passo2["Location"], CONCLUIDA)

    def test_efeitos_da_redefinicao(self):
        navegador = Client()

        self.redefinir(navegador, self.link)

        conta = User.objects.get(pk=self.conta.pk)
        self.assertTrue(conta.check_password(NOVA))
        self.assertTrue(conta.email_verified)
        self.assertIsNotNone(conta.email_verificado_em)
        self.assertEqual(vivos(conta), (0, 0, 0))

        linhas = self.marca()
        self.assertEqual(sorted(eventos(linhas)), ["senha_redefinida", "tokens_revogados", "tokens_revogados"])
        revogadas = [l["client_id"] for l in linhas if l["event"] == "tokens_revogados"]
        self.assertCountEqual(revogadas, [self.app1.client_id, self.app2.client_id])
        self.assertEqual(com_arroba(linhas), [])

        self.assertSessaoDeslogada(self.sessao1)
        self.assertSessaoDeslogada(self.sessao2)

        # Quem tem o link não ganha sessão, e a redefinição não é um login.
        self.assertNotIn("_auth_user_id", navegador.session)
        self.assertNotIn("user_logged_in", eventos(linhas))

    def test_o_axes_perde_so_o_bloqueio_e_o_historico_fica(self):
        self.redefinir(Client(), self.link)

        # `AccessAttempt` zerado nas duas caixas; as outras duas tabelas como estavam.
        self.assertEqual(contagem_axes(EMAIL), (0, self.antes[1], self.antes[2]))
        self.assertGreaterEqual(self.antes[0], 2)
        self.assertEqual(contagem_axes("outro@ex.com"), self.outro_antes)

    def test_o_aviso_de_senha_trocada_sai_ao_endereco_da_conta(self):
        self.redefinir(Client(), self.link)

        (aviso,) = mail.outbox
        self.assertEqual(aviso.to, [EMAIL])
        self.assertEqual(aviso.subject, "A senha da sua conta foi trocada")

    def test_o_aviso_sai_com_o_teto_das_confirmacoes_esgotado(self):
        self.esgotar_teto(EMAIL)

        self.redefinir(Client(), self.link)

        self.assertEqual([m.to for m in mail.outbox], [[EMAIL]])

    def test_o_aviso_nao_sai_com_o_teto_dos_avisos_esgotado_e_a_senha_muda(self):
        """TASK-028/T-76 — com o teto dos avisos esgotado a senha muda e o aviso não sai."""
        self.esgotar_teto_de_avisos(EMAIL)

        self.redefinir(Client(), self.link)

        self.assertEqual(mail.outbox, [])
        self.assertTrue(User.objects.get(email=EMAIL).check_password(NOVA))

    def test_a_pagina_final_so_tem_a_spa_como_destino_externo(self):
        corpo = Client().get(CONCLUIDA).content.decode()

        destinos = re.findall(r'(?:href|src|action)="([^"]*)"', corpo)
        externos = [d for d in destinos if re.match(r"(?:[a-z][a-z0-9+.-]*:)?//", d, re.I)]
        self.assertEqual(externos, [f"{settings.SPA_URL}/"])


class LinkDeRedefinicaoTests(_ComLink):
    """T-46."""

    def test_o_segundo_uso_do_link_e_link_invalido_com_saida_para_o_pedido(self):
        link = self.pedir_link()
        self.redefinir(Client(), link)

        resposta = Client().get(link)

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "<h1>Link inválido</h1>")
        self.assertContains(resposta, 'href="/accounts/password_reset/"')

    def test_link_de_conta_da_equipe_e_link_invalido(self):
        """TASK-028/T-73 — a equipe não abre o formulário, nem pelo token válido."""
        for campo in ("is_staff", "is_superuser"):
            with self.subTest(campo=campo):
                conta = User.objects.create_user(f"{campo}@ex.com", "x-Senha-forte-123")
                setattr(conta, campo, True)
                conta.save()
                uid = urlsafe_base64_encode(force_bytes(conta.pk))
                link = f"/accounts/reset/{uid}/{default_token_generator.make_token(conta)}/"

                resposta = Client().get(link)

                self.assertEqual(resposta.status_code, 200)
                self.assertContains(resposta, "<h1>Link inválido</h1>")

    def test_link_emitido_a_conta_que_virou_equipe_depois_e_link_invalido(self):
        link = self.pedir_link()
        User.objects.filter(pk=self.conta.pk).update(is_staff=True)

        resposta = Client().get(link)

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "<h1>Link inválido</h1>")
        self.assertTrue(User.objects.get(pk=self.conta.pk).check_password(SENHA))

    def test_o_link_vale_ate_uma_hora(self):
        link = self.pedir_link()

        def _em(segundos):
            return mock.patch.object(
                PasswordResetTokenGenerator,
                "_now",
                lambda self_: datetime.now() + timedelta(seconds=segundos),
            )

        with _em(3500):
            valido = Client().get(link)
        with _em(3601):
            vencido = Client().get(link)

        self.assertEqual(valido.status_code, 302)
        self.assertEqual(vencido.status_code, 200)
        self.assertContains(vencido, "<h1>Link inválido</h1>")

    def test_o_link_do_e_mail_sai_de_base_url_e_nao_do_host_do_pedido(self):
        hosts = [*settings.ALLOWED_HOSTS, "outro.example"]
        with override_settings(BASE_URL="https://idp.example", ALLOWED_HOSTS=hosts):
            self.postar(Client(), PEDIDO, {"email": EMAIL}, HTTP_HOST="outro.example")

        (mensagem,) = mail.outbox
        self.assertTrue(
            link_do_email(mensagem).startswith("https://idp.example/accounts/reset/"),
            mensagem.body,
        )
        self.assertNotIn("outro.example", mensagem.body)
        self.assertNotIn("outro.example", mensagem.subject)
