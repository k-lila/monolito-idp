---
description: Fechar lacuna de cobertura. Código de produção intocado.
argument-hint: [o que cobrir]
---

# /test-gap — cobertura, sem tocar produção

Alvo: $ARGUMENTS

## Quando esta rota se aplica

Existe código sem cobertura adequada, e nenhum defeito conhecido. Também é o desvio
obrigatório quando `/refactor` esbarra em caminho descoberto.

## Quando NÃO se aplica

- Há defeito conhecido → `/bugfix` (que já produz o teste de reprodução)
- A cobertura falta porque a feature está incompleta → `/feature`

## Abertura

Se esta tarefa ainda não está em `.claude/memory/context.json` — rota invocada direto, sem passar
por `/dev` —, abra a entrada antes da Fase 1, conforme *Ciclo de vida da tarefa* do
`PROTOCOLO-AGENTES.md`. Cada fase abaixo atualiza `fase_atual` e `fases_concluidas`; cada
apontamento recebido entra em `apontamentos_sem_disposicao` no ato.

## Fases

### Fase 1 — `quality-assurance`, modo `conformidade`

Passe: o alvo e o estado atual da suíte.
Espere: `DEMANDAS DE TESTE` (`T-NN`), cada uma com nível e justificativa do nível.

O QA é o único que decide o que testar e em que nível. A pirâmide da definição dele vale
inteira aqui, inclusive a parte que dispensa teste: comportamento sem decisão — repasse,
getter, glue trivial — **não** entra. Cobrir tudo degrada a suíte em vez de fortalecê-la.

### Fase 2 — `tester`

Passe: o bloco `DEMANDAS DE TESTE` na íntegra.
Espere: `DEMANDAS ATENDIDAS`, `INFRA`, `BUGS ENCONTRADOS`, `INTESTAVEL`.

**Gate de descoberta:** cobrir código não testado revela defeito com frequência. Se vier
`BUGS ENCONTRADOS`, o teste fica vermelho e documentado — o tester não corrige produção. O
defeito sai daqui como `/bugfix` próprio.

**Gate de costura:** se vier `INTESTAVEL`, a costura no código de produção é demanda ao
`writer` e sai daqui como `/chore` ou `/refactor`. Não se enxerta produção nesta rota.

### Fase 3 — `quality-assurance`, segunda passagem

Passe: o seu relatório da Fase 1 e o do tester.
Espere: confirmação de que cada `T-NN` foi atendido e que os testes verificam o
comportamento certo — não apenas que passam.

## Encerramento

Código de produção sai desta rota **byte a byte igual** ao que entrou. Se não saiu, a rota
estava errada — o que ficou em `arquivos_tocados` prova isso.

Feche conforme *Ciclo de vida da tarefa* do `PROTOCOLO-AGENTES.md`: cada apontamento recebe
disposição (`aceito`, `rejeitado` com justificativa, ou `adiado`), o que sobrevive à tarefa vai
para `.claude/memory/decisions.md`, e só então a entrada é **removida** de
`.claude/memory/context.json`. Apontamento sem disposição não fecha a tarefa.

Qualquer `BLOQUEIO` vira `BLOCK-NNN` em `.claude/memory/blockers.md` **antes** de subir ao
usuário, e para a rota aqui.
