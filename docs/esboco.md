# Esboço — Monólito IdP

## A) O que é e como se comporta um monólito IdP

Um **IdP (Identity Provider)** é um serviço que possui os usuários, autentica suas credenciais e *atesta* a identidade deles para outras aplicações. A ideia central é que outros sistemas — chamados *relying parties* (RP) ou clientes — não gerenciem senhas: eles **delegam** a autenticação ao IdP e apenas confiam no que ele responde. É o mesmo formato do botão "Entrar com o Google", onde o Google é o IdP, o site é a relying party e o usuário é a pessoa.

Chamá-lo de **monólito** significa que toda a lógica — modelo de usuário, telas de login e consentimento, servidor de autorização, emissão de tokens e endpoints de descoberta — vive em uma única aplicação implantável, em vez de estar espalhada por vários serviços. Essa é uma escolha deliberada por **compactação**: menos peças móveis, uma fronteira de segurança só e um deploy único em container.

### Comportamento básico

O IdP renderiza suas **próprias** telas de login e consentimento (server-side) e coordena o fluxo de autenticação por **redirecionamento de navegador** (OpenID Connect, *Authorization Code* com PKCE):

1. O usuário clica em "entrar" na relying party (o front-end de teste).
2. A RP redireciona o navegador ao IdP (`/authorize`).
3. O IdP autentica o usuário na sua própria página de login.
4. O IdP redireciona de volta à RP com um **código de autorização**.
5. A RP troca esse código por tokens no endpoint `/token`.
6. O IdP devolve a identidade (ID token + `/userinfo`).

Dois pontos definem o comportamento:

- **A senha só trafega dentro do IdP.** A relying party nunca vê a credencial — recebe apenas um token que afirma quem é o usuário.
- **Sessão de login *e* tokens stateless coexistem.** O IdP mantém uma **sessão de login (SSO)** server-side, para que o usuário não redigite a senha a cada nova RP; e emite **tokens assinados e stateless** que as RPs validam por conta própria usando a chave pública publicada no JWKS. A assinatura é assimétrica (RS256), justamente para que qualquer cliente possa verificar o token sem conhecer o segredo.

---

## B) Núcleo base de tecnologias

| Esfera / Decisão | Recomendação | Pontos fortes | Pontos fracos |
|---|---|---|---|
| **Linguagem** | Python 3.14 | Última série estável; suportada oficialmente pelo DOT 3.4 e pelo Django 5.2 (≥ 5.2.8), então não há conflito de versão no stack | *Wheels* de libs com C ainda maturando na série nova; menos respostas de comunidade para bugs específicos do 3.14 |
| **Framework** | Django 5.2 LTS | LTS com segurança até ~2028; a renderização server-side (templates) é *load-bearing* — é o que desenha as telas de login/consentimento do IdP dentro do monólito | Série 6.x fica de fora; async ainda secundário; upgrade LTS→LTS exige revisar *deprecations* |
| **Servidor OAuth2/OIDC (espinha dorsal)** | django-oauth-toolkit 3.4 | Implementa o *authorization server* completo: authorization code + PKCE, refresh, revogação, **discovery** (RFC 8414) e **JWKS** prontos; registro de *clients* e gestão de tokens via ORM/admin; mantido pelo Jazzband | Superfície de config grande (grants, scopes, chaves, políticas) — fácil configurar inseguro; docs assumem conhecimento de OAuth2/OIDC; o 4.0 vai endurecer a postura OAuth 2.1, exigindo atenção no upgrade futuro |
| **UI de login e consentimento** | Templates Django + views do DOT + `django.contrib.auth` | O DOT já fornece as views de autorização/consentimento; a senha só trafega dentro do IdP, nunca para o front de teste; usa a máquina de sessão/login madura do Django | É preciso estilizar os templates para uma UX decente; SSO com vários *clients* exige cuidado com sessão e com o parâmetro `prompt`; acessibilidade e i18n ficam por sua conta |
| **Assinatura de token e chaves** | RS256 (assimétrico) + JWKS, via `cryptography`/`jwcrypto` | Assinatura assimétrica deixa qualquer RP validar o token só com a **chave pública** (publicada no JWKS) — é a essência da federação; suporta rotação (chave ativa + inativas) sem invalidar tokens vivos | Você é responsável por gerar, guardar e rotacionar a chave RSA (segredo crítico — se vazar, compromete tudo); adiciona dependência com C; HS256 seria mais simples, mas é inadequado para federar com terceiros |
| **Descoberta / contrato** | OIDC Discovery + JWKS (embutidos no DOT) | O contrato do IdP é padronizado e auto-descoberto via `/.well-known` + JWKS: qualquer RP compatível se integra sem doc manual — é um "contrato vivo" superior a um OpenAPI escrito à mão | Cobre só a superfície OIDC; APIs custom (ex.: registro) ainda precisariam de doc à parte (`drf-spectacular`, opcional); exige entender o que cada campo do discovery expõe |
| **Hash de senha** | Argon2 (`argon2-cffi`) | Recomendação oficial do Django; *memory-hard*; o IdP faz a verificação real de credencial, então isso é linha de frente de segurança | Dependência com C; mais CPU/memória por login; parâmetros mal calibrados viram gargalo sob autenticação em massa |
| **Modelo de identidade** | `User` customizado | O IdP é o dono da identidade — modelo próprio desde o início evita a dor de trocar depois; base natural para *claims* futuras (nome, e-mail verificado) | Exige configurar `AUTH_USER_MODEL` no começo; migração posterior é custosa se deixar para depois |
| **Banco de dados** | PostgreSQL 17 | Guarda usuários, *applications* (clients) registrados, grants e tokens do DOT com integridade transacional; suporte de primeira classe no ORM; imagem oficial madura | Peso operacional de serviço stateful; a tabela de tokens cresce e pede limpeza periódica (o DOT oferece comando para isso); tuning sob carga |
| **Cache + sessão SSO** | Redis 7 | Guarda a sessão de login (SSO) do IdP — resolve com coerência o requisito de "sessão em cache", no lugar certo; serve também de cache geral e de *rate limiting* para proteger `/authorize` e `/token` contra força bruta | Serviço extra para operar; se o login SSO depender só dele, indisponibilidade barra novos logins; política de expiração/persistência exige decisão consciente |
| **Configuração** | `django-environ` + `.env` | Idiomático; injeta `DATABASE_URL`/`CACHE_URL` e — crucial — a `OIDC_RSA_PRIVATE_KEY` e a `SECRET_KEY` por variável de ambiente, mantendo chaves fora do código; 12-factor | Validação de tipos fraca; um `.env` com chave privada mal protegido é risco sério; dependência a mais |
| **Servidor de aplicação** | Gunicorn (WSGI) | Padrão previsível de produção; adequado ao monólito síncrono; simples de dimensionar por workers | Sem async nativo; precisa de proxy à frente para TLS (obrigatório num IdP — tudo trafega sob HTTPS) |
| **Arquivos estáticos** | WhiteNoise | Serve o CSS/JS reais das páginas de login e consentimento sem exigir Nginx no MVP; config trivial | Não escala para tráfego pesado; sem recursos de CDN; concentra a responsabilidade no app |
| **Segurança de borda (CORS)** | `django-cors-headers` | Necessário para o SPA de teste chamar `/token`, `/userinfo` e `/jwks` via `fetch` de outra origem; controle fino de origens | O login é por **redirecionamento** e não depende de CORS — a fronteira de segurança dos redirects é a *allowlist* de `redirect_uri` registrada no client, não o CORS; fácil configurar frouxo e criar falsa sensação de segurança |
| **Inicialização + saúde** | entrypoint (`migrate` + espera de deps) + `/health` + `healthcheck` no compose | Garante ordem de boot e migrations aplicadas (inclui as tabelas do DOT); healthcheck informa o orquestrador; elimina falhas intermitentes de subida | Entrypoint mal feito roda migrations concorrentes em múltiplos workers; healthcheck raso dá falsa sensação de saúde |
| **Containerização** | Docker + docker-compose (multi-stage) | Requisito do projeto; orquestra app + Postgres + Redis de forma reprodutível; multi-stage enxuga a imagem | Compose é dev/single-host, não produção real; estado em container exige disciplina de volumes/backup |
| **API REST (opcional)** | Django REST Framework | Só se o IdP também expuser uma API JSON (endpoint de registro, ou um *resource server* de demonstração com scopes); integra nativo com o DOT via permissões por scope | Não é necessário para o fluxo OIDC (DOT + templates já cobrem); incluí-lo sem uso real é peso morto — decida por necessidade, não por reflexo |
