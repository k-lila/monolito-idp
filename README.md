# IdP

Provedor de identidade (IdP, de *Identity Provider*) OpenID Connect (OIDC) sobre Django e
`django-oauth-toolkit`: fecha o fluxo Authorization Code + PKCE (Proof Key for Code Exchange),
publica descoberta e JWKS (JSON Web Key Set), e emite `id_token` assinado em RS256 (RSA, de
Rivest–Shamir–Adleman, com SHA-256).

## O escopo é o de host único, exposto só pelo proxy

Tudo o que está decidido neste repositório descansa sobre uma premissa única:

- host único, orquestrado por `docker-compose.yml`;
- uma réplica da aplicação;
- Postgres e Redis publicados em `127.0.0.1`; a aplicação não publica porta nenhuma;
- o proxy publicado em `127.0.0.1` em desenvolvimento e na jornada de container. Em produção
  nada é publicado: a ADR (Architecture Decision Record) 0027 serve o IdP da máquina do dono por
  um túnel nomeado da Cloudflare, e o override `docker-compose.prod.yml` zera por `!reset []` as
  portas de `proxy`, `postgres` e `redis` e declara o conector, o `cloudflared`. A entrada é o
  túnel, e quem controla a conta da Cloudflare ou as credenciais do túnel controla a entrada;
- TLS (Transport Layer Security) do navegador terminado na borda da Cloudflare, com o certificado
  Universal da zona, em produção, e no proxy, com certificado de uma autoridade certificadora
  (CA) local, na jornada de container em `idp.localhost`. O Caddy mantém `tls internal` nos dois
  ambientes, e o Gunicorn continua falando texto claro na rede interna, alcançado só pelo proxy;
- pessoas usuárias com conta criada no admin ou pelo cadastro público (ADR 0031), além de quem
  opera a máquina.

Isso não é provisório por descuido: é premissa de várias decisões registradas. O que o IdP
protege hoje, o que não protege e o que muda com a exposição está em `docs/seguranca.md`.

## As duas jornadas

A escolha entre elas é o passo zero, e as duas leem o mesmo `.env`.

- **Clonar-e-rodar** — a aplicação sobe no container `app`, ao lado do Postgres e do Redis. O
  host só precisa de Docker com o plugin `compose`. Serve para ver o IdP funcionando.
- **Construção** — a aplicação roda em `runserver` no host, contra o Postgres e o Redis do
  compose, e exige Python 3.14 com ambiente virtual. Serve para editar código e ver o efeito
  sem rebuild de imagem.

A diferença que importa está nas variáveis que o `docker-compose.yml` sobrescreve: o `.env`
guarda os valores da jornada de construção — `DATABASE_URL` e `REDIS_URL` em `localhost`,
`BASE_URL` em `http://localhost:8000`, sem proxy —, e o compose troca as seis quando a
aplicação roda em container. Lá o IdP atende em `https://$PUBLIC_HOST`, pelo proxy; aqui, em
`http://localhost:8000`, pelo `runserver`. É o endurecimento de transporte que separa as duas,
e ele é propriedade da jornada de container (ADR 0017).

## Arranque mínimo

Clonar-e-rodar, do zero ao `/admin/` aberto:

```bash
cp .env.example .env
./scripts/gen_env_secrets.sh   # cole as seis linhas impressas no .env; confira PUBLIC_HOST
docker compose up --wait
docker compose run --rm app python manage.py createsuperuser
```

Os dois primeiros passos exigem editar o `.env` à mão, e a chave RSA tem de estar lá **antes**
de o stack subir: sem ela o IdP responde normalmente e não assina `id_token` nenhum. Cada
passo, com as regras de caracteres do `.env` e o sinal de que deu certo, está em
`docs/receita.md` — inclusive o registro da Application e o fluxo PKCE fechado à mão.

O superusuário é `run`, e não `exec`: ele é criado uma vez, num container descartável, com a
senha digitada num prompt. O boot não cria conta nenhuma (ADR 0019), de modo que `up --wait`
verde não significa "pronto para usar" — significa que o stack está de pé.

O IdP passa a atender em **`https://$PUBLIC_HOST`**, pelo proxy, e não mais em
`http://localhost:8000`. Duas consequências no primeiro acesso. O navegador alerta sobre o
certificado, que sai de uma CA local — `docs/receita.md` mostra como extrair a raiz dela para
confiar. E o nome pode não resolver: o `.localhost` do exemplo é resolvido pelo navegador
sozinho, mas fora dele a resolução depende do `nsswitch` do host. A alternativa é uma linha em
`/etc/hosts`, derivada do próprio `.env` para não haver dois nomes:

```bash
echo "127.0.0.1 $(grep '^PUBLIC_HOST=' .env | cut -d= -f2)" | sudo tee -a /etc/hosts
```

### Se você já tem um `.env`

**Não rode o `cp` acima.** O `.env` é untracked e não tem cópia: ele guarda a única chave privada
RSA e a única `SECRET_KEY` deste clone, e sobrescrevê-lo destrói as duas sem que nenhum `git
reset` as devolva.

O que falta ao seu arquivo são até treze linhas, acrescentadas **à mão e antes de subir**. Sem
qualquer uma delas nada sobe, nem a suíte roda, e a mensagem nomeia a variável:

```
AUDIT_LOG_PATH=logs/audit.log
PUBLIC_HOST=
REDIS_PASSWORD=
SPA_URL=http://localhost:5173
SPA_CLIENT_ID=trocar-pelo-client-id-da-spa
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
EMAIL_HOST=localhost
EMAIL_PORT=25
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
EMAIL_USE_TLS=False
EMAIL_TIMEOUT=10
DEFAULT_FROM_EMAIL=IdP <nao-responda@localhost>
```

`AUDIT_LOG_PATH` é o caminho da trilha de auditoria na jornada de construção; dentro do
container o `docker-compose.yml` o sobrescreve por um caminho em volume nomeado.
`PUBLIC_HOST` é o nome que o proxy atende, e dele o compose deriva `BASE_URL`, `ALLOWED_HOSTS`
e o certificado; o `.env.example` traz o valor sugerido, e é o único arquivo versionado deste
repositório que carrega um nome de host.

`SPA_URL` é a origem da aplicação de página única (SPA, de _Single-Page Application_), destino
do botão "Ir para a aplicação" da home: só esquema, host e porta, sem barra final. A carga das settings recusa forma errada, e em produção
o valor é `https://`, o mesmo da entrada de `CORS_ALLOWED_ORIGINS`. O `http://localhost:5173`
do exemplo passa na carga mesmo atrás do proxy, porque loopback é isento, e o botão levaria à
máquina de quem clica.

`REDIS_PASSWORD` **não pode ficar vazia**: para o compose, vazia e ausente são o mesmo caso, e
o `up` aborta nomeando a variável nos dois. O `./scripts/gen_env_secrets.sh` a imprime em
hexadecimal, junto com a `REDIS_URL` da jornada de construção já coerente com ela. Das seis
linhas que ele imprime, copie só essas duas: as outras quatro trocariam a chave, a `SECRET_KEY`
e a senha do Postgres que o seu `.env` já usa. A coerência entre as duas é do script; ela só
volta a depender de você se uma delas for trocada à mão, e nenhum mecanismo a confere.

As nove últimas linhas do bloco vieram com o autoatendimento de conta (ADR 0031), e os valores
são os de desenvolvimento do `.env.example`: o backend de console escreve cada e-mail no stdout e
não envia nada. `SPA_CLIENT_ID` recebe o `client_id` da Application da SPA; com o marcador, o IdP
sobe, e a interface de programação (API, de _Application Programming Interface_) de conta
recusa toda chamada com 403 `aplicacao_nao_autorizada`. Antes de implantar a versão com essas variáveis num banco que já tem contas, leia "Implantar o
autoatendimento de conta (ADR 0031)", em `docs/receita.md`.

Se o seu ambiente **já rodou** o stack alguma vez, uma correção de posse, uma vez só:

```bash
docker compose run --rm --user root app chown -R 10001:10001 /var/log/idp
```

O processo deixou de rodar como `root`, e o volume `auditlog` já existente continua sendo de
`root` — o Docker só copia a posse da imagem para volume **vazio**. Sem isso o `app` morre no
boot, com mensagem de permissão de arquivo que não menciona o volume.

E, se o seu `.env` tinha `DJANGO_SUPERUSER_EMAIL` e `DJANGO_SUPERUSER_PASSWORD`, remova as
duas: o boot deixou de lê-las, e a senha de administrador em texto claro num arquivo é
justamente o que a ADR 0019 tirou do caminho.

## Produção

Produção roda num clone próprio, com os dois arquivos do compose em todo comando (ADR 0027). O
procedimento de implantação e o roteiro de operação ficaram no histórico: o passo 6 em
`git show 8caf117:docs/plano-implantacao.md`, e a seção "Produção pelo túnel" em
`git show 8caf117:docs/runbook.md`. Os dois projetos consolidados antes do deploy estão em
`../pre-deploy.md`. O que este arquivo registra, porque a ADR 0027 o manda registrar aqui, é o
que vive fora do repositório e nada nele verifica.

A zona do IdP, na conta da Cloudflare:

- "Always Use HTTPS" ligado, que leva todo acesso a HTTPS (_Hypertext Transfer Protocol Secure_,
  o HTTP sobre TLS); TLS mínimo 1.2; Pseudo IPv4 (versão 4 do IP, de _Internet Protocol_) em modo
  de sobrescrita;
- Security Level no mínimo;
- desligados: o HSTS (HTTP Strict Transport Security) da Cloudflare, Browser Integrity Check, Bot
  Fight Mode, Always Online, Rocket Loader, Email Address Obfuscation, Automatic HTTPS Rewrites e
  Web Analytics automático;
- nenhuma regra de cache.

A origem não percebe o "Always Use HTTPS" desligado: o trecho do conector ao Caddy é HTTPS, e o
redirecionamento do Django nunca é acionado. Medido no ensaio, `http://` do nome público respondeu
200 com a tela de login. A conferência é `http://` responder 301 para `https://`.

O clone de produção:

- fica fora da árvore de desenvolvimento, com ao menos um diretório ancestral fechado para
  "outros";
- ganha um `.env` novo a partir do `.env.example`, nunca copiado do de desenvolvimento. Nele, as
  seis linhas impressas por `./scripts/gen_env_secrets.sh`, cada uma no lugar da linha do
  exemplo, mais `PUBLIC_HOST`, `CORS_ALLOWED_ORIGINS`, `SPA_URL` em `https://`,
  `SPA_CLIENT_ID` com o `client_id` da Application de produção da SPA, as variáveis `EMAIL_*` e
  `DEFAULT_FROM_EMAIL` com o backend SMTP (_Simple Mail Transfer Protocol_) e os dados da conta
  de envio, `COMPOSE_PROJECT_NAME=nova_api_prod` e `TUNNEL_ID`;
- roda todo comando com `docker compose -f docker-compose.yml -f docker-compose.prod.yml`,
  digitado, sem script, `COMPOSE_FILE` nem link.

A conta da Cloudflare e a do registrador do domínio usam segundo fator. A data de expiração do
domínio e a data-limite de suporte da versão fixada do `cloudflared` ficam com quem opera, fora do
repositório.

## Os demais documentos

| Documento | A que pergunta responde |
| --- | --- |
| `docs/nucleo-idp.md` | o que é um IdP, as invariantes, o contrato com toda relying party e o núcleo de tecnologias |
| `docs/arquitetura.md` | que módulos existem, onde passa a fronteira entre eles e por onde caminha um pedido |
| `docs/receita.md` | como subir o stack passo a passo, o que rodar no dia a dia e o que falta decidir para produção |
| `docs/integracao-rp.md` | o que uma relying party — a aplicação que delega a autenticação a este IdP — precisa saber para integrar |
| `docs/seguranca.md` | o que o IdP protege, o que não protege e o que muda antes de ele sair de `localhost` |
| `docs/testes.md` | o que a suíte cobre, em que nível, com que rastreabilidade, e o que ficou de fora |
| `docs/observabilidade.md` | o que o log e a trilha registram, onde falham em silêncio e o que falta medir |
| `CLAUDE.md` | as regras de trabalho deste repositório |

O runbook, o plano de implantação e o esboço saíram na reorganização de 2026-09-29 e seguem
legíveis no histórico, por `git show 8caf117:docs/<arquivo>`.

As decisões de arquitetura vivem em `docs/adr/`, uma por arquivo e imutáveis depois de aceitas.
O índice está em `docs/arquitetura.md`; o formato, em `docs/adr/template-adr.md`.
