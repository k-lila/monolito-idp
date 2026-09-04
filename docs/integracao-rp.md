# Integrar uma relying party ao nova_api

## 1. A quem serve e o que não cobre

Este documento é o contrato entre o nova_api e quem implementa uma relying party (RP) — a
aplicação que delega a autenticação a este provedor de identidade (IdP, Identity Provider).
Cobre coordenadas, registro do cliente, o fluxo, as claims emitidas, a verificação do token e
os tempos de vida.

Não cobre operação. Subir o stack, diagnosticar falha e revogar token vivo são assunto de
`README.md`, `docs/receita.md` e `docs/runbook.md`, e este documento aponta para eles quando o
contrato depende de algo que só se resolve do lado do IdP.

**Aviso de estabilidade.** Enquanto o projeto for sandbox exploratório, o par `(iss, sub)` —
a chave de identidade que a OpenID Connect (OIDC) Core §5.7 manda a RP guardar — pode ser
reciclado entre execuções do IdP, e com ele a conta que a RP associou a uma pessoa. A condição
que dispara isso está em `docs/runbook.md`.

## 2. Coordenadas

O issuer é `{BASE_URL}/o`. Com o `BASE_URL` que sai de `.env.example`, isso é
`http://localhost:8000/o` — e é exatamente essa string que entra na claim `iss` de todo
`id_token`.

O documento de descoberta responde em:

```
{BASE_URL}/o/.well-known/openid-configuration
```

Essa é a forma da OIDC Discovery 1.0, que concatena o sufixo ao issuer inteiro. A forma da RFC
8414, que põe o segmento `.well-known` na raiz do host e o path do issuer no fim
(`{BASE_URL}/.well-known/oauth-authorization-server/o`), **responde 404**. Não é falha a
descobrir por tentativa: as rotas do servidor de autorização entram por um único `include` sob
`/o/`, e a decisão está registrada em
`docs/adr/0007-fixar-o-issuer-do-idp-em-base-url-barra-o.md`.

**Derive todo endpoint da descoberta, não os codifique.** O documento traz
`authorization_endpoint`, `token_endpoint`, `userinfo_endpoint` e `jwks_uri`, e são eles que
sobrevivem a uma mudança de `BASE_URL` sem que ninguém precise avisar a RP. Os caminhos citados
adiante estão aqui para tornar o texto legível, não para serem copiados para dentro da RP.

## 3. Registrar a Application

O registro é manual, feito por uma pessoa com acesso administrativo ao IdP, em
`/admin/oauth2_provider/application/add/`. O registro dinâmico de cliente (`/o/register/`)
responde 404 enquanto `DCR_ENABLED` mantiver o default `False` do
`django-oauth-toolkit`: não há como uma RP se auto-registrar nesta fase.

Quatro campos decidem se a integração funciona:

| Campo | Valor | Por quê |
| --- | --- | --- |
| `client_type` | `public` | a RP não guarda `client_secret` |
| `authorization_grant_type` | `authorization-code` | é o único fluxo suportado aqui |
| `algorithm` | `RS256` | sem ele não há `id_token` |
| `redirect_uris` | a URL de retorno da RP | comparada por igualdade exata |

**A comparação de `redirect_uri` é por igualdade exata, nunca por prefixo.** Uma barra final a
mais na URL enviada em `/o/authorize/` já basta para o servidor recusar antes de emitir
código, e esse comportamento está fixado em `tests/test_authorize_guards.py`. Cada URL
de retorno da RP tem de estar registrada literalmente, com esquema, host, porta e path. O
esquema `http` é aceito além de `https`, o que permite registrar uma RP de desenvolvimento em
`localhost`.

O `algorithm` deixado em branco não impede a autorização: o código é emitido normalmente e a
falha só aparece na troca, sem `id_token` nenhum. O sintoma e o diagnóstico estão em
`docs/runbook.md`.

Do registro sai o `client_id`, que é o que a RP guarda. Não há `client_secret`.

## 4. O fluxo que a RP implementa

### 4.1 Redirecionar para a autorização

`GET` no `authorization_endpoint` (`/o/authorize/`), com o navegador da pessoa:

| Parâmetro | Valor |
| --- | --- |
| `response_type` | `code` |
| `client_id` | o do registro |
| `redirect_uri` | uma das registradas, literal |
| `scope` | `openid`, mais `profile` e `email` conforme a seção 5 |
| `state` | valor imprevisível gerado pela RP a cada tentativa |
| `code_challenge` | o desafio PKCE (Proof Key for Code Exchange) |
| `code_challenge_method` | `S256` |
| `nonce` | opcional; volta no `id_token` |

`scope` sem `openid` produz uma autorização OAuth2 comum, sem `id_token`.

**`code_challenge_method=S256` é obrigatório e literal.** A descoberta anuncia
`code_challenge_methods_supported` igual a `["S256"]`, e o servidor recusa `plain`. Requisição
sem `code_challenge` também é recusada; as duas guardas estão verificadas em
`tests/test_authorize_guards.py`.

O `state` volta inalterado na redireção de retorno. Compará-lo com o que foi gerado é obrigação
da RP: o IdP apenas o transporta.

O retorno é uma redireção para a `redirect_uri` com `code` e `state` na query string. Se a
pessoa recusar o consentimento, ou se o pedido for inválido, a redireção vem com `error` e sem
`code`.

### 4.2 Trocar o código por tokens

`POST` no `token_endpoint` (`/o/token/`), da própria RP, não do navegador:

```
grant_type=authorization_code
code=<o código recebido>
redirect_uri=<a mesma enviada na autorização>
client_id=<o do registro>
code_verifier=<o verificador PKCE>
```

Cliente público: **não existe `client_secret`**, e o `code_verifier` é a prova de posse — é ele
que impede que um código interceptado seja trocado por token por outra parte. A resposta traz
`access_token`, `refresh_token` e, quando o scope inclui `openid`, `id_token`.

## 5. O que o `id_token` afirma

Três claims de identidade, e nenhuma além delas:

| Claim | Origem | Scope que a libera |
| --- | --- | --- |
| `sub` | a chave primária da conta no IdP | `openid` |
| `name` | `get_full_name()` da conta | `profile` |
| `email` | o e-mail da conta, que é o identificador de login | `email` |

O mapa é estrito: com `openid` sozinho chega apenas `sub`; `profile` acrescenta `name` sem
acrescentar `email`, e `email` acrescenta `email` sem acrescentar `name`. Os cinco casos estão
fixados em `tests/test_oauth_validators.py`.

Junto delas vêm as claims de protocolo que a verificação exige — `iss`, `aud`, `exp`, `iat` — e
as que o `oauthlib` acrescenta conforme o pedido, entre elas `nonce`, `auth_time`, `at_hash` e
`c_hash`.

**`name` pode chegar presente e vazia.** Ela sai de `get_full_name()`, e uma conta sem nome e
sem sobrenome preenchidos produz `"name": ""`. A chave existe; o valor é a string vazia. Não é
defeito, e a RP não deve tratar isso como resposta malformada.

**`sub` é a chave primária da conta**, e a chave de identidade que a RP guarda é o par
`(iss, sub)`, conforme a OIDC Core §5.7 — nunca o `email`, que é mutável, nem o `sub` sozinho.

`GET /o/userinfo/`, com o `access_token` no cabeçalho `Authorization: Bearer`, devolve as
mesmas claims sob os mesmos scopes.

## 6. O que o IdP não afirma

A seção que mais importa para quem integra: cada linha abaixo é uma garantia que a RP **não**
recebe e, portanto, precisa obter de outro lugar ou dispensar por escrito.

- **Não há `email_verified`.** A claim não aparece no `id_token` nem em `/o/userinfo/`, sob
  scope nenhum, porque não existe fluxo de verificação de e-mail nesta fase. A RP não pode
  presumir que o endereço recebido pertence a quem se autenticou.
- **Não há `end_session_endpoint`.** O logout iniciado pela relying party está desligado, e a
  chave está ausente do documento de descoberta. Encerrar a sessão na RP não encerra a sessão
  no IdP: a próxima ida a `/o/authorize/` reautentica sem pedir senha.
- **Nada além de `name` e `email`.** Não há grupos, papéis, telefone, foto nem atributo
  organizacional. O `claims_supported` da descoberta é exatamente `sub`, `name`, `email`, e o
  acoplamento entre ele e o que o servidor emite está verificado em
  `tests/test_authorization_code_flow.py`.
- **O `access_token` não é inspecionável pela RP.** Ele é uma string opaca, não um JWT (JSON
  Web Token), e a introspecção não está utilizável: `/o/introspect/` exige um scope que este
  IdP não declara e responde 403, conforme
  `docs/adr/0002-usar-django-oauth-toolkit-como-servidor-de-autorizacao.md`. Quem precisar do
  estado corrente chama `/o/userinfo/`, uma requisição ao IdP por consulta.
- **Não há garantia de revogação por desativação de conta:** `access_token` e `refresh_token`
  já emitidos seguem válidos. O procedimento de revogação está em `docs/runbook.md`.

## 7. Verificar o token

A chave pública está no JWKS (JSON Web Key Set), em `/o/.well-known/jwks.json`, anunciado como
`jwks_uri` na descoberta. Hoje o conjunto tem **uma** chave RSA (Rivest–Shamir–Adleman) com
`kid`, e o `kid` do cabeçalho do `id_token` casa com o da chave publicada — comportamento
fixado em `tests/test_jwks.py` e em
`tests/test_authorization_code_flow.py`.

O que a RP verifica em todo `id_token`, sem exceção:

1. a assinatura, contra a chave do JWKS cujo `kid` casa com o do cabeçalho, com `alg` igual a
   `RS256` (RSA com SHA-256);
2. `iss` igual ao issuer da seção 2, por igualdade exata de string;
3. `aud` contendo o `client_id` da própria RP;
4. `exp` ainda no futuro;
5. `nonce` igual ao enviado, se enviado.

**Rotação de chave.** Há uma chave ativa e nenhum conjunto de rotação, de modo que a primeira
troca invalidará a verificação de todo token vivo e exigirá que as RPs releiam o JWKS; a
decisão e seu custo estão em
`docs/adr/0004-assinar-tokens-com-rs256-e-custodiar-a-chave-privada-no-ambiente.md`. Reler o
JWKS quando aparecer um `kid` desconhecido é a postura que sobrevive a essa troca.

## 8. Ciclo de vida dos tokens

O projeto não sobrescreve nenhum tempo de vida: os valores abaixo são os defaults do
`django-oauth-toolkit` 3.4.1, declarados em `oauth2_provider/settings.py`.

| O quê | Chave | Valor |
| --- | --- | --- |
| Código de autorização | `AUTHORIZATION_CODE_EXPIRE_SECONDS` | 60 s |
| `access_token` | `ACCESS_TOKEN_EXPIRE_SECONDS` | 36 000 s (10 h) |
| `id_token` | `ID_TOKEN_EXPIRE_SECONDS` | 36 000 s (10 h) |
| `refresh_token` | `REFRESH_TOKEN_EXPIRE_SECONDS` | `None` — não expira |

O código vive 60 segundos: a troca é imediata, não uma tarefa de fila. O `refresh_token` não
expira por tempo, e é rotacionado a cada uso (`ROTATE_REFRESH_TOKEN` default `True`, sem
período de graça) — a RP tem de guardar o `refresh_token` novo que vem em cada renovação, sob
pena de perder o acesso ao descartá-lo.

Revogar tokens já emitidos é operação do lado do IdP, e o procedimento está em
`docs/runbook.md`.

## 9. Ambiente

**RP server-side funciona hoje.** A troca em `/o/token/` e a consulta a `/o/userinfo/` partem
do servidor da RP, e nada nelas depende de configuração adicional no IdP.

**RP que rode no navegador exige entrada em `CORS_ALLOWED_ORIGINS`**, que sai vazia no
`.env.example`. Enquanto a allowlist estiver vazia, uma aplicação de página única que tente
chamar `/o/token/` ou `/o/userinfo/` diretamente do navegador recebe erro de CORS (Cross-Origin
Resource Sharing). A origem da RP precisa ser acrescentada à variável no IdP.

**Não há TLS (Transport Layer Security) nesta fase**, e a porta é publicada em `127.0.0.1`:
nada descrito aqui deve atravessar rede não confiável, pelas razões e com a lista de
pendências de `docs/seguranca.md`.

## 10. Exemplo mínimo

O fluxo inteiro fechado à mão — gerar o par PKCE, abrir `/o/authorize/` no navegador, ler o
código e trocá-lo com `curl` — está em `docs/receita.md`, na seção "Fechar o fluxo PKCE à
mão". Os comandos não são reproduzidos aqui: um exemplo copiado envelhece em silêncio.
