---
name: estilo-de-prosa
description: Regras de escrita do projeto e a fronteira entre revisar a forma e alterar o conteúdo. Use ao escrever ou revisar prosa em português — README, ADR, roadmap, comentário, docstring, texto de tela, definição de agente — e quando o usuário pedir para revisar a linguagem, perguntar se o português está bom, ou reclamar que um texto está confuso, prolixo ou mal escrito. Use também antes de gravar documento novo. Não use para decidir o que dizer, apenas como dizer.
---

# Estilo de prosa

Toda regra aqui nasceu de um defeito real deste repositório, corrigido na TASK-011. Nenhuma é
preferência: cada uma tem o trecho que a originou.

**A distinção que governa tudo:** forma é como se diz; conteúdo é o que se diz. Esta skill só
autoriza mexer na forma. Defeito de conteúdo — afirmação falsa, número errado, referência a
coisa que não existe — se **reporta**, nunca se corrige de passagem. Corrigir conteúdo
dentro de uma revisão de forma esconde a mudança justamente de quem precisaria aprová-la.

## O que não é prosa

Estabeleça esta fronteira **antes** da primeira edição. Depois dela, cada correção é aposta.

| Nunca toque | Por quê |
| --- | --- |
| Identificador, caminho, comando, variável de ambiente | É código, não texto. |
| Classe CSS | `class="sessao"` sustenta `.sessao` na folha; acentuar quebra a tela. |
| Rótulo de contrato | `NAO FEITO`, `RELATORIO PRE-ALTERACAO`, `CRITICO` — o orquestrador casa a string literal, sem acento. |
| Valor de enum | `nao-se-aplica`, `aguardando-usuario`, `AC-NN`, `BLOCK-NNN`. |
| Dado de teste | Um `code_verifier` de PKCE (Proof Key for Code Exchange) só admite `[A-Za-z0-9-._~]`. |
| `description:` de frontmatter | É texto que a máquina casa, e tem de caber em uma linha. |
| Título e slug de ADR (Architecture Decision Record) | Renomear quebra o link e a numeração que outros documentos citam. |

**Uniformidade perfeita é assinatura de escolha.** Um "defeito" que aparece em N de N
arquivos é convenção, não defeito. Os blocos de contrato dos seis agentes estão sem acento
(todos, sem exceção), enquanto a prosa dos mesmos arquivos é acentuada. "Corrigir" isso
quebraria o casamento de rótulo.

## Siglas

- **Expanda na primeira aparição de cada documento**, não uma vez no projeto. Quem abre o
  `README.md` sozinho não leu o `docs/esboco.md`.
- **Amarre à forma por extenso quando ela já está no texto.** Prefira `relying parties (RPs)` a
  escrever o nome e, três linhas depois, `RPs (relying parties)`.
- **O parêntese leva a descrição, nunca a sigla sozinha.** `sessão de login (SSO)` dá ao leitor
  o rótulo que ele não conhece; `o SSO (Single Sign-On)` dá o significado que ele procura.
- **Nunca use a sigla antes de apresentar o nome.**
- **Não expanda dentro de código nem de string de roteamento.** Numa referência a valor de
  campo, `` `algorithm = RS256` `` fica intacto.

## Ortografia

- **Uma norma por repositório.** Duas convivendo não é estilo, é acidente que envelheceu — e a
  escolha entre elas não é simétrica: uma está correta.
- **Sem acento a palavra troca de classe.** `admin e o servidor` lê-se `admin é o servidor`,
  que pode ser falso. O acento não é enfeite; é desambiguação.
- **Texto visível à pessoa usuária primeiro.** É a única prosa que alguém de fora lê, e a mais
  barata de corrigir.

## Decalques do inglês

| Origem | Decalque | Português |
| --- | --- | --- |
| to be about | `X é sobre diagnóstico` | `X governa o diagnóstico` |
| matches against | `casa contra request.path` | `compara com request.path` |
| fail loud | `falhar alto` | `falhar ruidosamente` |
| to guard against | `guardaria um cenário` | `protegeria contra um cenário` |
| by design | `por design` | `deliberadamente` |
| zero-padded | `preenchido com zeros` | `com zeros à esquerda` |
| to budget for | `deve ser orçado` | `deve ser tratado` |
| to escalate | `escalar ao usuário` | `subir ao usuário` |
| to flip | `flipar na 4.0` | `inverter na 4.0` |

- **Duas metáforas para a mesma ação denunciam que uma foi importada.** Quando o projeto já tem
  forma própria, a outra veio de fora; unifique na portuguesa.
- **Anglicismo sem equivalente honesto fica.** `allowlist`, `healthcheck` e `stack` ficam.
  *Flipar* e *orçar* tinham equivalente, e saíram.

## Regência e concordância

- **Regência:** confiar **em**, precisar **de**, situar-se **quanto a**. Não `uma tela que
  ninguém confia`, e sim `uma tela em que ninguém confia`.
- **"Quem" é para gente.** Biblioteca, sistema e relying party levam `que` ou `as quais`.
- **Coordenação não troca de sujeito no meio.** O segundo verbo herda o sujeito do primeiro; se
  o agente muda, a oração recomeça.
- **Adjetivo precisa de antecedente do mesmo gênero na frase**, não na cabeça de quem escreveu.
- **Substantivo estrangeiro não ganha gênero por conta própria.** `settings única` e
  `o pré-alteração` não fecham em nenhuma das duas línguas: reescreva com núcleo português.
- **"Onde" é para lugar.** Para etapa, momento ou circunstância: `em que`.

## Precisão

Num projeto que cita `arquivo:linha` de dependência de terceiro e número de commit, a afirmação
genérica destoa mais do que destoaria em qualquer outro lugar.

- **Superlativo sem medida é impressão, não afirmação** — `uma das operações mais caras do
  ecossistema`, `a separação mais limpa possível`.
- **Advérbio de grau sem número, idem** — `alonga levemente o tempo de boot`.
- **Frequência exige fonte** — `é frequentemente lido como`.
- **Referência tem de ser resolvível.** Apontar para um diretório é apontar para nada: nomeie o
  arquivo.
- **Corrigir um genérico não é inventar a evidência que falta.** Se o parágrafo já provou a
  afirmação, retome o que ele provou; se não provou, corte a afirmação. Acrescentar um dado
  plausível troca um defeito de forma por um de conteúdo.

## Economia

- **Bloco que empilha quatro argumentos vira lista.** Reorganize; nunca corte informação.
- **Não diga duas vezes.** Duas frases seguidas com a mesma ideia é uma frase mal terminada.
- **Máxima vazia barateia as boas.** Num texto que fecha seções com aforismo, o aforismo sem
  conteúdo contamina os que têm.
- **Referência para a frente obriga a ler duas vezes** — `recusada no item seguinte desta
  lista`.
- **Travessão seguido de vírgula (`—,`) sempre obriga releitura.** Ou o aposto vira parêntese,
  ou a oração dispensa a vírgula.

## Verificação

Revisar forma sem tocar conteúdo é promessa forte. Estas são as travas que a tornam
verificável em vez de apenas afirmada.

1. **Palavra ambígua é leitura humana, uma a uma.** `e`/`é`, `esta`/`está`, `tem`/`têm`,
   `publica`/`pública`, `valida`/`válida`, `referencia`/`referência`. O padrão que resolve 98
   ocorrências erra a 99ª.
2. **Requebra de linha prova que não mudou nada.** Reflow, reorganização de lista e mudança de
   largura devem sair com a sequência de palavras idêntica:

   ```
   python3 -c "
   import subprocess,pathlib,sys
   f=sys.argv[1]
   a=subprocess.run(['git','show','HEAD:'+f],capture_output=True,text=True).stdout.split()
   b=pathlib.Path(f).read_text().split()
   print('palavras alteradas:', sum(1 for x,y in zip(a,b) if x!=y) + abs(len(a)-len(b)))
   " <arquivo>
   ```

   Se a reformatação foi pura, o número é zero. Se não é zero, cada palavra tem de ser uma
   correção que você escolheu fazer.
3. **Em código, compare a árvore sintática, não o arquivo.** Diff de texto não distingue
   docstring de lógica; `ast.dump` com as strings neutralizadas distingue.
4. **Conteúdo duplicado sincroniza-se e verifica-se por `diff`.** Sempre que um texto vive em
   dois lugares, a verificação não é lembrar de sincronizar; é o `diff` sair vazio no fim.
5. **A suíte é o critério.** Texto de tela e comentário de template podem quebrá-la: um
   `{# ... #}` multi-linha vaza para o corpo da página, e
   `accounts/tests/test_template_comment_leak.py` guarda contra isso.
6. **Verifique o achado antes de agir sobre ele.** Defeito reportado por outro agente pode ser
   falso positivo; agir sobre ele introduz erro onde não havia.

## Antes de dar por pronto

- Toda sigla expandida na primeira aparição **deste** documento?
- Uma ortografia só, acentos inclusive nas strings visíveis?
- Sobrou algum decalque da tabela acima?
- Cada `quem` se refere a uma pessoa?
- Cada verbo coordenado ainda tem o sujeito do primeiro?
- Todo superlativo tem medida, e toda referência resolve?
- Algum bloco empilha quatro argumentos sem quebra?
- O que mudei é prosa, e não rótulo, identificador ou dado?
- Havendo cópia do texto em outro lugar, o `diff` sai vazio?

## Não faz

- Não altera o que está sendo dito. Defeito de conteúdo vira apontamento, não correção.
- Não decide largura de linha do repositório nem reformata em massa por conta própria: reflow
  amplo soterra as correções em ruído de requebra, e a troca é do dono do repositório.
- Não renomeia arquivo, slug de ADR nem rótulo de contrato.
- Não edita ADR sem autorização explícita quando seu `Status` já é `Aceito`.
