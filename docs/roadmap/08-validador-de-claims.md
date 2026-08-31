# Passo 08 — Validador de claims

## Objetivo

Definir o que o IdP afirma sobre a pessoa: mapear o `User` para as claims OIDC do
`id_token` e do `/userinfo`.

## Depende de

- Passo 05, porque o validador lê campos do `accounts.User` — incluindo o
  `get_full_name()` herdado de `AbstractUser`.
- Passo 07, pelo bloco `OAUTH2_PROVIDER` e pelas tabelas do DOT migradas. O passo 07
  deixou de propósito o `OAUTH2_VALIDATOR_CLASS` de fora: a chave entra **aqui**, junto com
  o arquivo que ela referencia, para que nunca exista um boot com a string apontando para
  módulo inexistente.

Vem depois do User e antes de conferir o conteúdo de qualquer token: sem ele não há o que
conferir.

## Arquivos criados

- `accounts/oauth_validators.py` — `IdPOAuth2Validator`, subclasse de `OAuth2Validator`.

## Arquivos modificados

- `config/settings.py` — acrescenta ao bloco `OAUTH2_PROVIDER`:
  `"OAUTH2_VALIDATOR_CLASS": "accounts.oauth_validators.IdPOAuth2Validator"`. **Esta é a
  única linha de settings do passo, e ela entra depois de o arquivo do validador existir.**

## O que fazer

### `IdPOAuth2Validator`

Subclasse de `OAuth2Validator` com duas coisas:

**`oidc_claim_scope`** — o mapa de qual claim é liberada por qual scope, tomando o mapa da
classe base e acrescentando:

```
name  -> profile
email -> email
```

O mapa tem de ser coerente com os `SCOPES` declarados no passo 07 (`openid`, `profile`,
`email`): claim mapeada para um scope que a Application não concede simplesmente não
aparece, sem erro.

**`get_additional_claims`** — devolvendo, a partir do `User`:

```
name  -> user.get_full_name()
email -> user.email
```

`name` vem de `get_full_name()`, o método que `AbstractUser` já traz, e não de um campo
novo: um segundo lugar guardando o nome da pessoa seria um segundo lugar para ele
divergir.

**Consequência a esperar:** com `first_name` e `last_name` vazios — que é como o usuário
do passo 06 nasce —, `get_full_name()` devolve string vazia e a claim `name` chega vazia à
relying party. Não é defeito do validador; preencher os campos pelo admin mostra a claim
preenchida no fluxo seguinte.

Sem este passo, o `id_token` carrega apenas `sub` e o `/userinfo` é inútil para a relying
party.

O validador mora em `accounts` porque é o app dono da identidade: quem define o que um
token afirma sobre a pessoa é quem possui a pessoa. Não há app "core" nem "oidc" para
abrigá-lo — seria gaveta vazia.

Este é o **único** ponto onde o comportamento do servidor de autorização é customizado
(ADR 0002), e é um contrato por string, resolvido em runtime.

## Proibições que incidem aqui

- **Não emitir `email_verified`.** Não existe fluxo de verificação nesta fase; a claim
  seria sempre falsa, e uma claim mentirosa é pior que uma claim ausente.
- **Não usar o validador para reescrever lógica de protocolo.** Ele decide claims, não
  fluxo. Qualquer coisa além do mapeamento de claims é override de comportamento do DOT
  por outro nome.
- **Não criar app ou camada de serviço para hospedar o validador.** Dois pacotes bastam
  para este chão.

## Riscos e sinais

- **Validador não configurado ou classe não encontrada** — sinal: `ImproperlyConfigured`
  no boot, se o caminho estiver errado; **nenhum sinal**, se a settings simplesmente não
  tiver a chave: o fluxo fecha e o `id_token` chega só com `sub`.
- **`oidc_claim_scope` incoerente com `SCOPES`** — sinal: a claim some do `id_token` sem
  erro, porque o scope que a autoriza não foi concedido.
- **Claim `name` vazia** — sinal: `name` presente e vazio no `id_token`. É `first_name` e
  `last_name` em branco, não falha do mapeamento. Diagnóstico: preencher os dois no admin e
  refazer o fluxo.

## Passo concluído quando

Um fluxo Authorization Code + PKCE fechado à mão com scope `openid profile email` devolve
um `id_token` cujo payload contém `sub`, `name` e `email`, e `/o/userinfo/` devolve as
mesmas claims para o `access_token` correspondente. Com `first_name`/`last_name`
preenchidos no admin, `name` chega preenchida; vazios, chega vazia — as duas leituras
confirmam o passo.

Duas notas sobre executar isso **agora**, antes do passo 09:

- **A sessão autenticada vem do `/admin/login/`.** A tela de login do produto e a
  `LOGIN_URL` só existem no passo 09; até lá, autenticar no admin com o superusuário do
  passo 06 dá a sessão que `/o/authorize/` exige.
- **A tela de consentimento é a do próprio DOT.** O override de
  `oauth2_provider/authorize.html` chega no passo 09; o template que a biblioteca traz
  fecha o fluxo sem estilo, e isso basta para conferir claim.
