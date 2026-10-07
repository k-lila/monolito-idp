"""TASK-028/T-35 — o CORS (Cross-Origin Resource Sharing) da API de conta, sob
`CORS_URLS_REGEX = r"^/(?:o|api/conta)/"` (`config/settings.py`).

Demanda do quality-assurance. Nível integração, com a allowlist fixada por
`override_settings(CORS_ALLOWED_ORIGINS=[ORIGEM])`: o `.env.example` traz a lista vazia, e com
ela o middleware é inerte. Os casos de `/o/`, `/accounts/login/` e `/admin/` estão em
`tests/test_cors.py`.

A preflight da origem da SPA é respondida pelo `CorsMiddleware` antes de qualquer view, e por
isso sob `assertNumQueries(0)`: sem consulta ao token nem à sessão. Sem credenciais:
`Access-Control-Allow-Credentials` não pode aparecer, porque a API autentica por Bearer.
"""

from django.test import Client, override_settings

from tests.api_conta_helpers import ORIGEM_DA_SPA as ORIGEM
from tests.api_conta_helpers import CAMINHO_CONTA, ApiDeContaTestCase

ACAO = "Access-Control-Allow-Origin"
EXPOSE = "Access-Control-Expose-Headers"
CREDENCIAIS = "Access-Control-Allow-Credentials"
CAMINHOS = (CAMINHO_CONTA, "/api/conta/confirmacao/", "/api/conta/termos/", "/api/conta/confirmar/")


@override_settings(CORS_ALLOWED_ORIGINS=[ORIGEM])
class CorsDaApiDeContaTests(ApiDeContaTestCase):
    def _preflight(self, caminho, origem):
        return Client().options(
            caminho,
            HTTP_ORIGIN=origem,
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="PATCH",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="authorization,content-type",
        )

    def _confere_expostos(self, resposta):
        expostos = [parte.strip() for parte in resposta[EXPOSE].split(",")]
        self.assertIn("WWW-Authenticate", expostos)
        self.assertIn("Retry-After", expostos)

    def test_preflight_da_origem_da_spa_nos_quatro_caminhos(self):
        for caminho in CAMINHOS:
            with self.subTest(caminho=caminho):
                with self.assertNumQueries(0):
                    resposta = self._preflight(caminho, ORIGEM)

                self.assertEqual(resposta[ACAO], ORIGEM)
                self._confere_expostos(resposta)
                self.assertNotIn(CREDENCIAIS, resposta)

    def test_preflight_de_outra_origem_nao_recebe_cabecalho_de_cors(self):
        for caminho in CAMINHOS:
            with self.subTest(caminho=caminho):
                resposta = self._preflight(caminho, "https://mal.example")

                self.assertNotIn(ACAO, resposta)
                self.assertNotIn(CREDENCIAIS, resposta)

    def test_get_com_bearer_e_origin_da_spa(self):
        resposta = self.client.get(CAMINHO_CONTA, HTTP_ORIGIN=ORIGEM, **self.cabecalho)

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta[ACAO], ORIGEM)
        self._confere_expostos(resposta)
        self.assertNotIn(CREDENCIAIS, resposta)

    def test_get_sem_token_e_401_com_cors_para_a_spa_ler_o_desafio(self):
        resposta = self.client.get(CAMINHO_CONTA, HTTP_ORIGIN=ORIGEM)

        self.assertEqual(resposta.status_code, 401)
        self.assertEqual(resposta[ACAO], ORIGEM)
        self._confere_expostos(resposta)
        self.assertNotIn(CREDENCIAIS, resposta)

    def test_get_de_outra_origem_nao_recebe_cabecalho_de_cors(self):
        resposta = self.client.get(
            CAMINHO_CONTA, HTTP_ORIGIN="https://mal.example", **self.cabecalho
        )

        self.assertNotIn(ACAO, resposta)
