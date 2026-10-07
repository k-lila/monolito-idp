"""TASK-028/T-10 — o mixin `EmPortugues` (`accounts/paginas.py`).

Demanda do quality-assurance (TASK-028). Nível unitário: a decisão cabe numa view de teste que
herda do mixin e de `TemplateView`, sem URLConf e sem banco.

O `TemplateResponse` renderiza depois de o `dispatch` retornar, já fora do `override`, e a
mensagem preguiçosa sairia em inglês sem erro nenhum. O caso fica vermelho se o
`resposta.render()` sair de dentro do `with`: a resposta chega ao teste ainda sem renderizar.
"""

from django.test import RequestFactory, SimpleTestCase, override_settings
from django.utils import translation
from django.views.generic import TemplateView

from accounts.paginas import EmPortugues

# Motor próprio, com o template em memória: o caso não depende de arquivo em `templates/`.
TEMPLATES_DO_CASO = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "OPTIONS": {
            "loaders": [
                (
                    "django.template.loaders.locmem.Loader",
                    {
                        "t10.html": '{% load i18n %}{% translate "This field is required." %}',
                    },
                )
            ]
        },
    }
]


class VistaDeTeste(EmPortugues, TemplateView):
    template_name = "t10.html"


@override_settings(TEMPLATES=TEMPLATES_DO_CASO)
class EmPortuguesTests(SimpleTestCase):
    def test_resposta_sai_renderizada_em_portugues_e_o_idioma_volta(self):
        antes = translation.get_language()
        self.assertEqual(antes, "en-us")

        resposta = VistaDeTeste.as_view()(RequestFactory().get("/"))

        # Renderizada dentro do `dispatch`, e não pelo handler depois dele.
        self.assertTrue(resposta.is_rendered)
        self.assertEqual(resposta.content.decode(), "Este campo é obrigatório.")
        self.assertEqual(translation.get_language(), antes)
