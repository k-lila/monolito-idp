---
description: Auditoria read-only do que já existe. Ninguém escreve.
argument-hint: [o que auditar]
---

# /review — auditar sem tocar

Alvo: $ARGUMENTS

## Quando esta rota se aplica

Há código, documentação ou plano que já existe, e se quer saber em que estado está antes de
decidir o que fazer.

## Quando NÃO se aplica

Se já se sabe o que corrigir → a rota da correção. Review não é a antessala obrigatória de
nada; é para quando a pergunta ainda é "o que há aqui?".

## Abertura

Se esta tarefa ainda não está em `.claude/memory/context.json` — rota invocada direto, sem
passar por `/dev` —, abra a entrada antes da Fase 1, conforme *Ciclo de vida da tarefa* do
`PROTOCOLO-AGENTES.md`. Cada fase abaixo atualiza `fase_atual` e `fases_concluidas`; cada
apontamento recebido entra em `apontamentos_sem_disposicao` no ato.

## Fases

### Fase 1 — `quality-assurance` e `senso-critico`

Podem ser invocados **em paralelo**: nenhum depende do relatório do outro, e os objetos são
distintos por definição.

Ao `quality-assurance`, modo `conformidade`: passe o alvo e os `AC-NN` se existirem. Espere:
`QUALIDADE`, `REGRESSAO`, `DEMANDAS DE TESTE` se houver lacuna de cobertura.

Ao `senso-critico`: passe o alvo inteiro. Espere: `PREMISSAS IDENTIFICADAS`, `APONTAMENTOS` com
cenário concreto, `DESCARTADOS`.

**Ninguém escreve nesta rota.** Nem writer, nem tester. Os dois agentes desta fase são
read-only por construção — nem têm as ferramentas.

### Fase 2 — Consolidação

Junte os dois relatórios, agrupando por severidade. Divergência entre eles não se resolve aqui:
sobe ao usuário, como o protocolo determina.

Devolva:

```
ACHADOS
  [BLOQUEADOR] <achado> — <origem: qa | senso-critico> — <arquivo:linha ou cenario>
  [CRITICO] ...
  [OBSERVACAO] ...

ROTA RECOMENDADA
  <achado ou grupo> → /<command> — <por que>

DIVERGENCIAS
  <ponto em que os dois relatorios se contradizem; ou "nenhuma">
```

## Encerramento

Review termina em recomendação, nunca em correção. Se o usuário quiser agir, cada achado entra
por `/dev` como demanda própria — é assim que ele ganha pré-alteração, critério de aceite e
verificação, que uma correção enxertada aqui não teria.

Por isso a disposição aqui é quase sempre `adiado`: o achado sobrevive como linha em
`.claude/memory/decisions.md`, com a rota recomendada, e é essa linha que o `/dev` seguinte
recebe. Achado de review que não vira linha nem vira tarefa não sobreviveu ao review.

Fechada a disposição de todos os achados, **remova a entrada** de
`.claude/memory/context.json`. `arquivos_tocados` sai vazio — ninguém escreveu nesta rota.

`BLOQUEADOR` encontrado numa auditoria vira `BLOCK-NNN` em `.claude/memory/blockers.md`: ele
descreve um estado do código, não uma fase parada, e continua valendo depois que este review
fechar.
