# 0013. Registrar a trilha de auditoria dos quatro sinais num arquivo durável

## Status

Aceito — 2026-09-08

## Contexto

A seção 4 de `docs/seguranca.md` registra a ausência: não se sabe quem autenticou, qual relying
party (RP) recebeu token, nem quando. Diante de uma suspeita de credencial comprometida, a única
resposta possível hoje é "não dá para saber". Some-se que o log vive apenas no `stdout` do
container, e recriar o container apaga o histórico inteiro.

Quatro sinais já instalados cobrem o essencial, e foram verificados contra o código em `.venv/`:
`user_logged_in`, `user_login_failed` e `user_logged_out`, de `django/contrib/auth/signals.py`;
e `app_authorized`, de `oauth2_provider/signals.py`, emitido em
`oauth2_provider/views/base.py:506`, dentro de `TokenView`, com o `AccessToken` já persistido.
Dois eventos desejáveis **não** têm sinal: a criação de Application exigiria `post_save` no
modelo devolvido por `get_application_model()`, e a revogação de token não emite nada — o
`cleartokens` apaga linhas em silêncio.

Três propriedades do terreno decidem o desenho.

A primeira: `user_login_failed` entrega `credentials` já saneado por `_clean_credentials`
(`django/contrib/auth/__init__.py:84`), que substitui por asteriscos toda chave que compare com
`api|token|key|secret|password|signature`. A chave `username` não compara com nenhuma delas, e
neste projeto ela carrega o e-mail digitado, em claro. Registrar o identificador tentado é o que
distingue uma conta sob ataque de muitas contas sondadas; registrá-lo em claro grava dado pessoal
— inclusive de quem apenas errou a própria senha — num arquivo cuja retenção é maior que a do log
operacional.

A segunda: `user_logged_in` é enviado de dentro de `django.contrib.auth.login()`
(`__init__.py:197`). O que um receptor levantar ali sobe pela pilha do login.

A terceira: a suíte roda no mesmo processo e com as mesmas settings — `config/settings.py` declara
não haver split entre desenvolvimento e produção, porque um arquivo de dev que nunca roda em
produção é um caminho não exercitado. Sem cuidado, `manage.py test` escreveria na mesma trilha do
ambiente, misturando linha de teste com evidência de operação.

Por fim, o escopo: host único, uma réplica, três workers `sync`, sem coletor de log e sem
mecanismo de retenção. Rotação por processo é armadilha conhecida — três workers renomeando o
mesmo arquivo perdem linhas sem emitir nada.

## Decisão

Vamos escrever uma trilha de auditoria em arquivo próprio, durável, alimentada por quatro
receptores de sinal, com esquema de campos declarado e uma regra de desenho sem exceção sobre o
que nunca entra nela.

**O destino.** Logger `audit`, com `propagate` falso e nível fixo em `INFO` — nunca `LOG_LEVEL`,
porque uma trilha que um botão de verbosidade desliga não é trilha. O handler é
`logging.handlers.WatchedFileHandler`, nunca `RotatingFileHandler`: com três workers, a rotação
por processo perde linhas em silêncio, e a rotação, se um dia existir, será externa ao processo.
O modo de abertura é `"a"`, declarado mesmo sendo o default, porque um `"w"` truncaria a trilha a
cada boot. O `filename` vem de `AUDIT_LOG_PATH`, sem default no código: ausente, ela derruba o
processo na leitura das settings nomeando a si mesma, como manda o contrato do projeto e o
precedente da ADR (Architecture Decision Record) 0004. No container, o caminho aponta para um
volume nomeado, `auditlog`, montado em `/var/log/nova_api`, e o `docker-compose.yml` sobrescreve a
variável pelo mesmo mecanismo com que já sobrescreve `DATABASE_URL` — a trilha sobrevive a
`docker compose down`.

**Os eventos e os campos.** Os receptores vivem em `accounts/auditoria.py`, ligados em
`AccountsConfig.ready()` com `dispatch_uid`, e moram em `accounts` porque é o app dono da pessoa.
O campo `event` recebe **o nome do sinal**, para que quem lê a trilha chegue ao emissor por
`grep`. Além dos campos comuns a toda linha (ADR 0012), cada linha traz `event`, `sub`, `ip` e
`outcome`; `client_id` em `app_authorized`; `identifier_sha256` em `user_login_failed`. O `sub` é
a chave primária de `accounts.User` serializada como **string**, igual à claim `sub` do
`id_token`, e é `null` quando não há pessoa associada — no logout sem usuário a linha é emitida
assim mesmo, com o campo explicitamente vazio. Em `app_authorized`, o `sub` sai de `token.user_id`
e o `client_id` de `token.application.client_id`; o valor do token não é lido.

**A regra de desenho, sem exceção.** Nunca entram no log nem na trilha: `code`, `code_verifier`,
`access_token`, `refresh_token`, `id_token`, senha, `SECRET_KEY` e a chave privada RSA (Rivest–
Shamir–Adleman). A pessoa identifica-se pelo `sub`, nunca pelo e-mail.

**O identificador na falha de autenticação.** Registramos um resumo SHA-256 do identificador
tentado, em hexadecimal completo, e nunca o identificador em claro. O resumo é calculado sobre o
valor **como recebido**, sem `strip` e sem `lower`: `accounts.User.email` é único sob Postgres,
cuja unicidade é sensível a caixa, de modo que normalizar fundiria contas distintas numa mesma
linha da trilha. Duas tentativas contra o mesmo identificador produzem o mesmo resumo, que é o
que permite distinguir uma conta sob tentativa de muitas contas sondadas.

**A origem.** O campo `ip` sai de `REMOTE_ADDR`, e nunca de `X-Forwarded-For`. Não há proxy à
frente; um cabeçalho que ninguém impõe é um cabeçalho que qualquer cliente forja, e a trilha
registraria a origem que o atacante escolhesse.

**Auditar não nega autenticação.** Cada receptor tem o corpo capturado por um `except Exception`
que registra o erro no logger operacional, em `ERROR`. Uma falha ao auditar não pode derrubar um
login que ocorreu; a captura é silêncio, e por isso ela grita do outro lado.

**A suíte não escreve na trilha do ambiente.** `TEST_RUNNER` aponta para um `DiscoverRunner`
próprio, em `tests/runner.py`, que em `setup_test_environment()` reaplica o `dictConfig` com um
único valor trocado — o `filename` do handler `audit`, para um diretório temporário — e o remove
no teardown. Não há segunda configuração da aplicação: formatador, filtro, handler, receptores e
esquema são os mesmos objetos sob teste e em produção, e o caminho é exercitado inteiro, com
escrita real em arquivo real. O precedente é `DATABASES`, cujo nome o mesmo executor já
redireciona para `test_*`, e não um split de settings.

**O que esta decisão não decide:** retenção, poda e coleta externa da trilha; e os dois eventos
sem sinal instalado, criação de Application e revogação de token, que seguem fora.

## Consequências

Positivas:

- "Quem autenticou, quando, e qual RP recebeu token" passa a ter resposta, e a resposta sobrevive
  ao `docker compose down`, que é o que o log operacional nunca fez.
- Tentativa de senha errada passa a ser contável por conta, sem que nenhum e-mail seja gravado —
  o insumo que a limitação de taxa vai querer, quando existir, já começa a se acumular.
- A trilha é um arquivo JSON por linha, no mesmo esquema do log operacional e com o mesmo
  `request_id`: uma linha de auditoria e o traceback do mesmo pedido casam por igualdade.
- Nenhuma dependência nova e nenhum container novo; o custo é código próprio e uma variável.
- Um evento de negócio deixa de depender de leitura de tabela para ser reconstruído: o
  `app_authorized` registra a concessão no instante em que ela acontece, e não pelo estado que ela
  deixou.

Negativas:

- **A trilha guarda dado pessoal com retenção maior que a do log operacional, e não há poda.** O
  arquivo cresce indefinidamente num host que ninguém monitora. Retenção é explicitamente não
  decidida aqui, o que significa que a decisão está adiada, não resolvida.
- **Um SHA-256 de e-mail não é anonimização.** Quem tiver uma lista de candidatos confirma
  pertinência calculando o resumo de cada um. O que a escolha remove é o texto em claro, não a
  identificabilidade — e ela torna a investigação indireta: procurar por uma conta conhecida exige
  recalcular o resumo.
- `docker compose down -v` passa a destruir também a trilha, junto de `pgdata` e `redisdata`. É a
  mesma tecla, e agora leva a evidência junto dos dados.
- **A posse do diretório é de `root`, porque o container não tem `USER` dedicado.** No dia em que
  tiver — e o `Dockerfile` já marca essa revisão —, a configuração do logging falhará no boot por
  permissão de arquivo, com uma mensagem que fala de arquivo e não de `USER`.
- A escrita é síncrona e está no caminho do login e da emissão de token: um disco lento vira
  latência de autenticação.
- **Falha de escrita do handler é engolida pelo próprio `logging`**, que a manda para `stderr`. A
  trilha para de receber linhas e o sistema segue atendendo. É a falha silenciosa característica
  desta decisão, e por isso está em `docs/runbook.md`, seção 14.
- `app_authorized` é emitido em toda resposta 200 de `/o/token/`, o que inclui o grant de
  **refresh**: a trilha terá mais linhas do que houve consentimentos, e quem contar linhas para
  contar autorizações contará errado. O `client_id` e o `sub` continuam corretos.
- Ler `token.application.client_id` custa uma consulta a mais por emissão de token.
- **A lacuna de `docs/seguranca.md` não fecha inteira.** Criação de Application e revogação de
  token continuam sem registro, por ausência de sinal, e o documento tem de dizer o que fechou e o
  que continua aberto — declarar a lacuna fechada seria falso.
- O campo `ip` deixa de dizer a verdade no dia em que houver proxy à frente, e passará a registrar
  o endereço do proxy para todo mundo. É a mesma decisão já adiada para a chave de contagem do
  limitador de taxa: uma decisão, dois consumidores.
- Existe um `TEST_RUNNER` próprio, isto é, um objeto que só roda sob `manage.py test`. É
  infraestrutura de teste, roda em toda execução da suíte nas duas jornadas e não é ramo dormente
  — mas é uma peça a mais que alguém precisa entender antes de mexer em `LOGGING`.
- `AUDIT_LOG_PATH` derruba o boot e a suíte de todo ambiente já montado até que a linha seja
  acrescentada ao `.env`, que é untracked e não tem cópia.

## Alternativas consideradas

- **Registrar o identificador tentado em claro** — é o que torna a investigação direta, e é o que
  a maioria dos IdPs faz. Descartada porque gravaria e-mail de quem apenas errou a própria senha
  num arquivo com retenção maior que a do log operacional e sem poda decidida, contrariando a
  regra de desenho que a própria trilha existe para respeitar.
- **Truncar o resumo aos oito primeiros caracteres** — agruparia igual e ocuparia menos. Descartada
  porque introduz colisão sem comprar privacidade nenhuma: quem consegue inverter o resumo
  completo por dicionário inverte o truncado do mesmo jeito, e a colisão faz duas contas
  distintas parecerem a mesma.
- **HMAC do identificador com a `SECRET_KEY`, em vez de SHA-256 puro** — tornaria o ataque de
  dicionário inútil para quem não tem o segredo. Descartada por dois motivos: o adversário que o
  modelo de ameaças de `docs/seguranca.md` admite é "alguém com acesso ao host", que lê o `.env` e
  portanto a própria `SECRET_KEY`; e amarrar a trilha à `SECRET_KEY` faria uma rotação dela quebrar
  a comparabilidade de todo o histórico, em silêncio.
- **Trilha em tabela do Postgres** — consultável por SQL e coberta pelo backup do banco.
  Descartada porque a trilha passaria a depender do mesmo banco que ela precisa auditar quando ele
  falha, custaria modelo e migração em `accounts`, e continuaria morrendo com `down -v` do mesmo
  jeito.
- **Trilha no `stdout`, junto do log operacional** — nada de volume, nada de variável nova.
  Descartada porque é exatamente o que já existe e não serve: some no recreate, e afoga o
  `docker logs` que o `docker/entrypoint.sh` protege.
- **`if TESTING:` em `config/settings.py`, apontando o handler para `os.devnull`** — resolveria o
  isolamento da suíte sem `TEST_RUNNER`. Descartada porque criaria dois `LOGGING` no mesmo arquivo
  e faria do ramo de produção o caminho que a suíte nunca executa, que é a inversão exata que o
  docstring de `config/settings.py` recusa.
- **Substituir o handler por `NullHandler` durante a suíte** — mais simples que o diretório
  temporário. Descartada porque deixaria de exercitar a escrita real: nenhum teste poderia varrer a
  trilha em busca de campo proibido, que é a verificação que causa dano se falhar.
- **`post_save` no modelo de Application para cobrir a criação** — fecharia mais um item da lacuna.
  Fora do escopo deste bloco, e é decisão própria: sinal de modelo tem alcance diferente de sinal
  de autenticação, e alcança também criação por `loaddata` e por shell.
- **`syslog` ou `journald` do host** — traria rotação e retenção prontas. Descartada porque cria
  estado fora do repositório e quebra a promessa de clonar-e-rodar.
