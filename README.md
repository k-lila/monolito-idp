# nova_api

Provedor de identidade OpenID Connect sobre Django e `django-oauth-toolkit`: fecha o fluxo
Authorization Code + PKCE, publica discovery e JWKS, e emite `id_token` assinado em RS256.
Sandbox exploratório — host único, uma réplica, sem TLS próprio.

Existem **duas jornadas**. A de **clonar-e-rodar**, documentada aqui, sobe tudo em container
e não exige Python no host. A de **construção** roda a aplicação em `runserver` no host,
contra o Postgres e o Redis do compose, e exige Python 3.14 com virtualenv; as duas leem o
mesmo `.env`, e é o compose que sobrescreve `DATABASE_URL` e `REDIS_URL` para os nomes de
serviço quando a aplicação roda em container. O detalhe está em `docs/roadmap/`.

## Pré-requisitos

Docker com o plugin `compose`. Nada mais — `openssl` e `curl`, usados na receita abaixo,
acompanham qualquer distribuição; o Python que gera o par PKCE é o da própria imagem.

## A receita

Nesta ordem, que é a ordem em que os comandos funcionam.

### 1. Criar o `.env`

```bash
cp .env.example .env
```

Preencha `SECRET_KEY`, `POSTGRES_PASSWORD` e a `DATABASE_URL` coerente com
`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` e `POSTGRES_PORT`.

**A regra de caracteres deste arquivo não é cosmética.** O `.env` atravessa três gramáticas
— o `django-environ`, a interpolação do próprio docker compose e a gramática de URL de
`DATABASE_URL`/`REDIS_URL`:

- nenhum valor entre aspas;
- nenhum `${...}` dentro do arquivo;
- `SECRET_KEY` sem `$ # " ' \` — `openssl rand -hex 48` produz só hexadecimal e satisfaz
  a regra por construção;
- `POSTGRES_PASSWORD` alfanumérica — `openssl rand -hex 24`.

Um `$` faz o compose interpolar e **truncar** o valor, enquanto o `django-environ` lê o
valor íntegro. A manifestação é `password authentication failed` com as duas strings do
`.env` perfeitamente idênticas a olho nu.

`POSTGRES_PORT` e `REDIS_PORT` são as portas publicadas **no host**, com default `5432` e
`6379`. Se alguma já estiver ocupada nesta máquina, mude aqui — é para isso que a variável
existe, e as portas internas do compose não mudam.

### 2. Gerar a chave RSA

```bash
./scripts/gen_dev_key.sh
```

O script imprime a linha `OIDC_RSA_PRIVATE_KEY=...` pronta, com as quebras do PEM escapadas
como `\n`. Cole-a no `.env`, substituindo a linha vazia. O script não escreve no arquivo de
propósito: trocar a chave invalida todo token vivo e quebra o JWKS cacheado das relying
parties.

**Antes de subir o stack.** Sem a chave o IdP responde normalmente e falha em silêncio:
`/o/.well-known/jwks.json` devolve `{"keys": []}` com HTTP 200, e o único sinal na discovery
é `id_token_signing_alg_values_supported` caindo de `["RS256","HS256"]` para `["HS256"]`.
**Os quatro endpoints — authorize, token, userinfo e jwks — continuam listados**, com chave
ou sem; procurar por endpoint faltando não detecta nada. O `alg` é o sinal.

### 3. Subir o stack

```bash
docker compose up --wait
```

Os três serviços precisam ficar `healthy`. **Pare o `runserver` antes**: ele e o serviço
`app` disputam a 8000, e a mensagem de erro fala de bind, não de `runserver`.

### 4. Criar o superusuário

```bash
docker compose exec app python manage.py createsuperuser
```

Ou defina `DJANGO_SUPERUSER_EMAIL` e `DJANGO_SUPERUSER_PASSWORD` no `.env` — comentadas por
default — e o entrypoint cria a conta no boot seguinte. **O superusuário é um só**: rodar
`createsuperuser` de novo com o mesmo e-mail falha por unicidade, e isso é o modelo
funcionando. Este passo só é necessário em banco novo.

### 5. Registrar uma Application

Entre em `http://localhost:8000/admin/` e crie uma Application em
`/admin/oauth2_provider/application/add/`, com os quatro campos que importam:

- `client_type` = **public**
- `authorization_grant_type` = **authorization-code**
- `algorithm` = **RS256**
- `redirect_uri` = `http://localhost:8000/noop`

O `redirect_uri` aponta para uma URL que **não precisa existir**: o navegador é redirecionado
para lá com o `code` na query string, e o `code` é lido da barra de endereços. O 404 na tela
é o resultado esperado.

Anote o `client_id` gerado.

### 6. Conferir a discovery

```
http://localhost:8000/o/.well-known/openid-configuration
```

O `issuer` é `http://localhost:8000/o`, e é ele que entra na claim `iss` de todo `id_token`.

### 7. Fechar o fluxo PKCE à mão

Gere o par verificador/desafio:

```bash
docker compose exec app python -c "
import base64, hashlib, secrets
v = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b'=').decode()
c = base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b'=').decode()
print('code_verifier =', v)
print('code_challenge =', c)
"
```

Abra no navegador, substituindo `CLIENT_ID` e `CODE_CHALLENGE`:

```
http://localhost:8000/o/authorize/?response_type=code&client_id=CLIENT_ID&redirect_uri=http://localhost:8000/noop&scope=openid%20profile%20email&state=xyz&code_challenge=CODE_CHALLENGE&code_challenge_method=S256
```

**`code_challenge_method=S256` é obrigatório.** A discovery anuncia
`code_challenge_methods_supported` igual a `["S256"]`, e é literal. Com `plain` a tela de
consentimento **ainda aparece normalmente**; a recusa só acontece no POST do consentimento,
que redireciona para o `redirect_uri` com `error=invalid_request` e sem `code`. Quem trocar
o método para depurar vai depurar a tela errada.

Autentique em `/accounts/login/`, consinta na tela seguinte, e copie o `code` da barra de
endereços depois do 404 esperado em `/noop`. Troque-o por token:

```bash
curl -s -X POST http://localhost:8000/o/token/ \
  -d grant_type=authorization_code \
  -d code=CODE \
  -d redirect_uri=http://localhost:8000/noop \
  -d client_id=CLIENT_ID \
  -d code_verifier=CODE_VERIFIER
```

A resposta traz `access_token`, `refresh_token` e — o que interessa aqui — **`id_token`**.
As claims de identidade são `sub`, `name` e `email`, exatamente o `claims_supported` da
discovery.

## A suíte de testes

```bash
.venv/bin/python manage.py test          # jornada de construção
docker compose exec app python manage.py test
```

Sem argumento, `manage.py test` roda a suíte inteira — `accounts/tests/` e `config/tests/`.
`manage.py test accounts` deixa `config/tests/` de fora, e é por isso que a forma sem
argumento é a correta.

A suíte **não** exige `collectstatic` prévio (ver "Estáticos", abaixo).

## O que o código não diz

### `algorithm = RS256` é o alçapão clássico

Em branco na Application, `/o/authorize/` **não acusa nada**: a tela de consentimento
responde 200 e o `code` é emitido normalmente. A falha só se manifesta na troca — o
`POST /o/token/` devolve **HTTP 500** com a página de erro HTML do Django e **token
nenhum**. Não procure um `id_token` ausente numa resposta que não existe: a causa está em
`docker logs`, como `ImproperlyConfigured: This application does not support signed
tokens`. É um campo fácil de esquecer no admin, e o que custa a tarde é depurar o
`/o/authorize/`, que estava certo o tempo todo.

### `BEHIND_TLS_PROXY` governa o transporte, não `DEBUG`

Cookies com flag `Secure`, HSTS, redirecionamento para HTTPS e o `SECURE_PROXY_SSL_HEADER`
dependem dessa variável — nunca de `DEBUG`, porque `DEBUG` é sobre diagnóstico e cookie
seguro é sobre transporte. Com valor `False` **atrás de um proxy TLS real**, os cookies vão
sem `Secure` e sem HSTS, **silenciosamente**: não há sinal de alerta, e este README é o único
aviso que existe hoje.

O `.env.example` sai com `DEBUG=False` e `BEHIND_TLS_PROXY=False`, e o fluxo fecha assim
mesmo em `http://localhost`. Isso é deliberado, não descuido: não existe aqui um caminho de
desenvolvimento que nunca é exercitado.

### `/health` responde em texto claro mesmo com `BEHIND_TLS_PROXY=True`

`SECURE_REDIRECT_EXEMPT` isenta `/health` — e apenas ele — do redirecionamento para HTTPS.
Sem a isenção, a probe do container, que chega de dentro em texto claro e sem
`X-Forwarded-Proto`, receberia 301 e morreria no handshake: container eternamente unhealthy
com a aplicação atendendo normalmente por fora. O custo aceito é que o estado de banco e
cache fica legível para quem observe a rede antes do proxy.

**Ligar `BEHIND_TLS_PROXY` não basta.** A probe bate em
`http://127.0.0.1:8000/health` e envia `Host: 127.0.0.1:8000`; com `DEBUG=False`,
`ALLOWED_HOSTS` **tem de continuar listando `127.0.0.1`** depois que o IdP passar a
ser servido por um nome público. Estreitar a lista para o nome do proxy — o
movimento natural de quem põe TLS na frente, junto com `BASE_URL=https://...` — faz
a probe receber **400 `DisallowedHost`** e devolve o mesmo unhealthy eterno, com a
aplicação atendendo normalmente por fora. Duas causas do mesmo sintoma são
disparadas pela mesma mudança de ambiente.

### A porta publicada é `127.0.0.1:8000`

Por desenho. O IdP **não é alcançável de outra máquina da rede** — publicar sem endereço
instalaria DNAT à frente do firewall do host, sobre um formulário de senha em HTTP claro.
Mesmo tratamento dado ao Postgres e ao Redis.

### `docker compose down -v` recicla o par `(iss, sub)`

O `sub` de todo `id_token` é a PK do usuário. Derrubar o volume e deixar `migrate` +
`createsuperuser` recriarem `id=1` faz **uma pessoa diferente** receber o par
`("http://localhost:8000/o", "1")` — que a OIDC Core §5.7 manda a relying party usar como
chave de identidade. É seguro enquanto nenhuma RP tiver integrado; deixa de ser depois.

### `is_active=False` não desliga token nenhum

Desativar uma conta não invalida `access_token` nem `refresh_token` já emitidos: o refresh
segue trocável por token novo e `/o/userinfo/` continua respondendo 200. Agravante: o
`refresh_token` **não expira por default**. Desligar alguém hoje exige apagar os tokens à
mão.

### `{BASE_URL}/o` é o issuer, e a raiz devolve 404 para a RFC 8414

O contrato com a relying party é OIDC Discovery 1.0 a partir do issuer. Uma RP estritamente
RFC 8414 procurará em `http://localhost:8000/.well-known/oauth-authorization-server/o` e
receberá **404**; a forma suportada é
`http://localhost:8000/o/.well-known/openid-configuration`.

### `CorsMiddleware` tem de ficar no topo do `MIDDLEWARE`

Acima do `CommonMiddleware`, do `WhiteNoiseMiddleware` e de qualquer middleware capaz de
gerar resposta — resposta emitida antes dele sai sem os cabeçalhos de CORS. Com a allowlist
vazia o middleware é inerte, e por isso **uma posição errada é indetectável hoje**: o sinal
só aparece na fase do SPA, como erro de CORS que ninguém associa àquela linha.

### Estáticos

O backend é `whitenoise.storage.CompressedStaticFilesStorage` — compressão sim, **manifesto
de hash não**. Consequências:

- `collectstatic` é **obrigatório para subir a aplicação** (o entrypoint do container o
  executa) e **não** para a suíte passar;
- na jornada de construção, editar CSS exige `collectstatic` **e** reiniciar o `runserver`:
  o WhiteNoise monta o índice de arquivos no boot, e o modo `autorefresh` segue `DEBUG`,
  que é `False`;
- a omissão de `collectstatic` aparece como 404 no recurso, não como erro de template.

### `LOGIN_URL` é nome de rota

`LOGIN_URL`, `LOGIN_REDIRECT_URL` e `LOGOUT_REDIRECT_URL` guardam nomes de rota — `"login"`,
`"home"` —, resolvidos por `resolve_url` em runtime, não por `reverse` nas settings, que são
lidas antes do URLConf. Renomear uma rota produz `NoReverseMatch`, falha ruidosa.

## O que ficou fora desta fase

Inventário, não esquecimento:

- **Rate limiting** em `/o/authorize/`, `/o/token/` e `/admin/login/` — primeiro item antes
  de qualquer exposição fora de localhost.
- **`email_verified`** — as relying parties não distinguem e-mail verificado de não
  verificado.
- **RP-initiated logout** (`end_session_endpoint`) — desligado explicitamente.
- **`cleartokens` e `clearsessions` sem agendamento** — as tabelas do toolkit e a
  `django_session` crescem indefinidamente.
- **Chave RSA única, sem conjunto de rotação** — a primeira rotação será disruptiva.
- **`BEHIND_TLS_PROXY` mal configurada não tem sinal de alerta** — um check de startup
  resolveria; enquanto isso, o aviso vive só aqui.
- **Log só em stdout, sem coleta externa** — some quando o container é recriado.
- **Superusuário via `DJANGO_SUPERUSER_*`** — coloca credencial administrativa no `.env`;
  precisa sair antes de qualquer ambiente compartilhado.
- **Migração no entrypoint** — correta para uma réplica, errada para duas.
- **Dois pontos de resolução de dependências** — `pip wheel -r requirements.txt` resolve as
  transitivas sem pin **na data do build** (`jwcrypto`, `cryptography`,
  `argon2-cffi-bindings`), enquanto a suíte roda contra o venv do host. Um rebuild meses
  depois traz `jwcrypto` novo — a biblioteca que assina o `id_token` — e o container assina
  com código nunca exercitado, sob `docker compose up --wait` verde, porque `/health` não
  toca `jwcrypto`.
