# Registro de Decisões — histórico arquivado

> As entradas das tarefas encerradas, retiradas de `.claude/memory/decisions.md` quando ele
> passou de 900 linhas. **Nada aqui é regra viva:** é o registro do que foi decidido e por quê,
> na data em que foi. O conteúdo é idêntico ao que estava no arquivo principal, na mesma ordem.
>
> O arquivo principal guarda o índice das ADRs (Architecture Decision Records) e as entradas da
> última tarefa encerrada em diante. Quem procura uma decisão recente não precisa abrir este
> arquivo; quem investiga uma decisão antiga abre, e lê da TASK-001 à TASK-009.
>
> **A poda:** quando `decisions.md` passar de 300 linhas, as entradas de todas as tarefas
> encerradas, menos as da última, vêm para cá — no fim do arquivo, preservando a ordem. Quem
> move é o orquestrador, no encerramento de uma tarefa. O formato de entrada é o do arquivo
> principal.

---

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

---

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

---

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

---

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

---

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

---

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

---

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

---

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

---

## [2026-08-31] TASK-003 · Bloco A implementado: os quatro gates fecham

- **Decisão:** os passos 01, 02 e 03 foram executados como unidade única, pela rota `/scaffold`.
  Produto: `requirements.txt`, `.env.example`, `.env`, `.dockerignore`, `docker-compose.yml`,
  `scripts/gen_dev_key.sh` e o venv 3.14.6. O `quality-assurance` verificou os quatro gates
  contra o ambiente real, executando — não relendo relatório.
- **ADR:** nenhuma gravada. As sete de fundação seguem em `docs/roadmap/13-adrs.md`, para o
  bloco G. Ver a entrada específica sobre duas delas, abaixo.
- **Tipo:** decisão.

---

## [2026-08-31] TASK-003 · O pacote `redis` faltava no requirements, e o sinal seria três blocos adiante

- **Decisão:** o passo 04 configura `CACHES` com `django.core.cache.backends.redis.RedisCache`,
  que importa o cliente PyPI `redis`; ele não é transitiva de nenhuma das oito linhas originais.
  Sem a nona linha, o sinal seria `ModuleNotFoundError` no bloco E. **O usuário decidiu acrescentar
  `redis==8.1.0`** — verificado no PyPI: `requires_python >=3.10`, classifier para 3.14, Python
  puro. Mesma classe da correção do extra `[oidc]` em TASK-002: conferência do que o roadmap
  pressupõe contra a metadata real. `docs/roadmap/01-...md` foi corrigido junto.
- **Tipo:** decisão.

---

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

---

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

---

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

---

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

---

## [2026-08-31] TASK-003 · Portas publicadas só em `127.0.0.1`

- **Decisão:** as publicações do compose não tinham endereço, então o Docker fazia bind em
  `0.0.0.0` **e instalava DNAT à frente do firewall do host** — um UFW configurado não fechava a
  porta, e o Redis sobe sem `requirepass`, sendo onde a sessão SSO vai viver a partir do passo 04.
  Prefixadas com `127.0.0.1:`, preservando variáveis e defaults. Reverificado com os containers
  recriados: `ss -ltn` mostra `127.0.0.1:5433` e `127.0.0.1:6379`, e ambos respondem do host.
  Acesso de outra máquina da rede deixa de funcionar **por desenho**.
- **Tipo:** decisão.

---

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

---

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

---

## [2026-08-31] TASK-005 · Bloco C: o schema nasceu ancorado em `accounts.User`

- **Decisão:** o passo 06 foi executado e o gate fecha nos quatro critérios. O usuário rodou
  `makemigrations`, `migrate` e `createsuperuser` no terminal dele; o `writer` encontrou o
  estado pronto, obedeceu à regra de parada do pré-voo e **validou em vez de criar**, e o
  `quality-assurance` refez as dez verificações contra o ambiente. Commit `cf2ddde`.
- **O que ficou provado, e só este bloco prova:** o hasher da primeira senha do projeto é
  `argon2id` — é a **única confirmação empírica** que o `PASSWORD_HASHERS` do passo 04
  recebe em todo o roadmap. Se tivesse vindo `pbkdf2_sha256`, nenhum outro passo acusaria.
- **Tipo:** decisão.

---

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

---

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

---

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

---

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

---

## [2026-09-01] TASK-006 · Bloco D: servidor OAuth2/OIDC e validador de claims

- **Decisão:** os passos 07 e 08 fecharam em dois gates e dois commits (`d742dc3`, `a6b424d`),
  como `docs/implementacao.md` prescreve. Três pontos que o roadmap não decide foram resolvidos
  pelo `architect` e implementados: a chave RSA **reusa a variável de módulo** de
  `config/settings.py` em vez de reler o ambiente (uma segunda leitura é um segundo lugar para
  errar o `multiline=True`); `OIDC_RP_INITIATED_LOGOUT_ENABLED: False` entrou declarada **além
  das cinco chaves que o passo 07 enumera**, autorizada pelo usuário, porque a biblioteca
  documenta flips de default programados para a 4.0 e um flip publicaria `end_session_endpoint`
  sem uma linha de log; e `get_additional_claims` ficou na **forma agnóstica ao request** (um
  parâmetro, valores callables), porque só nessa forma o DOT soma as claims a
  `claims_supported` — na forma de dois parâmetros a discovery anunciaria `["sub"]` enquanto o
  servidor emite `sub`, `name` e `email`, sem reprovar AC nenhum.
- **Issuer confirmado:** `http://localhost:8000/o`, confirmado pelo usuário **duas vezes**,
  ciente de que a janela fecha na primeira relying party integrada e não no fim do roadmap.
  Fecha o `CRITICO` do `product-manager` que apontava a ausência desse registro. Ver o adiado
  sobre `sub` abaixo — o cerimonial cobriu chave e issuer e deixou o terceiro componente de fora.
- **AC-05 reescrito antes de ser verificado:** a redação original ("`/applications/` na raiz
  responde 404") era **verdadeira por construção** e não podia falhar, porque `config/urls.py`
  nunca monta nada do DOT na raiz. Mesmo defeito que a TASK-005 diagnosticou no gate do passo
  06, e que aquela tarefa pediu que os blocos D–F vigiassem. Substituído, com autorização, por
  três sinais que discriminam: `/o/applications/` em 302, um único `include` com prefixo `o/`,
  e `/o/logout/` em 404 **com** `end_session_endpoint` ausente da discovery.
- **Tipo:** decisão.

---

## [2026-09-01] TASK-006 · PKCE aceitava `plain`: o código contradizia o próprio comentário

- **Decisão:** o `quality-assurance` achou, e o orquestrador reproduziu, que
  `code_challenge_method=plain` fechava o fluxo inteiro — `code` emitido, `/o/token/` 200,
  `id_token` RS256 na mão. Com `plain` o `code_challenge` que trafega na URL de autorização **é**
  o `code_verifier`, então quem observa o pedido resgata o `code` — exatamente o ataque que o
  comentário de `PKCE_REQUIRED` afirmava prevenir desde o passo 07. Corrigido em `5aa4427` com
  `COMPLIANT_BCP_RFC9700_PKCE_METHOD: True`, autorizado pelo usuário. **Nenhum passo do roadmap
  pede essa chave**: entra pelo mesmo argumento que trouxe `OIDC_RP_INITIATED_LOGOUT_ENABLED` —
  um default não é um compromisso. `code_challenge_methods_supported` passou de
  `["plain","S256"]` para `["S256"]`.
- **Lição que sobrevive à tarefa:** `PKCE_REQUIRED` exige PKCE, **não restringe o método**. Um
  comentário afirmando uma proteção não é a proteção, e essa distância durou dois commits sem
  que ninguém a visse — o `check --deploy` já a nomeava em `W003` o tempo todo.
- **Tipo:** decisão.

---

## [2026-09-01] TASK-006 · A primeira suíte do projeto, verificada por mutação

- **Decisão:** o `ESCOPO` da tarefa punha testes automatizados fora desta fase, e o usuário
  **decidiu executá-los mesmo assim**. Cinco demandas do `quality-assurance`, uma por falha
  silenciosa do bloco, em `accounts/tests/` (commit `c6abaee`): 17 testes no runner nativo, sem
  dependência nova. A justificativa que decidiu: as cinco falhas deixam `manage.py check` verde,
  logo teste é o único sinal possível para elas.
- **A asserção que importa é T-04(v):** o conjunto de claims de identidade do `id_token` tem de
  ser **igual** ao `claims_supported` da discovery. É a única guarda contra a troca de aridade de
  `get_additional_claims`, que deixa o `id_token` correto e faz a discovery subdeclarar em
  silêncio. Nenhuma peça isolada percebe; só comparar os dois lados pega.
- **Suíte verificada por mutação, não por rodar verde** — pelo orquestrador e, de forma
  independente, pelo `quality-assurance` na segunda passagem: remover
  `COMPLIANT_BCP_RFC9700_PKCE_METHOD` deixa exatamente T-05(v) vermelho; `PKCE_REQUIRED=False`
  deixa exatamente T-05(i); trocar a aridade deixa exatamente T-04(v). Teste que nunca fica
  vermelho não é sinal, e esta suíte fica.
- **Tipo:** decisão.

---

## [2026-09-01] TASK-006 · O catálogo de falhas silenciosas estava invertido

- **Decisão:** o `senso-critico` apontou e o orquestrador confirmou nos dois ramos, com settings
  de mutação contra o servidor real, que o diagnóstico do JWKS vazio estava **ao contrário** —
  em `config/settings.py`, no docstring de `accounts/tests/test_jwks.py` e no próprio
  `docs/roadmap/07-servidor-oauth2-oidc.md:92-94`:

  | causa | sinal real | natureza |
  | --- | --- | --- |
  | chave **ausente** (string vazia) | `{"keys": []}`, e `id_token_signing_alg_values_supported` cai de `["RS256","HS256"]` para `["HS256"]`; **os quatro endpoints seguem listados** | **silenciosa** |
  | PEM **malformado** (`\n` literais) | `ValueError` em `jwcrypto/jwk.py:1140` → 500 em `/o/.well-known/jwks.json` e em `/o/token/`, logado por `django.request` | **ruidosa** |

  Os comentários do código atribuíam a falha silenciosa ao caso ruidoso. Corrigidos nesta tarefa.
- **Divergência do roadmap, anotada e não ajustada** (`docs/implementacao.md` §4): o passo 07
  afirma que sem a chave "a discovery omite os endpoints de token". **Não omite** —
  `ConnectDiscoveryInfoView` (`views/oidc.py:73-76`) monta os quatro com `required=True`,
  incondicionalmente. Consequência que importa para quem executar os blocos seguintes: **o gate
  do passo 07 "a discovery lista os endpoints de authorize, token, userinfo e jwks" é verdadeiro
  por construção**, com chave ou sem — mesma classe do AC-05. O sinal falsificável é o `alg`.
  O passo 12 escreve o README a partir do texto do passo 07 e congelaria a versão errada.
- **Tipo:** decisão.

---

## [2026-09-01] TASK-006 · Adiados do gate adversarial, com evidência e horizonte

Três apontamentos `CRITICO` do `senso-critico`, todos **verificados** pelo orquestrador e
nenhum deles defeito do que o Bloco D implementou — são defaults do DOT e decisões herdadas.
Adiados por isso, não por conveniência.

- **Desativar uma pessoa não desliga os tokens dela.** Verificado empiricamente: com
  `is_active=False`, o `refresh_token` ainda troca por `access_token` novo, `id_token` novo com
  `name` e `email`, e `/o/userinfo/` responde 200. A string `is_active` **não ocorre uma única
  vez** no pacote `oauth2_provider` 3.4.1. Agravante: `REFRESH_TOKEN_EXPIRE_SECONDS` é `None`
  por default, então o refresh **nunca expira** e `clear_expired()` nunca o coleta.
  `docs/roadmap/12-readme.md:102-104` arquiva `cleartokens` sem agendamento como problema de
  **crescimento de tabela** — a caracterização não alcança este caso. **Horizonte:** primeira RP
  integrada mais o primeiro desligamento de pessoa. A janela de registro barato é agora, porque
  o texto do passo 12 é escrito no bloco F.
- **O par `(iss, sub)` é reciclado pelo reset que o próprio projeto prescreve.** `sub` é
  `str(user.pk)`; `docker compose down -v` (nomeado em `docs/implementacao.md:47`) derruba o
  volume, e `migrate` + `createsuperuser` recriam `id=1`. Com o `iss` fixado como permanente,
  uma **pessoa diferente** passa a receber o par `("http://localhost:8000/o", "1")` — que a OIDC
  Core §5.7 manda a RP usar como chave de identidade. O cerimonial de irreversibilidade foi
  montado para a chave RSA e para o issuer e **nunca estendido ao terceiro componente do
  contrato**. **Horizonte:** primeiro `down -v` depois da primeira integração; a mitigação é uma
  decisão registrada agora e uma migration numa fase futura.
- **Duas das sete ADRs contêm afirmações que este bloco falsificou.** A **ADR 0002**
  (`13-adrs.md:213-214`) lista "introspecção" entre as capacidades que justificam a escolha do
  DOT — e o bloco `SCOPES` deste passo removeu o scope `introspection`, de modo que
  `/o/introspect/` segue anunciado na metadata RFC 8414 e responde 403. A **ADR 0007**
  (`13-adrs.md:677-680`) registra o 404 da RFC 8414 na raiz como consequência **inevitável** do
  prefixo; não é inevitável — `oauth2_provider/urls.py:107-114` documenta e exporta
  `metadata_urlpatterns` para montagem separada na raiz, e compor entre listas que a biblioteca
  exporta não é reescrever view nem path. Isto também **reformula o RISCO ESTRUTURAL 1 do
  `architect`**: a equação "montar `urlpatterns` seletivamente = reescrever rotas do DOT" é
  falsa, e com ela cai a conclusão de que o inventário sob `/o/` é irremovível por construção.
  **Horizonte: o Bloco G**, que grava as sete como imutáveis. Hoje custa duas frases no texto não
  gravado; depois de G, custa uma ADR 0008 e uma 0009. **Ajustado em 2026-09-01**, com
  autorização explícita do usuário e pelo precedente da TASK-005: a ADR 0002 perdeu
  "introspecção" da lista de capacidades prontas e ganhou, nas Negativas, o registro de que a
  view exige o scope `introspection`, que o bloco `SCOPES` não declara — nenhum token pode
  carregá-lo, e `/o/introspect/` segue anunciado e responde 403; a ADR 0007 passou a atribuir o
  404 à montagem atual, não ao prefixo, e ganhou a alternativa que faltava. Com isso o **RISCO
  ESTRUTURAL 1 não sobrevive afirmado em lugar nenhum**: fora deste arquivo, `RISCO ESTRUTURAL`
  só ocorre como rótulo de formato em `.claude/agents/architect.md:101` e
  `.claude/commands/scaffold.md:33`.

- **Tally das sete ADRs, quarto bloco: passa a 3,5 de 7 falsificadas** (0002 e 0005 no bloco A,
  0003 no C, 0002 de novo e 0007 aqui). O tally é histórico e não regride com a correção: as
  duas deste bloco foram corrigidas no texto não gravado, as três dos blocos anteriores não.
  **A conferência continua não sendo gate de bloco nenhum** — segue dependendo de alguém
  lembrar. Repassar a E, F e, sobretudo, a G.
- **Tipo:** decisão.

---

## [2026-09-01] TASK-007 · Disposições da Fase 3 (bloco E)

Duas disposições do usuário no gate de pré-alteração, antes de qualquer escrita.

- **[CRITICO] do `architect` — ACEITO.** Divergência deliberada com `docs/roadmap/09-telas-e-estaticos.md`:
  o backend de estáticos prescrito (`CompressedManifestStaticFilesStorage`) acopla a renderização de
  template a artefato de build e derruba sete dos 17 casos da suíte do bloco D — os que renderizam
  `/o/authorize/` e exigem 200. Mecanismo verificado no código pelo `architect`:
  `ManifestStaticFilesStorage.stored_name` consulta `staticfiles.json` e levanta
  `ValueError: Missing staticfiles manifest entry` durante a renderização. **Adotado
  `whitenoise.storage.CompressedStaticFilesStorage`** — compressão sim, manifesto não. `collectstatic`
  continua obrigatório para subir a aplicação; deixa de ser obrigatório para a suíte passar.
  Descartado o atalho `WHITENOISE_MANIFEST_STRICT = False`: mantém o custo e troca uma falha ruidosa
  (404 no recurso) por uma silenciosa (hash antigo servido sem aviso).
  **O roadmap passa a divergir do código neste ponto**, conforme `docs/implementacao.md` §4, que manda
  registrar em vez de absorver. O passo 12 escreve o README a partir do texto do passo 09 e
  congelaria a versão errada.
- **[OBSERVACAO] `LOGIN_URL` — ACEITA a forma do `architect`.** O passo 09 prescreve "resolvida por
  `reverse`" dentro das settings; a forma não se sustenta, porque `settings.py` é lido antes do
  URLConf. Adotado `LOGIN_URL = "login"` (e `LOGIN_REDIRECT_URL`/`LOGOUT_REDIRECT_URL` = `"home"`),
  resolvidos por `django.shortcuts.resolve_url` em runtime. A intenção do roadmap — acoplar pelo nome
  da rota, não pela string do path — é cumprida; a letra, não. Rota renomeada segue produzindo
  `NoReverseMatch`, falha ruidosa.
- **ADRs 0008 e 0009 — ADIADAS ao bloco G.** Redigidas pelo `architect` na Fase 2, não gravadas em
  `docs/adr/` nesta tarefa por decisão do usuário. Os textos íntegros ficam abaixo: são a única cópia
  durável, e o bloco G transcreve daqui. Numeração 0008/0009 porque 0001–0007 estão reservadas aos
  sete textos de fundação em `docs/roadmap/13-adrs.md`.
- **Tipo:** decisão.

> **Podados em 2026-09-02 (TASK-010).** Os textos integrais das ADRs 0008 e 0009 viviam aqui
> porque eram a única cópia durável. O bloco G gravou os arquivos em `docs/adr/`, que passam
> a ser a fonte — e, no caso da 0009, com emendas posteriores a este texto. Ver o índice no
> topo deste arquivo.

---

## [2026-09-01] TASK-007 · Bloco E implementado; disposição dos apontamentos das seis fases

Rota `/feature` completa: product-manager → architect → gate de pré-alteração → writer →
quality-assurance (2 passagens) → tester (2 rodadas) → gate adversarial. Passos 09 e 10 do
roadmap. 13 critérios de aceite, todos atendidos e verificados contra código em execução —
inclusive o AC-11, com `docker compose stop redis` de verdade. Suíte: 17 → **30 casos, verde**.

### Divergências deliberadas com o roadmap — registradas porque o passo 12 escreve o README a partir dele

- **Backend de estáticos sem manifesto** e **`LOGIN_URL` por nome de rota**: ver a entrada
  "TASK-007 · Disposições da Fase 3", acima.
- **O form de logout mora no header de `templates/base.html`, não em `templates/home.html`**
  como o passo 09 prescreve. Razão verificada pelo `quality-assurance`: `authorize.html` abre
  um `<form>` em torno de todo o conteúdo, então o logout dentro do bloco de conteúdo produziria
  **form aninhado** — HTML não tem isso, e o navegador desfaz o aninhamento de um jeito que o
  POST de consentimento não sobrevive. No header, os dois formulários ficam **irmãos**. A tela
  de consentimento foi conferida com exatamente 2 forms irmãos.

### Correção de produção fora do escopo original, autorizada pelo usuário

- **`CACHES["default"]` ganhou `OPTIONS` com `socket_connect_timeout=2` e `socket_timeout=2`.**
  O gate adversarial apontou que, sem eles, um Redis que **aceita a conexão e não responde**
  (`docker compose pause`, pressão de memória, firewall DROP) não produzia 503 — distinto da
  recusa de conexão, que já funcionava e é o único modo que o AC-11 e a T-09 exercitam.
  **O `writer` corrigiu o diagnóstico com medição**: `redis==8.1.0` define
  `DEFAULT_SOCKET_TIMEOUT = 5` em `redis/_defaults.py`, então não havia bloqueio infinito e sim
  bloqueio implícito de **5,03s** (medido) — acima da janela de `timeout: 3s` do healthcheck.
  Bug real, severidade menor que a descrita, e dependente de um pin que `pip install -U` muda
  sem aviso. Os 2s têm teto (a janela de 3s do compose) e piso (o `cached_db`, que toca o cache
  a cada request, com round-trip local na casa do milissegundo). `retry_on_timeout` descartado:
  só entraria em cena após 2s de silêncio e dobraria o tempo até o 503, estourando a janela que
  o valor foi escolhido para caber. Correção **observada**: 503 em 2,02s com o Redis pausado,
  com `redis.exceptions.TimeoutError` logado pela view, e 200 em 0,009s após o unpause.

### Aceitos e resolvidos nesta tarefa

- **Acomodação na T-10 desfeita (T-11).** A classe declarava `databases = {"default"}` para
  contornar a colisão entre o `patch.object` sobre o `ConnectionProxy` e o bloqueador de banco
  do `SimpleTestCase`. O diagnóstico do `tester` estava certo, a causa não: o problema era o
  **alvo** do patch. Trocado para `patch("config.views.connection")` — o nome que a view usa —
  e o `databases` removido. O bloqueador volta armado: query real futura no caminho do `health`
  falha ruidosamente em vez de escrever no banco de teste sem rollback.
- **Traceback em suíte verde eliminado (T-12).** Os dois casos de falha do `/health` passaram a
  envelopar a chamada em `assertLogs("config.views", level="ERROR")`. Além de calar o ruído que
  treina quem lê a saída a ignorar traceback, isso **assere o contrato de log** que o docstring
  da view declara: remover qualquer um dos dois `logger.exception` agora derruba o teste
  correspondente — verificado por mutação restaurada.
- **Colisão de namespace `T-NN`.** `T-01` a `T-05` designavam dois testes cada: os do bloco D
  (TASK-006) e os do bloco E. Como esta entrada e a da TASK-006 citam números — "remover
  `COMPLIANT_BCP_RFC9700_PKCE_METHOD` deixa exatamente T-05(v) vermelho" —, quem fosse conferir
  abriria o arquivo errado e concluiria que a memória mente. **Só os testes desta tarefa foram
  qualificados** (`TASK-007/T-NN`); os do bloco D ficaram intocados, de modo que todas as
  citações já gravadas seguem válidas sem edição. **Regra para as próximas tarefas: `T-NN` é
  cunhado por tarefa e não é único no repositório — qualifique ao citar fora da tarefa que o
  cunhou.**
- **Dois apontamentos da Fase 5 fecharam por verificação**, não por decisão: o `/static/` sem
  documentação e o CSS sem nome versionado já estavam absorvidos pela ADR 0008.

### Adiados, com horizonte nomeado

- **[CRITICO] `SECURE_SSL_REDIRECT` intercepta `/health` com `BEHIND_TLS_PROXY=True`.** A probe
  interna, sem `X-Forwarded-Proto`, recebe 301 para `https://` e falha no handshake contra um
  gunicorn em texto claro: container eternamente unhealthy, `docker compose up --wait` que não
  retorna, com a aplicação atendendo normalmente pelo proxy. O passo 11 cataloga duas causas de
  "unhealthy eterno" (curl em imagem slim, `ALLOWED_HOSTS`) e **não tem esta**. O sinal existe
  antes, mas engana: ligar a variável deixa a suíte vermelha por 301, o que se lê como ".env
  quebrou os testes". **Horizonte: bloco F.** Adiado porque o consumidor — o `HEALTHCHECK` — só
  existe no passo 11, e a isenção é decisão de segurança que merece o `architect`.
- **[MEDIO] O `/health` não tem teto próprio de tempo.** Banco e cache degradando juntos somam o
  timeout do Postgres aos 2s do cache. **Horizonte: bloco F**, cujo `HEALTHCHECK` precisa
  acomodar a soma ou vai expirar por fora em vez de ler o 503.
- **[OBSERVACAO] A suíte não tem caminho até a entrega do estático.** Remover ou reordenar o
  `WhiteNoiseMiddleware` deixa 30/30 verde com a tela de credencial sem CSS — que o passo 09
  chama de "tela que ninguém confia". `finders.find` prova que o fonte existe; `{% static %}`
  virou concatenação e não toca `STATIC_ROOT`; nenhum caso faz GET em `/static/`. O adversarial
  observa que a decisão do manifesto **não deslocou o acoplamento, removeu a janela de
  observação junto com o custo**. Adiado: fechar exigiria `collectstatic` dentro da suíte, que é
  exatamente o que a ADR 0008 rejeita. **Horizonte: primeira edição do `MIDDLEWARE`, ou o passo
  11 quando o entrypoint assumir a coleta.**
- **[OBSERVACAO] `{{ application.name }}` é a única identificação de quem pede consentimento e
  nenhum teste a asserta.** Uma edição do `<h1>` produz "Autorizar ?", a pessoa autoriza sem
  saber a quem, e a suíte segue verde porque o `code` continua saindo. É a única informação da
  tela sem a qual consentimento deixa de ser consentimento. **Horizonte: qualquer edição do
  template.**
- **[OBSERVACAO] O override congela a forma do `authorize.html` da 3.4.1 e nada compara com o
  upstream.** Campo **oculto** novo passa pelo laço; campo **visível** novo — consentimento
  granular por scope é o caso óbvio — desaparece em silêncio. **Horizonte: primeiro major do
  DOT.**
- **[OBSERVACAO] Teste do novo comportamento de timeout.** Exigiria um socket TCP que aceita e
  nunca responde, num thread. Disposição do orquestrador: **adiado por custo de manutenção
  desproporcional num sandbox**; a técnica está registrada aqui caso o bloco F o exija.
- **[OBSERVACAO] Mensagem de credencial inválida em inglês** numa tela em português (string do
  `AuthenticationForm` sob `LANGUAGE_CODE="en-us"`). Corrigir exige `LANGUAGE_CODE="pt-br"` ou
  `error_messages` próprio — decisão fora do escopo do bloco E. A T-03 foi escrita para **não**
  travar quando isso for corrigido: assere por classe CSS e por `form.errors`, nunca pelo texto.
- **[OBSERVACAO] Campo de e-mail renderiza `<input type="text">`** — widget do `username` do
  `AuthenticationForm`. Sem efeito sobre autenticação.
- **[OBSERVACAO] `{{ form.errors }}` + `{{ form.non_field_errors }}` duplicam o erro
  não-vinculado** no consentimento, e **"Recusar" vem antes de "Autorizar", então `Enter`
  recusa**. Ambos vêm do template original do DOT e foram preservados por fidelidade estrutural.
  A T-07 não congela a ordem: uma correção futura não quebra teste.
- **[OBSERVACAO] Banco de dev acumula 12 `AccessToken`, 13 `IDToken` e 13 `RefreshToken`.** O
  rollback por `transaction.savepoint()` sob `manage.py shell` **não funciona** — roda em
  autocommit e é inerte. Verificação manual contra o banco de dev **persiste tokens**; a leitura
  "nada persistido" é falsa. Some com `docker compose down -v`, que por sua vez recicla o par
  `(iss, sub)` — ver TASK-006.
- **[OBSERVACAO] Se o healthcheck do passo 11 fizer `grep` no corpo do `/health`**, espaçamento
  e ordem viram contrato sem guarda. A saída ali deve ser o **código HTTP** (200 vs 503), que os
  testes guardam.
- **[OBSERVACAO] Nenhum documento do repositório registra o comando da suíte.** `manage.py test
  accounts` roda 27 dos 30; o comando correto é `.venv/bin/python manage.py test`. **Horizonte:
  passo 12.** Também não está documentado que `/static/` só responde após `collectstatic`, nem
  que editar CSS exige `collectstatic` **e** reiniciar o runserver (o WhiteNoise monta o índice
  no boot; `autorefresh` segue `DEBUG`).

### Rejeitados, com justificativa

- **Teste de open-redirect via `next`.** `config/urls.py` usa `LoginView` de estoque, sem
  subclasse e sem `success_url_allowed_hosts`; a rejeição de `next` externo é do
  `RedirectURLMixin` via `url_has_allowed_host_and_scheme`. Um teste aqui fixaria comportamento
  do framework — cerimônia sob o `CLAUDE.md` deste repositório. **Passa a ser demanda no dia em
  que alguém subclassar `LoginView` ou mexer em `success_url_allowed_hosts`.**
- **Premissa da porta 6399 na T-09.** Se um serviço a ocupar e responder Redis, a sonda passa, o
  corpo sai `ok` e o `assertEqual(503)` **falha**. Fragilidade de ambiente real, mas o modo de
  falha é o seguro. Sem demanda.
- **"Alguém lê `request.user` no `/health`" como regressão que a T-09 deveria pegar.** O
  adversarial descartou com verificação: sem cookie de sessão, `session_key` é None e o
  `SessionStore` não faz I/O nenhum — nem `request.user`, nem `render()`, nem os context
  processors alcançam o Redis. A probe do container nunca envia cookie. **A frase das Negativas
  da ADR 0009 ("uma leitura de `request.user` reintroduz o 500 opaco") é mais larga que o
  mecanismo** — a estreitar antes do bloco G. O que a T-09 de fato pega: `@login_required`
  (viraria 302) e qualquer **escrita** de sessão, inclusive `messages` (viraria 500).

### Correção de um erro do orquestrador

Registrei em `context.json` uma nota afirmando que `decisions.md` estava desatualizado sobre as
edições em `docs/roadmap/13-adrs.md`. **Estava errado**: a entrada da TASK-006 registra "Ajustado
em 2026-09-01, com autorização explícita do usuário" e descreve as duas correções uma a uma. Li
aquela seção por `tail` truncado e concluí do trecho cortado. O gate adversarial pegou a
inversão. **O fato real, que permanece: as edições de `13-adrs.md` estão no disco e fora do
histórico do git.** `docs/implementacao.md` §2 nomeia `git checkout`/`clean` como recurso quando
um passo deixa lixo na árvore — aplicado aqui, descarta as correções, este arquivo segue
afirmando que foram aplicadas, e o bloco G transcreve as ADRs 0002 e 0007 falsificadas, agora
imutáveis. **Não faz parte do bloco E e não entra nos commits dele.**

### Sobre as ADRs 0008 e 0009

Seguem **adiadas ao bloco G** por decisão do usuário, reafirmada depois de o gate adversarial
argumentar que adiá-las as põe depois do único bloco capaz de falsificá-las. O texto integral
está acima, protegido por um aviso de não-poda. **Três frases da 0009 estão expostas ao bloco F**
e devem ser conferidas antes da gravação: a da causa que "sobrevive no log" (o timeout, agora
corrigido, mas a frase pressupõe que sempre houve timeout), a do "endpoint responde a quem chega
sem sessão e sem token" (falsa com `BEHIND_TLS_PROXY=True`), e a do "health verde significa
capaz de atender" (`SELECT 1` prova conectividade, não capacidade — migration pendente passa por
saudável). A **ADR 0008** tem uma incoerência interna: descarta `WHITENOISE_MANIFEST_STRICT` por
"trocar falha ruidosa por silenciosa" e adota opção que faz a mesma troca na jornada de
construção. A decisão continua defensável; o texto avalia o mesmo fato com sinais opostos em dois
parágrafos. Vale uma frase antes de virar imutável.

**Tally das sete ADRs, quinto bloco: segue em 3,5 de 7 falsificadas** — o bloco E não falsificou
nenhuma das sete. **A conferência continua não sendo gate de bloco nenhum.** Repassar a F e,
sobretudo, a G.

- **Tipo:** decisão.

---

## [2026-09-01] TASK-008 — o gate visual do passo 09 pegou comentário vazando nas telas

`{# ... #}` no Django é comentário **de uma linha só** — multi-linha não vira token e o texto sai
renderizado como conteúdo. Dos seis comentários dos templates, **cinco vazavam** (dois de
`base.html`, três de `login.html`): a tela de login servia quatro blocos de comentário de
implementação acima do campo de senha. O sexto, no topo de `authorize.html`, é **latente** — fora de
`{% block %}` num template que faz `{% extends %}`, o `ExtendsNode` descarta literal ali. Era
exibição, nunca execução: nenhum comentário continha `{{ }}` ou `{% %}`, logo não houve superfície de
injeção. Corrigido com `{% comment %}`, texto preservado palavra por palavra.

**Nenhum mecanismo automático via isso**: os testes asseram campo, classe CSS e código HTTP, nunca
que o corpo está livre de fonte vazado, e `check` não olha corpo de template. Justificativa
retroativa do gate visual, adiado cinco vezes ao custo de um bloco. Guarda em
`accounts/tests/test_template_comment_leak.py` (TASK-008/T-01), que assere pela **ausência dos
delimitadores**, nunca pelo texto; mordida observada restaurando os templates do `HEAD`. Suíte 30→33.

**A parte estética do gate continua sem passar** — a extensão do Chrome não conectou e nenhum olho
humano viu as telas. **Regra que fica:** docstring de teste não cita número de linha de template.

- **Tipo:** decisão.

---

## [2026-09-01] TASK-009 · Disposições do gate de pré-alteração (bloco F)

Quatro disposições do usuário antes de qualquer escrita.

- **Escopo — AUTORIZADOS OS CINCO ARQUIVOS.** O passo 11 declara três (`Dockerfile`,
  `docker/entrypoint.sh`, `docker-compose.yml`); entram também `config/settings.py` (duas linhas) e
  `README.md` (passo 12). As duas linhas de settings são o que torna o `HEALTHCHECK` honesto: sem
  elas o container nasce com o defeito que este gate encontrou.
- **Porta publicada — `127.0.0.1:8000:8000`, divergindo do passo 11**, que prescreve `8000:8000`.
  Publicação sem endereço instala DNAT à frente do firewall do host, e o que fica exposto aqui é um
  formulário de senha em HTTP claro com `BEHIND_TLS_PROXY=False`. É o mesmo argumento que a TASK-003
  já aceitou para Postgres e Redis, e aqui ele é mais forte, não mais fraco. Custo aceito: outra
  máquina da rede não alcança o IdP. O README congela esta forma.
- **ADRs 0010 e 0011 — ADIADAS ao bloco G**, como 0008 e 0009. Os textos íntegros ficam abaixo e são
  a única cópia durável. `docs/adr/` passa a ser preenchido de uma vez, em ordem, no bloco G.
- **[CRITICO] da guarda automática — ACEITO, com desvio de rota.** `/scaffold` não tem fase de
  `tester`; uma é acrescentada. Sem ela, remover `SECURE_REDIRECT_EXEMPT` deixa a suíte verde, e a
  correção mais importante do bloco ficaria sustentada só por disciplina — que é exatamente o que a
  TASK-006 encontrou mentindo no comentário do PKCE.
- **Tipo:** decisão.

> **Podados em 2026-09-02 (TASK-010).** Os textos integrais das ADRs 0010 e 0011 viviam aqui
> porque eram a única cópia durável. O bloco G gravou os arquivos em `docs/adr/`, que passam
> a ser a fonte — e, no caso da 0011, com emendas posteriores a este texto. Ver o índice no
> topo deste arquivo.

---

## [2026-09-02] TASK-009 · Bloco F: container, README, e o que a execução real derrubou

Os dois gates passaram: `up --wait` com três serviços `healthy`, boot na ordem, issuer igual a
`{BASE_URL}/o`, 500 provocado visível em `docker logs`; e o fluxo PKCE percorrido à mão contra o
container devolveu `id_token` — critério escrito do passo 12.

**Quatro coisas que só a execução revelou, todas invisíveis para a suíte:**

- **O alçapão do `algorithm` está descrito ao contrário no roadmap e estava no README.** O passo 12
  diz que em branco "o `access_token` chega e nenhum `id_token` é emitido". **Falso na 3.4.1**:
  `/o/authorize/` responde 200 e emite `code` normalmente, e o `POST /o/token/` devolve **HTTP 500 e
  token nenhum** — `ImproperlyConfigured: This application does not support signed tokens`, do
  `jwk_key` chamado por `finalize_id_token`, que sempre roda porque o DOT não implementa
  `get_id_token`. Previsto pelo `senso-critico` lendo o pacote, **verificado por mim** com duas
  Applications idênticas exceto pelo campo. Terceira vez que uma falha silenciosa deste projeto
  estava catalogada de cabeça para baixo (ver TASK-006, JWKS).
- **O orçamento de tempo do `HEALTHCHECK` estava errado, e a folga estava no lugar errado.** Os
  `socket_connect_timeout` e `socket_timeout` do cache são **aditivos dentro de uma operação**; o
  `cache.get` **não** entra na conta porque compartilha o `try` do `set`. Teto real da view: **6s**,
  não 4s. A probe tinha `timeout=4` contra ~4s de estado estacionário degradado — **margem zero**:
  ela se matava antes de o 503 existir, e sumia o corpo que nomeia o culpado. Corrigido para
  `timeout=7` sob `--timeout=8s`. **Medido depois**: `pause` nos dois componentes → 503 em
  **4,03s**, corpo com `database` e `cache` em `error`. Com os números velhos essa resposta não
  existiria.
- **Ligar `BEHIND_TLS_PROXY` não basta.** A probe manda `Host: 127.0.0.1:8000`; um `ALLOWED_HOSTS`
  estreitado ao nome público devolve **400 `DisallowedHost`** e o mesmo unhealthy eterno, pela
  segunda causa. Minha verificação empírica não pegou porque variei **uma** variável só — limite da
  evidência apontado corretamente pelo `senso-critico`.
- **O entrypoint descartava `$@`**: `docker compose run --rm app python manage.py migrate` tinha o
  comando engolido em silêncio e subia gunicorn. Guarda de duas linhas, verificada em container.

**Disposições.** ACEITOS e implementados: os quatro acima, mais a guarda `T-01` da isenção (mordida
provada em duas mutações — comentar a linha, e renomear a rota, que morde porque o teste usa
`reverse("health")`), `PYTHONUNBUFFERED=1` (sem ele a Positiva da ADR 0006 sobre `docker logs` é
falsa), a contagem da suíte **removida** do README em vez de corrigida (o número apodreceu em menos
de um dia; a instrução útil — usar `manage.py test` sem argumento — não envelhece), o gerador
`openssl rand -hex 48` da `SECRET_KEY` (a receita mandava "regerar" sem dizer como, e chave fraca
aqui não tem sinal nenhum), a derivação falsa de `--workers 3` substituída (o piso é >1; o 3 é
convenção — terceira vez que um comentário deste projeto afirma o que o código não faz), e o root
registrado como decisão no Dockerfile. REJEITADO: excluir `.claude/` do `.dockerignore` — cosmético,
e abriria um sexto arquivo. ADIADOS ao bloco G: a ADR 0006 incompleta (não registra a isenção), a
terceira frase da ADR 0009 (`health` verde não significa "capaz de atender": `SELECT 1` não vê
migration pendente), e as duas afirmações falsas de `docs/roadmap/12-readme.md`, que não foi
autorizado neste bloco.

**Regra que fica:** o número de casos da suíte não entra em documentação. O que entra é qual comando
roda o quê.

- **Tipo:** decisão.
