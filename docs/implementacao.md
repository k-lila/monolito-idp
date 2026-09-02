# Implementação — ordem aconselhada

Este documento não substitui `docs/roadmap/`: ele diz **em que granularidade** executar os
treze passos e o que fazer antes de começar. O conteúdo de cada passo continua sendo o do
arquivo correspondente em `docs/roadmap/`.

## O princípio: a unidade é o gate, não o arquivo

Cada passo do roadmap termina em uma seção **"Passo concluído quando"**. É essa seção — o
gate — a unidade de trabalho. Não o arquivo, e não o roadmap inteiro.

**Arquivo por arquivo é fino demais.** O passo 05 cria cinco arquivos e o 09 cria sete; um
`accounts/` pela metade não passa em `check`, um `templates/` pela metade não renderiza
nada. Não existe estado verificável no meio de um passo, e parar ali só produz a ilusão de
progresso incremental.

**Tudo de uma vez desperdiça o que o roadmap tem de melhor.** O valor do documento está no
catálogo de falhas silenciosas. Escrevendo os treze passos antes de subir qualquer coisa,
um JWKS respondendo `{"keys": []}` tem **três** causas candidatas: escape do PEM errado
(03), leitura sem `multiline=True` (04) ou `OIDC_ISS_ENDPOINT` incoerente (07). Passo a
passo, tem uma. Esse diferencial de diagnóstico é o produto inteiro do roadmap.

## Antes de começar

### 1. Verificar os nove pins, e o Gunicorn em particular

O passo 01 declara `gunicorn==26.2.0` e registra que o projeto **não declara suporte a
Python 3.14** — e que, se isso quebrar, o sinal aparece **só no passo 11**, como traceback
no boot do container, porque até o passo 10 quem serve é o `runserver`.

Isso é evitável ao custo de um comando. No virtualenv de Python 3.14, depois do
`pip install -r requirements.txt`:

```
gunicorn --version
```

Gunicorn é Python puro; importá-lo já resolve a dúvida. Um comando move um risco de dez
passos à frente para o passo 01.

Na mesma ocasião, confirmar que as nove versões existem de fato no PyPI. Falha de pin no
passo 01 é barata; no passo 11, não.

### 2. Um commit por gate

Commit a cada "Passo concluído quando" torna o rollback gratuito — com uma exceção que
importa: **commit não desfaz o passo 06**. Ali o reset é `docker compose down -v`, e ele é
barato **só enquanto não houver dado de valor no banco**. É exatamente por isso que o passo
06 vem antes de qualquer coisa interessante existir.

E há uma segunda: **commit nenhum protege o `.env`**. O arquivo é untracked — nenhum
`reset`, `checkout` ou revert o traz de volta —, e `git clean -xd`, que é a operação a que
se recorre quando um passo deixou lixo na árvore, **apaga** o `.env` junto com a única
cópia da chave RSA do passo 03 e da `SECRET_KEY`. Não há outra: é decisão declarada.

### 3. Confirmar as duas strings irreversíveis enquanto ainda custam nada

A chave RSA (passo 03) e o issuer `{BASE_URL}/o` (passo 07) travam quando a **primeira
relying party integrar**, não quando o passo rodar. Hoje, trocar qualquer uma das duas
custa uma linha do `.env`; depois, custa coordenação com todas as RPs integradas.

Decidir conscientemente nos passos 03 e 07 e seguir — sabendo que a janela fecha na
primeira integração, não no fim do roadmap.

### 4. Divergência se registra, não se absorve

Se um passo não fechar como está escrito — versão que não existe, comportamento diferente
do DOT —, anotar em vez de ajustar o roadmap em silêncio. O passo 13 pressupõe que a
implementação confirmou as sete ADRs; uma contradição não registrada corrompe esse
pressuposto e só aparece meses depois, quando alguém procurar a razão de uma escolha.

## Os blocos

| Bloco | Passos | Por que junto ou sozinho | Gate |
|---|---|---|---|
| **A** | 01 → 02 → 03 | Independentes entre si e sem Python de projeto ainda. Três checks numa sessão só. | `pip install` limpo no venv 3.14; os dois serviços `healthy`; linha da chave no `.env` |
| **B** | 04 **+** 05 | **Obrigatoriamente juntos.** O 04 deixa o projeto sem inicializar *por design* — `AUTH_USER_MODEL` aponta para um modelo que só existe no 05 —, e o próprio passo diz que `manage.py check` não é critério dele. | `manage.py check` verde, o primeiro do projeto, e `makemigrations accounts --dry-run` mostrando a criação do `User` |
| **C** | 06 | **Sozinho e deliberado.** É o único ponto de não retorno de toda a sequência. | `migrate` sem erro; a tabela de `accounts` existe e **`auth_user` não existe** — verificar ativamente, esse sinal não se anuncia sozinho |
| **D** | 07, depois 08 | Separados. O 07 omite `OAUTH2_VALIDATOR_CLASS` de propósito; juntar os dois reabre a chance de um boot com a settings apontando para módulo inexistente. | 07: discovery com `issuer` igual a `{BASE_URL}/o` e JWKS com **uma** chave. 08: `id_token` com `sub`, `name` e `email` |
| **E** | 09, depois 10 | Podem ser a mesma sessão — o 10 só depende do 09 por `config/views.py` já existir —, mas com dois gates distintos. | 09: `/accounts/login/` com CSS, home mostrando o usuário, logout por POST. 10: `docker compose stop redis` devolve 503 com `"cache": "error"` |
| **F** | 11, depois 12 | Separados. O 11 é onde o container entra pela primeira vez, com o `runserver` já parado. | 11: `docker compose up --wait` com os três serviços `healthy` e discovery respondendo do container. 12: alguém executa a receita do zero e obtém um `id_token` |
| **G** | 13 | Em lote. Transcrição literal, salvo as ADRs emendadas antes da gravação com autorização do usuário — é a última janela em que corrigir custa uma frase, porque ADR aceita é imutável. | Os onze arquivos em `docs/adr/`: 0001–0007 vindos dos blocos do passo 13, 0008–0011 de `.claude/memory/decisions.md`. Sete deles — 0002, 0004, 0005, 0006, 0008, 0009 e 0011 — foram alterados antes da gravação, com autorização explícita do usuário, para corrigir afirmações que a implementação falsificou; nos quatro que têm bloco no passo 13, o bloco foi atualizado no mesmo movimento e as duas cópias coincidem |

## Cadência

Um bloco por vez, e cada bloco na mesma forma:

1. relatório antes — razões, arquivos a criar, arquivos a modificar;
2. aprovação;
3. implementação;
4. o gate do passo, executado de verdade;
5. commit.

Os blocos B, D e E envolvem mais de dois arquivos, então cada um é precedido de pergunta.
