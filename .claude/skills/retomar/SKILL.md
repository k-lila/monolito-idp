---
name: retomar
description: Reconstrói o estado de uma tarefa em andamento a partir de .claude/memory/. Use quando o usuário perguntar o que está rodando, o que ficou pendente, "onde paramos", "retoma a tarefa", "o que estava fazendo", "status da tarefa", "continua de onde parou" — e no início de qualquer sessão que continue trabalho anterior, inclusive depois de /clear ou de compactação de contexto. Use também antes de abrir uma tarefa nova, para não abrir uma segunda entrada para uma demanda que já está em curso.
---

# Retomar

O `.claude/memory/context.json` é escrito ao longo de toda a rota e nunca é lido. Esta skill é
o lado que faltava: ela lê a memória e reconstrói onde a tarefa parou, para que o trabalho
sobreviva à perda de contexto.

Você lê e relata. **Não escreve em `.claude/memory/`** — nem para corrigir o que achar errado.

## Procedimento

### 1. Leia o `context.json`

`tarefas_ativas` vazia → responda **"nada em execução"** e pare aqui.

Não infira tarefa a partir do git, de arquivo modificado recentemente, ou do que a conversa
sugere. A lista vazia significar "nada rodando" é o valor inteiro do arquivo; adivinhar destrói
isso. Se o usuário acha que havia uma tarefa aberta e não há, isso é o achado — reporte a
discrepância em vez de fabricar a entrada.

### 2. Leia a entrada de cada tarefa ativa

Todos os campos. `fases_concluidas` é o rastro da orquestração; `fase_atual` é onde parou;
`pendencias_de_fechamento` é o que falta para fechar.

### 3. Puxe os bloqueios

Havendo `bloqueios_abertos`, leia `.claude/memory/blockers.md` e traga a descrição e o status
de cada `BLOCK-NNN` referenciado. Um `BLOCK-NNN` citado que não existe lá é divergência (passo
4).

### 4. Confira contra o disco, não contra o arquivo

Os `arquivos_tocados` existem? O que está neles corresponde ao que a entrada afirma ter sido
feito? As `adrs_pendentes` continuam ausentes de `docs/adr/`, ou já foram gravadas?

É a regra que o próprio `blockers.md` declara: *o critério de "fechado" verifica-se contra o
código, nunca contra outro documento.*

Divergência é **reportada, nunca corrigida em silêncio**. O `context.json` pode estar
desatualizado — uma fase que rodou e não foi registrada, um arquivo escrito e não anotado — e
essa defasagem é informação, não sujeira para limpar. Quem decide o que fazer com ela é o
usuário.

### 5. Devolva o bloco

Um bloco por tarefa ativa, neste formato:

```
TAREFA: TASK-NNN — <demanda>
ROTA: /<command>, aberta em AAAA-MM-DD
PERCORRIDO: <uma linha por fase concluida, com o veredito recebido; ou "nenhuma">
PARADO EM: <fase_atual: numero, responsavel, estado>
AUTORIZACAO PRE-ALTERACAO: <pendente | concedida em AAAA-MM-DD | nao-se-aplica>
PENDENTE PARA FECHAR
  apontamentos sem disposicao: <lista, ou "nenhum">
  bloqueios abertos: <BLOCK-NNN — resumo vindo do blockers.md, ou "nenhum">
DIVERGENCIA: <o que o disco contradiz na entrada, ou "nenhuma">
PROXIMA ACAO: <proxima_acao>
```

### 6. Pare

A skill lê e relata; não reinvoca agente e não avança fase. Retomar de fato é decisão do
orquestrador, e passa por montar um prompt de invocação novo — veja o limite abaixo antes de
montá-lo.

## O limite: o rastro sobrevive, os relatórios não

O `context.json` guarda **o rastro** — qual fase, qual agente, qual veredito. Ele não guarda o
conteúdo dos relatórios, e o conteúdo morre junto com a conversa.

Isso importa porque várias fases exigem repassar um relatório anterior **verbatim**: a Fase 8
do `/feature` manda passar ao `quality-assurance` o relatório dele mesmo da Fase 5 e o do
`tester`; a Fase 6 do `/bugfix` faz o mesmo. Retomada essa tarefa numa sessão nova, esse texto
não existe mais em lugar nenhum.

Há duas saídas honestas, e a escolha é do usuário:

- **reinvocar o agente da fase anterior** para produzir o relatório de novo; ou
- **perguntar ao usuário** se ele tem o texto.

Reconstruir de memória o que um agente disse é fabricação. Diga que o relatório se perdeu, e
ofereça as duas saídas.

## Não faz

- Não escreve em `.claude/memory/` — nem para consertar divergência que encontrou.
- Não abre tarefa. Isso é o `/dev`.
- Não atribui disposição a apontamento nem fecha tarefa. Isso é o encerramento da rota.
