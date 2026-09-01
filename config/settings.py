"""Configuracao unica do projeto, dirigida por ambiente.

Nao ha default no codigo: o `.env` e a fonte, e variavel ausente falha na leitura
nomeando-se. Nao ha split dev/prod — um arquivo de dev que nunca roda em producao
e um caminho nao exercitado.
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
# Caminho explicito: read_env() sem argumento localiza o .env por backtracking de stack.
environ.Env.read_env(BASE_DIR / ".env")

DEBUG = env.bool("DEBUG")
SECRET_KEY = env.str("SECRET_KEY")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

# Consumidas pelo bloco OAUTH2_PROVIDER abaixo, que reusa estas duas variaveis em vez de
# reler o ambiente: uma segunda leitura sem multiline=True produz um PEM com \n literais,
# que o DOT aceita em silencio e devolve como JWKS vazio.
BASE_URL = env.str("BASE_URL")
OIDC_RSA_PRIVATE_KEY = env.str("OIDC_RSA_PRIVATE_KEY", multiline=True)

BEHIND_TLS_PROXY = env.bool("BEHIND_TLS_PROXY")
LOG_LEVEL = env.str("LOG_LEVEL")
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # No INSTALLED_APPS, nao so no middleware: e o app que registra o check da tag
    # `security`, o que torna uma allowlist malformada um erro de `manage.py check`.
    "corsheaders",
    "oauth2_provider",
    "accounts",
]

AUTH_USER_MODEL = "accounts.User"

# A PK do User e o `sub` de todo id_token: 64 bits, fixado antes da migracao inicial.
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

MIDDLEWARE = [
    # CorsMiddleware SEMPRE no topo: acima do CommonMiddleware e de qualquer
    # middleware capaz de gerar resposta — resposta emitida antes dele sai sem
    # os cabecalhos de CORS. Com a allowlist vazia o middleware e inerte, e por
    # isso uma posicao errada e INDETECTAVEL nesta fase: o sinal so aparece na
    # fase do SPA, como erro de CORS sem pista que aponte para esta linha.
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoiseMiddleware entra AQUI no passo 09, logo abaixo do SecurityMiddleware,
    # para que o estatico seja servido sem atravessar sessao, CSRF e autenticacao.
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

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",  # nativo do Django; sem django-redis (ADR 0005)
        "LOCATION": env.str("REDIS_URL"),
    }
}

# Postgres como armazenamento duravel, Redis como leitura quente. Sobrevive a flush e a
# reinicio do Redis; nao tolera Redis indisponivel (ADR 0005).
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"

# Argon2 em primeiro; os demais preservados abaixo para re-hash de credencial legada
# no proximo login.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

OAUTH2_PROVIDER = {
    # Sem ela, OIDCOnlyMixin devolve 404 em discovery, JWKS e userinfo — o servidor sobe
    # inteiro e so os endpoints de OIDC somem.
    "OIDC_ENABLED": True,
    # Redundante com o default da 3.4.1, declarada porque e proibicao escrita: client
    # publico sem PKCE e code interceptavel, e um default nao e um compromisso.
    "PKCE_REQUIRED": True,
    # E esta chave que faz valer a linha acima: PKCE_REQUIRED sozinho ainda aceita
    # code_challenge_method=plain, em que o challenge e o proprio verifier em claro na
    # requisicao de autorizacao — quem observa o pedido troca o code interceptado por um
    # token. Restringe a S256 (RFC 9700 §2.1.1); default do DOT programado para flipar na 4.0.
    "COMPLIANT_BCP_RFC9700_PKCE_METHOD": True,
    # Default ja e False. A linha existe porque a propria biblioteca documenta que defaults
    # dela estao programados para flipar na 4.0: sem a declaracao explicita, um `pip install -U`
    # publicaria end_session_endpoint na discovery sem uma linha de log.
    "OIDC_RP_INITIATED_LOGOUT_ENABLED": False,
    # Descricoes em portugues: sao renderizadas cruas na tela de consentimento e lidas pela
    # pessoa usuaria. LANGUAGE_CODE governa a i18n do Django, nao o conteudo destas strings.
    "SCOPES": {
        "openid": "Confirmar sua identidade",
        "profile": "Ver seu nome e seus dados de perfil",
        "email": "Ver seu endereco de e-mail",
    },
    "OIDC_RSA_PRIVATE_KEY": OIDC_RSA_PRIVATE_KEY,
    # Coerente com o prefixo `o/` do include: e a claim `iss` de todo id_token emitido e
    # fica cacheada em cada relying party (ADR 0007). O rstrip evita que uma barra final no
    # .env produza `//o`, que nao gera erro nenhum e so aparece como issuer mismatch na RP.
    "OIDC_ISS_ENDPOINT": f"{BASE_URL.rstrip('/')}/o",
    # Contrato por string resolvido no boot: sem esta chave nao ha erro nenhum, o fluxo
    # fecha e o id_token chega so com `sub`.
    "OAUTH2_VALIDATOR_CLASS": "accounts.oauth_validators.IdPOAuth2Validator",
}

# Endurecimento de transporte governado por BEHIND_TLS_PROXY, nunca por DEBUG (ADR 0006):
# DEBUG e sobre diagnostico, cookie seguro e sobre transporte. Acoplar os dois produz
# login que falha com 302 silencioso e nenhum erro em lugar nenhum.
SESSION_COOKIE_SECURE = BEHIND_TLS_PROXY
CSRF_COOKIE_SECURE = BEHIND_TLS_PROXY
SECURE_SSL_REDIRECT = BEHIND_TLS_PROXY
SECURE_HSTS_SECONDS = 31536000 if BEHIND_TLS_PROXY else 0
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if BEHIND_TLS_PROXY else None

# Sem require_debug_true e sem mail_admins (ADR 0006): o default do Django emudece
# django.request quando DEBUG e falso, que e o modo em que o container roda.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",  # o default do StreamHandler e stderr
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
    },
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
