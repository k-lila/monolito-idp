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

---

## Entradas sem ADR

## [2026-09-02] TASK-010 · Bloco G: as onze ADRs gravadas, e a conferência que nunca foi gate

O bloco entrou como "transcrição literal em lote" e saiu com **treze alterações em sete das onze
ADRs**. O que mudou não foi o critério — foi o que se descobriu ao aplicá-lo.

**Onze, não sete.** `docs/implementacao.md` descrevia o gate como "os sete arquivos". As 0008 e
0009 (bloco E) e as 0010 e 0011 (bloco F) tinham sido adiadas para cá, e viviam só neste arquivo.
Os dois gates foram corrigidos, e agora registram a origem de cada faixa e as sete ADRs emendadas.

**A conferência foi feita, e o método dela era o defeito.** Desde a TASK-003 estava registrado que
conferir os achados de cada bloco contra as ADRs "não é gate de bloco nenhum", com instrução de
repassar a cada bloco. Cinco conferências foram feitas e o tally chegou a 3,5/7. Feita a sexta,
subiu para 5,5 e depois para **6,5 no mínimo** — só a 0007 atravessou seis blocos sem ser
falsificada. A razão: cada conferência perguntou *"o que este bloco contradiz?"*, nunca *"estas
ADRs são verdadeiras?"*. Achou-se o que os blocos esbarraram. **As 0004 e 0005 estavam erradas
desde 2026-08-29 e nunca foram esbarradas por bloco nenhum.**

**As duas que ninguém tinha visto**, ambas verificadas por mim no código antes de aceitar:

- **ADR 0004 — diagnóstico invertido**, a mesma classe que este projeto já pagou três vezes. Ela
  dizia "variável ausente → o sistema sobe e o JWKS responde vazio: falha silenciosa".
  `config/settings.py` lê `OIDC_RSA_PRIVATE_KEY` **sem default** e o docstring do módulo declara o
  contrato oposto. Ausente é `ImproperlyConfigured` no import — crash-loop ruidoso. A falha
  silenciosa é a da variável **presente e vazia**.
- **ADR 0005 — "os tokens são stateless e assinados" é falso.** `ACCESS_TOKEN_GENERATOR` é `None`
  no DOT 3.4.1 e o projeto não sobrescreve: o `access_token` é string opaca de 30 caracteres
  gravada em tabela, e só o `id_token` é JWT. A ADR 0002, **gravada no mesmo lote e no mesmo dia**,
  dizia o contrário em duas linhas. Consequência que a correção passou a registrar: a RP recebe um
  token opaco, o `introspection_endpoint` anunciado responde 403, e sobra `/o/userinfo/` — uma
  chamada ao IdP por request, o custo que a ADR 0004 diz que a assinatura existe para evitar.

**Divergência arbitrada pelo usuário.** Sobre a Positiva da ADR 0006 houve três posições: o
`architect` decidiu não mexer (uma Negativa que qualifica um ganho é a forma normal de registrar
um limite), o `quality-assurance` chamou de contradição interna, o `senso-critico` quis remover a
Negativa inserida. O usuário decidiu com o QA, e a razão vale registro: a primeira oração afirmava
identidade entre o caminho do compose e o caminho endurecido, e essa oração é falsa
independentemente de a Negativa existir — remover a Negativa não a consertaria.

**Duas cópias divergentes, fechadas.** Emendar uma ADR de 0001–0007 criava duas versões no disco:
a de `docs/adr/` e a da cerca em `13-adrs.md`, que é a que se lê por ordem de documento. As quatro
emendadas (0002, 0004, 0005, 0006) foram sincronizadas e **os sete pares batem byte a byte**,
verificado por SHA-256. Essa igualdade **não tem guarda automática**: a próxima emenda em qualquer
delas reabre a divergência em silêncio.

**O registro de que houve emenda é o commit**, deliberadamente. As datas de `## Status` continuam
sendo as da decisão, e a 0006 (2026-08-29) cita a 0010 (2026-09-01) — anacronismo apontado pelo
`senso-critico`. Rejeitado acrescentar rodapé de emenda a onze arquivos: o commit é durável,
greppável e sobrevive à poda deste arquivo, que é justamente o que ele apontou como frágil.

**Poda executada**: 526 linhas. Os textos integrais de 0008–0011 e os dois avisos NÃO PODAR
cumpriram o propósito e saíram; `docs/adr/` é a fonte. Índice do topo preenchido com as onze.

- **ADR:** as onze, de [0001](../../docs/adr/0001-adotar-django-5-2-lts-sobre-python-3-14.md) a
  [0011](../../docs/adr/0011-dar-teto-de-tempo-ao-health-e-derivar-o-healthcheck-dele.md). Ver o
  índice no topo.
- **Tipo:** decisão.

---

## [2026-09-02] TASK-010 · ADIADO — `BEHIND_TLS_PROXY` não entrega o IP do cliente, e a próxima fase é rate limiting

O achado mais caro do bloco, e ele **não é do bloco**: é da próxima fase. Registrado aqui porque o
sinal não existe até ser tarde.

`config/settings.py` liga `SECURE_PROXY_SSL_HEADER` e nada mais sobre proxy — não há
`USE_X_FORWARDED_HOST` nem resolução de `X-Forwarded-For`. Com TLS real na frente, **todo request
externo chega com `REMOTE_ADDR` igual ao IP do proxy**. A próxima fase entra por biblioteca de rate
limiting, e `django-axes` e `django-ratelimit` keiam por `REMOTE_ADDR` no default: o primeiro
atacante que estourar o limite **tranca a tela de login para a internet inteira**.

Passa em 100% dos testes deste sandbox, onde não há proxy. É a forma exata do bug que o bloco F
encontrou no `SECURE_SSL_REDIRECT`, e pela mesma razão: **o nome da variável promete "atrás de um
proxy" e configura só o esquema.** A emenda da ADR 0006 registrou uma condição não coberta
(`ALLOWED_HOSTS`); corrigiu a instância, não a classe. Nenhuma das onze diz que `BEHIND_TLS_PROXY`
cobre transporte e não identidade de cliente.

**Horizonte:** a fase de rate limiting, com sinal só no primeiro ambiente com proxy real.

- **Tech-debt / melhorias:** **adiado**, com disposição registrada. Quem abrir a fase de rate
  limiting resolve isto **antes** de escolher a chave de contagem.
- **Tipo:** observação.

---

**Regra ao acrescentar:** se a decisão tem ADR, escreva **uma linha** no índice e o resto
no ADR. Se não tem, escreva a entrada completa aqui. Um log que cresce sem poda não é
memória — é sedimento.

---

## [2026-09-04] TASK-011 · Fechamento: disposição dos três apontamentos de conteúdo

- **Decisão:** os três apontamentos que seguravam o fechamento receberam disposição do usuário
  em 2026-09-04, com a instrução de tratá-los antes de qualquer trabalho novo.
  - **[OBSERVACAO] docstring de `test_template_comment_leak.py` — ACEITO e corrigido.** A
    docstring descrevia no presente seis comentários `{# ... #}` multi-linha; `grep -rn '{#'
    templates/` não acha nenhum hoje, nem multi-linha nem de uma linha. O defeito era maior do
    que o registro dizia: as **três docstrings de classe** repetiam o mesmo pressuposto, cada
    uma nomeando o comentário específico que aquele caso pegaria. As quatro foram reescritas —
    o inventário da TASK-008 passou ao pretérito, o estado de hoje entrou explícito, e a
    justificativa de cada caso passou a ser a posição de renderização que ele cobre, não o
    comentário que morava lá. Suíte verde em 35 testes antes e depois.
  - **[OBSERVACAO] treze arquivos citando rótulos irrecuperáveis — ACEITO EM PARTE.**
    `TASK-NNN`, `T-NN` e `AC-NN` **não** são irrecuperáveis: `docs/testes.md`, seção "A
    convenção de rastreabilidade", decodifica as duas formas em uso e declara que são rótulos
    de contrato, que não se renumeram nem se reescrevem. Nada a fazer nos treze arquivos por
    esse motivo. Irrecuperáveis eram só as **três remissões a "prompt de invocação"** —
    `oauth_helpers.py`, `test_authorize_guards.py` e `test_authorization_code_flow.py` —, que
    mandavam o leitor consultar uma conversa que não existe. Em todas as três a afirmação já
    estava completa na própria frase; caiu só a atribuição.
  - **[OBSERVACAO] duas grafias para "passo NN" — ACEITO, resolvido por decodificação.** O
    referente sumiu: `docs/roadmap/` foi removido no commit `b7774d5`. Reescrever as sete
    ocorrências em código seria mexer em conteúdo para apagar um rótulo que as ADRs 0008 e
    0010 — imutáveis — continuam usando. Em vez disso, `docs/arquitetura.md` ganhou um
    parágrafo que decodifica o rótulo, nomeia os arquivos que o usam e mostra como ler o
    original no histórico (`git show b7774d5^:docs/roadmap/09-telas-e-estaticos.md`).
- **Arquivos tocados no fechamento:** `accounts/tests/test_template_comment_leak.py`,
  `accounts/tests/oauth_helpers.py`, `accounts/tests/test_authorize_guards.py`,
  `accounts/tests/test_authorization_code_flow.py`, `docs/arquitetura.md`.
- **Tipo:** decisão.
