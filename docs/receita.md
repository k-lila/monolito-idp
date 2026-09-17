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
| O IdP atende em | `https://$PUBLIC_HOST`, pelo proxy | `http://localhost:8000`, texto claro |
| Serve para | ver o IdP funcionando | editar código e ver o efeito sem rebuild |

As duas leem o mesmo `.env`, e o `docker-compose.yml` sobrescreve seis variáveis dele quando a
aplicação roda em container. Três são de endereço — `DATABASE_URL`, `REDIS_URL` e
`AUDIT_LOG_PATH` —, porque lá dentro `localhost` seria o próprio container. As outras três são
a fronteira de transporte — `BASE_URL`, `ALLOWED_HOSTS` e `BEHIND_TLS_PROXY` —, derivadas de
`PUBLIC_HOST` e ligadas só atrás do proxy: é o endurecimento que não faz sentido no
`runserver`, que fala texto claro (`docs/adr/0017-terminar-o-tls-num-proxy-declarado-no-compose.md`).

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
openssl rand -hex 32   # REDIS_PASSWORD
```

Preencha `SECRET_KEY`, `POSTGRES_PASSWORD` e `REDIS_PASSWORD`, e deixe `DATABASE_URL` e
`REDIS_URL` coerentes com elas e com `POSTGRES_USER`, `POSTGRES_DB`, `POSTGRES_PORT` e
`REDIS_PORT` — a coerência é manual, sem mecanismo que a verifique.

A `REDIS_URL` da jornada de construção fica `redis://:SENHA@localhost:6379/0`: usuário vazio,
senha depois dos dois pontos. Dentro do container o compose monta a mesma URL a partir da
mesma variável, de modo que a senha do servidor e a do cliente não podem divergir. **Vazia é o
mesmo que ausente**: nos dois casos `${REDIS_PASSWORD:?}` aborta o `up` nomeando a variável, e
servidor nenhum sobe sem `requirepass`. Fora do container a repetição é sua — a `REDIS_URL` do
`.env` carrega a senha à mão, e divergir dela derruba toda requisição do `runserver`
(`docs/runbook.md`).

`PUBLIC_HOST` já sai preenchida no exemplo, e é o nome pelo qual o proxy atende — dele o
compose deriva `BASE_URL`, `ALLOWED_HOSTS` e o certificado, e de `BASE_URL` sai o issuer,
`{BASE_URL}/o`. **Trocá-lo por um nome de verdade é editar esta linha antes de o nome antigo
ter sido usado; depois, não é.** Cada coisa que já foi emitida sob o nome velho tem de ser
refeita fora daqui: o certificado da CA local, a linha de `/etc/hosts` do passo 3b, o estado de
HSTS (HTTP Strict Transport Security) de um ano em cada navegador que visitou, e o issuer
cacheado em cada relying party (RP) que já integrou. O custo completo está no fim deste
documento, em "Produção — o que ainda não existe".

**A escolha de `https://<nome público>/o` como issuer vale por enquanto.** É de 2026-09-13, e
a janela para revê-la fecha na primeira RP integrada: enquanto não houver nenhuma, trocar a
string custa zero; dali em diante o issuer está cacheado do outro lado e a troca deixa de ser
edição deste arquivo para virar reconfiguração de terceiro
(`docs/adr/0007-fixar-o-issuer-do-idp-em-base-url-barra-o.md`). A forma está decidida; a string
definitiva, não — é o que `docs/seguranca.md` lista como pendente antes de expor.

**Nada confere o nome que você escrever.** As quatro derivações — o certificado,
`ALLOWED_HOSTS`, `BASE_URL` e a linha de `/etc/hosts` — saem todas desta mesma variável, de
modo que um erro de digitação é autoconsistente: `idp.locahost`, com um `l` a menos, sobe o
stack, emite certificado para esse nome, resolve esse nome, publica a descoberta sob ele e
passa a suíte inteira. Não existe no sistema um segundo ponto que possa discordar. O engano só
aparece a olho humano, na claim `iss` de um `id_token` ou no `issuer` da descoberta, e só fica
caro quando a primeira RP o cacheia.

Os comandos desta jornada o usam como variável de shell:

```bash
export PUBLIC_HOST=$(grep '^PUBLIC_HOST=' .env | cut -d= -f2)
```

A regra de caracteres deste arquivo não é cosmética: ele atravessa três gramáticas, a do
`django-environ`, a da interpolação do próprio docker compose e a de URL (Uniform Resource
Locator), que vale para `DATABASE_URL` e `REDIS_URL`.

- nenhum valor entre aspas;
- nenhum `${...}` dentro do arquivo;
- `SECRET_KEY` sem `$ # " ' \` — `openssl rand -hex 48` produz só hexadecimal e satisfaz a
  regra por construção;
- `POSTGRES_PASSWORD` alfanumérica, pelo mesmo motivo;
- `REDIS_PASSWORD` em hexadecimal, e aqui a razão é a terceira gramática: `@`, `:`, `/` e `#`
  quebram a URL, e o erro que sai fala de host ou de porta, nunca de senha.

`POSTGRES_PORT` e `REDIS_PORT` são as portas publicadas **no host**, com default `5432` e
`6379`. Se alguma já estiver ocupada nesta máquina, mude aqui: as portas internas do compose
não mudam.

`AUDIT_LOG_PATH` já sai preenchida com `logs/audit.log`, o caminho da trilha de auditoria na
jornada de construção — relativo ao diretório de trabalho, e é por isso que os comandos se rodam
da raiz do repositório. O diretório `logs/` vem versionado no clone, por um `.gitkeep`. Dentro do
container o `docker-compose.yml` sobrescreve a variável para `/var/log/nova_api/audit.log`, no
volume nomeado `auditlog`. **Se o seu `.env` é anterior a esta variável, acrescente a linha à
mão**: sem ela nada sobe, e a mensagem nomeia a variável
(`docs/adr/0013-registrar-a-trilha-de-auditoria-dos-quatro-sinais-em-arquivo-duravel.md`). O
mesmo vale, e pela mesma razão, para `PUBLIC_HOST` e `REDIS_PASSWORD`.

**Como você sabe que deu certo.**

```bash
docker compose config
```

O comando imprime o arquivo do compose já interpolado. Três conferências ali: a senha dentro
de `DATABASE_URL` e a dentro de `REDIS_URL` idênticas às do `.env`, caractere a caractere; e
`BASE_URL`, `ALLOWED_HOSTS` e o `PUBLIC_HOST` do serviço `proxy` carregando o mesmo nome.
Valor truncado é senha com `$`, e a manifestação é um erro de autenticação com as duas strings
iguais a olho nu. Variável ausente não chega aqui: o comando aborta nomeando-a
(`docs/runbook.md`).

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

**O que faz.** Constrói a imagem, sobe `postgres`, `redis`, `app` e `proxy` nessa ordem e
espera ficarem prontos. O entrypoint do `app` roda `migrate` e `collectstatic` antes do
gunicorn; o `proxy` emite o certificado do nome público pela sua autoridade certificadora (CA)
interna.

Se este ambiente **já rodou** o stack alguma vez, um passo antes, uma vez só:

```bash
docker compose run --rm --user root app chown -R 10001:10001 /var/log/nova_api
```

O processo deixou de rodar como `root`, e o volume `auditlog` já existente continua sendo de
`root`. O Docker copia dono e modo da imagem só para volume **vazio** — em volume populado
não recopia nada, e o `app` morre no boot com erro de permissão que não menciona o volume.

```bash
docker compose up --wait
```

**Como você sabe que deu certo.** O comando só retorna quando os serviços de sonda estão
`healthy`; `docker compose ps` mostra o estado de cada um. Os tempos do `HEALTHCHECK` são
derivados dos tetos da própria aplicação, não escolhidos — a conta está em
`docs/adr/0011-dar-teto-de-tempo-ao-health-e-derivar-o-healthcheck-dele.md`.

Pare o `runserver` antes: ele responde no mesmo `localhost:8000` de que a jornada de
construção depende, e a confusão entre o que está de pé e o que não está custa caro. Disputa
de porta já não há — o serviço `app` não publica nenhuma, e quem ocupa o host é o `proxy`, nas
portas 80 e 443 (`docs/runbook.md`).

### 3b. Confiar no certificado

**O que faz.** Extrai a raiz da CA local do Caddy, para que navegador e `curl` deixem de
alertar. Sem isso nada está errado — o alerta é o comportamento correto de quem não conhece
essa autoridade.

```bash
docker compose cp proxy:/data/caddy/pki/authorities/local/root.crt ./ca-local.crt
curl --cacert ./ca-local.crt https://$PUBLIC_HOST/health
```

A raiz vive no volume `caddydata`, e é ele que a preserva entre `up`s: sem o volume, cada
subida geraria uma CA nova e o certificado confiado ontem seria de outra autoridade.
`docker compose down -v` tem o mesmo efeito, de propósito — e obriga a confiar de novo.

Se o nome não resolver fora do navegador, o `nsswitch` deste host não trata `.localhost`
sozinho. A linha em `/etc/hosts`, derivada do próprio `.env` para não haver dois nomes:

```bash
echo "127.0.0.1 $PUBLIC_HOST" | sudo tee -a /etc/hosts
```

**Como você sabe que deu certo.** O `curl` acima devolve o JSON do `/health` sem reclamar de
certificado. No navegador, a mesma URL abre sem interstício depois de a raiz ser importada —
onde se importa varia com o sistema, e é a única parte deste passo que este documento não
prescreve.

### 4. Criar o superusuário

**O que faz.** Cria a conta administrativa que abre o `/admin/`. Necessário em banco novo, e
não há alternativa: o boot não cria conta nenhuma, de modo que `up --wait` verde significa
"de pé", não "pronto para usar"
(`docs/adr/0019-criar-o-superusuario-por-comando-explicito-fora-do-boot.md`).

```bash
docker compose run --rm app python manage.py createsuperuser
```

`run --rm`, e não `exec`: o comando precisa de terminal interativo para o prompt de senha, e o
container descartável some depois. A senha é digitada, nunca escrita em arquivo — as variáveis
`DJANGO_SUPERUSER_*` saíram do `.env.example` e do entrypoint, e se ainda estiverem no seu
`.env`, remova-as.

**Como você sabe que deu certo.** `https://$PUBLIC_HOST/admin/` aceita esse e-mail e abre a
tela de administração. O e-mail é o identificador de login e é único: repetir o mesmo falha, e
isso é o modelo funcionando.

### 5. Registrar uma Application

**O que faz.** Cria o cliente OAuth2 que a relying party usará. Quatro campos importam.

Entre em `https://$PUBLIC_HOST/admin/oauth2_provider/application/add/`:

- `client_type` = **public**
- `authorization_grant_type` = **authorization-code**
- `algorithm` = **RS256**
- `redirect_uri` = `http://localhost:8000/noop`

O `redirect_uri` aponta para uma URL que não precisa existir — e agora não existe mesmo: a
porta 8000 deixou de ser publicada, e o navegador mostra erro de conexão em vez do 404 de
antes. Tanto faz. O que importa é que ele foi levado para lá com o `code` na query string, e é
da barra de endereços que o `code` é lido.

**Como você sabe que deu certo.** Depois de salvar, a Application aparece na listagem com o
`client_id` preenchido — anote-o. Deixar `algorithm` em branco não acusa nada, nem aqui nem
no `/o/authorize/`: a falha só se manifesta na troca do código (`docs/runbook.md`).

### 6. Conferir a descoberta

**O que faz.** Lê o documento que a RP consome para descobrir os endpoints e o algoritmo de
assinatura. O contrato visto do lado dela está em `docs/integracao-rp.md`.

```bash
curl -s --cacert ./ca-local.crt https://$PUBLIC_HOST/o/.well-known/openid-configuration
```

**Como você sabe que deu certo.** Duas coisas no documento: `issuer` igual a
`https://$PUBLIC_HOST/o`, que é a claim `iss` de todo `id_token` e o que cada RP guarda em
cache; e
`id_token_signing_alg_values_supported` igual a `["RS256","HS256"]`. Os quatro endpoints —
authorize, token, userinfo e jwks — ficam listados com chave ou sem, e por isso é o `alg` que
denuncia a chave ausente.

### 7. Fechar o fluxo PKCE à mão

**O que faz.** Percorre à mão o caminho que a relying party percorre, do redirecionamento ao
`id_token`.

Gere o par verificador/desafio:

```bash
docker compose run --rm app python -c "
import base64, hashlib, secrets
v = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b'=').decode()
c = base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b'=').decode()
print('code_verifier =', v)
print('code_challenge =', c)
"
```

Abra no navegador, substituindo `CLIENT_ID` e `CODE_CHALLENGE`:

```
https://SEU_PUBLIC_HOST/o/authorize/?response_type=code&client_id=CLIENT_ID&redirect_uri=http://localhost:8000/noop&scope=openid%20profile%20email&state=xyz&code_challenge=CODE_CHALLENGE&code_challenge_method=S256
```

O `redirect_uri` da query tem de ser **idêntico** ao registrado na Application, caractere a
caractere — é por isso que ele continua em `http://localhost:8000/noop` mesmo agora que o IdP
atende em outro esquema e outro nome. Ele não é buscado pelo IdP; é só comparado e devolvido
ao navegador.

`code_challenge_method=S256` é obrigatório e literal: a descoberta anuncia
`code_challenge_methods_supported` igual a `["S256"]`. Com `plain` a tela de consentimento ainda
aparece normalmente, e a recusa vem só depois — quem trocar o método para depurar vai depurar a
tela errada (`docs/runbook.md`).

Autentique em `/accounts/login/`, consinta na tela seguinte e copie o `code` da barra de
endereços depois do erro esperado em `/noop`. Troque-o por token:

```bash
curl -s --cacert ./ca-local.crt -X POST https://$PUBLIC_HOST/o/token/ \
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
e nenhum `app` nem `proxy`. O `redis` verde aqui já significa autenticação de pé: o healthcheck
compara a saída com `PONG`, e sob senha errada ela seria `NOAUTH` ou `WRONGPASS`.

### 3. Apontar o `.env` para `localhost`

**O que faz.** Garante que `DATABASE_URL` e `REDIS_URL` usem `localhost` e as portas publicadas
no host, `POSTGRES_PORT` e `REDIS_PORT` — que é como o `.env.example` já sai. Quem se conecta
aqui é o `runserver`. Não altere as duas pensando no container: o `docker-compose.yml` as
sobrescreve por conta própria quando a aplicação roda lá dentro.

A `REDIS_URL` daqui carrega a mesma `REDIS_PASSWORD` do servidor, em
`redis://:SENHA@localhost:6379/0`. Sem ela, toda operação de cache falha com
`redis.exceptions.AuthenticationError` — e, como `SESSION_ENGINE` é `cached_db`, toda
requisição falha junto. A mensagem é a do cliente Python, que negocia com `HELLO`, e não traz
`NOAUTH`: o texto medido está na seção 20 de `docs/runbook.md`.

As três variáveis de transporte — `BASE_URL`, `ALLOWED_HOSTS` e `BEHIND_TLS_PROXY` — também
ficam como o exemplo as traz. **Não as aponte para o nome público**: o `runserver` fala texto
claro, e `BASE_URL` em `https` faz o Django devolver 301 para um nome que quem responde é o
container.

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
trocando o prefixo `docker compose run --rm app python` por `.venv/bin/python`. O endereço,
esse, **não** é o mesmo: aqui é `http://localhost:8000`, sem proxy e sem certificado, porque
`BASE_URL` é o do `.env`. Cai fora o `--cacert` de todo `curl`, e o issuer da descoberta é
`http://localhost:8000/o`.

Os passos 3b e o `chown` do passo 3 não têm equivalente aqui: não há proxy nem volume. A
trilha de auditoria vai para `logs/audit.log`, no diretório de trabalho.

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

O gunicorn continua rodando sem `--access-logfile`, mas o log de acesso existe por outro
caminho: quem emite a linha é o middleware do projeto, no logger `access`, com o nome da rota, o
método, o status e a duração — e o `/health` fica de fora, para que a sonda de dez em dez
segundos não afogue o resto. O log traz ainda `migrate` e `collectstatic` no boot, as mensagens
de `django.request` e de `oauth2_provider`, e o traceback de um 500. O nível vem de `LOG_LEVEL`,
que governa também a linha de acesso. Na jornada de construção esse mesmo log sai no terminal do
`runserver`.

**Toda linha da aplicação é um objeto JSON**, e o log do container é misto: as linhas do gunicorn
e a saída de `migrate` e de `collectstatic` continuam em texto plano. A forma que funciona é a de
`docs/runbook.md`:

```bash
docker compose logs --no-color --no-log-prefix app | jq -R 'fromjson? | select(.level=="ERROR")'
```

Não há coleta externa: o log operacional some com o container. A trilha de auditoria, essa não —
vive em volume nomeado, e como lê-la está em `docs/runbook.md`.

### Desbloquear uma conta ou uma origem

Cinco tentativas falhas de entrar bloqueiam a conta, e cinco de uma mesma origem bloqueiam a
origem. O bloqueio termina sozinho quinze minutos depois da última tentativa — insistir adia o
fim. Para devolver o acesso antes disso:

```bash
.venv/bin/python manage.py axes_reset_username pessoa@exemplo.com
.venv/bin/python manage.py axes_reset_ip 203.0.113.10

docker compose exec app python manage.py axes_reset_username pessoa@exemplo.com
docker compose exec app python manage.py axes_reset_ip 203.0.113.10
```

`axes_list_attempts` mostra o que está registrado — origem, identificador tentado e número de
falhas —, e `axes_reset` sem argumento apaga tudo de todo mundo, evidência de ataque inclusive.
O e-mail vai como foi digitado na tentativa, sem normalizar caixa. Os tetos de requisição de
`/accounts/login/`, de `/o/token/` e de `/o/authorize/` não têm comando — a janela dos três
expira em sessenta segundos, e comando nenhum acima alcança o 429 em JSON que o teto da própria
tela de login devolve. Sintoma, causa e o resto do procedimento estão em `docs/runbook.md`.

## Produção — o que ainda não existe

**Nada nesta seção foi exercitado.** Não é procedimento: é a lista das diferenças já
conhecidas e das decisões que o repositório ainda não tomou. Escrever um passo a passo de
produção agora seria inventar um caminho que ninguém percorreu.

### Diferenças de configuração já conhecidas

Quatro itens desta lista saíram dela com o proxy: `BASE_URL`, `BEHIND_TLS_PROXY` e
`ALLOWED_HOSTS` passaram a ser derivados de `PUBLIC_HOST` pelo próprio compose, e a porta do
`app` deixou de ser publicada. O que continua sendo diferença:

- **O endereço de publicação do proxy.** Hoje `127.0.0.1:80` e `127.0.0.1:443`; expor é editar
  esses dois endereços à mão, no `docker-compose.yml`. Deliberadamente não é variável
  (`docs/adr/0017-terminar-o-tls-num-proxy-declarado-no-compose.md`).
- **O certificado.** Sai da CA interna do Caddy, que nenhum cliente de fora conhece. Trocar
  por um de verdade é trocar a diretiva `tls internal` de `docker/Caddyfile`; deixar de trocá-la
  ao expor faz o Caddy tentar ACME contra a internet (`docs/runbook.md`).
- **O nome em `PUBLIC_HOST`.** Com ele muda o `issuer`, que é `{BASE_URL}/o` e fica cacheado em
  cada RP (`docs/adr/0007-fixar-o-issuer-do-idp-em-base-url-barra-o.md`). E o HSTS de um ano
  marca o navegador de quem visitar: trocar de nome depois exige
  limpar esse estado em cada navegador. É a decisão com prazo desta lista: o nome de hoje é
  provisório por escolha, e a provisoriedade acaba na primeira RP integrada — depois dela, o
  issuer é permanente na prática.
- **`TRUSTED_PROXY_COUNT`.** Vale `1`, que é o certo com um proxy só. Cada intermediário
  acrescentado à frente do Caddy soma um, e errar o número devolve à trilha e ao limitador de
  taxa um endereço que não é o do cliente.

### Decisões que o repositório ainda não tomou

- **Onde ficam os segredos.** O `.env` não serve: carrega `SECRET_KEY` e a chave privada RSA em
  texto claro, num arquivo do host.
- **A migração no entrypoint.** Correta para uma réplica, errada para duas — com mais de uma,
  ela sai do boot e vira passo próprio.
- **Rotação da chave RSA.** Existe uma chave, sem conjunto de rotação: a primeira troca
  invalida todo token vivo.
- **Coleta de log.** Só stdout: o log operacional some com o container.
- **Retenção da trilha de auditoria.** O arquivo é durável e cresce indefinidamente; poda e
  retenção não estão decididas.
- **Provisionamento não supervisionado.** A conta administrativa passou a exigir terminal
  interativo, e quem precisar criá-la sem terminal terá de decidir outra coisa
  (`docs/adr/0019-criar-o-superusuario-por-comando-explicito-fora-do-boot.md`).

O mesmo conjunto, visto como risco e não como procedimento, está em `docs/seguranca.md`: é lá
que moram as premissas de confiança, os controles ausentes e a fronteira de exposição.
