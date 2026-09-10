# Runbook — nova_api

Este documento é indexado por **sintoma**, não por assunto. É o que o distingue dos demais:
quem chega aqui está com o sistema quebrado, sabe o que viu na tela e não sabe o nome da
causa. Não se lê em ordem — procura-se a linha que descreve o que aconteceu.

Ele é o dono de todas as falhas silenciosas deste provedor de identidade (IdP, de *Identity
Provider*) e da operação corrente. Os demais documentos apontam para cá em vez de repetir.

## Como usar este documento

| O que você viu | Seção |
| --- | --- |
| Não sei por onde começar | [Onde olhar primeiro](#onde-olhar-primeiro) |
| O JWKS devolve `{"keys": []}` com HTTP 200 | [1](#1-o-jwks-devolve-keys--com-http-200) |
| O JWKS devolve HTTP 500 | [2](#2-o-jwks-e-o-otoken-devolvem-http-500) |
| `POST /o/token/` devolve 500 em HTML, sem token nenhum | [3](#3-post-otoken-devolve-500-em-html-e-token-nenhum) |
| O `id_token` chega só com `sub`, sem `name` e sem `email` | [4](#4-o-id_token-chega-só-com-sub) |
| Consenti e voltei com `error=invalid_request`, sem `code` | [5](#5-a-tela-de-consentimento-aparece-e-o-redirecionamento-volta-com-erro) |
| `/o/authorize/` recusa antes de mostrar a tela | [6](#6-oauthorize-recusa-antes-da-tela-de-consentimento) |
| Container `unhealthy` eterno, aplicação atendendo por fora | [7](#7-container-unhealthy-eterno-com-a-aplicação-atendendo-por-fora) |
| `password authentication failed`, com as strings idênticas | [8](#8-password-authentication-failed-com-as-duas-strings-idênticas) |
| Erro de bind na porta 8000 | [9](#9-erro-de-bind-na-porta-8000) |
| 404 num recurso estático, ou CSS editado que não muda | [10](#10-404-em-recurso-estático-ou-css-que-não-muda-na-tela) |
| `/health` devolve 503 | [11](#11-health-devolve-503) |
| `createsuperuser` falha por unicidade | [12](#12-createsuperuser-falha-por-unicidade) |
| A relying party não acha a descoberta e recebe 404 | [13](#13-a-relying-party-recebe-404-ao-procurar-a-descoberta) |
| Nada quebrou, e eu quero saber o que está errado assim mesmo | [14](#14-as-falhas-que-não-produzem-sintoma-nenhum-hoje) |
| O processo não sobe, e a mensagem cita `AUDIT_LOG_PATH` | [15](#15-o-processo-não-sobe-e-a-mensagem-cita-audit_log_path) |

A operação do dia a dia — revogar acesso, limpar tabela, trocar chave, subir versão — está em
[Operação corrente](#operação-corrente).

## Onde olhar primeiro

Três lugares, nesta ordem. Os comandos usam o nome de serviço do `docker-compose.yml`, porque
nenhum serviço declara `container_name` e o nome real do container é gerado pelo compose.

**1. O estado dos três serviços.**

```bash
docker compose ps
```

`app`, `postgres` e `redis` precisam estar `healthy`. Um `postgres` ou um `redis` fora de
`healthy` explica sozinho um `app` que nem subiu: a espera pelos dois é do `depends_on` com
`condition: service_healthy`, e não de laço no `docker/entrypoint.sh`.

**2. O log da aplicação.**

```bash
docker compose logs app
```

Ali estão a falha do `migrate`, o traceback dos 500 e os dois `logger.exception` do `/health`.
O `LOGGING` de `config/settings.py` manda tudo para `ext://sys.stdout` e não emudece
`django.request` com `DEBUG=False`, que é o modo em que o container roda.

**Toda linha emitida pela aplicação é um objeto JSON**, com `ts` em UTC, `level`, `logger`,
`request_id` e `msg`, mais `exc` quando houver traceback (ADR — Architecture Decision Record —
`docs/adr/0012-emitir-o-log-operacional-em-json-com-identificador-de-requisicao.md`). Quem opera
precisa de `jq`:

```bash
docker compose logs --no-color --no-log-prefix app | jq -R 'fromjson? | select(.level=="ERROR")'
```

**Nenhuma das três opções é enfeite, porque o log do container é misto.** As linhas do gunicorn
— boot, sinais, worker — e a saída de `migrate` e de `collectstatic` não atravessam o `logging`
do Django e continuam em texto plano, deliberadamente: é o que mantém a falha de `migrate`
legível sem rolagem. Um `jq .` puro morre na primeira delas. O `-R` mais o `fromjson?` leem o que
é JSON e descartam o resto; o `--no-log-prefix` remove o `app-1  | ` que o compose antepõe a cada
linha, e **sem ele o comando não devolve erro nenhum: devolve nada**.

Três propriedades desse log valem saber antes de precisar dele:

- **A linha sai na hora.** O `Dockerfile` declara `PYTHONUNBUFFERED=1`; sem ele, stdout ligado
  a um pipe — que é o que `docker logs` dá — seria bufferizado em bloco, e o traceback de um
  500 ficaria retido até o buffer encher.
- **Toda linha de um mesmo pedido carrega o mesmo `request_id`.** É o que amarra o traceback de
  `django.request` à linha de `oauth2_provider` da mesma requisição, entre os três workers —
  inclusive a linha de erro que o Django emite depois de a cadeia de middleware retornar, que é
  a de todo 404, 503 e 400 (ADR
  `docs/adr/0014-manter-o-identificador-de-requisicao-ate-a-requisicao-seguinte.md`). O
  identificador é sempre gerado aqui dentro: cabeçalho de entrada não é lido, e nenhuma resposta
  o devolve — quem investiga pelo navegador acha o pedido pelo horário. A contrapartida está no
  que **não** nasce numa requisição: essa linha sai com `-` num processo que ainda não atendeu
  nada, e com o identificador da última requisição num processo que já atendeu.
- **Há linha de acesso, e ela não é do gunicorn.** O `exec gunicorn` do `docker/entrypoint.sh`
  continua sem `--access-logfile`; quem emite a linha é o middleware do projeto, no logger
  `access`, com `route` (o **nome** da rota, nunca o caminho), `method`, `status` e
  `duration_ms`. O `/health` fica de fora por `ACCESS_LOG_EXCLUDED_ROUTES`, e é isso que impede
  a sonda de dez em dez segundos de afogar o log. Para toda rota que não seja a sonda, a
  ausência de registro passou a ser sinal:

```bash
docker compose logs --no-color --no-log-prefix app | jq -R 'fromjson? | select(.logger=="access")'
```

**3. O veredito da sonda do container.**

```bash
docker inspect --format '{{json .State.Health.Log}}' "$(docker compose ps -q app)"
```

A sonda do `HEALTHCHECK` é um `urllib.request.urlopen` do interpretador da própria imagem, e o
erro que ela levanta propaga de propósito: o texto fica aqui. É este log — não o da aplicação —
que distingue um 503 honesto de uma sonda que morreu sem resposta, e é ele que separa as duas
causas da seção 7.

## Sintoma, causa, verificação

### 1. O JWKS devolve `{"keys": []}` com HTTP 200

**Sintoma.** `http://localhost:8000/o/.well-known/jwks.json` responde 200 com uma lista de
chaves vazia. Nada mais parece errado: a descoberta responde e **os quatro endpoints — authorize,
token, userinfo e jwks — continuam listados**. Procurar endpoint faltando não detecta nada.

**Causa.** `OIDC_RSA_PRIVATE_KEY` está vazia no `.env`. O IdP sobe inteiro e falha em silêncio.

**Verificação.** O sinal é o `alg` da descoberta, não a lista de endpoints:

```bash
curl -s http://localhost:8000/o/.well-known/openid-configuration \
  | python3 -m json.tool | grep id_token_signing_alg
```

Com a chave, `["RS256","HS256"]`. Sem ela, cai para `["HS256"]`.

**Correção.** Gere e cole a chave, e recrie o container para que ele releia o `.env` — ver
[Trocar a chave RSA](#trocar-a-chave-rsa).

### 2. O JWKS e o `/o/token/` devolvem HTTP 500

**Sintoma.** Diferente da seção 1: aqui a resposta não é uma lista vazia, é um erro, e o log
traz um `ValueError` ao carregar a chave.

**Causa.** `OIDC_RSA_PRIVATE_KEY` está presente mas não carrega como PEM (Privacy-Enhanced
Mail) — tipicamente um PEM cujas quebras de linha não estão escapadas como `\n`, que é o
formato que `env.str(..., multiline=True)` desfaz. O comentário que registra essa falha está em
`config/settings.py`, na leitura da variável.

**Correção.** Regere a linha com `./scripts/gen_dev_key.sh`, que já imprime o escape correto, e
cole-a inteira, em uma linha só.

### 3. `POST /o/token/` devolve 500 em HTML, e token nenhum

**Sintoma.** O `curl` da troca devolve a página de erro HTML do Django. Não há `id_token`
ausente para investigar: não há resposta.

**Causa.** O campo `algorithm` da Application está em branco no admin.

**O que custa a tarde é a distância entre a causa e o sintoma.** `/o/authorize/` **não acusa
nada**: a tela de consentimento responde 200 e o `code` é emitido normalmente. Quem parte do
sintoma vai depurar o `/o/authorize/`, que estava certo o tempo todo.

**Verificação.**

```bash
docker compose logs --no-color --no-log-prefix app \
  | jq -R 'fromjson? | select((.exc // "") | test("ImproperlyConfigured"))'
```

A mensagem é `ImproperlyConfigured: This application does not support signed tokens`, e ela vem
no campo `exc`, que carrega o traceback — o `msg` do registro de `django.request` traz apenas
`Internal Server Error: /o/token/`. Acrescente `| .exc` ao filtro para ler a pilha formatada.

**Correção.** Em `/admin/oauth2_provider/application/`, ponha `algorithm` em **RS256**. Os
outros três campos que importam são `client_type` = public, `authorization_grant_type` =
authorization-code e a `redirect_uri` registrada.

### 4. O `id_token` chega só com `sub`

**Sintoma.** O fluxo fecha, o `id_token` é assinado e verifica, e as claims `name` e `email`
simplesmente não estão lá.

**Causa.** A chave `OAUTH2_VALIDATOR_CLASS` do bloco `OAUTH2_PROVIDER`, em `config/settings.py`,
está ausente ou aponta para um caminho que não é `accounts.oauth_validators.IdPOAuth2Validator`.
É contrato por string: caminho **errado** falha ruidosamente no boot; chave **ausente** não
produz erro nenhum, e o toolkit emite o `id_token` com o que a classe base dele monta.

**Verificação.** A descoberta denuncia junto — `claims_supported` cai para `["sub"]`:

```bash
curl -s http://localhost:8000/o/.well-known/openid-configuration \
  | python3 -m json.tool | grep -A 4 claims_supported
```

### 5. A tela de consentimento aparece, e o redirecionamento volta com erro

**Sintoma.** Tudo corre normalmente até o consentimento. Ao consentir, o navegador volta para a
`redirect_uri` com `error=invalid_request` e sem `code`.

**Causa.** `code_challenge_method=plain` na requisição de autorização. A descoberta anuncia
`code_challenge_methods_supported` igual a `["S256"]`, e é literal — a chave
`COMPLIANT_BCP_RFC9700_PKCE_METHOD` do bloco `OAUTH2_PROVIDER` é o que restringe o PKCE (Proof
Key for Code Exchange) a `S256`.

**A recusa acontece no POST do consentimento, não antes.** O GET de `/o/authorize/` responde
200 e mostra a tela normalmente. Quem trocar o método para `plain` só para simplificar a
depuração vai depurar a tela errada.

**Correção.** Use `code_challenge_method=S256`, com o desafio derivado do verificador por
SHA-256 e base64url sem preenchimento. O par se gera com o Python da própria imagem; o passo a
passo está em `docs/receita.md`.

### 6. `/o/authorize/` recusa antes da tela de consentimento

**Sintoma.** A tela de consentimento nunca aparece. O que volta é 400, ou um redirecionamento
de erro sem `code`.

**Duas causas, ambas na requisição de autorização:**

- **`redirect_uri` diferente da registrada.** A comparação é de **igualdade exata, não de
  prefixo**: `http://localhost:8000/noop/` não casa com `http://localhost:8000/noop`
  registrada — uma barra a mais basta. O resultado é 400 direto no GET, sem `Location`.
- **`code_challenge` ausente.** `PKCE_REQUIRED` está declarado em `config/settings.py`, e
  cliente público sem PKCE é recusado antes da tela, com `error=invalid_request`.

**Verificação.** Compare caractere a caractere a `redirect_uri` da barra de endereços com a
registrada em `/admin/oauth2_provider/application/`, e confirme que a query string carrega
`code_challenge` e `code_challenge_method=S256`.

### 7. Container `unhealthy` eterno, com a aplicação atendendo por fora

Esta é a entrada mais traiçoeira do documento, por três razões: o sintoma é o mesmo nos dois
casos, **duas causas distintas o produzem**, e **a mesma mudança de ambiente dispara as duas**.

**Sintoma.** `docker compose ps` mostra `app` em `unhealthy` indefinidamente, enquanto o IdP
responde normalmente a quem chega de fora, pelo proxy.

**A mudança que dispara.** Pôr um proxy TLS (Transport Layer Security) na frente. Quem faz isso
liga `BEHIND_TLS_PROXY=True`, troca `BASE_URL` para `https://...` e — o movimento natural, e
errado — estreita `ALLOWED_HOSTS` para o nome público do proxy. As três edições são a mesma
sessão de trabalho.

**Causa A — o redirecionamento para HTTPS alcança a sonda.** Com `BEHIND_TLS_PROXY=True`,
`SECURE_SSL_REDIRECT` fica ativo e o `SecurityMiddleware` responde 301 em `process_request`,
antes de qualquer view. A sonda chega de dentro, em texto claro e sem `X-Forwarded-Proto`:
recebe o 301, segue para `https://127.0.0.1:8000/health` e morre no handshake contra um gunicorn
que fala HTTP em claro. O que fecha essa causa é `SECURE_REDIRECT_EXEMPT = [r"^health$"]`, em
`config/settings.py` (ADR — Architecture Decision Record —
`docs/adr/0010-isentar-health-do-redirecionamento-para-https.md`). O acoplamento entre essa
expressão regular e o `path("health", ...)` de `config/urls.py` não tem mecanismo: renomear a
rota quebra a isenção em silêncio e devolve este mesmo sintoma.

**Causa B — `ALLOWED_HOSTS` sem `127.0.0.1`.** A sonda bate em `http://127.0.0.1:8000/health` e
envia `Host: 127.0.0.1:8000`. Com `DEBUG=False`, `ALLOWED_HOSTS` **tem de continuar listando
`127.0.0.1`** mesmo depois que o IdP passar a ser servido só por um nome público. Estreitada a
lista, a sonda recebe **400 `DisallowedHost`** e o container volta ao mesmo `unhealthy` eterno.

**Verificação — é o log da sonda que separa as duas:**

```bash
docker inspect --format '{{json .State.Health.Log}}' "$(docker compose ps -q app)"
```

- `HTTP Error 400: Bad Request` → causa B. A linha de `DisallowedHost` aparece também em
  `docker compose logs app`.
- erro de conexão ou de handshake TLS → causa A.
- **a sonda encerrada sem nenhum status HTTP** → não é nenhuma das duas: a view não chegou a
  montar resposta. As duas janelas de espera que nenhum teto alcança estão listadas em
  `docs/adr/0011-dar-teto-de-tempo-ao-health-e-derivar-o-healthcheck-dele.md`.

**Correção.** Causa A: manter a isenção declarada. Causa B: manter `127.0.0.1` em
`ALLOWED_HOSTS`, ao lado do nome público.

Nada disso produz alerta antes de acontecer: com `BEHIND_TLS_PROXY=False`, que é o valor do
`.env.example`, a isenção é inerte e o defeito só aparece no primeiro ambiente com TLS de
verdade — o que custa mais caro.

### 8. `password authentication failed`, com as duas strings idênticas

**Sintoma.** O `migrate` do entrypoint falha com `password authentication failed`, e a senha em
`POSTGRES_PASSWORD` é, a olho nu, perfeitamente igual à que está na `DATABASE_URL`.

**Causa.** Um `$` no valor. O `.env` atravessa três gramáticas — o `django-environ`, a
interpolação do próprio docker compose e a gramática de URL (Uniform Resource Locator) de
`DATABASE_URL` e `REDIS_URL`. O compose interpola e **trunca** o valor a partir do `$`,
enquanto o `django-environ` lê o valor íntegro. As duas metades do sistema passam a usar senhas
diferentes sem que nenhuma linha do arquivo pareça errada.

**Correção.** Regere a senha sem caracteres especiais — `openssl rand -hex 24` satisfaz a regra
por construção — e refaça a `DATABASE_URL` coerente com ela. As regras de caracteres do `.env`
inteiro estão em `docs/receita.md`; elas não são cosméticas.

### 9. Erro de bind na porta 8000

**Sintoma.** O `app` não sobe, e a mensagem fala de bind — de endereço já em uso.

**Causa.** Um `runserver` da jornada de construção está ocupando a 8000, e o serviço `app`
publica em `127.0.0.1:8000`. **A mensagem fala de bind, não de `runserver`**, e é aí que ela
engana.

**Correção.** Pare o `runserver` antes de `docker compose up --wait`. As duas jornadas não
convivem na mesma porta — ver [As duas jornadas](#as-duas-jornadas-e-como-não-misturá-las).

O mesmo vale, com outra porta, para `POSTGRES_PORT` e `REDIS_PORT`: são as portas publicadas
**no host**, com default `5432` e `6379`, e existem justamente para serem trocadas quando já
houver um Postgres ou um Redis nesta máquina. As portas internas do compose não mudam.

### 10. 404 em recurso estático, ou CSS que não muda na tela

São dois sintomas com causas diferentes. O backend de estáticos é
`whitenoise.storage.CompressedStaticFilesStorage`: compressão sim, manifesto de hash não (ADR
`docs/adr/0008-servir-estaticos-com-whitenoise-sem-manifesto-de-hash.md`).

**404 no recurso.** `collectstatic` não rodou. A omissão aparece assim, como 404 no arquivo, e
**não** como erro de template — sem manifesto, `{% static %}` não consulta artefato nenhum em
tempo de renderização. No container o `docker/entrypoint.sh` roda `collectstatic` no boot; na
jornada de construção, é comando à mão.

**CSS editado que não muda na tela.** O WhiteNoise monta o índice de arquivos **no boot**, e o
modo de recarga automática segue `DEBUG`, que é `False`. Editar o arquivo em `static/` não
basta e recolher também não: é preciso `collectstatic` **e** reiniciar o processo.

A suíte de testes **não** exige `collectstatic` prévio; é decisão registrada, não acaso.

### 11. `/health` devolve 503

**Sintoma.** O endpoint responde, e responde 503.

**Isso é o `/health` funcionando.** O corpo tem sempre as mesmas três chaves, em sucesso e em
falha, e é a que estiver em `"error"` que diz onde procurar:

```bash
curl -s -o /dev/stdout -w '\n%{http_code}\n' http://localhost:8000/health
```

- `"database": "error"` → Postgres inalcançável, ou aceitando conexão sem responder dentro do
  `connect_timeout` de 2 s;
- `"cache": "error"` → Redis inalcançável, ou aceitando conexão e não devolvendo o que gravou.

**A causa exata não está no corpo.** As três chaves não a carregam, por contrato (ADR
`docs/adr/0009-isolar-a-view-de-health-da-sessao-e-do-usuario.md`). Ela está no log, escrita
pelos dois `logger.exception` de `config/views.py`:

```bash
docker compose logs --no-color --no-log-prefix app \
  | jq -R 'fromjson? | select(.msg | startswith("health:"))'
```

As duas mensagens são `health: banco inalcançável` e `health: cache inalcançável ou
inconsistente`, cada uma seguida do traceback com o motivo real — recusa, timeout ou
autenticação.

Um detalhe que evita uma busca inútil: um `SELECT 1` verde prova conectividade, não capacidade.
Um banco alcançável com migração pendente responde 200 enquanto toda requisição real falha; no
container, quem fecha essa janela é o `migrate` do entrypoint, não este endpoint.

Os tempos do `HEALTHCHECK` são derivados, não escolhidos, e **não devem ser recalculados por
conta própria**: a cadeia inteira está em
`docs/adr/0011-dar-teto-de-tempo-ao-health-e-derivar-o-healthcheck-dele.md`.

### 12. `createsuperuser` falha por unicidade

**Sintoma.** O comando falha dizendo que o e-mail já existe. No boot do container, a linha do
`CommandError` aparece imediatamente acima de `entrypoint: createsuperuser não criou conta`.

**Não é defeito: é o modelo funcionando.** O `accounts.User` tem `username = None` e e-mail
único como identificador de login, e **o superusuário é um só**. O `||` do entrypoint engole o
código de saída — nunca a mensagem — justamente para que este caso não derrube o container a
cada boot.

O passo só é necessário em banco novo. Se o que você queria era uma segunda conta
administrativa, use outro e-mail.

### 13. A relying party recebe 404 ao procurar a descoberta

**Sintoma.** A biblioteca da relying party (RP) informa 404 ao buscar os metadados do servidor,
e o endereço que ela tentou termina em `/.well-known/oauth-authorization-server/o`.

**Causa.** O issuer tem componente de path — é `{BASE_URL}/o` (ADR
`docs/adr/0007-fixar-o-issuer-do-idp-em-base-url-barra-o.md`) —, e aí a OIDC (OpenID Connect)
Discovery 1.0 e a RFC 8414 deixam de coincidir. Este IdP publica a forma da OIDC Discovery 1.0,
que é o issuer concatenado com o sufixo:

```
http://localhost:8000/o/.well-known/openid-configuration
```

A forma path-component da RFC 8414 não foi montada, e responde 404. O contrato completo com a
relying party está em `docs/integracao-rp.md`.

### 14. As falhas que não produzem sintoma nenhum hoje

Oito defeitos deste sistema não têm entrada de sintoma porque **não têm sintoma**. Só se
descobrem lendo, e é por isso que estão listados aqui.

**`BEHIND_TLS_PROXY=False` atrás de um proxy TLS real.** Cookie com flag `Secure`, HSTS (HTTP
Strict Transport Security), redirecionamento para HTTPS e `SECURE_PROXY_SSL_HEADER` dependem
dessa variável — nunca de `DEBUG`. Com ela falsa atrás de um proxy de verdade, os cookies vão
sem `Secure` e sem HSTS, **silenciosamente**: não há alerta, e o aviso vive só na documentação.
Um check de startup resolveria; não existe.

**`CorsMiddleware` fora do topo do `MIDDLEWARE`.** Resposta emitida por um middleware acima dele
sai sem os cabeçalhos de CORS (Cross-Origin Resource Sharing). Com a allowlist vazia — que é a
configuração de hoje — o middleware é inerte, e uma posição errada é **indetectável**. O sinal
só apareceria na fase de uma SPA (Single-Page Application), como erro de CORS que ninguém
associa àquela linha.

**Log operacional só em stdout, sem coleta externa.** O log some quando o container é recriado.
Se você vai recriar o `app` para investigar alguma coisa, **salve o log antes**:

```bash
docker compose logs --no-color app > /tmp/app.log
```

Vale para o log operacional, e não para a trilha de auditoria: ela vive em volume nomeado e
sobrevive ao recreate — ver [A trilha de auditoria](#a-trilha-de-auditoria-onde-fica-e-como-lê-la).

**Linha de trilha perdida por falha de escrita do handler.** Disco cheio, volume desmontado ou
permissão negada no arquivo da trilha **não** derrubam nada e não produzem linha de erro no log:
o próprio `logging` engole o erro do handler e o manda para `stderr`. A trilha simplesmente para
de crescer enquanto o IdP segue autenticando normalmente. Os receptores de `accounts/auditoria.py`
capturam a própria exceção deles e gritam no log operacional, mas essa captura não alcança a
escrita do handler. A verificação é olhar o tamanho do arquivo depois de um login.

**O identificador de requisição permanece no worker depois da requisição.** Não há `reset` na
saída do middleware, deliberadamente: sem isso, a linha de erro de todo 404, 503 e 400 sairia
sem o pedido a que pertence, porque o Django a emite depois que a cadeia de middleware retornou
(ADR `docs/adr/0014-manter-o-identificador-de-requisicao-ate-a-requisicao-seguinte.md`). O preço
é este: uma linha emitida **fora** de qualquer requisição, num processo que já atendeu alguma,
sai carimbada com o identificador da última — parece correlacionada e não está, e nada a
distingue de uma correta. No container não há código que registre entre um pedido e o seguinte;
sob `manage.py test`, há.

**`LOG_LEVEL=WARNING` apaga a linha de acesso inteira.** A linha de acesso é log operacional e
segue `LOG_LEVEL`, que é coerente; o efeito é que subir o nível para reduzir ruído remove, sem
aviso nenhum, todo o registro de requisição — e volta-se ao estado em que a ausência de registro
não prova nada. A trilha de auditoria não é afetada: o logger `audit` tem nível `INFO` fixo, e
nenhuma variável de ambiente o desliga.

**A preflight de CORS não deixa rastro.** O middleware de observabilidade está no índice 1 do
`MIDDLEWARE`, logo abaixo do `CorsMiddleware` — e uma resposta emitida pelo `CorsMiddleware`,
como a preflight `OPTIONS`, sai sem `request_id` e sem linha de acesso. Hoje isso é inerte,
porque a allowlist está vazia e ele não emite resposta nenhuma. No dia da primeira SPA
(Single-Page Application) deixa de ser, e nada avisará: é o mesmo silêncio da posição do
`CorsMiddleware`, agora com um segundo efeito.

**`app_authorized` também dispara no refresh.** O sinal é emitido em toda resposta 200 de
`/o/token/`, o que inclui a renovação por `refresh_token`. A trilha terá mais linhas
`app_authorized` do que houve consentimentos, e quem contar linhas para contar autorizações
contará errado. O `client_id` e o `sub` de cada linha continuam corretos.

### 15. O processo não sobe, e a mensagem cita `AUDIT_LOG_PATH`

**Sintoma.** Nada sobe. Na jornada de construção, qualquer `manage.py` aborta antes de fazer o
que se pediu; no container, o `app` morre no boot. A mensagem nomeia a variável — é uma
`ImproperlyConfigured` dizendo que `AUDIT_LOG_PATH` está ausente do ambiente.

**Causa.** A linha não está no `.env`. `config/settings.py` não tem default no código, e este em
particular é ausência deliberada: um default faria a trilha gravar dentro da camada de escrita do
container e sumir no primeiro `down`, o que pareceria funcionar (ADR
`docs/adr/0013-registrar-a-trilha-de-auditoria-dos-quatro-sinais-em-arquivo-duravel.md`).

**Correção.** Acrescente `AUDIT_LOG_PATH=logs/audit.log` ao `.env`, à mão. **Não copie o
`.env.example` por cima:** o `.env` é untracked, não tem cópia, e sobrescrevê-lo apaga a chave
RSA e a `SECRET_KEY` do projeto.

Uma variante com o mesmo desfecho e outra mensagem: **a última linha do traceback é
`ValueError: Unable to configure handler 'audit'`**, que não nomeia caminho nenhum. O caminho
está mais acima, no `FileNotFoundError` ou no erro de permissão que o `logging` guardou como
causa — ler só o fim do traceback não encontra o que esta seção manda procurar. Aí a variável
existe e aponta para um diretório que não existe ou que o processo não pode escrever: o arquivo
é aberto na configuração do logging, dentro de `django.setup()`, e a falha é no boot de
propósito. Crie o diretório, ou corrija o caminho.

## Operação corrente

### Revogar o acesso de uma pessoa

`is_active=False` **não desliga token nenhum**. O que ele faz e o que ele não faz:

- **faz** — corta a sessão de navegador: o `ModelBackend` do Django devolve `None` em
  `get_user` para conta inativa (`django/contrib/auth/backends.py:230-235`), e a requisição
  seguinte passa a ser anônima. Novas autorizações ficam bloqueadas junto;
- **não faz** — não invalida `access_token` nem `refresh_token` já emitidos. O refresh segue
  trocável por token novo, e `/o/userinfo/` continua respondendo 200. Nenhum caminho de bearer
  do toolkit consulta `is_active`.

Esperar não resolve. O `access_token` expira pelo default do toolkit, 36 000 s (10 h), mas o
`refresh_token` **não expira por idade**: `REFRESH_TOKEN_EXPIRE_SECONDS` vale `None` e o
projeto não o sobrescreve. Como `ROTATE_REFRESH_TOKEN` é `True` por default, cada refresh emite
um refresh novo — a corrente se renova indefinidamente.

**O procedimento à mão, hoje, em `/admin/`:**

1. `/admin/accounts/user/` — desmarque `is_active`. Isso fecha a porta da frente.
2. `/admin/oauth2_provider/refreshtoken/?q=<e-mail>` — selecione tudo e aplique a ação
   **"Revoke selected refresh tokens"**. Revogar o refresh apaga junto o access token vinculado.
3. `/admin/oauth2_provider/accesstoken/?q=<e-mail>` — repita com **"Revoke selected access
   tokens"**, para os que não tinham refresh vinculado.
4. `/admin/oauth2_provider/grant/?q=<e-mail>` — apague os grants pendentes. Um código de
   autorização ainda não trocado continua trocável.

**Use a ação, não o `delete`.** O admin do toolkit desabilita a exclusão bruta de access e
refresh token de propósito: apagar a linha do access token deixa o refresh vinculado para trás
— a chave estrangeira `RefreshToken.access_token` é `SET_NULL` —, e esse órfão continua capaz
de emitir access token novo, anulando a revogação.

O endpoint `/o/revoke_token/` (RFC 7009) existe sob o prefixo `o/`, mas exige apresentar o
token que se quer revogar: é ferramenta da relying party, não de quem opera o IdP.

### Limpeza de tokens e de sessões

Nenhum dos dois comandos está agendado. As tabelas do toolkit e a `django_session` crescem
indefinidamente até que alguém os rode à mão:

```bash
docker compose exec app python manage.py cleartokens
docker compose exec app python manage.py clearsessions
```

**O `cleartokens` recolhe menos do que o nome promete neste projeto.** Ele mesmo avisa em
stderr: sem `REFRESH_TOKEN_EXPIRE_SECONDS` — que este projeto não declara —, os refresh tokens
nunca envelhecem, e o comando remove apenas os revogados e os órfãos. Access e ID tokens
expirados, mas ainda vinculados a um refresh vivo, permanecem. Reduzir de verdade a tabela
exige, hoje, revogar antes.

`clearsessions` apaga as linhas expiradas de `django_session`. A sessão vive no Postgres com
cópia quente no Redis (`SESSION_ENGINE = cached_db`), e é a linha do Postgres que se acumula.

### Trocar a chave RSA

```bash
./scripts/gen_dev_key.sh
```

O script imprime a linha `OIDC_RSA_PRIVATE_KEY=...` pronta, com as quebras do PEM escapadas
como `\n`. **Cole-a você mesmo no `.env`.** O script não escreve no arquivo de propósito:
escrita automática sobrescreveria sem confirmação uma chave possivelmente em uso.

Depois de colar, recrie o container — o `.env` é lido na criação, não a cada reinício:

```bash
docker compose up -d --force-recreate app
```

**O que a troca quebra.** Existe uma única chave ativa, sem conjunto de rotação (ADR
`docs/adr/0004-assinar-tokens-com-rs256-e-custodiar-a-chave-privada-no-ambiente.md`):

- todo `id_token` já emitido deixa de verificar contra o JWKS publicado;
- cada relying party guarda o JWKS em cache pelo prazo dela, e enquanto esse cache não vencer
  ela também rejeita os `id_token` assinados com a chave **nova**. A janela ruim é dos dois
  lados, não de um;
- `access_token` e `refresh_token` são opacos — linhas no Postgres, não artefatos assinados — e
  sobrevivem à troca. Quem depende deles não percebe nada.

A primeira rotação será disruptiva por construção. A chave de produção não sai deste script:
`gen_dev_key.sh` gera 2048 bits fixos, que é o piso aceito para RS256 (RSA com SHA-256).

### A trilha de auditoria: onde fica e como lê-la

Quatro eventos são registrados no instante em que acontecem: `user_logged_in`,
`user_login_failed`, `user_logged_out` e `app_authorized`. O arquivo é JSON por linha, no mesmo
esquema do log operacional e com o mesmo `request_id`, o que permite casar uma linha de auditoria
com o traceback do mesmo pedido.

**O casamento por `request_id` tem janela.** Ele vale enquanto o container corrente não tiver sido
recriado: o log operacional existe só em stdout e morre a cada `docker compose build` mais
`up -d`, que é a sequência de [Subir versão nova](#subir-versão-nova); a trilha é durável e
sobrevive às duas. Uma linha `app_authorized` de novembro investigada em fevereiro não tem
traceback com que casar, e `docker compose logs app | jq 'select(.request_id=="9f2c...")'` devolve
vazio. Salvar o log operacional antes de recriar o container é o que a
[seção 14](#14-as-falhas-que-não-produzem-sintoma-nenhum-hoje) prescreve.

Onde ele fica depende da jornada:

| Jornada | Caminho | Sobrevive a |
| --- | --- | --- |
| construção | `logs/audit.log`, relativo ao diretório de trabalho | tudo, menos `git clean -xd` |
| clonar-e-rodar | `/var/log/nova_api/audit.log`, no volume nomeado `auditlog` | `docker compose down`, e não `down -v` |

```bash
docker compose exec app cat /var/log/nova_api/audit.log | jq -c 'select(.event=="user_logged_in")'
```

O `jq` roda no host: a imagem é `python:3.14-slim` e não o traz. Os campos de cada linha, além
dos comuns, são `event` — que recebe o **nome do sinal**, para levar por `grep` até quem o emite
—, `sub`, `ip` e `outcome`; mais `client_id` em `app_authorized` e `identifier_sha256` em
`user_login_failed`.

**Nenhum e-mail é gravado, e nenhum valor de token.** A pessoa aparece pelo `sub`, que é a chave
primária do usuário — a mesma claim `sub` de todo `id_token`. Numa falha de autenticação não há
pessoa confirmada a nomear, e o que se registra é o resumo SHA-256 do identificador tentado.
Procurar as tentativas contra uma conta conhecida exige recalcular o resumo:

```bash
python3 -c 'import hashlib,sys; print(hashlib.sha256(sys.argv[1].encode("utf-8")).hexdigest())' \
  pessoa@exemplo.com
```

O resumo é calculado sobre o valor **como foi digitado**, sem normalizar caixa: `A@x.com` e
`a@x.com` são contas distintas sob Postgres, e por isso produzem resumos distintos. Se a busca
não achar nada, tente as outras caixas antes de concluir que não houve tentativa.

**A ausência de linha não prova a ausência do evento.** Procurar um `sub` e não achar nada é
compatível com quatro situações, e nada na trilha as distingue:

- o login ocorreu **na outra jornada**, e está em `logs/audit.log`, no host. A trilha bifurca por
  jornada; o Postgres é o mesmo nas duas, de modo que a identidade é única e a evidência não;
- o **volume foi recriado**, e para isso basta um clone do repositório em diretório de outro nome,
  porque o nome do volume carrega o nome do projeto do compose. Ver
  [Os volumes nomeados](#os-volumes-nomeados-e-por-que-down--v-é-grave);
- a **escrita do handler falhou** e o `logging` engoliu o erro para `stderr`, que é a falha sem
  sintoma da [seção 14](#14-as-falhas-que-não-produzem-sintoma-nenhum-hoje): a trilha para de
  crescer enquanto o IdP segue autenticando;
- o arquivo foi **truncado por quem tem acesso ao host**, que é o adversário que a ADR 0013 admite
  ao recusar o HMAC (Hash-based Message Authentication Code).

O arquivo tampouco declara desde quando cobre o que registra: não há marca de início, e uma
trilha curta é indistinguível de um sistema pouco usado.

**Na jornada de clonar-e-rodar, o campo `ip` não é a origem real.** O que se registra é
`REMOTE_ADDR`, e quem chega ao container passa antes pelo NAT (Network Address Translation) da
bridge do Docker: um `curl` partido do host aparece na trilha como `172.18.0.1`, o gateway da
rede do compose, e não como o endereço de quem chamou. Verificado à mão. Toda requisição de fora
do container colapsa nesse mesmo endereço, de modo que hoje o campo distingue "veio de dentro do
container" de "veio de fora", e nada mais fino. A ADR 0013 registra essa perda como futura, para
o dia em que houver um proxy à frente; ela já é presente aqui, porque o NAT já está à frente. Na
jornada de construção, com o `runserver` no host, o endereço é o real.

Duas ressalvas de contagem e uma de durabilidade: `app_authorized` sai também a cada renovação de
`refresh_token`, de modo que linhas não são consentimentos; criação de Application e revogação de
token **não** aparecem, por não existir sinal que as emita; e não há retenção nem poda — o arquivo
cresce indefinidamente, e nada o monitora.

### Os volumes nomeados, e por que `down -v` é grave

`docker compose down -v` destrói os três volumes nomeados: `pgdata`, `redisdata` e `auditlog`.
Com o `pgdata` vão-se contas, Applications, grants, tokens e a `django_session` — tudo; com o
`auditlog` vai-se a trilha de auditoria inteira, que é justamente a evidência de quem tocou o que
se perdeu. É a mesma tecla, e ela leva as duas coisas. `docker compose down` sem `-v` preserva os
três.

**A gravidade não é a perda dos dados; é a reciclagem do par `(iss, sub)`.** O `sub` de todo
`id_token` é a chave primária (PK) do usuário, um `BigAutoField` fixado antes da migração
inicial. Derrubar o volume e deixar `migrate` mais `createsuperuser` recriarem `id=1` faz **uma
pessoa diferente** receber o par `("http://localhost:8000/o", "1")` — e a OIDC Core §5.7 manda
a relying party usar exatamente esse par como chave de identidade. Do lado dela, é a mesma
pessoa.

É seguro enquanto nenhuma relying party tiver integrado. Deixa de ser no dia em que a primeira
integrar, e nada no sistema marca esse dia.

### Subir versão nova

```bash
docker compose build app
docker compose up -d --wait app
```

Três coisas a saber antes:

- **A migração roda no entrypoint**, antes do gunicorn. Isso é correto **com uma réplica**, que
  é a premissa declarada no `docker-compose.yml`; com duas, as instâncias migrariam
  concorrentemente no boot.
- **Há indisponibilidade.** Uma réplica significa que o container antigo para antes de o novo
  atender. Não há sobreposição.
- **O `start-period` do `HEALTHCHECK` é de 30 s**, e cobre `migrate` mais `collectstatic`. Uma
  migração mais longa que isso faz o veredito passar a valer antes de o gunicorn estar de pé, e
  o container pode ser declarado `unhealthy` durante um boot que está apenas demorando.

Falhou o `migrate`? O container não sobe, e a mensagem está em `docker compose logs app` — o
`set -euo pipefail` do entrypoint garante que ele pare ali em vez de seguir para o gunicorn.

## As duas jornadas, e como não misturá-las

| Jornada | Onde a aplicação roda | Quem define `DATABASE_URL` e `REDIS_URL` |
| --- | --- | --- |
| clonar-e-rodar | container `app` | o bloco `environment:` do `docker-compose.yml` |
| construção | `runserver` no host | o `.env`, direto |

As duas leem o mesmo `.env`. Dentro do container, o compose **sobrescreve** as duas variáveis
para os nomes de serviço e as portas **internas** — `postgres:5432` e `redis:6379` —, nunca
`POSTGRES_PORT` e `REDIS_PORT`, que só valem para quem chega pelo host. Sem essa sobrescrita, o
container herdaria os endereços da jornada de construção, em que `localhost` é o próprio
container, e o `migrate` falharia com erro que parece de credencial ou de rede.

Os dois modos de misturá-las, e o que cada um produz:

- rodar `runserver` com o `app` de pé → erro de bind na 8000, na
  [seção 9](#9-erro-de-bind-na-porta-8000);
- editar `DATABASE_URL` no `.env` para os nomes de serviço → a jornada de construção deixa de
  alcançar o banco, porque `postgres` não resolve no host.

A coerência entre `DATABASE_URL` e `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` e
`POSTGRES_PORT` é manual, sem mecanismo que a verifique. O passo a passo de cada jornada, do
`.env` ao fluxo PKCE fechado à mão, é de `docs/receita.md`.

## O que este documento não cobre

- **Incidente de segurança, premissas de confiança e a decisão de expor o IdP fora de
  localhost** — `docs/seguranca.md`. Aqui trata-se de restaurar o serviço; lá, de decidir se ele
  deve estar no ar e sob que condições.
- **Módulos, fronteiras e o caminho de um pedido** — `docs/arquitetura.md`.
- **O passo a passo das duas jornadas e as tarefas do dia a dia** — `docs/receita.md`.
- **O contrato com a relying party** — `docs/integracao-rp.md`.
- **Níveis de teste, rastreabilidade e o que não é coberto** — `docs/testes.md`.
- **O porquê de cada decisão** — `docs/adr/`, uma decisão por arquivo, imutáveis.
