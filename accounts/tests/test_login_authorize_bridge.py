"""TASK-007/T-06 — anonimo interrompido em /o/authorize/, resgatado pelo login, chega ao
consentimento sem reconstruir a query de autorizacao a mao.

Demanda do quality-assurance (bloco E). Nivel integracao: e a costura entre
LOGIN_URL por nome de rota, o `next` da LoginView e a view de autorizacao do
DOT — nenhuma peca isolada garante o fechamento do ciclo.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.tests.oauth_helpers import (
    REDIRECT_URI,
    create_public_rs256_application,
    make_pkce_pair,
)

User = get_user_model()


class LoginAuthorizeBridgeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="ponte@example.com", password="senha-forte-o-suficiente"
        )
        self.application = create_public_rs256_application(self.user)

    def test_anonimo_interrompido_em_authorize_fecha_login_e_chega_ao_consentimento(self):
        _verifier, challenge = make_pkce_pair()
        params = {
            "response_type": "code",
            "client_id": self.application.client_id,
            "redirect_uri": REDIRECT_URI,
            "scope": "openid profile email",
            "state": "ponte-state",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "nonce": "ponte-nonce",
        }

        # (1) anonimo em /o/authorize/: interrompido, mandado para o login nomeado.
        first = self.client.get("/o/authorize/", params)
        self.assertEqual(first.status_code, 302)
        location = first.get("Location")
        self.assertTrue(location.startswith("/accounts/login/"))
        self.assertIn("next=", location)

        # (2) a tela de login responde normalmente para esse next.
        login_page = self.client.get(location)
        self.assertEqual(login_page.status_code, 200)

        # (3) posta as credenciais no MESMO location (com o next na querystring):
        # LoginView.get_redirect_url le o next do POST ou do GET, entao postar
        # aqui escapa da armadilha do next HTML-escapado no hidden do template.
        login_post = self.client.post(
            location,
            {"username": "ponte@example.com", "password": "senha-forte-o-suficiente"},
        )
        self.assertEqual(login_post.status_code, 302)
        self.assertTrue(login_post.get("Location", "").startswith("/o/authorize/"))

        # (4) de volta a /o/authorize/, agora autenticado: tela de consentimento.
        consent_page = self.client.get(login_post.get("Location"))
        self.assertEqual(consent_page.status_code, 200)
        self.assertIn('name="allow"', consent_page.content.decode())
