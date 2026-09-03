# 0004. Assinar tokens com RS256 e custodiar a chave privada no ambiente

## Status

Aceito — 2026-08-29

## Contexto

A razão de existir de um IdP (Identity Provider) é que terceiros confiem no que ele afirma.
Essa confiança se materializa na assinatura do token: a relying party (RP) precisa poder
verificar, por conta própria, que aquele id_token foi emitido por nós e não foi adulterado —
sem chamar o IdP a cada request e sem compartilhar segredo conosco.

Um segredo simétrico compartilhado inverteria a propriedade essencial: quem pode verificar um
token também pode forjá-lo. Numa federação com múltiplas RPs, isso significa que qualquer
cliente comprometido passaria a poder emitir identidades em nosso nome.

Do outro lado, uma chave assimétrica cria uma obrigação nova: alguém precisa gerar, guardar e
eventualmente rotacionar a chave privada. Ela é o segredo mais crítico do sistema — quem a
possui é o IdP, para todos os efeitos práticos.

O projeto é um sandbox exploratório, sem infraestrutura de gestão de segredos disponível, e
roda em container com configuração 12-factor.

## Decisão

Vamos assinar os tokens com RS256 (RSA com SHA-256) e publicar a chave pública correspondente
no endpoint JWKS (JSON Web Key Set) do django-oauth-toolkit, de modo que qualquer RP valide o
token com material público obtido por discovery.

A chave privada é custodiada como variável de ambiente OIDC_RSA_PRIVATE_KEY, injetada via .env
e lida com django-environ em modo multiline. Ela nunca entra no repositório nem na imagem
Docker. Chaves de desenvolvimento são geradas por scripts/gen_dev_key.sh e são descartáveis por
definição.

Nesta fundação existe uma única chave ativa, sem conjunto de rotação.

## Consequências

Positivas:

- Verificar um token não exige segredo algum: a federação funciona com material público, que é
  a propriedade que torna um IdP útil.
- Nenhuma RP pode forjar um token, nem mesmo aquelas com as quais já nos integramos.
- A chave sai do código e da imagem, e passa a ser rotacionável por redeploy sem alteração de
  código.
- O JWKS estabelece o caminho para rotação futura (chave nova ativa, chave antiga ainda
  publicada) sem invalidar tokens vivos.

Negativas:

- Assumimos a custódia do segredo mais crítico do sistema; um .env mal protegido ou um dump de
  variáveis de ambiente em log compromete tudo, sem sinal visível.
- Trocar a chave hoje invalida na prática as sessões de token em curso, porque não há conjunto
  de rotação — a rotação real será uma decisão posterior, com ADR (Architecture Decision
  Record) própria.
- PEM (Privacy-Enhanced Mail) em variável de ambiente é formato hostil: precisa de escape de
  quebra de linha e falha de maneiras confusas quando mal formatado.
- RS256 é mais caro em CPU que HMAC na assinatura, e a dependência de cryptography adiciona
  extensão em C ao build.
- Os dois modos de falha da variável são opostos, e o perigoso é o menos evidente. Ausente, ela
  falha na leitura das settings nomeando a si mesma: o processo não sobe, o container entra em
  crash-loop e o erro está na primeira linha do log. Presente e vazia, ela deixa o sistema
  subir inteiro: o JWKS responde 200 com um conjunto vazio de chaves, e o único indício é o alg
  anunciado na discovery cair de RS256+HS256 para HS256 — falha silenciosa de ponta a ponta, e
  só percebida do lado da relying party, que não encontra chave com que verificar assinatura
  nenhuma.

## Alternativas consideradas

- **HS256 com segredo compartilhado** — mais simples e sem custódia de par de chaves, mas quem
  valida pode forjar. Inadequado para federar com terceiros, que é o ponto do produto.
- **ES256 (curva elíptica)** — chaves e assinaturas menores e mais rápidas, e igualmente
  assimétrico; descartado apenas por interoperabilidade: RS256 é o algoritmo que toda
  biblioteca de RP suporta sem configuração extra.
- **Chave em arquivo montado por volume** — evita o problema de escape do PEM e reduz o risco
  de vazar em log de ambiente, mas acopla o deploy à existência do volume e afasta a
  configuração do padrão 12-factor usado no resto do projeto.
- **Gerar a chave no boot do container** — dispensaria custódia, mas cada reinício invalidaria
  todos os tokens emitidos e quebraria o cache de JWKS das RPs. Proibido explicitamente.
