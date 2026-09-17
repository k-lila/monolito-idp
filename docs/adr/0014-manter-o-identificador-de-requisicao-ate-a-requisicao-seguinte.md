# 0014. Manter o identificador de requisição até a requisição seguinte, emendando a ADR 0012

## Status

Aceito — 2026-09-09

Emenda à ADR (Architecture Decision Record) 0012, que **permanece aceita e em vigor**. Esta
decisão substitui um único mecanismo daquela — o `reset()` do `ContextVar` no `finally` do
middleware — e a frase das Consequências que dele dependia. O formato JSON, o esquema de campos,
a linha de acesso, a exclusão por nome de rota e a posição do middleware no `MIDDLEWARE`
continuam valendo tal como a 0012 os fixou.

## Contexto

A ADR 0012 decidiu correlacionar as linhas de uma mesma requisição por um identificador guardado
num `contextvars.ContextVar`, posto por um middleware do projeto "com `reset()` obrigatório em
`finally`". O `reset` tinha uma razão declarada: o worker `sync` do Gunicorn atende o pedido
seguinte no mesmo contexto, e sem ele o identificador vazaria de uma requisição para a outra.

A execução da suíte mostrou que aquele `finally` roda cedo demais. `BaseHandler.get_response`
(`django/core/handlers/base.py:136-150`) chama a cadeia de middleware e, **depois que ela
inteira retornou**, chama `log_response` para toda resposta com status igual ou superior a 400.
O `reset` já aconteceu quando essa linha é emitida, e ela sai com o sentinela `-`.

O alcance não é o de um caso de borda. São 404, 503 e os 400 que uma view devolve sem levantar
exceção — no caso deste IdP (Identity Provider), as guardas do servidor de autorização
(`redirect_uri` divergente, `code_challenge` ausente, método `plain`), o `/health` degradado, o
`DisallowedHost` e o 404 da relying party que procura a descoberta na forma da RFC 8414. Quatro
das treze entradas de sintoma de `docs/runbook.md` vivem exatamente nessas linhas. O que
continua correlacionado é o 500 e o que a cadeia registra por dentro — `response_for_exception`,
`http_method_not_allowed` —, isto é, justamente o caso que já traz traceback e se acha pelo texto.

O agravante é de leitura. O sentinela `-` é o mesmo das linhas de arranque e das de comando de
`manage.py`: as linhas órfãs não apenas se separam do seu pedido, fundem-se entre si e com o
ruído de boot, e um filtro por `request_id` não isola nenhuma das três populações.

Duas afirmações escritas ficaram falsas: o comentário de `config/observabilidade.py`, que
promete que para o 404 o caminho está na linha do `django.request` "com o mesmo `request_id`", e
a linha de `docs/runbook.md` que diz que toda linha de um mesmo pedido carrega o mesmo
identificador — que é o que quem opera lê durante um incidente.

Há uma restrição estrutural que elimina a saída óbvia: **nenhuma posição no `MIDDLEWARE` alcança
o `log_response`**, porque ele roda acima da cadeia inteira. O problema não é de ordem entre
middlewares; é do tempo de vida do valor.

## Decisão

Vamos remover o `reset()` do `finally` e deixar que cada requisição **sobrescreva** o
identificador na entrada. O `try/finally` desaparece com ele, porque só existia por essa razão.

O tempo de vida do identificador passa a ser: **da entrada de uma requisição até a entrada da
seguinte, no mesmo contexto.** Requisições distintas continuam recebendo identificadores
distintos, que é a propriedade que o `reset` protegia; o que muda é que a janela cobre também o
que o Django registra depois que a cadeia retornou.

O sentinela `-` ganha um significado preciso e único: processo que ainda não atendeu requisição
nenhuma — arranque, `migrate`, `collectstatic`, comando de `manage.py`.

## Consequências

Positivas:

- Toda resposta 4xx e 5xx passa a ter a sua linha de `django.request` correlacionada ao pedido
  que a produziu. É a correlação exatamente onde o incidente acontece, e era o caso que faltava.
- O comentário de `config/observabilidade.py` e a frase de `docs/runbook.md` voltam a ser
  verdadeiros sem serem rebaixados: a correção repara a promessa em vez de reescrevê-la.
- `-` deixa de ser lata de lixo. Filtrar por ele passa a isolar uma população só, a de arranque,
  o que antes era impossível.
- Uma peça a menos: sem `try`, sem `finally`, sem token de `reset` para guardar.

Negativas:

- **Num processo que já atendeu alguma requisição, uma linha emitida fora de requisição carrega
  o identificador da última.** É correlação falsa, e correlação falsa é pior que correlação
  ausente, porque nada a distingue de uma correta. No container não há código que registre entre
  um pedido e o seguinte — o laço do Gunicorn tem handlers próprios e não atravessa o nosso
  filtro —, mas sob `manage.py test` há: `Client.login()` dispara `user_logged_in` fora de
  qualquer requisição HTTP, e há caso que chama view diretamente com `RequestFactory`. As linhas
  que esses caminhos produzem saem carimbadas com o pedido anterior.
- Decorre disso uma armadilha de teste: um caso que asserte `-` para linha emitida fora de
  requisição passa isolado e falha depois de qualquer caso que faça uma requisição no mesmo
  processo. Seria dependência de ordem, contra o AC-12.
- A propriedade "o identificador identifica a requisição" enfraquece para "identifica a última
  requisição vista neste contexto". A diferença é invisível enquanto todo registro nascer dentro
  de uma requisição, e é preciso lembrar dela no dia em que houver tarefa em segundo plano,
  worker assíncrono ou thread própria — os três reabrem o problema com força total.
- A decisão vive numa emenda, e não no arquivo que o leitor abre primeiro. Quem ler a ADR 0012
  isolada lerá um mecanismo que caiu. O que fecha isso é o índice de `docs/arquitetura.md`, que
  marca a 0012 como emendada — mecanismo de documentação, não de código.

## Alternativas consideradas

- **Envolver a aplicação no nível WSGI (Web Server Gateway Interface), em `config/wsgi.py`,
  pondo e tirando o identificador em volta de `get_response` inteiro** — resolve a causa em vez
  do sintoma, cobre o `log_response` e preserva o `reset`. Descartada porque `django.test.Client`
  não passa por ali: o `ClientHandler` é chamado direto, sem WSGI. O wrapper nunca seria
  exercitado pela suíte, e a correlação inteira passaria a ser um caminho que só roda em
  produção — ou conviveriam dois mecanismos para uma coisa só, um deles morto sob teste. É a
  figura que a ADR 0013 recusou ao fixar que o `TEST_RUNNER` troca um caminho de arquivo e nada
  mais, para que os objetos sejam os mesmos no teste e em produção.
- **Conviver com a limitação, nomeando-a** — custo zero de código. Descartada porque a limitação
  cai sobre a superfície de diagnóstico inteira deste IdP, e porque o AC-02 precisaria ser
  emendado para caber num defeito de desenho, que é a forma irmã de ajustar teste para passar
  sobre comportamento errado.
- **Acrescentar o caminho à linha de acesso quando o status for maior ou igual a 400**, tornando
  a nossa linha autossuficiente — mitiga o 404 e não resolve nada: a linha órfã do
  `django.request` continua saindo, continua com `-` e continua fundida com o ruído de arranque.
- **Marcar o valor na saída, por exemplo com um sufixo, para distinguir "cauda da requisição" de
  "resíduo"** — quebraria o filtro por igualdade que o próprio AC-02 descreve, em troca de uma
  distinção que ninguém pediu.
- **Resetar por um receptor de `request_finished`, que roda depois do `log_response`** — cobre a
  janela e mantém o `reset`. Descartada por desproporção e por fragilidade: exigiria guardar o
  token do `ContextVar` em algum lugar por requisição, e o sinal é justamente um dos que o
  cliente de teste desconecta e reconecta em volta do `close()` da resposta.
