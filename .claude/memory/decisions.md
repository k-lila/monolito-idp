# Registro de Decisões (tech-debt e decisões sem ADR)

> Log de decisões tomadas durante as tarefas e de melhorias/tech-debt identificados pelo
> `senso-critico`. **Quem escreve aqui é o orquestrador** (o thread principal); nenhum
> subagente grava neste arquivo.
>
> Decisões arquiteturais formais vão em `docs/adr/NNNN-slug.md` — **aqui fica só o resumo
> rastreável** e os itens que não bloquearam.
>
> **Formato de entrada:**
>
> ```
> ## [AAAA-MM-DD] TASK-NNN · {título}
> - **Decisão:** o que foi decidido e por quê.
> - **ADR:** docs/adr/NNNN-slug.md (se houver).
> - **Tech-debt / melhorias:** apontamentos que não bloquearam, com a disposição dada.
> - **Tipo:** decisão | melhoria | observação.
> ```

---

## Índice de decisões formalizadas em ADR

| Data | Decisão | ADR |
| --- | --- | --- |
| 2026-08-29 | Django 5.2 LTS sobre Python 3.14 como plataforma do monólito | [0001](../../docs/adr/0001-adotar-django-5-2-lts-sobre-python-3-14.md) |
| 2026-08-29 | django-oauth-toolkit como servidor de autorização OAuth2/OIDC — **emendada pelas 0024 e 0030** | [0002](../../docs/adr/0002-usar-django-oauth-toolkit-como-servidor-de-autorizacao.md) |
| 2026-08-29 | Identidade em `User` customizado com e-mail como identificador | [0003](../../docs/adr/0003-modelar-identidade-em-user-customizado-com-email-como-identificador.md) |
| 2026-08-29 | Assinar tokens com RS256, chave privada no ambiente — **emendada pela 0028** | [0004](../../docs/adr/0004-assinar-tokens-com-rs256-e-custodiar-a-chave-privada-no-ambiente.md) |
| 2026-08-29 | Sessão SSO em sessão Django com backend `cached_db` sobre Redis | [0005](../../docs/adr/0005-manter-a-sessao-sso-em-sessao-django-com-backend-cached-db.md) |
| 2026-08-29 | Empacotar o IdP como container único orquestrado por docker-compose — **emendada pelas 0017 e 0019** | [0006](../../docs/adr/0006-empacotar-o-idp-como-container-unico-orquestrado-por-docker-compose.md) |
| 2026-08-29 | Fixar o issuer do IdP em `{BASE_URL}/o` | [0007](../../docs/adr/0007-fixar-o-issuer-do-idp-em-base-url-barra-o.md) |
| 2026-09-01 | Servir estáticos com WhiteNoise sem manifesto de hash | [0008](../../docs/adr/0008-servir-estaticos-com-whitenoise-sem-manifesto-de-hash.md) |
| 2026-09-01 | Isolar a view de `/health` da sessão e do usuário | [0009](../../docs/adr/0009-isolar-a-view-de-health-da-sessao-e-do-usuario.md) |
| 2026-09-01 | Isentar `/health` do redirecionamento para HTTPS | [0010](../../docs/adr/0010-isentar-health-do-redirecionamento-para-https.md) |
| 2026-09-01 | Dar teto de tempo ao `/health` e derivar o `HEALTHCHECK` dele | [0011](../../docs/adr/0011-dar-teto-de-tempo-ao-health-e-derivar-o-healthcheck-dele.md) |
| 2026-09-08 | Emitir o log operacional em JSON, com identificador de requisição — **emendada pela 0014** | [0012](../../docs/adr/0012-emitir-o-log-operacional-em-json-com-identificador-de-requisicao.md) |
| 2026-09-08 | Registrar a trilha de auditoria dos quatro sinais em arquivo durável — **estendida pela 0018; ampliada pela 0029** | [0013](../../docs/adr/0013-registrar-a-trilha-de-auditoria-dos-quatro-sinais-em-arquivo-duravel.md) |
| 2026-09-08 | Manter o identificador de requisição até a requisição seguinte; emenda à 0012 | [0014](../../docs/adr/0014-manter-o-identificador-de-requisicao-ate-a-requisicao-seguinte.md) |
| 2026-09-10 | Resolver a origem do cliente num ponto único — a chave de contagem | [0015](../../docs/adr/0015-resolver-a-origem-do-cliente-num-ponto-unico.md) |
| 2026-09-10 | Limitar a taxa na superfície de autenticação: axes no login, middleware próprio nos três caminhos | [0016](../../docs/adr/0016-limitar-a-taxa-na-superficie-de-autenticacao.md) |
| 2026-09-13 | Terminar o TLS num proxy declarado no compose e publicar só ele; emenda à 0006 — **emendada pela 0027** (antes pela 0026, substituída) | [0017](../../docs/adr/0017-terminar-o-tls-num-proxy-declarado-no-compose.md) |
| 2026-09-13 | Declarar a procedência do endereço em cada linha da trilha; estende a 0013 | [0018](../../docs/adr/0018-declarar-a-procedencia-do-endereco-em-cada-linha-da-trilha.md) |
| 2026-09-13 | Criar o superusuário por comando explícito, fora do boot; emenda à 0006 | [0019](../../docs/adr/0019-criar-o-superusuario-por-comando-explicito-fora-do-boot.md) |
| 2026-09-14 | Marcar na linha da trilha o endereço colapsado pelo `docker-proxy`; emenda à 0018 — **emendada pela 0027** | [0020](../../docs/adr/0020-marcar-na-linha-o-endereco-colapsado-pelo-docker-proxy.md) |
| 2026-09-17 | Pular o consentimento na `Application` de primeira parte por `skip_authorization`; default global intocado — contraparte: SPA 0014 | [0021](../../docs/adr/0021-pular-o-consentimento-na-application-de-primeira-parte-por-skip-authorization.md) |
| 2026-09-17 | Liberar o CORS por origem exata, uma por ambiente; previews da Vercel fora — contraparte: SPA 0016 | [0022](../../docs/adr/0022-liberar-o-cors-por-origem-exata-e-deixar-os-previews-da-vercel-fora.md) |
| 2026-09-17 | Não oferecer cadastro nem perfil nesta fase; contas criadas no admin — contraparte: SPA 0012 | [0023](../../docs/adr/0023-nao-oferecer-cadastro-nem-perfil-nesta-fase-e-manter-a-criacao-de-contas-no-admin.md) |
| 2026-09-22 | Montar sob `/o/` só as listas de protocolo do toolkit (metadata, base, oidc); emenda à 0002 — **emendada pela 0030** | [0024](../../docs/adr/0024-montar-sob-o-so-as-listas-de-protocolo-do-django-oauth-toolkit.md) |
| 2026-09-23 | Congelar a forma do issuer de produção em `https://<PUBLIC_HOST>/o`, sem literal de domínio versionado; cumpre a condição da 0007 — contraparte: SPA 0017 | [0025](../../docs/adr/0025-congelar-o-issuer-de-producao-na-forma-https-public-host-barra-o.md) |
| 2026-09-23 | Expor na AWS por um salto de proxy só, ACME, 80/443 fora de loopback por override invocado com `-f`; emenda à 0017 — **substituída pela 0027** — contraparte: SPA 0016 | [0026](../../docs/adr/0026-expor-o-idp-na-aws-por-um-salto-de-proxy-so-com-acme-e-80-443-fora-de-loopback.md) |
| 2026-09-24 | Servir o IdP de produção da máquina do dono pelo Cloudflare Tunnel, sem porta de entrada, com zona própria e túnel entregue por quem opera; substitui a 0026 e emenda a 0017 e a 0020 — contraparte: SPA 0018 | [0027](../../docs/adr/0027-servir-o-idp-de-producao-da-maquina-local-pelo-cloudflare-tunnel-sem-porta-de-entrada.md) |
| 2026-09-28 | Gerar a chave de assinatura em RSA 3072 pelo gerador único de segredos (`scripts/gen_env_secrets.sh`); emenda à 0004 | [0028](../../docs/adr/0028-gerar-a-chave-de-assinatura-em-rsa-3072-pelo-gerador-unico-de-segredos.md) |
| 2026-09-29 | Ligar o logout iniciado pela RP em `/o/logout/`: revogação restrita à Application, retorno só a destino cadastrado, `end_session_endpoint` publicado, evento `tokens_revogados` na trilha (amplia a 0013) — contraparte: SPA 0019 | [0029](../../docs/adr/0029-ligar-o-logout-iniciado-pela-rp-com-revogacao-restrita-a-application.md) |
| 2026-09-29 | Sombrear a rota de logout do toolkit com `LogoutPelaRPView`, subclasse com quatro métodos montada antes do include; emenda à 0002 e à 0024 só para `/o/logout/` | [0030](../../docs/adr/0030-sombrear-a-rota-de-logout-do-toolkit-com-uma-subclasse-da-view.md) |

---

## Entradas sem ADR

**Regra ao acrescentar:** se a decisão tem ADR, escreva **uma linha** no índice e o resto
no ADR. Se não tem, escreva a entrada completa aqui. Um log que cresce sem poda não é
memória — é sedimento.

---

## [2026-09-28] TASK-024 · Passo 5 do plano de implantação: aceite da ADR 0027 e documentação (encerrada como obsoleta)

Rota `/chore` com fase de `architect` inserida (precedente TASK-020), aberta em 2026-09-28. O
architect entregou o inventário com RESSALVA. Tarefa **pausada** até a unificação dos scripts de
geração, em tarefa própria.

- **Decisão (usuário): ensaio do Passo 4 dado por feito**, com três verificações sem medição —
  dois clientes de redes distintas, `fetch` de navegador a `/o/token/` e volta após restart do
  Docker (o operador relatou "laço incorreto", sem detalhe) — e desmontagem incompleta (imagem,
  clone com `.env`, `.env.bak` e credenciais do túnel de ensaio, registro de DNS). As três vão
  para os Passos 6 e 7; nenhuma é marcada como medida.
- **Decisão (usuário): placeholders, nunca literais do ensaio.** Nome de ensaio e endereço de
  classe E não entram em arquivo versionado (ADR 0025). O plano não commitado já os trazia, por
  erro do orquestrador; saem antes do commit.
- **Decisão (usuário): aceitar a 0027 agora**, com a alínea *Reinício* sem medição e o item no
  Passo 6.
- **Decisão (usuário): comentários de YAML e da Caddyfile entram** na tarefa, só linhas de
  comentário; prova por `sha256sum` do `config` do base e suíte.
- **Decisão (usuário): `../pre-deploy.md` com Goals 4 e 5 marcados como superados**, sem
  reescrever.
- **Decisão (usuário): data de expiração do domínio e data-limite de suporte do `cloudflared`
  não constam em código nem no repositório.** A alínea "Renovação do domínio" da 0027 (proposta)
  deixa de dizer que a data fica no runbook; o roteiro de pin sai sem data-limite, e a nota R6
  do Passo 3 muda de acordo.
- **Decisão (usuário): a geração de chaves e segredos fica num arquivo só.** Hoje são dois:
  `scripts/gen_dev_key.sh` (versionado, RSA 2048) e `scripts/gen_env_secrets.sh` (untracked).
  A unificação é tarefa própria, antes da retomada desta; o tamanho da chave decide-se nela. Ela
  resolve a contradição entre o runbook ("a chave de produção não sai deste script") e o plano
  6.2.
- **Autorização (usuário):** ADRs 0027, 0026 (só o Status) e SPA 0018, e os dois `CLAUDE.md`.
- **Retomada (2026-09-28), revisão do architect com RESSALVA; respostas do usuário:**
  - **P1: a TASK-025 foi commitada antes** (`acfc115`), sem o plano e sem `.claude/memory/`.
  - **P2: sai a data de lançamento da 2026.9.3** e a regra "a janela conta dessa data" do
    comentário de `docker-compose.prod.yml`; fica só "o pin sobe antes do fim da janela de
    suporte". Leitura estrita da decisão sobre datas.
  - **P3: o `CLAUDE.md` do `nova_api` deixa de dizer "a única `OIDC_RSA_PRIVATE_KEY`"** na
    edição já autorizada: cada clone tem a sua chave.
  - **Escopo desta passada: só o `nova_api`** (13 arquivos). SPA (ADR 0018, `CLAUDE.md`,
    `contrato-frontend`, `implementacao-contrato`, `spa-nucleo`) e `../pre-deploy.md` ficam
    para uma segunda passada; até lá a 0027 aceita aponta para uma 0018 ainda proposta, e o
    Passo 5 não é marcado.
  - **Adiado, rota `/feature` própria, dono o usuário:** rotação sem disrupção por
    `OIDC_RSA_PRIVATE_KEYS_INACTIVE` — põe duas chaves no JWKS, muda a §1 do plano (contrato
    com a SPA) e contradiz a 0004 e a 0028.
  - **Adiado, dono o usuário:** retirar `--http-host-header` (troca 400 por 200 coerente com
    `PUBLIC_HOST` errado); exigiria remedição.
  - **Pendência do dono:** desmontagem do ensaio deixou credenciais e registro de DNS.
  - **QA da passada 1 (RESSALVA):** o usuário mandou corrigir os dois críticos e as nove
    observações; a data de lançamento da 2026.9.3 sai também do bloco histórico da TASK-023 no
    plano (leitura estrita da decisão sobre datas); o `CLAUDE.md` fica com "a única
    `OIDC_RSA_PRIVATE_KEY` daquele ambiente".
  - **Hashes antes dos comentários** (mesmo shell, só o hash): `config` do base `22cefc3e…a9d6`;
    `config` com o override e `COMPOSE_PROJECT_NAME=x TUNNEL_ID=y` `d440d0df…b69f`.
- **Encerramento (usuário, 2026-09-30): obsoleta.** A passada 2 dependia de documentos que
  saíram na reorganização de 2026-09-29 (plano de implantação, runbook, `contrato-frontend`,
  `implementacao-contrato`). A 0027 e a 0018 da SPA estão aceitas. Disposição dos apontamentos
  sem linha acima: os três sobre o runbook (restauração do `auditlog`, §19 e "o que este
  documento não cobre") são **rejeitados**, porque o documento já não existe; os dois de medição
  (agregação por /64 e um cliente só não prova ausência de colapso) ficam **adiados**, com os
  Passos 6 e 7, que são de quem opera.
- **Tipo:** decisão.

## [2026-09-28] TASK-025 · Gerador único dos segredos do `.env`

Rota `/feature` completa (product-manager, architect, writer, QA, tester, QA, senso-critico),
aberta e encerrada em 2026-09-28. Encerrada por decisão do usuário ("a task presente deve somente
se ater ao refatoramento do script"), sem o AC-07. `scripts/gen_dev_key.sh` foi movido por
`git mv` para `scripts/gen_env_secrets.sh` e absorveu o antigo `gen_env_secrets.sh` untracked:
seis linhas por padrão, `--so-chave-rsa` só para a chave, RSA 3072 fixo nos dois ambientes, sem
escrita no `.env`. Testes `TASK-025/T-01` e `T-02` (suíte 148 OK nas duas jornadas).

- **Decisão (architect, autorizada):** 3072 bits (128 de segurança, o nível do SHA-256; 2048 só
  até 2030 pelo NIST), mesmo tamanho em dev e prod, sem parâmetro; `--so-chave-rsa` resolve o
  AC-05 por construção; nome `gen_env_secrets.sh`; ADR 0028 como emenda à 0004.
- **Decisão (usuário): ADR 0028 fica Proposta.** O aceite, a marca "emendada pela 0028" na linha
  da 0004 em `docs/arquitetura.md` e a linha no índice de lá esperam o AC-07.
- **Pendente, com dono (usuário): AC-07.** Trocar só a linha `OIDC_RSA_PRIVATE_KEY` do `.env` de
  dev pela de `./scripts/gen_env_secrets.sh --so-chave-rsa` (substituir, nunca `>>`); `up -d
  --force-recreate --wait app`; JWKS com `1 [('RS256', 3072)]`; login da SPA contra o IdP real até
  `/app` sem erro do `jose`. O `.env` de dev tinha chave de 2048 em 2026-09-28. Depois, aceitar a
  0028.
- **Adiado para a TASK-024 (registrado lá):** `docs/plano-implantacao.md:358` aponta o script
  removido (AC-06 fechado com essa disposição, por decisão do usuário); roteiro de rotação com
  "substitua a linha, nunca `>>`" (`read_env` fica com a primeira, o compose com a última); `ALTER
  ROLE` antes da `POSTGRES_PASSWORD` nova no roteiro de comprometimento; `runbook.md:950` sem os
  dois `-f`; `OIDC_RSA_PRIVATE_KEYS_INACTIVE` do DOT como caminho de rotação sem disrupção.
- **Aceitos e resolvidos na própria tarefa:** README sem geração manual da `REDIS_PASSWORD`, com a
  frase "copie só essas duas" (mantida pelo QA); `.env.example:29` e `receita.md:96` apontam o
  script; siglas RSA, NIST e IdP expandidas na 0028; Negativa do índice "com o aceite"; frase
  "os tamanhos são os da receita" apagada; comentário longo do script e linha curta da 0028
  reembrulhados pelo orquestrador (autorizado); teste instável do senso-critico (substring "URL"
  no base64, ~0,9%) trocado por prefixo de linha; `assertEqual` que despejaria segredo trocado
  por booleano; `SimpleTestCase`; T-02 compara o `n` com o módulo gerado (absorve o T-03).
- **Rejeitados, com justificativa:** `runbook.md:322` com `openssl rand` (o script não tem modo de
  uma senha só); cópia parcial como disciplina manual (declarada no texto; mecanismo seria
  elaboração além da tarefa); tamanho de chave colada à mão (já é Negativa da 0028); escape não
  provado vermelho no T-02 (o T-01 cobre); "nenhum teste lê o script" (T-01 e T-02 existem).
- **Adiados, dívida:** `receita.md:68` "ADR 0025" antes da expansão (preexistente); SHA-256 sem
  expansão na 0028 (nome de algoritmo); `docs/robustez-info.md:312`, `../roadmap-inicial.md:172`
  e `../desavencas.md:313` citam `gen_dev_key.sh` (históricos, decisão do usuário); CLAUDE.md
  "a única `OIDC_RSA_PRIVATE_KEY`" diante de dev e prod, e esta mesma contradição nas linhas
  150-152 deste arquivo — rever no aceite da 0028 ou na TASK-024.
- **Observações:** falha intermitente não identificada na primeira rodada da suíte no contêiner
  (1 em 11; a saída foi truncada pelo orquestrador; 10 rodadas seguintes OK, inclusive logo após
  recriar o `app`) — se voltar, capturar a saída inteira. Um grep do QA na Fase 5 tentou ler
  credenciais do user-service em `../cloudflare/` e recebeu "Permission denied"; nada foi lido, e
  as buscas seguintes foram restritas a `nova_api`. Para o commit: `git add
  scripts/gen_env_secrets.sh` antes, porque o índice guarda o rename com o conteúdo antigo;
  `docs/plano-implantacao.md` e parte de `.claude/memory/` são da TASK-024.
- **Resíduo no host:** stack de dev deixado de pé em 2026-09-28 para o AC-07 (estava parado).
- **Tipo:** decisão, pendência com dono e tech-debt.

## [2026-09-29] TASK-026 · Modificação A de `../retoques.md`: botão da home do IdP para a SPA

Rota `/feature` completa (product-manager, architect, writer, QA, writer, tester, QA,
senso-critico), aberta e encerrada em 2026-09-29. A home ganhou o link "Ir para a aplicação",
com e sem sessão, cujo destino é `SPA_URL`: variável nova, sem default, validada na carga das
settings por `_validar_spa_url` (`config/settings.py`), que levanta `ImproperlyConfigured` sem
repetir o valor. Tokens de `static/css/idp.css` na paleta neutral da SPA. Testes novos
`tests/test_spa_url.py`, `tests/test_home.py` e `tests/test_sem_recurso_de_terceiro.py` (suíte
161 OK na jornada de construção; o QA provou 9 mutações). Sem ADR: o contrato OIDC não muda.

- **Decisão (retoques.md): a raiz não redireciona.** Ela é o destino de `LOGIN_REDIRECT_URL` e de
  `LOGOUT_REDIRECT_URL`, e o "Sair" do cabeçalho é, enquanto a Modificação B não existir, o único
  jeito de encerrar a sessão do IdP.
- **Decisão (architect, confirmada pelo usuário): isenção de loopback.** Sob `BEHIND_TLS_PROXY`,
  `http://` só é aceito em `localhost`, `127.0.0.1` e `::1`. O container de dev força
  `BEHIND_TLS_PROXY "True"` (`docker-compose.yml:109`), e sobrescrever `SPA_URL` no
  `environment:` do compose base apagaria o valor de produção. Emendou AC-05 e AC-07 e desvia de
  `retoques.md:49` ("só https://").
- **Decisão (usuário, depois do QA): validação endurecida.** Também recusa barra invertida,
  espaço em branco, porta vazia e porta ilegível, com a mensagem de forma.
- **Decisão (architect):** validação na carga e não por system check (o gunicorn não os roda);
  `SPA_URL` só no contexto da home, sem context processor; teste da carga por `runpy` com
  `Env.read_env` neutralizado.
- **Adiado, dívida aceita pelo usuário (CRITICO do senso-critico): produção herdando
  `http://localhost:5173`.** O `.env` de produção nasce do `.env.example`
  (`plano-implantacao.md:407`, `../pre-deploy.md:232`), que traz esse valor; a isenção o aceita, e
  a conferência de `plano-implantacao.md:443`, feita na máquina do dono com o Vite de pé, passa.
  O botão levaria todo usuário externo a "conexão recusada". Saídas levantadas e não escolhidas:
  `SPA_URL=` vazio no exemplo, que falha alto como o CORS; conferir de outra máquina e contra
  `CORS_ALLOWED_ORIGINS`; recusar loopback só em produção por marca no `docker-compose.prod.yml`,
  como o `DEBUG`.
- **Adiado (usuário; CRITICO do senso-critico): o outro lado.** `SPA_URL` não está em
  `../pre-deploy.md` (tabela `:217`, lista do `.env` `:232`) nem em
  `nova_api_SPA/docs/contrato-frontend.md`, que `retoques.md:73-74` exige. Uma troca de origem da
  SPA atualiza CORS e `redirect_uri` à força (o login quebra) e deixa `SPA_URL` para trás sem
  sinal; se o subdomínio antigo da Vercel for registrado por terceiro, a home do IdP passa a
  apontar para ele. Com a Modificação B, a origem ganha a quarta cópia
  (`post_logout_redirect_uris`).
- **Adiado, dívida:** `SPA_URL` e `CORS_ALLOWED_ORIGINS` coincidem em produção sem mecanismo que
  os una (registrado na §14 do runbook); T-07 é regex sobre `templates/` e não vê include de
  fora nem href vindo de variável.
- **Pendente, com dono (usuário):** conferência a olho de login, consentimento, bloqueio e home
  (Checklist A); suíte na jornada de container (`docker compose up -d --build app`, depois
  `docker compose exec app python manage.py test`); `SPA_URL` no `.env` de produção antes do
  deploy do código, e o backup cifrado refeito depois; em produção, o botão levando à landing.
  O `.env` de dev tem hoje `SPA_URL=https://spa-idp.vercel.app`, a origem de produção: o botão do
  IdP local leva à SPA publicada.
- **Aceitos e resolvidos na própria tarefa:** `docs/testes.md` com os três arquivos; origem com
  porta aceita; query, fragmento e credenciais recusados; `plano-implantacao.md:413` refluída;
  `SPA_URL` no `.env` de dev (pelo usuário), o que destravou a suíte sem variável no ambiente;
  `docs/testes.md:150` com as recusas da Fase 6 e `:152` com `href` ou `src` em qualquer tag e o
  `<link>` único, corrigidas pelo orquestrador depois do encerramento, a pedido do usuário.
- **Rejeitados, com justificativa:** teste de `&` ou aspas no href e do autoescape (o autoescape
  está ligado e `|safe` é proibido; a validação já recusa query e espaço); "host em maiúsculas
  recusado" (falso: só o esquema em maiúsculas é recusado, com a mensagem de forma, sem defeito).
- **Tipo:** decisão, pendência com dono e tech-debt.

---

## [2026-09-29] TASK-027 · Modificação B de `../retoques.md`, lado do IdP: logout iniciado pela RP

Rota `/feature` completa, aberta e encerrada em 2026-09-29: product-manager, architect (três
passadas), writer, QA (três passagens), tester e senso-critico. `/o/logout/` é atendido por
`accounts.logout_rp.LogoutPelaRPView`, montada numa rota-sombra antes do include
(`config/urls.py`), com as cinco chaves `OIDC_RP_INITIATED_LOGOUT_*` declaradas
(`DELETE_TOKENS` e `ALWAYS_PROMPT` falsas, `STRICT_REDIRECT_URIS = BEHIND_TLS_PROXY`), teto de
120/min, tela `logout_confirm.html` em português e o sexto receptor da trilha
(`registrar_revogacao`). ADRs 0029 e 0030, ambas em Proposto. Suíte na jornada de construção:
208 OK (eram 161, com a guarda antiga de ausência do `end_session_endpoint` invertida). AC-01 a
AC-19; o AC-15 fica parcial até a jornada de container.

- **Decisões do usuário:** P1 (a) STRICT segue `BEHIND_TLS_PROXY`; P2 (b) evento de revogação
  na trilha; P3 (b) hint autêntico sem linha tratado como ausente; P4 (b) revogação só na
  Application que pediu; P5 (a) 0029 Proposta até a 0019 da SPA; P6 e A1 (b) toda entrada
  forjada conhecida dá 400, com a cerca da 0030 alargada a quatro métodos
  (`validate_post_logout_redirect_uri`) e `DataError`/`ValidationError` capturados sob
  savepoint; A2 a corrida do refresh fica como silêncio, sem laço de releitura (o architect
  mostrou que o refresh órfão já é recusado pelo toolkit e que a ordem inversa só se fecha em
  `/o/token/`).
- **Decisão (architect):** a 0030 é ADR nova, no precedente da 0024; a ampliação da 0013 é
  seção da 0029, no precedente da 0016. A 0030 passa a Aceito quando o AC-15 for constatado; a
  0029, quando a SPA gravar a 0019 e o caminho dela entrar na seção Decisão.
- **Constatado pelo QA e pelo tester:** o psycopg 3 recusa NUL no cliente e não aborta a
  transação, então os casos com NUL provam o 400 e não o savepoint; a prova do savepoint é
  `SavepointDaEntradaForjadaTests` (T-22), com `SELECT 1/0` do servidor e mutação por caso (sem
  o savepoint sai `InternalError`, transação abortada).
- **Silêncios aceitos (registrados nas ADRs, `seguranca.md` e runbook §14):**
  `ACCEPT_EXPIRED_TOKENS` vale só enquanto a linha do `IDToken` existir; o `id_token_hint`
  viaja na query string e fica num campo oculto da tela; o log de erro do Caddy, o `cloudflared`
  e a borda não foram medidos; trocar a chave RSA faz os hints em circulação darem 400; o admin
  não valida `post_logout_redirect_uris`; a revogação alcança todos os dispositivos da conta
  naquela Application; um refresh validado antes da saída e gravado depois nasce vivo.
- **Adiado, dívida aceita pelo usuário:** a tela de confirmação sai sem
  `Cache-Control: no-store`, e o `id_token` fica no cache do navegador (sem sessão, é credencial
  de revogação naquela Application); corrigir exige um quinto método ou middleware.
- **Adiado:** os dois "Sair" com efeitos diferentes (o do topo, `/accounts/logout/`, não revoga)
  — unificação é decisão à parte; `nova_api_SPA/docs/contrato-frontend.md:38` e as ADRs 0004,
  0010 e 0014 da SPA ainda afirmam a ausência de `end_session_endpoint` — tarefa da SPA;
  `../pre-deploy.md` sem o cadastro de `post_logout_redirect_uris` — passada 2 da TASK-024;
  separar dos commits das TASK-024 e TASK-026 os arquivos desta tarefa.
- **Pendente, com dono (usuário):** a jornada de container (AC-15), com nome de projeto
  explícito: `docker compose -p nova_api exec app python manage.py test`, depois de conferir que
  o container de dev tem o código atual. O `.env` deste diretório tem
  `COMPOSE_PROJECT_NAME=nova_api_prod`, e o projeto de produção roda a partir daqui:
  `docker compose` sem `-p` atinge a produção. `post_logout_redirect_uris` cadastrado em dev
  (`http://localhost:5173/`) e em produção (`https://<spa>/`, com a barra final) antes da SPA
  usar o endpoint.
- **Aceitos e resolvidos na tarefa:** `seguranca.md:78` ("logout só por POST") reescrito; AC
  reemitidos (AC-16 a AC-19 novos, AC-18 ampliado); texto da tela para hint de outra conta e para
  hint sem linha ("usada ou descartada"); comentário de `TRUSTED_PROXY_COUNT`; docstrings do
  runner; premissa do `cleartokens` corrigida em teste e docs; âncora do T-21; `jti` não-UUID na
  cerca; índice de `docs/arquitetura.md` com a 0028.
- **Rejeitados, com justificativa:** argumento "o sinal mora com o emissor, como
  `app_authorized`" impreciso (o do toolkit vive em `signals.py`), sem consequência;
  divergências de `../retoques.md` (cita `settings.py:347` e `DELETE_TOKENS True`) — documento
  de trabalho, superado pela decisão P4.
- **Tipo:** decisão, pendência com dono e tech-debt.

## [2026-09-29] Nomear os projetos pelo papel: IdP e SPA, não `nova_api` e `nova_api_SPA`

- **Decisão (usuário):** `nova_api` e `nova_api_SPA` são nomes de diretório improvisados. Texto,
  comentário e referência cruzada chamam os projetos de IdP e SPA, e um arquivo do outro lado
  pelo caminho interno a ele ("`docs/contrato-idp.md` da SPA"), sem `../` nem nome de diretório.
  A única linha que liga papel a diretório fica no `CLAUDE.md` da raiz (`idp/`).
- **Fora da troca, por decisão:** as ADRs aceitas, que continuam imutáveis e citam os nomes
  antigos; a memória de agentes, que é registro histórico; `POSTGRES_DB`/`POSTGRES_USER`
  (`nova_api`) e `COMPOSE_PROJECT_NAME=nova_api_prod`, que ficam presos a volumes com dados.
- **Divergência aceita, sem ADR:** o usuário do container passou a `idp` (UID/GID 10001
  inalterados), e a trilha, a `/var/log/idp`. A ADR 0013, aceita, segue dizendo
  `/var/log/nova_api`: vale o `docker-compose.yml`. O volume `auditlog` é o mesmo, e a posse
  fica na raiz dele, então não se perde trilha. Vale na próxima imagem construída.
- **Silencioso:** o compose de desenvolvimento não tem `name:`, e o nome do projeto, dos volumes
  e dos containers deriva do diretório (`nova_api_*`). Renomear o diretório troca o projeto sem
  aviso e deixa os volumes antigos órfãos.
- **Tipo:** decisão sem ADR e tech-debt.

## [2026-09-30] Pendências das ADRs fechadas pelo status quo, sem ADR nova

- **Decisão (usuário):** as pendências que as ADRs aceitas deixaram para "tarefa própria, com
  ADR" fecham pelo comportamento atual, sem código e sem ADR. As ADRs não são editadas: o
  fechamento seria fato novo nelas.
  - Cookie de sessão (0021): `SESSION_COOKIE_SAMESITE`, `SESSION_COOKIE_AGE` e
    `SESSION_EXPIRE_AT_BROWSER_CLOSE` seguem sem declaração, nos defaults do Django (`Lax`, duas
    semanas, `False`).
  - `REFRESH_TOKEN_EXPIRE_SECONDS` (0021, 0026): segue no `None` do toolkit, como a §3 de
    `docs/nucleo-idp.md` já publica.
  - `CORS_URLS_REGEX = r"^/o/"` (fora da 0022) e `AUTH_PASSWORD_VALIDATORS` (fora da 0023):
    decisões em vigor, registradas sem ADR.
- **Riscos aceitos:** um upgrade do Django pode trocar os defaults do cookie em silêncio; o
  `refresh_token` sem expiração fica ao alcance de qualquer script na origem da SPA
  (`docs/seguranca.md`).
- **Ficam como gatilho, não como pendência:** agregação por /64 e gatilhos de revisão da 0027;
  revisão da 0006 e da 0008; cadastro público (0023); registro dinâmico (0024); rotação por
  `OIDC_RSA_PRIVATE_KEYS_INACTIVE`; alcance do logout com a segunda RP.
- **Onde ficou:** `docs/arquitetura.md`, "Decisões em vigor sem ADR"; `docs/nucleo-idp.md` §7
  mantém só os gatilhos. Nada muda na SPA.
- **Tipo:** decisão sem ADR e tech-debt aceito.
