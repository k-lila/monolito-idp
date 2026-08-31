# Passo 07 — Servidor OAuth2/OIDC

## Objetivo

Habilitar o django-oauth-toolkit como authorization server sob o prefixo `/o/`, com OIDC
ligado, PKCE exigido e discovery e JWKS respondendo.

## Depende de

- Passo 06, e esta dependência é dura: as tabelas do DOT resolvem
  `settings.AUTH_USER_MODEL` na própria migração. Só agora elas podem apontar FK ao User
  certo.
- Passo 03, pela `OIDC_RSA_PRIVATE_KEY` no `.env`. Sem ela o servidor sobe e o JWKS
  responde vazio.
- Passo 04, pelas settings e por `BASE_URL`, de onde o issuer é derivado.

## Arquivos modificados

- `config/settings.py` — `oauth2_provider` em `INSTALLED_APPS` e o bloco
  `OAUTH2_PROVIDER`.
- `config/urls.py` — include de `oauth2_provider.urls` sob o prefixo `/o/`.

## O que fazer

### `INSTALLED_APPS`

Acrescentar `oauth2_provider`.

### Bloco `OAUTH2_PROVIDER`

Configurado explicitamente — nada por default:

- `OIDC_ENABLED = True`
- `PKCE_REQUIRED = True`
- `SCOPES` com `openid`, `profile` e `email`
- `OIDC_RSA_PRIVATE_KEY` — a chave lida do ambiente com
  `env.str("OIDC_RSA_PRIVATE_KEY", multiline=True)`
- `OIDC_ISS_ENDPOINT` — derivado de `BASE_URL` e **coerente com o prefixo `/o/`**, isto é,
  `{BASE_URL}/o`

**`OAUTH2_VALIDATOR_CLASS` não entra neste passo.** Ela aponta por string para uma classe
que só existe no passo 08, e settings apontando para módulo inexistente derruba o boot. O
DOT usa o validador padrão até lá — o fluxo fecha, o `id_token` sai só com `sub`, e é
exatamente isso que o passo 08 corrige. A linha entra junto com o arquivo que ela
referencia.

### Rotas

Include de `oauth2_provider.urls` sob `/o/`, como vem. Nenhuma rota do DOT é reescrita à
mão.

### Migração das tabelas do DOT

`python manage.py migrate` — agora aplica as migrations do `oauth2_provider`, cujas FKs
resolvem para `accounts.User`.

### Registro do primeiro client

Pelo admin:

- `client_type = public`
- `authorization_grant_type = authorization-code`
- `algorithm = RS256` — o alçapão clássico do DOT; ver riscos
- `redirect_uri = http://localhost:8000/noop`

O `redirect_uri` é **uma URL que não precisa existir**. Fechando o fluxo à mão, o
navegador é redirecionado para lá com o `code` na query string, e o `code` é lido da barra
de endereços — um 404 na tela é o resultado esperado, não um erro. O que importa é que a
string registrada aqui seja idêntica à enviada em `/o/authorize/`: a comparação é por
igualdade exata, e essa allowlist é a fronteira de segurança real do redirecionamento.

`http://localhost:8000` é o `BASE_URL` da jornada de construção; quem rodar pelo container
(passo 11) usa a mesma porta. A receita completa fica no README (passo 12).

## Proibições que incidem aqui

- **Não reescrever, envelopar ou duplicar view, rota ou lógica de protocolo do DOT.** Cada
  endpoint de protocolo é uma superfície onde um erro sutil vira vulnerabilidade real:
  `redirect_uri` comparado por prefixo em vez de igualdade exata, code sem uso único,
  `state` não verificado. São erros que não aparecem em teste funcional — o fluxo continua
  fechando. A única customização permitida no comportamento do servidor é o
  `OAUTH2_VALIDATOR_CLASS`. Override de **template** (passo 09) é permitido e esperado, e
  não é a mesma coisa.
- **Não tornar PKCE opcional nem aceitar client público sem PKCE**, nem mesmo
  temporariamente para destravar um teste. Configuração frouxa temporária vira permanente.
- **Não implementar `end_session_endpoint`** (RP-initiated logout) nesta fase.
- **Não montar as urls do DOT na raiz do host.** Publicaria as views de gestão de
  applications e de tokens no espaço de nomes do produto (ADR 0007).

## Riscos e sinais

- **`OIDC_RSA_PRIVATE_KEY` ausente ou mal escapada** — sinal:
  `/o/.well-known/jwks.json` responde `{"keys": []}` e a discovery omite os endpoints de
  token. A aplicação sobe normalmente; nada no log acusa.
- **Application registrada sem `algorithm = RS256`** — sinal: o fluxo Authorization Code
  **completa**, o `access_token` chega, e **não há `id_token`** na resposta de `/token`. É
  o alçapão mais comum do DOT e não gera erro nenhum.
- **Issuer inconsistente entre discovery e `id_token`** — sinal: a relying party rejeita o
  token com erro de issuer mismatch. Ocorre quando `OIDC_ISS_ENDPOINT` não acompanha o
  prefixo `/o/`, ou quando o host visto atrás de proxy difere de `BASE_URL`.
- **`OAUTH2_VALIDATOR_CLASS` configurada antes do passo 08** — sinal: o boot falha ao
  importar a classe. Falha ruidosa, ao contrário das duas primeiras, e evitada por a linha
  só entrar no 08.
- **`redirect_uri` divergente entre o registro e o pedido** — sinal: o DOT recusa a
  autorização por `redirect_uri` inválida, antes mesmo da tela de consentimento. Ruidoso,
  e é o comportamento correto: a comparação é por igualdade exata.

## Fronteira de decisão — irreversibilidade por exposição externa

**Isto não é sequência de implementação.** A string do issuer, `{BASE_URL}/o`, entra na
claim `iss` de todo `id_token` emitido e fica cacheada na configuração de cada relying
party integrada. Mudá-la depois não é alteração de código: é reconfiguração simultânea de
todas as RPs e invalidação do `iss` de todo token vivo.

Ela deve ser confirmada com o usuário **antes da primeira relying party integrar**; depois
disso é permanente para efeitos práticos (ADR 0007).

Consequência já conhecida e aceita: com issuer sob um path, a OIDC Discovery 1.0 e a RFC
8414 deixam de coincidir. Uma RP que implemente estritamente a RFC 8414 procurará em
`{BASE_URL}/.well-known/oauth-authorization-server/o` e receberá 404. Não prometemos essa
forma de descoberta; documentamos a URL correta no README.

## Passo concluído quando

- `{BASE_URL}/o/.well-known/openid-configuration` responde com `issuer` igual a
  `{BASE_URL}/o` e lista os endpoints de authorize, token, userinfo e jwks;
- `{BASE_URL}/o/.well-known/jwks.json` responde com **uma chave**, não com
  `{"keys": []}`;
- as tabelas do `oauth2_provider` existem e suas FKs apontam para o modelo de `accounts`;
- há uma Application registrada com `algorithm = RS256` e
  `redirect_uri = http://localhost:8000/noop`.
