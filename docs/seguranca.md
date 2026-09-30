# Segurança — IdP

| Campo | Valor |
| --- | --- |
| Componente | provedor de identidade (IdP, Identity Provider) OpenID Connect (OIDC) |
| Público | quem decide expor este IdP a alguém |
| Diz | o que ele protege hoje, com a evidência no código; o que não protege; o que muda ao sair de `localhost` |
| Exposição | decidida pelas ADRs (Architecture Decision Records) 0025 e 0027; aplicada nos passos 1 a 7 do plano de implantação (`git show 8caf117:docs/plano-implantacao.md`), consolidados em `../pre-deploy.md` |
| Índice das ADRs | `docs/arquitetura.md`, "Índice das ADRs" |

---

## 1. A premissa de ambiente

Declarada no `README.md` e em `docs/arquitetura.md`. Tudo aqui descansa sobre ela.

| Item | Desenvolvimento e jornada de container | Produção |
| --- | --- | --- |
| Host | único, orquestrado por `docker-compose.yml` | o mesmo; a máquina do dono (ADR 0027) |
| Réplicas | uma — premissa da migração no entrypoint | uma |
| Postgres e Redis | publicados em `127.0.0.1` | nada publicado |
| Aplicação | não publica porta nenhuma | não publica porta nenhuma |
| Proxy | publicado em `127.0.0.1` | nada publicado: o override `docker-compose.prod.yml`, invocado com os dois `-f`, zera as portas e declara o conector, o `cloudflared` |
| Entrada | loopback | túnel nomeado da Cloudflare; não há porta de entrada no host nem no roteador |
| TLS (Transport Layer Security) do navegador | em `idp.localhost`, terminado no proxy, com certificado de uma autoridade certificadora (CA) local, que nenhum cliente de fora conhece | terminado na borda da Cloudflare, com o certificado Universal da zona do IdP |
| TLS interno | o Caddy mantém `tls internal`; o Gunicorn fala texto claro na rede interna, alcançado só pelo proxy | idem |
| Pessoas | conta criada no admin (ADR 0023), além de quem opera a máquina | idem |

Pré-condição que vive fora do repositório, e que nada nele verifica: quem controla a conta da
Cloudflare ou as credenciais do túnel controla a entrada.

**As escolhas descritas adiante são coerentes com esta premissa e só com ela.** Não são posturas
defensáveis em geral.

- **Quem alcança o IdP.** Até o passo 6 do plano de implantação, fora do ensaio do passo 4, só um
  processo na mesma máquina. A partir dele, a internet, pelo túnel.
- **Nesse dia**, o que a seção 6 ainda listar como aberto deixa de ser inventário e passa a ser
  dívida vencida.
- **Riscos aceitos da exposição**, nas Consequências da ADR 0027:
  - a borda da Cloudflare, que lê tudo o que passa por ela ("Um terceiro vê tudo");
  - produção e desenvolvimento sob o mesmo usuário ("Mesmo privilégio");
  - mantidos da 0026: o `refresh_token` sem expiração e os cookies com a política do default.
- **O mesmo vale** se a premissa for quebrada por outro caminho — outro túnel ou um proxy à
  frente.

---

## 2. O que o IdP protege hoje

| Controle | O que fecha | Evidência |
| --- | --- | --- |
| A senha não sai do IdP | credencial nas mãos da relying party (RP) | a RP recebe token, nunca credencial |
| Senha armazenada com Argon2 | — | `PASSWORD_HASHERS` em `config/settings.py`, Argon2 em primeiro |
| Política de senha onde a senha é escolhida | senha curta, comum, só numérica ou parecida com o e-mail da própria conta; sustenta a aritmética do teto de cinco tentativas. Limites na seção 4 | `AUTH_PASSWORD_VALIDATORS` em `config/settings.py` |
| PKCE (Proof Key for Code Exchange) obrigatório, restrito a S256 | interceptação de código (2.1) | `PKCE_REQUIRED` e `COMPLIANT_BCP_RFC9700_PKCE_METHOD` |
| `redirect_uri` por igualdade exata | extensão de um retorno registrado para destino de terceiro (2.2) | `tests/test_authorize_guards.py` |
| `redirect_uri` só em `https` atrás do proxy TLS | código de autorização em texto claro pelo canal de frente (2.3) | `ALLOWED_REDIRECT_URI_SCHEMES`, condicionada a `BEHIND_TLS_PROXY` |
| Gestão de `Application` e de token só no admin; sem registro dinâmico | registro de cliente por conta comum: as rotas de gestão do toolkit não são montadas, e `/admin/` exige `is_staff` | `config/urls.py`, ADR 0024 |
| `/accounts/logout/` apenas por POST | logout forjado naquela rota: um `GET` responde 405 e preserva a sessão; uma imagem ou um link para `/accounts/logout/` não desloga ninguém | `tests/test_logout_view.py` |
| Logout pela RP só com destino cadastrado, revogando só na `Application` que pede | saída forjada e revogação alheia (2.4) | `accounts/logout_rp.py`, ADRs 0029 e 0030 |
| Assinatura assimétrica em RS256 (RSA, Rivest–Shamir–Adleman, com SHA-256) | segredo compartilhado para verificar: nenhuma RP integrada pode forjar um token em nome do IdP | `docs/adr/0004-assinar-tokens-com-rs256-e-custodiar-a-chave-privada-no-ambiente.md` |
| Cookie sem estado de identidade | sessão irrevogável: o cookie carrega só o identificador; o estado vive no Postgres com cópia quente no Redis, e é revogável do lado do servidor — propriedade que um cookie assinado não teria | `SESSION_ENGINE = cached_db` em `config/settings.py` |
| CORS (Cross-Origin Resource Sharing) por origem exata, e só sob `/o/` | cabeçalho fora da superfície de protocolo: com a origem da SPA na allowlist, `/admin/` e `/accounts/login/` continuam sem `Access-Control-Allow-Origin` | `CORS_ALLOWED_ORIGINS` no `.env`, uma origem por ambiente (ADR 0022); `CORS_URLS_REGEX` em `config/settings.py` |
| Sem fluxo de recuperação de senha | fluxo de e-mail a sequestrar. É controle, não lacuna acidental: `config/urls.py` monta uma rota de autenticação por vez | `config/urls.py`, `tests/test_password_reset_urls.py` |
| Trilha de auditoria de autenticação e de concessão de token | quem autenticou, quando, de que origem e qual RP recebeu token (2.5) | `accounts/auditoria.py`, ADR 0013 |

### 2.1 PKCE com S256

- Sem ele, um código capturado na barra de endereços ou no log de um proxy é trocável por token
  por quem o capturou.
- `PKCE_REQUIRED` sozinho ainda aceitaria `plain`, em que o desafio é o próprio verificador em
  claro; a segunda chave é o que restringe a S256.

### 2.2 Igualdade exata de `redirect_uri`

- A comparação por prefixo é o erro clássico do protocolo.
- O teste da barra a mais existe para que afrouxá-la fique vermelho.

### 2.3 `https` como único esquema de retorno, com `BEHIND_TLS_PROXY=True`

- O admin recusa gravar `redirect_uri` em `http://`.
- Uma `Application` já gravada assim recebe 400 em `/o/authorize/` em vez do código.
- Com `BEHIND_TLS_PROXY=False`, na jornada de construção, `http` continua aceito: é o que deixa a
  SPA (Single-Page Application) de desenvolvimento voltar a `http://localhost:5173/callback`.

### 2.4 `/o/logout/`

- **Desloga por `GET`**, porque é o que o OpenID Connect RP-Initiated Logout exige.
- **Sem pergunta só quando** o `id_token_hint` vivo é da conta da sessão. O controle contra a
  saída forjada é a posse do `id_token`: sem ele, ou com o de outra conta, a view pede
  confirmação por POST com CSRF (Cross-Site Request Forgery).
- **Retorno** só a destino cadastrado na `Application`.
- **Revogação** só na `Application` que pede (ADR 0029).
- **Entrada forjada recebe 400**, e não o 500 que a view do toolkit daria (ADR 0030):
  - `client_id` inexistente ou com o caractere NUL;
  - hint com carga que não é JSON;
  - hint com `aud` de `Application` sem algoritmo;
  - hint com `aud` contendo NUL;
  - hint assinado por segredo de cliente HS256 com `jti` que não é UUID;
  - `post_logout_redirect_uri` que não se decompõe como URL.
- **A lista é fechada**: entrada nova que dê 500 é defeito (ADR 0029).

### 2.5 A trilha de auditoria

- **Onde:** arquivo durável que sobrevive à recriação do container
  (`docs/adr/0013-registrar-a-trilha-de-auditoria-dos-quatro-sinais-em-arquivo-duravel.md`).
- **Seis sinais:**
  - autenticação;
  - falha de autenticação;
  - logout;
  - concessão de token;
  - bloqueio por tentativas em excesso, acrescentado pela limitação de taxa (ADR 0016);
  - revogação de tokens no logout pela RP (ADR 0029).
- **O que nunca entra:** e-mail e valor de token. A pessoa aparece pelo `sub`, e o identificador
  de uma tentativa falha, por resumo SHA-256.
- **Não fecha a lacuna inteira:** o que continua sem registro está na seção 4.

---

## 3. Superfície exposta

### 3.1 Portas

| Serviço | Desenvolvimento (`docker-compose.yml`) | Produção (`docker-compose.prod.yml`) |
| --- | --- | --- |
| Proxy | `127.0.0.1`, portas 80 e 443 | não publicado (`!reset []`) |
| Postgres | `127.0.0.1:5432` | não publicado (`!reset []`) |
| Redis | `127.0.0.1:6379` | não publicado (`!reset []`) |
| Aplicação | não publica | não publica |

- **A aplicação não publica porta nenhuma.** O proxy é o único caminho até ela, e é isso, e não
  vigilância, que impede um cliente do host de desligar o redirecionamento para HTTPS escrevendo
  `X-Forwarded-Proto` (ADR 0017).
- **Em produção a entrada é o túnel.** O conector só disca para fora e alcança só o proxy, pela
  rede `borda` (ADR 0027). Caminho do que chega da internet, nessa ordem: borda da Cloudflare →
  conector → Caddy.

### 3.2 Rotas próprias

Em `config/urls.py`: `/`, `/health`, `/accounts/login/`, `/accounts/logout/`, `/admin/`, e tudo
sob `/o/`.

- **`/health`** é público e sem sessão, e revela o estado de banco e de cache — custo aceito nas
  ADRs 0009 e 0010 (`docs/adr/0009-isolar-a-view-de-health-da-sessao-e-do-usuario.md` e
  `docs/adr/0010-isentar-health-do-redirecionamento-para-https.md`).
- **`/admin/` está na mesma origem do IdP**, e portanto atrás do mesmo endereço, do mesmo
  transporte e do mesmo formulário de senha que o fluxo de autorização.

### 3.3 Rotas sob `/o/`

Entram três das cinco listas de rotas do `django-oauth-toolkit` — as de protocolo —, e ainda
assim mais do que este projeto usa (ADR 0024). Inventário lido de `oauth2_provider/urls.py` e de
`config/urls.py`:

| Rota | Situação |
| --- | --- |
| `/o/authorize/`, `/o/token/`, `/o/userinfo/`, as duas `.well-known` | em uso |
| `/o/logout/` | em uso: logout pela RP, atendido pela subclasse que sombreia a rota do toolkit (ADRs 0029 e 0030) |
| `/o/applications/...`, `/o/authorized_tokens/...` | 404, com ou sem sessão: `management_urlpatterns` não é montada |
| `/o/device-authorization/`, `/o/device/`, `/o/device-confirm/...`, `/o/device-grant-status/...` | device grant; sem uso pelo projeto, mas o POST de `/o/device-authorization/` grava no banco sem autenticação (seção 4) |
| `/o/revoke_token/` | revogação RFC 7009; não usada por este projeto |
| `/o/introspect/` | responde 403 — nenhum token pode carregar o scope exigido (ADR 0002) |
| `/o/.well-known/oauth-authorization-server`, `/o/.well-known/oauth-protected-resource` | metadados RFC 8414 e RFC 9728, montados pelo `include` |
| `/o/register/` | 404: `dcr_urlpatterns` não é montada, e `DCR_ENABLED` segue no default `False` |

- **Fechados pela ausência no URLConf:** as rotas de gestão e o registro dinâmico.
- **De pé sem uso:** device grant, revogação e introspecção. A unidade da montagem é a lista, e
  retirá-los exigiria copiar rotas da biblioteca.
- **Sem uso não quer dizer inerte:** `/o/device-authorization/` aceita POST anônimo e grava uma
  linha por requisição. Por isso tem teto de requisição, sem que o URLConf da ADR 0024 mude
  (seção 4).
- **Nenhuma conta, com ou sem `is_staff`, registra Application fora do admin**, que é o único
  lugar de gestão de clientes e de tokens.
- **O preço, no próprio admin:** o botão "Ver no site" da edição de uma Application aponta para a
  rota de detalhe que deixou de existir, e o clique responde 500. Dívida aceita, sem desligar
  `view_on_site` (ADR 0024).

---

## 4. Controles ausentes

Cada item é uma ausência conhecida, com o risco que ela deixa aberto.

| Ausência | Risco aberto | Referência |
| --- | --- | --- |
| Teto de requisição em `/admin/login/` | um laço que apenas carregue aquele formulário não encontra limite nenhum; ali só o axes barra (4.1) | `RATE_LIMIT_POR_CAMINHO`, ADR 0016 |
| Limpeza de `DeviceGrant` | linhas acumulam a partir de origens distintas, sem nada que as recolha (4.2) | dívida registrada; ADR 0024 |
| Política de senha fora da tela e do comando | senha fraca gravada ou mantida por outros caminhos (4.3) | `AUTH_PASSWORD_VALIDATORS` |
| Alerta de `BEHIND_TLS_PROXY` incoerente com o ambiente | a variável, configurada de forma incoerente, não emite sinal nenhum (4.4) | `git show 8caf117:docs/runbook.md`, §14 |
| Conferência da senha do Redis repetida no `.env` | divergência manual na jornada de construção (4.5) | `docs/receita.md`, "Criar o `.env`" |
| Conjunto de rotação da chave RSA | resposta a suspeita de vazamento da chave é disruptiva por construção (4.6) | ADR 0004 |
| Dois eventos na trilha, e retenção decidida | criação de Application e revogação fora do logout pela RP sem registro; arquivo sem poda (4.7) | ADRs 0013 e 0029 |
| Logout pela RP: `id_token` vivo é credencial de revogação | quem tem o `id_token` vivo de alguém revoga os tokens do dono (4.8) | ADR 0029 |
| Logout pela RP: hint sem registro | redireciona sem revogar (4.9) | ADR 0029 |
| Logout pela RP: refresh em curso | par novo pode nascer vivo depois da saída (4.10) | ADR 0029 |
| Logout pela RP: hint na query string | log de acesso com a URL completa passaria a gravar `id_token` (4.11) | — |
| Coleta externa de log | recriar o container apaga o histórico do log operacional (4.12) | — |
| Ponto único de resolução de dependências | a imagem pode assinar com código que nenhum teste exercitou (4.13) | `Dockerfile`, `requirements.txt` |

### 4.1 Teto de requisição em `/admin/login/`

A limitação de taxa existe desde a ADR 0016, que a pôs nas três portas de autenticação, e hoje
alcança também `/o/device-authorization/` e `/o/logout/`:

- **`django-axes`:** conta tentativa falha em `/accounts/login/` e em `/admin/login/`, por conta e
  por origem separadamente, bloqueando por quinze minutos contados da última tentativa;
- **`config/limites.py`:** teto de requisição por origem.

| Caminho | Teto por origem |
| --- | --- |
| `/accounts/login/` | 60 por minuto |
| `/o/token/`, `/o/authorize/`, `/o/logout/` | 120 por minuto |
| `/o/device-authorization/` | 30 por minuto |

Falta uma coisa: `/admin/login/` **não tem teto de requisição**. O dicionário
`RATE_LIMIT_POR_CAMINHO` não o nomeia.

### 4.2 `DeviceGrant` acumula sem limpeza

- `/o/device-authorization/` é a única superfície anônima que grava no banco: aceita POST sem
  sessão e sem CSRF.
- O oauthlib só confere que o `client_id` existe, e o `client_id` da SPA é público.
- Cada POST responde 200 e grava uma linha de `DeviceGrant`.
- Token nenhum sai dali: `/o/token/` recusa o grant pelo tipo da Application.
- O `django-oauth-toolkit` 3.4.1 não tem setting que desligue o device flow; a rota continua
  publicada porque vem na mesma lista do protocolo (ADR 0024).
- O teto de 30 requisições por minuto limita o custo por origem, e só isso: `clear_expired()` não
  apaga `DeviceGrant`.

### 4.3 A política de senha só alcança a senha escolhida por tela ou por comando

**Onde roda:** formulários do admin de adicionar conta e de alterar senha, `changepassword` e
`createsuperuser` interativo.

**Onde é silenciosa:**

- o login não valida, e conta cuja senha foi gravada antes da política continua entrando com ela,
  por fraca que seja;
- `create_user` e `set_password` não validam, e a suíte e o `shell` passam por baixo;
- `createsuperuser` interativo oferece ignorar a recusa ("Bypass password validation");
- `createsuperuser --noinput` não valida nada.

**As contas de teste de desenvolvimento** têm senha que a política recusaria, e ficam assim até o
passo 6 do plano de implantação (`git show 8caf117:docs/plano-implantacao.md`, consolidado em
`../pre-deploy.md`); nenhuma conta nova nasce com essa senha.
Numa conta dessas, o teto de cinco tentativas volta a supor um espaço de busca que não existe.

### 4.4 `BEHIND_TLS_PROXY` incoerente com o ambiente não emite alerta

- O transporte é TLS desde a ADR 0017.
- O endurecimento — cookie `Secure`, HSTS (HTTP Strict Transport Security), redirecionamento e
  `SECURE_PROXY_SSL_HEADER` — está ligado na jornada de container e em produção.
- A jornada de construção segue em texto claro, com `BEHIND_TLS_PROXY=False`.
- Configurada de forma incoerente com o ambiente, a variável não emite sinal de alerta. Sintoma e
  procedimento: `git show 8caf117:docs/runbook.md`, §14.

### 4.5 Sem mecanismo que confira a senha do Redis repetida no `.env`

- **Garantido:** o `requirepass` e a `REDIS_URL` do container saem da mesma variável, e o
  `${REDIS_PASSWORD:?}` do compose aborta o `up` com ela ausente e com ela vazia. Não há como este
  Redis subir sem autenticação.
- **Manual:** na jornada de construção, a mesma senha é escrita de novo na `REDIS_URL` do `.env`.
- **Efeito da divergência:** não abre acesso — o servidor recusa. Sintoma em `docs/receita.md`,
  "Criar o `.env`", e em `git show 8caf117:docs/runbook.md`, §20.

### 4.6 Chave RSA única, sem conjunto de rotação

- Não há como rotacionar sem invalidar a verificação de todo token vivo (ADR 0004).
- O toolkit oferece o conjunto por `OIDC_RSA_PRIVATE_KEYS_INACTIVE`.
- Ligá-lo põe mais de uma chave no JWKS (JSON Web Key Set), que é contrato com a SPA: é tarefa
  própria, com ADR nos dois projetos, ainda não decidida.

### 4.7 A trilha de auditoria não cobre dois eventos, e não tem retenção decidida

| Evento sem registro | Por quê |
| --- | --- |
| Criação de Application | ausência de sinal; exigiria um `post_save` no modelo devolvido por `get_application_model()` |
| Revogação de token fora do logout pela RP | ausência de sinal, e nem o `post_save` bastaria: `/o/revoke_token/`, o admin e o `cleartokens` apagam linhas sem emitir nada |

- Só a revogação de `/o/logout/` tem sinal, e é deste projeto (ADR 0029).
- Retenção e poda do arquivo não estão decididas: ele guarda dado pessoal, cresce
  indefinidamente e nada o monitora (ADR 0013).

### 4.8 No logout pela RP, o `id_token` vivo é credencial de revogação

- Sem sessão no navegador, a view não pergunta.
- Quem tem o `id_token` vivo de alguém revoga os tokens do dono naquela `Application`.
- A revogação alcança a conta **naquela `Application`, em todos os dispositivos**, e não só a
  sessão que pediu.
- A sessão de SSO (_single sign-on_) do IdP termina inteira, e as outras RPs perdem a volta sem
  senha.
- O teto de 120 por minuto limita custo, não isso.

### 4.9 O hint sem registro redireciona sem revogar

- Um `id_token` autêntico cuja linha já sumiu, por exemplo numa segunda saída, é tratado como
  ausente.
- Sem sessão, o pedido vai ao destino cadastrado e nada é revogado.
- Os tokens que a conta tenha naquela `Application`, por um login posterior, sobrevivem a essa
  saída.

### 4.10 Um refresh em curso durante a saída pode sobreviver a ela

- O toolkit valida o `refresh_token` fora de trava e, ao gravar o par novo, não reconfere a
  revogação.
- Validação antes da saída e gravação depois: o par novo nasce vivo, e nada acusa.
- Fechar a janela exige mexer em `/o/token/`, fora da ADR 0029.

### 4.11 O `id_token_hint` viaja na query string de `/o/logout/`

- Nenhum log deste projeto grava a URL completa hoje.
- Ligar log de acesso com ela passa a gravar `id_token`.
- Não medidos: o log de erro do Caddy, o `cloudflared` e a borda da Cloudflare.

### 4.12 Log operacional só em `stdout`, sem coleta externa

- Recriar o container apaga o histórico do log operacional.
- A trilha de auditoria não está nesse caso — vive em volume nomeado —, mas também não tem coleta
  externa nenhuma.

### 4.13 Dois pontos de resolução de dependências

- O `Dockerfile` roda `pip wheel -r requirements.txt`, que resolve as transitivas sem pin na data
  do build.
- A suíte roda contra o venv do host.
- `jwcrypto` — a biblioteca que assina o `id_token` — é uma dessas transitivas.
- Consequência: um rebuild meses depois pode assinar com código que nenhum teste deste repositório
  jamais exercitou, sob `docker compose up --wait` verde.

---

## 5. Modelo de ameaças

Curto de propósito, e limitado ao que a premissa da seção 1 admite.

| Ator | Alcança | Não alcança | Situação |
| --- | --- | --- | --- |
| Observador da rede local | hoje, nada | — | 5.1 |
| Alguém com acesso ao host | o `.env` e, com ele, a identidade do IdP | a credencial do superusuário (ADR 0019) | sem mitigação nesta fase (5.2) |
| A borda da Cloudflare | tudo o que passa por ela, em texto claro | — | risco aceito, ADR 0027, "Um terceiro vê tudo" (5.3) |
| Um processo do usuário de desenvolvimento | o `.env`, as credenciais do túnel e os volumes de produção | — | risco aceito, ADR 0027, "Mesmo privilégio" (5.4) |
| RP registrada e maliciosa | o `id_token` de quem consentiu com ela; reter o `refresh_token` | forjar token; verificar o de outra RP | revogação manual (5.5) |
| Pessoa usuária hostil, com conta | a própria conta | dados de outra conta; registrar Application | fechado (5.6) |

### 5.1 Observador da rede local

- Hoje não alcança nada: o tráfego do IdP é loopback e não sai do host.
- Publicar o proxy sem endereço ou abrir um túnel muda isso. Com a terminação TLS de pé, ele
  passaria a ver tráfego cifrado, desde que o certificado seja aceito pelo cliente.
- Continua em claro o trecho interno, entre o proxy e o Gunicorn, dentro da rede do compose.

### 5.2 Alguém com acesso ao host

- Lê o `.env` e com ele obtém a `SECRET_KEY`, a chave privada RSA e as senhas do Postgres e do
  Redis.
- No clone de produção, lê também as credenciais do túnel, com que recebe o tráfego do domínio do
  IdP.
- A credencial do superusuário saiu desse conjunto com a ADR 0019: é digitada num prompt e não
  fica em arquivo nenhum.
- Quem tem a chave privada é o IdP, para todos os efeitos: pode emitir identidade em nome dele
  para qualquer RP integrada.
- Não há controle que mitigue isso nesta fase; o bind em loopback apenas limita quem alcança o
  serviço.

### 5.3 A borda da Cloudflare

- Em produção, termina o TLS do navegador e lê em texto claro senhas, `code`, os tokens e o
  cookie `sessionid`, inclusive o do superusuário.
- Poderia servir qualquer conteúdo sob o domínio.
- Quem capture esse cookie entra no `/admin/` e cria uma `Application` com `redirect_uri` própria
  e `skip_authorization=True`, que persiste depois da captura e não aparece na trilha.
- Risco aceito pelo dono, com gatilho de revisão.

### 5.4 Um processo do usuário de desenvolvimento

- Produção divide a máquina, o daemon do Docker e o usuário com o desenvolvimento.
- Qualquer processo desse usuário — pacote de `npm` ou `pip` comprometido, extensão de editor,
  agente com shell — lê o `.env` e as credenciais do túnel do clone de produção e, pelo grupo
  `docker`, alcança os volumes de produção.
- Risco aceito pelo dono, com gatilho de revisão.

### 5.5 RP registrada e maliciosa

- Recebe `id_token` apenas das pessoas que consentiram com ela.
- Não pode forjar token nem verificar o de outra RP: a assinatura é assimétrica e o `aud` a
  identifica.
- Consegue reter indefinidamente o `refresh_token` que recebeu, que não expira por tempo e que a
  desativação da conta não invalida.
- Procedimento de revogação: `git show 8caf117:docs/runbook.md`, "Revogar o acesso de uma
  pessoa".

### 5.6 Pessoa usuária hostil, com conta neste IdP

- Não alcança dados de outra conta pelo IdP: as claims saem sempre da conta autenticada, e
  `/admin/` exige `is_staff`.
- Não registra Application: as rotas de gestão do toolkit não são montadas, e o registro é só do
  admin (seção 3).

---

## 6. A fronteira: o que muda antes de expor fora de `localhost`

### 6.1 O que já saiu da lista

| Item | Fechado por |
| --- | --- |
| Limitação de taxa — era o primeiro, e o único com posição fixada | seção 4, ADR 0016 |
| Proxy TLS com `BEHIND_TLS_PROXY=True` e `ALLOWED_HOSTS` composto pelo compose | ADR 0017 |
| `requirepass` no Redis | sem ADR, no bloco das ADRs 0017 a 0019 |
| `USER` dedicado com a posse de `/var/log/idp` | sem ADR, no bloco das ADRs 0017 a 0019 |
| Criação de superusuário fora do `.env` | ADR 0019 |
| Restrição de quem pode registrar Application | ADR 0024 |
| Confirmação da forma do issuer que a ADR 0007 pedia | ADR 0025 |
| Certificado emitido por uma autoridade que o cliente já conheça — em produção, o Universal da borda da Cloudflare | ADR 0027 |
| Publicação de produção — deixou de existir: o override zera as portas, e a entrada é o túnel | ADR 0027 |

### 6.2 O que resta

Nenhum item tem ordem declarada; a ordem é decisão pendente, na seção 7.

- **`TRUSTED_PROXY_COUNT` contra a topologia real**, e as marcas de origem da trilha junto:
  - sob o túnel, `peer` não prova nada: o colapso no conector também sai `peer` (ADR 0027, emenda
    à 0020);
  - sinal de acerto: dois clientes de redes sabidamente distintas aparecem na trilha com `ip`
    distintos entre si;
  - sinal de colapso: o mesmo `ip` em todas as linhas, com `ip_src` `forwarded` e `ip_edge`
    `peer` (`git show 8caf117:docs/runbook.md`, §22);
  - na jornada de container, enquanto toda linha disser `gateway`, o `docker-proxy` continua no
    caminho e o `ip` não identifica cliente nenhum;
  - `remote_addr_fallback` NÃO é sinal deste dia e não aparecerá: com o Caddy à frente o
    cabeçalho sempre chega, e aquele rótulo denuncia proxy mal configurado, em qualquer dia
    (ADRs 0018 e 0020).
- **Conjunto de rotação de chave RSA** — ver 4.6.
- **Coleta externa de log.**
- **Pin das dependências transitivas**, unificando os dois pontos de resolução.
- **Agendamento de `cleartokens` e `clearsessions`**, hoje inexistente.
- **Posição do `CorsMiddleware`**, a conferir ao ligar a primeira aplicação de página única: a
  configuração incorreta é indetectável enquanto a allowlist estiver vazia (`docs/arquitetura.md`,
  §II.6).
- **`email_verified` e revogação efetiva**, que são contrato com a RP e estão em
  `docs/integracao-rp.md`.

---

## 7. Decisões abertas

| Decisão | Estado |
| --- | --- |
| 7.1 — O `include` do toolkit publica rotas que o projeto não usa | fechada pela ADR 0024; registrada pelo desfecho |
| 7.2 — A ordem real da lista da seção 6 | pendente; este documento não a resolve |

**7.1 — Fechada.**

- **A pergunta:** manter o `include` inteiro, como mandava a ADR 0002 ao proibir reescrever e
  envelopar endpoint de protocolo, ou restringir o URLConf às rotas em uso.
- **O desfecho:** a ADR 0024 restringiu pela lista, e não pela rota. `management_urlpatterns` e
  `dcr_urlpatterns` saíram.
- **O preço:** o que continua publicado sem uso — device grant, revogação e introspecção — é o
  preço de não copiar rota da biblioteca. O resultado é a tabela da seção 3.3.
- **A parte do preço que grava no banco** é o device grant; o teto de requisição e a dívida que
  ele não cobre estão na seção 4.

**7.2 — Pendente.**

- O único item com posição declarada era a limitação de taxa, e ela saiu da lista por já estar
  implantada.
- Nenhum dos que restam tem ordem; ela é decisão de quem for expor o IdP.
- Enquanto não for tomada, a lista da seção 6.2 é inventário, não plano.

---

## 8. Mapa: controle, arquivo, decisão

| Controle | Onde vive | Decisão |
| --- | --- | --- |
| PKCE obrigatório | `config/settings.py`, `PKCE_REQUIRED` | ADR 0002 |
| Restrição a `S256` | `config/settings.py`, `COMPLIANT_BCP_RFC9700_PKCE_METHOD` | sem ADR |
| Assinatura RS256 e custódia da chave no ambiente | `config/settings.py`, `scripts/gen_env_secrets.sh` | ADR 0004; tamanho e gerador, ADR 0028 |
| Issuer em `{BASE_URL}/o`, rotas do toolkit sob prefixo | `config/urls.py`, `config/settings.py` | ADR 0007; quais rotas, ADR 0024 |
| Só as listas de protocolo do toolkit sob `/o/`; gestão de `Application` só no admin | `config/urls.py` | ADR 0024, emenda à 0002 |
| `redirect_uri` só em `https` com `BEHIND_TLS_PROXY` | `config/settings.py`, `ALLOWED_REDIRECT_URI_SCHEMES` | sem ADR; a condição é a da ADR 0006 |
| Política de senha na criação e na troca | `config/settings.py`, `AUTH_PASSWORD_VALIDATORS` | sem ADR |
| CORS por origem exata, só sob `/o/` | `config/settings.py`, `CORS_ALLOWED_ORIGINS` e `CORS_URLS_REGEX` | ADR 0022, a allowlist; sem ADR, o prefixo |
| Claims emitidas, sem `email_verified` | `accounts/oauth_validators.py` | sem ADR |
| Logout iniciado pela RP, ligado, com revogação restrita à `Application` e destino cadastrado | `config/settings.py`, as cinco chaves `OIDC_RP_INITIATED_LOGOUT_*`; `accounts/logout_rp.py`; `config/urls.py` | ADR 0029; o mecanismo, ADR 0030 |
| Sessão revogável no servidor, cookie sem estado | `config/settings.py`, `SESSION_ENGINE` | ADR 0005 |
| Endurecimento de transporte por `BEHIND_TLS_PROXY` | `config/settings.py` | ADR 0006 |
| Isenção de `/health` no redirecionamento para HTTPS | `config/settings.py`, `SECURE_REDIRECT_EXEMPT` | ADR 0010 |
| `/health` sem sessão e sem usuário | `config/views.py` | ADR 0009 |
| Trilha de auditoria dos seis sinais, sem e-mail e sem token | `accounts/auditoria.py`, `config/settings.py`, `LOGGING` | ADR 0013, ampliada pela 0016 e pela 0029 |
| Origem do cliente resolvida num ponto único | `config/origem.py` | ADR 0015 |
| Bloqueio por tentativa falha em `/accounts/login/` e `/admin/login/` | `config/settings.py`, bloco `AXES_*` | ADR 0016 |
| Teto de requisição por origem em `/accounts/login/`, `/o/token/` e `/o/authorize/` | `config/settings.py`, `RATE_LIMIT_POR_CAMINHO`; o mecanismo, `config/limites.py` | ADR 0016 |
| Teto de requisição por origem em `/o/logout/` | `config/settings.py`, `RATE_LIMIT_POR_CAMINHO`; o mecanismo, `config/limites.py` | ADR 0029 |
| Teto de requisição por origem em `/o/device-authorization/` | `config/settings.py`, `RATE_LIMIT_POR_CAMINHO`; o mecanismo, `config/limites.py` | sem ADR; a rota, ADR 0024 |
| Terminação TLS no proxy, e só ele publicado em `127.0.0.1` | `docker-compose.yml`, `docker/Caddyfile` | ADR 0017, emenda à 0006; emendada pela 0027 |
| Nenhuma porta em produção; entrada pelo túnel | `docker-compose.prod.yml` | ADR 0027 |
| `CF-Connecting-IP` confiado só do /32 do conector | `docker/Caddyfile` | ADR 0027 |
| `DEBUG` fixado em `False` em produção | `docker-compose.prod.yml` | sem ADR |
| Uma réplica, migração no boot, endurecimento por variável | `docker-compose.yml`, `Dockerfile` | ADR 0006 |
| Procedência do endereço em cada linha da trilha | `config/origem.py`, `accounts/auditoria.py` | ADR 0018 |
| Alcance do endereço em cada linha da trilha | `config/origem.py`, `accounts/auditoria.py` | ADR 0020, emenda à 0018 |
| Redis sob `requirepass`, com senha de origem única | `docker-compose.yml` | sem ADR |
| Processo sem `root` no container, UID e GID 10001 | `Dockerfile` | sem ADR |
| Superusuário criado por comando explícito, fora do `.env` | `docker/entrypoint.sh`, `.env.example` | ADR 0019 |

Os nomes de arquivo das ADRs estão em `docs/arquitetura.md`, no "Índice das ADRs".
