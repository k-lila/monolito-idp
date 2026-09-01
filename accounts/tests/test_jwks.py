"""T-03 — GET /o/.well-known/jwks.json.

Demanda do quality-assurance (TASK-006). Nivel integracao: o defeito que este
teste existe para pegar e a chave PEM chegar malformada a settings (`\\n`
literais de uma segunda leitura do ambiente sem multiline=True) — o DOT engole
isso em silencio e serve {"keys": []}. So a view revela o resultado.
"""

from django.test import TestCase


class JwksDocumentTests(TestCase):
    def test_uma_chave_rsa_com_kid(self):
        response = self.client.get("/o/.well-known/jwks.json")

        self.assertEqual(response.status_code, 200)
        body = response.json()

        self.assertEqual(len(body["keys"]), 1)
        key = body["keys"][0]
        self.assertEqual(key["kty"], "RSA")
        self.assertTrue(key["kid"])
