---
name: auditar-sistema
description: Auditoria read-only de consistência do próprio sistema de agentes em .claude/ — definições que não carregam, referência a arquivo que não existe, agente ou rota citada que sumiu, fronteira de escrita furada, memória incoerente, settings.json inválido. Use quando o usuário pedir para auditar ou verificar o sistema de agentes, perguntar se o .claude está consistente, e depois de criar, renomear ou editar agente, command ou skill.
---

# Auditar o sistema

Varredura de consistência do `.claude/` sobre si mesmo. Você **reporta; não conserta** — nem o
defeito mais trivial. Achado vira demanda do usuário, e ele escolhe a rota.

Nada aqui escreve. Use `Read`, `Grep`, `Glob` e `Bash` só para constatar.

## Checagens

Rode todas. Cada uma nasceu de uma classe de defeito que já ocorreu neste sistema.

### 1. Frontmatter que carrega

Todo arquivo de definição abre com `---`, fecha o bloco, e traz os campos que o **seu tipo**
exige — que não são os mesmos:

| Tipo | Exige | `name:` |
| --- | --- | --- |
| `agents/*.md` | `name`, `description` | igual ao nome do arquivo, sem extensão |
| `skills/*/SKILL.md` | `name`, `description` | igual ao nome da pasta |
| `commands/*.md` | `description` | **não tem** — o nome vem do arquivo |

Cobrar `name:` de command é o erro a não cometer aqui: dispara nos nove de uma vez, e falso
positivo em massa é o que faz uma auditoria parar de ser lida.

```bash
for f in .claude/agents/*.md .claude/skills/*/SKILL.md; do
  b=$(basename "$f" .md); [ "$b" = "SKILL" ] && b=$(basename "$(dirname "$f")")
  n=$(grep -m1 '^name:' "$f" | sed 's/^name: *//')
  [ "$b" = "$n" ] || echo "DIVERGE: $f -> name=$n"
  grep -q '^description:' "$f" || echo "SEM DESCRIPTION: $f"
done
for f in .claude/commands/*.md; do
  grep -q '^description:' "$f" || echo "SEM DESCRIPTION: $f"
done
```

### 2. Caminho citado que não existe

Extraia dos markdowns os caminhos citados (`.claude/...`, `docs/...`, `skills/...`) e confira a
existência de cada um no disco. É a checagem que pega referência a arquivo deletado — o modo de
falha mais silencioso do sistema, porque o texto continua parecendo correto.

Filtre no próprio comando o que não é referência: caminho com `NNNN`, `NN` ou `<placeholder>`
no nome é modelo; `docs/...` e `.claude/...` com reticências é o texto falando de si mesmo; e
caminho dentro de bloco de exemplo — o `docs/adr/0001-usar-postgresql-para-persistencia.md` da
skill `new-adr` — ilustra formato. Nota pedindo filtragem manual é ruído por design: o que a
checagem manda ignorar, ela não deve emitir.

```bash
grep -rhoE '(\.claude|docs)/[A-Za-z0-9._/-]+' .claude/*.md .claude/agents .claude/commands .claude/skills \
  | tr -d '`' | sed 's/[.,;:)]*$//' | sort -u \
  | grep -vE 'NNNN|NN|<|slug|0001-usar-postgresql' \
  | while read -r p; do [ -e "$p" ] || echo "FALTA: $p"; done
```

### 3. Agente invocado que não existe

Todo agente citado nos commands existe em `.claude/agents/`. Compare os nomes citados com a
saída de `ls .claude/agents/`. Pega agente renomeado sem atualizar quem o chama.

### 4. Rota citada que não existe

Todo alvo da tabela de classificação do `/dev` e dos blocos "Quando NÃO se aplica" existe em
`.claude/commands/`. Pega roteamento para o vazio.

### 5. `context.json` íntegro

- É JSON válido: `python3 -m json.tool .claude/memory/context.json > /dev/null`.
- Tem as chaves que o próprio arquivo declara em `_modelo_de_tarefa`.
- **Nenhuma tarefa em `tarefas_ativas` com as duas listas de `pendencias_de_fechamento`
  vazias.** Essa é tarefa que já cumpriu a regra de saída e deveria ter sido removida. Tarefa
  que fica é o que faz a lista vazia parar de significar alguma coisa.

### 6. Memória coerente entre os três arquivos

- Todo `BLOCK-NNN` em `bloqueios_abertos` existe em `blockers.md` com status diferente de
  `resolvido`.
- Todo `BLOCK-NNN` aberto em `blockers.md` está referenciado por alguma tarefa ativa. Bloqueio
  aberto sem tarefa é bloqueio esquecido.
- Toda ADR (Architecture Decision Record) listada no índice de `decisions.md` existe em
  `docs/adr/`.
- Todo `TASK-NNN` é único entre `context.json` e `decisions.md` — número reaproveitado
  embaralha o histórico.

### 7. Fronteira de escrita intacta

O campo `tools:` de cada agente confere com a tabela de *Fronteiras de escrita* do
`PROTOCOLO-AGENTES.md`: **só `writer` e `tester` têm `Write` ou `Edit`**.

```bash
grep -n '^tools:' .claude/agents/*.md
```

Esta é a checagem mais importante da lista. O protocolo declara, na seção *O que é imposto e o
que é confiança*, que o `tools:` é a **única** garantia real do sistema — todo o resto é
compromisso. Um `Write` concedido por engano a um agente de análise não deixa rastro em lugar
nenhum.

### 8. `settings.json`

JSON válido, e **nenhum padrão de permissão começando com `/`**. A barra inicial ancora o
padrão na raiz do sistema de arquivos em vez do projeto, e a regra nunca dispara — falha
silenciosa, porque uma permissão que não pega se parece exatamente com uma permissão que nunca
foi acionada.

```bash
python3 -m json.tool .claude/settings.json >/dev/null && grep -nE '"[A-Za-z]+\(/' .claude/settings.json
```

### 9. Arquivo órfão

Arquivo em `.claude/` que nenhum outro cita. Procure pela forma como o sistema **de fato** cita
cada tipo, não pelo nome do arquivo: agente aparece como `` `writer` ``, rota como `/feature`.
Procurar por `writer.md` acusa o sistema inteiro de órfão.

```bash
for f in .claude/agents/*.md; do b=$(basename "$f" .md)
  grep -rq "\`$b\`" .claude/commands .claude/PROTOCOLO-AGENTES.md || echo "ORFAO: $f"; done
for f in .claude/commands/*.md; do b=$(basename "$f" .md)
  grep -rq --exclude="$b.md" "/$b" .claude/commands .claude/PROTOCOLO-AGENTES.md || echo "ORFAO: $f"; done
```

Skill fica de fora: ela é encontrada pela `description`, não por referência de outro arquivo,
então não ser citada é o normal dela.

Sempre `OBSERVACAO`, nunca mais que isso: pode ser intencional, e a skill não sabe a intenção.

## Relatório

No vocabulário que o sistema já tem — seções *Severidade dos apontamentos* e *Veredito* do
`PROTOCOLO-AGENTES.md`. Não invente escala nova.

```
ESCOPO: <o que foi varrido>

ACHADOS
  [SEVERIDADE] <arquivo:linha> — <o que esta errado> — <consequencia>

VEREDITO: LIBERADO | RESSALVA | BLOQUEIO
```

Calibragem, para a auditoria não virar ruído:

| Severidade | Aqui significa |
| --- | --- |
| `BLOQUEADOR` | impede o sistema de funcionar: definição que não carrega, referência quebrada em caminho de execução, fronteira de escrita furada |
| `CRITICO` | incoerência de memória — os três arquivos discordando entre si ou do disco; e defeito nesta própria skill, como checagem que dispara em arquivo correto |
| `OBSERVACAO` | órfão, estilo, duplicação de texto entre commands |

Campo sem achado recebe `nenhum`. Auditoria limpa termina em `VEREDITO: LIBERADO` — não procure
achado para justificar a varredura.

## Não faz

- Não corrige nada, nem o defeito de uma linha.
- Não audita o código do projeto. Isso é `/review`. O objeto aqui é o `.claude/`.
