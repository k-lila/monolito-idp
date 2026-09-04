# Protocolo dos subagentes

Convenções comuns aos agentes. Todo agente lê este arquivo e o `CLAUDE.md` antes de qualquer
outra coisa.

## Contexto frio

Nenhum agente enxerga a conversa que o invocou. O que você precisa saber está na sua definição,
neste protocolo e no prompt de invocação — em nenhum outro lugar. Se a informação necessária
não estiver ali, pergunte no relatório em vez de supor.

Corolário: quando um agente é invocado duas vezes na mesma tarefa, a segunda invocação não
lembra a primeira. O orquestrador é quem repassa o relatório anterior no prompt.

## Orquestrador

O orquestrador é o **thread principal**, não um subagente. Cabe só a ele:

- invocar agentes e repassar, no prompt, tudo que o agente precisa ler;
- atribuir disposição aos apontamentos recebidos;
- parar e subir ao usuário diante de um `BLOQUEIO`;
- apresentar ao usuário o relatório pré-alteração exigido pelo `CLAUDE.md`, antes de autorizar
  qualquer escrita;
- manter `.claude/memory/` ao longo da rota, conforme *Ciclo de vida da tarefa*.

Nenhum agente faz nada disso por conta própria.

## Fluxos

Os fluxos de trabalho vivem em `.claude/commands/`. Cada um é uma sequência explícita de
invocações de agente, com gates declarados. `/dev` é a porta de entrada: classifica a demanda e
anuncia a rota antes de executar.

Um command é **roteiro, não executor**. Nada nele é imposto pelo harness — quem o executa é a
sessão principal, e as garantias reais continuam sendo apenas as `tools` declaradas em cada
agente. Um subagente não invoca command e não invoca outro agente.

## Fronteiras de escrita

| Agente   | Pode escrever                                    |
| -------- | ------------------------------------------------ |
| `writer` | código de produção e documentação                |
| `tester` | testes, fixtures, mocks, infraestrutura de teste |
| demais   | nada                                             |

Sem exceção e sem sobreposição. Quem precisa de uma alteração fora da sua fronteira registra a
necessidade no relatório e devolve.

Isso vale inclusive para ADRs (Architecture Decision Records): o `architect` **decide e
redige** o conteúdo dentro do seu relatório; o `writer` **grava** o arquivo.

### O que é imposto e o que é confiança

O harness impõe **uma coisa só**: o campo `tools:` de cada definição. É ele que torna real a
linha "demais: nada" — quem não tem `Write` nem `Edit` não escreve, e não há como contornar.

Todo o resto é compromisso, não garantia: a ordem das fases, a apresentação do relatório
pré-alteração, a divisão entre código de produção e teste dentro das ferramentas concedidas
(`writer` e `tester` têm as mesmas), e a escrita por meio de `Bash`. Nada disso é barrado por
mecanismo; sustenta-se na definição de cada agente e neste protocolo.

## Severidade dos apontamentos

Todo apontamento sai marcado com uma destas três severidades:

| Severidade    | Significado                                                 |
| ------------- | ----------------------------------------------------------- |
| `BLOQUEADOR`  | prosseguir causaria dano difícil de reverter                 |
| `CRITICO`     | tem de ser resolvido antes de a tarefa fechar                |
| `OBSERVACAO`  | registro para depois; não impede nada                        |

## Veredito

Todo relatório termina com uma linha:

```
VEREDITO: LIBERADO | RESSALVA | BLOQUEIO
```

O veredito é derivado das severidades, não escolhido:

- ao menos um `BLOQUEADOR` → `BLOQUEIO`;
- nenhum `BLOQUEADOR`, ao menos um `CRITICO` ou `OBSERVACAO` → `RESSALVA`;
- nada apontado → `LIBERADO`.

O veredito não interrompe nada por conta própria: você devolve um relatório e encerra.
`BLOQUEIO` é um compromisso do orquestrador de parar e subir ao usuário. Marcar algo como
`BLOQUEADOR` para dar ênfase é abuso do mecanismo.

## Apontamentos

O agente aponta e classifica a severidade. **A disposição é do orquestrador**: `aceito` (vira
tarefa), `rejeitado` (com justificativa registrada) ou `adiado`. Apontamento sem disposição não
fecha a tarefa. Máximo de uma rodada de recrítica por tarefa — depois, sobe ao usuário.

## Arbitragem

Agentes não negociam entre si. Divergência entre dois relatórios sobe para o usuário.

## Convenções compartilhadas

- **Critérios de aceite (AC):** `AC-NN`, com dois dígitos (`AC-01`). Cunhados pelo
  `product-manager`, ou pelo `quality-assurance` em modo `caracterizacao` quando a rota não
  passa pelo `product-manager` — nunca pelos dois na mesma tarefa. Referenciados sem renumerar
  por todos os demais.
- **Demandas de teste:** `T-NN`, atribuídas pelo `quality-assurance`.
- **ADRs:** `docs/adr/NNNN-slug-em-kebab-case.md`, numeração sequencial de quatro dígitos,
  conforme `docs/adr/template-adr.md`. Uma decisão por ADR, de meia a uma página. **ADR aceita
  é imutável:** decisão que mudou vira ADR nova, e a antiga recebe status `Substituído por
  ADR-NNNN` — essa troca de status é a única edição permitida nela. Numa rota, quem redige é o
  `architect` e quem grava é o `writer`; a skill `new-adr` é para invocação direta pelo
  usuário, fora de rota.
- **Memória:** `.claude/memory/` é escrita **só pelo orquestrador**. Agente algum escreve lá —
  quem precisa registrar algo aponta no relatório. Quatro arquivos, quatro funções distintas:
  `context.json` é o que está em execução agora, `blockers.md` o que está parado,
  `decisions.md` o que sobrevive à tarefa, e `decisions-arquivo.md` o que já sobreviveu e saiu
  do caminho. Procedimento em *Ciclo de vida da tarefa*.
- **Tarefas:** `TASK-NNN`, três dígitos, sequencial. `BLOCK-NNN` para impedimentos.

## Ciclo de vida da tarefa

O orquestrador mantém `.claude/memory/` ao longo de toda a rota. Isto é procedimento dele, não
de agente nenhum, e vale para **todas** as rotas de `.claude/commands/`.

Sessão que continua trabalho anterior — depois de `/clear`, de compactação, ou numa sessão nova
— começa pela skill `retomar`, antes de tocar em qualquer fase. É ela que lê o `context.json`;
sem isso o arquivo é escrito e nunca consultado.

### Abertura

Confirmada a rota com o usuário, antes de invocar o primeiro agente: cunhe o `TASK-NNN`
(próximo número livre, olhando `context.json` e `decisions.md`) e acrescente a entrada em
`tarefas_ativas`, no formato de `_modelo_de_tarefa`. `rota` e `fase_atual` já saem preenchidos.

### A cada fase

Antes de invocar: `fase_atual` recebe o número, o responsável e o estado. Ao receber o
relatório: empurre a fase para `fases_concluidas` com o veredito que veio, e atualize o que o
relatório produziu — `ac`, `t`, `adrs_pendentes`, `arquivos_tocados`, `proxima_acao`. Gate
autorizado pelo usuário atualiza `autorizacao_pre_alteracao`.

Todo apontamento recebido entra em `apontamentos_sem_disposicao` no ato. Só sai de lá quando
ganhar disposição registrada.

### Diante de um `BLOQUEIO`

Grave o impedimento em `blockers.md` como `BLOCK-NNN`, no formato que aquele arquivo declara,
**antes** de subir ao usuário — o que sobe é conversa, e conversa se perde. Referencie o
`BLOCK-NNN` em `bloqueios_abertos` e pare a rota.

Impedimento resolvido sai de `blockers.md` e de `bloqueios_abertos`. Se virou decisão, o resumo
vai para `decisions.md`.

### Encerramento

Nesta ordem, e só assim a tarefa fecha:

1. Cada apontamento de `apontamentos_sem_disposicao` recebe `aceito`, `rejeitado` (com
   justificativa) ou `adiado`, e o que sobrevive à tarefa vai para `decisions.md` — decisão
   tomada, tech-debt aceito, apontamento adiado. Apontamento aceito que virou correção na
   própria tarefa não precisa de linha; ele já está no código.
2. Cada ADR gravada ganha **uma linha** no índice de `decisions.md`. O conteúdo fica na ADR.
3. `bloqueios_abertos` e `apontamentos_sem_disposicao` vazios.
4. Só então **remova a entrada** de `tarefas_ativas` e atualize `atualizado_em`.

Tarefa concluída não fica em `context.json`. O valor do arquivo é a lista vazia significar que
nada está em execução.

### A poda de `decisions.md`

Fechada a tarefa, se `decisions.md` passar de 300 linhas, mova para `decisions-arquivo.md` as
entradas de todas as tarefas encerradas menos as da última — no fim do arquivo, preservando a
ordem, sem reescrever uma linha do que se move. O índice das ADRs fica sempre no arquivo
principal.

O critério é o tamanho, não a idade. Um arquivo que já não cabe numa leitura deixa de ser
aberto, e memória que ninguém abre não é memória.

## Relatório

Escreva o relatório para quem vai consumi-lo, não para exibir raciocínio. Direto, preciso, sem
preâmbulo. O contrato de saída da sua definição é obrigatório: os campos existem para serem
lidos por outro agente. Campo sem conteúdo recebe `nenhum` — não se omite.
