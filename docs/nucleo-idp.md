# Núcleo do IdP — o monólito e as relying parties

| Campo | Valor |
| --- | --- |
| Componente | provedor de identidade (IdP, de _Identity Provider_) OpenID Connect (OIDC) |
| Forma | monólito: uma aplicação Django implantável, orquestrada por Docker Compose |
| Clientes | relying parties (RPs), hoje só a aplicação de página única (SPA, de _Single-Page Application_) |
| Produção | máquina do dono, publicada por túnel nomeado da Cloudflare (ADR 0027) |
| Decisões | `docs/adr/`, uma ADR (Architecture Decision Record) por arquivo; índice em `docs/arquitetura.md` |

Este documento é espelho e guia. Espelho: resume o que o projeto é, verificado contra o código
em 2026-10-01. Guia: diz o que uma mudança precisa preservar e o que uma RP nova precisa
receber. Onde há detalhe em outro arquivo, aponta em vez de repetir. Quando este texto e o
código divergirem, vale o código; quando divergir de uma ADR, vale a ADR.

---

## 1. O que é um monólito IdP

Um IdP possui as pessoas usuárias, autentica as credenciais delas e atesta a identidade para
outras aplicações. Essas aplicações, as relying parties, não gerenciam senha: delegam a
autenticação ao IdP e confiam no que ele responde. É o formato do botão "Entrar com o Google",
em que o Google é o IdP e o site é a RP.

Monólito quer dizer que modelo de usuário, telas de login e consentimento, servidor de
autorização, emissão de token e endpoints de descoberta vivem numa aplicação só. A escolha é
por compactação: menos peças móveis, uma fronteira de segurança e um deploy.

Dois fatos definem o comportamento:

- **A senha só trafega dentro do IdP.** A RP nunca vê a credencial; recebe um token que afirma
  quem é a pessoa.
- **Sessão e token coexistem.** O IdP mantém uma sessão de login server-side (SSO, de _Single
  Sign-On_), para que a pessoa não redigite a senha a cada volta, e emite tokens assinados que
  a RP valida sozinha com a chave pública do JWKS (JSON Web Key Set).

---

## 2. Invariantes

Mudança que contrarie um destes itens exige ADR, e, se tocar o contrato da §3, ADR nos dois
projetos.

- **N1.** Uma aplicação implantável só. Identidade, telas, protocolo e descoberta não se
  separam em serviços.
- **N2.** Escopo de host único e uma réplica. O TLS (Transport Layer Security) do navegador
  termina fora da aplicação: na borda da Cloudflare em produção, no Caddy do compose na jornada
  de container (ADRs 0017 e 0027). O Gunicorn fala texto claro na rede interna.
- **N3.** Autenticação só por redirecionamento de navegador, com Authorization Code e PKCE
  (Proof Key for Code Exchange) restrito a `S256`. Login e consentimento são telas do próprio
  IdP.
- **N4.** A identidade é o `accounts.User`, com e-mail como identificador de login, gravado em
  minúsculas (ADRs 0003 e 0031). Contas nascem no admin ou pelo cadastro, e a pessoa edita a
  própria conta pelas páginas do IdP e pela interface de programação (API, de _Application
  Programming Interface_) de conta (ADR 0031).
- **N5.** Assinatura assimétrica, RS256 (RSA, de Rivest–Shamir–Adleman, com SHA-256), com uma
  chave só, custodiada no `.env` (ADRs 0004 e 0028). O `.env` é untracked e sem cópia no
  repositório; perdê-lo é perder a identidade do IdP naquele clone.
- **N6.** Claims decididas num ponto só: `accounts/oauth_validators.py`, por
  `get_additional_claims()`, inclusive o `sub`. Nenhum método de protocolo do
  `django-oauth-toolkit` é sobrescrito, com uma exceção deliberada: a rota `/o/logout/` (ADR
  0030). O `dispatch` de `RecursoDaConta`, a view de recurso da API de conta em
  `accounts/api.py`, também é sobrescrito, e não é método de protocolo: confere o Bearer pelo
  toolkit, uma vez, e acrescenta as recusas por Application e por conta inativa (ADR 0031).
- **N7.** O issuer é `{BASE_URL}/o`, e em produção tem a forma congelada
  `https://<PUBLIC_HOST>/o` (ADRs 0007 e 0025).

---

## 3. O contrato com toda RP

É contrato público: cada RP guarda issuer, descoberta e JWKS em cache. Mudar uma linha desta
tabela não é refatoração, é quebra de contrato com terceiro.

| Item | Valor | Onde se verifica |
| --- | --- | --- |
| Issuer | `{BASE_URL}/o`, sem barra final | `OIDC_ISS_ENDPOINT` em `config/settings.py` |
| Descoberta | `{issuer}/.well-known/openid-configuration`, com `authorization`, `token`, `userinfo`, `end_session` e `jwks_uri` | `tests/test_discovery.py` |
| PKCE | obrigatório, só `S256` | `PKCE_REQUIRED` e `COMPLIANT_BCP_RFC9700_PKCE_METHOD` |
| Scopes | exatamente `openid`, `profile`, `email` e `conta`; `conta` só a API de conta exige | `OAUTH2_PROVIDER["SCOPES"]`; `tests/test_discovery.py` (igualdade do conjunto) |
| Claims | `sub`: o UUID (_Universally Unique Identifier_) versão 4 da conta, em texto minúsculo com hífens, e não a chave primária. Com `profile`: `name` (pode ser `""`), `nickname` (presente mesmo vazia) e `updated_at` (segundos desde 1970, move só com nome, apelido, e-mail ou verificação). Com `email`: `email`, em minúsculas, e `email_verified`, booleana, que nasce falsa | `accounts/oauth_validators.py`, ADR 0031 |
| Cadastro | `prompt=create` em `/o/authorize/` leva a pessoa sem sessão a `/accounts/registrar/` e, criada a conta, de volta ao mesmo pedido sem `create`; com sessão, `create` não muda nada. `create` está em `prompt_values_supported` | `OIDC_RP_INITIATED_REGISTRATION_*` em `config/settings.py`, ADR 0031 |
| Assinatura | RS256, uma chave RSA com `kid` no JWKS | `tests/test_jwks.py` |
| `userinfo` | as mesmas claims; token inválido → 401 | oauthlib |
| `redirect_uri` | igualdade exata com a registrada | `tests/test_authorize_guards.py` |
| Logout pela RP | `end_session_endpoint` = issuer + `/logout/`; revoga os tokens da conta só na `Application` que pede e encerra a sessão | ADRs 0029 e 0030 |
| Tempos de vida | `code` 60 s; `access_token` e `id_token` 10 h; `refresh_token` sem expiração | defaults do `django-oauth-toolkit` 3.4.1 |
| CORS (Cross-Origin Resource Sharing) | origem exata, sem curinga; `CORS_URLS_REGEX = r"^/(?:o|api/conta)/"`; `CORS_EXPOSE_HEADERS` com `WWW-Authenticate` e `Retry-After`; `CorsMiddleware` no topo do `MIDDLEWARE` | `config/settings.py`; origem exata pela ADR 0022; o prefixo `api/conta/` e os cabeçalhos expostos pela ADR 0031 |
| API de conta | `GET` e `PATCH` em `/api/conta/`, `POST` em `/api/conta/confirmacao/` e em `/api/conta/termos/`, sob Bearer só no cabeçalho `Authorization`, com o scope `conta` e um token da Application da SPA (`SPA_CLIENT_ID`). `GET /api/conta/confirmar/?t=` é o link do e-mail, sem autenticação. 401 e 403 de scope sem corpo, com `WWW-Authenticate: Bearer` e `resource_metadata`; 403 com `{"codigo": "aplicacao_nao_autorizada"}` ou `{"codigo": "conta_inativa"}`; 400 na forma `{"erros": {"<campo>": [{"codigo", "mensagem"}]}}`, com `geral/json_invalido`; `null` no `PATCH` limpa o campo | `accounts/api.py`, `tests/test_api_conta.py`, ADR 0031 |
| Páginas do IdP | cadastro em `/accounts/registrar/`; recuperação em `/accounts/password_reset/`, com link de uma hora e uso único para `/accounts/reset/<uidb64>/<token>/`; troca de senha em `/accounts/password_change/`; troca de e-mail em `/accounts/email/`; exclusão em `/accounts/excluir/`. Em português e com proteção contra CSRF (_Cross-Site Request Forgery_). Cadastro, recuperação e redefinição são anônimas; troca de senha, troca de e-mail e exclusão exigem a sessão do IdP, e o cadastro a abre; das páginas de conta, só o cadastro lê `next`, e as outras voltam a destino fixo da SPA | `config/urls.py`, `accounts/paginas.py`, ADR 0031 |
| Rotas da SPA conhecidas pelo IdP | `{SPA_URL}/`, `/?email=confirmado`, `/?email=invalido`, `/?conta=desativada`, `/?conta=apagada`, `/app/conta`, `/app/conta?aviso=senha-trocada`, `/app/conta?aviso=email-trocado`, `/termos` e `/privacidade`; mudar uma delas na SPA quebra a volta | `accounts/paginas.py`, `accounts/api.py`, `templates/registration/` |
| Efeitos colaterais | troca de senha, redefinição e exclusão revogam os tokens da conta em todas as Applications. A troca de senha mantém a sessão em que foi feita e derruba as outras; a redefinição derruba todas; a redefinição também liga `email_verified`, porque quem abriu o link leu a caixa do endereço; a troca de e-mail mantém o `sub` e as sessões e zera `email_verified` | `accounts/revogacao.py`, `accounts/paginas.py`, ADR 0031 |
| Ordem de implantação | o IdP implanta antes da SPA: antes dele, a SPA receberia `invalid_scope` ao pedir `conta` e 400 em "Criar conta" | ADR 0031; procedimento em `docs/receita.md` |
| Transição do `sub` | a implantação troca o `sub` de toda conta pelo UUID, sem volta. A sessão da SPA aberta antes dela mostra erro até o reload, porque o `id_token` traz o `sub` antigo e o `userinfo`, o novo. A trilha de auditoria fica com duas populações: o `id` interno antes, o UUID depois | ADR 0031 |

O caminho completo de um pedido, de `/o/authorize/` ao "Sair", está em `docs/arquitetura.md`;
o que a RP verifica no token, em `docs/integracao-rp.md`.

---

## 4. Como uma RP entra

Toda RP entra pelo admin, uma `Application` por ambiente. Nada no código muda para acolher uma
RP nova; muda a configuração.

### 4.1 O que a RP entrega e o que recebe

| A RP entrega | O IdP devolve |
| --- | --- |
| origem, para `CORS_ALLOWED_ORIGINS` | `issuer` |
| `redirect_uri` | `client_id` |
| `post_logout_redirect_uri` | |

Os valores vão literais. O `post_logout_redirect_uri` tem o caminho da landing, com a barra
final; a entrada de CORS é origem, sem barra.

### 4.2 A `Application`

- `client_type` `public` e `authorization_grant_type` `authorization-code`.
- `algorithm` `RS256`. Vazio, o IdP emite o `code` e não emite `id_token`, sem erro.
- Uma `redirect_uri`. Produção e desenvolvimento nunca na mesma `Application`: atrás do proxy,
  `ALLOWED_REDIRECT_URI_SCHEMES` só aceita `https`.
- Um `post_logout_redirect_uris`. O admin não valida o campo: vazio, em `http` atrás do proxy
  ou sem a barra, ele grava sem aviso, e o "Sair" da RP termina na tela de erro do IdP.
- `skip_authorization=True` só para RP de primeira parte (ADR 0021). O default global continua
  pedindo consentimento.

### 4.3 O que a primeira RP assume

A SPA é cliente público, guarda tokens só em memória e volta a `/o/authorize/` a
cada reload, contando com o cookie de sessão do IdP (`SameSite=Lax`) para voltar sem senha.
Ela ignora o `refresh_token`, e é a única RP cujo token a API de conta aceita. Daí duas travas
deste lado: `SESSION_COOKIE_SAMESITE` não vai a
`Strict`, e passar a usar o `refresh_token` é ADR cruzada. O lado dela está em
`docs/spa-nucleo.md` e `docs/contrato-idp.md`, ambos da SPA.

### 4.4 Uma segunda RP

O "Sair" de uma RP revoga só os tokens dela, mas encerra a sessão do IdP inteira: a outra RP
perde a volta sem senha (ADR 0029). A entrada de uma segunda RP é o gatilho para rever esse
alcance, além de pedir a própria `Application`, a própria origem no CORS e o próprio
`post_logout_redirect_uris`. Ela não usa a API de conta: o token dela recebe 403
`aplicacao_nao_autorizada`, ainda que traga o scope `conta`.

---

## 5. O núcleo de tecnologias

| Peça | Escolha | Por que | ADR |
| --- | --- | --- | --- |
| Plataforma | Python 3.14 e Django 5.2 LTS (_Long-Term Support_) | as telas de login e consentimento são templates server-side | 0001 |
| Servidor de autorização | `django-oauth-toolkit` 3.4.1, montado sob `/o/` só com as listas de protocolo | authorization code, PKCE, descoberta, JWKS e logout prontos | 0002, 0024 |
| Identidade | `User` customizado, e-mail como login | o IdP é dono da pessoa; trocar o modelo depois é caro | 0003 |
| Hash de senha | Argon2 (`argon2-cffi`) | o IdP é quem verifica a credencial | — |
| Sessão SSO | backend `cached_db`: grava no Postgres, lê do Redis | a sessão sobrevive à perda do cache | 0005 |
| Banco | PostgreSQL | usuários, `Applications`, grants e tokens com integridade transacional | — |
| Configuração | `django-environ` e `.env`, sem default no código | chave e segredos fora do código | 0004 |
| Aplicação | Gunicorn, três workers, atrás do Caddy | monólito síncrono; TLS fora do processo | 0006, 0017 |
| Estáticos | WhiteNoise, sem manifesto de hash | serve o CSS das telas sem outro servidor | 0008 |
| CORS | `django-cors-headers`, origem exata | a RP chama `/o/token/`, `/o/userinfo/` e a API de conta por `fetch` | 0022, 0031 |
| E-mail | SMTP (_Simple Mail Transfer Protocol_) pelo backend do Django, numa thread depois do commit | confirmação, redefinição e avisos de conta sem segurar a resposta | 0031 |
| Limite de taxa | middleware próprio por origem, e `django-axes` na tela de login | protege a superfície de autenticação | 0015, 0016 |
| Observabilidade | log JSON com identificador de requisição e trilha de auditoria em arquivo | diagnóstico e prova de quem autenticou | 0012 a 0014, 0018, 0020 |
| Saúde | `/health` isolado de sessão e usuário, com teto de tempo | o `HEALTHCHECK` do compose deriva dele | 0009 a 0011 |
| Entrada de produção | `cloudflared` no override `docker-compose.prod.yml` | nenhuma porta publicada na máquina do dono | 0027 |

A fronteira entre os módulos `config`, `accounts`, `oauth2_provider` e `axes` está em
`docs/arquitetura.md`.

---

## 6. Proibições

- Mudar qualquer linha da §3 sem ADR nos dois projetos.
- Curinga, regex, `CORS_ALLOW_ALL_ORIGINS` ou `*.vercel.app` no CORS.
- Copiar o `.env` de desenvolvimento para produção; rodar `git clean -xd` num clone com `.env`.
- Em produção: porta publicada; comando do compose sem os dois `-f`; `down -v`,
  `docker volume prune` ou `docker system prune --volumes`. Agentes não operam o diretório de
  produção.
- `trycloudflare.com` como nome do IdP: fere a forma congelada do issuer (ADR 0025).
- Versionar as credenciais do túnel; tag móvel no `cloudflared` ou no Caddy.

---

## 7. Dívidas abertas

Cada uma é tarefa própria, com ADR. O cookie de sessão pelos defaults e o `refresh_token` sem
expiração foram fechados pelo status quo e estão em `docs/arquitetura.md`, "Decisões em vigor
sem ADR".

- Rotação da chave sem disrupção por `OIDC_RSA_PRIVATE_KEYS_INACTIVE`: publica mais de uma
  chave no JWKS, o que muda a §3 e pede ADR nos dois projetos (levantamento em
  `git show 8caf117:docs/robustez-info.md`, §2.11).
- A revisão do alcance do logout, quando entrar a segunda RP (§4.4).
- `is_active` fora do `userinfo` e do refresh: o toolkit não confere a conta nesses dois, e a
  conta desativada pelo admin continua a receber claims e a renovar token até ele expirar. Só a
  API de conta recusa (ADR 0031).
- `DEFAULT_SCOPES` do toolkit é `["__all__"]`, e não há scope por Application: uma RP que omita
  `scope` recebe `conta`. A recusa por `client_id` no `dispatch` da API fecha o caso; declarar o
  default é decisão à parte.

---

## 8. Onde buscar mais

| Assunto | Arquivo |
| --- | --- |
| Módulos, fronteiras, caminho de um pedido, índice das ADRs | `docs/arquitetura.md` |
| O que uma RP verifica no token e como integra | `docs/integracao-rp.md` |
| Subir o stack, registrar a `Application`, fluxo PKCE à mão | `docs/receita.md` |
| Sintoma, causa e correção; operação de produção pelo túnel, no estado de 2026-09-29 | `git show 8caf117:docs/runbook.md` (histórico) |
| O que o IdP protege e o que não protege | `docs/seguranca.md` |
| O que a suíte cobre | `docs/testes.md` |
| O que o log e a trilha registram, e o que falta medir | `docs/observabilidade.md` |
| Os dois projetos consolidados antes do deploy | `../pre-deploy.md` |
| Regras de trabalho | `CLAUDE.md` |
