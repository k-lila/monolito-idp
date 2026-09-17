"""TASK-008/T-01 — nenhuma das três telas serve texto de comentário de template no corpo.

Demanda do quality-assurance: `{# ... #}` é comentário de uma linha só no Django. Com o
`#}` em outra linha, o tokenizer não reconhece o token e o texto sai renderizado como
conteúdo. Quando a TASK-008 abriu, o projeto tinha seis comentários `{# ... #}`
multi-linha e cinco vazavam assim; o sexto — o do topo de `authorize.html`, fora de
qualquer `{% block %}` num template que faz `{% extends %}` — não vazava, porque o
`ExtendsNode` descarta todo texto literal fora de bloco nesse tipo de template e aquele
comentário nunca chegava a ser emitido. Era defeito latente, não ativo: passaria a vazar
no dia em que alguém o movesse para dentro de um `{% block %}`.

Hoje os templates não têm comentário `{# #}` nenhum, nem de uma linha nem multi-linha. O
que este módulo guarda é a volta do defeito: um comentário multi-linha acrescentado a
qualquer das três telas volta a vazar pelo mesmo caminho. Ver docstring de
`AuthorizeConsentTemplateCommentLeakTests` abaixo.

Nível integração: o que pode quebrar é a costura entre a sintaxe do template e o que o
motor de renderização emite — nenhuma peça isolável revela isso, só a resposta HTTP.

Módulo novo, não espalhado pelos três módulos existentes (test_login_view.py,
test_authorize_consent.py, test_login_authorize_bridge.py): as três telas compartilham o
mesmo critério de aceite (ausência dos delimitadores `{#`/`#}` no corpo), e um módulo só
deixa essa repetição de asserção explícita em vez de diluída em classes que já existem por
outro motivo. Reusa as fixtures de tests/oauth_helpers.py em vez de duplica-las.

Critério: assere pelos delimitadores `{#` e `#}`, nunca pelo texto de um comentário
específico — o texto é documentação viva e muda; os delimitadores nunca podem aparecer
numa resposta renderizada.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from tests.oauth_helpers import (
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
    """/accounts/login/, anônimo — cobre duas posições de uma vez: o corpo de base.html,
    fora de qualquer bloco, e o `{% block content %}` de login.html. Quatro dos cinco
    vazamentos que a TASK-008 encontrou estavam aí."""

    def test_login_anonimo_nao_vaza_comentario_de_template(self):
        response = self.client.get("/accounts/login/")

        self.assertEqual(response.status_code, 200)
        assert_no_template_comment_delimiters(self, response.content.decode())


class HomeAuthenticatedTemplateCommentLeakTests(TestCase):
    """/, com sessão ativa — única superfície que renderiza o ramo
    `{% if user.is_authenticated %}` do cabeçalho de base.html, onde estava o quinto
    vazamento da TASK-008. Sem sessão ativa esse ramo não entra na renderização, e nada
    que ele contenha pode vazar."""

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

    O topo de authorize.html, fora de qualquer `{% block %}` num template que faz
    `{% extends %}`, é posição cega: o `ExtendsNode` descarta todo texto literal que
    esteja ali, e o que ocupa essa posição nunca chega a ser emitido. Era onde vivia o
    sexto comentário da TASK-008, o único que não vazava. O que este caso alcança é o
    corpo herdado de base.html, que toda tela que o estende carrega, consentimento
    inclusive.

    O valor do caso não é redundância com o de login: um comentário multi-linha
    acrescentado ao `{% block %}` desta tela — para documentar algo do formulário,
    digamos — vaza sem que nenhuma outra tela acuse, e só um teste que a renderize de
    verdade pega isso."""

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
