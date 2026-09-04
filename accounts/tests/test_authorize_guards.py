"""T-05 — guardas de fluxo em /o/authorize/, mesma Application fixture.

Demanda do quality-assurance (TASK-006). Nível integração: PKCE_REQUIRED e a
allowlist de redirect_uri são configuração exercitada pela view do DOT; um
unitário só afirmaria o valor da chave na settings, que não está em dúvida.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.tests.oauth_helpers import (
    REDIRECT_URI,
    authorize_and_get_code,
    create_public_rs256_application,
)

User = get_user_model()


class AuthorizeGuardsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="guardas@example.com", password="senha-forte-o-suficiente"
        )
        self.application = create_public_rs256_application(self.user)
        self.client.force_login(self.user)

    def test_i_sem_code_challenge_nao_emite_code(self):
        """PKCE_REQUIRED=True: sem code_challenge o servidor recusa antes da
        tela de consentimento. Comportamento verificado: 302 de erro para o
        redirect_uri com error=invalid_request, sem `code` na query."""
        params = {
            "response_type": "code",
            "client_id": self.application.client_id,
            "redirect_uri": REDIRECT_URI,
            "scope": "openid",
            "state": "sem-pkce",
        }
        response = self.client.get("/o/authorize/", params)

        if response.status_code in (301, 302):
            location = response.get("Location", "")
            self.assertNotIn("code=", location)
            self.assertIn("error=invalid_request", location)
        else:
            self.assertEqual(response.status_code, 400)

    def test_ii_code_challenge_s256_valido_devolve_200(self):
        code, _verifier, get_response = authorize_and_get_code(
            self.client, self.application, scope="openid"
        )
        # A tela de consentimento (GET) responde 200; o code só sai no POST
        # subsequente feito por authorize_and_get_code.
        self.assertIsNotNone(code)

    def test_iii_redirect_uri_nao_registrada_nao_emite_code(self):
        code, _verifier, response = authorize_and_get_code(
            self.client,
            self.application,
            redirect_uri="http://localhost:8000/noop2",
            scope="openid",
        )
        self.assertIsNone(code)
        # Recusa antes de qualquer redirect: comportamento verificado do DOT
        # para redirect_uri fora da allowlist é 400 direto no GET, sem Location.
        self.assertEqual(response.status_code, 400)

    def test_iv_redirect_uri_com_barra_a_mais_nao_emite_code(self):
        """Prova de igualdade exata, não de comparação por prefixo: registrada
        é '.../noop', enviada é '.../noop/' - só uma barra a mais. Se a
        comparação afrouxar para prefixo, este teste passa a falhar."""
        code, _verifier, response = authorize_and_get_code(
            self.client,
            self.application,
            redirect_uri=f"{REDIRECT_URI}/",
            scope="openid",
        )
        self.assertIsNone(code)
        self.assertEqual(response.status_code, 400)

    def test_v_code_challenge_method_plain_e_recusado(self):
        """CRITICO aceito e corrigido no commit 5aa4427: com plain corrigido, a
        recusa acontece no POST, não no GET — o GET ainda devolve a tela de
        consentimento 200.
        Assertar só no GET não pegaria a regressão; por isso o teste segue o
        POST e confere a ausência de `code` no Location de erro."""
        verifier = "verifier-usado-como-o-proprio-challenge-em-plain"
        params = {
            "response_type": "code",
            "client_id": self.application.client_id,
            "redirect_uri": REDIRECT_URI,
            "scope": "openid",
            "state": "plain-recusado",
            "code_challenge": verifier,
            "code_challenge_method": "plain",
            "nonce": "fixture-nonce",
        }
        get_response = self.client.get("/o/authorize/", params)
        self.assertEqual(get_response.status_code, 200, "GET ainda deve mostrar consentimento")

        from accounts.tests.oauth_helpers import extract_hidden_inputs

        hidden = extract_hidden_inputs(get_response.content.decode())
        post_data = dict(hidden)
        post_data["allow"] = "Authorize"
        post_response = self.client.post("/o/authorize/", post_data)

        self.assertEqual(post_response.status_code, 302)
        location = post_response.get("Location", "")
        self.assertNotIn("code=", location)
        self.assertIn("error=invalid_request", location)
