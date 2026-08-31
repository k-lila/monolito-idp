# Passo 03 — Chave RSA de desenvolvimento

## Objetivo

Gerar o par RSA que assina os tokens e colocá-lo no `.env` local, no formato que o
`django-environ` sabe ler.

## Depende de

Passo 01, por três coisas: o contrato de `OIDC_RSA_PRIVATE_KEY` no `.env.example`, o
`.env` local já criado — este passo escreve nele —, e o `.gitignore` que barra `*.pem`.

A chave precede qualquer configuração de OIDC (passo 07): sem ela o servidor sobe e falha
em silêncio. Precede também o passo 04, que lê a variável: vazia, a leitura falha
ruidosamente nomeando-a.

## Arquivos criados

- `scripts/gen_dev_key.sh` — gera o par RSA de 2048 bits e imprime a linha pronta para o
  `.env`, já com as quebras de linha escapadas como `\n`.

## O que fazer

O script produz um par de **2048 bits — tamanho fixo, sem parâmetro** — e escreve na saída
padrão a linha `OIDC_RSA_PRIVATE_KEY=...`, com o PEM em uma única linha e `\n` escapado.
Quem executa copia essa linha para o `.env` local.

2048 é fixo por não haver decisão a tomar aqui: é o piso aceito para RS256 e o que toda
biblioteca de relying party valida sem configuração. Um parâmetro de tamanho seria opção
sem consumidor, e a chave de produção não sai deste script.

### O script imprime; quem escreve no `.env` é uma pessoa

**Decisão declarada, não omissão:** `gen_dev_key.sh` não edita o `.env`.

Escrita automática significaria sobrescrever, sem confirmação, uma chave possivelmente em
uso — e trocar a chave invalida na prática todo token vivo e quebra o JWKS cacheado das
RPs, porque não há conjunto de rotação (ADR 0004). Rodar um script duas vezes é acidente
barato; sobrescrever a identidade do IdP não é.

O custo dessa escolha é um passo manual de copiar e colar. É o custo certo: torna a troca
de chave um ato deliberado.

Do lado das settings (passo 04), a leitura é
`env.str("OIDC_RSA_PRIVATE_KEY", multiline=True)` — é o modo do `django-environ` que
desfaz o escape.

A chave privada nunca entra no repositório nem na imagem Docker. Chaves de
desenvolvimento são descartáveis por definição (ADR 0004).

## Proibições que incidem aqui

- **Não gerar a chave dentro do entrypoint nem do Dockerfile.** Chave nova a cada boot
  invalida todo token vivo e quebra o cache de JWKS das relying parties. O script é
  executado por uma pessoa, uma vez, fora do ciclo de boot.
- **Não commitar `.pem` nem o `.env`.** Chave de sandbox commitada é chave que reaparece
  em produção.
- **Não introduzir rotação de chaves nesta fase.** Existe uma única chave ativa, sem
  conjunto de rotação; a primeira rotação será disruptiva e terá ADR própria.

## Riscos e sinais

- **`OIDC_RSA_PRIVATE_KEY` ausente ou mal escapada** — sinal:
  `/o/.well-known/jwks.json` responde `{"keys": []}` e a discovery omite os endpoints de
  token. **A aplicação sobe normalmente e nada no log acusa.** É a falha silenciosa mais
  cara deste passo, e só aparece do lado da relying party.
- **PEM em variável de ambiente é formato hostil** — sinal: erro confuso de parsing de
  chave, ou o mesmo JWKS vazio, quando o escape de quebra de linha está errado.

## Fronteira de decisão — irreversibilidade por exposição externa

**Isto não é sequência de implementação.** A identidade da chave RSA deixa de ser
reversível no instante em que a primeira relying party integra, independentemente de
quando o passo foi executado: sem conjunto de rotação, trocar a chave invalida na prática
os tokens em curso e quebra o JWKS cacheado das RPs.

Enquanto o IdP não tiver RP integrada, gerar uma chave nova custa uma linha do `.env`.
Depois, custa coordenação. A decisão sobre qual chave é a chave do IdP deve ser
confirmada com o usuário **antes** da primeira integração, não depois (ADR 0004).

## Passo concluído quando

`scripts/gen_dev_key.sh` roda e imprime a linha; a linha está no `.env` local; `git
status` não enxerga nenhum arquivo de chave. A verificação real do efeito só é possível no
passo 07, quando o JWKS responde com uma chave.
