---
description: Investigação com código descartável. A saída é um relatório, não um merge.
argument-hint: [a pergunta a responder]
---

# /spike — descobrir se dá

Pergunta: $ARGUMENTS

## Quando esta rota se aplica

Não se sabe se algo é viável, e a resposta não vem de leitura — vem de tentar. A dúvida
bloqueia uma decisão de desenho que não pode ser tomada no escuro.

## Quando NÃO se aplica

- Já se sabe que dá, falta fazer → a rota da construção
- A dúvida é de produto, não técnica → `/feature`, que começa pelo `product-manager`
- A resposta está no código, basta ler → `/review`

## Regras da rota

**O código não sobrevive.** Ele existe para produzir uma resposta e é descartado. Isto é o
que separa spike de implementação apressada, e é a única regra que não se negocia aqui.

- Todo código vive sob `spikes/<nome-do-spike>/`, declarado antes de começar.
- Nada fora dessa pasta é criado ou modificado.
- Sem QA, sem tester: não se verifica conformidade de algo que será jogado fora.

## Abertura

Se esta tarefa ainda não está em `.claude/memory/context.json` — rota invocada direto, sem passar
por `/dev` —, abra a entrada antes da Fase 1, conforme *Ciclo de vida da tarefa* do
`PROTOCOLO-AGENTES.md`. Cada fase abaixo atualiza `fase_atual` e `fases_concluidas`; cada
apontamento recebido entra em `apontamentos_sem_disposicao` no ato.

## Fases

### Fase 1 — Delimitação

Antes de invocar ninguém, declare ao usuário:

```
PERGUNTA: <o que precisa ser respondido, de forma falsificavel>
CRITERIO DE PARADA: <o que faz o spike terminar, respondido ou nao>
PASTA: spikes/<nome>/
```

Spike sem critério de parada não termina — vira implementação por acidente, sem nenhuma das
garantias que as outras rotas têm.

### Fase 2 — `writer`

Passe: a pergunta, o critério de parada, a pasta isolada, e a instrução explícita de que
o código é descartável e que **nada fora da pasta pode ser tocado**.
Espere: `IMPLEMENTADO`, `DECISOES`, e sobretudo o que se aprendeu.

O padrão de escrita do writer — a solução mais simples, sem abstração para caso de uso
inexistente — vale, mas a elegância aqui é secundária. O produto é a resposta.

### Fase 3 — Relatório

```
PERGUNTA
  <a que foi feita>

RESPOSTA
  <deu | nao deu | deu com ressalva> — <evidencia observada, nao suposta>

O QUE SE APRENDEU
  <fatos tecnicos que sobrevivem ao codigo descartado>

ROTA RECOMENDADA
  /<command> — <o que fazer com esta resposta>

DESCARTE
  spikes/<nome>/ — apagar agora | manter ate <quando> — <por que>
```

## Encerramento

O que sobrevive ao spike é o conhecimento, não o código. Todo fato duradouro aprendido aqui —
uma limitação de biblioteca, um comportamento não documentado, um custo medido — vira linha em
`.claude/memory/decisions.md`, ou uma ADR se sustentar uma decisão. Esta rota não deixa código
para trás, então o registro é a **única** coisa que ela produz: spike que fecha sem linha em
`decisions.md` foi trabalho jogado fora junto com a pasta.

Confirme o descarte da pasta com o usuário. Feito o registro e resolvido o descarte, **remova a
entrada** de `.claude/memory/context.json` — o `DESCARTE` pendente é a última coisa a sair.

Se o spike parou por um impedimento em vez de uma resposta, grave `BLOCK-NNN` em
`.claude/memory/blockers.md` antes de subir ao usuário.
