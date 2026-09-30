# 0028. Gerar a chave de assinatura em RSA 3072 pelo gerador único de segredos

## Status

Aceito — 2026-09-29

Emenda à ADR (Architecture Decision Record) 0004, que **permanece aceita e em vigor**. Esta
decisão substitui uma única frase daquela — "Chaves de desenvolvimento são geradas por
scripts/gen_dev_key.sh e são descartáveis por definição". RS256, a custódia da chave privada em
`OIDC_RSA_PRIVATE_KEY` e a chave única, sem conjunto de rotação, ficam como estão.

## Contexto

A ADR 0004 nomeou o gerador das chaves de desenvolvimento e calou sobre o da chave de produção. O
script que ela nomeia gerava 2048 bits fixos e dizia no cabeçalho que a chave de produção não saía
dele, e a documentação operacional repetia isso; ao mesmo tempo, o roteiro de implantação mandava
gerar a chave de produção com ele. Ao lado dele, um segundo script, fora do repositório, gerava a `SECRET_KEY` e as
senhas do Postgres e do Redis. Eram dois geradores para um `.env` só, e nenhum lugar dizia de onde
sai a chave de produção nem com que tamanho.

O tamanho pesa mais aqui do que num sistema que rotaciona. A chave de produção vive até a primeira
troca, e a troca é disruptiva por construção: sem conjunto de rotação, todo `id_token` vivo deixa de
verificar, e cada relying party (RP) rejeita os novos enquanto o seu cache do JSON Web Key Set
(JWKS) não vencer. RSA (Rivest–Shamir–Adleman) de 2048 bits dá 112 bits de segurança, que o NIST
(National Institute of Standards and Technology) aceita para gerar assinatura só até 2030
(SP 800-131A rev. 2); RSA de 3072 bits dá 128, o mesmo nível do SHA-256 que o RS256 usa
(SP 800-57 Parte 1, rev. 5). Uma chave gerada em 2026 que dure até a primeira troca pode cruzar
2030.

Nada no código depende do tamanho. `config/settings.py` só lê o PEM, o django-oauth-toolkit publica
o módulo que recebe, e a única RP, a SPA, verifica com `jose` restrito a RS256, que
aceita qualquer módulo de 2048 bits para cima.

## Decisão

Vamos gerar a `OIDC_RSA_PRIVATE_KEY` de desenvolvimento e a de produção pelo mesmo comando, em RSA
de 3072 bits fixos, sem parâmetro de tamanho. O comando é `scripts/gen_env_secrets.sh`, o único
gerador dos segredos do `.env` (a chave, a `SECRET_KEY`, as senhas do Postgres e do Redis e as duas
URLs derivadas delas). Ele imprime as linhas e não escreve arquivo nenhum.

- **Um tamanho só, nos dois ambientes.** A chave de produção sai do mesmo caminho que o
  desenvolvimento exercita, pelo mesmo princípio que dispensa settings separadas para produção.
- **A troca da chave tem saída própria.** `--so-chave-rsa` imprime só a linha da chave. Colar a
  saída inteira numa troca trocaria também a `SECRET_KEY` e as senhas, e uma `POSTGRES_PASSWORD`
  nova num `.env` cujo volume `pgdata` já existe não muda a senha no banco.
- **Chaves existentes não são trocadas por esta decisão.** Uma chave de 2048 bits em uso continua
  válida até a próxima troca, que já sai em 3072.

Nada muda para a RP: issuer, descoberta, `jwks_uri`, `alg` e claims ficam iguais, e só o módulo
publicado no JWKS fica mais longo. Por isso esta decisão não tem contraparte na SPA.

## Consequências

Positivas:

- A chave de produção chega a 128 bits de segurança, o nível do hash que o RS256 já usa, e sai do
  prazo de 2030 que pesaria sobre uma chave de 2048 que ninguém rotaciona.
- Um só lugar diz de onde vêm os segredos do `.env`, e a contradição entre o script e a documentação
  da época desaparece.
- A troca da chave não arrasta, por descuido de cópia, as senhas e a `SECRET_KEY`.

Negativas:

- Assinar com 3072 bits custa cerca de três vezes o de 2048 por `id_token`. Numa réplica só, com uma
  assinatura por login, o custo é de milissegundos, mas cresce com o volume.
- O JWKS e cada busca dele pelas RPs ficam maiores: o `n` passa de 342 para 512 caracteres.
- Nada fora do script confere o tamanho. Uma chave de 2048 bits colada à mão sobe o IdP (Identity
  Provider) sem aviso, e a garantia do tamanho é o hábito de usar o script, não um mecanismo.
- A decisão vive numa emenda, e não no arquivo que o leitor abre primeiro. Com o aceite, o índice de
  `docs/arquitetura.md` passa a marcar a 0004 como emendada pela 0028.

## Alternativas consideradas

- **Manter 2048** — o que toda biblioteca aceita e o que já roda. Descartada: 112 bits têm prazo, e
  a chave que o prazo alcança é justamente a que não se troca sem disrupção.
- **4096 bits** — margem maior. Descartada: não chega ao nível seguinte (192 bits exige 7680) e
  custa cerca do dobro de 3072 para assinar, sem ganho diante de um SHA-256 que fica em 128.
- **Tamanhos diferentes em desenvolvimento e em produção, ou um parâmetro de tamanho** — chave de
  dev mais barata. Descartada: a chave de produção sairia de um caminho que o desenvolvimento não
  exercita, que é a situação que esta ADR desfaz.
- **Manter dois scripts, um da chave e um das senhas** — cada um com uma responsabilidade.
  Descartada: dois geradores para um arquivo só é o que deixou a origem da chave de produção sem
  dono, e a separação que importa na operação, trocar só a chave, cabe numa opção do script.
