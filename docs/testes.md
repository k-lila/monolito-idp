# Testes — IdP

| Campo | Valor |
| --- | --- |
| Papel | dono da suíte |
| Diz | os níveis de teste e o critério que os separa; o que cada arquivo garante; a infraestrutura compartilhada; a convenção de rastreabilidade; o inventário do que não está coberto |
| Não diz | o modelo mental do sistema, em `docs/arquitetura.md`; a receita de subir o stack, em `docs/receita.md` |

---

## 1. O que a suíte é

| Peça | O que é |
| --- | --- |
| `tests/test_*.py` | os testes, num pacote só, na raiz do repositório |
| `tests/oauth_helpers.py` | infraestrutura que os testes de fluxo reusam (seção 6) |
| `tests/logout_helpers.py` | infraestrutura que os do logout pela relying party (RP) reusam (seção 7) |
| `tests/api_conta_helpers.py`, `tests/paginas_helpers.py`, `tests/envio_helpers.py` | infraestrutura que os da interface de programação (API, de _Application Programming Interface_) de conta, das páginas de conta e do envio de e-mail reusam (seção 7.1) |
| `tests/runner.py` | o executor: um `DiscoverRunner` do Django subclassado, sobre `unittest` da biblioteca padrão (seção 5) |

**Por que o pacote é da raiz, e não de dentro de `accounts/`:** a suíte quase toda exercita
superfícies que `accounts` não possui — rotas declaradas em `config/urls.py`, views do toolkit e
views prontas do `django.contrib.auth`. Importar de `accounts` é a exceção. Quais módulos o fazem
responde-se por `grep -l '^from accounts' tests/*.py`; a lista cresce a cada função do app que
valha uma prova isolada, e por isso não está escrita aqui.

**O que não há:**

| Ausência | Evidência |
| --- | --- |
| pytest | nenhum `conftest.py`, nenhuma dependência de teste em `requirements.txt`, que lista apenas as dez de execução |
| Ferramenta de cobertura | nenhum `coverage`, nenhum relatório gerado |
| Integração contínua versionada | `git ls-files` não devolve `.github/`, nem `.gitlab-ci.yml`, nem `tox.ini`. A suíte roda quando alguém a roda |
| Nível fim-a-fim | nenhuma requisição HTTP de verdade, nenhum servidor vivo, nenhum navegador; nem `LiveServerTestCase` nem cliente HTTP externo. O cliente de teste do Django chama a aplicação em memória |

---

## 2. Como rodar

```bash
.venv/bin/python manage.py test                # jornada de construção
docker compose exec app python manage.py test  # jornada de clonar-e-rodar
```

| Invocação | Efeito |
| --- | --- |
| `manage.py test` | descobre o pacote inteiro |
| `manage.py test tests` | forma explícita; roda os mesmos casos |
| `manage.py test accounts` | `Found 0 test(s)` — nenhum teste mora lá. Enquanto a suíte esteve dividida entre `accounts/` e `config/`, esse mesmo comando rodava dez dos doze arquivos e calava sobre os outros dois |

**Pré-requisito:** Postgres e Redis de pé — nas duas jornadas, `docker compose up` tendo subido,
no mínimo, os serviços `postgres` e `redis`.

- **Postgres:** o executor cria e destrói o banco de teste sozinho, mas precisa de um servidor a
  que se conectar.
- **Redis:** tocado por toda requisição com sessão, porque `SESSION_ENGINE` é `cached_db`, e
  consultado diretamente pela view de `/health`.

**Não exige `collectstatic` prévio.** `tests/test_login_view.py` confere o CSS (Cascading Style
Sheets) por dois caminhos, e nenhum depende do diretório coletado:

- `finders.find("css/idp.css")`, que procura no diretório-fonte;
- `static("css/idp.css")`, que resolve a URL (Uniform Resource Locator) em tempo de execução.

Preservar isso foi parte do que se decidiu em
`docs/adr/0008-servir-estaticos-com-whitenoise-sem-manifesto-de-hash.md`.

---

## 3. Os níveis, e o critério que os separa

| Nível | Classe base | O que atravessa |
| --- | --- | --- |
| Sem banco | `SimpleTestCase` | nada além da função sob prova |
| Com banco e cliente de teste | `TestCase` | o URLConf, o middleware, a view, o template e o banco de teste |
| Com banco, fora da transação do caso | `TransactionTestCase` | o mesmo, mais o commit de verdade e o DDL (Data Definition Language) do Postgres (seção 3.3) |

**O critério:** o nível sem banco vale quando a decisão cabe inteira numa função isolável; nos
demais, o que pode quebrar é a costura, e só a resposta HTTP a revela.

- **A costura aqui é quase sempre entre configuração e biblioteca de terceiro:**
  `PKCE_REQUIRED`, que exige o Proof Key for Code Exchange (PKCE); `OIDC_ISS_ENDPOINT`, que fixa
  o issuer; `SECURE_REDIRECT_EXEMPT`, que isenta `/health`; a allowlist de `redirect_uri`.
- **Um teste isolado sobre qualquer uma delas** só afirmaria o valor de uma chave de
  `config/settings.py`, que não está em dúvida.
- **Uma exceção nomeada:** `TrilhaIsoladaDuranteASuiteTests` (tabela abaixo).

### 3.1 Sem banco

O que está sob prova não precisa de linha no banco: ou a função é chamada diretamente, com um
portador falso no lugar do que ela leria do mundo, ou é pura, ou o estado que ela confere já foi
montado antes de o primeiro caso rodar.

| Onde | Por que dispensa banco |
| --- | --- |
| `tests/test_oauth_validators.py`, inteiro | `get_oidc_claims` lê só `.user` e `.scopes`, então um objeto de duas linhas basta, e o `User` é construído sem nunca ser salvo |
| `tests/test_origem.py`, inteiro | ver 3.1.1 |
| `tests/test_gen_env_secrets.py`, inteiro | ver 3.1.2 |
| `tests/test_endurecimento_transporte.py`, inteiro | leitura de settings, sem cliente HTTP. Quando a pergunta é o valor de produção de uma chave que o executor neutraliza, lê o que ele guardou antes de neutralizar, e não o que `settings` mostra durante a suíte |
| `tests/test_borda_do_tunel.py`, inteiro | lê como texto, a partir de `settings.BASE_DIR`, o `docker/Caddyfile` e o `docker-compose.prod.yml`, compara o endereço do conector nos dois e o situa na rede `borda`, dentro da `subnet` e fora do `ip_range`; não há requisição nenhuma a montar |
| `tests/test_spa_url.py`, inteiro | o que se prova é a carga de `config/settings.py`, executada por `runpy` com o ambiente montado pelo caso: a exceção que ela levanta ou o valor que ela aceita. A carga não abre conexão, e não há requisição a montar |
| `tests/test_sem_recurso_de_terceiro.py`, inteiro | lê como texto, a partir de `settings.BASE_DIR`, o `static/css/idp.css` e cada `templates/**/*.html`, e procura a forma de um recurso buscado fora do IdP; não há template a renderizar nem requisição a montar |
| `HealthViewDatabaseDownUnitTests`, em `tests/test_health.py` | `RequestFactory` mais chamada direta a `health`, com `connection` substituída por um duplo que levanta |
| `FormatadorJSONTests`, em `tests/test_observabilidade.py` | um registro emitido por um logger próprio do módulo, com o par filtro e formatador de produção anexado a um handler efêmero, de modo que a linha capturada é a que sairia de verdade |
| `ResumoDoIdentificadorTests`, em `tests/test_auditoria.py` | não há portador nenhum a falsificar: `_resumo_do_identificador` é função pura, entra uma string e sai um hexadecimal |
| `RotaDoLogoutTests`, em `tests/test_logout_rp.py` | confere a resolução de `/o/logout/` contra o URLConf, sem requisição |
| `ConstantesDeProducaoDoLogoutTests`, em `tests/test_logout_rp.py` | lê as cinco chaves `OIDC_RP_INITIATED_LOGOUT_*` do dicionário que o executor guardou antes de neutralizar `OAUTH2_PROVIDER` |
| `tests/test_api_conta_settings.py` e `tests/test_email_settings.py`, inteiros | a carga de `config/settings.py` por `runpy`, como em `tests/test_spa_url.py`, com `read_env` neutralizado para o `.env` do clone não repor a variável que o caso tirou |
| `tests/test_envio_settings.py`, inteiro | lê os valores que o executor guardou antes de neutralizar o teto por destinatário e o envio em thread |
| `tests/test_confirmacao.py`, inteiro | o token sai de `signing.dumps` sobre um objeto com `sub` e `email`, sem conta gravada |
| `tests/test_emails.py`, inteiro | as funções de aviso leem só o endereço e a hora, com `timezone.now` fixado |
| `tests/test_em_portugues.py`, inteiro | uma view de teste herda do mixin e de `TemplateView`, sem URLConf e sem banco |
| `TrilhaIsoladaDuranteASuiteTests`, em `tests/test_auditoria.py` | **a exceção ao critério, e deliberada:** confere o handler `audit` **real**, já redirecionado pelo executor, e a escrita que faz é em arquivo de verdade. Nada disso pede banco, e falsificar o handler destruiria justamente o que se quer provar |

#### 3.1.1 `tests/test_origem.py`

- `origem_da_requisicao` e `origem_e_procedencia` decidem sobre duas settings e o `META` de uma
  requisição; `RequestFactory` mais `override_settings` dão as duas coisas.
- `origem_completa` lê ainda a tabela de rotas. O que substitui o mundo é um arquivo temporário
  para o qual o teste aponta `config.origem._TABELA_DE_ROTAS`, em vez de `/proc/net/route`.
- Todo caso que assere a procedência fixa `BEHIND_TLS_PROXY` por `override_settings`, e não herda
  o da jornada. Dois casos de `OrigemCompletaTests` não o faziam: passavam na jornada de
  construção e falhavam na de container, onde a mesma requisição cai em `remote_addr_fallback`
  (T-13 da TASK-019).

#### 3.1.2 `tests/test_gen_env_secrets.py`

- O que se prova é a saída do script, e não há objeto Python a isolar.
- Invoca `bash scripts/gen_env_secrets.sh` por subprocess, com o ambiente limpo de `POSTGRES_*` e
  `REDIS_PORT`, e lê o `stdout`.
- Exige o `openssl` no PATH e não tem pulo condicional: sem ele o teste falha, como o script
  falharia.
- Custa três gerações de chave de 3072 bits.
- As mensagens de asserção nunca trazem o valor gerado.

### 3.2 Com banco e cliente de teste

Todo o resto: os arquivos ausentes da tabela 3.1, inteiros, e as demais classes dos que aparecem
nela. Só `tests/test_oauth_validators.py` não deixa nada para cá.

### 3.3 Com banco, fora da transação do caso

O `TestCase` envolve cada caso numa transação que nunca faz commit. Três provas precisam do
commit, ou de não estar dentro de transação nenhuma, e usam `TransactionTestCase`:

| Onde | Por quê |
| --- | --- |
| `tests/test_conta_migracao.py`, inteiro | a migração faz DDL. Cada caso cria um schema Postgres próprio, aponta o `search_path` para ele e migra do zero ali, de `accounts.0001` até a folha do grafo; o `public`, onde vive o banco de teste, não é tocado, e o `finally` apaga o schema. A volta pelo grafo só é tentada para provar que a 0004 a recusa |
| `DepoisDoCommitRealTests`, em `tests/test_envio.py` | o envio parte de `transaction.on_commit`, e só o commit do banco o dispara sem `captureOnCommitCallbacks` |
| `tests/test_pagina_sinais_e_transacao.py`, inteiro | prova que cada sinal da trilha sai com `connection.in_atomic_block` falso; dentro do `TestCase` ele seria sempre verdadeiro |

---

## 4. O que cada arquivo garante

| Assunto | Arquivo | Nível |
| --- | --- | --- |
| Claims emitidas pelo validador, por combinação de scope: o `sub` UUID (_Universally Unique Identifier_), e não a chave primária; `name`, `nickname` e `updated_at` com `profile`; `email` e `email_verified` com `email` | `tests/test_oauth_validators.py` | sem banco |
| Os dois documentos de descoberta, o do OpenID Connect (OIDC) e o da Request for Comments (RFC) 8414: `issuer`, o valor exato de cada endpoint, `end_session_endpoint` inclusive, só no do OIDC, o que não deve aparecer; `create` em `prompt_values_supported`; e o `alg` da chave publicada em `/o/.well-known/jwks.json` | `tests/test_discovery.py` | com banco |
| JWKS (JSON Web Key Set) publicado: uma chave RSA (Rivest–Shamir–Adleman) com `kid` | `tests/test_jwks.py` | com banco |
| Authorization Code + PKCE fechado de ponta a ponta | `tests/test_authorization_code_flow.py` | com banco |
| Guardas de `/o/authorize/`: PKCE obrigatório, `redirect_uri`, método `plain` | `tests/test_authorize_guards.py` | com banco |
| Tela de consentimento e o ramo de recusa | `tests/test_authorize_consent.py` | com banco |
| Anônimo interrompido em `/o/authorize/` e resgatado pelo login | `tests/test_login_authorize_bridge.py` | com banco |
| Tela de login: renderização, sucesso e falha de credencial | `tests/test_login_view.py` | com banco |
| Logout local por POST, a recusa do GET, e o logout local que encerra a sessão sem revogar token nem gravar `tokens_revogados` (`LogoutLocalNaoRevogaTokensTests`) | `tests/test_logout_view.py` | com banco |
| As rotas de recuperação de senha, uma a uma, com template próprio e em português; `password_change_done` e o resto do que `django.contrib.auth.urls` publicaria, ausentes | `tests/test_password_reset_urls.py` | com banco |
| Comentário de template vazando para o corpo da página: login, home, consentimento, e a confirmação e o erro do logout pela RP | `tests/test_template_comment_leak.py` | com banco |
| Prontidão de banco e de cache, e a isenção de HTTPS | `tests/test_health.py` | misto |
| Esquema da linha de log, correlação por `request_id` e a linha de acesso: campos, o `/health` fora dela, e a de `/o/logout/` com `route` igual a `logout_rp` e sem a query | `tests/test_observabilidade.py` | misto |
| Trilha de auditoria: os cinco eventos — `user_logged_in`, `user_login_failed`, `user_logged_out` e `app_authorized`, da ADR 0013, e `user_locked_out`, da ADR 0016 —, com o `sub` UUID e o resumo do identificador em minúsculas; a tripla `ip`, `ip_src` e `ip_edge` presente em cada um deles, a ausência de segredo, o `id_token_hint` válido e o forjado do logout pela RP inclusive, e o isolamento sob a suíte. O sexto evento, `tokens_revogados`, é provado em `tests/test_logout_rp.py`, e os dez de conta, nos arquivos das páginas e da API | `tests/test_auditoria.py` | misto |
| Endereço de origem do cliente: a tabela inteira de `origem_da_requisicao`, o par de `origem_e_procedencia` — endereço e rótulo de procedência — nos quatro desfechos, com e sem proxy declarado, e a tripla de `origem_completa`, com `ip_edge` nos três valores contra uma tabela de rotas de fixture, mais `_alcance_do_endereco` | `tests/test_origem.py` | sem banco |
| Limite do login: o bloqueio do `django-axes` por conta, por origem e o prazo; o teto de requisição da mesma porta; o que o 429 não diz e o que distingue os dois 429; e a linha `user_locked_out` na trilha, com a origem igual à que o axes contou | `tests/test_limite_login.py` | com banco |
| Limite de `/o/token/`, `/o/authorize/`, `/o/device-authorization/`, `/o/logout/` e da API de conta: o teto, o corpo do 429, a linha de log; em `/o/device-authorization/`, uma linha de `DeviceGrant` por POST abaixo do teto e nenhuma a mais no POST recusado com 429 (`LimiteDeDeviceAuthorizationTests`); em `/o/logout/`, o 429 acima do teto (`LimiteDoLogoutPelaRPTests`); em `/api/conta/`, o 429 com `Retry-After` e com os cabeçalhos de CORS (`LimiteDaApiDeContaTests`); e o dicionário de produção alcançando nove caminhos, `/accounts/login/` e os quatro da API inclusive | `tests/test_limite_oauth.py` | com banco |
| Falha aberta do limitador: com o Redis inalcançável, a requisição segue e uma linha `WARNING` registra o silêncio | `tests/test_falha_aberta_limites.py` | com banco |
| As cinco chaves do endurecimento de transporte e `ALLOWED_REDIRECT_URI_SCHEMES` seguindo `BEHIND_TLS_PROXY` — as duas que o executor neutraliza, lidas do valor que ele guardou —; e o cache do toolkit alcançado pela neutralização | `tests/test_endurecimento_transporte.py` | sem banco |
| Admin de `Application`: esquema de `redirect_uris` recusado e aceito sob `["https"]` e sob o valor neutro da suíte, com o efeito em `/o/authorize/`; as quatro views de gestão; e o 500 do "View on site", dívida aceita pela ADR 0024 | `tests/test_admin_oauth2_application.py` | com banco |
| As sete rotas de gestão do `django-oauth-toolkit` (DOT) e a de registro dinâmico de cliente respondendo 404 sob `/o/`, para as quatro identidades | `tests/test_gestao_dot_ausente.py` | com banco |
| Política de senha nas quatro superfícies de quem opera: adicionar conta e trocar senha no admin, `changepassword` e `createsuperuser` interativo. A das páginas de conta está nos arquivos delas | `tests/test_politica_de_senha.py` | com banco |
| Login com senha legada fraca: entra, e a senha continua a mesma | `tests/test_login_senha_legada.py` | com banco |
| Cross-Origin Resource Sharing (CORS) sob `/o/`: ausente em `/accounts/login/` e em `/admin/`, com a origem exata dentro do prefixo, preflight e 401 incluídos | `tests/test_cors.py` | com banco |
| Endereço do conector do túnel: o `trusted_proxies static` do `docker/Caddyfile` e o `ipv4_address` do `docker-compose.prod.yml`, uma ocorrência de cada e iguais, sem fixar o valor; e o mesmo endereço dentro da `subnet` da rede `borda` e fora do seu `ip_range`, com o `ip_range` contido na `subnet`, para que o `proxy` nunca o tome por atribuição dinâmica | `tests/test_borda_do_tunel.py` | sem banco |
| Saída do gerador de segredos `scripts/gen_env_secrets.sh`, por subprocess (TASK-025/T-01): seis linhas na ordem, tamanho hexadecimal de cada senha, URLs derivadas das senhas da própria saída e do ambiente, `--so-chave-rsa` com uma linha só e sem senha nem URL (AC-05), e argumento inválido com saída 2 e stdout vazio; as linhas proibidas são conferidas pelo nome no início, não por substring do base64 | `tests/test_gen_env_secrets.py` | sem banco |
| A chave de `--so-chave-rsa`, desescapada como `env.str(..., multiline=True)` a desfaz, publicada no JWKS (JSON Web Key Set): uma chave RSA, `RS256`, `kid` presente, 3072 bits e `n` igual ao módulo da chave gerada (TASK-025/T-02) | `tests/test_gen_env_secrets_jwks.py` | com banco |
| `SPA_URL` na carga das settings, por `runpy`: a ausência derruba a carga nomeando a variável; as recusas (esquema, credenciais, caminho, barra final, query, fragmento, barra invertida, espaço em branco, porta vazia ou ilegível, `http://` fora de loopback sob `BEHIND_TLS_PROXY`) nomeiam a variável e o motivo sem repetir o valor; e os aceitos, `https://` sob proxy, loopback em `http://` com e sem proxy, e porta explícita. A guarda de boot em `GuardaDeProducaoTests` (TASK-028/T-70): com `BASE_URL` público, recusa `SPA_URL` em loopback (`localhost`, `127.0.0.1`, `[::1]`) e os quatro backends de e-mail que não entregam (console, dummy, locmem, filebased), com mensagens que nomeiam a variável sem repetir o valor; `idp.localhost`, `localhost:8000` e `127.0.0.1:8000` não a ativam; `carregar()` fixa `BASE_URL=http://localhost:8000` e aceita sobrescritas | `tests/test_spa_url.py` | sem banco |
| Home com e sem sessão: o link "Ir para a aplicação" com `href` igual a `SPA_URL`, sem `target` e sem query, mais os textos de sessão que já existiam; e a tela de login sem o link e sem o valor de `SPA_URL` | `tests/test_home.py` | com banco |
| Logout iniciado pela RP em `/o/logout/` (TASK-027): a rota sombreada resolvendo para a subclasse; as cinco chaves de produção; a saída com hint vivo, que revoga só na `Application` do hint, encerra a sessão e grava `tokens_revogados` antes de `user_logged_out`, com o mesmo `request_id`; o destino não cadastrado, sem a barra ou em `http`; a confirmação, o CSRF, o cancelar e o hint de outra conta; os hints forjados e as entradas que davam 500, agora 400, com a lista fechada da ADR 0029 em `EntradaForjadaAmpliadaTests` (NUL em `client_id` e em `aud`, destino que não se decompõe como URL, `jti` que não é UUID num hint HS256), e o savepoint de cada trecho que consulta com entrada do pedido em `SavepointDaEntradaForjadaTests`; o hint vencido; o hint autêntico sem linha; e as funções `_aplicacao_do_hint_sem_linha` e `accounts.revogacao._revogar` isoladas, esta também sem Application, com `revogar_tokens` emitindo uma vez por Application afetada (TASK-028/T-43) | `tests/test_logout_rp.py` | misto |
| O modelo da conta: a restrição `Lower(email)` no banco, por `update` e `bulk_create`; o manager e o `save()` em minúsculas, com `sub` UUID versão 4; o carimbo `senha_alterada_em` por `set_password`, `changepassword` e admin, e nunca no re-hash nem no login; as regras de `updated_at` e da verificação, inclusive com `update_fields` | `tests/test_conta_modelo.py` | com banco |
| As migrações de 0002 até a folha do grafo: a colisão de caixa para a migração sem estado parcial, e resolvida migra tudo; a 0004 é irreversível, e um `migrate` seguinte volta à folha | `tests/test_conta_migracao.py` | com banco, `TransactionTestCase` |
| O admin de conta: o grupo "Estado da conta" somente leitura; o carimbo de desativação e de reativação; a troca de e-mail que zera a verificação sem enviar e-mail e esquece o `axes` do endereço antigo; a troca só de caixa, que não zera nem esquece; a conta que só a caixa distingue, recusada | `tests/test_admin_conta.py` | com banco |
| O login com o formulário próprio: a caixa diferente entra; a conta desativada com a senha certa vê a mensagem dela, e com a errada, a genérica; a bloqueada vê o bloqueio; cinco caixas do mesmo endereço contam na mesma conta | `tests/test_login_conta.py` | com banco |
| O login do admin: a caixa diferente entra, as caixas contam na mesma conta, e quem não é staff não entra | `tests/test_login_admin_conta.py` | com banco |
| Os links "Criar conta", com o `next` conferido e codificado, e "Esqueci a senha", sem `next`; o POST vazio em português | `tests/test_login_links.py` | com banco |
| O mixin `EmPortugues`, com a resposta renderizada dentro do `override` | `tests/test_em_portugues.py` | sem banco |
| As oito variáveis de e-mail obrigatórias na carga das settings | `tests/test_email_settings.py` | sem banco |
| `SPA_CLIENT_ID` ausente ou vazia derrubando a carga sem repetir o valor, e `TERMOS_VERSAO_VIGENTE` literal | `tests/test_api_conta_settings.py` | sem banco |
| O executor neutralizando os dois tetos por destinatário, o das confirmações e o dos avisos (TASK-028/T-76), e o envio em thread, e os literais de produção que ele guardou | `tests/test_envio_settings.py` | sem banco |
| O envio: só depois do commit, e nada no rollback; a falha do SMTP (_Simple Mail Transfer Protocol_) e o defeito no envio, no log, sem o endereço nem na pilha; a thread não daemon, com o `request_id` da chamada; o teto de cinco por destinatário, o aviso de segurança fora dele, a chave com o resumo em minúsculas e a falha aberta com o Redis fora. O teto próprio dos avisos em `TetoPorDestinatarioTests` (TASK-028/T-75): a chave separada (`throttle:aviso:`), as confirmações que não suprimem aviso, o 21º aviso suprimido com `aviso_suprimido` sem o endereço, o teto `None` que não cria chave, e o Redis fora, que deixa sair com `throttle_unavailable` | `tests/test_envio.py` | com banco |
| O token de confirmação: prazo de sete dias, `sub` e resumo do e-mail sem o endereço, o salt próprio, e a recusa do adulterado | `tests/test_confirmacao.py` | sem banco |
| As mensagens de aviso: hora no fuso de Brasília, assunto em português, remetente, e nenhum endereço nem link no texto | `tests/test_emails.py` | sem banco |
| A API de conta: o corpo do `GET`, as datas em ISO 8601; as recusas na ordem do `dispatch` (sem credencial, só cookie de sessão, token vencido, sem o scope, de outra Application, de conta inativa, sem dono, fora do cabeçalho); o `PATCH`, com `null` gravando texto vazio e a trilha só com os nomes dos campos; o 400 de corpo inválido; o reenvio e o aceite dos termos | `tests/test_api_conta.py` | com banco |
| O link de confirmação: a primeira vez confirma e registra, a segunda não; o token vazio, adulterado, vencido, de e-mail trocado, de conta inativa ou apagada leva a `invalido`; o `FOR UPDATE` da leitura | `tests/test_api_conta_confirmar.py` | com banco |
| O CORS da API de conta: a origem exata nos quatro caminhos, nenhuma para outra origem, a preflight sem consulta e sem credenciais, e o 401 legível pela aplicação de página única (SPA, de _Single-Page Application_), com `CORS_EXPOSE_HEADERS` | `tests/test_api_conta_cors.py` | com banco |
| O cadastro: o desvio de `prompt=create` com `next` absoluto, a conta criada sem privilégio e não verificada, as boas-vindas, o teto esgotado e as recusas | `tests/test_pagina_cadastro.py` | com banco |
| O `next` do cadastro, que não vira redirecionamento aberto no GET nem no POST | `tests/test_pagina_cadastro_next.py` | com banco |
| O pedido de recuperação, com a mesma resposta para conta ativa, outra caixa, inexistente, inativa e sem senha utilizável; e a conta da equipe (`is_staff`, `is_superuser`), que não recebe e-mail nem gera trilha, com resposta idêntica à do endereço sem conta (TASK-028/T-72) | `tests/test_pagina_recuperacao.py` | com banco |
| A redefinição pelo link: os efeitos (senha, verificação, revogação, sessões, desbloqueio do `axes` com o histórico preservado, aviso), o uso único, o prazo de uma hora e o link sobre `BASE_URL`; o link de conta da equipe, inclusive a promovida depois da emissão, que dá "Link inválido" sem mudar a senha (TASK-028/T-73); e os dois tetos do aviso (TASK-028/T-76) | `tests/test_pagina_redefinicao.py` | com banco |
| A troca de senha: a senha atual por `authenticate()`, o destino fixo, a sessão que fica e as que caem, a revogação e o aviso; e os dois tetos do aviso (TASK-028/T-76) | `tests/test_pagina_troca_de_senha.py` | com banco |
| A troca de e-mail: as recusas, o destino fixo, o `sub` e as sessões que ficam, a confirmação ao novo e o aviso ao antigo, o `axes` do antigo apagado e os links anteriores invalidados; e os dois tetos do aviso ao antigo (TASK-028/T-76) | `tests/test_pagina_troca_de_email.py` | com banco |
| A exclusão: a recusa a conta da equipe; desativar e apagar, com revogação, aviso, trilha e `axes`; a conta dona de Application, que só desativa; os dois tetos do aviso na desativação (TASK-028/T-76) e, em `ApagarTests`, no modo "apagar": com o teto das confirmações esgotado, a conta é apagada e o aviso "conta apagada" sai; com o dos avisos esgotado, a conta é apagada e nenhum e-mail sai (TASK-028/T-77) | `tests/test_pagina_exclusao.py` | com banco |
| Os sinais de conta e `tokens_revogados` emitidos fora de bloco atômico, e o rollback da troca de e-mail sem rastro | `tests/test_pagina_sinais_e_transacao.py` | com banco, `TransactionTestCase` |
| CSRF (Cross-Site Request Forgery) nas seis páginas com formulário, o Bearer que não abre página de sessão, o idioma, o "Cancelar" e o `no-store` | `tests/test_paginas_csrf_bearer_idioma.py` | com banco |
| O teto do cadastro e do pedido de recuperação, e a ausência dele no link de redefinição; e o de `/accounts/password_change/`, `/accounts/email/` e `/accounts/excluir/`, que vale 60, com a 61ª requisição devolvendo 429 (TASK-028/T-74) | `tests/test_limite_paginas_de_conta.py` | com banco |
| `esquecer_tentativas` nas três tabelas do `axes` e `desbloquear` só em `AccessAttempt`, sem distinção de caixa. O handler do `axes` em `HandlerDoAxesTests` (TASK-028/T-71): `get_implementation()` é `TentativasPorConta`; o login em A pela origem X mantém as falhas de X contra V, e o login de V zera as dela; a mutação para o handler da biblioteca apaga as de V, e o caso falha de propósito se o `axes` mudar; `desbloquear` devolve a contagem | `tests/test_tentativas.py` | com banco |
| Nenhum recurso de terceiro nas páginas do IdP, por leitura estática: nem `@import` nem `url(` em `static/css/idp.css`; nem `<script>`, nem `href` ou `src` com endereço absoluto (`http://`, `https://` ou `//`) em qualquer tag de `templates/**/*.html`, e um `<link>` só, o da folha de estilo local | `tests/test_sem_recurso_de_terceiro.py` | sem banco |

### 4.1 O que o nome do arquivo não explica sozinho

Cada item: a guarda, e a razão de ela existir.

**Claims do validador** — `tests/test_oauth_validators.py`

- `name` sai **presente e vazia** quando a pessoa não tem nome cadastrado. A asserção é de
  presença da chave, porque um `dict.get("name")` com valor default esconderia a ausência.
- Nos cinco arranjos de scope, o conjunto de claims é conferido por igualdade: cada uma sai com o
  scope que a libera e só com ele, e `given_name` e `family_name` nunca saem.
- O `sub` é comparado com o UUID da conta e, à parte, declarado diferente da chave primária.
- Um caso à parte traz `email_verified` verdadeiro e `nickname` preenchido: o arranjo padrão só
  prova `False` e `""`, que um valor fixo também devolveria.

**Fluxo completo** — `tests/test_authorization_code_flow.py`

Além de fechar o ciclo até o `id_token`, amarra três coisas que se afastam com facilidade:

- o `kid` do cabeçalho do token contra o `kid` publicado no JWKS;
- as claims do `id_token` contra as do `/o/userinfo/`, por igualdade;
- o conjunto de claims de identidade contra o `claims_supported` da descoberta. Protege contra uma
  troca de assinatura em `get_additional_claims` que deixaria o `id_token` correto e a descoberta
  subdeclarando em silêncio.

**Descoberta** — `tests/test_discovery.py`

- **`issuer` por igualdade exata**, nunca por substring: tanto o `{BASE_URL}` sem o sufixo `/o`
  quanto uma barra final indevida passariam numa comparação frouxa.
- **`end_session_endpoint` presente no documento do OIDC**, com o valor exato, o issuer mais
  `/logout/`: com `OIDC_RP_INITIATED_LOGOUT_ENABLED` falsa, o toolkit omite o campo sem erro
  nenhum (ADR 0029).
- **`end_session_endpoint` ausente no documento da RFC 8414**, porque aquele vocabulário não a
  declara.
- **Cada endpoint dos dois documentos por valor**, o issuer mais o sufixo literal, e nunca por
  `reverse()`, que resolveria contra o mesmo URLConf sob prova.
- **No documento da RFC 8414 essa comparação é a única guarda:** a view do toolkit engole o
  `NoReverseMatch` de um endpoint sem rota e omite a chave com 200, e é o que acusaria uma lista
  de protocolo desmontada do include (ADR 0024).
- **`registration_endpoint` ausente dos dois.**

**Admin de `Application`** — `tests/test_admin_oauth2_application.py`

- Desde a ADR 0024 é a única superfície de gestão. O que se prova é a costura entre o formulário,
  o `clean()` do modelo do toolkit e `ALLOWED_REDIRECT_URI_SCHEMES`.
- Os dois valores dessa chave estão na mesma classe: `["https"]` por `override_settings` sobre
  `OAUTH2_PROVIDER`, e o neutro que o executor aplica.
- O endurecido nunca se alcança por `override_settings(BEHIND_TLS_PROXY=True)`, que mudaria
  também o redirecionamento, a procedência e o issuer.
- A classe do CRUD confere que o clique em "View on site" responde 500: é a dívida que a ADR 0024
  aceita, e o caso existe para que a correção dela, ou a troca por um 200 silencioso, não passe
  sem ser vista.

**Gestão do DOT ausente** — `tests/test_gestao_dot_ausente.py`

- A prova é de ausência de rota: o esperado é 404 sem `Location` para toda identidade,
  superusuário incluído. 403 seria permissão negada por view, e 302, redirecionamento para o
  login.
- As rotas com `pk` recebem o de objetos gravados pelo módulo: um `pk` inexistente daria 404 pela
  ausência do objeto, e as duas causas não se distinguiriam.

**Política de senha** — `tests/test_politica_de_senha.py`

- As recusas são asseridas pelo `code` do `ValidationError`, nunca pelo texto.
- No `createsuperuser` interativo, o `stdin` é substituído por um que se declara terminal, sem o
  que o comando sai antes de pedir senha.
- O caso sem bypass termina num `KeyboardInterrupt` simulado, porque o comando, ao contrário do
  `changepassword`, não tem teto de tentativas.
- O arquivo vizinho, `tests/test_login_senha_legada.py`, prova o outro lado do mesmo silêncio,
  registrado no comentário de `AUTH_PASSWORD_VALIDATORS`: o login não valida a política.

**CORS** — `tests/test_cors.py`

- As duas classes fixam `CORS_ALLOWED_ORIGINS` por `override_settings`, com o mesmo literal do
  `.env`, para que o que esteja sob prova seja só `CORS_URLS_REGEX`.
- Fora de `/o/` e de `/api/conta/`, a asserção é só a ausência de `Access-Control-Allow-Origin`, e
  nunca a de `Vary`, cabeçalho que outras camadas também escrevem e cuja presença nada diria sobre
  CORS. A API de conta tem arquivo próprio, `tests/test_api_conta_cors.py`.
- Dentro de `/o/`, o 401 de `/o/userinfo/` também leva a origem exata: sem ela, o navegador da
  SPA esconderia o 401 atrás de um erro de CORS.

**Prontidão** — `tests/test_health.py`

- **O caso sem banco** prova que um componente falhando não apaga o estado do outro: com o banco
  fora, `"cache": "ok"` continua presente e correto. É a guarda que cai se alguém unificar os dois
  blocos de tratamento num só.
- **Os dois casos da isenção de HTTPS** ligam `SECURE_SSL_REDIRECT` por override — sem isso a
  isenção fica inerte na suíte inteira — e resolvem a rota por nome em vez de escrevê-la: renomear
  a rota sem atualizar o regex da isenção é a segunda mutação silenciosa possível ali.
- **O caso de controle**, com a rota não isenta recebendo 301, é o que distingue "a isenção
  funciona" de "o redirecionamento nunca esteve ligado".

**Correlação por `request_id`** — `RequestIdCorrelationTests`, em `tests/test_observabilidade.py`

- É a prova de regressão da ADR (Architecture Decision Record)
  `docs/adr/0014-manter-o-identificador-de-requisicao-ate-a-requisicao-seguinte.md`: fica vermelho
  se alguém repuser o `reset()` do `ContextVar` no middleware.
- O que a sustenta é o momento em que a linha nasce: tanto o 404 quanto o 400 devolvido por uma
  view são registrados por `log_response`, depois que a cadeia de middleware inteira retornou.
- Um `reset()` ali os mandaria de volta ao sentinela `-`, sem ligação com o pedido que os causou.

### 4.2 Logout pela RP — `tests/test_logout_rp.py`

**Geral**

| Guarda | Razão |
| --- | --- |
| Lê a trilha pelo arquivo real para onde o executor a redireciona, e não por `assertLogs` | `assertLogs` não vê o `request_id` posto pelo filtro do handler; é o que prova que `tokens_revogados` e `user_logged_out` saem da mesma requisição |
| Alcance da revogação conferido pelo efeito, `/o/userinfo/` e o refresh em `/o/token/` | não só pela contagem de linhas |
| Caso de controle de `SaidaComHintVivoTests` liga `OIDC_RP_INITIATED_LOGOUT_DELETE_TOKENS` e vê os tokens da outra `Application` caírem | distingue "a revogação é restrita" de "a outra `Application` nunca teria sido tocada" |
| Todo destino de fixture é `https`; o `http` só aparece em `DestinoTests`, sob `override_settings` | o executor não neutraliza `OIDC_RP_INITIATED_LOGOUT_STRICT_REDIRECT_URIS`, e um destino `http` passaria na jornada de construção e cairia na de container |
| Hints forjados assinados no próprio teste, com a chave do IdP ou com uma gerada ali | variar uma condição de cada vez |

**`EntradaForjadaAmpliadaTests`** — cobre o AC-18 ampliado: as entradas que o toolkit deixaria
chegar a 500 e que a subclasse recusa com 400.

| Caso | Entrada |
| --- | --- |
| `test_ii` | `client_id` com o caractere NUL |
| `test_v` | hint com `aud` igual a NUL |
| `test_vi_e_vii` | destino que não se decompõe como URL, em três `subTest`s: colchete aberto no host, porta acima de 65535 e porta não numérica |
| `test_viii` | hint HS256 com `jti` que não é UUID, assinado com o segredo de uma `Application` confidencial criada no caso. O `client_secret` da fixture passa de 32 bytes, porque o jwcrypto exige 256 bits de chave para HS256 |

- Todo caso confere, depois do 400, que a sessão, os tokens e a trilha ficaram intactos, e faz um
  `GET /` autenticado, que consulta o banco.
- Em `test_ii` e `test_v` essa consulta **não** prova o savepoint: o psycopg 3 recusa o NUL no
  cliente, antes de a consulta chegar ao servidor, e a conexão não fica marcada. Os dois casos
  passam com ou sem savepoint; o que eles provam é o 400.

**`SavepointDaEntradaForjadaTests`** (T-22) — a prova do savepoint.

- Roda num `TestCase`, isto é, dentro de um bloco atômico externo.
- Provoca um `DataError` que só o servidor levanta, uma divisão por zero (`SELECT 1/0`), dentro de
  cada um dos três trechos que a view envolve em `transaction.atomic()`.
- O erro entra por `mock.patch` no método do toolkit que o `super()` resolve, ou na API privada
  do validador:

| Caso | Onde o erro entra |
| --- | --- |
| `test_a` | no `super()` de `get_request_application` |
| `test_b` | no `super()` de `validate_logout_request_user` |
| `test_c` | no corpo de `_aplicacao_do_hint_sem_linha`, pela consulta de `aud` (`_get_client_by_audience`), com um hint autêntico e sem linha. Um segundo patch faz o `super()` de `validate_logout_request_user` levantar `InvalidIDTokenError`, para que o erro passe só por este savepoint |

- Cada caso passa por um savepoint só e cai se o `transaction.atomic()` dele for removido.
- Depois do 400, o `GET /` seguinte tem de funcionar, e sessão, tokens e trilha têm de estar
  intactos.
- Sem o savepoint, o erro do servidor aborta a transação no Postgres sem que o Django saiba, e o
  `GET /` seguinte levanta `InternalError` ("current transaction is aborted"), constatado por
  mutação.

**O hint autêntico sem linha (T-14), adaptado**

- **O desenho pedia** afirmar que o `refresh_token` sobrevive e continua utilizável depois da
  saída.
- **Para fabricar o hint sem linha**, o próprio teste apaga o `IDToken`. O `cleartokens` não faria
  isso, porque só apaga `IDToken` sem access token ligado (`oauth2_provider/models.py:1296-1300`).
- **Apagar o `IDToken`** apaga em cascata o `AccessToken` ligado, e o toolkit recusa o refresh que
  ficou órfão com `invalid_grant`, por conta própria e não por decisão da view.
- **O teste afirma, então,** que o refresh **não foi revogado**, pela linha sem `revoked`, e não
  que ele ainda troca por token.
- **O 200 no refresh** é afirmado em outro caso, o do hint sem linha de outra conta, em que o
  `jti` da linha é trocado em vez de apagado e os tokens do dono seguem inteiros.

### 4.3 Três guardas cuja razão de ser não está no nome

| Guarda | Arquivo | Razão |
| --- | --- | --- |
| A `redirect_uri` com uma barra a mais: registrada `.../noop`, enviada `.../noop/` | `tests/test_authorize_guards.py` | prova de igualdade exata. Se a comparação um dia afrouxar para prefixo, este caso passa a falhar, e essa falha é o objetivo. Um teste com `redirect_uri` grosseiramente diferente passaria nos dois mundos sem dizer nada |
| `GET /accounts/logout/` responde 405 e preserva a sessão | `tests/test_logout_view.py` | um logout que aceitasse GET tornaria qualquer `<img src="/accounts/logout/">` numa página de terceiro um vetor de logout forjado. A asserção não é de conveniência: é o fechamento desse vetor |
| O comentário de template que vaza | `tests/test_template_comment_leak.py` | ver abaixo |

**O comentário de template que vaza.** É uma classe de defeito que nenhuma leitura de código pega:
só aparece na tela renderizada.

- **O defeito:** `{# ... #}` é comentário de uma linha só no Django; com o `#}` em outra linha, o
  texto sai renderizado no corpo da página.
- **As três telas originais:** a asserção é pelos delimitadores, nunca pelo texto de um
  comentário — o texto muda, os delimitadores nunca podem aparecer numa resposta.
- **A tela do logout pela RP, na confirmação e no erro:** confere também o começo do texto do
  comentário. Ela se documenta num `{% comment %}`, cuja forma de vazar é virar texto solto, sem
  delimitador nenhum.
- **A âncora:** a procura por texto só vale enquanto o texto procurado existir no template.
  `test_ancora_o_texto_esta_no_bloco_comment_do_template` lê a fonte do template e confere que o
  trecho está entre `{% comment %}` e `{% endcomment %}`. Se a redação do comentário mudar, a
  âncora fica vermelha, e a ausência do texto na tela deixa de passar sem provar nada.

---

## 5. `tests/runner.py`, e por que a suíte tem executor próprio

`TEST_RUNNER`, em `config/settings.py`, aponta para `tests.runner.RunnerComTrilhaIsolada`. As
settings são únicas, sem separação entre desenvolvimento e produção, de modo que não há um
segundo `LOGGING` nem um segundo conjunto de chaves a declarar: o executor troca sete valores
durante a suíte e os repõe no teardown.

| Valor | Durante a suíte | Produção guardada em | Sem a troca | Religar num caso |
| --- | --- | --- | --- | --- |
| `filename` do handler `audit` | diretório temporário | — (desfeito no teardown) | `manage.py test` escreveria na trilha de auditoria do ambiente, o arquivo de `AUDIT_LOG_PATH`, misturando linha de teste com evidência de operação | — |
| `settings.RATE_LIMIT_POR_CAMINHO` | `{}` | `tests.runner.RATE_LIMIT_DE_PRODUCAO` | execuções seguidas somariam ao contador do ambiente até um caso que não fala de limitação falhar com 429 | `override_settings`, com `REMOTE_ADDR` forjado |
| `settings.SECURE_SSL_REDIRECT` | zerado | `tests.runner.SECURE_SSL_REDIRECT_DE_PRODUCAO` | na jornada de container, toda requisição a rota não isenta receberia 301 antes de a view rodar | `override_settings(SECURE_SSL_REDIRECT=True)` vale por cima do zeramento |
| `settings.OAUTH2_PROVIDER` | cópia com `"ALLOWED_REDIRECT_URI_SCHEMES": ["http", "https"]` | `tests.runner.OAUTH2_PROVIDER_DE_PRODUCAO` | na jornada de container, o 302 de `/o/authorize/` viraria 400 em todo teste de fluxo | `override_settings` sobre `OAUTH2_PROVIDER` |
| `settings.TETO_DE_ENVIOS_POR_DESTINATARIO` | `None`, sem teto | `tests.runner.TETO_DE_ENVIOS_DE_PRODUCAO` | o contador de cada destinatário vive no Redis, não volta com o rollback, e o sexto envio a um endereço de fixture seria suprimido em silêncio | `override_settings`, apagando as chaves por `accounts.envio.chave_do_envio` |
| `settings.TETO_DE_AVISOS_POR_DESTINATARIO` | `None`, sem teto | `tests.runner.TETO_DE_AVISOS_DE_PRODUCAO` | pela mesma razão do teto das confirmações, o 21º aviso de segurança a um endereço de fixture seria suprimido em silêncio | `override_settings`, apagando as chaves por `accounts.envio.chave_do_aviso` |
| `settings.ENVIO_DE_EMAIL_EM_SEGUNDO_PLANO` | `False`, envio síncrono | `tests.runner.ENVIO_EM_SEGUNDO_PLANO_DE_PRODUCAO` | a mensagem sairia numa thread, e `mail.outbox` estaria vazio quando o callback de commit retorna | `override_settings(ENVIO_DE_EMAIL_EM_SEGUNDO_PLANO=True)` e `join` da thread |

### 5.1 A trilha

- **O que troca:** em `setup_test_environment()`, reaplica o `dictConfig` com o `filename` do
  handler `audit` apontando para um diretório temporário, e desfaz no teardown.
- **O que não troca:** formatador, filtro, handler, receptores e esquema são os mesmos objetos
  sob teste e em produção, e a escrita é real, em arquivo real. É o que permite a um teste varrer
  a trilha em busca de campo proibido.
- **Precedente:** `DATABASES`, cujo nome o mesmo executor já redireciona para `test_*`.
- **Alternativa recusada:** um `if TESTING:` nas settings, registrada em
  `docs/adr/0013-registrar-a-trilha-de-auditoria-dos-quatro-sinais-em-arquivo-duravel.md`.
- **Consequência de operação:** **rodar a suíte não polui a trilha, e a trilha da suíte não
  sobrevive à execução.** Quem quiser inspecionar o que um teste escreveu tem de fazê-lo de dentro
  do próprio teste.

### 5.2 O limitador

- Mesma razão e mesma disciplina de reposição da trilha.
- **Esvazia o dicionário inteiro**, hoje os catorze caminhos de `RATE_LIMIT_POR_CAMINHO`, e não
  apenas as entradas de `/o/`:
  - o contador de cada caminho limitado vive no Redis do ambiente e não volta com o rollback do
    `TestCase`;
  - o `REMOTE_ADDR` default do cliente de teste — `127.0.0.1` — é a mesma chave que o `runserver`
    da jornada de construção usa.
- **Dicionário vazio não abre ramo dormente:** é o caminho que toda requisição de caminho não
  limitado já percorre em produção, e o middleware continua na cadeia.
- **Quem religa** apaga as próprias chaves por `config.limites.chave_do_contador` — nunca por
  `cache.clear()`, que o `RedisCache` implementa como `FLUSHDB` e levaria junto a cópia quente das
  sessões (ADR 0005).

### 5.3 O redirecionamento para HTTPS

- Na jornada de container o compose liga `BEHIND_TLS_PROXY`, de que o redirecionamento deriva, e
  o cliente de teste fala HTTP simples.
- **Zera-se o redirecionamento, e nunca `BEHIND_TLS_PROXY`:** é esta variável que decide a
  procedência da origem (ADR 0018) e o esquema do issuer, e a jornada de container existe para
  exercitá-las.

### 5.4 `OAUTH2_PROVIDER`

- **Mesma razão do redirecionamento:** com `BEHIND_TLS_PROXY` ligado,
  `ALLOWED_REDIRECT_URI_SCHEMES` é `["https"]`, e as fixtures registram `redirect_uri` em
  `http://`.
- **Mecanismo:**
  1. guarda o dicionário de produção em `tests.runner.OAUTH2_PROVIDER_DE_PRODUCAO`;
  2. põe no lugar uma cópia com `"ALLOWED_REDIRECT_URI_SCHEMES": ["http", "https"]`;
  3. envia `django.test.signals.setting_changed` com `setting="OAUTH2_PROVIDER"` e `enter=True`;
  4. no teardown, repõe o original e envia o sinal com `enter=False`.
- **A cópia, e nunca a mutação no lugar nem um `setattr` em `oauth2_settings`:** o objeto de
  settings do toolkit guarda referência ao dicionário e faz cache por atributo, e só o `reload()`
  que o sinal dispara limpa os dois caches.
- **O sinal** é o mesmo canal do `override_settings`, e é isso que mantém a suíte independente de
  ordem.
- **Incondicional**, como a do redirecionamento.
- **Dois testes fecham o par**, em `tests/test_endurecimento_transporte.py`: um lê de volta o
  valor guardado para provar que o de produção segue `BEHIND_TLS_PROXY`; o outro confere que o
  cache do toolkit chegou a `["http", "https"]`, o que só o sinal garante.
- **A cópia troca só `ALLOWED_REDIRECT_URI_SCHEMES`.** `OIDC_RP_INITIATED_LOGOUT_STRICT_REDIRECT_URIS`,
  que também segue `BEHIND_TLS_PROXY`, não é neutralizada: na jornada de container ela recusa
  destino de logout em `http` para `Application` pública, e por isso as fixtures do logout usam
  `https`.

### 5.5 O envio de e-mail

- **Os dois tetos por destinatário somem**, o das confirmações e o dos avisos, pela razão do
  limitador: o contador vive no Redis e não volta com o rollback do `TestCase`. Quem religa um
  deles apaga as próprias chaves por `accounts.envio.chave_do_envio` ou
  `accounts.envio.chave_do_aviso`, nunca por `cache.clear()`.
- **O envio fica síncrono.** O backend de e-mail é o `locmem`, que o próprio Django põe na suíte,
  e a mensagem está em `mail.outbox` quando o callback de commit retorna. Num `TestCase`, o commit
  não acontece, e os casos rodam os callbacks por `captureOnCommitCallbacks(execute=True)`.
- **O caminho da thread** é provado por `override_settings(ENVIO_DE_EMAIL_EM_SEGUNDO_PLANO=True)`,
  com `join`, em `EmSegundoPlanoTests`.
- **`tests/test_envio_settings.py`** lê de volta os três valores guardados e confere os literais de
  produção.

---

## 6. `tests/oauth_helpers.py`

O inventário do que já existe pronto para quem for escrever teste novo de fluxo. Reusar daqui é a
regra; duplicar o ritual do fluxo em cada arquivo é o que este módulo existe para evitar.

| Peça | O que entrega |
| --- | --- |
| `REDIRECT_URI` | a `redirect_uri` registrada na fixture; não precisa existir de verdade, só bater por igualdade exata |
| `make_pkce_pair()` | par verificador/desafio válido para o método `S256` |
| `create_public_rs256_application(user)` | a Application do enunciado: client público, `authorization-code` e `algorithm` RS256 (RSA com SHA-256); sempre criada no banco de teste, nunca a linha do banco de desenvolvimento |
| `extract_hidden_inputs(html)` | os `<input type="hidden">` do formulário de consentimento, em dicionário |
| `authorize_and_get_code(...)` | fecha o GET mais o POST de `/o/authorize/` e devolve `(code, code_verifier, response)` |
| `exchange_code_for_tokens(...)` | o POST em `/o/token/` com o `code_verifier`, sem `client_secret` |
| `decode_jwt(token)` | cabeçalho e payload de um JWT (JSON Web Token) compacto, sem verificar assinatura |

O motivo que não se lê na assinatura:

| Peça | Motivo |
| --- | --- |
| `extract_hidden_inputs` | o GET em `/o/authorize/` com parâmetros válidos devolve 200 com o formulário de consentimento, e os campos ocultos dele precisam ser repostados **integralmente** no POST. Ler o HTML e repostar é o que substitui um navegador aqui. Sustenta também o caso de recusa: como só captura campos ocultos, os dois botões de envio ficam de fora, e o dicionário resultante já nasce sem `allow` — exatamente o corpo que o clique em "Recusar" enviaria |
| `decode_jwt` | decodifica de propósito sem verificar a assinatura. Nenhuma demanda pede verificação criptográfica, e fazê-la aqui acrescentaria dependência; `base64` e `json` da biblioteca padrão bastam para ler `alg`, `kid` e as claims |
| `authorize_and_get_code` | devolve `code` igual a `None` quando o servidor recusa antes de emitir — é o que permite às guardas distinguir uma recusa de um código de verdade, e por isso também devolve a resposta bruta |

---

## 7. `tests/logout_helpers.py`

A infraestrutura do logout pela RP, reusada por `tests/test_logout_rp.py` e pelos arquivos que a
TASK-027 estendeu. Constrói sobre `tests/oauth_helpers.py`, sem duplicá-lo.

| Peça | O que entrega |
| --- | --- |
| `DESTINO` | o `post_logout_redirect_uri` das fixtures, `https` e com a barra final |
| `criar_application(dono, nome, post_logout_redirect_uris)` | Application pública RS256, sem `skip_authorization`, com destino de logout cadastrado |
| `emitir_tokens(usuario, aplicacao, client)` | sessão da pessoa e tokens pelo fluxo real, Authorization Code com PKCE; devolve `(client, corpo)` |
| `status_userinfo(access_token)` e `status_refresh(aplicacao, refresh_token)` | o status de `/o/userinfo/` e do grant de refresh em `/o/token/`, a prova da revogação pelo efeito |
| `tamanho_da_trilha()` e `linhas_da_trilha_desde(tamanho)` | as linhas que a trilha ganhou desde um ponto, lidas do arquivo para onde o executor a redireciona |
| `partes_do_token`, `b64`, `claims_de_hint`, `assinar`, `chave_do_idp`, `gerar_chave_rsa` | a montagem de hints: partir um `id_token` real, assinar claims com a chave do IdP ou com outra |
| `adulterar_assinatura(id_token)` | troca um caractere do meio da assinatura — nunca o último: o final da assinatura em base64 carrega bits de preenchimento, e trocá-lo pode deixar a assinatura válida |

`claims_de_hint` sorteia um `sub` UUID quando o caso não passa um: o `sub` das claims nunca é a
chave primária (ADR 0031).

### 7.1 Os helpers da conta

Os três nasceram com a TASK-028 (ADR 0031) e não dependem um do outro.

| Módulo | Peça | O que entrega |
| --- | --- | --- |
| `tests/api_conta_helpers.py` | `ApiDeContaTestCase` | uma conta, a Application da SPA e outra, e `SPA_CLIENT_ID` apontada para a da SPA por `override_settings`; `corpo_json` envia um corpo cru ou serializado com o Bearer |
| | `criar_token(usuario, aplicacao, scope, expira_em)` e `bearer(token)` | o `AccessToken` direto no banco, sem o fluxo de autorização, e o cabeçalho `Authorization` do cliente de teste |
| | `texto_da_trilha_desde`, `linhas_do_evento` e `fotografia(usuario)` | a trilha crua desde um ponto, e todas as colunas da conta, para provar que um 400 não gravou |
| `tests/paginas_helpers.py` | `PaginasDeContaTestCase` | uma conta, o `dono` das duas Applications, `tokens_nas_duas`, `outra_sessao`, `postar` com os callbacks de commit executados, `esgotar_teto`, `esgotar_teto_de_avisos` e `trilha`. `esgotar_teto_de_avisos` zera o teto dos avisos, outro contador que o de `esgotar_teto`, e apaga as chaves no fim (TASK-028/T-76) |
| | `semear_axes`, `contagem_axes` e `vivos` | as três tabelas do `axes` de um endereço, e os tokens vivos da conta |
| | `dados_de_cadastro`, `link_do_email` e `caminho_do_link` | o corpo válido do cadastro e o link de uma mensagem, pronto para o cliente de teste |
| `tests/envio_helpers.py` | `capturar_envio` e `campos` | as linhas de `accounts.envio` pelo `FormatadorJSON` e pelo `FiltroRequestId` de produção |
| | `BackendQueLevanta` e `BackendQueBloqueia` | backends de e-mail falsos, importáveis por `override_settings(EMAIL_BACKEND=...)`, com o estado em atributo de classe |

As Applications de `PaginasDeContaTestCase` têm outra pessoa como dona: a conta dona de
Application não pode ser apagada pela página, e os casos de apagamento precisam de tokens sem essa
trava.

---

## 8. A convenção de rastreabilidade

Todo teste nomeia, no docstring do módulo, a demanda que o originou.

| Forma | Exemplo | Onde |
| --- | --- | --- |
| Qualificada | `TASK-007/T-01`, `TASK-008/T-01`, `TASK-009/T-01` | tarefa e demanda de teste no mesmo rótulo |
| Curta | `T-01` a `T-05` | nos cinco módulos da TASK-006, cuja tarefa aparece na linha seguinte do mesmo docstring (`Demanda do quality-assurance (TASK-006)`) |
| Critério de aceite | `AC-10` em `tests/test_oauth_validators.py`, `AC-05` em `tests/test_logout_view.py` | no docstring do caso que o prova |

- **Formato dos rótulos:** fixado em "Convenções compartilhadas", em
  `.claude/PROTOCOLO-AGENTES.md` — `AC-NN` e `T-NN`, dois dígitos, `TASK-NNN` com três. São
  **rótulos de contrato**, casados literalmente: não se renumeram, não se reescrevem e não se
  acentuam.
- **O que a convenção compra:** a travessia nos dois sentidos — de um critério de aceite até o
  teste que o prova, com um `grep`; e de um teste vermelho de volta ao que se pediu e por quê, sem
  depender de quem lembre.
- **Por isso o porquê de cada teste mora no docstring**, e não neste documento: aqui ele
  envelheceria longe do código que descreve.

**Demanda resolvida por declaração.** Nenhum docstring a nomeia; por isso está registrada aqui.

| Demanda | Resolução |
| --- | --- |
| `T-05` da TASK-015 — dois `X-Forwarded-For` distintos atrás do mesmo proxy contando separado | já provada por `DoisClientesAtrasDoMesmoProxyTests`, em `tests/test_limite_login.py`, escrita para a `T-04` da TASK-014. Caso novo nenhum nasceu dela; quem procurar esse rótulo em `tests/` não acha nada |

---

## 9. Quem escreve teste aqui

A separação é rígida.

| Papel | Faz | Não faz |
| --- | --- | --- |
| `quality-assurance` | decide o que testar e em que nível, e emite as demandas `T-NN` | — |
| `tester` | implementa essas demandas, e só elas; é o único agente que escreve em `tests/` | — |
| `writer` | escreve o código de produção e a documentação | **não toca em arquivo de teste** em hipótese nenhuma, nem ao corrigir o defeito que um teste apontou |

Definições em `.claude/agents/quality-assurance.md`, `.claude/agents/tester.md` e
`.claude/agents/writer.md`; a tabela de fronteiras de escrita, em `.claude/PROTOCOLO-AGENTES.md`.

**Teste vermelho não se conserta ajustando o teste.**

- Teste malfeito: quem o conserta é quem o escreveu.
- Código de produção errado: a correção é dele.
- Um teste ajustado para passar sobre comportamento errado é pior que teste ausente, porque mente
  sobre a cobertura.

---

## 10. O que a suíte não cobre

Não há medida de cobertura neste projeto. O que segue é leitura da suíte e do código, não
relatório de ferramenta — vale como inventário, não como percentual.

| Lacuna | O que falta | Exceção ou quem cobre |
| --- | --- | --- |
| Carga e concorrência | nenhum teste com mais de um cliente simultâneo, nenhuma medição de tempo de resposta | — |
| Expiração de token | o ciclo de vida de `access_token` e `refresh_token`: a suíte emite e usa, nunca espera vencer nem tenta usar vencido | o `id_token` que `tests/test_logout_rp.py` emite já vencido, por `ID_TOKEN_EXPIRE_SECONDS` negativo, para provar que a aba aberta há mais de dez horas sai |
| Verificação criptográfica da assinatura | `decode_jwt` lê o `id_token` sem validá-lo; prova-se que o `kid` do cabeçalho é o publicado no JWKS, não que a assinatura confere | no logout pela RP a verificação é da view, e a suíte prova que ela recusa assinatura adulterada ou de outra chave — mas não verifica por conta própria a assinatura do que o IdP emite |
| `docker/entrypoint.sh` | a sequência de boot — `migrate`, `collectstatic`, `exec gunicorn` | — |
| O `BASE_URL` de uma implantação | um `BASE_URL` errado (10.1) | o procedimento de `docs/receita.md`, lido por uma pessoa |
| A fronteira de transporte inteira | o serviço `proxy`, o `docker/Caddyfile`, a ausência de `ports:` no `app`, o `requirepass` do Redis e o `USER` do container (10.2) | `tests/test_borda_do_tunel.py`, só para o endereço do conector |
| O `HEALTHCHECK` como o Docker o executa | a probe de verdade, com os tempos de `docs/adr/0011-dar-teto-de-tempo-ao-health-e-derivar-o-healthcheck-dele.md` | `tests/test_health.py` exercita a view e a isenção de redirecionamento, ambas em processo |
| O build da imagem | nada verifica que o `Dockerfile` constrói, nem que a imagem sobe | — |
| Segredo que a suíte não conhece | dado sensível de um caminho que a suíte não exercita, ou de um campo que alguém acrescente amanhã (10.3) | — |
| O que o container instala | o conjunto de pacotes do container (10.4) | — |
| O SMTP de verdade | nenhum caso fala com um servidor de e-mail: a suíte envia pelo backend `locmem`, e a falha do SMTP é simulada por backend falso | `tests/test_envio.py`, para o que o log registra |
| A morte do worker durante o envio | a perda da mensagem na thread, que não é fila durável | — |

### 10.1 O `BASE_URL` de uma implantação

- **As duas asserções de issuer:** uma em `tests/test_discovery.py`, sobre o documento de
  descoberta, e outra em `tests/test_authorization_code_flow.py`, sobre a claim `iss` do
  `id_token`.
- **O que comparam:** o valor publicado com `f"{settings.BASE_URL.rstrip('/')}/o"`, derivado do
  `BASE_URL` vigente e não de um literal.
- **O que pegam:** a expressão esperada repete a composição de `config/settings.py`, de modo que
  pegam defeito de **composição** — sufixo `/o` ausente, barra dobrada, barra final indevida,
  esquema divergente do `BASE_URL`.
- **O que não podem pegar:** um `BASE_URL` errado. Os dois lados da igualdade se movem juntos, e
  um issuer apontando para o host errado passa nas duas.
- **Quem detecta:** o procedimento de `docs/receita.md`, lido por uma pessoa. É a única coisa
  deste repositório que a suíte declaradamente entrega à verificação manual.

### 10.2 A fronteira de transporte

- Os itens da tabela são propriedades de arquivos que a suíte não lê.
- **O que ela exercita do ramo de proxy** é `config/origem.py`, por `override_settings`, com um
  `X-Forwarded-For` que os testes escrevem — nunca um que um proxy tenha escrito.
- **A única exceção** é `tests/test_borda_do_tunel.py`, que lê o `docker/Caddyfile` e o
  `docker-compose.prod.yml` como texto só para comparar o literal do endereço do conector,
  duplicado à mão entre os dois (ADR 0027, "Literal duplicado"), e a sua posição na rede `borda`,
  fora da faixa dinâmica.
- **O que ela não prova:** a igualdade dos literais não prova que o proxy confie no conector, e a
  posição fora do `ip_range` não prova que o daemon do Docker respeite a faixa. O comportamento do
  proxy e o do daemon continuam fora da suíte.

### 10.3 Segredo que a suíte não conhece

- **O que a varredura do log e da trilha procura:** valores que o próprio fluxo produziu — senha,
  `code`, `code_verifier`, tokens, `SECRET_KEY`, o e-mail digitado —, em todos os loggers do
  processo, a raiz inclusive.
- **O que ela não pode fazer:** procurar o que não sabe existir.

### 10.4 O que o container instala

- A suíte roda contra o ambiente virtual do host, resolvido a partir de `requirements.txt`.
- O container instala de um wheelhouse construído por `pip wheel` no momento do build, que
  resolve as dependências transitivas sem versão fixada.
- São dois conjuntos de pacotes que podem divergir, e a suíte só enxerga um deles.
- **Este item toca o núcleo:** a biblioteca que assina o `id_token` está entre as transitivas sem
  versão fixada. O `docs/seguranca.md`, na seção 4.13, registra a consequência operacional disso.
