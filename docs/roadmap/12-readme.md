# Passo 12 — README

## Objetivo

Escrever a receita que leva alguém do repositório clonado a um fluxo Authorization Code +
PKCE fechado à mão.

## Depende de

Todos os anteriores: o README documenta o que existe, com os valores que de fato foram
usados. Escrito antes, descreveria intenção.

## Arquivos criados

- `README.md`

## O que fazer

O README documenta a **jornada de clonar-e-rodar**: clonar, configurar o `.env`, subir o
compose e fechar o fluxo. Não exige Python no host — só Docker.

Uma nota curta, no início, registra que existe uma segunda jornada: quem for **desenvolver**
roda a aplicação em `runserver` no host, contra o Postgres e o Redis do compose, e para
isso precisa de Python 3.14 com virtualenv. As duas jornadas leem o mesmo `.env`, e é o
compose que sobrescreve `DATABASE_URL` e `REDIS_URL` para os nomes de serviço quando a
aplicação roda em container. Duas linhas bastam; o detalhe está em `docs/roadmap/`.

A receita, **nesta ordem**, que é a ordem em que os comandos funcionam:

1. **Criar o `.env`** — copiar de `.env.example`, gerar a `SECRET_KEY` e definir
   `POSTGRES_*` e a `DATABASE_URL` coerente com elas (passo 01).
2. **Gerar a chave RSA** — `scripts/gen_dev_key.sh` e a linha `OIDC_RSA_PRIVATE_KEY` no
   `.env` (passo 03). Antes de subir o stack: subir sem a chave produz um IdP que responde
   normalmente, com JWKS vazio e discovery sem os endpoints de token — a falha silenciosa
   que este roadmap existe para prevenir.
3. **Subir o stack** — `docker compose up --wait`, com a nota de que os três serviços
   precisam ficar `healthy`.
4. **Criar o superusuário** — por `createsuperuser` ou pelas variáveis
   `DJANGO_SUPERUSER_*` do entrypoint.
5. **Registrar uma Application** pelo admin, com os quatro campos que importam:
   - `client_type = public`
   - `authorization_grant_type = authorization-code`
   - **`algorithm = RS256`**
   - `redirect_uri = http://localhost:8000/noop` — URL que **não precisa existir**: o
     navegador é redirecionado para lá com o `code` na query string, e o `code` é lido da
     barra de endereços. O 404 na tela é o resultado esperado.
6. **A URL exata da discovery**: `{BASE_URL}/o/.well-known/openid-configuration`.
7. **O fluxo PKCE fechado à mão** — gerar `code_verifier` e `code_challenge`, chamar
   `/o/authorize/`, autenticar, consentir, capturar o `code` e trocá-lo em `/o/token/`,
   conferindo que a resposta traz `id_token` além do `access_token`.

### O que o README precisa dizer e o código não diz

- **`algorithm = RS256` é o alçapão clássico.** Em branco, o fluxo Authorization Code
  completa, o `access_token` chega e **nenhum `id_token` é emitido, sem erro visível**.
  Quem lê a receita precisa saber disso antes de perder uma tarde.
- **`BEHIND_TLS_PROXY`** — o que é, e por que o endurecimento de transporte depende dela e
  não de `DEBUG`. Com valor `False` atrás de um proxy TLS real, os cookies vão sem flag
  `Secure` e sem HSTS, **silenciosamente**. Não há sinal de alerta; o README é o único
  aviso que existe hoje.
- **`.env.example` sai com `DEBUG=False` e `BEHIND_TLS_PROXY=False`**, e o fluxo fecha
  assim mesmo em `http://localhost`. Isso é deliberado, não descuido.
- **A exigência de posição do `CorsMiddleware`** — acima de `CommonMiddleware` e do
  `WhiteNoiseMiddleware`. Sem consumidor nesta fase, um posicionamento errado é
  indetectável agora e reaparece na fase do SPA como erro de CORS que ninguém associa
  àquela linha. Registrar no README é parte do que torna defensável ter mantido a
  dependência.
- **O superusuário é um só.** Quem seguiu o roadmap já criou um no passo 06, e o banco é o
  mesmo: o volume do Postgres do compose. Rodar `createsuperuser` de novo com o mesmo
  e-mail falha por unicidade, e isso é o modelo funcionando, não um erro de receita. O
  passo 4 acima só é necessário em banco novo.
- **`{BASE_URL}/o` é o issuer.** Uma RP estritamente RFC 8414 procurará em
  `{BASE_URL}/.well-known/oauth-authorization-server/o` e receberá 404; a forma que
  suportamos é a da OIDC Discovery 1.0 (ADR 0007).

## Proibições que incidem aqui

- **Não documentar rota interna, tabela ou formato de sessão como contrato para relying
  party.** O contrato com a RP é OIDC Discovery 1.0 a partir do issuer, e nada além disso.
- **Não documentar receita que peça senha fora de `/accounts/login/` ou `/admin/login/`.**

## Riscos e sinais

- **README que descreve valores diferentes dos que estão no código** — sinal: nenhum
  automático. Documentação que envelhece e mente é passivo; os valores citados aqui devem
  ser conferidos contra os arquivos, não contra a memória.
- **Ausência da nota sobre `BEHIND_TLS_PROXY`** — sinal: nenhum, e é o ponto: um erro de
  configuração sem sinal técnico só é evitável por documentação.

## Apontamentos de fase seguinte

Registrados aqui como o inventário do que ficou de fora desta fase, para que não se percam
entre passos. Cada um entra com o fluxo que o justifica.

- **Rate limiting em `/authorize`, `/token` e `/admin/login/`** — primeiro item da fase
  seguinte, antes de qualquer exposição fora de localhost. O `docs/esboco.md` só menciona
  os dois primeiros; `/admin/login/` é tela de senha com sessão própria e hoje sem
  cobertura nenhuma.
- **`email_verified`** — fora desta fase. As RPs não distinguirão e-mail verificado de não
  verificado.
- **RP-initiated logout (`end_session_endpoint`)** — fora do núcleo.
- **`cleartokens` e `clearsessions` sem agendamento** — as tabelas do DOT e a
  `django_session` crescem indefinidamente. Vira obrigação operacional a partir do primeiro
  uso contínuo.
- **Chave RSA única, sem conjunto de rotação** — a primeira rotação será disruptiva e
  demandará ADR própria.
- **`BEHIND_TLS_PROXY` mal configurada não tem sinal de alerta** — um check de startup do
  Django resolveria; fica adiado. Enquanto isso, o aviso vive só no README.
- **Log só em stdout, sem coleta externa** — some quando o container é recriado.
- **Superusuário via `DJANGO_SUPERUSER_*`** — coloca credencial administrativa no `.env`;
  precisa ser removido antes de qualquer ambiente compartilhado.
- **Nenhum teste automatizado nesta fase** — a cobertura do fluxo OIDC fica pendente.

## Passo concluído quando

Alguém que nunca viu o projeto executa a receita do começo ao fim, sem consultar outro
arquivo, e obtém um `id_token` válido na resposta de `/o/token/`.
