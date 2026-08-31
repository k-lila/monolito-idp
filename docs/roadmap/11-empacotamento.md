# Passo 11 — Empacotamento

## Objetivo

Empacotar a aplicação como container único, com boot determinístico e healthcheck que
funciona na imagem enxuta, e acrescentar o serviço `app` ao compose.

## Depende de

Todos os anteriores, e por uma razão de método: **o empacotamento vem por último, quando a
aplicação já roda em `runserver`**. Antes disso, depura-se aplicação e imagem ao mesmo
tempo e a causa de cada falha fica ambígua.

Isto é custo de depuração, **não irreversibilidade**. Nada aqui envenena estado.

Dependência concreta: passo 10, porque o `HEALTHCHECK` consome `/health`.

## Arquivos criados

- `Dockerfile` — imagem multi-stage (build de wheels, depois runtime enxuto), base
  `python:3.14-slim`.
- `docker/entrypoint.sh` — sequência de boot.

## Arquivos modificados

- `docker-compose.yml` — serviço `app` ao lado de `postgres` e `redis`.

## O que fazer

### Dockerfile

Multi-stage: um estágio constrói as wheels, o outro instala num runtime enxuto. Base
`python:3.14-slim`.

**`collectstatic` não roda no build.** Roda no entrypoint. A razão: no build não há
ambiente, e settings que precisem importar `SECRET_KEY` ou alcançar o banco fazem o
`docker build` falhar.

### `docker/entrypoint.sh`

Sequência determinística:

1. `migrate`
2. `collectstatic --noinput`
3. criação **condicional** de superusuário via `DJANGO_SUPERUSER_*`
4. `exec gunicorn`, com **bind em `0.0.0.0:8000`**

`exec` no final para que o Gunicorn receba os sinais do container diretamente.

O bind é em `0.0.0.0` e não em `127.0.0.1`: dentro do container, escutar só no loopback
torna a porta inalcançável do host mesmo publicada, e o sintoma é uma aplicação que sobe
bem e não responde a ninguém.

A porta é a `8000` porque é a de `BASE_URL` (passo 01) — ver "Porta", abaixo.

Nenhum laço de polling esperando Postgres ou Redis: a espera é do compose.

### `HEALTHCHECK`

Executado pelo **interpretador Python da própria imagem**, via `urllib` da stdlib, batendo
em `/health`.

`python:*-slim` não traz `curl` nem `wget`, e instalá-los só para o healthcheck é engordar
a imagem por um contrato que a stdlib já cumpre.

### Serviço `app` no compose

- `depends_on` com `condition: service_healthy` sobre `postgres` e `redis` — é assim que a
  espera por dependências é feita, e não por script;
- variáveis vindas do `.env`, com **duas sobrescritas** (abaixo);
- publicação de porta `8000:8000`;
- **uma réplica**. O compose declara uma só, e isso é premissa da migração no entrypoint.

TLS é responsabilidade de um proxy à frente, fora deste escopo — e é exatamente por isso
que o endurecimento é opt-in por `BEHIND_TLS_PROXY` (passo 04).

### `DATABASE_URL` e `REDIS_URL` são sobrescritas aqui

O `.env` é um só e carrega os endereços da **jornada de construção**: `localhost`, nas
portas publicadas pelo compose, porque quem conecta dos passos 04 ao 10 é o `runserver` no
host (passo 01).

Dentro do container, `localhost` é o próprio container. O Postgres atende em `postgres` e
o Redis em `redis`, que são os nomes de serviço na rede do compose.

Por isso o serviço `app` **sobrescreve as duas no bloco `environment:`**:

```
environment:
  DATABASE_URL: postgres://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
  REDIS_URL: redis://redis:6379/0
```

As portas aqui são as **internas** — `5432` e `6379` —, não as de `POSTGRES_PORT` e
`REDIS_PORT`, que só valem para quem chega pelo host.

Um `.env` só, e a sobrescrita visível no lugar onde ela se aplica. Sem ela, o container
sobe e falha ao alcançar o banco com erro que parece de credencial ou de rede.

### Porta

O serviço publica **`8000:8000`**, e o Gunicorn faz bind em `0.0.0.0:8000`.

A exigência vem de `BASE_URL=http://localhost:8000` (passo 01): `BASE_URL` é a raiz de que
o issuer `{BASE_URL}/o` é derivado, e ele entra na claim `iss` de todo `id_token` e no
documento de descoberta. Publicar em outra porta faz a discovery anunciar um endereço em
que ela própria não responde — e o erro se apresenta do lado da relying party, como issuer
inválido, não como erro de porta.

**Pare o `runserver` antes de subir o serviço `app`.** Os dois querem a mesma `8000`; com o
`runserver` de pé, o compose falha ao publicar a porta, e a mensagem fala de bind, não de
`runserver`.

## Proibições que incidem aqui

- **Não instalar `curl` nem `wget` na imagem para o healthcheck.** O interpretador já está
  lá.
- **Não gerar a chave RSA no entrypoint nem no Dockerfile.** Chave nova a cada boot
  invalida todo token vivo e quebra o cache de JWKS das relying parties. A chave vem do
  ambiente (passo 03).
- **Não rodar `collectstatic` no build.**
- **Não escalar réplicas** enquanto a migração estiver no entrypoint.
- **Não commitar o `.env`** nem deixá-lo entrar no contexto de build — o `.dockerignore` do
  passo 01 cobre isso.
- **Não editar o `.env.example` neste passo.** O contrato inteiro, inclusive as
  `DJANGO_SUPERUSER_*` que o entrypoint lê, já foi declarado no passo 01. Variável que
  aparece tarde é variável que ninguém sabe que precisa definir.
- **Não trocar os endereços do `.env` por `postgres`/`redis`** para fazer o container
  funcionar. Isso conserta a jornada de clonar-e-rodar e quebra a de construção; a
  sobrescrita em `environment:` atende as duas.

## Riscos e sinais

- **Healthcheck escrito com `curl` numa imagem slim** — sinal: serviço `app` eternamente
  unhealthy e `docker compose up --wait` que nunca retorna, **com a aplicação respondendo
  normalmente a quem chega por fora**. O sinal aponta para o lugar errado.
- **`ALLOWED_HOSTS` sem `localhost`** — sinal: healthcheck em 400 e o mesmo unhealthy
  eterno, pela outra causa.
- **`DATABASE_URL`/`REDIS_URL` do host valendo dentro do container** — sinal: o `app` sobe,
  o `migrate` do entrypoint falha ao conectar, e o erro parece de credencial ou de rede.
  Contido pela sobrescrita em `environment:`.
- **Gunicorn com bind em `127.0.0.1`** — sinal: container `unhealthy` e nenhuma resposta na
  porta publicada, com o processo rodando normalmente lá dentro.
- **Porta publicada diferente de `BASE_URL`** — sinal: a discovery responde, mas anuncia um
  issuer que não corresponde ao endereço real; a RP rejeita o token por issuer mismatch.
- **`runserver` ainda de pé na `8000`** — sinal: o compose falha ao publicar a porta, com
  mensagem de bind que não menciona `runserver`.
- **`collectstatic` no build da imagem** — sinal: `docker build` falha por `SECRET_KEY`
  ausente ou por settings tentando alcançar o banco.
- **Migrations concorrentes ao escalar réplicas** — sinal: erro de lock ou de migration já
  aplicada no boot da segunda instância. Hoje contido por uma réplica só; é dívida com data
  de vencimento conhecida, e o sinal de que passou da hora aparece justamente quando há
  pressa para escalar.
- **Log sem `LOGGING` explícito** — sinal: `docker logs` mudo diante de um 500. Contido no
  passo 04.

## Apontamentos de fase seguinte que nascem aqui

- **Superusuário via `DJANGO_SUPERUSER_*`** coloca credencial administrativa no `.env`.
  Aceitável em sandbox de host único; precisa ser removido antes de qualquer ambiente
  compartilhado.
- **Log só em stdout, sem coleta externa** — some quando o container é recriado.
- **Migração no entrypoint** — correta para uma réplica, errada para duas. Separar a
  migração do boot é o próximo passo no dia de escalar.

## Passo concluído quando

Com o `runserver` parado, `docker compose up --wait` retorna com os três serviços
`healthy`; `docker logs` do `app` mostra `migrate` e `collectstatic` executados antes do
Gunicorn; `http://localhost:8000/o/.well-known/openid-configuration` responde a partir do
container, com `issuer` igual a `{BASE_URL}/o`; e um 500 provocado aparece em
`docker logs`.
