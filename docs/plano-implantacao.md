# Plano de implantação — o `nova_api` em produção para a `nova_api_SPA`

| Campo | Valor |
| --- | --- |
| Origem | síntese, em 2026-09-24, de `contrato-backend.md`, `plano-contrato-backend.md` e `cloudflare.md` (apagados; ver §9) |
| Contraparte | projeto `nova_api_SPA` (relying party, RP), que recebe o `contrato-frontend.md` |
| Rota | provedor de identidade (IdP, de _Identity Provider_) de produção na máquina do dono, publicado por Cloudflare Tunnel sob domínio próprio, pela ADR (Architecture Decision Record) 0027, proposta, em `docs/adr/0027-servir-o-idp-de-producao-da-maquina-local-pelo-cloudflare-tunnel-sem-porta-de-entrada.md`; aplicação de página única (SPA, de _Single-Page Application_) na Vercel |
| Critério de pronto | todos os itens "Pronto quando" da §5 marcados, cada um verificado contra o código ou o ambiente, nunca contra um documento |

Este documento diz o que o IdP `nova_api` preserva e o que ainda precisa fazer para que a SPA
`nova_api_SPA` feche o fluxo OpenID Connect (OIDC) contra ele em produção. As §1 e §2 são o
contrato; a §5 é o caminho. As decisões ficam registradas em ADRs em `docs/adr/`.

---

## 1. O contrato que não muda

Verificado no código. É contrato público: mudar qualquer linha quebra a RP; não é refatoração.

| Item | Como está | Onde |
| --- | --- | --- |
| Issuer | `{BASE_URL}/o`, sem barra final; em produção `https://<PUBLIC_HOST>/o` | ADRs 0007 e 0025 |
| Descoberta | `{issuer}/.well-known/openid-configuration`, com os endpoints `authorization`, `token`, `userinfo` e `jwks_uri` | `tests/test_discovery.py` |
| PKCE (Proof Key for Code Exchange) | obrigatório, só `S256` | `PKCE_REQUIRED` |
| Scopes | exatamente `openid`, `profile`, `email` | `OAUTH2_PROVIDER["SCOPES"]` |
| Claims | `sub` (string), `name` (**pode ser `""`**), `email`; sem `email_verified` | `accounts/oauth_validators.py` |
| Assinatura | RS256, uma chave RSA (Rivest–Shamir–Adleman) com `kid` no JWKS (JSON Web Key Set) | `tests/test_jwks.py` |
| `userinfo` | mesmas claims; token inválido → **401** | oauthlib |
| Logout pela RP | desligado; sem `end_session_endpoint` | `OIDC_RP_INITIATED_LOGOUT_ENABLED=False` |
| `redirect_uri` | igualdade exata | `tests/test_authorize_guards.py` |
| Tempos de vida | `code` 60 s; `access_token` e `id_token` 10 h; `refresh_token` sem expiração | defaults do django-oauth-toolkit (DOT) 3.4.1 |
| `CorsMiddleware` | no topo do `MIDDLEWARE` | `config/settings.py` |

A SPA é cliente público, guarda tokens só em memória, volta a `/o/authorize/` a cada reload e
conta com o cookie de sessão do IdP (`SameSite=Lax`) para voltar sem senha. Ignora o
`refresh_token`; usá-lo seria ADR cruzada.

---

## 2. O que a SPA exige deste projeto

### 2.1 Valores por ambiente

| Valor | Produção | Desenvolvimento |
| --- | --- | --- |
| `issuer` | `https://<PUBLIC_HOST>/o` | `http://localhost:8000/o` |
| `client_id` | o da `Application` de produção | o da `Application` de dev |
| Origem no CORS (Cross-Origin Resource Sharing) | `https://<spa>` | `http://localhost:5173` |
| `redirect_uri` | `https://<spa>/callback` | `http://localhost:5173/callback` |

A SPA entrega origem e `redirect_uri` literais; este projeto devolve `issuer` e `client_id`.

### 2.2 Uma `Application` por ambiente

Pelo admin: `client_type` `public`; `authorization_grant_type` `authorization-code`; `algorithm`
`RS256` (vazio emite o `code` e não o `id_token`, em silêncio); **uma** `redirect_uri`;
`skip_authorization=True`. Nunca as duas `redirect_uris` na mesma `Application`: produção não
aceita retorno em `localhost`, e `ALLOWED_REDIRECT_URI_SCHEMES = ["https"]` sob
`BEHIND_TLS_PROXY` recusaria o `http` de qualquer forma.

### 2.3 CORS

- `CORS_ALLOWED_ORIGINS` com a origem **exata**; sem curinga, regex, `CORS_ALLOW_ALL_ORIGINS` nem
  `*.vercel.app`. Previews da Vercel ficam fora (ADR 0022).
- A allowlist governa `/o/token/` e `/o/userinfo/`. Descoberta e `jwks_uri` saem com `*` pelo
  próprio DOT, ou com a origem exata quando ela está na lista.
- `CORS_URLS_REGEX = r"^/o/"`; preflight já aceita `authorization` e `content-type`.
- Com a lista preenchida, conferir a posição do `CorsMiddleware` e do `LimiteDeTaxaMiddleware`:
  posição errada é indetectável com a lista vazia.

### 2.4 Consentimento e o que fica por decisão

- `skip_authorization=True` só na `Application` de primeira parte; o default global continua
  `"force"` (ADR 0021).
- Sem páginas de cadastro nem de perfil; contas pelo admin (ADR 0023).
- Não trocar `SESSION_COOKIE_SAMESITE` para `Strict`: quebraria a volta sem senha.

---

## 3. Já fechado

- **Desenvolvimento integrado** contra o IdP real: `.env` em dia, `Application` de dev, contas
  com e sem nome, SPA chegando a `/app` (antigos passos 1 a 4).
- **Endurecimento:** `AUTH_PASSWORD_VALIDATORS`, rotas de gestão do DOT fora do URLConf (ADR 0024),
  `ALLOWED_REDIRECT_URI_SCHEMES` condicionada, `CORS_URLS_REGEX` (antigo passo 5).
- **ADRs:** 0021 a 0023 (cruzadas com a SPA), 0025 (issuer congelado) e 0026 (instância da AWS, de
  _Amazon Web Services_, a ser substituída pela 0027).

---

## 4. Regras de todos os passos

- Relatório antes de alterar código; pergunta antes de tocar mais de dois arquivos.
- ADR aceita não se edita: emenda ou substituição. A 0026 vale até a 0027 ser aceita.
- `.env` untracked e sem cópia: backup antes de qualquer edição.
- `PUBLIC_HOST` não é visitado por navegador antes do passo 6: o HSTS (HTTP Strict Transport
  Security, sobre o HTTP, de _Hypertext Transfer Protocol_) de um ano do Django marca o nome na
  primeira visita.
- Nenhum código Python muda nesta rota.
- O projeto entrega código e documentação; criar e configurar túnel, zona e DNS (Domain Name
  System), pôr segredos no `.env` e operar produção cabem a quem opera, fora do
  repositório.

---

## 5. Passos

### Passo 1 — ADRs propostas

Responsável: projeto (documentação).

- ADR 0027 gravada em `docs/adr/0027-servir-o-idp-de-producao-da-maquina-local-pelo-cloudflare-tunnel-sem-porta-de-entrada.md`,
  Status `Proposto`, revista em 2026-09-24.
- ADR 0018 da SPA gravada em `../nova_api_SPA/docs/adr/0018-aceitar-o-idp-de-producao-servido-pelo-cloudflare-tunnel-com-o-contrato-inalterado.md`,
  `Proposto`: nenhuma mudança de código; `VITE_OIDC_ISSUER` conferido byte a byte; aceite da borda
  vendo os tokens e da chave na máquina do dono; migração futura para uma máquina virtual (VM) sem
  redeploy.

Pronto quando:

- [x] as duas ADRs apontam uma para a outra; a 0026 continua intocada (conferido nos arquivos em
      2026-09-24)

### Passo 2 — Caddy confia no endereço real

Responsável: projeto (código).

Arquivo: `docker/Caddyfile`.

- Global: `servers { trusted_proxies static <ip do cloudflared>/32; client_ip_headers CF-Connecting-IP }`.
- `reverse_proxy app:8000 { header_up X-Forwarded-For {client_ip} }`: um valor só, e
  `TRUSTED_PROXY_COUNT = 1` e `config/origem.py` não mudam. `tls internal` fica.
- Comentário registra o silêncio: se a confiança falhar, toda linha sai com o IP (endereço de
  _Internet Protocol_) do `cloudflared` e `ip_edge` = `peer`; o literal também vive no
  `docker-compose.prod.yml`.

Decidido e fechado na TASK-022, em 2026-09-24:

- O literal do conector é `10.203.14.200`.
- `header_up X-Forwarded-Proto {scheme}` também: confiar no conector deixaria passar o
  `X-Forwarded-Proto` que ele repassa, e é nele que o `SECURE_PROXY_SSL_HEADER` do Django decide
  o redirecionamento e o cookie seguro. O aviso "Unnecessary header_up X-Forwarded-Proto" do
  Caddy é falso para esse par, e o Caddyfile registra a medição (sem o `set`, `http` vindo do
  conector produz 301).
- O sinal do colapso é o mesmo `ip` em todas as linhas, com `ip_edge` = `peer`, e não o `ip`
  igual ao literal: só no caso do cabeçalho ausente os dois coincidem.

Pronto quando:

- [x] `caddy adapt` (`caddy:2.11.4`) mostra `trusted_proxies`, `client_ip_headers` e o `set`
- [x] jornada de container em `https://idp.localhost` sobe, com `ip_edge=gateway`
- [x] rede temporária com o IP do conector: 121 POST em `/o/token/` em 60 s com
      `CF-Connecting-IP` A → 429; com B, não; do host, o cabeçalho forjado é ignorado
- [x] `manage.py test` verde nas duas jornadas

### Passo 3 — Override de produção e conector

Responsável: projeto (código).

Arquivos: `docker-compose.prod.yml` (novo), `docker-compose.yml` (só comentários), `.env.example`,
`.gitignore`, `.dockerignore`, `tests/test_borda_do_tunel.py` (novo) e `docs/testes.md`.

- Override: `name: ${COMPOSE_PROJECT_NAME:?...}`; `ports: !reset []` em `proxy`, `postgres` e
  `redis`; rede `borda` com sub-rede `10.203.14.0/24`, fora dos pools padrão, e `ip_range`
  `10.203.14.0/25`, para que o `proxy` receba de `.2` a `.126` e nunca tome o `.200`;
  `proxy.networks: [default, borda]`; `restart: unless-stopped` em `postgres`, `redis`, `app`,
  `proxy` e `cloudflared`. O arquivo base não ganha a política.
- Serviço `cloudflared`: versão exata; só em `borda`, com `ipv4_address` `10.203.14.200`, igual ao
  literal do `docker/Caddyfile`; sem `ports:`; `tunnel --no-autoupdate run
  --credentials-file /etc/cloudflared/credenciais.json --url https://proxy:443 --origin-server-name ${PUBLIC_HOST} --http-host-header ${PUBLIC_HOST}
  --no-tls-verify ${TUNNEL_ID:?...}`; credenciais de `./cloudflared/`, somente-leitura.
- `.env.example`: bloco "só em produção" com `COMPOSE_PROJECT_NAME=nova_api_prod` e `TUNNEL_ID`.
  `.gitignore`: `cloudflared/`.
- `docker-compose.yml`: o comentário do serviço `proxy` troca a razão do pin ("`trusted_proxies`
  vazio") pelos dois comportamentos medidos que o `docker/Caddyfile` registra: o `header_up`
  prevalece sobre o cabeçalho que o `reverse_proxy` monta, e `{client_ip}` só lê
  `CF-Connecting-IP` do par declarado.

Decidido e fechado na TASK-023, em 2026-09-24:

- Pin `cloudflare/cloudflared:2026.9.3`, lançada em 2026-09-24. A imagem roda como uid
  (identificador de usuário) 65532:65532, e o entrypoint é `cloudflared --no-autoupdate`.
- As flags da origem ficam depois de `run` por escolha: o `tunnel --help` desta versão também as
  aceita, mas o nível documentado do comando que as usa é o `tunnel run`. O `TUNNEL_ID` fica por
  último por necessidade, porque o parser para de ler flags no primeiro argumento posicional.
- Credenciais com o dono de desenvolvimento, `0644` no arquivo e `0755` no diretório, sem
  `chown` e sem `user:`: o uid 65532 precisa ler o arquivo. A barreira é o modo de um diretório
  ancestral do clone, e isso é pré-condição do Passo 6, não fato garantido.
- Montagem do diretório `./cloudflared`, somente-leitura, em sintaxe longa com
  `create_host_path: false`: sem ela, o diretório ausente viraria um diretório vazio de root, e
  o conector sairia em laço sem sinal no host.
- `cloudflared/` no `.gitignore` e no `.dockerignore`. O segundo não estava na lista original:
  sem ele, o `COPY . .` do clone de produção levaria as credenciais a uma camada da imagem do
  `app`.
- O bloco do `.env.example` fica comentado, porque `COMPOSE_PROJECT_NAME` descomentada num `.env`
  de desenvolvimento faz o Compose de desenvolvimento adotar os contêineres e os volumes de
  produção sem aviso.
- `DEBUG` fixado em `"False"` no `environment:` do `app`, só no override, que é o único arquivo
  que sabe que aquilo é produção.
- Teste de guarda `tests/test_borda_do_tunel.py`, dois casos que leem os arquivos como texto e
  não fixam valor. O T-01 afirma que o `/32` do `docker/Caddyfile` e o `ipv4_address` do
  override são iguais. O T-02 afirma que o endereço fica dentro da `subnet` (`10.203.14.0/24`) e
  fora do `ip_range` (`10.203.14.0/25`), a faixa dinâmica de onde o `proxy` recebe endereço, e
  que o `ip_range` cabe na `subnet`. O silêncio que ele guarda: com o literal dentro da faixa, o
  `proxy` pode tomar o endereço num recreate ou reboot, o conector não sobe, `unless-stopped`
  não repara falha de início, e a borda responde 1033 sem sinal no host. Prova a relação entre os
  três valores do arquivo, não que o daemon do Docker respeite o `ip_range`.
- Medido no ensaio isolado, sem alcançar a Cloudflare: as flags são aceitas; o arquivo em `0644`
  é lido e o em `0600` é recusado pelo uid do conector; flag que o nível não declara sai com
  código 0, e flag depois do identificador sai com 255.

Pronto quando:

O `docker compose config` expande o `env_file` na saída e imprime a `OIDC_RSA_PRIVATE_KEY`, a
`SECRET_KEY` e as senhas. Por isso cada leitura abaixo é por campo, com `config --format json | jq`
do campo, e a comparação do base é por `sha256sum`, sem imprimir a saída inteira.

- [x] `config` com os dois `-f`, lido por campo, mostra o nome do projeto, nenhum `ports`, `proxy`
      nas duas redes e `cloudflared` só em `borda`
- [x] `config` com os dois `-f`, lido por campo, mostra `restart: unless-stopped` nos cinco
      serviços, e o `config` do base não mostra `restart`
- [x] sem `COMPOSE_PROJECT_NAME` ou `TUNNEL_ID`, o `config` aborta nomeando a variável
- [x] `grep` acha o mesmo IP do conector nos dois arquivos
- [x] `config` do arquivo base idêntico ao de antes, por `sha256sum`; `up postgres redis` em dev
      continua subindo
- [x] `config` com os dois `-f`, lido por campo, mostra `DEBUG` = `False` no `app`
- [x] `cloudflared/` fora do git e da imagem do `app`
- [x] teste de guarda verde nas duas jornadas (140 testes)

### Passo 4 — Zona e ensaio

Responsável: quem opera. O projeto só entrega os Passos 2 e 3 e esta checklist.

Nada versionado muda. O ensaio usa um subdomínio diferente de `PUBLIC_HOST`.

Pré-requisitos, entregues pelo dono fora do repositório: domínio do IdP registrado e delegado a
uma zona própria na conta da Cloudflare; túnel de ensaio criado, com a rota de DNS do nome de
ensaio na zona do IdP; `TUNNEL_ID` e arquivo JSON (JavaScript Object Notation)
de credenciais desse túnel.

- Zona do IdP na Cloudflare: TLS (Transport Layer Security) mínimo 1.2; "Always Use HTTPS", que
  leva todo acesso a HTTPS (HTTP sobre TLS); Pseudo IPv4 (IP versão 4) em sobrescrita; Security
  Level no mínimo; desligados HSTS da Cloudflare, Browser Integrity Check, Bot Fight Mode, Always
  Online, Rocket Loader, Email Obfuscation, Automatic HTTPS Rewrites e Web Analytics; sem cache.
- Clone de ensaio com `.env` descartável (`COMPOSE_PROJECT_NAME=nova_api_ensaio`), o `TUNNEL_ID`
  do túnel de ensaio no `.env` e o JSON dele em `cloudflared/credenciais.json`.
- `up --wait` com os dois `-f`.
- Desmontar ao fim, nesta ordem: `down -v` e o clone apagado, deste lado; depois, o túnel de
  ensaio e o registro de DNS do nome de ensaio, apagados pelo dono.

Pronto quando:

- [ ] descoberta responde 200 com o issuer do nome de ensaio (se `--url` não servir, decidir o
      `config.yml` com `ingress:` antes do aceite)
- [ ] dois clientes de redes distintas aparecem com os próprios IPs; `CF-Connecting-IP` forjado
      não aparece, em três formas: valor único, cabeçalho em linha duplicada e lista separada
      por vírgula. O Caddy junta as linhas e toma o primeiro IP válido da esquerda: se a borda
      anexar em vez de sobrescrever, o valor do cliente vence. Nenhuma linha com o IP do
      `cloudflared`
- [ ] anotado o que chega em `ip` de um cliente IPv6 (IP versão 6)
- [ ] `fetch` cross-origin a `/o/token/` recebe o Django com CORS, não desafio da borda
- [ ] `restart proxy` não derruba o login; `up`/`down` sem `-f` falham fechados
- [ ] `systemctl is-enabled docker` = `enabled`; depois de `sudo systemctl restart docker`, a
      descoberta de ensaio volta sem comando
- [ ] `docker compose run --rm` do `createsuperuser` (passo 6.3) funciona com `restart:` no
      override, ou recusa com "Conflicting options" e o passo 6.3 é ajustado
- [ ] ensaio desmontado: sem volumes nem redes de `nova_api_ensaio` e sem o clone; túnel de
      ensaio e registro de DNS do nome de ensaio apagados pelo dono
- [ ] indicação de nome do servidor (SNI, de _Server Name Indication_) e `Host` conferidos de
      ponta a ponta: o ensaio isolado do Passo 3 não alcançou a borda
- [ ] se o ensaio permitir distinguir, conferido que as flags de origem são de fato aplicadas, e
      não só aceitas e listadas na linha `Settings:` do log

### Passo 5 — Aceite e documentação

Responsável: projeto (documentação), com o que quem opera mediu no passo 4.

- ADR 0027: alíneas **[ensaio]** reescritas com o medido; `Aceito — <data>`. ADR 0026: só o
  Status, `Substituído por ADR-0027 — <data>`. Na SPA, aceite da 0018.
- Índice em `docs/arquitetura.md` (0026 substituída; 0017 e 0020 emendadas pela 0027).
- Tirar AWS, ACME (Automatic Certificate Management Environment), security group e `CADDY_TLS` de:
  `CLAUDE.md` (com autorização), `README.md` (e ganhar zona, clone de produção,
  `COMPOSE_PROJECT_NAME`, segundo fator), `docs/runbook.md` (seções 9, 18, 19; seção 14, no
  parágrafo que diz que o Caddyfile não traz `trusted_proxies` nem `header_up X-Forwarded-For`;
  colapso no IP do conector, com o sinal do `docker/Caddyfile`: o mesmo `ip` em todas as linhas,
  com `ip_edge` = `peer`, e não o `ip` igual ao literal. O sinal só é conclusivo com dois
  clientes que se sabe estarem em redes distintas, e o roteiro diz como gerar o segundo, como no
  passo 4: um acesso de outra rede que não a do primeiro, como um celular em dados móveis, e não
  outra máquina da mesma rede local; erro 1033; `-f` duplo; proibição de `prune`; backup;
  expiração do domínio; pin e rotação do túnel; roteiro de vazamento da chave ou de processo comprometido, da ADR 0027;
  restauração com `COMPOSE_PROJECT_NAME` trocado e o desenvolvimento derrubado; migração com um
  conector só), `docs/receita.md`, `docs/seguranca.md`,
  `docs/integracao-rp.md`, este documento, e na SPA `contrato-frontend.md`,
  `implementacao-contrato.md`, `spa-nucleo.md`, além de `../pre-deploy.md`.
- Também ao `docs/runbook.md` e aos documentos, vindos do Passo 3:
  - `--http-host-header` torna um `PUBLIC_HOST` esquecido como `idp.localhost` num 200 coerente
    com o nome errado, em vez de 400. A guarda é a conferência do issuer nos Passos 4 e 6.
  - Na seção de pin do runbook, o prazo de suporte do pin do `cloudflared` como data-limite: a
    Cloudflare suporta cada versão por uma janela contada da data de lançamento, 2026-09-24 para
    a 2026.9.3.
  - A sub-rede fixa da `borda` é uma segunda guarda, involuntária, contra `COMPOSE_PROJECT_NAME`
    trocado: um `export` esquecido no shell cria uma segunda `borda`, e o `up` para com "Pool
    overlaps", o que impede dois conectores do mesmo túnel no host. Trocar para sub-rede
    dinâmica apagaria essa guarda em silêncio.
  - Na revisão de aceite da ADR 0027, corrigir "Esquecer o `-f`": o `down` sem `-f` não para o
    `cloudflared`, que fica de pé porque nada o parou, e a política `unless-stopped` o traz de
    volta depois de um reboot.
  - O comentário das portas do `proxy` no `docker-compose.yml` ("Expor de verdade é editar estes
    dois endereços", ADR 0017), revisto depois do aceite da 0027.

Pronto quando:

- [ ] `grep -rn "AWS\|security group\|ACME\|HTTP-01\|CADDY_TLS\|ip_edge.*peer" README.md CLAUDE.md docs/*.md`
      só devolve menções históricas
- [ ] cada roteiro que este passo manda ao `docs/runbook.md` está lá, conferido no arquivo:
      colapso no IP do conector, erro 1033, `-f` duplo, proibição de `prune`, backup, expiração
      do domínio, pin e rotação do túnel, vazamento da chave ou de processo comprometido,
      restauração com `COMPOSE_PROJECT_NAME` trocado e migração com um conector só
- [ ] `manage.py test` verde; ramo integrado

### Passo 6 — Produção

Responsável: quem opera.

Nada versionado muda.

1. Clone de produção fora da árvore de dev, com o JSON de credenciais do túnel de produção,
   entregue pelo dono, em `cloudflared/credenciais.json`. O túnel e a rota de DNS de
   `PUBLIC_HOST`, na zona do IdP, são criados pelo dono fora do repositório. Pré-condição: ao
   menos um diretório ancestral do clone fechado para "outros". As credenciais ficam em `0644`
   para o uid do conector, e o `.env` chega em `0644` pela umask 022; num clone sob `/srv` ou
   `/opt` com todos os pais em `0755`, qualquer uid de serviço do host lê as credenciais do
   túnel, a `OIDC_RSA_PRIVATE_KEY` e a `SECRET_KEY`, sem erro nem aviso.
2. `.env` novo no clone de produção: `SECRET_KEY`, `OIDC_RSA_PRIVATE_KEY`
   (`scripts/gen_dev_key.sh`) e senhas novas; `PUBLIC_HOST`;
   `CORS_ALLOWED_ORIGINS=https://<spa>`; `COMPOSE_PROJECT_NAME=nova_api_prod`; `TUNNEL_ID` do
   túnel de produção, entregue pelo dono. `DEBUG` não depende do `.env`: o override o fixa em
   `False`, e um `DEBUG=True` no `.env` não chega ao `app`.
3. `docker compose -f docker-compose.yml -f docker-compose.prod.yml up --wait`; `createsuperuser`
   por `run --rm` com os dois `-f` (ADR 0019).
4. Backup cifrado fora da máquina (`.env`, `./cloudflared/`, dump de `pgdata` e `auditlog`);
   restauração ensaiada com `COMPOSE_PROJECT_NAME` trocado no `.env` restaurado **antes de
   qualquer comando**, só com o arquivo base, sem `cloudflared`, e com o desenvolvimento derrubado
   antes (`down`, sem `-v`, no diretório de dev), porque o arquivo base publica as mesmas portas em
   `127.0.0.1`; `docker compose ls` confirma o nome antes do `down -v`.

Pronto quando:

- [ ] `namei -l <clone>/cloudflared/credenciais.json` mostra ao menos um diretório ancestral
      sem permissão para "outros" (pré-condição do 6.1)
- [ ] descoberta externa 200; `issuer` byte a byte igual a `VITE_OIDC_ISSUER`; `S256`; sem
      `end_session_endpoint`
- [ ] certificado aceito sem aviso; `http` → 301 para `https`
- [ ] medição de origem do passo 4 repetida
- [ ] varredura externa do IP residencial em 80, 443, 5432 e 6379: nada responde
- [ ] `kid` de produção ≠ `kid` de dev; `docker compose ls` com dois projetos; dev sobe junto.
      O arquivo base publica `127.0.0.1:80`, e no host o Apache ocupa a porta 80: o `up` com o
      arquivo base falha com "address already in use". A falha é ruidosa, não silenciosa, e
      produção não é afetada, porque o override zera `ports`
- [ ] restauração ensaiada (6.4) com `COMPOSE_PROJECT_NAME` trocado; `docker compose ls`
      conferido antes do `down -v`; `nova_api_prod` com os volumes intactos depois

### Passo 7 — `Application` de produção e SPA

Responsável: quem opera.

- `Application` de produção pelo admin, como na §2.2, com `https://<spa>/callback`.
- Entregar à SPA `issuer` e `client_id` de produção.

Pronto quando:

- [ ] `/o/token/` e `/o/userinfo/` com `Origin: https://<spa>` devolvem o cabeçalho, e com origem
      estranha não; preflight de `/o/userinfo/` responde
- [ ] fluxo PKCE à mão (`docs/receita.md`) fecha com `iss`, `aud`, `sub`, `name`, `email`, sem
      consentimento na segunda vez
- [ ] `/o/userinfo/` com token inválido → 401 com cabeçalho de CORS
- [ ] SPA de produção faz login e chega a `/app` com as claims (critério da raiz)

### Depois do primeiro deploy

Responsável: quem opera; a normalização de IPv6, se vier, é código do projeto.

- IPv6: se o Pseudo IPv4 não agregar o /64, normalizar por prefixo em `config/origem.py`, com ADR
  própria (toca a ADR 0015).
- Subir o pin do `cloudflared` antes do fim do suporte, repetindo a medição de origem; idem para
  o Caddy. A medição do Passo 2 numa rede temporária `10.203.14.0/24` não roda com a produção de
  pé, porque a sub-rede está ocupada pela `borda`: usa-se outro literal num Caddyfile de teste, ou
  a produção fica fora durante a medição.
- Rotação do túnel após vazamento das credenciais: o dono cria túnel novo, passa para ele a rota
  de DNS de `PUBLIC_HOST` e entrega `TUNNEL_ID` e credenciais novos; `up` com os dois `-f`;
  depois, o dono apaga o túnel antigo.
- Vazamento da chave: roteiro da ADR 0027, detalhado no `docs/runbook.md`.
- Migração: `down` com os dois `-f`, sem `-v`, na origem, antes do dump final e do `up` no destino;
  um conector só.
- Backup mensal e depois de cada mudança de conta ou de `Application`.

---

## 6. Verificação sem a SPA

Em cada ambiente, com `curl` e navegador: descoberta com o `issuer` entregue, `S256` e sem
`end_session_endpoint`; `jwks_uri` com uma chave RSA com `kid`; CORS como na §2.3; fluxo PKCE à
mão fechando sem consentimento repetido; `/o/userinfo/` inválido → 401.

---

## 7. Proibições

- `trycloudflare.com` (fere a regra 1 da ADR 0025).
- `cloudflared` na rede `default`, em `app:8000` ou na porta 80.
- `trusted_proxies` além do /32 do conector; mudar `TRUSTED_PROXY_COUNT` ou `config/origem.py`
  por causa do túnel.
- Porta publicada em produção.
- Comando compose em produção sem os dois `-f`; `up` com o override em dev; `COMPOSE_FILE`,
  script ou link de override.
- Copiar o `.env` de dev para produção.
- Em produção: `git clean -xd`, `down -v`, `docker volume prune`, `docker system prune --volumes`.
  Agentes não operam no diretório de produção.
- Versionar credenciais do túnel; tag móvel no `cloudflared` ou no Caddy.
- Restaurar com `COMPOSE_PROJECT_NAME=nova_api_prod` fora de produção; dois conectores com o mesmo
  `TUNNEL_ID`.

---

## 8. Pendências fora do plano

Dívidas da ADR 0021 (TASK-018), sensíveis com a exposição; cada uma é tarefa própria, com ADR:

- `SESSION_COOKIE_SAMESITE`, `SESSION_COOKIE_AGE` e `SESSION_EXPIRE_AT_BROWSER_CLOSE` não
  declarados: uma atualização do Django pode trocá-los em silêncio.
- `REFRESH_TOKEN_EXPIRE_SECONDS` sem valor finito (`docs/robustez-info.md` §2.8).

---

## 9. Documentos substituídos

Este arquivo substitui `docs/contrato-backend.md`, `docs/plano-contrato-backend.md` e
`docs/cloudflare.md`, apagados em 2026-09-24. ADRs aceitas e memórias em `.claude/memory/`
continuam citando os nomes antigos, porque não se editam; o histórico está no `git`.
Correspondência: contrato §2 → §1; §3 e §5 → §2; §4.5 e §6 → §3; §7 → §6; passos 7 a 9 do plano
antigo e blocos 1 a 8 do `cloudflare.md` → §5.

---

## Apêndice A — ADR 0027

O texto da ADR 0027 vive em
`docs/adr/0027-servir-o-idp-de-producao-da-maquina-local-pelo-cloudflare-tunnel-sem-porta-de-entrada.md`,
revisto em 2026-09-24; a contraparte, em
`../nova_api_SPA/docs/adr/0018-aceitar-o-idp-de-producao-servido-pelo-cloudflare-tunnel-com-o-contrato-inalterado.md`.
Este plano não guarda cópia: quando os dois divergirem, vale o arquivo da ADR.
