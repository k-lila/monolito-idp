# Passo 04 — Projeto Django e settings

## Objetivo

Criar o projeto Django com uma configuração única dirigida por ambiente, com
`AUTH_USER_MODEL` já apontado para `accounts.User` antes de qualquer migração.

## Depende de

- Passo 01, pelas dependências instaladas e pelo contrato de variáveis do `.env.example`.
- Passo 02, porque `DATABASE_URL` e `REDIS_URL` precisam apontar para serviços de pé.
- Passo 03, porque `OIDC_RSA_PRIVATE_KEY` já é lida aqui, ainda que só seja usada no 07.

## Arquivos criados

- `manage.py` — CLI do Django.
- `config/__init__.py` — pacote do projeto.
- `config/settings.py` — configuração única, dirigida por env via `django-environ`.
- `config/urls.py` — nesta versão, só o admin. O include do DOT entra no passo 07, as
  rotas de autenticação e a home no passo 09, `/health` no passo 10.
- `config/wsgi.py` — ponto de entrada WSGI para o Gunicorn.

`config/asgi.py` **não** é criado: Gunicorn é WSGI e o arquivo ficaria sem consumidor.

## O que fazer

### Configuração dirigida por ambiente

`django-environ` lê as dez variáveis do contrato do passo 01: `DEBUG`, `SECRET_KEY`,
`ALLOWED_HOSTS`, `BASE_URL`, `DATABASE_URL`, `REDIS_URL`, `OIDC_RSA_PRIVATE_KEY`,
`BEHIND_TLS_PROXY`, `LOG_LEVEL` e `CORS_ALLOWED_ORIGINS`.

Nenhuma delas ganha default no código: o `.env` é a fonte, e variável ausente falha na
leitura nomeando-se. `LOG_LEVEL` é a exceção parcial — vale como nível dos loggers do
bloco `LOGGING`, e o `.env.example` a entrega em `INFO`.

`ALLOWED_HOSTS` precisa conter `localhost` e `127.0.0.1`.

`DATABASE_URL` e `REDIS_URL`, neste passo, são as do host: quem conecta é o `runserver`.
São as mesmas variáveis que o serviço `app` sobrescreve no passo 11 — ver "As duas
jornadas", no passo 01.

### `AUTH_USER_MODEL`

`AUTH_USER_MODEL = "accounts.User"`, e `accounts` em `INSTALLED_APPS`, **desde a primeira
versão do arquivo**. É um contrato de string resolvido em tempo de migration, e o
acoplamento mais rígido do projeto. O app `accounts` só ganha modelo no passo 05; a
configuração vem antes para que nenhum `migrate` acidental encontre a settings apontando
para o User padrão.

#### Entre este passo e o 05, o projeto não inicializa — e isso é esperado

`accounts` está em `INSTALLED_APPS` e `AUTH_USER_MODEL` aponta para um modelo que ainda
não existe. Enquanto isso durar, `manage.py check`, `manage.py shell` e qualquer outro
comando que faça a inicialização do Django falham: a inicialização importa cada entrada de
`INSTALLED_APPS`, e a checagem do modelo de usuário resolve `AUTH_USER_MODEL` pelo
registro de apps.

**Isto é estado transitório, não erro de configuração.** Criar `accounts/__init__.py`
vazio agora não adianta: o pacote passa a importar, mas o modelo continua sem existir e a
checagem continua falhando. A saída é executar o passo 05.

As duas correções intuitivas diante desse erro são as duas erradas:

- **remover ou adiar o `AUTH_USER_MODEL`** — desfaz a única razão de a configuração vir
  antes do modelo, e deixa a settings apontando para o User padrão no momento em que
  alguém rodar `migrate`;
- **rodar `migrate` "para criar as tabelas"** — é o único erro irreversível deste
  scaffold. Ver o passo 06.

O erro some no passo 05, sem que nada precise ser desfeito aqui.

### Hash de senha

```
PASSWORD_HASHERS = [Argon2PasswordHasher, ...demais hashers do Django]
```

`Argon2PasswordHasher` **em primeiro lugar**, com os demais hashers preservados abaixo
para permitir re-hash de credenciais legadas no próximo login.

### Endurecimento de transporte — governado por `BEHIND_TLS_PROXY`

`SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_SSL_REDIRECT`,
`SECURE_HSTS_SECONDS` e `SECURE_PROXY_SSL_HEADER` ligam **quando e somente quando**
`BEHIND_TLS_PROXY` é verdadeira. **Nunca** derivados de `DEBUG`.

`DEBUG` é variável sobre diagnóstico; cookie seguro depende de transporte. São dimensões
independentes, e acoplá-las produz o pior modo de falha possível aqui: com `DEBUG=False`
sem TLS, o cookie de sessão é descartado, o login falha com 302 silencioso e não há erro
em lugar nenhum.

### `LOGGING` explícito

Bloco `dictConfig` com handler de console em stdout, **sem `require_debug_true`** e **sem
`mail_admins`**, nível vindo de `LOG_LEVEL` (`INFO` no `.env.example`), cobrindo os
loggers `root`, `django`,
`django.request` e `oauth2_provider`.

O `DEFAULT_LOGGING` do Django prende o console a `require_debug_true` e roteia
`django.request` para `mail_admins`. Com `DEBUG=False` e sem e-mail configurado — que é
exatamente o modo em que este projeto roda — um 500 no endpoint de token simplesmente
desaparece. Esta é a linha que faz os erros aparecerem em `docker logs`.

### Banco, cache e sessão

- Banco: Postgres via `psycopg[binary]`, configurado a partir de `DATABASE_URL`.
- `CACHES` default: `django.core.cache.backends.redis.RedisCache` a partir de `REDIS_URL`
  — backend nativo do Django, sem `django-redis`.
- `SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"` — Postgres como
  armazenamento durável, Redis como camada de leitura quente. O que isso compra é
  sobreviver a flush e a reinício do Redis; **não** compra tolerância a indisponibilidade
  de conexão (ADR 0005).

### CORS — posição do middleware

`CORS_ALLOWED_ORIGINS` lido do ambiente e **vazio por default**: enquanto não houver SPA,
a allowlist fica vazia e o middleware é inerte.

**`CorsMiddleware` vai no topo da lista de middleware** — acima do `CommonMiddleware` e
de qualquer outro capaz de gerar resposta.

A razão de a exigência importar: instalada sem consumidor, uma posição errada é
**indetectável nesta fase** e reaparece na fase do SPA como erro de CORS que ninguém
associa a esta linha. Registrar a exigência no código (comentário na lista de middleware)
e no README (passo 12) é o que torna defensável manter a dependência agora.

A lista de middleware ainda não está completa aqui: o `WhiteNoiseMiddleware` entra no
passo 09, e é **lá que está a lista final, escrita por extenso**. Este passo estabelece a
regra; o 09 fixa o resultado.

### Estáticos e templates

`STATIC_URL`, `STATICFILES_DIRS` apontando para `static/` e `TEMPLATES` com o diretório
`templates/` no `DIRS`.

`STATIC_ROOT`, `STORAGES` e o `WhiteNoiseMiddleware` entram no passo 09, junto com os
arquivos que eles servem.

## Proibições que incidem aqui

- **Não rodar `migrate` neste passo.** O User ainda não existe (passo 05) e a primeira
  migração é o passo 06. Rodar antes envenena `contenttypes`, admin e as FKs do DOT.
- **Não atrelar cookies seguros, HSTS ou redirect de HTTPS ao valor de `DEBUG`.** Produz
  login que falha sem erro.
- **Não deixar as settings sem bloco `LOGGING`.** O default emudece `django.request`
  quando `DEBUG` é falso, que é o modo em que o container roda.
- **Não deixar valendo o `PASSWORD_HASHERS` default.** Argon2 primeiro, sempre. Trocar
  depois só re-hasha no próximo login bem-sucedido, e usuário inativo fica em PBKDF2 para
  sempre.
- **Não usar `CORS_ALLOW_ALL_ORIGINS`.**
- **Não fazer split dev/prod de settings.** Um `settings.py` dirigido por env cobre os
  dois, e um arquivo de dev que nunca roda em produção é um caminho não exercitado.
- **Não usar sintaxe nem stdlib exclusivos do Python 3.14.** É o que mantém a descida para
  3.13 ao custo de uma linha de `FROM`, e é a contrapartida declarada da ADR 0001.

## Riscos e sinais

- **`ALLOWED_HOSTS` sem `localhost`** — sinal: o healthcheck do compose recebe 400 e o
  serviço fica eternamente unhealthy, embora a aplicação esteja funcionando para quem
  chega por fora.
- **`BEHIND_TLS_PROXY` em False atrás de um proxy TLS real** — sinal: **nenhum**. Cookies
  sem flag `Secure` e sem HSTS, silenciosamente. É o preço de desacoplar de `DEBUG`, e por
  isso precisa constar do README (passo 12).
- **Endurecimento atrelado a `DEBUG`** — sinal: login que não conclui, com 302 de volta ao
  formulário e nenhuma mensagem de erro.
- **Ausência de `LOGGING` explícito** — sinal: silêncio. Erros 500 que não aparecem em
  `docker logs`, que é o único lugar onde alguém iria procurar.
- **Redis inalcançável** — sinal: 500 em todo request autenticado, inclusive `/admin`, e
  `/health` em 503 (passo 10). Comportamento correto do `cached_db`, não defeito.
- **`CorsMiddleware` mal posicionado** — sinal: **nenhum nesta fase**; erro de CORS na
  fase do SPA, sem pista que aponte para cá.

## Passo concluído quando

`manage.py check` **não é critério deste passo** — ele só passa a partir do passo 05, pela
razão acima. O que é verificável aqui:

- importar o módulo de settings isoladamente, sem inicializar o Django
  (`python -c "import config.settings"` a partir da raiz do projeto), completa sem erro com
  o `.env` local — o que confirma que o arquivo não tem erro de sintaxe e que toda variável
  obrigatória está presente no `.env`; faltando alguma, a leitura falha com
  `ImproperlyConfigured` nomeando-a;
- a leitura do arquivo mostra `AUTH_USER_MODEL = "accounts.User"`, `Argon2PasswordHasher`
  no topo de `PASSWORD_HASHERS`, `SESSION_ENGINE` em `cached_db`, o bloco `LOGGING` sem
  `require_debug_true` e sem `mail_admins`, o endurecimento condicionado a
  `BEHIND_TLS_PROXY` e o `CorsMiddleware` no topo da lista de middleware;
- **nenhum `migrate` foi executado.**

O primeiro `manage.py check` verde do projeto acontece no passo 05.
