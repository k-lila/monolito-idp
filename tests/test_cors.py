"""TASK-019/T-10, T-11 — o Cross-Origin Resource Sharing (CORS) do `django-cors-headers`
(`CorsMiddleware`, primeiro em `MIDDLEWARE`) sob `CORS_URLS_REGEX = r"^/o/"`
(`config/settings.py`).

Demanda do quality-assurance (TASK-019/Fase 7). Nível integração: o que está sob prova é a
COSTURA entre o regex e o prefixo real das rotas — `CorsMiddleware.add_response_headers`
(`corsheaders/middleware.py`) só escreve cabeçalho quando `CORS_URLS_REGEX` casa o
`request.path`, e só a resposta HTTP de verdade revela se casou.

`override_settings(CORS_ALLOWED_ORIGINS=[...])` explícito nas duas classes, e não o valor do
`.env` (`http://localhost:5173`, o mesmo literal): fixar a allowlist no teste separa o que está
sob prova — o REGEX — do que já é `.env` de outro ambiente, que poderia mudar sem relação
nenhuma com este teste.

T-10 — fora de `/o/`: NENHUM cabeçalho de CORS, mesmo com uma origem da allowlist e mesmo em
preflight. A única asserção é a AUSÊNCIA de `Access-Control-Allow-Origin` — nunca `Vary` nem
qualquer outro cabeçalho de CORS. A razão não é ordem dentro de `add_response_headers`: fora de
`/o/`, `CORS_URLS_REGEX` (`config/settings.py`) não casa o `request.path`, `is_enabled` devolve
`False` e `add_response_headers` retorna na guarda de entrada (`corsheaders/middleware.py:87-94`)
— antes até de chegar a `patch_vary_headers`. Nenhum cabeçalho de CORS é escrito, `Vary`
incluído, porque o middleware sai da função antes de qualquer um dos dois.

T-11 — dentro de `/o/`: o cabeçalho sai com o valor EXATO da origem (nunca `*`), inclusive em
preflight sobre `/o/token/` e `/o/userinfo/`, nos dois documentos de descoberta publicados sob
`/o/` (`/o/.well-known/openid-configuration`, da OIDC, e `/o/.well-known/oauth-authorization-
server`, da RFC 8414), no `/o/.well-known/jwks.json`, e num 401 de `/o/userinfo/` — o
middleware corre por cima de QUALQUER resposta que a view produza, erro incluído."""

from django.test import TestCase, override_settings

ORIGEM = "http://localhost:5173"
ACAO = "Access-Control-Allow-Origin"


@override_settings(CORS_ALLOWED_ORIGINS=[ORIGEM])
class CorsForaDoPrefixoOAusenteTests(TestCase):
    """T-10 — /accounts/login/ e /admin/, GET e preflight OPTIONS."""

    def test_get_login_sem_cabecalho_de_cors_e_200(self):
        resposta = self.client.get("/accounts/login/", HTTP_ORIGIN=ORIGEM)

        self.assertEqual(resposta.status_code, 200)
        self.assertNotIn(ACAO, resposta)

    def test_preflight_login_sem_cabecalho_de_cors(self):
        resposta = self.client.options(
            "/accounts/login/",
            HTTP_ORIGIN=ORIGEM,
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        )

        self.assertNotIn(ACAO, resposta)

    def test_get_admin_anonimo_sem_cabecalho_de_cors_e_302(self):
        resposta = self.client.get("/admin/", HTTP_ORIGIN=ORIGEM)

        self.assertEqual(resposta.status_code, 302)
        self.assertNotIn(ACAO, resposta)

    def test_preflight_admin_sem_cabecalho_de_cors(self):
        resposta = self.client.options(
            "/admin/",
            HTTP_ORIGIN=ORIGEM,
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        )

        self.assertNotIn(ACAO, resposta)


@override_settings(CORS_ALLOWED_ORIGINS=[ORIGEM])
class CorsDentroDoPrefixoComOrigemExataTests(TestCase):
    """T-11 — /o/token/, /o/userinfo/ e os dois documentos publicados sob /o/."""

    def test_preflight_o_token_devolve_a_origem_exata(self):
        resposta = self.client.options(
            "/o/token/",
            HTTP_ORIGIN=ORIGEM,
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="content-type",
        )

        self.assertEqual(resposta[ACAO], ORIGEM)

    def test_preflight_o_userinfo_devolve_a_origem_exata(self):
        resposta = self.client.options(
            "/o/userinfo/",
            HTTP_ORIGIN=ORIGEM,
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="authorization",
        )

        self.assertEqual(resposta[ACAO], ORIGEM)

    def test_get_openid_configuration_devolve_a_origem_exata(self):
        resposta = self.client.get(
            "/o/.well-known/openid-configuration", HTTP_ORIGIN=ORIGEM
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta[ACAO], ORIGEM)

    def test_get_oauth_authorization_server_devolve_a_origem_exata(self):
        """O documento de descoberta da RFC 8414 — a rota que `oauth2_provider.urls`
        publica na raiz de `/o/` (ADR 0024) —, e não só o da OIDC acima: a mesma allowlist
        e o mesmo REGEX cobrem os dois."""
        resposta = self.client.get(
            "/o/.well-known/oauth-authorization-server", HTTP_ORIGIN=ORIGEM
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta[ACAO], ORIGEM)

    def test_get_jwks_devolve_a_origem_exata(self):
        resposta = self.client.get("/o/.well-known/jwks.json", HTTP_ORIGIN=ORIGEM)

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta[ACAO], ORIGEM)

    def test_userinfo_com_bearer_invalido_e_401_com_a_origem_exata(self):
        """O middleware roda por cima de QUALQUER resposta, inclusive de erro: um 401 do
        DOT ainda carrega o cabeçalho de CORS — sem ele, o navegador da SPA esconderia o
        401 real atrás de um erro de CORS sem pista nenhuma (o mesmo silêncio que o
        comentário do `LimiteDeTaxaMiddleware`, em `config/settings.py`, já nomeia para o
        429)."""
        resposta = self.client.get(
            "/o/userinfo/",
            HTTP_ORIGIN=ORIGEM,
            HTTP_AUTHORIZATION="Bearer invalido",
        )

        self.assertEqual(resposta.status_code, 401)
        self.assertEqual(resposta[ACAO], ORIGEM)
