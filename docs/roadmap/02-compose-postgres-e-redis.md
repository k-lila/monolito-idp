# Passo 02 — Compose com Postgres e Redis

## Objetivo

Subir Postgres 17 e Redis 7 com healthchecks e volumes, acessíveis a partir do host, para
que todo o desenvolvimento a partir daqui aconteça contra o alvo real.

## Depende de

Passo 01, pelo `.env`: é dele que vêm `POSTGRES_DB`, `POSTGRES_USER`,
`POSTGRES_PASSWORD`, `POSTGRES_PORT` e `REDIS_PORT`, e é com ele que a `DATABASE_URL` e a
`REDIS_URL` usadas pelo `runserver` (passo 04) precisam ser coerentes.

## Arquivos criados

- `docker-compose.yml` — **só com `postgres` e `redis`** nesta versão.

## O que fazer

Dois serviços, cada um com healthcheck e volume nomeado para o dado durável.

### Nenhum literal de credencial no compose

O `docker-compose.yml` **não repete valor nenhum de credencial**: referencia por `${...}`
as variáveis que o passo 01 declarou no `.env`, que o compose lê sozinho do diretório do
projeto.

```
POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD   -> environment do serviço postgres
POSTGRES_PORT, REDIS_PORT                       -> portas publicadas no host
```

Um lugar só para o segredo, e o compose não vira arquivo com senha dentro. Escrever a
senha literal aqui e também no `.env` cria duas fontes de verdade que divergem no dia em
que alguém troca uma delas.

### Publicação restrita ao loopback

As duas portas são publicadas com endereço explícito, `127.0.0.1:`. Publicar sem endereço
faz o Docker escutar em todas as interfaces **e** instalar as regras de DNAT à frente do
firewall do host: um UFW configurado não fecha a porta que o compose abriu. No Postgres,
o que fica exposto à rede é um servidor com senha; no Redis, que nesta versão sobe sem
`requirepass`, é um servidor sem autenticação nenhuma.

### `postgres:17`

Porta publicada no host como `127.0.0.1:${POSTGRES_PORT}:5432`, com default `5432` — a
variável existe porque colisão com um Postgres já instalado na máquina é comum.

Healthcheck com o comando exato:

```
pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}
```

`pg_isready` retorna 0 quando o servidor **responde** — inclusive quando a resposta é
falha de autenticação ou banco inexistente. Não é preciso fornecer usuário, senha ou banco
corretos para obter o status. `-U` e `-d` mudam o que aparece no log do servidor, não o
veredito: este healthcheck atesta que o Postgres está de pé, e nada além disso.

### `redis:7`

Porta publicada no host como `127.0.0.1:${REDIS_PORT}:6379`, com default `6379`, e
healthcheck que confirma resposta do servidor.

### Por que os healthchecks agora

Não são decoração: no passo 11 o serviço `app` vai depender deles por `depends_on` com
`condition: service_healthy`. Declará-los agora evita ter de voltar aqui.

O serviço `app` **não entra neste passo**. Ele entra no passo 11, quando a aplicação já
roda em `runserver` e a imagem pode ser depurada isoladamente.

## Proibições que incidem aqui

- **Não rodar `migrate` ainda.** O banco sobe vazio e fica vazio até o passo 06. Migrar
  antes de `accounts.User` existir ancora `contenttypes`, o admin e todas as FKs do
  django-oauth-toolkit no User padrão, e a correção é apagar o volume.
- **Não usar laço de polling no shell para esperar dependência.** A espera é do compose,
  por `depends_on` com `condition: service_healthy` (passo 11).

## Riscos e sinais

- **Credenciais divergentes entre compose e `DATABASE_URL`** — sinal: erro de autenticação
  no primeiro `migrate`, no passo 06. Falha ruidosa, fácil de ver. Contido pelo compose não
  ter literal nenhum: as duas pontas leem o mesmo `.env`.
- **`healthy` não significa banco do projeto acessível** — o healthcheck verde só diz que
  o servidor responde; usuário, senha e banco não são verificados por ele. Sinal: serviço
  `healthy` e erro de autenticação no primeiro `migrate`, no passo 06, longe daqui.
- **Porta 5432 ou 6379 ocupada no host** — sinal: o serviço não sobe, ou — pior — a
  aplicação do passo 04 conversa com um Postgres local que não é o do projeto e o
  `migrate` do passo 06 vai para o banco errado. Contido por `POSTGRES_PORT`/`REDIS_PORT`.
- **Volume do Postgres reaproveitado de um experimento anterior** — sinal: tabelas que não
  deveriam existir, ou `makemigrations` acusando dependência inconsistente de
  `contenttypes`. Antes do passo 06, apagar o volume ainda é gratuito.
- **O volume `pgdata` é o terceiro detentor da senha** — a imagem oficial só aplica
  `POSTGRES_PASSWORD` no `initdb`; com o volume já criado, trocar a senha no `.env` não
  troca a senha do banco. Sinal: os dois serviços `healthy`, o gate deste passo passa, o
  `depends_on` do passo 11 libera o `app` — e a falha aparece no `migrate`, como erro de
  autenticação, com `.env` e compose perfeitamente coerentes entre si. Antes do passo 06,
  apagar o volume resolve; depois, a senha se troca no banco, não no arquivo.
- **Redis inalcançável** — sinal: no passo 04 em diante, 500 em todo request autenticado,
  inclusive `/admin`, e `/health` em 503. Com `cached_db` isso é comportamento correto,
  não defeito. O risco é alguém interpretá-lo como bug e "consertar" engolindo a exceção.

## Passo concluído quando

`docker compose up -d` deixa os dois serviços `healthy`, e ambos respondem a partir do
host — e só do host — nas portas de `POSTGRES_PORT` e `REDIS_PORT`, com as credenciais do
`.env`.
