"""TASK-007/T-01, TASK-007/T-02, TASK-007/T-03 — GET/POST /accounts/login/, sem sessão prévia.

Demanda do quality-assurance (bloco E). Nível integração nos três: o que pode
quebrar é a costura entre template, rota nomeada, staticfiles e o
AuthenticationForm, nunca uma peça isolada.
"""

from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.test import TestCase

User = get_user_model()


class LoginPageRendersTests(TestCase):
    """TASK-007/T-01 — a tela de login serve o form certo e referencia um CSS que existe."""

    def test_get_login_sem_sessao_traz_form_e_link_de_css_resolvido(self):
        response = self.client.get("/accounts/login/")

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()

        # Campo chama-se `username` mesmo com USERNAME_FIELD = "email" (armadilha
        # do enunciado): postar "email" no form devolveria 200 com form inválido,
        # nunca a autenticação pretendida.
        self.assertIn('name="username"', html)
        self.assertIn('name="password"', html)

        # A URL que {% static %} resolveu de verdade em runtime, não um literal
        # duplicado no teste — se STATIC_URL ou STORAGES mudar, o teste acompanha.
        self.assertIn(static("css/idp.css"), html)

        # O arquivo-fonte existe no STATICFILES_DIRS: se a folha for apagada, esta
        # guarda cai antes de qualquer coisa depender de collectstatic/WhiteNoise.
        self.assertIsNotNone(finders.find("css/idp.css"))


class LoginSuccessTests(TestCase):
    """TASK-007/T-02 — credenciais corretas estabelecem sessão e redirecionam para home."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="login-ok@example.com",
            password="senha-forte-o-suficiente",
            first_name="Krishna",
            last_name="Lila",
        )

    def test_post_credenciais_validas_redireciona_para_home_e_abre_sessao(self):
        response = self.client.post(
            "/accounts/login/",
            {"username": "login-ok@example.com", "password": "senha-forte-o-suficiente"},
        )

        self.assertEqual(response.status_code, 302)
        # Explícito, sem follow=True: é a linha que pegaria a regressão para o
        # default /accounts/profile/ (que nem existe neste projeto).
        self.assertEqual(response.get("Location"), "/")
        self.assertIn("_auth_user_id", self.client.session)

        home_response = self.client.get("/")
        self.assertEqual(home_response.status_code, 200)
        self.assertIn(self.user.email, home_response.content.decode())


class LoginFailureTests(TestCase):
    """TASK-007/T-03 — senha incorreta não autentica e não estabelece sessão."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="login-falha@example.com",
            password="senha-forte-o-suficiente",
        )

    def test_post_senha_incorreta_nao_abre_sessao_e_mostra_erro_do_form(self):
        response = self.client.post(
            "/accounts/login/",
            {"username": "login-falha@example.com", "password": "senha-errada"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

        # Marcador estrutural (classe CSS do form / lista de erros do form no
        # contexto), nunca o texto da mensagem: ela está em inglês hoje
        # (LANGUAGE_CODE = "en-us") e mudaria com uma correção legítima de i18n.
        # "errorlist nonfield": é o non_field_errors do AuthenticationForm — a
        # credencial inválida reprova o form inteiro, não um campo específico.
        self.assertIn("errorlist", response.content.decode())
        self.assertTrue(response.context["form"].errors)
