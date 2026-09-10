# Arquitetura — nova_api

Guia de orientação para quem abre este repositório sem contexto prévio. Dá o modelo mental do
sistema e diz, para cada assunto, em que arquivo o detalhe já está escrito. Onde há detalhe em
outro lugar, este documento aponta em vez de repetir.

## O que o sistema é

Um provedor de identidade (IdP) OpenID Connect (OIDC), monolítico, sobre Django 5.2 e
`django-oauth-toolkit` 3.4.1. Fecha o fluxo Authorization Code com PKCE (Proof Key for Code
Exchange) restrito a `S256`, publica descoberta e JWKS (JSON Web Key Set) e emite `id_token`
assinado em RS256 (RSA com SHA-256). As aplicações que delegam a autenticação a ele são as
relying parties (RPs).

Monólito significa que modelo de usuário, telas de login e consentimento, servidor de
autorização, emissão de token e endpoints de descoberta vivem em uma aplicação implantável só.

O escopo declarado é o de sandbox exploratório: host único, uma réplica, sem TLS (Transport
Layer Security) próprio, porta publicada em `127.0.0.1`. Isso não é provisório por descuido —
é premissa de várias decisões registradas, e a lista do que ainda não existe está em
`docs/seguranca.md`, como risco, e em `docs/receita.md`, como pendência de produção.

## Os módulos e a fronteira entre eles

Três módulos, com fronteira nítida. Cada um decide uma coisa.

**`config` — a borda e a composição.** Não afirma nada sobre identidade e não toca o modelo de
usuário. Contém a configuração (`config/settings.py`, arquivo único dirigido por ambiente, sem
default no código e sem separação entre desenvolvimento e produção), o URLConf raiz
(`config/urls.py`) e duas views em `config/views.py`: `home`, destino de `LOGIN_REDIRECT_URL` e
de `LOGOUT_REDIRECT_URL`, e `health`, a sonda de prontidão. Também `config/observabilidade.py`,
que decide o formato de uma linha de log, o identificador que correlaciona as linhas de um mesmo
pedido e a linha de acesso — e que, como o resto de `config`, não afirma nada sobre identidade.

`LOGIN_URL`, `LOGIN_REDIRECT_URL` e `LOGOUT_REDIRECT_URL` guardam nomes de rota (`"login"`,
`"home"`), não caminhos: quem os resolve é `resolve_url`, em tempo de execução, e não
`reverse` nas settings, lidas antes do URLConf. Renomear uma rota produz `NoReverseMatch`,
falha ruidosa.

**`accounts` — a identidade.** É o app dono da pessoa e do que o IdP afirma sobre ela:

- `accounts/models.py` — `User` herdando de `AbstractUser`, com `username = None` e e-mail
  único como identificador de login;
- `accounts/oauth_validators.py` — `IdPOAuth2Validator`, o único ponto em que o comportamento
  do servidor de autorização é customizado. Decide claims (`sub`, `name`, `email`); não toca
  em fluxo;
- `accounts/auditoria.py` — os quatro receptores de sinal e o que a trilha de auditoria afirma
  sobre quem autenticou: `sub`, origem e desfecho, nunca e-mail nem valor de token. Ligados em
  `AccountsConfig.ready()`;
- `accounts/admin.py` — `UserAdmin` ajustado a um modelo sem `username`.

**`oauth2_provider` — o protocolo.** É dependência de terceiro, montada sob o prefixo `o/` pelo
`include` em `config/urls.py`. Nenhum método de protocolo é sobrescrito; a única peça
substituída é o template da tela de consentimento,
`templates/oauth2_provider/authorize.html`.

O acoplamento entre `accounts` e o toolkit é uma chave só: `OAUTH2_VALIDATOR_CLASS`, no bloco
`OAUTH2_PROVIDER` de `config/settings.py`. É contrato por string, resolvido no boot — caminho
errado falha ali; chave ausente não dá erro nenhum e o `id_token` sai só com `sub`.

## O caminho de um pedido

1. A relying party redireciona o navegador para `/o/authorize/`, com `code_challenge` e
   `code_challenge_method=S256`.
2. Sem sessão, a view do toolkit desvia para `/accounts/login/` carregando o `next`.
3. Autenticada a pessoa, abre-se a sessão de login (SSO), no backend `cached_db`: grava no
   Postgres, lê do Redis.
4. A tela de consentimento lista os scopes concedidos, com as descrições declaradas em
   `SCOPES`.
5. O consentimento redireciona de volta à `redirect_uri` registrada, com o código de
   autorização na query string.
6. A RP troca o código em `POST /o/token/`, apresentando o `code_verifier`, e recebe
   `access_token`, `refresh_token` e `id_token`.
7. A RP verifica a assinatura do `id_token` contra `/o/.well-known/jwks.json` e confere o
   `iss`, que é `{BASE_URL}/o`.

A superfície HTTP própria do projeto é curta: `/`, `/health` (sem barra final, porque é a URL
da sonda do container), `/accounts/login/`, `/accounts/logout/` (só POST) e `/admin/`. Tudo o
mais vem do `include` do toolkit sob `/o/`: `authorize/`, `token/`, `userinfo/`,
`.well-known/openid-configuration` e `.well-known/jwks.json`, e junto com eles a gestão de
Applications e de tokens, o fluxo de device grant e `/o/register/` — rotas que este projeto não
usa. O registro dinâmico de client responde 404 enquanto `DCR_ENABLED` mantiver o default
`False`. `/accounts/password_reset/` é um 404 deliberado, explicado no comentário de
`config/urls.py`.

## Onde mora o estado

| Lugar | O que guarda |
| --- | --- |
| Postgres | contas, Applications, grants, tokens e `django_session`; volume `pgdata` |
| Redis | cópia quente da sessão e a chave da sonda do `/health`; volume `redisdata` |
| Ambiente do processo | a chave privada RSA e a `SECRET_KEY`, fora do banco e da imagem |
| Cookie do navegador | apenas o identificador da sessão |
| Arquivo, no container | a trilha de auditoria; volume `auditlog`, montado em `/var/log/nova_api` |

O Redis é descartável — a sessão sobrevive a `flush` e a reinício dele —, mas o IdP não tolera
sua ausência: `SESSION_ENGINE = cached_db` toca o cache a cada requisição. O detalhe está na
ADR (Architecture Decision Record) `docs/adr/0005-manter-a-sessao-sso-em-sessao-django-com-backend-cached-db.md`.

## A árvore, comentada

Cada entrada diz o que aquele arquivo **decide**.

```
config/
  settings.py          toda a configuração; leitura do ambiente e o bloco OAUTH2_PROVIDER
  urls.py              a superfície HTTP: o que existe, sob que prefixo, com que nome de rota
  views.py             home e health — a borda que não afirma nada sobre identidade
  observabilidade.py   como uma linha de log é escrita e como duas linhas se ligam
  wsgi.py              ponto de entrada do gunicorn
accounts/
  models.py            o que é uma pessoa aqui: e-mail único, sem username
  oauth_validators.py  o que um token afirma sobre a pessoa
  auditoria.py         o que a trilha afirma sobre quem autenticou
  admin.py             a tela de administração de contas
  apps.py              registro do app
  migrations/          o esquema de accounts, a chave primária de 64 bits que vira o `sub`
tests/                 a suíte inteira: fluxo OIDC, telas, validador, /health, log e auditoria
logs/                  a trilha de auditoria da jornada de construção; versionado por .gitkeep
templates/
  base.html            o esqueleto das telas e o form de logout
  home.html            a home pública
  registration/login.html            a tela de login
  oauth2_provider/authorize.html     a tela de consentimento (override de template, não de view)
static/css/idp.css     a aparência das telas
docker/entrypoint.sh   a sequência de boot do container
scripts/gen_dev_key.sh gera o par RSA de desenvolvimento; não escreve no .env de propósito
Dockerfile             a imagem e o HEALTHCHECK
docker-compose.yml     os três serviços, a ordem de subida e o que é publicado no host
requirements.txt       as versões fixadas, e o piso de compatibilidade do Django
.env.example           o contrato de variáveis de ambiente
docs/adr/              as quatorze decisões de arquitetura, uma por arquivo, mais o template
.claude/               sistema de agentes; não participa da execução do IdP
```

## Empacotamento e execução

Imagem em dois estágios sobre `python:3.14-slim`: o primeiro constrói o wheelhouse, o segundo
instala a partir dele. O `docker-compose.yml` sobe três serviços — `app`, `postgres` (17) e
`redis` (7) —, e a espera pelos dois últimos é do `depends_on` com `condition:
service_healthy`, não de laço no entrypoint.

`docker/entrypoint.sh` abre com uma guarda de comando explícito — argumento passado à imagem
roda sozinho, sem a sequência de boot — e depois executa `migrate`, `collectstatic`, a criação
condicional de superusuário e o `exec gunicorn` com três workers.

O `HEALTHCHECK` do `Dockerfile` deriva seus tempos dos tetos da própria aplicação, em vez de
escolhê-los: 2 s de conexão com o banco, 4 s de cache (os dois timeouts do Redis são aditivos)
e 1 s de folga, dando 7 s internos sob 8 s externos.

Existem duas jornadas de execução, e `docs/receita.md` descreve as duas: clonar-e-rodar, tudo
em container, e a de construção, com a aplicação em `runserver` no host contra o Postgres e o
Redis do compose.

## Onde buscar mais detalhe

| Assunto | Arquivo |
| --- | --- |
| Passo a passo das duas jornadas, do `.env` ao fluxo PKCE fechado à mão, e as tarefas do dia a dia | `docs/receita.md` |
| Sintoma, causa e correção, mais os alçapões — `algorithm` em branco, `BEHIND_TLS_PROXY`, estáticos, reciclagem do `sub` | `docs/runbook.md` |
| O que o IdP protege, o que não protege e o que muda antes de ele sair de `localhost` | `docs/seguranca.md` |
| O contrato de quem integra uma relying party: claims, verificação do token, tempos de vida | `docs/integracao-rp.md` |
| Níveis de teste, rastreabilidade, helpers e o que não é coberto | `docs/testes.md` |
| Identidade do projeto, as duas jornadas nomeadas e o índice dos documentos | `README.md` |
| Por que cada tecnologia do núcleo, com prós e contras | `docs/esboco.md` |
| O que é um IdP e como ele se comporta | `docs/esboco.md`, seção A |
| Motivo de cada valor de configuração | comentários de `config/settings.py` |
| Regras de trabalho e restrições do repositório | `CLAUDE.md` |
| Convenções entre agentes, incluindo as de ADR | `.claude/PROTOCOLO-AGENTES.md` |

As decisões de arquitetura, uma por arquivo em `docs/adr/`:

| Assunto | ADR |
| --- | --- |
| Plataforma: Django 5.2 sobre Python 3.14 | `0001-adotar-django-5-2-lts-sobre-python-3-14.md` |
| O toolkit como servidor de autorização | `0002-usar-django-oauth-toolkit-como-servidor-de-autorizacao.md` |
| `User` customizado com e-mail como identificador | `0003-modelar-identidade-em-user-customizado-com-email-como-identificador.md` |
| RS256 e a custódia da chave privada | `0004-assinar-tokens-com-rs256-e-custodiar-a-chave-privada-no-ambiente.md` |
| A sessão SSO em `cached_db` | `0005-manter-a-sessao-sso-em-sessao-django-com-backend-cached-db.md` |
| Container único orquestrado por docker-compose | `0006-empacotar-o-idp-como-container-unico-orquestrado-por-docker-compose.md` |
| O issuer em `{BASE_URL}/o` | `0007-fixar-o-issuer-do-idp-em-base-url-barra-o.md` |
| WhiteNoise sem manifesto de hash | `0008-servir-estaticos-com-whitenoise-sem-manifesto-de-hash.md` |
| O `/health` isolado da sessão e do usuário | `0009-isolar-a-view-de-health-da-sessao-e-do-usuario.md` |
| A isenção de `/health` no redirecionamento para HTTPS | `0010-isentar-health-do-redirecionamento-para-https.md` |
| O teto de tempo do `/health` e o `HEALTHCHECK` derivado dele | `0011-dar-teto-de-tempo-ao-health-e-derivar-o-healthcheck-dele.md` |
| O log operacional em JSON, com identificador de requisição — **emendada pela 0014** | `0012-emitir-o-log-operacional-em-json-com-identificador-de-requisicao.md` |
| A trilha de auditoria dos quatro sinais, em arquivo durável | `0013-registrar-a-trilha-de-auditoria-dos-quatro-sinais-em-arquivo-duravel.md` |
| O tempo de vida do identificador de requisição; emenda à 0012 | `0014-manter-o-identificador-de-requisicao-ate-a-requisicao-seguinte.md` |

ADR aceita é imutável: decisão que mudou vira ADR nova. O formato está em
`docs/adr/template-adr.md`.

As ADRs 0008 e 0010 citam "o passo NN do roadmap", e o mesmo rótulo aparece encurtado para
"passo NN" em comentários do `Dockerfile`, do `docker-compose.yml`, de `config/settings.py`, de
`accounts/models.py` e de `tests/test_password_reset_urls.py`. São os treze arquivos de
`docs/roadmap/`, a ordem de implementação que guiou a construção do núcleo, de
`01-dependencias-e-contrato-de-ambiente.md` a `13-adrs.md`. Foram removidos no commit `b7774d5`
depois de cumpridos, e cada um segue legível no histórico — por exemplo, `git show
b7774d5^:docs/roadmap/09-telas-e-estaticos.md`. Onde o código diverge deliberadamente do que um
passo prescrevia, quem decide é o código, e a divergência está registrada na ADR ou no próprio
comentário que cita o passo.

O comportamento verificado está nos arquivos `test_*.py` de `tests/`, ao lado de dois módulos
que não são teste: `tests/oauth_helpers.py`, que carrega a infraestrutura do fluxo, e
`tests/runner.py`, o executor que aponta a trilha de auditoria da suíte para um diretório
temporário. O que cada arquivo garante, em que nível e contra que regressão está em
`docs/testes.md`, na seção "O que cada arquivo garante"; é lá que também estão como rodar a
suíte e o que ela não cobre.
