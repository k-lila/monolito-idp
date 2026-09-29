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
| Erro de bind nas portas 80 e 443 | [9](#9-erro-de-bind-nas-portas-80-e-443) |
| 404 num recurso estático, ou CSS editado que não muda | [10](#10-404-em-recurso-estático-ou-css-que-não-muda-na-tela) |
| `/health` devolve 503 | [11](#11-health-devolve-503) |
| `createsuperuser` falha por unicidade | [12](#12-createsuperuser-falha-por-unicidade) |
| A relying party não acha a descoberta e recebe 404 | [13](#13-a-relying-party-recebe-404-ao-procurar-a-descoberta) |
| Nada quebrou, e eu quero saber o que está errado assim mesmo | [14](#14-as-falhas-que-não-produzem-sintoma-nenhum-hoje) |
| O processo não sobe, e a mensagem cita `AUDIT_LOG_PATH` | [15](#15-o-processo-não-sobe-e-a-mensagem-cita-audit_log_path) |
| HTTP 429 na tela de login, ou 429 em `/o/token/` e `/o/authorize/` | [16](#16-http-429-conta-ou-origem-barrada-por-excesso) |
| O `app` morre no boot, com erro de permissão no diretório de log | [17](#17-o-app-morre-no-boot-com-erro-de-permissão-em-varlognova_api) |
| O nome público não resolve, ou o certificado é recusado | [18](#18-o-nome-público-não-resolve-ou-o-certificado-não-é-aceito) |
| O proxy não atende, ou devolve 502 | [19](#19-o-proxy-não-atende-ou-responde-502) |
| Toda requisição do `runserver` falha, com erro de autenticação do Redis | [20](#20-authenticationerror-do-redis-na-jornada-de-construção) |
| Produção: a borda responde 1033 | [21](#21-produção-a-borda-responde-1033) |
| Produção: a trilha inteira com o mesmo `ip`, e o login trancado para todos | [22](#22-produção-a-trilha-inteira-com-o-mesmo-ip-e-o-login-trancado-para-todos) |
| Produção: `Found orphan containers` com o `cloudflared`, ou erro de bind | [23](#23-produção-found-orphan-containers-com-o-cloudflared-ou-erro-de-bind) |
| Produção: o `up` para com `Pool overlaps` | [24](#24-produção-o-up-para-com-pool-overlaps) |
| Produção: a descoberta responde 200 com o issuer de outro nome | [25](#25-produção-a-descoberta-responde-200-com-o-issuer-de-outro-nome) |
| Produção: `http://` do nome público responde 200 com a tela de login | [26](#26-produção-http-do-nome-público-responde-200-com-a-tela-de-login) |
| O processo não sobe, e a mensagem cita `SPA_URL` | [27](#27-o-processo-não-sobe-e-a-mensagem-cita-spa_url) |
| Produção: `invalid_grant` intermitente | [Migração com um conector só](#5-migração-com-um-conector-só) |

A operação do dia a dia — desbloquear conta, revogar acesso, limpar tabela, trocar chave, subir
versão — está em
[Operação corrente](#operação-corrente). Os roteiros próprios do clone de produção — invocação,
backup, restauração, migração, pin, rotação do túnel, vazamento e renovação do domínio — estão em
[Produção pelo túnel](#produção-pelo-túnel).

**No clone de produção, todo comando deste documento leva
`-f docker-compose.yml -f docker-compose.prod.yml`** (ADR — Architecture Decision Record — 0027,
alínea *Invocação*). Os comandos aparecem na forma curta, a do desenvolvimento; os roteiros de
produção os trazem por extenso. Um comando sem os dois arquivos no clone de produção recria os
serviços só com o arquivo base, e a borda responde 502
([23](#23-produção-found-orphan-containers-com-o-cloudflared-ou-erro-de-bind)).

## Onde olhar primeiro

Três lugares, nesta ordem. Os comandos usam o nome de serviço do `docker-compose.yml`, porque
nenhum serviço declara `container_name` e o nome real do container é gerado pelo compose.

**1. O estado dos quatro serviços.**

```bash
docker compose ps
```

Em produção são cinco: o quinto é o conector do túnel, o `cloudflared`, e nenhum dos cinco
publica porta no host.

`app`, `postgres` e `redis` precisam estar `healthy`. Um `postgres` ou um `redis` fora de
`healthy` explica sozinho um `app` que nem subiu: a espera pelos dois é do `depends_on` com
`condition: service_healthy`, e não de laço no `docker/entrypoint.sh`.

O `proxy` aparece como `running`, e nunca `healthy`: ele não declara `HEALTHCHECK`. Um `proxy`
de pé com o `app` fora do ar devolve **502** a quem chega de fora, e é o único serviço com
porta publicada — a aplicação não publica nenhuma. O log dele é próprio:

```bash
docker compose logs proxy
```

Ali estão a emissão do certificado, o nome que ele atende e o erro de quem não consegue
alcançar `app:8000`.

Em produção, o `cloudflared` também aparece como `running`, e nunca `healthy`: a imagem não tem
shell com que sondar. O log dele mostra, na linha `Settings:`, cada flag que o conector aceitou, e
é o único lugar do host em que aparece a falha de o conector alcançar o `proxy`:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs cloudflared
```

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

**Uma convenção sobre os `curl` deste documento.** Eles aparecem no endereço da jornada de
construção, `http://localhost:8000`. Na de clonar-e-rodar o IdP atende pelo proxy, e o mesmo
comando vira `curl --cacert ./ca-local.crt https://$PUBLIC_HOST/...` — o certificado sai de uma
CA local, e como extrair a raiz dela está na
[seção 18](#18-o-nome-público-não-resolve-ou-o-certificado-não-é-aceito). O caminho depois do
host é o mesmo nas duas.

### 1. O JWKS devolve `{"keys": []}` com HTTP 200

**Sintoma.** `/o/.well-known/jwks.json` responde 200 com uma lista de chaves vazia. Nada mais parece errado: a descoberta responde e **os quatro endpoints — authorize,
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

**Correção.** Regere a linha com `./scripts/gen_env_secrets.sh --so-chave-rsa`, que já imprime o escape
correto, e cole-a inteira, em uma linha só.

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

**Três causas, as duas primeiras na requisição de autorização e a terceira no registro da
`Application`:**

- **`redirect_uri` diferente da registrada.** A comparação é de **igualdade exata, não de
  prefixo**: `http://localhost:8000/noop/` não casa com `http://localhost:8000/noop`
  registrada — uma barra a mais basta. O resultado é 400 direto no GET, sem `Location`.
- **`code_challenge` ausente.** `PKCE_REQUIRED` está declarado em `config/settings.py`, e
  cliente público sem PKCE é recusado antes da tela, com `error=invalid_request`.
- **`redirect_uri` registrada em `http://`, com `BEHIND_TLS_PROXY=True`.** Ali
  `ALLOWED_REDIRECT_URI_SCHEMES` é só `["https"]`, e o redirecionamento com o `code` vira
  `DisallowedRedirect`: 400 **depois** do login, sem `Location`. Na `Application` com
  `skip_authorization` a recusa vem no GET, sem tela nenhuma; nas demais, a tela de
  consentimento aparece e o 400 vem no POST dela. O admin já não aceita gravar `http://` sob
  essa variável, de modo que a causa é uma `Application` gravada antes, ou na jornada de
  construção, e servida pela de container. A linha de log sai no logger
  `django.security.DisallowedRedirect`, com `Redirect to scheme 'http' is not permitted`.

**Verificação.** Compare caractere a caractere a `redirect_uri` da barra de endereços com a
registrada em `/admin/oauth2_provider/application/`, confira o esquema dela contra
`BEHIND_TLS_PROXY` da jornada em curso, e confirme que a query string carrega `code_challenge`
e `code_challenge_method=S256`.

### 7. Container `unhealthy` eterno, com a aplicação atendendo por fora

Esta é a entrada mais traiçoeira do documento, por três razões: o sintoma é o mesmo nos dois
casos, **duas causas distintas o produzem**, e **a mesma mudança de ambiente dispara as duas**.

**Sintoma.** `docker compose ps` mostra `app` em `unhealthy` indefinidamente, enquanto o IdP
responde normalmente a quem chega de fora, pelo proxy.

**A mudança que dispara.** Pôr um proxy TLS (Transport Layer Security) na frente. Quem faz isso
liga `BEHIND_TLS_PROXY=True`, troca `BASE_URL` para `https://...` e — o movimento natural, e
errado — estreita `ALLOWED_HOSTS` para o nome público do proxy. As três edições são a mesma
sessão de trabalho.

**Neste repositório essa mudança já aconteceu, e as três edições são uma linha cada no
`docker-compose.yml`**, derivadas de `PUBLIC_HOST` (ADR 0017). A causa B deixou de depender de
alguém lembrar: o compose compõe `ALLOWED_HOSTS` com o nome público **e** `127.0.0.1` na mesma
linha. As duas causas continuam aqui porque quem editar aquela linha as recria — e porque a
jornada de construção segue com a variável falsa, onde a isenção da causa A é inerte.

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

### 9. Erro de bind, nas portas 80 e 443

**Sintoma.** O `proxy` não sobe, e a mensagem fala de bind — de endereço já em uso.

**Causa.** Outra coisa ocupa a 80 ou a 443 deste host: um servidor web instalado, outro stack
de compose, um túnel. As duas portas são publicadas em `127.0.0.1` pelo serviço `proxy`, e são
as únicas portas da aplicação — o `app` deixou de publicar a 8000 (ADR 0017).

**Correção.** Libere a porta, ou edite as duas publicações no `docker-compose.yml`, mantendo o
endereço `127.0.0.1`. Não são variáveis, e isso é deliberado: o endereço de publicação é a
decisão que separa "só este host" de "exposto", e não deve caber num valor de ambiente.

Produção não publica porta nenhuma: o override `docker-compose.prod.yml` zera o `ports:` de
`proxy`, `postgres` e `redis` (ADR 0027). Erro de bind no clone de produção é comando sem os dois
`-f`, que recriou os serviços só com o arquivo base
([23](#23-produção-found-orphan-containers-com-o-cloudflared-ou-erro-de-bind)). Na máquina do
dono, a 80 já é ocupada por outro servidor web, e o `up` do base falha ruidosamente ali.

**O que este sintoma deixou de ser.** Um `runserver` de pé na 8000 já não colide com nada: as
duas jornadas convivem na mesma máquina, uma em `localhost:8000` e a outra em
`$PUBLIC_HOST`. Convivem, mas não se misturam — ver
[As duas jornadas](#as-duas-jornadas-e-como-não-misturá-las).

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

**Sintoma.** O comando falha dizendo que o e-mail já existe.

**Não é defeito: é o modelo funcionando.** O `accounts.User` tem `username = None` e e-mail
único como identificador de login, e **o superusuário é um só**. O comando é interativo e roda
por `docker compose run --rm app python manage.py createsuperuser`; o boot não cria conta
nenhuma, de modo que a falha acontece no seu terminal e não derruba container nenhum
(ADR `docs/adr/0019-criar-o-superusuario-por-comando-explicito-fora-do-boot.md`).

O passo só é necessário em banco novo. Se o que você queria era uma segunda conta
administrativa, use outro e-mail.

**`exec` em vez de `run` também falha, e por outro motivo:** sem terminal alocado o prompt de
senha não aparece, e o comando morre pedindo um TTY. É `run --rm`.

### 13. A relying party recebe 404 ao procurar a descoberta

**Sintoma.** A biblioteca da relying party (RP) informa 404 ao buscar os metadados do servidor,
e o endereço que ela tentou termina em `/.well-known/oauth-authorization-server/o`.

**Causa.** O issuer tem componente de path — é `{BASE_URL}/o` (ADR
`docs/adr/0007-fixar-o-issuer-do-idp-em-base-url-barra-o.md`) —, e aí a OIDC (OpenID Connect)
Discovery 1.0 e a RFC 8414 deixam de coincidir. Este IdP publica a forma da OIDC Discovery 1.0,
que é o issuer concatenado com o sufixo:

```
{BASE_URL}/o/.well-known/openid-configuration
```

A forma path-component da RFC 8414 não foi montada, e responde 404. O contrato completo com a
relying party está em `docs/integracao-rp.md`.

### 14. As falhas que não produzem sintoma nenhum hoje

Dezessete defeitos deste sistema não têm entrada de sintoma porque **não têm sintoma**. Só se
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

**O limitador de taxa acima do `CorsMiddleware`.** `config.limites.LimiteDeTaxaMiddleware`
**emite resposta** — o 429 de `/o/token/`, de `/o/authorize/`, de `/o/device-authorization/` e
de `/accounts/login/` — e por
isso vale para ele a mesma regra da entrada acima: acima do `CorsMiddleware`, aquele 429 sairia
sem os cabeçalhos de CORS. Com a allowlist vazia é **indetectável**, e o sinal só aparecerá na
fase de uma SPA (Single-Page Application), como um 429 que o navegador esconde atrás de um erro
de CORS. Dos quatro caminhos, `/accounts/login/` é o único que uma pessoa abre diretamente no
navegador — é por ele que a mordida apareceria primeiro.

**A queda do Redis desliga o teto de requisição dos quatro caminhos.** `config/limites.py` falha
**aberto**: quando o cliente de Redis recusa a conexão ou esgota o tempo de espera, o middleware
captura o erro e **deixa a requisição seguir**. Enquanto durar a queda não há teto nenhum em
`/o/token/`, em `/o/authorize/`, em `/o/device-authorization/` nem em `/accounts/login/`, e nada
acusa: não há 429, não há
erro, e o único rastro é uma linha `WARNING` por requisição no log operacional. É troca
deliberada — o preço de não converter queda de cache em 500 num endpoint que antes atravessava a
queda inteiro (ADR `docs/adr/0016-limitar-a-taxa-na-superficie-de-autenticacao.md`). A queda em
si tem sintoma, e é o `/health` devolvendo 503 ([seção 11](#11-health-devolve-503)); o que não
tem sintoma nenhum é o teto ter sumido. O comando que acha as linhas:

```bash
docker compose logs --no-color --no-log-prefix app | jq -R 'fromjson? | select(.outcome=="throttle_unavailable")'
```

Cada uma dessas linhas é uma requisição que passou sem ser contada, e traz o `path` e o `ip`
dela. Elas param de sair quando o Redis volta, e o intervalo em que o sistema
ficou sem teto não fica registrado em lugar nenhum além delas — o log é só stdout, de modo que
vale a advertência de "Log operacional só em stdout": salve antes de recriar o container.

O que **não** some junto é o `django-axes`: ele conta no Postgres, e o bloqueio por conta e por
origem continua valendo durante a queda. Isso não quer dizer que a tela de login siga
funcionando. `django/contrib/sessions/backends/cached_db.py` captura `Exception` em `load` e em
`save`, e **não** em `exists`, que é quem responde pela criação de chave de sessão: o login
bem-sucedido chama `cycle_key()`, que chama `create()`, que chama `exists()` — e ali o erro do
cliente de Redis sobe. Verificado contra o pacote instalado: com o cache apontando para uma
porta fechada, `SessionStore()._get_new_session_key()` levanta `redis.exceptions.ConnectionError`.
Com o Redis fora, portanto, a senha errada continua contada e bloqueada, e a senha certa tende a
500.

**A origem colapsa numa só, e com ela o bloqueio por origem alcança todo mundo.** O limitador
do login conta pela origem que `config/origem.py` devolve, e quatro arranjos fazem essa função
devolver o mesmo endereço para toda requisição externa.

O primeiro é o do cabeçalho que não chega: com `BEHIND_TLS_PROXY` **verdadeiro** atrás de um
proxy que não escreva `X-Forwarded-For`, ou que escreva menos saltos que os declarados em
`TRUSTED_PROXY_COUNT`, a função cai no `REMOTE_ADDR`, que ali é o endereço do proxy.

O segundo é de rede, e é o que ocorre na jornada de clonar-e-rodar: **as portas do `proxy` são
publicadas em `127.0.0.1`, e quem encaminha uma publicação em loopback é o `docker-proxy`, um
processo de userland que abre até o container uma conexão própria**. Os processos estão à
vista, um por porta publicada:

```bash
pgrep -a docker-proxy
```

O Caddy recebe todas as conexões do gateway da bridge e escreve esse endereço em
`X-Forwarded-For` — corretamente, e substituindo o que o cliente tenha mandado —, de modo que
toda requisição vinda do host chega à trilha e ao limitador como um cliente só. Nada acusa: a
linha sai com `ip_src: "forwarded"` e um endereço plausível, que é o que uma implantação
correta também produz. Nada no caminho está errado; o endereço real foi perdido antes de
chegar. Em produção nada é publicado, e o `ip` vem de `CF-Connecting-IP`, lido só do conector do
túnel (ADR 0027): esse arranjo não ocorre ali.

O terceiro é o de antes do proxy, e vale para a jornada de construção quando alguém sobe o
`app` sem o `proxy`: com a variável **falsa**, `REMOTE_ADDR` é o gateway da bridge,
`172.18.0.1`, para tudo que vem de fora. Verificado à mão.

O quarto é o de produção. O conector do túnel entrega todas as requisições pela mesma conexão, e
se a confiança do `docker/Caddyfile` no endereço dele falhar, todo cliente vira o conector. A
procedência não o distingue, porque a linha sai com a forma de uma correta, e ele tem entrada
própria, na [seção 22](#22-produção-a-trilha-inteira-com-o-mesmo-ip-e-o-login-trancado-para-todos).

A procedência distingue o primeiro dos outros dois. Toda linha da trilha carrega `ip_src`
desde a ADR 0018, e `remote_addr_fallback` em toda linha é o cabeçalho que não chega — o único
sinal que esse arranjo emite. `forwarded` com um endereço só é o proxy de userland; `remote_addr`
é a jornada sem proxy nenhum na frente:

```bash
docker compose exec app cat /var/log/nova_api/audit.log | jq -c '[.ip, .ip_src]' | sort | uniq -c
```

Nos dois, o contador soma o tráfego externo inteiro numa chave só. Cinco falhas de login vindas
de fora do container — espalhadas por contas diferentes, de modo que quem conte seja a origem —
bloqueiam aquele endereço e, **com ele, a tela de login para todo o tráfego externo**, por
quinze minutos de prazo móvel: cada nova tentativa, inclusive as que já chegam barradas,
recomeça a contagem do prazo. O campo `ip` da trilha registra o mesmo endereço em todas essas
linhas. Sem erro, sem log, com a suíte verde. Fora de produção, o alcance é um host, e não a
internet: as únicas portas publicadas são as do `proxy`, em `127.0.0.1:80` e `127.0.0.1:443`, de
modo que "de fora do container" quer dizer de dentro do próprio host — o que muda o tamanho do
dano, não o mecanismo. Em produção, o colapso no conector tranca a internet inteira
([seção 22](#22-produção-a-trilha-inteira-com-o-mesmo-ip-e-o-login-trancado-para-todos)). A verificação é olhar uma linha da trilha vinda de fora do container: se o `ip`
for o gateway da bridge, ou o endereço do proxy, é isto (ADR — Architecture Decision Record —
`docs/adr/0015-resolver-a-origem-do-cliente-num-ponto-unico.md`). A saída é o `axes_reset_ip`
daquele endereço, em
[Desbloquear uma conta ou uma origem](#desbloquear-uma-conta-ou-uma-origem).

**`ip_edge: unknown` em toda linha.** O processo não lê a própria tabela de rotas —
`/proc/net/route` ausente, ilegível ou sem rota default. A distinção entre endereço colapsado e
endereço real deixa de existir a partir dali, e nada mais a acusa: a leitura falha em silêncio
de propósito, porque a alternativa seria a exceção subir até o `except Exception` do receptor e
levar a **linha inteira** da trilha junto. O comando que conta os valores:

```bash
docker compose exec app cat /var/log/nova_api/audit.log | jq -c '[.ip, .ip_src, .ip_edge]' | sort | uniq -c
```

**O logger `axes` está em `ERROR`, e isso apaga o diagnóstico da biblioteca.** As mensagens
próprias do `django-axes` — tentativa registrada, bloqueio aplicado — saem em `INFO` e
`WARNING` e carregam o identificador tentado **em claro**; o nível `ERROR` foi escolhido para
manter e-mail fora do stdout. O efeito colateral é que investigar um bloqueio pelo log
operacional não devolve nada: o rastro é o da trilha de auditoria, na linha `user_locked_out`,
com `identifier_sha256` no lugar do e-mail.

**Renomear o campo `username` do formulário de login desliga a contagem por conta.** O axes lê
o campo cujo nome está em `AXES_USERNAME_FORM_FIELD`, declarado como `"username"` em
`config/settings.py` porque é o nome que o `AuthenticationForm` do Django usa mesmo com
`USERNAME_FIELD = "email"`. Um nome diferente ali faz o axes ler `None` em toda tentativa e
passar a contar **só por origem**: o bloqueio por conta simplesmente nunca dispara, sem erro e
sem log.

**A tela de bloqueio declara quinze minutos por extenso.** `templates/registration/bloqueio.html`
escreve o prazo na prosa, e o prazo real é `AXES_COOLOFF_TIME`, em `config/settings.py`. Mudar
a setting sem mudar a tela faz a tela mentir para quem espera, e nada acusa.

**O Caddy devolvendo ao cliente a escolha do próprio `X-Forwarded-For`.** O `reverse_proxy` do
Caddy 2.11 **substitui** o cabeçalho de quem não é par confiável: o valor que o cliente
escreveu é descartado, e o que chega ao `app` é o endereço da conexão, sozinho. É essa
propriedade que `TRUSTED_PROXY_COUNT = 1` pressupõe — o único salto foi escrito pelo proxy e
não é forjável —, e ela tem duas consequências que não se leem no arquivo. A primeira: como o
cabeçalho chega sempre com um salto só, `TRUSTED_PROXY_COUNT` maior que 1 não tem o que contar
e cai em `remote_addr_fallback` em **toda** requisição, registrando o endereço do proxy no
lugar do de quem chamou. A segunda é a silenciosa: um `header_up X-Forwarded-For
{header.X-Forwarded-For}` no `docker/Caddyfile`, ou um `trusted_proxies` que declare confiável
quem vem de fora, faz o valor do cliente atravessar — e com ele a chave do limitador de taxa e
o `ip` da trilha passam a ser escolhidos por quem chama. Nada acusa: as linhas continuam saindo
com `ip_src: "forwarded"` e endereços plausíveis. O `docker/Caddyfile` traz `trusted_proxies`
só para o /32 do conector e `header_up X-Forwarded-For {client_ip}`, e é assim que deve ficar.
O perigo é o `trusted_proxies` além do /32 e o `header_up` com `{header.X-Forwarded-For}`.

**O HSTS de um ano marca o navegador pelo nome de exemplo.** Sob `BEHIND_TLS_PROXY`,
`SECURE_HSTS_SECONDS` vale 31536000, e o primeiro acesso por navegador ao nome de `PUBLIC_HOST`
grava ali uma política de um ano. Sem `includeSubDomains` e sem `preload`, o estrago fica
contido em um nome — mas trocar de nome depois de alguém ter visitado exige **limpar o estado
de HSTS de cada navegador que visitou o anterior**, e enquanto isso não for feito aquele nome
não volta a atender em texto claro. Nada avisa antes, e a marca é do lado do cliente: nenhum
comando deste repositório a apaga.

**`SPA_URL` válida e errada.** A validação da carga confere a forma, não o destino: uma origem
bem formada que não é a da `nova_api_SPA` passa, e o botão "Ir para a aplicação" da home leva
para lá. Só quem clica percebe.

**`SPA_URL=http://localhost` no `.env` de produção.** Loopback é aceito em `http://` mesmo com
`BEHIND_TLS_PROXY` verdadeiro, porque o container de desenvolvimento roda assim. Em produção o
valor passa, e o botão leva à máquina de quem clica.

**`SPA_URL` e `CORS_ALLOWED_ORIGINS` sem vínculo.** Em produção as duas carregam a mesma
origem, e nenhum mecanismo confere isso. Trocar só `CORS_ALLOWED_ORIGINS` deixa o botão
levando à origem antiga; trocar só `SPA_URL` leva a uma SPA cujas chamadas a `/o/` o navegador
barra por CORS. Nenhum dos dois casos falha na carga.

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

### 16. HTTP 429: conta ou origem barrada por excesso

**Sintoma.** Três respostas possíveis, e duas delas saem da mesma tela. Na tela de login os dois
limitadores convivem, e **o corpo da resposta, junto com a presença do `Retry-After`, é o que
diz qual dos dois respondeu**:

- na tela de login, **HTTP 429 em HTML, com a página "Tentativas em excesso" e sem
  `Retry-After`** — é o `django-axes`. A página não diz de quem é a conta nem se a conta existe,
  deliberadamente: uma senha correta recebe a mesma resposta;
- na tela de login, **HTTP 429 com corpo JSON** `{"error": "temporarily_unavailable", ...}` **e
  cabeçalho `Retry-After: 60`** — é `config/limites.py`, o mesmo mecanismo que barra em `/o/`.
  Nenhuma tentativa foi registrada: a requisição nem chegou a `authenticate()`;
- em `/o/token/`, `/o/authorize/` ou `/o/device-authorization/`, **HTTP 429 com o mesmo corpo
  JSON e o mesmo `Retry-After: 60`**.

Não há um quarto caso: o 429 do axes é sempre página HTML e nunca traz o cabeçalho; o do
middleware é sempre JSON e sempre traz. Tudo o mais nesta seção depende de qual dos dois foi.

**Causa.** São dois limitadores, e na tela de login os dois agem sobre o mesmo tráfego (ADR
`docs/adr/0016-limitar-a-taxa-na-superficie-de-autenticacao.md`):

| Onde | Quem barra | Conta o quê | Termina |
| --- | --- | --- | --- |
| `/accounts/login/` e `/admin/login/` | `django-axes` | tentativas **falhas**, por conta e por origem, separadamente | 15 minutos após a última tentativa |
| `/accounts/login/` | `config/limites.py` | **todas** as requisições, o GET que renderiza o formulário inclusive, por origem | até 60 segundos |
| `/o/token/` e `/o/authorize/` | `config/limites.py` | **todas** as requisições, por origem e por endpoint | até 60 segundos |
| `/o/device-authorization/` | `config/limites.py` | **todas** as requisições, por origem | até 60 segundos |

Na tela de login o teto do axes é de cinco falhas e o do middleware é de 60 requisições por
minuto; em `/o/token/` e `/o/authorize/`, o do middleware é de 120 por minuto, e em
`/o/device-authorization/`, de 30 — rota sem uso por este projeto, em que um 429 só aparece
diante de tráfego que não é da SPA. Uma tentativa feita pela tela custa
**duas** requisições contadas (o GET do formulário e o POST que o envia), de modo que as
sessenta dão cerca de trinta tentativas por minuto. Contar por conta tem custo conhecido e
aceito: quem souber o e-mail de alguém pode mantê-lo fora por quinze minutos sem nunca acertar
uma senha.

**Verificação.** O rastro depende de qual 429 apareceu, e trocar um pelo outro custa caro: **a
recusa do middleware não deixa linha na trilha de auditoria em caminho nenhum, no login
inclusive.** Quem procurar só na trilha não encontra nada e conclui que não houve bloqueio.

O bloqueio do axes deixa linha na **trilha de auditoria**; a recusa do middleware, nos quatro
caminhos, deixa linha no **log operacional**:

```bash
cat logs/audit.log | jq -c 'select(.event=="user_locked_out")'

docker compose exec app cat /var/log/nova_api/audit.log | jq -c 'select(.event=="user_locked_out")'
docker compose logs --no-color --no-log-prefix app | jq -R 'fromjson? | select(.outcome=="throttled")'
```

O primeiro comando é o da jornada de construção, em que a trilha é `logs/audit.log`, relativo ao
diretório de trabalho; os dois seguintes são os da clonar-e-rodar. O log operacional da jornada
de construção não tem comando: ele sai no terminal em que o `runserver` está rodando, e é ali que
se procura a linha com `outcome: "throttled"`.

A linha da trilha traz `ip` e `identifier_sha256` — nunca o e-mail. Para saber se ela é da conta
que você investiga, recalcule o resumo com o comando de
[A trilha de auditoria](#a-trilha-de-auditoria-onde-fica-e-como-lê-la). A linha do log
operacional traz `path` e `ip`, e nunca `route`: o limitador roda antes de a URL ser resolvida.
É o `path` que diz qual caminho foi recusado — uma linha com `outcome: "throttled"` e
`path: "/accounts/login/"` é o teto de requisição da tela de login, e não o axes.

**As saídas.** Também dependem de qual dos dois barrou:

- **429 em JSON, com `Retry-After`**, em qualquer um dos quatro caminhos: nenhuma ação. A janela
  fecha sozinha em no máximo sessenta segundos, e o cabeçalho já diz isso. `axes_reset_ip` **não
  faz absolutamente nada** contra este 429 — o contador dele vive no cache, e não na tabela de
  tentativas do axes;
- **429 em HTML, na tela de login**: esperar quinze minutos **sem tentar de novo** basta — o
  axes conta as falhas da janela e atualiza o registro a cada nova falha, inclusive as que chegam
  com a conta já bloqueada, de modo que insistir adia o fim e um ataque sustentado mantém a conta
  fora enquanto durar. Para devolver o acesso na hora, os comandos estão em
  [Desbloquear uma conta ou uma origem](#desbloquear-uma-conta-ou-uma-origem).

**Se ninguém entra, de conta nenhuma**, o mais provável é que a origem tenha colapsado: na
jornada de clonar-e-rodar, toda requisição de fora do container chega como `172.18.0.1`, e
cinco falhas quaisquer trancam esse endereço — que é o de todo mundo.
`axes_reset_ip 172.18.0.1` devolve o acesso na hora; a entrada "A origem colapsa numa só" da
[seção 14](#14-as-falhas-que-não-produzem-sintoma-nenhum-hoje) explica o mecanismo, que vale
igualmente com `BEHIND_TLS_PROXY=True` atrás de um proxy que não escreva `X-Forwarded-For`. A
origem colapsada alimenta também o contador do middleware: sessenta requisições por minuto
vindas de fora do container (cerca de trinta tentativas, pelas duas requisições que cada uma
custa) recusam o login para todo o tráfego externo, e aí a espera é de segundos, não de quinze
minutos.

Em produção, o `ip` colapsado é o do conector do túnel — o literal do `docker/Caddyfile` ou o
endereço real do conector —, e o que ele tranca é a internet inteira. A verificação e a correção
estão na [seção 22](#22-produção-a-trilha-inteira-com-o-mesmo-ip-e-o-login-trancado-para-todos).

**E se nenhum 429 aparecer**, por mais requisições que se faça, o limitador do middleware está
falhando aberto por queda do Redis: a entrada "A queda do Redis desliga o teto de requisição dos
quatro caminhos" da [seção 14](#14-as-falhas-que-não-produzem-sintoma-nenhum-hoje) diz como
confirmar e o que mais sai de lugar enquanto durar. O bloqueio do axes não depende do cache e
continua valendo.

### 17. O `app` morre no boot, com erro de permissão em `/var/log/nova_api`

**Sintoma.** O container `app` não sobe. A mensagem é de permissão negada ao abrir
`/var/log/nova_api/audit.log`, emitida na configuração do `logging`, antes de qualquer view.

**Causa.** O processo deixou de rodar como `root` — é o usuário `nova_api`, de UID (identificador
de usuário) e GID (identificador de grupo) 10001 — e o volume `auditlog` **já existente** continua
sendo de `root`. O Docker copia dono e modo da imagem apenas para volume **vazio**; em volume
populado não recopia nada, e a posse antiga sobrevive ao rebuild. Ambiente novo não vê isto.

**Correção**, uma vez só:

```bash
docker compose run --rm --user root app chown -R 10001:10001 /var/log/nova_api
docker compose up -d --wait app
```

O `chown` não está no entrypoint de propósito: pô-lo ali exigiria que o boot escalasse
privilégio a cada subida para corrigir um estado que ocorre uma vez.

### 18. O nome público não resolve, ou o certificado não é aceito

**Sintoma.** Duas formas. `curl` e ferramentas de linha de comando falham dizendo que não
resolvem o nome, enquanto o navegador abre a mesma URL sem problema. Ou tudo resolve e o
cliente recusa o certificado.

**Causa da resolução.** O nome do exemplo termina em `.localhost`, reservado pela RFC 6761. O
navegador o resolve em `127.0.0.1` por conta própria; fora dele a resolução depende do
`nsswitch` deste host, e nem todo sistema trata esse sufixo.

**Correção**, derivada do próprio `.env` para não haver dois nomes:

```bash
echo "127.0.0.1 $(grep '^PUBLIC_HOST=' .env | cut -d= -f2)" | sudo tee -a /etc/hosts
```

**Causa do certificado.** Ele é emitido pela autoridade certificadora (CA) interna do Caddy,
que cliente nenhum conhece de fábrica. Recusar é o comportamento correto de quem não a conhece.

**Correção.** Extrair a raiz e apresentá-la ao cliente — o procedimento completo, com o
navegador, está em `docs/receita.md`:

```bash
docker compose cp proxy:/data/caddy/pki/authorities/local/root.crt ./ca-local.crt
curl --cacert ./ca-local.crt https://$PUBLIC_HOST/health
```

**Se o certificado era aceito e deixou de ser**, a CA foi regerada: ela vive no volume
`caddydata`, e `docker compose down -v` o destrói junto dos outros quatro. Extraia a raiz nova.

**Em produção**, nada disso se aplica. O navegador vê o certificado Universal da borda da
Cloudflare, que os clientes já conhecem, e não há CA local a extrair nem linha de `/etc/hosts` a
escrever. Um nome que não resolve é a rota de DNS (Domain Name System) do túnel, que é do dono do
domínio. Um `PUBLIC_HOST` mais fundo que um subdomínio de primeiro nível fica fora do certificado
Universal, e o navegador o recusa (ADR 0027, alínea *Certificado*).

### 19. O `proxy` não atende, ou responde 502

**Sintoma.** Três formas, com causas distintas.

**502 em toda requisição.** O `proxy` está de pé e o `app` não — ele é o único serviço
publicado, e um `app` morto vira 502 na borda. A causa está em `docker compose logs app`, e as
[seções 15](#15-o-processo-não-sobe-e-a-mensagem-cita-audit_log_path) e
[17](#17-o-app-morre-no-boot-com-erro-de-permissão-em-varlognova_api) cobrem os dois motivos
mais prováveis de ele não subir.

Em produção, o 502 vem da borda da Cloudflare, e tem mais duas causas: o `proxy` fora da rede
`borda`, por um `up` sem os dois `-f` (medido no ensaio), e o conector de pé sem `proxy` a
alcançar, depois de um `down` sem os dois `-f`. As duas estão na [seção 23](#23-produção-found-orphan-containers-com-o-cloudflared-ou-erro-de-bind).

**Resposta nenhuma, e o log do proxy fala de desafio ou de conta ACME.** A diretiva `tls
internal` saiu do `docker/Caddyfile`, ou foi trocada por engano. Sem ela o Caddy tenta emitir
certificado pela internet, falha na validação do domínio e fica tentando de novo — sem erro de
configuração, porque a configuração é válida. Reponha a diretiva.

**400 `DisallowedHost`, vindo pelo proxy.** O `PUBLIC_HOST` do serviço `proxy` e o do
`ALLOWED_HOSTS` do `app` divergiram, o que só acontece se alguém editar uma das linhas do
compose sem a outra. `docker compose config` mostra as duas já interpoladas.

### 20. `AuthenticationError` do Redis, na jornada de construção

**Sintoma.** Com o `runserver` no host, toda requisição falha e o traceback termina em
`redis.exceptions.AuthenticationError`. O `/health` responde, com 503 e `"cache": "error"`
([seção 11](#11-health-devolve-503)); o `migrate` continua passando, porque o banco não tem
parte nisto.

**Causa.** O servidor exige senha — o `redis` do compose sobe com `--requirepass` —, e a
`REDIS_URL` do seu `.env` não a carrega, ou carrega outra. Dentro do container esse caso não
existe: lá a URL e a senha do servidor saem da mesma variável. Na jornada de construção a senha
é escrita de novo à mão, e nada confere se as duas são a mesma. Como `SESSION_ENGINE` é
`cached_db`, a sessão toca o cache a cada requisição, e é por isso que falham todas em vez de
algumas.

**A mensagem não traz `NOAUTH` nem `WRONGPASS`.** Essas são as palavras do `redis-cli`, e não
as do cliente Python, que negocia com `HELLO`: sem senha nenhuma o texto é `HELLO must be
called with the client already authenticated...`, e com a senha errada é `invalid
username-password pair or user is disabled.` — procurar no log pelas palavras do `redis-cli`
não acha nada. Quem as devolve é o servidor, perguntado diretamente:

```bash
docker compose exec redis sh -c 'unset REDISCLI_AUTH; redis-cli ping'
```

`NOAUTH Authentication required.` aqui é o servidor **correto**, sob `requirepass`.

**Correção.** Repita a `REDIS_PASSWORD` do `.env` dentro da `REDIS_URL` do mesmo arquivo, em
`redis://:SENHA@localhost:6379/0` — usuário vazio, senha depois dos dois pontos. O `runserver`
lê a URL no boot: reinicie-o, e nada mais precisa ser recriado.

### 21. Produção: a borda responde 1033

**Sintoma.** O nome público responde com a página de erro 1033 da Cloudflare: nenhum conector
está ligado ao túnel da rota.

**Causa.** Cinco casos:

- o `cloudflared` parado: `stop`, `down` com os dois `-f`, daemon do Docker fora, máquina
  desligada ou suspensa;
- o `cloudflared` em laço de reinício: o JSON de credenciais em `0600`, que o uid 65532 da imagem
  não lê; um `TUNNEL_ID` que não casa com as credenciais; ou uma flag que o nível não declara, que
  sai com `flag provided but not defined` e código 0, de modo que o código de saída mostra
  sucesso enquanto a política de reinício o repete;
- o contêiner nem criado: sem o diretório `cloudflared/`, o `up` para com `bind source path does
  not exist`, de forma ruidosa;
- o `.200` da `borda` tomado pelo `proxy` num recreate ou num reboot, e o conector sem endereço
  para subir. O T-02 de `tests/test_borda_do_tunel.py` guarda a relação entre os valores do
  arquivo, e não o que o daemon faz;
- a rota de DNS apontando para um túnel sem conector, como ficou o nome de ensaio depois da
  desmontagem do passo 4 do plano (medido).

**Verificação.** O estado, a contagem de reinícios e o log do conector:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps -a cloudflared
docker inspect --format '{{.RestartCount}}' \
  "$(docker compose -f docker-compose.yml -f docker-compose.prod.yml ps -aq cloudflared)"
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs cloudflared
```

Contagem que cresce entre duas leituras é laço, e o log nomeia a flag recusada. Contêiner que não
aparece nem com `-a` nunca foi criado.

**Correção.** Por caso: `up -d --wait` com os dois `-f`; `chmod 0644 cloudflared/credenciais.json`;
conferir com o dono o `TUNNEL_ID` e as credenciais do mesmo túnel; a flag de volta ao nível que a
declara, como diz o comentário do `docker-compose.prod.yml`; o `cloudflared/` restaurado do
backup ([Produção pelo túnel](#produção-pelo-túnel), item 3); a rota de DNS, com o dono.

### 22. Produção: a trilha inteira com o mesmo `ip`, e o login trancado para todos

**Sintoma.** Ninguém entra, de conta nenhuma, ou o 429 chega a todos ao mesmo tempo. Lida, a
trilha mostra o mesmo `ip` em todas as linhas.

**Causa.** O colapso no conector (ADR 0027, *Colapso silencioso*). A confiança do
`docker/Caddyfile` no /32 do conector falhou — literal divergente do override, conector em outro
endereço, borda sem o cabeçalho, ou uma subida de pin do Caddy ou do `cloudflared` que mudou um
comportamento medido —, e todo cliente vira o conector. O `ip` é o literal quando só falta o
cabeçalho, e o endereço real do conector nos outros casos. O limitador e o `django-axes` contam a
internet inteira numa chave só, e o primeiro atacante tranca todos.

**Verificação.**

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec app \
  cat /var/log/nova_api/audit.log | jq -c '[.ip, .ip_src, .ip_edge]' | sort | uniq -c
```

- O colapso é o mesmo `ip` em todas as linhas, com `ip_src` `forwarded` e `ip_edge` `peer`, e cada
  linha tem a forma de uma correta. Comparar o `ip` com o literal do `docker/Caddyfile` não basta,
  porque dois dos três casos não o mostram.
- A prova só vale com dois clientes em redes sabidamente distintas, um login falho de cada, e as
  duas linhas com `ip` distintos. O segundo cliente é um celular em dados móveis, com o Wi-Fi
  desligado, e não outra máquina da mesma rede local, que divide com a primeira o IPv4 (versão
  4 do IP, de _Internet Protocol_) público e o /64.
- Sob o Pseudo IPv4 da zona, um endereço de `240.0.0.0/4` é normal: é o IPv4 de classe E que a
  borda põe no lugar de um cliente IPv6 (versão 6 do IP).
- O endereço real do conector lê-se na rede, e a igualdade dos dois literais, na suíte
  (`tests/test_borda_do_tunel.py`):

  ```bash
  docker inspect --format '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}' \
    "$(docker compose -f docker-compose.yml -f docker-compose.prod.yml ps -q cloudflared)"
  ```

- `CF-Connecting-IP` mandado de fora recebe 403 com `error code: 1000`. É o esperado, medido no
  ensaio, e não falha.

**Correção.** O `docker/Caddyfile` é a fonte do valor, e o override volta a ele, e não o
contrário. O `proxy` só relê o Caddyfile montado num `restart`, e o `up` recria o que o override
mudou. Depois, o desbloqueio da origem colapsada; o teto do limitador expira sozinho em sessenta
segundos:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart proxy
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --wait
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec app \
  python manage.py axes_reset_ip <ip colapsado>
```

### 23. Produção: `Found orphan containers` com o `cloudflared`, ou erro de bind

**Sintoma.** No clone de produção, um `up` avisa de contêiner órfão, o `cloudflared`, para com erro
de bind, ou deixa a borda respondendo 502. Depois de um `down`, nada avisa, e o `ps` com os dois
`-f` mostra só o `cloudflared`.

**Causa.** Comando sem os dois `-f` (ADR 0027, *Esquecer o `-f`*). Medido no ensaio: o `up` sem
`-f` recria `app` e `proxy` só com o arquivo base, sem `restart:` e com o `proxy` fora da rede
`borda`, e a borda responde 502. Com o desenvolvimento de pé, o `postgres` nem sobe, porque o
arquivo base o publica na `127.0.0.1:5432` que o desenvolvimento ocupa. O aviso de órfão vem
nesse `up`. O `down` sem `-f` remove os quatro serviços do base e a rede `default` sem aviso
nenhum; o `cloudflared` fica de pé, sem `proxy` a alcançar, e a política de reinício o traz de
volta depois de um reboot. Nos dois casos, a falha é fechada para a internet.

**Correção.** O mesmo comando, com os dois arquivos:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --wait
```

### 24. Produção: o `up` para com `Pool overlaps`

**Sintoma.** O `up` com os dois `-f` para ao criar a rede, com `Pool overlaps`.

**Causa.** Uma segunda rede `borda` com a mesma sub-rede, `10.203.14.0/24`. Dois caminhos: um
`COMPOSE_PROJECT_NAME` exportado no shell com outro valor, que prevalece sobre o do `.env` e faz o
compose criar um segundo projeto; ou um ensaio e a produção de pé na mesma máquina.

**A falha é guarda.** A sub-rede fixa impede, ruidosamente, dois conectores do mesmo túnel no
host. Passar a `borda` para sub-rede dinâmica apagaria essa guarda em silêncio, e não se faz.

**Correção.** Ver os projetos de pé, limpar o shell e repetir o `up` com os dois `-f`:

```bash
docker compose ls
unset COMPOSE_PROJECT_NAME
```

### 25. Produção: a descoberta responde 200 com o issuer de outro nome

**Sintoma.** A descoberta do nome público responde 200, e o `issuer` não é
`https://<nome público>/o`. A SPA recusa o login pelo issuer divergente.

**Causa.** `PUBLIC_HOST` errado no `.env` do clone de produção, por exemplo esquecido no valor de
desenvolvimento, `idp.localhost`. O conector entrega `PUBLIC_HOST` na indicação de nome do
servidor (SNI, de _Server Name Indication_) e no `Host`, e o Caddy e o Django atendem o nome que
recebem: a cadeia inteira responde 200, coerente com o nome errado, em vez de 400 (ADR 0027,
*Nome errado, resposta coerente*). A guarda é conferir o issuer, de fora:

```bash
curl -s https://<nome público>/o/.well-known/openid-configuration | jq -r .issuer
```

**Correção.** Backup do `.env` antes ([Produção pelo túnel](#produção-pelo-túnel), item 3);
`PUBLIC_HOST` corrigido no lugar da linha existente; e o `up` com os dois `-f`:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --wait
```

### 26. Produção: `http://` do nome público responde 200 com a tela de login

**Sintoma.** `http://<nome público>/` responde 200 com a tela de login, em vez de redirecionar.

**Causa.** O "Always Use HTTPS" da zona do IdP não vale. A origem não tem como perceber: o trecho
do conector ao Caddy é HTTPS, e o redirecionamento do Django nunca é acionado. A zona é a única
barreira (medido no ensaio).

**Correção.** Na zona, pelo dono do domínio, ligando a opção. A conferência é a resposta 301, com
`Location` em `https://`:

```bash
curl -sI http://<nome público>/
```

### 27. O processo não sobe, e a mensagem cita `SPA_URL`

**Sintoma.** Nada sobe, como na [15](#15-o-processo-não-sobe-e-a-mensagem-cita-audit_log_path):
qualquer `manage.py` aborta, o `app` morre no boot, e a suíte não chega ao primeiro teste. A
mensagem é uma `ImproperlyConfigured` que nomeia `SPA_URL`.

**Causa.** Uma de duas, e a mensagem distingue:

- **Ausente.** A linha não está no `.env`. Não há default no código: `SPA_URL` é o destino do
  botão "Ir para a aplicação" da home, e um default levaria o botão a um lugar que ninguém
  escolheu.
- **Recusada.** A linha está lá, e a forma não é a de uma origem. A mensagem diz o motivo e não
  repete o valor, que poderia trazer credenciais. São quatro: esquema que não é `http` nem
  `https`, ou sem host; credenciais (`usuario:senha@`); caminho, barra final, query ou
  fragmento, e também barra invertida, espaço em branco em qualquer ponto e porta vazia, não
  numérica ou acima de 65535, todos sob a mesma mensagem de forma; e `http://` fora de loopback
  com `BEHIND_TLS_PROXY` verdadeiro.

**Correção.** Acrescente ou corrija a linha no `.env`, à mão: `SPA_URL=http://localhost:5173` em
desenvolvimento, `SPA_URL=https://<origem da SPA>` em produção, o mesmo valor da entrada de
`CORS_ALLOWED_ORIGINS`. **Não copie o `.env.example` por cima:** o `.env` é untracked, não tem
cópia, e sobrescrevê-lo apaga a chave RSA e a `SECRET_KEY` do projeto. No clone de produção,
backup do `.env` antes ([Produção pelo túnel](#produção-pelo-túnel), item 3).

O que a carga não recusa (destino errado mas bem formado, loopback em produção, divergência
com `CORS_ALLOWED_ORIGINS`) está na [14](#14-as-falhas-que-não-produzem-sintoma-nenhum-hoje).

## Operação corrente

### Desbloquear uma conta ou uma origem

Os três comandos abaixo vêm do `django-axes`, apagam registros de tentativa e valem para o 429
em HTML — o dele, na tela de login e em `/admin/login/` — e só para esse: o teto de requisição
de `/accounts/login/`, de `/o/token/` e de `/o/authorize/` não tem comando, porque a janela dos
três expira sozinha em sessenta segundos, e nem `axes_reset_username` nem `axes_reset_ip`
alcançam o 429 em JSON que aquele teto devolve na própria tela de login:

```bash
docker compose exec app python manage.py axes_reset_username pessoa@exemplo.com
docker compose exec app python manage.py axes_reset_ip 203.0.113.10
docker compose exec app python manage.py axes_reset
```

O primeiro devolve o acesso a uma conta; o segundo, a uma origem; o terceiro apaga **todas** as
tentativas registradas, de todo mundo, e com elas some a evidência de que houve ataque. Prefira
os dois primeiros.

O e-mail vai **como foi digitado na tentativa**: o axes guarda o identificador tal como veio, e
`A@x.com` e `a@x.com` são contas distintas sob Postgres. Para ver o que está registrado antes de
apagar — origem, identificador tentado e número de falhas:

```bash
docker compose exec app python manage.py axes_list_attempts
```

Esperar quinze minutos sem novas tentativas tem o mesmo efeito e não apaga nada. Sob ataque
sustentado contra a mesma conta, não tem: cada nova falha adia o fim da janela, e aí o comando é
a única saída.

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
./scripts/gen_env_secrets.sh --so-chave-rsa
```

O script imprime a linha `OIDC_RSA_PRIVATE_KEY=...` pronta, com as quebras do PEM escapadas
como `\n`. A opção faz a saída conter só essa linha, para que colá-la não troque também a
`SECRET_KEY` e as senhas. **Cole-a você mesmo no `.env`.** O script não escreve no arquivo de propósito:
escrita automática sobrescreveria sem confirmação uma chave possivelmente em uso.

**No lugar da linha que já existe, nunca acrescentada ao fim** (`>> .env`). Com a linha
duplicada, as duas jornadas divergem em silêncio: o `django-environ` da jornada de construção
fica com a primeira ocorrência, porque o `read_env` usa `setdefault`, e o `env_file` do compose
fica com a última. A conferência conta as linhas sem imprimi-las, e tem de dar 1:

```bash
grep -c '^OIDC_RSA_PRIVATE_KEY=' .env
```

Depois de colar, recrie o container — o `.env` é lido na criação, não a cada reinício:

```bash
docker compose up -d --force-recreate --wait app
```

No clone de produção, com os dois arquivos, sem exceção: sem eles, o `app` é recriado só com o
arquivo base, sem `DEBUG` fixo em `False`, sem `restart:` e com o `proxy` fora da `borda` (ADR
0027, *Esquecer o `-f`*):

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --force-recreate --wait app
```

Confira que a troca chegou ao que as relying parties leem. O `kid` publicado, antes e depois,
dá valores diferentes, e o tamanho do módulo dá 512 caracteres, que são 3072 bits (ADR 0028):

```bash
curl -s <base>/o/.well-known/jwks.json | jq -r '.keys[].kid'
curl -s <base>/o/.well-known/jwks.json | jq '.keys[].n | length'
```

`<base>` é o endereço da jornada em uso, com o `--cacert` da
[convenção](#sintoma-causa-verificação) na de container. Em produção, a consulta é de fora da
máquina, pelo nome público.

**O que a troca quebra.** Existe uma única chave ativa, sem conjunto de rotação (ADR
`docs/adr/0004-assinar-tokens-com-rs256-e-custodiar-a-chave-privada-no-ambiente.md`):

- todo `id_token` já emitido deixa de verificar contra o JWKS publicado;
- cada relying party guarda o JWKS em cache pelo prazo dela, e enquanto esse cache não vencer
  ela também rejeita os `id_token` assinados com a chave **nova**. A janela ruim é dos dois
  lados, não de um;
- `access_token` e `refresh_token` são opacos — linhas no Postgres, não artefatos assinados — e
  sobrevivem à troca. Quem depende deles não percebe nada.

A primeira rotação será disruptiva por construção. O mesmo script gera a chave de
desenvolvimento e a de produção, em 3072 bits fixos, o nível de 128 bits de segurança do SHA-256
que o RS256 (RSA com SHA-256) usa (ADR
`docs/adr/0028-gerar-a-chave-de-assinatura-em-rsa-3072-pelo-gerador-unico-de-segredos.md`).

### A trilha de auditoria: onde fica e como lê-la

Cinco eventos são registrados no instante em que acontecem: `user_logged_in`,
`user_login_failed`, `user_logged_out`, `app_authorized` e `user_locked_out`, este último o
bloqueio por tentativas em excesso. O arquivo é JSON por linha, no mesmo esquema do log
operacional e com o mesmo `request_id`, o que permite casar uma linha de auditoria com o
traceback do mesmo pedido.

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
—, `sub`, `ip`, `ip_src`, `ip_edge` e `outcome`; mais `client_id` em `app_authorized` e
`identifier_sha256` em `user_login_failed` e em `user_locked_out`.

**`ip_src` diz de onde o `ip` daquela linha saiu**, e é o que torna o arquivo legível depois de
`BEHIND_TLS_PROXY` mudar de valor: a trilha é append-only, o instante da troca não fica gravado
em lugar nenhum, e sem esse campo nada distingue as duas populações (ADR
`docs/adr/0018-declarar-a-procedencia-do-endereco-em-cada-linha-da-trilha.md`). São três
valores:

| `ip_src` | O `ip` é | Quando |
| --- | --- | --- |
| `remote_addr` | o endereço da conexão | `BEHIND_TLS_PROXY` falso |
| `forwarded` | o salto de `X-Forwarded-For` na posição de `TRUSTED_PROXY_COUNT` | proxy declarado, cabeçalho com saltos suficientes |
| `remote_addr_fallback` | o endereço da conexão — atrás de um proxy, o **do proxy** | proxy declarado, cabeçalho ausente ou curto demais |

`remote_addr_fallback` em toda linha de uma implantação atrás de proxy é defeito, e é o único
sinal que ele emite — ver a entrada "A origem colapsa numa só" da
[seção 14](#14-as-falhas-que-não-produzem-sintoma-nenhum-hoje).

**`ip_edge` diz o que o `ip` daquela linha é para o processo que a escreveu**, e é o que separa
o endereço real do endereço em que o `docker-proxy` colapsa tudo que vem do host. O processo
compara o `ip` com o próprio gateway padrão, lido de `/proc/net/route` a cada linha (ADR
`docs/adr/0020-marcar-na-linha-o-endereco-colapsado-pelo-docker-proxy.md`, emenda à 0018).
Também são três valores:

| `ip_edge` | O `ip` é | O que se pode concluir |
| --- | --- | --- |
| `gateway` | o gateway padrão do processo | é nele que colapsa tudo que veio pelo `docker-proxy`, e a origem real não está no arquivo |
| `peer` | um endereço diferente do gateway padrão | não é a borda em que o host colapsa — e nada além disso: não afirma cliente único |
| `unknown` | indeterminado | a rota padrão não pôde ser lida, ou o `ip` não é IPv4 |

**A regra de leitura das três populações de linha:**

- sem `ip_src`: escrita antes da ADR 0018; o `ip` é `REMOTE_ADDR`;
- com `ip_src` e sem `ip_edge`: escrita entre a ADR 0018 e esta decisão. O `ip` NÃO identifica
  cliente nenhum — é endereço da rede do compose (o gateway da bridge sob `forwarded`, o
  endereço do próprio Caddy sob `remote_addr_fallback`) ou `127.0.0.1` na jornada de
  construção. O que sustenta: a única publicação que este repositório já teve é `127.0.0.1`,
  expor exige editar à mão um arquivo versionado (ADR 0017), e a proibição desta decisão trava
  essa edição até o campo existir;
- com `ip_edge`: responde sozinha.

A primeira das três vale por construção, e não por memória de alguém: `BEHIND_TLS_PROXY` nunca
foi ligado em ambiente nenhum antes de `ip_src` existir, porque a ADR 0015 o proibia
nominalmente.

**A verificação do `gateway`, na jornada de container, é à mão, e é esta.** A suíte não
alcança o caso `gateway`: ela constrói requisições sintéticas, e a tabela de rotas de verdade
não é a do cenário. Provoque uma falha de login pelo endereço publicado — três comandos, porque
a tela exige CSRF (Cross-Site Request Forgery) — e leia a última linha da trilha:

```bash
curl -sk -c /tmp/cookies.txt https://127.0.0.1/accounts/login/ -o /dev/null
csrf=$(awk '/csrftoken/{print $7}' /tmp/cookies.txt)
curl -sk -b /tmp/cookies.txt -e https://127.0.0.1/accounts/login/ \
  -d "csrfmiddlewaretoken=$csrf&username=inexistente@exemplo.com&password=x" \
  https://127.0.0.1/accounts/login/ -o /dev/null
docker compose exec app tail -n 1 /var/log/nova_api/audit.log | jq -c '[.ip, .ip_src, .ip_edge]'
```

Do próprio host sai `["172.18.0.1","forwarded","gateway"]`: quem chega pelo loopback atravessa
o `docker-proxy` de todo modo. A tentativa conta para o `django-axes`, que bloqueia na quinta —
ver [Desbloquear uma conta ou uma origem](#desbloquear-uma-conta-ou-uma-origem).

Em produção, nada sai de loopback: o proxy não publica porta, e a entrada é o túnel (ADR 0027,
que emendou a 0020). Sob o túnel, `peer` não prova nada, porque o colapso no conector também sai
`peer`. A verificação de produção é a da [seção 22](#22-produção-a-trilha-inteira-com-o-mesmo-ip-e-o-login-trancado-para-todos), com dois clientes de redes sabidamente
distintas. Os `curl` acima continuam valendo para a jornada de container.

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

**Na jornada de clonar-e-rodar, o campo `ip` continua não sendo a origem real.** O Caddy
escreve em `X-Forwarded-For` o endereço de quem lhe abriu a conexão — substituindo o que o
cliente tenha mandado, em vez de anexar a ele —, e a linha sai com `ip_src: "forwarded"`. Mas
quem lhe abriu a conexão foi o `docker-proxy`, o processo de userland que encaminha porta
publicada em loopback, e o endereço que ele apresenta é o dele. Duas pessoas no mesmo host
aparecem com o mesmo endereço, o do gateway da bridge. Quem marca esse colapso na linha é
`ip_edge`, e não `ip_src`: `gateway` é exatamente o endereço em que o `docker-proxy` faz
convergir tudo que vem do host, e `peer` é o endereço que não convergiu ali — sem afirmar que
identifique um cliente único (ADR 0020). Em produção, o `ip` vem de `CF-Connecting-IP`, lido
só do conector do túnel (ADR 0027). Na jornada de construção, com o `runserver` no host e sem proxy, o
endereço é o real e `ip_src` é `remote_addr`.

Três ressalvas de contagem e uma de durabilidade:

- `app_authorized` sai também a cada renovação de `refresh_token`, de modo que linhas não são
  consentimentos;
- `user_locked_out` sai uma vez por **tentativa barrada**, e não uma por bloqueio: o axes
  reemite o sinal a cada nova falha que chega com a conta já trancada. Oito falhas seguidas
  contra a mesma conta e a mesma origem produzem oito `user_login_failed` e quatro
  `user_locked_out` — medido. Quem contar linhas para contar bloqueios contará errado, e é o
  `jq` da [seção 16](#16-http-429-conta-ou-origem-barrada-por-excesso) que conta essas linhas;
- criação de Application e revogação de token **não** aparecem, por não existir sinal que as
  emita;
- não há retenção nem poda — o arquivo cresce indefinidamente, e nada o monitora. Sob ataque
  sustentado ele cresce duas linhas por tentativa, que é a ressalva anterior cobrando o preço
  desta.

### Os volumes nomeados, e por que `down -v` é grave

`docker compose down -v` destrói os cinco volumes nomeados: `pgdata`, `redisdata`, `auditlog`,
`caddydata` e `caddyconfig`. Com o `pgdata` vão-se contas, Applications, grants, tokens e a
`django_session` — tudo; com o `auditlog` vai-se a trilha de auditoria inteira, que é justamente
a evidência de quem tocou o que se perdeu. É a mesma tecla, e ela leva as duas coisas.
`docker compose down` sem `-v` preserva os cinco.

Com o `caddydata` vai-se a autoridade certificadora local: o stack volta a subir normalmente,
emitindo certificado novo de uma CA nova, e quem havia confiado na anterior passa a recusá-lo.
É perda de conveniência, não de dado — mas é a única das cinco que se manifesta do lado do
cliente, e por isso parece outra coisa ([seção 18](#18-o-nome-público-não-resolve-ou-o-certificado-não-é-aceito)).

**A gravidade não é a perda dos dados; é a reciclagem do par `(iss, sub)`.** O `sub` de todo
`id_token` é a chave primária (PK) do usuário, um `BigAutoField` fixado antes da migração
inicial. Derrubar o volume e deixar `migrate` mais `createsuperuser` recriarem `id=1` faz **uma
pessoa diferente** receber o par `("{BASE_URL}/o", "1")` — e a OIDC Core §5.7 manda
a relying party usar exatamente esse par como chave de identidade. Do lado dela, é a mesma
pessoa.

É seguro enquanto nenhuma relying party tiver integrado. Deixa de ser no dia em que a primeira
integrar, e nada no sistema marca esse dia.

Em produção, `down -v` é proibido ([Produção pelo túnel](#produção-pelo-túnel), item 2). O
`caddydata` de produção não guarda nada caro: o navegador vê o certificado da borda, e o
conector não verifica a CA interna.

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

## Produção pelo túnel

Os roteiros do clone de produção, cada um ancorado numa alínea da ADR 0027. São passos de quem
opera: criar, trocar ou apagar túnel, zona e rota de DNS é do dono do domínio, fora do
repositório, e agente nenhum opera no diretório de produção. Os comandos vão por extenso, com os
dois arquivos. Nenhum imprime segredo: a conferência de uma linha do `.env` é por `grep -c`, que
conta sem mostrar.

### 1. Os dois `-f`

Todo comando `docker compose` no clone de produção leva os dois arquivos, digitados, sem exceção
(ADR 0027, *Invocação*):

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --wait
```

Não há script, `COMPOSE_FILE` nem link que os lembre: o que sobe o IdP no boot é a política de
reinício, declarada no override. Num diretório de desenvolvimento, nunca `up` com o override. O
que o esquecimento produz está na
[seção 23](#23-produção-found-orphan-containers-com-o-cloudflared-ou-erro-de-bind).

### 2. O que nunca se roda em produção

- `git clean -xd`: apaga o `.env` e o `cloudflared/`, que são untracked, e nenhum `reset` os
  devolve;
- `down -v`, `docker volume prune` e `docker system prune --volumes`: apagam o `pgdata` e o
  `auditlog`, e com eles contas, tokens, `Application` e a trilha, e reciclam o par `(iss, sub)`
  ([Os volumes nomeados](#os-volumes-nomeados-e-por-que-down--v-é-grave));
- agente com shell no diretório de produção (`docs/plano-implantacao.md`, §7);
- a saída inteira de `docker compose config`: ela expande o `env_file` e imprime a
  `OIDC_RSA_PRIVATE_KEY`, a `SECRET_KEY` e as senhas. Lê-se por campo, com
  `config --format json | jq` do campo, e compara-se por `sha256sum`;
- `grep` sem `-c` sobre uma linha de segredo do `.env`, que a imprime.

### 3. Backup

O que entra, cifrado e fora da máquina (ADR 0027, *Backup*):

- o `.env` e o `cloudflared/`, a cada mudança de qualquer dos dois;
- o dump do `pgdata` e a trilha do `auditlog`, no mínimo por mês e depois de cada mudança de conta
  ou de `Application`.

O dump guarda o hash das senhas, as sessões, as `Application` e os `access_token` e
`refresh_token` vivos: é segredo da mesma classe do `.env`, e não toca o disco em claro. A cifra
abaixo é a simétrica do `gpg`, que pede a frase-senha no terminal; qualquer outra que cifre no
pipe serve. Com a entrada vinda do pipe, o `gpg` só acha o terminal em que pedir a frase-senha
por `GPG_TTY`, exportado antes. `AAAAMMDD` é a data do backup.

```bash
export GPG_TTY=$(tty)
tar -c .env cloudflared | gpg --symmetric -o env-AAAAMMDD.tar.gpg
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T postgres \
  sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB"' | gpg --symmetric -o pgdata-AAAAMMDD.sql.gpg
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T app \
  cat /var/log/nova_api/audit.log | gpg --symmetric -o audit-AAAAMMDD.log.gpg
```

Os três arquivos saem da máquina depois de cifrados, e a cópia local é apagada em seguida: na
máquina, ela estaria ao alcance do mesmo processo de que o backup protege.

```bash
rm env-AAAAMMDD.tar.gpg pgdata-AAAAMMDD.sql.gpg audit-AAAAMMDD.log.gpg
```

Um backup anterior a uma rotação — da chave,
da `SECRET_KEY`, das senhas ou do túnel — fica marcado como inválido: restaurá-lo traria de volta
o segredo trocado.

### 4. Restauração ensaiada

Uma restauração ensaiada antes do primeiro login real, e nesta ordem (ADR 0027, *Restauração*).
Cada passo diz o dano que evita.

1. **O desenvolvimento derrubado**, no diretório dele, com `docker compose down`, sem `-v`. O
   arquivo base publica em `127.0.0.1` as mesmas portas do desenvolvimento, e o ensaio não subiria
   ao lado dele.
2. **Um clone de ensaio**, com o `.env` decifrado do backup, e `COMPOSE_PROJECT_NAME` trocado por
   um nome que não é o de produção nem o de desenvolvimento, **antes de qualquer comando
   `docker compose`**. Com o nome de produção, o compose adota os contêineres e os volumes de
   `nova_api_prod`, e o `down -v` do fim apaga o `pgdata` de produção, sem aviso.
3. **Só o arquivo base, sem o override.** Com ele, um segundo conector com o `TUNNEL_ID` de
   produção passaria a receber parte do tráfego.
4. **`docker compose ls` antes de subir**, para ver o nome do ensaio, e não o de produção.
5. **A carga do dump, e a conferência.** O `postgres` sobe sozinho, recebe o dump, e só depois
   sobem `redis` e `app`, cujo `migrate` encontra o esquema já carregado. O `proxy` fica fora: a
   conferência não precisa dele, e na máquina do dono a 80 já está ocupada.

   ```bash
   docker compose up -d --wait postgres
   gpg -d pgdata-AAAAMMDD.sql.gpg | docker compose exec -T postgres \
     sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
   docker compose up -d --wait redis app
   docker compose exec app python manage.py shell -c \
     "from django.contrib.auth import get_user_model; print(get_user_model().objects.count())"
   ```

6. **`docker compose ls` de novo, antes do `down -v`**, que é a única tecla deste roteiro capaz de
   apagar produção se o nome estiver errado:

   ```bash
   docker compose ls
   docker compose down -v
   ```

7. **Produção intacta, por fim**: `nova_api_prod` de pé em `docker compose ls`, e os volumes dele
   em `docker volume ls --filter name=nova_api_prod`. O clone de ensaio é apagado, e com ele o
   `.env` decifrado e o que mais do backup tiver sido decifrado ali, que são segredos de
   produção fora do clone de produção. O desenvolvimento volta a subir no diretório dele.

### 5. Migração com um conector só

Levar o IdP a outro host é mover o clone, as credenciais do túnel e os volumes, sem mudar DNS nem
issuer (ADR 0027, *Migração*). Dois conectores com o mesmo `TUNNEL_ID` repartem as requisições
entre dois bancos, e um `code` emitido num volta `invalid_grant` no outro, de forma intermitente:
esse é o sintoma da migração feita fora de ordem.

1. Na origem, `down` com os dois `-f`, sem `-v`, antes do dump final. Para o dump, sobe só o
   `postgres`, que não tem conector nem porta:

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml down
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --wait postgres
   ```

2. O dump final e a trilha, com o `app` parado. A trilha sai por um contêiner descartável do
   `app`, que monta o volume `auditlog` e roda só o `cat`, sem a sequência de boot e, por
   `--no-deps`, sem subir mais nada. Depois, o `down` de novo:

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T postgres \
     sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB"' | gpg --symmetric -o pgdata-AAAAMMDD.sql.gpg
   docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm --no-deps -T app \
     cat /var/log/nova_api/audit.log | gpg --symmetric -o audit-AAAAMMDD.log.gpg
   docker compose -f docker-compose.yml -f docker-compose.prod.yml down
   ```

3. O clone, com o `.env` e o `cloudflared/`, e os dois arquivos cifrados levados ao destino.
4. No destino, onde o volume nasce vazio, o `postgres` sozinho, a carga do dump e o resto:

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --wait postgres
   gpg -d pgdata-AAAAMMDD.sql.gpg | docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T postgres \
     sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --wait
   ```
5. As verificações do passo 6 de `docs/plano-implantacao.md`.
6. Os volumes da origem ficam como cópia fria até o destino passar por elas.

### 6. Pin do `cloudflared` e do Caddy

A versão fixada do `cloudflared` sai da janela de suporte da Cloudflare numa data que quem opera
acompanha fora do repositório; o pin sobe antes dela (ADR 0027, *Manutenção*). A tag muda no
`docker-compose.prod.yml`, que é arquivo versionado.

Subir o pin do `cloudflared` é remedir, e não ler a nota de versão:

- o `--help` de `tunnel` e de `tunnel run`, para o nível de cada flag, e o usuário da imagem, que
  lê as credenciais:

  ```bash
  docker run --rm cloudflare/cloudflared:<versão> tunnel --help
  docker run --rm cloudflare/cloudflared:<versão> tunnel run --help
  docker image inspect --format '{{.Config.User}}' cloudflare/cloudflared:<versão>
  ```

- as medições de origem do ensaio: o Caddy recusa o handshake com SNI `proxy` ou sem SNI;
  `CF-Connecting-IP` forjado em três formas — valor único, linha duplicada e lista separada por
  vírgula — recebe 403 da borda; dois clientes de redes distintas chegam com `ip` distintos
  ([seção 22](#22-produção-a-trilha-inteira-com-o-mesmo-ip-e-o-login-trancado-para-todos)); e
  nenhuma linha da trilha traz o literal do conector.

Subir o pin do Caddy é remedir os dois comportamentos que o comentário do serviço `proxy` no
`docker-compose.yml` registra: o `header_up` prevalece sobre o cabeçalho que o `reverse_proxy`
monta, e `{client_ip}` só lê `CF-Connecting-IP` do par declarado.

A medição do passo 2 do plano, numa rede temporária `10.203.14.0/24`, não roda com produção de
pé, porque a sub-rede está ocupada pela `borda`: usa-se outro literal num Caddyfile de teste, ou
produção fica fora durante a medição.

### 7. Rotação do túnel

Para vazamento das credenciais do túnel (ADR 0027, *Vazamento das credenciais do túnel*):

1. Backup cifrado do `.env` e do `cloudflared/` antes de tocar neles (item 3).
2. O dono cria o túnel novo, passa para ele a rota de DNS de `PUBLIC_HOST` e entrega o
   `TUNNEL_ID` e o JSON de credenciais novos.
3. `TUNNEL_ID` no lugar da linha existente, e o JSON em `cloudflared/credenciais.json`, em `0644`:

   ```bash
   chmod 0644 cloudflared/credenciais.json
   grep -c '^TUNNEL_ID=' .env
   ```

   A contagem tem de dar 1.
4. O `up` troca o conector:

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --wait
   ```

5. A descoberta responde 200 de fora, com o issuer do nome público
   ([seção 25](#25-produção-a-descoberta-responde-200-com-o-issuer-de-outro-nome)).
6. O dono apaga o túnel antigo.
7. Os backups do `.env` e do `cloudflared/` anteriores à troca ficam marcados como inválidos.

### 8. Vazamento da chave, ou processo comprometido na máquina

A ordem é a da ADR 0027, alínea *Vazamento da `OIDC_RSA_PRIVATE_KEY`, ou processo comprometido
na máquina*. A troca é disruptiva: sem conjunto de rotação, a SPA falha todo login por até 1 a
2 h.

1. **Limpar a máquina.** Fora do escopo deste documento, e antes de todo o resto.
2. **Os segredos novos**, num terminal, sem redirecionar para arquivo; as seis linhas ficam à
   vista só até serem coladas:

   ```bash
   ./scripts/gen_env_secrets.sh
   ```

3. **A senha nova do Postgres, primeiro no banco**, que não a relê do `.env` depois de criado o
   volume. O `\password` pede a senha num prompt que não a ecoa e não a deixa no histórico do
   shell nem na lista de processos, como deixaria um `ALTER ROLE ... PASSWORD` na linha de
   comando:

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml exec postgres \
     sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
   ```

   Dentro do `psql`, `\password`, e a senha nova, que é a da linha `POSTGRES_PASSWORD` impressa
   no passo 2. Sem esse passo, o `app` sobe com a senha nova na `DATABASE_URL` e cai no sintoma
   da [seção 8](#8-password-authentication-failed-com-as-duas-strings-idênticas).
4. **Cada uma das seis linhas no lugar da linha existente do `.env`**, nunca com `>>`. Cada
   contagem tem de dar 1:

   ```bash
   for v in SECRET_KEY OIDC_RSA_PRIVATE_KEY POSTGRES_PASSWORD REDIS_PASSWORD DATABASE_URL REDIS_URL; do
     printf '%s ' "$v"; grep -c "^$v=" .env
   done
   ```

   Uma cópia do `.env` antigo serve só até a conferência do passo 9, e depois é apagada; os
   backups anteriores ficam inválidos.
5. **A rotação do túnel**, pelo item 7.
6. **O `up` com os dois `-f`.** A `SECRET_KEY` nova derruba as sessões, e o Redis é recriado e
   sobe com a senha nova, porque o `--requirepass` vem do `.env` na criação:

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --wait
   ```

7. **O `kid` conferido de fora**, diferente do anterior, e o módulo com 512 caracteres:

   ```bash
   curl -s https://<nome público>/o/.well-known/jwks.json | jq -r '.keys[].kid'
   curl -s https://<nome público>/o/.well-known/jwks.json | jq '.keys[].n | length'
   ```

8. **Restauração só com o marco.** Pode-se restaurar o dump de `pgdata` mais recente anterior ao
   primeiro indício de acesso à máquina; sem esse marco, não se restaura. Nenhuma restauração traz
   de volta a chave, a `SECRET_KEY`, as senhas nem as credenciais antigas. O volume de produção
   tem dados, e um dump carregado por cima deixaria um banco misto: o banco é recriado vazio
   dentro do mesmo volume, sem `down -v`, com o `app`, o `proxy` e o `cloudflared` parados, para
   que nada o use durante a troca. O `ON_ERROR_STOP` faz a carga parar no primeiro erro, em vez
   de deixar um banco pela metade com código de saída de sucesso:

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml stop app proxy cloudflared
   docker compose -f docker-compose.yml -f docker-compose.prod.yml exec postgres \
     sh -c 'dropdb -U "$POSTGRES_USER" "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
   gpg -d pgdata-AAAAMMDD.sql.gpg | docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T postgres \
     sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --wait
   ```
9. **A revisão do banco em uso**, restaurado ou não: revogar os `access_token` e `refresh_token`
   vivos ([Revogar o acesso de uma pessoa](#revogar-o-acesso-de-uma-pessoa)); rever pelo admin as
   `Application`, cuja criação não entra na trilha; rever as contas com `is_staff` ou
   `is_superuser`. A conta que o dono não reconhece sai, e as outras recebem senha nova. A
   restauração não dispensa essa revisão: o acesso pode ter começado antes do primeiro indício.
10. **A SPA fora por 1 a 2 h**, até o cache do JWKS dela vencer.

### 9. Renovação do domínio

O issuer depende de o domínio continuar registrado: um domínio expirado pode ser registrado por
outro, que passa a servir descoberta e JWKS sob o issuer que a SPA aceita (ADR 0027, negativa
*Renovação do domínio*). A defesa fica no registrador:

- renovação automática ligada;
- segundo fator na conta do registrador, como na da Cloudflare;
- a data de expiração, conferida por quem opera no painel do registrador. Ela não se escreve
  aqui, por decisão registrada na ADR 0027.

## As duas jornadas, e como não misturá-las

| Jornada | Onde a aplicação roda | O IdP atende em | Quem define as seis variáveis |
| --- | --- | --- | --- |
| clonar-e-rodar | container `app` | `https://$PUBLIC_HOST`, pelo proxy | o bloco `environment:` do `docker-compose.yml` |
| construção | `runserver` no host | `http://localhost:8000`, texto claro | o `.env`, direto |

As duas leem o mesmo `.env`, e dentro do container o compose **sobrescreve** seis variáveis
dele. Três são de endereço: `DATABASE_URL` e `REDIS_URL` passam a apontar para os nomes de
serviço e as portas **internas** — `postgres:5432` e `redis:6379` —, nunca `POSTGRES_PORT` e
`REDIS_PORT`, que só valem para quem chega pelo host; e `AUDIT_LOG_PATH`, para o volume
nomeado. Sem essa sobrescrita o container herdaria os endereços da jornada de construção, em
que `localhost` é o próprio container, e o `migrate` falharia com erro que parece de credencial
ou de rede.

As outras três são a fronteira de transporte — `BASE_URL`, `ALLOWED_HOSTS` e
`BEHIND_TLS_PROXY` —, derivadas de `PUBLIC_HOST` e ligadas **só** atrás do proxy (ADR 0017). É
por isso que as duas jornadas divergem no endereço, e a divergência é deliberada: a de
construção é a única que não exercita o endurecimento, e é a que se usa todo dia.

Os dois modos de misturá-las, e o que cada um produz:

- editar `BASE_URL` do `.env` para o nome público → o `runserver` passa a devolver 301 para um
  nome servido pelo container, e vê-se de pé o código que não se editou;
- editar `DATABASE_URL` no `.env` para os nomes de serviço → a jornada de construção deixa de
  alcançar o banco, porque `postgres` não resolve no host.

O que **não** é mais modo de misturá-las: rodar `runserver` com o `app` de pé. O `app` deixou
de publicar a 8000, e as duas convivem na mesma máquina ([seção 9](#9-erro-de-bind-nas-portas-80-e-443)).

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
