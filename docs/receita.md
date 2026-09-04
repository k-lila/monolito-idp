# Receita — nova_api

Como colocar este provedor de identidade (IdP) de pé, o que rodar no dia a dia e o que ainda
falta decidir antes de pensar em produção. Cada passo traz o que faz, o comando e o sinal de
que deu certo.

Quando um passo falha, o diagnóstico não está aqui: sintoma, causa e correção vivem em
`docs/runbook.md`. Este documento nomeia em uma frase a falha que se parece com outra coisa, e
aponta para lá.

## Passo zero: escolher a jornada

| | clonar-e-rodar | construção |
| --- | --- | --- |
| A aplicação roda | no container `app` | em `runserver` no host |
| Exige no host | Docker com o plugin `compose` | Docker, Python 3.14 e ambiente virtual |
| Postgres e Redis | do compose, pelo nome de serviço | do compose, por `localhost` |
| Serve para | ver o IdP funcionando | editar código e ver o efeito sem rebuild |

As duas leem o mesmo `.env`. A diferença que importa está em `DATABASE_URL` e `REDIS_URL`: o
arquivo guarda os endereços da jornada de construção, em `localhost`, e é o
`docker-compose.yml` que sobrescreve as duas em `environment:` quando a aplicação roda em
container — lá dentro `localhost` seria o próprio container.

Além do Docker, os comandos abaixo usam `openssl` e `curl`. O Python que gera o par PKCE
(Proof Key for Code Exchange) é o da própria imagem, e não precisa estar no host.

## A jornada de clonar-e-rodar

Nesta ordem, que é a ordem em que os comandos funcionam.

### 1. Criar o `.env`

**O que faz.** Copia o contrato de variáveis e o preenche. Não há default no código: variável
ausente falha na leitura, nomeando-se.

```bash
cp .env.example .env
openssl rand -hex 48   # SECRET_KEY
openssl rand -hex 24   # POSTGRES_PASSWORD
```

Preencha `SECRET_KEY` e `POSTGRES_PASSWORD`, e deixe `DATABASE_URL` coerente com
`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` e `POSTGRES_PORT` — a coerência é manual,
sem mecanismo que a verifique.

A regra de caracteres deste arquivo não é cosmética: ele atravessa três gramáticas, a do
`django-environ`, a da interpolação do próprio docker compose e a de URL (Uniform Resource
Locator), que vale para `DATABASE_URL` e `REDIS_URL`.

- nenhum valor entre aspas;
- nenhum `${...}` dentro do arquivo;
- `SECRET_KEY` sem `$ # " ' \` — `openssl rand -hex 48` produz só hexadecimal e satisfaz a
  regra por construção;
- `POSTGRES_PASSWORD` alfanumérica, pelo mesmo motivo.

`POSTGRES_PORT` e `REDIS_PORT` são as portas publicadas **no host**, com default `5432` e
`6379`. Se alguma já estiver ocupada nesta máquina, mude aqui: as portas internas do compose
não mudam.

**Como você sabe que deu certo.**

```bash
docker compose config
```

O comando imprime o arquivo do compose já interpolado. Na seção do serviço `app`, a senha
dentro de `DATABASE_URL` tem de ser idêntica à do `.env`, caractere a caractere. Valor
truncado ali é senha com `$`, e a manifestação é um erro de autenticação com as duas strings
iguais a olho nu (`docs/runbook.md`).

### 2. Gerar a chave RSA, antes de subir o stack

**O que faz.** Gera o par RSA (Rivest–Shamir–Adleman) de desenvolvimento e imprime a linha
pronta para o `.env`, com as quebras do PEM (Privacy-Enhanced Mail) escapadas como `\n`.

```bash
./scripts/gen_dev_key.sh
```

Cole a linha impressa no lugar da `OIDC_RSA_PRIVATE_KEY=` vazia. O script não escreve no
arquivo de propósito: trocar a chave invalida todo token vivo e quebra o JWKS (JSON Web Key
Set) cacheado das relying parties (RPs), conforme a ADR (Architecture Decision Record)
`docs/adr/0004-assinar-tokens-com-rs256-e-custodiar-a-chave-privada-no-ambiente.md`.

**Como você sabe que deu certo.** A linha colada é uma linha só, abre com
`OIDC_RSA_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\n` e fecha com `-----END PRIVATE KEY-----\n`.
A confirmação de verdade vem no passo 6, no `alg` da descoberta: sem a chave o IdP sobe e
responde normalmente, e a falha é silenciosa (`docs/runbook.md`).

### 3. Subir o stack

**O que faz.** Constrói a imagem, sobe `postgres`, `redis` e `app` nessa ordem e espera os três
ficarem prontos. O entrypoint do `app` roda `migrate` e `collectstatic` antes do gunicorn.

```bash
docker compose up --wait
```

**Como você sabe que deu certo.** O comando só retorna quando os três serviços estão
`healthy`; `docker compose ps` mostra o estado de cada um. Os tempos do `HEALTHCHECK` são
derivados dos tetos da própria aplicação, não escolhidos — a conta está em
`docs/adr/0011-dar-teto-de-tempo-ao-health-e-derivar-o-healthcheck-dele.md`.

Pare o `runserver` antes: ele e o serviço `app` disputam a porta 8000, e a mensagem de erro
fala de bind, não de `runserver` (`docs/runbook.md`).

### 4. Criar o superusuário

**O que faz.** Cria a conta administrativa que abre o `/admin/`. Só é necessário em banco novo.

```bash
docker compose exec app python manage.py createsuperuser
```

Alternativa: defina `DJANGO_SUPERUSER_EMAIL` e `DJANGO_SUPERUSER_PASSWORD` no `.env` (as duas
saem comentadas), e o entrypoint cria a conta no boot seguinte.

**Como você sabe que deu certo.** `http://localhost:8000/admin/` aceita esse e-mail e abre a
tela de administração. O e-mail é o identificador de login e é único: repetir o mesmo falha, e
isso é o modelo funcionando.

### 5. Registrar uma Application

**O que faz.** Cria o cliente OAuth2 que a relying party usará. Quatro campos importam.

Entre em `http://localhost:8000/admin/oauth2_provider/application/add/`:

- `client_type` = **public**
- `authorization_grant_type` = **authorization-code**
- `algorithm` = **RS256**
- `redirect_uri` = `http://localhost:8000/noop`

O `redirect_uri` aponta para uma URL que não precisa existir: o navegador é levado para lá com
o `code` na query string, e o `code` é lido da barra de endereços. O 404 na tela é o resultado
esperado.

**Como você sabe que deu certo.** Depois de salvar, a Application aparece na listagem com o
`client_id` preenchido — anote-o. Deixar `algorithm` em branco não acusa nada, nem aqui nem
no `/o/authorize/`: a falha só se manifesta na troca do código (`docs/runbook.md`).

### 6. Conferir a descoberta

**O que faz.** Lê o documento que a RP consome para descobrir os endpoints e o algoritmo de
assinatura. O contrato visto do lado dela está em `docs/integracao-rp.md`.

```bash
curl -s http://localhost:8000/o/.well-known/openid-configuration
```

**Como você sabe que deu certo.** Duas coisas no documento: `issuer` igual a
`http://localhost:8000/o`, que é a claim `iss` de todo `id_token`; e
`id_token_signing_alg_values_supported` igual a `["RS256","HS256"]`. Os quatro endpoints —
authorize, token, userinfo e jwks — ficam listados com chave ou sem, e por isso é o `alg` que
denuncia a chave ausente.

### 7. Fechar o fluxo PKCE à mão

**O que faz.** Percorre à mão o caminho que a relying party percorre, do redirecionamento ao
`id_token`.

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

`code_challenge_method=S256` é obrigatório e literal: a descoberta anuncia
`code_challenge_methods_supported` igual a `["S256"]`. Com `plain` a tela de consentimento ainda
aparece normalmente, e a recusa vem só depois — quem trocar o método para depurar vai depurar a
tela errada (`docs/runbook.md`).

Autentique em `/accounts/login/`, consinta na tela seguinte e copie o `code` da barra de
endereços depois do 404 esperado em `/noop`. Troque-o por token:

```bash
curl -s -X POST http://localhost:8000/o/token/ \
  -d grant_type=authorization_code \
  -d code=CODE \
  -d redirect_uri=http://localhost:8000/noop \
  -d client_id=CLIENT_ID \
  -d code_verifier=CODE_VERIFIER
```

**Como você sabe que deu certo.** A resposta traz `access_token`, `refresh_token` e — o que
interessa aqui — `id_token`. As claims de identidade são `sub`, `name` e `email`, exatamente o
`claims_supported` da descoberta.

## A jornada de construção

Roda a aplicação em `runserver` no host, contra o Postgres e o Redis do compose. É a jornada de
quem edita código: a alteração vale no request seguinte, sem rebuild de imagem.

### 1. Ambiente virtual com Python 3.14

**O que faz.** Isola as dependências fixadas em `requirements.txt` sob o interpretador que a
imagem também usa. O piso de compatibilidade é o Python 3.14 com Django 5.2.17
(`docs/adr/0001-adotar-django-5-2-lts-sobre-python-3-14.md`).

```bash
python3.14 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

**Como você sabe que deu certo.** `.venv/bin/python --version` imprime `Python 3.14.x`, e
`.venv/bin/python -m django --version` imprime `5.2.17`.

### 2. Subir apenas os dados

**O que faz.** Sobe Postgres e Redis, e nada mais: quem atende HTTP agora é o `runserver`.

```bash
docker compose up --wait postgres redis
```

**Como você sabe que deu certo.** `docker compose ps` lista `postgres` e `redis` como `healthy`,
e nenhum `app`.

### 3. Apontar o `.env` para `localhost`

**O que faz.** Garante que `DATABASE_URL` e `REDIS_URL` usem `localhost` e as portas publicadas
no host, `POSTGRES_PORT` e `REDIS_PORT` — que é como o `.env.example` já sai. Quem se conecta
aqui é o `runserver`. Não altere as duas pensando no container: o `docker-compose.yml` as
sobrescreve por conta própria quando a aplicação roda lá dentro.

**Como você sabe que deu certo.** A resposta vem do passo seguinte: o `migrate` conecta.

### 4. Migrar

```bash
.venv/bin/python manage.py migrate
```

**Como você sabe que deu certo.** Cada migração aplicada sai com `OK`, e uma segunda execução
não aplica nada.

### 5. Servir

```bash
.venv/bin/python manage.py runserver
```

**Como você sabe que deu certo.** `http://127.0.0.1:8000/` abre a home. Página sem estilo
significa `collectstatic` não executado, tratado em "Coletar estáticos", abaixo. O serviço
`app` e o `runserver` disputam a porta 8000, e a mensagem de erro fala de bind
(`docs/runbook.md`).

Superusuário, Application, descoberta e fluxo PKCE são os passos 4 a 7 da outra jornada,
trocando o prefixo `docker compose exec app python` por `.venv/bin/python`. O endereço é o
mesmo, `http://localhost:8000`, porque `BASE_URL` é o mesmo.

## Tarefas do dia a dia

### Rodar a suíte

```bash
.venv/bin/python manage.py test                 # jornada de construção
docker compose exec app python manage.py test   # clonar-e-rodar
```

Sem argumento: a suíte inteira está em `tests/`, e um rótulo de app encontra zero teste. A
suíte não exige `collectstatic` prévio. Níveis de teste, rastreabilidade e o que não é
coberto estão em `docs/testes.md`.

### Criar e aplicar migração

```bash
.venv/bin/python manage.py makemigrations accounts
.venv/bin/python manage.py migrate
```

`accounts` é o app com esquema próprio deste projeto. Na jornada de clonar-e-rodar não há passo
de aplicar: o entrypoint roda `migrate` a cada boot, o que é correto para uma réplica.

### Coletar estáticos

```bash
.venv/bin/python manage.py collectstatic --noinput
```

Obrigatório para servir a aplicação, dispensável para a suíte. Na jornada de construção,
editar `static/css/idp.css` exige `collectstatic` **e** reiniciar o `runserver`: o WhiteNoise
monta o índice de arquivos no boot, e o modo `autorefresh` segue `DEBUG`, que é `False`
(`docs/adr/0008-servir-estaticos-com-whitenoise-sem-manifesto-de-hash.md`). No container o
entrypoint já executa a coleta.

### Abrir o shell do Django

```bash
.venv/bin/python manage.py shell
docker compose exec app python manage.py shell
```

### Ler o log

```bash
docker compose logs -f app
```

O gunicorn roda sem `--access-logfile`, e o log traz só o que interessa: `migrate` e
`collectstatic` no boot, as mensagens de `django.request` e de `oauth2_provider`, e o
traceback de um 500. O nível vem de `LOG_LEVEL`. Na jornada de construção esse mesmo log sai
no terminal do `runserver`. Não há coleta externa: o log some com o container.

## Produção — o que ainda não existe

**Nada nesta seção foi exercitado.** Não é procedimento: é a lista das diferenças já
conhecidas e das decisões que o repositório ainda não tomou. Escrever um passo a passo de
produção agora seria inventar um caminho que ninguém percorreu.

### Diferenças de configuração já conhecidas

- `BASE_URL` passa a ser o nome público, e com ele muda o `issuer`, que é `{BASE_URL}/o` e
  fica cacheado em cada RP (`docs/adr/0007-fixar-o-issuer-do-idp-em-base-url-barra-o.md`).
- `BEHIND_TLS_PROXY=True` liga cookie `Secure`, HSTS (HTTP Strict Transport Security),
  redirecionamento para HTTPS e o `SECURE_PROXY_SSL_HEADER`. É essa variável que governa o
  transporte, nunca `DEBUG`.
- `ALLOWED_HOSTS` tem de **continuar listando `127.0.0.1`** depois de ganhar o nome público: a
  sonda do container chega de dentro com `Host: 127.0.0.1:8000`, e estreitar a lista para o
  nome do proxy a faz receber 400 (`docs/runbook.md`).
- A porta do serviço `app` teria de ser publicada além de `127.0.0.1`. Hoje ela é publicada em
  loopback, como o Postgres e o Redis, e isso é premissa de outras escolhas.

### Decisões que o repositório ainda não tomou

- **Onde ficam os segredos.** O `.env` não serve: carrega `SECRET_KEY` e a chave privada RSA em
  texto claro, num arquivo do host.
- **A migração no entrypoint.** Correta para uma réplica, errada para duas — com mais de uma,
  ela sai do boot e vira passo próprio.
- **Rotação da chave RSA.** Existe uma chave, sem conjunto de rotação: a primeira troca
  invalida todo token vivo.
- **Coleta de log.** Só stdout: o log some com o container.
- **`USER` no container.** A imagem roda como root, deliberadamente, sob a premissa de host
  único com a porta em loopback — a exposição derruba a premissa.
- **`DJANGO_SUPERUSER_*`.** Credencial administrativa no `.env`; precisa sair antes de qualquer
  ambiente compartilhado.

O mesmo conjunto, visto como risco e não como procedimento, está em `docs/seguranca.md`: é lá
que moram as premissas de confiança, os controles ausentes e a fronteira de exposição.
