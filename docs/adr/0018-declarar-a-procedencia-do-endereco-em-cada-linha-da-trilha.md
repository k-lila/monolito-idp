# 0018. Declarar a procedência do endereço em cada linha da trilha

## Status

Aceito — 2026-09-13

## Contexto

A ADR (Architecture Decision Record) 0015 concentrou a leitura de origem numa função só e
terminou com uma obrigação nominal: "o Bloco C não pode ligar `BEHIND_TLS_PROXY` sem antes
decidir o versionamento da linha da trilha". A razão está escrita ali e é aritmética: ligar a
variável troca, na mesma tecla, o significado do campo `ip` da trilha de auditoria e a chave do
limitador de taxa. A trilha é um arquivo append-only, gravado por `WatchedFileHandler` em modo
`"a"` desde a ADR 0013, sem retenção e sem poda decididas. O instante da troca não fica
registrado em lugar nenhum, e nada na linha distingue as duas populações: depois da troca, uma
investigação que conte origens distintas sobre o arquivo inteiro soma duas grandezas
diferentes, e o erro não tem sintoma.

A função de `config/origem.py` tem hoje três desfechos, e não dois. Com a variável falsa,
devolve `REMOTE_ADDR`. Com ela verdadeira e o cabeçalho presente com saltos suficientes,
devolve o salto contado a partir da direita. Com ela verdadeira e o cabeçalho ausente ou mais
curto que o declarado, cai de volta em `REMOTE_ADDR` — que, atrás de um proxy, é o endereço do
proxy para todo mundo. A ADR 0015 registra esse terceiro desfecho como consequência negativa em
negrito, "exatamente a falha que ela existe para impedir", e ele não emite sinal nenhum.

Duas restrições cercam a solução. A primeira: a ADR 0013 fixou o esquema de campos da linha e é
imutável. A segunda: o arquivo já gravado não pode ser tocado — reescrevê-lo destruiria a
propriedade que faz dele evidência.

Há um fato que a solução pode usar: **a variável nunca foi ligada em ambiente nenhum**. É o que
a ADR 0015 proibiu e o que este bloco respeita. Toda linha já gravada é, portanto,
`REMOTE_ADDR`, por construção e não por memória de alguém.

## Decisão

Vamos acrescentar a cada linha da trilha um campo `ip_src`, que declara de onde veio o valor do
campo `ip` daquela linha, com três valores: `remote_addr`, `forwarded` e
`remote_addr_fallback`.

**Onde o valor nasce.** `config/origem.py` ganha `origem_e_procedencia(request)`, que devolve o
par `(endereço, procedência)` calculado no mesmo percurso, e `origem_da_requisicao` passa a ser
a projeção dela no primeiro elemento. A assinatura e o tipo de retorno de
`origem_da_requisicao` não mudam: ela é contrato de string do `django-axes` em
`AXES_CLIENT_IP_CALLABLE` e import direto de `config/limites.py`. O valor e a sua procedência
não podem divergir, porque são o mesmo cálculo — a mesma propriedade que a ADR 0015 comprou
para o endereço.

**Quem grava.** `accounts/auditoria.py`, nos cinco receptores, gravando `ip` e `ip_src` lado a
lado. O log operacional não recebe o campo: ele vive no `stdout`, que é efêmero e recriado com
o container, e o problema que esta decisão resolve é o de um arquivo que sobrevive.

**O terceiro valor.** `remote_addr_fallback` não é exigido pela distinção entre as duas
populações: os dois primeiros valores já bastariam. Ele entra porque custa nada e porque
converte a falha silenciosa da ADR 0015 numa marca em toda linha — atrás de um proxy, uma
trilha em que todas as linhas dizem `remote_addr_fallback` denuncia um cabeçalho que não está
chegando, coisa que hoje só apareceria como "todo mundo tem o mesmo IP".

**O que a ausência do campo significa.** Linha sem `ip_src` é linha escrita antes desta
decisão, e o seu `ip` é `REMOTE_ADDR`. A afirmação é sustentada pela proibição da ADR 0015, e
não por memória externa: a variável de proxy não foi ligada em ambiente nenhum antes de este
campo existir, e a ordem de implementação deste bloco põe o campo antes da variável.

**Relação com a ADR 0013.** Esta decisão **estende** o esquema de campos daquela ADR com um
campo novo; não redefine nenhum campo existente, não altera o significado de `ip` em linha
nenhuma já gravada e não toca o arquivo. A extensão é o modo de crescer que a ADR 0012 declarou
ao fixar que "um `extra=` acrescenta campo, nunca sobrescreve o contrato de leitura". A
ADR 0013 não é editada.

## Consequências

Positivas:

- O arquivo passa a responder sozinho, linha a linha, a que população cada `ip` pertence. Não
  há instante a lembrar nem documento a consultar.
- A resposta é por linha, e não por posição no arquivo: ela sobrevive a concatenação, a
  rotação externa, a cópia parcial e a ordem de escrita de três workers.
- O valor e a procedência não podem divergir, porque saem do mesmo cálculo.
- A falha silenciosa mais cara da ADR 0015 — cabeçalho ausente atrás do proxy — passa a deixar
  marca em toda linha, em vez de nenhuma.
- O contrato de string do `django-axes` fica intacto: nada em terceiro precisa saber deste
  campo.

Negativas:

- O esquema da linha cresce, e quem escreveu ferramenta de leitura sobre o esquema da ADR 0013
  vê um campo novo. É acréscimo, não quebra, mas é acréscimo num contrato de leitura.
- Cada linha da trilha fica alguns bytes maior, num arquivo que já cresce indefinidamente e
  cuja poda continua não decidida — a negativa que a ADR 0013 registrou e que esta agrava um
  pouco.
- "Ausência do campo significa `remote_addr`" é uma regra que vale por causa de uma proibição
  respeitada. Se alguém tiver ligado `BEHIND_TLS_PROXY` num ambiente qualquer antes disto,
  contra a ADR 0015, as linhas daquele período são indistinguíveis e não há como recuperá-las.
- As linhas de WARNING de `config/limites.py` continuam gravando `ip` sem procedência. São
  operacionais e efêmeras, mas é a mesma ambiguidade num segundo lugar, e ninguém a fechou.
- Um terceiro valor de vocabulário obriga quem lê a saber que `remote_addr` e
  `remote_addr_fallback` são ambos "endereço direto" para efeito da pergunta de origem.

## Alternativas consideradas

- **Gravar uma linha de marcação no boot, declarando a semântica vigente** — o arquivo ganharia
  separadores e as linhas antigas ficariam intocadas, sem campo novo. Descartada porque a
  atribuição passaria a depender de posição: uma cópia parcial do arquivo, um `grep` sobre um
  intervalo ou uma rotação externa separam a linha do seu marcador, e o erro que isso produz é
  mudo. Três workers escrevendo o marcador também produziriam três.
- **Começar um arquivo novo, renomeando o atual** — a distinção ficaria trivial, com uma
  população por arquivo. Descartada porque toca o arquivo já gravado, porque depende de um
  passo manual cuja omissão funde as duas populações em silêncio, e porque `AUDIT_LOG_PATH`
  passaria a ter história.
- **Um campo booleano, `behind_proxy`** — diria a configuração vigente em vez da procedência do
  valor. Descartada porque é o dado errado: sob `behind_proxy: true` com o cabeçalho ausente, o
  campo `ip` é o endereço direto e o booleano afirma o contrário.
- **Só documentar o instante da troca em `docs/runbook.md`** — custo zero. Descartada porque é
  exatamente a "memória externa" que o critério de aceite recusa, e porque documento e arquivo
  se separam.
- **Levar a procedência também às linhas do limitador de taxa** — fecharia a mesma ambiguidade
  no log operacional. Fora do escopo declarado deste bloco, que proíbe tocar
  `config/limites.py` além do que esta decisão exigir, e o log operacional não tem a
  propriedade que cria o problema: ele não sobrevive ao container.
