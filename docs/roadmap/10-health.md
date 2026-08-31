# Passo 10 — `/health`

## Objetivo

Expor um sinal honesto de prontidão: um endpoint que verifica banco e cache de verdade.

## Depende de

- Passo 04, pela configuração de banco e de `CACHES`.
- Passo 09, porque a view mora em `config/views.py`, que já existe por causa da `home`.

## Arquivos modificados

- `config/views.py` — view `health`.
- `config/urls.py` — rota `/health`.

## O que fazer

A view executa duas verificações reais:

- **banco**: uma query trivial;
- **cache**: um `set` seguido de `get`.

Formato exato da resposta, com as duas passando — **200**:

```
{"status": "ok", "database": "ok", "cache": "ok"}
```

Com qualquer uma falhando — **503**, nomeando o componente e preservando as demais chaves.
Falha no Redis, por exemplo:

```
{"status": "error", "database": "ok", "cache": "error"}
```

Nomear o componente é o que separa um health de um sino: `503` sozinho manda procurar em
dois lugares, e o corpo diz em qual. A chave de cada componente é sempre a mesma, em
sucesso e em falha, para que quem lê não precise de dois parsers.

Healthcheck raso — que responde 200 só porque o processo está de pé — dá falsa sensação de
saúde e é pior que healthcheck nenhum, porque o orquestrador passa a confiar nele. É esta
rota que o `HEALTHCHECK` do serviço `app` vai consumir no passo 11.

`ALLOWED_HOSTS` precisa conter `localhost` e `127.0.0.1` (passo 04): o healthcheck bate na
própria aplicação a partir de dentro do container.

## Proibições que incidem aqui

- **Não engolir exceção de cache para "estabilizar" o health.** Com `cached_db` sobre
  Redis, Redis fora significa 503 — e isso é o comportamento correto, não um bug. O IdP
  com Redis inalcançável não atende request autenticado nenhum; um `/health` verde nessa
  situação é mentira.
- **Não usar `django-redis` com `IGNORE_EXCEPTIONS` para contornar.** Escrita de sessão
  perdida em silêncio é logout mudo, sem erro, sem log e sem causa aparente. Preferimos
  falhar alto (ADR 0005).

## Riscos e sinais

- **Redis inalcançável** — sinal: `/health` em 503 e 500 em todo request autenticado,
  inclusive `/admin`. Comportamento correto; o risco é alguém interpretá-lo como bug.
- **`ALLOWED_HOSTS` sem `localhost`** — sinal: o healthcheck recebe 400 DisallowedHost e o
  serviço fica eternamente unhealthy, embora a aplicação responda normalmente a quem chega
  por fora. O sinal engana: parece problema de saúde da aplicação e é configuração de host.
- **Healthcheck raso** — sinal: nenhum, até o dia em que o serviço estiver verde e sem
  banco.
- **503 sem nomear o componente** — sinal: o serviço fica unhealthy e a causa exige
  investigar Postgres e Redis um a um, num sistema cujos modos de falha já são difíceis de
  ver.

## Passo concluído quando

`GET /health` responde `200` com `{"status": "ok", "database": "ok", "cache": "ok"}`; ao
derrubar o Redis (`docker compose stop redis`), responde `503` com `"cache": "error"`.
Subir o Redis de volta devolve o `200`.
