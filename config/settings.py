"""Configuração única do projeto, dirigida por ambiente.

Não há default no código: o `.env` é a fonte, e variável ausente falha na leitura
nomeando-se. Não há split dev/prod — um arquivo de dev que nunca roda em produção
é um caminho não exercitado.
"""

from datetime import timedelta
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
# O django-cors-headers só age sob `/o/`: `/admin/` e `/accounts/login/` nunca são chamados
# por `fetch` de outra origem, e ali uma origem da allowlist não recebe cabeçalho nenhum. O
# acoplamento é com o prefixo `o/` de config/urls.py, e é silencioso: mudar o prefixo sem
# mudar esta linha tira o CORS de /o/token/ e de /o/userinfo/ sem erro. Descoberta, JWKS e
# metadados das RFCs 8414 e 9728 não dependem desta linha nem do middleware: a view do DOT
# põe `Access-Control-Allow-Origin: *` à mão. Literal no código, e não no `.env`, pela razão
# escrita em RATE_LIMIT_POR_CAMINHO.
CORS_URLS_REGEX = r"^/o/"

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
    # No INSTALLED_APPS por dois motivos: traz as próprias migrações, e é o app que registra
    # os checks de `axes/checks.py`, que denunciam middleware ausente (`axes.W002`), backend
    # ausente (`axes.W003`) e `AXES_LOCKOUT_PARAMETERS` sem `ip_address` (`axes.W006`).
    # Denunciam, e não reprovam: são `Warning`, e `manage.py check` os imprime com código de
    # saída ZERO — só quebram o comando com `--fail-level WARNING`. Quem confia no código de
    # saída não vê uma tela de login sem teto.
    "axes",
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
    # Índice 4, e as três razões desta posição são independentes.
    #
    # Abaixo do SecurityMiddleware e do WhiteNoise: o 301 de HTTPS (ADR 0010) e cada arquivo
    # estático não consomem contador — não é tráfego contra a superfície de autenticação.
    #
    # Acima do SessionMiddleware: a recusa por excesso não precisa de sessão, de CSRF
    # (Cross-Site Request Forgery) nem de usuário, e cada um desses custa Redis ou Postgres.
    # É exatamente o custo que o limitador existe para não pagar sob varredura.
    #
    # Abaixo do ObservabilidadeMiddleware: o 429 é uma resposta, e tem de sair com
    # `request_id` e com linha de acesso como qualquer outra.
    #
    # O SILÊNCIO desta linha: este middleware EMITE RESPOSTA, e por isso tem de ficar abaixo
    # do CorsMiddleware — resposta emitida acima dele sai sem os cabeçalhos de CORS. Com a
    # allowlist vazia isso é INDETECTÁVEL, e o sinal só apareceria na fase do SPA
    # (Single-Page Application), como um 429 que o navegador esconde atrás de um erro de
    # CORS sem pista que aponte para cá.
    "config.limites.LimiteDeTaxaMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # No fim da lista, como a documentação do axes pede. Ele não conta nada — converte em
    # resposta a exceção PermissionDenied que o backend levanta, e para isso precisa
    # envolver a cadeia inteira. O check `axes.W002` verifica a PRESENÇA desta linha, nunca
    # a posição: posição errada aqui é silenciosa.
    "axes.middleware.AxesMiddleware",
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

# Os quatro validadores prontos do Django, nos defaults: mínimo de 8 caracteres, e a
# semelhança medida contra `email`, `first_name` e `last_name` — `username` é None no
# accounts.User, e o validador o pula. É esta lista que sustenta a aritmética do teto de cinco
# tentativas do axes, que supõe um espaço de busca inviável.
#
# Os silêncios: a validação roda só onde uma senha é ESCOLHIDA pela tela ou pelo comando — os
# formulários do admin de adicionar conta e de alterar senha, `changepassword` e
# `createsuperuser` interativo. Não roda no login, de modo que conta com senha antiga fraca
# continua entrando; não roda em `create_user` nem em `set_password`, de modo que a suíte e o
# `shell` passam por baixo; `createsuperuser` interativo oferece "Bypass password validation"
# depois da recusa; e `createsuperuser --noinput` não valida nada.
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# A PRIMEIRA declaração de AUTHENTICATION_BACKENDS na história deste projeto, e o silêncio
# mais caro do arquivo: declarar a lista SUBSTITUI o default do Django. Sem a segunda linha,
# `ModelBackend`, ninguém autentica — todas as contas trancadas de uma vez, e o sintoma é uma
# senha correta recusada, indistinguível de senha errada.
#
# `AxesStandaloneBackend`, e nunca `AxesBackend`: o segundo herda de `ModelBackend` e produz
# uma lista que parece certa e verifica a senha duas vezes. Primeiro na ordem porque é ele
# quem recusa a conta bloqueada antes de o `ModelBackend` chegar a conferir credencial.
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# Teto da tela de login, contado por tentativa falha no caminho de `authenticate()`. Cinco, e
# não o default 3: três erros trancam quem digitou com a tecla de maiúsculas presa, e cinco
# mantêm o espaço de busca inviável.
AXES_FAILURE_LIMIT = 5
# Quinze minutos, e nunca o default None, que é bloqueio sem prazo. Este projeto não tem rota
# de recuperação de senha (`tests/test_password_reset_urls.py` prova a ausência), e um
# bloqueio sem prazo transferiria a quem opera todo engano de quem usa.
#
# O prazo conta da ÚLTIMA tentativa, e não do bloqueio: o axes soma as falhas da janela e
# atualiza o registro a cada nova falha, inclusive as que chegam com a conta já bloqueada
# (`AXES_RESET_COOL_OFF_ON_FAILURE_DURING_LOCKOUT`, cujo default é True na 8.3.1). Quem
# insiste adia o próprio acesso, e um ataque sustentado mantém a conta fora enquanto durar —
# daí a saída manual de `docs/runbook.md`. É este prazo que a tela de bloqueio declara.
AXES_COOLOFF_TIME = timedelta(minutes=15)
# DOIS ELEMENTOS, e é o número deles que separa "por conta OU por origem" de "pela combinação
# das duas". `get_client_parameters` (`axes/helpers.py:285-293`) percorre a lista e faz de cada
# ELEMENTO um filtro independente: elemento string filtra por uma chave, elemento lista filtra
# pela combinação das chaves dele. Daí que `["username", "ip_address"]`, sem os colchetes
# internos, é idêntico ao valor escrito abaixo — dois elementos, dois filtros — e trocar um
# pelo outro não muda nada.
#
# O erro de digitação caro é outro: `[["username", "ip_address"]]`, com UM elemento só e as
# duas chaves dentro. Aí o axes passa a contar pelo par, e nem o excesso contra a mesma conta
# vindo de origens diferentes nem o excesso da mesma origem contra contas diferentes chegam a
# disparar. Falha calada: os dois cenários simplesmente nunca bloqueiam.
AXES_LOCKOUT_PARAMETERS = [["username"], ["ip_address"]]
# Declarado, embora seja o default de `axes/conf.py`, porque é o nome do campo do FORMULÁRIO,
# e não o do modelo. O `AuthenticationForm` do Django chama seu campo de `username` mesmo com
# USERNAME_FIELD = "email" (a armadilha já registrada em `tests/test_login_view.py:28`), e o
# default do axes na 8.3.1 é `USERNAME_FIELD` — ou seja, `email`, campo que este formulário
# não tem. Sem esta linha o axes lê None em toda tentativa e para de contar por conta, sem
# erro e sem log, restando só a contagem por origem. Renomear o campo do formulário produz o
# mesmo silêncio.
AXES_USERNAME_FORM_FIELD = "username"
# Login bem-sucedido zera o contador da conta: erros espaçados ao longo de semanas não somam
# contra quem nunca esteve sob ataque.
AXES_RESET_ON_SUCCESS = True
# Contador no banco, que é o default, e a escolha é deliberada: o rollback do `TestCase` o
# limpa entre casos, e a independência de ordem da suíte deixa de depender da disciplina de
# quem escreve teste. O handler de cache seria mais rápido e alcançaria, na limpeza, o cache
# que guarda a sessão (ADR 0005).
AXES_HANDLER = "axes.handlers.database.AxesDatabaseHandler"
# Contrato por string, resolvido em runtime pelo axes: é o que faz a origem que ele conta ser
# a mesma que a trilha grava (ADR 0015).
#
# O SILÊNCIO DESTA LINHA é o de removê-la: hoje a remoção não muda um único valor, e por isso
# nada a acusaria. O `ipware` não está instalado — não é dependência do axes 8.3.1 —, de modo
# que `IPWARE_INSTALLED` é falso e o caminho alternativo de `axes/helpers.py:206-225` cai em
# `request.META.get("REMOTE_ADDR")`, que é exatamente o que esta função devolve enquanto
# `BEHIND_TLS_PROXY` for falso. A remoção só passa a custar quando a variável de proxy for
# ligada, e aí custa a igualdade inteira. O único teste que alcança a diferença é o T-04 de
# `tests/test_limite_login.py`, e ele só a alcança porque roda sob
# `override_settings(BEHIND_TLS_PROXY=True)`.
AXES_CLIENT_IP_CALLABLE = "config.origem.origem_da_requisicao"
# 429, e não o default 403: a recusa é por excesso, não por falta de permissão, e o status
# distingue-a do 200 com a lista de erros do formulário que uma senha errada isolada devolve.
AXES_HTTP_RESPONSE_CODE = 429
AXES_LOCKOUT_TEMPLATE = "registration/bloqueio.html"
AXES_VERBOSE = False

# O teto de requisições por origem, por caminho, aplicado por `config/limites.py`. O nome não
# diz "OAUTH" porque a chave governa também `/accounts/login/`, que não é OAuth.
#
# Cento e vinte por minuto em `/o/` é duas por segundo sustentadas por uma origem só — uma
# ordem de grandeza acima do pico plausível desta sandbox, e ordens de grandeza abaixo do que
# uma varredura de `code` precisaria para ter chance.
#
# Sessenta REQUISIÇÕES por minuto em `/accounts/login/`, e a unidade é o que importa: o contador
# soma toda requisição do caminho, e uma tentativa feita pela tela custa DUAS — o GET que
# renderiza o formulário e o POST que o envia. Sessenta requisições são, portanto, cerca de
# trinta tentativas por minuto, contra as cinco a dez que quem digita senha faz no pior caso —
# ainda uma ordem de grandeza acima de todo uso legítimo de uma tela de login vinda de uma
# origem só. O teto fica ACIMA do teto de cinco falhas do axes de propósito — a semântica de
# segurança continua sendo dele, e este teto existe só para pôr limite no CUSTO de cada
# tentativa.
#
# O custo, medido contra `axes/handlers/database.py:139-246`: com o prazo móvel, cada tentativa
# bloqueada roda um DELETE, um `select_for_update`, um UPDATE com dois `Concat` e dois SELECT
# de agregação, e reescreve `attempt_time` — o que impede `clean_expired_user_attempts` de
# alcançar aquela linha. A linha cresce cerca de 130 bytes por tentativa, e cada UPDATE a
# reescreve inteira. Sem teto de requisição, um laço de `curl` paga isso indefinidamente.
#
# Trinta por minuto em `/o/device-authorization/`, abaixo dos demais porque ali não há uso
# legítimo: este projeto não usa o device grant, e a rota só está publicada porque vem na mesma
# lista do toolkit que `/o/authorize/` e `/o/token/` (ADR 0024). Mesmo assim, é a única
# superfície anônima que grava no banco: o oauthlib só confere que o `client_id` existe, a view
# é `csrf_exempt` e `login_not_required`, e cada POST com o `client_id` público da SPA grava uma
# linha de `DeviceGrant` e responde 200. Token nenhum sai dali — `/o/token/` recusa o grant pelo
# tipo da Application —, mas a linha fica. O teto só limita o custo POR ORIGEM, e é dívida
# registrada: `clear_expired()` não apaga `DeviceGrant`, de modo que as linhas continuam
# acumulando a partir de origens distintas, sem nada que as recolha.
#
# Literais no código versionado, NUNCA variáveis de ambiente: não são segredo, não variam por
# ambiente, e uma variável nova sem default derrubaria o boot e a suíte de todo ambiente já
# montado — o `.env` é untracked e não tem cópia, como `AUDIT_LOG_PATH` mostrou. Política vive
# no código, com a razão ao lado.
RATE_LIMIT_POR_CAMINHO = {
    "/o/token/": 120,
    "/o/authorize/": 120,
    "/accounts/login/": 60,
    "/o/device-authorization/": 30,
}
RATE_LIMIT_JANELA_SEGUNDOS = 60

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
    # Governa o transporte do `code` pelo canal de frente, e por isso segue BEHIND_TLS_PROXY e
    # nunca DEBUG (ADR 0006): atrás do proxy TLS, só `https`. Alcança dois pontos: o formulário
    # de Application no admin, que recusa `http://` no campo, e o 302 de /o/authorize/ — numa
    # Application já gravada com `http://`, o redirecionamento vira DisallowedRedirect, isto é,
    # 400 depois do login, sem `code`. Na suíte vale sempre ["http", "https"], por
    # tests/runner.py. Declarada mesmo quando coincide com o default da 3.4.1: a biblioteca
    # anuncia defaults que mudam na 4.0 (ver OIDC_RP_INITIATED_LOGOUT_ENABLED), e um teste
    # indexa esta chave.
    "ALLOWED_REDIRECT_URI_SCHEMES": ["https"] if BEHIND_TLS_PROXY else ["http", "https"],
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
# Quantos proxies escrevem em `X-Forwarded-For` antes de a requisição chegar aqui. Vizinha da
# linha acima porque as duas confiam no mesmo terceiro: uma no `X-Forwarded-Proto`, outra no
# `X-Forwarded-For`. Só é lida com BEHIND_TLS_PROXY verdadeiro, e quem a lê é
# `config/origem.py`, que conta o salto a partir da direita — nunca o primeiro elemento, que
# é escrito pelo cliente. Mal escolhido, este número erra de dois modos. Alto demais: o
# cabeçalho nunca traz tantos saltos quanto os declarados, toda requisição externa cai no
# endereço direto e a contagem colapsa numa chave só, sem erro nenhum. Zero: `saltos[-0]` é
# `saltos[0]`, o primeiro elemento — o que o cliente escreve. Com o cabeçalho presente, isso
# entrega ao cliente a escolha da própria chave de contagem; com o cabeçalho AUSENTE, a lista
# está vazia e a leitura levanta `IndexError`, isto é, 500 em toda tentativa de login e em
# toda requisição a `/o/token/` e a `/o/authorize/` — as três superfícies limitadas, que são
# as que chamam a função. O resto do site, `/health` inclusive, segue respondendo, e é o que
# torna o estrago difícil de ler pela sonda. Não há guarda contra o zero, deliberadamente: o
# número é literal versionado, não vem do ambiente, e o cenário só existe se alguém escrever
# `0` nesta linha.
TRUSTED_PROXY_COUNT = 1

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
        "axes": {
            "handlers": ["console"],
            # ERROR fixo, e é uma decisão de APAGAR log de terceiro: o axes escreve o
            # identificador tentado em claro nas mensagens de tentativa e de bloqueio, todas
            # em INFO e WARNING, e o e-mail de quem tenta entrar não vai para o stdout deste
            # projeto. O rastro do bloqueio não se perde — ele passa a ser o da trilha, com
            # `identifier_sha256` em vez do e-mail, que é a regra de desenho da ADR 0013. O
            # que se perde é o diagnóstico próprio da biblioteca: quem investigar um bloqueio
            # tem a trilha, e não estas linhas.
            "level": "ERROR",
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
