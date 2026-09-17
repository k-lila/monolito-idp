# Contrato do back-end — o que o `nova_api` deve cumprir para integrar a `nova_api_SPA`

| Campo | Valor |
| --- | --- |
| Destinatário | projeto `nova_api` (provedor de identidade, IdP) |
| Contraparte | projeto `nova_api_SPA` (relying party, RP), que recebe o `contrato-frontend.md` |
| Origem | levantamento de 2026-09-16 (`contrato-geral.md`, `desavencas-parciais.md`, `desavencas.md`, na raiz `idp/`) |
| Ambientes | produção: IdP na AWS, SPA na Vercel (prioritário) · desenvolvimento: tudo em `localhost` |
| Critério de pronto | a checklist da seção 9 inteira marcada |

Este documento diz **o que** o IdP precisa oferecer, configurar e decidir para que a SPA feche o
fluxo OpenID Connect (OIDC) contra ele. **Como** fazer cada item é decisão do projeto, dentro das
próprias regras (`CLAUDE.md`, ADRs — Architecture Decision Records — imutáveis, relatório antes
de alterar código). Onde este documento pede uma decisão, a recomendação vem com a razão; a
decisão em si é registrada em ADR (seção 8).

---

## 1. Quem é a contraparte

A SPA (Single-Page Application, aplicação de página única) roda **no navegador**, em origem
diferente da do IdP — `https://<spa>` na Vercel em produção, `http://localhost:5173` em
desenvolvimento. Ela:

- é cliente **público**: não guarda `client_secret`; a prova de posse é o PKCE (Proof Key for
  Code Exchange) com `S256`;
- usa o fluxo Authorization Code: redireciona o navegador para `/o/authorize/`, recebe `code` em
  `/callback`, troca o `code` em `/o/token/` **por `fetch` a partir do navegador** (requisição
  cross-origin, sujeita a CORS — Cross-Origin Resource Sharing);
- lê `authorization_endpoint`, `token_endpoint`, `userinfo_endpoint` e `jwks_uri` do documento
  de descoberta; só o `issuer` entra por configuração;
- pede sempre `scope=openid profile email` e envia `state` e `nonce`;
- guarda tokens **só em memória**: todo reload da página a leva de volta a `/o/authorize/`, e
  ela conta com a sessão do IdP (cookie) para voltar sem senha;
- chama `GET /o/userinfo/` com `Authorization: Bearer` a cada entrada na área autenticada, e
  trata **401** como "token recusado, re-autenticar";
- vai passar a verificar a assinatura do `id_token` com a chave do `jwks_uri`, e a comparar
  `iss` com o issuer configurado e `aud` com o `client_id`;
- faz logout **só local** e avisa a pessoa que a sessão no IdP continua; não usa iframe algum
  (sem check-session, sem silent renew);
- **não** terá cadastro nem edição de perfil, nem link para páginas assim no IdP (decisão da
  seção 5.3).

O que a SPA assume sobre o IdP está escrito em `nova_api_SPA/docs/contrato-frontend.md` §1
e `plano-pre-implementacao.md` §3. Este documento é a versão conferida contra o código.

---

## 2. O que já está certo e não pode mudar

Tudo abaixo foi verificado no código do IdP e é exatamente o que a SPA consome. É **contrato
público**: mudar qualquer linha é quebrar a RP, não refatorar.

| Item | Como está | Onde |
| --- | --- | --- |
| Forma do issuer | `{BASE_URL}/o`, sem barra final | `OIDC_ISS_ENDPOINT`, ADR 0007 |
| Descoberta | `{issuer}/.well-known/openid-configuration` (forma OIDC Discovery 1.0) | `tests/test_discovery.py` |
| Endpoints na descoberta | `authorization_endpoint`, `token_endpoint`, `userinfo_endpoint`, `jwks_uri` | idem |
| PKCE | obrigatório, só `S256`; `plain` e ausência recusados | `PKCE_REQUIRED`, `COMPLIANT_BCP_RFC9700_PKCE_METHOD` |
| Scopes | exatamente `openid`, `profile`, `email` | `OAUTH2_PROVIDER["SCOPES"]` |
| Claims | `sub` (chave primária, string), `name` (`get_full_name()`, **pode ser `""`**), `email`; nada além | `accounts/oauth_validators.py` |
| `email_verified` | **não** é emitida | idem |
| Assinatura | RS256, uma chave RSA com `kid` no JWKS (JSON Web Key Set); `kid` do cabeçalho casa | `tests/test_jwks.py` |
| `userinfo` | mesmas claims sob os mesmos scopes; token inválido → **401** (RFC 6750) | oauthlib |
| Logout pela RP | desligado; `end_session_endpoint` ausente da descoberta | `OIDC_RP_INITIATED_LOGOUT_ENABLED=False` |
| `redirect_uri` | igualdade exata | `tests/test_authorize_guards.py` |
| Tempos de vida | `code` 60 s; `access_token` e `id_token` 10 h; `refresh_token` sem expiração, rotacionado a cada uso | defaults do DOT 3.4.1 |
| `CorsMiddleware` | no topo do `MIDDLEWARE`, acima de tudo que emite resposta (limitador, segurança) | `config/settings.py` |
| Token endpoint | aceita cliente público sem secret; `csrf_exempt` | DOT |

A SPA **ignora** o `refresh_token` (nunca renova) e o `expires_at`; se um dia for usá-los, será
por ADR cruzada. Nada aqui precisa mudar por causa disso.

---

## 3. O que a SPA precisa receber deste projeto

Quatro valores, por ambiente. Sem eles a SPA não sobe (o boot dela falha sem variável).

| Valor | Produção | Desenvolvimento | Quem gera |
| --- | --- | --- | --- |
| `issuer` | `https://<dominio-do-idp>/o` | `http://localhost:8000/o` | este projeto (seção 4.1) |
| `client_id` | o da `Application` de produção | o da `Application` de dev | este projeto (seção 5.1) |
| Origem liberada no CORS | `https://<spa>` | `http://localhost:5173` | este projeto configura; valor vem da SPA |
| `redirect_uri` registrada | `https://<spa>/callback` | `http://localhost:5173/callback` | este projeto registra; valor vem da SPA |

E o que este projeto **recebe** da SPA: a origem e a `redirect_uri` de cada ambiente, literais
(esquema, host, porta, path, sem barra final). O `contrato-frontend.md` pede à SPA que os
entregue.

---

## 4. Produção: expor o IdP na AWS

Hoje o IdP é sandbox em `127.0.0.1` com certificado de autoridade certificadora (CA) local. Para
a SPA na Vercel alcançá-lo, ele precisa ter nome público, HTTPS que o navegador aceite e a
topologia que o código já mediu.

### 4.1 Issuer com domínio próprio

- Fixar o nome público num **domínio seu** (ex.: `idp.<seu-dominio>`), apontado por DNS para a
  instância. `PUBLIC_HOST=idp.<seu-dominio>` no `.env` de produção; o compose deriva
  `BASE_URL`, `ALLOWED_HOSTS` e `BEHIND_TLS_PROXY=True`.
- O issuer resultante, `https://idp.<seu-dominio>/o`, é o valor que vai para a SPA e que **congela
  na primeira integração** (ADR 0007 pede confirmação explícita antes disso — é agora).
- Não usar nome atribuído pela AWS (`*.amazonaws.com`): é reciclável para outro cliente e não
  recebe certificado público.

### 4.2 HTTPS público

- Trocar `tls internal` do `docker/Caddyfile` por emissão automática (ACME — Automatic
  Certificate Management Environment, Let's Encrypt), que é o default do Caddy sem a diretiva.
- Publicar 80/443 em `0.0.0.0` no `docker-compose.yml` (edição deliberada, prevista na ADR
  0017). Security group: só 80/443 da internet; SSH restrito.
- Manter o volume `caddydata`: certificado e conta ACME vivem nele; recriá-lo esgota o limite de
  emissão.
- Verificação: `GET http://<host>/` responde 308 para `https`; a descoberta responde em
  `https://<host>/o/.well-known/openid-configuration` com `"issuer": "https://<host>/o"`.

### 4.3 Um salto de proxy só

- O Caddy do compose é o que atende a internet. **Sem ALB, sem CloudFront** à frente dele:
  o Caddy substitui `X-Forwarded-For` de quem chega, e um balanceador na frente faria todos
  os usuários da SPA virarem um único endereço — o limitador de taxa (120/min em `/o/token/`
  e `/o/authorize/`) passaria a valer para a SPA inteira somada, e a trilha de auditoria
  perderia o cliente. `TRUSTED_PROXY_COUNT` fica em 1.
- Verificação: depois do primeiro acesso externo, as linhas da trilha (`logs/audit.log` no
  volume `auditlog`) trazem `ip_edge` = `peer`. Enquanto disser `gateway`, a exposição não tomou
  efeito.
- Se um dia houver balanceador, é ADR nova, com `trusted_proxies` no Caddy e
  `TRUSTED_PROXY_COUNT` remedido.

### 4.4 `.env` de produção

- Gerado **na instância**, nunca copiado do de desenvolvimento: `SECRET_KEY` nova,
  `OIDC_RSA_PRIVATE_KEY` nova (`scripts/gen_dev_key.sh`), senhas novas de Postgres e Redis,
  `DEBUG=False`, `PUBLIC_HOST` da seção 4.1, `CORS_ALLOWED_ORIGINS` da seção 5.2.
- A chave privada de produção não deve existir em nenhuma outra máquina. Backup do `.env` e
  snapshot dos volumes `pgdata`, `auditlog`, `caddydata`.

### 4.5 Antes de abrir a porta

Itens de `docs/seguranca.md` que deixam de ser inventário quando o IdP sai de `localhost`, e
que afetam diretamente a RP:

- `AUTH_PASSWORD_VALIDATORS` (hoje lista vazia): o teto de 5 tentativas do axes supõe senha
  forte.
- `/o/applications/register/` permite a **qualquer conta autenticada** registrar uma
  `Application`. Restringir a `is_staff` ou retirar do URLConf antes que exista mais de uma
  conta.
- Superusuário por `createsuperuser` (ADR 0019), nunca por variável.

---

## 5. Configuração que a SPA exige

### 5.1 Uma `Application` por ambiente

Registrar no admin (`/admin/oauth2_provider/application/add/`), **uma para dev e uma para
produção**, com `client_id` distintos:

| Campo | Valor | Por quê |
| --- | --- | --- |
| `client_type` | `public` | a SPA não guarda secret |
| `authorization_grant_type` | `authorization-code` | único fluxo |
| `algorithm` | `RS256` | sem ele o `code` é emitido e o `id_token` não vem — falha silenciosa |
| `redirect_uris` | **uma** URL literal: `https://<spa>/callback` (prod) ou `http://localhost:5173/callback` (dev) | igualdade exata |
| `skip_authorization` | `True` | seção 5.3 |

Por que separadas: o cliente de produção nunca aceita retorno em `http://localhost`; revogar ou
apagar o de dev não toca produção; a trilha de auditoria distingue os dois. Nunca colocar as
duas `redirect_uris` na mesma `Application`.

Recomendado em produção: `ALLOWED_REDIRECT_URI_SCHEMES = ["https"]` no `OAUTH2_PROVIDER`, para
que nem por engano se registre `http` ali (hoje o default aceita os dois; isso é global à
instância, então em dev fica como está).

Entregar o `client_id` de cada `Application` à SPA.

### 5.2 CORS

- `CORS_ALLOWED_ORIGINS` com a origem **exata** da SPA daquele ambiente: `https://<spa>` em
  produção, `http://localhost:5173` em dev. Sem curinga, sem regex, sem `CORS_ALLOW_ALL_ORIGINS`.
  `CORS_ALLOW_CREDENTIALS` fica no default `False` (a SPA não manda cookie).
- A liberação vale para **quatro** caminhos que a SPA chama por `fetch`: descoberta, `jwks_uri`,
  `/o/token/`, `/o/userinfo/`. O IdP fake que a SPA usou em dev ecoava qualquer origem em
  descoberta e JWKS, então esses dois nunca foram testados contra uma allowlist real.
- Preflight: `django-cors-headers` 4.9.0 já inclui `authorization` e `content-type` em
  `CORS_ALLOW_HEADERS` por default; nada a acrescentar.
- Recomendado: `CORS_URLS_REGEX = r"^/o/"`, para que cabeçalhos de CORS saiam só na superfície
  de protocolo (`/admin/` e `/accounts/login/` nunca são cross-origin).
- **Ao preencher a allowlist, conferir a posição do `CorsMiddleware` e do
  `LimiteDeTaxaMiddleware`** — o `runbook.md` avisa que uma posição errada é indetectável
  enquanto a lista estiver vazia. Verificação: `curl -i -H "Origin: https://<spa>"
  https://<host>/o/.well-known/openid-configuration` devolve `Access-Control-Allow-Origin:
  https://<spa>`; o mesmo com `-X OPTIONS -H "Access-Control-Request-Method: GET" -H
  "Access-Control-Request-Headers: authorization"` em `/o/userinfo/`.
- Previews da Vercel (origem única por deploy) **não** entram no CORS nem na `Application` de
  produção. Se a SPA precisar autenticar em preview, ela entregará um alias estável, que
  ganha uma terceira `Application` e uma terceira entrada de CORS — nunca um regex de
  `*.vercel.app`, que é domínio compartilhado por todos os usuários da Vercel.

### 5.3 Consentimento: pular para a SPA

O DOT fica em `REQUEST_APPROVAL_PROMPT="force"`: tela de consentimento em toda ida a
`/o/authorize/`. Como a SPA vai ao IdP em **todo reload**, a pessoa veria a tela a cada F5.

- Marcar `skip_authorization=True` **na `Application` da SPA** (dev e prod). A SPA é aplicação
  de primeira parte do mesmo sistema; o consentimento repetido não informa nada e ensina a
  clicar sem ler.
- Não trocar o default global para `"auto"`: valeria para toda RP futura, e a decisão de pular
  depende do estado da tabela de tokens.
- Disciplina: o campo **nunca** é marcado numa `Application` de terceiro; nada no IdP impede
  isso além de quem opera.

### 5.4 O que fica como está, por decisão

- **Logout pela RP continua desligado.** A SPA faz logout local e avisa. Se um dia ligar
  `OIDC_RP_INITIATED_LOGOUT_ENABLED`, é ADR cruzada: a SPA lê `end_session_endpoint` da
  descoberta e passará a usá-lo, e o `post_logout_redirect_uri` dela terá de ser registrado.
- **Sem páginas de cadastro ou edição de perfil.** A SPA deixa de exigi-las. Contas continuam
  sendo criadas pelo admin. Cadastro público, se vier, é funcionalidade com ADR própria e
  pré-condições (validadores de senha, limite de taxa no cadastro, verificação de e-mail e só
  então `email_verified`).
- **Sessão no reload é por redirect + SSO.** O cookie de sessão do IdP (`SameSite=Lax`, default)
  viaja na navegação top-level cross-site, então a volta é sem senha. Nada a configurar; só
  não mudar `SESSION_COOKIE_SAMESITE` para `Strict`, que quebraria isso.

---

## 6. Desenvolvimento: o IdP real em `localhost`

A regra da raiz: a SPA só está integrada quando fecha contra o IdP real, não contra o fake.

1. **Corrigir o `.env` atual**, que está atrás do `docker-compose.yml` e impede até `docker
   compose up postgres redis`: faltam `PUBLIC_HOST` (`idp.localhost`) e `REDIS_PASSWORD`
   (`openssl rand -hex 32`); `REDIS_URL` está sem a senha. **Preservar `SECRET_KEY` e
   `OIDC_RSA_PRIVATE_KEY`** — o `.env` é untracked e sem cópia; fazer backup antes de editar.
2. A jornada de integração em dev é a **de construção**: `runserver` em
   `http://localhost:8000`, `BEHIND_TLS_PROXY=False`. Issuer `http://localhost:8000/o`. Texto
   claro em loopback é aceitável em dev e evita instalar a CA do Caddy no navegador. A jornada
   de container (`https://idp.localhost`) fica como segunda verificação antes da AWS.
3. `CORS_ALLOWED_ORIGINS=http://localhost:5173` no `.env`.
4. `Application` de dev (seção 5.1) com `http://localhost:5173/callback`; entregar o
   `client_id`.
5. Uma conta de teste com nome preenchido e outra **sem** nome (`name` = `""`), para a SPA
   exercitar os dois casos que o fake não reproduz fielmente.

---

## 7. Como verificar que a parte do back-end está cumprida

Sem a SPA, com `curl` e um navegador, em cada ambiente:

1. Descoberta responde em `{issuer}/.well-known/openid-configuration`, com `issuer` igual ao
   valor entregue à SPA, `code_challenge_methods_supported: ["S256"]`, sem
   `end_session_endpoint`.
2. `jwks_uri` responde com uma chave RSA com `kid`.
3. Os dois acima, e `/o/token/` e `/o/userinfo/`, respondem com `Access-Control-Allow-Origin`
   igual à origem da SPA quando chamados com `Origin` (seção 5.2).
4. O fluxo PKCE à mão de `docs/receita.md` fecha com a `Application` da SPA: `id_token` com
   `iss`, `aud` = `client_id`, `sub`, `name`, `email`; sem tela de consentimento na segunda
   autorização.
5. `/o/userinfo/` com token inválido responde 401.
6. Em produção: `https` com certificado aceito por navegador sem aviso; `ip_edge` = `peer` na
   trilha; `http://` redireciona para `https://`.

Depois disso, a etapa final é da SPA: login em produção chega a `/app` com as claims.

---

## 8. Decisões a registrar em ADR (uma aqui, uma na SPA, apontando uma para a outra)

| Decisão | Referência na SPA |
| --- | --- |
| Issuer congelado em `https://<dominio>/o` (confirmação pedida pela ADR 0007) | ADR da SPA fixando `VITE_OIDC_ISSUER` |
| Premissa de sandbox rompida: IdP exposto na AWS, um salto, ACME | ADR da SPA de deploy na Vercel |
| `skip_authorization` para a `Application` de primeira parte | ADR da SPA fechando "sessão no reload" (§7.2 do plano dela) |
| CORS por origem exata; previews da Vercel fora | ADR da SPA sobre previews |
| Sem páginas de conta; cadastro continua administrativo | ADR da SPA emendando D2 |

---

## 9. Checklist do back-end

Marcar cada item só quando verificado contra o código ou contra o ambiente, nunca contra um
documento.

### Desenvolvimento

- [x] `.env` corrigido (`PUBLIC_HOST`, `REDIS_PASSWORD`, `REDIS_URL` com senha), com
      `SECRET_KEY` e `OIDC_RSA_PRIVATE_KEY` preservados e backup feito
- [x] `docker compose up postgres redis` sobe e `manage.py test` passa
- [x] `runserver` em `http://localhost:8000`; descoberta publica `"issuer":
      "http://localhost:8000/o"`
- [x] `CORS_ALLOWED_ORIGINS=http://localhost:5173` e os quatro caminhos respondem com
      `Access-Control-Allow-Origin` (seção 5.2)
- [ ] `Application` de dev registrada: `public`, `authorization-code`, `RS256`,
      `http://localhost:5173/callback`, `skip_authorization=True`
- [ ] Contas de teste: uma com nome, uma sem nome
- [ ] Entregue à SPA: issuer de dev e `client_id` de dev

### Produção

- [ ] Domínio próprio apontando para a instância; `PUBLIC_HOST` definido com ele
- [ ] `.env` de produção gerado na instância (chaves e senhas novas), com backup
- [ ] Caddy com certificado público (ACME), `tls internal` removido; volume `caddydata` mantido
- [ ] Portas 80/443 publicadas em `0.0.0.0`; security group só 80/443 (+ SSH restrito)
- [ ] Nenhum proxy entre a internet e o Caddy; `TRUSTED_PROXY_COUNT = 1`; trilha mostra
      `ip_edge` = `peer` após acesso externo
- [ ] `https://<host>/o/.well-known/openid-configuration` responde com `"issuer":
      "https://<host>/o"`, sem `end_session_endpoint`, com `S256`
- [ ] `CORS_ALLOWED_ORIGINS=https://<spa>` (origem exata); os quatro caminhos respondem com
      o cabeçalho; posição do `CorsMiddleware` e do limitador conferida com a lista preenchida
- [ ] `Application` de produção registrada: `public`, `authorization-code`, `RS256`,
      `https://<spa>/callback`, `skip_authorization=True`; `client_id` entregue à SPA
- [ ] `ALLOWED_REDIRECT_URI_SCHEMES = ["https"]` avaliado e decidido
- [ ] `CORS_URLS_REGEX = r"^/o/"` avaliado e decidido
- [ ] `AUTH_PASSWORD_VALIDATORS` declarado
- [ ] `/o/applications/register/` restrito ou removido
- [ ] Superusuário criado por `createsuperuser`
- [ ] Fluxo PKCE à mão (`docs/receita.md`) fecha contra a `Application` de produção com
      `id_token` completo e sem consentimento repetido
- [ ] `/o/userinfo/` com token inválido → 401, com cabeçalho de CORS
- [ ] Snapshot/backup de `pgdata`, `auditlog`, `caddydata` configurado

### Registro

- [ ] ADR: issuer congelado (confirmação da ADR 0007), com referência à ADR da SPA
- [ ] ADR: premissa de sandbox rompida (exposição na AWS, um salto, ACME)
- [ ] ADR: `skip_authorization` para RP de primeira parte
- [ ] ADR: CORS por origem exata, previews fora
- [ ] ADR: sem páginas de conta nesta fase
- [ ] `docs/integracao-rp.md` atualizado com o issuer de produção e a orientação de
      `skip_authorization`
