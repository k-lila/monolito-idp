# 0010. Isentar /health do redirecionamento para HTTPS

## Status

Aceito — 2026-09-01

## Contexto

O endurecimento de transporte do projeto é governado por BEHIND_TLS_PROXY, e não por DEBUG (ADR
— Architecture Decision Record — 0006). Uma das chaves que essa variável liga é
SECURE_SSL_REDIRECT: com ela ativa, o SecurityMiddleware do Django responde 301 para o
equivalente em https:// a toda requisição que não seja segura, e faz isso em process_request —
antes de qualquer view executar.

O container publica sua prontidão por um HEALTHCHECK que bate em /health a partir de dentro de
si mesmo, em http, contra o Gunicorn, que fala texto claro. Essa requisição não atravessa o
proxy TLS (Transport Layer Security) e portanto não carrega X-Forwarded-Proto, que é o
cabeçalho de que SECURE_PROXY_SSL_HEADER depende para considerar a requisição segura. Do ponto
de vista do middleware, é uma requisição insegura como outra qualquer.

O resultado é um serviço eternamente unhealthy com a aplicação atendendo normalmente a quem
chega pelo proxy: a probe recebe 301, segue o redirecionamento, tenta um handshake TLS contra
um socket que fala HTTP em claro e falha ali. O orquestrador conclui que a aplicação está fora;
ela não está. O passo 11 do roadmap cataloga duas causas para esse mesmo sintoma — healthcheck
escrito com curl numa imagem slim, e ALLOWED_HOSTS sem localhost — e não tem esta terceira.

A falha está latente e não hipotética: o .env.example sai com BEHIND_TLS_PROXY=False, que é o
valor da jornada de sandbox, e o defeito aparece no primeiro ambiente que a ligar — isto é, no
primeiro ambiente com TLS de verdade, que é onde ele custa mais caro. O sinal que existe antes
disso engana: ligar a variável na jornada de construção deixa a suíte vermelha por 301, o que
se lê como "o .env quebrou os testes".

Há uma tensão real a resolver, e não uma correção óbvia. Redirecionar tudo para HTTPS é a
postura correta para um IdP (Identity Provider), em que toda requisição carrega credencial ou
token; a probe interna é a única requisição do sistema para a qual essa postura não faz
sentido, e qualquer saída consiste em abrir uma exceção para ela em algum lugar.

## Decisão

Vamos declarar SECURE_REDIRECT_EXEMPT = [r"^health$"] em config/settings.py,
incondicionalmente, isentando a rota /health — e apenas ela — do redirecionamento para HTTPS.

O padrão é ancorado nas duas pontas porque o Django o compara com request.path.lstrip("/"), e a
rota é registrada sem barra final (config/urls.py). A declaração é incondicional porque a lista
é inerte enquanto SECURE_SSL_REDIRECT for False; condicioná-la a BEHIND_TLS_PROXY acrescentaria
um ramo de configuração sem acrescentar comportamento.

A isenção alcança apenas o redirecionamento. HSTS (HTTP Strict Transport Security) continua
sendo emitido pelo SecurityMiddleware nas respostas a requisições seguras, e as flags Secure de
cookie continuam governadas por BEHIND_TLS_PROXY como antes; /health não emite cookie.

## Consequências

Positivas:

- O container passa a conseguir observar a própria prontidão com o endurecimento de transporte
  ligado, que é a configuração de qualquer ambiente com TLS real — desde que ALLOWED_HOSTS
  continue aceitando 127.0.0.1, que é a outra condição e não é fechada por esta decisão (ver
  Negativas).
- A mensagem de erro da probe volta a ser honesta. Sem a isenção, uma falha de banco ou de
  cache aparece no log de saúde do container como erro de handshake TLS, apontando para o lugar
  errado; com ela, aparece como HTTP 503.
- A exceção fica declarada num único lugar, ao lado da chave que a torna necessária, e não
  espalhada entre o Dockerfile e as settings.
- O Dockerfile permanece ignorante da configuração de proxy da aplicação: a probe é uma
  requisição HTTP comum, sem cabeçalho forjado.

Negativas:

- /health passa a responder em texto claro também a quem chega de fora, sem ser redirecionado.
  A ADR 0009 já aceitou que o endpoint é público e revela o estado de banco e cache; o que esta
  decisão acrescenta é que essa revelação deixa de exigir HTTPS. Quem puder observar a rede
  entre o cliente e o proxy vê o estado dos componentes em claro.
- A isenção é uma lista de expressões regulares, e uma expressão frouxa isenta mais do que se
  pretende sem produzir sinal nenhum. r"^health$" é estreito hoje; nada impede que alguém a
  alargue amanhã.
- O acoplamento entre a string do padrão e o path registrado em config/urls.py não tem
  mecanismo. Renomear a rota quebra a isenção em silêncio, e o sintoma que volta é o unhealthy
  eterno — o mesmo que esta decisão remove.
- Fica uma exceção declarada numa postura de segurança que se pretendia sem exceções, e quem
  ler apenas SECURE_SSL_REDIRECT = BEHIND_TLS_PROXY não saberá que ela existe.
- A isenção remove uma das condições para a probe funcionar com TLS ligado, não todas. A probe
  alcança a aplicação por http://127.0.0.1:8000/health e envia Host: 127.0.0.1:8000; com
  DEBUG=False, ALLOWED_HOSTS precisa listar 127.0.0.1 mesmo quando o IdP só é servido por um
  nome público. Quem estreitar a lista ao nome do proxy — leitura natural de quem põe TLS na
  frente, e o mesmo movimento que liga BEHIND_TLS_PROXY e troca a BASE_URL — recebe 400
  DisallowedHost e o unhealthy eterno volta, pela segunda das causas que o passo 11 já
  catalogava. As duas causas do mesmo sintoma são disparadas pela mesma mudança de ambiente, e
  esta decisão fecha apenas uma; a outra vive no README, que é o que o operador lê no momento
  em que erra.

## Alternativas consideradas

- **Mandar X-Forwarded-Proto: https na probe do HEALTHCHECK** — funciona, não exige tocar nas
  settings e é inerte quando BEHIND_TLS_PROXY é False, porque nesse caso
  SECURE_PROXY_SSL_HEADER é None e o cabeçalho é ignorado. Descartada por duas razões: o
  Dockerfile passaria a depender do nome e do valor do cabeçalho configurado nas settings, e
  uma troca desse nome devolveria o unhealthy eterno pela mesma porta; e a probe passaria a
  afirmar sobre o próprio transporte algo que é falso, num projeto cuja postura é preferir a
  falha alta à conveniência silenciosa.
- **Fazer a probe seguir o redirecionamento** — não é opção: urllib segue o 301, e o destino é
  um handshake TLS contra um socket que fala HTTP em claro. É precisamente o modo de falha que
  se quer remover.
- **Aceitar 301 como resposta saudável no HEALTHCHECK** — a mudança mais barata de todas, e a
  pior. O 301 é emitido pelo middleware antes da view: um healthcheck que o aceita não observa
  banco nem cache e vira o healthcheck raso que o passo 10 do roadmap proíbe por ser pior que
  healthcheck nenhum.
- **Desligar SECURE_SSL_REDIRECT** — eliminaria o problema e a proteção junto, deixando ao
  proxy a responsabilidade inteira pelo redirecionamento. Descartada porque troca uma exceção
  estreita e declarada por uma renúncia ampla, e porque a proteção em profundidade aqui custa
  uma linha.
- **Expor a prontidão por outra porta, servida por um processo à parte** — é o que se faz
  quando o endpoint de saúde não deve compartilhar a superfície pública. Descartada por
  desproporção: acrescenta um processo e uma porta ao container para evitar uma linha de
  configuração, num sistema que é deliberadamente um monólito de um processo (ADR 0006).
