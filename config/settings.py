"""Configuração única do projeto, dirigida por ambiente.

Não há default no código: o `.env` é a fonte, e variável ausente falha na leitura
nomeando-se. Não há split dev/prod — um arquivo de dev que nunca roda em produção
é um caminho não exercitado.
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
# Caminho explícito: read_env() sem argumento localiza o .env por backtracking de stack.
environ.Env.read_env(BASE_DIR / ".env")

DEBUG = env.bool("DEBUG")
SECRET_KEY = env.str("SECRET_KEY")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

# Consumidas pelo bloco OAUTH2_PROVIDER abaixo, que reusa estas duas variáveis em vez de
# reler o ambiente: uma segunda leitura sem multiline=True produz um PEM com \n literais,
# que falha ruidosamente — ValueError ao carregar a chave, 500 em /o/.well-known/jwks.json
# e em /o/token/, logado por django.request. A falha silenciosa é a da chave ausente: JWKS
# vazio com 200, e na discovery só o alg denuncia, caindo de RS256+HS256 para HS256.
BASE_URL = env.str("BASE_URL")
OIDC_RSA_PRIVATE_KEY = env.str("OIDC_RSA_PRIVATE_KEY", multiline=True)

BEHIND_TLS_PROXY = env.bool("BEHIND_TLS_PROXY")
LOG_LEVEL = env.str("LOG_LEVEL")
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS")

# Sem default, deliberadamente: um default faria a trilha de auditoria gravar dentro da
# camada de escrita do container e desaparecer no primeiro `docker compose down` —
# pareceria funcionar, seria confiada, e sumiria. Ausente, esta linha derruba o processo na
# leitura das settings nomeando a si mesma, como manda o precedente da ADR 0004. O caminho
# é relativo ao diretório de trabalho do processo; no container o compose o sobrescreve
# por um absoluto, dentro do volume nomeado `auditlog`.
AUDIT_LOG_PATH = env.str("AUDIT_LOG_PATH")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # No INSTALLED_APPS, não só no middleware: é o app que registra o check da tag
    # `security`, o que torna uma allowlist malformada um erro de `manage.py check`.
    "corsheaders",
    "oauth2_provider",
    "accounts",
]

AUTH_USER_MODEL = "accounts.User"

# A PK do User é o `sub` de todo id_token: 64 bits, fixado antes da migração inicial.
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

MIDDLEWARE = [
    # CorsMiddleware SEMPRE no topo: acima do CommonMiddleware e de qualquer
    # middleware capaz de gerar resposta — resposta emitida antes dele sai sem
    # os cabeçalhos de CORS. Com a allowlist vazia o middleware é inerte, e por
    # isso uma posição errada é INDETECTÁVEL nesta fase: o sinal só aparece na
    # fase do SPA, como erro de CORS sem pista que aponte para esta linha.
    "corsheaders.middleware.CorsMiddleware",
    # Índice 1, e as duas metades da razão importam.
    #
    # Por que tão alto: tudo que estiver acima dele emite resposta sem request_id e sem
    # linha de acesso. Abaixo dele ficam o 301 do SecurityMiddleware (o mesmo da ADR 0010),
    # os estáticos do WhiteNoise, o redirecionamento de APPEND_SLASH e o 403 do CSRF —
    # exatamente as respostas que hoje não deixam rastro nenhum.
    #
    # Por que não acima do CorsMiddleware: a regra escrita ali é absoluta, e o que se
    # ganharia é registrar as preflight OPTIONS, que são zero enquanto a allowlist estiver
    # vazia. A perda é real: no dia em que houver uma SPA, a preflight não aparecerá no log
    # de acesso, e nada avisará.
    "config.observabilidade.ObservabilidadeMiddleware",
    "django.middleware.security.SecurityMiddleware",
    # Logo abaixo do SecurityMiddleware: o estático é servido sem atravessar sessão,
    # CSRF e autenticação. Com DEBUG=False é quem serve /static/ — o runserver não serve.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {"default": env.db("DATABASE_URL")}

# Teto da metade "banco" do /health, simétrico ao socket_connect_timeout do CACHES. Com
# CONN_MAX_AGE default (0) toda request abre conexão nova, então é na conexão que o tempo
# mora — `SELECT 1` não toma lock nem lê relação, e um statement_timeout guardaria um
# cenário que não existe. 2s é o mínimo que a libpq aceita. É deste teto que o `timeout`
# do HEALTHCHECK é derivado (ADR 0011).
DATABASES["default"].setdefault("OPTIONS", {})["connect_timeout"] = 2

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",  # nativo do Django; sem django-redis (ADR 0005)
        "LOCATION": env.str("REDIS_URL"),
        # A falha que estes dois fecham não é a recusa de conexão — essa devolve RST na
        # hora, o except da view roda e o 503 sai —, é a do Redis que aceita a conexão e
        # não responde (`compose pause`, BGSAVE sob pressão de memória, firewall que faz
        # DROP): sem timeout `cache.set` pendura, nenhuma linha de log sai da view e quem
        # encerra é o worker timeout do gunicorn, levando junto as outras requisições em
        # voo naquele worker. Explícitos porque o default é implícito e versionado: None
        # (bloqueio sem limite) em redis-py antigo, 5s no 8.1.0 de requirements.txt — já
        # acima do `timeout: 3s` do healthcheck do redis no compose. 2s cabe nessa janela
        # e fica três ordens de grandeza acima do round-trip local, para que um soluço do
        # Redis não vire erro de sessão: o SESSION_ENGINE abaixo toca o cache a cada
        # request. Sem retry_on_timeout — o que dura menos de 2s não estoura, e insistir
        # contra um Redis travado só adia o 503.
        "OPTIONS": {
            "socket_connect_timeout": 2,
            "socket_timeout": 2,
        },
    }
}

# Postgres como armazenamento durável, Redis como leitura quente. Sobrevive a flush e a
# reinício do Redis; não tolera Redis indisponível (ADR 0005).
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"

# Argon2 em primeiro; os demais preservados abaixo para re-hash de credencial legada
# no próximo login.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

OAUTH2_PROVIDER = {
    # Sem ela, OIDCOnlyMixin devolve 404 em discovery, JWKS e userinfo — o servidor sobe
    # inteiro e só os endpoints de OIDC somem.
    "OIDC_ENABLED": True,
    # Redundante com o default da 3.4.1, declarada porque é proibição escrita: client
    # público sem PKCE é code interceptável, e um default não é um compromisso.
    "PKCE_REQUIRED": True,
    # É esta chave que faz valer a linha acima: PKCE_REQUIRED sozinho ainda aceita
    # code_challenge_method=plain, em que o challenge é o próprio verifier em claro na
    # requisição de autorização — quem observa o pedido troca o code interceptado por um
    # token. Restringe a S256 (RFC 9700 §2.1.1); default do DOT programado para flipar na 4.0.
    "COMPLIANT_BCP_RFC9700_PKCE_METHOD": True,
    # Default já é False. A linha existe porque a própria biblioteca documenta que defaults
    # dela estão programados para flipar na 4.0: sem a declaração explícita, um `pip install -U`
    # publicaria end_session_endpoint na discovery sem uma linha de log.
    "OIDC_RP_INITIATED_LOGOUT_ENABLED": False,
    # Descrições em português: são renderizadas cruas na tela de consentimento e lidas pela
    # pessoa usuária. LANGUAGE_CODE governa a i18n do Django, não o conteúdo destas strings.
    "SCOPES": {
        "openid": "Confirmar sua identidade",
        "profile": "Ver seu nome e seus dados de perfil",
        "email": "Ver seu endereço de e-mail",
    },
    "OIDC_RSA_PRIVATE_KEY": OIDC_RSA_PRIVATE_KEY,
    # Coerente com o prefixo `o/` do include: é a claim `iss` de todo id_token emitido e
    # fica cacheada em cada relying party (ADR 0007). O rstrip evita que uma barra final no
    # .env produza `//o`, que não gera erro nenhum e só aparece como issuer mismatch na RP.
    "OIDC_ISS_ENDPOINT": f"{BASE_URL.rstrip('/')}/o",
    # Contrato por string resolvido no boot: sem esta chave não há erro nenhum, o fluxo
    # fecha e o id_token chega só com `sub`.
    "OAUTH2_VALIDATOR_CLASS": "accounts.oauth_validators.IdPOAuth2Validator",
}

# Endurecimento de transporte governado por BEHIND_TLS_PROXY, nunca por DEBUG (ADR 0006):
# DEBUG é sobre diagnóstico, cookie seguro é sobre transporte. Acoplar os dois produz
# login que falha com 302 silencioso e nenhum erro em lugar nenhum.
SESSION_COOKIE_SECURE = BEHIND_TLS_PROXY
CSRF_COOKIE_SECURE = BEHIND_TLS_PROXY
SECURE_SSL_REDIRECT = BEHIND_TLS_PROXY
# SecurityMiddleware.process_request roda antes de qualquer view: com SECURE_SSL_REDIRECT
# ligado, a probe do container — que chega de dentro, em texto claro, sem X-Forwarded-Proto —
# recebe 301 para https:// e morre no handshake contra um gunicorn em texto claro. O padrão
# casa contra request.path.lstrip("/"), por isso `health` sem barra é ancorado nas duas pontas.
# Inerte enquanto SECURE_SSL_REDIRECT for False (ADR 0010).
SECURE_REDIRECT_EXEMPT = [r"^health$"]
# Exclusão por NOME de rota, nunca por caminho. Adjacente à lista acima de propósito: as
# duas se acoplam à mesma string, `health`, e nenhum mecanismo verifica nenhuma das duas —
# a vizinhança é o que dá a quem renomear a rota alguma chance de ver as duas. Sem esta
# entrada, a sonda de dez em dez segundos afogaria o log, que é o problema que a omissão do
# --access-logfile no docker/entrypoint.sh fechou.
ACCESS_LOG_EXCLUDED_ROUTES = ["health"]
SECURE_HSTS_SECONDS = 31536000 if BEHIND_TLS_PROXY else 0
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if BEHIND_TLS_PROXY else None

# Sem require_debug_true e sem mail_admins (ADR 0006): o default do Django emudece
# django.request quando DEBUG é falso, que é o modo em que o container roda.
#
# Todo registro sai como um objeto JSON por linha, com o identificador da requisição
# (ADR 0012). O filtro vai nos HANDLERS, não em cada logger: uma declaração por handler
# alcança as entradas todas, e um logger novo não esquece o filtro em silêncio.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"request_id": {"()": "config.observabilidade.FiltroRequestId"}},
    "formatters": {"json": {"()": "config.observabilidade.FormatadorJSON"}},
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",  # o default do StreamHandler é stderr
            "formatter": "json",
            "filters": ["request_id"],
        },
        "audit": {
            # WatchedFileHandler, nunca RotatingFileHandler: três workers rotacionando o
            # mesmo arquivo perdem linhas sem emitir nada. A rotação, se um dia existir,
            # é externa ao processo — este handler apenas reabre o arquivo quando ele é
            # substituído.
            "class": "logging.handlers.WatchedFileHandler",
            "filename": AUDIT_LOG_PATH,
            "encoding": "utf-8",
            # É o default do FileHandler, e está escrito assim mesmo porque um "w"
            # truncaria a trilha a cada boot: perda total, silenciosa e irrecuperável.
            "mode": "a",
            # Sem delay=True: o arquivo é aberto na configuração do logging, dentro de
            # django.setup(), de modo que caminho inválido ou diretório sem permissão
            # derruba o processo no boot, ruidosamente. Com delay, a mesma falha só
            # apareceria no primeiro login — o pior momento possível.
            "formatter": "json",
            "filters": ["request_id"],
        },
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "oauth2_provider": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "access": {
            "handlers": ["console"],
            # Segue LOG_LEVEL porque a linha de acesso é log operacional, e LOG_LEVEL é o
            # botão do log operacional. A consequência não tem sintoma: LOG_LEVEL=WARNING
            # apaga a linha de acesso inteira, sem aviso nenhum.
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "audit": {
            "handlers": ["audit"],
            # INFO fixo, nunca LOG_LEVEL: uma trilha que um botão de verbosidade desliga
            # não é trilha.
            "level": "INFO",
            # Não propaga para o console: duas cópias da mesma evidência, com tempos de
            # vida diferentes, divergem.
            "propagate": False,
        },
    },
}

# A suíte não pode escrever na trilha do ambiente: linha de teste misturada com evidência
# de operação contamina as duas. O executor redireciona o handler `audit` para um diretório
# temporário, pelo mesmo precedente com que já redireciona o nome do banco para `test_*`.
TEST_RUNNER = "tests.runner.RunnerComTrilhaIsolada"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Sem manifesto, divergindo do passo 09: o backend com manifesto faz `{% static %}`
# consultar staticfiles.json em tempo de renderização, e um artefato de build ausente
# vira ValueError na própria renderização — a suíte roda sem collectstatic prévio. A
# chave `default` é obrigatória: declarar STORAGES substitui o dicionário inteiro.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

# Nomes de rota, não caminhos: as três passam por resolve_url, que chama reverse em
# runtime. Os defaults do Django apontam para /accounts/profile/, que não existe aqui —
# seria um 404 logo após um login bem-sucedido.
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"
