"""T-01, T-02, T-03, T-05, T-10, T-13 — o par filtro+formatador, o identificador de
requisição e a linha de acesso.

Demanda do quality-assurance (TASK-013), sobre `config/observabilidade.py`. T-01, T-02 e
T-03 exercitam `FormatadorJSON`/`FiltroRequestId` isoladamente, sem HTTP nem banco; T-05,
T-10 e T-13 atravessam o `ObservabilidadeMiddleware` de verdade, por uma requisição real do
cliente de teste.

T-05 é também a prova de regressão da ADR (Architecture Decision Record) 0014 — a emenda que
tirou o `reset()` do `ContextVar` do `finally` do middleware porque `log_response` roda
depois que a cadeia de middleware inteira retornou. Este arquivo não asserta o sentinela "-"
em lugar nenhum para uma linha nascida DENTRO de uma requisição: por design da própria ADR
0014, o identificador sobrevive à requisição que o gerou, e um teste que dependesse do "-"
apareceria e sumiria conforme a ordem em que os arquivos da suíte rodam — exatamente a
dependência de ordem que o AC-12 proíbe. O "-" que T-13 asserta é o outro: o do campo
`route`, escrito pelo middleware quando a URL não resolve rota nenhuma. Os dois sentinelas
têm a mesma grafia e nada mais em comum — aquele depende do histórico do processo, este só
da requisição em curso.
"""

import json
import logging

from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import resolve

from config.observabilidade import FiltroRequestId, FormatadorJSON


class _ColetorDeLinhas(logging.Handler):
    """Handler efêmero, anexado a um logger só para a duração de um teste.

    Usa o MESMO par filtro+formatador que os handlers `console` e `audit` usam em
    produção (`LOGGING`, em `config/settings.py`) — não uma reimplementação —, de
    modo que a linha capturada é byte a byte a que sairia de verdade. `Handler.handle()`
    já aplica `self.filters` antes de chamar `emit()`, então o `FiltroRequestId`
    corrige `record.request_id` antes de `emit` ver o registro, igual à cadeia real.
    """

    def __init__(self):
        super().__init__()
        self.addFilter(FiltroRequestId())
        self.setFormatter(FormatadorJSON())
        self.linhas = []

    def emit(self, record):
        self.linhas.append(json.loads(self.format(record)))


class FormatadorJSONTests(SimpleTestCase):
    """T-01, T-02, T-03.

    Nível unitário: cada caso passa um registro por um logger próprio deste
    módulo — nunca "access", "audit" ou "django", que já correm ligados aos
    handlers de `LOGGING` durante a suíte inteira, e um handler efêmero ali
    disputaria estado com outros arquivos de teste.
    """

    def _emitir(self, mensagem="mensagem original", **kwargs):
        logger = logging.getLogger("tests.observabilidade.formatador")
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
        coletor = _ColetorDeLinhas()
        logger.addHandler(coletor)
        try:
            logger.info(mensagem, **kwargs)
        finally:
            logger.removeHandler(coletor)
        self.assertEqual(len(coletor.linhas), 1)
        return coletor.linhas[0]

    def test_t01_chaves_fixas_do_contrato_sobrevivem_a_extra_invasivo(self):
        """T-01: um `extra=` tentando reescrever ts/level/logger/request_id perde
        para o valor do contrato, e um campo próprio do extra continua presente
        no topo do objeto — a ordem do dict literal em `FormatadorJSON.format`
        poe as chaves fixas por último, de propósito.

        `request_id` não é comparado contra "-": a ADR 0014 fixou que o
        identificador sobrevive à requisição que o gerou, então o valor real
        aqui pode ser "-" (processo que ainda não atendeu requisição) ou o de um
        pedido anterior de outro arquivo da suíte, dependendo da ordem de
        descoberta. O que este teste prova é mais estrito: seja lá qual for o
        valor real, não é a string "invadido" que o extra tentou impor.
        """
        linha = self._emitir(
            extra={
                "ts": "invadido",
                "level": "invadido",
                "logger": "invadido",
                "request_id": "invadido",
                "campo_proprio": 1,
            }
        )

        self.assertNotEqual(linha["ts"], "invadido")
        self.assertTrue(linha["ts"].endswith("+00:00"), linha["ts"])
        self.assertEqual(linha["level"], "INFO")
        self.assertEqual(linha["logger"], "tests.observabilidade.formatador")
        self.assertNotEqual(linha["request_id"], "invadido")
        self.assertEqual(linha["campo_proprio"], 1)
        self.assertEqual(linha["msg"], "mensagem original")

        # json.loads já não teria devolvido nada se a linha não fosse JSON válido;
        # a asserção de tipo é só para deixar o critério de aceite legível aqui.
        self.assertIsInstance(linha, dict)

    def test_t01_chave_msg_e_nativa_de_logrecord_e_a_propria_stdlib_recusa_o_extra(self):
        """T-01, a quinta chave do contrato.

        `msg` já é atributo nativo de `LogRecord` — é onde `record.getMessage()`
        lê —, e por isso `Logger.makeRecord` levanta `KeyError` antes mesmo de o
        registro existir, quando `extra` traz essa chave. Não há como produzir
        "uma linha em que msg do contrato sobrevive a um extra com msg": as duas
        coisas — linha emitida, e extra com `msg` aceito — são mutuamente
        exclusivas na própria biblioteca padrão, e é essa exclusão, mais forte
        que qualquer defesa que `FormatadorJSON` pudesse escrever, que esta prova
        demonstra.
        """
        logger = logging.getLogger("tests.observabilidade.formatador.msg")
        logger.setLevel(logging.DEBUG)

        with self.assertRaises(KeyError):
            logger.info("mensagem original", extra={"msg": "invadido"})

    def test_t02_exc_carrega_o_traceback_sem_a_variavel_local_secreta(self):
        """T-02: `formatException` roda sem os locais de cada quadro — é o que
        impede um traceback de carregar uma variável secreta para dentro da
        linha. O valor abaixo nasce só nesta função, para que a busca não
        confunda "nunca vazou" com "nunca existiu na pilha"."""
        segredo = "valor-secreto-nunca-deve-vazar-no-log-fabricado-para-t02"

        def _explode():
            senha_local = segredo  # noqa: F841 -- só precisa existir na pilha
            raise RuntimeError("falha proposital de T-02")

        try:
            _explode()
        except RuntimeError:
            linha = self._emitir("falha capturada", exc_info=True)

        self.assertIn("exc", linha)
        self.assertIn("RuntimeError", linha["exc"])
        self.assertIn("falha proposital de T-02", linha["exc"])
        self.assertNotIn(segredo, json.dumps(linha, ensure_ascii=False))

    def test_t03_atributo_request_de_log_response_e_excluido(self):
        """T-03: `extra={"request": ..., "status_code": ...}` é exatamente o que
        `django.core.handlers.exception.log_response` anexa a toda resposta
        4xx/5xx (`config/observabilidade.py`, comentário de `_ATRIBUTOS_DO_REGISTRO`).
        Sem a exclusão, cada 404 despejaria o `repr` de um `HttpRequest` inteiro."""
        request = RequestFactory().get("/qualquer-caminho-t03")

        linha = self._emitir("Not Found: /qualquer-caminho-t03", extra={
            "request": request,
            "status_code": 404,
        })

        self.assertEqual(linha["status_code"], 404)
        self.assertNotIn("request", linha)


class RequestIdCorrelationTests(TestCase):
    """T-05. Prova de regressão da ADR 0014.

    Anexa o coletor diretamente aos loggers "access" e "django.request" durante
    a requisição — a linha de "access" nasce dentro do middleware, e a de
    "django.request" nasce em `log_response`, DEPOIS que a cadeia de middleware
    inteira retornou (`django/core/handlers/base.py`); é essa segunda que o
    `reset()` antigo perdia, e a emenda da ADR 0014 corrige.
    """

    def setUp(self):
        self.coletor = _ColetorDeLinhas()
        logging.getLogger("access").addHandler(self.coletor)
        logging.getLogger("django.request").addHandler(self.coletor)

    def tearDown(self):
        logging.getLogger("access").removeHandler(self.coletor)
        logging.getLogger("django.request").removeHandler(self.coletor)

    def test_a_requisicoes_distintas_recebem_identificadores_distintos(self):
        self.client.get("/o/.well-known/openid-configuration")
        self.assertEqual(len(self.coletor.linhas), 1)
        primeiro_id = self.coletor.linhas[0]["request_id"]
        self.assertNotEqual(primeiro_id, "-")

        self.coletor.linhas.clear()
        self.client.get("/o/.well-known/jwks.json")
        self.assertEqual(len(self.coletor.linhas), 1)
        segundo_id = self.coletor.linhas[0]["request_id"]

        self.assertNotEqual(segundo_id, "-")
        self.assertNotEqual(segundo_id, primeiro_id)

    def test_b_404_correlaciona_a_linha_de_django_request(self):
        """Rota que não resolve: a guarda exata que a ADR 0014 registra como
        sintoma — "Not Found" saindo com o sentinela "-" antes da emenda."""
        self.coletor.linhas.clear()

        response = self.client.get("/rota-que-nao-existe-t05")

        self.assertEqual(response.status_code, 404)
        self.assertGreaterEqual(len(self.coletor.linhas), 2, self.coletor.linhas)
        ids = {linha["request_id"] for linha in self.coletor.linhas}
        self.assertEqual(len(ids), 1, self.coletor.linhas)
        self.assertNotIn("-", ids)

    def test_c_4xx_devolvido_por_uma_view_sem_levantar_correlaciona(self):
        """`redirect_uri` fora da allowlist: 400 devolvido pela própria view do
        DOT (django-oauth-toolkit), sem exceção — o outro sintoma nomeado pela
        ADR 0014, ao lado do 404 e do /health degradado."""
        from django.contrib.auth import get_user_model

        from tests.oauth_helpers import authorize_and_get_code, create_public_rs256_application

        User = get_user_model()
        user = User.objects.create_user(
            email="t05c@example.com", password="senha-forte-o-suficiente"
        )
        application = create_public_rs256_application(user)
        self.client.force_login(user)
        self.coletor.linhas.clear()

        _code, _verifier, response = authorize_and_get_code(
            self.client,
            application,
            redirect_uri="http://localhost:8000/nao-registrada-t05c",
            scope="openid",
        )

        self.assertEqual(response.status_code, 400)
        self.assertGreaterEqual(len(self.coletor.linhas), 2, self.coletor.linhas)
        ids = {linha["request_id"] for linha in self.coletor.linhas}
        self.assertEqual(len(ids), 1, self.coletor.linhas)
        self.assertNotIn("-", ids)


class AccessLogExclusionTests(TestCase):
    """T-10. `ACCESS_LOG_EXCLUDED_ROUTES = ["health"]`, em `config/settings.py`."""

    def test_get_health_nao_produz_linha_de_acesso(self):
        with self.assertNoLogs("access", level="INFO"):
            self.client.get("/health")

    def test_rota_qualquer_produz_exatamente_uma_linha_de_acesso(self):
        with self.assertLogs("access", level="INFO") as captura:
            self.client.get("/o/.well-known/openid-configuration")

        self.assertEqual(len(captura.records), 1)


class LinhaDeAcessoTests(TestCase):
    """T-13. Os quatro campos da linha de acesso, na linha que sai de verdade.

    Asserção sobre o JSON formatado pelo par real `FiltroRequestId` + `FormatadorJSON`
    — nunca sobre `record.__dict__` —, porque o que `docs/runbook.md` promete ao
    operador é a linha, não o dicionário que a originou: um campo que o formatador
    descartasse passaria despercebido numa leitura do registro.

    Os dois casos abaixo são o mesmo caminho visto dos dois lados da costura entre o
    middleware e o resolvedor: `request.resolver_match` só existe depois de
    `get_response`, e é dessa ordem que dependem tanto o nome da rota quanto o
    sentinela "-" de quem não resolve rota nenhuma.
    """

    def setUp(self):
        self.coletor = _ColetorDeLinhas()
        # Só "access": a linha de acesso nasce ali, e o logger não propaga
        # (`LOGGING`, em `config/settings.py`). Nenhum outro logger entra, para que
        # a contagem de linhas do coletor seja a contagem de linhas de acesso.
        logging.getLogger("access").addHandler(self.coletor)

    def tearDown(self):
        logging.getLogger("access").removeHandler(self.coletor)

    def test_rota_que_resolve_sai_com_nome_da_rota_metodo_status_e_duracao(self):
        caminho = "/o/.well-known/openid-configuration"

        response = self.client.get(caminho)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.coletor.linhas), 1, self.coletor.linhas)
        linha = self.coletor.linhas[0]

        # O NOME da rota, nunca o caminho. Comparado por igualdade contra o que o
        # próprio resolvedor devolve — comparar por substring do caminho aceitaria
        # `request.path` no lugar de `view_name` e deixaria passar a redução que
        # este caso existe para pegar.
        self.assertEqual(linha["route"], resolve(caminho).view_name)
        self.assertEqual(linha["route"], "oauth2_provider:oidc-connect-discovery-info")
        self.assertNotEqual(linha["route"], caminho)

        self.assertEqual(linha["method"], "GET")
        self.assertEqual(linha["status"], 200)
        self.assertIsInstance(linha["duration_ms"], (int, float))
        self.assertGreaterEqual(linha["duration_ms"], 0)

    def test_rota_que_nao_resolve_sai_com_o_sentinela_e_o_status_do_404(self):
        """O "-" é o valor que o middleware escreve quando `resolver_match` é None.
        A linha continua sendo emitida: "-" não está em
        `ACCESS_LOG_EXCLUDED_ROUTES`, e um 404 que não deixasse linha de acesso
        esconderia do operador a requisição que houve."""
        response = self.client.get("/rota-que-nao-existe-t13")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(len(self.coletor.linhas), 1, self.coletor.linhas)
        linha = self.coletor.linhas[0]

        self.assertEqual(linha["route"], "-")
        self.assertEqual(linha["method"], "GET")
        self.assertEqual(linha["status"], 404)
        self.assertIsInstance(linha["duration_ms"], (int, float))
        self.assertGreaterEqual(linha["duration_ms"], 0)
