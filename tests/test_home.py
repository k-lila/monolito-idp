"""TASK-026/T-04, T-05 e T-06 — o botão "Ir para a aplicação" da home.

Demanda do quality-assurance. Nível integração: o valor sai de `settings.SPA_URL`, passa pela
view `home` e chega ao `href` renderizado; só a resposta HTTP mostra a costura inteira.

O `<a>` é extraído por `html.parser`, nunca por substring solta: o critério é o `href` byte a
byte, e a ausência de `target` (o botão navega na mesma aba) e de `?` (nenhum parâmetro é
acrescentado à origem).
"""

from html.parser import HTMLParser

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

User = get_user_model()

SPA = "https://spa.exemplo.test"
TEXTO = "Ir para a aplicação"


class _ColetaLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []  # (atributos, texto)
        self._atual = None

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._atual = [dict(attrs), ""]

    def handle_data(self, data):
        if self._atual is not None:
            self._atual[1] += data

    def handle_endtag(self, tag):
        if tag == "a" and self._atual is not None:
            self.links.append((self._atual[0], self._atual[1].strip()))
            self._atual = None


def links_do_botao(html):
    coleta = _ColetaLinks()
    coleta.feed(html)
    return [attrs for attrs, texto in coleta.links if texto == TEXTO]


class _BotaoMixin:
    def assertBotaoParaSpa(self, corpo):
        botoes = links_do_botao(corpo)
        self.assertEqual(len(botoes), 1)
        self.assertEqual(botoes[0].get("href"), SPA)
        self.assertNotIn("target", botoes[0])
        self.assertNotIn("?", botoes[0]["href"])


@override_settings(SPA_URL=SPA)
class HomeAnonimaTests(_BotaoMixin, TestCase):
    """T-04."""

    def test_home_anonima_traz_o_botao_e_o_convite_ao_login(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        corpo = response.content.decode()
        self.assertBotaoParaSpa(corpo)
        self.assertIn("Nenhuma sessão ativa", corpo)
        self.assertIn("Entrar", corpo)


@override_settings(SPA_URL=SPA)
class HomeComSessaoTests(_BotaoMixin, TestCase):
    """T-05 — o botão está fora do `{% if user.is_authenticated %}`: os dois estados o têm."""

    def test_home_com_sessao_traz_o_botao_o_email_e_o_sair(self):
        user = User.objects.create_user(
            email="home@example.com", password="senha-forte-o-suficiente"
        )
        self.client.force_login(user)

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        corpo = response.content.decode()
        self.assertBotaoParaSpa(corpo)
        self.assertIn("Sessão ativa como", corpo)
        self.assertIn("home@example.com", corpo)
        self.assertIn("Sair", corpo)


@override_settings(SPA_URL="https://sentinela-spa.exemplo.test")
class LoginNaoTemOBotaoTests(TestCase):
    """T-06 — o botão é só da home. Falha se `SPA_URL` for posta em `base.html` ou num
    context processor, que a levariam a toda tela."""

    def test_login_nao_traz_o_botao_nem_o_endereco_da_spa(self):
        response = self.client.get("/accounts/login/")

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, TEXTO)
        self.assertNotContains(response, "sentinela-spa")
