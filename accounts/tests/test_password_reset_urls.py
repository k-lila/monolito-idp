"""TASK-007/T-05 — /accounts/password_reset/ e /accounts/password_reset/done/ nao existem.

Demanda do quality-assurance (bloco E). Nivel integracao: a proibicao escrita no
passo 09 e nao incluir `django.contrib.auth.urls` — quatro rotas de recuperacao
de senha sem template, cada uma um 500 esperando um clique. Dois casos bastam
para pegar o include inteiro voltando; as outras seis rotas do mesmo include nao
acrescentam informacao nova.
"""

from django.test import TestCase


class PasswordResetUrlsAusentesTests(TestCase):
    def test_password_reset_e_404(self):
        response = self.client.get("/accounts/password_reset/")
        self.assertEqual(response.status_code, 404)

    def test_password_reset_done_e_404(self):
        response = self.client.get("/accounts/password_reset/done/")
        self.assertEqual(response.status_code, 404)
