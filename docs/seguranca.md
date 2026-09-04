# Segurança — nova_api

Escrito para quem decide expor este provedor de identidade (IdP, Identity Provider) a alguém.
Diz o que ele protege hoje, com a evidência no código; o que não protege; e o que muda antes
de ele sair de `localhost`.

## 1. A premissa de ambiente

Tudo aqui descansa sobre uma premissa única, declarada no `README.md` e em
`docs/arquitetura.md`:

- host único, orquestrado por `docker-compose.yml`;
- uma réplica da aplicação — premissa da migração no entrypoint;
- portas publicadas em `127.0.0.1`, para a aplicação, o Postgres e o Redis;
- sem TLS (Transport Layer Security) próprio: o Gunicorn fala texto claro;
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
| `redirect_uri` por igualdade exata | `accounts/tests/test_authorize_guards.py` |
| Logout apenas por POST | `accounts/tests/test_logout_view.py` |
| Assinatura assimétrica | `docs/adr/0004-assinar-tokens-com-rs256-e-custodiar-a-chave-privada-no-ambiente.md` |
| Cookie sem estado de identidade | `SESSION_ENGINE = cached_db` em `config/settings.py` |
| Nenhuma origem cruzada autorizada | `CORS_ALLOWED_ORIGINS` vazia em `.env.example` |
| Sem fluxo de recuperação de senha | `config/urls.py`, `accounts/tests/test_password_reset_urls.py` |

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

## 3. Superfície exposta

Publicado em `127.0.0.1`, e apenas ali: a aplicação na 8000, o Postgres na 5432 e o Redis na
6379, conforme `docker-compose.yml`.

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

- **Sem limitação de taxa em `/o/authorize/`, `/o/token/` e `/admin/login/`.** Nada limita
  tentativa de senha, enumeração de conta pelo formulário de login nem repetição de troca de
  código. É o único item da lista com ordem declarada: a seção 6 o põe como primeiro antes de
  qualquer exposição fora de `localhost`.
- **Sem TLS próprio.** O Gunicorn fala texto claro; TLS é responsabilidade de um proxy à
  frente, e o endurecimento de transporte é opt-in por `BEHIND_TLS_PROXY`. Essa variável,
  quando configurada de forma incoerente com o ambiente, não emite sinal de alerta; o sintoma
  e o procedimento estão em `docs/runbook.md`.
- **Redis sem `requirepass`.** Quem alcança `127.0.0.1:6379` lê e escreve a cópia quente das
  sessões, o que inclui sessões administrativas. O bind em loopback é a única barreira.
- **Container sem `USER` dedicado.** O processo roda como `root` dentro do container — decisão
  declarada no `Dockerfile`, com a revisão marcada para a primeira exposição fora de
  `localhost`.
- **Credencial administrativa no `.env`.** Com `DJANGO_SUPERUSER_EMAIL` e
  `DJANGO_SUPERUSER_PASSWORD` definidas, a senha do superusuário fica em texto claro num
  arquivo lido pelo docker compose e pelo processo. As duas saem comentadas do `.env.example`;
  quem as descomenta assume o custo.
- **Chave RSA única, sem conjunto de rotação.** Não há como rotacionar
  sem invalidar a verificação de todo token vivo, o que significa que a resposta a uma suspeita
  de vazamento da chave é disruptiva por construção (ADR 0004).
- **Log só em `stdout`, sem coleta externa.** Recriar o container apaga o histórico. Não existe
  trilha de auditoria de quem autenticou, de qual RP recebeu token nem de quando uma Application
  foi criada.
- **Dois pontos de resolução de dependências.** O `Dockerfile` roda
  `pip wheel -r requirements.txt`, que resolve as transitivas sem pin na data do build, enquanto
  a suíte roda contra o venv do host. `jwcrypto` — a biblioteca que assina o `id_token` — é uma
  dessas transitivas: um rebuild meses depois pode assinar com código que nenhum teste deste
  repositório jamais exercitou, sob `docker compose up --wait` verde.

## 5. Modelo de ameaças

Curto de propósito, e limitado ao que a premissa da seção 1 admite.

**Observador da rede local.** Hoje não alcança nada: o tráfego do IdP é loopback e não sai do
host. Publicar a porta sem endereço, abrir um túnel ou pôr um proxy sem TLS muda isso de uma
vez — o que passa a trafegar em claro é o formulário de senha, o cookie de sessão e os tokens.

**Alguém com acesso ao host.** Lê o `.env` e com ele obtém a `SECRET_KEY`, a chave privada RSA,
a senha do Postgres e, se definidas, a credencial do superusuário. Quem tem a chave privada é o
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

Só o primeiro item tem ordem declarada; a dos demais é decisão pendente, registrada na seção 7.

1. **Limitação de taxa** em `/o/authorize/`, `/o/token/` e `/admin/login/`.

Sem ordem declarada entre si:

- TLS de verdade à frente, com `BEHIND_TLS_PROXY=True` e `ALLOWED_HOSTS` mantendo `127.0.0.1`
  para a sonda do container — a armadilha e o procedimento estão em `docs/runbook.md`;
- `requirepass` no Redis;
- `USER` dedicado no `Dockerfile`;
- criação de superusuário fora do `.env`;
- conjunto de rotação de chave RSA;
- coleta externa de log e trilha de auditoria;
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

**7.2 — A ordem real da lista da seção 6, além do primeiro item.** Só a limitação de taxa tem
posição declarada. A ordem dos demais é decisão de quem for expor o IdP, e enquanto não for
tomada a lista acima é inventário, não plano.

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
| Portas em `127.0.0.1`, uma réplica, sem TLS próprio | `docker-compose.yml`, `Dockerfile` | ADR 0006 |

Os nomes de arquivo das ADRs estão em `docs/arquitetura.md`, na tabela de decisões.
