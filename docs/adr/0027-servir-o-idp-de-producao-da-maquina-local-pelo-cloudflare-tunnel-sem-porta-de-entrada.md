# 0027. Servir o IdP de produção da máquina local pelo Cloudflare Tunnel, sem porta de entrada

## Status

Aceito — 2026-09-28

Revisão — 2026-09-29: referências a documentos de trabalho suprimidas; decisão inalterada (ver índice).

Proposto em 2026-09-23 e revisto em 2026-09-24.

O dono do projeto aceitou, em 2026-09-23:

- que a Cloudflare termine o TLS (Transport Layer Security) do navegador e veja em texto claro
  senhas, `code`, `id_token`, `access_token` e `refresh_token`, pela praticidade e pelo
  custo-benefício num projeto de estudo;
- que produção divida máquina e privilégio com o desenvolvimento, com as consequências
  registradas em *Mesmo privilégio*.

Na revisão de 2026-09-24, o dono aceitou também que a borda veja o cookie `sessionid`, inclusive o
do superusuário, e que quem o capture persista pelo `/admin/` numa `Application` com
`skip_authorization=True`, como descreve a negativa *Um terceiro vê tudo*.

O ensaio de implantação rodou em 2026-09-28, sob um subdomínio de
ensaio da zona do domínio próprio, com `cloudflare/cloudflared:2026.9.3` e `caddy:2.11.4`. As
duas alíneas marcadas **[ensaio]** na proposta trazem agora o resultado medido, e as negativas
registram o que o ensaio mostrou da invocação sem `-f`, do nome errado e da configuração da zona.
O dono deu o ensaio por encerrado com três verificações sem medição, que esta ADR (Architecture
Decision Record) não afirma:

- dois clientes de redes distintas aparecendo na trilha com `ip` distintos entre si, que é o
  sinal da emenda à ADR 0020;
- o `fetch` cross-origin de navegador a `/o/token/`: o preflight e o `POST` foram medidos só por
  `curl`;
- a volta do serviço depois de `sudo systemctl restart docker`, de que depende a alínea
  *Reinício*. O operador relatou um "laço incorreto", sem detalhe, e nada foi investigado.

As três passam às verificações de implantação, antes do primeiro login real.

Aceita, esta ADR **substitui a ADR 0026**, que recebe o status `Substituído por ADR-0027` (a
única edição permitida nela), e **emenda as ADRs 0017 e 0020**, que permanecem aceitas.

## Contexto

A ADR 0026 decidiu expor este provedor de identidade (IdP, de _Identity Provider_) numa instância
da AWS (Amazon Web Services). Para um projeto de estudo com um operador só, manter uma VM (máquina
virtual) na nuvem é custo recorrente e operação a mais. A alternativa é a máquina do próprio dono,
publicada por um túnel nomeado da Cloudflare sob um domínio próprio, como exige a ADR 0025. A
relying party (RP), a aplicação de página única (SPA, de _Single-Page Application_)
na Vercel, compara o issuer `https://<PUBLIC_HOST>/o` byte a byte com `VITE_OIDC_ISSUER`.

Estes fatos decidem o desenho:

- **Quem conecta ao Caddy em nome de todos vira a origem de todos.** O `reverse_proxy` do
  `caddy:2.11.4`, com `trusted_proxies` vazio, substitui o `X-Forwarded-For` pelo endereço da
  conexão (`docker/Caddyfile`), e `config/origem.py` lê o salto da direita com
  `TRUSTED_PROXY_COUNT = 1` (`config/settings.py`). Um conector que entregue todas as requisições
  põe um endereço só na trilha de auditoria, no limitador de taxa e no `django-axes` (ADR 0015).
- **A marca da ADR 0020 não vê esse colapso.** `ip_edge` compara com o gateway padrão do `app`. Um
  conector numa rede do compose que não seja esse gateway sai como `peer`, como a linha correta.
- **`CF-Connecting-IP` só vale vindo da borda.** Por qualquer outro caminho, o cabeçalho é
  forjável.
- **Um cliente IPv6 (versão 6 do IP, de _Internet Protocol_) chega com o endereço inteiro
  (/128).** Quem controla um /64 troca de endereço a
  cada requisição, e o bloqueio `["ip_address"]` do `django-axes` e a chave do limitador por origem
  deixam de frear quem espalha tentativas.
- **O site do Caddy responde 308 na porta 80**, porque o `docker/Caddyfile` declara `https://`
  explícito, e só tem certificado interno para `PUBLIC_HOST`. O conector precisa falar HTTPS
  (_Hypertext Transfer Protocol Secure_, o HTTP, de _Hypertext Transfer Protocol_, sobre TLS) com
  esse nome na indicação de nome do servidor (SNI, de _Server Name Indication_).
- **Um serviço que entra no namespace de rede de outro perde a rede quando o outro reinicia.** O
  namespace é refeito a cada restart, e não só a cada recriação.
- **Nenhum serviço do `docker-compose.yml` declara `restart:`.** Depois de um reboot ou da queda de
  um processo, o contêiner fica parado até alguém rodar `up`.
- **Desenvolvimento e produção passam a dividir a máquina, o daemon e o privilégio.** O compose
  deriva o nome do projeto do diretório, ou de `COMPOSE_PROJECT_NAME` no `.env`, e dois projetos
  com o mesmo nome dividem contêineres e volumes. O usuário de desenvolvimento está no grupo
  `docker`, o que equivale a root, e na mesma máquina rodam `npm install`, `pip install`, extensões
  de editor e agentes com shell.
- **Pseudo IPv4 (versão 4 do IP) e Bot Fight Mode valem para a zona inteira** e, no plano
  gratuito da Cloudflare, não se ajustam por hostname.
- **A chave de assinatura não tem conjunto de rotação** (`docs/seguranca.md`). A SPA guarda o JWKS
  (JSON Web Key Set) no cache HTTP do navegador, e seu login falha por até 1–2 h depois de uma
  troca de chave (ADR 0013 da SPA).
- **O nome é permanente desde a primeira visita.** `SECURE_HSTS_SECONDS` vale 31536000 sob
  `BEHIND_TLS_PROXY` (ADR 0025, regra 3).

## Decisão

Vamos servir o IdP de produção a partir da máquina do dono, **sem nenhuma porta de entrada**, por
um túnel nomeado da Cloudflare cujo conector roda como serviço do compose de produção, sob um
domínio do IdP com zona própria. A cadeia é navegador → borda da Cloudflare → túnel →
`cloudflared` → Caddy → `app`.

- **Zona.** O domínio do IdP é só dele e tem zona própria na conta da Cloudflare, configurada para
  o IdP. O Pseudo IPv4 e o Bot Fight Mode valem para a zona inteira: com o Bot Fight Mode ligado,
  a borda desafiaria as chamadas cross-origin da SPA ao IdP, e sem o Pseudo IPv4 o IPv6 ficaria
  sem agregação. A zona do IdP tem as configurações registradas no `README.md`: "Always Use
  HTTPS", TLS mínimo 1.2, Pseudo IPv4 em sobrescrita; Security Level no mínimo; desligados o HSTS
  (HTTP Strict Transport Security) da Cloudflare, Browser Integrity Check, Bot Fight Mode, Always
  Online, Rocket Loader, Email Address Obfuscation, Automatic HTTPS Rewrites e Web Analytics
  automático; nenhuma regra de cache. Nada na borda desafia, reescreve ou injeta conteúdo em
  `https://<PUBLIC_HOST>/*`.
- **Certificado.** O TLS do navegador termina na borda, com o certificado Universal da zona do IdP,
  sem ACME (Automatic Certificate Management Environment) e sem porta 80. `PUBLIC_HOST` é o apex
  da zona ou um subdomínio de primeiro nível, que o certificado Universal cobre. O Caddy mantém
  `tls internal` nos dois ambientes, e o `cloudflared` não verifica a CA (autoridade
  certificadora) interna.
- **Conector.** O `cloudflared` é serviço declarado só no `docker-compose.prod.yml`, em versão
  exata e sem `ports:`, ligado **só** à rede `borda`, que o override declara com sub-rede fixa fora
  dos pools padrão do Docker e endereço fixo para ele. O `proxy` fica em `default` e em `borda`; o
  `cloudflared` não alcança `app`, `postgres` nem `redis`. A origem é `https://proxy:443`, com SNI
  e `Host` iguais a `PUBLIC_HOST` e sem verificação de certificado.
- **Túnel.** Gerido localmente, com arquivo de credenciais. O dono cria o túnel fora do
  repositório, com uma rota de DNS (Domain Name System) só, na zona do IdP, e entrega o
  identificador do túnel (UUID, de _Universally Unique Identifier_) e o arquivo JSON (JavaScript
  Object Notation) de credenciais. O identificador vai em `TUNNEL_ID`, no `.env`. O JSON fica em
  diretório não versionado do clone de produção, montado somente-leitura no conector. A origem é
  dada por flags depois de `run` que interpolam `PUBLIC_HOST`, sem literal de domínio em arquivo
  versionado. Medido no ensaio: as flags servem, e o `config.yml` com `ingress:` não foi preciso.
  A descoberta respondeu 200 com o issuer do nome de ensaio, só `S256` e sem
  `end_session_endpoint`. O JWKS trouxe uma chave RSA (Rivest–Shamir–Adleman) RS256 com `kid`, e
  `/o/userinfo/` com token inválido respondeu 401. O `--origin-server-name` é aplicado, e não só
  aceito. De dentro da rede, o Caddy recusa o handshake TLS com SNI `proxy` ou sem SNI e aceita só
  o nome de ensaio; com `Host` diferente desse nome, não entrega a descoberta. Pela borda, a
  descoberta chegou. O `--http-host-header` não se distinguiu, porque a borda já repassa o `Host`
  original.
- **Origem.** Nas opções globais, o `docker/Caddyfile` declara
  `trusted_proxies static <endereço do cloudflared>/32` e `client_ip_headers CF-Connecting-IP`. O
  `reverse_proxy` escreve `X-Forwarded-For` com `{client_ip}`, um valor só, e `X-Forwarded-Proto`
  com `{scheme}`, o esquema da conexão que o próprio Caddy terminou. Sem esse segundo `set`, o
  `X-Forwarded-Proto` que o conector confiável repassa chegaria ao Django, que decide por ele o
  redirecionamento para HTTPS, o cookie seguro e o HSTS (`SECURE_PROXY_SSL_HEADER`): medido no
  `caddy:2.11.4`, `http` vindo do conector produziu 301. O endereço do conector é IPv4 privado,
  fora dos pools padrão do Docker e da rede local do host, e fora da faixa de alocação dinâmica da
  `borda`, para que o `proxy` não o tome. O literal é o mesmo no `docker/Caddyfile`, que é a
  fonte do valor, e no override. `TRUSTED_PROXY_COUNT = 1` fica, e `config/` não muda. Se a
  confiança falhar, toda linha da trilha sai com o mesmo `ip`, `ip_src` `forwarded` e `ip_edge`
  `peer`. Esse `ip` é o literal quando só falta o cabeçalho, e o endereço real do conector quando
  este difere do literal. O sinal do colapso é esse conjunto, e não a comparação do `ip` com o
  literal. Medido no ensaio: a borda recusa com 403 e `error code: 1000`, antes da origem, toda
  requisição de cliente que traga `CF-Connecting-IP`, em valor único, em linha duplicada ou em
  lista separada por vírgula, em qualquer caixa, em HTTP/2 e em HTTP/1.1. `X-Forwarded-For` e
  `True-Client-IP` forjados não chegaram à trilha, que registrou o endereço real do cliente com
  `ip_src` `forwarded` e `ip_edge` `peer`, e nenhuma linha trouxe o literal do conector. A recusa
  é comportamento da borda, fora do repositório, e nada a guarda entre uma medição e a seguinte.
- **IPv6.** A zona do IdP liga o Pseudo IPv4 em modo de sobrescrita, e `CF-Connecting-IP` chega
  como IPv4 de classe E. Medido no ensaio: com a opção valendo, um cliente IPv6 chegou à trilha
  com um endereço de `240.0.0.0/4` em `ip`, `ip_src` `forwarded` e `ip_edge` `peer`, e é esse
  endereço a chave do limitador e do `django-axes`. Antes de a opção valer, chegou o IPv6 inteiro,
  com `ip_edge` `unknown`. A agregação por /64 não foi confirmada. Um segundo aparelho, que o
  operador julgava em outra rede e que provavelmente estava no Wi-Fi da mesma casa, chegou com o
  mesmo endereço de classe E. Não se confirmou que ele tenha saído por IPv6. Se saiu, dois
  endereços do mesmo /64 caíram no mesmo IPv4, o que é indício, e não prova. Se a medição de
  produção mostrar que dois endereços do mesmo /64 não caem no mesmo IPv4, a normalização por
  prefixo em `config/origem.py` fica para depois do primeiro deploy funcional, com ADR própria.
- **Publicação.** O override substitui por `!reset []` as listas `ports:` de `proxy`, `postgres` e
  `redis`, e produção não publica nada. O arquivo base não muda: desenvolvimento e jornada de
  container continuam em `127.0.0.1`.
- **Reinício.** O override declara `restart: unless-stopped` em `postgres`, `redis`, `app`,
  `proxy` e `cloudflared`. Depois de um reboot ou da queda de um processo, o daemon do Docker sobe
  de novo o que estava de pé, e o IdP volta sem comando. O daemon precisa estar habilitado no boot
  da máquina. Na máquina do dono ele está (`systemctl is-enabled docker`, conferido no ensaio). A
  volta depois de um restart do daemon não foi medida (Status). No reboot, o daemon não respeita
  `depends_on`: o `app` pode subir antes do `postgres` e sair na migração do entrypoint, e a
  política o repete até passar. A política reage a processo
  que sai, e não a contêiner `unhealthy`. `stop` e `down` continuam deixando o IdP fora de
  propósito. O arquivo base não ganha a política, e o desenvolvimento não sobe sozinho.
- **Invocação.** No diretório de produção, **todo** comando `docker compose` leva
  `-f docker-compose.yml -f docker-compose.prod.yml`, digitado, sem exceção: o override declara
  serviço e rede. Não há script, `COMPOSE_FILE`, link nem unidade de sistema; o que sobe o IdP no
  boot é a política de reinício do daemon, declarada no override. Em diretório de
  desenvolvimento, nunca `up` com o override.
- **Coexistência.** Produção vive num clone próprio, fora da árvore de desenvolvimento, com `.env`
  gerado nele: `SECRET_KEY`, `OIDC_RSA_PRIVATE_KEY` e senhas novas, e
  `COMPOSE_PROJECT_NAME=nova_api_prod`. O override declara `name: ${COMPOSE_PROJECT_NAME:?...}`.
  Conta da Cloudflare e conta do registrador com segundo fator.
- **Backup.** Cifrado, fora da máquina: o `.env` e as credenciais do túnel a cada mudança; o dump
  de `pgdata` e o arquivo de `auditlog` no mínimo por mês, e depois de cada mudança de conta ou de
  `Application`. Uma restauração ensaiada antes do primeiro login real.
- **Restauração.** O `.env` restaurado traz `COMPOSE_PROJECT_NAME=nova_api_prod` e o `TUNNEL_ID` de
  produção. Num ensaio, e em toda restauração que não substitua produção, ele troca
  `COMPOSE_PROJECT_NAME` por um nome que não é o de produção nem o de desenvolvimento, antes de
  qualquer comando `docker compose`. O ensaio usa só o arquivo base, sem o `cloudflared`. O
  arquivo base publica em `127.0.0.1` as portas 80, 443, 5432 e 6379, as mesmas do
  desenvolvimento. Por isso o desenvolvimento é derrubado antes, com `down` sem `-v` no diretório
  dele, e `docker compose ls` confere o nome do projeto antes do `down -v` do fim. Com o nome
  de produção, o compose adota os contêineres e os volumes de `nova_api_prod`, e o `down -v` do fim
  do ensaio apaga o `pgdata` de produção. Com o override, um segundo conector com o `TUNNEL_ID` de
  produção passa a receber parte do tráfego.
- **Migração.** Levar o IdP a outro host é mover o clone, as credenciais do túnel e os volumes, sem
  mudar DNS nem issuer, e com **um conector só**. Na origem, `down` com os dois `-f`, sem `-v`,
  vem antes do dump final e antes do `up` no destino. Dois conectores com o mesmo `TUNNEL_ID`
  repartem as requisições entre dois bancos, e um `code` emitido num volta `invalid_grant` no outro,
  de forma intermitente. Os volumes da origem ficam como cópia fria até o destino passar pelas
  verificações de implantação.
- **Barreira de rede.** Não há porta de entrada no host nem no roteador; a entrada é o túnel. Quem
  controla a conta da Cloudflare ou tem as credenciais do túnel controla a entrada. As duas são
  segredo da classe de `OIDC_RSA_PRIVATE_KEY`.
- **Manutenção.** O pin do `cloudflared` sobe antes de a versão fixada sair da janela de suporte
  da Cloudflare. Cada subida do `cloudflared` ou do Caddy repete as medições de origem do ensaio.
  A data-limite de suporte não entra no repositório: quem opera a acompanha.
- **Vazamento das credenciais do túnel.** O dono cria um túnel novo, passa para ele a rota de DNS
  de `PUBLIC_HOST` e entrega `TUNNEL_ID` e credenciais novos. O `up` com os dois `-f` troca o
  conector; depois, o dono apaga o túnel antigo.
- **Vazamento da `OIDC_RSA_PRIVATE_KEY`, ou processo comprometido na máquina.** Primeiro, limpar a
  máquina, o que esta ADR não descreve. Depois, no clone de produção: chave, `SECRET_KEY` e senhas
  novas no `.env` (a do Postgres troca-se no banco antes, porque a imagem só a lê ao criar o
  volume); a `SECRET_KEY` nova derruba as sessões. Então a rotação do túnel da alínea anterior;
  `up` com os dois `-f`; conferência, de fora, de que o `kid` publicado mudou. Pode-se, nesse
  ponto, restaurar o dump de `pgdata` mais recente anterior ao primeiro indício de acesso à
  máquina; sem esse marco, não se restaura. Por fim, sobre o banco em uso, restaurado ou não:
  revogar os `access_token` e `refresh_token` vivos, rever pelo admin as `Application`, cuja
  criação não entra na trilha, e rever as contas com `is_staff` ou `is_superuser`. Quem teve o
  processo pode ter criado uma conta dessas ou trocado a senha de outra direto no banco. A conta
  que o dono não reconhece sai, e as outras recebem senha nova. A restauração não dispensa essa
  revisão: o acesso pode ter começado antes do primeiro indício, e o dump restaurado pode já
  trazer a conta ou a `Application` de quem o teve. Os backups do `.env` e das credenciais do
  túnel anteriores à troca ficam marcados como inválidos. Nenhuma restauração traz de volta a
  chave, a `SECRET_KEY`, as senhas nem as credenciais antigas. A troca é disruptiva, porque não há
  conjunto de rotação: a SPA falha todo login por até 1–2 h (ADR 0013 da SPA).
- **Premissa.** Host único e réplica única, e o host é a máquina do dono.

Esta ADR não altera código Python.

**Emenda à ADR 0017.** O certificado de produção passa a ser o da borda, e a CA interna fica no
salto interno. O proxy de produção não publica porta. O resto da 0017 vale.

**Emenda à ADR 0020.** A alínea que toma a primeira linha `peer` como sinal de que a exposição
tomou efeito não vale sob esta topologia, porque o colapso no conector também sai `peer`. O sinal
passa a ser o de clientes de redes distintas aparecerem na trilha com `ip` distintos entre si. O
mesmo `ip` em todas as linhas, com `ip_src` `forwarded` e `ip_edge` `peer`, é o colapso, e esse
`ip` pode não ser o literal do `docker/Caddyfile`. O campo e os três valores não mudam.

Contraparte: a ADR 0018 da SPA.

## Consequências

Positivas:

- Nenhuma porta de entrada, e o endereço residencial fica fora do DNS. Sem VM a manter.
- Um salto só escreve `X-Forwarded-For`. `config/origem.py`, `config/settings.py` e a suíte não
  mudam.
- Um `docker/Caddyfile` só, com `tls internal` nos dois ambientes. Somem `CADDY_TLS` e as duas opções
  de certificado da exposição pela AWS, e `caddydata` deixa de guardar estado caro.
- O conector sobrevive a restart do `proxy`, porque o alcança pelo nome, numa rede própria, e não
  alcança o resto do compose. No ensaio, a sessão do `/admin/` sobreviveu ao `restart proxy`.
- O IdP volta sozinho depois de reboot ou queda de processo, por política declarada num arquivo
  versionado, sem peça fora do compose.
- A regra de confiança fica inerte em desenvolvimento, e produção e desenvolvimento sobem juntos
  sem disputar porta.
- Levar o IdP a uma VM é mover o clone, as credenciais e os volumes, com um conector só, sem mudar
  DNS nem issuer.

Negativas:

- **Um terceiro vê tudo.** A borda lê senhas, tokens e o cookie `sessionid`, e poderia servir
  qualquer conteúdo sob o domínio. Com o `sessionid` do superusuário, quem o captura entra no
  `/admin/` e cria uma `Application` com `redirect_uri` própria e `skip_authorization=True`. Por
  ela, quem tem sessão no IdP entrega tokens sem ver consentimento. Ela persiste depois de a
  captura cessar e não aparece na trilha. Aceito pelo dono. **Gatilho de revisão:** usuário real
  além do dono, ou segunda RP.
- **Mesmo privilégio.** Qualquer processo do usuário de desenvolvimento — pacote de `npm` ou `pip`
  comprometido, extensão, agente — alcança produção inteira. Lê o `.env` e as credenciais do túnel
  no clone de produção. Pelo grupo `docker`, roda `docker exec` no `app` e no `postgres`, monta
  `pgdata` e `auditlog` em outro contêiner, ou os apaga com `prune`. O `pgdata` guarda as contas
  com o hash das senhas, as sessões, as `Application` e os `access_token` e `refresh_token` vivos,
  e o `refresh_token` não expira. Com a `OIDC_RSA_PRIVATE_KEY`, emite `id_token` que a SPA aceita
  para qualquer `sub`; com as credenciais do túnel, recebe tráfego do domínio. Aceito pelo dono.
  **Gatilho de revisão:** usuário real além do dono, ou segunda RP.
- **Disponibilidade.** Máquina desligada, suspensa ou sem rede deixa o IdP fora, e a política de
  reinício não cobre isso. Um `app` `unhealthy` que não sai também fica fora até alguém agir.
- **Resposta a vazamento da chave é disruptiva.** Sem conjunto de rotação, trocar a chave derruba
  o login da SPA por até 1–2 h.
- **Renovação do domínio.** O issuer depende de o domínio continuar registrado; um domínio
  expirado pode ser registrado por outro, que passa a servir descoberta e JWKS sob o issuer que a
  SPA aceita. A data de expiração não entra no repositório: quem opera a acompanha no registrador,
  com renovação automática e segundo fator na conta.
- **IPv6.** Enquanto a agregação por /64 não estiver confirmada, o limitador e o `django-axes` são
  contornáveis por quem tem um /64, e sobra o teto por `username`. Com o Pseudo IPv4, a trilha
  registra o IPv4 de classe E, e não o IPv6 real.
- **Colapso silencioso.** Se a confiança falhar, por subida do Caddy ou do `cloudflared`, por
  endereço divergente entre os dois arquivos ou por borda sem o cabeçalho, toda linha sai com o
  mesmo `ip`, `ip_src` `forwarded` e `ip_edge` `peer`, e o limitador tranca todos juntos. Esse
  `ip` é o literal quando só falta o cabeçalho, e o endereço real do conector quando este difere
  do literal. O único sinal é o mesmo `ip` em linhas de clientes que se sabe estarem em redes
  distintas; comparar o `ip` com o literal não basta.
- **Literal duplicado.** O endereço do conector vive em dois arquivos versionados, sincronizados à
  mão.
- **Esquecer o `-f`.** Medido no ensaio. O `up` sem `-f` recria `app` e `proxy` só com o arquivo
  base, sem `restart:` e com o `proxy` fora da rede `borda`, e a borda responde 502. Com o
  desenvolvimento de pé, o `postgres` nem sobe, porque o arquivo base o publica na
  `127.0.0.1:5432` que o desenvolvimento ocupa. O único aviso é o de contêiner órfão, o
  `cloudflared`, e ele vem nesse `up`. O `down` sem `-f` remove os quatro serviços do base e a
  rede `default` sem aviso nenhum. O `cloudflared` fica de pé porque nada o parou, e a política de
  reinício o traz de volta depois de um reboot, sem `proxy` a alcançar. Nos dois casos, a falha é
  fechada para a internet.
- **Nome errado, resposta coerente.** O conector entrega `PUBLIC_HOST` no SNI e no `Host`, e o
  Caddy e o Django atendem o nome que recebem. Um `PUBLIC_HOST` esquecido no valor de
  desenvolvimento, como `idp.localhost`, faz a cadeia inteira responder 200 sob o domínio público,
  com o issuer do nome errado, em vez de 400. A guarda é a conferência do issuer (regra 4 da ADR
  0025).
- **Nome de projeto na restauração.** Esquecer a troca de `COMPOSE_PROJECT_NAME` no `.env`
  restaurado põe o ensaio sobre os volumes de produção, sem aviso.
- Um domínio e uma zona a registrar, renovar e configurar. A configuração da zona e do túnel vive
  fora do repositório, e nada a verifica. Medido no ensaio: com o "Always Use HTTPS" sem efeito,
  `http://` respondeu 200 com a tela de login. Só a zona podia impedi-lo, porque o trecho do
  conector ao Caddy é HTTPS e o redirecionamento do Django nunca é acionado. Com a opção ligada, a
  resposta foi 301 para `https://`.
- **Riscos aceitos da 0026, mantidos por esta.** O `refresh_token` não expira; os cookies usam a
  política padrão do Django 5.2. A correção de cada um é tarefa própria.
- Os gatilhos das ADRs 0006 e 0008 seguem vencidos, como dívida.
- **Gatilhos de revisão da topologia.** Segundo operador, deploy automatizado ou mudança nos termos
  do plano gratuito da Cloudflare.

## Alternativas consideradas

- **Manter a AWS (ADR 0026).** Custo recorrente e uma VM a operar, desproporcionais a um projeto
  de estudo. Descartada.
- **Render ou Koyeb.** Não rodam o compose, hibernam e não oferecem Redis. Descartadas.
- **Quick Tunnel em `trycloudflare.com`.** Nome aleatório, fere a regra 1 da ADR 0025. Descartada.
- **Encaminhar 80 e 443 no roteador, com ACME.** Nenhum terceiro veria o conteúdo, mas publica o
  endereço residencial e abre portas; endereço dinâmico, CGNAT (tradução de endereços na
  operadora, de _Carrier-Grade NAT_) e bloqueio da porta 80 impedem o desafio. Descartada.
- **`cloudflared` no host, em `127.0.0.1:443`.** Chegaria ao Caddy com o endereço do gateway (ADR
  0020), e confiar no gateway seria confiar em todo processo do host. Descartada.
- **`cloudflared` com `network_mode: "service:proxy"`**, confiando em `127.0.0.1/32`. Menos peças,
  mas o namespace é refeito a cada restart do `proxy`, e o conector fica sem rede e sem sair.
  Descartada.
- **`cloudflared` direto em `app:8000`.** Fere a ADR 0017, faria a cadeia de `X-Forwarded-For`
  depender da borda e separaria as topologias de produção e de desenvolvimento. Descartada.
- **`cloudflared` em `http://proxy:80`.** Fecha o laço de 308. Descartada.
- **Verificar a CA interna (`--origin-ca-pool`).** Montaria `caddydata` no conector por um salto
  interno ao host. Descartada.
- **`TRUSTED_PROXY_COUNT = 2`.** Dependeria da semântica de anexação da borda e cairia em
  `remote_addr_fallback` em desenvolvimento. Descartada.
- **Túnel gerido pelo painel, com token.** A configuração de origem ficaria fora do repositório.
  Descartada.
- **Origem em `config.yml` com `ingress:`.** O compose não interpola dentro do arquivo montado, e
  a regra por hostname levaria o domínio literal a um arquivo versionado. Era o recuo se as flags
  não servissem; no ensaio, serviram. Descartada.
- **Unidade de sistema ou script que sobe o IdP no boot.** Seria uma peça fora do compose, contra
  a alínea *Invocação*, para fazer o que a política de reinício do daemon faz declarada no
  override. Descartada.
- **Nenhuma política de reinício.** Nenhuma linha a mais, mas cada reboot ou queda deixa o IdP
  fora até um `up` digitado. Descartada.
- **Separar privilégios de fato** (outro usuário do sistema, Docker rootless, VM local). Outro
  usuário não isola enquanto o de desenvolvimento estiver no grupo `docker`; rootless muda a
  publicação em portas abaixo de 1024 e a origem que a ADR 0020 mede; o disco de uma VM local
  continua ao alcance do root. Descartada por custo num projeto de estudo, sob o gatilho de
  revisão.
- **Normalizar IPv6 no Caddy.** Exigiria expressão por família de endereço num arquivo que já
  carrega a propriedade de segurança do pin. Descartada.
- **Cloudflare Access à frente do IdP.** Fora do escopo: o IdP já autentica.
