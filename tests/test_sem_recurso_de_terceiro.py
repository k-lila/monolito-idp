"""TASK-026/T-07 — o IdP não carrega recurso de terceiro nas telas.

Demanda do quality-assurance. Nível unitário, sem banco: leitura de texto de `static/css/idp.css`
e de `templates/**/*.html`. A razão é a da política de conteúdo do IdP: tela de login que busca
CSS, fonte ou script em outro domínio entrega ao terceiro o endereço de quem se autentica e
abre a página a código que o projeto não controla.

Passa hoje e falha se entrar `@import` (o do Tailwind, por exemplo), fonte por `url()` ou
`<script src="https://...">`. Regex sobre texto, e não parser: o critério é a presença do
padrão, e um falso positivo aqui é uma pergunta que vale a pena responder.
"""

import re

from django.conf import settings
from django.test import SimpleTestCase

CSS = settings.BASE_DIR / "static" / "css" / "idp.css"
TEMPLATES = sorted((settings.BASE_DIR / "templates").rglob("*.html"))
ABSOLUTO = re.compile(r"""\b(?:href|src)\s*=\s*["']?\s*(?:https?:)?//""", re.IGNORECASE)
LINK = re.compile(r"<link\b[^>]*>", re.IGNORECASE)


class SemRecursoDeTerceiroTests(SimpleTestCase):
    def test_ha_templates_a_verificar(self):
        # Sem isto, um caminho errado faria os demais passarem sobre lista vazia.
        self.assertTrue(CSS.is_file())
        self.assertGreaterEqual(len(TEMPLATES), 5)

    def test_css_sem_import_nem_url(self):
        texto = CSS.read_text(encoding="utf-8")
        self.assertNotIn("@import", texto)
        self.assertNotIn("url(", texto.lower())

    def test_templates_sem_script(self):
        for caminho in TEMPLATES:
            with self.subTest(template=caminho.name):
                self.assertNotRegex(caminho.read_text(encoding="utf-8"), r"(?i)<script\b")

    def test_templates_sem_endereco_absoluto_em_href_ou_src(self):
        for caminho in TEMPLATES:
            with self.subTest(template=caminho.name):
                self.assertIsNone(ABSOLUTO.search(caminho.read_text(encoding="utf-8")))

    def test_unico_link_e_o_stylesheet_de_static(self):
        links = []
        for caminho in TEMPLATES:
            links += LINK.findall(caminho.read_text(encoding="utf-8"))
        self.assertEqual(len(links), 1, links)
        self.assertIn('rel="stylesheet"', links[0])
        self.assertIn("{% static ", links[0])
