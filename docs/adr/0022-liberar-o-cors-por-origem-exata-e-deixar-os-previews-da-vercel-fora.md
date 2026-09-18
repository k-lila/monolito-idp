# 0022. Liberar o CORS por origem exata, uma por ambiente, e deixar os previews da Vercel fora

## Status

Aceito — 2026-09-17

## Contexto

A `nova_api_SPA` é relying party (RP) deste provedor de identidade (IdP, de _Identity
Provider_) e roda no navegador, em origem diferente da dele: `http://localhost:5173` em
desenvolvimento e `https://<spa>` na Vercel em produção. Ela troca o `code` em `/o/token/` e
consulta `/o/userinfo/` por `fetch` — requisições cross-origin, sujeitas a CORS (Cross-Origin
Resource Sharing). O IdP responde a isso com `django-cors-headers` 4.9.0: `CORS_ALLOWED_ORIGINS`
é lista lida do ambiente (`config/settings.py:33`), hoje `http://localhost:5173`; o
`CorsMiddleware` está no topo do `MIDDLEWARE`; a comparação é por esquema e `netloc` literais
(`corsheaders/middleware.py:161-166`). `CORS_ALLOW_CREDENTIALS` é `False` por default
(`corsheaders/conf.py:27`), o projeto não o declara, e a aplicação de página única (SPA, de
_Single-Page Application_) não manda cookie.

Dois dos quatro caminhos que a SPA chama não passam pela allowlist. A descoberta e o JWKS (JSON
Web Key Set) saem do próprio `django-oauth-toolkit` (DOT) com `Access-Control-Allow-Origin: *`
(`oauth2_provider/views/oidc.py:107` e `:129`; o metadado RFC 8414 idem,
`views/metadata.py:154`): são metadados públicos, e a especificação OpenID Connect (OIDC) espera
que qualquer origem os leia. Com a origem na allowlist, o middleware sobrescreve o `*` pela
origem exata (`middleware.py:115`) — é por isso que o `curl` de verificação do contrato mostra
a origem nos quatro caminhos; com uma origem de fora, os dois metadados continuam saindo com
`*`. A allowlist governa, portanto, `/o/token/` e `/o/userinfo/`, os dois que carregam token.

A Vercel dá a cada preview de deploy uma origem própria em `*.vercel.app`, domínio compartilhado
por todos os usuários da plataforma. Liberar previews por padrão exigiria regex, e um regex
sobre `*.vercel.app` aceita qualquer deploy alheio. `docs/contrato-backend.md` §5.2 fixou a
saída; esta ADR (Architecture Decision Record) a registra.

## Decisão

Vamos liberar o CORS por origem literal, uma por ambiente: `http://localhost:5173` em
desenvolvimento e `https://<spa>` em produção, cada uma no `CORS_ALLOWED_ORIGINS` do `.env`
daquele ambiente, sem barra final, com esquema e porta explícitos. Sem
`CORS_ALLOWED_ORIGIN_REGEXES`, sem `CORS_ALLOW_ALL_ORIGINS`, sem `*.vercel.app`.
`CORS_ALLOW_CREDENTIALS` fica no default `False`, sem declaração.

Os previews da Vercel ficam fora do CORS e fora da `Application` de produção. Se a SPA precisar
autenticar num preview, ela entrega ao IdP um alias estável — branch domain ou domínio próprio
de preview —, que ganha uma terceira `Application`, com a própria `redirect_uri`, e uma
terceira origem literal. Nunca um padrão.

O escopo desta decisão é a allowlist. Se os cabeçalhos de CORS devem sair só sob `/o/`
(`CORS_URLS_REGEX`) é o passo 5 de `docs/plano-contrato-backend.md`, não isto.

Contraparte: a ADR 0016 da `nova_api_SPA`
(`../../../nova_api_SPA/docs/adr/0016-publicar-na-vercel-com-vercel-json-variaveis-por-ambiente-e-previews-sem-idp-de-producao.md`)
fixa, do lado dela, que previews não autenticam e que o alias estável é o caminho se um dia for
preciso.

## Consequências

Positivas:

- Uma origem por ambiente é verificável por `curl`, sem a SPA: `Origin: https://<spa>` devolve
  `Access-Control-Allow-Origin: https://<spa>` em `/o/token/` e `/o/userinfo/`, e uma origem
  qualquer não devolve o cabeçalho (`contrato-backend.md` §5.2 e §7).
- Preencher a allowlist é o que torna detectável a posição do `CorsMiddleware` e do
  `LimiteDeTaxaMiddleware`, o alçapão de `docs/runbook.md` que a lista vazia escondia.
- A `Application` de produção só devolve `code` a `https://<spa>/callback`, e só a página em
  `https://<spa>` lê a resposta de `/o/token/` no navegador: duas listas literais fecham a mesma
  fronteira por dois mecanismos.

Negativas:

- É disciplina de operação, não mecanismo: `CORS_ALLOWED_ORIGIN_REGEXES` e
  `CORS_ALLOW_ALL_ORIGINS` continuam disponíveis, e um regex em `config/settings.py` passa em
  `manage.py check` sem aviso. A ADR só deixa escrito que isso contraria a decisão; nenhum teste
  a protege.
- Previews não autenticam; toda verificação contra o IdP real é local ou em produção. É o custo
  que a SPA aceitou na ADR 0016 dela.
- A frase do contrato "a liberação vale para quatro caminhos" (§5.2) é mais larga do que o
  mecanismo: descoberta e JWKS são públicos por decisão da biblioteca, com ou sem allowlist.
  Quem ler o contrato sem esta ADR pode concluir que a allowlist protege os quatro.
- Um terceiro ambiente custa uma `Application` e uma origem a mais, à mão, no admin e no `.env`,
  sem automação.

## Alternativas consideradas

- **`CORS_ALLOWED_ORIGIN_REGEXES` com `^https://.*\.vercel\.app$`** — cobriria todos os previews
  sem tocar o `.env` a cada deploy. Descartada: o domínio é de todos os usuários da Vercel.
  CORS não impede chamada fora do navegador — `curl` chega a `/o/token/` de qualquer lugar, e
  quem protege a troca é o PKCE (Proof Key for Code Exchange) —; o que a allowlist declara é
  quais páginas, no navegador, podem ler as respostas deste IdP, e um domínio compartilhado
  esvazia essa declaração.
- **`CORS_ALLOW_ALL_ORIGINS = True`** — a mesma perda, para o mundo inteiro. `CORS_ALLOW_CREDENTIALS`
  em `False` ainda barraria cookie, mas o token vai no cabeçalho `Authorization`, que o `*` não
  protege. Descartada.
- **Uma `Application` de preview com `redirect_uri` variável** — o DOT compara `redirect_uri` por
  igualdade exata (`tests/test_authorize_guards.py`), e `ALLOW_URI_WILDCARDS` é `False` por
  default (`oauth2_provider/settings.py:85`). Descartada; o alias estável é a forma de ter uma
  URL literal.
