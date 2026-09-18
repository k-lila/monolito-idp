# 0023. Não oferecer cadastro nem edição de perfil nesta fase e manter a criação de contas no admin

## Status

Aceito — 2026-09-17

## Contexto

A `nova_api_SPA`, relying party (RP) deste provedor de identidade (IdP, de _Identity
Provider_), nasceu assumindo que ele teria páginas de cadastro e de edição de perfil, alcançadas
por link a partir dela, com a base em `VITE_IDP_ACCOUNT_URL`. No IdP, essas páginas não existem:
`accounts/` tem modelo, validador de claims, auditoria e admin (`accounts/models.py`,
`oauth_validators.py`, `auditoria.py`, `admin.py`) e nenhuma view; `config/urls.py` publica
`/accounts/login/`, `/accounts/logout/`, `/health`, `/`, `/admin/` e o `include` do
`django-oauth-toolkit` (DOT) sob `/o/` — nada de registro nem de perfil. Contas são criadas por
quem opera, em `/admin/accounts/user/add/`; a conta administrativa, por `createsuperuser` (ADR
— Architecture Decision Record — 0019).

Cadastro público num IdP tem pré-condições que este projeto ainda não cumpre, todas conferidas
contra o código: `AUTH_PASSWORD_VALIDATORS` não está declarada em `config/settings.py`, e o
default do Django é lista vazia (`docs/seguranca.md` §4) — o teto de cinco tentativas do `axes`
supõe senha forte; não há teto de requisição num caminho de cadastro, porque não há caminho
(`RATE_LIMIT_POR_CAMINHO` nomeia três); não há verificação de e-mail, e por isso o `id_token`
não emite `email_verified` (`accounts/oauth_validators.py`; `docs/integracao-rp.md` §6). Um
formulário aberto sem as três coisas cria contas com senha fraca, sem limite e com e-mail que
ninguém confirmou — e a RP passaria a receber a claim `email` de contas assim.

`docs/contrato-backend.md` §5.4 fixou a saída; esta ADR a registra.

## Decisão

Vamos manter o IdP sem páginas de cadastro e de edição de perfil nesta fase. A criação de contas
continua administrativa, pelo admin, e a SPA (Single-Page Application, aplicação de página
única) deixa de exigir as páginas.

Cadastro público, se vier, é funcionalidade nova com ADR própria, que nomeará, na ordem, as
pré-condições cumpridas antes de abrir o formulário: validadores de senha declarados
(`AUTH_PASSWORD_VALIDATORS`); teto de requisição no caminho de cadastro
(`RATE_LIMIT_POR_CAMINHO`); verificação de e-mail; e só depois disso a claim `email_verified`,
que hoje não é emitida e não será enquanto o IdP não puder sustentá-la. A ordem importa: a claim
é a última porque é a única promessa feita à RP.

Edição de perfil (nome, e-mail, senha) segue o mesmo caminho: pelo admin, por quem opera,
enquanto não houver decisão em contrário.

Contraparte: a ADR 0012 da `nova_api_SPA`
(`../../../nova_api_SPA/docs/adr/0012-retirar-as-paginas-de-conta-do-escopo-e-remover-vite-idp-account-url.md`)
retira `VITE_IDP_ACCOUNT_URL` e as páginas de conta do escopo dela. Nenhuma mudança de código,
`Application` ou claim no IdP decorre daqui.

## Consequências

Positivas:

- O contrato entre os dois projetos fecha sem uma superfície que não existe: a SPA não tem link
  para 404 nem variável com valor fictício.
- O IdP não ganha formulário público antes de ter política de senha e teto; `docs/seguranca.md`
  continua verdadeiro, e o passo 5 de `docs/plano-contrato-backend.md` declara
  `AUTH_PASSWORD_VALIDATORS` sem um cadastro já dependendo disso.
- `email_verified` continua ausente por decisão, não por esquecimento; a RP sabe que não pode
  presumir que o e-mail pertence a quem se autenticou (`docs/integracao-rp.md` §6).

Negativas:

- Toda conta nova é trabalho de quem opera: sem cadastro, o IdP não cresce em pessoas sem alguém
  no admin. Para o escopo — uma SPA, uma instância, poucas contas — cabe; deixa de caber no
  primeiro uso com público.
- A pessoa não troca a própria senha nem o próprio e-mail: `/accounts/password_reset/` é 404
  deliberado (`config/urls.py`), e sem página de perfil não há outra porta. Tudo passa por quem
  opera.
- A SPA fica com uma landing de um botão só (ADR 0012 dela); a funcionalidade que veio da
  conversa de UX foi retirada, e nada fica preparado para ela.
- Quando o cadastro vier, será ADR cruzada nos dois projetos, com configuração e interface
  reintroduzidas na SPA: o custo de retirar agora é pagar a reintrodução depois.

## Alternativas consideradas

- **Cadastro público agora, com formulário mínimo** — fecharia a suposição original da SPA.
  Descartada: exigiria as três pré-condições antes, e nenhuma está pronta; abrir o formulário
  antes delas expõe o IdP fora de `localhost` com senha fraca e conta sem e-mail confirmado.
- **Página de perfil só, sem cadastro** — a pessoa alteraria nome e e-mail. Descartada: e-mail é
  o identificador de login (ADR 0003) e a claim `email` do token; mudá-lo sem verificação é a
  mesma lacuna do cadastro, e nome sozinho não justifica uma superfície autenticada nova.
- **Manter o link da SPA apontando para `/admin/`** — o admin exige `is_staff`; para a pessoa
  comum é 403. Descartada nos dois projetos.
