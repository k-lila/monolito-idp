"""TASK-028/T-53, T-54, T-55 e T-64 — a exclusão em `/accounts/excluir/`.

Demanda do quality-assurance (T-64, decisão da pessoa usuária). Nível integração:
`PaginaDeExclusao`, `FormularioDeExclusao`, a revogação, `esquecer_tentativas`, o envio, a
sessão e a trilha só se encontram numa requisição.

T-53: a conta da equipe (`is_staff` ou `is_superuser`) recebe 403 em GET e em POST válido, sem
formulário, com a volta à SPA, e nada muda: apagar a última conta de admin pela página deixaria o
IdP sem quem o administre.

T-54, desativar: recusa por senha errada, sem confirmação ou com modo inválido deixa a conta
ativa. O pedido válido, com `next` hostil, vai exatamente a `{SPA_URL}/?conta=desativada`;
carimba a conta, revoga os tokens de todas as Applications, derruba as sessões, avisa o endereço
mesmo com o teto esgotado e registra `tokens_revogados`, `conta_desativada` e `user_logged_out`
sem e-mail. O histórico do `axes` FICA: a conta continua existindo.

T-55, apagar: a conta, os tokens e o histórico do `axes` somem; o aviso vai ao endereço que a
conta tinha; a trilha guarda o `sub` anterior em texto; a sessão cai; e quem se cadastra depois
com o mesmo endereço recebe um `sub` diferente.

T-64: a conta que é `user` de uma Application só desativa. A página não oferece "apagar", e o
envio de "apagar" é recusado no servidor, com a conta, a Application e o token de outra pessoa
nessa Application intactos. A checagem tem de estar no envio, e não só na exibição.

Vermelho se a recusa à equipe sair, se um passo da desativação ou do apagamento faltar, se o
histórico do `axes` seguir o caminho errado em cada modo, ou se a checagem de T-64 sair do POST.
"""

from django.core import mail
from oauth2_provider.models import AccessToken, get_application_model

from tests.logout_helpers import criar_application, emitir_tokens
from tests.paginas_helpers import (
    dados_de_cadastro,
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

URL = "/accounts/excluir/"
Application = get_application_model()


def _pedido(modo="desativar", **mudancas):
    dados = {"modo": modo, "confirmo": "on", "senha": SENHA}
    dados.update(mudancas)
    return {chave: valor for chave, valor in dados.items() if valor is not None}


class ContaDaEquipeTests(PaginasDeContaTestCase):
    """T-53."""

    def test_staff_e_superusuario_recebem_403_em_get_e_em_post_sem_mudar_nada(self):
        equipe = {
            "staff": User.objects.create_user("staff@ex.com", SENHA, is_staff=True),
            "superusuario": User.objects.create_superuser("super@ex.com", SENHA),
        }
        for nome, conta in equipe.items():
            self.client.force_login(conta)
            marca = self.trilha()
            for metodo, dados in (("get", None), ("post", _pedido("apagar"))):
                with self.subTest(conta=nome, metodo=metodo):
                    resposta = (
                        self.client.get(URL)
                        if dados is None
                        else self.postar(self.client, URL, dados)
                    )

                    self.assertEqual(resposta.status_code, 403)
                    corpo = resposta.content.decode()
                    self.assertNotIn('name="modo"', corpo)
                    self.assertNotIn('name="senha"', corpo)
                    self.assertIn(f'href="{self.spa}/app/conta"', corpo)
                    conta.refresh_from_db()
                    self.assertTrue(conta.is_active)
                    self.assertTrue(User.objects.filter(pk=conta.pk).exists())
            self.assertEqual(marca(), [])
        self.assertEqual(mail.outbox, [])


class DesativarTests(PaginasDeContaTestCase):
    """T-54."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.conta)

    def test_recusas_deixam_a_conta_ativa(self):
        casos = {
            "senha errada": _pedido(senha="errada-errada-1"),
            "sem confirmo": _pedido(confirmo=None),
            "modo inválido": _pedido(modo="sumir"),
        }
        for nome, dados in casos.items():
            with self.subTest(caso=nome):
                resposta = self.postar(self.client, URL, dados)

                self.assertEqual(resposta.status_code, 200)
                self.assertTrue(User.objects.get(pk=self.conta.pk).is_active)
                self.assertEqual(vivos(self.conta), (0, 0, 0))
        self.assertEqual(mail.outbox, [])

    def test_desativacao_valida_vai_a_spa_e_carimba_a_conta(self):
        resposta = self.postar(
            self.client,
            f"{URL}?next=https://evil.com",
            _pedido(next="https://evil.com"),
        )

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta["Location"], f"{self.spa}/?conta=desativada")
        conta = User.objects.get(pk=self.conta.pk)
        self.assertFalse(conta.is_active)
        self.assertEqual(conta.desativada_por, "propria_pessoa")
        self.assertIsNotNone(conta.desativada_em)

    def test_revoga_tudo_derruba_as_sessoes_registra_e_avisa(self):
        sessao = self.tokens_nas_duas()
        outra = self.outra_sessao()
        semear_axes(EMAIL)
        semeado = contagem_axes(EMAIL)
        self.esgotar_teto(EMAIL)
        marca = self.trilha()

        self.postar(sessao, URL, _pedido())

        self.assertEqual(vivos(self.conta), (0, 0, 0))
        self.assertSessaoDeslogada(sessao)
        self.assertSessaoDeslogada(outra)
        linhas = marca()
        self.assertEqual(
            eventos(linhas),
            ["tokens_revogados", "tokens_revogados", "conta_desativada", "user_logged_out"],
        )
        self.assertCountEqual(
            [l["client_id"] for l in linhas[:2]], [self.app1.client_id, self.app2.client_id]
        )
        self.assertEqual(com_arroba(linhas), [])
        (aviso,) = mail.outbox
        self.assertEqual(aviso.to, [EMAIL])
        self.assertEqual(aviso.subject, "A sua conta foi desativada")
        # A conta continua existindo, e o histórico de login dela com ela.
        self.assertEqual(contagem_axes(EMAIL), semeado)


    def test_o_aviso_de_desativacao_nao_sai_com_o_teto_dos_avisos_esgotado_e_a_conta_desativa(self):
        """TASK-028/T-76 — com o teto dos avisos esgotado a conta desativa e o aviso não sai."""
        sessao = self.tokens_nas_duas()
        self.esgotar_teto_de_avisos(EMAIL)

        self.postar(sessao, URL, _pedido())

        self.assertEqual(mail.outbox, [])
        self.conta.refresh_from_db()
        self.assertFalse(self.conta.is_active)


class ApagarTests(PaginasDeContaTestCase):
    """T-55."""

    def setUp(self):
        super().setUp()
        self.sub = str(self.conta.sub)
        self.pk = self.conta.pk
        self.sessao = self.tokens_nas_duas()
        for caixa, ip in ((EMAIL, "10.0.0.1"), ("Pessoa@Ex.com", "10.0.0.2")):
            semear_axes(caixa, ip)
        semear_axes("outro@ex.com", "10.0.0.3")
        self.outro_antes = contagem_axes("outro@ex.com")
        self.marca = self.trilha()
        mail.outbox.clear()

    def _apagar(self):
        return self.postar(self.sessao, URL, _pedido("apagar"))

    def test_apaga_a_conta_os_tokens_e_o_historico_do_axes(self):
        resposta = self._apagar()

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta["Location"], f"{self.spa}/?conta=apagada")
        self.assertFalse(User.objects.filter(pk=self.pk).exists())
        self.assertEqual(AccessToken.objects.filter(user_id=self.pk).count(), 0)
        self.assertEqual(contagem_axes(EMAIL), (0, 0, 0))
        self.assertEqual(contagem_axes("outro@ex.com"), self.outro_antes)
        self.assertSessaoDeslogada(self.sessao)

    def test_avisa_o_endereco_que_a_conta_tinha(self):
        self._apagar()

        (aviso,) = mail.outbox
        self.assertEqual(aviso.to, [EMAIL])
        self.assertEqual(aviso.subject, "A sua conta foi apagada")

    def test_apaga_e_avisa_mesmo_com_o_teto_das_confirmacoes_esgotado(self):
        """TASK-028/T-77 — o teto das confirmações não cala o aviso de apagamento."""
        self.esgotar_teto(EMAIL)

        self._apagar()

        self.assertFalse(User.objects.filter(pk=self.pk).exists())
        (aviso,) = mail.outbox
        self.assertEqual(aviso.to, [EMAIL])
        self.assertEqual(aviso.subject, "A sua conta foi apagada")

    def test_apaga_sem_avisar_com_o_teto_dos_avisos_esgotado(self):
        """TASK-028/T-77 — com o teto dos avisos esgotado a conta é apagada sem aviso."""
        self.esgotar_teto_de_avisos(EMAIL)

        self._apagar()

        self.assertFalse(User.objects.filter(pk=self.pk).exists())
        self.assertEqual(mail.outbox, [])

    def test_a_trilha_guarda_o_sub_anterior_em_texto_e_nao_leva_e_mail(self):
        self._apagar()

        linhas = self.marca()
        self.assertEqual(
            sorted(eventos(linhas)),
            ["conta_apagada", "tokens_revogados", "tokens_revogados", "user_logged_out"],
        )
        apagada = next(l for l in linhas if l["event"] == "conta_apagada")
        self.assertEqual(apagada["sub"], self.sub)
        self.assertEqual(com_arroba(linhas), [])

    def test_o_cadastro_seguinte_com_o_mesmo_endereco_recebe_outro_sub(self):
        self._apagar()

        self.client.post("/accounts/registrar/", dados_de_cadastro(EMAIL, next=None))

        nova = User.objects.get(email=EMAIL)
        self.assertNotEqual(str(nova.sub), self.sub)


class ContaDonaDeApplicationTests(PaginasDeContaTestCase):
    """T-64."""

    def setUp(self):
        super().setUp()
        self.propria = criar_application(self.conta, "Da conta")
        self.outra_pessoa = User.objects.create_user("outra@ex.com", SENHA)
        emitir_tokens(self.outra_pessoa, self.propria)
        self.client.force_login(self.conta)

    def test_a_pagina_nao_oferece_apagar_e_explica(self):
        resposta = self.client.get(URL)

        self.assertEqual(resposta.status_code, 200)
        self.assertNotContains(resposta, 'value="apagar"')
        self.assertContains(resposta, 'value="desativar"')
        self.assertContains(resposta, "só pode ser desativada")

    def test_o_envio_de_apagar_e_recusado_e_nada_some(self):
        resposta = self.postar(self.client, URL, _pedido("apagar"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "só pode ser desativada")
        self.assertTrue(User.objects.filter(pk=self.conta.pk).exists())
        self.assertTrue(Application.objects.filter(pk=self.propria.pk).exists())
        self.assertEqual(AccessToken.objects.filter(user=self.outra_pessoa).count(), 1)
        self.assertEqual(mail.outbox, [])

    def test_desativar_segue_valendo_e_a_application_fica(self):
        resposta = self.postar(self.client, URL, _pedido("desativar"))

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta["Location"], f"{self.spa}/?conta=desativada")
        self.assertFalse(User.objects.get(pk=self.conta.pk).is_active)
        self.assertTrue(Application.objects.filter(pk=self.propria.pk).exists())

    def test_conta_sem_application_continua_vendo_apagar(self):
        sem = User.objects.create_user("sem@ex.com", SENHA)
        self.client.force_login(sem)

        resposta = self.client.get(URL)

        self.assertContains(resposta, 'value="apagar"')
