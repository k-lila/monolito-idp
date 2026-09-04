# Observabilidade — a lacuna, o que a guia e as tecnologias

> **Estado: levantamento.** Nada aqui está decidido. Este documento é insumo para as ADRs
> (Architecture Decision Records) que a implementação vai exigir, e não substitui nenhuma
> delas. Os `arquivo:linha` de terceiros e os metadados de pacote foram lidos em 2026-09-03,
> contra o que está instalado em `.venv/` e contra os wheels publicados; nenhuma linha foi
> executada. Classificador de compatibilidade é declaração do autor do pacote, não prova de
> funcionamento.

## Como ler este documento

| A que pergunta você quer responder | Seção |
| --- | --- |
| O que existe hoje, e o que exatamente falta | [1](#1-o-ponto-de-partida) |
| Por que estas escolhas e não outras | [2](#2-os-seis-critérios-que-guiam-a-escolha) |
| O que é fundamental numa suíte para um IdP | [3](#3-o-que-é-fundamental-para-este-idp) |
| Qual tecnologia, e por quê | [4](#4-as-tecnologias-coerentes-com-este-projeto) |
| O que pode quebrar sem avisar | [5](#5-os-alçapões) |
| Em que ordem implementar | [6](#6-o-caminho-em-quatro-fatias) |
| Como começar, concretamente | [7](#7-esqueleto-de-implementação) |
| O que testar, e as ADRs a escrever | [8](#8-o-que-testar) e [9](#9-as-adrs-que-isto-exige) |

---

## 1. O ponto de partida

O provedor de identidade (IdP, de *Identity Provider*) tem hoje um instrumento só, e ele
responde uma pergunta binária sobre o instante presente.

### 1.1 O que já existe

| Instrumento | O que responde | O que não responde |
| --- | --- | --- |
| `/health` (`config/views.py`) | banco e cache respondem agora? | há quanto tempo, com que frequência, com que latência |
| `HEALTHCHECK` (`Dockerfile`) | o container está saudável agora? | o histórico — o Docker guarda cinco entradas em `.State.Health.Log` |
| `LOGGING` (`config/settings.py`) | o que a aplicação imprimiu desde o último `up` | tudo o que veio antes do último recreate |

### 1.2 O que não existe, e o que isso custa

- **Log sem marca de tempo, sem nível e sem nome de logger.** O `handlers.console` de
  `config/settings.py` declara `class` e `stream`, e nenhum `formatters`. Sem formatador, o
  `StreamHandler` cai no default `%(message)s`. Consequência prática: as linhas saem nuas.
  Log sem marca de tempo não serve a coletor nenhum e não se correlaciona com nada.
- **Nenhum registro de requisição bem-sucedida.** O `docker/entrypoint.sh` omite
  `--access-logfile` deliberadamente, para que o probe de dez em dez segundos não afogue o
  `docker logs`. O efeito colateral é que um fluxo que funcionou não deixa rastro nenhum.
- **Nenhuma retenção.** Recriar o container apaga o histórico. Já registrado como risco em
  `docs/seguranca.md`, seção 4.
- **Nenhuma trilha de auditoria.** Também da seção 4 de `docs/seguranca.md`: não se sabe quem
  autenticou, qual relying party (RP) recebeu token, nem quando uma Application foi criada.
- **Nenhuma métrica e nenhum trace.**

---

## 2. Os seis critérios que guiam a escolha

Cada critério tem origem no próprio repositório. Não são preferências.

**C1 — A premissa de escopo manda.** Host único, uma réplica, portas publicadas em
`127.0.0.1` (`README.md`). Suíte que pressupõe cluster, descoberta de serviço ou alta
disponibilidade está fora antes de ser avaliada.

**C2 — Nada compila.** O comentário de cabeçalho do `Dockerfile` registra que toda a árvore
de `requirements.txt` instala sem compilação local, e que por isso não há `build-essential` no
estágio 1. Dependência sem wheel para `cp314` quebra essa propriedade. Toda candidata
avaliada aqui é `py3-none-any` ou `py2.py3-none-any`.

**C3 — Dependência nova tem custo já documentado.** A seção 4 de `docs/seguranca.md` registra
os dois pontos de resolução de dependências — `pip wheel` no build e o `.venv` do host — e
cada pacote novo alarga essa fresta. A regra que decorre disso, e que este documento aplica:
**aceita-se dependência quando o código que ela substitui é grande e difícil de acertar;
recusa-se quando são poucas linhas cujo formato queremos possuir.**

**C4 — ADR aceita não se contraria.** A 0005 recusou `django-redis`; a 0009, a 0010 e a 0011
fixaram o desenho de `/health`, e um endpoint `/metrics` herda os três problemas que elas
resolveram. Contrariar qualquer uma exige ADR nova, nunca edição.

**C5 — Falha silenciosa é a moeda deste repositório.** Instrumento que mente calado é pior que
instrumento ausente, porque desloca a confiança. A seção 5 lista, para cada escolha, o que ela
cala.

**C6 — O log é o que o `docs/runbook.md` ensina a ler.** A seção "Onde olhar primeiro" manda
procurar linhas específicas em `docker compose logs app`. Mudar o formato do log desatualiza
esse documento no mesmo commit em que a mudança entra.

---

## 3. O que é fundamental para este IdP

A lista canônica — logs, métricas, traces — fica curta aqui. Falta a trilha de auditoria, que
num provedor de identidade responde o que nenhum dos outros três responde.

### 3.1 As perguntas, e o que as responde

| Pergunta que hoje não tem resposta | Instrumento |
| --- | --- |
| Isso já tinha acontecido antes de ontem? | log com retenção |
| Estas duas linhas são do mesmo pedido? | identificador de requisição |
| Quem autenticou, quando, e qual RP recebeu token? | trilha de auditoria |
| Quantas senhas erradas na última hora, e de que origem? | métrica |
| O `/o/token/` está mais lento que na semana passada? | métrica |
| O banco caiu — por quanto tempo, e quantas vezes no mês? | métrica |
| As tabelas de grant e de token estão crescendo sem limite? | métrica |
| Dentro deste pedido, o tempo foi para onde? | trace |

### 3.2 Os quatro fundamentos, em ordem de dependência

**F1 — Log estruturado.** É o degrau de que todo o resto depende. Uma linha por evento, em
JSON, com marca de tempo, nível, logger e identificador de requisição. Sem isto, não há o que
coletar, o que correlacionar nem o que reter.

**F2 — Correlação.** Um `request_id` por requisição, propagado por `contextvars` e injetado em
toda linha emitida durante ela. É o que amarra o traceback de `django.request` à linha do
`oauth2_provider` do mesmo pedido — hoje, duas linhas vizinhas no `docker logs` podem ser de
requisições diferentes, e nada no texto diz isso.

**F3 — Métricas.** O que vale medir aqui é curto e específico:

| Métrica | A que serve |
| --- | --- |
| latência e taxa por rota, com atenção a `/o/authorize/`, `/o/token/` e `/accounts/login/` | é o caminho crítico inteiro |
| falhas de autenticação por unidade de tempo | é o insumo do item 1 da fronteira de produção — limitação de taxa, `docs/seguranca.md` seção 6 |
| respostas 5xx por rota | hoje só aparecem como traceback perdido no `docker logs` |
| disponibilidade de banco e de cache, com série temporal | o `/health` sabe apenas o agora |
| contagem de linhas em `oauth2_provider_grant`, `_accesstoken` e `_refreshtoken` | `cleartokens` e `clearsessions` não estão agendados (`docs/seguranca.md`, seção 6) |

**F4 — Trilha de auditoria.** Fecha a lacuna nomeada em `docs/seguranca.md`, seção 4. Os
sinais necessários já estão instalados:

| Evento | Origem verificada | Observação |
| --- | --- | --- |
| autenticação bem-sucedida | `user_logged_in` (`django/contrib/auth/signals.py`) | traz `user` e `request` |
| falha de autenticação | `user_login_failed` | ver a decisão aberta em 3.3 |
| encerramento de sessão | `user_logged_out` | traz `user`, que pode ser `None` |
| token concedido a uma RP | `app_authorized` (`oauth2_provider/signals.py`), emitido em `oauth2_provider/views/base.py:506` | traz a Application e o token |
| Application criada | não há sinal | exige `post_save` no modelo devolvido por `get_application_model()` |
| token revogado | não há sinal | exigiria sinal de modelo; `cleartokens` apaga linhas sem emitir nada |

Campos mínimos por evento: marca de tempo, `request_id`, tipo do evento, `sub` (a chave
primária de `accounts.User`, que já é a claim `sub` de todo `id_token`), `client_id` da
Application quando houver, endereço de origem e desfecho.

**Regra de desenho, sem exceção.** Nunca entram no log: `code`, `code_verifier`,
`access_token`, `refresh_token`, `id_token`, senha, `SECRET_KEY` e a chave privada RSA (de
Rivest–Shamir–Adleman). A pessoa identifica-se pelo `sub`, nunca pelo e-mail.

### 3.3 Uma decisão aberta: o identificador na falha de autenticação

O `user_login_failed` do Django entrega `credentials` já saneado — `_clean_credentials`, em
`django/contrib/auth/__init__.py:77-90`, substitui por asteriscos toda chave que compare com
`api|token|key|secret|password|signature`. **A chave `username` não compara com nenhuma
delas**, e neste projeto ela carrega o e-mail digitado. Duas saídas:

- **registrar o identificador tentado.** Prós: é o que torna a trilha útil contra ataque de
  credencial, porque distingue uma conta sob tentativa de muitas contas sondadas. Contra:
  grava dado pessoal — inclusive de quem só errou a própria senha — num arquivo com retenção
  maior que a do log operacional.
- **registrar apenas um resumo do identificador** (por exemplo os oito primeiros caracteres do
  SHA-256). Prós: agrupa tentativas contra a mesma conta sem guardar o endereço. Contra: torna
  a investigação indireta, e exige recalcular o resumo para procurar uma conta conhecida.

Nenhuma das duas é escolhida aqui. É matéria de ADR.

### 3.4 Tracing: por que fica por último

Monólito de três workers `sync` com duas dependências, e o caminho de um pedido cabe nos
sete passos já escritos em `docs/arquitetura.md`. Um span de `/o/token/` vai mostrar "Django →
Postgres → assinatura", que é exatamente o que a leitura do código mostra. Tracing paga quando
o caminho atravessa processos que ninguém consegue ler juntos; não é o caso aqui. Somando: o
`opentelemetry-sdk` está estável na 1.44.0, mas `opentelemetry-instrumentation-django` está em
`0.65b0` — versão beta, que um `pip install` sem `--pre` nem seleciona.

---

## 4. As tecnologias coerentes com este projeto

### 4.1 Dentro do processo

#### Formato do log — **formatador próprio**, sem dependência

`logging.Formatter` subclassado em `config/`, com `json.dumps(..., default=str,
ensure_ascii=False)`.

- **Por quê:** o critério C3 aplicado ao pé da letra. São cerca de quinze linhas, o esquema de
  campos é contrato nosso, e `default=str` fecha o único modo de falha real — objeto não
  serializável vindo de um `extra`, que sem ele levantaria dentro do `logging` e faria o
  registro ser descartado com uma linha em `stderr`.
- **A alternativa, honestamente:** `python-json-logger` 4.2.0 (`py3-none-any`, exige Python
  3.10 ou mais, sem dependência de execução). É mantido, e o tratamento dos campos reservados do
  `LogRecord` já vem pronto nele. Escolha legítima para quem preferir código de terceiros a
  código próprio; a troca é uma dependência a mais contra quinze linhas a menos.

#### Identificador de requisição — **middleware próprio**

`contextvars.ContextVar` preenchido por um middleware, lido por um `logging.Filter` instalado
no handler `console`.

- **Por quê:** o filtro no handler — e não em cada logger — alcança as quatro entradas de
  `LOGGING` de uma vez, inclusive `django.request`. `django-guid` faria o mesmo trazendo
  propagação entre serviços e integrações que não existem neste monólito.

#### Métricas — **`django-prometheus` 2.5.0**

- **Por quê:** é `py2.py3-none-any`, declara `Requires-Dist: prometheus-client>=0.7` e
  `Django!=5.0.*,<6.1,>=4.2`, e os classificadores incluem Python 3.14 e Django 5.2. Satisfaz
  C2 e C1. O que ele substitui é justamente o caso do C3 em que a dependência se paga: o
  registro de métricas, o formato de exposição e o modo multiprocesso não são código que se
  queira reescrever.
- **A cardinalidade dos rótulos é segura aqui, e isto foi verificado.** O rótulo `view` sai de
  `request.resolver_match.view_name` (`django_prometheus/middleware.py:229-235`), que é o
  **nome da rota**, não o caminho: `/o/applications/1/` vira `oauth2_provider:update`, e a
  superfície de rotas deste projeto é curta. Não há explosão de séries a temer, e nenhum
  rótulo carrega dado pessoal.
- **O que dele NÃO se usa, e por quê:** o backend de cache instrumentado. O módulo
  `django_prometheus/cache/backends/redis.py` importa `django_redis` na segunda linha, no topo
  do arquivo — ou seja, mesmo a classe `NativeRedisCache`, que herda do `RedisCache` nativo do
  Django, é inalcançável sem instalar `django-redis`. A ADR 0005 recusou essa dependência.
  Critério C4: o cache fica sem métrica de acerto e erro nesta fase, e a saúde do
  Redis passa a ser coberta pelo exportador dedicado da seção 4.2.
- **O backend de banco instrumentado é usável**, e trata psycopg 3 explicitamente
  (`django_prometheus/db/backends/postgresql/base.py`). Custo: sobrescrever o `ENGINE` que
  `env.db("DATABASE_URL")` monta.

#### Traces — **adiado**

`opentelemetry-sdk` mais as instrumentações de Django, psycopg e redis. Ver a seção 3.4. Se um dia
entrar, entra pelo OpenTelemetry Protocol (OTLP), e o destino passa a ser escolha da camada
de coleta, não da aplicação.

### 4.2 Fora do processo

Três arranjos, e o critério C1 pesa em todos: cada container novo é um container num host que
já roda três.

#### Arranjo A — retenção mínima, zero container

Log em JSON no `stdout`, mais um logger `audit` dedicado escrevendo num volume nomeado.

- **Prós:** nada de novo sobe, o `docker compose logs app` continua servindo o runbook, e a
  trilha de auditoria passa a sobreviver ao recreate.
- **Contra:** não responde nenhuma pergunta de tendência, e a busca é `grep`.
- **Atenção:** o bloco `logging:` do compose com `max-size` limita o tamanho, **mas não
  sobrevive ao recreate** — o `docker compose down` leva o log junto. Rotação e retenção são
  problemas diferentes, e só o volume resolve o segundo.

#### Arranjo B — Prometheus, Grafana e Loki (recomendado para a suíte completa)

| Container | Papel |
| --- | --- |
| `prom/prometheus` | coleta `/metrics` pela rede interna do compose; nada precisa ser publicado |
| `grafana/grafana` | visualização e alerta; **dispensa o Alertmanager**, cujo papel a Grafana cumpre para um destino único |
| `grafana/loki` | armazenamento de log |
| `grafana/alloy` | agente que lê os arquivos de log e os envia ao Loki |
| `prometheuscommunity/postgres-exporter` | conexões, e — por consulta declarada — a contagem das tabelas de grant e de token |
| `oliver006/redis_exporter` | memória, evicções e conexões do Redis |

- **Prós:** cada peça é substituível, o formato de exposição é padrão, e o Prometheus alcança
  o `app` pela rede interna sem publicar porta nova. Só a interface da Grafana precisa de
  publicação, e em `127.0.0.1`, como todo o resto.
- **Contra:** seis containers para observar um sistema de três. É a suíte completa custando
  o dobro do que ela observa.
- **A escolha que importa aqui é como o log chega ao Loki**, e há três caminhos:
  1. **a aplicação escreve num volume nomeado, e o agente lê esse volume.** É o caminho
     recomendado: nenhum socket do Docker montado, nenhum caminho do host exposto;
  2. o agente monta `/var/run/docker.sock` ou `/var/lib/docker/containers`. Dá acesso amplo ao
     daemon ou a caminho do host a um container — desproporcional num projeto cujo documento
     de segurança conta cada porta publicada;
  3. plugin de driver de log do Docker, instalado no host. Funciona, mas cria estado fora do
     repositório e quebra a promessa do "clonar-e-rodar" do `README.md`.

#### Arranjo C — `grafana/otel-lgtm`, um container só

Imagem única com coletor OpenTelemetry, Prometheus, Tempo, Loki e Grafana dentro.

- **Prós:** um serviço a somar em vez de seis, o que casa bem com "host único, uma réplica"; a
  aplicação fala apenas OTLP, sem saber qual é o destino.
- **Contra:** o próprio Grafana a publica como imagem de demonstração e desenvolvimento, não
  de produção; amarra as três telemetrias a um bundle só; e obriga a instrumentação
  OpenTelemetry, cujas partes de Django ainda estão em beta, conforme a seção 3.4.

#### O que se recusou

- **Sentry auto-hospedado.** Traz banco, fila e serviços próprios: infraestrutura maior que o
  sistema observado. Desproporcional por C1.
- **Sentry hospedado.** Enviaria traceback do IdP para fora do host, o que contraria a
  premissa de escopo do `README.md`.
- **GlitchTip**, alternativa leve, reusaria o Postgres e o Redis já de pé. Continua sendo dois
  serviços para uma pergunta que o log estruturado com retenção responde em boa parte.

---

## 5. Os alçapões

Cada item abaixo falha **sem emitir sinal**. É a seção a reler antes de dar qualquer fatia por
pronta, e a fonte do que deve ser acrescentado à seção 14 de `docs/runbook.md`.

**A1 — Três workers e um registro de métricas por processo.** O `ExportToDjangoView` decide o
modo em tempo de requisição: se `PROMETHEUS_MULTIPROC_DIR` está no ambiente, monta um
`MultiProcessCollector`; se não está, serve o registro do processo que atendeu
(`django_prometheus/exports.py:116-122`). Com os três workers do `docker/entrypoint.sh` e sem
a variável, **cada coleta acerta um worker sorteado**: os contadores oscilam, nunca somam e
não produzem erro nenhum. É o alçapão principal desta escolha.

- Ligar a variável exige diretório existente — `prometheus_client/multiprocess.py:30` levanta
  `ValueError` se ela apontar para o que não é diretório, e essa falha é ruidosa;
- exige limpar o diretório no boot, antes do `exec gunicorn`, sob pena de somar métrica de
  processo morto de uma execução anterior;
- exige o gancho `child_exit` do gunicorn (`gunicorn/config.py:2041`) chamando
  `multiprocess.mark_process_dead(pid)` (`prometheus_client/multiprocess.py:177`).

**A2 — A posição do middleware.** O `CorsMiddleware` no topo é regra escrita em comentário no
`config/settings.py`, e uma posição errada é indetectável enquanto a allowlist de CORS
(Cross-Origin Resource Sharing) estiver vazia. O `django-prometheus` pede **duas** entradas —
`PrometheusBeforeMiddleware` na primeira posição e `PrometheusAfterMiddleware` na última.
Colocar a primeira acima do `CorsMiddleware` viola a regra sem produzir sintoma. A saída é a
mesma da seção 7.2: a entrada `Before` fica logo **abaixo** do `CorsMiddleware`, e o que se
perde é a medição das respostas que ele mesmo emite, que são nenhuma enquanto a allowlist
estiver vazia.

**A3 — O `/metrics` repete os três problemas do `/health`.** A rota do
`django_prometheus/urls.py` é `path("metrics", ...)`, **sem barra final**, igual ao `/health`
e pelo mesmo motivo. As três decisões já tomadas voltam a valer: não pode tocar sessão (ADR
0009), precisa entrar em `SECURE_REDIRECT_EXEMPT` junto com `health` (ADR 0010) e é mais uma
rota sem autenticação na superfície pública. Enquanto a porta estiver em `127.0.0.1`, o
alcance é o mesmo do resto; ao sair de `localhost`, `/metrics` entra na lista da seção 6 de
`docs/seguranca.md`.

**A4 — Rotação de arquivo com três processos.** `RotatingFileHandler` rotaciona por processo:
os três workers renomeiam o mesmo arquivo em momentos diferentes e linhas se perdem sem
aviso. Use `WatchedFileHandler`, que reabre o arquivo quando ele é substituído, e delegue a
rotação a um mecanismo externo ao processo.

**A5 — OpenTelemetry sob workers `sync`.** Instrumentação inicializada antes do fork
exporta com estado herdado de outro processo. O sintoma é ausência de dados, não erro. Exige o
gancho `post_fork` (`gunicorn/config.py:1917`).

**A6 — Ligar o access log sem coletor.** Reintroduz exatamente o que o `docker/entrypoint.sh`
evitou: uma linha a cada dez segundos de probe afogando o log em que a falha de `migrate` e o
traceback de 500 precisam ser vistos. **Access log e coleta são uma decisão, não duas** — e há
uma saída melhor que `--access-logfile`, na seção 7.3.

**A7 — O runbook desatualiza no mesmo commit.** `docs/runbook.md` ensina a procurar linhas
específicas em `docker compose logs app`. Com o log em JSON, o idioma passa a ser
`docker compose logs app | jq -r 'select(.level=="ERROR")'`, e a seção "Onde olhar primeiro"
precisa dizer isso.

---

## 6. O caminho em quatro fatias

Ordenadas pelo que paga mais cedo, e não pela ordem canônica dos pilares.

| Fatia | O que entra | Dependência nova | Container novo | O que passa a responder |
| --- | --- | --- | --- | --- |
| **1** | formatador JSON, `request_id`, log de acesso próprio | nenhuma | nenhum | quando, em que nível, em que pedido |
| **2** | logger `audit` com os quatro sinais, em volume nomeado | nenhuma | nenhum | quem autenticou, qual RP recebeu token |
| **3** | `django-prometheus`, Prometheus, Grafana, dois exportadores | duas | quatro | latência, taxa, 5xx, crescimento das tabelas |
| **4** | Loki e Alloy; tracing só depois, e só se preciso | nenhuma na aplicação | dois | busca no histórico de log |

As fatias 1 e 2 não custam dependência nem container, e sozinhas fecham a lacuna que
`docs/seguranca.md` nomeia. A fatia 3 é a que traz o alçapão A1. A fatia 4 é a que decide o
arranjo da seção 4.2.

---

## 7. Esqueleto de implementação

Esboços para poupar a redescoberta. **Não são código pronto**: falta o comentário de
justificativa que o `CLAUDE.md` exige, e nenhum deles foi executado.

### 7.1 `LOGGING`, com formatador e filtro

O filtro vai no handler, não em cada logger: as quatro entradas de `LOGGING` desembocam no
mesmo `console`, e uma declaração alcança as quatro.

```python
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"request_id": {"()": "config.observabilidade.FiltroRequestId"}},
    "formatters": {"json": {"()": "config.observabilidade.FormatadorJSON"}},
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "formatter": "json",
            "filters": ["request_id"],
        },
        "audit": {
            "class": "logging.handlers.WatchedFileHandler",   # nunca Rotating: ver A4
            "filename": env.str("AUDIT_LOG_PATH"),
            "formatter": "json",
            "filters": ["request_id"],
        },
    },
    # ... os quatro loggers atuais seguem apontando para "console" ...
    # "audit": {"handlers": ["audit"], "level": "INFO", "propagate": False},
}
```

### 7.2 O identificador de requisição

```python
_request_id = contextvars.ContextVar("request_id", default="-")

class RequestIdMiddleware:
    def __init__(self, get_response): self.get_response = get_response
    def __call__(self, request):
        token = _request_id.set(uuid.uuid4().hex[:16])
        try:
            return self.get_response(request)
        finally:
            _request_id.reset(token)   # obrigatório: o worker atende o próximo pedido
```

**Posição no `MIDDLEWARE`:** logo **abaixo** do `CorsMiddleware`, nunca acima (A2). O que se
perde ali são as respostas que o próprio `CorsMiddleware` emite, e não há nenhuma enquanto a
allowlist estiver vazia.

### 7.3 Log de acesso próprio, em vez de `--access-logfile`

Uma linha estruturada por requisição, emitida pelo mesmo middleware, **excluindo `/health` e
`/metrics`**. Resolve A6 sem reabrir o problema que o `docker/entrypoint.sh` fechou: o probe
de dez em dez segundos continua invisível, e o fluxo de autenticação passa a deixar rastro.

Campos: `request_id`, nome da rota (`request.resolver_match.view_name`, e não o caminho),
método, status, duração em milissegundos.

### 7.4 Os receptores de auditoria

Ligados em `AppConfig.ready()` de `accounts/apps.py`, que é o momento em que o Django
garante que os modelos já estão carregados. `app_authorized` entrega `token`; dele saem
`client_id` e o `sub`, e **nunca o valor do token**.

### 7.5 Gunicorn, para a fatia 3

Arquivo `config/gunicorn.py`, passado por `-c`:

```python
def child_exit(server, worker):
    from prometheus_client import multiprocess
    # sem isto, a métrica de um worker morto soma para sempre
    multiprocess.mark_process_dead(worker.pid)
```

E no `docker/entrypoint.sh`, antes do `exec gunicorn`: criar e esvaziar
`PROMETHEUS_MULTIPROC_DIR`.

### 7.6 As rotas

```python
path("metrics", include("django_prometheus.urls")),   # sem barra final, como /health
```

E em `config/settings.py`: `SECURE_REDIRECT_EXEMPT = [r"^health$", r"^metrics$"]` (A3).

### 7.7 As variáveis de ambiente

Toda variável nova entra no `.env.example`, porque o `config/settings.py` não tem default no
código: ausente, ela derruba o processo na leitura das settings, nomeando a si mesma. Previsão
mínima: `AUDIT_LOG_PATH`, `PROMETHEUS_MULTIPROC_DIR` e `LOG_FORMAT`, se o formato for
comutável.

### 7.8 Os documentos que mudam junto

| Documento | O que muda |
| --- | --- |
| `docs/runbook.md` | "Onde olhar primeiro" passa a ensinar `jq`; a seção 14 recebe os alçapões da seção 5 (A7) |
| `docs/seguranca.md` | a seção 4 perde a lacuna de trilha de auditoria; a seção 6 ganha `/metrics` |
| `docs/arquitetura.md` | a árvore comentada e o índice de ADRs |
| `docs/testes.md` | os casos novos, na convenção de rastreabilidade já vigente |
| `README.md` | a tabela de documentos, se este arquivo virar referência estável |

---

## 8. O que testar

O executor é o do Django, sem pytest e sem dependência de teste no `requirements.txt`. Quem
decide o que testar é o `quality-assurance`, e quem escreve é o `tester`
(`docs/testes.md`). O que segue é sugestão de alvo, não demanda `T-NN`.

| Alvo | Nível | Por que não é supérfluo |
| --- | --- | --- |
| o formatador serializa `exc_info` e um `extra` não serializável | unidade | é o modo de falha que `default=str` fecha |
| duas linhas do mesmo pedido saem com o mesmo `request_id`, e pedidos distintos com identificadores distintos | integração | o `reset()` do `contextvars` é fácil de esquecer |
| nenhum campo proibido aparece no log de um fluxo completo | integração | é a regra de desenho da seção 3.2, e é a que causa dano se falhar |
| `/health` e `/metrics` não entram no log de acesso | integração | é o que impede a regressão de A6 |
| `/metrics` responde sem tocar sessão | integração | é a garantia da ADR 0009 aplicada à rota nova |

O teste que **não** dá para escrever com esta suíte é o de A1: ele exige três processos, e a
suíte roda em um. Isso vira verificação manual no runbook — coletar duas vezes seguidas e
conferir que o contador não regride.

---

## 9. As ADRs que isto exige

Provavelmente três, e nenhuma contraria as onze existentes: a 0009, a 0010 e a 0011 são
precedente a seguir, não obstáculo.

| Decisão a registrar | Por que é ADR, e não comentário |
| --- | --- |
| formato do log, esquema de campos e destino | é contrato de leitura para toda ferramenta que vier depois, e desatualiza o runbook |
| métricas: biblioteca, modo multiprocesso e exposição de `/metrics` | acrescenta rota pública, dependência e gancho de gunicorn, e recusa o backend de cache do pacote por causa da ADR 0005 |
| trilha de auditoria: eventos, campos, retenção e o identificador da seção 3.3 | decide o que se guarda sobre pessoas, e por quanto tempo |

O arranjo de coleta da seção 4.2 provavelmente merece uma quarta, se e quando a fatia 4 for
adiante.

---

## 10. O que este documento não decide

- Qual dos três arranjos da seção 4.2 será adotado.
- A questão aberta da seção 3.3.
- Retenção: por quanto tempo o log de auditoria fica, e o que o poda.
- Alertas: que condição acorda alguém, num sandbox em que não há quem seja acordado.
- Se a fatia 4 acontece.

Este arquivo é levantamento e insumo. Fechado prova-se contra o código e contra a suíte, nunca
contra o documento que descreve o código — e não há, ainda, código nenhum a provar.
