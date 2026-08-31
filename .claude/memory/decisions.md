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

---

**Regra ao acrescentar:** se a decisão tem ADR, escreva **uma linha** no índice e o resto
no ADR. Se não tem, escreva a entrada completa aqui. Um log que cresce sem poda não é
memória — é sedimento.
