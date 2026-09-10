# Testes — nova_api

Este documento é o dono da suíte: os níveis de teste e o critério que os separa, a convenção de
rastreabilidade que liga cada teste à demanda que o pediu, a infraestrutura compartilhada, e o
inventário do que não está coberto. O modelo mental do sistema está em `docs/arquitetura.md`; a
receita de subir o stack, no `docs/receita.md`.

## O que a suíte é

Arquivos `test_*.py` num pacote só, `tests/`, na raiz do repositório, mais dois módulos que não
são teste e sim a infraestrutura que a suíte usa: `tests/oauth_helpers.py`, que os testes de
fluxo reusam, e `tests/runner.py`, o executor.

O pacote é da raiz, e não de dentro de `accounts/`, porque a suíte quase toda exercita
superfícies que `accounts` não possui: rotas declaradas em `config/urls.py`, views do toolkit
e views prontas do `django.contrib.auth`. Importar de `accounts` é a exceção, e quais módulos o
fazem responde-se por `grep -l '^from accounts' tests/*.py` — a lista cresce a cada função do
app que valha uma prova isolada, e por isso não está escrita aqui.

O executor é um `DiscoverRunner` do Django subclassado, sobre `unittest` da biblioteca padrão.
Isso é o que há:

- **não há pytest** — nenhum `conftest.py`, nenhuma dependência de teste em `requirements.txt`,
  que lista apenas as nove de execução;
- **não há ferramenta de cobertura** — nenhum `coverage`, nenhum relatório gerado;
- **não há integração contínua versionada** — `git ls-files` não devolve `.github/`, nem
  `.gitlab-ci.yml`, nem `tox.ini`. A suíte roda quando alguém a roda.

## Como rodar

```bash
.venv/bin/python manage.py test                # jornada de construção
docker compose exec app python manage.py test  # jornada de clonar-e-rodar
```

Sem argumento, `manage.py test` descobre o pacote inteiro; `manage.py test tests` é a forma
explícita e roda os mesmos casos. Rótulo de app não serve mais como atalho:
`manage.py test accounts` responde `Found 0 test(s)` — nenhum teste mora lá. Enquanto a suíte
esteve dividida entre `accounts/` e `config/`, esse mesmo comando rodava dez dos doze arquivos
e calava sobre os outros dois.

O pré-requisito é ter Postgres e Redis de pé. O executor cria e destrói o banco de teste
sozinho, mas precisa de um servidor a que se conectar; e o Redis é tocado por toda requisição
com sessão, porque `SESSION_ENGINE` é `cached_db`, além de ser consultado diretamente pela view
de `/health`. Nas duas jornadas isso significa `docker compose up` tendo subido, no mínimo, os
serviços `postgres` e `redis`.

A suíte **não** exige `collectstatic` prévio. `tests/test_login_view.py` confere o CSS
(Cascading Style Sheets) por `finders.find("css/idp.css")`, que procura no diretório-fonte, e
por `static("css/idp.css")`, que resolve a URL (Uniform Resource Locator) em tempo de execução
— nenhum dos dois depende do diretório coletado. Preservar isso foi parte do que se decidiu em
`docs/adr/0008-servir-estaticos-com-whitenoise-sem-manifesto-de-hash.md`.

## Os dois níveis, e o critério que os separa

**Sem banco (`SimpleTestCase`).** O que está sob prova não precisa de linha no banco: ou a
função é chamada diretamente, com um portador falso no lugar do que ela leria do mundo, ou é
pura, ou o estado que ela confere já foi montado antes de o primeiro caso rodar. Os lugares:

- `tests/test_oauth_validators.py`, inteiro — `get_oidc_claims` lê só `.user` e
  `.scopes`, então um objeto de duas linhas basta, e o `User` é construído sem nunca ser salvo;
- a classe `HealthViewDatabaseDownUnitTests`, em `tests/test_health.py` — `RequestFactory`
  mais chamada direta a `health`, com `connection` substituída por um duplo que levanta;
- a classe `FormatadorJSONTests`, em `tests/test_observabilidade.py` — um registro emitido por
  um logger próprio do módulo, com o par filtro e formatador de produção anexado a um handler
  efêmero, de modo que a linha capturada é a que sairia de verdade;
- a classe `ResumoDoIdentificadorTests`, em `tests/test_auditoria.py` — aqui não há portador
  nenhum a falsificar: `_resumo_do_identificador` é função pura, entra uma string e sai um
  hexadecimal;
- a classe `TrilhaIsoladaDuranteASuiteTests`, em `tests/test_auditoria.py` — a exceção ao
  critério, e deliberada: o que ela confere é o handler `audit` **real**, já redirecionado pelo
  executor, e a escrita que ela faz é em arquivo de verdade. Nada disso pede banco, e falsificar
  o handler destruiria justamente o que se quer provar.

**Com banco e cliente de teste (`TestCase`).** A requisição atravessa o URLConf, o middleware, a
view, o template e o banco de teste. É onde está todo o resto: os arquivos ausentes da lista
acima, inteiros, e as demais classes dos que aparecem nela — só `tests/test_oauth_validators.py`
não deixa nada para cá.

Fora a exceção nomeada acima, o critério de escolha é um só: **o nível sem banco vale quando a
decisão cabe inteira numa função isolável; nos demais, o que pode quebrar é a costura, e só a
resposta HTTP a revela.** A costura aqui é quase sempre entre configuração e biblioteca de terceiro:
`PKCE_REQUIRED`, que exige o Proof Key for Code Exchange (PKCE); `OIDC_ISS_ENDPOINT`, que fixa o
issuer; `SECURE_REDIRECT_EXEMPT`, que isenta `/health`; a allowlist de `redirect_uri`. Um teste
isolado sobre qualquer uma delas só afirmaria o valor de uma chave de `config/settings.py`, que
não está em dúvida.

O que a suíte inteira não faz: sair do processo. Nenhuma requisição HTTP de verdade, nenhum
servidor vivo, nenhum navegador. Não há `LiveServerTestCase` nem cliente HTTP externo em lugar
nenhum dela — o cliente de teste do Django chama a aplicação em memória. Não existe, portanto,
nível fim-a-fim neste projeto.

## O que cada arquivo garante

| Assunto | Arquivo | Nível |
| --- | --- | --- |
| Claims emitidas pelo validador, por combinação de scope | `tests/test_oauth_validators.py` | sem banco |
| Documento de descoberta: `issuer`, endpoints, o que não deve aparecer | `tests/test_discovery.py` | com banco |
| JWKS (JSON Web Key Set) publicado: uma chave RSA (Rivest–Shamir–Adleman) com `kid` | `tests/test_jwks.py` | com banco |
| Authorization Code + PKCE fechado de ponta a ponta | `tests/test_authorization_code_flow.py` | com banco |
| Guardas de `/o/authorize/`: PKCE obrigatório, `redirect_uri`, método `plain` | `tests/test_authorize_guards.py` | com banco |
| Tela de consentimento e o ramo de recusa | `tests/test_authorize_consent.py` | com banco |
| Anônimo interrompido em `/o/authorize/` e resgatado pelo login | `tests/test_login_authorize_bridge.py` | com banco |
| Tela de login: renderização, sucesso e falha de credencial | `tests/test_login_view.py` | com banco |
| Logout por POST, e a recusa do GET | `tests/test_logout_view.py` | com banco |
| Ausência das rotas de recuperação de senha | `tests/test_password_reset_urls.py` | com banco |
| Comentário de template vazando para o corpo da página | `tests/test_template_comment_leak.py` | com banco |
| Prontidão de banco e de cache, e a isenção de HTTPS | `tests/test_health.py` | misto |
| Esquema da linha de log, correlação por `request_id` e a linha de acesso: campos, e o `/health` fora dela | `tests/test_observabilidade.py` | misto |
| Trilha de auditoria: os quatro sinais, a ausência de segredo e o isolamento sob a suíte | `tests/test_auditoria.py` | misto |

As linhas que o nome do arquivo não explica sozinho:

**Claims do validador.** Prova que a claim `name` sai **presente e vazia** quando a pessoa não
tem nome cadastrado — a asserção é de presença da chave, porque um `dict.get("name")` com valor
default esconderia a ausência. E prova, nos cinco arranjos de scope, que `email_verified` nunca
sai: o scope `email` isolado herdaria essa claim do mapa da classe base do toolkit se
`get_additional_claims` alguma vez passasse a devolvê-la.

**Fluxo completo.** Além de fechar o ciclo até o `id_token`, amarra três coisas que se afastam
com facilidade: o `kid` do cabeçalho do token contra o `kid` publicado no JWKS, as claims do
`id_token` contra as do `/o/userinfo/` por igualdade, e o conjunto de claims de identidade
contra o `claims_supported` da descoberta. Esta última guarda protege contra uma troca de
assinatura em `get_additional_claims` que deixaria o `id_token` correto e a descoberta
subdeclarando em silêncio.

**Descoberta.** Compara o `issuer` por igualdade exata, nunca por substring, porque tanto o
`{BASE_URL}` sem o sufixo `/o` quanto uma barra final indevida passariam numa comparação
frouxa. E afirma a **ausência** de `end_session_endpoint`, cujo default na biblioteca está
programado para inverter numa versão futura.

**Prontidão.** O caso sem banco existe para provar que um componente falhando não apaga o
estado do outro: com o banco fora, `"cache": "ok"` continua presente e correto. É a guarda que
cai se alguém unificar os dois blocos de tratamento num só. Os dois casos da isenção de HTTPS
ligam `SECURE_SSL_REDIRECT` por override — sem isso a isenção fica inerte na suíte inteira — e
resolvem a rota por nome em vez de escrevê-la, porque renomear a rota sem atualizar o regex da
isenção é a segunda mutação silenciosa possível ali. O caso de controle, com a rota não
isenta recebendo 301, é o que distingue "a isenção funciona" de "o redirecionamento nunca
esteve ligado".

**Correlação por `request_id`.** A classe `RequestIdCorrelationTests`, em
`tests/test_observabilidade.py`, é a prova de regressão da ADR (Architecture Decision Record)
`docs/adr/0014-manter-o-identificador-de-requisicao-ate-a-requisicao-seguinte.md`: é o caso que
fica vermelho se alguém repuser o `reset()` do `ContextVar` no middleware. O que a sustenta é o
momento em que a linha nasce — tanto o 404 quanto o 400 devolvido por uma view são registrados
por `log_response`, depois que a cadeia de middleware inteira retornou, e um `reset()` ali os
mandaria de volta ao sentinela `-`, sem ligação com o pedido que os causou.

### Três guardas cuja razão de ser não está no nome

**A `redirect_uri` com uma barra a mais.** Em `tests/test_authorize_guards.py`, a
registrada é `.../noop` e a enviada, `.../noop/`. O teste é prova de igualdade exata: se a
comparação um dia afrouxar para prefixo, este caso passa a falhar, e essa falha é o objetivo.
Um teste com `redirect_uri` grosseiramente diferente passaria nos dois mundos sem dizer nada.

**`GET /accounts/logout/` responde 405 e preserva a sessão.** Um logout que aceitasse GET
tornaria qualquer `<img src="/accounts/logout/">` numa página de terceiro um vetor de logout
forjado. A asserção não é de conveniência: é o fechamento desse vetor, e está em
`tests/test_logout_view.py`.

**O comentário de template que vaza.** `{# ... #}` é comentário de uma linha só no Django; com
o `#}` em outra linha, o texto sai renderizado no corpo da página.
`tests/test_template_comment_leak.py` cobre as três telas e assere pelos
delimitadores, nunca pelo texto de um comentário — o texto muda, os delimitadores nunca podem
aparecer numa resposta. É uma classe de defeito que nenhuma leitura de código pega: só aparece
na tela renderizada.

## `tests/runner.py`, e por que a suíte tem executor próprio

`TEST_RUNNER`, em `config/settings.py`, aponta para `tests.runner.RunnerComTrilhaIsolada`. Sem
ele, `manage.py test` escreveria na **trilha de auditoria do ambiente** — o arquivo de
`AUDIT_LOG_PATH` —, misturando linha de teste com evidência de operação. As settings são únicas,
sem separação entre desenvolvimento e produção, de modo que não há um segundo `LOGGING` a
declarar.

O que ele faz é trocar um valor só: em `setup_test_environment()`, reaplica o `dictConfig` com o
`filename` do handler `audit` apontando para um diretório temporário, e desfaz no teardown.
Formatador, filtro, handler, receptores e esquema são os mesmos objetos sob teste e em produção,
e a escrita é real, em arquivo real — é o que permite a um teste varrer a trilha em busca de
campo proibido. O precedente é `DATABASES`, cujo nome o mesmo executor já redireciona para
`test_*`; a alternativa recusada, um `if TESTING:` nas settings, está registrada em
`docs/adr/0013-registrar-a-trilha-de-auditoria-dos-quatro-sinais-em-arquivo-duravel.md`.

A consequência de operação: **rodar a suíte não polui a trilha, e a trilha da suíte não
sobrevive à execução.** Quem quiser inspecionar o que um teste escreveu tem de fazê-lo de dentro
do próprio teste.

## `tests/oauth_helpers.py`

O inventário do que já existe pronto para quem for escrever teste novo de fluxo. Reusar daqui
é a regra; duplicar o ritual do fluxo em cada arquivo é o que este módulo existe para evitar.

| Peça | O que entrega |
| --- | --- |
| `REDIRECT_URI` | a `redirect_uri` registrada na fixture; não precisa existir de verdade, só bater por igualdade exata |
| `make_pkce_pair()` | par verificador/desafio válido para o método `S256` |
| `create_public_rs256_application(user)` | a Application do enunciado: client público, `authorization-code` e `algorithm` RS256 (RSA com SHA-256); sempre criada no banco de teste, nunca a linha do banco de desenvolvimento |
| `extract_hidden_inputs(html)` | os `<input type="hidden">` do formulário de consentimento, em dicionário |
| `authorize_and_get_code(...)` | fecha o GET mais o POST de `/o/authorize/` e devolve `(code, code_verifier, response)` |
| `exchange_code_for_tokens(...)` | o POST em `/o/token/` com o `code_verifier`, sem `client_secret` |
| `decode_jwt(token)` | cabeçalho e payload de um JWT (JSON Web Token) compacto, sem verificar assinatura |

Duas dessas peças existem por um motivo que não se lê na assinatura:

- **`extract_hidden_inputs`** — o GET em `/o/authorize/` com parâmetros válidos devolve 200 com
  o formulário de consentimento, e os campos ocultos dele precisam ser repostados
  **integralmente** no POST. Ler o HTML e repostar é o que substitui um navegador aqui. O mesmo
  helper sustenta o caso de recusa: como ele só captura campos ocultos, os dois botões de envio
  ficam de fora, e o dicionário resultante já nasce sem `allow` — exatamente o corpo que o
  clique em "Recusar" enviaria.
- **`decode_jwt`** — decodifica de propósito sem verificar a assinatura. Nenhuma demanda pede
  verificação criptográfica, e fazê-la aqui acrescentaria dependência; `base64` e `json` da
  biblioteca padrão bastam para ler `alg`, `kid` e as claims.

`authorize_and_get_code` devolve `code` igual a `None` quando o servidor recusa antes de emitir
— é o que permite às guardas distinguir uma recusa de um código de verdade, e por isso a função
também devolve a resposta bruta.

## A convenção de rastreabilidade

Todo teste nomeia, no docstring do módulo, a demanda que o originou. Duas formas convivem:

- **qualificada** — `TASK-007/T-01`, `TASK-008/T-01`, `TASK-009/T-01`: tarefa e demanda de
  teste no mesmo rótulo;
- **curta** — `T-01` a `T-05`, nos cinco módulos da TASK-006, cuja tarefa aparece na linha
  seguinte do mesmo docstring (`Demanda do quality-assurance (TASK-006)`).

Critérios de aceite entram pela mesma porta, no docstring do caso que os prova: `AC-10` em
`tests/test_oauth_validators.py`, `AC-05` em `tests/test_logout_view.py`.

O formato dos rótulos está fixado em "Convenções compartilhadas", em
`.claude/PROTOCOLO-AGENTES.md`: `AC-NN` e `T-NN`, dois dígitos, `TASK-NNN` com três. São
**rótulos de contrato**, casados literalmente — não se renumeram, não se reescrevem e não
se acentuam.

O que a convenção compra é a travessia nos dois sentidos: de um critério de aceite até o teste
que o prova, com um `grep`; e de um teste vermelho de volta ao que se pediu e por quê, sem
depender de quem lembre. É por isso que o porquê de cada teste mora no docstring, e não neste
documento: aqui ele envelheceria longe do código que descreve.

## Quem escreve teste aqui

O repositório separa três papéis, e a separação é rígida:

- o **`quality-assurance`** decide o que testar e em que nível, e emite as demandas `T-NN`;
- o **`tester`** implementa essas demandas, e só elas — é o único agente que escreve em
  `tests/`;
- o **`writer`** escreve o código de produção e a documentação, e **não toca em arquivo de
  teste** em hipótese nenhuma, nem ao corrigir o defeito que um teste apontou.

As definições estão em `.claude/agents/quality-assurance.md`, `.claude/agents/tester.md` e
`.claude/agents/writer.md`; a tabela de fronteiras de escrita, em `.claude/PROTOCOLO-AGENTES.md`.

A regra prática que decorre disso: **teste vermelho não se conserta ajustando o teste.** Ou o
teste está malfeito, e quem o conserta é quem o escreveu, ou o código de produção está errado,
e a correção é dele. Um teste ajustado para passar sobre comportamento errado é pior que teste
ausente, porque mente sobre a cobertura.

## O que a suíte não cobre

Não há medida de cobertura neste projeto. O que segue é leitura da suíte e do código, não
relatório de ferramenta — vale como inventário, não como percentual.

- **Carga e concorrência.** Nada. Nenhum teste com mais de um cliente simultâneo, nenhuma
  medição de tempo de resposta.
- **Expiração de token.** O ciclo de vida de `access_token` e `refresh_token` não é exercitado:
  a suíte emite e usa, nunca espera vencer nem tenta usar vencido.
- **Verificação criptográfica da assinatura.** `decode_jwt` lê o `id_token` sem validá-lo. O que
  se prova é que o `kid` do cabeçalho é o publicado no JWKS, não que a assinatura confere.
- **`docker/entrypoint.sh`.** A sequência de boot — `migrate`, `collectstatic`, criação
  condicional de superusuário, `exec gunicorn` — não tem teste nenhum.
- **O `HEALTHCHECK` como o Docker o executa.** `tests/test_health.py` exercita a view e a
  isenção de redirecionamento, ambas em processo. A probe de verdade, com os tempos de
  `docs/adr/0011-dar-teto-de-tempo-ao-health-e-derivar-o-healthcheck-dele.md`, nunca roda aqui.
- **O build da imagem.** Nada verifica que o `Dockerfile` constrói, nem que a imagem sobe.
- **Segredo que a suíte não conhece.** A varredura do log e da trilha procura valores que o
  próprio fluxo produziu — senha, `code`, `code_verifier`, tokens, `SECRET_KEY`, o e-mail
  digitado —, em todos os loggers do processo, a raiz inclusive. O que ela não pode fazer é
  procurar o que não sabe existir: dado sensível de um caminho que a suíte não exercita, ou de
  um campo que alguém acrescente amanhã, passa sem ser visto.
- **O que o container instala.** A suíte roda contra o ambiente virtual do host, resolvido a
  partir de `requirements.txt`. O container instala de um wheelhouse construído por `pip wheel`
  no momento do build, que resolve as dependências transitivas sem versão fixada. São dois
  conjuntos de pacotes que podem divergir, e a suíte só enxerga um deles.

Entre esses itens, o último toca o núcleo: a biblioteca que assina o `id_token` está entre as
transitivas sem versão fixada. O `docs/seguranca.md`, na seção 4, "Controles ausentes", registra
a consequência operacional disso.
