"""T-04, T-06 a T-09, T-11 e T-12 — a trilha de auditoria e o isolamento dela sob a suíte.
T-02 (TASK-015/Fase 7) — o par `(ip, ip_src)` gravado em cada um dos cinco eventos.

Demanda do quality-assurance (TASK-013), sobre `accounts/auditoria.py` e sobre
`tests/runner.py`, que redireciona o handler `audit` durante `manage.py test` (ADR —
Architecture Decision Record — 0013). T-04 é unitário e puro; os demais atravessam a
trilha de verdade, lendo o arquivo real para onde o executor a redirecionou — nunca um
handler substituído pelo teste —, porque o ponto de T-06/T-07/T-08 é provar que a escrita
em arquivo aconteceu, e o de T-09 é provar que ela não aconteceu no lugar errado.

T-02 é integração pela mesma razão: o cálculo de `origem_e_procedencia` já está coberto,
função pura, em `tests/test_origem.py` (T-01); o que só um caminho HTTP real prova aqui é a
costura — o receptor de sinal ligado, o par chegando ao `extra=` do `logging` e sobrevivendo
ao `FormatadorJSON` (ADR 0018). Um receptor que esqueça `ip_src` passa em qualquer teste
unitário sobre a função de origem e apaga, na trilha gravada, a distinção entre
`remote_addr` e `remote_addr_fallback` que a ADR 0018 existe para criar.
"""

import hashlib
import json
import logging
import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings

from accounts.auditoria import _resumo_do_identificador
from config.observabilidade import FiltroRequestId, FormatadorJSON
from config.origem import origem_da_requisicao
from tests.oauth_helpers import (
    authorize_and_get_code,
    create_public_rs256_application,
    exchange_code_for_tokens,
)

User = get_user_model()


class _ColetorDeLinhas(logging.Handler):
    """Handler efêmero, usado por T-07, T-11 e T-12 para ler o log operacional.

    Duplicata deliberadamente pequena da classe homônima em
    `tests/test_observabilidade.py`: este arquivo não importa de outro arquivo
    de teste (só de `tests/oauth_helpers.py`, a infraestrutura compartilhada de
    verdade), para que cada arquivo continue lendo-se sozinho. A técnica é a
    mesma: o par filtro+formatador real de produção, anexado a um logger só
    para a duração de um teste.
    """

    def __init__(self):
        super().__init__()
        self.addFilter(FiltroRequestId())
        self.setFormatter(FormatadorJSON())
        self.linhas = []

    def emit(self, record):
        self.linhas.append(json.loads(self.format(record)))


def _handler_da_trilha():
    """O handler do logger "audit" em uso agora — real na produção, redirecionado
    para o diretório temporário sob a suíte (tests/runner.py)."""
    return logging.getLogger("audit").handlers[0]


def _tamanho_da_trilha():
    return os.path.getsize(_handler_da_trilha().baseFilename)


def _ler_linhas_novas_da_trilha(tamanho_antes):
    """As linhas escritas na trilha DEPOIS de `tamanho_antes`.

    Por posição de byte, e não por conteúdo do arquivo inteiro: a trilha é
    compartilhada por todo o processo da suíte, e outro arquivo de teste pode
    já ter escrito nela antes deste caso rodar. Ler só o que cresceu desde a
    marca própria de cada teste é o que torna a leitura independente da ordem
    de execução (AC-12).
    """
    with open(_handler_da_trilha().baseFilename, "r", encoding="utf-8") as arquivo:
        arquivo.seek(tamanho_antes)
        return [json.loads(linha) for linha in arquivo if linha.strip()]


class ResumoDoIdentificadorTests(SimpleTestCase):
    """T-04. Nível unitário: `_resumo_do_identificador` é função pura."""

    def test_mesmo_identificador_produz_o_mesmo_resumo(self):
        self.assertEqual(
            _resumo_do_identificador("pessoa@example.com"),
            _resumo_do_identificador("pessoa@example.com"),
        )

    def test_caixa_diferente_produz_resumo_diferente(self):
        """`accounts.User.email` é `unique=True` sob Postgres, sensível a caixa;
        normalizar aqui fundiria duas contas distintas numa mesma linha da
        trilha (razão registrada no docstring da própria função)."""
        self.assertNotEqual(
            _resumo_do_identificador("A@x.com"),
            _resumo_do_identificador("a@x.com"),
        )

    def test_identificador_ausente_devolve_none(self):
        """`None` é o caso de `authenticate()` chamado sem a credencial `username`."""
        self.assertIsNone(_resumo_do_identificador(None))

    def test_resumo_e_hexadecimal_completo_de_64_caracteres(self):
        """64 caracteres: SHA-256 (Secure Hash Algorithm) em hexadecimal completo,
        nunca truncado — truncar criaria colisão sem comprar privacidade."""
        resumo = _resumo_do_identificador("pessoa@example.com")

        self.assertEqual(len(resumo), 64)
        int(resumo, 16)  # levanta ValueError se não for hexadecimal


class QuatroSinaisPelosCaminhosHttpReaisTests(TestCase):
    """T-06. Cada evento nasce de uma requisição HTTP de verdade — nunca de uma
    chamada direta a um receptor —, o que prova que os quatro sinais estão de
    fato ligados por `AccountsConfig.ready()` e não só testáveis isoladamente."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="t06@example.com", password="senha-forte-o-suficiente-t06"
        )
        self.application = create_public_rs256_application(self.user)
        self.tamanho_antes = _tamanho_da_trilha()

    def test_os_quatro_eventos_pelos_caminhos_reais(self):
        # user_login_failed: senha errada pelo formulário de login.
        self.client.post(
            "/accounts/login/",
            {"username": "t06@example.com", "password": "senha-errada-t06"},
        )

        # user_logged_in: credenciais corretas pelo mesmo formulário — a sessão
        # aberta aqui é a que os dois passos seguintes reusam.
        login_response = self.client.post(
            "/accounts/login/",
            {"username": "t06@example.com", "password": "senha-forte-o-suficiente-t06"},
        )
        self.assertEqual(login_response.status_code, 302)

        # app_authorized: Authorization Code + PKCE (Proof Key for Code Exchange)
        # de ponta a ponta, sobre a sessão já autenticada.
        code, verifier, _resp = authorize_and_get_code(
            self.client, self.application, scope="openid"
        )
        self.assertIsNotNone(code, "consentimento não produziu code")
        token_response = exchange_code_for_tokens(self.client, self.application, code, verifier)
        self.assertEqual(token_response.status_code, 200)

        # user_logged_out: logout da sessão aberta acima.
        self.client.post("/accounts/logout/")

        linhas = _ler_linhas_novas_da_trilha(self.tamanho_antes)
        por_evento = {linha["event"]: linha for linha in linhas}

        self.assertEqual(
            set(por_evento),
            {"user_login_failed", "user_logged_in", "user_logged_out", "app_authorized"},
            linhas,
        )

        falha = por_evento["user_login_failed"]
        self.assertIsNone(falha["sub"])
        self.assertEqual(falha["outcome"], "failure")
        self.assertIn("identifier_sha256", falha)
        self.assertNotIn("client_id", falha)

        login = por_evento["user_logged_in"]
        self.assertEqual(login["sub"], str(self.user.pk))
        self.assertIsInstance(login["sub"], str)
        self.assertEqual(login["outcome"], "success")

        logout = por_evento["user_logged_out"]
        self.assertEqual(logout["sub"], str(self.user.pk))
        self.assertEqual(logout["outcome"], "success")

        autorizado = por_evento["app_authorized"]
        self.assertEqual(autorizado["sub"], str(self.user.pk))
        self.assertEqual(autorizado["client_id"], self.application.client_id)
        self.assertNotIn("identifier_sha256", autorizado)

        for linha in linhas:
            self.assertIn("ip", linha)


class NenhumSegredoVazaTests(TestCase):
    """T-07. Os valores procurados vêm da RESPOSTA do próprio fluxo em curso,
    nunca de uma constante fixa no teste — uma constante passaria para sempre
    sem checar nada (guarda explícita do quality-assurance)."""

    def setUp(self):
        self.email = "t07@example.com"
        self.senha = "senha-forte-o-suficiente-t07"
        self.user = User.objects.create_user(email=self.email, password=self.senha)
        self.application = create_public_rs256_application(self.user)
        # Loggers explicitamente declarados em LOGGING, cada um com
        # propagate=False: capturar o log operacional exige anexar o coletor a
        # cada um, porque nenhum deles borbulha para o root.
        self._loggers_operacionais = [
            logging.getLogger(nome)
            for nome in ("django", "django.request", "oauth2_provider", "access")
        ]
        self._coletor = _ColetorDeLinhas()
        for logger in self._loggers_operacionais:
            logger.addHandler(self._coletor)

    def tearDown(self):
        for logger in self._loggers_operacionais:
            logger.removeHandler(self._coletor)

    def test_nenhum_segredo_do_fluxo_aparece_na_trilha_nem_no_log_operacional(self):
        tamanho_trilha_antes = _tamanho_da_trilha()

        # A senha trafega em claro só aqui, no POST do formulário de login.
        login_response = self.client.post(
            "/accounts/login/", {"username": self.email, "password": self.senha}
        )
        self.assertEqual(login_response.status_code, 302)

        code, verifier, _resp = authorize_and_get_code(
            self.client, self.application, scope="openid"
        )
        self.assertIsNotNone(code, "consentimento não produziu code")

        token_response = exchange_code_for_tokens(self.client, self.application, code, verifier)
        self.assertEqual(token_response.status_code, 200)
        body = token_response.json()

        segredos = {
            "email": self.email,
            "senha": self.senha,
            "code": code,
            "code_verifier": verifier,
            "access_token": body["access_token"],
            "id_token": body["id_token"],
            "SECRET_KEY": settings.SECRET_KEY,
        }
        # refresh_token é opcional por grant; só entra na lista se o token
        # endpoint de fato o emitiu para este client.
        if "refresh_token" in body:
            segredos["refresh_token"] = body["refresh_token"]

        linhas_trilha = _ler_linhas_novas_da_trilha(tamanho_trilha_antes)
        trilha_serializada = "\n".join(
            json.dumps(linha, ensure_ascii=False) for linha in linhas_trilha
        )
        operacional_serializado = "\n".join(
            json.dumps(linha, ensure_ascii=False) for linha in self._coletor.linhas
        )

        for nome, valor in segredos.items():
            self.assertNotIn(valor, trilha_serializada, f"{nome} vazou na trilha")
            self.assertNotIn(valor, operacional_serializado, f"{nome} vazou no log operacional")


class LogoutSemSessaoTests(TestCase):
    """T-08. `POST /accounts/logout/` sem sessão autenticada."""

    def test_logout_sem_sessao_registra_evento_com_sub_nulo_sem_erro_operacional(self):
        tamanho_antes = _tamanho_da_trilha()

        # accounts.auditoria envolve o corpo inteiro de cada receptor num
        # `except Exception` que grita em ERROR no logger do próprio módulo
        # (nunca na trilha): auditar não pode negar o logout, então a falha, se
        # houver, tem de aparecer aqui — não silenciosamente na trilha.
        with self.assertNoLogs("accounts.auditoria", level="ERROR"):
            response = self.client.post("/accounts/logout/")

        self.assertEqual(response.status_code, 302)

        linhas = _ler_linhas_novas_da_trilha(tamanho_antes)
        eventos = [linha for linha in linhas if linha["event"] == "user_logged_out"]

        self.assertEqual(len(eventos), 1, linhas)
        self.assertIsNone(eventos[0]["sub"])


class TrilhaIsoladaDuranteASuiteTests(SimpleTestCase):
    """T-09. Nível unitário: não abre requisição nem sessão de banco — só
    confere o handler já redirecionado por `tests.runner.RunnerComTrilhaIsolada`
    (`setup_test_environment`, chamado antes de qualquer teste ser descoberto) e
    escreve uma linha direto no logger "audit", sem passar pelos sinais de
    `accounts/auditoria.py`."""

    def test_handler_audit_nao_aponta_para_o_arquivo_do_ambiente(self):
        caminho_em_uso = os.path.abspath(_handler_da_trilha().baseFilename)
        caminho_do_ambiente = os.path.abspath(settings.AUDIT_LOG_PATH)

        self.assertNotEqual(caminho_em_uso, caminho_do_ambiente)

    def test_arquivo_do_ambiente_nao_ganha_bytes_durante_a_suite(self):
        caminho_do_ambiente = os.path.abspath(settings.AUDIT_LOG_PATH)
        existe_antes = os.path.exists(caminho_do_ambiente)
        tamanho_antes = os.path.getsize(caminho_do_ambiente) if existe_antes else None

        logging.getLogger("audit").info(
            "linha de teste do T-09 -- nunca deve tocar o arquivo do ambiente"
        )

        existe_depois = os.path.exists(caminho_do_ambiente)
        tamanho_depois = os.path.getsize(caminho_do_ambiente) if existe_depois else None

        self.assertEqual(existe_antes, existe_depois)
        self.assertEqual(tamanho_antes, tamanho_depois)


class NenhumSegredoVazaPelaRaizTests(TestCase):
    """T-11. O mesmo fluxo de T-07, com o coletor anexado TAMBÉM ao logger raiz.

    T-07 varre os quatro loggers nomeados em `LOGGING` — `django`, `django.request`,
    `oauth2_provider` e `access` —, que é onde o código do projeto registra. Todo logger
    NÃO declarado ali (`oauthlib.*`, `redis.connection`, `django.db.backends`, e qualquer
    biblioteca que entre no `requirements.txt` amanhã) não é alcançado por aquela varredura:
    não tendo entrada própria, ele borbulha até a raiz e sai pelo handler `console` — o
    mesmo destino, o mesmo stdout do container, o mesmo olho de quem lê. A raiz é, portanto,
    a boca por onde um segredo sairia sem que nenhum dos quatro nomes o visse passar.

    As quatro anexações nomeadas continuam aqui ao lado da anexação à raiz, e não são
    redundância: os quatro têm `propagate=False`, de modo que um registro deles nunca chega
    à raiz — quem só anexasse à raiz deixaria de ver justamente o que T-07 vê.

    A varredura é feita nos NÍVEIS DE PRODUÇÃO, sem baixar o nível de logger nenhum: o que
    se quer provar é o que de fato sai pelo `console` com a configuração implantada. Baixar
    a raiz para DEBUG mediria uma configuração que não existe em lugar nenhum.
    """

    def setUp(self):
        self.email = "t11@example.com"
        self.senha = "senha-forte-o-suficiente-t11"
        self.user = User.objects.create_user(email=self.email, password=self.senha)
        self.application = create_public_rs256_application(self.user)
        self._loggers_operacionais = [
            logging.getLogger(nome)
            for nome in ("django", "django.request", "oauth2_provider", "access")
        ]
        # A raiz por último na lista só por leitura; a ordem não importa, porque um mesmo
        # handler anexado a vários loggers é chamado uma vez por registro que o alcança.
        self._loggers_operacionais.append(logging.getLogger())
        self._coletor = _ColetorDeLinhas()
        for logger in self._loggers_operacionais:
            logger.addHandler(self._coletor)

    def tearDown(self):
        for logger in self._loggers_operacionais:
            logger.removeHandler(self._coletor)

    def test_nenhum_segredo_do_fluxo_aparece_em_logger_algum_do_processo(self):
        tamanho_trilha_antes = _tamanho_da_trilha()

        login_response = self.client.post(
            "/accounts/login/", {"username": self.email, "password": self.senha}
        )
        self.assertEqual(login_response.status_code, 302)

        code, verifier, _resp = authorize_and_get_code(
            self.client, self.application, scope="openid"
        )
        self.assertIsNotNone(code, "consentimento não produziu code")

        token_response = exchange_code_for_tokens(self.client, self.application, code, verifier)
        self.assertEqual(token_response.status_code, 200)
        body = token_response.json()

        # Todos os valores saem da resposta do próprio fluxo ou das variáveis deste caso.
        # Nenhuma constante fixa: uma constante que o fluxo não produz passaria para sempre
        # sem ter checado coisa alguma.
        segredos = {
            "email": self.email,
            "senha": self.senha,
            "code": code,
            "code_verifier": verifier,
            "access_token": body["access_token"],
            "id_token": body["id_token"],
            "SECRET_KEY": settings.SECRET_KEY,
        }
        if "refresh_token" in body:
            segredos["refresh_token"] = body["refresh_token"]

        # O coletor tem de ter visto alguma coisa: zero linha capturada faria a varredura
        # abaixo passar por vacuidade, e é assim que um teste desses apodrece calado.
        self.assertGreater(len(self._coletor.linhas), 0)

        linhas_trilha = _ler_linhas_novas_da_trilha(tamanho_trilha_antes)
        trilha_serializada = "\n".join(
            json.dumps(linha, ensure_ascii=False) for linha in linhas_trilha
        )
        operacional_serializado = "\n".join(
            json.dumps(linha, ensure_ascii=False) for linha in self._coletor.linhas
        )

        for nome, valor in segredos.items():
            self.assertNotIn(valor, trilha_serializada, f"{nome} vazou na trilha")
            self.assertNotIn(
                valor,
                operacional_serializado,
                f"{nome} vazou no log operacional (varredura com a raiz incluída)",
            )


class FalhaDeLoginNaoRevelaOEmailTests(TestCase):
    """T-12. A falha de autenticação pelo caminho HTTP real.

    É o único caminho em que o e-mail digitado chega a um receptor de sinal: ele vem em
    `credentials["username"]`, e `django.contrib.auth._clean_credentials` não saneia essa
    chave — só as que comparam com api|token|key|secret|password|signature. Quem monta esse
    dicionário é o `AuthenticationForm` da view de login, não este teste; por isso a
    requisição é real, e não uma chamada direta a `registrar_falha_de_login`.

    O e-mail é de caixa mista de propósito. `_resumo_do_identificador` resume o valor COMO
    RECEBIDO, sem `lower`, porque `accounts.User.email` é sensível a caixa sob Postgres — e
    é o resumo do valor digitado, não o de uma versão normalizada dele, que a linha tem de
    trazer.
    """

    def setUp(self):
        # Domínio já em minúsculas: `BaseUserManager.normalize_email` baixa a caixa do
        # domínio e preserva a da parte local, de modo que o valor digitado abaixo é
        # exatamente o valor gravado — a conta existe como digitada, e a autenticação
        # falha pela senha, que é o caminho que este caso quer.
        self.email = "T12.Pessoa@example.com"
        self.senha = "senha-forte-o-suficiente-t12"
        self.senha_errada = "senha-errada-t12"
        self.user = User.objects.create_user(email=self.email, password=self.senha)
        self.assertEqual(self.user.email, self.email)

        self._loggers_operacionais = [
            logging.getLogger(nome)
            for nome in ("django", "django.request", "oauth2_provider", "access")
        ]
        self._loggers_operacionais.append(logging.getLogger())
        self._coletor = _ColetorDeLinhas()
        for logger in self._loggers_operacionais:
            logger.addHandler(self._coletor)

    def tearDown(self):
        for logger in self._loggers_operacionais:
            logger.removeHandler(self._coletor)

    def test_senha_errada_grava_o_resumo_e_nunca_o_email_digitado(self):
        tamanho_antes = _tamanho_da_trilha()

        response = self.client.post(
            "/accounts/login/",
            {"username": self.email, "password": self.senha_errada},
        )

        # 200, e não 302: o formulário volta a ser renderizado com o erro, e nenhuma
        # sessão é aberta.
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

        linhas = _ler_linhas_novas_da_trilha(tamanho_antes)
        falhas = [linha for linha in linhas if linha["event"] == "user_login_failed"]
        self.assertEqual(len(falhas), 1, linhas)

        # O resumo esperado é calculado aqui, com a stdlib, sobre a variável do setUp —
        # nunca por `_resumo_do_identificador`, que é a própria função sob prova: usá-la
        # faria a asserção concordar consigo mesma.
        esperado = hashlib.sha256(self.email.encode("utf-8")).hexdigest()
        self.assertEqual(falhas[0]["identifier_sha256"], esperado)
        self.assertNotEqual(
            falhas[0]["identifier_sha256"],
            hashlib.sha256(self.email.lower().encode("utf-8")).hexdigest(),
        )

        trilha_serializada = "\n".join(
            json.dumps(linha, ensure_ascii=False) for linha in linhas
        )
        operacional_serializado = "\n".join(
            json.dumps(linha, ensure_ascii=False) for linha in self._coletor.linhas
        )

        for destino, serializado in (
            ("trilha", trilha_serializada),
            ("log operacional", operacional_serializado),
        ):
            self.assertNotIn(self.email, serializado, f"e-mail digitado vazou na {destino}")
            self.assertNotIn(self.senha_errada, serializado, f"senha vazou na {destino}")


class ParDeOrigemNaTrilhaTests(TestCase):
    """T-02 (TASK-015/Fase 7). `ip` e `ip_src` PRESENTES em cada um dos cinco eventos,
    pelo caminho HTTP real, com o `ip_src` correspondente ao ramo de `BEHIND_TLS_PROXY`
    vigente e o `ip` igual ao que a MESMA requisição entregaria a `origem_da_requisicao`.

    A comparação nunca é contra um endereço fixo escrito no teste: é contra
    `origem_da_requisicao(resposta.wsgi_request)`, chamada sobre o objeto de requisição
    que o próprio Django processou. É o que prova a costura — que o receptor de sinal
    passa adiante o MESMO `request` e não recalcula, arredonda ou lê `REMOTE_ADDR` direto
    — sem duplicar aqui a tabela de decisão da função, que é o que T-01 já cobre.

    Toda asserção sobre `ip_src` é `assertIn` sobre a chave, nunca sobre o valor: é a
    PRESENÇA da chave que versiona a linha (ADR 0018) — uma linha gravada antes desta
    decisão não tem `ip_src` nenhum, e o valor, quando presente, pode legitimamente ser
    qualquer um dos três rótulos, `None` inclusive fora de uma requisição HTTP (T-01 cobre
    esse desfecho; não é alcançável pelos cinco eventos aqui, que nascem todos de uma
    requisição HTTP de verdade).
    """

    def setUp(self):
        self.senha = "senha-forte-o-suficiente-t02"
        self.user = User.objects.create_user(email="t02-ipsrc@example.com", password=self.senha)
        self.application = create_public_rs256_application(self.user)

    @override_settings(BEHIND_TLS_PROXY=False)
    def test_quatro_eventos_por_sessao_trazem_ip_e_ip_src_coerentes_com_a_origem(self):
        """`BEHIND_TLS_PROXY=False` explícito, e não ambiente: a segunda jornada de
        verificação (`docs/runbook.md`) exporta essa variável como `True` por padrão, e sem
        o override este caso mediria o ramo errado — `remote_addr_fallback`, por cabeçalho
        ausente — dependendo de qual jornada o executasse. O ramo que este caso prova é o
        de `BEHIND_TLS_PROXY` desligado, e ele vale sob qualquer jornada só por dizê-lo."""
        tamanho_antes = _tamanho_da_trilha()

        falha = self.client.post(
            "/accounts/login/",
            {"username": self.user.email, "password": "senha-errada-t02"},
            REMOTE_ADDR="203.0.113.10",
        )
        ip_esperado_falha = origem_da_requisicao(falha.wsgi_request)

        sucesso = self.client.post(
            "/accounts/login/",
            {"username": self.user.email, "password": self.senha},
            REMOTE_ADDR="203.0.113.10",
        )
        self.assertEqual(sucesso.status_code, 302)
        ip_esperado_sucesso = origem_da_requisicao(sucesso.wsgi_request)

        code, verifier, _resp = authorize_and_get_code(
            self.client, self.application, scope="openid"
        )
        self.assertIsNotNone(code, "consentimento não produziu code")
        token_response = exchange_code_for_tokens(self.client, self.application, code, verifier)
        self.assertEqual(token_response.status_code, 200)
        ip_esperado_autorizacao = origem_da_requisicao(token_response.wsgi_request)

        logout = self.client.post("/accounts/logout/", REMOTE_ADDR="203.0.113.10")
        ip_esperado_logout = origem_da_requisicao(logout.wsgi_request)

        linhas = _ler_linhas_novas_da_trilha(tamanho_antes)
        por_evento = {linha["event"]: linha for linha in linhas}

        esperado_por_evento = {
            "user_login_failed": ip_esperado_falha,
            "user_logged_in": ip_esperado_sucesso,
            "app_authorized": ip_esperado_autorizacao,
            "user_logged_out": ip_esperado_logout,
        }

        for evento, ip_esperado in esperado_por_evento.items():
            self.assertIn(evento, por_evento, linhas)
            linha = por_evento[evento]
            self.assertIn("ip", linha, linha)
            self.assertIn("ip_src", linha, linha)
            self.assertEqual(linha["ip"], ip_esperado, linha)
            # `BEHIND_TLS_PROXY=False` vem do override da classe (:507), não do ambiente:
            # sem ele, este caso passaria nas duas jornadas por motivos diferentes — pelo
            # ramo `remote_addr` na de construção, pelo `remote_addr_fallback` na de
            # container — e a asserção abaixo deixaria de significar o que o nome promete.
            self.assertEqual(linha["ip_src"], "remote_addr", linha)

    @override_settings(BEHIND_TLS_PROXY=False)
    def test_user_locked_out_traz_ip_e_ip_src_coerentes_com_a_origem(self):
        """O quinto evento, que só a ADR 0016 introduziu — fora do laço de sessão acima
        porque nasce de cinco tentativas, e não de uma sessão só. A conta não precisa
        existir: o axes conta a falha de qualquer forma (mesma guarda do T-04 de
        `tests/test_limite_login.py`). `BEHIND_TLS_PROXY=False` explícito pela mesma razão
        do caso acima — a segunda jornada de verificação liga essa variável por padrão."""
        tamanho_antes = _tamanho_da_trilha()

        ultima_resposta = None
        for _ in range(5):
            ultima_resposta = self.client.post(
                "/accounts/login/",
                {"username": "bloqueio-t02@example.com", "password": "senha-errada"},
                REMOTE_ADDR="198.51.100.20",
            )
        self.assertEqual(ultima_resposta.status_code, 429, "quinta falha não bloqueou")
        ip_esperado = origem_da_requisicao(ultima_resposta.wsgi_request)

        linhas = _ler_linhas_novas_da_trilha(tamanho_antes)
        bloqueios = [linha for linha in linhas if linha["event"] == "user_locked_out"]

        self.assertEqual(len(bloqueios), 1, linhas)
        linha = bloqueios[0]
        self.assertIn("ip", linha, linha)
        self.assertIn("ip_src", linha, linha)
        self.assertEqual(linha["ip"], ip_esperado, linha)
        self.assertEqual(linha["ip_src"], "remote_addr", linha)

    @override_settings(BEHIND_TLS_PROXY=True, TRUSTED_PROXY_COUNT=1)
    def test_sob_proxy_ip_e_ip_src_mudam_juntos_de_remote_addr_para_forwarded(self):
        """A alínea que prova que os dois campos giram JUNTOS: o mesmo evento
        (`user_login_failed`) que grava `remote_addr` no teste acima grava `forwarded`
        aqui, e o `ip` muda do endereço do proxy para o salto declarado — nunca um dos
        dois campos sem o outro."""
        tamanho_antes = _tamanho_da_trilha()

        falha = self.client.post(
            "/accounts/login/",
            {"username": self.user.email, "password": "senha-errada-t02-proxy"},
            REMOTE_ADDR="172.16.0.1",
            HTTP_X_FORWARDED_FOR="203.0.113.55",
        )
        # Calculado ENQUANTO o override ainda vale: `origem_e_procedencia` lê as duas
        # settings a cada chamada (nunca no import), e calcular depois de sair do bloco
        # compararia contra `BEHIND_TLS_PROXY=False` — o valor de fora do teste — e não
        # contra o que a própria requisição gravou.
        ip_esperado = origem_da_requisicao(falha.wsgi_request)

        linhas = _ler_linhas_novas_da_trilha(tamanho_antes)
        falhas = [linha for linha in linhas if linha["event"] == "user_login_failed"]

        self.assertEqual(len(falhas), 1, linhas)
        linha = falhas[0]
        self.assertIn("ip", linha, linha)
        self.assertIn("ip_src", linha, linha)
        self.assertEqual(linha["ip_src"], "forwarded", linha)
        self.assertEqual(linha["ip"], ip_esperado, linha)
        self.assertEqual(linha["ip"], "203.0.113.55", linha)
        self.assertNotEqual(linha["ip"], "172.16.0.1", linha)
