"""T-03 — GET /o/.well-known/jwks.json.

Demanda do quality-assurance (TASK-006). Nível integração: o defeito que este
teste existe para pegar é a chave ausente em settings — o DOT engole isso em
silêncio e serve {"keys": []} com 200. Só a view revela o resultado. PEM
malformado não precisa de guarda aqui: levanta e vira 500 logado.
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
