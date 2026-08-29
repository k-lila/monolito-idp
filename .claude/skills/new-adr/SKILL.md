---
name: new-adr
description: Gera Architecture Decision Records (ADRs) no formato padrão de Michael Nygard. Use esta skill sempre que o usuário quiser documentar, registrar ou escrever uma decisão de arquitetura ou técnica — incluindo frases como "cria uma ADR", "documenta essa decisão", "por que escolhemos X", "registra esse trade-off", "adiciona uma ADR para", ou quando um projeto tem uma pasta docs/adr/ que precisa de uma nova entrada. Use também de forma proativa quando o usuário acabou de tomar uma decisão significativa de design ou arquitetura (banco de dados, framework, estratégia de autenticação, modelo de deploy, estilo de API) e se beneficiaria de registrar o raciocínio.
---

# Gerador de ADR

Uma ADR (Architecture Decision Record, ou Registro de Decisão de Arquitetura) é um documento curto e imutável que captura uma decisão de arquitetura significativa: o contexto que a forçou, a decisão em si e as consequências aceitas. Seu propósito é responder "por que fizemos assim?" meses ou anos depois, quando o raciocínio já teria se perdido.

Esta skill produz ADRs no formato popularizado por Michael Nygard, que é o padrão de fato e o que a maioria dos revisores e tech leads reconhece.

## Fora do pipeline

Esta skill é para invocação direta, quando o usuário quer registrar uma decisão avulsa. Numa tarefa
que corre por `.claude/commands/`, o caminho da ADR é outro e está no `.claude/PROTOCOLO-AGENTES.md`:
o `architect` redige o texto dentro do relatório e o `writer` grava o arquivo sem reescrever.

Gravar por aqui no meio de uma rota fura a fronteira de escrita e deixa a ADR fora do `context.json`
e do índice de `decisions.md`. Se houver tarefa ativa em `.claude/memory/context.json`, pergunte
antes de escrever.

## Fluxo de trabalho

Siga estes passos ao criar uma ADR:

### 1. Reúna a decisão

Extraia da conversa, ou peça ao usuário, as quatro coisas que uma ADR precisa:

- **O que foi decidido** (a escolha em si)
- **O problema ou as forças** que tornaram a decisão necessária (requisitos, restrições, trade-offs)
- **Alternativas consideradas** e por que foram descartadas
- **Consequências** — tanto os benefícios quanto os pontos negativos que estão sendo aceitos

Se a decisão já foi discutida antes na conversa, puxe os detalhes de lá e confirme com o usuário em vez de perguntar tudo de novo. Só pergunte sobre o que realmente estiver faltando.

### 2. Determine o número da ADR

ADRs são numeradas sequencialmente com um prefixo de 4 dígitos preenchido com zeros. Verifique a pasta de destino (padrão `docs/adr/`) em busca dos arquivos existentes:

```bash
ls docs/adr/ 2>/dev/null | grep -oE '^[0-9]{4}' | sort -n | tail -1
```

A nova ADR recebe o próximo número. Se a pasta estiver vazia ou não existir, comece em `0001`. Se não houver repositório disponível, ainda assim numere como `0001` e avise o usuário para ajustar conforme a sequência dele.

### 3. Nomeie o arquivo

Formato: `NNNN-titulo-curto-em-kebab-case.md`

Exemplos:

- `0001-usar-postgresql-para-persistencia.md`
- `0002-adotar-jwt-para-auth-stateless.md`
- `0007-dividir-monolito-em-microsservicos.md`

Mantenha o slug curto e descritivo — deve se ler como a decisão, não como uma frase completa.

### 4. Preencha o template

Use exatamente o template em `docs/adr/template-adr.md`. Carregue-o e depois preencha todas as seções. A estrutura do template é fixa — não adicione, renomeie ou reordene seções sem o usuário pedir.

Orientação por seção:

- **Título**: `# NNNN. Decisão em uma linha`, no modo imperativo (ex.: "Usar PostgreSQL para persistência", não "Banco de dados"). Presente do indicativo, tom de ação.
- **Status**: Um entre `Proposto`, `Aceito`, `Descontinuado` ou `Substituído por ADR-NNNN`. Uma ADR recém-criada normalmente é `Proposto`, a menos que o usuário diga que a decisão já foi tomada, caso em que é `Aceito`. Inclua a data.
- **Contexto**: Descreva o problema e as forças em jogo — restrições técnicas, requisitos, fatores de equipe. Escreva em linguagem neutra, sem juízo de valor: descreva a situação, não a decisão. Uma boa seção de contexto faz a decisão parecer quase inevitável ao final.
- **Decisão**: Diga o que foi escolhido, em voz ativa: "Vamos usar...". Uma ou duas frases com a escolha central, seguidas de quaisquer especificidades relevantes.
- **Consequências**: Liste o que fica mais fácil, mais difícil ou mais arriscado como resultado. É fundamental incluir as consequências negativas e os trade-offs aceitos — uma ADR só com pontos positivos é um sinal de alerta. Separe em positivas e negativas se houver várias de cada.
- **Alternativas consideradas** (opcional, mas recomendada): Para cada opção séria não escolhida, uma linha sobre o que era e por que perdeu. Essa costuma ser a seção mais valiosa — mostra que a decisão foi ponderada, não tomada por inércia.

### 5. Escreva e confirme

Escreva o arquivo na pasta de destino. Se ainda não existir pasta, crie `docs/adr/` e mencione que esse é o local convencional. Mostre o resultado ao usuário e ofereça ajustar o tom, a profundidade ou o status.

## Regras centrais

Estas regras são o que faz as ADRs funcionarem como registro histórico — respeite-as:

1. **ADRs são imutáveis depois de aceitas.** Se uma decisão mudar mais tarde, não edite a ADR antiga. Crie uma ADR _nova_ e mude o status da antiga para `Substituído por ADR-NNNN` (essa mudança de status é a única edição permitida em uma ADR aceita). Isso preserva o histórico de como o pensamento evoluiu.

2. **Uma decisão por ADR.** Se o usuário descrever várias decisões, proponha dividi-las em ADRs separadas.

3. **Mantenha curta.** Uma ADR costuma ter de meia a uma página. Se estiver crescendo demais, o contexto provavelmente está fazendo um trabalho que pertence a documentos de design.

4. **Acompanhe o idioma do projeto.** Se o projeto e a conversa ao redor estiverem em inglês (ou outro idioma), escreva a ADR nesse idioma, traduzindo os títulos das seções. O padrão é o idioma em que o usuário está escrevendo.

## Exemplo (preenchido)

**Entrada:** "Escolhemos PostgreSQL em vez de MongoDB para o user service porque precisamos de transações e os dados são relacionais, mesmo o time conhecendo melhor o Mongo."

**Saída** (`docs/adr/0001-usar-postgresql-para-persistencia.md`):

```markdown
# 0001. Usar PostgreSQL para persistência

## Status

Aceito — 2026-08-27

## Contexto

O user service armazena contas, papéis e seus relacionamentos. Essas
entidades são fortemente relacionais e várias operações precisam ser
atômicas (por exemplo, criar uma conta e seu papel padrão juntos).
Precisamos de transações confiáveis com múltiplas linhas e forte
consistência. O time tem mais experiência prévia com MongoDB do que
com bancos relacionais.

## Decisão

Vamos usar o PostgreSQL como camada de persistência do user service.

## Consequências

Positivas:

- Transações ACID cobrem as operações atômicas que precisamos.
- O modelo relacional mapeia naturalmente nossas entidades via chaves
  estrangeiras.
- Ferramental maduro e várias opções de hospedagem amplamente disponíveis.

Negativas:

- O time precisará investir tempo aprendendo modelagem relacional e SQL.
- Migrações de schema exigem mais disciplina inicial do que um banco sem
  schema fixo.

## Alternativas consideradas

- **MongoDB** — familiar ao time, mas transações entre múltiplos documentos
  são complicadas e os dados são naturalmente relacionais, então estaríamos
  lutando contra o modelo.
```
