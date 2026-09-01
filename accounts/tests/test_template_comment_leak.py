"""TASK-008/T-01 — nenhuma das tres telas serve texto de comentario de template no corpo.

Demanda do quality-assurance: `{# ... #}` e comentario de uma linha so no Django. Com o
`#}` em outra linha, o tokenizer nao reconhece o token e o texto sai renderizado como
conteudo. Dos seis comentarios `{# ... #}` multi-linha do projeto, cinco vazam assim. O
sexto — o do topo de `authorize.html`, fora de qualquer `{% block %}` num template que faz
`{% extends %}` — nunca vaza: o `ExtendsNode` descarta todo texto literal fora de bloco
nesse tipo de template, entao esse comentario nunca chega a ser emitido. E defeito
latente, nao ativo: passaria a vazar no dia em que alguem o movesse para dentro de um
`{% block %}`. Ver docstring de `AuthorizeConsentTemplateCommentLeakTests` abaixo.

Nivel integracao: o que pode quebrar e a costura entre a sintaxe do template e o que o
motor de renderizacao emite — nenhuma peca isolavel revela isso, so a resposta HTTP.

Modulo novo, nao espalhado pelos tres modulos existentes (test_login_view.py,
test_authorize_consent.py, test_login_authorize_bridge.py): as tres telas compartilham o
mesmo criterio de aceite (ausencia dos delimitadores `{#`/`#}` no corpo), e um modulo so
deixa essa repeticao de asserção explicita em vez de diluida em classes que ja existem por
outro motivo. Reusa as fixtures de accounts/tests/oauth_helpers.py em vez de duplica-las.

Criterio: assere pelos delimitadores `{#` e `#}`, nunca pelo texto de um comentario
especifico — o texto e documentacao viva e muda; os delimitadores nunca podem aparecer
numa resposta renderizada.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.tests.oauth_helpers import (
    REDIRECT_URI,
    create_public_rs256_application,
    make_pkce_pair,
)

User = get_user_model()


def assert_no_template_comment_delimiters(testcase, html):
    """Nenhum `{#` ou `#}` sobrevive no HTML renderizado.

    Delimitador, nunca texto: o conteudo dos comentarios e reescrito com o tempo, os
    delimitadores nao podem aparecer numa resposta de verdade em hipotese nenhuma.
    """
    testcase.assertNotIn("{#", html)
    testcase.assertNotIn("#}", html)


class LoginPageTemplateCommentLeakTests(TestCase):
    """/accounts/login/, anonimo — pega o comentario herdado de base.html no topo do
    <body>, fora de qualquer bloco, mais os tres que vivem dentro do
    `{% block content %}` de login.html."""

    def test_login_anonimo_nao_vaza_comentario_de_template(self):
        response = self.client.get("/accounts/login/")

        self.assertEqual(response.status_code, 200)
        assert_no_template_comment_delimiters(self, response.content.decode())


class HomeAuthenticatedTemplateCommentLeakTests(TestCase):
    """/, com sessao ativa — unica superficie que exercita o comentario de base.html que
    vive dentro do ramo `{% if user.is_authenticated %}` do cabecalho; sem sessao ativa
    esse ramo nem entra no template e nada haveria para vazar."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="vazamento-home@example.com", password="senha-forte-o-suficiente"
        )

    def test_home_com_sessao_ativa_nao_vaza_comentario_de_template(self):
        self.client.force_login(self.user)
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        assert_no_template_comment_delimiters(self, response.content.decode())


class AuthorizeConsentTemplateCommentLeakTests(TestCase):
    """/o/authorize/, usuario logado e requisicao valida.

    Nao pega o comentario que abre authorize.html: ele fica fora de qualquer
    `{% block %}` num template que faz `{% extends %}`, e o `ExtendsNode` descarta
    todo texto literal nessa posicao — nunca chega a ser emitido. O que este caso
    de fato pega e o comentario herdado de base.html no topo do <body>, que toda
    tela que estende base.html carrega, consentimento inclusive.

    O valor do caso nao e redundancia com o de login: e a guarda contra o defeito
    latente de authorize.html — se um dia alguem mover aquele comentario para dentro
    de um `{% block %}` (ex.: para documentar algo especifico do formulario), ele
    passa a vazar, e so um teste que renderiza esta tela de verdade pega isso."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="vazamento-consentimento@example.com",
            password="senha-forte-o-suficiente",
        )
        self.application = create_public_rs256_application(self.user)
        self.client.force_login(self.user)

    def test_tela_de_consentimento_nao_vaza_comentario_de_template(self):
        _verifier, challenge = make_pkce_pair()
        params = {
            "response_type": "code",
            "client_id": self.application.client_id,
            "redirect_uri": REDIRECT_URI,
            "scope": "openid",
            "state": "vazamento-state",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "nonce": "vazamento-nonce",
        }

        response = self.client.get("/o/authorize/", params)

        self.assertEqual(response.status_code, 200)
        assert_no_template_comment_delimiters(self, response.content.decode())
