---
description: Esqueleto do projeto — estrutura, build, config. Sem comportamento de usuário.
argument-hint: [o que montar]
---

# /scaffold — fundação

Alvo: $ARGUMENTS

## Quando esta rota se aplica

Estrutura de pastas, build, configuração, escolha de stack, esqueleto de módulo. Não há
comportamento de usuário a especificar — há um chão a construir.

## Quando NÃO se aplica

- Já existe estrutura e o que se quer é comportamento → `/feature`
- Reorganizar estrutura que já existe → `/refactor`

## Abertura

Se esta tarefa ainda não está em `.claude/memory/context.json` — rota invocada direto, sem
passar por `/dev` —, abra a entrada antes da Fase 1, conforme *Ciclo de vida da tarefa* do
`PROTOCOLO-AGENTES.md`. Cada fase abaixo atualiza `fase_atual` e `fases_concluidas`; cada
apontamento recebido entra em `apontamentos_sem_disposicao` no ato.

## Fases

### Fase 1 — `architect`

Passe: o alvo, o que já existe no repositório, e as restrições conhecidas (stack desejada,
convenções, o que o `CLAUDE.md` determina). Espere: `ESTRUTURA ALVO`, `CONTRATOS`, `ADRS A
REGISTRAR`, `PROIBICOES`, `RISCO ESTRUTURAL`.

Esta é a rota que mais usa o bloco `ADRS A REGISTRAR`. As decisões de fundação — linguagem,
framework, banco, estratégia de autenticação, modelo de deploy — são exatamente as que se
perdem se não forem registradas na hora, e são caras de reverter depois.

Sem `product-manager`: não há problema de usuário a traduzir. Sem `tester`: não há
comportamento a cobrir ainda.

### Fase 2 — Pré-alteração

Apresente ao usuário: a estrutura proposta, os arquivos a criar, e **as ADRs (Architecture
Decision Records) propostas com seus títulos**. Espere autorização.

Scaffold cria muitos arquivos de uma vez. A pré-alteração aqui é a única barreira antes de o
repositório ganhar uma forma difícil de desfazer.

### Fase 3 — `writer`

Passe: `ESTRUTURA ALVO`, `PROIBICOES`, o bloco `ADRS A REGISTRAR` na íntegra, e a autorização.
Espere: `IMPLEMENTADO`, `DECISOES`.

As ADRs vão para `docs/adr/NNNN-slug.md`, no formato de `docs/adr/template-adr.md`, **como
vieram do architect** — o writer grava, não reescreve.

### Fase 4 — `quality-assurance`, modo `conformidade`

Passe: a estrutura alvo e o relatório do writer. Espere: constatação de que a estrutura existe
como desenhada, que o projeto **builda** e que o comando de teste roda, ainda que sem testes.

Não há `AC-NN` a conferir. O critério é: o chão aguenta peso?

### Gate adversarial

`senso-critico` entra aqui quase sempre. Decisão de fundação é premissa por definição, e é a
que cobra mais caro em seis meses.

Passe: o desenho do architect e as ADRs propostas.

## Encerramento

Feche conforme *Ciclo de vida da tarefa* do `PROTOCOLO-AGENTES.md`: cada apontamento recebe
disposição (`aceito`, `rejeitado` com justificativa, ou `adiado`), o que sobrevive à tarefa vai
para `.claude/memory/decisions.md`, cada ADR gravada ganha uma linha no índice de
`decisions.md`, e só então a entrada é **removida** de `.claude/memory/context.json`.
Apontamento sem disposição não fecha a tarefa.

`adrs_pendentes` vazio é a confirmação de que o writer gravou tudo que o architect redigiu.

Qualquer `BLOQUEIO` vira `BLOCK-NNN` em `.claude/memory/blockers.md` **antes** de subir ao
usuário, e para a rota aqui.
