# nova_api

Provedor de identidade (IdP, de *Identity Provider*) OpenID Connect (OIDC) sobre Django e
`django-oauth-toolkit`: fecha o fluxo Authorization Code + PKCE (Proof Key for Code Exchange),
publica descoberta e JWKS (JSON Web Key Set), e emite `id_token` assinado em RS256 (RSA, de
Rivest–Shamir–Adleman, com SHA-256).

## O escopo é o de host único, exposto só pelo proxy

Tudo o que está decidido neste repositório descansa sobre uma premissa única:

- host único, orquestrado por `docker-compose.yml`;
- uma réplica da aplicação;
- Postgres e Redis publicados em `127.0.0.1`; a aplicação não publica porta nenhuma;
- o proxy publicado em `127.0.0.1` em desenvolvimento e na jornada de container. Em produção ele
  é a exceção declarada: a ADR 0026 o publica em 80 e 443 fora de loopback por um arquivo de
  override do compose, `docker-compose.prod.yml`, que quem opera a instância da AWS (Amazon Web
  Services) invoca com `docker compose -f docker-compose.yml -f docker-compose.prod.yml`, com um
  salto de proxy só. O security group da instância é a única barreira de rede — pré-condição que
  vive fora do repositório e que nada nele verifica: só 80 e 443 da internet, SSH (Secure Shell)
  restrito ao endereço de quem opera;
- TLS (Transport Layer Security) terminado nesse proxy: certificado de uma autoridade
  certificadora (CA) local na jornada de container em `idp.localhost`, e certificado público, por
  ACME (Automatic Certificate Management Environment), em produção (ADR 0026). O Gunicorn
  continua falando texto claro na rede interna, e só o proxy o alcança;
- pessoas usuárias com conta criada no admin (ADR 0023), além de quem opera a máquina.

O override e o certificado público entram no passo 7 de `docs/plano-contrato-backend.md`; até
lá, o proxy publica em `127.0.0.1` e o `docker/Caddyfile` emite pela CA interna (`tls internal`).

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
cp .env.example .env       # preencha SECRET_KEY, POSTGRES_PASSWORD, REDIS_PASSWORD,
                           # DATABASE_URL e REDIS_URL; confira PUBLIC_HOST
./scripts/gen_dev_key.sh   # cole a linha impressa na OIDC_RSA_PRIVATE_KEY vazia
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
RSA e a única `SECRET_KEY` deste IdP, e sobrescrevê-lo destrói as duas sem que nenhum `git
reset` as devolva.

O que falta ao seu arquivo são três linhas, acrescentadas **à mão e antes de subir**. Sem
qualquer uma delas nada sobe, e a mensagem nomeia a variável:

```
AUDIT_LOG_PATH=logs/audit.log
PUBLIC_HOST=
REDIS_PASSWORD=
```

`AUDIT_LOG_PATH` é o caminho da trilha de auditoria na jornada de construção; dentro do
container o `docker-compose.yml` o sobrescreve por um caminho em volume nomeado.
`PUBLIC_HOST` é o nome que o proxy atende, e dele o compose deriva `BASE_URL`, `ALLOWED_HOSTS`
e o certificado; o `.env.example` traz o valor sugerido, e é o único arquivo versionado deste
repositório que carrega um nome de host.

`REDIS_PASSWORD` **não pode ficar vazia**: para o compose, vazia e ausente são o mesmo caso, e
o `up` aborta nomeando a variável nos dois. Gere com `openssl rand -hex 32` — `@`, `:`, `/` e
`#` quebram a URL — e ponha o mesmo valor na sua `REDIS_URL` da jornada de construção, que é a
repetição que nenhum mecanismo confere:

```
REDIS_URL=redis://:a-senha-gerada@localhost:6379/0
```

Se o seu ambiente **já rodou** o stack alguma vez, uma correção de posse, uma vez só:

```bash
docker compose run --rm --user root app chown -R 10001:10001 /var/log/nova_api
```

O processo deixou de rodar como `root`, e o volume `auditlog` já existente continua sendo de
`root` — o Docker só copia a posse da imagem para volume **vazio**. Sem isso o `app` morre no
boot, com mensagem de permissão de arquivo que não menciona o volume.

E, se o seu `.env` tinha `DJANGO_SUPERUSER_EMAIL` e `DJANGO_SUPERUSER_PASSWORD`, remova as
duas: o boot deixou de lê-las, e a senha de administrador em texto claro num arquivo é
justamente o que a ADR 0019 tirou do caminho.

## Os demais documentos

| Documento | A que pergunta responde |
| --- | --- |
| `docs/arquitetura.md` | que módulos existem, onde passa a fronteira entre eles e por onde caminha um pedido |
| `docs/receita.md` | como subir o stack passo a passo, o que rodar no dia a dia e o que falta decidir para produção |
| `docs/runbook.md` | quebrou: qual o sintoma, qual a causa, qual a correção; e como operar o que já está de pé |
| `docs/integracao-rp.md` | o que uma relying party — a aplicação que delega a autenticação a este IdP — precisa saber para integrar |
| `docs/seguranca.md` | o que o IdP protege, o que não protege e o que muda antes de ele sair de `localhost` |
| `docs/testes.md` | o que a suíte cobre, em que nível, com que rastreabilidade, e o que ficou de fora |
| `docs/esboco.md` | o que é um IdP e por que cada tecnologia do núcleo, com prós e contras |
| `docs/contrato-backend.md` | o que este IdP deve oferecer, configurar e decidir para a `nova_api_SPA` fechar o fluxo contra ele |
| `docs/plano-contrato-backend.md` | em que ordem cumprir esse contrato, com prós, contras e alternativas de cada passo |
| `CLAUDE.md` | as regras de trabalho deste repositório |

As decisões de arquitetura vivem em `docs/adr/`, uma por arquivo e imutáveis depois de aceitas.
O índice está em `docs/arquitetura.md`; o formato, em `docs/adr/template-adr.md`.
