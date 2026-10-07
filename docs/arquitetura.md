# Arquitetura — IdP

O mapa do projeto e o desenho do sistema. A parte I diz onde cada coisa está; a parte II, como
as peças se ligam. O que o sistema é, as invariantes e o contrato com as relying parties (RPs)
estão em `docs/nucleo-idp.md`; o apêndice traz o índice das ADRs (Architecture Decision
Records).

Em uma linha: um provedor de identidade (IdP, de _Identity Provider_) OpenID Connect (OIDC),
monolítico, sobre Django 5.2 e `django-oauth-toolkit` 3.4.1, que fecha o fluxo Authorization
Code com PKCE (Proof Key for Code Exchange) e emite `id_token` assinado em RS256 (RSA, de
Rivest–Shamir–Adleman, com SHA-256) para as RPs que delegam a autenticação a ele.

---

## I. Árvore de arquivos

Os diretórios e arquivos que importam, cada um com o que **decide**. Migrações, `__init__.py`
e arquivos de apoio ficam de fora.

```
./
├── config/                    a borda e a composição; não afirma nada sobre identidade
│   ├── settings.py            toda a configuração, lida do ambiente, e o bloco OAUTH2_PROVIDER
│   ├── urls.py                a superfície HTTP: o que existe, sob que prefixo, com que nome
│   ├── views.py               home, com o botão para a aplicação de página única (SPA, de
│   │                          Single-Page Application), e health, a sonda de prontidão
│   ├── origem.py              de que endereço veio a requisição, e de onde esse valor saiu
│   ├── limites.py             o teto de requisições por origem na autenticação e na conta
│   ├── observabilidade.py     como uma linha de log é escrita e como duas linhas se ligam
│   └── wsgi.py                ponto de entrada do gunicorn
├── accounts/                  a identidade: a pessoa e o que o IdP afirma sobre ela
│   ├── models.py              User com e-mail único em minúsculas e sem username; o sub é um
│   │                          UUID (Universally Unique Identifier), e a chave primária fica
│   │                          interna; as regras de escrita no save()
│   ├── oauth_validators.py    o que um token afirma sobre a pessoa (seis claims, o sub inclusive)
│   ├── logout_rp.py           o que o "Sair" de uma RP faz com os tokens da pessoa
│   ├── revogacao.py           a ordem de revogação dos tokens de uma conta e o sinal que a anuncia
│   ├── paginas.py             as páginas de conta, em português: cadastro, senha, e-mail, exclusão
│   ├── formularios.py         os formulários das páginas; a senha atual por authenticate()
│   ├── api.py                 a interface de programação (API, de Application Programming
│   │                          Interface) de conta da SPA, sob Bearer, e o link de confirmação
│   ├── confirmacao.py         o token assinado do link de confirmação de e-mail
│   ├── emails.py              as seis mensagens, montadas em português, com links sobre BASE_URL
│   ├── envio.py               quando e como a mensagem sai: teto por destinatário, commit, thread
│   ├── tentativas.py          o esquecimento e o desbloqueio das linhas do axes de um endereço
│   ├── sinais.py              os dez eventos de conta que a trilha registra
│   ├── auditoria.py           o que a trilha afirma sobre quem autenticou e o que mudou na conta
│   ├── admin.py               a administração de contas
│   └── apps.py                liga os receptores da trilha no ready()
├── templates/
│   ├── base.html              o esqueleto das telas e o form de logout
│   ├── home.html              a home pública
│   ├── registration/          login, bloqueio (excesso de tentativas) e as páginas de conta
│   ├── emails/                assunto e corpo, em texto puro, de cada uma das seis mensagens
│   └── oauth2_provider/       authorize.html (consentimento) e logout_confirm.html
├── static/css/idp.css         a aparência das telas
├── tests/                     a suíte inteira, com o executor e os helpers do fluxo
│   ├── runner.py              aponta a trilha de auditoria da suíte para diretório temporário
│   ├── oauth_helpers.py       a infraestrutura do fluxo OIDC usada pelos testes
│   ├── logout_helpers.py      a infraestrutura do logout pela RP
│   ├── api_conta_helpers.py   o token da SPA e as chamadas à API de conta
│   ├── paginas_helpers.py     a conta, a sessão e os dados das páginas de conta
│   ├── envio_helpers.py       o envio com o commit executado e o contador por destinatário
│   └── test_*.py              um arquivo por comportamento garantido
├── docker/
│   ├── entrypoint.sh          a sequência de boot: migrate, collectstatic, gunicorn
│   └── Caddyfile              o nome atendido, o certificado, o destino e a confiança no conector
├── scripts/gen_env_secrets.sh gera os segredos do .env, a chave RSA inclusive; não escreve nele
├── Dockerfile                 a imagem em dois estágios, o usuário sem root e o HEALTHCHECK
├── docker-compose.yml         os quatro serviços, a ordem de subida e o que se publica no host
├── docker-compose.prod.yml    o override de produção: o conector do túnel e nenhuma porta
├── requirements.txt           as versões fixadas
├── .env.example               o contrato de variáveis de ambiente
├── logs/                      a trilha de auditoria da jornada de construção (.gitkeep)
├── docs/
│   ├── nucleo-idp.md          espelho e guia: o que o IdP é e o que se preserva
│   ├── arquitetura.md         este mapa
│   ├── integracao-rp.md       o contrato de quem integra uma RP
│   ├── receita.md             subir o stack e as tarefas do dia a dia
│   ├── seguranca.md           o que o IdP protege e o que não protege
│   ├── testes.md              os níveis de teste e o que cada arquivo garante
│   ├── observabilidade.md     o que o log e a trilha registram, e o que falta
│   └── adr/                   as decisões, uma por arquivo, mais o template
├── .claude/                   o sistema de agentes; não participa da execução do IdP
├── CLAUDE.md                  as regras de trabalho do repositório
└── README.md                  a identidade do projeto e o arranque mínimo
```

Fora do versionamento, e só no clone de cada ambiente: o `.env`, com a única chave privada e a
única `SECRET_KEY` daquele clone e as credenciais do SMTP (_Simple Mail Transfer Protocol_), e,
no de produção, o diretório `cloudflared/`, com as credenciais do túnel (ADR 0027).

---

## II. Arquitetura

### 1. Contexto: o IdP e quem fala com ele

```
                         ┌──────────────────────────────┐
     pessoa usuária ────►│          navegador           │
                         └──┬──────────────┬────────────┘
         (a) redirect de    │              │ (b) fetch com CORS
         navegador: login,  │              │     /o/token/, /o/userinfo/,
         consentimento,     │              │     descoberta, JWKS,
         "Sair", páginas    │              │     /api/conta/
         de conta           │              │
                            ▼              ▼
                ┌───────────────────────────────────────┐
                │  borda da Cloudflare (só em produção) │  TLS do navegador termina aqui
                └───────────────────┬───────────────────┘
                                    │ túnel nomeado, iniciado de dentro
                                    ▼
      ┌──────────────────────────────────────────────────────────┐
      │                       o IdP (monólito)                   │
      │  login · consentimento · emissão de token · descoberta   │
      └──────────────────────────────────────────────────────────┘
                                    ▲
                                    │ (c) servidor a servidor: /o/token/, /o/userinfo/
                          ┌─────────┴─────────┐
                          │ RP com back-end   │  (nenhuma hoje)
                          └───────────────────┘

      RPs no navegador: a SPA (primeira parte). Cada RP é uma Application no admin.
```

O IdP não conhece as RPs pelo código, só pela configuração: cada uma é uma `Application`
cadastrada no admin e, se roda no navegador, uma origem em `CORS_ALLOWED_ORIGINS`. Há três
canais, e cada um tem uma regra própria:

- **(a) Redirect de navegador.** É o único caminho da autenticação e das páginas de conta. A
  senha só é digitada em tela do IdP e nunca chega à RP.
- **(b) `fetch` de uma RP de navegador.** Passa pelo CORS (Cross-Origin Resource Sharing), com
  origem exata e só sob `/o/` e `/api/conta/` (ADRs 0022 e 0031). A API de conta aceita só o
  token da SPA.
- **(c) Servidor a servidor.** Não passa pelo CORS e dispensa configuração no IdP.

Há ainda uma saída que nenhuma RP vê: o e-mail, que o IdP entrega por SMTP ao servidor de
`EMAIL_HOST`, numa thread do processo, depois do commit (ADR 0031).

### 2. Implantação: os serviços e o que se publica

```
  desenvolvimento e jornada de container          produção (dois -f: base + override)
  ──────────────────────────────────────          ───────────────────────────────────
  host: 127.0.0.1:80/443 ──► proxy                internet ──► borda Cloudflare
                               │                                     │ túnel
                               │                           cloudflared (rede borda,
                               │                                     │   10.203.14.200)
                               ▼                                     ▼
                     ┌──────────────────┐                  ┌──────────────────┐
                     │ proxy (Caddy)    │                  │ proxy (Caddy)    │ redes default
                     │ tls internal     │                  │ tls internal     │ e borda
                     └────────┬─────────┘                  └────────┬─────────┘
                              │ http, rede interna                   │
                              ▼                                      ▼
                     ┌──────────────────┐                  ┌──────────────────┐
                     │ app (gunicorn,   │ sem ports:       │ app              │ DEBUG="False"
                     │ 3 workers, :8000)│                  │                  │
                     └───┬──────────┬───┘                  └───┬──────────┬───┘
                         ▼          ▼                          ▼          ▼
                     postgres    redis                     postgres    redis
                     (127.0.0.1) (127.0.0.1)               (sem porta) (sem porta)
```

O arquivo base é o mesmo nos dois lados, e o override de produção só subtrai e acrescenta:

- **Base, `docker-compose.yml`.** Quatro serviços: `proxy` (`caddy:2.11.4`, fixado em versão
  exata), `app`, `postgres` (17) e `redis` (7). A subida espera os dois de estado por
  `depends_on` com `condition: service_healthy`.
- **Override, `docker-compose.prod.yml`.** Zera por `!reset []` o `ports:` de `proxy`,
  `postgres` e `redis`. Declara o `cloudflared` na rede `borda`, com endereço fixo, põe
  `restart: unless-stopped` em todos os serviços e fixa `DEBUG`.
- **O `app` não publica porta em nenhum dos dois.** A rede interna é o único caminho até a
  porta 8000 (ADR 0017).
- **O TLS (Transport Layer Security).** Em produção, o do navegador termina na borda da
  Cloudflare; o Caddy mantém a CA (autoridade certificadora) interna nos dois ambientes, e o
  conector não a verifica (ADR 0027).
- **O nome atendido.** Sai de `PUBLIC_HOST`. Dele o compose deriva `BASE_URL` e `ALLOWED_HOSTS`
  do `app`, ao lado de `BEHIND_TLS_PROXY`, fixada em `"True"`, e de `BASE_URL` sai o issuer.

A imagem é construída em dois estágios sobre `python:3.14-slim` e roda como o usuário
`idp`, UID e GID 10001. O `docker/entrypoint.sh` roda `migrate`, `collectstatic` e `exec
gunicorn`; a conta administrativa não nasce ali, e sim por `createsuperuser` interativo (ADR
0019). O `HEALTHCHECK` deriva os tempos dos tetos da aplicação: 2 s de banco, 4 s de cache e
1 s de folga, dentro de 8 s externos (ADR 0011).

Há também a jornada de construção: a aplicação roda em `runserver` no host, em
`http://localhost:8000`, contra o Postgres e o Redis do compose, sem proxy. Os passos das duas
jornadas estão em `docs/receita.md`.

### 3. Módulos: a fronteira dentro do monólito

```
   ┌────────────────────────── config (a borda) ───────────────────────────┐
   │ settings · urls · views(home, health) · origem · limites · observab.  │
   └──────┬───────────────────────┬────────────────────────────┬───────────┘
          │ OAUTH2_VALIDATOR_CLASS│ rota-sombra /o/logout/     │ origem da
          │ (string, no boot)     │ (import, antes do include) │ requisição
          ▼                       ▼                            ▼
   ┌──────────────────────── accounts (a identidade) ───────────────────────┐
   │ User · IdPOAuth2Validator · LogoutPelaRPView · auditoria · admin       │
   │ páginas · API de conta · revogação · envio · e-mails · sinais          │
   └──────┬──────────────────────────────┬──────────────────────────────────┘
          │ herda / estende              │ auditoria importa de config só
          ▼                              │ a função de origem
   ┌──────────────────────┐   ┌──────────┴────────────┐
   │ oauth2_provider      │   │ axes                  │
   │ (terceiro) protocolo │   │ (terceiro) teto do    │
   │ sob /o/              │   │ login; origem de      │
   └──────────────────────┘   │ config/origem.py      │
                              └───────────────────────┘
```

Cada módulo decide uma coisa:

- **`config`, a borda e a composição.** Não toca o modelo de usuário. Dois arquivos respondem
  perguntas que servem a vários consumidores. `config/origem.py` diz de que endereço veio a
  requisição, e a resposta é única no sistema: servem-se dela a trilha, o limitador e o
  `django-axes` (ADRs 0015, 0018 e 0020). `config/limites.py` limita requisições por origem em
  `/o/token/`, `/o/authorize/`, `/o/device-authorization/`, `/o/logout/`, `/accounts/login/`,
  `/accounts/registrar/`, `/accounts/password_reset/` e nos quatro caminhos de `/api/conta/`,
  sem conhecer pessoa nem conta (ADRs 0016 e 0031). A contagem na janela dele também serve o
  teto por destinatário de `accounts/envio.py`.
- **`accounts`, a identidade.** É dono da pessoa e do que o IdP afirma sobre ela.
  `IdPOAuth2Validator` é o único ponto em que se decidem claims. `LogoutPelaRPView` é o único
  código deste projeto no caminho de um endpoint de protocolo, com revogação restrita à
  `Application` que pede (ADRs 0029 e 0030). A trilha de auditoria grava `sub`, origem,
  procedência e desfecho, nunca e-mail nem valor de token. Desde a ADR 0031, também é dono do
  autoatendimento:
  - as páginas (`paginas.py`, `formularios.py`) recebem toda senha e voltam a destinos fixos da
    SPA;
  - a API (`api.py`) nunca recebe senha e lê a conta só do token;
  - as duas dependem de `envio.py`, `emails.py`, `revogacao.py` e `sinais.py`, e nenhuma importa
    da outra;
  - `accounts` importa de `config` só funções sem identidade: `config.origem` e
    `config.limites.contagem_na_janela`.
- **`oauth2_provider`, o protocolo.** Dependência de terceiro, montada sob `o/` com só três das
  cinco listas de rotas, as de protocolo (ADR 0024). Nenhum método de protocolo é sobrescrito,
  salvo o logout. As outras peças trocadas são templates. Fora de `/o/`, o toolkit serve a API
  de conta pela `ScopedProtectedResourceMetadataView`, e o cadastro entra pelo `prompt=create`
  dele (ADR 0031).
- **`axes`, o teto da tela de login.** A única dependência que entra em `authenticate()`, com
  `AxesStandaloneBackend` antes do `ModelBackend`. Conta falhas por conta e por origem (ADR
  0016). As páginas de conta conferem a senha atual por `authenticate()`, com o e-mail em
  minúsculas, para o `axes` contar as falhas na mesma conta (ADR 0031).

O acoplamento entre `accounts` e o toolkit passa por quatro pontos, e todos falham sem erro
nenhum:

- **`OAUTH2_VALIDATOR_CLASS`.** É um contrato por string. Um caminho errado falha no boot, mas
  a chave ausente emite o `id_token` só com `sub`, e esse `sub` é a chave primária.
- **A rota-sombra de `/o/logout/`.** Ela precisa vir antes do `include`. Fora de ordem, a view
  do toolkit volta a atender, e o "Sair" deixa de revogar.
- **O `dispatch` de `RecursoDaConta`.** Ele chama `View.dispatch` direto, pulando o do mixin do
  toolkit, para não verificar o token duas vezes. A subida do toolkit relê esse método contra o
  dele.
- **`OIDC_RP_INITIATED_REGISTRATION_URL`.** É um nome de rota, resolvido só quando uma pessoa
  sem sessão pede `create`: um nome que não resolve não derruba o boot, e só esse pedido recebe
  500.

### 4. O caminho de um pedido

```
  RP            navegador           IdP (/o/…, /accounts/…)           Postgres / Redis
  │ 1 redirect ──►│── GET /o/authorize/ (code_challenge, S256) ──►│
  │               │◄── 302 /accounts/login/?next=… (sem sessão) ───│
  │               │── POST credenciais ────────────────────────────►│── sessão SSO ──►│
  │               │◄── consentimento (pulado se skip_authorization)│
  │               │◄── 302 redirect_uri?code=…&state=… ────────────│
  │◄── code ──────│                                                │
  │── POST /o/token/ (code, code_verifier) ───────────────────────►│── grant/tokens ─►│
  │◄── access_token, refresh_token, id_token ──────────────────────│
  │── GET /o/.well-known/jwks.json, confere assinatura e iss ─────►│
  │     …                                                          │
  │ 8 "Sair" ──►│── GET /o/logout/ (id_token_hint, destino, state)►│── revoga na App ─►│
  │◄────────────│◄── 302 post_logout_redirect_uri?state=… ─────────│   encerra sessão
```

1. A RP redireciona o navegador para `/o/authorize/` com `code_challenge` e
   `code_challenge_method=S256`.
2. Sem sessão, o toolkit desvia para `/accounts/login/`, carregando o `next`; com
   `prompt=create`, para `/accounts/registrar/`, que abre a sessão ao criar a conta.
3. Autenticada a pessoa, abre-se a sessão de login (SSO, de _Single Sign-On_) no backend
   `cached_db`, que grava no Postgres e lê do Redis (ADR 0005).
4. A tela de consentimento lista os scopes. Na `Application` de primeira parte, com
   `skip_authorization`, ela não aparece (ADR 0021).
5. O IdP redireciona à `redirect_uri` registrada, com `code` e `state`.
6. A RP troca o código em `POST /o/token/`, com o `code_verifier`, e recebe os três tokens.
7. A RP verifica o `id_token` contra o JWKS (JSON Web Key Set) e confere o `iss`, que é
   `{BASE_URL}/o`.
8. No "Sair", a RP manda o navegador a `/o/logout/`. O IdP revoga os tokens da conta naquela
   `Application`, encerra a sessão e devolve o navegador ao destino cadastrado (ADR 0029).

A superfície HTTP própria é esta:

- `/`, `/health` (sem barra final, porque é a URL da sonda), `/accounts/login/`,
  `/accounts/logout/` (só POST) e `/admin/`;
- as páginas de conta, em `accounts/paginas.py`: `/accounts/registrar/`, as quatro de
  recuperação de senha (`/accounts/password_reset/`, `/accounts/password_reset/done/`,
  `/accounts/reset/<uidb64>/<token>/` e `/accounts/reset/done/`), `/accounts/password_change/`,
  `/accounts/email/` e `/accounts/excluir/`;
- a API de conta, em `accounts/api.py`: `/api/conta/`, `/api/conta/confirmacao/`,
  `/api/conta/termos/` e `/api/conta/confirmar/`.

Cada rota de `accounts/` é montada uma a uma, sem `django.contrib.auth.urls`, e
`password_change_done` não existe: a troca de senha volta à SPA. O resto vem do toolkit sob
`/o/`:

- `authorize/`, `token/` e `userinfo/`;
- `logout/`, atendido pela subclasse de `accounts`;
- a descoberta OIDC e o JWKS, sob `.well-known/`;
- device grant, revogação, introspecção e os metadados das RFCs 8414 e 9728, que estão nas
  mesmas listas mas não são usados.

`/o/applications/`, `/o/authorized_tokens/` e `/o/register/` respondem 404: a gestão é do admin
(ADR 0024).

### 5. Onde mora o estado

| Lugar | O que guarda |
| --- | --- |
| Postgres | contas, Applications, grants, tokens, `django_session` e as tentativas que o `axes` conta; volume `pgdata` |
| Redis | cópia quente da sessão, a chave da sonda do `/health`, os contadores de taxa e o de envios por destinatário, com o resumo SHA-256 do endereço na chave; volume `redisdata` |
| Ambiente do processo | a chave privada RSA, a `SECRET_KEY` e a senha do SMTP, fora do banco e da imagem |
| Cookie do navegador | só o identificador da sessão |
| Arquivo, no container | a trilha de auditoria; volume `auditlog`, em `/var/log/idp` |
| Volume do proxy | a CA interna do Caddy, em `caddydata`; sem ele, cada `up` emite por uma CA nova |
| `cloudflared/` do clone de produção | as credenciais do túnel, segredo da mesma classe da chave RSA (ADR 0027) |

O Redis é descartável, porque a sessão sobrevive a `flush` e a reinício dele, e os dois tetos
falham abertos. Mas o IdP não tolera a ausência do Redis: `cached_db` toca o cache a cada
requisição.

### 6. Onde a arquitetura falha em silêncio

- `OAUTH2_VALIDATOR_CLASS` ausente: o `id_token` sai só com `sub`.
- `OIDC_RSA_PRIVATE_KEY` presente e vazia: o JWKS sai vazio, com 200. Ausente, o processo cai na
  leitura das settings, nomeando a variável (ADR 0004).
- `CorsMiddleware` fora do topo do `MIDDLEWARE`: o erro não aparece enquanto a allowlist de CORS
  estiver vazia.
- A rota-sombra de `/o/logout/` depois do `include`: o "Sair" deixa de revogar.
- O endereço fixo do `cloudflared` divergente entre `docker-compose.prod.yml` e
  `docker/Caddyfile`: toda requisição passa a ter a mesma origem, e o limitador tranca todos os
  clientes numa chave só. O comentário do `Caddyfile` descreve esse caso.
- O worker que morre durante o envio: a thread não é fila durável, e o e-mail se perde. A
  pessoa já viu a resposta de sucesso; a saída dela é "reenviar" ou "pedir outro link".
- A falha do SMTP: aparece só no log operacional, como `envio_falhou`. A resposta à pessoa não
  muda.
- O backend de console com `BASE_URL` local: nada sai do servidor, e a mensagem inteira, com
  endereço e link, vai para o stdout. Com `BASE_URL` público, o boot o recusa, como recusa
  `SPA_URL` em loopback; `SPA_URL` pública e errada passa.
- O handler do `axes` em `accounts/tentativas.py` sobrescreve `reset_user_attempts`, método
  interno da biblioteca. Uma subida que o renomeie, ou passe a zerar por outro caminho, faz o
  login voltar a apagar as falhas da origem contra outras contas, sem erro. Voltar
  `AXES_HANDLER` ao handler da biblioteca tem o mesmo efeito, e só o teste do zeramento cai.
- `_password`, atributo privado do Django, renomeado numa subida: o carimbo `senha_alterada_em`
  para, ou passa a marcar o re-hash do login. O comentário do `save()` de `accounts/models.py`
  descreve esse caso.
- As regras do `save()` da conta não alcançam `QuerySet.update()`: escrita em massa no e-mail ou
  no perfil não zera a verificação nem move `updated_at`.
- `SPA_CLIENT_ID` com o valor errado: o boot passa, e toda chamada à API de conta recebe 403
  `aplicacao_nao_autorizada`, inclusive as da SPA.
- `CORS_EXPOSE_HEADERS` ausente: o `fetch` da SPA lê o status e não lê o desafio. O 401 de
  token vencido e o 403 de scope faltando ficam indistinguíveis, e o 429 não diz quanto
  esperar.
- Um caminho da API de conta mudado em `config/urls.py` sem mudar `RATE_LIMIT_POR_CAMINHO` e
  `CORS_URLS_REGEX`: o caminho perde o teto ou o CORS.

---

## III. Apêndice

### Índice das ADRs

Uma decisão por arquivo em `docs/adr/`. ADR aceita é imutável: decisão que mudou vira ADR
nova. O formato está em `docs/adr/template-adr.md`.

As ADRs guardam o que se sabia e se decidiu na data delas; este índice guarda o que ajuda a
lê-las hoje. Uma ADR aceita só é editada para restabelecer a verdade: em 2026-09-29, as
referências a documentos de trabalho que não existem mais (runbook, roadmap, planos, contrato de
back-end, fichas de robustez) e os caminhos para o diretório da SPA foram suprimidos, sem mudar
decisão. Cada ADR editada traz, sob o status, uma linha de revisão. A 0004 ainda cita
`scripts/gen_dev_key.sh`: a frase inteira é o que a 0028 emenda.

| Assunto | ADR | Revisões depois do aceite |
| --- | --- | --- |
| Plataforma: Django 5.2 sobre Python 3.14 | `0001-adotar-django-5-2-lts-sobre-python-3-14.md` | revisão de prosa (a6b5014, 2026-09-03) |
| O toolkit como servidor de autorização — **emendada pela 0024 e pela 0030** | `0002-usar-django-oauth-toolkit-como-servidor-de-autorizacao.md` | revisão de prosa (a6b5014, 2026-09-03) |
| `User` customizado com e-mail como identificador — **emendada pela 0031** (proposta) | `0003-modelar-identidade-em-user-customizado-com-email-como-identificador.md` | revisão de prosa (a6b5014, 2026-09-03) |
| RS256 e a custódia da chave privada — **emendada pela 0028** | `0004-assinar-tokens-com-rs256-e-custodiar-a-chave-privada-no-ambiente.md` | revisão de prosa (a6b5014, 2026-09-03) |
| A sessão SSO em `cached_db` | `0005-manter-a-sessao-sso-em-sessao-django-com-backend-cached-db.md` | revisão de prosa (a6b5014, 2026-09-03) |
| Container único orquestrado por docker-compose | `0006-empacotar-o-idp-como-container-unico-orquestrado-por-docker-compose.md` | revisão de prosa (a6b5014, 2026-09-03) |
| O issuer em `{BASE_URL}/o` | `0007-fixar-o-issuer-do-idp-em-base-url-barra-o.md` | revisão de prosa (a6b5014, 2026-09-03) |
| WhiteNoise sem manifesto de hash | `0008-servir-estaticos-com-whitenoise-sem-manifesto-de-hash.md` | revisão de prosa (a6b5014, 2026-09-03); supressão de referências voláteis (2026-09-29) |
| O `/health` isolado da sessão e do usuário | `0009-isolar-a-view-de-health-da-sessao-e-do-usuario.md` | revisão de prosa (a6b5014, 2026-09-03) |
| A isenção de `/health` no redirecionamento para HTTPS | `0010-isentar-health-do-redirecionamento-para-https.md` | revisão de prosa (a6b5014, 2026-09-03); supressão de referências voláteis (2026-09-29) |
| O teto de tempo do `/health` e o `HEALTHCHECK` derivado dele | `0011-dar-teto-de-tempo-ao-health-e-derivar-o-healthcheck-dele.md` | revisão de prosa (a6b5014, 2026-09-03) |
| O log operacional em JSON, com identificador de requisição — **emendada pela 0014** | `0012-emitir-o-log-operacional-em-json-com-identificador-de-requisicao.md` | supressão de referências voláteis (2026-09-29) |
| A trilha de auditoria dos quatro sinais, em arquivo durável — **ampliada pela 0016, pela 0029 e pela 0031**; **estendida pela 0018**; **emendada pela 0031** (proposta) | `0013-registrar-a-trilha-de-auditoria-dos-quatro-sinais-em-arquivo-duravel.md` | supressão de referências voláteis (2026-09-29) |
| O tempo de vida do identificador de requisição; emenda à 0012 | `0014-manter-o-identificador-de-requisicao-ate-a-requisicao-seguinte.md` | supressão de referências voláteis (2026-09-29) |
| A origem do cliente resolvida num ponto único | `0015-resolver-a-origem-do-cliente-num-ponto-unico.md` | supressão de referências voláteis (2026-09-29) |
| O limite de taxa nas três portas de autenticação — **emendada pela 0031** (proposta) | `0016-limitar-a-taxa-na-superficie-de-autenticacao.md` | supressão de referências voláteis (2026-09-29) |
| O proxy de terminação TLS no compose, e só ele publicado — emenda a **0006**; **emendada pela 0027** (antes pela 0026, substituída) | `0017-terminar-o-tls-num-proxy-declarado-no-compose.md` | supressão de referências voláteis (2026-09-29) |
| A procedência do endereço em cada linha da trilha — estende a **0013** | `0018-declarar-a-procedencia-do-endereco-em-cada-linha-da-trilha.md` | supressão de referências voláteis (2026-09-29) |
| O superusuário criado por comando explícito — emenda a **0006** | `0019-criar-o-superusuario-por-comando-explicito-fora-do-boot.md` | supressão de referências voláteis (2026-09-29) |
| O endereço colapsado pelo `docker-proxy` marcado em cada linha da trilha — emenda a **0018**; **emendada pela 0027** | `0020-marcar-na-linha-o-endereco-colapsado-pelo-docker-proxy.md` | supressão de referências voláteis (2026-09-29) |
| O consentimento pulado na `Application` de primeira parte, por `skip_authorization` | `0021-pular-o-consentimento-na-application-de-primeira-parte-por-skip-authorization.md` | supressão de referências voláteis (2026-09-29) |
| O CORS por origem exata, uma por ambiente; previews da Vercel fora | `0022-liberar-o-cors-por-origem-exata-e-deixar-os-previews-da-vercel-fora.md` | supressão de referências voláteis (2026-09-29) |
| Sem cadastro nem edição de perfil nesta fase; contas criadas no admin — **a substituir pela 0031**, no aceite dela | `0023-nao-oferecer-cadastro-nem-perfil-nesta-fase-e-manter-a-criacao-de-contas-no-admin.md` | supressão de referências voláteis (2026-09-29) |
| A montagem sob `/o/` só das listas de protocolo do toolkit — emenda a **0002**; **emendada pela 0030** | `0024-montar-sob-o-so-as-listas-de-protocolo-do-django-oauth-toolkit.md` | supressão de referências voláteis (2026-09-29) |
| O issuer de produção congelado na forma `https://<PUBLIC_HOST>/o` — cumpre a condição da **0007** | `0025-congelar-o-issuer-de-producao-na-forma-https-public-host-barra-o.md` | supressão de referências voláteis (2026-09-29) |
| A exposição na AWS (Amazon Web Services) por um salto de proxy só, com ACME (Automatic Certificate Management Environment) e 80/443 fora de loopback por override de compose — emenda a **0017**; **substituída pela 0027** | `0026-expor-o-idp-na-aws-por-um-salto-de-proxy-so-com-acme-e-80-443-fora-de-loopback.md` | supressão de referências voláteis (2026-09-29) |
| O IdP de produção servido da máquina do dono pelo Cloudflare Tunnel, sem porta de entrada — substitui a **0026**; emenda a **0017** e a **0020** | `0027-servir-o-idp-de-producao-da-maquina-local-pelo-cloudflare-tunnel-sem-porta-de-entrada.md` | supressão de referências voláteis (2026-09-29) |
| A chave de assinatura em RSA 3072, pelo gerador único de segredos — emenda a **0004** | `0028-gerar-a-chave-de-assinatura-em-rsa-3072-pelo-gerador-unico-de-segredos.md` | — |
| O logout iniciado pela RP ligado, com revogação restrita à `Application` e retorno só a destino cadastrado — amplia a **0013**; par com a ADR 0019 da SPA, aceitas no mesmo dia; **emendada pela 0031** (proposta) | `0029-ligar-o-logout-iniciado-pela-rp-com-revogacao-restrita-a-application.md` | — |
| A rota de logout do toolkit sombreada por uma subclasse da view, montada antes do `include` — emenda a **0002** e a **0024** | `0030-sombrear-a-rota-de-logout-do-toolkit-com-uma-subclasse-da-view.md` | — |
| O autoatendimento de conta: cadastro por `prompt=create`, recuperação, troca de senha e de e-mail, exclusão, API de conta e `sub` em UUID — substitui a **0023**; emenda a **0003**, a **0013**, a **0016** e a **0029**; par com a ADR 0020 da SPA, que substitui a 0012 dela; as duas mudam de status no mesmo ato | `0031-abrir-o-autoatendimento-de-conta-com-as-telas-de-senha-no-idp-e-o-sub-em-uuid.md` | — |

### Decisões em vigor sem ADR

- `CORS_URLS_REGEX`, hoje `r"^/(?:o|api/conta)/"`: a ADR 0022 declara a questão fora do seu
  escopo. A 0024 registra que ela se apoia no prefixo `/o/`. Decidida pela 0031, proposta; sai
  desta lista no aceite.
- `AUTH_PASSWORD_VALIDATORS` declarada: a 0023 registra só que a declaração vem fora dela.
- Cookie de sessão pelos defaults do Django: `SESSION_COOKIE_SAMESITE`, `SESSION_COOKIE_AGE` e
  `SESSION_EXPIRE_AT_BROWSER_CLOSE` não são declarados. A 0021 os deixou como pendência. Risco
  aceito: uma atualização do Django pode trocá-los em silêncio.
- `refresh_token` sem expiração: `REFRESH_TOKEN_EXPIRE_SECONDS` fica no `None` do toolkit, que é
  o que a §3 de `docs/nucleo-idp.md` publica. A 0021 e a 0026 o deixaram como pendência; o risco
  aceito está em `docs/seguranca.md`.

As quatro foram fechadas pelo status quo em 2026-09-30, sem ADR. Mudar qualquer uma é ADR nova,
e nas duas últimas a mudança toca a SPA.

### Pares com a SPA

| Tema | IdP | SPA |
| --- | --- | --- |
| Issuer | 0007, 0025 | 0017 |
| Sessão no reload e consentimento | 0021 | 0014 |
| Páginas de conta e autoatendimento | 0023, a substituir pela 0031 | 0012, a substituir pela 0020 |
| CORS e previews | 0022 | 0016 |
| Túnel da Cloudflare | 0027 | 0018 |
| Logout pela RP | 0029, 0030 | 0019 |

Quem decidiu depois cita quem decidiu antes; a citação mútua só existe nos pares propostos
juntos. Este índice registra o par nos dois sentidos. O par do autoatendimento foi proposto
junto, e a 0031 e a 0020 da SPA citam uma à outra.

O par do túnel não mudou de status no mesmo ato: a 0027 foi aceita em 2026-09-28, e a 0018 da
SPA em 2026-09-29, que registra a data desta.

### O "passo NN" nos comentários

Alguns comentários de código citam "passo NN" do roadmap; as ADRs 0008 e 0010, que também citavam, falam agora do "roteiro de construção da época". Os comentários
estão no `Dockerfile`, no `docker-compose.yml`, em `config/settings.py`, em `accounts/models.py`,
no `.env.example`, no `.gitignore` e no `.dockerignore`. O roadmap eram os treze arquivos de `docs/roadmap/`,
removidos no commit `b7774d5` depois de cumpridos, e cada um segue legível no histórico, por
exemplo em `git show b7774d5^:docs/roadmap/09-telas-e-estaticos.md`. Onde o código diverge
deliberadamente de um passo, vale o código.

### Onde buscar mais

| Assunto | Arquivo |
| --- | --- |
| O que é um IdP, as invariantes, o contrato com toda RP | `docs/nucleo-idp.md` |
| O contrato de quem integra uma RP: registro, fluxo, claims, verificação, tempos de vida | `docs/integracao-rp.md` |
| As duas jornadas, do `.env` ao fluxo PKCE fechado à mão, e as tarefas do dia a dia | `docs/receita.md` |
| O que o IdP protege, o que não protege e a fronteira de exposição | `docs/seguranca.md` |
| Níveis de teste, o que cada arquivo garante e o que não é coberto | `docs/testes.md` |
| O log operacional, a trilha de auditoria, o que falha em silêncio e o que falta medir | `docs/observabilidade.md` |
| O motivo de cada valor de configuração | comentários de `config/settings.py` |
| Regras de trabalho e restrições do repositório | `CLAUDE.md` |
| Convenções entre agentes, incluindo as de ADR | `.claude/PROTOCOLO-AGENTES.md` |
