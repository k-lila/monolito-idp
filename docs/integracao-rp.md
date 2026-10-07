# Integrar uma relying party ao IdP

## 1. A quem serve e o que não cobre

Este documento é o contrato entre este provedor de identidade (IdP, Identity Provider) e quem
implementa uma relying party (RP) — a aplicação que delega a autenticação a ele.
Cobre coordenadas, registro do cliente, o fluxo, as claims emitidas, a verificação do token, os
tempos de vida e, para a aplicação de página única (SPA, de _Single-Page Application_), a
interface de programação (API, de _Application Programming Interface_) de conta e as páginas de
conta do IdP.

Não cobre operação. Subir o stack e as tarefas do lado do IdP são assunto de `README.md` e de
`docs/receita.md`. Há uma exceção, e ela está na seção 10: a raiz da autoridade certificadora
da jornada de container, sem a qual o cliente da RP não chega a abrir conexão. Apontar para
fora seria apontar para fora do contrato justamente onde ele não fecha.

O resumo do que toda RP recebe, e das invariantes que o IdP preserva, está em
`docs/nucleo-idp.md`. Este documento é o detalhe.

**Aviso de estabilidade.** O par `(iss, sub)` — a chave de identidade que a OpenID Connect
(OIDC) Core §5.7 manda a RP guardar — se perde se o banco do IdP for recriado: as contas
recriadas recebem um `sub` novo, sorteado, e a RP passa a vê-las como pessoas novas. Em
desenvolvimento isso acontece a cada `docker compose down -v`; em produção, só com a perda do
volume `pgdata`. A implantação da ADR 0031 troca uma vez o `sub` de toda conta (seção 6).

## 2. Coordenadas

O issuer é `{BASE_URL}/o`, e é exatamente essa string que entra na claim `iss` de todo
`id_token`. **A forma depende da implantação, e não há um valor que este documento possa
declarar por ela**: na jornada de container o `BASE_URL` é `https://` mais o nome público, e na
de construção é `http://localhost:8000`. Quem integra lê o `issuer` do documento de descoberta
daquela implantação — é ele a fonte, e nunca um literal copiado daqui.

Duas propriedades do issuer valem em qualquer implantação: ele termina em `/o`, e o esquema é
`https` se e somente se o IdP está atrás do proxy de terminação TLS (Transport Layer Security).

**A forma do issuer de produção está congelada pela ADR (Architecture Decision Record) 0025:
`https://` mais o nome público, seguido de `/o`, sem barra final e sem porta.** O nome vive só
no ambiente de produção e é entregue à RP na integração, nunca escrito neste documento. A
partir do primeiro login de produção ele é permanente, e trocá-lo exige ADR nova e reconfiguração de quem integrou. Quem lê
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

## 3. Entrar como RP: o que se troca

Nada no código do IdP muda para acolher uma RP nova: muda a configuração, feita por quem
administra o IdP. A integração é uma troca de valores literais.

| A RP entrega | O IdP devolve |
| --- | --- |
| cada `redirect_uri`, com esquema, host, porta e path | o `client_id` |
| cada `post_logout_redirect_uri`, com a barra final se o path a tiver | o `issuer` daquela implantação |
| se roda no navegador, a origem, para `CORS_ALLOWED_ORIGINS` | |
| se é de primeira parte, a declaração disso, para `skip_authorization` | |

- **Uma `Application` por ambiente.** Atrás do proxy de terminação TLS o IdP só aceita `https`
  em `redirect_uris` e em `post_logout_redirect_uris`. A RP de desenvolvimento, em
  `http://localhost`, fica numa `Application` da jornada de construção, e a de produção, noutra. As
  duas nunca se misturam.
- **A origem de CORS (Cross-Origin Resource Sharing) é origem, não URL.** É esquema, host e
  porta, sem path e sem barra final. Vale uma por ambiente, sem curinga nem regex, e os previews
  da Vercel ficam fora (ADR 0022).
- **O `issuer` vai por escrito, mas a RP o lê da descoberta.** O valor entregue serve para a RP
  conferir que aponta para o IdP certo; a fonte continua sendo o documento de descoberta (seção
  2).
- **`SPA_URL` não é configuração de RP.** É o destino do botão da home do IdP, que hoje leva à
  SPA do sistema. Uma RP nova não precisa dela.

## 4. Registrar a Application

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
| `post_logout_redirect_uris` | a URL para onde o "Sair" volta, literal, com a barra final | comparada como `redirect_uris`; sem ela, o "Sair" termina na tela de erro do IdP (seção 5.3) |

**A comparação de `redirect_uri` é por igualdade exata, nunca por prefixo.** Uma barra final a
mais na URL enviada em `/o/authorize/` já basta para o servidor recusar antes de emitir
código, e esse comportamento está fixado em `tests/test_authorize_guards.py`. Cada URL
de retorno da RP tem de estar registrada literalmente, com esquema, host, porta e path. O
esquema aceito depende da implantação: atrás do proxy de terminação TLS, só `https`; na jornada
de construção, `http` também, o que permite registrar uma RP de desenvolvimento em
`localhost`.

**`post_logout_redirect_uris` é conferido do mesmo jeito, mas só quando alguém sai.** A
comparação é a de `redirect_uris`, por igualdade exata, e o esquema segue a mesma regra: atrás
do proxy, só `https`. O valor é o que a RP envia em `post_logout_redirect_uri`, literal, e para
a SPA é a landing com a barra final, não a origem. O admin não valida o campo: um
cadastro esquecido, em `http` ou sem a barra, é gravado sem aviso e só aparece quando alguém
tenta sair.

O `algorithm` deixado em branco não impede a autorização: o código é emitido normalmente e a
falha só aparece na troca: a resposta de `/o/token/` vem sem `id_token`, e sem erro.

Do registro sai o `client_id`, que é o que a RP guarda. Não há `client_secret`.

**O campo `user` da Application fica vazio ou aponta para uma conta da equipe.** A conta comum
dona de uma Application não pode ser apagada pela página de exclusão, só desativada: apagá-la
levaria em cascata a Application e os tokens de toda a RP (ADR 0031).

**`skip_authorization` separa primeira parte de terceiro.** Marcado, o servidor emite o código
sem mostrar a tela de consentimento, inclusive na primeira autorização. É o que a `Application`
da SPA recebe: ela volta a `/o/authorize/` a cada recarga da página, e uma pergunta
cuja resposta já se conhece não informa nada. Numa `Application` de terceiro o campo fica
desmarcado, sempre — nada no IdP impede marcá-lo, e a regra vive em
`docs/adr/0021-pular-o-consentimento-na-application-de-primeira-parte-por-skip-authorization.md`.

## 5. O fluxo que a RP implementa

### 5.1 Redirecionar para a autorização

`GET` no `authorization_endpoint` (`/o/authorize/`), com o navegador da pessoa:

| Parâmetro | Valor |
| --- | --- |
| `response_type` | `code` |
| `client_id` | o do registro |
| `redirect_uri` | uma das registradas, literal |
| `scope` | `openid`, mais `profile` e `email` conforme a seção 6; `conta` só a SPA pede (seção 5.6) |
| `state` | valor imprevisível gerado pela RP a cada tentativa |
| `code_challenge` | o desafio PKCE (Proof Key for Code Exchange) |
| `code_challenge_method` | `S256` |
| `nonce` | opcional; volta no `id_token` |
| `prompt` | opcional; `create` leva ao cadastro (seção 5.5) |

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

### 5.2 Trocar o código por tokens

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

### 5.3 Encerrar a sessão

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
5.1.

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

**Com uma segunda RP, o "Sair" de uma alcança a outra.** A outra RP guarda os próprios tokens,
mas na próxima ida a `/o/authorize/` a pessoa digita a senha de novo. Esse alcance está
decidido para uma RP só, e a entrada da segunda é o gatilho para revê-lo (ADR 0029).

**O hint sem registro é tratado como ausente.** Um hint com assinatura válida e `iss` deste IdP,
cujo registro já sumiu, vem de uma saída anterior, por exemplo numa segunda aba, ou da limpeza
de tokens vencidos. Sem sessão, o pedido vai ao destino com o `state` e nada é revogado; com
sessão, o IdP pergunta.

**O que termina na tela de erro, com 400, e sem encerrar nem revogar nada:** destino não
cadastrado, destino em `http` atrás do proxy, destino que não se decompõe como URL, hint de
assinatura inválida, de outro issuer, malformado ou assinado por uma chave anterior à troca, e
`client_id` inexistente, com o caractere NUL ou divergente do hint. A RP não recebe redireção
nesses casos: a pessoa fica no IdP, com um link para o início dele.

### 5.4 RP no navegador

O que uma SPA precisa, e é o caso da SPA deste sistema, se reúne aqui:

- **Cliente público, com PKCE.** Não há segredo que o navegador possa guardar; o
  `code_verifier` é a única prova de posse.
- **CORS por origem exata.** A troca em `/o/token/`, a consulta a `/o/userinfo/` e as chamadas
  à API de conta partem do navegador por `fetch` e só passam se a origem da RP estiver em
  `CORS_ALLOWED_ORIGINS`. O CORS vale só sob `/o/` e `/api/conta/`: o login, as páginas de conta
  e o admin nunca são chamados por `fetch`. `WWW-Authenticate` e `Retry-After` são expostos ao
  `fetch` (`CORS_EXPOSE_HEADERS`), úteis a qualquer RP: por eles se distingue token vencido de
  scope faltando e se sabe quanto esperar depois de um 429. A SPA deste sistema não lê nenhum
  dos dois.
- **A sessão do IdP é o que dispensa a senha na volta.** Uma RP que guarda tokens só em memória
  volta a `/o/authorize/` a cada recarga, e o cookie de sessão do IdP, com `SameSite=Lax`, é o
  que a faz voltar sem senha. Com `skip_authorization`, a volta não mostra tela nenhuma.
- **O `refresh_token` rotaciona.** Quem o usar tem de guardar o novo a cada renovação (seção
  9). A SPA o ignora, e passar a usá-lo é decisão com ADR nos dois projetos.

### 5.5 Cadastro pelo protocolo

O "Criar conta" de uma RP é o pedido da seção 5.1 com `prompt=create` (OpenID Connect Prompt
Create 1.0), e a descoberta anuncia `create` em `prompt_values_supported`. Sem sessão, o IdP
valida o pedido e leva a pessoa a `/accounts/registrar/`, com um `next` absoluto para o mesmo
`/o/authorize/` sem `create`. Criada a conta, a sessão do IdP abre e o pedido segue como um
login comum. Com sessão, `create` não muda nada. Pedido inválido termina no erro do próprio
`/o/authorize/`, antes do cadastro.

A conta nasce ativa, com `email_verified` falso e o aceite da versão vigente dos termos, e o
IdP envia o e-mail de boas-vindas com o link de confirmação. A página é pública na prática:
nada impede abri-la direto, e então ela volta à raiz da SPA.

### 5.6 A API de conta

Só a SPA a usa. Os caminhos são fixos, com barra final, e não constam da descoberta:

| Método e caminho | O que faz | Resposta |
| --- | --- | --- |
| `GET /api/conta/` | lê a conta | 200 com o corpo abaixo |
| `PATCH /api/conta/` | altera `first_name`, `last_name` e `nickname`; o resto do corpo é ignorado, e `null` limpa o campo | 200 com o mesmo corpo do `GET` |
| `POST /api/conta/confirmacao/` | reenvia o link de confirmação, se o e-mail ainda não está confirmado | 204, com ou sem envio |
| `POST /api/conta/termos/` | grava o aceite de `{"versao": "<vigente>"}` | 204 |
| `GET /api/conta/confirmar/?t=` | o link do e-mail, sem autenticação | 302 a `{SPA_URL}/?email=confirmado` ou `?email=invalido` |

O corpo do `GET` traz `sub`, `email`, `email_verified`, `first_name`, `last_name`, `nickname`,
`date_joined`, `updated_at`, `senha_alterada_em` (`null` nas contas anteriores ao campo),
`termos_versao` (`""` se a pessoa nunca aceitou) e `termos_versao_vigente`. As datas saem em ISO
8601, em UTC, com o deslocamento.

**Quem a API aceita.** Um `access_token` só no cabeçalho `Authorization: Bearer`; o token em
`?access_token=` ou no corpo é tratado como ausente. O token precisa do scope `conta` e de ter
sido emitido para a Application da SPA, cujo `client_id` o IdP lê de `SPA_CLIENT_ID`. O cookie
de sessão do IdP não vale nada aqui: a API não aceita sessão, e é por isso que dispensa o token
CSRF.

**As recusas.**

- 401 sem corpo, ao token ausente, vencido ou inválido, e 403 sem corpo, ao token sem o scope
  `conta`. Os dois levam o desafio `WWW-Authenticate: Bearer`, com `error` conforme o caso e com o
  parâmetro `resource_metadata` da RFC 9728. Esse parâmetro aponta para
  `/o/.well-known/oauth-protected-resource` no host do pedido, cujo `resource` é esse host
  seguido de `/o` (igual ao issuer quando o pedido chega pelo nome dele), e não a API: a SPA o
  ignora, e um cliente estrito da RFC 9728 o recusaria.
- 403 com `{"codigo": "aplicacao_nao_autorizada"}`, ao token de outra Application, e com
  `{"codigo": "conta_inativa"}`, ao token de conta desativada. Sem desafio.
- 400 na forma `{"erros": {"<campo>": [{"codigo": "...", "mensagem": "..."}]}}`. O corpo que não
  é objeto JSON dá `geral` com `json_invalido`; valor que não é texto dá `invalid`, e texto
  acima de 150 caracteres, `max_length`; a versão dos termos ausente dá `required`, e diferente
  da vigente, `termos_desatualizados`. A `mensagem` sai em inglês, e a RP exibe pelo `codigo`.
- 429 pelo teto por origem, com `Retry-After`.

A falta de aceite dos termos não bloqueia nada no IdP; o bloqueio é da SPA. A versão vigente é
uma só, e a API recusa toda outra: implantado o IdP com a versão nova, a SPA antiga recebe
`termos_desatualizados`, e implantada a SPA antes, ela envia uma versão que o IdP ainda não
conhece. Por isso, trocar a versão exige decisão nos dois projetos e uma janela em que o IdP
aceita as duas.

### 5.7 As páginas de conta e a volta à SPA

Tudo o que recebe senha é página do IdP, em português. Cadastro, recuperação e redefinição são
anônimas; troca de senha, troca de e-mail e exclusão exigem a sessão do IdP, e o cadastro a
abre. A SPA leva a pessoa até elas por navegação, nunca por `fetch`:

| Página | Caminho | Ao concluir |
| --- | --- | --- |
| cadastro | `/accounts/registrar/` | o `next` conferido, ou `{SPA_URL}/` |
| recuperação de senha | `/accounts/password_reset/` | o link do e-mail, que vale uma hora e uma vez, leva a `/accounts/reset/<uidb64>/<token>/`; a página final tem link para `{SPA_URL}/`, sem abrir sessão |
| troca de senha | `/accounts/password_change/` | `{SPA_URL}/app/conta?aviso=senha-trocada` |
| troca de e-mail | `/accounts/email/` | `{SPA_URL}/app/conta?aviso=email-trocado` |
| exclusão | `/accounts/excluir/` | `{SPA_URL}/?conta=desativada` ou `{SPA_URL}/?conta=apagada`, sem sessão |

O "Cancelar" das três últimas leva a `{SPA_URL}/app/conta`, e o cadastro tem links para
`{SPA_URL}/termos` e `{SPA_URL}/privacidade`. Essas são as rotas da SPA que o IdP conhece, e
mudar uma delas do lado da SPA quebra a volta sem erro no IdP. Das páginas de conta, só o
cadastro lê `next`.

**O que cada uma muda além da conta.**

- A troca de senha mantém a sessão do IdP em que foi feita e derruba as outras. A redefinição
  derruba todas, e também confirma o e-mail: quem abriu o link leu a caixa.
- Troca de senha, redefinição e exclusão revogam os tokens da conta em **todas** as
  Applications. A RP descobre isso na próxima chamada, pelo 401.
- A troca de e-mail vale na hora e mantém o `sub` e as sessões. `email_verified` volta a falso,
  o link de confirmação vai ao endereço novo, e um aviso vai ao antigo.
- A exclusão oferece desativar ou apagar, e recusa conta da equipe. Conta dona de Application só
  desativa (seção 4).

## 6. O que o `id_token` afirma

Seis claims de identidade, e nenhuma além delas:

| Claim | Origem | Scope que a libera |
| --- | --- | --- |
| `sub` | o UUID (_Universally Unique Identifier_) versão 4 da conta, em texto minúsculo com hífens | `openid` |
| `name` | `get_full_name()` da conta | `profile` |
| `nickname` | o apelido da conta, presente mesmo vazio | `profile` |
| `updated_at` | a última mudança de nome, apelido, e-mail ou verificação, em segundos desde 1970 | `profile` |
| `email` | o e-mail da conta, em minúsculas, que é o identificador de login | `email` |
| `email_verified` | `true` se o endereço atual foi confirmado | `email` |

O mapa é estrito: com `openid` sozinho chega apenas `sub`; `profile` acrescenta `name`,
`nickname` e `updated_at` sem acrescentar `email`, e `email` acrescenta `email` e
`email_verified` sem acrescentar os de `profile`. `given_name` e `family_name` não saem. Os cinco
arranjos estão fixados em `tests/test_oauth_validators.py`. O scope `conta` não libera claim
nenhuma.

Junto delas vêm as claims de protocolo que a verificação exige — `iss`, `aud`, `exp`, `iat` — e
as que o `oauthlib` acrescenta conforme o pedido, entre elas `nonce`, `auth_time`, `at_hash` e
`c_hash`.

**`name` pode chegar presente e vazia.** Ela sai de `get_full_name()`, e uma conta sem nome e
sem sobrenome preenchidos produz `"name": ""`. A chave existe; o valor é a string vazia. Não é
defeito, e a RP não deve tratar isso como resposta malformada.

**`sub` é o UUID da conta, e não a chave primária**, que fica interna (ADR 0031). Ele não muda
com o e-mail e não revela a sequência do banco. A chave de identidade que a RP guarda é o par
`(iss, sub)`, conforme a OIDC Core §5.7 — nunca o `email`, que é mutável, nem o `sub` sozinho.

**A transição do `sub`.** A implantação da ADR 0031 troca o `sub` de toda conta, da chave
primária para o UUID, sem volta. A sessão da RP aberta antes dela traz o `sub` antigo no
`id_token`, e o `/o/userinfo/` já responde com o novo: a SPA mostra erro até o reload. Quem
guardou o `sub` antigo perde a correlação; ela passa pelo admin do IdP.

`GET /o/userinfo/`, com o `access_token` no cabeçalho `Authorization: Bearer`, devolve as
mesmas claims sob os mesmos scopes.

## 7. O que o IdP não afirma

A seção que mais importa para quem integra: cada linha abaixo é uma garantia que a RP **não**
recebe e, portanto, precisa obter de outro lugar ou dispensar por escrito.

- **`email_verified` falso não diz que o endereço é alheio, e verdadeiro vale só para o
  endereço atual.** As contas anteriores à ADR 0031 nascem com ela falsa, a troca de e-mail a
  zera, e só o link de confirmação ou a redefinição de senha a liga. Um antivírus que abra o
  link confirma a conta sem clique humano. Com ela falsa, a RP não pode presumir que o endereço
  recebido pertence a quem se autenticou.
- **Nada além das seis claims da seção 6.** Não há grupos, papéis, telefone, foto nem atributo
  organizacional. O `claims_supported` da descoberta é exatamente `sub`, `name`, `nickname`,
  `updated_at`, `email` e `email_verified`, e o acoplamento entre ele e o que o servidor emite
  está verificado em `tests/test_authorization_code_flow.py`.
- **O `access_token` não é inspecionável pela RP.** Ele é uma string opaca, não um JWT (JSON
  Web Token), e a introspecção não está utilizável: `/o/introspect/` exige um scope que este
  IdP não declara e responde 403, conforme
  `docs/adr/0002-usar-django-oauth-toolkit-como-servidor-de-autorizacao.md`. Quem precisar do
  estado corrente chama `/o/userinfo/`, uma requisição ao IdP por consulta.
- **Não há garantia de revogação por desativação de conta pelo admin:** `access_token` e
  `refresh_token` já emitidos seguem válidos até vencer, e nem `/o/userinfo/` nem a renovação
  conferem se a conta está ativa. Só a API de conta recusa, com `conta_inativa`. A desativação
  pela própria pessoa, na página de exclusão, revoga os tokens em todas as Applications.

## 8. Verificar o token

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

## 9. Ciclo de vida dos tokens

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

Fora do "Sair" da seção 5.3, os tokens já emitidos são revogados pelo IdP: pela troca de
senha, pela redefinição e pela exclusão feitas pela pessoa (seção 5.7), e por quem opera.

## 10. Ambiente

**Em produção, a RP não precisa de nada além do contrato.** O IdP é servido por um túnel da
Cloudflare, e o certificado que o cliente vê é o Universal da borda, que os clientes já
conhecem (ADR 0027). A borda termina o TLS e vê em texto claro o que passa por ela, os tokens
inclusive (ADR 0027, "Um terceiro vê tudo"). O que o IdP protege e o que não protege quando
exposto está em `docs/seguranca.md`.

**RP com back-end funciona sem configuração no IdP.** A troca em `/o/token/` e a consulta a
`/o/userinfo/` partem do servidor da RP e não passam pelo CORS.

**RP no navegador exige entrada em `CORS_ALLOWED_ORIGINS`**, que sai vazia no `.env.example`.
Enquanto a origem da RP não estiver lá, o `fetch` a `/o/token/`, a `/o/userinfo/` ou à API de
conta recebe erro de CORS (seção 5.4).

**A SPA implanta depois do IdP.** O scope `conta`, o `create` e a API de conta entram com o IdP
(ADR 0031). Implantada antes, a SPA pediria `conta` e receberia `invalid_scope`, e o "Criar
conta" receberia 400. Antes de implantar a SPA, confira na descoberta `conta` em
`scopes_supported` e `create` em `prompt_values_supported`. O IdP de cada ambiente também
precisa de `SPA_CLIENT_ID` igual ao `client_id` da Application da SPA: errado, nada falha no
boot, e toda chamada à API recebe 403 `aplicacao_nao_autorizada`.

### 10.1 O certificado da jornada de container

O IdP tem TLS quando está atrás do proxy de terminação, e não tem quando roda em
`http://localhost:8000`. É a mesma divisão da seção 2, e o esquema do `issuer` a denuncia. Na
jornada de container, em `idp.localhost`, o certificado sai de uma **autoridade certificadora
(CA) interna do Caddy, que cliente nenhum conhece de fábrica**. Esta subseção vale só para ela.

O sintoma é a troca em `/o/token/` falhar antes de haver resposta, com `certificate verify
failed: unable to get local issuer certificate`. Recusar é o comportamento correto de quem não
conhece a autoridade, e não defeito do IdP nem erro de integração.

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

## 11. Exemplo mínimo

O fluxo inteiro fechado à mão — gerar o par PKCE, abrir `/o/authorize/` no navegador, ler o
código e trocá-lo com `curl` — está em `docs/receita.md`, na seção "Fechar o fluxo PKCE à
mão". Os comandos não são reproduzidos aqui: um exemplo copiado envelhece em silêncio.
