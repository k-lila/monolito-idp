"""T-02, T-03, T-04, T-05, T-06, T-08, T-12, T-14, T-16, T-18 — a limitação de taxa de
`/accounts/login/`: a semântica de segurança do `django-axes` (T-02 a T-08, T-12) e o teto de
requisição de `config/limites.py` que convive com ela na mesma porta (T-14, T-16, T-18).

Demanda do quality-assurance (TASK-014, blocos B e a 3ª passagem), sobre
`AUTHENTICATION_BACKENDS`, `AxesStandaloneBackend`, `AxesMiddleware`,
`AXES_LOCKOUT_PARAMETERS`, `AXES_USERNAME_FORM_FIELD` e `RATE_LIMIT_POR_CAMINHO` em
`config/settings.py`. Nível integração nos casos do axes: o bloqueio não está em peça
isolável nenhuma, e só a resposta HTTP revela o resultado — um unitário sobre o handler do
axes testaria a biblioteca, não esta configuração. T-16 é a exceção: unitário, porque é uma
relação entre duas settings, sem I/O.

REGRA QUE VALE PARA TODO CASO, inclusive os do axes: `REMOTE_ADDR` explícito e forjado. Os
casos do axes (T-02 a T-08, T-12) não precisam dele pela razão do limitador de taxa — contam
por `REMOTE_ADDR`/username no Postgres, já limpo pelo rollback de cada `TestCase`, sem
depender de `tests/runner.py` —, mas os que ligam o teto de requisição por `override_settings`
(T-14) precisam: o contador dele vive no Redis do ambiente, e a chave é a mesma que o
`runserver` da jornada de construção usa. Ver `tests/runner.py` (T-10, revisado por T-13) e o
módulo `config.limites`.
"""

import hashlib
import json
import logging

from axes.models import AccessAttempt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from datetime import timedelta

import tests.runner as runner
from config.limites import chave_do_contador
from config.observabilidade import FiltroRequestId, FormatadorJSON
from tests.test_template_comment_leak import assert_no_template_comment_delimiters

User = get_user_model()


class _ColetorDeLinhas(logging.Handler):
    """Duplicata pequena e deliberada da classe homônima de outros arquivos de teste (ver
    razão em `tests/test_auditoria.py`): cada arquivo continua legível sozinho."""

    def __init__(self):
        super().__init__()
        self.addFilter(FiltroRequestId())
        self.setFormatter(FormatadorJSON())
        self.linhas = []

    def emit(self, record):
        self.linhas.append(json.loads(self.format(record)))


class BloqueioPorContaTests(TestCase):
    """T-02 — AC-01. Cinco falhas contra o MESMO `username`, cada uma de uma origem
    diferente, bloqueiam pela conta; a credencial correta, vinda de uma sexta origem,
    continua recusada enquanto o bloqueio durar."""

    def setUp(self):
        self.email = "alvo@exemplo.com"
        self.senha = "senha-forte-o-suficiente-t02"
        self.user = User.objects.create_user(email=self.email, password=self.senha)

    def test_quinta_falha_contra_a_mesma_conta_bloqueia_mesmo_com_origens_diferentes(self):
        codigos = []
        for i in range(1, 5):
            response = self.client.post(
                "/accounts/login/",
                {"username": self.email, "password": "senha-errada"},
                REMOTE_ADDR=f"10.10.0.{i}",
            )
            codigos.append(response.status_code)
        self.assertEqual(codigos, [200, 200, 200, 200])

        quinta = self.client.post(
            "/accounts/login/",
            {"username": self.email, "password": "senha-errada"},
            REMOTE_ADDR="10.10.0.5",
        )
        self.assertEqual(quinta.status_code, 429)

        sexta = self.client.post(
            "/accounts/login/",
            {"username": self.email, "password": self.senha},
            REMOTE_ADDR="10.10.0.99",
        )

        self.assertEqual(sexta.status_code, 429)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertNotIn(self.email, sexta.content.decode())


class BloqueioPorOrigemTests(TestCase):
    """T-03 — AC-02. Cinco falhas contra contas DIFERENTES, todas da MESMA origem,
    bloqueiam pela origem; outra origem continua livre. Vive ao lado do T-02 de propósito
    — se `AXES_LOCKOUT_PARAMETERS` virar `[["username", "ip_address"]]`, um elemento só
    com as duas chaves dentro, o axes passa a contar pelo PAR e os dois falham juntos.
    (Verificado à mão pelo QA (`quality-assurance`), TASK-014: perder só os colchetes
    internos — `["username", "ip_address"]`, dois elementos, dois filtros independentes —
    NÃO produz esse efeito; a suíte continua verde. `axes/helpers.py:285-293` trata cada
    ELEMENTO da lista como um filtro: elemento string filtra por uma chave, elemento lista
    filtra pela combinação das chaves dele — é o número de elementos que decide, não a
    presença dos colchetes internos em si.)"""

    def setUp(self):
        self.senha = "senha-forte-o-suficiente-t03"
        self.contas = [
            User.objects.create_user(email=f"conta{i}@exemplo.com", password=self.senha)
            for i in range(5)
        ]

    def test_quinta_falha_da_mesma_origem_bloqueia_mesmo_com_contas_diferentes(self):
        codigos = []
        for i in range(4):
            response = self.client.post(
                "/accounts/login/",
                {"username": self.contas[i].email, "password": "senha-errada"},
                REMOTE_ADDR="10.20.0.1",
            )
            codigos.append(response.status_code)
        self.assertEqual(codigos, [200, 200, 200, 200])

        quinta = self.client.post(
            "/accounts/login/",
            {"username": self.contas[4].email, "password": "senha-errada"},
            REMOTE_ADDR="10.20.0.1",
        )
        self.assertEqual(quinta.status_code, 429)

        # A mesma origem continua bloqueada mesmo para uma credencial correta.
        credencial_correta_mesma_origem = self.client.post(
            "/accounts/login/",
            {"username": self.contas[0].email, "password": self.senha},
            REMOTE_ADDR="10.20.0.1",
        )
        self.assertEqual(credencial_correta_mesma_origem.status_code, 429)

        # Sem essa metade o teste não distingue "bloqueou por origem" de "bloqueou tudo".
        credencial_correta_outra_origem = self.client.post(
            "/accounts/login/",
            {"username": self.contas[0].email, "password": self.senha},
            REMOTE_ADDR="10.20.0.2",
        )
        self.assertEqual(credencial_correta_outra_origem.status_code, 302)
        self.assertEqual(credencial_correta_outra_origem.get("Location"), "/")
        self.assertIn("_auth_user_id", self.client.session)


class DoisClientesAtrasDoMesmoProxyTests(TestCase):
    """T-04 — AC-03. `BEHIND_TLS_PROXY=True`, `TRUSTED_PROXY_COUNT=1`: dois clientes com o
    MESMO `REMOTE_ADDR` (o proxy) e `X-Forwarded-For` distintos não compartilham contador.
    Provável em processo, e não fim-a-fim (registro explícito do QA)."""

    def setUp(self):
        self.senha = "senha-forte-o-suficiente-t04"
        self.user = User.objects.create_user(email="clienteb@exemplo.com", password=self.senha)

    def test_dois_clientes_atras_do_mesmo_proxy_nao_compartilham_contador(self):
        with self.settings(BEHIND_TLS_PROXY=True, TRUSTED_PROXY_COUNT=1):
            for _ in range(4):
                self.client.post(
                    "/accounts/login/",
                    {"username": "clientea@exemplo.com", "password": "senha-errada"},
                    REMOTE_ADDR="172.16.0.1",
                    HTTP_X_FORWARDED_FOR="203.0.113.7",
                )
            quinta_a = self.client.post(
                "/accounts/login/",
                {"username": "clientea@exemplo.com", "password": "senha-errada"},
                REMOTE_ADDR="172.16.0.1",
                HTTP_X_FORWARDED_FOR="203.0.113.7",
            )
            self.assertEqual(quinta_a.status_code, 429)

            cliente_b = self.client.post(
                "/accounts/login/",
                {"username": self.user.email, "password": self.senha},
                REMOTE_ADDR="172.16.0.1",
                HTTP_X_FORWARDED_FOR="198.51.100.9",
            )
            self.assertEqual(cliente_b.status_code, 302)
            self.assertEqual(cliente_b.get("Location"), "/")

    def test_guarda_contra_ler_o_primeiro_elemento_do_xff(self):
        """O cliente forja o cabeçalho, e o proxy anexa o salto real à direita a cada
        tentativa. As cinco caem na MESMA chave DE ORIGEM — a de `198.51.100.55`, o salto
        real — e bloqueiam na quinta assim mesmo, mesmo com uma CONTA DIFERENTE a cada
        tentativa (nenhuma precisa existir; o axes conta a falha de qualquer forma, como o
        T-06 já prova). Contas diferentes é o que garante que só o contador POR ORIGEM pode
        produzir este bloqueio — com a mesma conta repetida, como a versão anterior deste
        caso fazia, o contador POR CONTA também chegaria a cinco, e o 429 não distinguiria
        qual dos dois mecanismos disparou.

        Se `origem_da_requisicao` fosse "consertada" para ler o primeiro elemento, as cinco
        cairiam em cinco chaves de origem distintas — e, com contas também distintas, em
        cinco chaves de conta distintas — e nenhuma bloquearia; é essa mudança que este caso
        impede de passar despercebida."""
        with self.settings(BEHIND_TLS_PROXY=True, TRUSTED_PROXY_COUNT=1):
            for i in range(4):
                self.client.post(
                    "/accounts/login/",
                    {"username": f"forja{i}@exemplo.com", "password": "senha-errada"},
                    REMOTE_ADDR="172.16.0.1",
                    HTTP_X_FORWARDED_FOR=f"1.2.3.{i}, 198.51.100.55",
                )
            quinta = self.client.post(
                "/accounts/login/",
                {"username": "forja4@exemplo.com", "password": "senha-errada"},
                REMOTE_ADDR="172.16.0.1",
                HTTP_X_FORWARDED_FOR="1.2.3.4, 198.51.100.55",
            )
            self.assertEqual(quinta.status_code, 429)


class PrazoDoBloqueioTests(TestCase):
    """T-05 — AC-04, as duas metades do prazo. Manipula `attempt_time` diretamente no
    Postgres: é a única forma de não esperar quinze minutos, e é honesta — mexe no dado, não
    no código."""

    def setUp(self):
        self.email = "prazo@exemplo.com"
        self.senha = "senha-forte-o-suficiente-t05"
        self.user = User.objects.create_user(email=self.email, password=self.senha)
        self.origem = "10.30.0.1"

    def _cinco_falhas(self):
        for _ in range(5):
            self.client.post(
                "/accounts/login/",
                {"username": self.email, "password": "senha-errada"},
                REMOTE_ADDR=self.origem,
            )

    def test_a_fim_observavel_apos_o_prazo_a_credencial_valida_volta_a_autenticar(self):
        self._cinco_falhas()
        bloqueado = self.client.post(
            "/accounts/login/",
            {"username": self.email, "password": self.senha},
            REMOTE_ADDR=self.origem,
        )
        self.assertEqual(bloqueado.status_code, 429)

        AccessAttempt.objects.update(attempt_time=timezone.now() - timedelta(minutes=16))

        depois_do_prazo = self.client.post(
            "/accounts/login/",
            {"username": self.email, "password": self.senha},
            REMOTE_ADDR=self.origem,
        )
        self.assertEqual(depois_do_prazo.status_code, 302)
        self.assertEqual(depois_do_prazo.get("Location"), "/")

    def test_b_prazo_movel_insistir_durante_o_bloqueio_adia_o_fim(self):
        self._cinco_falhas()
        AccessAttempt.objects.update(attempt_time=timezone.now() - timedelta(minutes=14))

        instante_antes_da_nova_tentativa = timezone.now()
        self.client.post(
            "/accounts/login/",
            {"username": self.email, "password": "senha-errada"},
            REMOTE_ADDR=self.origem,
        )

        attempt_time_depois = AccessAttempt.objects.get().attempt_time
        self.assertGreater(attempt_time_depois, instante_antes_da_nova_tentativa)


class ContaInexistenteTambemBloqueiaTests(TestCase):
    """T-06, ampliado por T-18 — AC-05. Não há oráculo de existência: uma conta que não
    corresponde a ninguém bloqueia exatamente como uma que existe, e o corpo do 429 não vaza
    o identificador nem o teto. T-18 acrescenta, ao mesmo caso, a prova de que este 429 é
    identificável como o do `django-axes` e não o do teto de requisição da mesma porta."""

    def setUp(self):
        self.origem = "10.40.0.1"

    def test_a_cinco_falhas_contra_conta_inexistente_bloqueiam_na_quinta(self):
        codigos = []
        for _ in range(5):
            response = self.client.post(
                "/accounts/login/",
                {"username": "nao-existe@exemplo.com", "password": "senha-qualquer"},
                REMOTE_ADDR=self.origem,
            )
            codigos.append(response.status_code)

        self.assertEqual(codigos, [200, 200, 200, 200, 429])

    def test_b_corpo_do_429_nao_vaza_identificador_teto_nem_delimitador_de_comentario(self):
        for _ in range(5):
            resposta = self.client.post(
                "/accounts/login/",
                {"username": "nao-existe@exemplo.com", "password": "senha-qualquer"},
                REMOTE_ADDR=self.origem,
            )

        html = resposta.content.decode()
        self.assertEqual(resposta.status_code, 429)
        self.assertNotIn("nao-existe@exemplo.com", html)
        self.assertNotIn(str(settings.AXES_FAILURE_LIMIT), html)
        # Reusa a guarda de tests/test_template_comment_leak.py: traz a quarta tela
        # (bloqueio.html) para dentro da mesma guarda de comentário, sem precisar de
        # teste próprio para isso.
        assert_no_template_comment_delimiters(self, html)

        # T-18 — a discriminação: este 429 é o do axes, e não o do outro mecanismo que
        # recusa na mesma porta (`config.limites.LimiteDeTaxaMiddleware`, T-14). O axes
        # renderiza `AXES_LOCKOUT_TEMPLATE` (`registration/bloqueio.html`) como página HTML
        # de verdade, e nunca emite `Retry-After` — o middleware, ao contrário, sempre
        # devolve JSON com `Retry-After` (T-14, alínea c). Um caso só basta: o que se guarda
        # é que os dois 429 são distinguíveis, e isso se prova uma vez.
        self.assertTrue(resposta["Content-Type"].startswith("text/html"))
        self.assertIn("<html", html.lower())
        self.assertNotIn("Retry-After", resposta)

    def test_c_senha_errada_isolada_continua_distinguivel_do_429(self):
        User.objects.create_user(email="c06@exemplo.com", password="senha-forte-o-suficiente")

        resposta = self.client.post(
            "/accounts/login/",
            {"username": "c06@exemplo.com", "password": "senha-errada"},
            REMOTE_ADDR="10.40.0.2",
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertIn("errorlist", resposta.content.decode())


class IgualdadeDeOrigemComATrilhaTests(TestCase):
    """T-08 — AC-08. A igualdade, na forma mais forte que existe: o que o axes CONTOU
    (`AccessAttempt.ip_address`) e o que a trilha GRAVOU (campo `ip` de `user_locked_out`)
    são o mesmo valor, e nenhum dos dois é o `REMOTE_ADDR` do proxy — sobre a MESMA
    requisição que bloqueou."""

    def setUp(self):
        self.email = "t08@exemplo.com"
        self.senha = "senha-forte-o-suficiente-t08"
        self.user = User.objects.create_user(email=self.email, password=self.senha)

    def _handler_da_trilha(self):
        return logging.getLogger("audit").handlers[0]

    def _ler_linhas_novas_da_trilha(self, tamanho_antes):
        with open(self._handler_da_trilha().baseFilename, "r", encoding="utf-8") as arquivo:
            arquivo.seek(tamanho_antes)
            return [json.loads(linha) for linha in arquivo if linha.strip()]

    def test_c_ip_contado_pelo_axes_e_ip_gravado_pela_trilha_sao_iguais_e_nao_e_o_proxy(self):
        import os

        tamanho_antes = os.path.getsize(self._handler_da_trilha().baseFilename)

        with self.settings(BEHIND_TLS_PROXY=True, TRUSTED_PROXY_COUNT=1):
            for _ in range(4):
                self.client.post(
                    "/accounts/login/",
                    {"username": self.email, "password": "senha-errada"},
                    REMOTE_ADDR="172.16.0.1",
                    HTTP_X_FORWARDED_FOR="203.0.113.7",
                )
            bloqueio = self.client.post(
                "/accounts/login/",
                {"username": self.email, "password": "senha-errada"},
                REMOTE_ADDR="172.16.0.1",
                HTTP_X_FORWARDED_FOR="203.0.113.7",
            )
            self.assertEqual(bloqueio.status_code, 429)

        ip_contado = AccessAttempt.objects.get().ip_address

        linhas = self._ler_linhas_novas_da_trilha(tamanho_antes)
        linhas_de_bloqueio = [linha for linha in linhas if linha["event"] == "user_locked_out"]
        self.assertEqual(len(linhas_de_bloqueio), 1, linhas)
        linha = linhas_de_bloqueio[0]

        # (a) o que o axes contou.
        self.assertEqual(ip_contado, "203.0.113.7")
        # (b) o que a trilha gravou.
        self.assertEqual(linha["ip"], "203.0.113.7")
        # (c) os dois são iguais entre si, e nenhum é o REMOTE_ADDR do proxy.
        self.assertEqual(ip_contado, linha["ip"])
        self.assertNotEqual(ip_contado, "172.16.0.1")
        self.assertNotEqual(linha["ip"], "172.16.0.1")

        # (d) os demais campos da linha.
        self.assertEqual(linha["event"], "user_locked_out")
        self.assertIsNone(linha["sub"])
        self.assertEqual(
            linha["identifier_sha256"], hashlib.sha256(self.email.encode("utf-8")).hexdigest()
        )
        self.assertEqual(linha["outcome"], "blocked")

        # (e) nenhuma linha da trilha traz o e-mail em claro.
        for l in linhas:
            self.assertNotIn(self.email, json.dumps(l, ensure_ascii=False))


ORIGEM_T14 = "10.60.0.1"
ORIGEM_T14_OUTRA = "10.60.0.2"


@override_settings(
    RATE_LIMIT_POR_CAMINHO={"/accounts/login/": 2}, RATE_LIMIT_JANELA_SEGUNDOS=60
)
class TetoDeRequisicaoDoLoginTests(TestCase):
    """T-14 — o teto de requisição de `/accounts/login/`, aplicado por
    `config.limites.LimiteDeTaxaMiddleware`, e a distinção entre a recusa DELE e a recusa do
    `django-axes` na mesma porta.

    GET anônimo em todo caso, nunca POST com senha errada: o POST convocaria o axes, e o
    mesmo 429 passaria a ter duas causas possíveis dentro do caso — o GET não conta falha
    nenhuma e isola o mecanismo sob teste.

    Teto baixo por `override_settings` (2), e não as sessenta requisições de produção: pelo
    precedente do T-07, um caso que fizesse 61 requisições para provar que a 61ª passa do
    teto provaria só que o teste reescreve o literal `60` — tautologia que quebra em toda
    revisão de política e não verifica nada que o teto 2 não verifique. O número 60 em si não
    merece asserção; o que merece guarda é a RELAÇÃO dele com o teto do axes, e essa é o
    T-16.

    As chaves são apagadas por `chave_do_contador`, nunca por `cache.clear()` — que o
    `RedisCache` implementa como `FLUSHDB` e levaria junto a cópia quente das sessões
    (ADR 0005)."""

    def setUp(self):
        self._chave = chave_do_contador("/accounts/login/", ORIGEM_T14)
        self._chave_outra = chave_do_contador("/accounts/login/", ORIGEM_T14_OUTRA)
        cache.delete(self._chave)
        cache.delete(self._chave_outra)

    def tearDown(self):
        cache.delete(self._chave)
        cache.delete(self._chave_outra)

    def test_terceira_requisicao_e_429_do_middleware_sem_convocar_o_axes(self):
        codigos = []
        for _ in range(2):
            resposta = self.client.get("/accounts/login/", REMOTE_ADDR=ORIGEM_T14)
            codigos.append(resposta.status_code)
        self.assertEqual(codigos, [200, 200])

        terceira = self.client.get("/accounts/login/", REMOTE_ADDR=ORIGEM_T14)

        # (a) — o 429 do middleware, com o corpo e o cabeçalho do protocolo.
        self.assertEqual(terceira.status_code, 429)
        self.assertEqual(terceira["Retry-After"], "60")
        corpo = terceira.json()
        self.assertEqual(corpo["error"], "temporarily_unavailable")
        self.assertIn("error_description", corpo)

        # (b) — a recusa não chegou a `authenticate()`. É a divisão de papéis inteira entre
        # este teto e o axes: sem este critério o caso não distingue este 429 do 429 do
        # axes, que SEMPRE conta uma linha em AccessAttempt para uma tentativa recusada.
        self.assertEqual(AccessAttempt.objects.count(), 0)

        # (c) — a resposta é JSON e não é a página do axes. Sem este critério, a página de
        # bloqueio (`registration/bloqueio.html`, text/html) poderia substituir o corpo JSON
        # sem que nada aqui acusasse.
        self.assertTrue(terceira["Content-Type"].startswith("application/json"))
        self.assertNotIn("<html", terceira.content.decode().lower())

        # (d) — outra origem não compartilha contador.
        outra_origem = self.client.get("/accounts/login/", REMOTE_ADDR=ORIGEM_T14_OUTRA)
        self.assertEqual(outra_origem.status_code, 200)

        # (e) — apagar a chave pela função de produção devolve a origem bloqueada a 200.
        cache.delete(self._chave)
        seguinte = self.client.get("/accounts/login/", REMOTE_ADDR=ORIGEM_T14)
        self.assertEqual(seguinte.status_code, 200)


class InvarianteEntreOTetoDoLoginEOAxesTests(TestCase):
    """T-16 — a invariante entre os dois mecanismos da mesma porta: o teto de requisição de
    `/accounts/login/` (`config.limites`) tem de ficar ACIMA do teto de falhas do axes
    (`AXES_FAILURE_LIMIT`).

    O QUE ISSO GUARDA, medido pelo QA (`quality-assurance`): com o teto do middleware em 3 e
    o do axes em 5, seis POST com senha errada da mesma origem produzem
    `[200, 200, 200, 429, 429, 429]` — os três últimos em JSON —, e o axes para em 3 falhas
    registradas. Ele NUNCA tranca: a página "Tentativas em excesso" deixa de ser alcançável,
    e a semântica de segurança migra, calada, de um mecanismo que conta por conta e esquece
    em quinze minutos para um que não conhece conta e esquece em sessenta segundos. Nada no
    sistema acusa isso sozinho — os dois devolvem 429, e até o T-14 continuaria verde.
    Baixar o teto do login "para endurecer" é exatamente o engano plausível que esta linha
    impede.

    A direção inversa não merece caso: com o axes trancado, as requisições seguem passando
    pelo middleware e somando, e o 429 do axes não esconde nada do outro.

    Unitário, e não integração: é uma relação entre duas settings, sem I/O, sem requisição e
    sem banco. Levar isso a integração custaria a cadeia inteira para verificar uma
    comparação — e, pior, teria de PRODUZIR o mascaramento para o detectar, isto é, fixar em
    teste um comportamento que não se quer. Sem literal `60` nem `5` no corpo do caso:
    assertá-los reescreveria a política dentro do teste, pelo mesmo argumento do T-11/T-17. O
    que se assere é a ORDEM, que é o que a ADR 0016 e o comentário de `config/settings.py`
    afirmam por escrito.

    A leitura é `tests.runner.RATE_LIMIT_DE_PRODUCAO`, e não `settings.RATE_LIMIT_POR_CAMINHO`
    direto: T-13 esvazia o dicionário inteiro em `settings` para a suíte inteira (docstring
    de `tests/runner.py`), e o valor de produção — hoje as QUATRO chaves — só continua acessível
    pelo atributo de módulo que o runner guardou antes de zerar. Ler `settings` direto aqui
    devolveria `KeyError`, não a política de produção. `AXES_FAILURE_LIMIT` não sofre essa
    troca — não há runner nenhum guardando-o —, e por isso é lido de `settings` normalmente."""

    def test_teto_do_login_fica_acima_do_teto_de_falhas_do_axes(self):
        self.assertIsNotNone(
            runner.RATE_LIMIT_DE_PRODUCAO,
            "T-10/T-13 não guardou o teto de produção — o runner rodou sem passar pelo setup?",
        )
        self.assertGreater(
            runner.RATE_LIMIT_DE_PRODUCAO["/accounts/login/"], settings.AXES_FAILURE_LIMIT
        )
