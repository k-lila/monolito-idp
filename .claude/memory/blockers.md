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

## [2026-09-13] BLOCK-001 · TASK-015
- **Origem:** product-manager
- **Referência:** AC-01, AC-02, AC-12; `docs/adr/0007-fixar-o-issuer-do-idp-em-base-url-barra-o.md`;
  `.claude/memory/decisions-arquivo.md:418`
- **Descrição:** o usuário fixou em 2026-09-13 a **forma** do issuer: subdomínio dedicado ao
  provedor de identidade (IdP), sob `https`, mantendo o sufixo `/o` — `https://<host>/o`. A
  escolha preserva a ADR (Architecture Decision Record) 0007, que fixa o issuer em
  `{BASE_URL}/o`, e dispensa a ADR nova que o "destino natural" daquela ADR exigiria. Fica
  declarada provisória: pode mudar até a primeira relying party (RP) integrar, e essa é a
  janela.

  **O que ainda bloqueia:** o `<host>` não foi nomeado, e sem ele AC-01 e AC-04 não têm onde
  ser verificados. O host é valor de implantação, não literal de repositório — vive na
  `BASE_URL` do `.env`, que é untracked. Isso entrelaça este impedimento com a pergunta do
  ambiente-alvo, delegada ao `architect` na Fase 2: quem disser onde o proxy vive dirá também
  que nome ele atende. Antes da primeira RP integrar, o host tem de ser confirmado, sob pena de
  um ano de HTTP Strict Transport Security (HSTS) no navegador de quem visitar o nome errado.

  **Resolução (Fase 2, architect, 2026-09-13):** o host deixa de ser necessário para
  implementar. Ele passa a ser `PUBLIC_HOST`, variável lida pelo compose, de onde saem
  `BASE_URL`, `ALLOWED_HOSTS` e o nome que o proxy atende. O único literal em arquivo
  versionado é `PUBLIC_HOST=idp.localhost` no `.env.example`, e a RFC 6761 impede que
  `.localhost` seja um host real. O que resta é obrigação futura, não impedimento: confirmar o
  host real antes da primeira RP integrar, agora com o custo do HSTS sobre o nome visitado.
- **Status:** resolvido

## [2026-09-13] BLOCK-002 · TASK-015
- **Origem:** product-manager
- **Referência:** AC-06; `docs/adr/0015-resolver-a-origem-do-cliente-num-ponto-unico.md:55-59`;
  `.claude/memory/decisions.md:178-181`
- **Descrição:** a ADR 0015 proíbe nominalmente ligar `BEHIND_TLS_PROXY` antes de decidir o
  versionamento da linha da trilha de auditoria. Ligar a variável troca, na mesma tecla, o
  significado do campo `ip` da trilha e a chave do limitador de taxa; a trilha é append-only e
  o instante da troca não fica gravado em lugar nenhum, de modo que as linhas anteriores e as
  posteriores ficam indistinguíveis. O dano é irreversível por construção. A resolução é de
  ADR e cabe ao `architect`; sobe ao usuário apenas se o mecanismo escolhido tocar o arquivo já
  gravado ou o esquema de campos que a ADR 0013 fixou.

  **Resolução (Fase 2, architect, 2026-09-13):** cada linha passa a declarar a procedência do
  endereço num campo `ip_src`, com três valores — `remote_addr`, `forwarded` e
  `remote_addr_fallback`. O valor e a procedência saem do mesmo cálculo em `config/origem.py`,
  e a resposta é por linha, não por posição no arquivo. Linha sem o campo é anterior a esta
  tarefa e é `remote_addr` por construção, porque a proibição da ADR 0015 foi respeitada. O
  mecanismo **estende** o esquema da ADR 0013 e **não toca** o arquivo já gravado: não sobe ao
  usuário. Gravado na Fase 4 como
  `docs/adr/0018-declarar-a-procedencia-do-endereco-em-cada-linha-da-trilha.md`, com
  `config/origem.py` e `accounts/auditoria.py` implementando o campo antes de
  `BEHIND_TLS_PROXY` ser ligado, como a ADR 0015 exige.
- **Status:** resolvido

## [2026-09-14] BLOCK-003 · TASK-015
- **Origem:** orquestrador
- **Referência:** `docs/arquitetura.md`, `docs/testes.md`, `tests/test_origem.py`,
  `tests/test_auditoria.py`
- **Descrição:** a rodada que fecha a ADR 0020 ficou pela metade. O `writer` gravou o código, a
  ADR, `docs/seguranca.md` e `docs/runbook.md` — tudo verificado contra o código pelo
  orquestrador, com a suíte em 95 testes verdes nas duas jornadas — e caiu por limite de sessão
  antes de `docs/arquitetura.md` e `docs/testes.md`. Os casos de teste do campo `ip_edge`
  também não foram escritos: hoje ele é gravado em toda linha da trilha sem cobertura nenhuma.
  O impedimento não é do projeto, é da conta: o limite reseta às 05:10 de 2026-09-15, e o
  usuário decidiu esperar em vez de o orquestrador cruzar a fronteira de escrita dos agentes.
- **Status:** aberto

---

**Regra ao usar este arquivo:** bloqueador resolvido sai daqui. O valor de um arquivo de
impedimentos é que a lista vazia significa alguma coisa.

**Regra de verificação:** o critério de "fechado" verifica-se contra o código, nunca contra
outro documento. O escopo de um problema verifica-se varrendo a superfície no código, nunca
relendo o texto que o descreve.
