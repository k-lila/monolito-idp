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

---

## Entradas sem ADR

**Regra ao acrescentar:** se a decisão tem ADR, escreva **uma linha** no índice e o resto
no ADR. Se não tem, escreva a entrada completa aqui. Um log que cresce sem poda não é
memória — é sedimento.

---

## [2026-09-13] TASK-014 · Bloco B: o teto nas três portas, e o preço de desenhar contra documento

O limitador entrou nas três portas e a chave de contagem foi decidida antes do proxy, que era a
única ordem que o repositório já tinha por escrito. O que o guia não previa está aqui.

**A ficha 2.1 estava errada, e ninguém tinha como saber antes de instalar.** O desenho inteiro do
`architect` repousou em `docs/robustez-info.md`, e a dependência que ela descreve não estava no
`.venv` nem no `requirements.txt`. Três afirmações caíram assim que o `writer` instalou:
`AXES_USERNAME_FORM_FIELD` tem por default `USERNAME_FIELD`, isto é `email` — campo que o
formulário não tem —, e sem a linha explícita o AC-01 **nunca dispararia**, em silêncio; os checks
do axes são `Warning` e `manage.py check` sai com código zero, não reprova; e
`AXES_RESET_COOL_OFF_ON_FAILURE_DURING_LOCKOUT` é `True`, de modo que o prazo é móvel. As duas
últimas nem estavam na ficha — foram omissões, e omissão não aparece em revisão nenhuma.

**O critério que sobrou disso vale para os blocos que faltam**, e é mais estreito que "desconfiar
das fichas": tudo que a ficha 2.1 cita como **valor** com `arquivo:linha` continua verdadeiro; o
que caiu foi o único ponto em que ela usa **verbo** sobre comportamento. Valor citado com
`arquivo:linha` conta como levantamento; verbo sobre o que a biblioteca faz conta como hipótese. A
ficha 2.2, que governa o Bloco C, tem a mesma forma — e o verbo sem citação dela
(`SECURE_PROXY_SSL_HEADER` "faz o Django confiar em `X-Forwarded-Proto` de qualquer origem")
sustenta um item inteiro daquele bloco.

**A ADR 0016 nasceu com quatro afirmações falsas, e a imutabilidade foi suspensa três vezes.** Duas
vinham da ficha (os checks, e a forma de `AXES_LOCKOUT_PARAMETERS`); uma era do desenho ("uma
escrita a mais no Postgres a cada tentativa falha", quando são quatro a cinco consultas); e a
quarta nem era culpa dela — uma decisão posterior do `quality-assurance` a superou. O usuário
autorizou as três correções in loco, com a mesma justificativa a cada vez: untracked, nunca
revisada, carimbada "Aceito" pelo próprio autor. **A regra do `CLAUDE.md` continua valendo para
todas as outras ADRs.** O que este caso ensina é anterior à regra: ADR redigida sobre documento não
conferido não é decisão registrada, é hipótese com carimbo.

**A mutação achou o que a leitura não achava, de novo — e desta vez contra um comentário.** O
comentário de `AXES_LOCKOUT_PARAMETERS` existia para nomear uma falha silenciosa e nomeava a
mutação **inócua**: dizia que `["username", "ip_address"]`, sem os colchetes internos, faria o axes
contar pelo par. Não faz — a suíte fica inteira verde com ela. Em `axes/helpers.py:285-293` cada
**elemento** da lista vira um filtro independente, e elemento string produz o mesmo filtro que
elemento lista de um item. A forma cara, que derruba AC-01 e AC-02 de uma vez, é
`[["username", "ip_address"]]`: um elemento só, com as duas chaves dentro. O comentário estava em
três lugares e os três foram corrigidos.

**O AC-12 reprovou por um defeito que a suíte verde escondia.** Seis execuções consecutivas em
menos de sessenta segundos: as cinco primeiras `OK`, a sexta `FAILED (failures=15)`, com
diagnóstico que não mencionava limitação em lugar nenhum — `consentimento nao produziu code`. O
contador vivia no Redis do ambiente, na mesma chave que o `runserver` da jornada de construção
enche, e `tests/runner.py` isolava `DATABASES` e `LOGGING` e não `CACHES`. Fechado desligando o
dicionário inteiro na suíte (T-10, revisto pelo T-13), e o preço disso é pago pelo T-17, que prova
que o dicionário de produção ainda alcança o middleware — sem ele, `RATE_LIMIT_POR_CAMINHO = {}`
deixado por engano passaria com tudo verde.

**Dois comportamentos nasceram de decisão do usuário depois dos treze critérios**, e por isso a
tarefa voltou ao `product-manager` para cunhar AC-14 e AC-15. O gate adversarial mostrou que o
prazo móvel, que já estava decidido, é **também** o caminho de escrita caro: com ele, o retorno
curto de `axes/handlers/database.py:150-162` nunca dispara, e cada tentativa bloqueada roda um
DELETE, um `select_for_update`, um UPDATE com dois `Concat` e dois SELECT, reescrevendo
`attempt_time` e escapando da limpeza automática. `/accounts/login/` ganhou teto de requisição de
60 por minuto por origem — **acima** do teto do axes de propósito, porque a semântica de segurança
continua sendo dele e este teto existe só para limitar custo. E o limitador passou a **falhar
aberto**: antes desta tarefa `/o/token/` não tocava o Redis, e o middleware novo o tinha tornado
500 durante uma queda.

**O `product-manager` recusou-se a prometer o que não daria para verificar.** O gate adversarial
afirmou que "o axes continua de pé durante a queda do Redis, porque conta no Postgres"; ele foi ao
código e achou a metade falsa — `cached_db.py` captura `Exception` em `load` e em `save` e **não**
em `exists`, usado na criação de chave de sessão. O `writer` confirmou rodando
`SessionStore()._get_new_session_key()` com o cache fora do ar. Senha errada continua contada e
bloqueada; senha certa tende a 500, por caminho alheio ao limitador. Isso ficou fora do AC-15 e
dentro do runbook.

**Onze documentos afirmavam sobre este código coisa que o código desmentia.** O pior deles só foi
aberto na passagem final: `docs/seguranca.md` listava "**Sem limitação de taxa**" como controle
ausente e mantinha a limitação de taxa como item 1 do que precisa mudar antes de expor o IdP — e
ninguém o abrira porque o `architect` não o listou. O método que os achou foi sempre o mesmo, e é o
que o `CLAUDE.md` já manda: varrer a superfície no código, não reler o texto que a descreve. Foi
assim que o `writer` achou sozinho uma terceira linha falsa em `docs/arquitetura.md` e que o
`quality-assurance` achou a contradição interna do runbook — a seção 14 dando por hipotético um
colapso de origem que a seção seguinte, 270 linhas adiante, já registrava como presente.

- **Tech-debt e apontamentos que sobrevivem, com a disposição de cada um.** Mais de quarenta
  apontamentos entraram na lista ao longo da tarefa. Os corrigidos dentro dela não têm linha aqui:
  estão no código.

  **Aceitos e já corrigidos na tarefa** — sem linha própria: as três falsidades da ficha 2.1 (na
  ADR e nos comentários), a contradição do runbook, o comentário de `AXES_LOCKOUT_PARAMETERS`, o de
  `AXES_CLIENT_IP_CALLABLE`, o de `TRUSTED_PROXY_COUNT`, o AC-12, a guarda vazia do T-04, a
  obrigação do Bloco C no guia, `docs/seguranca.md`, `docs/testes.md`, os dois procedimentos de
  desbloqueio e as duas contaminações da trilha (truncadas por decisão do usuário).

  **Adiados, com o gatilho de cada um:**
  - **Sem política de senha.** `AUTH_PASSWORD_VALIDATORS` não é declarado, e o default é lista
    vazia. Enfraquece a aritmética do teto de cinco tentativas: contra senha de seis caracteres,
    cinco por quinze minutos ainda é muito. Candidato a bloco próprio, fora do B.
  - **`/admin/login/` sem teto de requisição.** Protegido só pelo axes; `RATE_LIMIT_POR_CAMINHO`
    não o nomeia. Registrado em `docs/seguranca.md`.
  - **O T-16 guarda invariante mais fraca do que a necessária.** Ele assere
    `teto > AXES_FAILURE_LIMIT`; como cada tentativa pela tela custa **duas** requisições contadas
    (o GET do formulário e o POST), a alcançabilidade da tela de bloqueio exige
    `teto > 2 × AXES_FAILURE_LIMIT`. Um valor entre 6 e 10 passaria no teste e tornaria a página
    "Tentativas em excesso" inalcançável. Hoje são 60 contra 5, folga de seis vezes. Apertar a
    asserção exige o AC pedir — não se legisla por cima do `product-manager`.
  - **A alínea (b) do T-14 é vazia sob GET.** `authenticate()` não é chamado em hipótese nenhuma
    ali, e `AccessAttempt.objects.count() == 0` valeria com o middleware ausente. A perna do AC-14
    está atendida pela estrutura e por constatação com POST, não por aquela linha.
  - **`tests/runner.py` não isola `CACHES`.** Além do contador, a suíte escreve no mesmo Redis do
    ambiente a cópia quente das sessões e a chave da sonda do `/health`. Anterior a esta tarefa; o
    T-13 resolve o contador, não o cache.
  - **Concorrência entre jornadas.** Os três módulos que reativam o limitador por
    `override_settings` fixam origem e apagam a chave à mão, no Redis compartilhado. Rodar as duas
    jornadas ao mesmo tempo, ou passar `--parallel`, faz o `setUp` de uma apagar a chave enquanto a
    outra conta.
  - **`config/origem.py` subdeclara quem depende dele.** O docstring diz "o limitador de taxa de
    `/o/`", e o limitador cobre três caminhos desde este bloco. O módulo existe justamente para ser
    a única leitura de origem.
  - **`docs/seguranca.md`, seção 2** ("O que o IdP protege hoje") não tem linha para o limitador
    nem para o axes. Não é falsidade — a seção não se declara exaustiva —, mas quem ler só ela
    conclui que o IdP não tem teto.
  - **`docs/robustez.md:11` e `docs/robustez-info.md:67`** ainda descrevem a superfície como
    "throttle nos endpoints de token". São documentos de levantamento anteriores à ADR 0016.
  - **Uma linha de WARNING por requisição sob queda do Redis**, sem supressão. O único aviso da
    ausência de teto é também o que mais cresce durante o incidente que o gerou.
  - **A trilha emite uma linha `user_locked_out` por tentativa bloqueada**, não uma por bloqueio:
    oito falhas produzem oito `user_login_failed` e quatro `user_locked_out`. Catalogado no
    runbook; sob ataque sustentado a trilha cresce duas linhas por tentativa, em arquivo
    append-only sem retenção.

  **O que o Bloco C herda, e que encarece se for adiado:**
  - **Ligar `BEHIND_TLS_PROXY` troca a população do campo `ip` da trilha e a chave do limitador na
    mesma tecla**, num arquivo append-only onde nada distingue as duas populações. A ADR 0015
    proíbe ligá-la antes de decidir o versionamento da linha, e o campo "Exige antes" do Bloco C
    passou a registrar isso.
  - **`TRUSTED_PROXY_COUNT = 0`** faria `saltos[-0]` devolver o primeiro salto, o escrito pelo
    cliente; com o cabeçalho ausente e a variável de proxy ligada, é `IndexError` — 500 nas três
    portas de autenticação, e não na sonda.
  - **Uma função, três sumidouros, três domínios de validade.** Um proxy configurado para
    repassar em vez de anexar deixa o cliente escrever `X-Forwarded-For: nao-e-um-ip`; o limitador
    aceita como pedaço de chave, a trilha grava como string, e o axes o entrega a
    `AccessAttempt.ip_address`, que é `GenericIPAddressField` sobre coluna `inet` — `DataError` e
    500 em toda tentativa de login. Proxy que anexa `ip:porta` não dá erro nenhum: cada requisição
    ganha chave própria e os dois limitadores param de contar, em silêncio.
  - **O `requirepass` do Redis, que o Bloco C liga, é exatamente a janela da falha aberta** — só
    que sustentada. Durante ela não há teto em nenhum dos três caminhos.

- **ADR:** [0015](../../docs/adr/0015-resolver-a-origem-do-cliente-num-ponto-unico.md) e
  [0016](../../docs/adr/0016-limitar-a-taxa-na-superficie-de-autenticacao.md). Ver o índice no topo.
- **Tipo:** decisão e tech-debt.
