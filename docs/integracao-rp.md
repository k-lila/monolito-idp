# Integrar uma relying party ao nova_api

## 1. A quem serve e o que não cobre

Este documento é o contrato entre o nova_api e quem implementa uma relying party (RP) — a
aplicação que delega a autenticação a este provedor de identidade (IdP, Identity Provider).
Cobre coordenadas, registro do cliente, o fluxo, as claims emitidas, a verificação do token e
os tempos de vida.

Não cobre operação. Subir o stack, diagnosticar falha e revogar token vivo são assunto de
`README.md`, `docs/receita.md` e `docs/runbook.md`, e este documento aponta para eles quando o
contrato depende de algo que só se resolve do lado do IdP. Há uma exceção, e ela está na seção
9: a raiz da autoridade certificadora, sem a qual o cliente da RP não chega a abrir conexão.
Apontar para fora seria apontar para fora do contrato justamente onde ele não fecha.

**Aviso de estabilidade.** O par `(iss, sub)` — a chave de identidade que a OpenID Connect
(OIDC) Core §5.7 manda a RP guardar — é reciclado se o banco do IdP for recriado, e com ele a
conta que a RP associou a uma pessoa. Em desenvolvimento isso acontece a cada `docker compose
down -v`; em produção, só com a perda do volume `pgdata`. A condição exata está em
`docs/runbook.md`.

## 2. Coordenadas

O issuer é `{BASE_URL}/o`, e é exatamente essa string que entra na claim `iss` de todo
`id_token`. **A forma depende da implantação, e não há um valor que este documento possa
declarar por ela**: na jornada de container o `BASE_URL` é `https://` mais o nome público, e na
de construção é `http://localhost:8000`. Quem integra lê o `issuer` do documento de descoberta
daquela implantação — é ele a fonte, e nunca um literal copiado daqui.

Duas propriedades do issuer valem em qualquer implantação: ele termina em `/o`, e o esquema é
`https` se e somente se o IdP está atrás do proxy de terminação TLS (Transport Layer Security).

**A forma do issuer de produção está congelada (ADR 0025): `https://` mais o nome público,
seguido de `/o`, sem barra final e sem porta.** O nome vive só no ambiente de produção e é
entregue à RP na integração, nunca escrito neste documento. A partir do primeiro login de
produção ele é permanente, e trocá-lo exige ADR nova e reconfiguração de quem integrou. Quem lê
o `issuer` da descoberta em vez de fixar um literal atravessa essa troca sem reconfigurar nada;
quem copiou a string, não.

O documento de descoberta responde em:

```
{BASE_URL}/o/.well-known/openid-configuration
```

Essa é a forma da OIDC Discovery 1.0, que concatena o sufixo ao issuer inteiro. A forma da RFC
8414, que põe o segmento `.well-known` na raiz do host e o path do issuer no fim
(`{BASE_URL}/.well-known/oauth-authorization-server/o`), **responde 404**. Não é falha a
descobrir por tentativa: as rotas do servidor de autorização, os metadados inclusive, entram
só sob `/o/`, e nenhuma é montada na raiz. A decisão do prefixo está registrada em
`docs/adr/0007-fixar-o-issuer-do-idp-em-base-url-barra-o.md`, e a de quais rotas entram, em
`docs/adr/0024-montar-sob-o-so-as-listas-de-protocolo-do-django-oauth-toolkit.md`.

**Derive todo endpoint da descoberta, não os codifique.** O documento traz
`authorization_endpoint`, `token_endpoint`, `userinfo_endpoint`, `end_session_endpoint` e
`jwks_uri`, e são eles que sobrevivem a uma mudança de `BASE_URL` sem que ninguém precise avisar
a RP. Os caminhos citados adiante estão aqui para tornar o texto legível, não para serem
copiados para dentro da RP.

## 3. Registrar a Application

O registro é manual, feito por uma pessoa com acesso administrativo ao IdP, em
`/admin/oauth2_provider/application/add/`. O registro dinâmico de cliente (`/o/register/`)
responde 404, e por duas razões: a rota não é montada (ADR 0024), e `DCR_ENABLED` mantém o
default `False` do `django-oauth-toolkit`. Não há como uma RP se auto-registrar nesta fase, nem
registrar-se por formulário fora do admin.

Quatro campos decidem se a integração funciona; um quinto decide se a pessoa vê a tela de
consentimento, e um sexto, se o "Sair" da RP volta a ela:

| Campo | Valor | Por quê |
| --- | --- | --- |
| `client_type` | `public` | a RP não guarda `client_secret` |
| `authorization_grant_type` | `authorization-code` | é o único fluxo suportado aqui |
| `algorithm` | `RS256` | sem ele não há `id_token` |
| `redirect_uris` | a URL de retorno da RP | comparada por igualdade exata |
| `skip_authorization` | `True` só para RP de primeira parte; `False` (default) para qualquer terceiro | pula a tela de consentimento; `docs/adr/0021-pular-o-consentimento-na-application-de-primeira-parte-por-skip-authorization.md` |
| `post_logout_redirect_uris` | a URL para onde o "Sair" volta, literal, com a barra final | comparada como `redirect_uris`; sem ela, o "Sair" termina na tela de erro do IdP (seção 4.3) |

**A comparação de `redirect_uri` é por igualdade exata, nunca por prefixo.** Uma barra final a
mais na URL enviada em `/o/authorize/` já basta para o servidor recusar antes de emitir
código, e esse comportamento está fixado em `tests/test_authorize_guards.py`. Cada URL
de retorno da RP tem de estar registrada literalmente, com esquema, host, porta e path. O
esquema aceito depende da implantação: atrás do proxy de terminação TLS, só `https`; na jornada
de construção, `http` também, o que permite registrar uma RP de desenvolvimento em
`localhost`.

**`post_logout_redirect_uris` é conferido do mesmo jeito, e só no primeiro "Sair".** A
comparação é a de `redirect_uris`, por igualdade exata, e o esquema segue a mesma regra: atrás
do proxy, só `https`. O valor é o que a RP envia em `post_logout_redirect_uri`, literal, e para
a `nova_api_SPA` é a landing com a barra final, não a origem. O admin não valida o campo: um
cadastro esquecido, em `http` ou sem a barra, é gravado sem aviso e só aparece quando alguém
tenta sair.

O `algorithm` deixado em branco não impede a autorização: o código é emitido normalmente e a
falha só aparece na troca, sem `id_token` nenhum. O sintoma e o diagnóstico estão em
`docs/runbook.md`.

Do registro sai o `client_id`, que é o que a RP guarda. Não há `client_secret`.

**`skip_authorization` separa primeira parte de terceiro.** Marcado, o servidor emite o código
sem mostrar a tela de consentimento, inclusive na primeira autorização. É o que a `Application`
da `nova_api_SPA` recebe: ela volta a `/o/authorize/` a cada recarga da página, e uma pergunta
cuja resposta já se conhece não informa nada. Numa `Application` de terceiro o campo fica
desmarcado, sempre — nada no IdP impede marcá-lo, e a regra vive em
`docs/adr/0021-pular-o-consentimento-na-application-de-primeira-parte-por-skip-authorization.md`.

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

### 4.3 Encerrar a sessão

`GET` no `end_session_endpoint` (`/o/logout/`), com o navegador da pessoa. É o OpenID Connect
RP-Initiated Logout 1.0, com as decisões de
`docs/adr/0029-ligar-o-logout-iniciado-pela-rp-com-revogacao-restrita-a-application.md`. Só
`GET` vale para a RP; o `POST` na mesma rota é o da tela de confirmação do próprio IdP.

| Parâmetro | Valor |
| --- | --- |
| `id_token_hint` | o `id_token` que a RP recebeu na troca, mesmo vencido |
| `post_logout_redirect_uri` | uma das cadastradas em `post_logout_redirect_uris`, literal |
| `state` | valor imprevisível gerado pela RP; volta no retorno |
| `client_id` | opcional; se vier com o hint, tem de ser o do `aud` dele |

Com o hint vivo da conta que tem sessão no navegador, não há pergunta: o IdP encerra a sessão,
revoga os tokens e responde 302 para `post_logout_redirect_uri?state=<state>`. Há tela de
confirmação quando o hint falta, é de outra conta ou já não tem registro no IdP; ela é em
português, e só um `POST` com o token CSRF (Cross-Site Request Forgery) a confirma. Sem sessão no
navegador, não há o que perguntar, e o IdP segue direto ao destino.

O `state` volta inalterado; compará-lo com o que foi gerado é obrigação da RP, como na seção
4.1.

**De onde vem a Application, e o que se revoga.**

| Pedido | Application | O que se revoga | Sessão |
| --- | --- | --- | --- |
| hint vivo (com ou sem `client_id` igual) | a do `id_token` | os tokens da conta do hint, só nessa Application | termina |
| hint vivo e `client_id` diferente | — | nada; 400 | intacta |
| hint autêntico sem registro | a do `aud`; `client_id` diferente dá 400 | com sessão e confirmação, os tokens da conta da sessão nessa Application; sem sessão, nada | termina |
| só `client_id` | a dele; inexistente dá 400 | com sessão e confirmação, os tokens da conta da sessão nessa Application; sem sessão, nada | termina |
| nenhum dos dois, com `post_logout_redirect_uri` | nenhuma | nada; 400 | intacta |
| nenhum dos dois, sem destino | nenhuma | nada; com sessão, pede confirmação | termina; 302 à raiz do IdP |

Revogar é apagar `access_token`, `refresh_token` e `id_token` da conta **naquela Application,
em todos os dispositivos da conta**, e não só os desta aba. Os tokens da mesma conta em outra
RP sobrevivem, mas a sessão do IdP termina inteira, e a volta sem senha acaba para todas.

**O hint sem registro é tratado como ausente.** Um hint com assinatura válida e `iss` deste IdP,
cujo registro já sumiu, vem de uma saída anterior, por exemplo numa segunda aba, ou da limpeza
de tokens vencidos. Sem sessão, o pedido vai ao destino com o `state` e nada é revogado; com
sessão, o IdP pergunta.

**O que termina na tela de erro, com 400, e sem encerrar nem revogar nada:** destino não
cadastrado, destino em `http` atrás do proxy, destino que não se decompõe como URL, hint de
assinatura inválida, de outro issuer, malformado ou assinado por uma chave anterior à troca, e
`client_id` inexistente, com o caractere NUL ou divergente do hint. A RP não recebe redireção
nesses casos: a pessoa fica no IdP, com um link para o início dele.

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
2. `iss` igual ao `issuer` que a descoberta daquela implantação publica, por **igualdade exata
   de string** — comparação byte a byte, sem normalizar esquema, barra final nem caixa;
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
do servidor da RP, e nada nelas depende de configuração adicional **no IdP**. Do lado da RP há
uma, e só uma, quando o IdP atende em `https`: confiar na raiz da autoridade certificadora,
logo abaixo.

**RP que rode no navegador exige entrada em `CORS_ALLOWED_ORIGINS`**, que sai vazia no
`.env.example`. Enquanto a allowlist estiver vazia, uma aplicação de página única que tente
chamar `/o/token/` ou `/o/userinfo/` diretamente do navegador recebe erro de CORS (Cross-Origin
Resource Sharing). A origem da RP precisa ser acrescentada à variável no IdP.

### 9.1 O certificado, quando o IdP atende em `https`

O IdP tem TLS quando está atrás do proxy de terminação, e não tem quando roda em
`http://localhost:8000` — é a mesma divisão da seção 2, e é o esquema do `issuer` que a
denuncia. Em desenvolvimento, as duas implantações publicam em `127.0.0.1`, e o certificado da
jornada de container sai da autoridade interna descrita abaixo. Em produção o certificado é o
Universal da borda da Cloudflare, que os clientes já conhecem, e o que segue sobre a autoridade
interna vale só para a jornada de container em `idp.localhost` (ADR 0027). A borda termina o TLS
e vê em texto claro o que passa por ela, os tokens inclusive (ADR 0027, "Um terceiro vê tudo").
O que o IdP protege e o que não protege quando exposto está em `docs/seguranca.md`.

**O certificado do IdP sai de uma autoridade certificadora (CA) interna, que cliente nenhum
conhece de fábrica.** O sintoma é a troca em `/o/token/` falhar antes de haver resposta, com
`certificate verify failed: unable to get local issuer certificate`. Recusar é o comportamento
correto de quem não conhece a autoridade, e não defeito do IdP nem erro de integração.

A raiz vive dentro do container do proxy, e quem administra o IdP a extrai com um comando:

```bash
docker compose cp proxy:/data/caddy/pki/authorities/local/root.crt ./ca-local.crt
```

O arquivo que sai daí é o que se entrega ao cliente HTTP da RP — `REQUESTS_CA_BUNDLE`,
`SSL_CERT_FILE`, o `verify=` do `requests`, o truststore da linguagem, conforme o que a RP
usar. Peça-o a quem opera o IdP se você não tiver acesso ao stack.

**Desligar a verificação de certificado não é a alternativa barata.** O `id_token` é assinado e
a RP o verifica de qualquer jeito, mas `access_token` e `refresh_token` chegam em texto no
corpo da resposta de `/o/token/`, e são eles que uma conexão não verificada entrega a quem
estiver no meio.

A raiz é regerada quando o IdP é derrubado com destruição de volumes, e o certificado aceito
ontem passa a ser de outra autoridade. O sintoma é o mesmo erro acima, voltando sem que nada
tenha mudado na RP; o remédio é extrair a raiz de novo.

Esta subseção inteira vale enquanto o certificado sair da CA interna, que é a configuração de
hoje. Com um certificado de autoridade que o cliente já conheça, nada aqui é preciso — e o
sinal da troca é o cliente HTTP da RP parar de exigir a raiz.

## 10. Exemplo mínimo

O fluxo inteiro fechado à mão — gerar o par PKCE, abrir `/o/authorize/` no navegador, ler o
código e trocá-lo com `curl` — está em `docs/receita.md`, na seção "Fechar o fluxo PKCE à
mão". Os comandos não são reproduzidos aqui: um exemplo copiado envelhece em silêncio.
