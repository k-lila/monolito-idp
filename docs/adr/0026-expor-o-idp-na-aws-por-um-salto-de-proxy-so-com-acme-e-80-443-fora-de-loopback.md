# 0026. Expor o IdP na AWS por um salto de proxy só, com ACME e 80/443 fora de loopback

## Status

Aceito — 2026-09-23

Emenda à ADR (Architecture Decision Record) 0017, que **permanece aceita e em vigor**. Mudam
duas alíneas dela. A publicação fora de loopback, que a 0017 previa como "editar esse endereço à
mão", passa a ser um arquivo de override do compose, versionado e invocado à mão com `-f` por
quem opera a instância de produção. E o certificado de produção deixa de vir da autoridade
certificadora (CA) interna do Caddy e passa a ser público. O que a 0017 recusou continua
recusado, agora sem exceção nenhuma: a exposição não é variável de ambiente, e fica escrita e
visível na linha de comando. O resto da 0017 segue valendo: o proxy declarado no compose, o
`app` sem `ports:`, `PUBLIC_HOST` como variável única de fronteira e o `docker-compose.yml` base
publicando o proxy em `127.0.0.1`. A 0017 não é editada.

## Contexto

A ADR 0017 construiu a fronteira de TLS (Transport Layer Security) e deixou a exposição de fora:
publicou o proxy em `127.0.0.1:80` e `127.0.0.1:443`. A `nova_api_SPA` vai para a Vercel e
precisa alcançar este provedor de identidade (IdP, de _Identity Provider_) pela internet, com
certificado que o navegador aceite e sob o issuer que a ADR 0025 congelou. O destino é uma
instância na AWS (Amazon Web Services), operada por uma pessoa só. O `CLAUDE.md` condiciona a
queda da premissa de sandbox à aceitação desta ADR.

Seis fatos decidem a topologia e o mecanismo:

- **O Caddy substitui `X-Forwarded-For`.** Com `trusted_proxies` vazio, o `reverse_proxy` do
  `caddy:2.11.4` descarta o valor que chega e escreve só o endereço da conexão (`docker/Caddyfile`,
  medido nessa versão, fixada por isso em `docker-compose.yml`). `config/origem.py` lê o salto
  da direita, com `TRUSTED_PROXY_COUNT = 1`.
- **A origem é chave de limite e de trilha.** O limitador de taxa conta por origem
  (`config/limites.py`; `RATE_LIMIT_POR_CAMINHO` em `config/settings.py`, 120 por minuto em
  `/o/token/` e em `/o/authorize/`), e a trilha de auditoria grava `ip`, `ip_src` e `ip_edge`
  (ADRs 0015, 0018 e 0020).
- **Publicação sem endereço é DNAT (tradução do endereço de destino) à frente do firewall do
  host** (`docker-compose.yml`, comentário do Postgres). Um firewall na própria máquina não
  filtra as portas que o Docker publica.
- **Sem a diretiva `tls internal`, o Caddy pede certificado por ACME (Automatic Certificate
  Management Environment).** O desafio HTTP-01 exige a porta 80 alcançável da internet, e conta
  ACME e certificado ficam no volume `caddydata`.
- **O mesmo `docker-compose.yml` sobe desenvolvimento e produção.** Publicar sem endereço no
  arquivo base poria na rede local toda máquina de desenvolvimento que rodasse a jornada de
  container, com a chave e as contas de desenvolvimento. Editar à mão na instância deixaria um
  diff local no checkout de produção, que nenhum `git` mostra a quem lê o repositório.
- **Um override de compose só vale quando é invocado, e o esquecimento falha fechado.** Um
  `docker compose up` que omita o override recria o proxy com as publicações do base, em
  `127.0.0.1`, e termina sem erro. O IdP fica inalcançável da internet, e nada fica exposto além
  do devido: é defeito de disponibilidade, e não de segurança. Só os subcomandos que criam ou
  recriam contêiner, como `up` e `up --build`, o produzem; `ps`, `logs`, `exec`, `restart` e
  `down` não. Rodar o comando certo o reverte, e o certificado persiste em `caddydata`, sem nova
  emissão ACME.

## Decisão

Vamos expor o IdP na AWS com **um salto de proxy só**: o Caddy do compose atende a internet
diretamente, sem ALB (Application Load Balancer), CloudFront nem outro proxy à frente dele.

- **Publicação.** Um arquivo de override versionado, `docker-compose.prod.yml`, substitui as
  publicações do serviço `proxy` por 80 e 443 sem endereço. O `docker-compose.yml` base continua
  publicando o proxy em `127.0.0.1`, e desenvolvimento e jornada de container ficam em loopback.
  Postgres e Redis continuam em `127.0.0.1` nos dois casos, e o `app` continua sem `ports:`.
- **Invocação.** Na instância, todo comando que cria ou recria contêiner é
  `docker compose -f docker-compose.yml -f docker-compose.prod.yml ...`, digitado por quem opera.
  Não há script, nem `COMPOSE_FILE`, nem link para `docker-compose.override.yml`. Depois de cada
  deploy, `docker compose ps` confere o `proxy` em `0.0.0.0:80` e `0.0.0.0:443`. Em máquina de
  desenvolvimento, nunca `up` com o override; `config` pode, porque só renderiza.
- **Substituir, não acrescentar.** Em overrides, o Compose concatena as listas de `ports:` dos
  dois arquivos, em vez de substituí-las. O override precisa declarar a substituição, com a tag
  `!override` (Compose 2.24 ou posterior, segundo a documentação do Docker) ou com `!reset`
  seguido da lista nova. Sem isso, o proxy herdaria as publicações em `127.0.0.1` junto das
  novas. A versão do Compose da instância e o resultado da fusão, conferido por
  `docker compose -f docker-compose.yml -f docker-compose.prod.yml config`, são medição do passo
  7, e não desta ADR.
- **Certificado.** Público, por ACME com desafio HTTP-01. A porta 80 fica alcançável da internet
  para o desafio e para o 308 com que o Caddy manda o cliente para `https`. O volume `caddydata`
  guarda conta ACME e certificado e não é recriado.
- **Origem.** `TRUSTED_PROXY_COUNT = 1` fica. O Caddy continua sendo o único salto que escreve
  `X-Forwarded-For`, e o DNAT entrega a ele o endereço real de quem conecta de fora. A prova é
  `ip_edge` = `peer` nas linhas da trilha depois do primeiro acesso externo (ADR 0020).
- **Barreira de rede.** O security group da instância é declarado a **única** barreira de rede:
  80 e 443 da internet, SSH (Secure Shell) restrito ao endereço de quem opera, nada mais. Ele
  vive fora do repositório. O `README.md` o registra como pré-condição, e nada no repositório o
  verifica.
- **Premissa.** A premissa de loopback passa a valer para Postgres e Redis em todo ambiente, e
  para o proxy fora de produção. O proxy de produção é a exceção declarada. Host único e réplica
  única continuam.

Esta ADR não altera código. Quem a aplica é o passo 7 de `docs/plano-contrato-backend.md`:
`docker/Caddyfile` com a diretiva `tls` condicionada por placeholder de ambiente, e o arquivo
`docker-compose.prod.yml`.

Contraparte: a ADR 0016 da `nova_api_SPA`
(`../../../nova_api_SPA/docs/adr/0016-publicar-na-vercel-com-vercel-json-variaveis-por-ambiente-e-previews-sem-idp-de-producao.md`)
publica a SPA na Vercel com os valores do IdP de produção no painel. É a origem que esta
exposição existe para servir.

## Consequências

Positivas:

- A SPA na Vercel alcança o IdP por HTTPS com certificado que o navegador aceita, sem CA local a
  instalar.
- A cadeia de origem medida sob a ADR 0017 vale sem remedição: um salto, `X-Forwarded-For`
  substituído, `TRUSTED_PROXY_COUNT = 1`. O limitador conta cada cliente, e a trilha registra o
  endereço de cada um.
- O colapso do proxy de userland do Docker (ADRs 0017 e 0020) deixa de alcançar o tráfego
  externo, e `ip_edge` separa, linha a linha, o que veio de fora do que veio do próprio host.
- Máquina de desenvolvimento nenhuma passa a atender na rede local: o arquivo base continua em
  loopback, e a exposição só existe onde o override é invocado.
- Nenhuma peça além do override: a diferença entre produção e desenvolvimento cabe num arquivo
  pequeno, versionado e revisável, e a 0017 é emendada no mínimo.

Negativas:

- O override tem de ficar coerente com o arquivo base: um serviço renomeado no base deixa o
  override apontando para um serviço que não existe.
- A fusão de `ports:` concatena por padrão. Um override escrito sem `!override` ou `!reset`
  acrescenta publicações em vez de trocá-las, e só o `config` com os dois arquivos mostra o
  resultado real. A tag exige Compose 2.24 ou posterior na instância.
- Esquecer o segundo `-f` num `up` derruba o acesso externo sem aviso do comando. A falha é
  fechada: o proxy volta a `127.0.0.1` e nada fica exposto. O sinal é `docker compose ps`
  mostrando o `proxy` em `127.0.0.1:80` e `127.0.0.1:443`, e a conferência está na checklist do
  passo 8. Até alguém rodar o comando certo, a SPA e a renovação por HTTP-01 ficam sem acesso.
- A documentação operacional (`docs/runbook.md`, `docs/receita.md`) cita `docker compose up` sem
  `-f`. Lida na instância, ensina o comando errado. A varredura é dos passos 7 e 8.
- **Gatilho de revisão.** A invocação manual se sustenta em um operador só e uma instância. Se
  houver um segundo operador ou deploy automatizado, o esquecimento deixa de ser raro, e esta
  escolha é revista entre script versionado, link para `docker-compose.override.yml` e
  `COMPOSE_FILE`.
- Um salto só prende a topologia a uma instância com uma réplica. Balanceador, CloudFront ou
  segunda instância é ADR nova, com `trusted_proxies` no Caddy, `TRUSTED_PROXY_COUNT` remedido e
  a cadeia das ADRs 0015, 0018 e 0020 medida de novo.
- A proteção de rede depende de configuração que o repositório não vê. Como a publicação sem
  endereço fura o firewall da instância, não existe segunda linha atrás do security group.
- `caddydata` passa a guardar estado caro de regenerar: recriá-lo pede certificado novo, e
  recriações repetidas esgotam o limite de emissão do Let's Encrypt para o nome, deixando o IdP
  sem certificado até a janela reabrir. `docker compose down -v`, que a ADR 0017 aceitava como
  perda da CA local, passa a ser incidente em produção.
- O primeiro `up` de produção depende de DNS (Domain Name System) já propagado e da porta 80
  aberta. Sem os dois, o Caddy falha no desafio e serve 502 ou nada enquanto tenta de novo
  (`docs/runbook.md`, seção 19).
- A exposição aciona, na letra, os gatilhos de duas ADRs aceitas. A 0006 diz que o
  `docker-compose` "precisará ser substituído se o projeto sair do sandbox", e a 0008, que a
  decisão sobre estáticos "terá de ser revista" na mesma condição. Esta ADR não as revisa. A
  revisão de cada uma fica registrada como dívida em `.claude/memory/decisions.md`, e até lá as
  duas seguem em vigor com o gatilho vencido.
- **Risco aceito: `refresh_token` sem expiração.** `OAUTH2_PROVIDER` não declara
  `REFRESH_TOKEN_EXPIRE_SECONDS` nem `ROTATE_REFRESH_TOKEN`. Valem os defaults do
  `django-oauth-toolkit` 3.4.1 (`oauth2_provider/settings.py:65-68`):
  `REFRESH_TOKEN_EXPIRE_SECONDS = None`, `ROTATE_REFRESH_TOKEN = True` e
  `REFRESH_TOKEN_REUSE_PROTECTION = False`. Cada troca de `code` em `/o/token/` devolve um
  `refresh_token` que não expira e que o `cleartokens` não recolhe enquanto não for revogado. Ele
  é rotacionado a cada uso, e reapresentar um token já rotacionado não revoga a cadeia. A SPA o
  recebe em memória e o ignora (`docs/contrato-backend.md` §2). Com o IdP exposto, é uma
  credencial de vida indefinida ao alcance de qualquer script que rode na origem da SPA. A
  correção é tarefa própria, com ADR.
- **Risco aceito: cookies com a política do default.** `config/settings.py` declara só
  `SESSION_COOKIE_SECURE` e `CSRF_COOKIE_SECURE`, ambos iguais a `BEHIND_TLS_PROXY`. O resto vem
  do Django 5.2: `SESSION_COOKIE_SAMESITE = "Lax"`, `SESSION_COOKIE_HTTPONLY = True`,
  `SESSION_COOKIE_AGE` de duas semanas, `SESSION_EXPIRE_AT_BROWSER_CLOSE = False`,
  `CSRF_COOKIE_SAMESITE = "Lax"`, `CSRF_COOKIE_HTTPONLY = False` e `CSRF_COOKIE_AGE` de 52
  semanas. A volta sem senha no reload da SPA depende do `Lax`. Como o logout da SPA é só local,
  num navegador compartilhado quem vier depois entra sem senha por até duas semanas. Nada impede
  que uma atualização do Django troque esses valores sem aviso. A correção é tarefa própria, com
  ADR.

## Alternativas consideradas

- **Script versionado (`scripts/compose-prod.sh`) que sempre invoca os dois arquivos.**
  Descartada: é um mecanismo a manter para um operador só, e um `docker compose` direto o
  contorna de todo modo.
- **Link `docker-compose.override.yml` → `docker-compose.prod.yml` na instância, no
  `.gitignore`.** O Compose lê esse nome sozinho, sem `-f`. Descartada: é estado local invisível
  no repositório, e um link criado por engano em desenvolvimento expõe a máquina.
- **`COMPOSE_FILE` no `.env` da instância.** Descartada: faz da exposição um valor de ambiente, o
  que a ADR 0017 recusou porque "uma variável convida a flipá-la sem decidir".
- **Publicar 80 e 443 sem endereço no `docker-compose.yml` base.** Um arquivo só, nada a lembrar.
  Descartada: o base também sobe a jornada de container em desenvolvimento, e toda máquina que a
  rodasse passaria a atender na rede local, com a chave e as contas de desenvolvimento, por DNAT
  à frente do firewall dela.
- **Editar os endereços à mão no checkout da instância**, como a ADR 0017 previa. Nenhuma peça
  nova. Descartada: a configuração de produção viveria como diff local não versionado, invisível
  a quem lê o repositório, sujeito a conflito ou descarte no próximo `git pull` e sem revisão.
- **Dois arquivos de compose completos, um por ambiente.** Descartada: duplica todos os serviços,
  os dois divergem sem aviso, e selecionar um deles ainda exige `-f`.
- **ALB com certificado do ACM (AWS Certificate Manager) e o Caddy como proxy interno.** É o
  arranjo mais comum na AWS, com TLS gerenciado e caminho aberto para escala horizontal.
  Descartada porque acrescenta um segundo salto que o código não mede. O Caddy teria de declarar o
  ALB em `trusted_proxies` para anexar ao `X-Forwarded-For` em vez de substituí-lo,
  `TRUSTED_PROXY_COUNT` subiria para 2, e as ADRs 0015, 0018 e 0020 teriam de ser remedidas contra
  uma topologia que este escopo, com uma SPA e uma instância, não usa. Sem essa remedição, todos
  os usuários chegariam com o endereço do balanceador: o limitador contaria a SPA inteira como um
  cliente só, e a trilha perderia a origem. É o defeito que a 0015 trata por código e a 0020
  marca na linha, de volta por topologia.
- **CloudFront à frente do Caddy.** O mesmo segundo salto, com um cache de borda que um IdP não
  aproveita: descoberta e JWKS (JSON Web Key Set) são pequenos, e `/o/token/` e `/o/authorize/`
  não se cacheiam. Descartada pelas mesmas razões.
- **Certificado por desafio DNS-01, com a porta 80 fechada.** Dispensaria a porta 80. Descartada:
  a imagem oficial `caddy:2.11.4` não traz módulo de provedor de DNS, e o desafio exigiria
  credencial do provedor na instância. A porta 80 já serve ao 308 para `https`.
