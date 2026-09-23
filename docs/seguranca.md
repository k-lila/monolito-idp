# Segurança — nova_api

Escrito para quem decide expor este provedor de identidade (IdP, Identity Provider) a alguém.
Diz o que ele protege hoje, com a evidência no código; o que não protege; e o que muda ao sair
de `localhost` — exposição decidida pelas ADRs (Architecture Decision Records) 0025 e 0026 e
aplicada nos passos 7 a 9 de `docs/plano-contrato-backend.md`.

## 1. A premissa de ambiente

Tudo aqui descansa sobre uma premissa única, declarada no `README.md` e em
`docs/arquitetura.md`:

- host único, orquestrado por `docker-compose.yml`;
- uma réplica da aplicação — premissa da migração no entrypoint;
- Postgres e Redis publicados em `127.0.0.1`; a aplicação não publica porta nenhuma;
- o proxy publicado em `127.0.0.1` em desenvolvimento e na jornada de container. Em produção ele
  é a exceção declarada: a ADR 0026 o publica em 80 e 443 fora de loopback por um arquivo de
  override do compose, `docker-compose.prod.yml`, que quem opera a instância da AWS (Amazon Web
  Services) invoca com `docker compose -f docker-compose.yml -f docker-compose.prod.yml`, com um
  salto de proxy só. O security group da instância é a única barreira de rede — pré-condição que
  vive fora do repositório e que nada nele verifica: só 80 e 443 da internet, SSH (Secure Shell)
  restrito ao endereço de quem opera;
- TLS (Transport Layer Security) terminado nesse proxy: certificado de uma autoridade
  certificadora (CA) local, que nenhum cliente de fora conhece, na jornada de container em
  `idp.localhost`, e certificado público, por ACME (Automatic Certificate Management
  Environment), em produção (ADR 0026). O Gunicorn fala texto claro na rede interna, e só o proxy
  o alcança;
- pessoas usuárias com conta criada no admin (ADR 0023), além de quem opera a máquina.

O override e o certificado público entram no passo 7 de `docs/plano-contrato-backend.md`; até
lá, o proxy publica em `127.0.0.1` e o `docker/Caddyfile` emite pela CA interna (`tls internal`).

**As escolhas descritas adiante são coerentes com esta premissa e só com ela.** Não são
posturas defensáveis em geral. Até o passo 7 de `docs/plano-contrato-backend.md`, a única coisa
que alcança o IdP é um processo na mesma máquina; a partir do passo 8, a internet o alcança pela
instância. Nesse dia, o que a seção 6 ainda listar como aberto deixa de ser inventário e passa a
ser dívida vencida. Só dois itens estão aceitos como risco da exposição, nas Consequências da
ADR 0026: o `refresh_token` sem expiração e os cookies com a política do default. O mesmo vale
se a premissa for quebrada por outro caminho — um túnel ou um proxy à frente.

## 2. O que o IdP protege hoje

| Controle | Evidência |
| --- | --- |
| A senha não sai do IdP | a relying party (RP) recebe token, nunca credencial |
| Senha armazenada com Argon2 | `PASSWORD_HASHERS` em `config/settings.py`, Argon2 em primeiro |
| Política de senha onde a senha é escolhida | `AUTH_PASSWORD_VALIDATORS` em `config/settings.py` |
| PKCE (Proof Key for Code Exchange) obrigatório, restrito a S256 | `PKCE_REQUIRED` e `COMPLIANT_BCP_RFC9700_PKCE_METHOD` |
| `redirect_uri` por igualdade exata | `tests/test_authorize_guards.py` |
| `redirect_uri` só em `https` atrás do proxy TLS | `ALLOWED_REDIRECT_URI_SCHEMES`, condicionada a `BEHIND_TLS_PROXY` |
| Gestão de `Application` e de token só no admin; sem registro dinâmico | `config/urls.py`, ADR 0024 |
| Logout apenas por POST | `tests/test_logout_view.py` |
| Assinatura assimétrica | `docs/adr/0004-assinar-tokens-com-rs256-e-custodiar-a-chave-privada-no-ambiente.md` |
| Cookie sem estado de identidade | `SESSION_ENGINE = cached_db` em `config/settings.py` |
| CORS (Cross-Origin Resource Sharing) por origem exata, e só sob `/o/` | `CORS_ALLOWED_ORIGINS` no `.env`, uma origem por ambiente (ADR 0022); `CORS_URLS_REGEX` em `config/settings.py` |
| Sem fluxo de recuperação de senha | `config/urls.py`, `tests/test_password_reset_urls.py` |
| Trilha de auditoria de autenticação e de concessão de token | `accounts/auditoria.py`, ADR 0013 |

O que cada linha compra:

- **PKCE com S256** fecha a interceptação de código. Sem ele, um
  código capturado na barra de endereços ou no log de um proxy é trocável por token por quem o
  capturou. `PKCE_REQUIRED` sozinho ainda aceitaria `plain`, em que o desafio é o próprio
  verificador em claro; a segunda chave é o que restringe a S256.
- **Igualdade exata de `redirect_uri`** impede que um endereço de retorno registrado seja
  estendido para um destino controlado por terceiro. A comparação por prefixo é o erro clássico do
  protocolo, e o teste da barra a mais existe para que afrouxá-la fique vermelho.
- **`https` como único esquema de retorno, com `BEHIND_TLS_PROXY=True`,** impede que o código de
  autorização viaje em texto claro pelo canal de frente. O admin recusa gravar `redirect_uri` em
  `http://`, e uma `Application` já gravada assim recebe 400 em `/o/authorize/` em vez do código.
  Com `BEHIND_TLS_PROXY=False`, na jornada de construção, `http` continua aceito, e é o que deixa
  a SPA (Single-Page Application) de desenvolvimento voltar a `http://localhost:5173/callback`.
- **A política de senha** recusa senha curta, comum, só numérica ou parecida com o e-mail da
  própria conta, e é ela que sustenta a aritmética do teto de cinco tentativas. O alcance dela
  tem limites, nomeados na seção 4.
- **A gestão de `Application` só no admin** fecha o registro de cliente por conta comum: as rotas
  de gestão do toolkit não são montadas, e `/admin/` exige `is_staff`.
- **CORS só sob `/o/`** restringe o cabeçalho à superfície de protocolo: com a origem da SPA na
  allowlist, `/admin/` e `/accounts/login/` continuam sem `Access-Control-Allow-Origin`.
- **Logout só por POST** fecha o logout forjado: um `GET` responde 405 e preserva a sessão, de
  modo que uma imagem ou um link apontando para `/accounts/logout/` não desloga ninguém.
- **Assinatura assimétrica em RS256** (RSA, Rivest–Shamir–Adleman, com SHA-256) dispensa
  segredo compartilhado para verificar: nenhuma RP integrada pode forjar um token em nome do IdP.
- **O cookie carrega só o identificador da sessão.** O estado vive no Postgres com cópia quente
  no Redis, o que torna a sessão revogável do lado do servidor — propriedade que um cookie
  assinado não teria.
- **A ausência de recuperação de senha** é controle, não lacuna acidental: `config/urls.py`
  monta uma rota de autenticação por vez, e não existe fluxo de e-mail a sequestrar.
- **A trilha de auditoria** responde quem autenticou, quando, de que origem e qual relying party
  recebeu token, num arquivo durável que sobrevive à recriação do container
  (`docs/adr/0013-registrar-a-trilha-de-auditoria-dos-quatro-sinais-em-arquivo-duravel.md`).
  Ela registra os cinco sinais que existem — autenticação, falha de autenticação, logout,
  concessão de token e bloqueio por tentativas em excesso, este último acrescentado pela
  limitação de taxa (ADR 0016) — e **não fecha a lacuna inteira**: o que continua sem
  registro está nomeado na seção 4. Nenhum e-mail e nenhum valor de token entram nela: a
  pessoa aparece pelo `sub`, e o identificador de uma tentativa falha, por resumo SHA-256.

## 3. Superfície exposta

Publicado em `127.0.0.1`, e apenas ali: o proxy nas portas 80 e 443, o Postgres na 5432 e o
Redis na 6379, conforme `docker-compose.yml`. **A aplicação não publica porta nenhuma** — o
proxy é o único caminho até ela, e é isso, e não vigilância, que impede um cliente do host de
desligar o redirecionamento para HTTPS escrevendo `X-Forwarded-Proto` (ADR 0017).

Superfície própria do projeto, em `config/urls.py`: `/`, `/health`, `/accounts/login/`,
`/accounts/logout/`, `/admin/`, e tudo sob `/o/`. O `/health` é público e sem sessão, e revela
o estado de banco e de cache — custo aceito nas ADRs 0009 e
0010, `docs/adr/0009-isolar-a-view-de-health-da-sessao-e-do-usuario.md` e
`docs/adr/0010-isentar-health-do-redirecionamento-para-https.md`.

**`/admin/` está na mesma origem do IdP**, e portanto atrás do mesmo endereço, do mesmo
transporte e do mesmo formulário de senha que o fluxo de autorização.

Sob `/o/` entram três das cinco listas de rotas do `django-oauth-toolkit` — as de protocolo —,
e ainda assim mais do que este projeto usa (ADR 0024). O inventário, lido de
`oauth2_provider/urls.py` e de `config/urls.py`:

| Rota | Situação |
| --- | --- |
| `/o/authorize/`, `/o/token/`, `/o/userinfo/`, as duas `.well-known` | em uso |
| `/o/applications/...`, `/o/authorized_tokens/...` | 404, com ou sem sessão: `management_urlpatterns` não é montada |
| `/o/device-authorization/`, `/o/device/`, `/o/device-confirm/...`, `/o/device-grant-status/...` | device grant; sem uso pelo projeto, mas o POST de `/o/device-authorization/` grava no banco sem autenticação (seção 4) |
| `/o/revoke_token/` | revogação RFC 7009; não usada por este projeto |
| `/o/introspect/` | responde 403 — nenhum token pode carregar o scope exigido (ADR 0002) |
| `/o/.well-known/oauth-authorization-server`, `/o/.well-known/oauth-protected-resource` | metadados RFC 8414 e RFC 9728, montados pelo `include` |
| `/o/logout/` | 404 com `OIDC_RP_INITIATED_LOGOUT_ENABLED=False` |
| `/o/register/` | 404: `dcr_urlpatterns` não é montada, e `DCR_ENABLED` segue no default `False` |

As rotas de gestão e o registro dinâmico estão fechados pela ausência no URLConf, e
`/o/logout/`, por configuração declarada em `config/settings.py`. Device grant, revogação e
introspecção estão de pé sem que nenhum uso deste projeto os exercite: a unidade da montagem é
a lista, e retirá-los exigiria copiar rotas da biblioteca. Sem uso não quer dizer inerte:
`/o/device-authorization/` aceita POST anônimo e grava uma linha por requisição, e por isso tem
teto de requisição, sem que o URLConf da ADR 0024 mude (seção 4). **Nenhuma conta, com ou sem
`is_staff`, registra Application fora do admin**, que é o único lugar de gestão de clientes e
de tokens.

O preço aparece no próprio admin: o botão "Ver no site" da edição de uma Application aponta
para a rota de detalhe que deixou de existir, e o clique responde 500. É dívida aceita, sem
desligar `view_on_site` (ADR 0024).

## 4. Controles ausentes

Cada item é uma ausência conhecida, com o risco que ela deixa aberto.

- **Sem teto de requisição em `/admin/login/`.** A limitação de taxa
  existe desde a ADR 0016, e alcança as três portas: o `django-axes` conta tentativa falha em
  `/accounts/login/` e em `/admin/login/`, por conta e por origem separadamente, bloqueando por
  quinze minutos contados da última tentativa; e `config/limites.py` põe teto de requisição por
  origem em `/accounts/login/` (60 por minuto), `/o/token/` e `/o/authorize/` (120 por minuto) e
  `/o/device-authorization/` (30 por minuto).
  Falta uma coisa: `/admin/login/` **não tem teto de requisição**. O dicionário
  `RATE_LIMIT_POR_CAMINHO` não o nomeia, de modo que ali só o axes barra, e um laço que apenas
  carregue aquele formulário não encontra limite nenhum.
- **`DeviceGrant` acumula sem limpeza.** `/o/device-authorization/` é a única superfície
  anônima que grava no banco: aceita POST sem sessão e sem CSRF, o oauthlib só confere que o
  `client_id` existe, e o `client_id` da SPA é público. Cada POST responde 200 e grava uma
  linha de `DeviceGrant`. Token nenhum sai dali — `/o/token/` recusa o grant pelo tipo da
  Application —, e o `django-oauth-toolkit` 3.4.1 não tem setting que desligue o device flow;
  a rota continua publicada porque vem na mesma lista do protocolo (ADR 0024). O teto de 30
  requisições por minuto limita o custo por origem, e só isso: `clear_expired()` não apaga
  `DeviceGrant`, e as linhas continuam acumulando a partir de origens distintas, sem nada que as
  recolha. É dívida registrada.
- **A política de senha só alcança a senha escolhida por tela ou por comando.**
  `AUTH_PASSWORD_VALIDATORS` roda nos formulários do admin de adicionar conta e de alterar
  senha, em `changepassword` e em `createsuperuser` interativo. Fora deles, é silenciosa:
  - o login não valida, e conta cuja senha foi gravada antes da política continua entrando com
    ela, por fraca que seja;
  - `create_user` e `set_password` não validam, e a suíte e o `shell` passam por baixo;
  - `createsuperuser` interativo oferece ignorar a recusa ("Bypass password validation"), e
    `createsuperuser --noinput` não valida nada.

  As contas de teste de desenvolvimento têm senha que a política recusaria, e ficam assim até o
  passo 8 de `docs/plano-contrato-backend.md`; nenhuma conta nova nasce com essa senha. Numa
  conta dessas, o teto de cinco tentativas volta a supor um espaço de busca que não existe.
- **Certificado de uma CA local, e só.** O transporte é TLS desde a ADR 0017, e o
  endurecimento — cookie `Secure`, HSTS (HTTP Strict Transport Security), redirecionamento e
  `SECURE_PROXY_SSL_HEADER` — está ligado na jornada de container. O que falta é um certificado
  que um cliente de fora aceite: o de hoje sai da CA interna do Caddy, e confiar nela é passo
  manual de quem opera. A jornada de construção segue em texto claro, com
  `BEHIND_TLS_PROXY=False` — e essa variável, configurada de forma incoerente com o ambiente,
  não emite sinal de alerta; o sintoma e o procedimento estão em `docs/runbook.md`.
- **Sem mecanismo que confira a senha do Redis repetida no `.env`.** O `requirepass` e a
  `REDIS_URL` do container saem da mesma variável, e o `${REDIS_PASSWORD:?}` do compose aborta
  o `up` com ela ausente e com ela vazia: não há como este Redis subir sem autenticação. O que
  continua manual é a jornada de construção, em que a mesma senha é escrita de novo na
  `REDIS_URL` do `.env`. A divergência não abre acesso — o servidor recusa —, e o sintoma está
  em `docs/runbook.md`.
- **Chave RSA única, sem conjunto de rotação.** Não há como rotacionar
  sem invalidar a verificação de todo token vivo, o que significa que a resposta a uma suspeita
  de vazamento da chave é disruptiva por construção (ADR 0004).
- **A trilha de auditoria não cobre dois eventos, e não tem retenção decidida.** Criação de
  Application e revogação de token continuam sem registro, e por ausência de sinal: a primeira
  exigiria um `post_save` no modelo devolvido por `get_application_model()`, e a segunda nem
  isso — o `cleartokens` apaga linhas sem emitir nada. Some-se que retenção e poda do arquivo não
  estão decididas: ele guarda dado pessoal, cresce indefinidamente e nada o monitora (ADR 0013).
- **Log operacional só em `stdout`, sem coleta externa.** Recriar o container apaga o histórico do
  log operacional. A trilha de auditoria não está nesse caso — vive em volume nomeado —, mas
  também não tem coleta externa nenhuma.
- **Dois pontos de resolução de dependências.** O `Dockerfile` roda
  `pip wheel -r requirements.txt`, que resolve as transitivas sem pin na data do build, enquanto
  a suíte roda contra o venv do host. `jwcrypto` — a biblioteca que assina o `id_token` — é uma
  dessas transitivas: um rebuild meses depois pode assinar com código que nenhum teste deste
  repositório jamais exercitou, sob `docker compose up --wait` verde.

## 5. Modelo de ameaças

Curto de propósito, e limitado ao que a premissa da seção 1 admite.

**Observador da rede local.** Hoje não alcança nada: o tráfego do IdP é loopback e não sai do
host. Publicar o proxy sem endereço ou abrir um túnel muda isso — e, com a terminação TLS de
pé, o que ele passaria a ver é tráfego cifrado, desde que o certificado seja aceito pelo
cliente. O que continua em claro é o trecho interno, entre o proxy e o Gunicorn, dentro da rede
do compose.

**Alguém com acesso ao host.** Lê o `.env` e com ele obtém a `SECRET_KEY`, a chave privada RSA
e as senhas do Postgres e do Redis. A credencial do superusuário saiu desse conjunto com a
ADR 0019: ela é digitada num prompt e não fica em arquivo nenhum. Quem tem a chave privada é o
IdP, para todos os efeitos: pode emitir identidade em nome dele para qualquer RP integrada.
Não há controle que mitigue isso nesta fase; o bind em loopback apenas limita quem alcança o
serviço.

**RP registrada e maliciosa.** Recebe `id_token` apenas das pessoas que consentiram com ela, e
não pode forjar token nem verificar o de outra RP — a assinatura é assimétrica e o `aud` a
identifica. O que ela consegue é reter indefinidamente o `refresh_token` que recebeu, que não
expira por tempo e que a desativação da conta não invalida; o procedimento de revogação está em
`docs/runbook.md`.

**Pessoa usuária hostil, com conta neste IdP.** Não alcança dados de outra conta pelo IdP: as
claims saem sempre da conta autenticada, e `/admin/` exige `is_staff`. Também não registra
Application: as rotas de gestão do toolkit não são montadas, e o registro é só do admin
(seção 3).

## 6. A fronteira: o que muda antes de expor fora de `localhost`

Nenhum item tem ordem declarada. A limitação de taxa era o primeiro, e o único com posição
fixada; ela saiu desta lista porque está de pé, conforme a seção 4. Saíram também quatro itens
de transporte e de container, implantados no mesmo bloco das ADRs 0017, 0018 e 0019: o proxy
TLS com `BEHIND_TLS_PROXY=True` e `ALLOWED_HOSTS` composto pelo compose (ADR 0017), o
`requirepass` no Redis e o `USER` dedicado com a posse de `/var/log/nova_api` — esses dois sem
ADR —, e a criação de superusuário fora do `.env` (ADR 0019). Saiu também a restrição de quem
pode registrar Application, fechada pela ADR 0024. A confirmação da forma do issuer que a ADR
0007 pedia saiu com a ADR 0025.
A ordem do que restou é decisão pendente, registrada na seção 7.

- certificado emitido por uma autoridade que o cliente já conheça, no lugar da CA interna do
  Caddy — é trocar a diretiva `tls internal` de `docker/Caddyfile`, e deixar de trocá-la ao
  expor faz o Caddy tentar ACME contra a internet (`docs/runbook.md`); o certificado público
  por ACME é o que a ADR 0026 decide;
- publicar o proxy fora de `127.0.0.1`, pelo override `docker-compose.prod.yml` invocado à mão
  com `-f` na instância, e não por variável — é a decisão que este bloco inteiro existe para
  preparar (ADRs 0017 e 0026), aplicada no passo 7 de `docs/plano-contrato-backend.md`;
- conferir `TRUSTED_PROXY_COUNT` contra a topologia real, e as marcas de origem da trilha
  junto. O sinal do próprio dia é `ip_edge`: enquanto toda linha disser `gateway`, o
  `docker-proxy` continua no caminho e o `ip` não identifica cliente nenhum — ou a exposição
  não tomou efeito, ou o tráfego que se está olhando veio do próprio host, que atravessa o
  `docker-proxy` mesmo depois de a porta sair de `127.0.0.1`. A primeira linha `peer` é o que
  prova que a origem real chegou. `remote_addr_fallback` NÃO é sinal deste dia e não
  aparecerá: com o Caddy à frente o cabeçalho sempre chega, e aquele rótulo denuncia proxy mal
  configurado, em qualquer dia (ADRs 0018 e 0020);
- conjunto de rotação de chave RSA;
- coleta externa de log;
- pin das dependências transitivas, unificando os dois pontos de resolução;
- agendamento de `cleartokens` e `clearsessions`, hoje inexistente;
- ao ligar a primeira aplicação de página única, conferir a posição do `CorsMiddleware`, cuja
  configuração incorreta é indetectável enquanto a allowlist estiver vazia — ver
  `docs/runbook.md`;
- `email_verified` e revogação efetiva, que são contrato com a RP e estão em
  `docs/integracao-rp.md`.

## 7. Decisões abertas

A 7.1 fechou com a ADR 0024 e fica registrada pelo desfecho; a 7.2 continua pendente, e este
documento não a resolve.

**7.1 — O `include` do toolkit publica rotas que o projeto não usa. Fechada.** A pergunta era
manter o `include` inteiro, como mandava a ADR 0002 ao proibir reescrever e envelopar endpoint
de protocolo, ou restringir o URLConf às rotas em uso. A ADR 0024 restringiu pela lista, e não
pela rota: `management_urlpatterns` e `dcr_urlpatterns` saíram, e o que continua publicado sem
uso — device grant, revogação e introspecção — é o preço de não copiar rota da biblioteca. O
resultado é a tabela da seção 3. Do preço, o device grant é a parte que grava no banco, e o
teto de requisição e a dívida que ele não cobre estão na seção 4.

**7.2 — A ordem real da lista da seção 6.** O único item com posição declarada era a limitação
de taxa, e ela saiu da lista por já estar implantada. Nenhum dos que restam tem ordem; ela é
decisão de quem for expor o IdP, e enquanto não for tomada a lista acima é inventário, não
plano.

## 8. Mapa: controle, arquivo, decisão

| Controle | Onde vive | Decisão |
| --- | --- | --- |
| PKCE obrigatório | `config/settings.py`, `PKCE_REQUIRED` | ADR 0002 |
| Restrição a `S256` | `config/settings.py`, `COMPLIANT_BCP_RFC9700_PKCE_METHOD` | sem ADR |
| Assinatura RS256 e custódia da chave no ambiente | `config/settings.py`, `scripts/gen_dev_key.sh` | ADR 0004 |
| Issuer em `{BASE_URL}/o`, rotas do toolkit sob prefixo | `config/urls.py`, `config/settings.py` | ADR 0007; quais rotas, ADR 0024 |
| Só as listas de protocolo do toolkit sob `/o/`; gestão de `Application` só no admin | `config/urls.py` | ADR 0024, emenda à 0002 |
| `redirect_uri` só em `https` com `BEHIND_TLS_PROXY` | `config/settings.py`, `ALLOWED_REDIRECT_URI_SCHEMES` | sem ADR; a condição é a da ADR 0006 |
| Política de senha na criação e na troca | `config/settings.py`, `AUTH_PASSWORD_VALIDATORS` | sem ADR |
| CORS por origem exata, só sob `/o/` | `config/settings.py`, `CORS_ALLOWED_ORIGINS` e `CORS_URLS_REGEX` | ADR 0022, a allowlist; sem ADR, o prefixo |
| Claims emitidas, sem `email_verified` | `accounts/oauth_validators.py` | sem ADR |
| Logout iniciado pela RP, desligado | `config/settings.py`, `OIDC_RP_INITIATED_LOGOUT_ENABLED` | sem ADR |
| Sessão revogável no servidor, cookie sem estado | `config/settings.py`, `SESSION_ENGINE` | ADR 0005 |
| Endurecimento de transporte por `BEHIND_TLS_PROXY` | `config/settings.py` | ADR 0006 |
| Isenção de `/health` no redirecionamento para HTTPS | `config/settings.py`, `SECURE_REDIRECT_EXEMPT` | ADR 0010 |
| `/health` sem sessão e sem usuário | `config/views.py` | ADR 0009 |
| Trilha de auditoria dos cinco sinais, sem e-mail e sem token | `accounts/auditoria.py`, `config/settings.py`, `LOGGING` | ADR 0013, ampliada pela 0016 |
| Origem do cliente resolvida num ponto único | `config/origem.py` | ADR 0015 |
| Bloqueio por tentativa falha em `/accounts/login/` e `/admin/login/` | `config/settings.py`, bloco `AXES_*` | ADR 0016 |
| Teto de requisição por origem em `/accounts/login/`, `/o/token/` e `/o/authorize/` | `config/settings.py`, `RATE_LIMIT_POR_CAMINHO`; o mecanismo, `config/limites.py` | ADR 0016 |
| Teto de requisição por origem em `/o/device-authorization/` | `config/settings.py`, `RATE_LIMIT_POR_CAMINHO`; o mecanismo, `config/limites.py` | sem ADR; a rota, ADR 0024 |
| Terminação TLS no proxy, e só ele publicado em `127.0.0.1` | `docker-compose.yml`, `docker/Caddyfile` | ADR 0017, emenda à 0006 |
| Uma réplica, migração no boot, endurecimento por variável | `docker-compose.yml`, `Dockerfile` | ADR 0006 |
| Procedência do endereço em cada linha da trilha | `config/origem.py`, `accounts/auditoria.py` | ADR 0018 |
| Alcance do endereço em cada linha da trilha | `config/origem.py`, `accounts/auditoria.py` | ADR 0020, emenda à 0018 |
| Redis sob `requirepass`, com senha de origem única | `docker-compose.yml` | sem ADR |
| Processo sem `root` no container, UID e GID 10001 | `Dockerfile` | sem ADR |
| Superusuário criado por comando explícito, fora do `.env` | `docker/entrypoint.sh`, `.env.example` | ADR 0019 |

Os nomes de arquivo das ADRs estão em `docs/arquitetura.md`, na tabela de decisões.
