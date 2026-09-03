# Esboço — Monólito IdP

## A) O que é e como se comporta um monólito IdP

Um **IdP (Identity Provider)** é um serviço que possui os usuários, autentica suas credenciais
e *atesta* a identidade deles para outras aplicações. A ideia central é que outros sistemas —
chamados *relying parties* (RP) ou clientes — não gerenciem senhas: eles **delegam** a
autenticação ao IdP e apenas confiam no que ele responde. É o mesmo formato do botão "Entrar
com o Google", onde o Google é o IdP, o site é a relying party e o usuário é a pessoa.

Chamá-lo de **monólito** significa que toda a lógica — modelo de usuário, telas de login e
consentimento, servidor de autorização, emissão de tokens e endpoints de descoberta — vive em
uma única aplicação implantável, em vez de estar espalhada por vários serviços. Essa é uma
escolha deliberada por **compactação**: menos peças móveis, uma fronteira de segurança só e um
deploy único em container.

### Comportamento básico

O IdP renderiza suas **próprias** telas de login e consentimento (server-side) e coordena o
fluxo de autenticação por **redirecionamento de navegador**, no padrão OpenID Connect (OIDC),
com *Authorization Code* e PKCE (Proof Key for Code Exchange):

1. O usuário clica em "entrar" na relying party (o front-end de teste).
2. A RP redireciona o navegador ao IdP (`/authorize`).
3. O IdP autentica o usuário na sua própria página de login.
4. O IdP redireciona de volta à RP com um **código de autorização**.
5. A RP troca esse código por tokens no endpoint `/token`.
6. O IdP devolve a identidade (ID token + `/userinfo`).

Dois pontos definem o comportamento:

- **A senha só trafega dentro do IdP.** A relying party nunca vê a credencial — recebe apenas
  um token que afirma quem é o usuário.
- **Sessão de login *e* tokens stateless coexistem.** O IdP mantém uma **sessão de login**
  server-side — o SSO (Single Sign-On) —, para que o usuário não redigite a senha a cada nova
  RP; e emite **tokens assinados e stateless** que as RPs validam por conta própria usando a
  chave pública publicada no JWKS (JSON Web Key Set). A assinatura é assimétrica (RS256, RSA
  com SHA-256), justamente para que qualquer cliente possa verificar o token sem conhecer o
  segredo.

---

## B) Núcleo base de tecnologias

### Linguagem — Python 3.14

A favor:

- Última série estável.
- Suportada oficialmente pelo django-oauth-toolkit (DOT) 3.4 e pelo Django 5.2 (≥ 5.2.8): não
  há conflito de versão no stack.

Contra:

- *Wheels* de bibliotecas com C ainda maturando na série nova.
- Menos respostas de comunidade para bugs específicos do 3.14.

### Framework — Django 5.2 LTS

A favor:

- LTS (Long-Term Support) com segurança até ~2028.
- A renderização server-side (templates) é *load-bearing*: é o que desenha as telas de login e
  consentimento do IdP dentro do monólito.

Contra:

- Série 6.x fica de fora.
- Async ainda secundário.
- Upgrade LTS→LTS exige revisar *deprecations*.

### Servidor OAuth2/OIDC, a espinha dorsal — django-oauth-toolkit 3.4

A favor:

- Implementa o *authorization server* completo: authorization code + PKCE, refresh, revogação,
  **discovery** (RFC 8414) e **JWKS** prontos.
- Registro de *clients* e gestão de tokens via ORM (Object-Relational Mapping) e admin.
- Mantido pelo Jazzband.

Contra:

- Superfície de configuração grande — grants, scopes, chaves, políticas —, e é fácil configurar
  inseguro.
- A documentação assume conhecimento de OAuth2 e OIDC.
- O 4.0 vai endurecer a postura OAuth 2.1, exigindo atenção no upgrade futuro.

### UI de login e consentimento — templates Django + views do DOT + `django.contrib.auth`

A favor:

- O DOT já fornece as views de autorização e consentimento.
- A senha só trafega dentro do IdP, nunca para o front de teste.
- Usa a máquina de sessão e login madura do Django.

Contra:

- É preciso estilizar os templates para uma UX (User Experience) decente.
- SSO com vários *clients* exige cuidado com sessão e com o parâmetro `prompt`.
- Acessibilidade e i18n (internacionalização) ficam por sua conta.

### Assinatura de token e chaves — RS256 + JWKS, via `cryptography`/`jwcrypto`

A favor:

- Assinatura assimétrica deixa qualquer RP validar o token só com a **chave pública**,
  publicada no JWKS: é a essência da federação.
- Suporta rotação — chave ativa mais inativas — sem invalidar tokens vivos.

Contra:

- Você é responsável por gerar, guardar e rotacionar a chave RSA (Rivest–Shamir–Adleman),
  segredo crítico: se vazar, compromete tudo.
- Adiciona dependência com C.
- HS256 seria mais simples, mas é inadequado para federar com terceiros.

### Descoberta e contrato — OIDC Discovery + JWKS, embutidos no DOT

A favor:

- O contrato do IdP é padronizado e auto-descoberto via `/.well-known` mais JWKS: qualquer RP
  compatível se integra sem documentação manual.
- É um "contrato vivo", superior a um OpenAPI escrito à mão.

Contra:

- Cobre só a superfície OIDC.
- APIs (Application Programming Interface) próprias, como um endpoint de registro, ainda
  precisariam de documentação à parte — `drf-spectacular`, opcional.
- Exige entender o que cada campo do discovery expõe.

### Hash de senha — Argon2 (`argon2-cffi`)

A favor:

- Recomendação oficial do Django.
- *Memory-hard*.
- O IdP faz a verificação real de credencial, então isso é linha de frente de segurança.

Contra:

- Dependência com C.
- Mais CPU e memória por login.
- Parâmetros mal calibrados viram gargalo sob autenticação em massa.

### Modelo de identidade — `User` customizado

A favor:

- O IdP é o dono da identidade, e modelo próprio desde o início evita a dor de trocar depois.
- Base natural para *claims* futuras: nome, e-mail verificado.

Contra:

- Exige configurar `AUTH_USER_MODEL` no começo.
- Migração posterior é custosa, se deixar para depois.

### Banco de dados — PostgreSQL 17

A favor:

- Guarda usuários, *applications* (clients) registrados, grants e tokens do DOT com integridade
  transacional.
- Suporte de primeira classe no ORM.
- Imagem oficial madura.

Contra:

- Peso operacional de serviço stateful.
- A tabela de tokens cresce e pede limpeza periódica — o DOT oferece comando para isso.
- Tuning sob carga.

### Cache e sessão SSO — Redis 7

A favor:

- Guarda a sessão de login (SSO) do IdP, que é o requisito de "sessão em cache".
- Serve também de cache geral e de *rate limiting*, para proteger `/authorize` e `/token`
  contra força bruta.

Contra:

- Serviço extra para operar.
- Se o login SSO depender só dele, indisponibilidade barra novos logins.
- Política de expiração e persistência exige decisão consciente.

### Configuração — `django-environ` + `.env`

A favor:

- Idiomático.
- Injeta `DATABASE_URL` e `CACHE_URL` e — crucial — a `OIDC_RSA_PRIVATE_KEY` e a `SECRET_KEY`
  por variável de ambiente, mantendo chaves fora do código.
- 12-factor.

Contra:

- Validação de tipos fraca.
- Um `.env` com chave privada mal protegido é risco sério.
- Dependência a mais.

### Servidor de aplicação — Gunicorn (WSGI)

A favor:

- Padrão previsível de produção.
- Adequado ao monólito síncrono.
- Simples de dimensionar por workers.

Contra:

- Sem async nativo, por ser WSGI (Web Server Gateway Interface).
- Precisa de proxy à frente para TLS (Transport Layer Security), obrigatório num IdP: tudo
  trafega sob HTTPS.

### Arquivos estáticos — WhiteNoise

A favor:

- Serve o CSS e o JS reais das páginas de login e consentimento sem exigir Nginx no MVP
  (Minimum Viable Product).
- Configuração trivial.

Contra:

- Não escala para tráfego pesado.
- Sem recursos de CDN (Content Delivery Network).
- Concentra a responsabilidade no app.

### Segurança de borda — `django-cors-headers`

A favor:

- Necessário para o SPA (Single-Page Application) de teste chamar `/token`, `/userinfo` e
  `/jwks` via `fetch` de outra origem.
- Controle fino de origens.

Contra:

- O login é por **redirecionamento** e não depende de CORS (Cross-Origin Resource Sharing): a
  fronteira de segurança dos redirects é a *allowlist* de `redirect_uri` registrada no client,
  não o CORS.
- É fácil configurar frouxo e criar falsa sensação de segurança.

### Inicialização e saúde — entrypoint + `/health` + `healthcheck` no compose

A favor:

- Garante ordem de boot e migrations aplicadas, inclusive as tabelas do DOT.
- O healthcheck informa o orquestrador.
- Elimina falhas intermitentes de subida.

Contra:

- Entrypoint mal feito roda migrations concorrentes em múltiplos workers.
- Healthcheck raso dá falsa sensação de saúde.

### Containerização — Docker + docker-compose, multi-stage

A favor:

- Requisito do projeto.
- Orquestra app, Postgres e Redis de forma reprodutível.
- Multi-stage enxuga a imagem.

Contra:

- Compose é de desenvolvimento e host único, não produção real.
- Estado em container exige disciplina de volumes e backup.

### API REST, opcional — Django REST Framework

A favor:

- Só entra se o IdP também expuser uma API JSON: endpoint de registro, ou um *resource server*
  de demonstração com scopes.
- Integra nativo com o DOT, por permissões por scope.

Contra:

- Não é necessário para o fluxo OIDC — DOT e templates já cobrem.
- Incluí-lo sem uso real é peso morto: decida por necessidade, não por reflexo.
