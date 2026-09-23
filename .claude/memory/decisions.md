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
| 2026-08-29 | django-oauth-toolkit como servidor de autorização OAuth2/OIDC — **emendada pela 0024** | [0002](../../docs/adr/0002-usar-django-oauth-toolkit-como-servidor-de-autorizacao.md) |
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
| 2026-09-17 | Pular o consentimento na `Application` de primeira parte por `skip_authorization`; default global intocado — contraparte: SPA 0014 | [0021](../../docs/adr/0021-pular-o-consentimento-na-application-de-primeira-parte-por-skip-authorization.md) |
| 2026-09-17 | Liberar o CORS por origem exata, uma por ambiente; previews da Vercel fora — contraparte: SPA 0016 | [0022](../../docs/adr/0022-liberar-o-cors-por-origem-exata-e-deixar-os-previews-da-vercel-fora.md) |
| 2026-09-17 | Não oferecer cadastro nem perfil nesta fase; contas criadas no admin — contraparte: SPA 0012 | [0023](../../docs/adr/0023-nao-oferecer-cadastro-nem-perfil-nesta-fase-e-manter-a-criacao-de-contas-no-admin.md) |
| 2026-09-22 | Montar sob `/o/` só as listas de protocolo do toolkit (metadata, base, oidc); emenda à 0002 | [0024](../../docs/adr/0024-montar-sob-o-so-as-listas-de-protocolo-do-django-oauth-toolkit.md) |

---

## Entradas sem ADR

**Regra ao acrescentar:** se a decisão tem ADR, escreva **uma linha** no índice e o resto
no ADR. Se não tem, escreva a entrada completa aqui. Um log que cresce sem poda não é
memória — é sedimento.

---

## [2026-09-23] TASK-019 · Passo 5 do plano do contrato: o IdP endurecido para sair de `localhost`

Rota `/feature`, aberta em 2026-09-18. Os relatórios das fases 1 e 2 se perderam com a conversa;
retomada em 2026-09-22 com o `product-manager` e o `architect` reinvocados, por escolha do
usuário. Quatro controles: `AUTH_PASSWORD_VALIDATORS` (os quatro do Django); `/o/` monta só
`metadata + base + oidc` do DOT, com o namespace preservado (ADR 0024); `ALLOWED_REDIRECT_URI_SCHEMES`
condicionada a `BEHIND_TLS_PROXY`; `CORS_URLS_REGEX = r"^/o/"`. Doze AC, T-01 a T-15.

- **ADR 0024** gravada, no índice acima; emenda à 0002 (a 0002 não foi tocada).
- **Decisão: `BEHIND_TLS_PROXY` passa a governar uma política de protocolo** (o transporte do
  `code` no canal de frente), e não só o transporte da resposta. Limite: o próximo valor que
  quiser pegar carona nela pede ADR — a variável não é chave "é produção" (ADR 0006).
- **Decisão: quarta neutralização em `tests/runner.py`** (`OAUTH2_PROVIDER_DE_PRODUCAO`, cópia
  neutra, sinal `setting_changed`), pelo precedente do `SECURE_SSL_REDIRECT`; fixtures em
  `http://` intocadas (usuário). O sinal é o canal que o `reload()` do DOT escuta; um `setattr`
  antes da primeira leitura nunca entraria em `_cached_attrs` e mascararia o override do T-04.
- **Decisão: teto de 30/min em `/o/device-authorization/`**, sem ADR (a 0016 nomeia três
  caminhos). Achado do `senso-critico`, constatado pelo orquestrador: POST anônimo com o
  `client_id` público da SPA grava uma linha de `DeviceGrant` por requisição; token não sai. O
  DOT 3.4.1 não tem setting para desligar o device flow, e a rota vem em `base_urlpatterns`.
- **Decisão: contas de teste de dev mantêm a senha fraca até o passo 8**; nenhuma conta nova com
  ela (usuário). O AC-02 garante que continuam entrando.
- **Decisão: renumeração das ADRs do passo 6 (0024/0025 → 0025/0026) adiada para a TASK-020**
  (usuário). Até lá, `docs/plano-contrato-backend.md` e `../pre-deploy.md` chamam de 0024 o
  issuer; risco de ADR duplicada para quem executar o passo 6 pelo documento.
- **Dívidas aceitas:** (1) "Ver no site" do admin de `Application` responde 500
  (`get_absolute_url` reverte `oauth2_provider:detail`, que saiu); o T-12 o fixa. (2)
  `DeviceGrant` sem limpeza: `clear_expired()` não o apaga, e o teto só limita o custo por
  origem. (3) Cada bump do pin do DOT, não só a 4.0, exige reler as cinco listas: rota nova numa
  lista montada entra sozinha, com CORS e sem teto; o guarda por valor pega endpoint que some,
  não o que aparece. (4) `ALLOWED_REDIRECT_URI_SCHEMES` é global; uma RP nativa ou em loopback
  (RFC 8252) exigiria trocar o modelo de `Application`. (5) `--parallel` com `spawn` perde as
  quatro neutralizações do runner (registrado no próprio runner).
- **Para o passo 7:** a jornada de container recusa a SPA de dev em `http://` (400
  `DisallowedRedirect`); o plano conta com ela como segunda verificação.
- **Apontamentos adiados** (prosa, para a próxima tarefa com esse escopo): `seguranca.md` §6 e
  os comentários do `MIDDLEWARE` descrevem a allowlist de CORS como vazia; `seguranca.md` usa
  "ADR" em §2 antes de expandir em §3; o título do `runbook.md` §6 não cobre o 400 no POST do
  consentimento; a convenção de rastreabilidade de `docs/testes.md` fala em docstring de módulo,
  e a prática já é de classe e caso; faltam testes de client confidencial no admin e de GET em
  `/o/device-authorization/`.
- **Rejeitados:** editar `robustez-info.md`, `gaps/observabilidade.md` e `../desavencas*.md`
  (registros datados) e as ADRs 0002, 0007 e 0023 (imutáveis); o risco "https-only só
  exercitado no passo 9", porque o Goal 5 do `../pre-deploy.md` o exercita na jornada de
  container.
- **Ambiente:** a jornada de container morreu no boot pelo `runbook.md` §17 (volume `auditlog`
  de `root`); corrigido com o `chown` documentado.
- **Pendente com o usuário:** a verificação da SPA em `/app` contra o IdP endurecido (Goal 2 do
  `../pre-deploy.md`, caixa aberta).
- **Prova:** 138 testes OK na jornada de construção, com `BEHIND_TLS_PROXY=True` no host e na
  jornada de container real (imagem reconstruída); `manage.py check` sem issues. T-14 e o caso
  de CORS da RFC 8414 provados por mutação pelo `quality-assurance`.
- **Tipo:** decisão, tech-debt e apontamento adiado.
