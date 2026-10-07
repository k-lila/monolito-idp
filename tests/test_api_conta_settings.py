"""TASK-028/T-37 — `SPA_CLIENT_ID` e `TERMOS_VERSAO_VIGENTE` na carga de `config/settings.py`.

Demanda do quality-assurance. Nível unitário, sem banco, no molde de `tests/test_spa_url.py`:
cada caso executa o módulo de settings de novo por `runpy.run_path`, com o ambiente do processo
sobrescrito, porque `override_settings` só enxergaria o valor já carregado.

O `read_env` é neutralizado para o `.env` do clone não repor, por baixo do `patch.dict`, o
valor que o caso quer. Sem `clear=True`: as demais variáveis obrigatórias já estão em
`os.environ`. `BEHIND_TLS_PROXY` entra explícito, porque o container o força a "True".
"""

import os
import runpy
from unittest import mock

import environ
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

CAMINHO_SETTINGS = settings.BASE_DIR / "config" / "settings.py"
SENTINELA = "sentinela-spa-client-x9k2q7"


def carregar(spa_client_id, **extras):
    """Executa `config/settings.py` do zero e devolve o seu namespace.

    `spa_client_id=None` remove a variável do ambiente do processo, para o caso de ausência."""
    ambiente = {"BEHIND_TLS_PROXY": "False", **extras}
    if spa_client_id is not None:
        ambiente["SPA_CLIENT_ID"] = spa_client_id
    with mock.patch.object(environ.Env, "read_env"), mock.patch.dict(os.environ, ambiente):
        if spa_client_id is None:
            os.environ.pop("SPA_CLIENT_ID", None)
        return runpy.run_path(str(CAMINHO_SETTINGS))


class SpaClientIdTests(SimpleTestCase):
    def test_ausente_derruba_a_carga_nomeando_a_variavel(self):
        with self.assertRaises(ImproperlyConfigured) as ctx:
            carregar(None)

        self.assertIn("SPA_CLIENT_ID", str(ctx.exception))

    def test_vazia_derruba_a_carga_nomeando_a_variavel(self):
        with self.assertRaises(ImproperlyConfigured) as ctx:
            carregar("")

        self.assertIn("SPA_CLIENT_ID", str(ctx.exception))

    def test_presente_e_devolvida_intacta(self):
        self.assertEqual(carregar(SENTINELA)["SPA_CLIENT_ID"], SENTINELA)


class TermosVersaoVigenteTests(SimpleTestCase):
    def test_a_versao_vigente_e_literal_e_nao_vem_do_ambiente(self):
        ns = carregar(SENTINELA, TERMOS_VERSAO_VIGENTE="9")

        self.assertEqual(ns["TERMOS_VERSAO_VIGENTE"], "1")
