# 0016. Limitar a taxa na superfície de autenticação

## Status

Aceito — 2026-09-10

## Contexto

As três portas de autenticação do IdP (Identity Provider) aceitam tentativas sem teto.
`/accounts/login/` é a `LoginView` pronta do Django e não conta nada. `/o/token/` e
`/o/authorize/` são `TokenView` e `AuthorizationView` do `django-oauth-toolkit`, e o toolkit **não
traz gancho de throttle nenhum** — verificado por varredura do pacote instalado, zero ocorrências
de `throttle`, `ratelimit` ou `rate_limit` em `oauth2_provider/`. Força bruta contra uma conta,
credential stuffing e varredura de `code` custam ao atacante apenas tempo de rede. O único sinal
que existe é a trilha de auditoria da ADR (Architecture Decision Record) 0013, que registra depois
do fato e não impede nada.

Duas superfícies, dois mecanismos possíveis. A tela de login passa por `authenticate()`, onde há
sinal instalado e ponto de interceptação natural. Os dois endpoints de `/o/` não passam: o
authorize é autenticado por sessão e o token por credencial de cliente, e nenhum dos dois chama
`authenticate()` com credencial de pessoa.

Três propriedades do terreno decidem o resto.

A primeira: o projeto **não tem rota de recuperação de senha**, e a ausência é deliberada e provada
em `tests/test_password_reset_urls.py`. Um bloqueio sem prazo, que é o default da biblioteca
candidata, só terminaria por ação manual de quem opera.

A segunda: `config/settings.py` **nunca declarou `AUTHENTICATION_BACKENDS`**. Declarar a lista
substitui o default do Django, e esquecer `ModelBackend` ao lado do backend novo tranca todas as
contas de uma vez, com o sintoma de uma senha correta recusada.

A terceira: o contador. Um contador em cache não volta com o rollback do `TestCase`, e a suíte fica
dependente de ordem. Um contador em banco volta. E o cache `default` deste projeto guarda também a
cópia quente da sessão (ADR 0005), de modo que qualquer limpeza grosseira dele alcança as sessões.

## Decisão

Vamos limitar a taxa nas três portas com **dois mecanismos**, cada um na superfície onde encaixa.
A tela de login é a única onde os dois encaixam, e ali os dois agem, com papéis distintos: um
responde por quem está bloqueado, o outro por quanto custa tentar.

**Na tela de login, `django-axes`.** Ele intercepta o caminho de `authenticate()`, conta por
tentativa falha e **denuncia a própria instalação incompleta**: `axes/checks.py` registra checks
que acusam middleware ausente, backend ausente, `AXES_LOCKOUT_PARAMETERS` sem `ip_address` e
backend de cache incompatível. Denunciam, e não reprovam — todos são `Warning` (`axes.W001` a
`axes.W006`), e `manage.py check` os imprime com código de saída **zero**; só quebram o comando
com `--fail-level WARNING`. O erro de configuração passa a estar escrito na saída do comando, e
para quem só lê o código de saída continua invisível.
`AUTHENTICATION_BACKENDS` passa a existir com `AxesStandaloneBackend` primeiro e
`django.contrib.auth.backends.ModelBackend` em seguida — o Standalone não herda do ModelBackend e
existe para quem já lista o backend real ao lado; primeiro na ordem porque recusa a conta bloqueada
antes de a senha ser verificada.

**Os números, e a razão de cada um.** Teto de **5 tentativas falhas**, e não o default 3: três
erros trancam quem digitou errado com a tecla de maiúsculas presa, e cinco ainda deixam o espaço
de busca inviável. Prazo de **15 minutos**, e nunca o default `None`, que é bloqueio sem prazo: sem
rota de recuperação de senha, um bloqueio sem prazo transfere a quem opera todo engano de quem usa.
Quinze minutos limitam a vinte tentativas por hora. E o prazo é **móvel**, contado da última
tentativa e não da primeira falha: `AXES_RESET_COOL_OFF_ON_FAILURE_DURING_LOCKOUT` tem default
`True` (`axes/conf.py:164`), e cada falha que chega com a conta já trancada reinicia os quinze
minutos. Quem se enganou e parou de tentar recupera o acesso sozinho; quem insiste adia o próprio
fim, e sob ataque sustentado a conta fica fora enquanto o ataque durar — ali a saída não é
esperar, é `axes_reset_username`.
Contagem por **conta e por origem separadamente** — `[["username"], ["ip_address"]]`, e o que
separa "conta OU origem" de "o par das duas" é o **número de elementos** da lista, não o fato de
serem listas: `get_client_parameters` (`axes/helpers.py:285-293`) faz de cada elemento um filtro
independente, de modo que a lista plana `["username", "ip_address"]` é idêntica a esta, e quem
conta pelo par é `[["username", "ip_address"]]`, com um elemento só — porque as duas ameaças são
distintas: uma senha adivinhada contra uma conta, e uma lista de contas sondada de uma origem.
Contador zerado no login bem-sucedido, para que erros espaçados ao longo de semanas não somem
contra quem nunca esteve sob ataque.

**Em `/o/token/` e `/o/authorize/`, um middleware próprio**, `config/limites.py`: janela fixa de 60
segundos, teto de **120 requisições por origem e por endpoint**, chave em cache formada pela origem
da ADR 0015 e pelo caminho. Cento e vinte por minuto é duas por segundo sustentadas por uma única
origem — uma ordem de grandeza acima do pico plausível de uma sandbox de host único, e ordens de
grandeza abaixo do que uma varredura de `code` precisaria para ter chance. O fim do bloqueio é o
fim da janela: no máximo sessenta segundos, sem ação de ninguém. A resposta é 429 com
`Retry-After`.

**E o mesmo middleware limita `/accounts/login/` a 60 requisições por minuto e por origem.** Quem
digita senha faz cinco a dez tentativas por minuto no pior caso, e sessenta é uma ordem de
grandeza acima de todo uso legítimo de uma tela de login vinda de uma origem só. O teto fica
**acima** do teto de cinco falhas do axes de propósito: a semântica de segurança — quem está
bloqueado, por quanto tempo, por conta ou por origem — continua sendo toda do axes, e este teto
existe só para pôr limite no **custo** de cada tentativa, que a seção `Consequências` mede. Sem
ele, um laço de `curl` paga aquele custo indefinidamente, já bloqueado e sem nunca parar.

**Cache indisponível faz o limitador falhar aberto.** Com o Redis inalcançável, o middleware
captura o erro do cliente de Redis, registra uma linha em `WARNING` no log operacional e deixa a
requisição seguir. O que se troca está dito: durante a queda não há teto nenhum, em nenhum dos três
caminhos. A alternativa seria deixar a exceção subir, e ela é pior — até este limitador existir,
`/o/token/` não tocava o Redis, porque é autenticado por credencial de cliente e nunca lê
`request.session`, de modo que o `SessionMiddleware` com `cached_db` não chegava a ler nada;
deixar subir transformaria toda queda de cache em 500 num endpoint que antes atravessava a queda
inteiro. Capturam-se as duas exceções do cliente de Redis — conexão recusada e servidor que não
responde —, nunca `Exception`, para que defeito nosso continue aparecendo.

**O backend de cada contador.** O do axes vai para o **banco**, que é o default dele: o
rollback do `TestCase` o limpa entre casos, e a independência de ordem da suíte deixa de depender
da disciplina de quem escreve teste. O do middleware vai para o **cache**, porque é contagem de janela
curta que não merece uma tabela, e o zeramento entre casos é explícito — o módulo expõe a função
que forma a chave, e a suíte apaga o que ela mesma encheu, sem `clear()`, que faria `FLUSHDB` e
levaria as sessões junto.

**Os tetos e os prazos são literais em `config/settings.py`, não variáveis de ambiente.** Não são
segredo, não variam por ambiente, e uma variável nova sem default derrubaria o boot e a suíte de
todo ambiente já montado — o `.env` é untracked e não tem cópia. Política vive no código
versionado, com a razão ao lado. Como consequência, os tetos respondem a `override_settings`, e um
dicionário vazio desliga o middleware pelo mesmo caminho que toda requisição de caminho não
limitado já percorre, sem ramo especial.

**O rastro.** O bloqueio do login entra na trilha de auditoria como um quinto receptor,
`user_locked_out`, com `identifier_sha256`, `ip` e `outcome: "blocked"` — amplia o conjunto de
eventos da ADR 0013 sem tocar no esquema de campos dela, e respeita a mesma regra de desenho:
nunca o e-mail em claro, nunca credencial. A recusa do middleware vai para o log operacional, em
`WARNING`, e não para a trilha — nos três caminhos, o de login inclusive: ele roda acima do
`SessionMiddleware` e não lê o corpo da requisição, de modo que não há pessoa a nomear, e uma linha
sem `sub` degradaria o que a trilha afirma. O cache indisponível deixa o mesmo rastro, em `WARNING`
e com `outcome: "throttle_unavailable"`. O logger `axes` é declarado em `LOGGING` no nível `ERROR`, porque as mensagens
próprias dele carregam o identificador tentado em claro.

## Consequências

Positivas:

- As três portas passam a ter teto, e o teto é o primeiro controle deste projeto que **impede** em
  vez de registrar.
- `manage.py check` passa a **denunciar** a configuração incompleta do limitador: middleware
  ausente, backend ausente, backend de cache incompatível. São `Warning`, e o comando sai com
  código zero — o erro passa a estar escrito na saída, e continua invisível para quem só olhe o
  código de saída ou rode o comando como gate.
- O `/admin/login/` fica protegido de graça, pelo mesmo caminho de `authenticate()`.
- Nenhum teste existente precisa de ajuste por causa do login: nenhum caso da suíte faz cinco
  falhas seguidas, e o contador em banco volta com o rollback. A quebra que a ficha 2.1 previa em
  `tests/test_login_view.py` não se materializa.
- O fluxo Authorization Code legítimo não chega perto do teto de `/o/`, e o fim de todo bloqueio
  daquele endpoint é automático.

Negativas:

- **Contar por conta permite negação de serviço dirigida.** Quem souber o e-mail de alguém pode
  mantê-lo fora por quinze minutos, indefinidamente, sem nunca acertar uma senha. É o custo
  inerente do AC-01, e o prazo curto é a única mitigação — não há segundo fator nem allowlist a
  que recorrer.
- Dependência nova, com as migrações e as tabelas dela, e **quatro a cinco consultas ao Postgres
  a cada tentativa falha** no caminho do login — bloqueada ou não. São, em
  `axes/handlers/database.py:139-246`, um DELETE de limpeza, um `select_for_update`, um UPDATE
  com dois `Concat` e dois SELECT de agregação. Com o prazo móvel, a tentativa que chega com a
  conta já bloqueada reescreve `attempt_time` e com isso escapa da limpeza automática de
  `clean_expired_user_attempts`: a linha do ataque em curso cresce cerca de 130 bytes por
  tentativa, e cada UPDATE a reescreve inteira. É este custo, e não a semântica de segurança, que
  o teto de requisição de `/accounts/login/` limita.
- **Duas mecânicas de limitação em vez de uma**, com defaults, vocabulário e diagnóstico
  diferentes. Quem operar precisa saber qual das duas barrou — e na tela de login as duas agem
  sobre o mesmo tráfego, uma respondendo 429 com o template de bloqueio e a outra 429 com JSON.
- O contador do middleware vive no cache e não volta com o rollback do `TestCase`. A
  consequência que esta ADR previa aqui — um teste novo que tocasse `/o/` ou `/accounts/login/`
  sem zerar contador falhando com 429 numa asserção sem relação nenhuma com limitação — não se
  materializa: uma decisão posterior do `quality-assurance` esvaziou `RATE_LIMIT_POR_CAMINHO`
  para a suíte inteira em `tests/runner.py`, guardando o valor de produção e repondo-o no
  teardown. A dependência de disciplina explícita sobrou nos casos que reativam o limitador por
  `override_settings`: são eles que apagam as próprias chaves.
- A janela fixa admite, na borda entre duas janelas, o dobro do teto num instante. Irrelevante
  contra varredura sustentada, e é o preço de não guardar uma lista de marcas de tempo por chave.
- O `Retry-After` informa a janela inteira, e não o tempo restante: o `RedisCache` do Django não
  expõe o TTL de uma chave. É um limite superior, e quem esperar por ele espera demais.
- A recusa do middleware sai em JSON também em `/o/authorize/` e em `/accounts/login/`, que são
  endpoints que o navegador visita. Uma superfície humana recebendo corpo de máquina.
- **O nível `ERROR` no logger `axes` apaga linhas de diagnóstico de terceiro.** Foi escolhido para
  manter e-mail fora do stdout, e o preço é que a investigação passa a depender da trilha própria.
- O limitador do middleware conta requisições, não recusas: uma vez sobre o teto, um cliente
  legítimo da mesma origem é recusado junto do atacante. Atrás de um proxy, isso só não vira dano
  coletivo por causa da ADR 0015.
- **Queda do Redis desliga o limitador por inteiro**, sem teto nenhum em nenhum dos três caminhos
  enquanto durar. É o preço deliberado de não converter queda de cache em 500, e o único aviso é
  uma linha em `WARNING` por requisição no log operacional.

## Alternativas consideradas

- **`django-ratelimit` para as três portas** — decorador simples, sem migração e sem backend de
  autenticação novo. Descartada por duas razões: não tem noção de conta bloqueada, só de taxa por
  chave, e o AC-01 pede bloqueio por conta; e aplicá-lo às views do toolkit exigiria sobrepor
  rotas que `oauth2_provider.urls` já registra e que a descoberta monta por `reverse()`. Havia uma
  terceira, e ela caiu: a de que o axes verificaria a própria instalação e ele não. Os checks do
  axes apenas denunciam, como a seção `Decisão` registra, de modo que a diferença entre as duas
  bibliotecas nesse ponto é de aviso impresso, não de comando reprovado.
- **Subclassear `TokenView` e `AuthorizationView` e registrar as rotas antes do `include`** —
  daria o teto sem middleware novo. Descartada porque deixaria duas entradas de URLConf para o
  mesmo caminho, uma delas inalcançável, e porque `docs/arquitetura.md` registra que nenhum método
  de protocolo do toolkit é sobrescrito neste projeto.
- **Estender o axes aos endpoints de `/o/`** — um mecanismo só. Descartada porque o axes age no
  caminho de `authenticate()`, e nenhuma das duas views passa por lá.
- **Contador do login em cache (`AxesCacheHandler`)** — mais rápido, sem migração. Descartada
  porque não volta com o rollback do `TestCase`: a suíte ficaria dependente de ordem, e a limpeza
  entre casos alcançaria o cache que guarda a sessão.
- **Contar apenas as recusas em `/o/`, e não todas as requisições** — o fluxo legítimo nunca
  consumiria contador, e a suíte ficaria imune por construção. Descartada porque muitas recusas do
  authorize são 302 com `error=` no `Location`, e não 4xx: contar por status perderia parte do que
  interessa, e parsear o `Location` acoplaria o middleware ao protocolo.
- **Tetos e prazos vindos do `.env`** — ajustáveis sem recompilar. Descartada porque não variam por
  ambiente, não são segredo, e uma variável nova sem default derruba todo ambiente já montado, como
  `AUDIT_LOG_PATH` derrubou.
- **Bloqueio sem prazo, o default do axes** — mais seguro contra ataque persistente. Descartada
  porque este projeto não tem rota de recuperação de senha, e todo engano viraria chamado para
  quem opera.
- **Captcha ou segundo fator** — atacam o mesmo problema com muito mais eficácia. Fora do escopo
  deste bloco, e ambos exigem decisão própria sobre dependência externa e sobre o que se envia a
  terceiro.
