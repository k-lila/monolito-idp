# Observabilidade — o que existe e o que falta

| Campo | Valor |
| --- | --- |
| Log operacional | um objeto JSON por linha em `stdout`, com identificador de requisição e linha de acesso própria |
| Trilha de auditoria | seis sinais, em arquivo durável no volume nomeado `auditlog` |
| Métricas, traces, coleta, alertas | não existem |
| Código | `config/observabilidade.py`, `accounts/auditoria.py`, `LOGGING` em `config/settings.py` |
| Decisões | ADRs (Architecture Decision Records) 0012, 0013 e 0014; ampliadas pelas 0016, 0018, 0020 e 0029 |

Este documento é espelho e lacuna. Espelho: descreve o que o provedor de identidade (IdP, de
_Identity Provider_) registra hoje, verificado contra o código em 2026-09-29. Lacuna: o que
ainda não existe, os critérios para escolher e o que pode quebrar sem avisar quando entrar.
Quando este texto e o código divergirem, vale o código; quando divergir de uma ADR, vale a ADR.

Ele substitui o levantamento de `docs/gaps/observabilidade.md`, escrito em 2026-09-03, antes da
TASK-013, e que sustentou as ADRs 0012 a 0014. O levantamento continua legível em
`git show 8caf117:docs/gaps/observabilidade.md`. Os metadados de pacote de terceiros citados na
seção 4 foram lidos naquela data e não foram reverificados.

---

## 1. O que existe

### 1.1 Os instrumentos

| Instrumento | Onde | O que responde | O que não responde |
| --- | --- | --- | --- |
| `/health` | `config/views.py`, ADRs 0009 a 0011 | banco e cache respondem agora? | há quanto tempo, com que frequência, com que latência |
| `HEALTHCHECK` | `Dockerfile` | o container está saudável agora? | o histórico: o Docker guarda cinco entradas em `.State.Health.Log` |
| Log operacional | `config/observabilidade.py`, ADRs 0012 e 0014 | o que aconteceu, quando, em que nível e em que requisição, desde o último `up` | nada anterior à última recriação do container |
| Linha de acesso | `ObservabilidadeMiddleware`, logger `access` | que rota respondeu, com que status e em quanto tempo | o caminho tentado quando a rota não resolve (ver 1.3) |
| Trilha de auditoria | `accounts/auditoria.py`, ADR 0013 | quem autenticou, de que origem, qual relying party (RP) recebeu token | criação de Application e revogação fora do logout (seção 3) |

### 1.2 O log operacional

Todo registro da aplicação sai como um objeto JSON por linha, pelo `FormatadorJSON`. As chaves
fixas são contrato de leitura (ADR 0012):

| Chave | Conteúdo |
| --- | --- |
| `ts` | marca de tempo ISO 8601 em UTC, com fuso explícito |
| `level` | nível do registro |
| `logger` | nome do logger |
| `request_id` | 16 caracteres hexadecimais; `-` em processo que ainda não atendeu requisição |
| `msg` | a mensagem formatada |
| `exc` | o traceback, quando houver, sem as variáveis locais de cada quadro |

O que vier de um `extra=` entra como campo a mais, e nunca sobrescreve uma chave fixa. O
atributo `request` que o Django anexa a toda resposta 4xx e 5xx fica de fora.

**O identificador de requisição** nasce no `ObservabilidadeMiddleware`, índice 1 do
`MIDDLEWARE`, logo abaixo do `CorsMiddleware`. É sempre gerado ali, nunca lido de cabeçalho de
entrada. Não há `reset` na saída: o valor vale até a entrada da requisição seguinte, para que a
linha que o Django emite depois da cadeia de middleware, em toda resposta de status 400 ou
superior, ainda saia correlacionada (ADR 0014). O `FiltroRequestId` fica nos dois handlers,
`console` e `audit`, e não em cada logger.

**A linha de acesso** é emitida pelo mesmo middleware, no logger `access`, com `route` (o nome
da rota, de `request.resolver_match.view_name`, nunca o caminho), `method`, `status` e
`duration_ms`. A rota `health` fica de fora por nome, em `ACCESS_LOG_EXCLUDED_ROUTES`, para que a
sonda de dez em dez segundos não afogue o log. É por isso que o `docker/entrypoint.sh` continua
sem `--access-logfile`.

Como a linha registra o nome da rota, e não a URL, o `id_token_hint` que viaja na query string
de `/o/logout/` não entra no log (`docs/seguranca.md`, 4.11).

**Os loggers e os níveis**, em `LOGGING`:

| Logger | Handler | Nível |
| --- | --- | --- |
| raiz, `django`, `django.request`, `oauth2_provider` | `console` | `LOG_LEVEL` |
| `access` | `console` | `LOG_LEVEL` |
| `axes` | `console` | `ERROR` fixo: o `django-axes` escreve o identificador tentado em claro nas mensagens de INFO e WARNING |
| `audit` | `audit` | `INFO` fixo, sem propagação para o console |

Ler o log, com o `jq` que separa as linhas JSON das de texto plano do gunicorn, está em
`docs/receita.md`, "Ler o log".

### 1.3 A trilha de auditoria

Seis receptores de sinal, ligados em `AccountsConfig.ready()`, escrevem no logger `audit`. O
handler é um `WatchedFileHandler` em `AUDIT_LOG_PATH`: `logs/audit.log` na jornada de
construção, `/var/log/idp/audit.log` no volume `auditlog` do container. O arquivo sobrevive
a `docker compose down`.

| `event` | Sinal e emissor | `sub` | Campos próprios | `outcome` | Decisão |
| --- | --- | --- | --- | --- | --- |
| `user_logged_in` | Django | a conta | — | `success` | 0013 |
| `user_login_failed` | Django | `None` | `identifier_sha256` | `failure` | 0013 |
| `user_logged_out` | Django | a conta, ou `None` sem sessão | — | `success` | 0013 |
| `app_authorized` | `django-oauth-toolkit`, em `/o/token/` | o dono do token, ou `None` em client credentials | `client_id` | `success` | 0013 |
| `user_locked_out` | `django-axes` | `None` | `identifier_sha256` | `blocked` | 0016 |
| `tokens_revogados` | este projeto, `accounts/logout_rp.py` | o dono dos tokens revogados | `client_id` | `success` | 0029 |

Toda linha traz também a origem, calculada num ponto só por `config/origem.py` (ADR 0015):

- `ip`, o endereço;
- `ip_src`, de onde o endereço saiu (ADR 0018);
- `ip_edge`, o que aquele endereço é para este processo (ADR 0020, emendada pela 0027).

A regra de leitura das linhas antigas, escritas antes de um desses campos existir, está na
docstring de `_origem`, em `accounts/auditoria.py`.

**O identificador na falha de autenticação.** O Django saneia `credentials` antes de enviar
`user_login_failed`, mas a chave `username` escapa do saneamento, e aqui ela carrega o e-mail
digitado. A trilha grava o resumo SHA-256 (Secure Hash Algorithm de 256 bits) desse valor, em
hexadecimal completo e sem normalizar maiúsculas e minúsculas (ADR 0013). Truncar foi recusado:
cria colisão e não compra privacidade.

**Duas leituras que enganam:**

- `app_authorized` sai também a cada renovação por `refresh_token`, e não só a cada
  consentimento. Contar essas linhas não conta autorizações.
- Na saída pela RP, `tokens_revogados` sai antes de `user_logged_out`, com o mesmo `request_id`,
  e os dois `sub` podem diferir.

### 1.4 A regra de desenho

Vale para o log operacional e para a trilha, sem exceção. Nunca entram:

- `code`, `code_verifier`, `access_token`, `refresh_token`, `id_token`;
- senha, `SECRET_KEY` e a chave privada RSA (de Rivest–Shamir–Adleman).

A pessoa identifica-se pelo `sub`, nunca pelo e-mail. O `tests/test_auditoria.py` e o
`tests/test_logout_rp.py` provam a ausência desses valores; o que cada caso cobre está em
`docs/testes.md`.

---

## 2. Onde falha em silêncio

Cada item abaixo falha sem emitir sinal, e cada um está registrado no comentário do código que
o produz.

| Silêncio | Efeito | Onde está escrito |
| --- | --- | --- |
| `LOG_LEVEL=WARNING` ou mais alto | a linha de acesso some inteira | `LOGGING`, logger `access` |
| Erro de escrita na trilha: disco cheio, volume desmontado | o `logging` manda o erro para `stderr`, a trilha para de receber linhas e o IdP segue atendendo | `accounts/auditoria.py`, antes dos receptores |
| Linha emitida fora de requisição, num processo que já atendeu uma | carrega o `request_id` da última requisição e parece correlacionada; no container não acontece, sob `manage.py test` sim | `ObservabilidadeMiddleware.__call__` |
| Atributo novo de `LogRecord` numa versão futura do Django | entra como campo solto no JSON até alguém acrescentá-lo a `_ATRIBUTOS_DO_REGISTRO`; aparece na linha, mas nada o acusa | `config/observabilidade.py` |
| Rota `health` renomeada | a sonda passa a afogar o log, e a isenção de HTTPS deixa de valer; nada liga `ACCESS_LOG_EXCLUDED_ROUTES` a `SECURE_REDIRECT_EXEMPT` além da vizinhança | `config/settings.py` |
| Resposta emitida acima do `ObservabilidadeMiddleware` | sai sem `request_id` e sem linha de acesso; hoje só o `CorsMiddleware` está acima, e a preflight `OPTIONS` não aparece no log | `MIDDLEWARE`, comentário do índice 1 |
| Confiança do `docker/Caddyfile` que falha em produção | toda linha da trilha sai com o mesmo `ip` e `ip_edge` igual a `peer`, cada uma com a forma de uma linha correta | `docker/Caddyfile`, opções globais |
| Receptor de auditoria que levanta | o login não é negado; o erro vai para o log operacional, e a linha da trilha não existe | `accounts/auditoria.py`, `except Exception` de cada receptor |

---

## 3. O que falta

| Lacuna | O que deixa sem resposta | Estado |
| --- | --- | --- |
| Coleta e retenção do log operacional | recriar o container apaga o histórico; a busca é `grep` ou `jq` | não decidida (`docs/seguranca.md`, 4.12) |
| Retenção e poda da trilha | o arquivo guarda dado pessoal, cresce indefinidamente, e nada o monitora | não decidida (`docs/seguranca.md`, 4.7) |
| Dois eventos na trilha | criação de Application e revogação fora do logout pela RP não têm sinal | não decidida (`docs/seguranca.md`, 4.7) |
| Métricas | latência e taxa por rota, falhas de autenticação por hora, 5xx, disponibilidade em série temporal, crescimento das tabelas de grant e de token | não iniciada |
| Tracing | para onde foi o tempo dentro de um pedido | adiada (4.1) |
| Alertas | que condição acorda alguém | não decidida; hoje não há quem acordar |

As perguntas que as métricas responderiam:

| Pergunta | Por que importa aqui |
| --- | --- |
| O `/o/token/` está mais lento que na semana passada? | `/o/authorize/`, `/o/token/` e `/accounts/login/` são o caminho crítico inteiro |
| Quantas falhas de autenticação na última hora, e de que origem? | a trilha registra cada uma, mas não soma; o limitador de taxa (ADR 0016) conta sem expor a contagem |
| Quantas respostas 5xx por rota? | a linha de acesso as registra, mas só enquanto o container vive |
| O banco caiu por quanto tempo, e quantas vezes no mês? | o `/health` sabe apenas o agora |
| As tabelas `oauth2_provider_grant`, `_accesstoken` e `_refreshtoken` crescem sem limite? | `cleartokens` e `clearsessions` não estão agendados |

---

## 4. Critérios para o que vier

Cada critério tem origem no próprio repositório.

- **C1. A premissa de escopo manda.** Host único e uma réplica. Em produção, a máquina do dono,
  sem porta de entrada, servida pelo túnel da Cloudflare (ADR 0027). O compose já roda quatro
  serviços, e cinco em produção com o `cloudflared`. Suíte que pressupõe cluster ou alta
  disponibilidade está fora antes de ser avaliada.
- **C2. Nada compila.** O cabeçalho do `Dockerfile` registra que a árvore do `requirements.txt`
  instala sem compilação local. Dependência nova precisa de wheel `py3-none-any` ou para
  `cp314`.
- **C3. Dependência nova tem custo já registrado.** São dois pontos de resolução de
  dependências (`docs/seguranca.md`, 4.13). Aceita-se dependência quando o código que ela
  substitui é grande e difícil de acertar; recusa-se quando são poucas linhas cujo formato
  queremos possuir. Foi o critério que manteve o formatador JSON como código próprio (ADR 0012).
- **C4. ADR aceita não se contraria.** A 0005 recusou `django-redis`, e as 0009 a 0011 fixaram o
  desenho de `/health`.
- **C5. Instrumento que mente calado é pior que instrumento ausente.** Toda escolha nova declara
  o que ela cala, como a seção 2 faz com o que já existe.
- **C6. Mudar o formato do log muda a leitura.** `docs/receita.md`, "Ler o log", e o esquema da
  ADR 0012 mudam no mesmo commit.

### 4.1 As tecnologias, como o levantamento as deixou

**Métricas: `django-prometheus` 2.5.0.** Na leitura de 2026-09-03: wheel `py2.py3-none-any`,
dependência de `prometheus-client>=0.7`, e classificadores com Python 3.14 e Django 5.2.

- O rótulo `view` sai de `request.resolver_match.view_name`, o nome da rota, e não o caminho. A
  cardinalidade fica limitada à superfície de rotas, e nenhum rótulo carrega dado pessoal.
- O backend de cache instrumentado fica de fora: o módulo importa `django_redis` no topo, e a
  ADR 0005 recusou essa dependência. A saúde do Redis ficaria com um exportador dedicado.
- O backend de banco instrumentado trata psycopg 3. Custo: sobrescrever o `ENGINE` que
  `env.db("DATABASE_URL")` monta.

**Traces: adiados.** Monólito de três workers `sync`, com o caminho de um pedido descrito em
`docs/arquitetura.md`, seção II.4. Um span de `/o/token/` mostraria o que a leitura do código já
mostra. Na leitura de 2026-09-03, `opentelemetry-instrumentation-django` estava em `0.65b0`,
versão beta que um `pip install` sem `--pre` não seleciona. Se entrar, entra pelo OpenTelemetry
Protocol (OTLP).

### 4.2 Os arranjos de coleta

| Arranjo | O que sobe | Pró | Contra |
| --- | --- | --- | --- |
| **A. Mínimo** | nada; é o que existe hoje, com a trilha em volume | nenhum container novo | nenhuma pergunta de tendência; a busca é `grep` |
| **B. Prometheus, Grafana e Loki** | Prometheus, Grafana, Loki, Alloy e os exportadores de Postgres e de Redis | peças substituíveis; o Prometheus alcança o `app` pela rede interna, sem publicar porta | seis containers para observar quatro |
| **C. `grafana/otel-lgtm`** | um container | um serviço só; a aplicação fala apenas OTLP | o próprio Grafana a publica como imagem de demonstração; obriga a instrumentação OpenTelemetry, ainda em beta para Django |

No arranjo B, o caminho do log até o Loki é o que importa. O recomendado é a aplicação escrever
num volume nomeado e o agente ler esse volume. Montar `/var/run/docker.sock` daria acesso amplo
ao daemon; plugin de driver de log cria estado no host, fora do repositório.

A publicação de qualquer interface nova, a da Grafana por exemplo, segue a regra de produção:
nada publicado, e o override `docker-compose.prod.yml` precisa de uma entrada para cada serviço
novo, sob pena de o `ports:` do base publicar na máquina de produção sem aviso.

Recusados no levantamento: Sentry auto-hospedado (infraestrutura maior que o sistema
observado), Sentry hospedado (traceback do IdP fora do host) e GlitchTip (dois serviços para
uma pergunta que o log com retenção responde em boa parte).

---

## 5. Os alçapões das métricas

Os alçapões do log e da trilha que o levantamento previa estão fechados: `WatchedFileHandler`
em vez de `RotatingFileHandler`, e linha de acesso própria em vez de `--access-logfile`. Os que
restam são todos da fatia de métricas, e cada um falha sem emitir sinal.

**A1. Três workers e um registro de métricas por processo.** Sem `PROMETHEUS_MULTIPROC_DIR`, o
`ExportToDjangoView` serve o registro do worker que atendeu a coleta. Com os três workers do
`docker/entrypoint.sh`, os contadores oscilam e nunca somam. Ligar a variável exige:

- diretório existente, senão `prometheus_client` levanta `ValueError`, ruidosamente;
- limpar o diretório no boot, antes do `exec gunicorn`, para não somar métrica de processo
  morto;
- o gancho `child_exit` do gunicorn chamando `multiprocess.mark_process_dead(pid)`, num
  `config/gunicorn.py` passado por `-c`.

A suíte roda num processo só e não prova A1. A verificação é manual: coletar duas vezes
seguidas e conferir que o contador não regride.

**A2. A posição no `MIDDLEWARE`.** O `django-prometheus` pede `PrometheusBeforeMiddleware` no
topo e `PrometheusAfterMiddleware` no fim. O topo é do `CorsMiddleware`, e a regra escrita ali é
absoluta. A entrada `Before` fica abaixo dele, e a posição relativa ao `ObservabilidadeMiddleware`
e ao `LimiteDeTaxaMiddleware` precisa de decisão: o 429 do limitador deve ser medido como
qualquer resposta. A `After` precisa conviver com o `AxesMiddleware`, que também pede o fim da
lista.

**A3. O `/metrics` repete os problemas do `/health`.** A rota do pacote é `metrics`, sem barra
final. Ela:

- não pode tocar sessão (ADR 0009);
- precisa entrar em `SECURE_REDIRECT_EXEMPT` ao lado de `health` (ADR 0010);
- precisa entrar em `ACCESS_LOG_EXCLUDED_ROUTES` pelo nome de rota que o pacote declara, senão
  cada coleta vira uma linha de acesso;
- é rota sem autenticação: entra na seção 3.2 de `docs/seguranca.md`, e em produção o túnel a
  exporia à internet se o Caddy não a recusar.

---

## 6. O que uma mudança aqui exige

| Mudança | ADR | Documentos que mudam junto |
| --- | --- | --- |
| Métricas: biblioteca, modo multiprocesso, exposição de `/metrics` | nova; acrescenta rota pública, dependência e gancho de gunicorn, e recusa o backend de cache por causa da 0005 | `docs/seguranca.md` (3.2 e 4), `docs/arquitetura.md`, `docs/testes.md`, `.env.example` |
| Arranjo de coleta | nova | `docs/arquitetura.md` (II.2), `docs/receita.md`, `docker-compose.prod.yml` |
| Retenção e poda da trilha | nova, ou emenda à 0013; decide o que se guarda sobre pessoas e por quanto tempo | `docs/seguranca.md` (4.7) |
| Evento novo na trilha | amplia a 0013 sem tocar o esquema, como a 0016 e a 0029 | `docs/seguranca.md` (2.5 e 4.7), `docs/testes.md` |
| Campo novo ou formato novo no log | emenda à 0012 | `docs/receita.md`, "Ler o log" |

Toda variável de ambiente nova entra no `.env.example`: o `config/settings.py` não tem default
no código, e a variável ausente derruba o processo na leitura das settings, nomeando a si mesma.
Candidatas: `PROMETHEUS_MULTIPROC_DIR`.

O que testar é decisão do `quality-assurance`, e quem escreve é o `tester` (`docs/testes.md`).
Os alvos óbvios da fatia de métricas: `/metrics` responde sem tocar sessão, e não produz linha
de acesso.
