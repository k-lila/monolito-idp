# Segurança — nova_api

Escrito para quem decide expor este provedor de identidade (IdP, Identity Provider) a alguém.
Diz o que ele protege hoje, com a evidência no código; o que não protege; e o que muda antes
de ele sair de `localhost`.

## 1. A premissa de ambiente

Tudo aqui descansa sobre uma premissa única, declarada no `README.md` e em
`docs/arquitetura.md`:

- host único, orquestrado por `docker-compose.yml`;
- uma réplica da aplicação — premissa da migração no entrypoint;
- portas publicadas em `127.0.0.1`, para o proxy, o Postgres e o Redis; a aplicação não publica
  nenhuma;
- TLS (Transport Layer Security) terminado no proxy do compose, com certificado de uma
  autoridade certificadora (CA) local que nenhum cliente de fora conhece; o Gunicorn fala texto
  claro na rede interna, e só o proxy o alcança;
- nenhuma pessoa usuária além de quem opera a máquina.

**As escolhas descritas adiante são coerentes com esta premissa e só com ela.** Não são
posturas defensáveis em geral; são o que faz sentido enquanto a única coisa que alcança o IdP é
um processo na mesma máquina. Quebrada a premissa por uma porta publicada sem endereço, por um
túnel ou por um proxy à frente, a lista da seção 6 deixa de ser inventário e passa a ser dívida
vencida.

## 2. O que o IdP protege hoje

| Controle | Evidência |
| --- | --- |
| A senha não sai do IdP | a relying party (RP) recebe token, nunca credencial |
| Senha armazenada com Argon2 | `PASSWORD_HASHERS` em `config/settings.py`, Argon2 em primeiro |
| PKCE (Proof Key for Code Exchange) obrigatório, restrito a S256 | `PKCE_REQUIRED` e `COMPLIANT_BCP_RFC9700_PKCE_METHOD` |
| `redirect_uri` por igualdade exata | `tests/test_authorize_guards.py` |
| Logout apenas por POST | `tests/test_logout_view.py` |
| Assinatura assimétrica | `docs/adr/0004-assinar-tokens-com-rs256-e-custodiar-a-chave-privada-no-ambiente.md` |
| Cookie sem estado de identidade | `SESSION_ENGINE = cached_db` em `config/settings.py` |
| Nenhuma origem cruzada autorizada | `CORS_ALLOWED_ORIGINS` vazia em `.env.example` |
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
o estado de banco e de cache — custo aceito nas ADRs (Architecture Decision Records) 0009 e
0010, `docs/adr/0009-isolar-a-view-de-health-da-sessao-e-do-usuario.md` e
`docs/adr/0010-isentar-health-do-redirecionamento-para-https.md`.

**`/admin/` está na mesma origem do IdP**, e portanto atrás do mesmo endereço, do mesmo
transporte e do mesmo formulário de senha que o fluxo de autorização.

O `include` do `django-oauth-toolkit` publica sob `/o/` mais do que este projeto usa. O
inventário, lido de `oauth2_provider/urls.py`:

| Rota | Situação |
| --- | --- |
| `/o/authorize/`, `/o/token/`, `/o/userinfo/`, as duas `.well-known` | em uso |
| `/o/applications/...` | gestão de Applications; exige sessão autenticada |
| `/o/authorized_tokens/...` | tokens da própria conta; exige sessão autenticada |
| `/o/device-authorization/`, `/o/device/`, `/o/device-confirm/...`, `/o/device-grant-status/...` | device grant; não usado |
| `/o/revoke_token/` | revogação RFC 7009; não usada por este projeto |
| `/o/introspect/` | responde 403 — nenhum token pode carregar o scope exigido (ADR 0002) |
| `/o/.well-known/oauth-authorization-server`, `/o/.well-known/oauth-protected-resource` | metadados RFC 8414 e RFC 9728, montados pelo `include` |
| `/o/logout/` | 404 com `OIDC_RP_INITIATED_LOGOUT_ENABLED=False` |
| `/o/register/` | 404 com `DCR_ENABLED` no default `False` |

Duas dessas rotas estão fechadas por configuração declarada em `config/settings.py`; as demais
estão de pé sem que nenhum uso ou teste deste projeto as exercite. Uma consequência merece
registro: a view de `/o/applications/register/` exige apenas sessão autenticada, sem checagem
de `is_staff` nem de permissão — **qualquer conta com senha neste IdP pode registrar uma
Application própria.** Hoje isso é inerte porque a única conta é a de quem opera; deixa de ser
no primeiro ambiente com mais de uma pessoa.

## 4. Controles ausentes

Cada item é uma ausência conhecida, com o risco que ela deixa aberto.

- **Sem teto de requisição em `/admin/login/`, e sem política de senha.** A limitação de taxa
  existe desde a ADR 0016, e alcança as três portas: o `django-axes` conta tentativa falha em
  `/accounts/login/` e em `/admin/login/`, por conta e por origem separadamente, bloqueando por
  quinze minutos contados da última tentativa; e `config/limites.py` põe teto de requisição por
  origem em `/accounts/login/` (60 por minuto), `/o/token/` e `/o/authorize/` (120 por minuto).
  Faltam duas coisas. `/admin/login/` **não tem teto de requisição**: o dicionário
  `RATE_LIMIT_POR_CAMINHO` não o nomeia, de modo que ali só o axes barra, e um laço que apenas
  carregue aquele formulário não encontra limite nenhum. E **não há política de senha**:
  `config/settings.py` não declara `AUTH_PASSWORD_VALIDATORS`, cujo default é lista vazia, de
  modo que nenhuma senha é recusada por ser curta, comum, numérica ou parecida com o próprio
  identificador — os quatro defeitos que os validadores prontos do Django cobrem. É essa
  ausência que enfraquece a aritmética do teto de cinco tentativas, o qual supõe um espaço de
  busca inviável.
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
claims saem sempre da conta autenticada, e `/admin/` exige `is_staff`. O que ela pode fazer
hoje é registrar uma Application própria por `/o/applications/register/`, conforme a seção 3.

## 6. A fronteira: o que muda antes de expor fora de `localhost`

Nenhum item tem ordem declarada. A limitação de taxa era o primeiro, e o único com posição
fixada; ela saiu desta lista porque está de pé, conforme a seção 4. Saíram também quatro itens
de transporte e de container, implantados no mesmo bloco das ADRs 0017, 0018 e 0019: o proxy
TLS com `BEHIND_TLS_PROXY=True` e `ALLOWED_HOSTS` composto pelo compose (ADR 0017), o
`requirepass` no Redis e o `USER` dedicado com a posse de `/var/log/nova_api` — esses dois sem
ADR —, e a criação de superusuário fora do `.env` (ADR 0019).
A ordem do que restou é decisão pendente, registrada na seção 7.

- certificado emitido por uma autoridade que o cliente já conheça, no lugar da CA interna do
  Caddy — é trocar a diretiva `tls internal` de `docker/Caddyfile`, e deixar de trocá-la ao
  expor faz o Caddy tentar ACME contra a internet (`docs/runbook.md`);
- publicar o proxy fora de `127.0.0.1`, que é edição à mão no `docker-compose.yml` e não uma
  variável — é a decisão que este bloco inteiro existe para preparar (ADR 0017);
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
- restrição de quem pode registrar Application;
- confirmação da string do issuer antes da primeira RP integrar, conforme
  `docs/adr/0007-fixar-o-issuer-do-idp-em-base-url-barra-o.md`;
- ao ligar a primeira aplicação de página única, conferir a posição do `CorsMiddleware`, cuja
  configuração incorreta é indetectável enquanto a allowlist estiver vazia — ver
  `docs/runbook.md`;
- `email_verified` e revogação efetiva, que são contrato com a RP e estão em
  `docs/integracao-rp.md`.

## 7. Duas decisões abertas

Registradas como pendentes; nenhuma delas é resolvida por este documento.

**7.1 — O `include` do toolkit publica rotas que o projeto não usa.** Mantém-se o `include`
inteiro, como manda a ADR 0002 ao proibir reescrever e envelopar endpoint de protocolo, ou
restringe-se o URLConf às rotas em uso? A tensão é entre fidelidade à biblioteca e superfície
mínima, e a lista do que está em jogo é a tabela da seção 3.

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
| Issuer em `{BASE_URL}/o`, rotas do toolkit sob prefixo | `config/urls.py`, `config/settings.py` | ADR 0007 |
| Claims emitidas, sem `email_verified` | `accounts/oauth_validators.py` | sem ADR |
| Logout iniciado pela RP, desligado | `config/settings.py`, `OIDC_RP_INITIATED_LOGOUT_ENABLED` | sem ADR |
| Sessão revogável no servidor, cookie sem estado | `config/settings.py`, `SESSION_ENGINE` | ADR 0005 |
| Endurecimento de transporte por `BEHIND_TLS_PROXY` | `config/settings.py` | ADR 0006 |
| Isenção de `/health` no redirecionamento para HTTPS | `config/settings.py`, `SECURE_REDIRECT_EXEMPT` | ADR 0010 |
| `/health` sem sessão e sem usuário | `config/views.py` | ADR 0009 |
| Trilha de auditoria dos cinco sinais, sem e-mail e sem token | `accounts/auditoria.py`, `config/settings.py`, `LOGGING` | ADR 0013, ampliada pela 0016 |
| Origem do cliente resolvida num ponto único | `config/origem.py` | ADR 0015 |
| Bloqueio por tentativa falha em `/accounts/login/` e `/admin/login/` | `config/settings.py`, bloco `AXES_*` | ADR 0016 |
| Teto de requisição por origem em `/accounts/login/`, `/o/token/` e `/o/authorize/` | `config/limites.py`, `RATE_LIMIT_POR_CAMINHO` | ADR 0016 |
| Terminação TLS no proxy, e só ele publicado em `127.0.0.1` | `docker-compose.yml`, `docker/Caddyfile` | ADR 0017, emenda à 0006 |
| Uma réplica, migração no boot, endurecimento por variável | `docker-compose.yml`, `Dockerfile` | ADR 0006 |
| Procedência do endereço em cada linha da trilha | `config/origem.py`, `accounts/auditoria.py` | ADR 0018 |
| Alcance do endereço em cada linha da trilha | `config/origem.py`, `accounts/auditoria.py` | ADR 0020, emenda à 0018 |
| Redis sob `requirepass`, com senha de origem única | `docker-compose.yml` | sem ADR |
| Processo sem `root` no container, UID e GID 10001 | `Dockerfile` | sem ADR |
| Superusuário criado por comando explícito, fora do `.env` | `docker/entrypoint.sh`, `.env.example` | ADR 0019 |

Os nomes de arquivo das ADRs estão em `docs/arquitetura.md`, na tabela de decisões.
