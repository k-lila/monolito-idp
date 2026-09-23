# CLAUDE.md — nova_api

Provedor de identidade (IdP, de _Identity Provider_) OpenID Connect (OIDC) de pé: fecha o fluxo
Authorization Code com PKCE (Proof Key for Code Exchange), publica descoberta e JWKS (JSON Web
Key Set) e emite `id_token` assinado em RS256 (RSA, de Rivest–Shamir–Adleman, com SHA-256).
Monólito: identidade, telas de login e consentimento, servidor de autorização e endpoints de
descoberta vivem em uma aplicação implantável só.

O escopo é o de host único e uma réplica, e a aplicação não tem TLS (Transport Layer Security)
próprio: ele termina no proxy do compose. Postgres e Redis publicam em `127.0.0.1`, e o proxy
também, fora de produção. O proxy é a exceção declarada em produção: a ADR (Architecture Decision
Record) 0026 o publica em 80 e 443 fora de loopback na instância da AWS (Amazon Web Services), por
um arquivo de override do compose que quem opera invoca com `-f`, com um salto de proxy só e o
security group da instância como única barreira de rede. Isso é premissa registrada de várias
decisões, não licença para decidir de qualquer jeito: as decisões já tomadas são compromissos.

## O que já está fechado

- As ADRs são imutáveis depois de aceitas. Contrariar uma exige emenda ou ADR nova, nunca edição do
  arquivo aceito. O índice está em `docs/arquitetura.md`; os arquivos, em `docs/adr/`.
- O contrato OIDC é público e fica cacheado em cada relying party (RP): issuer, descoberta e
  JWKS. Mudança nele não é refatoração interna — é quebra de contrato com terceiro.
- Fechado prova-se com a suíte e contra o código, nunca contra o documento que descreve o
  código. O escopo de um problema verifica-se varrendo a superfície no código, nunca relendo o
  texto que o descreve.
- Decisão sem ADR e dívida técnica ficam em `.claude/memory/decisions.md`; impedimento aberto,
  em `.claude/memory/blockers.md`.
- O `.env` é untracked e não tem cópia. Ele guarda a única `OIDC_RSA_PRIVATE_KEY` e a única
  `SECRET_KEY` do projeto: `git clean -xd` apaga a identidade do IdP, e nenhum `reset` a
  restaura.
- A primeira RP é a `nova_api_SPA`, e a integração em desenvolvimento está fechada contra
  este IdP real (passos 1 a 4 de `docs/plano-contrato-backend.md`). O que a SPA consome e o
  que este projeto lhe deve estão em `docs/contrato-backend.md`; o caminho até a exposição na
  AWS são os passos 5 a 9 do plano. Os passos 5 e 6 estão fechados (ADRs 0024, 0025 e 0026): a
  forma do issuer de produção está congelada, e a premissa de loopback deixou de valer para o
  proxy em produção com a aceitação da 0026. Os passos 7 a 9 aplicam a decisão, e nenhum
  começou.

## Como se escreve código aqui

- Mecanismo simples, sem elaboração além do que a tarefa pede.
- Comentário exaustivo na justificativa: registra a razão, não a operação.
- Onde a falha é silenciosa, o comentário registra o silêncio. Precedentes vivos:
  `OIDC_RSA_PRIVATE_KEY` presente e vazia devolve JWKS vazio com 200, e ausente derruba o
  processo na leitura das settings, nomeando a si mesma (ADR 0004); `OAUTH2_VALIDATOR_CLASS`
  ausente emite `id_token` só com `sub`; posição errada do `CorsMiddleware` é indetectável
  enquanto a allowlist de CORS (Cross-Origin Resource Sharing) estiver vazia. O catálogo
  completo é de `docs/runbook.md`.
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
- `docs/arquitetura.md` — os módulos, a fronteira entre eles e o índice das ADRs.
- `docs/contrato-backend.md` — o contrato com a `nova_api_SPA`: o que não pode mudar, o que
  falta configurar e a checklist por ambiente. `docs/plano-contrato-backend.md` — a ordem de
  cumpri-lo, passo a passo. `../pre-deploy.md` — os dois lados consolidados antes do deploy.
- `.claude/settings.json` — exige confirmação para `Edit` e `Write` em `.claude/**` e
  `docs/adr/**`. Escrita por `Bash` passa por baixo: é compromisso, não barreira.
