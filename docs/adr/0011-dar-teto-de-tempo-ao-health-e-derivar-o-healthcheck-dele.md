# 0011. Dar teto de tempo ao /health e derivar o HEALTHCHECK dele

## Status

Aceito — 2026-09-01

## Contexto

A view /health verifica banco e cache de verdade, um try por componente, e responde 200 ou
503 nomeando quem falhou (ADR 0009). O container consome essa resposta como sinal de
prontidão.

Os dois componentes chegaram a esta fase com tetos de tempo assimétricos. O cache tem os
seus, declarados nas OPTIONS de CACHES: socket_connect_timeout e socket_timeout, ambos em
2 segundos, escolhidos deliberadamente para caber na janela do healthcheck do Redis. O
banco não tem nenhum. A distinção que motivou aqueles dois valores vale igualmente aqui: a
recusa de conexão devolve RST na hora, o except da view roda e o 503 sai; a falha que não
tem teto é a do servidor que aceita a conexão e não responde — pause do container, pressão
de memória, firewall que faz DROP.

Sem teto do lado do banco, essa falha não produz um 503 lento: produz uma requisição que
não termina. O Docker mata a probe pelo próprio timeout, o container vai a unhealthy — o
que está correto — mas o corpo que nomeia o componente nunca é montado e o logger.exception
da view nunca é alcançado. Some exatamente a informação que separa um health de um sino, e
o log fica mudo sobre a causa. Junto, um worker síncrono do Gunicorn fica preso até o
timeout dele, levando as outras requisições em voo naquele worker.

Há uma consequência de projeto que decide a questão, para além do risco em si. O timeout
do HEALTHCHECK precisa ser maior que o pior caso honesto da view, ou o 503 nunca é
observado — a probe morre antes de a resposta existir. Enquanto uma das metades da
verificação não tiver teto, não existe pior caso a partir do qual dimensionar esse número,
e qualquer valor escrito no Dockerfile é arbitrário.

Um pior caso honesto exige saber como os tetos se compõem, e a composição não é a soma
ingênua dos valores declarados. Três regras a governam, todas verificadas no código
instalado. Primeira: os dois tetos do cache são aditivos dentro de uma única operação —
redis/connection.py aplica socket_connect_timeout ao socket antes do connect e
socket_timeout depois dele, e o handshake que segue o connect já contém leitura
bloqueante, de modo que uma operação de cache pode queimar 2 segundos em cada fase.
Segunda: os dois tetos de connect são por endereço resolvido, não por URL — em redis-py o
settimeout está dentro do laço sobre o retorno de getaddrinfo, e a libpq documenta o mesmo
comportamento; hoje cada nome do compose resolve para um endereço, e é essa contingência,
não o código, que impede a multiplicação. Terceira, e é a que mais barateia o orçamento: a
metade do cache paga uma operação, não duas. A view executa cache.set e cache.get dentro do
mesmo try, então quando o set levanta, o get não chega a rodar. A medição feita quando os
tetos do cache foram introduzidos — 503 em 2,02 segundos com o Redis pausado — é a
confirmação empírica disso.

O regime de conexão do projeto delimita onde o teto do banco precisa estar. CONN_MAX_AGE
não é declarado, portanto vale o default 0: cada requisição abre uma conexão nova e a fecha
ao final. É na fase de conexão que o tempo mora. A query em si é SELECT 1, que não toca
relação nenhuma e não toma lock nenhum.

## Decisão

Vamos declarar connect_timeout = 2 nas OPTIONS da conexão default, em config/settings.py,
logo abaixo da leitura de DATABASE_URL, e dimensionar o HEALTHCHECK do container a partir
do pior caso que esse teto fecha.

O pior caso da view é de 6 segundos: 2 segundos na metade do banco, e 4 segundos na metade
do cache — uma única operação, com os dois tetos de 2 segundos aditivos entre a fase de
conexão e a primeira leitura bloqueante. Sobre esses 6 segundos a probe recebe timeout
interno de 7, uma folga de 1 segundo para a cadeia de middleware, os dois logger.exception
e a serialização da resposta. O HEALTHCHECK recebe timeout de 8 segundos, outra folga de 1
segundo, para que a mensagem de erro da probe seja emitida antes de o Docker encerrar o
processo — uma probe morta pelo orquestrador não deixa registro legível.

O intervalo permanece em 10 segundos, que já acomoda o timeout de 8 sem que este o
ultrapasse. As duas folgas cumprem funções distintas e nenhuma é ornamental: a de fora
protege a mensagem contra o Docker, a de dentro protege a resposta contra a própria probe.

Os tetos da aplicação não mudam para caber neste orçamento. O do banco não pode: 2 segundos
é o mínimo que a libpq aceita. Os do cache poderiam, mas incidem sobre toda requisição —
SESSION_ENGINE é cached_db e toca o cache a cada uma —, e encolhê-los para acomodar um
número do Dockerfile faria o orçamento da probe governar a robustez da aplicação.

O teto do banco é de conexão, não de statement. Não declaramos statement_timeout: com
conexão nova a cada requisição, a espera vive na conexão, e SELECT 1 não toma lock nem lê
relação — limitá-lo guardaria um cenário que não existe.

A view não é alterada. O contrato de três chaves da ADR 0009 segue intacto.

## Consequências

Positivas:

- Um banco que aceita conexão e não responde passa a produzir o 503 nomeando "database",
  com a exceção no log, em vez de uma probe morta sem registro.
- O timeout do HEALTHCHECK passa a ser um número derivado do comportamento da aplicação, e
  não um palpite: existe um pior caso a que ele responde, ele está escrito, e cada parcela
  dele aponta para a linha de configuração que a produz.
- Os dois componentes de /health passam a ter a mesma disciplina, o que torna a view
  legível como uma coisa só em vez de duas com regimes diferentes.
- Um worker do Gunicorn deixa de poder ficar preso por dezenas de segundos numa requisição
  de prontidão.

Negativas:

- Um Postgres que leve mais de 2 segundos para aceitar conexão passa a ser reportado como
  falho onde antes seria reportado como lento. O start_period do HEALTHCHECK cobre a
  janela de boot; fora dela, isso é sinal e não falso positivo — mas é uma escolha, e num
  host sobrecarregado ela pode surpreender.
- Seis números passam a estar acoplados em dois arquivos — três tetos nas settings, três no
  HEALTHCHECK — numa cadeia que nenhum mecanismo verifica: a soma dos tetos tem de caber no
  timeout da probe, que tem de caber no timeout do Docker, que tem de caber no intervalo.
  Quebrar qualquer elo reintroduz o problema inteiro sem produzir sinal distinguível do
  próprio problema.
- O orçamento depende da forma do bloco try da view, não só dos valores. A metade do cache
  custa uma operação porque o cache.get compartilha o try do cache.set e não executa quando
  este levanta. Separá-los em dois try, ou inverter a ordem, dobra essa metade para 8
  segundos e estoura o orçamento em silêncio — e essa é uma edição que parece uma melhoria
  de legibilidade.
- O orçamento cobre uma operação falha por componente, não uma sequência de operações
  lentas mas bem-sucedidas. Um Redis que responda cada round-trip logo abaixo dos 2 segundos
  faz o set concluir e o get falhar depois, e o total passa dos 7 segundos da probe. Fica
  fora do orçamento por decisão: é um regime que não se produz com pause nem com DROP, e
  cobri-lo custaria dobrar o tempo até o veredito de unhealthy em todo cenário real.
- Dois trechos de espera não têm teto nenhum e nenhuma configuração os alcança. O
  getaddrinfo que precede o connect do cache está fora de qualquer settimeout, e o SELECT 1
  não tem limite depois que a conexão foi estabelecida — este último é uma janela de corrida
  estreita, porque com CONN_MAX_AGE em 0 a degradação estacionária é capturada pela fase de
  conexão, mas é uma janela. Uma resolução de nome travada ou um Postgres que congele entre
  o connect e a query devolvem a probe morta sem corpo.
- Os tetos de connect são por endereço resolvido, e não por DATABASE_URL ou REDIS_URL:
  redis-py aplica o settimeout dentro do laço sobre getaddrinfo, e a libpq documenta o mesmo
  para connect_timeout. O orçamento de 6 segundos pressupõe um endereço por nome, o que hoje
  é verdade no DNS do compose e deixa de ser no dia em que um nome resolver A e AAAA — sem
  aviso e sem sinal distinguível.
- O teto vale para toda conexão de banco da aplicação, não só para a de /health. É o
  comportamento que queremos, mas a decisão foi tomada olhando um endpoint e passa a
  valer para todos.
- Nenhum teste alcança este comportamento. Exercitá-lo exigiria um socket que aceita
  conexão e nunca responde, e a suíte não tem essa infraestrutura; o mesmo custo já levou
  ao adiamento do teste equivalente do lado do cache.
- O tempo até o veredito de unhealthy piora num regime só, e não é o regime que esta
  decisão existe para tratar. A probe só queima o teto inteiro nas duas janelas sem teto
  listadas acima — resolução de nome travada, ou SELECT 1 congelado depois do connect —, e
  ali cada tentativa pode ocupar 8 segundos em vez de 5: com três tentativas e intervalo
  de 10 segundos, são cerca de 44 segundos até o container ser declarado fora, contra
  cerca de 35 antes. São exatamente os casos em que não existe 503 para ler, de modo que
  ali se paga a espera sem receber corpo nenhum. Nos cenários que o teto fecha o sinal se
  inverte: um banco que aceita conexão e não responde devolve o 503 em cerca de 2
  segundos, o que dá cerca de 26 segundos até o veredito, e os dois componentes pausados
  foram medidos em 4,03 segundos, cerca de 32 — ambos mais rápidos que os 35 de antes, e
  agora com o corpo que nomeia o componente. Quem for afinar failover deve ler os 44
  segundos como teto de um caso sem benefício, e não como preço do 503: encolher timeout,
  retries ou interval para recuperá-los devolve a margem zero que este orçamento fechou.

## Alternativas consideradas

- **Baixar os tetos do cache em config/settings.py para caber num orçamento menor** — o
  outro lado do mesmo trade-off, e o único capaz de encolher o pior caso, já que o teto do
  banco está no piso da libpq. Descartada porque esses tetos incidem sobre toda requisição
  do IdP e não só sobre a probe: com SESSION_ENGINE cached_db, um valor abaixo de 2
  segundos transforma um soluço do Redis em erro de sessão para quem está autenticando. O
  orçamento da probe passaria a governar a robustez da aplicação, que é a inversão exata da
  hierarquia certa. Subir os números do container custa apenas latência até um veredito que,
  no cenário em questão, ninguém está esperando com pressa.
- **statement_timeout no servidor, via a opção options da conexão** — limitaria a query em
  vez da conexão, e é o instrumento certo quando as conexões são persistentes. Descartada
  porque CONN_MAX_AGE é 0 e SELECT 1 não toma lock nem lê relação: o cenário que ela
  guardaria não se materializa neste projeto, e seria tratamento de erro para caso
  impossível.
- **Escrever o parâmetro na query string da DATABASE_URL** — não exigiria tocar nas
  settings, já que o django-environ transporta parâmetros de URL para OPTIONS. Descartada
  porque existem três cópias dessa URL — .env, .env.example e a sobrescrita em environment:
  do compose —, duas delas fora do alcance de quem alterar o valor, e a divergência entre
  elas não produz sinal.
- **Impor o teto dentro da view, por alarme ou thread** — daria um limite total em vez de
  um limite por componente, e tornaria o orçamento independente da forma do bloco try.
  Descartada por complexidade desproporcional e por mexer numa view cujo contrato a ADR
  0009 fixa deliberadamente simples.
- **Adiar o teto e dar folga generosa ao timeout do HEALTHCHECK** — o caminho de menor
  esforço. Descartada porque sem pior caso não há folga a calcular: o número seria
  arbitrário, e a probe continuaria morrendo antes do 503 nos casos em que o 503 é a única
  informação útil.
- **Não fazer nada, aceitando que o container vá a unhealthy de qualquer modo** — é
  verdade que o veredito final é o mesmo. Descartada porque o veredito não é o produto do
  endpoint: o produto é dizer em qual dos dois lugares procurar, e é exatamente isso que se
  perde quando a resposta nunca é montada.
