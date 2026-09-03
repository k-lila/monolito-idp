# 0008. Servir estáticos com WhiteNoise sem manifesto de hash

## Status

Aceito — 2026-09-01

## Contexto

O projeto roda com DEBUG=False em todo ambiente, inclusive na jornada de construção: é decisão
declarada, para que não exista um caminho de desenvolvimento que nunca é exercitado. Com
DEBUG=False o runserver não serve arquivos estáticos; quem serve é o WhiteNoise, a partir do
STATIC_ROOT, o que torna `collectstatic` um passo obrigatório antes de subir a aplicação.

O passo 09 do roadmap prescreveu o backend `CompressedManifestStaticFilesStorage`, que
acrescenta a esse arranjo um manifesto: `collectstatic` grava um `staticfiles.json` mapeando
cada caminho lógico para um nome com hash, e a tag `{% static %}` passa a resolver por consulta
a esse mapa, servindo os arquivos com nome versionado e cache longo.

Essa resolução acontece em tempo de renderização de template, e é aí que ela deixa de ser um
detalhe de entrega. As telas do IdP (Identity Provider) — login, home e consentimento —
compartilham um layout que referencia a folha de estilo por `{% static %}`, e a tela de
consentimento é exercitada por sete casos de teste de integração que renderizam `/o/authorize/`
e leem o HTML resultante. Com manifesto estrito e sem artefato coletado, a renderização levanta
ValueError e esses testes falham por um motivo que nada tem a ver com o que verificam. O teste
passa a depender de um passo de build.

Há uma forma de afrouxar isso sem trocar o backend: o WhiteNoise expõe
WHITENOISE_MANIFEST_STRICT, que faz um caminho ausente do manifesto ser devolvido intacto em
vez de levantar. Essa opção merece consideração explícita porque parece resolver o problema sem
abrir mão do cache-busting.

O contexto de uso é um sandbox exploratório: host único, uma réplica, uma folha de estilo
própria mais os estáticos do admin, sem CDN (Content Delivery Network) e sem tráfego.

## Decisão

Vamos configurar o backend de arquivos estáticos como
`whitenoise.storage.CompressedStaticFilesStorage` — compressão sim, manifesto de hash não —,
mantendo a chave `default` do dicionário STORAGES em FileSystemStorage.

`collectstatic` continua obrigatório antes de subir a aplicação, e o entrypoint do container
continua executando-o. O que deixa de ser obrigatório é executá-lo para que a suíte de testes
passe: sem manifesto, `{% static %}` é concatenação de STATIC_URL com o caminho lógico e não
consulta artefato algum.

Esta decisão diverge do texto do passo 09 do roadmap, e a divergência é deliberada.

## Consequências

Positivas:

- Nenhuma renderização de template depende de um artefato de build. A suíte de integração fica
  verde sem preparação, sem override de settings e sem detecção de ambiente dentro do arquivo
  de configuração.
- A omissão de `collectstatic` aparece como um 404 no recurso, direto e localizável, em vez de
  uma exceção de template que parece problema de template.
- O ciclo de edição de CSS deixa de ter o modo de falha "editei e a tela não mudou" por hash
  desatualizado: o arquivo é sobrescrito na coleta seguinte e o cabeçalho de cache de arquivos
  sem hash é curto. O modo de falha em si não desaparece — `collectstatic` continua obrigatório
  a cada edição, e o WhiteNoise monta o índice de arquivos no boot, de modo que o servidor
  também precisa ser reiniciado.
- A compressão do WhiteNoise é preservada; o custo da mudança é uma palavra na configuração.

Negativas:

- Perdemos cache-busting por nome e o cabeçalho de cache imutável de longa duração. Cada visita
  revalida os estáticos, o que é irrelevante em host único e deixa de ser quando houver volume.
- A garantia de que ninguém receba a versão anterior de um estático depois de um deploy passa a
  depender do cabeçalho de cache, não do nome do arquivo — uma garantia mais fraca.
- Se o projeto sair do sandbox, esta decisão terá de ser revista, e a revisão traz de volta o
  acoplamento entre renderização de template e artefato de build que ela remove. O custo terá
  de ser pago naquele momento, provavelmente com uma etapa de coleta no pipeline de teste.
- O texto do passo 09 do roadmap passa a divergir do código, e quem ler o roadmap sem ler esta
  ADR (Architecture Decision Record) encontrará uma prescrição que não foi seguida.

## Alternativas consideradas

- **`CompressedManifestStaticFilesStorage`, como o roadmap prescreveu** — entrega nome
  versionado e cache longo, que é a razão pela qual foi prescrito. Descartada porque transforma
  a resolução de `{% static %}` numa consulta a artefato de build e, com isso, faz sete casos
  de teste de integração dependerem de um comando externo à suíte. O benefício não se realiza
  em host único sem tráfego; o custo se realiza toda vez que alguém roda os testes.
- **Manter o manifesto e afrouxá-lo com `WHITENOISE_MANIFEST_STRICT = False`** — preservaria a
  prescrição do roadmap trocando a exceção por um retorno tolerante. Descartada por dois
  motivos:
    - mantém o manifesto e, com ele, o que esta decisão existe para remover: a resolução de
      `{% static %}` continua consultando um artefato de build;
    - o caminho que a suíte exercita — o do fallback, sem manifesto — deixa de ser o caminho
      que a aplicação serve depois de `collectstatic`. É a mesma divergência entre configuração
      exercitada e configuração real que motiva a recusa da alternativa seguinte.

O afrouxamento não é rejeitado por trocar falha ruidosa por silenciosa: nisso as duas opções
empatam — sem manifesto, um estático editado e não recoletado também é servido em silêncio na
versão antiga.
- **Configuração de estáticos condicionada ao modo de teste** — resolveria o conflito sem abrir
  mão de nada. Descartada porque criaria exatamente o que a decisão de settings única existe
  para evitar: um caminho de configuração que roda em produção e nunca é exercitado, e outro
  que é exercitado e nunca roda.
- **Executar `collectstatic` antes da suíte** — a solução do lado do processo, não da
  configuração. Descartada porque acopla a execução dos testes a um passo manual cuja omissão
  produz falhas cujo diagnóstico não aponta para a causa.
