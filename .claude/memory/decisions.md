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
| 2026-08-29 | Empacotar o IdP como container único orquestrado por docker-compose | [0006](../../docs/adr/0006-empacotar-o-idp-como-container-unico-orquestrado-por-docker-compose.md) |
| 2026-08-29 | Fixar o issuer do IdP em `{BASE_URL}/o` | [0007](../../docs/adr/0007-fixar-o-issuer-do-idp-em-base-url-barra-o.md) |
| 2026-09-01 | Servir estáticos com WhiteNoise sem manifesto de hash | [0008](../../docs/adr/0008-servir-estaticos-com-whitenoise-sem-manifesto-de-hash.md) |
| 2026-09-01 | Isolar a view de `/health` da sessão e do usuário | [0009](../../docs/adr/0009-isolar-a-view-de-health-da-sessao-e-do-usuario.md) |
| 2026-09-01 | Isentar `/health` do redirecionamento para HTTPS | [0010](../../docs/adr/0010-isentar-health-do-redirecionamento-para-https.md) |
| 2026-09-01 | Dar teto de tempo ao `/health` e derivar o `HEALTHCHECK` dele | [0011](../../docs/adr/0011-dar-teto-de-tempo-ao-health-e-derivar-o-healthcheck-dele.md) |
| 2026-09-08 | Emitir o log operacional em JSON, com identificador de requisição — **emendada pela 0014** | [0012](../../docs/adr/0012-emitir-o-log-operacional-em-json-com-identificador-de-requisicao.md) |
| 2026-09-08 | Registrar a trilha de auditoria dos quatro sinais em arquivo durável | [0013](../../docs/adr/0013-registrar-a-trilha-de-auditoria-dos-quatro-sinais-em-arquivo-duravel.md) |
| 2026-09-08 | Manter o identificador de requisição até a requisição seguinte; emenda à 0012 | [0014](../../docs/adr/0014-manter-o-identificador-de-requisicao-ate-a-requisicao-seguinte.md) |

---

## Entradas sem ADR

**Regra ao acrescentar:** se a decisão tem ADR, escreva **uma linha** no índice e o resto
no ADR. Se não tem, escreva a entrada completa aqui. Um log que cresce sem poda não é
memória — é sedimento.

---

## [2026-09-09] TASK-013 · Bloco A: o instrumento de pé, e o que a mutação achou que a leitura não achava

O log operacional em JSON com identificador de requisição e a trilha de auditoria dos quatro
sinais entraram juntos, como o guia previa. O que o guia não previa está aqui.

**Três ADRs, não duas.** `docs/gaps/observabilidade.md` §9 previa duas. A terceira nasceu de um
critério de aceite que o desenho não atendia: o `reset` do `ContextVar` na saída do middleware
rodava antes de `log_response`, e a linha de erro de todo 404, 503 e 400 saía sem o pedido a que
pertencia. O `architect` recusou emendar o critério e redigiu a ADR 0014 como emenda à 0012 —
sobrescrever sem repor. O preço está na seção 14 do runbook: linha emitida fora de requisição,
num processo que já atendeu alguma, carrega o identificador da última.

**A suíte foi de 35 para 57 casos, e o que a fez crescer duas vezes foi a mutação.** A segunda
passagem do `quality-assurance` não conferiu os testes lendo-os: inverteu o código num clone
descartável e olhou qual caso ficava vermelho. Onze mutações ficaram vermelhas, o que prova as
guardas. Três sobreviveram, e cada uma virou demanda:

- segredo registrado em logger não declarado em `LOGGING` sai pelo handler da raiz, e o coletor
  do caso que varre segredos estava anexado só aos quatro loggers nomeados (T-11);
- `"identifier": credentials.get("username")` acrescentado à linha de falha de autenticação grava
  o e-mail em claro, e nenhum caso exercitava o caminho de falha (T-12);
- o `extra=` da linha de acesso reduzido a `{"route": request.path}` perde `method`, `status` e
  `duration_ms` e troca o nome da rota pelo caminho, contra o que o runbook promete a quem opera
  (T-13).

As três estão fechadas, e a mutação de cada uma hoje derruba exatamente o caso que a persegue.
O método fica: **guarda de teste prova-se invertendo o código, não lendo o teste.**

**A trilha ia para dentro da imagem.** O gate adversarial achou o que duas passagens de
conformidade não acharam: o `.dockerignore` barra `.env`, `*.pem` e `docs/`, e não barrava
`logs/`; o `Dockerfile` faz `COPY . .`. Verificado na imagem de então —
`docker run --rm --entrypoint ls nova_api-app -la /app/logs/` devolvia `audit.log`. Numa máquina
onde alguém autenticou pela jornada de construção, aquele arquivo leva `sub`, endereço de origem
real e `identifier_sha256` para toda imagem construída dali em diante: inerte, porque o compose
aponta `AUDIT_LOG_PATH` para o volume, e ao mesmo tempo presente, sem retenção e fora de todo
lugar que a documentação dá como endereço da trilha. Corrigido com uma linha, e verificado: na
imagem nova `/app/logs` não existe, o container sobe `Healthy`, a suíte passa dentro dele, e a
trilha do volume atravessou o build intacta — 1284 bytes, as mesmas quatro linhas. **O que a
correção introduz**, e está no relatório do `writer`: `docker run` nu da imagem, sem compose,
herda `AUDIT_LOG_PATH=logs/audit.log` do `.env` e agora morre no boot com o
`ValueError: Unable to configure handler 'audit'` da seção 15. Não é jornada documentada — toda
invocação escrita passa por `docker compose exec` ou `run`, que carregam a sobrescrita.

**A contagem saiu dos documentos, por decisão.** `docs/testes.md` afirmava quatro números — "um
único módulo testa código do app", "dois lugares" sem banco, "os outros dez arquivos" — e os
quatro ficaram falsos dentro desta mesma tarefa. Nenhum volta. O documento passou a dizer o
critério e o comando que o responde: `grep -l '^from accounts' tests/*.py`. A contagem da suíte
também não entrou em documento nenhum.

**O que este fechamento deve à perda de contexto.** A sessão que rodou as fases 1 a 8 morreu, e
com ela os relatórios que a fase 8 do `/feature` manda repassar verbatim. A segunda passagem foi
**reexecutada** contra o disco, e achou o que a original não tinha achado: cinco apontamentos
críticos em vez de dois, e o AC-10 parcial onde a original dava os catorze critérios por
atendidos. Os dois críticos de documentação da passagem original nunca foram gravados em
`context.json` e continuam desconhecidos. A lição entrou no arquivo: os enunciados íntegros de
T-11, T-12 e T-13 foram gravados em `context.json` antes de o `tester` ser invocado, justamente
porque o relatório que os continha ia morrer.
- **Tech-debt e melhorias, com a disposição de cada um.** Quarenta e nove apontamentos entraram
  na lista ao longo da tarefa. Os que foram corrigidos dentro dela não têm linha aqui: estão no
  código. Ficam registrados os que sobrevivem.

  **Adiado para um bloco nomeado de `docs/implementacao-robustez.md`:**
  - **Bloco B.** O campo `ip` da trilha e a chave de contagem do limitador são a mesma decisão
    vista duas vezes; decidir uma sem a outra é adiar a metade que não emite sinal.
  - **Bloco C.** O usuário dedicado no container exigirá revisar a posse do volume da trilha. E,
    mais grave, é o bloco que cria duas populações de `ip` no mesmo arquivo append-only: hoje o
    campo é `REMOTE_ADDR`, que no container é sempre `172.18.0.1`; no dia em que alguém ler
    `X-Forwarded-For` para que o campo volte a dizer algo, o passado fica ambíguo e nada na linha
    distingue as duas leituras, porque o instante da troca não está gravado. A ADR 0012 declara
    que mudar o esquema "não depende de ninguém" — o que era verdade enquanto o único destino era
    efêmero. **A decisão de versionar a linha tem de ser tomada antes da troca**, pela primeira
    regra do próprio guia: decisão que encarece depois vem antes.
  - **Bloco F.** O bloco passa a ter um terceiro objeto a copiar, o volume `auditlog`; o guia
    ainda o descreve como "o par banco mais segredo".
  - **Ficha 2.9, tuning do gunicorn.** Nenhuma linha identifica o processo que a escreveu:
    `process`, `processName` e `thread` estão na lista de atributos excluídos do objeto JSON.
    Um worker que degrada produz `duration_ms` bimodal e nada que o separe de dependência
    intermitente. A seção 4 do guia afirma que com o bloco A haveria como saber; não há.

  **Adiado sem bloco, por não ter dono ainda:**
  - Retenção e poda da trilha seguem indecididas, e o volume cresce sem limite. Disco cheio para
    a escrita em silêncio. O levantamento pedia que a terceira ADR decidisse também isto; a ADR
    0013 recusa por escrito, e o que faltava era justamente o registro de por que a recusa era
    aceitável: o bloco A entrega o instrumento, e retenção é política de dado pessoal, que numa
    sandbox de host único sem TLS próprio não tem ainda quem a defina.
  - A lacuna de `docs/seguranca.md` §4 não fecha inteira: criação de `Application` e revogação de
    token não têm sinal.
  - Nenhum teste alcança a concorrência entre os três workers sobre o mesmo arquivo, nem o
    alçapão A4. A escolha do `WatchedFileHandler` é leitura de código, não propriedade
    verificada. Com `LOG_LEVEL=DEBUG`, `oauthlib` registra material de token em DEBUG e sairia
    pelo `console`, e nenhum caso cobre essa configuração. Os dois são candidatos a `/test-gap`,
    não a correção.
  - A lista nominal das classes sem banco, em `docs/testes.md`, envelhece a cada teste novo, e
    nada acusa quando envelhece. Foi o formato pedido pelo `quality-assurance` e é o mais útil
    hoje.

  **Aceito e já documentado, sem correção de código:**
  - A posição do middleware de observabilidade ante o `CorsMiddleware` é indetectável quando
    violada, e a preflight `OPTIONS` não deixa rastro; `app_authorized` dispara também no grant
    de refresh, de modo que contar linhas conta errado; `LOG_LEVEL=WARNING` apaga a linha de
    acesso inteira. Os três estão na seção 14 do runbook, que é o catálogo das falhas sem
    sintoma.
  - `AUDIT_LOG_PATH=logs/audit.log` é relativo ao diretório de trabalho, e `manage.py` rodado de
    fora da raiz cria `logs/` no lugar errado. Está em `.env.example`, em `docs/receita.md` e na
    tabela da seção da trilha, no runbook.
  - A saída de `manage.py test` passa a carregar uma linha JSON de acesso por requisição, entre
    os pontos do executor. Silenciar exigiria decidir algo sobre o handler `console` sob teste.
  - O sentinela `-` no `request_id` cobria três populações quando foi apontado; a terceira
    desapareceu com a ADR 0014, e as duas que restam — boot e comandos de `manage.py` — estão na
    seção 2 do runbook.

  **Registrado sem correção possível nesta tarefa:**
  - A ADR 0013 afirma que não normalizar a caixa do resumo SHA-256 preserva a distinção entre
    contas. É falso: `UserManager.create_user` chama `normalize_email`, que abaixa a caixa do
    domínio, então `a@X.com` e `a@x.com` não são contas distintas. Não há consequência prática —
    `get_by_natural_key` é sensível a caixa sob Postgres, e variar caixa não compra evasão a
    quem ataca —, e ADR aceita é imutável: a correção, se vier, é ADR nova.
  - A trilha não declara desde quando cobre o que afirma, e não tem proteção de integridade
    contra quem tem acesso ao host. O runbook passou a dizer o que a ausência de linha não
    prova; o mecanismo segue recusado pela ADR 0013.

  **Três lições de processo, que não são do código:**
  - **Evidência de container exige reconstruir a imagem antes de medir.** A evidência da jornada
    de clonar-e-rodar reportada na fase 7 era inválida: a imagem era de 2026-09-02 e não continha
    o código da tarefa. A segunda passagem refez quatro critérios de aceite por isso, e passou a
    conferir `md5sum` dentro e fora do container.
  - **A mutação que prova uma guarda roda em clone descartável, nunca na árvore.** Na fase 7 o
    `tester` editou `config/observabilidade.py` para provar a regressão do T-05 e reverteu byte a
    byte, declarando o desvio. É travessia de fronteira de escrita, que o protocolo define como
    compromisso e não barreira. Na fase 8b o mesmo agente, avisado, fez as onze mutações num
    clone fora do repositório.
  - **Não paralelizar o `writer` sobre `docs/` com o `tester` sobre `tests/` quando o documento
    descreve a suíte.** Foi decisão minha, e produziu duas quase-falsidades em `docs/testes.md`,
    pegas só porque o `writer` releu o código antes de escrever: dois itens de "O que a suíte não
    cobre" já eram falsos quando ele chegou, porque o `tester` acabara de fechar os buracos.
    Sequenciar as duas fases custaria uma espera e removeria a classe inteira de erro.

- **ADR:** [0012](../../docs/adr/0012-emitir-o-log-operacional-em-json-com-identificador-de-requisicao.md),
  [0013](../../docs/adr/0013-registrar-a-trilha-de-auditoria-dos-quatro-sinais-em-arquivo-duravel.md) e
  [0014](../../docs/adr/0014-manter-o-identificador-de-requisicao-ate-a-requisicao-seguinte.md),
  esta última emenda à 0012. Ver o índice no topo.
- **Tipo:** decisão.
