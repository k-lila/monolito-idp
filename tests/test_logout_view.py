"""TASK-007/T-04 — /accounts/logout/, dois métodos sobre o mesmo usuário logado.

Demanda do quality-assurance (bloco E). Nível integração: a guarda que importa
e (b) — falha se um dia alguém publicar um logout que aceite GET, cenário do
AC-05 (CSRF por logout via link/imagem).
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

User = get_user_model()


class LogoutViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="logout@example.com", password="senha-forte-o-suficiente"
        )
        self.client.force_login(self.user)

    def test_a_post_logout_encerra_sessao_e_redireciona_para_home(self):
        response = self.client.post("/accounts/logout/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.get("Location"), "/")
        self.assertNotIn("_auth_user_id", self.client.session)

        home_response = self.client.get("/")
        self.assertNotIn(self.user.email, home_response.content.decode())

    def test_b_get_logout_e_405_e_preserva_a_sessao(self):
        """A guarda central de TASK-007/T-04: GET não pode encerrar sessão. Um logout que
        aceitasse GET tornaria a home (ou qualquer <img src="/accounts/logout/">)
        um vetor de logout forjado."""
        response = self.client.get("/accounts/logout/")

        self.assertEqual(response.status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)
