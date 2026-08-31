# Passo 01 — Dependências e contrato de ambiente

## Objetivo

Fixar o conjunto de dependências com pin exato e declarar o contrato de variáveis de
ambiente, antes de existir qualquer linha de Python.

## Depende de

Nada. É o primeiro passo: as versões escolhidas condicionam tudo o que vem depois, e o
`.env.example` é o que os passos 03, 04 e 11 leem como contrato.

## As duas jornadas

O roadmap descreve **duas jornadas distintas**, e quase toda confusão de configuração
nasce de tratá-las como uma:

- **Jornada de construção** — a de quem implementa este roadmap. Virtualenv no host,
  `runserver` no host, compose rodando só Postgres e Redis. Vale dos passos 01 ao 10; o
  container entra no 11.
- **Jornada de clonar-e-rodar** — a de quem só quer o IdP de pé. Um `docker compose up`,
  sem Python no host. Existe a partir do passo 11 e é a jornada que o README documenta
  (passo 12).

As duas leem o **mesmo `.env`**, e é aí que está a armadilha: `DATABASE_URL` e `REDIS_URL`
não podem ter o mesmo valor nas duas. Ver "Endereços de banco e cache", abaixo.

## Pré-requisito de host

O pré-requisito é da **jornada de construção**. Dos passos 04 ao 10 a aplicação roda em
`runserver` no host, contra o Postgres e o Redis do compose. Isso exige, na máquina de
quem implementa:

- **Python 3.14**, a mesma série da imagem base do passo 11 — rodar o host em outra série
  desloca o ambiente de desenvolvimento do ambiente empacotado, e diferenças aparecem só
  no passo 11;
- um **virtualenv local** onde `requirements.txt` é instalado;
- Docker com `docker compose`, para o passo 02 em diante.

O container só entra no passo 11. Até lá, tudo o que o roadmap manda executar roda no
host. A jornada de clonar-e-rodar não exige nada disto além do Docker.

## Arquivos criados

- `requirements.txt` — dependências diretas com pin exato.
- `.env.example` — contrato das variáveis, sem um único valor secreto.
- `.gitignore` — barra `.env`, `*.pem`, `__pycache__`, `staticfiles/`.
- `.dockerignore` — mantém `.git`, `.env` e venv fora do contexto de build.

## O que fazer

### `requirements.txt`

Pin exato em toda dependência direta:

```
Django==5.2.17
django-oauth-toolkit==3.4.1
psycopg[binary]==3.3.4
argon2-cffi==25.1.0
django-environ==0.14.0
django-cors-headers==4.9.0
gunicorn==26.2.0
whitenoise==6.12.0
redis==8.1.0
```

O arquivo traz **um comentário registrando que 5.2.8 é o piso de compatibilidade com
Python 3.14**. A compatibilidade entrou por patch da série 5.2, não na 5.2.0; o piso não
pode viver apenas na ADR 0001, porque quem instala lê o requirements, não a ADR.

Notas sobre itens que não são óbvios pela linha:

- `django-oauth-toolkit==3.4.1` — o `jwcrypto`, que é quem viabiliza a assinatura de
  `id_token` e o JWKS, entra como dependência **incondicional** do pacote; não há extra a
  declarar. A linha dizia `[oidc]` e foi corrigida após conferência da metadata: o extra
  `oidc` **não existe** na 3.4.1 — os extras publicados são `dev`, `docs` e `test` — e
  declará-lo apenas emite warning no install.
- `psycopg[binary]==3.3.4` — publica wheels cp314 e é o driver suportado nativamente pelo
  Django 5.2.
- `argon2-cffi==25.1.0` — necessário para o `Argon2PasswordHasher` do passo 04.
- `django-cors-headers==4.9.0` — **decisão do usuário: MANTER** (ver abaixo).
- `whitenoise==6.12.0` — declara classifier para Python 3.14.
- `gunicorn==26.2.0` — **não declara** classifier para Python 3.14. Tem
  `requires_python >= 3.10` e é Python puro, então não há incompatibilidade conhecida; o
  que falta é a declaração de suporte pelo projeto, não a compatibilidade. Registrado como
  é: ausência de declaração. Se quebrar, o sinal aparece **só no passo 11**, no boot do
  container, como traceback do Gunicorn em `docker logs` do serviço `app` — nunca antes,
  porque até o passo 10 quem serve é o `runserver`. É o primeiro lugar a olhar se o
  container subir e morrer sem servir nada.
- `redis==8.1.0` — **acrescentada depois da redação original**, na mesma classe da
  correção do extra `[oidc]`: conferência do que o roadmap pressupõe contra a metadata
  real. O passo 04 configura `CACHES` com
  `django.core.cache.backends.redis.RedisCache`, que importa o cliente PyPI `redis`, e
  ele não é dependência transitiva de nenhuma das outras oito linhas. Sem esta linha o
  sinal seria `ModuleNotFoundError` no primeiro uso efetivo do cache, no passo 10 —
  longe daqui. É Python puro, com `requires_python >= 3.10` e classifier para Python
  3.14.

Todas as nove linhas levam pin exato, inclusive as duas últimas: dependência sem pin é a
que muda sozinha entre um `pip install` e o seguinte.

### `.env.example`

É o contrato completo do ambiente: **toda variável lida em qualquer passo aparece aqui**,
mesmo as que só passam a ser consumidas depois. Variável que só existe no passo que a usa
é variável que ninguém sabe que precisa definir.

Lidas por `config/settings.py` (passo 04):

`DEBUG`, `SECRET_KEY`, `ALLOWED_HOSTS`, `BASE_URL`, `DATABASE_URL`, `REDIS_URL`,
`OIDC_RSA_PRIVATE_KEY`, `BEHIND_TLS_PROXY`, `LOG_LEVEL`, `CORS_ALLOWED_ORIGINS`.

Lidas pelo `docker-compose.yml` (passo 02), para configurar os serviços de dependência:

`POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_PORT`, `REDIS_PORT`.

As duas últimas são as portas **publicadas no host**, com default `5432` e `6379`.
Publicá-las por variável em vez de literal existe por um motivo prático: colisão com um
Postgres ou um Redis já instalados na máquina é comum, e o sinal é confuso — o serviço não
sobe, ou pior, sobe e a aplicação conversa com o banco errado.

Lidas pelo `docker/entrypoint.sh` (passo 11), para a criação condicional de superusuário:

`DJANGO_SUPERUSER_EMAIL`, `DJANGO_SUPERUSER_PASSWORD`. Saem **comentadas** no
`.env.example`: o entrypoint só cria o superusuário quando elas estão definidas, e o
caminho default é `createsuperuser` à mão. Ver o apontamento sobre credencial
administrativa no `.env`, no passo 12.

Valores de saída que não são o default de tutorial:

- `DEBUG=False`
- `BEHIND_TLS_PROXY=False`

A razão: o caminho endurecido de diagnóstico é o que se exercita desde o primeiro boot, e
mesmo assim o fluxo PKCE fecha em `http://localhost` sem cookie descartado. Não existe um
"modo de desenvolvimento" que nunca é usado.

Demais valores de saída:

- `BASE_URL=http://localhost:8000` — a porta do `runserver`, que é como a aplicação roda
  dos passos 04 ao 10. `BASE_URL` é a raiz de que o issuer `{BASE_URL}/o` é derivado
  (passo 07), então **a porta publicada pelo serviço `app` no passo 11 tem de bater com
  este valor**; se não bater, a discovery não responde no endereço documentado e o critério
  de conclusão do passo 11 falha por um motivo que parece ser do DOT e é de porta.
- `ALLOWED_HOSTS` com `localhost` e `127.0.0.1` — sem isso o healthcheck do passo 11 bate
  em 400 DisallowedHost.
- `CORS_ALLOWED_ORIGINS` **vazia**.
- `LOG_LEVEL=INFO`.
- `SECRET_KEY=` e `OIDC_RSA_PRIVATE_KEY=` — **vazias**, sem placeholder de texto. A
  `SECRET_KEY` é gerada ao criar o `.env` local, abaixo; a chave RSA, no passo 03. A ordem
  01 → 03 → 04 garante que as duas estejam preenchidas quando o passo 04 as lê. Vazio é
  melhor que placeholder porque falha **ruidosamente**, nomeando a variável na leitura das
  settings, em vez de passar por válido e reaparecer no passo 07 como JWKS vazio, que é
  falha silenciosa.

### Onde moram as credenciais do Postgres

`POSTGRES_DB`, `POSTGRES_USER` e `POSTGRES_PASSWORD` moram **no `.env`**, e o
`docker-compose.yml` do passo 02 as referencia por `${...}` em vez de repetir literais.
Um lugar só para o segredo, e o compose não vira arquivo com senha dentro.

`DATABASE_URL` mora no mesmo `.env` e é escrita à mão de forma coerente com aquelas três.
A coerência entre as quatro variáveis é manual: não há mecanismo que a verifique, e o
sinal de divergência aparece no passo 06.

### Endereços de banco e cache — as duas jornadas divergem aqui

`DATABASE_URL` e `REDIS_URL` no `.env` são escritas para a **jornada de construção**:
apontam para `localhost`, nas portas de `POSTGRES_PORT` e `REDIS_PORT`, porque quem se
conecta dos passos 04 ao 10 é o `runserver` rodando no host.

Esses dois valores **não servem dentro do container**. Para o serviço `app` do passo 11,
`localhost` é o próprio container: o Postgres atende em `postgres` e o Redis em `redis`,
que são os nomes de serviço na rede do compose.

A saída, decidida e aplicada no passo 11: **o serviço `app` sobrescreve `DATABASE_URL` e
`REDIS_URL` no bloco `environment:` do compose**, com os nomes de serviço. Um `.env` só,
com os valores do host, e a sobrescrita visível exatamente onde ela vale.

Sem essa sobrescrita, o container sobe e falha ao alcançar o banco — e o erro parece de
credencial ou de rede, não de endereço.

### Criar o `.env` local

Ainda neste passo, e não em outro:

1. Copiar `.env.example` para `.env`. O `.gitignore` já barra o destino.
2. Gerar a `SECRET_KEY` e escrevê-la no `.env`. Com as dependências instaladas, serve o
   utilitário do próprio Django:
   `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`.
3. Definir `POSTGRES_*`, `POSTGRES_PORT` e `REDIS_PORT`, e escrever `DATABASE_URL` e
   `REDIS_URL` coerentes com elas, apontando para `localhost`.

Duas variáveis ficam pendentes de propósito e são preenchidas nos passos que as produzem:
`OIDC_RSA_PRIVATE_KEY` no passo 03, e as `DJANGO_SUPERUSER_*` só se e quando o passo 11
for usar o caminho automático.

O `.env` precisa existir a partir daqui porque os passos 03 e 04 já o pressupõem: o 03
escreve nele, e o 04 falha a leitura sem ele.

### CORS — decisão registrada

O `architect` recomendou adiar `django-cors-headers` para a fase que tiver um consumidor
real. **O usuário decidiu mantê-lo**, por fidelidade à seção B do `docs/esboco.md`, que é
premissa dada. A discordância fica registrada aqui.

O que torna a manutenção defensável: a allowlist fica vazia por default (middleware
inerte) e a exigência de posição do `CorsMiddleware` é cumprida no passo 04.

## Proibições que incidem aqui

- **Não commitar `.env`, arquivo `.pem` ou qualquer chave privada**, ainda que só de
  desenvolvimento. Chave de sandbox commitada é chave que reaparece em produção. É por isso
  que `.gitignore` e `.dockerignore` nascem neste passo, e não depois da chave existir.
- **Não usar `CORS_ALLOW_ALL_ORIGINS`.** O login é por redirecionamento e não depende de
  CORS; a fronteira real é a allowlist de `redirect_uri` registrada no client. CORS frouxo
  só produz falsa sensação de segurança.
- **Não adicionar DRF, SPA, rate limiting ou verificação de e-mail ao requirements.** Cada
  dependência entra com o fluxo que a justifica; instalada sem consumidor, ninguém percebe
  quando está mal configurada.

## Riscos e sinais

- **Django abaixo de 5.2.8 com Python 3.14** — sinal: falhas de importação ou
  incompatibilidade em runtime, sem relação aparente com a versão. Contido pelo pin em
  5.2.17 e pelo comentário do piso.
- **`django-oauth-toolkit` sem o extra `oidc` — causa descartada** — sinal: nenhum, e não
  haverá: o extra `oidc` **não existe** na 3.4.1 e o `jwcrypto` entra como dependência
  incondicional do pacote. Item mantido porque a redação original o listava como risco real:
  diante de um JWKS vazio no passo 07, "extra faltando" **não** é uma das causas candidatas —
  olhe para `OIDC_RSA_PRIVATE_KEY` e para o escape do PEM, dos passos 03 e 04.
- **`.env` commitado** — sinal: nenhum, até o vazamento. Contido pelo `.gitignore` nascer
  antes do `.env`.
- **`.env` inexistente ou sem `SECRET_KEY`** — sinal: `ImproperlyConfigured` na primeira
  leitura das settings, no passo 04. Falha ruidosa e imediata, mas a mensagem aponta para o
  passo 04 quando a causa está aqui.
- **`DATABASE_URL` incoerente com as `POSTGRES_*`** — sinal: erro de autenticação no
  primeiro `migrate`, no passo 06 — isto é, três passos depois de a divergência ter sido
  escrita.
- **`BASE_URL` divergente da porta em uso** — sinal: no `runserver`, discovery com issuer
  que não corresponde ao endereço real; no passo 11, a discovery não responde onde o
  critério manda procurar. Em nenhum dos dois o erro se anuncia como erro de porta.
- **`gunicorn` sob Python 3.14 sem suporte declarado** — sinal: traceback no boot do
  container, em `docker logs` do serviço `app`, no passo 11. Nenhum sinal antes disso,
  porque até o passo 10 quem serve é o `runserver`.
- **`DATABASE_URL`/`REDIS_URL` do host usadas dentro do container** — sinal: o serviço
  `app` sobe e falha ao alcançar Postgres ou Redis, com erro que parece de credencial ou de
  rede. Contido pela sobrescrita em `environment:` no passo 11.
- **Porta 5432 ou 6379 já ocupada no host** — sinal: o serviço do compose não sobe, ou a
  aplicação conversa com um banco local que não é o do projeto. Contido por
  `POSTGRES_PORT`/`REDIS_PORT`.

## Passo concluído quando

- `pip install -r requirements.txt` completa sem erro no virtualenv de Python 3.14 do host;
- `.env.example` declara todas as variáveis consumidas pelos passos 02, 03, 04 e 11 — as
  de settings, as `POSTGRES_*`, `POSTGRES_PORT`, `REDIS_PORT` e as `DJANGO_SUPERUSER_*`
  comentadas — com `DEBUG=False`, `BEHIND_TLS_PROXY=False`, `LOG_LEVEL=INFO`,
  `BASE_URL=http://localhost:8000` e `SECRET_KEY`/`OIDC_RSA_PRIVATE_KEY` vazias;
- `.env` local existe, com `SECRET_KEY` gerada e `POSTGRES_*`, `DATABASE_URL` e
  `REDIS_URL` coerentes entre si e apontando para `localhost`;
- `git status` não enxerga `.env` nem `*.pem`.
