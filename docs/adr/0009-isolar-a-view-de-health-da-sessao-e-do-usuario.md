# 0009. Isolar a view de /health da sessão e do usuário

## Status

Aceito — 2026-09-01

## Contexto

O IdP (Identity Provider) expõe /health como sinal de prontidão: ele verifica banco e cache de
verdade e é consumido pelo HEALTHCHECK do próprio container, que decide se o serviço está apto
a receber tráfego. O contrato de resposta é um JSON de três chaves — status, database e cache
—, sempre as mesmas em sucesso e em falha, com HTTP 200 quando tudo passa e 503 quando algum
componente falha, nomeando qual.

A sessão de login usa o backend cached_db sobre Redis, e o backend Redis nativo do Django
propaga ConnectionError em vez de degradar. Com o Redis inalcançável, todo request que carrega
a sessão falha — o que é o comportamento correto e desejado para um IdP, conforme a ADR
(Architecture Decision Record) 0005.

Daí nasce o problema desta decisão. A situação em que o /health mais precisa ser útil é
exatamente a situação em que o cache está fora. Se a própria request de health carregar a
sessão, a exceção de conexão sobe antes de a view executar qualquer verificação, e o endpoint
responde 500 com traceback em vez de 503 nomeando o cache. O orquestrador vê um serviço
unhealthy — o que é correto — mas perde a informação que separa um health de um sino: em qual
dos dois lugares procurar.

O carregamento de sessão não acontece por si só. Nenhum middleware da lista faz I/O de sessão
sem que alguém toque nela: o SessionMiddleware apenas instancia o store, que é preguiçoso, e só
grava na resposta se a sessão tiver sido modificada. Quem dispara a carga é a view — lendo
request.user, lendo ou escrevendo request.session, usando um decorator de autenticação, ou
renderizando um template cujos context processors fazem qualquer uma dessas coisas.

Existe uma saída tentadora e errada: capturar a exceção de cache e responder 200 assim mesmo,
ou configurar o cliente de cache para ignorar exceções. Ela produz um health verde sobre um IdP
que não atende request autenticado nenhum.

## Decisão

Vamos implementar /health como uma view pública que não toca em sessão, em request.user nem em
template.

Ela executa duas verificações independentes — uma query trivial no banco e um set seguido de
get no cache, comparando o valor devolvido com o gravado —, cada uma dentro do seu próprio
try/except, e monta a resposta com django.http.JsonResponse. Cada except escreve "error" na
chave do seu componente, força "status": "error" e o HTTP 503, e registra a exceção no logger,
que a ADR 0006 garante estar ligado ao stdout mesmo com DEBUG=False.

A distinção que a decisão fixa é entre capturar para reportar e mascarar. Capturar para
reportar é obrigatório: sem isso a resposta é um 500 opaco. Mascarar é proibido em qualquer
forma — responder 200 com o cache fora, omitir a chave do componente que falhou, capturar sem
refletir a falha no corpo, ou suprimir o erro na camada do cliente de cache.

O formato de três chaves é contrato de quem lê o corpo: alguém diagnosticando, ou um consumidor
futuro. O HEALTHCHECK do container não é um desses — ele decide pelo código de status —, e é
assim que deve permanecer: nenhuma probe pode passar a inspecionar o corpo, porque isso
transformaria ordem de chaves e espaçamento do JSON em contrato sem guarda nenhuma.

## Consequências

Positivas:

- Com o Redis fora, /health responde 503 nomeando o cache, que é a única resposta que poupa
  alguém de investigar Postgres e Redis um a um.
- A verificação diz respeito ao que a aplicação precisa para atender, não a se o processo está
  de pé: um health verde passa a significar algo. Significa menos do que parece, e o limite é o
  próprio SELECT 1 — ele prova conectividade, não capacidade. Um banco alcançável sem as
  tabelas do projeto, ou com migration pendente, responde 200 enquanto todo request real falha;
  o que fecha essa janela no container é o migrate do entrypoint, não este endpoint.
- A causa exata da falha — recusa de conexão, timeout, autenticação — sobrevive no log, ainda
  que o corpo de três chaves não a carregue.
- O endpoint responde a quem chega sem sessão e sem token, que é a condição do healthcheck
  executado de dentro do container.

Negativas:

- O isolamento é disciplina, não mecanismo, e as violações não custam todas o mesmo. Ler
  request.user ou renderizar um template não bastam para reintroduzir o 500: sem cookie de
  sessão — que é a condição da probe do container — session_key é None e o SessionStore não faz
  I/O nenhum. O que reintroduz é qualquer escrita de sessão, messages inclusive, e o sinal só
  aparece no dia em que o Redis cair, que é o pior dia para descobri-lo. Um `@login_required`
  acrescentado por hábito é pior ainda: a probe segue o 302 até a tela de login, recebe 200 e
  declara saudável um container em que verificação nenhuma rodou.
- /health fica sem autenticação, e revela a terceiros que alcancem a porta o estado de banco e
  cache. Aceito nesta fase: a exposição da porta é responsabilidade do proxy à frente, e um
  healthcheck autenticado não serviria ao orquestrador.
- O contrato de três chaves passa a ser público sem que nada o verifique. Mudá-lo não quebra o
  HEALTHCHECK do container, que lê apenas o código de status, e é justamente por isso que a
  mudança não produz sinal: quem consumir o corpo descobre pela chave que sumiu, no dia em que
  precisar dela.
- A verificação de cache escreve uma chave a cada chamada; num healthcheck com intervalo curto,
  isso é escrita constante, ainda que trivial.

## Alternativas consideradas

- **Renderizar a resposta por template** — daria uma página legível por humanos. Descartada
  porque arrastaria os context processors de auth e de messages, que tocam a sessão, e
  transformaria a falha de cache num 500 exatamente quando o diagnóstico importa.
- **Proteger /health com autenticação** — reduziria a exposição do estado interno. Descartada
  porque tornaria o endpoint inutilizável pelo healthcheck do container e, pior, faria o
  próprio ato de proteger carregar a sessão, quebrando o 503 pela mesma razão da alternativa
  anterior.
- **Um único try/except envolvendo as duas verificações** — menos código. Descartada porque a
  falha do primeiro componente esconderia o estado do segundo, e o corpo passaria a mentir por
  omissão justamente na chave que existe para localizar o problema.
- **Ignorar exceções de cache (IGNORE_EXCEPTIONS ou equivalente)** — daria um health estável.
  Descartada porque estabilidade aqui é falsidade: o IdP com Redis inalcançável não atende
  request autenticado nenhum, e a mesma supressão produziria escrita de sessão perdida em
  silêncio. Já rejeitada pela ADR 0005 e reafirmada aqui.
- **Healthcheck raso, respondendo 200 se o processo responde** — trivial e sem dependências.
  Descartada porque é pior que healthcheck nenhum: o orquestrador passa a confiar num sinal que
  não observa nada.
