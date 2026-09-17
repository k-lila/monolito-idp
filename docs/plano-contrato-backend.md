# Plano de implementação do contrato do back-end

| Campo | Valor |
| --- | --- |
| Origem | `docs/contrato-backend.md`, conferido contra o código em 2026-09-17 |
| Escopo | só o que precisa mudar — o que já cumpre o contrato não aparece aqui |
| Ordem | a de implementação: cada passo supõe os anteriores fechados |
| Critério de pronto | a checklist do fim inteira marcada, cada item verificado contra o código ou contra o ambiente |

Este documento lista, em ordem, o que o `nova_api` (provedor de identidade, IdP, de _Identity
Provider_) precisa modificar para que a `nova_api_SPA` (relying party, RP) feche o fluxo OpenID
Connect (OIDC) contra ele. O contrato em si — o que se preserva, o que a SPA (Single-Page
Application, aplicação de página única) assume — está em `docs/contrato-backend.md`; aqui está
o caminho. Cada passo traz: os itens que se implementam juntos; as informações que importam
para fazê-lo; os prós e os contras; e a alternativa considerada, com a razão de não servir a
este projeto.

Regras que valem em todos os passos, herdadas do `CLAUDE.md`: relatório antes de alterar
código; pergunta antes de tocar mais de dois arquivos; ADR (Architecture Decision Record)
aceita não se edita, emenda-se ou substitui-se; `.env` untracked e sem cópia — backup antes de
qualquer edição.

---

## Passo 1 — Corrigir o contrato e dar-lhe ponteiro

### A) Itens implementados juntos

1. `docs/contrato-backend.md`, seção 6, item 1 e seção 9, item "`.env` corrigido": remover a
   afirmação de que `DATABASE_URL` aponta para 5433 "sem `POSTGRES_PORT` correspondente".
2. `docs/contrato-backend.md`, seções 8 e 9: alinhar a tabela de decisões (seis linhas) com a
   checklist de registro (cinco itens) — a linha do logout pela RP está numa e falta na outra.
3. `README.md` (mapa de documentos) e `../CLAUDE.md` (raiz `idp/`, tabela "Contrato"): apontar
   para `docs/contrato-backend.md` e para este plano.

### B) Informações relevantes

- O `.env` atual tem `POSTGRES_PORT=5433` e `DATABASE_URL=...@localhost:5433/...`: são
  coerentes. O que falta no `.env` é outra coisa (passo 2).
- A decisão de manter o logout pela RP desligado já tem justificativa registrada em
  `.claude/memory/decisions-arquivo.md:411-427` e no comentário de `config/settings.py:307-310`.
  Ela não está "sem registro"; está sem ADR. A escolha é entre formalizar (uma ADR curta) ou
  retirar a linha da seção 8. Este plano recomenda retirar: a ADR 0010 da SPA já a fixa do lado
  de quem consome, e do lado do IdP a declaração explícita no `settings.py` com a razão ao
  lado cumpre o papel.
- Nenhum arquivo do repositório cita `docs/contrato-backend.md` hoje. O `README.md:122-128`
  lista os documentos de `docs/`; a tabela do `../CLAUDE.md` nomeia `docs/integracao-rp.md`
  como contrato do IdP.

### C) Prós e contras

- Pró: o documento que governa os passos seguintes passa a ser verdadeiro contra o código,
  que é o critério do `CLAUDE.md` para "fechado".
- Pró: com ponteiro, o contrato deixa de ser órfão — quem abre o `README.md` chega nele.
- Contra: são quatro arquivos, três deles fora deste diretório ou fora de `docs/`; exige
  pergunta antes.
- Contra: `docs/contrato-backend.md` e `docs/integracao-rp.md` passam a ser dois lugares que
  descrevem o contrato. A sobreposição é parcial (issuer, claims, PKCE — Proof Key for Code
  Exchange), e este passo não a resolve; só a torna visível pelo ponteiro.

### D) Alternativa considerada

**Fundir o contrato em `docs/integracao-rp.md`** e não ter um segundo documento. Descartada
porque os dois têm leitores diferentes: `integracao-rp.md` fala a qualquer RP futura, em termos
do protocolo; `contrato-backend.md` fala a este projeto sobre uma RP específica, com decisões
de implantação (AWS, Vercel) que não pertencem a um documento de integração genérico. Fundir
levaria a implantação para dentro do contrato público.

---

## Passo 2 — Pôr o `.env` de desenvolvimento em dia com o compose

### A) Itens implementados juntos

1. Acrescentar `PUBLIC_HOST=idp.localhost`.
2. Acrescentar `REDIS_PASSWORD=<openssl rand -hex 32>`.
3. Reescrever `REDIS_URL=redis://:<a mesma senha>@localhost:6379/0`.
4. Preencher `CORS_ALLOWED_ORIGINS=http://localhost:5173`.

### B) Informações relevantes

- Sem `PUBLIC_HOST` e `REDIS_PASSWORD`, o `docker-compose.yml` aborta o `up` pelo `${VAR:?}`
  (linhas 35, 40, 76, 90, 96, 133): nem `docker compose up postgres redis` sobe, e sem os
  dois a suíte não roda. É o primeiro passo de código porque tudo o mais depende da suíte.
- A senha do Redis aparece em dois lugares do `.env` (`REDIS_PASSWORD` e `REDIS_URL`) e nada
  verifica que coincidem; a divergência aparece na primeira operação de cache, com erro que
  fala de host ou porta. Hexadecimal, para não ter `@`, `:`, `/` nem `#` na URL.
- `CORS_ALLOWED_ORIGINS` é lida por `env.list` (`config/settings.py:33`): sem espaço depois da
  vírgula, sem barra final, esquema e porta literais.
- Preencher a allowlist é o que torna detectável a posição do `CorsMiddleware` e do
  `LimiteDeTaxaMiddleware`. As posições hoje estão certas (índices 0 e 4 do `MIDDLEWARE`);
  a verificação com `curl -i -H "Origin: http://localhost:5173"` nos quatro caminhos
  (descoberta, `jwks_uri`, `/o/token/`, `/o/userinfo/`) é a prova, não a leitura.
- **Backup do `.env` antes de editar.** `SECRET_KEY` e `OIDC_RSA_PRIVATE_KEY` não têm cópia.
- Fora do escopo do contrato, mas no mesmo arquivo: o `.env` guarda um comentário obsoleto
  sobre `DJANGO_SUPERUSER_EMAIL`/`DJANGO_SUPERUSER_PASSWORD` ("só é criado se as duas forem
  definidas"), de antes da ADR 0019. O `docker/entrypoint.sh:20` já não lê essas variáveis.
  Vale retirar na mesma edição, para que o `.env` não ensine um mecanismo que não existe.

### C) Prós e contras

- Pró: um arquivo só, untracked — não passa por revisão de código nem por commit.
- Pró: destrava a suíte, o `runserver` e a jornada de container de uma vez.
- Contra: o `.env` é o arquivo mais frágil do projeto; um erro de edição na chave privada
  troca a identidade do IdP sem mensagem de erro. O backup é obrigatório, não recomendado.
- Contra: a senha do Redis vive em dois lugares por construção do compose; este passo herda a
  fragilidade, não a cria.

### D) Alternativa considerada

**Recriar o `.env` a partir do `.env.example`** com `scripts/gen_dev_key.sh`. Descartada
porque geraria `OIDC_RSA_PRIVATE_KEY` e `SECRET_KEY` novas: todo `id_token` já emitido
deixaria de validar e toda sessão cairia. Em desenvolvimento isso custa pouco, mas a jornada de
container está com um volume `pgdata` cujas `Application`s e contas continuam valendo, e não
há razão para trocar a chave quando o problema são três variáveis ausentes.

---

## Passo 3 — Registrar as decisões cruzadas de contrato

### A) Itens implementados juntos

1. ADR 0021: `skip_authorization=True` para a `Application` de primeira parte.
2. ADR 0022: CORS (Cross-Origin Resource Sharing) por origem exata; previews da Vercel fora.
3. ADR 0023: sem páginas de cadastro ou edição de perfil nesta fase.
4. `docs/arquitetura.md`: índice das ADRs atualizado. `docs/integracao-rp.md`: orientação de
   `skip_authorization` para RP de primeira parte.
5. Cada ADR aponta para a correspondente na SPA (`nova_api_SPA/docs/adr/`), e vice-versa.

### B) Informações relevantes

- A regra da raiz: decisão que afeta os dois projetos é registrada nos dois, uma ADR apontando
  para a outra. A SPA vai fechar "sessão no reload" (§7.2 do plano dela) contando com o pulo
  do consentimento; sem ADR daqui, ela assume o que ninguém decidiu.
- `REQUEST_APPROVAL_PROMPT` é `"force"` por default do DOT (django-oauth-toolkit) 3.4.1
  (`settings.py:82` da biblioteca), não sobrescrito: tela de consentimento em toda ida a
  `/o/authorize/`. `skip_authorization` é campo de `Application`, por cliente; não altera o
  default global.
- A ADR 0022 é a que fixa a disciplina que nenhum código impõe: nem regex, nem
  `CORS_ALLOW_ALL_ORIGINS`, nem `*.vercel.app` (domínio compartilhado por todos os usuários da
  Vercel). Se a SPA precisar de preview autenticado, entrega um alias estável, que vira uma
  terceira `Application` e uma terceira origem.
- A ADR 0023 fecha a desavença com a SPA, que assumia cadastro e perfil no IdP, e nomeia as
  pré-condições de um cadastro público futuro: validadores de senha, limite de taxa no
  cadastro, verificação de e-mail e só então `email_verified`.
- Escrever em `docs/adr/**` exige confirmação pelo `.claude/settings.json`; o formato é o de
  `docs/adr/template-adr.md`. São mais de dois arquivos: pergunta antes.
- Ordem dentro do passo: as três ADRs primeiro, o índice e o `integracao-rp.md` depois, no
  mesmo commit — o índice cita número e título, e o título não muda depois de aceito.

### C) Prós e contras

- Pró: os passos 4 e 9 (registro das `Application`s) passam a executar uma decisão, em vez de
  tomá-la no admin.
- Pró: a SPA pode fechar as ADRs dela apontando para números que existem.
- Contra: três ADRs antes de qualquer código de integração alongam o caminho até o primeiro
  login real.
- Contra: a ADR 0022 registra uma disciplina de operação, não um mecanismo. Nada no IdP impede
  que alguém marque `skip_authorization` numa `Application` de terceiro ou ponha um regex em
  CORS; a ADR só deixa escrito que isso contraria a decisão.

### D) Alternativa considerada

**Trocar o default global para `REQUEST_APPROVAL_PROMPT="auto"`**, que pula a tela quando já
existe token válido para aquele cliente e escopo, sem tocar a `Application`. Descartada
porque valeria para toda RP futura, inclusive de terceiro, e porque o pulo dependeria do estado
da tabela de tokens: a SPA guarda tokens só em memória e volta ao `/o/authorize/` a cada reload,
de modo que a tela reapareceria a cada F5 sempre que o token anterior tivesse expirado — a
mesma experiência que se quer evitar, só que intermitente.

---

## Passo 4 — Registrar a `Application` de desenvolvimento e fechar o fluxo em `localhost`

### A) Itens implementados juntos

1. `Application` de dev pelo admin (`/admin/oauth2_provider/application/add/`): `client_type`
   `public`; `authorization_grant_type` `authorization-code`; `algorithm` `RS256`;
   `redirect_uris` só `http://localhost:5173/callback`; `skip_authorization` marcado.
2. Duas contas de teste: uma com `first_name`/`last_name` preenchidos, outra com os dois em
   branco (`name` = `""`).
3. Entrega à SPA: `issuer` `http://localhost:8000/o` e o `client_id` da `Application`.
4. Verificação: descoberta, JWKS (JSON Web Key Set) e CORS por `curl`; fluxo PKCE à mão de
   `docs/receita.md` contra essa `Application`; segunda autorização sem tela de consentimento;
   `/o/userinfo/` com token inválido → 401 com cabeçalho de CORS.

### B) Informações relevantes

- Nada disto é código: é dado de banco e verificação. Não há commit.
- `algorithm` vazio é a falha silenciosa que o `docs/runbook.md` cataloga: o `code` é emitido,
  a troca fecha, e o `id_token` não vem. Conferir no admin antes de entregar o `client_id`.
- `redirect_uris` é comparada por igualdade exata (`tests/test_authorize_guards.py`): barra
  final, porta e esquema literais. Uma URL só — a de produção vai noutra `Application`
  (passo 9).
- A conta sem nome existe para a SPA exercitar `name` presente e vazia, caso que o IdP falso
  de `nova_api_SPA/dev/idp-fake/` não reproduz. `get_full_name()` de `AbstractUser` devolve
  `""` com os dois campos em branco (`accounts/oauth_validators.py`).
- A SPA só é considerada integrada quando fecha contra o IdP real (regra da raiz). Este passo
  é o primeiro em que isso é possível; o login em `/app` com as claims é o critério do lado
  dela.

### C) Prós e contras

- Pró: primeiro fluxo real ponta a ponta, sem infraestrutura nova, em texto claro em loopback
  — sem instalar a CA (autoridade certificadora) do Caddy no navegador.
- Pró: cada verificação tem `curl` correspondente na seção 7 do contrato; o passo fecha ou não
  fecha, sem interpretação.
- Contra: `Application` e contas vivem no `pgdata` da jornada de construção. `docker compose
  down -v` apaga os dois, e o passo se repete inteiro. Não há fixture nem comando de
  gerenciamento que os recrie.
- Contra: a jornada de container (`https://idp.localhost`) não é exercitada aqui; fica como
  segunda verificação antes da AWS (passo 8), e o `client_id` dela é o mesmo, porque o banco é
  o mesmo, mas o issuer não.

### D) Alternativa considerada

**Integrar em dev pela jornada de container**, `https://idp.localhost`, que é a topologia de
produção. Descartada como primeiro passo porque exige a CA local do Caddy confiada no navegador
de quem desenvolve a SPA, e porque o issuer `https://idp.localhost/o` obrigaria a SPA a ter uma
terceira configuração (dev-container) além de dev e produção. A topologia de produção
verifica-se no passo 8, uma vez, antes de abrir a porta.

---

## Passo 5 — Endurecer o que deixa de ser inventário fora de `localhost`

### A) Itens implementados juntos

1. `config/settings.py`: declarar `AUTH_PASSWORD_VALIDATORS` com os quatro validadores do
   Django (`UserAttributeSimilarityValidator`, `MinimumLengthValidator`,
   `CommonPasswordValidator`, `NumericPasswordValidator`).
2. `config/urls.py`: montar sob `o/` só `metadata_urlpatterns + base_urlpatterns +
   oidc_urlpatterns` do DOT, com o namespace `oauth2_provider` preservado — o que retira
   `/o/applications/…` e `/o/authorized_tokens/` do URLConf.
3. `config/settings.py`: `ALLOWED_REDIRECT_URI_SCHEMES = ["https"] if BEHIND_TLS_PROXY else
   ["http", "https"]` dentro de `OAUTH2_PROVIDER`.
4. `config/settings.py`: `CORS_URLS_REGEX = r"^/o/"`.
5. `docs/seguranca.md`: os itens 1 e 2 saem do inventário e entram no que o IdP protege.
6. Testes, pelo `quality-assurance` → `tester`: `/o/applications/register/` responde 404 para
   conta autenticada; `password_validation` recusa senha de quatro dígitos; cabeçalho de CORS
   ausente em `/accounts/login/` com `Origin` na allowlist.

### B) Informações relevantes

- `AUTH_PASSWORD_VALIDATORS` não está declarada em `config/settings.py`; o default do Django é
  lista vazia (`docs/seguranca.md:119`). O teto de cinco tentativas do axes supõe senha forte
  — sem validador, o teto protege uma senha `1234`. Validador só age ao definir senha: contas
  existentes não são tocadas, e as contas de teste do passo 4 precisam de senha que passe.
- `/o/applications/register/` vem de `management_urlpatterns` (`oauth2_provider/urls.py:67-81`)
  pelo `include("oauth2_provider.urls")` de `config/urls.py`. A view exige só sessão
  autenticada (`docs/seguranca.md:102`): qualquer conta com senha registra uma `Application`
  com a `redirect_uri` que quiser. A descoberta monta cada endpoint por `reverse()` no
  namespace `oauth2_provider` — o namespace tem de sobreviver à montagem seletiva:
  `path("o/", include((metadata + base + oidc, "oauth2_provider"), namespace="oauth2_provider"))`.
  `dcr_urlpatterns` (Dynamic Client Registration) fica fora também; `DCR_ENABLED` é `False`
  por default (`settings.py:166` da biblioteca), então nada muda ali.
- `ALLOWED_REDIRECT_URI_SCHEMES` é global à instância (`settings.py:83` da biblioteca, default
  `["http", "https"]`). Fixá-la em `["https"]` sem condição quebraria a `Application` de dev,
  cuja `redirect_uri` é `http://localhost:5173/callback`. Condicionar a `BEHIND_TLS_PROXY` é o
  precedente da ADR 0006: o endurecimento segue a variável de transporte, nunca `DEBUG`. Em
  produção, `BEHIND_TLS_PROXY` é `True` pelo compose (`docker-compose.yml:104`).
- `CORS_URLS_REGEX = r"^/o/"` faz o `django-cors-headers` emitir cabeçalho só na superfície de
  protocolo: `/admin/` e `/accounts/login/` nunca são chamados cross-origin. A descoberta
  (`/o/.well-known/…`), o JWKS, `/o/token/` e `/o/userinfo/` estão todos sob `/o/`.
- São dois arquivos de código, um de documentação e testes novos: pergunta antes, e a rota é a
  de `feature` ou `test-gap` do `.claude/commands/`, conforme o orquestrador classificar.

### C) Prós e contras

- Pró: os quatro itens são pequenos, locais e verificáveis pela suíte; nenhum toca o contrato
  público da seção 2 do `contrato-backend.md`.
- Pró: fechá-los antes das ADRs de exposição (passo 7) evita que a exposição espere por
  endurecimento — e evita que alguém abra a porta "só para testar" com o registro aberto.
- Contra: retirar `management_urlpatterns` remove também `/o/applications/` (lista) e
  `/o/authorized_tokens/`; quem operava por ali passa a usar `/admin/`, que já exige
  `is_staff`. É perda de conveniência, não de função.
- Contra: `ALLOWED_REDIRECT_URI_SCHEMES` condicional é um quarto valor que difere entre a
  jornada de construção e a de container. Os três primeiros (`SESSION_COOKIE_SECURE`,
  `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS`) já são assim e a suíte já os neutraliza
  (`tests/runner.py`); o quarto entra no mesmo mecanismo.
- Contra: os validadores de senha valem em dev também. Senha de teste passa a ter de cumprir
  os quatro; é o preço de uma norma só.

### D) Alternativa considerada

**Restringir `/o/applications/register/` a `is_staff` por decorator ou middleware**, mantendo
as rotas. Descartada porque acrescentaria código de produção (um `dispatch` sobrescrito ou uma
condição num middleware) para proteger uma superfície que o projeto não usa — o registro de
`Application` é pelo admin, e o `contrato-backend.md` §5.1 já o diz. Retirar a rota é
mecanismo mais simples, sem código novo, e a ausência (404) é verificável pela suíte tanto
quanto uma recusa (403) seria. Para `ALLOWED_REDIRECT_URI_SCHEMES`, a alternativa de não
declarar (manter o default) foi descartada porque em produção deixaria um `http://` entrar
por engano numa `Application` e o erro só apareceria como `redirect_uri` recusada na hora do
login, sem indicar a causa.

---

## Passo 6 — Decidir o issuer e romper a premissa de sandbox

### A) Itens implementados juntos

1. ADR 0024: confirmar e congelar o issuer de produção em `https://<dominio-proprio>/o`
   (a confirmação que a ADR 0007:35 exige antes da primeira RP).
2. ADR 0025: expor o IdP na AWS — um salto de proxy só (Caddy do compose, sem balanceador),
   certificado por ACME (Automatic Certificate Management Environment), portas 80/443
   publicadas fora de loopback, `TRUSTED_PROXY_COUNT = 1` mantido.
3. `CLAUDE.md` (deste projeto), `README.md` ("O escopo é o de sandbox exploratório") e
   `docs/arquitetura.md`: a premissa "portas publicadas em `127.0.0.1`" passa a valer para
   Postgres e Redis, e o proxy é a exceção declarada.
4. Emenda à ADR 0017: a exposição fora de loopback, que ela previa como "editar esse endereço à
   mão" (linha 60), ganha a ADR que a governa.

### B) Informações relevantes

- O domínio escolhido é permanente por dois motivos independentes: o issuer fica cacheado em
  cada RP (ADR 0007), e o HSTS (HTTP Strict Transport Security) de um ano marca o nome no
  navegador de quem o visitar (ADR 0017:107-111). Trocar depois exige reconfigurar a SPA e
  limpar HSTS em cada navegador. Nome atribuído pela AWS (`*.amazonaws.com`) não serve: é
  reciclável e não recebe certificado público.
- O `reverse_proxy` do Caddy substitui `X-Forwarded-For` (`docker/Caddyfile`, medido no
  `caddy:2.11.4`). Um balanceador (ALB, CloudFront) à frente faria todos os usuários da SPA
  chegarem com um endereço só: o limitador de taxa (120/min em `/o/token/` e `/o/authorize/`,
  `config/settings.py`) passaria a contar a SPA inteira como um cliente, e a trilha de auditoria
  perderia a origem. É o defeito que a ADR 0015 impede por código e a ADR 0020 marca na linha,
  reaparecendo por topologia.
- ACME por HTTP-01 precisa da porta 80 alcançável da internet. O volume `caddydata` guarda a
  conta ACME e o certificado; recriá-lo esgota o limite de emissão do Let's Encrypt.
- Escrever em `docs/adr/**` exige confirmação; são mais de dois arquivos.

### C) Prós e contras

- Pró: sem estas duas ADRs, cada linha do passo 8 contraria compromisso escrito — o `CLAUDE.md`
  diz que a premissa de sandbox "não é licença para decidir de qualquer jeito".
- Pró: a ADR 0024 fecha a pendência mais antiga do projeto: a ADR 0007 pediu esta confirmação
  antes da primeira RP, e a primeira RP é agora.
- Contra: a ADR 0025 rompe a premissa de quatro documentos e de várias ADRs; a emenda à 0017 e
  as edições em `CLAUDE.md`, `README.md` e `arquitetura.md` são custo de coerência, não de
  função.
- Contra: "um salto só" é decisão de topologia que limita a escala: uma réplica, uma instância.
  Para este escopo (uma SPA, uma instância) é o correto; se houver balanceador um dia, é ADR
  nova com `trusted_proxies` no Caddy e `TRUSTED_PROXY_COUNT` remedido.

### D) Alternativa considerada

**Expor por um balanceador gerenciado (ALB) com certificado do ACM (AWS Certificate Manager)**,
e o Caddy só como proxy interno — o arranjo mais comum na AWS. Descartada porque acrescenta um
segundo salto que o código não mede: `TRUSTED_PROXY_COUNT` teria de subir para 2, o Caddy
teria de declarar o ALB em `trusted_proxies` para anexar em vez de substituir `X-Forwarded-For`,
e o comportamento medido no `Caddyfile` (substituição) deixaria de valer. O ganho — TLS
gerenciado e escala horizontal — não é necessidade deste escopo, e o custo é remedir a cadeia
inteira de origem (ADRs 0015, 0018, 0020) contra uma topologia que não se vai usar.

---

## Passo 7 — Alterar o transporte e a publicação para a exposição

### A) Itens implementados juntos

1. `docker/Caddyfile`: retirar `tls internal`; o comentário que a justifica passa a registrar
   o contrário — ACME é o default do Caddy sem a diretiva, e é isso que se quer.
2. `docker-compose.yml`: as publicações do serviço `proxy` passam de `127.0.0.1:80:80` e
   `127.0.0.1:443:443` para `80:80` e `443:443`. Postgres e Redis continuam em `127.0.0.1`.
3. `docs/runbook.md`, seção 19 (Caddy): o sintoma "log do proxy fala de desafio ou de conta
   ACME" deixa de significar "faltou `tls internal`" e passa a significar "porta 80 não
   alcançável da internet, ou DNS não propagado".
4. `docs/receita.md`: o passo de extrair a CA local e confiá-la no navegador passa a valer só
   para a jornada de container em `idp.localhost`, não para produção.

### B) Informações relevantes

- Este passo é uma edição por arquivo, mas os quatro arquivos são um só commit: `tls internal`
  fora com a porta ainda em loopback produz um Caddy que tenta ACME, falha no desafio e serve
  502 ou nada (`docker/Caddyfile`, comentário da diretiva; `docs/runbook.md:795`).
- A jornada de container em `idp.localhost` deixa de funcionar com o `Caddyfile` sem
  `tls internal`: `.localhost` não recebe certificado público. Ou se aceita perder a jornada
  de container local, ou o `Caddyfile` passa a condicionar a diretiva. Este plano recomenda
  condicionar por variável de ambiente lida pelo Caddy — `{$CADDY_TLS}` com valor `internal`
  no `.env` de dev e ausente no de produção — porque é o mesmo mecanismo do `{$PUBLIC_HOST}`
  que o arquivo já usa. Isso acrescenta um item ao `.env.example` e ao passo 2.
- A suíte na jornada de container continua neutralizando `SECURE_SSL_REDIRECT`
  (`tests/runner.py`); nada muda para ela.
- `tests/test_endurecimento_transporte.py` cobre o Django atrás do proxy, não o Caddy. O
  Caddy verifica-se pelo `curl` do passo 8.

### C) Prós e contras

- Pró: são as duas únicas linhas de infraestrutura que separam o sandbox da exposição; tudo o
  mais já está medido e testado atrás de `BEHIND_TLS_PROXY`.
- Pró: com a diretiva condicionada, a jornada de container local sobrevive e continua sendo a
  segunda verificação antes da AWS.
- Contra: publicação sem endereço é DNAT à frente do firewall do host (comentário de
  `docker-compose.yml:9`); o security group da instância passa a ser a única barreira, e ele
  não está em arquivo versionado. Fica no `README.md` como pré-condição, sem mecanismo que o
  verifique.
- Contra: o `Caddyfile` com placeholder condicional é um segundo valor que difere entre dev e
  produção, e um `{$CADDY_TLS}` mal escrito no `.env` de produção (com `internal` por engano)
  serve certificado que nenhum navegador aceita — sintoma claro, mas em produção.

### D) Alternativa considerada

**Dois `Caddyfile`s**, um de dev com `tls internal` e um de produção sem, escolhidos pelo
`docker-compose.yml` por variável. Descartada porque duplica o `reverse_proxy` e as quarenta
linhas de comentário que justificam a substituição de `X-Forwarded-For`, e porque conteúdo
duplicado exige `diff` vazio a cada mudança (regra da skill `estilo-de-prosa`). Uma diretiva
sob placeholder mantém um arquivo só, com uma diferença só.

---

## Passo 8 — Montar a instância e o `.env` de produção

### A) Itens implementados juntos

1. Domínio próprio com registro DNS `A` apontando para a instância; `PUBLIC_HOST=<dominio>`.
2. Security group: 80 e 443 da internet; SSH restrito ao endereço de quem opera; nada mais.
3. `.env` de produção gerado **na instância**: `SECRET_KEY` nova, `OIDC_RSA_PRIVATE_KEY` nova
   (`scripts/gen_dev_key.sh`), `POSTGRES_PASSWORD` e `REDIS_PASSWORD` novas, `DEBUG=False`,
   `PUBLIC_HOST`, `CORS_ALLOWED_ORIGINS=https://<spa>`, sem `CADDY_TLS`.
4. `docker compose up --wait`; superusuário por `docker compose run --rm app python manage.py
   createsuperuser` (ADR 0019).
5. Backup do `.env` e snapshot dos volumes `pgdata`, `auditlog`, `caddydata`.
6. Verificação: `GET http://<host>/` → 308 para `https`; certificado aceito pelo navegador sem
   aviso; `https://<host>/o/.well-known/openid-configuration` com `"issuer": "https://<host>/o"`,
   `code_challenge_methods_supported: ["S256"]`, sem `end_session_endpoint`; depois do primeiro
   acesso externo, `ip_edge` = `peer` nas linhas de `logs/audit.log` do volume `auditlog`.

### B) Informações relevantes

- A chave privada de produção não deve existir em nenhuma outra máquina: é a identidade do IdP,
  e o `CLAUDE.md` já diz que `git clean -xd` a apaga sem volta. O backup é do `.env` inteiro,
  fora da instância, cifrado.
- `ip_edge` = `gateway` depois do acesso externo significa que a publicação ainda passa pelo
  proxy de userland do Docker (ADR 0017:112, ADR 0020) — a porta continua em loopback, ou o
  acesso veio do próprio host. Enquanto disser `gateway`, a exposição não tomou efeito.
- O `docker-compose.yml` deriva `BASE_URL`, `ALLOWED_HOSTS` e `BEHIND_TLS_PROXY=True` de
  `PUBLIC_HOST` (linhas 90-104); nenhum deles entra no `.env` de produção.
- O primeiro `up` com ACME demora o tempo do desafio HTTP-01; `--wait` espera pelo healthcheck
  do `app`, que não passa pelo proxy (`ALLOWED_HOSTS` inclui `127.0.0.1` por isso).
- Nenhum arquivo do repositório muda neste passo; é operação. O que se versiona é o `README.md`
  com a pré-condição do security group, se ainda não estiver (passo 6, item 3).

### C) Prós e contras

- Pró: tudo que este passo executa foi decidido nos passos 6 e 7 e medido antes; o passo é
  reproduzível a partir do `README.md` e do `docs/receita.md`.
- Pró: `ip_edge` dá uma verificação binária de que a topologia é a decidida — sem ela, o
  limitador e a trilha colapsariam em silêncio.
- Contra: `.env` gerado à mão numa instância é o ponto único de falha do IdP de produção; um
  snapshot esquecido e a identidade se perde com a instância.
- Contra: o security group é configuração fora do repositório, sem teste; a regra vive no
  `README.md` e na disciplina de quem opera.

### D) Alternativa considerada

**Copiar o `.env` de desenvolvimento para a instância e trocar o `PUBLIC_HOST`.** Descartada
porque levaria a chave privada de dev — que já esteve em máquina de desenvolvimento, em
backup local e possivelmente em terminal — para assinar `id_token`s de produção. A chave de
produção nasce na instância e não sai dela; a de dev continua assinando só `localhost`.

---

## Passo 9 — Registrar a `Application` de produção e entregar à SPA

### A) Itens implementados juntos

1. `Application` de produção pelo `/admin/` da instância: `public`, `authorization-code`,
   `RS256`, `redirect_uris` só `https://<spa>/callback`, `skip_authorization` marcado.
2. Entrega à SPA: `issuer` `https://<dominio>/o` e o `client_id` de produção.
3. `docs/integracao-rp.md`: o issuer de produção passa a constar ao lado do de construção.
4. Verificação: os quatro caminhos com `Origin: https://<spa>` devolvem
   `Access-Control-Allow-Origin: https://<spa>`, e `OPTIONS` em `/o/userinfo/` com
   `Access-Control-Request-Headers: authorization` responde a preflight; fluxo PKCE à mão de
   `docs/receita.md` fecha com `id_token` completo (`iss`, `aud`, `sub`, `name`, `email`) e sem
   consentimento na segunda autorização; `/o/userinfo/` com token inválido → 401 com cabeçalho
   de CORS.

### B) Informações relevantes

- `client_id` de produção é distinto do de dev por três razões independentes: a `Application`
  de produção nunca aceita retorno em `http://localhost`; revogar ou apagar a de dev não toca
  produção; a trilha de auditoria distingue as duas.
- Com `ALLOWED_REDIRECT_URI_SCHEMES = ["https"]` sob `BEHIND_TLS_PROXY` (passo 5), o admin
  recusa `http://` no campo — é aqui que aquele item paga.
- A verificação de CORS com a lista preenchida é a que torna detectável a posição do
  `CorsMiddleware` e do limitador; foi feita em dev (passo 2), repete-se em produção porque o
  processo é outro.
- Depois deste passo, a etapa final é da SPA: login em produção chega a `/app` com as claims. É
  o critério da regra da raiz — fluxo fechado contra o IdP real.

### C) Prós e contras

- Pró: um arquivo versionado (`integracao-rp.md`) e o resto é dado de banco; nenhuma decisão
  nova.
- Pró: a checklist da seção 7 do `contrato-backend.md` fecha inteira com `curl` e um navegador,
  sem a SPA.
- Contra: a `Application` de produção não é versionada nem exportável; vive no `pgdata` da
  instância. O snapshot do passo 8 é o que a preserva.
- Contra: entregar `issuer` e `client_id` é comunicação entre projetos sem canal versionado; o
  `contrato-frontend.md` da SPA é onde o valor deve ficar escrito.

### D) Alternativa considerada

**Uma `Application` só, com as duas `redirect_uris`** (dev e produção), e um `client_id` só.
Descartada porque a `Application` de produção passaria a aceitar retorno em
`http://localhost:5173/callback` — qualquer pessoa com o `client_id` (que é público) e um
servidor local receberia o `code` de um login em produção; o PKCE impede a troca, mas não a
captura. Além disso, `ALLOWED_REDIRECT_URI_SCHEMES = ["https"]` recusaria a URL de dev na
mesma `Application`, e as duas não poderiam coexistir.

---

## Checklist

Marcar cada item só quando verificado contra o código ou contra o ambiente, nunca contra um
documento.

### Passo 1 — contrato e ponteiros

- [ ] `docs/contrato-backend.md` §6 e §9 sem a afirmação sobre `POSTGRES_PORT`
- [ ] `docs/contrato-backend.md` §8 e §9 com o mesmo conjunto de decisões
- [ ] `README.md` e `../CLAUDE.md` apontando para `docs/contrato-backend.md` e para este plano

### Passo 2 — `.env` de desenvolvimento

- [x] Backup do `.env` feito antes de editar
- [x] `PUBLIC_HOST`, `REDIS_PASSWORD` presentes; `REDIS_URL` com a mesma senha
- [x] `CORS_ALLOWED_ORIGINS=http://localhost:5173`
- [x] Comentário obsoleto de `DJANGO_SUPERUSER_*` retirado
- [x] `docker compose up postgres redis` sobe e `manage.py test` passa
- [x] `curl -i -H "Origin: http://localhost:5173"` nos quatro caminhos devolve
      `Access-Control-Allow-Origin`

### Passo 3 — ADRs cruzadas

- [ ] ADR 0021 `skip_authorization` aceita, apontando para a ADR da SPA
- [ ] ADR 0022 CORS por origem exata, previews fora, aceita, apontando para a ADR da SPA
- [ ] ADR 0023 sem páginas de conta nesta fase, aceita, apontando para a ADR da SPA
- [ ] `docs/arquitetura.md` com as três no índice
- [ ] `docs/integracao-rp.md` com a orientação de `skip_authorization`

### Passo 4 — integração em `localhost`

- [ ] `Application` de dev: `public`, `authorization-code`, `RS256`,
      `http://localhost:5173/callback`, `skip_authorization`
- [ ] Conta de teste com nome e conta sem nome
- [ ] `issuer` `http://localhost:8000/o` e `client_id` entregues à SPA
- [ ] Fluxo PKCE à mão fecha; segunda autorização sem consentimento
- [ ] `/o/userinfo/` com token inválido → 401 com cabeçalho de CORS
- [ ] SPA faz login em `/app` contra o IdP real

### Passo 5 — endurecimento

- [ ] `AUTH_PASSWORD_VALIDATORS` declarada com os quatro validadores
- [ ] `/o/applications/register/` responde 404; descoberta continua a montar os endpoints
- [ ] `ALLOWED_REDIRECT_URI_SCHEMES` condicionada a `BEHIND_TLS_PROXY`
- [ ] `CORS_URLS_REGEX = r"^/o/"`; `/accounts/login/` sem cabeçalho de CORS
- [ ] `docs/seguranca.md` atualizado
- [ ] Testes novos verdes na suíte inteira (`manage.py test`)

### Passo 6 — ADRs de exposição

- [ ] ADR 0024 issuer de produção congelado, referindo a ADR 0007 e a ADR da SPA
- [ ] ADR 0025 exposição na AWS: um salto, ACME, portas fora de loopback
- [ ] Emenda à ADR 0017 apontando para a 0025
- [ ] `CLAUDE.md`, `README.md`, `docs/arquitetura.md` com a premissa atualizada

### Passo 7 — transporte e publicação

- [ ] `docker/Caddyfile` com `tls` condicionado por placeholder; `.env.example` com a variável
- [ ] `docker-compose.yml` com 80/443 publicadas sem endereço; Postgres e Redis em `127.0.0.1`
- [ ] `docs/runbook.md` §19 e `docs/receita.md` atualizados
- [ ] Jornada de container em `idp.localhost` ainda sobe com certificado da CA local

### Passo 8 — instância e `.env` de produção

- [ ] Domínio próprio com DNS apontando; `PUBLIC_HOST` definido
- [ ] Security group: só 80/443 da internet, SSH restrito
- [ ] `.env` gerado na instância, chaves e senhas novas, `DEBUG=False`, `CORS_ALLOWED_ORIGINS`
- [ ] Superusuário por `createsuperuser`
- [ ] Backup cifrado do `.env` fora da instância; snapshot de `pgdata`, `auditlog`, `caddydata`
- [ ] `http://` → 308 `https://`; certificado aceito sem aviso
- [ ] Descoberta com `"issuer": "https://<host>/o"`, `S256`, sem `end_session_endpoint`
- [ ] `ip_edge` = `peer` na trilha após acesso externo

### Passo 9 — `Application` de produção e entrega

- [ ] `Application` de produção: `public`, `authorization-code`, `RS256`,
      `https://<spa>/callback`, `skip_authorization`
- [ ] `issuer` de produção e `client_id` entregues à SPA
- [ ] `docs/integracao-rp.md` com o issuer de produção
- [ ] Quatro caminhos com `Access-Control-Allow-Origin: https://<spa>`; preflight de
      `/o/userinfo/` responde
- [ ] Fluxo PKCE à mão fecha em produção com `id_token` completo, sem consentimento repetido
- [ ] `/o/userinfo/` com token inválido → 401 com cabeçalho de CORS
- [ ] SPA faz login em produção e chega a `/app` com as claims
