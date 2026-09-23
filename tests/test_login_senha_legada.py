"""TASK-019/T-09 — o login não valida a política de senha (silêncio já registrado no
comentário de `AUTH_PASSWORD_VALIDATORS`, em `config/settings.py`): uma conta com senha fraca
criada por `create_user` — o caminho que a suíte e o `shell` usam, e que nenhuma das quatro
superfícies do T-08 protege — continua entrando.

Demanda do quality-assurance (TASK-019/Fase 7). Nível integração: a costura é entre
`AuthenticationForm`, `AXES_CLIENT_IP_CALLABLE` e a sessão — `authenticate()` isolado não
atravessa nada disso.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

User = get_user_model()


class LoginComSenhaLegadaFracaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="legada-t09@example.com", password="1234")

    def test_login_com_senha_fraca_legada_abre_sessao_e_a_senha_continua_a_mesma(self):
        resposta = self.client.post(
            "/accounts/login/", {"username": "legada-t09@example.com", "password": "1234"}
        )

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta.get("Location"), "/")
        self.assertIn("_auth_user_id", self.client.session)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("1234"))
