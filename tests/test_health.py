"""TASK-007/T-08, TASK-007/T-09, TASK-007/T-10 — /health e a view `health`, prontidão de banco e cache.

Demanda do quality-assurance (bloco E). /health não afirma nada sobre identidade,
e é o único módulo da suíte que não puxa nada de `oauth_helpers`: não há Application,
nem fluxo, nem sessão a montar antes de sondar banco e cache.
"""

import json
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from config.views import health


class HealthEndpointOkTests(TestCase):
    """TASK-007/T-08 — banco e cache reais, de pé: 200 com as três chaves esperadas."""

    def test_get_health_sem_sessao_e_com_host_real_devolve_ok(self):
        # `host=127.0.0.1` é um dos hosts reais de ALLOWED_HOSTS (não "testserver",
        # que o runner acrescenta por conta própria): asserta a configuração de
        # verdade, não um artefato do test client.
        response = self.client.get("/health", headers={"host": "127.0.0.1"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")

        # Dicionário desserializado, não a string: não amarra o teste ao
        # espaçamento que o JsonResponse decidir usar.
        body = json.loads(response.content)
        self.assertEqual(body, {"status": "ok", "database": "ok", "cache": "ok"})


class HealthEndpointCacheDownTests(TestCase):
    """TASK-007/T-09 — cache real, porém inalcançável: 503 sem derrubar container nenhum."""

    @override_settings(
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.redis.RedisCache",
                # Porta fechada em loopback: falha imediata de conexão, sem o
                # timeout de DNS que um hostname inexistente custaria.
                "LOCATION": "redis://127.0.0.1:6399/0",
            }
        }
    )
    def test_get_health_com_cache_inalcancavel_devolve_503(self):
        # Client sem login: com SESSION_ENGINE = cached_db, uma sessão viva leria
        # o cache morto no middleware, e a falha reportada seria do middleware,
        # não da view sob teste.
        with self.assertLogs("config.views", level="ERROR"):
            response = self.client.get("/health")

        self.assertEqual(response.status_code, 503)
        body = json.loads(response.content)
        self.assertEqual(body, {"status": "error", "database": "ok", "cache": "error"})


class HealthViewDatabaseDownUnitTests(SimpleTestCase):
    """TASK-007/T-10 — decisão da própria view: um try por componente (config/views.py:42-57).

    RequestFactory + chamada direta: derrubar o Postgres de verdade custaria
    caro e impediria o próprio banco de teste de existir. Único caso do lote em
    que o mock é a ferramenta certa.
    """

    def setUp(self):
        self.factory = RequestFactory()

    def test_banco_falhando_nao_apaga_o_estado_do_cache(self):
        request = self.factory.get("/health")

        with self.assertLogs("config.views", level="ERROR"):
            with patch("config.views.connection") as conexao:
                conexao.cursor.side_effect = Exception("banco fora do ar")
                response = health(request)

        self.assertEqual(response.status_code, 503)
        body = json.loads(response.content)
        # "cache": "ok" continua presente e correto enquanto o banco falha —
        # é a guarda que cai se alguém unificar os dois try num só.
        self.assertEqual(body, {"status": "error", "database": "error", "cache": "ok"})


class HealthRedirectExemptionTests(TestCase):
    """TASK-009/T-01 — SECURE_REDIRECT_EXEMPT tem de sobreviver a duas mutações silenciosas.

    O .env da jornada de construção traz BEHIND_TLS_PROXY=False, então
    SECURE_SSL_REDIRECT é False e a isenção fica inerte na suíte inteira: sem o
    override abaixo, apagar `SECURE_REDIRECT_EXEMPT` em settings.py não derrubaria
    teste nenhum. reverse("health") em vez de "/health" escrito a mao morde a
    segunda mutação — renomear a rota `health` em urls.py sem atualizar o regex faz
    a isenção deixar de casar, e é o path resolvido aqui, não um literal, que
    denunciaria isso ficando vermelho.
    """

    @override_settings(SECURE_SSL_REDIRECT=True)
    def test_health_e_isento_do_redirecionamento_https(self):
        response = self.client.get(reverse("health"), headers={"host": "127.0.0.1"})

        self.assertEqual(response.status_code, 200)

    @override_settings(SECURE_SSL_REDIRECT=True)
    def test_rota_nao_isenta_continua_redirecionada_para_https(self):
        # Caso de controle: sem ele, o 200 do teste acima não distingue "a isenção
        # funciona" de "o redirecionamento nunca esteve ligado nesta suíte".
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 301)
        self.assertTrue(response["Location"].startswith("https://"))
