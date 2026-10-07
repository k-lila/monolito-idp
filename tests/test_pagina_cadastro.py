"""TASK-028/T-48, T-49 e T-50 — o cadastro em `/accounts/registrar/`.

Demanda do quality-assurance. Nível integração: o desvio de `prompt=create` do toolkit, o
`RedirectURLMixin`, `FormularioDeCadastro`, o modelo, o envio, a sessão e a trilha só se
encontram numa requisição.

T-48: o anônimo que chega a `/o/authorize/` com `prompt=create` vai ao cadastro levando um `next`
absoluto para o mesmo pedido, sem o `create`; com sessão, ao consentimento; com `client_id` ou
`redirect_uri` inválidos, 400 sem `Location`, de modo que o desvio nunca vira redirecionamento
para destino não conferido. A página traz o `next` conferido, os campos, o CSRF, os dois links
da SPA, a versão dos termos e um `<li>` por requisito de senha.

T-49: o POST válido cria a conta sem staff, sem superusuário e não verificada, ainda que o corpo
traga `is_staff`, `is_superuser` e `email_verified`; envia as boas-vindas ao endereço em
minúsculas, registra `conta_criada` e `user_logged_in` sem e-mail, abre a sessão e segue o
`next`. Com o teto do destinatário esgotado a conta nasce e o e-mail não sai.

T-50: cada recusa devolve 200 com a mensagem, sem conta, sem e-mail e sem linha na trilha.

Vermelho se algum campo de privilégio for aceito do corpo, se o e-mail sair antes do commit ou
com o teto ignorado, se a trilha levar o e-mail, ou se uma recusa deixar efeito.
"""

import html
import re
import uuid
from urllib.parse import parse_qs, urlsplit

from django.conf import settings
from django.contrib.auth.password_validation import password_validators_help_texts
from django.core import mail
from django.test import Client

from tests.oauth_helpers import REDIRECT_URI, make_pkce_pair
from tests.paginas_helpers import (
    NEXT_ABSOLUTO,
    NOVA,
    PaginasDeContaTestCase,
    User,
    com_arroba,
    dados_de_cadastro,
    eventos,
)

URL = "/accounts/registrar/"


def _next_oculto(corpo):
    achado = re.search(r'<input type="hidden" name="next" value="([^"]*)"', corpo)
    return html.unescape(achado.group(1)) if achado else None


class DesvioDoPromptCreateTests(PaginasDeContaTestCase):
    """T-48, a metade do `/o/authorize/`."""

    def setUp(self):
        super().setUp()
        verificador, desafio = make_pkce_pair()
        self.parametros = {
            "response_type": "code",
            "client_id": self.app1.client_id,
            "redirect_uri": REDIRECT_URI,
            "scope": "openid",
            "state": "s",
            "code_challenge": desafio,
            "code_challenge_method": "S256",
            "nonce": "n",
        }

    def _authorize(self, client=None, **extra):
        return (client or Client()).get("/o/authorize/", {**self.parametros, **extra})

    def test_anonimo_com_prompt_create_vai_ao_cadastro_com_next_absoluto_sem_o_create(self):
        resposta = self._authorize(prompt="create")

        self.assertEqual(resposta.status_code, 302)
        destino = urlsplit(resposta["Location"])
        self.assertEqual(destino.path, URL)
        (proximo,) = parse_qs(destino.query)["next"]
        interno = urlsplit(proximo)
        self.assertEqual(f"{interno.scheme}://{interno.netloc}{interno.path}", "http://testserver/o/authorize/")
        self.assertEqual(
            {k: v[0] for k, v in parse_qs(interno.query).items()}, self.parametros
        )

    def test_prompt_login_create_mantem_o_login(self):
        resposta = self._authorize(prompt="login create")

        destino = urlsplit(resposta["Location"])
        self.assertEqual(destino.path, URL)
        (proximo,) = parse_qs(destino.query)["next"]
        self.assertEqual(parse_qs(urlsplit(proximo).query)["prompt"], ["login"])

    def test_com_sessao_o_prompt_create_mostra_o_consentimento(self):
        client = Client()
        client.force_login(self.conta)

        resposta = self._authorize(client, prompt="create")

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'name="allow"')

    def test_client_id_inexistente_e_400_sem_location(self):
        resposta = self._authorize(prompt="create", client_id="nao-existe")

        self.assertEqual(resposta.status_code, 400)
        self.assertNotIn("Location", resposta)

    def test_redirect_uri_fora_da_lista_e_400_sem_location(self):
        resposta = self._authorize(prompt="create", redirect_uri="https://evil.example/cb")

        self.assertEqual(resposta.status_code, 400)
        self.assertNotIn("Location", resposta)


class PaginaDeCadastroTests(PaginasDeContaTestCase):
    """T-48, a metade da página."""

    def test_o_next_oculto_traz_o_valor_conferido_e_a_pagina_traz_o_que_o_cadastro_pede(self):
        resposta = self.client.get(URL, {"next": NEXT_ABSOLUTO})

        self.assertEqual(resposta.status_code, 200)
        corpo = resposta.content.decode()
        self.assertEqual(_next_oculto(corpo), NEXT_ABSOLUTO)
        for campo in (
            "email", "first_name", "last_name", "nickname",
            "password1", "password2", "aceite", "termos_versao",
        ):  # fmt: skip
            self.assertRegex(corpo, rf'<input[^>]*name="{campo}"')
        self.assertIn('name="csrfmiddlewaretoken"', corpo)
        self.assertIn(f'href="{self.spa}/termos"', corpo)
        self.assertIn(f'href="{self.spa}/privacidade"', corpo)
        self.assertRegex(corpo, rf"versão\s+{settings.TERMOS_VERSAO_VIGENTE}\.")
        self.assertRegex(
            corpo, rf'name="termos_versao" value="{settings.TERMOS_VERSAO_VIGENTE}"'
        )
        self.assertEqual(corpo.count("<li>"), len(password_validators_help_texts()))


class CadastroValidoTests(PaginasDeContaTestCase):
    """T-49."""

    def test_conta_criada_sem_privilegio_nao_verificada_e_com_o_aceite(self):
        resposta = self.postar(
            self.client,
            URL,
            dados_de_cadastro(is_staff="on", is_superuser="on", email_verified="on"),
        )

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta["Location"], NEXT_ABSOLUTO)
        conta = User.objects.get(email="nova@ex.com")
        self.assertTrue(conta.is_active)
        self.assertFalse(conta.is_staff)
        self.assertFalse(conta.is_superuser)
        self.assertFalse(conta.email_verified)
        self.assertIsNone(conta.email_verificado_em)
        self.assertIsInstance(conta.sub, uuid.UUID)
        self.assertEqual(conta.termos_versao, settings.TERMOS_VERSAO_VIGENTE)
        self.assertIsNotNone(conta.termos_aceitos_em)
        self.assertTrue(conta.has_usable_password())
        self.assertTrue(conta.check_password(NOVA))
        self.assertEqual(self.client.session["_auth_user_id"], str(conta.pk))

    def test_boas_vindas_ao_endereco_minusculo_e_trilha_sem_e_mail(self):
        marca = self.trilha()

        self.postar(self.client, URL, dados_de_cadastro())

        (mensagem,) = mail.outbox
        self.assertEqual(mensagem.to, ["nova@ex.com"])
        self.assertEqual(mensagem.subject, "Boas-vindas: confirme o seu e-mail")
        conta = User.objects.get(email="nova@ex.com")
        linhas = marca()
        self.assertEqual(sorted(eventos(linhas)), ["conta_criada", "user_logged_in"])
        criada = next(l for l in linhas if l["event"] == "conta_criada")
        self.assertEqual(criada["sub"], str(conta.sub))
        self.assertEqual(com_arroba(linhas), [])

    def test_com_o_teto_esgotado_a_conta_nasce_e_o_e_mail_nao_sai(self):
        self.esgotar_teto("nova@ex.com")

        resposta = self.postar(self.client, URL, dados_de_cadastro())

        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(User.objects.filter(email="nova@ex.com").exists())
        self.assertEqual(mail.outbox, [])


class CadastroRecusadoTests(PaginasDeContaTestCase):
    """T-50. Cada recusa: 200 com a mensagem, e nada gravado, enviado ou registrado."""

    def _recusar(self, mensagem, **mudancas):
        contas = User.objects.count()
        marca = self.trilha()

        resposta = self.postar(self.client, URL, dados_de_cadastro(**mudancas))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, mensagem)
        self.assertEqual(User.objects.count(), contas)
        self.assertEqual(mail.outbox, [])
        self.assertEqual(marca(), [])
        return resposta

    def test_e_mail_em_uso_em_outra_caixa(self):
        self._recusar("Já existe uma conta com este e-mail.", email="PESSOA@ex.com")

    def test_senha_fraca(self):
        resposta = self._recusar(
            "Esta senha é muito curta", password1="123", password2="123"
        )
        self.assertContains(resposta, "Esta senha é muito comum")
        self.assertContains(resposta, "Esta senha é inteiramente numérica")

    def test_confirmacao_diferente(self):
        self._recusar("Os dois campos de senha não correspondem.", password2=NOVA + "x")

    def test_sem_aceite(self):
        self._recusar(
            "Para criar a conta, aceite os termos de uso e a política de privacidade.",
            aceite=None,
        )

    def test_versao_dos_termos_desatualizada_ou_vazia(self):
        for versao in ("0", ""):
            with self.subTest(versao=versao):
                mensagem = (
                    "Os termos mudaram desde que esta página foi aberta."
                    if versao
                    else "Este campo é obrigatório."
                )
                self._recusar(mensagem, termos_versao=versao)

    def test_senha_parecida_com_o_e_mail_em_portugues_sem_o_nome_em_ingles(self):
        resposta = self._recusar(
            "A senha é muito parecida com e-mail",
            password1="nova@ex.com1",
            password2="nova@ex.com1",
        )

        corpo = resposta.content.decode()
        self.assertNotIn("email address", corpo)
