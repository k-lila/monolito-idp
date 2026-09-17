# Robustez — o que cada reforço exige antes de ser implementado

> **Estado: levantamento.** Nada aqui está decidido. Este documento é insumo para as ADRs
> (Architecture Decision Records) que a implementação vai exigir, e não substitui nenhuma
> delas. Os `arquivo:linha` de terceiros foram lidos em 2026-09-08 contra o que está instalado
> em `.venv/`; os metadados de pacote, contra o que o PyPI publicava nessa data. Classificador
> de compatibilidade é declaração do autor do pacote, não prova de funcionamento. Três coisas
> aqui foram executadas, e só três: `manage.py check --deploy` neste repositório, um `redis:7`
> descartável para medir o código de saída do `redis-cli` sob senha, e um `postgres:17`
> descartável para ler o default de `max_connections`.

`docs/robustez.md` diz **o que** reforçar e **por quê**. Este documento diz **o que é preciso
saber antes** de encostar em cada item: a superfície que a mudança toca, o default real da
dependência envolvida, o que o repositório já traz pronto, a armadilha que não emite sinal, o
que a suíte trava e se a mudança exige ADR. Procedimento de operação é de `docs/runbook.md`;
estado dos controles de segurança, de `docs/seguranca.md`; o plano de observabilidade inteiro,
de `docs/gaps/observabilidade.md`. Este documento aponta para os três em vez de repeti-los.

## Como ler este documento

| A que pergunta você quer responder | Seção |
| --- | --- |
| O que já existe e eu não preciso construir | [1](#1-o-que-já-existe-e-dispensa-construção) |
| O que este reforço específico exige | [2](#2-as-fichas-dos-quatorze-reforços) |
| O que a tabela de `docs/robustez.md` não lista | [3](#3-os-controles-que-a-tabela-não-lista) |
| O que o `check --deploy` acusa hoje | [4](#4-os-onze-avisos-de-manage-py-check---deploy) |
| Em que `docs/robustez.md` erra | [5](#5-quatro-afirmações-que-este-levantamento-derruba) |
| Em que ordem, e por imposição de quê | [6](#6-a-ordem-que-as-dependências-impõem) |
| Que decisão precisa de ADR | [7](#7-as-adrs-que-isto-exige) |

---

## 1. O que já existe e dispensa construção

Cinco reforços chegam com parte do mecanismo pronta. Levantar isso primeiro evita construir o
que já está construído.

| Mecanismo pronto | Onde | Que reforço ele já atende em parte |
| --- | --- | --- |
| Conjunto de rotação de chave RSA (Rivest–Shamir–Adleman) | `oauth2_provider/settings.py:91` e `oauth2_provider/views/oidc.py:117-127` | Rotação de chave: publicar duas chaves é configuração, não código |
| Isenção da sonda no redirecionamento para HTTPS | `config/settings.py:182` (ADR 0010) | Terminação TLS (Transport Layer Security) |
| Comando avulso sem a sequência de boot | a guarda `[ "$#" -gt 0 ]` em `docker/entrypoint.sh` | Separar a migração do boot: `docker compose run --rm app python manage.py migrate` já funciona |
| Teto de tempo nas duas dependências do `/health` | `config/settings.py:99` e `:117-120` (ADR 0011) | Liveness e readiness separados |
| Plano de log estruturado e de auditoria, em quatro fatias | `docs/gaps/observabilidade.md` seções 6 e 7 | Erro rastreado, logs estruturados e auditoria |

---

## 2. As fichas dos quatorze reforços

Cada ficha tem os mesmos seis campos. **Superfície** é o que a mudança toca; **Verificado**, o
default real da dependência; **Já existe**, o que dispensa construção; **Armadilha**, a falha
que não emite sinal; **Suíte**, o que fica vermelho; **Decisão**, se cabe ADR.

### 2.1 Rate limiting na superfície de auth 🔴

**Superfície.** `config/settings.py` — `INSTALLED_APPS`, `MIDDLEWARE` e um
`AUTHENTICATION_BACKENDS` que **o projeto nunca declarou**. Mais `requirements.txt` e uma
migração nova, se o backend de contagem for o banco.

**Verificado.** `django-axes` 8.3.1 declara Django 5.2 e Python 3.14; `django-ratelimit` 4.1.0
declara Python até 3.11 e nenhuma versão de Django. Defaults do axes, em `axes/conf.py`:
`AXES_FAILURE_LIMIT` é **3** (`:32`); `AXES_COOLOFF_TIME` é `None`, isto é, bloqueio sem prazo
até alguém destravar à mão (`:118`); `AXES_LOCKOUT_PARAMETERS` cai em `["ip_address"]`
(`:39-53`); `AXES_HANDLER` é `axes.handlers.database.AxesDatabaseHandler` (`:110-112`), **não**
o de cache; e `AXES_IPWARE_META_PRECEDENCE_ORDER` é `("REMOTE_ADDR",)` (`:217-223`). O toolkit
não traz limitação nenhuma: `/o/token/` é `TokenView` (`oauth2_provider/views/base.py:485`) e
`/o/authorize/` é `AuthorizationView` (`:79`), ambas sem gancho de throttle.

**Já existe.** O axes verifica a própria instalação: `axes/checks.py:91-137` reprova
`manage.py check` se faltar o middleware ou o backend, e `:62-89` reprova cache de memória
local, de arquivo ou dummy. O cache deste projeto é Redis, compatível.

**Armadilha.** Está registrada em `.claude/memory/decisions.md:101-118` e o código de terceiro
confirma: contando por `REMOTE_ADDR` atrás de um proxy, todo request externo chega com o IP do
proxy, e o primeiro atacante que estourar o limite tranca a tela de login para todo mundo. O
antídoto é `AXES_IPWARE_PROXY_COUNT` com `AXES_IPWARE_META_PRECEDENCE_ORDER`
(`axes/conf.py:201-223`) ou um `AXES_CLIENT_IP_CALLABLE` (`:95`) — e a escolha da chave de
contagem tem de ser feita **antes** de o proxy existir, porque com `BEHIND_TLS_PROXY=False` o
defeito não se manifesta. Segunda armadilha, própria deste repositório: declarar
`AUTHENTICATION_BACKENDS` pela primeira vez para incluir o do axes e esquecer
`django.contrib.auth.backends.ModelBackend` tranca todas as contas de uma vez.

**Suíte.** Nenhum teste faz login em série: há três `POST /accounts/login/` na suíte inteira
(`tests/test_login_view.py:52` e `:78`, `tests/test_login_authorize_bridge.py:55`), e só um com
senha errada. Mas `tests/test_login_view.py:78-91` espera 200 com `errorlist` no HTML, e a
resposta de bloqueio do axes não é isso. Um teto por IP em `/o/` encosta na suíte de verdade:
`tests/oauth_helpers.py:91` e `:104-113` disparam cinco `POST` em authorize e dois em token, do
mesmo IP, sem espera. E contador em cache não volta com o rollback do `TestCase` — com o
handler de cache, a suíte fica dependente de ordem.

**Decisão.** ADR nova: escolha da biblioteca, da chave de contagem e do backend do contador.

### 2.2 Terminação TLS e reverse proxy 🔴

**Superfície.** Nenhum arquivo de código. `.env` (`BASE_URL`, `BEHIND_TLS_PROXY`,
`ALLOWED_HOSTS`), `docker-compose.yml` (publicação da porta) e o proxy, que é externo.

**Verificado.** `env.bool` aceita `1` como verdadeiro (`environ/environ.py:122`), então o
`BEHIND_TLS_PROXY=1` que `docs/robustez.md` prescreve funciona, ainda que o `.env.example` use
`True` e `False`. As quatro chaves de endurecimento derivam da variável em
`config/settings.py:174-184`.

**Já existe.** O procedimento está escrito em dois lugares: `docs/receita.md:317-334`, aberto
com o aviso de que nada ali foi exercitado, e `docs/runbook.md:189-235`, que documenta as duas
causas do `unhealthy` eterno.

**Armadilha.** Três, e as duas primeiras já estão catalogadas: o 301 do `SecurityMiddleware`
alcançando a sonda, fechado por `SECURE_REDIRECT_EXEMPT`; e `ALLOWED_HOSTS` estreitado para o
nome público, que devolve 400 `DisallowedHost` à sonda. A terceira não está em documento
nenhum: `SECURE_PROXY_SSL_HEADER` faz o Django confiar em `X-Forwarded-Proto` **de qualquer
origem**, de modo que publicar a porta do `app` além de `127.0.0.1` permite que o cliente forje
o cabeçalho e desligue o redirecionamento por conta própria. O proxy tem de ser o único caminho
até a porta.

**Suíte.** Trocar `BASE_URL` para `https://` quebra dois testes, que fixam o issuer por
igualdade literal: `tests/test_discovery.py:20` e `tests/test_authorization_code_flow.py:60`.

**Decisão.** ~~Nenhuma ADR nova para o transporte.~~ **Corrigido pelo Bloco C implantado:** o
transporte rendeu três ADRs — 0017, para o proxy no compose e a publicação só por ele; 0018,
para a procedência do endereço em cada linha da trilha; e 0019, para o superusuário fora do
boot. A troca do `BASE_URL` muda a claim `iss`
de todo `id_token` — `oauth2_provider/views/oidc.py` devolve `OIDC_ISS_ENDPOINT` literalmente —
e `docs/integracao-rp.md:182` promete às relying parties (RPs) comparação por igualdade exata
de string. É quebra de contrato público, e `docs/seguranca.md:168-169` já pede a confirmação da
string antes de a primeira RP integrar.

### 2.3 Custódia da chave RSA fora do `.env` 🔴

**Superfície.** `config/settings.py:28`, `docker-compose.yml` e `docker/entrypoint.sh`.

**Verificado.** As settings leem só do ambiente, sem default e sem suporte a arquivo
(`config/settings.py:1-6` e `:28`). O compose já sabe montar segredo em `/run/secrets/<nome>`,
mas o valor montado é arquivo, não variável.

**Já existe.** O modo de falha desejado: chave ausente derruba o processo na leitura das
settings, nomeando a si mesma (ADR 0004).

**Armadilha.** Um segredo montado como arquivo não chega ao `env.str`, e a única convenção que
fecha isso — ler `OIDC_RSA_PRIVATE_KEY_FILE` quando a variável direta faltar — introduz um
segundo caminho de leitura, com a divergência entre os dois sem produzir sinal. É o mesmo
padrão que a ADR 0011 recusou para a `DATABASE_URL`, e pela mesma razão.

**Suíte.** Nenhum teste.

**Decisão.** A ADR 0004 decidiu custodiar a chave **no ambiente**. Tirá-la de lá exige emenda
ou ADR nova, não ajuste de settings.

### 2.4 Backup e restore testados do Postgres 🔴

**Superfície.** `docker-compose.yml`: o volume de destino e, para PITR (Point-In-Time
Recovery), opções no serviço `postgres`. Mais um script novo, seguindo a convenção de
`scripts/`.

**Verificado.** O compose não monta arquivo de configuração no Postgres: ligar arquivamento de
WAL (Write-Ahead Log) exige passar as opções por `command:` e montar um volume para o arquivo
morto. `pg_dump` roda dentro do container, mas escreve no sistema de arquivos dele — o destino
tem de ser um volume ou a saída padrão redirecionada para o host.

**Já existe.** Nada.

**Armadilha.** O escopo do item, como está escrito em `docs/robustez.md`, cobre o Postgres e
deixa de fora o `.env`, que é untracked, não tem cópia e guarda a única `OIDC_RSA_PRIVATE_KEY`
e a única `SECRET_KEY` do projeto. Restaurar o banco sem a chave devolve um IdP (Identity
Provider) que não assina nada e cuja identidade, para as RPs, é outra. Segunda armadilha: um
dump restaurado numa imagem cujo estado de migração seja outro sobe com o esquema errado, e
`manage.py migrate` no boot esconde isso.

**Suíte.** Nenhum teste, e nem cabe: é procedimento de operação.

**Decisão.** Nenhuma ADR. O que falta é procedimento em `docs/runbook.md`, exercitado.

### 2.5 Separar a migração do boot 🔴

**Superfície.** `docker/entrypoint.sh` (retirar `migrate`), `docker-compose.yml` (passo
dedicado, com `depends_on` na condição `service_completed_successfully`) e o `HEALTHCHECK` do
`Dockerfile`, cujo `start-period=30s` foi dimensionado para cobrir `migrate` mais
`collectstatic`.

**Verificado.** O compose instalado é 2.27.0, que suporta a condição de conclusão. A guarda
`[ "$#" -gt 0 ]` do entrypoint já executa comando avulso sem a sequência de boot.

**Já existe.** Metade da costura, pela guarda acima.

**Armadilha.** O ganho é condicionado. `docker-compose.yml` declara uma réplica e a
ADR 0006 registra, nas consequências, que migração no entrypoint só é segura assim — dívida
contratada conscientemente. Enquanto a réplica for uma, separar a migração não destrava nada
que hoje esteja travado; o que ela destrava é o que ainda não existe.

**Suíte.** Nenhum teste. `docker/entrypoint.sh` não tem cobertura
(`docs/testes.md:226-227`), de modo que a mudança não tem rede.

**Decisão.** Contraria a ADR 0006 na decisão e nas consequências. Exige emenda ou ADR nova.

### 2.6 Erro rastreado, logs estruturados e auditoria 🔴

**Superfície.** `config/settings.py` (`LOGGING`), um middleware novo, um logger de auditoria e
os receptores dos sinais. Tudo já desenhado.

**Verificado.** `docs/gaps/observabilidade.md` seções 6 e 7 trazem as quatro fatias e o
esqueleto. As fatias 1 e 2 — formatador JSON com identificador de requisição, e logger de
auditoria com quatro sinais — **não custam dependência nem container novo**.

**Já existe.** O plano inteiro, e mais: a recusa do Sentry, registrada em
`docs/gaps/observabilidade.md:281-288`, por dois motivos independentes — auto-hospedado traz
infraestrutura maior que o sistema observado, e hospedado enviaria traceback do IdP para fora
do host, contra a premissa de escopo.

**Armadilha.** As sete de `docs/gaps/observabilidade.md` seção 5, entre elas o registro de
métricas por processo com os três workers do `docker/entrypoint.sh`.

**Suíte.** `docs/gaps/observabilidade.md:476-492` já lista os alvos e o nível de cada um.

**Decisão.** As ADRs estão nomeadas em `docs/gaps/observabilidade.md:496-508`.

### 2.7 Liveness e readiness separados 🟡

**Superfície.** `config/urls.py` (rota nova), `config/views.py`, `config/settings.py:182` e o
`HEALTHCHECK` do `Dockerfile`.

**Verificado.** O `/health` de hoje já é a sonda de prontidão, com teto de tempo derivado
(ADR 0011). O `docker-compose.yml` não declara `restart:` nenhum.

**Já existe.** A metade profunda da separação. O que falta é a rasa.

**Armadilha.** Uma segunda rota **não** fica isenta do redirecionamento para HTTPS: o
`SECURE_REDIRECT_EXEMPT` de `config/settings.py:182` é `[r"^health$"]`, ancorado nas duas
pontas. É o mesmo alçapão que `docs/gaps/observabilidade.md:320-326` registra para `/metrics`.
Sob TLS, esquecer a segunda entrada devolve exatamente o sintoma da seção 7 do
`docs/runbook.md`.

**Suíte.** As três asserções de `tests/test_health.py:20-83` comparam o corpo inteiro por
igualdade de dicionário: qualquer chave nova quebra as três.

**Decisão.** Toca a ADR 0009 (isolamento da view), a ADR 0010 (isenção) e a ADR 0011 (teto de
tempo). Emenda, no mínimo.

### 2.8 Agendar `cleartokens` 🟡

**Superfície.** Nenhum arquivo de código, se o agendamento ficar fora do container. Se entrar
no compose, um serviço novo.

**Verificado.** Lido em `oauth2_provider/models.py:1201-1306`. Sem
`REFRESH_TOKEN_EXPIRE_SECONDS` — que o projeto não declara, e cujo default é `None`
(`oauth2_provider/settings.py:65`) — o comando remove apenas refresh tokens revogados e órfãos,
access tokens sem refresh e grants vencidos. O próprio comando avisa em stderr
(`oauth2_provider/management/commands/cleartokens.py:11-19`).

**Já existe.** O diagnóstico completo, em `docs/runbook.md:409-427`, inclusive o
`clearsessions`, que `docs/robustez.md` não menciona e que colhe a `django_session` do
Postgres.

**Armadilha.** Duas. A primeira liga este item ao 4: com `REFRESH_TOKEN_REUSE_PROTECTION`
ligado — que é o que o aviso `oauth2_provider.W007` do `check --deploy` recomenda — e sem
`REFRESH_TOKEN_EXPIRE_SECONDS`, o marco de corte vira `None` e **nenhum** refresh revogado é
apagado (`oauth2_provider/models.py:1244-1255`). Adotar a conformidade sem declarar a expiração
piora a limpeza em vez de melhorá-la. A segunda: declarar `REFRESH_TOKEN_EXPIRE_SECONDS` muda o
que `docs/integracao-rp.md:193-208` promete às RPs, e nenhum teste cobre expiração
(`docs/testes.md:222`).

**Suíte.** Nenhum teste quebra, e é justamente esse o problema.

**Decisão.** Declarar tempo de vida de refresh token é contrato com a RP: cabe ADR.

### 2.9 Tuning do gunicorn e limites de recurso 🟡

**Superfície.** A última linha do `docker/entrypoint.sh`, ou um `config/gunicorn.py` passado
por `-c`; e `docker-compose.yml`, para limite de CPU e de memória.

**Verificado.** `max_requests` tem default `0`, isto é, desligado
(`gunicorn/config.py:813-816`), e `timeout` tem default 30 segundos (`:852-855`).

**Já existe.** O piso de workers está derivado e comentado no `docker/entrypoint.sh`: com um
worker só, a sonda espera na fila atrás de qualquer requisição em voo.

**Armadilha.** O evento que o item mitiga — vazamento de memória, worker preso — não foi
medido neste projeto. `--max-requests` é profilaxia, não correção de defeito observado, e com
três workers síncronos o reciclo de um deles durante degradação tira um terço da capacidade
justamente quando a sonda precisa dela. Segunda armadilha, de coordenação:
`docs/gaps/observabilidade.md:435-448` já prevê um `config/gunicorn.py` para a fatia 3. Dois
caminhos levam ao mesmo arquivo, e convém que ele seja um só.

**Suíte.** Nenhum teste.

**Decisão.** Nenhuma ADR.

### 2.10 Pool de conexões do banco 🟡

**Superfície.** `config/settings.py:92-99` e `requirements.txt`. Com PgBouncer, também o
compose.

**Verificado.** Há três opções, e `docs/robustez.md` menciona duas. A terceira é nativa: o
Django 5.2 aceita `OPTIONS["pool"]` no backend do Postgres
(`django/db/backends/postgresql/base.py:185-223`), o que dispensa container novo, exige
`psycopg[pool]` — ausente hoje — e é **incompatível com `CONN_MAX_AGE` diferente de zero**
(`:191-194`), que é a outra opção do mesmo item.

**Já existe.** Nada, e não é preciso: o alçapão clássico do PgBouncer com psycopg3 não se
aplica aqui. O Django já desliga prepared statements, com o comentário dizendo por quê — "to
keep connection poolers working" (`django/db/backends/postgresql/base.py:296-301`).

**Armadilha.** O acoplamento com a ADR 0011. Ela deriva `connect_timeout = 2` e todo o
orçamento de sete segundos do `HEALTHCHECK` do regime de conexão nova por requisição, e diz
isso expressamente. Sob pool ou conexão persistente, o `SELECT 1` do `/health` passa a pegar
conexão viva, e a sonda deixa de medir a fase que o teto protege.

**Suíte.** Nenhum teste quebra. O comportamento de tempo do `/health` muda sem sinal.

**Decisão.** Emenda à ADR 0011, cuja premissa a mudança invalida.

### 2.11 Plano de rotação de chave 🟡

**Superfície.** `config/settings.py:161`, `.env`, `.env.example` e `scripts/gen_dev_key.sh`.

**Verificado.** O toolkit já publica conjunto de rotação: o JWKS (JSON Web Key Set) itera sobre
a chave ativa mais `OIDC_RSA_PRIVATE_KEYS_INACTIVE` (`oauth2_provider/views/oidc.py:117-127`;
default `[]` em `oauth2_provider/settings.py:91`). O `kid` de cada chave é o thumbprint da
RFC 7638, e o cabeçalho do `id_token` publica o mesmo valor
(`oauth2_provider/oauth2_validators.py:1421-1433`), de modo que o casamento entre JWKS e token
sai de graça. Do lado da leitura, `env.list` **não** tem o parâmetro `multiline`
(`environ/environ.py:334`; só `env.str` tem, em `:263-277`), então uma lista de PEMs não entra
por uma variável só: cada chave inativa precisa da própria variável, montadas em lista nas
settings.

**Já existe.** Tudo o que é código de terceiro. Falta configuração e procedimento.

**Armadilha.** O JWKS inteiro está sob `if oauth2_settings.OIDC_RSA_PRIVATE_KEY`
(`oauth2_provider/views/oidc.py:119`): com a chave ativa vazia, a resposta sai com a lista de
chaves vazia e status 200 mesmo que a lista de inativas esteja cheia. É o precedente que o
`CLAUDE.md` já nomeia, agravado — durante uma rotação, o silêncio passa a ter duas causas.

**Suíte.** Dois testes fixam o formato de chave única: `tests/test_jwks.py:19` afirma
`len(keys) == 1`, e `tests/test_authorization_code_flow.py:54-56` amarra o `kid` do cabeçalho
ao de `keys[0]`, que deixa de ser determinístico com duas chaves publicadas.

**Decisão.** A ADR 0004 é o registro da chave única. Publicar um conjunto exige emenda ou ADR
nova, e muda o que `docs/integracao-rp.md:187-191` promete.

### 2.12 CI/CD e varredura de dependências e de imagem 🟡

**Superfície.** Um diretório de automação que não existe: não há `.github/` no repositório.
CI/CD é integração e entrega contínuas, de *continuous integration* e *continuous delivery*.

**Verificado.** `pip-audit` 2.10.1 está publicado e exige Python 3.10 ou mais. A suíte precisa
de Postgres e de Redis de pé, o que significa serviços no ambiente de integração contínua.

**Já existe.** A suíte, que é ampla, e `manage.py check`, que os checks do axes e do
`corsheaders` alimentam.

**Armadilha.** Varrer `requirements.txt` não varre o que a imagem embarca.
`docs/seguranca.md:120-124` já nomeia o defeito: o `Dockerfile` roda `pip wheel -r
requirements.txt`, que resolve as transitivas sem pin na data do build, enquanto a suíte roda
contra o `.venv/` do host. `jwcrypto`, a biblioteca que assina o `id_token`, é uma dessas
transitivas. Um scanner de CVE (Common Vulnerabilities and Exposures) sobre o arquivo de
requisitos não vê essa divergência; sobre a imagem construída, vê.

**Suíte.** Nenhuma mudança.

**Decisão.** Unificar os dois pontos de resolução — com arquivo de travamento, por exemplo — é
decisão com ADR. O restante é mecânica.

### 2.13 Container não-root e imagem endurecida 🟡

**Superfície.** `Dockerfile` e `docker/entrypoint.sh`.

**Verificado.** O `collectstatic` roda no boot e escreve em `/app/staticfiles`
(`docker/entrypoint.sh`), diretório que não existe na imagem antes disso.

**Já existe.** O adiamento declarado no `Dockerfile`, com a condição de revisão escrita —
primeira exposição fora de `localhost` — e repetido em `docs/seguranca.md:106-109`.

**Armadilha.** Sistema de arquivos read-only e `collectstatic` no boot são incompatíveis: ou o
`collectstatic` migra para o build, ou `/app/staticfiles` vira volume. Nada nisso emite aviso
antes do primeiro boot com o sistema de arquivos travado, e o sintoma é o container morrendo
antes do gunicorn.

**Suíte.** Nenhum teste.

**Decisão.** Nenhuma ADR. O `Dockerfile` já registra a intenção.

### 2.14 `manage.py check --deploy` como gate ⚪

**Superfície.** O ambiente de integração contínua da ficha 2.12, ou o `docker/entrypoint.sh`.

**Verificado, por execução.** Sem `--fail-level`, o comando sai com código zero mesmo emitindo
os onze avisos: como gate, não reprova nada. Com `--fail-level WARNING`, sai com código um.

**Já existe.** Nada.

**Armadilha.** A prioridade está invertida em relação à dependência. O item é ⚪ e prescreve
"rodar no CI", mas o CI é o item 🟡 da ficha 2.12 e não existe. E ligar o gate hoje reprova por
onze avisos, dos quais sete não têm relação nenhuma com cookie, HSTS (HTTP Strict Transport
Security) ou `DEBUG` — são os da
seção 4 abaixo.

**Suíte.** Nenhuma mudança.

**Decisão.** Nenhuma ADR para o gate. Cada aviso que ele acusar é que pode exigir uma.

---

## 3. Os controles que a tabela não lista

`docs/seguranca.md:150-174` é a lista de fronteira do projeto. Sete itens dela não aparecem em
`docs/robustez.md`, e três são da mesma gravidade dos 🔴.

- **Redis sem `requirepass`.** Ele guarda a cópia quente das sessões, inclusive as
  administrativas, e a única barreira é o bind em loopback — que é exatamente o que a exposição
  remove. A armadilha está no healthcheck, e foi **medida**: sob `requirepass`, `redis-cli
  ping` responde `NOAUTH Authentication required.` e **sai com código zero**; com a senha
  errada, responde `WRONGPASS` e também sai com zero. O `test: ["CMD", "redis-cli", "ping"]` do
  `docker-compose.yml` fica verde contra um Redis que rejeita tudo, e o `depends_on` na
  condição `service_healthy` libera o `app` para subir. Nenhuma variante de `redis-cli ping`
  distingue os casos pelo código de saída: o teste tem de comparar a saída com `PONG`.
- **Pin das dependências transitivas.** É o mesmo defeito da ficha 2.12, visto do lado da
  segurança: `jwcrypto` assina o `id_token` e nenhum teste deste repositório exercitou a versão
  que a imagem embarca.
- **Criação de superusuário fora do `.env`.** Com as duas variáveis definidas, a senha fica em
  texto claro num arquivo lido pelo compose e pelo processo.
- **Restrição de quem registra Application.** Ver a seção 4: é o que torna dois dos avisos do
  `check --deploy` alcançáveis por qualquer conta.
- **`email_verified` e revogação efetiva**, que são contrato com a RP e estão em
  `docs/integracao-rp.md`.
- **Posição do `CorsMiddleware`**, indetectável enquanto a allowlist estiver vazia — e a
  ficha 2.1 acrescenta um middleware a essa mesma lista.
- **Confirmação da string do issuer** antes de a primeira RP integrar, que a ficha 2.2 torna
  urgente.

---

## 4. Os onze avisos de `manage.py check --deploy`

Executado neste repositório em 2026-09-08, com o `.env` corrente. Quatro avisos são de
transporte e somem **onde** `BEHIND_TLS_PROXY` for verdadeiro: `security.W004` (HSTS),
`security.W008` (redirecionamento), `security.W012` e `security.W016` (cookies). São esses os
que `docs/robustez.md` antecipa.

O "onde" não é detalhe de redação. Desde a ADR 0017 essa variável é ligada num lugar só, o
`environment:` do serviço `app` do `docker-compose.yml`, e o `.env` — inclusive o
`.env.example`, que é o que um ambiente de integração contínua tende a copiar — a carrega como
`False`. Os quatro avisos somem em `docker compose exec app python manage.py check --deploy` e
continuam saindo em toda outra forma de rodar o comando. A medição acima é a da jornada de
construção.

Os outros sete são do django-oauth-toolkit, todos sobre a RFC 9700, e nenhum deles aparece em
`docs/robustez.md`:

| Aviso | O que está ligado hoje | Chave que o desliga |
| --- | --- | --- |
| `W001` | grant implícito habilitado | `COMPLIANT_BCP_RFC9700_IMPLICIT_GRANT` |
| `W002` | grant de senha do dono do recurso habilitado | `COMPLIANT_BCP_RFC9700_PASSWORD_GRANT` |
| `W004` | access token aceito na query string | `COMPLIANT_BCP_RFC9700_ACCESS_TOKEN_TRANSPORT` |
| `W005` | parâmetro `iss` da RFC 9207 omitido na resposta de autorização | `COMPLIANT_BCP_RFC9700_AUTHZ_RESPONSE_ISS` |
| `W006` | tokens guardados em texto claro | `COMPLIANT_BCP_RFC9700_TOKEN_STORAGE` |
| `W007` | sem detecção de reuso de refresh token | `REFRESH_TOKEN_REUSE_PROTECTION` |
| `W008` | `redirect_uri` em `http` permitido | `ALLOWED_REDIRECT_URI_SCHEMES` |

Dois deles não são teóricos neste projeto. `authorization_grant_type` é campo do formulário
público de registro (`oauth2_provider/views/application.py:10-21`), e a view só exige estar
autenticado (`:35`); as escolhas incluem `implicit` e `password`
(`oauth2_provider/models.py:170-182`). Qualquer conta registra hoje uma Application com um
grant que a RFC 9700 deprecia — o que amarra este bloco ao controle "restrição de quem registra
Application" da seção 3.

Três ressalvas antes de ligar as chaves em bloco. `W007` sem `REFRESH_TOKEN_EXPIRE_SECONDS`
piora o `cleartokens`, conforme a ficha 2.8. `W008` proíbe `redirect_uri` em `http`, o que
inclui o retorno em `127.0.0.1` de aplicação nativa, permitido pela RFC 8252. E `W006` muda a
forma como o token é guardado, o que alcança linhas já existentes.

---

## 5. Quatro afirmações que este levantamento derruba

Registradas aqui porque `docs/robustez.md` continua no disco e ninguém deve descobrir a
divergência sozinho.

- **"o Redis já está disponível como backend" (rate limiting).** O default do `django-axes` é
  o banco, não o cache: `AXES_HANDLER` é `axes.handlers.database.AxesDatabaseHandler`
  (`axes/conf.py:110-112`). Usar Redis é escolha explícita, e traz o efeito colateral de o
  contador não voltar com o rollback do `TestCase`.
- **"Rotação com sobreposição" como trabalho a construir.** O toolkit já publica conjunto de
  rotação por `OIDC_RSA_PRIVATE_KEYS_INACTIVE` (`oauth2_provider/views/oidc.py:117-127`), com
  `kid` casando automaticamente. O que falta é configuração, procedimento e a correção de dois
  testes que fixam a chave única.
- **"um soluço de dependência reiniciaria o container".** Não reiniciaria: o
  `docker-compose.yml` não declara `restart:` e a marca `unhealthy` do Docker não é, por si,
  gatilho de reinício. O sintoma real está documentado em `docs/runbook.md:189-235` —
  "container `unhealthy` eterno, com a aplicação atendendo por fora". O evento descrito vale
  sob orquestrador, que é o que a própria linha ressalva, mas a coluna afirma no presente.
- **"sob N workers estoura `too many connections`".** Não na forma atual: o
  `docker/entrypoint.sh` sobe três workers síncronos, que abrem no máximo três conexões
  simultâneas, contra as cem que a imagem `postgres:17` traz como default
  (`/usr/share/postgresql/postgresql.conf.sample`). O evento é condicionado à escala que a
  ficha 2.5 destravaria, não ao estado de hoje.

---

## 6. A ordem que as dependências impõem

`docs/seguranca.md:152-159` declara ordem para um item só, e é o primeiro: limitação de taxa.
`docs/robustez.md` elege a separação da migração como peça-chave. As duas ordens não podem
valer ao mesmo tempo, e o levantamento tem uma preferência com razão escrita.

**A escolha da chave de contagem precede o proxy.** É a única ordem que o repositório já
registrou por escrito, em `.claude/memory/decisions.md:101-118`, e a única cuja inversão produz
defeito sem sinal: com o proxy de pé antes, o limitador conta o IP errado e a suíte continua
verde. A sequência de `docs/robustez.md` põe TLS e rate limiting no mesmo passo, o que é a
condição exata do defeito.

O resto das dependências, sem ambiguidade:

| Item | Depende de | Por quê |
| --- | --- | --- |
| Gate do `check --deploy` (2.14) | CI (2.12) | O gate roda em algum lugar, e esse lugar não existe |
| Ligar as chaves da RFC 9700 (seção 4) | `REFRESH_TOKEN_EXPIRE_SECONDS` (2.8) | `W007` sem ela piora o `cleartokens` |
| Pool ou `CONN_MAX_AGE` (2.10) | Emenda à ADR 0011 | A premissa do teto de tempo deixa de valer |
| Liveness e readiness (2.7) | Ter orquestrador | Sem ele o veredito não aciona nada |
| Container read-only (2.13) | Mover o `collectstatic` | O boot escreve no sistema de arquivos |
| Rotação de chave (2.11) | Corrigir dois testes | Eles fixam o conjunto de uma chave |
| Restrição do registro de Application (seção 3) | — | É o que torna `W001` e `W002` alcançáveis |

---

## 7. As ADRs que isto exige

Seis itens não são tarefa: são decisão registrável. Contrariar ADR aceita exige emenda ou ADR
nova, nunca edição do arquivo aceito.

| Item | ADR envolvida | Natureza |
| --- | --- | --- |
| Rate limiting (2.1) | nenhuma ainda | ADR nova: biblioteca, chave de contagem, backend |
| Custódia da chave (2.3) | ADR 0004 | Emenda: ela decidiu custódia no ambiente |
| Migração fora do boot (2.5) | ADR 0006 | Emenda: a réplica única é premissa declarada |
| Liveness e readiness (2.7) | ADRs 0009, 0010 e 0011 | Emenda: as três descrevem uma sonda só |
| Pool de conexões (2.10) | ADR 0011 | Emenda: o regime de conexão é a premissa do teto |
| Rotação de chave (2.11) | ADR 0004 | Emenda: ela registra a chave única |

Mais duas decisões de contrato, que alcançam terceiro e não só este repositório: declarar
`REFRESH_TOKEN_EXPIRE_SECONDS` (2.8) e trocar a string do issuer (2.2).

---

## 8. O que este documento não decide

Não decide **se** algum reforço será feito, nem em que release. Não escolhe entre
`django-axes` e `django-ratelimit`, entre pool nativo e PgBouncer, nem entre `pg_dump` agendado
e PITR: levanta o que cada escolha custa e o que ela quebra. Não corrige `docs/robustez.md`,
que continua no disco como está — a seção 5 registra a divergência em vez de resolvê-la. E não
substitui `docs/gaps/observabilidade.md`, que é dono do item 2.6 inteiro.

Cada afirmação daqui foi lida contra o código, contra `.venv/` ou contra a saída de um comando
executado, e não contra o documento que descreve o código. Se este documento e o código
divergirem, o código está certo.
