"""TASK-008/T-01 — nenhuma das três telas serve texto de comentário de template no corpo.

Demanda do quality-assurance: `{# ... #}` é comentário de uma linha só no Django. Com o
`#}` em outra linha, o tokenizer não reconhece o token e o texto sai renderizado como
conteúdo. Dos seis comentários `{# ... #}` multi-linha do projeto, cinco vazam assim. O
sexto — o do topo de `authorize.html`, fora de qualquer `{% block %}` num template que faz
`{% extends %}` — nunca vaza: o `ExtendsNode` descarta todo texto literal fora de bloco
nesse tipo de template, então esse comentário nunca chega a ser emitido. E defeito
latente, não ativo: passaria a vazar no dia em que alguém o movesse para dentro de um
`{% block %}`. Ver docstring de `AuthorizeConsentTemplateCommentLeakTests` abaixo.

Nível integração: o que pode quebrar é a costura entre a sintaxe do template e o que o
motor de renderização emite — nenhuma peça isolável revela isso, só a resposta HTTP.

Módulo novo, não espalhado pelos três módulos existentes (test_login_view.py,
test_authorize_consent.py, test_login_authorize_bridge.py): as três telas compartilham o
mesmo critério de aceite (ausência dos delimitadores `{#`/`#}` no corpo), e um módulo só
deixa essa repetição de asserção explícita em vez de diluída em classes que já existem por
outro motivo. Reusa as fixtures de accounts/tests/oauth_helpers.py em vez de duplica-las.

Critério: assere pelos delimitadores `{#` e `#}`, nunca pelo texto de um comentário
específico — o texto é documentação viva e muda; os delimitadores nunca podem aparecer
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

    Delimitador, nunca texto: o conteúdo dos comentários é reescrito com o tempo, os
    delimitadores não podem aparecer numa resposta de verdade em hipótese nenhuma.
    """
    testcase.assertNotIn("{#", html)
    testcase.assertNotIn("#}", html)


class LoginPageTemplateCommentLeakTests(TestCase):
    """/accounts/login/, anônimo — pega o comentário herdado de base.html no topo do
    <body>, fora de qualquer bloco, mais os três que vivem dentro do
    `{% block content %}` de login.html."""

    def test_login_anonimo_nao_vaza_comentario_de_template(self):
        response = self.client.get("/accounts/login/")

        self.assertEqual(response.status_code, 200)
        assert_no_template_comment_delimiters(self, response.content.decode())


class HomeAuthenticatedTemplateCommentLeakTests(TestCase):
    """/, com sessão ativa — única superfície que exercita o comentário de base.html que
    vive dentro do ramo `{% if user.is_authenticated %}` do cabeçalho; sem sessão ativa
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
    """/o/authorize/, usuário logado e requisição válida.

    Não pega o comentário que abre authorize.html: ele fica fora de qualquer
    `{% block %}` num template que faz `{% extends %}`, e o `ExtendsNode` descarta
    todo texto literal nessa posição — nunca chega a ser emitido. O que este caso
    de fato pega é o comentário herdado de base.html no topo do <body>, que toda
    tela que estende base.html carrega, consentimento inclusive.

    O valor do caso não é redundância com o de login: é a guarda contra o defeito
    latente de authorize.html — se um dia alguém mover aquele comentário para dentro
    de um `{% block %}` (ex.: para documentar algo específico do formulário), ele
    passa a vazar, e só um teste que renderiza esta tela de verdade pega isso."""

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
