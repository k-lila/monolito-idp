# Registro de Decisões (tech-debt e decisões sem ADR)

> Log de decisões tomadas durante as tarefas e de melhorias/tech-debt identificados pelo
> `senso-critico`. **Quem escreve aqui é o orquestrador** (o thread principal); nenhum
> subagente grava neste arquivo.
>
> Decisões arquiteturais formais vão em `docs/adr/NNNN-slug.md` — **aqui fica só o resumo
> rastreável** e os itens que não bloquearam.
>
> **Formato de entrada:**
>
> ```
> ## [AAAA-MM-DD] TASK-NNN · {título}
> - **Decisão:** o que foi decidido e por quê.
> - **ADR:** docs/adr/NNNN-slug.md (se houver).
> - **Tech-debt / melhorias:** apontamentos que não bloquearam, com a disposição dada.
> - **Tipo:** decisão | melhoria | observação.
> ```

---

## Índice de decisões formalizadas em ADR

| Data | Decisão | ADR |
| --- | --- | --- |
| — | _nenhuma ainda_ | — |

---

## Entradas sem ADR

## [2026-08-31] TASK-001 · Fundação do IdP: desenho e roadmap, sem implementação

- **Decisão:** a rota `/scaffold` foi executada até a Fase 4, mas o usuário redirecionou a
  Fase 3 para **documentação apenas**. Nenhum código foi escrito. O produto é
  `docs/roadmap/` — 13 arquivos, um por passo da ordem de implementação do núcleo base
  (Authorization Code + PKCE fechando ponta a ponta, discovery e JWKS respondendo; SPA de
  teste, DRF e `end_session` fora).
- **ADR:** nenhuma gravada. As **sete ADRs de fundação foram redigidas pelo `architect` e
  estão em `docs/roadmap/13-adrs.md`**, em texto integral e verificadas por diff — mas
  **não** em `docs/adr/`, que segue só com o template. Gravá-las é trabalho de outra fase,
  e por isso `adrs_pendentes` fecha esta tarefa **não vazio**, por decisão do usuário e não
  por omissão do writer.
- **Tech-debt / melhorias:** o inventário do que ficou de fora — rate limiting (incluindo
  `/admin/login/`, que o `docs/esboco.md` não menciona), `email_verified`, `end_session`,
  agendamento de `cleartokens`/`clearsessions`, rotação de chave RSA, `BEHIND_TLS_PROXY` sem
  sinal de alerta, log sem coleta externa, superusuário no `.env` e ausência de testes — está
  em `docs/roadmap/12-readme.md`. Todos **adiados**; não replico aqui o que o repositório já
  registra.
- **Tipo:** decisão.

## [2026-08-31] TASK-001 · `django-cors-headers` mantido contra a recomendação do `architect`

- **Decisão:** o `architect` propôs adiar a dependência para a fase que tiver um consumidor
  real, pelo mesmo critério de "peso morto" que excluiu o DRF — a única justificativa do CORS
  no `docs/esboco.md` é o SPA de teste, que está fora desta fase. **O usuário decidiu manter**,
  por fidelidade à seção B do esboço, que é premissa dada. A discordância fica registrada.
  Contrapartida exigida: allowlist vazia por default e a posição do `CorsMiddleware` no topo
  da lista declarada por escrito, porque sem consumidor um posicionamento errado é
  indetectável e só reaparece na fase do SPA.
- **ADR:** nenhuma.
- **Tipo:** decisão.

## [2026-08-31] TASK-001 · Matriz de versões verificada no PyPI

- **Decisão:** o risco herdado do esboço — "wheels de libs com C ainda maturando no 3.14" —
  **não se sustentou**. Verificado na API do PyPI em 2026-08-29: `psycopg-binary` publica
  wheels cp314; `cryptography` e `argon2-cffi-bindings` publicam wheels abi3;
  `django-oauth-toolkit` 3.4.1 declara Python 3.14 e Django 5.2/6.0. Duas consequências
  duráveis: **o piso de compatibilidade com 3.14 é Django 5.2.8**, não 5.2.0 — entrou por
  patch da série —, e **`gunicorn` 26.2.0 não declara suporte a 3.14** (`requires_python
  >= 3.10`, Python puro): ausência de declaração, não incompatibilidade conhecida.
- **ADR:** o raciocínio de versão está na ADR 0001, ainda não gravada (ver primeira entrada).
- **Tipo:** observação. **Validade:** dados de 2026-08-29; reconferir antes de assumir.

## [2026-08-31] TASK-002 · O extra `[oidc]` não existe em `django-oauth-toolkit` 3.4.1

- **Decisão:** o passo 01 pedia `django-oauth-toolkit[oidc]==3.4.1` e explicava que "o extra
  `oidc` é quem traz o `jwcrypto`". Ambos estão errados na 3.4.1. Conferido na metadata do
  PyPI e confirmado num install real: `provides_extra` é `['dev', 'docs', 'test']`, e
  `jwcrypto>=1.5.0` é `Requires-Dist` **incondicional**. Declarar o extra é no-op que emite
  `warning: ... does not have an extra named oidc` em todo install. **O usuário decidiu
  remover o extra e corrigir a nota** em `docs/roadmap/01-dependencias-e-contrato-de-ambiente.md`.
  A capacidade que a nota descrevia não muda: `jwcrypto` continua sendo o que viabiliza
  assinatura de `id_token` e JWKS — ele só não é opcional.
- **ADR:** nenhuma. A ADR 0001 (ainda não gravada, ver TASK-001) trata de versões, não de extras.
- **Tipo:** decisão.

## [2026-08-31] TASK-002 · `gunicorn` 26.2.0 executa sob CPython 3.14

- **Decisão:** o risco que o passo 01 registrava — ausência de classifier 3.14, com o sinal
  aparecendo só no passo 11 como traceback de boot de container — foi **antecipado e
  fechado**. Em venv CPython 3.14.6: `gunicorn (version 26.2.0)`, exit 0, e o import de
  `gunicorn.app.wsgiapp.WSGIApplication` passa inclusive sob `-W error::DeprecationWarning`.
  O registro do passo 01 continua correto como está: a ausência é **declaratória**, não
  funcional. **Limite do que foi provado:** importar não é servir requisição sob carga com
  worker fork; isso só o passo 11 exercita.
- **ADR:** nenhuma.
- **Tipo:** observação. **Validade:** medido em 2026-08-31 com gunicorn 26.2.0 e CPython 3.14.6.

## [2026-08-31] TASK-002 · Wheels com código nativo sob 3.14: risco encerrado

- **Decisão:** reconfere e **encerra** a observação de 2026-08-29 (TASK-001, "Matriz de
  versões verificada no PyPI"), que valia só como dado de API e pedia reconferência. As oito
  linhas instalaram juntas num venv 3.14.6, versão exata em todas, 23 pacotes, **zero
  compilação local**: `psycopg-binary` 3.3.4 traz wheel `cp314` nativo; `cryptography` 50.0.1
  e `argon2-cffi-bindings` 26.1.0 trazem wheels `abi3`. Em runtime, `psycopg.pq.__impl__`
  é `binary`, `argon2.low_level.Type.ID` acessível, `cryptography` sobre OpenSSL 4.0.2.
  O ponto fraco herdado do `docs/esboco.md` — "wheels de libs com C ainda maturando na série
  nova" — **não se materializou**.
- **ADR:** nenhuma.
- **Tipo:** observação.

## [2026-08-31] TASK-002 · Python 3.14 no host, e o que ficou sem pin

- **Decisão:** o host tinha só 3.12.3, o que descumpria o pré-requisito da *jornada de
  construção* do passo 01 (passos 04→10 em `runserver` no host). **O usuário instalou o
  3.14 no sistema**: `/usr/bin/python3.14`, 3.14.6 — mesma minor do venv do spike, então a
  evidência acima vale para o venv real. `venv`, `pip` e `ssl` verificados.
- **Tech-debt / melhorias:** **adiado** — `cryptography` 50.0.1 e `argon2-cffi-bindings`
  26.1.0 são as duas dependências com código nativo do grafo e entram **sem pin**, por serem
  transitivas. Um bump silencioso delas troca o ambiente entre dois `pip install` sem que o
  `requirements.txt` mude. O passo 01 pina só dependências diretas, por decisão dele; fica
  registrado como a superfície não coberta, não como erro.
- **Tipo:** decisão.

## [2026-08-31] TASK-002 · `.gitignore` antecipado, com um acréscimo ao passo 01

- **Decisão:** o `.gitignore` é entregável do passo 01, mas o usuário pediu para criá-lo antes
  de o bloco A abrir — o repositório estava com tudo untracked e sem barreira nenhuma para o
  `.env`. As quatro entradas ditadas pelo passo 01 (`.env`, `*.pem`, `__pycache__`,
  `staticfiles/`) foram escritas literalmente. **Acréscimo:** `.venv/` e `venv/`, que o passo
  01 não lista. Razão concreta: o venv do spike tinha 85 MB e 4714 arquivos untracked, e a
  jornada de construção (passos 04→10) cria um venv no host — sem essa linha, um `git add -A`
  o arrasta para o índice. O `.dockerignore` do mesmo passo já reconhece o venv como algo a
  manter fora do contexto de build; o `.gitignore` só não tinha o par. Registrado como
  acréscimo consciente, não absorvido em silêncio.
- **ADR:** nenhuma.
- **Tipo:** decisão.

## [2026-08-31] TASK-003 · Bloco A implementado: os quatro gates fecham

- **Decisão:** os passos 01, 02 e 03 foram executados como unidade única, pela rota `/scaffold`.
  Produto: `requirements.txt`, `.env.example`, `.env`, `.dockerignore`, `docker-compose.yml`,
  `scripts/gen_dev_key.sh` e o venv 3.14.6. O `quality-assurance` verificou os quatro gates
  contra o ambiente real, executando — não relendo relatório.
- **ADR:** nenhuma gravada. As sete de fundação seguem em `docs/roadmap/13-adrs.md`, para o
  bloco G. Ver a entrada específica sobre duas delas, abaixo.
- **Tipo:** decisão.

## [2026-08-31] TASK-003 · O pacote `redis` faltava no requirements, e o sinal seria três blocos adiante

- **Decisão:** o passo 04 configura `CACHES` com `django.core.cache.backends.redis.RedisCache`,
  que importa o cliente PyPI `redis`; ele não é transitiva de nenhuma das oito linhas originais.
  Sem a nona linha, o sinal seria `ModuleNotFoundError` no bloco E. **O usuário decidiu acrescentar
  `redis==8.1.0`** — verificado no PyPI: `requires_python >=3.10`, classifier para 3.14, Python
  puro. Mesma classe da correção do extra `[oidc]` em TASK-002: conferência do que o roadmap
  pressupõe contra a metadata real. `docs/roadmap/01-...md` foi corrigido junto.
- **Tipo:** decisão.

## [2026-08-31] TASK-003 · A chave RSA: descartável até a primeira RP, e sem cópia

- **Decisão do usuário**, tomada enquanto ainda custava nada, conforme o item 3 de
  `docs/implementacao.md`: (1) a chave gerada agora é **descartável até a primeira relying party
  integrar** — a janela fecha na integração, não no fim do roadmap; (2) **não há cópia** fora do
  `.env` local, e isso é escolha declarada, não esquecimento; (3) uma chave só serve às duas
  jornadas, porque o `.env` é um só. Consequência aceita: perder a máquina é perder a identidade
  do IdP.
- **Verificação:** o round-trip foi feito com `jwcrypto` — a biblioteca que o próprio DOT importa
  para assinar —, e não só com `cryptography`: `kty: RSA`, `n` de 2048 bits, JWKS com **uma**
  chave. Isso antecipa para o bloco A o que o gate do passo 07 verificaria, contra o que o passo
  03 afirmava ser possível só lá.
- **Tipo:** decisão.

## [2026-08-31] TASK-003 · A regra de caracteres do `.env` — recusada no roadmap, registrada aqui

- **Decisão:** o `senso-critico` mostrou que o `.env` atravessa **três gramáticas** — `django-environ`,
  a interpolação do docker compose (que ocorre dentro do próprio `.env`) e a gramática de URL em
  `DATABASE_URL`/`REDIS_URL`. O alfabeto de `get_random_secret_key()` inclui `$`, com ~64% de chance
  de aparecer em 50 caracteres; um `$` faz o compose interpolar e **truncar** o valor, enquanto o
  `django-environ` lê o valor íntegro. Manifestação: `POSTGRES_PASSWORD` mutilada no `initdb`, com
  `password authentication failed` no passo 06 e as duas strings do `.env` perfeitamente idênticas.
  **O usuário recusou escrever a regra no passo 01**; fica aqui, e é esta:
  **nenhum valor entre aspas; nenhum `${...}` dentro do `.env`; `SECRET_KEY` regerada até sair sem
  `$ # " ' \`; `POSTGRES_PASSWORD` alfanumérica (`openssl rand -hex 24`), para não exigir
  percent-encoding na URL.** Os valores de hoje cumprem a regra — o `.env` foi escrito assim.
- **Tipo:** decisão. **Validade:** vale a cada recriação do `.env` e a cada troca de senha.

## [2026-08-31] TASK-003 · `pg_isready` não verifica o que o passo 02 afirmava, e a senha tem três detentores

- **Decisão:** o passo 02 e o comentário do compose afirmavam que `pg_isready -U X -d Y` "confirma
  que o banco do projeto aceita aquele usuário". **A ferramenta não faz isso**: retorna 0 quando o
  servidor responde, inclusive respondendo falha de autenticação; `-U`/`-d` mudam o log do servidor,
  não o veredito. Corrigido o texto, **mantido o comando** por decisão do usuário. Junto, registrou-se
  o que nenhum dos treze arquivos nomeava: **o volume `pgdata` é o terceiro detentor da senha** — a
  imagem só aplica `POSTGRES_PASSWORD` no `initdb`, então trocar a senha no `.env` com o volume já
  criado deixa os serviços `healthy`, o gate passa, e a falha aparece no `migrate` com `.env` e
  compose coerentes entre si.
- **Tipo:** decisão.

## [2026-08-31] TASK-003 · Duas das sete ADRs já estavam falsificadas antes de serem gravadas

- **Decisão:** o `senso-critico` apontou que o mecanismo de revisão do `docs/roadmap/13-adrs.md`
  não tem dono nem gate, e que o bloco A já produzira contradição sem propagá-la. Confirmado: a
  **ADR 0002** mandava instalar o DOT "com o extra `oidc`", que não existe na 3.4.1; a **ADR 0005**
  dizia "sem dependência extra" sobre o backend Redis, no mesmo dia em que `redis==8.1.0` entrou
  por causa dele. As duas foram corrigidas **no texto ainda não gravado** — hoje custa duas frases;
  depois do bloco G custaria uma ADR 0008 substituindo a 0002, porque ADR gravada é imutável.
- **Tech-debt / melhorias:** **adiado, e vale para os próximos blocos** — conferir se os achados do
  bloco contradizem alguma das sete ADRs **não é gate de bloco nenhum**. Taxa observada: 1,5 ADR
  falsificada no primeiro dos sete blocos, com a gravação prevista para o décimo terceiro passo.
  Quem fechar B, C, D, E e F deveria repetir a conferência no fecho de cada um.
- **Tipo:** decisão.

## [2026-08-31] TASK-003 · Portas publicadas só em `127.0.0.1`

- **Decisão:** as publicações do compose não tinham endereço, então o Docker fazia bind em
  `0.0.0.0` **e instalava DNAT à frente do firewall do host** — um UFW configurado não fechava a
  porta, e o Redis sobe sem `requirepass`, sendo onde a sessão SSO vai viver a partir do passo 04.
  Prefixadas com `127.0.0.1:`, preservando variáveis e defaults. Reverificado com os containers
  recriados: `ss -ltn` mostra `127.0.0.1:5433` e `127.0.0.1:6379`, e ambos respondem do host.
  Acesso de outra máquina da rede deixa de funcionar **por desenho**.
- **Tipo:** decisão.

## [2026-08-31] TASK-003 · `POSTGRES_PORT=5433` neste host, e o `.env` fora do alcance do rollback

- **Decisão:** a 5432 do host está ocupada por um Postgres alheio (`ss -ltn`: `127.0.0.1:5432`),
  e o bind do compose falhou. `POSTGRES_PORT=5433` **só no `.env` local**; o `.env.example` mantém
  o default 5432 do contrato. É literalmente o caso de uso para o qual o passo 01 criou a variável.
  Divergência ambiental, não de projeto: o próximo clone volta a 5432, e o passo 11 fixa as portas
  **internas** literalmente, então nada vaza.
- **Tech-debt / melhorias:** registrado no roadmap, não só aqui — `docs/implementacao.md` prometia
  rollback gratuito por commit e nomeava uma exceção; a segunda passou a estar escrita: **`.env` é
  untracked, nenhum `reset`/`checkout`/revert o restaura, e `git clean -xd` o apaga** junto com a
  única cópia da chave RSA e da `SECRET_KEY`.
- **Tipo:** decisão.

## [2026-08-31] TASK-003 · Apontamentos com disposição de rejeição ou adiamento

- **Rejeitado:** `2>/dev/null` no `openssl genpkey` de `scripts/gen_dev_key.sh`, sugerido pelo
  `quality-assurance` para calar os pontos de progresso em stderr. **Decisão do usuário:** o
  contrato do script exige não suprimir stderr, e o redirecionamento engoliria também a mensagem
  de erro real do `openssl` — trocaria ruído cosmético por cegueira em falha de verdade.
- **Adiado:** `CORS_ALLOWED_ORIGINS=` vazia pode ser lida como `['']` e não como `[]` pelo
  `env.list()`, dependendo da versão do `django-environ`. Não afeta o bloco A, onde o valor vazio é
  o correto. **Repassar ao bloco B**, que configura o middleware: uma allowlist contendo string
  vazia é uma origem inválida registrada, e o `CorsMiddleware` deixaria de ser inerte — que é
  exatamente a contrapartida exigida quando o usuário decidiu manter `django-cors-headers`.
- **Adiado:** a ADR 0005 não nomeia o cliente `redis` na lista de dependências com extensão em C da
  ADR 0001. Não é contradição — `redis` é Python puro —, mas aquela lista deixou de ser inventário
  completo do `requirements.txt`.
- **Aceito e resolvido nesta tarefa:** `*.pem` no `.dockerignore` (o `.gitignore` barrava do repo,
  o contexto de build não); a contradição do extra `oidc` no catálogo de riscos do passo 01, herdada
  do commit `1e8b060`; "oito pins" → "nove" em `docs/implementacao.md`; e "quatro causas candidatas"
  → três para o JWKS vazio, já que "extra faltando" deixou de ser candidata.
- **Tipo:** decisão.

---

**Regra ao acrescentar:** se a decisão tem ADR, escreva **uma linha** no índice e o resto
no ADR. Se não tem, escreva a entrada completa aqui. Um log que cresce sem poda não é
memória — é sedimento.

## [2026-08-31] TASK-004 · Bloco B implementado; os quatro apontamentos do `architect` fecham por verificação

- **Decisão:** os passos 04 e 05 foram executados como unidade única (commit `a89a776`). A
  tarefa ficou aberta em `context.json` porque um `/clear` cortou a rota antes do
  encerramento; os quatro apontamentos receberam disposição agora, contra o repositório real,
  não contra relatório.
- **Aceito e resolvido:** (1) o `[CRITICO]` da **janela SQLite** — `find` não encontra
  `*.sqlite3` em lugar nenhum da árvore, e `settings.DATABASES['default']` resolve para
  `django.db.backends.postgresql`/`nova_api`; a janela entre `startproject` e a settings
  definitiva fechou sem deixar banco órfão. (2) `config/asgi.py` **não existe** — a remoção
  que o passo 04 exigia foi feita. (3) `TIME_ZONE = "UTC"` está escrito literalmente
  (`config/settings.py:154`), então o `America/Chicago` do `global_settings` não foi herdado.
- **Observação registrada:** `makemigrations --dry-run` abre conexão com o Postgres e emite
  `RuntimeWarning` se ele estiver parado. Não é falha de gate — é ruído de diagnóstico, e
  saber disso evita confundi-lo com erro no bloco C.
- **Fecha também um adiado de TASK-003:** `CORS_ALLOWED_ORIGINS=` vazia no `.env` é lida como
  `[]` — **não** como `['']` — pelo `django-environ` desta versão. A contrapartida exigida
  quando o usuário decidiu manter `django-cors-headers` está cumprida: o `CorsMiddleware`
  é de fato inerte nesta fase.
- **ADR:** nenhuma. Conferência das sete ADRs de `docs/roadmap/13-adrs.md` contra os achados
  do bloco B: nenhuma contradição encontrada (o bloco não tocou em versão, extra, backend de
  cache nem transporte).
- **Tipo:** decisão.

## [2026-08-31] TASK-005 · Bloco C: o schema nasceu ancorado em `accounts.User`

- **Decisão:** o passo 06 foi executado e o gate fecha nos quatro critérios. O usuário rodou
  `makemigrations`, `migrate` e `createsuperuser` no terminal dele; o `writer` encontrou o
  estado pronto, obedeceu à regra de parada do pré-voo e **validou em vez de criar**, e o
  `quality-assurance` refez as dez verificações contra o ambiente. Commit `cf2ddde`.
- **O que ficou provado, e só este bloco prova:** o hasher da primeira senha do projeto é
  `argon2id` — é a **única confirmação empírica** que o `PASSWORD_HASHERS` do passo 04
  recebe em todo o roadmap. Se tivesse vindo `pbkdf2_sha256`, nenhum outro passo acusaria.
- **Tipo:** decisão.

## [2026-08-31] TASK-005 · O aceite do passo 07 é **9 FKs**, não 7 — e o passo 06 listava quatro tabelas de seis

- **Decisão:** `docs/roadmap/06-primeira-migration.md` enumerava as tabelas do
  django-oauth-toolkit que resolvem `AUTH_USER_MODEL` como `Application, AccessToken, Grant,
  IDToken`. São **seis**: faltavam `RefreshToken` (na própria `0001_initial`) e `DeviceGrant`
  (na `0013`). Verificado em `oauth2_provider/models.py` da 3.4.1 instalada — seis ocorrências
  de `settings.AUTH_USER_MODEL`, linhas 201, 520, 607, 761, 911 e 1015. Enumeração corrigida
  no passo 06.
- **O número a carimbar:** hoje há **3** FKs apontando para `accounts_user`
  (`django_admin_log`, `accounts_user_groups`, `accounts_user_user_permissions`). Depois do
  `migrate` do passo 07 devem ser **9**. Carimbar 7 — como esta rota chegou a fazer, antes da
  conferência — reprovaria um passo 07 correto.
- **Tipo:** decisão. **Validade:** vale para django-oauth-toolkit 3.4.1; outra versão pode ter
  outro conjunto de modelos.

## [2026-08-31] TASK-005 · O gate do passo 06 não mede o que pretende medir

- **Decisão:** o passo 06 manda procurar ativamente a tabela `auth_user` depois do primeiro
  `migrate`. `auth/migrations/0001_initial.py` cria o `User` com
  `options={"swappable": "AUTH_USER_MODEL"}`: com `AUTH_USER_MODEL` já nas settings
  commitadas, **`auth_user` não pode nascer em ordem nenhuma de comandos**. Pior, o erro que
  o passo teme — `migrate` antes da `0001` de `accounts` — falharia **ruidosamente**, na
  resolução da `swappable_dependency`, e não em silêncio. O check é verdadeiro e não pode
  falhar; um check que só passa não mede nada. Ele só teria valor para a variante *volume
  reaproveitado*, que o roadmap trata como risco secundário e é o risco vivo de verdade.
- **O que substitui:** cinco sinais independentes e estritamente mais fortes, todos colhidos
  neste bloco — (1) `min/max(applied)` em `django_migrations` numa janela de 79 ms, provando
  volume aplicado de uma vez; (2) `accounts.0001_initial` id 15 < `admin.0001_initial` id 16,
  provando a ordem realmente aplicada; (3) três FKs para `accounts_user`; (4) contenttype
  `accounts | user` sem `auth | user`; (5) permissões `add/change/delete/view_user` sob
  `app_label = accounts`. **Repassar aos blocos D a F**: quando um gate do roadmap indicar um
  sinal, conferir se ele é falsificável no estado em que o passo roda.
- **Texto do roadmap não alterado neste ponto** — a correção autorizada foi só a das duas
  imprecisões factuais. A divergência fica aqui.
- **Tipo:** decisão.

## [2026-08-31] TASK-005 · Apontamentos com disposição de rejeição ou adiamento

- **Rejeitado:** o `writer` supôs que a Fase 3 havia sido invocada duas vezes, ao encontrar o
  banco já migrado. Diagnóstico errado — o usuário executou a sequência no terminal dele às
  19:52–19:53, e o `createsuperuser` 23 segundos depois do `migrate`. Registro porque a
  suposição errada, se absorvida, viraria desconfiança do orquestrador em vez de um fato
  simples sobre quem executou o quê.
- **Rejeitado:** `conname` de `accounts_user_user_permissions` truncado em 63 caracteres não é
  defeito — é o limite de identificador do Postgres.
- **Adiado para o passo 11:** a criação **condicional** de superusuário no entrypoint tem de
  tolerar conta já existente. Com `teste@teste.com` no banco, `createsuperuser --noinput`
  termina em `CommandError: That email address is already taken.` e código 1; com `set -e`, o
  container não sobe, e a mensagem não menciona superusuário. A dívida nasceu aqui e vence lá.
  Neste bloco o risco não se materializou porque o usuário rodou o comando interativo, e as
  variáveis `DJANGO_SUPERUSER_*` seguem comentadas no `.env`.
- **Adiado:** não há `AUTH_PASSWORD_VALIDATORS` nas settings — o passo 04 não os exige, então
  não é divergência. Consequência real: **nenhuma restrição de força de senha valeu sobre a
  primeira conta administrativa do IdP**, e não valerá sobre nenhuma outra até que alguém os
  acrescente.
- **Adiado:** não há suíte de testes, conforme `docs/roadmap/12-readme.md:112` ("Nenhum teste
  automatizado nesta fase"). O único ponto deste bloco com decisão própria a cobrir, quando a
  fase de teste chegar, é `UserManager.create_user` (`accounts/models.py:10-11`, o `ValueError`
  com e-mail vazio) — unitário. O resto é herança de `AbstractUser`, sem decisão.
- **Observação, para não virar depuração inútil:** `runserver` com `DEBUG=False` e sem
  WhiteNoise não serve estático — `/admin/` renderiza sem CSS até o passo 09. Confirmado na
  prática: o login funcionou assim.
- **Aceito e resolvido nesta tarefa:** as duas imprecisões factuais do passo 06 (a oração sobre
  `contenttypes` referenciar por FK, e a enumeração incompleta do DOT) e a mesma oração na
  ADR 0003 de `docs/roadmap/13-adrs.md`.
- **Tipo:** decisão.

## [2026-08-31] TASK-005 · A conferência das sete ADRs, terceiro bloco: uma falsificada

- **Decisão:** cumprindo o adiado de TASK-003 — que pedia a quem fechasse B, C, D, E e F que
  repetisse a conferência —, o bloco C encontrou **uma** contradição: a ADR 0003 afirmava que
  `contenttypes` referencia `AUTH_USER_MODEL` por chave estrangeira. Não referencia; grava o
  tipo do modelo, e a verificação de FKs deste bloco é a prova. Corrigida no texto ainda não
  gravado, com autorização do usuário. **Tally acumulado: 2,5 ADRs falsificadas em três
  blocos** (0002 e 0005 no bloco A, 0003 aqui), com a gravação prevista para o passo 13.
  O bloco B não contradisse nenhuma.
- **A conferência continua não sendo gate de bloco nenhum** — segue dependendo de alguém
  lembrar. Repassar a D, E e F.
- **Tipo:** decisão.
