"""TASK-007/T-05 — /accounts/password_reset/ e /accounts/password_reset/done/ não existem.

Demanda do quality-assurance (bloco E). Nível integração: a proibição escrita no
passo 09 é não incluir `django.contrib.auth.urls` — quatro rotas de recuperação
de senha sem template, cada uma um 500 esperando um clique. Dois casos bastam
para pegar o include inteiro voltando; as outras seis rotas do mesmo include não
acrescentam informação nova.
"""

from django.test import TestCase


class PasswordResetUrlsAusentesTests(TestCase):
    def test_password_reset_e_404(self):
        response = self.client.get("/accounts/password_reset/")
        self.assertEqual(response.status_code, 404)

    def test_password_reset_done_e_404(self):
        response = self.client.get("/accounts/password_reset/done/")
        self.assertEqual(response.status_code, 404)
