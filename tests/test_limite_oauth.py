"""T-07, T-09, T-11/T-17 — a limitação de taxa de `/o/token/`, de `/o/authorize/` e (a partir
de T-17) de `/accounts/login/` (`config/limites.py`), e o preço que o T-10/T-13 cobram por
desligá-la durante a suíte.

Demanda do quality-assurance (TASK-014, bloco B). Nível integração em T-07 e T-09: o teto é
um middleware sobre o cache real e sobre a posição dele na cadeia, e a costura entre
`LimiteDeTaxaMiddleware` e `ObservabilidadeMiddleware` só se prova pela resposta HTTP e pelo
log de verdade. T-11/T-17 é unitário — uma única decisão: o dicionário de produção, com as
TRÊS chaves declaradas hoje, alcança o middleware.

REGRA DO BLOCO: todo teste aqui passa `REMOTE_ADDR` explícito e forjado (`10.x.y.z`). O
default do test client é `127.0.0.1`, a MESMA chave de contador que o `runserver` da jornada
de construção usa — omiti-lo escreveria no contador do ambiente. `tests/runner.py` (T-10,
revisado por T-13) já desliga `RATE_LIMIT_POR_CAMINHO` inteiro para a suíte; cada teste que
precisa do limitador ligado o faz por `override_settings`, e limpa as próprias chaves por
`chave_do_contador` — nunca por `cache.clear()`, que o `RedisCache` implementa como `FLUSHDB`
e levaria junto a cópia quente das sessões (ADR 0005).
"""

import json
import logging

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings

import tests.runner as runner
from config.limites import chave_do_contador
from config.observabilidade import FiltroRequestId, FormatadorJSON
from tests.oauth_helpers import REDIRECT_URI, create_public_rs256_application, make_pkce_pair

User = get_user_model()


class _ColetorDeLinhas(logging.Handler):
    """Duplicata pequena e deliberada (ver razão em `tests/test_auditoria.py`)."""

    def __init__(self):
        super().__init__()
        self.addFilter(FiltroRequestId())
        self.setFormatter(FormatadorJSON())
        self.linhas = []

    def emit(self, record):
        self.linhas.append(json.loads(self.format(record)))


ORIGEM_T07 = "10.50.0.1"


@override_settings(
    RATE_LIMIT_POR_CAMINHO={"/o/token/": 2, "/o/authorize/": 2},
    RATE_LIMIT_JANELA_SEGUNDOS=60,
)
class LimiteDeOAuthTests(TestCase):
    """T-07 — AC-06, AC-07 e a metade in loco do AC-12."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="t07-oauth@exemplo.com", password="senha-forte-o-suficiente"
        )
        self.application = create_public_rs256_application(self.user)
        self._apaga_as_duas_chaves()

    def tearDown(self):
        self._apaga_as_duas_chaves()

    def _apaga_as_duas_chaves(self):
        cache.delete(chave_do_contador("/o/token/", ORIGEM_T07))
        cache.delete(chave_do_contador("/o/authorize/", ORIGEM_T07))

    def test_a_terceiro_post_a_o_token_e_429_sem_token_no_corpo(self):
        dados = {
            "grant_type": "authorization_code",
            "code": "code-que-nao-existe",
            "redirect_uri": REDIRECT_URI,
            "client_id": self.application.client_id,
            "code_verifier": "verifier-que-nao-bate",
        }

        codigos = []
        for _ in range(2):
            resposta = self.client.post("/o/token/", dados, REMOTE_ADDR=ORIGEM_T07)
            codigos.append(resposta.status_code)
        self.assertEqual(codigos, [400, 400])

        terceira = self.client.post("/o/token/", dados, REMOTE_ADDR=ORIGEM_T07)

        self.assertEqual(terceira.status_code, 429)
        self.assertEqual(terceira["Retry-After"], "60")
        corpo = terceira.json()
        self.assertEqual(corpo["error"], "temporarily_unavailable")
        self.assertIn("error_description", corpo)
        self.assertNotIn("access_token", corpo)
        self.assertNotIn("id_token", corpo)

    def test_b_terceiro_get_a_o_authorize_e_429_sem_code_e_sem_location(self):
        self.client.force_login(self.user)
        _verifier, challenge = make_pkce_pair()
        params = {
            "response_type": "code",
            "client_id": self.application.client_id,
            "redirect_uri": REDIRECT_URI,
            "scope": "openid",
            "state": "t07b-state",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "nonce": "t07b-nonce",
        }

        codigos = []
        for _ in range(2):
            resposta = self.client.get("/o/authorize/", params, REMOTE_ADDR=ORIGEM_T07)
            codigos.append(resposta.status_code)
        self.assertEqual(codigos, [200, 200])

        terceira = self.client.get("/o/authorize/", params, REMOTE_ADDR=ORIGEM_T07)

        self.assertEqual(terceira.status_code, 429)
        self.assertIsNone(terceira.get("Location"))
        self.assertNotIn("code=", terceira.content.decode())

    def test_c_apagar_a_chave_pela_funcao_de_producao_devolve_o_status_do_protocolo(self):
        dados = {
            "grant_type": "authorization_code",
            "code": "code-que-nao-existe",
            "redirect_uri": REDIRECT_URI,
            "client_id": self.application.client_id,
            "code_verifier": "verifier-que-nao-bate",
        }

        for _ in range(2):
            self.client.post("/o/token/", dados, REMOTE_ADDR=ORIGEM_T07)
        bloqueada = self.client.post("/o/token/", dados, REMOTE_ADDR=ORIGEM_T07)
        self.assertEqual(bloqueada.status_code, 429)

        cache.delete(chave_do_contador("/o/token/", ORIGEM_T07))

        seguinte = self.client.post("/o/token/", dados, REMOTE_ADDR=ORIGEM_T07)
        self.assertEqual(seguinte.status_code, 400)


ORIGEM_T09 = "10.50.0.2"


class ObservabilidadeDoLimiteDeOAuthTests(TestCase):
    """T-09 — AC-08 no lado de /o/, e é este teste que sustenta a arbitragem do QA de que o
    log operacional satisfaz o critério para /o/ (sem conta alvo, sem trilha)."""

    def setUp(self):
        self._coletor = _ColetorDeLinhas()
        self._loggers = [logging.getLogger("config.limites"), logging.getLogger("access")]
        for logger in self._loggers:
            logger.addHandler(self._coletor)
        cache.delete(chave_do_contador("/o/authorize/", ORIGEM_T09))

    def tearDown(self):
        for logger in self._loggers:
            logger.removeHandler(self._coletor)
        cache.delete(chave_do_contador("/o/authorize/", ORIGEM_T09))

    def test_linha_throttled_correlaciona_com_a_linha_de_acesso_e_nao_traz_route(self):
        # Teto 0: a primeira requisição já basta para provocar o 429 — o ponto deste caso
        # é a linha de log, não a contagem, que T-07 já cobre.
        with override_settings(
            RATE_LIMIT_POR_CAMINHO={"/o/authorize/": 0}, RATE_LIMIT_JANELA_SEGUNDOS=60
        ):
            resposta = self.client.get("/o/authorize/", REMOTE_ADDR=ORIGEM_T09)

        self.assertEqual(resposta.status_code, 429)

        linhas_throttled = [
            linha for linha in self._coletor.linhas if linha.get("outcome") == "throttled"
        ]
        linhas_de_acesso = [
            linha for linha in self._coletor.linhas if linha.get("msg") == "requisição atendida"
        ]

        self.assertEqual(len(linhas_throttled), 1, self._coletor.linhas)
        linha = linhas_throttled[0]
        # (a)
        self.assertEqual(linha["path"], "/o/authorize/")
        self.assertEqual(linha["ip"], ORIGEM_T09)
        self.assertEqual(linha["outcome"], "throttled")
        # (b) — o middleware roda antes da resolução da URL; `route` não pode aparecer.
        self.assertNotIn("route", linha)

        # (c) — mesmo request_id da linha de acesso da MESMA requisição.
        self.assertEqual(len(linhas_de_acesso), 1, self._coletor.linhas)
        self.assertEqual(linha["request_id"], linhas_de_acesso[0]["request_id"])


ORIGEM_T11_TOKEN = "10.50.0.3"
ORIGEM_T11_AUTHORIZE = "10.50.0.4"
ORIGEM_T17_LOGIN = "10.50.0.5"


class OAuthRateLimitDeProducaoAlcancaOMiddlewareTests(TestCase):
    """T-11, ampliado por T-17 — o preço do T-10/T-13. Prova que `RATE_LIMIT_POR_CAMINHO` de
    produção, e não um dicionário qualquer, alcança de fato o middleware para os TRÊS
    caminhos declarados e faz o contador de cada um subir — sem asserir o teto numérico,
    porque isso reescreveria a política dentro do teste.

    A terceira chave (`/accounts/login/`) é o preço específico do T-13: com o dicionário
    inteiro esvaziado pelo runner durante a suíte (e não só as duas de `/o/`, como antes),
    nada mais prova que a entrada de login declarada em `config/settings.py` chega ao
    middleware. Sem este caso, apagar `"/accounts/login/"` daquele dicionário deixaria a tela
    de login sem teto e a suíte inteira verde."""

    def tearDown(self):
        cache.delete(chave_do_contador("/o/token/", ORIGEM_T11_TOKEN))
        cache.delete(chave_do_contador("/o/authorize/", ORIGEM_T11_AUTHORIZE))
        cache.delete(chave_do_contador("/accounts/login/", ORIGEM_T17_LOGIN))

    def test_contador_sobe_para_os_tres_caminhos_com_o_dicionario_de_producao(self):
        # `tests.runner.RunnerComTrilhaIsolada.setup_test_environment` (T-10/T-13) guardou o
        # valor de produção aqui antes de zerar `settings.RATE_LIMIT_POR_CAMINHO` para a suíte.
        self.assertIsNotNone(
            runner.RATE_LIMIT_DE_PRODUCAO,
            "T-10/T-13 não guardou o teto de produção — o runner rodou sem passar pelo setup?",
        )

        with override_settings(RATE_LIMIT_POR_CAMINHO=runner.RATE_LIMIT_DE_PRODUCAO):
            self.client.post("/o/token/", {}, REMOTE_ADDR=ORIGEM_T11_TOKEN)
            self.client.get("/o/authorize/", REMOTE_ADDR=ORIGEM_T11_AUTHORIZE)
            # GET anônimo, e não POST: o objeto deste caso é só o contador do middleware, e
            # um GET não convoca o `django-axes` (que só age no caminho de `authenticate()`,
            # ou seja, sobre POST) — a mesma separação de papéis que T-14 usa.
            self.client.get("/accounts/login/", REMOTE_ADDR=ORIGEM_T17_LOGIN)

        self.assertEqual(cache.get(chave_do_contador("/o/token/", ORIGEM_T11_TOKEN)), 1)
        self.assertEqual(
            cache.get(chave_do_contador("/o/authorize/", ORIGEM_T11_AUTHORIZE)), 1
        )
        self.assertEqual(
            cache.get(chave_do_contador("/accounts/login/", ORIGEM_T17_LOGIN)), 1
        )
