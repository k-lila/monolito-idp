---
description: Diagnóstico e correção de defeito, com teste vermelho antes da correção.
argument-hint: [o que está quebrado]
---

# /bugfix — algo que deveria funcionar não funciona

Relato: $ARGUMENTS

## Quando esta rota se aplica

Existe comportamento esperado, e o sistema não o entrega.

## Quando NÃO se aplica

- O comportamento nunca existiu → `/feature`
- Está feio mas funciona → `/refactor`
- Falta cobertura, sem defeito conhecido → `/test-gap`

## Abertura

Se esta tarefa ainda não está em `.claude/memory/context.json` — rota invocada direto, sem
passar por `/dev` —, abra a entrada antes da Fase 1, conforme *Ciclo de vida da tarefa* do
`PROTOCOLO-AGENTES.md`. Cada fase abaixo atualiza `fase_atual` e `fases_concluidas`; cada
apontamento recebido entra em `apontamentos_sem_disposicao` no ato.

## Fases

### Fase 1 — `quality-assurance`, modo `caracterizacao`

Passe: o relato verbatim e a instrução explícita `MODO: caracterizacao`. Espere: `DEFEITO`
(reproduzido, origem, alcance), os `AC-NN` cunhados descrevendo o comportamento correto, e o
`T-NN` da reprodução.

**Gate de reprodução:** se o defeito não reproduz, pare. Um defeito não reproduzível vira
pergunta ao usuário, não correção às cegas.

### Fase 2 — `tester`

Passe: o `T-NN` de reprodução e a origem apontada pelo QA (quality-assurance). Espere: teste
**vermelho**, com o bug em `BUGS ENCONTRADOS`.

O teste vermelho é o enunciado falsificável do defeito. Ele é a prova de que o problema existe,
e vira a guarda de não-regressão depois da correção.

**Gate:** se o teste passa de primeira, a caracterização está errada. Volte à Fase 1 em vez de
seguir corrigindo algo que não se demonstrou quebrado.

### Fase 3 — Pré-alteração

Apresente ao usuário: causa, correção pretendida, arquivos a modificar. Espere autorização.

### Fase 4 — `writer`

Passe: os `AC-NN`, o `DEFEITO` com a origem, o caminho do teste vermelho, e a autorização.
Espere: `IMPLEMENTADO`, `DECISOES`, `PARA O QA`.

**Gate de escalada:** se o writer reportar que a correção exige mudança estrutural, ele para —
é o comportamento definido dele. Reroteie para `/feature`, ou insira o `architect` antes de
voltar ao writer.

### Fase 5 — `tester`

Passe: o mesmo `T-NN` e o relatório do writer. Espere: **verde**. Se seguir vermelho, volte à
Fase 4 com o motivo.

Verde por complacência é proibido pela definição do tester — teste ajustado para passar sobre
comportamento errado mente sobre a cobertura.

### Fase 6 — `quality-assurance`, segunda passagem

Passe: o seu relatório da Fase 1 e o do tester. Espere: `CONFORMIDADE` de cada `AC-NN` cunhado
na Fase 1, e o estado da suíte.

**Alcance:** se a Fase 1 apontou outros pontos com o mesmo defeito, eles fecham aqui ou saem
registrados como apontamento. Corrigir o caso visível em vez da classe é o que faz o problema
voltar.

## Encerramento

Feche conforme *Ciclo de vida da tarefa* do `PROTOCOLO-AGENTES.md`: cada apontamento recebe
disposição (`aceito`, `rejeitado` com justificativa, ou `adiado`), o que sobrevive à tarefa vai
para `.claude/memory/decisions.md`, e só então a entrada é **removida** de
`.claude/memory/context.json`. Apontamento sem disposição não fecha a tarefa.

Qualquer `BLOQUEIO` vira `BLOCK-NNN` em `.claude/memory/blockers.md` **antes** de subir ao
usuário, e para a rota aqui.
