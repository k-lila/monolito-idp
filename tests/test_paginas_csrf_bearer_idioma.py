"""TASK-028/T-57 — CSRF, Bearer, idioma, "Cancelar" e `Cache-Control` das páginas de conta.

Demanda do quality-assurance. Nível integração.

CSRF: com `Client(enforce_csrf_checks=True)`, o POST sem token recebe 403 em login, cadastro,
recuperação, troca de senha, troca de e-mail e exclusão. As páginas são de sessão, e o
middleware do Django é a única defesa contra o formulário forjado em outra origem.

Bearer: um `Authorization: Bearer` válido não abre as páginas de sessão. GET e POST em
`/accounts/password_change/`, `/accounts/email/` e `/accounts/excluir/` redirecionam ao login e
não mudam a conta: o token é da API, não da sessão.

Idioma: o `LANGUAGE_CODE` segue `en-us` (com `pt-br`, o `error_description` do protocolo sairia
acentuado, fora da RFC 6749), e o português vale só nas páginas, por `EmPortugues`. O atributo
`lang` não prova isso: é constante do `base.html` e sai igual com ou sem `EmPortugues`. A prova é
a mensagem de erro do formulário, em português e sem a inglesa, num POST inválido de recuperação,
redefinição, troca de e-mail e exclusão, as quatro páginas em que só ela revela a ausência da
tradução. As demais têm a mensagem afirmada nos testes de cada página. A recusa 403 da exclusão
e o "Cancelar" das três páginas de sessão (`{SPA_URL}/app/conta`) seguem aqui.

Cache: o cadastro, a troca de e-mail e a exclusão saem com `no-store` (`never_cache`): a página
que pede a senha, ou a que o anônimo preenche, não fica no cache do navegador nem de um proxy.

Vermelho se algum POST passar sem CSRF, se o Bearer valer nas páginas, se uma das quatro páginas
perder o `EmPortugues`, ou se o `never_cache` sair de uma das três views.
"""

import html
import re

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.test import Client
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from tests.api_conta_helpers import bearer, criar_token
from tests.paginas_helpers import (
    EMAIL,
    NOVA,
    SENHA,
    PaginasDeContaTestCase,
    User,
)

PAGINAS_DE_SESSAO = ("/accounts/password_change/", "/accounts/email/", "/accounts/excluir/")


class CsrfTests(PaginasDeContaTestCase):
    def test_post_sem_token_e_403_nas_seis_paginas(self):
        estrito = Client(enforce_csrf_checks=True)
        estrito.force_login(self.conta)
        casos = {
            "/accounts/login/": {"username": EMAIL, "password": SENHA},
            "/accounts/registrar/": {"email": "nova@ex.com"},
            "/accounts/password_reset/": {"email": EMAIL},
            "/accounts/password_change/": {
                "old_password": SENHA, "new_password1": NOVA, "new_password2": NOVA,
            },  # fmt: skip
            "/accounts/email/": {"novo_email": "novo@ex.com", "senha": SENHA},
            "/accounts/excluir/": {"modo": "desativar", "confirmo": "on", "senha": SENHA},
        }
        for caminho, dados in casos.items():
            with self.subTest(caminho=caminho):
                self.assertEqual(estrito.post(caminho, dados).status_code, 403)

        conta = User.objects.get(pk=self.conta.pk)
        self.assertEqual(conta.email, EMAIL)
        self.assertTrue(conta.is_active)
        self.assertTrue(conta.check_password(SENHA))
        self.assertFalse(User.objects.filter(email="nova@ex.com").exists())


class BearerTests(PaginasDeContaTestCase):
    def test_o_bearer_valido_nao_abre_as_paginas_de_sessao(self):
        token = criar_token(self.conta, self.app1)
        anonimo = Client()
        for caminho in PAGINAS_DE_SESSAO:
            for metodo in ("get", "post"):
                with self.subTest(caminho=caminho, metodo=metodo):
                    enviar = getattr(anonimo, metodo)
                    dados = (
                        {
                            "old_password": SENHA, "new_password1": NOVA, "new_password2": NOVA,
                            "novo_email": "novo@ex.com", "senha": SENHA,
                            "modo": "desativar", "confirmo": "on",
                        }  # fmt: skip
                        if metodo == "post"
                        else {}
                    )
                    resposta = enviar(caminho, dados, **bearer(token))

                    self.assertEqual(resposta.status_code, 302)
                    self.assertTrue(
                        resposta["Location"].startswith("/accounts/login/"), resposta["Location"]
                    )
        conta = User.objects.get(pk=self.conta.pk)
        self.assertEqual(conta.email, EMAIL)
        self.assertTrue(conta.is_active)
        self.assertTrue(conta.check_password(SENHA))


class IdiomaECancelarTests(PaginasDeContaTestCase):
    def test_o_projeto_segue_em_ingles_e_cada_pagina_sai_em_portugues(self):
        self.assertEqual(settings.LANGUAGE_CODE, "en-us")
        equipe = User.objects.create_user("staff@ex.com", SENHA, is_staff=True)
        anonimas = [
            "/accounts/login/",
            "/accounts/registrar/",
            "/accounts/password_reset/",
            "/accounts/password_reset/done/",
            "/accounts/reset/MQ/x/",
            "/accounts/reset/done/",
        ]
        for caminho in anonimas:
            with self.subTest(caminho=caminho):
                resposta = Client().get(caminho)
                self.assertEqual(resposta.status_code, 200)
                self.assertIn('<html lang="pt-br">', resposta.content.decode())

        sessao = Client()
        sessao.force_login(self.conta)
        for caminho in PAGINAS_DE_SESSAO:
            with self.subTest(caminho=caminho):
                resposta = sessao.get(caminho)
                self.assertEqual(resposta.status_code, 200)
                self.assertIn('<html lang="pt-br">', resposta.content.decode())

        da_equipe = Client()
        da_equipe.force_login(equipe)
        recusa = da_equipe.get("/accounts/excluir/")
        self.assertEqual(recusa.status_code, 403)
        self.assertIn('<html lang="pt-br">', recusa.content.decode())

    def test_a_mensagem_de_erro_sai_em_portugues_e_sem_a_inglesa_nas_quatro_paginas(self):
        """T-66. Vermelho sem `EmPortugues` em qualquer das quatro."""
        sessao = Client()
        sessao.force_login(self.conta)
        # Depois do login: o token do Django deriva de `last_login`, e o login o muda.
        conta = User.objects.get(pk=self.conta.pk)
        uid = urlsafe_base64_encode(force_bytes(conta.pk))
        navegador = Client()
        passo1 = navegador.get(f"/accounts/reset/{uid}/{default_token_generator.make_token(conta)}/")
        self.assertEqual(passo1.status_code, 302)
        casos = {
            "recuperacao": (
                Client(),
                "/accounts/password_reset/",
                {"email": "x"},
                ["Informe um endereço de email válido."],
                ["Enter a valid email address."],
            ),
            "redefinicao": (
                navegador,
                passo1["Location"],
                {"new_password1": NOVA, "new_password2": NOVA + "x"},
                ["Os dois campos de senha não correspondem."],
                ["The two password fields didn"],
            ),
            "troca de e-mail": (
                sessao,
                "/accounts/email/",
                {"novo_email": "x"},
                ["Informe um endereço de email válido.", "Este campo é obrigatório."],
                ["Enter a valid email address.", "This field is required."],
            ),
            "exclusao": (
                sessao,
                "/accounts/excluir/",
                {"modo": "desativar"},
                ["Este campo é obrigatório."],
                ["This field is required."],
            ),
        }
        for nome, (cliente, caminho, dados, em_pt, em_en) in casos.items():
            with self.subTest(pagina=nome):
                resposta = cliente.post(caminho, dados)

                self.assertEqual(resposta.status_code, 200)
                corpo = html.unescape(resposta.content.decode())
                for texto in em_pt:
                    self.assertIn(texto, corpo)
                for texto in em_en:
                    self.assertNotIn(texto, corpo)

    def test_cancelar_volta_a_area_de_conta_da_spa_nas_tres(self):
        sessao = Client()
        sessao.force_login(self.conta)
        for caminho in PAGINAS_DE_SESSAO:
            with self.subTest(caminho=caminho):
                corpo = sessao.get(caminho).content.decode()

                destinos = re.findall(r'<a class="botao" href="([^"]*)">Cancelar</a>', corpo)
                self.assertEqual(destinos, [f"{self.spa}/app/conta"])


class SemCacheTests(PaginasDeContaTestCase):
    def test_cadastro_troca_de_email_e_exclusao_saem_com_no_store(self):
        sessao = Client()
        sessao.force_login(self.conta)
        casos = (
            (Client(), "/accounts/registrar/"),
            (sessao, "/accounts/email/"),
            (sessao, "/accounts/excluir/"),
        )
        for cliente, caminho in casos:
            with self.subTest(caminho=caminho):
                resposta = cliente.get(caminho)

                self.assertIn("no-store", resposta["Cache-Control"])
