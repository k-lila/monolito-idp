---
description: Tarefa mecânica sem decisão — renomear, mover, formatar, bump de versão.
argument-hint: [o que fazer]
---

# /chore — mecânico, sem decisão

Tarefa: $ARGUMENTS

## Quando esta rota se aplica

A tarefa é mecânica: o resultado correto é evidente antes de começar, e não há escolha a
fazer. Renomear, mover arquivo, aplicar formatação, subir versão de dependência.

## Quando NÃO se aplica

Se existe uma decisão a tomar, não é chore. Esta é a rota mais barata e a mais fácil de
escolher errado — na dúvida, suba para `/feature` ou `/refactor`.

## Abertura

Se esta tarefa ainda não está em `.claude/memory/context.json` — rota invocada direto, sem passar
por `/dev` —, abra a entrada antes da Fase 1, conforme *Ciclo de vida da tarefa* do
`PROTOCOLO-AGENTES.md`. Cada fase abaixo atualiza `fase_atual` e `fases_concluidas`; cada
apontamento recebido entra em `apontamentos_sem_disposicao` no ato.

## Fases

### Fase 1 — Pré-alteração

Apresente ao usuário: o que muda, arquivos afetados. Espere autorização.

Em chore, o pré-alteração é curto, mas não é dispensável — o `CLAUDE.md` exige perguntar
antes de agir quando a tarefa envolve mais de dois arquivos, e chore costuma envolver
muitos.

### Fase 2 — `writer`

Passe: a tarefa, o escopo exato, e a autorização.
Espere: `IMPLEMENTADO`, `NAO FEITO`.

**Gate de escape:** se o writer descobrir que a tarefa não é mecânica — que há uma decisão
a tomar, ou que o escopo se espalha —, ele para e reporta, como a definição dele já manda.
Reroteie em vez de deixar seguir.

### Fase 3 — `quality-assurance`, modo `conformidade`

Passe: o relatório do writer.
Espere: `REGRESSAO`. Só isso.

Não há `AC-NN` e não há demanda de teste: chore não introduz comportamento. Se o QA achar
que precisa de teste novo, a tarefa não era chore.

## Encerramento

Feche conforme *Ciclo de vida da tarefa* do `PROTOCOLO-AGENTES.md`: cada apontamento recebe
disposição (`aceito`, `rejeitado` com justificativa, ou `adiado`), o que sobrevive à tarefa vai
para `.claude/memory/decisions.md`, e só então a entrada é **removida** de
`.claude/memory/context.json`. Apontamento sem disposição não fecha a tarefa.

Qualquer `BLOQUEIO` vira `BLOCK-NNN` em `.claude/memory/blockers.md` **antes** de subir ao
usuário, e para a rota aqui.
