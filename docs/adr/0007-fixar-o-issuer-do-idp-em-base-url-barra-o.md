# 0007. Fixar o issuer do IdP em {BASE_URL}/o

## Status

Aceito — 2026-08-29

## Contexto

O issuer é a identidade pública do IdP. Ele vai na claim iss de todo id_token emitido, é a
raiz a partir da qual as relying parties montam a URL do documento de descoberta, e fica
cacheado na configuração de cada RP integrada. Diferente de quase tudo neste projeto,
mudá-lo depois não é uma alteração de código: é reconfiguração simultânea de todas as RPs
e invalidação do iss de todo token vivo.

O django-oauth-toolkit publica seus endpoints sob o prefixo em que suas urls forem
incluídas, e deriva o issuer desse prefixo. Montá-lo na raiz do host publicaria também
suas views de gestão de applications e de tokens autorizados no espaço de nomes raiz,
misturando superfície administrativa da biblioteca com o espaço de rotas do produto.

Há ainda uma divergência entre especificações que só importa quando o issuer tem
componente de path. A OIDC Discovery 1.0 manda concatenar: issuer +
/.well-known/openid-configuration. A RFC 8414, para metadados de authorization server,
manda inserir o segmento well-known antes do path do issuer. Com issuer na raiz, as duas
formas coincidem; com issuer sob um path, não.

## Decisão

Vamos fixar o issuer do IdP em {BASE_URL}/o, montando as urls do django-oauth-toolkit sob
o prefixo /o/ e definindo OIDC_ISS_ENDPOINT coerente com ele.

O documento de descoberta responde, portanto, em
{BASE_URL}/o/.well-known/openid-configuration, que é a forma da OIDC Discovery 1.0. O
README documenta essa URL exata.

Esta é uma decisão deliberada e não uma consequência da escolha de roteamento. Ela deve
ser confirmada antes da primeira relying party integrar; depois disso, é permanente para
efeitos práticos.

## Consequências

Positivas:

- O espaço de rotas do produto fica livre: /login/, /admin/, / e o que vier depois não
  disputam nomes com a biblioteca, e as views administrativas do DOT ficam contidas sob
  um prefixo identificável.
- O prefixo /o/ é a convenção documentada do DOT, o que faz a configuração coincidir com
  os exemplos da biblioteca e reduz a chance de erro sutil.
- A separação entre superfície de protocolo e superfície de produto fica legível na URL,
  o que ajuda em proxy, log e regra de rate limiting mais adiante.

Negativas:

- O issuer passa a ter componente de path, e com isso as formas de descoberta da OIDC
  Discovery 1.0 e da RFC 8414 deixam de coincidir. Uma RP que implemente estritamente a
  RFC 8414 procurará em {BASE_URL}/.well-known/oauth-authorization-server/o e hoje
  receberá 404 — consequência da montagem atual, um único include sob /o/, e não do
  prefixo em si: o DOT exporta metadata_urlpatterns e documenta que deployment sob
  prefixo deve montá-la também na raiz do servidor, onde a forma path-component da RFC
  8414 reflete o sufixo de volta no issuer. Esta fase não a montou: não prometemos essa
  forma de descoberta e documentamos a URL correta. A escolha fica em aberto.
- A string do issuer torna-se irreversível assim que a primeira RP integra. Levar o IdP
  para a raiz do host depois exige janela coordenada com todas elas.
- Uma URL de login com prefixo técnico ("/o/authorize") é menos apresentável que uma na
  raiz, num fluxo em que o usuário vê a barra de endereços no momento em que decide
  confiar.

## Alternativas consideradas

- **Montar na raiz do host (issuer = {BASE_URL})** — faria OIDC Discovery e RFC 8414
  coincidirem, eliminando de vez a divergência, e daria a URL pública mais limpa.
  Descartada porque publicaria as views de gestão do DOT na raiz e colocaria o espaço de
  nomes do produto em disputa permanente com o da biblioteca — um custo de acoplamento
  diário contra um risco de interoperabilidade ocasional e documentável.
- **Subdomínio dedicado (issuer = https://idp.exemplo)** — a separação mais limpa
  possível, com raiz livre e sem componente de path. Descartada nesta fase por exigir DNS
  e certificado próprios, que estão fora do escopo de um compose de host único; continua
  sendo o destino natural se o IdP for exposto de verdade, e é a razão pela qual a string
  do issuer deve ser confirmada antes da primeira integração.
- **Montar metadata_urlpatterns também na raiz, mantendo o issuer em {BASE_URL}/o** —
  atenderia a RP estrita da RFC 8414 sem mover o issuer nem publicar as views de gestão
  do DOT na raiz, compondo listas que a própria biblioteca exporta para esse fim. Não
  adotada nesta fase: nenhuma RP a exige ainda, e a raiz ganharia rotas .well-known antes
  de haver quem as consulte. Permanece disponível.
