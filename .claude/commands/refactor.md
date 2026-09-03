---
description: Estrutura muda, comportamento não. A suíte existente é o critério de aceite.
argument-hint: [o que refatorar]
---

# /refactor — mudar a forma sem mudar o comportamento

Alvo: $ARGUMENTS

## Quando esta rota se aplica

A estrutura precisa mudar e o comportamento observável deve permanecer **idêntico**.

## Quando NÃO se aplica

- O comportamento muda, mesmo que pouco → `/feature`
- Corrigir algo quebrado → `/bugfix`
- Rename ou movimentação mecânica → `/chore`

## Gate de segurança — antes de tudo

**Refactor sem suíte é cego.** Se não existe cobertura do caminho a ser tocado, não há como
provar que o comportamento não mudou.

Verifique a cobertura do caminho alvo antes da Fase 1. Se não houver, passe por `/test-gap`
primeiro e só então volte. Esse desvio não é burocracia: é a única coisa que distingue refactor
de reescrita torcendo para dar certo.

## Abertura

Se esta tarefa ainda não está em `.claude/memory/context.json` — rota invocada direto, sem
passar por `/dev` —, abra a entrada antes da Fase 1, conforme *Ciclo de vida da tarefa* do
`PROTOCOLO-AGENTES.md`. Cada fase abaixo atualiza `fase_atual` e `fases_concluidas`; cada
apontamento recebido entra em `apontamentos_sem_disposicao` no ato.

## Fases

### Fase 1 — `architect`

Passe: o alvo, a estrutura atual e a razão do refactor. Espere: `ESTRUTURA ALVO`, `CONTRATOS`,
`ORDEM SUGERIDA DE IMPLEMENTACAO`, `PROIBICOES`.

Sem `product-manager` nesta rota: não há comportamento novo a especificar. O critério de aceite
é a suíte que já existe.

### Fase 2 — Pré-alteração

Apresente ao usuário: estrutura alvo, arquivos a modificar, o que **não** muda. Espere
autorização.

### Fase 3 — `writer`

Passe: `ESTRUTURA ALVO`, `ORDEM SUGERIDA`, `PROIBICOES` e a autorização. Espere:
`IMPLEMENTADO`, `DECISOES`, `NAO FEITO`.

A `ORDEM SUGERIDA` importa mais aqui do que em qualquer outra rota: refactor em passos que
mantêm a suíte verde é reversível; refactor em um salto, não.

### Fase 4 — `quality-assurance`, modo `conformidade`

Passe: a estrutura alvo do architect e o relatório do writer. Espere: `REGRESSAO` como campo
principal — o estado da suíte antes e depois.

O foco não é conformidade a `AC-NN` (não há), é **ausência de diferença**. Suíte verde antes e
depois, com o mesmo conjunto de testes, é a prova.

**Gate:** teste alterado durante um refactor é sinal de alerta. Se a suíte só passa porque um
teste mudou, o comportamento mudou — aponte como `[CRITICO]`.

### Gate adversarial

`senso-critico` entra se o refactor move fronteiras entre componentes. Passe o desenho e o que
foi implementado.

## Encerramento

Feche conforme *Ciclo de vida da tarefa* do `PROTOCOLO-AGENTES.md`: cada apontamento recebe
disposição (`aceito`, `rejeitado` com justificativa, ou `adiado`), o que sobrevive à tarefa vai
para `.claude/memory/decisions.md`, e só então a entrada é **removida** de
`.claude/memory/context.json`. Apontamento sem disposição não fecha a tarefa.

Qualquer `BLOQUEIO` vira `BLOCK-NNN` em `.claude/memory/blockers.md` **antes** de subir ao
usuário, e para a rota aqui.
