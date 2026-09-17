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
| 2026-08-29 | django-oauth-toolkit como servidor de autorização OAuth2/OIDC | [0002](../../docs/adr/0002-usar-django-oauth-toolkit-como-servidor-de-autorizacao.md) |
| 2026-08-29 | Identidade em `User` customizado com e-mail como identificador | [0003](../../docs/adr/0003-modelar-identidade-em-user-customizado-com-email-como-identificador.md) |
| 2026-08-29 | Assinar tokens com RS256, chave privada no ambiente | [0004](../../docs/adr/0004-assinar-tokens-com-rs256-e-custodiar-a-chave-privada-no-ambiente.md) |
| 2026-08-29 | Sessão SSO em sessão Django com backend `cached_db` sobre Redis | [0005](../../docs/adr/0005-manter-a-sessao-sso-em-sessao-django-com-backend-cached-db.md) |
| 2026-08-29 | Empacotar o IdP como container único orquestrado por docker-compose — **emendada pelas 0017 e 0019** | [0006](../../docs/adr/0006-empacotar-o-idp-como-container-unico-orquestrado-por-docker-compose.md) |
| 2026-08-29 | Fixar o issuer do IdP em `{BASE_URL}/o` | [0007](../../docs/adr/0007-fixar-o-issuer-do-idp-em-base-url-barra-o.md) |
| 2026-09-01 | Servir estáticos com WhiteNoise sem manifesto de hash | [0008](../../docs/adr/0008-servir-estaticos-com-whitenoise-sem-manifesto-de-hash.md) |
| 2026-09-01 | Isolar a view de `/health` da sessão e do usuário | [0009](../../docs/adr/0009-isolar-a-view-de-health-da-sessao-e-do-usuario.md) |
| 2026-09-01 | Isentar `/health` do redirecionamento para HTTPS | [0010](../../docs/adr/0010-isentar-health-do-redirecionamento-para-https.md) |
| 2026-09-01 | Dar teto de tempo ao `/health` e derivar o `HEALTHCHECK` dele | [0011](../../docs/adr/0011-dar-teto-de-tempo-ao-health-e-derivar-o-healthcheck-dele.md) |
| 2026-09-08 | Emitir o log operacional em JSON, com identificador de requisição — **emendada pela 0014** | [0012](../../docs/adr/0012-emitir-o-log-operacional-em-json-com-identificador-de-requisicao.md) |
| 2026-09-08 | Registrar a trilha de auditoria dos quatro sinais em arquivo durável — **estendida pela 0018** | [0013](../../docs/adr/0013-registrar-a-trilha-de-auditoria-dos-quatro-sinais-em-arquivo-duravel.md) |
| 2026-09-08 | Manter o identificador de requisição até a requisição seguinte; emenda à 0012 | [0014](../../docs/adr/0014-manter-o-identificador-de-requisicao-ate-a-requisicao-seguinte.md) |
| 2026-09-10 | Resolver a origem do cliente num ponto único — a chave de contagem | [0015](../../docs/adr/0015-resolver-a-origem-do-cliente-num-ponto-unico.md) |
| 2026-09-10 | Limitar a taxa na superfície de autenticação: axes no login, middleware próprio nos três caminhos | [0016](../../docs/adr/0016-limitar-a-taxa-na-superficie-de-autenticacao.md) |
| 2026-09-13 | Terminar o TLS num proxy declarado no compose e publicar só ele; emenda à 0006 | [0017](../../docs/adr/0017-terminar-o-tls-num-proxy-declarado-no-compose.md) |
| 2026-09-13 | Declarar a procedência do endereço em cada linha da trilha; estende a 0013 | [0018](../../docs/adr/0018-declarar-a-procedencia-do-endereco-em-cada-linha-da-trilha.md) |
| 2026-09-13 | Criar o superusuário por comando explícito, fora do boot; emenda à 0006 | [0019](../../docs/adr/0019-criar-o-superusuario-por-comando-explicito-fora-do-boot.md) |
| 2026-09-14 | Marcar na linha da trilha o endereço colapsado pelo `docker-proxy`; emenda à 0018 | [0020](../../docs/adr/0020-marcar-na-linha-o-endereco-colapsado-pelo-docker-proxy.md) |

---

## Entradas sem ADR

**Regra ao acrescentar:** se a decisão tem ADR, escreva **uma linha** no índice e o resto
no ADR. Se não tem, escreva a entrada completa aqui. Um log que cresce sem poda não é
memória — é sedimento.

---

## [2026-09-17] TASK-015 · Bloco C: o proxy no compose, a procedência do endereço e as duas decisões sem ADR

O TLS (Transport Layer Security) passou a terminar num proxy declarado no compose, só ele
publicado, em `127.0.0.1:443`; a trilha de auditoria ganhou dois campos que dizem, linha a
linha, de onde saiu o `ip` e o que ele é para o processo que o gravou; a credencial
administrativa saiu do boot. Três ADRs (Architecture Decision Records) novas e uma quarta que
emenda a segunda — ver o índice no topo. O que sobrou fora delas está aqui.

**Duas decisões sem ADR, tomadas no Bloco C e atribuídas por engano à ADR 0017 até a segunda
passagem do `quality-assurance`:**

- **O Redis exige senha (`requirepass`), e a senha tem origem única.** `REDIS_PASSWORD` no
  `.env` alimenta o `command` do servidor, o `REDISCLI_AUTH` do healthcheck e a `REDIS_URL` do
  container — um valor, três leitores, para que servidor e cliente não possam divergir.
  `${REDIS_PASSWORD:?}` aborta o `up` com a variável ausente **e** com a vazia: é a convenção do
  shell, e a afirmação contrária esteve escrita em seis pontos até o QA medi-la. O que não tem
  mecanismo é a `REDIS_URL` da jornada de construção, copiada à mão no mesmo `.env`; a
  divergência aparece na primeira operação de cache, e o sintoma medido está na seção 20 do
  `docs/runbook.md`.
- **O processo do container não é `root`: `USER` dedicado com UID e GID 10001.** Literal em
  arquivo versionado, deliberado: o volume nomeado `auditlog` guarda posse numérica, e um UID
  que mudasse entre builds deixaria a trilha sem dono. O volume que já existia era de `root`;
  o `chown -R 10001:10001 /var/log/nova_api` roda **uma vez**, por `run --rm --user root`, e
  está fora do entrypoint de propósito (`docs/receita.md`, passo 3; `docs/runbook.md`).

**Provisório por escolha, e escrito onde a escolha se propaga:** o issuer é
`https://$PUBLIC_HOST/o`, e as quatro derivações — `BASE_URL`, `ALLOWED_HOSTS`, o nome que o
Caddy atende e a claim `iss` — saem da mesma variável. Um erro de digitação em `PUBLIC_HOST` é
autoconsistente: nada no sistema pode discordar dele. A provisoriedade acaba na primeira
relying party (RP) integrada, e depois dela custa um ano de HSTS (HTTP Strict Transport
Security) no navegador de quem visitou o nome errado. BLOCK-001 resolveu-se assim, e o que
resta é obrigação, não impedimento: **confirmar o host real antes da primeira RP integrar.**

**O que foi aceito e ficou como está, com a razão:**

- **A ADR 0017 diz `caddy:2` e o compose declara `caddy:2.11.4`.** O pin entrou no gate
  adversarial, porque a propriedade antiforja do `reverse_proxy` — substituir, e não anexar,
  o `X-Forwarded-For` de par não confiável — foi **medida** numa versão, e tag móvel apostava
  que ela se mantém. A decisão da ADR está intacta; o pin é detalhe abaixo dela, e a ADR é
  imutável. Subir o pin exige remedir, e essa exigência vive só em comentário no
  `docker/Caddyfile`.
- **`TRUSTED_PROXY_COUNT` maior que 1 produz `remote_addr_fallback` em toda requisição**, pela
  mesma propriedade: o cabeçalho chega sempre com um salto. Catalogado no runbook.
- **`ip_edge` é constante em toda linha vinda do host enquanto a publicação ficar em loopback**
  — peso morto até o dia em que a porta sair de `127.0.0.1`, e é para esse dia que existe. O
  caso `gateway` real não é alcançável pela suíte, que constrói requisições sintéticas contra
  uma tabela de rotas de fixture; a única verificação é manual, e está na seção do runbook
  sobre o dia D. A regra de leitura da população do meio (com `ip_src`, sem `ip_edge`)
  apoia-se em o compose nunca ter publicado fora de loopback — é a última vez que esse
  argumento pode ser usado.
- **AC-05 e AC-07 valem para o host, não para outro contêiner na rede do compose:** a porta
  da aplicação continua alcançável por quem estiver na bridge, e é por ali que o proxy fala.
  AC-07 não é verificável por dois `curl` do host — o `docker-proxy` colapsa a origem no
  gateway da bridge —, e é exatamente o que a ADR 0020 marca.

**Tech-debt aceito, adiado:**

- **`_gateway_padrao` não tem caso para tabela de rotas corrompida** — campo `Gateway` que não é
  hexadecimal, ou linha com menos de três campos. A captura larga do código nomeia os dois
  ramos; a T-19 cobre só a ausência do arquivo. Apontado pelo tester, sem demanda.

- **`config/settings.py:247-254`** afirma que remover `AXES_CLIENT_IP_CALLABLE` "hoje não muda
  um único valor". Deixou de valer na jornada de container, onde `BEHIND_TLS_PROXY` é
  verdadeira. O arquivo não foi tocado por proibição nominal do `architect`; é uma frase de
  comentário a corrigir na próxima tarefa que abrir o arquivo.
- **`CLAUDE.md:9` declara o escopo "sem TLS próprio"**, contra as ADRs 0017 e 0020. É arquivo
  do usuário; nenhum agente o toca. Cabe ao usuário decidir a frase.
- **As duas linhas de WARNING de `config/limites.py` gravam `ip` sem procedência.** Fluxo
  efêmero, sem dano de evidência: log operacional, não trilha.
- **Os quatro avisos de transporte do `check --deploy` só somem dentro do container**, porque
  `BEHIND_TLS_PROXY` foi ligada no `environment` do serviço `app`, não no `.env`. O gate do
  Bloco H pressupõe que o C os resolveu; resolveu no container, e é lá que o gate deve rodar.
- **O comentário de `PUBLIC_HOST` no `.env.example` não diz que a escolha é provisória**, e ele
  acompanha a variável até o `.env` de cada implantação. A provisoriedade está em
  `docs/receita.md`; levá-la ao exemplo é uma linha, na próxima tarefa que o abrir.

**Obrigação do ambiente, não do repositório:** o `.env` desta máquina não tem `PUBLIC_HOST` nem
`REDIS_PASSWORD`, e o `REDIS_URL` dele não carrega senha. `docker compose config`, `up` e
`exec` abortam nomeando a variável — a jornada clonar-e-rodar não roda aqui até o usuário
completar o arquivo, e o `.env` não tem cópia nem agente que o escreva. As verificações desta
tarefa que dependiam da jornada de container foram feitas em 2026-09-14 com o ambiente
completo; o fechamento, em 2026-09-17, provou-se só pela jornada de construção.

**O que esta tarefa custou em rodadas, para a próxima:** um `product-manager` com BLOQUEIO e dois
BLOCK resolvidos na Fase 2; dois `writer`, dois `quality-assurance`, dois `tester`; um gate
adversarial com quatro CRITICO, todos aceitos; uma emenda do `architect` (ADR 0020) cuja
gravação caiu por limite de sessão (BLOCK-003) e fechou três dias depois, com `T-19` (sete casos
unitários de `origem_completa` contra tabela de rotas de fixture) e `T-20` (a chave `ip_edge`
nos cinco eventos): 102 testes verdes na jornada de construção. Os três BLOCKs da tarefa saíram
de `blockers.md`: BLOCK-001 virou `PUBLIC_HOST` e a obrigação acima; BLOCK-002 virou a ADR 0018;
BLOCK-003 fechou hoje. Cinquenta e três apontamentos ao todo, todos com disposição.

- **ADR:** [0017](../../docs/adr/0017-terminar-o-tls-num-proxy-declarado-no-compose.md),
  [0018](../../docs/adr/0018-declarar-a-procedencia-do-endereco-em-cada-linha-da-trilha.md),
  [0019](../../docs/adr/0019-criar-o-superusuario-por-comando-explicito-fora-do-boot.md) e
  [0020](../../docs/adr/0020-marcar-na-linha-o-endereco-colapsado-pelo-docker-proxy.md). Ver o
  índice no topo.
- **Tipo:** decisão e tech-debt.
