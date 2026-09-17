# 0012. Emitir o log operacional em JSON, com identificador de requisição e linha de acesso própria

## Status

Aceito — 2026-09-08

## Contexto

O bloco `LOGGING` de `config/settings.py` declara um handler `console` com `class` e `stream`, e
nenhum `formatters`. Sem formatador declarado, o `StreamHandler` usa o default `%(message)s`: as
linhas saem nuas, sem marca de tempo, sem nível e sem nome de logger. Log sem marca de tempo não
serve a coletor nenhum, não se ordena e não se correlaciona com nada.

Some-se que o `docker/entrypoint.sh` omite `--access-logfile` de propósito, e o comentário ali
registra a razão: uma linha a cada dez segundos de sonda afogaria o log em que a falha de
`migrate` e o traceback de um 500 precisam ser vistos. A consequência colateral está escrita em
`docs/runbook.md`: a ausência de registro de uma requisição não é prova de que ela não chegou. Um
fluxo de autorização que funcionou não deixa rastro nenhum.

Falta ainda a correlação. O container roda três workers `sync` do Gunicorn, e duas linhas
vizinhas em `docker compose logs app` podem ser de requisições diferentes, de workers diferentes,
sem que nada no texto diga isso. É o que separa um traceback de `django.request` da linha de
`oauth2_provider` do mesmo pedido.

Três forças delimitam a solução. A primeira é a regra de dependência que o repositório já
aplica: aceita-se dependência quando o código que ela substitui é grande e difícil de acertar, e
recusa-se quando são poucas linhas cujo formato queremos possuir. A segunda é a lista
`MIDDLEWARE`, que carrega uma regra escrita — o `CorsMiddleware` sempre no topo — cuja violação é
indetectável enquanto a allowlist de CORS (Cross-Origin Resource Sharing) estiver vazia. A
terceira é `docs/runbook.md`, que ensina a procurar linhas específicas em `docker compose logs
app`: mudar o formato do log desatualiza esse documento no mesmo commit em que a mudança entra.

## Decisão

Vamos emitir todo log da aplicação como um objeto JSON por linha, produzido por um formatador
próprio em `config/observabilidade.py`, e vamos correlacionar as linhas de uma mesma requisição
por um identificador gerado por um middleware do projeto.

O esquema de campos é contrato de leitura, e é este: `ts` (ISO-8601 em UTC), `level`, `logger`,
`request_id` e `msg` em toda linha; `exc` quando houver exceção; e os pares passados em `extra`
no topo do objeto, com as chaves fixas escritas por último, de modo que um `extra` nunca
sobrescreva o contrato. A serialização usa `default=str` e `ensure_ascii=False`: o único modo de
falha real é um objeto não serializável vindo de um `extra`, que sem isso levantaria dentro do
`logging` e faria o registro ser descartado com uma linha em `stderr`. O atributo `request`, que
o próprio Django anexa a toda resposta 4xx e 5xx, é excluído da varredura de `extra` — ele
carrega um `HttpRequest` inteiro, e não um dado.

O identificador é `uuid.uuid4().hex[:16]`, guardado num `contextvars.ContextVar`, sempre gerado
pelo IdP (Identity Provider) e nunca lido de cabeçalho de entrada, com `reset()` obrigatório em
`finally`. Ele é injetado por um `logging.Filter` instalado nos **handlers**, e não em cada
logger: as quatro entradas de `LOGGING` desembocam no mesmo `console`, e uma declaração alcança
as quatro, inclusive `django.request`.

O mesmo middleware emite uma linha de acesso por requisição, no logger `access`, com `route`
(o nome da rota, de `request.resolver_match.view_name`, nunca o caminho), `method`, `status` e
`duration_ms`. As rotas listadas em `ACCESS_LOG_EXCLUDED_ROUTES` — hoje só `health` — não
produzem linha nenhuma: é o que dá registro de requisição bem-sucedida sem reabrir o problema que
a omissão de `--access-logfile` fechou. O `--access-logfile` continua fora, e a decisão sobre
access log e sobre ruído continua sendo uma só.

O middleware fica no índice 1 de `MIDDLEWARE`, imediatamente abaixo do `CorsMiddleware` e acima
do `SecurityMiddleware`. Abaixo dele passam a ter identificador e linha de acesso o 301 do
`SecurityMiddleware`, os estáticos do WhiteNoise, o redirecionamento de `APPEND_SLASH` e o 403 do
CSRF (Cross-Site Request Forgery) — todas respostas que hoje não deixam rastro. Acima dele fica
apenas o `CorsMiddleware`, porque a regra do topo é escrita e o que se ganharia ali é registrar
respostas que ele não emite enquanto a allowlist estiver vazia.

O log operacional não carrega endereço de origem nem identificador de pessoa. Quem responde "de
que origem" é a trilha de auditoria, que tem outro destino e outra disciplina (ADR 0013).

## Consequências

Positivas:

- Toda linha passa a ter marca de tempo, nível e nome de logger, e o log passa a ser legível por
  ferramenta — o degrau de que retenção, coleta e busca dependem.
- Duas linhas do mesmo pedido são reconhecíveis como tais, inclusive entre workers, o que amarra
  o traceback de `django.request` à linha de `oauth2_provider` do mesmo request.
- Uma requisição bem-sucedida deixa rastro pela primeira vez, sem que a sonda de dez em dez
  segundos volte a afogar o log: a exclusão é por nome de rota, declarada.
- Respostas emitidas por middleware, que nunca aparecem em log de acesso de servidor porque não
  chegam à view, passam a aparecer — inclusive o 301 do `SecurityMiddleware`, que já custou uma
  investigação inteira (ADR 0010).
- Nenhuma dependência nova, nenhum container novo, e o esquema de campos é nosso: mudá-lo não
  depende de ninguém.

Negativas:

- O log deixa de ser legível a olho nu. Todo procedimento de `docs/runbook.md` que mandava
  procurar uma linha específica muda de idioma no mesmo commit, e quem opera precisa de `jq`.
- **O log do container passa a ser misto, e isso quebra o `jq` ingênuo.** As linhas do Gunicorn
  (boot, sinais, worker) e a saída de `migrate` e de `collectstatic` não atravessam o `logging` do
  Django e continuam em texto plano. `docker compose logs app | jq .` morre na primeira delas; a
  forma que funciona é `jq -R 'fromjson? | select(...)'`. Configurar o logger do Gunicorn exigiria
  um `config/gunicorn.py`, que está fora deste bloco.
- `LOG_LEVEL=WARNING` apaga a linha de acesso inteira, sem aviso nenhum. É coerente — a linha é
  log operacional e `LOG_LEVEL` é o botão do log operacional —, mas o efeito é uma capacidade que
  some sem sintoma.
- A preflight de CORS, quando houver allowlist, será respondida pelo `CorsMiddleware` acima do
  nosso: sai sem `request_id` e sem linha de acesso. Hoje é inerte, e no dia em que deixar de ser
  nada avisará — é o mesmo silêncio que a posição do `CorsMiddleware` já tem.
- Requisição que não resolve rota — estático servido pelo WhiteNoise, 404, o 301 do
  `SecurityMiddleware` — sai com `route` igual a `"-"`, e a linha de acesso não diz qual caminho
  foi tentado. Foi a troca escolhida para manter caminho e identificador fora do campo; para o
  404, o caminho está na linha que o próprio `django.request` emite, com o mesmo `request_id`.
- O `request_id` não sai em cabeçalho de resposta. Quem investiga com o navegador na mão não tem
  como pegar o identificador do pedido que acabou de fazer; precisa achá-lo pelo horário.
- Uma entrada a mais em `MIDDLEWARE`, cuja posição relativa nada verifica, num arquivo em que a
  posição errada de um vizinho já é indetectável por natureza.
- O formatador é nosso, e passa a ser mantido por nós: um atributo novo de `LogRecord` numa versão
  futura do Django entra como campo solto no JSON até que alguém o exclua da varredura.
- Custo por linha: um `json.dumps`; por requisição, dois `contextvars` e um `perf_counter`.
  Irrelevante nesta escala, e mensurável se um dia deixar de ser.

## Alternativas consideradas

- **`python-json-logger` 4.2.0** — `py3-none-any`, mantido, e já traz pronto o tratamento dos
  campos reservados do `LogRecord`. Descartada pela regra de dependência do projeto: são cerca de
  quinze linhas, e o esquema de campos é contrato que queremos possuir. É escolha legítima, e a
  troca seria uma dependência a mais por quinze linhas a menos.
- **`django-guid`** — faria o mesmo do middleware e do filtro, trazendo junto propagação entre
  serviços e integrações com bibliotecas que este monólito não tem.
- **`--access-logfile` do Gunicorn** — é o caminho óbvio e é exatamente o que o
  `docker/entrypoint.sh` recusou: reintroduziria a linha de sonda a cada dez segundos, e o
  formato seria o do Gunicorn, fora do esquema JSON e sem `request_id`.
- **Aceitar `X-Request-ID` de entrada** — é o que se faz quando há proxy ou serviço a montante
  que já gerou o identificador. Descartada porque não há nenhum: o cabeçalho seria controlado por
  quem chama, e a correlação passaria a ser escrita por terceiro.
- **Devolver o `request_id` num cabeçalho de resposta** — ajudaria quem depura pelo navegador.
  Descartada por ser superfície nova exposta a terceiro, sem consumidor declarado, num bloco cujo
  escopo é instrumento interno.
- **Instalar o filtro em cada logger, e não nos handlers** — quatro declarações onde uma basta, e
  um logger novo esqueceria o filtro em silêncio.
- **logfmt (`chave=valor`)** — mais legível a olho nu e sem `jq`. Descartada porque escapar valor
  com espaço e serializar traceback multilinha vira código de novo, e porque toda ferramenta de
  coleta considerada adiante lê JSON sem configuração.
