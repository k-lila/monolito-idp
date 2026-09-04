"""T-02 — GET /o/.well-known/openid-configuration.

Demanda do quality-assurance (TASK-006). Nível integração: o que pode quebrar
mora na costura entre OIDC_ISS_ENDPOINT, o prefixo do include em config/urls.py
é o reverse() do namespace do DOT — não em uma função isolável.
"""

from django.test import TestCase


class DiscoveryDocumentTests(TestCase):
    def test_issuer_e_endpoints_obrigatorios(self):
        response = self.client.get("/o/.well-known/openid-configuration")

        self.assertEqual(response.status_code, 200)
        body = response.json()

        # Igualdade exata, não substring: pega tanto {BASE_URL} sem o sufixo /o
        # quanto uma barra final indevida (rstrip ausente em OIDC_ISS_ENDPOINT).
        self.assertEqual(body["issuer"], "http://localhost:8000/o")

        for key in (
            "authorization_endpoint",
            "token_endpoint",
            "userinfo_endpoint",
            "jwks_uri",
        ):
            self.assertIn(key, body)
            self.assertTrue(body[key])

    def test_end_session_endpoint_ausente(self):
        """OIDC_RP_INITIATED_LOGOUT_ENABLED=False (settings): guarda contra flip
        silencioso no upgrade do DOT — o próprio default da lib está programado
        para virar True na 4.0 (comentário em config/settings.py)."""
        response = self.client.get("/o/.well-known/openid-configuration")

        self.assertNotIn("end_session_endpoint", response.json())

    def test_discovery_na_raiz_do_host_e_404(self):
        """As rotas do DOT vivem sob /o/ (ADR 0007) — na raiz não há view nenhuma."""
        response = self.client.get("/.well-known/openid-configuration")

        self.assertEqual(response.status_code, 404)
