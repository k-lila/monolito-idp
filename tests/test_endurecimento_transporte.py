"""T-18 — o endurecimento de transporte segue `BEHIND_TLS_PROXY`, nunca `DEBUG` (ADR 0006) e
nunca um valor solto: `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_SSL_REDIRECT`,
`SECURE_HSTS_SECONDS` e `SECURE_PROXY_SSL_HEADER` (`config/settings.py:331-347`).

Demanda do gate adversarial (`senso-critico`, TASK-015): a neutralização de
`SECURE_SSL_REDIRECT` em `tests/runner.py` (T-04) removeu o único detector que acoplava o
endurecimento a `BEHIND_TLS_PROXY` — o 301 em massa que a jornada de container produzia antes
da neutralização — sem repor a guarda que o T-17 já fixara no mesmo arquivo para
`RATE_LIMIT_POR_CAMINHO`. Um valor de produção neutralizado e não guardado antes é invisível: a
razão que `tests/runner.py:94-98` registra para o T-17 vale aqui palavra por palavra.

Nível unitário, sem banco: leitura pura de settings, nenhum cliente HTTP envolvido — o
comportamento do redirecionamento em si (a resposta 301 de verdade, sob `override_settings`)
já é de `tests.test_health.HealthRedirectExemptionTests`, que a docstring daquele arquivo
descreve. O que falta e este arquivo cobre é mais estreito: as CINCO chaves são de fato o valor
que `BEHIND_TLS_PROXY` manda, e não um literal solto ou um valor que sobrevive de uma edição
anterior.

Só `SECURE_SSL_REDIRECT` precisa de guarda contra o zeramento do runner: é a ÚNICA das cinco
que `tests.runner.RunnerComTrilhaIsolada` toca durante a suíte (zerada para a jornada de
container não devolver 301 ao test client, que fala HTTP puro — razão completa no docstring de
`tests/runner.py`). Por isso este arquivo lê `runner.SECURE_SSL_REDIRECT_DE_PRODUCAO` — o valor
que o setup guardou ANTES de zerar —, nunca `settings.SECURE_SSL_REDIRECT`, que vale `False` do
início ao fim da suíte inteira, por construção do próprio runner: comparar contra o valor
neutralizado provaria só que o runner zerou, nunca o que `config/settings.py:333` declara. As
outras quatro settings nunca são tocadas pelo runner — o valor lido em `settings` a qualquer
instante da suíte já é o de produção —, e por isso dispensam a mesma guarda.

Uma asserção por chave, e não uma agregada sobre "o conjunto": as cinco derivam de
`BEHIND_TLS_PROXY` por expressões distintas (booleano direto, condicional numérica,
tupla-ou-`None`), e uma asserção só sobre o conjunto obscureceria qual delas quebrou — a
mensagem de falha do `assertEqual` isolado já nomeia o par (esperado, obtido) da chave certa.
"""

from django.conf import settings
from django.test import SimpleTestCase
from oauth2_provider.settings import oauth2_settings

import tests.runner as runner


class EndurecimentoDeTransporteSegueBehindTlsProxyTests(SimpleTestCase):
    """T-18 — AC implícito do achado do `senso-critico`: apagar ou inverter
    `config/settings.py:331-347` tem de deixar a suíte vermelha, nas duas jornadas."""

    def test_secure_ssl_redirect_de_producao_segue_behind_tls_proxy(self):
        # `tests.runner.RunnerComTrilhaIsolada.setup_test_environment` (T-04/T-18) guardou o
        # valor de produção aqui, ANTES de zerar `settings.SECURE_SSL_REDIRECT` para a suíte —
        # ver docstring de `tests/runner.py`.
        self.assertIsNotNone(
            runner.SECURE_SSL_REDIRECT_DE_PRODUCAO,
            "tests/runner.py não guardou SECURE_SSL_REDIRECT de produção — a suíte rodou sem "
            "passar por setup_test_environment?",
        )
        self.assertEqual(runner.SECURE_SSL_REDIRECT_DE_PRODUCAO, settings.BEHIND_TLS_PROXY)

    def test_session_cookie_secure_segue_behind_tls_proxy(self):
        # Nunca neutralizada pelo runner: o valor em `settings` é o de produção em
        # qualquer ponto da suíte.
        self.assertEqual(settings.SESSION_COOKIE_SECURE, settings.BEHIND_TLS_PROXY)

    def test_csrf_cookie_secure_segue_behind_tls_proxy(self):
        self.assertEqual(settings.CSRF_COOKIE_SECURE, settings.BEHIND_TLS_PROXY)

    def test_secure_hsts_seconds_e_um_ano_atras_do_proxy_e_zero_fora_dele(self):
        esperado = 31536000 if settings.BEHIND_TLS_PROXY else 0
        self.assertEqual(settings.SECURE_HSTS_SECONDS, esperado)

    def test_secure_proxy_ssl_header_so_existe_atras_do_proxy(self):
        esperado = (
            ("HTTP_X_FORWARDED_PROTO", "https") if settings.BEHIND_TLS_PROXY else None
        )
        self.assertEqual(settings.SECURE_PROXY_SSL_HEADER, esperado)


class AllowedRedirectUriSchemesDeProducaoSegueBehindTlsProxyTests(SimpleTestCase):
    """TASK-019/T-01 — `ALLOWED_REDIRECT_URI_SCHEMES` (`config/settings.py:360`) é o QUINTO
    valor governado por `BEHIND_TLS_PROXY`, e o único, entre os cinco, que
    `tests.runner.RunnerComTrilhaIsolada` neutraliza — pela mesma razão de
    `SECURE_SSL_REDIRECT`: as fixtures de `tests/oauth_helpers.py` registram `redirect_uri`
    em `http://`, e `["https"]` de produção, sob `BEHIND_TLS_PROXY` ligado, rejeitaria o
    redirecionamento de todo teste de fluxo com `DisallowedRedirect` (400).

    TASK-019/T-02 — único teste capaz de ver a derivação de produção, que a neutralização do
    runner apaga do resto da suíte: os dois ramos de `settings.OAUTH2_PROVIDER` durante a
    suíte valem sempre `["http", "https"]`, por construção do próprio runner, e comparar
    contra ele provaria só que o runner neutralizou — nunca o que
    `config/settings.py:360` declara. Por isso a comparação é contra
    `tests.runner.OAUTH2_PROVIDER_DE_PRODUCAO`, o dicionário que o setup guardou ANTES de
    substituir `settings.OAUTH2_PROVIDER` pela cópia neutra — nunca contra
    `settings.OAUTH2_PROVIDER`."""

    def test_allowed_redirect_uri_schemes_de_producao_segue_behind_tls_proxy(self):
        self.assertIsNotNone(
            runner.OAUTH2_PROVIDER_DE_PRODUCAO,
            "tests/runner.py não guardou OAUTH2_PROVIDER de produção — a suíte rodou sem "
            "passar por setup_test_environment?",
        )
        esperado = ["https"] if settings.BEHIND_TLS_PROXY else ["http", "https"]
        self.assertEqual(
            runner.OAUTH2_PROVIDER_DE_PRODUCAO["ALLOWED_REDIRECT_URI_SCHEMES"], esperado
        )


class OAuth2SettingsRecebeOSinalDeNeutralizacaoTests(SimpleTestCase):
    """TASK-019/T-03 — prova que o sinal `setting_changed` do runner chegou de fato ao CACHE
    do toolkit (`oauth2_provider.settings.oauth2_settings`), e não só que
    `settings.OAUTH2_PROVIDER` mudou de valor. `oauth2_settings` lê o dicionário sob demanda,
    por `__getattr__`, e só essa leitura acrescenta o atributo a `_cached_attrs`
    (`oauth2_provider/settings.py`) — quando este runner roda, `ALLOWED_REDIRECT_URI_SCHEMES`
    ainda não foi lido por ninguém. Sem o sinal — ou com um `setattr` direto em
    `oauth2_settings` no lugar dele, ANTES de qualquer leitura real —, o atributo nunca
    passaria por `__getattr__`, nunca entraria em `_cached_attrs`, e nenhum `reload()` futuro
    (nem o do primeiro `override_settings(OAUTH2_PROVIDER=...)` legítimo de outro teste)
    encontraria o que apagar: o `setattr` sobreviveria à suíte inteira (razão completa no
    docstring de `tests/runner.py`) — este teste é o único capaz de distinguir
    "settings.OAUTH2_PROVIDER trocou" de "o toolkit recarregou"."""

    def test_oauth2_settings_alcanca_as_duas_letras_durante_a_suite(self):
        self.assertEqual(oauth2_settings.ALLOWED_REDIRECT_URI_SCHEMES, ["http", "https"])
