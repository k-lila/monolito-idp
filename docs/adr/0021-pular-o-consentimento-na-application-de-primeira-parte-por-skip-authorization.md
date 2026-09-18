# 0021. Pular o consentimento na `Application` de primeira parte por `skip_authorization`

## Status

Aceito — 2026-09-17

## Contexto

O `django-oauth-toolkit` (DOT) 3.4.1 decide se mostra a tela de consentimento em
`/o/authorize/` por `REQUEST_APPROVAL_PROMPT`, cujo default é `"force"`
(`oauth2_provider/settings.py:82`): tela em toda autorização, mesmo quando a pessoa já aprovou
os mesmos scopes para o mesmo cliente. `config/settings.py` não sobrescreve a chave. A view lê
o valor por requisição, `request.GET.get("approval_prompt", oauth2_settings.REQUEST_APPROVAL_PROMPT)`
(`oauth2_provider/views/base.py:257`), e antes de consultá-lo testa o campo `skip_authorization`
da `Application` (`views/base.py:268-272`): com o campo marcado, o código é emitido sem tela,
inclusive na primeira autorização. O campo é booleano por cliente, default `False`
(`oauth2_provider/models.py:234`), editável no admin.

A primeira relying party (RP) deste provedor de identidade (IdP, de _Identity Provider_) é a
`nova_api_SPA`, aplicação de página única (SPA, de _Single-Page Application_) do mesmo sistema.
Ela guarda tokens só em memória e, por decisão própria, volta a `/o/authorize/` em toda recarga
da página, contando com a sessão do IdP (cookie) para voltar sem senha. Com o default do DOT,
cada F5 passaria pela tela de consentimento — uma pergunta cuja resposta já se conhece, repetida
até que se clique sem ler.

`docs/contrato-backend.md` §5.3 fixou a saída; esta ADR (Architecture Decision Record) a
registra.

## Decisão

Vamos marcar `skip_authorization=True` na `Application` da `nova_api_SPA`, na de desenvolvimento
e na de produção, pelo admin, ao registrá-las (`contrato-backend.md` §5.1). A SPA é aplicação de
primeira parte: o consentimento entre duas metades do mesmo sistema não informa nada à pessoa.

O default global fica intocado: `REQUEST_APPROVAL_PROMPT` continua `"force"`, sem declaração em
`config/settings.py`. A decisão é por cliente, no campo que o DOT oferece para isso, nunca por
configuração da instância.

Disciplina que acompanha a decisão: `skip_authorization` **nunca** é marcado em `Application` de
terceiro. Uma RP que não seja deste sistema passa pela tela em toda autorização, e é assim que se
quer.

Contraparte: a ADR 0014 da `nova_api_SPA`
(`../../../nova_api_SPA/docs/adr/0014-manter-a-sessao-no-reload-por-redirect-e-sso-do-idp-sem-token-fora-da-memoria.md`)
fecha "sessão no reload" contando com esta marcação, e diz que, enquanto ela faltar, a recarga
passa pela tela — um passo a mais no mesmo redirect, sem mudança de código lá. A mesma ADR
endereça a esta duas notas cruzadas: declarar e testar as três settings do cookie de sessão
(`SESSION_COOKIE_SAMESITE`, `SESSION_COOKIE_AGE`, `SESSION_EXPIRE_AT_BROWSER_CLOSE`) e dar a
`REFRESH_TOKEN_EXPIRE_SECONDS` um valor finito. Nenhuma das duas se decide aqui, porque cada
uma é decisão própria: a primeira toca o mecanismo de SSO (Single Sign-On) da ADR 0005; a
segunda muda o que `docs/integracao-rp.md` §8 promete a toda RP, e `docs/robustez-info.md` §2.8
já a reservou para ADR. As duas ficam registradas nas consequências como pendências desta. O que
o contrato já fixa (§5.4) e esta ADR reafirma: `SESSION_COOKIE_SAMESITE` não muda para `Strict`.
O pulo do consentimento só vale alguma coisa se o cookie de sessão viajar na navegação top-level
cross-site; com `Strict`, a pessoa digitaria a senha a cada recarga, sem erro em lugar nenhum.

## Consequências

Positivas:

- A recarga da SPA volta autenticada sem tela nenhuma: `/o/authorize/` vira um redirect que a
  pessoa não vê. É o que fecha o §7.2 do plano da SPA.
- A decisão vive no dado da `Application`, ao lado de `client_type`, `algorithm` e
  `redirect_uris`: quem registra o cliente decide, e a instância não muda de comportamento para
  os demais clientes.
- A verificação é binária e dispensa a SPA: o fluxo PKCE (Proof Key for Code Exchange) à mão de
  `docs/receita.md`, contra a `Application` da SPA, não mostra a tela na segunda autorização
  (`contrato-backend.md` §7, item 4).

Negativas:

- A disciplina "nunca em terceiro" é de quem opera, não do código. O campo é uma caixa no admin,
  ao lado das demais; nada no IdP distingue primeira parte de terceiro, e marcá-lo numa
  `Application` alheia faz o IdP emitir código para aquele cliente sem que a pessoa aprove nada.
  Não há teste que acuse isso: a marcação é dado, não código.
- A `Application` da SPA passa a autorizar sem interação humana em toda ida a `/o/authorize/`
  com sessão viva. Cada F5 grava um `AccessToken`, um `RefreshToken` e um `IDToken` novos; o
  refresh não expira (`REFRESH_TOKEN_EXPIRE_SECONDS` é `None`, `docs/integracao-rp.md` §8), e as
  tabelas crescem com as recargas. A mitigação — expiração finita do refresh — é a pendência
  nomeada acima, e não está tomada.
- O pulo depende de o cookie de sessão viajar no redirect top-level cross-site, o que hoje é o
  default `Lax` do Django, não declarado nem testado. Um endurecimento para `Strict` ou uma
  mudança de política de navegador vira senha a cada recarga, em silêncio. Declarar e testar as
  três settings é a outra pendência.
- A tela de consentimento, com as descrições de `SCOPES` em português, deixa de ser exercitada
  pela única RP existente. Continua de pé para qualquer terceiro, e `tests/` cobre a
  renderização; o que fica sem exercício é o caminho de uso.

## Alternativas consideradas

- **`REQUEST_APPROVAL_PROMPT="auto"` em `config/settings.py`** — pula a tela quando existe
  `AccessToken` não expirado para aquela pessoa, aquele cliente e aqueles scopes
  (`views/base.py:274-292`). Descartada por duas razões independentes. É global: valeria para
  toda RP futura, inclusive de terceiro, invertendo o default que se quer manter. E o pulo
  depende do estado da tabela de tokens, não da natureza do cliente: a SPA perde o token a cada
  recarga, e a tela reapareceria sempre que o último token gravado tivesse expirado (10 h) ou
  sido recolhido — a mesma experiência, intermitente, sem que ninguém soubesse por quê. Vale
  registrar que o `"auto"` já está ao alcance de qualquer cliente, por requisição, pelo
  parâmetro `approval_prompt` que a view lê antes do default: o default global é default, não
  barreira.
- **Deixar a tela em todo F5** — custo zero no IdP; a SPA já tolera (ADR 0014 dela). Descartada
  porque um consentimento repetido a cada recarga é pior que nenhum: ensina a clicar sem ler, e
  o clique passa a valer nada também nas RPs de terceiro, em que ele importa.
- **Sobrescrever a view de autorização para pular só clientes de uma lista em settings** — o
  mesmo efeito com código de produção novo. Descartada: o DOT já tem o campo por cliente, e
  `docs/arquitetura.md` fixa que nenhum método de protocolo é sobrescrito; a única peça
  substituída é o template de consentimento.
