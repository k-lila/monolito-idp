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
| 2026-09-30 | Abrir o autoatendimento de conta (cadastro, API `/api/conta/`, telas de senha e de e-mail, exclusão) com as telas de senha no IdP e o `sub` em UUID; emenda a premissa da 0016 — **Proposto**; contraparte: ADR da SPA que substitui a 0012 dela, devida lá | [0031](../../docs/adr/0031-abrir-o-autoatendimento-de-conta-com-as-telas-de-senha-no-idp-e-o-sub-em-uuid.md) |

---

## Entradas sem ADR

**Regra ao acrescentar:** se a decisão tem ADR, escreva **uma linha** no índice e o resto
no ADR. Se não tem, escreva a entrada completa aqui. Um log que cresce sem poda não é
memória — é sedimento.

---

## [2026-09-30] TASK-028 · Autoatendimento de conta: disposições da Fase 1

- **Decisão (usuário):**
  - D12, D13 e a parte da 0003 sobre o `sub` entram como **emenda na ADR nova** do
    autoatendimento. A 0003, a 0013 e a 0016 seguem aceitas e intocadas, e o índice as marca
    "emendada pela NNNN". Isso troca o "linha de revisão" da §4 do relatório de
    pré-implementação, porque a linha de revisão só restabelece a verdade.
  - O código começa com a ADR do IdP em **"Proposto"**. Ela e a ADR par da SPA passam a "Aceito"
    no mesmo ato, antes da implantação.
  - A troca de e-mail pelo admin **zera `email_verified`** (e `email_verificado_em`) e não envia
    e-mail. A pessoa confirma pelo "reenviar" da SPA.
- **Tech-debt / melhorias (apontamentos do product-manager):**
  - `desativada_por=admin` é escrito na desativação pelo admin (AC-11), conforme o domínio §3.3.
  - O `sub` UUID entra nos quatro pontos de `accounts/auditoria.py` que gravam a conta, não só no
    citado pela §3.e.
  - O `userinfo` do toolkit não confere `is_active`, e a conta desativada pelo admin continua
    respondendo até o token expirar. O problema já existia antes desta tarefa e ficou fora do
    escopo.
  - Os nomes das variáveis novas (D1 contra `SPA_CLIENT_ID` e `TERMOS_VERSAO_VIGENTE`) ficam para
    o architect.
  - As variáveis novas sem default derrubam a suíte do clone local até quem opera atualizar o
    `.env`. O aviso sai antes do merge.
- **Tipo:** decisão e observação.

## [2026-09-30] TASK-028 · Autoatendimento de conta: disposições da Fase 2

- **Decisão (usuário):** as escolhas do architect que vão além dos critérios de aceite foram aceitas:
  - o token de confirmação leva o `sub` e o resumo SHA-256 do e-mail, não o e-mail em claro, e o
    AC-16 fica cumprido pelo efeito;
  - entra o sinal `email_trocado`;
  - a ADR 0029 também é emendada, porque `tokens_revogados` vai para `accounts/revogacao.py`;
  - o `next` é preservado só em "Criar conta";
  - a tela de login também sai em `pt-br`;
  - o link de confirmação de uma conta desativada leva a `?email=invalido`, e o segundo clique
    leva a `confirmado` sem linha nova na trilha.
- **Autorização:** concedida em 2026-09-30 para os passos 0 e 1. Os passos 2 a 5 esperam nova
  autorização e o `.env` local com `EMAIL_*`, `DEFAULT_FROM_EMAIL` e `SPA_CLIENT_ID`.
- **Tech-debt / riscos aceitos, sem código nesta tarefa:**
  - `DEFAULT_SCOPES` do toolkit é `["__all__"]`, e uma RP que omita `scope` recebe `conta`. A
    conferência do `client_id` no `dispatch` da API fecha o caso, e declarar o default é
    decisão à parte;
  - o `uid` do link de redefinição é o base64 do `id` interno;
  - o `check_password` extra da mensagem de conta desativada abre um canal de tempo, da mesma
    classe da revelação já aceita no cadastro;
  - a conta desativada pelo admin mantém os tokens, porque nem o `userinfo` nem o grant de
    refresh conferem `is_active`;
  - a ADR 0031 passa de uma página, por causa das emendas que concentra;
  - `../pre-deploy.md` não existe e continua citado, como achado paralelo.
- **Pendente:** o número da ADR par da SPA (0020) precisa ser confirmado pela sessão da SPA antes
  do aceite.
- **Tipo:** decisão e tech-debt.

## [2026-09-30] TASK-028 · Mensagem genérica de login e ambiente de verificação

- **Decisão (usuário):** a mensagem genérica de login passa a ser "E-mail ou senha incorretos.",
  por `error_messages["invalid_login"]` do `FormularioDeLogin`.
- **Observação:** com o aval da pessoa usuária, `docker compose up -d postgres redis` subiu neste
  clone o projeto `nova_api_prod`, por causa do `COMPOSE_PROJECT_NAME` do `.env`. Os volumes
  `nova_api_prod_pgdata` e `nova_api_prod_redisdata` nasceram vazios em 2026-09-30, e os antigos
  `nova_api_pgdata` e `nova_api_redisdata`, de 2026-09-28, ficaram sem uso. A produção real, o
  projeto `idp_prod`, não foi tocada.
- **Tech-debt:** o template de login não mostra erros de campo, o que fica para o passo 4. O
  apontamento do writer de que `claims_supported` sairia com `sub` duplicado não procede: a view
  de descoberta deduplica com `list(set(...))`, conferido pelo QA em 2026-09-30.
- **Tipo:** decisão e observação.

## [2026-09-30] TASK-028 · Disposições da Fase 5 (passos 0 e 1)

- **Decisão (usuário):**
  - o login do admin põe o e-mail em minúsculas, por um formulário ligado a
    `admin.site.login_form`. A ADR 0031 ressalva `manage.py changepassword`, que recebe o e-mail
    como está gravado, em minúsculas. O `get_by_natural_key` não muda;
  - a D1 (nomes em português) ganha uma frase na ADR 0031, que ainda está em "Proposto";
  - a linha 38 de `accounts/formularios.py` é quebrada dentro de 100 caracteres.
- **Tipo:** decisão.
- **Tech-debt (Fase 6):** a mensagem padrão de login inválido do admin, `AdminAuthenticationForm`,
  ainda diz que os campos podem distinguir caixa. É um texto impreciso, visto só por staff e sem
  efeito na segurança. Fica como está.

## [2026-09-30] TASK-028 · Fechamento do lote dos passos 0 e 1

- **Decisão (usuário):**
  - nada é commitado por enquanto. A documentação que os passos 0 e 1 tornaram falsa
    (`nucleo-idp`, `integracao-rp`, `arquitetura`, `seguranca`, `testes`) é corrigida no passo 5;
  - o senso-crítico roda agora, sobre os passos 0 e 1, e de novo no fim;
  - os passos 2 a 5 estão autorizados, e o orquestrador pode modificar o `.env` conforme for
    necessário.
- **Feito no `.env`:** as variáveis `EMAIL_*` e `DEFAULT_FROM_EMAIL` foram acrescentadas no fim
  do arquivo, com os valores de desenvolvimento (backend de console). Nenhuma linha existente
  foi lida nem alterada. `SPA_CLIENT_ID` ainda não entrou: falta o valor do `client_id` da
  Application de desenvolvimento.
- **Ajustes de teste dispostos como aceitos (QA, segunda passagem):** T-12, T-06b, a asserção
  da restrição no caso de colisão do admin, o docstring de T-01, o `updated_at` em
  `update_fields`, e as docstrings acima de 100 colunas. Suíte com 241 testes verdes.
- **Tipo:** decisão.

## [2026-10-01] TASK-028 · Disposições do gate adversarial (passos 0 e 1)

- **Decisão (usuário):**
  - A migração 0004 passa a ser irreversível (reversa `None`). O passo 5 escreve, no procedimento
    de quem opera, a única volta atrás permitida: corrigir para a frente com imagem nova, nunca
    voltar a imagem antiga sobre o esquema novo nem restaurar um dump anterior à implantação. A
    ADR 0031, ainda em "Proposto", registra isso em Consequências.
  - Na troca de e-mail, tanto pela página (passo 4) quanto pelo admin, as linhas de
    `AccessAttempt`, `AccessFailureLog` e `AccessLog` do endereço antigo são apagadas por
    `username__iexact`. Assim, apagar a conta passa a ser completo. O histórico de login do
    endereço antigo se perde, e a ADR 0031 registra isso.
- **Aceitos, sem decisão nova:**
  - o SQL que verifica colisão de caixa entra no procedimento de quem opera, no passo 5;
  - os passos 3 e 4 gravam com `update_fields`;
  - o admin editando ao mesmo tempo que a pessoa fica como risco aceito;
  - no passo 5, a disposição de 2026-09-30 prevalece sobre a §4 e a §5 do documento de
    pré-implementação: as ADRs 0013 e 0016 são emendadas pela 0031 e não ganham linha de
    revisão.
- **Tipo:** decisão.

## [2026-10-01] TASK-028 · Disposições do QA do passo 2 (orquestrador)

- **W-01, aceito:** o CONTRATO do architect manda usar `logger.exception` no ramo genérico de
  `envio._enviar`, e isso contradiz a PROIBIÇÃO "e-mail em claro no log, inclusive por
  `str(exc)`". Prevalece a PROIBIÇÃO, que é regra de segurança, e o vazamento foi reproduzido
  pelo QA com um `BadHeaderError`. O ramo vira `logger.error` sem `exc_info`, com
  `outcome="envio_defeito"`, `error_class` e `pilha` por `traceback.format_tb` (a opção A, que
  guarda o lugar do defeito sem a mensagem).
- **Aceito:** o teto por destinatário é contado na chamada de `enfileirar`, não no commit. O erro
  vai só na direção de suprimir um envio, e o passo 4 precisa do retorno síncrono.
- **Risco aceito:** o link de confirmação leva o `sub` e o SHA-256 sem sal do e-mail. Por
  dicionário, quem lê a URL confirma um endereço candidato, como na trilha
  (`accounts/auditoria.py`). Trocar por `salted_hmac` fica em aberto, a pedido.
- **Adiados para os passos seguintes:**
  - W-02 (passo 5): o procedimento de quem opera diz que `migrate accounts <anterior>`
    desaplica a 0005 antes de falhar e que a saída é rodar `migrate` de novo;
  - W-03 (passo 5): `envio_suprimido` pode referir-se a uma operação desfeita, e
    `envio_falhou` e `envio_defeito` entram em `docs/observabilidade.md`;
  - W-04 (passo 4): a limpeza do axes na troca de e-mail cobre também o `save_model` do
    admin;
  - nota para o passo 4: a trilha não volta com o rollback, então nenhum sinal deve ser
    emitido dentro do `atomic` antes do commit, ou emitido sabendo disso.
- **Testes:** T-13 a T-22, T-24 e T-25 vão para o tester. O T-23 espera as rotas dos passos 3
  e 4.
- **Tipo:** decisão.

## [2026-10-01] TASK-028 · Passo 2 fechado

- **Resultado:** a segunda passagem do QA deu RESSALVA só por observações. Os 16 mutantes, de
  M01 a M16, ficaram vermelhos, e a suíte tem 270 testes verdes.
- **Observação aceita:** a docstring de `tests/test_conta_migracao.py` atribui o vermelho à ordem
  da verificação. Na verdade ele vem do `unique` de `email` da 0001. É uma imprecisão de
  comentário, sem efeito na proteção, e fica como está.
- **Observação aceita:** a `pilha` inclui o texto-fonte de cada quadro. É risco residual, sem dado
  da pessoa usuária.
- **Pendente:** o T-23 (links de confirmação e de redefinição) entra depois dos passos 3 e 4.
- **Tipo:** observação.
- **`.env` (2026-10-01, usuário):** entrou `SPA_CLIENT_ID=trocar-pelo-client-id-da-spa` como
  placeholder. A pessoa usuária troca pelo `client_id` real da Application de desenvolvimento.
  Enquanto não trocar, a API recusa toda chamada com `aplicacao_nao_autorizada`.

## [2026-10-01] TASK-028 · Passo 3 (API de conta), disposições do orquestrador

- **Aceito:** `null` no PATCH de `/api/conta/` limpa o campo (vira ""). É semântica comum de
  PATCH, e o passo 5 a registra no contrato do IdP (`docs/integracao-rp.md` e `nucleo-idp` §3),
  para a SPA saber.
- **Aceito:** valor JSON que não é string recebe `invalid`. Corpo malformado ou aninhado demais
  recebe `geral/json_invalido`, e não 500.
- **Aceito:** a confirmação usa `select_for_update`, para que dois cliques gravem só uma linha
  `email_confirmado`.
- **Observação:** para constatar o boot, o writer criou por segundos, no scratchpad da sessão,
  uma cópia filtrada do `.env` (com segredos e sem a linha `SPA_CLIENT_ID`), e a apagou em
  seguida. O orquestrador conferiu que não sobrou cópia. Nas próximas constatações vale outra
  regra: o boot sem uma variável se prova por `patch.dict(os.environ)`, como nos testes, sem
  copiar o `.env`.
- **Tipo:** decisão e observação.

## [2026-10-01] TASK-028 · Disposições do QA do passo 3 (orquestrador)

- **Aceito, a corrigir (writer):**
  - a API recusa o Bearer em `?access_token=` e no corpo form-urlencoded. Só vale o cabeçalho
    `Authorization`, para o token não parar em log de borda nem no Referer. `/o/userinfo/` fica
    como o toolkit o entrega;
  - um token sem dono (`token.user is None`) recebe 403 `aplicacao_nao_autorizada`, e não 500;
  - `versao` dos termos sem `strip`: só a vigente exata vale.
- **Adiado para o passo 5:** a API, o CORS novo, `CORS_EXPOSE_HEADERS`, `resource_metadata` e a
  semântica de `null` vão para `docs/integracao-rp.md` e para a §3 de `docs/nucleo-idp.md`.
- **Testes:** T-26 a T-38 vão para o tester, mais dois casos para as correções acima. O T-38
  cobre a parte de confirmação do T-23; a de redefinição espera o passo 4.
- **Tipo:** decisão.

## [2026-10-01] TASK-028 · Passo 3 fechado

- **Resultado:** a segunda passagem do QA deu RESSALVA só por observações. Das 20 mutações, 19
  foram pegas pela suíte. A que sobreviveu foi tirar o `select_for_update` da confirmação. A
  suíte tem 326 testes verdes.
- **Adiado:** o T-41 (o SQL da confirmação sai com `FOR UPDATE`) entra no lote de testes do
  passo 4. O T-28 não cobre o PATCH recusado, risco baixo e aceito: a guarda está no `dispatch`
  comum aos dois.
- **Tipo:** observação.

## [2026-10-01] TASK-028 · Disposições do passo 4 (writer)

- **Decisão (usuário):** concluir a redefinição de senha apaga as tentativas do axes da conta,
  por `esquecer_tentativas(email)`. Assim vale a promessa da ADR 0031 de que o bloqueio de quinze
  minutos tem saída pela própria pessoa. O risco de quem controla a caixa de e-mail zerar o
  bloqueio fica dentro do risco já aceito: essa pessoa já consegue trocar a senha.
- **Aceito (orquestrador):**
  - `accounts/tentativas.py` e o partial `requisitos_de_senha.html` entram fora da lista do
    architect;
  - `revogar_tokens` sem Application alcançaria um token com `application` nula. Nenhum fluxo
    cria esse token, e o caso fica sem guarda;
  - o T-15 vai para o tester trocar `logout_rp._revogar` por `revogacao._revogar`.
- **Tipo:** decisão.
- **Disposição (orquestrador, apontamento MÉDIO do writer):** a redefinição apaga só
  `AccessAttempt`, que é o que o próprio axes apaga no login bem-sucedido. `AccessFailureLog` e
  `AccessLog` ficam. A decisão da pessoa usuária era desbloquear, não apagar o histórico. Já a
  troca de e-mail e a exclusão continuam com `esquecer_tentativas` completo.
- **Aceito:** o bloqueio por IP continua até o fim do prazo. A ADR fala só do bloqueio da conta.

## [2026-10-01] TASK-028 · Disposições do QA do passo 4

- **Decisão (usuário):** apagar a conta é recusado quando existe `Application` com `user` igual à
  conta. Nesse caso só "desativar" é oferecido, porque o `on_delete=CASCADE` do toolkit apagaria
  a Application e os tokens de toda a RP sem volta. A ADR 0031 registra a regra.
- **Aceito, a corrigir pelo writer (orquestrador):**
  - o comentário de `AXES_COOLOFF_TIME` é reescrito: a redefinição encerra o bloqueio da conta
    (`desbloquear`), e o bloqueio por IP segue até o prazo;
  - `verbose_name` do campo `email` passa a "e-mail" (migração só de estado), para não vazar
    "email address" no validador de semelhança;
  - `never_cache` nas páginas de troca de e-mail e de exclusão.
- **Risco aceito:** o tempo de resposta da recuperação difere em cerca de 0,3 ms com e sem
  conta, como no `PasswordResetView` do Django. Status, `Location` e corpo são idênticos.
- **Testes:** T-42 a T-63 vão para o tester (o T-63 é o T-41 adiado), mais um caso para a recusa
  por Application.
- **Tipo:** decisão.
- **Aceito (orquestrador, apontamento MÉDIO do writer):** `desbloquear(email)` tira também, da
  contagem por origem, as falhas contra aquele endereço, porque o axes 8.3.1 conta a origem
  sobre as mesmas linhas de `AccessAttempt`. Quem quer usar isso para escapar do bloqueio por
  origem precisa redefinir a senha de cada conta atacada, o que já exige controlar a caixa de
  e-mail (risco aceito). O comentário de `AXES_COOLOFF_TIME` descreve isso, e o passo 5 leva a
  ressalva a `docs/seguranca.md`.
- **Aceito:** a mensagem `required` de `modo` ("Escolha entre desativar e apagar.") continua
  igual quando só "desativar" é oferecido.

## [2026-10-01] TASK-028 · Segunda passagem do QA no passo 4 (orquestrador)

- **Aceito, a corrigir (writer):** no admin, `esquecer_tentativas` só roda quando o endereço muda
  de fato, e não quando muda só a caixa. O QA reproduziu o defeito: uma troca só de caixa apagava
  o histórico e o bloqueio de um endereço que continua sendo da conta.
- **Aceito, a testar (tester):**
  - T-65: troca só de caixa pelo admin preserva o axes;
  - T-66: mensagens em pt-br nas quatro páginas em que `<html lang>` não provava nada;
  - T-67: `email_confirmado` emitido fora de `atomic`;
  - o `never_cache` do cadastro, que é a lacuna (b);
  - `_dados` passa para `tests/paginas_helpers.py`.
- **Tipo:** decisão.

## [2026-10-01] TASK-028 · Passo 4 fechado

- **Resultado:** T-65, T-66 e T-67 estão escritos, junto com o `never_cache` do cadastro e o
  `dados_de_cadastro` movido para os helpers. Cada teste novo foi provado por mutação: o
  mutante fica vermelho. A suíte tem 412 testes verdes.
- **Observação aceita:** as páginas `PaginaDeRecuperacaoPedida` e `PaginaDeRedefinicaoConcluida`
  continuam verdes sem `EmPortugues`. São páginas estáticas, sem texto preguiçoso, e o mutante
  é equivalente.
- **Tipo:** observação.

## [2026-10-01] TASK-028 · QA do passo 5 (orquestrador)

- **Aceito:** todas as demandas ao writer e ao tester da passagem do QA sobre a documentação.
  - O número 0020 da ADR par da SPA não existe no disco. Os documentos e a ADR 0031, ainda em
    "Proposto", passam a dizer "a ADR da SPA que substitui a 0012 dela, devida lá", sem número,
    até a sessão da SPA confirmar.
  - A §3 do núcleo passa a ter verificação real dos scopes (T-01 deste passo, igualdade de
    conjunto).
  - Os comentários antigos de `tests/runner.py` e de `accounts/paginas.py` são corrigidos.
  - As siglas vêm por extenso no primeiro uso.
  - Ficam corrigidas as imprecisões de `testes.md`, da origem do `resource_metadata`, das
    páginas anônimas e do estado intermediário da migração.
- **Constatado pelo QA:** o SQL de colisão, a volta da migração (a 0006 e a 0005 desfeitas e
  depois reaplicadas por `migrate`), `up -d` contra `restart`, e `/o/userinfo/` aceitando o
  token em query e no corpo.
- **Tipo:** decisão.

## [2026-10-01] TASK-028 · Disposições do gate adversarial final

- **Decisões (usuário):**
  1. **Axes.** No login bem-sucedido, o axes passa a zerar só as falhas da própria conta, por um
     handler próprio. O contador da origem fica, para que o login numa conta criada no cadastro
     público não apague as falhas contra a vítima. A 0031 emenda a premissa da 0016.
  2. **Volume de e-mail.** `/accounts/password_change/`, `/accounts/email/` e `/accounts/excluir/`
     ganham teto por origem. Os avisos de segurança ganham um teto próprio por destinatário, alto
     (ordem de 20 por hora). Assim o volume fica limitado, e suprimir um aviso exige uma rajada
     que já alerta a dona.
  3. **Recuperação.** Conta `is_staff` ou `is_superuser` não recebe link de recuperação, e a
     resposta continua idêntica. A equipe troca a senha por `changepassword`.
  4. **Boot de produção.** Com `DEBUG` falso, o boot falha se `SPA_URL` for loopback ou se
     `EMAIL_BACKEND` for o de console, nomeando a variável. A receita confere `SPA_URL`. Isso
     desfaz, para `SPA_URL`, a isenção de loopback aceita na TASK-026.
- **Pendente de desenho:** o architect desenha 1, 2 e 4 (handler do axes, teto dos avisos, guarda
  no boot) e o texto das emendas na 0031.
- **Para o desenho:** a troca de versão dos termos não tem ordem entre IdP e SPA. O architect
  propõe tratamento ou registro.
- **Correção junto:** a docstring de `RecursoDaConta` diz que o `resource_metadata` aponta para o
  issuer, e ele aponta para o host do pedido.
- **Tipo:** decisão.
- **Disposições sobre o desenho (usuário, 2026-10-01):**
  - o sinal de produção da guarda de boot é o host de `BASE_URL` fora de loopback e de
    `.localhost`, e não `DEBUG`, porque a ADR 0008 deixa `DEBUG` falso em todo ambiente;
  - aceitas: a página de redefinição recusa o link de conta da equipe, e a guarda recusa os
    quatro backends de e-mail que não entregam;
  - rejeitada: recusar no boot o marcador de `SPA_CLIENT_ID`;
  - o desenho consolidado está no scratchpad, em `architect-TASK-028-gate-final.md`.
- **Dívidas registradas (architect):**
  - a troca de versão dos termos fica sem código: a primeira troca exige uma janela em que o IdP
    aceite as duas versões, decidida nos dois projetos;
  - a cota diária do SMTP continua alcançável pelo cadastro com endereços distintos, e a saída é
    um desafio no cadastro ou um serviço transacional;
  - o pedido de recuperação de conta da equipe não deixa linha na trilha;
  - o `axes` passa a ser a terceira dependência de método interno de terceiro, depois de
    `_password` do Django e do `dispatch` do toolkit;
  - a linha da TASK-026 sobre a isenção de loopback de `SPA_URL` passa a ser desfeita, com
    `BASE_URL` público, pela ADR 0031.

## [2026-10-01] TASK-028 · Fechamento

- **Estado:** passos 0 a 5 do documento de trabalho implementados e o gate final corrigido. Suíte
  com 436 testes, verde. Nada commitado, por pedido da pessoa usuária. A ADR 0031 fica em
  "Proposto" até a ADR par da SPA existir.
- **Gate final:** QA com RESSALVA. O único CRITICO (o aviso "conta apagada" sem teste que fixasse
  `aviso=True`) virou T-77, que fica vermelho sob a mutação. As três demandas ao writer
  (`docs/testes.md`, comentário de `TERMOS_VERSAO_VIGENTE`, `seguranca.md` §6.2) foram feitas, e
  os testes T-76 e T-77 ganharam rótulo no docstring.
- **Rejeitado (QA):** teste do POST da redefinição por conta da equipe. O Django chama `get_user`
  no `dispatch` de todo método, e T-73 já prova a checagem no momento do uso.
- **Registrado (QA):** a guarda compara o host de `SPA_URL` só com `_HOSTS_DE_LOOPBACK`, então
  `https://spa.localhost` passa com `BASE_URL` público. Está dentro do contrato; estender é
  decisão futura do architect.
- **Adiado para a pessoa usuária:**
  - confirmar na sessão da SPA o número da ADR par antes de aceitar a 0031 (CRITICO do architect);
  - trocar o `SPA_CLIENT_ID` provisório do `.env` pelo real; sem isso a API responde 403
    `aplicacao_nao_autorizada` a toda chamada;
  - termos v1, SMTP real e as dívidas já listadas no gate adversarial final;
  - avaliar o `COMPOSE_PROJECT_NAME=nova_api_prod` do `.env` de desenvolvimento e a permissão 664
    do `.env`;
  - `../pre-deploy.md`, citado no `CLAUDE.md`, não existe no disco.
- **Aceito (pessoa usuária):** o writer expandiu siglas no documento de trabalho
  `docs/pre-implementacao-autoatendimento.md` sem pedido. Fica como está; nada depende dele.
- **Tipo:** decisão.
