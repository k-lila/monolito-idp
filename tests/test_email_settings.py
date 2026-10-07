"""TASK-028/T-24 — as oito variáveis de e-mail são obrigatórias na carga de `config/settings.py`.

Demanda do quality-assurance. Nível unitário, sem banco, pelo precedente de
`tests/test_spa_url.py`: o módulo de settings é executado de novo por `runpy.run_path`, com
`read_env` neutralizado (o `.env` do clone não repõe, por baixo do `patch.dict`, a variável que
o caso removeu) e `os.environ` sobrescrito sem `clear=True`, porque as demais já estão lá.

A mensagem é conferida por fronteira de palavra: `EMAIL_HOST` é prefixo de `EMAIL_HOST_USER`, e
um `assertIn` simples aprovaria a mensagem de uma pela outra. Falha se qualquer uma ganhar
default, ou sair do `.env.example`.
"""

import os
import re
import runpy
from unittest import mock

import environ
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

CAMINHO_SETTINGS = settings.BASE_DIR / "config" / "settings.py"
CAMINHO_ENV_EXAMPLE = settings.BASE_DIR / ".env.example"

VARIAVEIS = [
    "EMAIL_BACKEND",
    "EMAIL_HOST",
    "EMAIL_PORT",
    "EMAIL_HOST_USER",
    "EMAIL_HOST_PASSWORD",
    "EMAIL_USE_TLS",
    "EMAIL_TIMEOUT",
    "DEFAULT_FROM_EMAIL",
]


def carregar_sem(variavel):
    with mock.patch.object(environ.Env, "read_env"), mock.patch.dict(
        os.environ, {"BEHIND_TLS_PROXY": "False"}
    ):
        os.environ.pop(variavel, None)
        return runpy.run_path(str(CAMINHO_SETTINGS))


class EmailObrigatorioTests(SimpleTestCase):
    def test_a_ausencia_de_cada_variavel_derruba_a_carga_nomeando_a_si_mesma(self):
        for nome in VARIAVEIS:
            with self.subTest(nome):
                with self.assertRaises(ImproperlyConfigured) as ctx:
                    carregar_sem(nome)
                self.assertRegex(str(ctx.exception), rf"\b{nome}\b")

    def test_o_env_example_lista_as_oito_com_o_backend_de_console(self):
        linhas = CAMINHO_ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()
        valores = dict(
            linha.split("=", 1) for linha in linhas if re.match(r"^[A-Z_]+=", linha)
        )
        for nome in VARIAVEIS:
            self.assertIn(nome, valores, f"{nome} fora do .env.example")
        self.assertEqual(
            valores["EMAIL_BACKEND"], "django.core.mail.backends.console.EmailBackend"
        )
