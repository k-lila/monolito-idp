"""TASK-026/T-01, T-02 e T-03 — `SPA_URL` é validada na carga de `config/settings.py`.

Demanda do quality-assurance. Nível unitário, sem banco: a validação acontece quando o módulo
de settings é executado, e por isso cada caso o carrega de novo por `runpy.run_path`, com o
ambiente do processo sobrescrito. Não há cliente HTTP nem `override_settings`, que só
enxergariam o valor já carregado.

O `read_env` é neutralizado para o `.env` do clone não repor, por baixo do `patch.dict`, o
valor que o caso quer. Sem `clear=True`: as demais variáveis (`SECRET_KEY`, banco, chave RSA)
já estão em `os.environ` — o `.env` as gravou na primeira carga, ou o compose as deu ao
container —, e esvaziar o ambiente derrubaria a carga antes de chegar a `SPA_URL`.
`BEHIND_TLS_PROXY` entra sempre explícito, porque o container o força a "True".

A mensagem de recusa nunca repete o valor, que poderia trazer credenciais. Por isso cada caso
de recusa usa uma sentinela única no host (ou na senha) e confere que ela não aparece na
mensagem — é o que falha se alguém passar a interpolar o valor.
"""

import os
import runpy
from unittest import mock

import environ
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

CAMINHO_SETTINGS = settings.BASE_DIR / "config" / "settings.py"
SENTINELA = "sentinela-x9k2q7"
HOST = f"{SENTINELA}.exemplo.test"


def carregar(spa_url, behind_tls_proxy, debug=None, **outras):
    """Executa `config/settings.py` do zero e devolve o seu namespace.

    `spa_url=None` remove a variável do ambiente do processo, para o caso de ausência.
    `BASE_URL` é fixado em loopback: o `.env` do clone pode trazer um host público, e a guarda de
    produção (abaixo) recusaria `SPA_URL` em loopback antes de o caso chegar ao que testa.
    `outras` sobrescreve variáveis do ambiente, como `BASE_URL` e `EMAIL_BACKEND`."""
    ambiente = {"BEHIND_TLS_PROXY": behind_tls_proxy, "BASE_URL": "http://localhost:8000"}
    ambiente.update(outras)
    if spa_url is not None:
        ambiente["SPA_URL"] = spa_url
    if debug is not None:
        ambiente["DEBUG"] = debug
    with mock.patch.object(environ.Env, "read_env"), mock.patch.dict(os.environ, ambiente):
        if spa_url is None:
            os.environ.pop("SPA_URL", None)
        return runpy.run_path(str(CAMINHO_SETTINGS))


class SpaUrlAusenteTests(SimpleTestCase):
    """T-01 — sem default: a ausência derruba a carga, nomeando a variável. Falha se alguém
    puser default em `env.str("SPA_URL")`, que faria o botão da home levar a lugar nenhum."""

    def test_ausencia_levanta_improperly_configured_nomeando_a_variavel(self):
        for proxy in ("True", "False"):
            with self.subTest(behind_tls_proxy=proxy):
                with self.assertRaises(ImproperlyConfigured) as ctx:
                    carregar(None, proxy)
                self.assertIn("SPA_URL", str(ctx.exception))


class SpaUrlRecusadaTests(SimpleTestCase):
    """T-02 — cada classe de valor inválido levanta `ImproperlyConfigured` com o motivo
    da classe e sem repetir o valor."""

    ORIGEM = "origem"

    CASOS_NOS_DOIS_PROXIES = [
        (f"ftp://{HOST}", "http:// ou https://"),
        (f"https://usuario:{SENTINELA}@spa.exemplo.test", "credenciais"),
        (f"https://{HOST}/a", ORIGEM),
        (f"https://{HOST}/", ORIGEM),
        (f"https://{HOST}?a=1", ORIGEM),
        (f"https://{HOST}?", ORIGEM),
        (f"https://{HOST}#f", ORIGEM),
        (f"https://{HOST}:abc", ORIGEM),
        (f"https://{HOST}:99999", ORIGEM),
        (f"https://{HOST}:", ORIGEM),
        (f"https://{HOST}\\y", ORIGEM),
        (f"https://{HOST} ", ORIGEM),
    ]

    def _confere_recusa(self, valor, trecho, proxy, debug=None):
        with self.assertRaises(ImproperlyConfigured) as ctx:
            carregar(valor, proxy, debug)
        mensagem = str(ctx.exception)
        self.assertIn("SPA_URL", mensagem)
        self.assertIn(trecho, mensagem)
        self.assertNotIn(SENTINELA, mensagem)
        # A ValueError de `urlsplit(...).port` repete o trecho da porta; ela não pode
        # sobreviver como contexto da exceção que o operador vê.
        self.assertIsNone(ctx.exception.__cause__)
        self.assertIsNone(ctx.exception.__context__)

    def test_recusas_valem_com_e_sem_proxy_tls(self):
        for proxy in ("True", "False"):
            for valor, trecho in self.CASOS_NOS_DOIS_PROXIES:
                with self.subTest(behind_tls_proxy=proxy, valor=valor):
                    self._confere_recusa(valor, trecho, proxy)

    def test_http_fora_de_loopback_e_recusado_atras_do_proxy(self):
        self._confere_recusa(f"http://{HOST}", "loopback", "True")

    def test_debug_nao_entra_na_regra_do_http(self):
        self._confere_recusa(f"http://{HOST}", "loopback", "True", debug="True")


class SpaUrlAceitaTests(SimpleTestCase):
    """T-03 — origens válidas passam sem alteração. Falha se a isenção de loopback sumir ou
    a porta explícita passar a ser recusada."""

    ACEITOS = [
        ("https://spa.exemplo.test", "True"),
        ("https://spa.exemplo.test", "False"),
        ("https://spa.exemplo.test:8443", "True"),
        ("http://localhost:5173", "True"),
        ("http://localhost:5173", "False"),
        ("http://127.0.0.1:5173", "True"),
        ("http://[::1]:5173", "True"),
        # A recusa de http depende do proxy: sem ele, fora de loopback, passa.
        ("http://spa.exemplo.test", "False"),
    ]

    def test_origens_validas_sao_devolvidas_intactas(self):
        for valor, proxy in self.ACEITOS:
            with self.subTest(valor=valor, behind_tls_proxy=proxy):
                self.assertEqual(carregar(valor, proxy)["SPA_URL"], valor)


SMTP = "django.core.mail.backends.smtp.EmailBackend"
BASE_PUBLICA = f"https://{HOST}"


class GuardaDeProducaoTests(SimpleTestCase):
    """TASK-028/T-70 — com `BASE_URL` público, o boot recusa `SPA_URL` em loopback e backend de
    e-mail que não entrega, nomeando a variável e sem repetir o valor. Vermelho se a guarda sumir,
    se uma das quatro classes de backend sair do conjunto, ou se a mensagem trouxer o valor."""

    BACKENDS = ["console", "dummy", "locmem", "filebased"]

    def test_spa_url_em_loopback_e_recusada_com_base_url_publico(self):
        for spa in ("http://localhost:5173", "http://127.0.0.1:5173", "http://[::1]:5173"):
            with self.subTest(spa=spa):
                with self.assertRaises(ImproperlyConfigured) as ctx:
                    carregar(spa, "False", BASE_URL=BASE_PUBLICA, EMAIL_BACKEND=SMTP)
                mensagem = str(ctx.exception)
                self.assertIn("SPA_URL aponta para loopback", mensagem)
                self.assertIn("BASE_URL é público", mensagem)
                self.assertNotIn(SENTINELA, mensagem)

    def test_cada_backend_que_nao_entrega_e_recusado(self):
        for nome in self.BACKENDS:
            backend = f"django.core.mail.backends.{nome}.EmailBackend"
            with self.subTest(backend=nome):
                with self.assertRaises(ImproperlyConfigured) as ctx:
                    carregar(
                        "https://spa.exemplo.test", "False", BASE_URL=BASE_PUBLICA,
                        EMAIL_BACKEND=backend,
                    )
                mensagem = str(ctx.exception)
                self.assertIn("EMAIL_BACKEND não entrega e-mail", mensagem)
                self.assertIn("smtp.EmailBackend", mensagem)
                self.assertNotIn(SENTINELA, mensagem)
                self.assertNotIn(backend, mensagem)

    def test_com_base_publico_spa_publica_e_smtp_passam(self):
        ns = carregar("https://spa.exemplo.test", "False", BASE_URL=BASE_PUBLICA, EMAIL_BACKEND=SMTP)
        self.assertEqual(ns["EMAIL_BACKEND"], SMTP)

    def test_base_url_local_nao_ativa_a_guarda(self):
        for base in ("https://idp.localhost", "http://localhost:8000", "http://127.0.0.1:8000"):
            for backend in self.BACKENDS:
                with self.subTest(base=base, backend=backend):
                    ns = carregar(
                        "http://localhost:5173", "False", BASE_URL=base,
                        EMAIL_BACKEND=f"django.core.mail.backends.{backend}.EmailBackend",
                    )
                    self.assertEqual(ns["SPA_URL"], "http://localhost:5173")
