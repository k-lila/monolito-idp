---
description: Comportamento novo para quem usa. Pipeline completo, com gates de profundidade.
argument-hint: [descrição da feature]
---

# /feature — comportamento novo

Demanda: $ARGUMENTS

## Quando esta rota se aplica

Há comportamento novo, observável por quem usa o sistema.

## Quando NÃO se aplica

- Estrutura muda e comportamento não → `/refactor`
- Algo que já deveria funcionar não funciona → `/bugfix`
- Esqueleto ou config sem comportamento de usuário → `/scaffold`

## Abertura

Se esta tarefa ainda não está em `.claude/memory/context.json` — rota invocada direto, sem passar
por `/dev` —, abra a entrada antes da Fase 1, conforme *Ciclo de vida da tarefa* do
`PROTOCOLO-AGENTES.md`. Cada fase abaixo atualiza `fase_atual` e `fases_concluidas`; cada
apontamento recebido entra em `apontamentos_sem_disposicao` no ato.

## Fases

### Fase 1 — `product-manager`

Passe: a demanda bruta, verbatim.
Espere: `CLASSIFICACAO`, `ESPECIFICACAO`, `CRITERIOS DE ACEITE` (`AC-NN`), `ESCOPO`.

### Gate de profundidade

Decida com o relatório na mão, não antes:

- `CLASSIFICACAO: SUBSTANTIVO` **e** a mudança toca estrutura, contratos ou fluxo de
  dados → **Fase 2**.
- `TRIVIAL`, ou mudança localizada dentro de fronteiras que já existem → **pule à Fase 3**.

Anuncie a decisão do gate e a razão. É aqui que a rota se estreita ou se aprofunda.

### Fase 2 — `architect` (condicional)

Passe: a `ESPECIFICACAO` e os `AC-NN` do product-manager, na íntegra.
Espere: `ESTRUTURA ALVO`, `CONTRATOS`, `DIRETRIZES`, `ADRS A REGISTRAR`, `PROIBICOES`.

### Fase 3 — Pré-alteração

Apresente ao usuário o relatório exigido pelo `CLAUDE.md`: razões, arquivos a criar,
arquivos a modificar. **Espere autorização.** Nenhuma escrita antes disto.

### Fase 4 — `writer`

Passe: os `AC-NN`, as `DIRETRIZES` e as `PROIBICOES` do architect (se houve Fase 2), as
`ADRS A REGISTRAR` para gravar, e a confirmação explícita de que a alteração está
autorizada.
Espere: `IMPLEMENTADO`, `DECISOES`, `NAO FEITO`, `PARA O QA`.

As ADRs vão para `docs/adr/NNNN-slug.md` **como vieram do architect** — o writer grava, não
reescreve. Gravada uma ADR, ela sai de `adrs_pendentes` no `context.json` e ganha a linha de
índice em `decisions.md` no encerramento.

### Fase 5 — `quality-assurance`, modo `conformidade`, primeira passagem

Passe: os `AC-NN` e o relatório do writer na íntegra.
Espere: `CONFORMIDADE` por AC, `QUALIDADE`, `REGRESSAO`, `DEMANDAS DE TESTE` (`T-NN`),
`DEMANDAS AO WRITER`.

### Fase 6 — `writer` (condicional)

Só se houver `DEMANDAS AO WRITER`. Passe as demandas verbatim. Uma rodada apenas.

### Fase 7 — `tester`

Passe: o bloco `DEMANDAS DE TESTE` na íntegra.
Espere: `DEMANDAS ATENDIDAS`, `BUGS ENCONTRADOS`, `INTESTAVEL`.

Se vier `BUGS ENCONTRADOS`, volte ao `writer` com eles — o tester não corrige produção.

### Fase 8 — `quality-assurance`, segunda passagem

Passe: o seu próprio relatório da Fase 5 e o relatório do tester. Ele não os recorda.

### Gate adversarial

`senso-critico` entra se o `architect` entrou, ou se a especificação assume algo que
ninguém verificou. **Nunca como etapa fixa** — a definição dele proíbe isso.

Passe: a especificação, o desenho e o que foi implementado.

## Encerramento

Consolide os vereditos.

Feche conforme *Ciclo de vida da tarefa* do `PROTOCOLO-AGENTES.md`: cada apontamento recebe
disposição (`aceito`, `rejeitado` com justificativa, ou `adiado`), o que sobrevive à tarefa vai
para `.claude/memory/decisions.md`, cada ADR gravada ganha uma linha no índice de
`decisions.md`, e só então a entrada é **removida** de
`.claude/memory/context.json`. Apontamento sem disposição não fecha a tarefa.

Qualquer `BLOQUEIO` vira `BLOCK-NNN` em `.claude/memory/blockers.md` **antes** de subir ao
usuário, e para a rota aqui.
