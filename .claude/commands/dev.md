---
description: Porta de entrada. Classifica a demanda e roteia para o fluxo adequado.
argument-hint: [descrição da demanda]
---

# /dev — porta de entrada

Demanda: $ARGUMENTS

Você é o orquestrador. Sua tarefa aqui é **classificar e anunciar a rota**, não executá-la
ainda.

## Passo 1 — Classifique

| Sinal na demanda | Rota |
| --- | --- |
| Algo que deveria funcionar não funciona | `/bugfix` |
| Comportamento novo para quem usa | `/feature` |
| Estrutura muda, comportamento não | `/refactor` |
| Mecânico, sem decisão: renomear, mover, formatar, bump de versão | `/chore` |
| Esqueleto, build, config inicial — sem comportamento de usuário | `/scaffold` |
| Auditar o que existe, sem escrever | `/review` |
| Cobertura de teste, produção intocada | `/test-gap` |
| Não se sabe se é viável | `/spike` |

**Desempate:** se duas rotas servem, escolha a **mais profunda** e diga por quê. Barato
demais é o erro caro: um `/chore` que era `/feature` produz código sem critério de aceite.

**Se nenhuma serve:** pergunte ao usuário. Não force a demanda dentro da rota mais próxima.

## Passo 2 — Anuncie

Antes de executar qualquer fase, devolva ao usuário:

```
ROTA: /<command>
POR QUE: <uma linha, ancorada no sinal da tabela>
DESCARTADAS: <rota plausível> — <por que não>
PRIMEIRA FASE: <agente> — <o que ele vai receber>
```

Pare aqui e espere. O usuário pode vetar a rota, e essa é a razão de o anúncio existir.

## Passo 3 — Abra a tarefa

Confirmada a rota pelo usuário, e **antes** de invocar o primeiro agente: cunhe o `TASK-NNN` e
acrescente a entrada em `.claude/memory/context.json`, conforme *Ciclo de vida da tarefa* do
`PROTOCOLO-AGENTES.md`. `rota` recebe a rota confirmada; `fase_atual` recebe a Fase 1 do command
correspondente.

Rota vetada pelo usuário não abre tarefa. Se ele trocar a rota, atualize `rota` em vez de abrir
uma segunda entrada — é a mesma demanda.

## Passo 4 — Execute

Siga o command correspondente em `.claude/commands/`. Ele assume que a tarefa já está aberta.

O `CLAUDE.md` exige perguntar antes de agir quando a tarefa envolve mais de dois arquivos —
isso vale por cima de qualquer fase de qualquer rota.
