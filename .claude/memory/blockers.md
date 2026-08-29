# Impedimentos Ativos

> Bloqueadores que pararam um pipeline e aguardam resolução humana ou de outro agente.
> **Quem escreve aqui é o orquestrador** (o thread principal), a partir de apontamentos
> marcados `[BLOQUEADOR]` nos relatórios dos agentes. Nenhum subagente grava neste arquivo.
> Remova a entrada apenas quando o impedimento for resolvido — mova o resumo para
> `decisions.md` se virar decisão.
>
> **Formato de entrada:**
>
> ```
> ## [AAAA-MM-DD] BLOCK-NNN · TASK-NNN
> - **Origem:** <agente que apontou>
> - **Referência:** AC-NN / T-NN / arquivo:linha
> - **Descrição:** o que está bloqueado e por quê (específico e acionável).
> - **Status:** aberto | escalado-humano | resolvido
> ```

---

> _Nenhum impedimento ativo._

---

**Regra ao usar este arquivo:** bloqueador resolvido sai daqui. O valor de um arquivo de
impedimentos é que a lista vazia signifique alguma coisa.

**Regra de verificação:** o critério de "fechado" verifica-se contra o código, nunca contra
outro documento. O escopo de um problema verifica-se varrendo a superfície no código, nunca
relendo o texto que o descreve.
