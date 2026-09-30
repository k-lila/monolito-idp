# CLAUDE.md — IdP

Provedor de identidade (IdP, de _Identity Provider_) OpenID Connect (OIDC) de pé: fecha o fluxo
Authorization Code com PKCE (Proof Key for Code Exchange), publica descoberta e JWKS (JSON Web
Key Set) e emite `id_token` assinado em RS256 (RSA, de Rivest–Shamir–Adleman, com SHA-256).
Monólito: identidade, telas de login e consentimento, servidor de autorização e endpoints de
descoberta vivem em uma aplicação implantável só.

O IdP aceita relying parties (RPs), as aplicações que delegam a ele a autenticação. Uma RP entra
por configuração, nunca por código: uma `Application` no admin por ambiente e, se roda no
navegador, a origem dela em `CORS_ALLOWED_ORIGINS`. O que o IdP é, as invariantes que ele
preserva e o contrato com toda RP estão em `docs/nucleo-idp.md`.

O escopo é o de host único e uma réplica, e a aplicação não tem TLS (Transport Layer Security)
próprio: ele termina no proxy do compose. Postgres e Redis publicam em `127.0.0.1`, e o proxy
também, fora de produção. Em produção nada é publicado: a ADR (Architecture Decision Record) 0027
serve o IdP da máquina do dono por um túnel nomeado da Cloudflare, cujo conector é serviço do
override `docker-compose.prod.yml`, invocado com os dois `-f`. O TLS do navegador termina na borda
da Cloudflare, e quem controla a conta da Cloudflare ou as credenciais do túnel controla a
entrada. Isso é premissa registrada de várias decisões, não licença para decidir de qualquer
jeito: as decisões já tomadas são compromissos.

## O que já está fechado

- As ADRs são imutáveis depois de aceitas. Contrariar uma exige emenda ou ADR nova, nunca edição do
  arquivo aceito. O índice está em `docs/arquitetura.md`; os arquivos, em `docs/adr/`.
- O contrato OIDC é público e fica cacheado em cada RP: issuer, descoberta e
  JWKS. Mudança nele não é refatoração interna — é quebra de contrato com terceiro.
- Fechado prova-se com a suíte e contra o código, nunca contra o documento que descreve o
  código. O escopo de um problema verifica-se varrendo a superfície no código, nunca relendo o
  texto que o descreve.
- Decisão sem ADR e dívida técnica ficam em `.claude/memory/decisions.md`; impedimento aberto,
  em `.claude/memory/blockers.md`.
- Cada clone tem o seu `.env`, untracked e sem cópia no repositório. Ele guarda a única
  `OIDC_RSA_PRIVATE_KEY` e a única `SECRET_KEY` daquele ambiente: `git clean -xd` apaga a
  identidade do IdP naquele clone, e nenhum `reset` a restaura. O de produção tem backup cifrado
  fora da máquina (ADR 0027, Backup).
- O contrato com toda RP é a §3 de `docs/nucleo-idp.md`, e o detalhe de quem integra está em
  `docs/integracao-rp.md`. Mudar uma linha dele exige ADR nos dois projetos (`docs/nucleo-idp.md`
  §2).
- A primeira RP é a aplicação de página única (SPA, de _Single-Page Application_) do sistema, e a
  integração em desenvolvimento está fechada contra este IdP real. A forma do issuer de produção
  está congelada (ADR 0025), e a ADR 0027, aceita em 2026-09-28, substituiu a 0026. O caminho até
  produção está consolidado em `../pre-deploy.md`. O plano de implantação que numerava os passos
  saiu do repositório e segue em `git show 8caf117:docs/plano-implantacao.md`: os passos 1 a 4
  estão fechados, o 4 com três verificações levadas aos passos 6 e 7; o 5 fecha com a revisão da
  SPA e do `../pre-deploy.md`, e os passos 6 e 7 são de quem opera.

## Como se escreve código aqui

- Mecanismo simples, sem elaboração além do que a tarefa pede.
- Comentário exaustivo na justificativa: registra a razão, não a operação.
- Onde a falha é silenciosa, o comentário registra o silêncio. Precedentes vivos:
  `OIDC_RSA_PRIVATE_KEY` presente e vazia devolve JWKS vazio com 200, e ausente derruba o
  processo na leitura das settings, nomeando a si mesma (ADR 0004); `OAUTH2_VALIDATOR_CLASS`
  ausente emite `id_token` só com `sub`; posição errada do `CorsMiddleware` é indetectável
  enquanto a allowlist de CORS (Cross-Origin Resource Sharing) estiver vazia. O catálogo está
  em `docs/arquitetura.md` §II.6 e em `docs/observabilidade.md` §2; o anterior, mais extenso,
  em `git show 8caf117:docs/runbook.md` §14.
- Prosa em português segue a skill `estilo-de-prosa`, inclusive em comentário e docstring.

## Como se verifica

As duas jornadas abaixo exigem Postgres e Redis de pé — no mínimo `docker compose up postgres
redis`. O que as separa está no `README.md`.

```bash
.venv/bin/python manage.py test                 # jornada de construção
docker compose exec app python manage.py test   # clonar-e-rodar
```

Sem argumento: a suíte inteira vive em `tests/`, na raiz, e é isso que `manage.py test`
descobre. Um rótulo de app — `manage.py test accounts` — hoje encontra zero teste e diz
isso em voz alta. O executor é o do Django: não há pytest, `conftest.py` nem dependência de
teste no `requirements.txt`. O que cada arquivo de teste cobre é de `docs/testes.md`.

## Regras de trabalho

### Restrições explícitas

- Não refatore código fora do escopo explícito da tarefa pedida.
- Não adicione tratamento de erro para cenários impossíveis.
- Não crie nem modifique arquivos sem que seja pedido ou autorizado explicitamente.

### Regras gerais (do orquestrador)

- Pergunte antes de agir se a tarefa envolver mais de dois arquivos.
- Antes de cada alteração no código, apresente um relatório que aponte: as razões do novo
  código e das modificações; e os arquivos a criar e a modificar, quando houver.
- Ao elaborar perguntas ou opções de resposta, dê um panorama das opções em até duas
  linhas. Cada opção leva ao menos um pró e um contra.
- Sempre que utilizar pela primeira vez a sigla, escrever o nome completo e a sigla entre parênteses. Exemplo: 'Identity provider (IdP)'.

## Ponteiros

- `.claude/PROTOCOLO-AGENTES.md` — as convenções entre agentes: fronteiras de escrita,
  severidade, veredito e ciclo de vida da tarefa. Vale em toda rota, e todo agente o lê. Os
  fluxos em si estão em `.claude/commands/`.
- `README.md` — o mapa dos documentos e o arranque mínimo.
- `docs/nucleo-idp.md` — o que é o monólito IdP, as invariantes, o contrato com toda RP e como
  uma RP nova entra.
- `docs/arquitetura.md` — os módulos, a fronteira entre eles e o índice das ADRs.
- `docs/integracao-rp.md` — o contrato visto por quem integra uma RP: registro, fluxo, claims,
  verificação e tempos de vida.
- `../pre-deploy.md` — os dois lados consolidados antes do deploy.
- Os documentos que saíram na reorganização de 2026-09-29 (runbook, plano de implantação,
  esboço, robustez) e que as ADRs ainda citam: `git show 8caf117:docs/<arquivo>`.
- `.claude/settings.json` — exige confirmação para `Edit` e `Write` em `.claude/**` e
  `docs/adr/**`. Escrita por `Bash` passa por baixo: é compromisso, não barreira.
