# 0005. Manter a sessão SSO em sessão Django com backend cached_db sobre Redis

## Status

Aceito — 2026-08-29

## Contexto

O IdP tem dois tipos de estado de autenticação que coexistem por desenho, e ambos são
server-side. O estado dos tokens vive nas tabelas do django-oauth-toolkit: o access_token
entregue à relying party é uma string opaca gravada em banco, e só o id_token é JWT
assinado, que a RP valida sozinha. A consequência prática é que a RP que precise validar o
access_token não tem introspecção — o endpoint anunciado responde 403 (ADR 0002) — e recai
sobre /o/userinfo/, uma chamada ao IdP por request, que é justamente o custo que a
assinatura da ADR 0004 existe para evitar. A sessão de login é o outro estado, e é ela que
faz o single sign-on existir — é ela que permite ao usuário chegar a uma segunda relying
party e não redigitar a senha. O que a distingue do estado dos tokens não é ser
server-side: é ser lida em todo request autenticado. Ela está no caminho quente, e por
isso onde ela mora é decisão de desempenho e não só de durabilidade.

Essa sessão é comportamento de produto, não detalhe de infraestrutura. Perdê-la não causa
erro visível: causa um pedido de senha inesperado, que é exatamente a experiência que o
SSO existe para evitar.

O stack já prevê Redis para cache e, mais adiante, rate limiting. Surge a questão de onde
a sessão vive: apenas em Redis, apenas no banco, ou nos dois. Cabe distinguir três modos
de falha que costumam ser confundidos: perda de dados do cache (flush ou eviction),
reinício do serviço de cache com memória vazia, e indisponibilidade de conexão. Os
backends de sessão respondem de forma diferente a cada um, e a escolha só faz sentido se
essa distinção estiver explícita.

## Decisão

Vamos manter a sessão de login como sessão do Django com SESSION_ENGINE =
django.contrib.sessions.backends.cached_db: Postgres como armazenamento durável e Redis
como camada de leitura quente, usando o backend Redis nativo do Django
(django.core.cache.backends.redis.RedisCache), sem django-redis.

A vantagem que estamos comprando é precisa e limitada: sobreviver a perda de dados e a
reinício do Redis. Não estamos comprando tolerância a indisponibilidade de conexão.

Redis segue como cache geral da aplicação e base para o rate limiting futuro.

## Consequências

Positivas:

- A leitura de sessão, que acontece em todo request autenticado, é servida por Redis; o
  Postgres não vira gargalo do caminho quente.
- Flush, eviction ou reinício do Redis não deslogam ninguém: a sessão é reidratada do
  banco. Num serviço de cache que também guarda outras coisas, isso não é hipótese
  remota.
- Usa a máquina de sessão do Django, madura, com expiração, rotação de chave no login e
  invalidação por troca de senha já resolvidas.
- Sem django-redis: o backend Redis é do próprio Django desde a 4.0. A única dependência
  acrescentada é o cliente redis, que o backend nativo importa, e ela está pinada.

Negativas:

- Redis continua sendo dependência dura do IdP. O backend nativo propaga ConnectionError,
  e SessionStore toca o cache em todo request: com o Redis inalcançável, todo request
  autenticado falha, inclusive o admin, e /health responde 503. Em disponibilidade,
  cached_db e sessão em cache puro empatam. Redis deve ser orçado como serviço crítico,
  não como acelerador dispensável.
- Toda criação e modificação de sessão escreve no Postgres, e a tabela django_session
  cresce; clearsessions vira obrigação operacional.
- Há dois lugares onde a sessão existe, e portanto uma janela de incoerência possível
  entre eles.
- O SSO permanece preso ao cookie de sessão de um domínio; federação entre domínios
  distintos exigirá decisão nova.

## Alternativas consideradas

- **Sessão apenas em cache (backends.cache)** — a configuração mais simples e a mais
  rápida, e igual ao cached_db diante de indisponibilidade de conexão. Descartada porque
  perde para ele nos outros dois modos de falha: um flush ou um reinício do Redis
  desloga todo mundo, inclusive as sessões administrativas.
- **Sessão apenas em banco (backends.db)** — durabilidade máxima e uma peça a menos no
  caminho crítico, o que a torna a escolha certa caso Redis se mostre instável na
  prática. Descartada agora por levar ao Postgres uma leitura por request autenticado,
  no caminho mais quente do IdP.
- **django-redis com IGNORE_EXCEPTIONS** — daria a tolerância a indisponibilidade que o
  backend nativo não dá, ao custo de engolir erros de cache. Para sessão isso é o pior
  dos mundos: uma escrita de sessão perdida em silêncio é um logout mudo, sem erro,
  sem log e sem causa aparente. Preferimos falhar alto.
- **Sessão em cookie assinado** — dispensa armazenamento, mas impede revogação
  server-side de sessão, o que é inaceitável para um provedor de identidade.
