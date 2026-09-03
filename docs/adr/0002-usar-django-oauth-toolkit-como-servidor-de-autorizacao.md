# 0002. Usar django-oauth-toolkit como servidor de autorização OAuth2/OIDC

## Status

Aceito — 2026-08-29

## Contexto

O núcleo do produto é um authorization server OpenID Connect (OIDC): precisa suportar
Authorization Code com PKCE (Proof Key for Code Exchange), emitir e renovar tokens, revogar,
publicar documento de descoberta e JWKS (JSON Web Key Set), registrar clients com allowlist de
redirect_uri e expor /userinfo.

Cada um desses elementos é uma superfície onde um erro sutil vira vulnerabilidade real:
redirect_uri comparado por prefixo em vez de igualdade exata, code sem uso único, PKCE aceito
como opcional, state não verificado. São erros que não aparecem em teste funcional — o fluxo
continua fechando — e só aparecem quando alguém os explora.

A alternativa a adotar uma implementação existente é escrever a máquina de estados do
protocolo, o que significa assumir a manutenção permanente de conformidade com uma família de
RFCs em evolução.

## Decisão

Vamos usar django-oauth-toolkit (DOT) 3.4.1 como authorization server, instalado sem extra — o
jwcrypto, que viabiliza a assinatura de id_token e o JWKS, entra como dependência incondicional
do pacote —, com PKCE exigido e não meramente oferecido.

As rotas do DOT são incluídas como vêm: não reescrevemos, envelopamos nem duplicamos endpoint
de protocolo. A única customização permitida no comportamento do servidor é o
OAUTH2_VALIDATOR_CLASS, que define quais claims sobre o usuário o IdP (Identity Provider)
afirma. Override de template — a tela de consentimento — é permitido e esperado, e não é a
mesma coisa que override de view.

O ponto de montagem das rotas e o issuer resultante são decisão própria, registrada na ADR
(Architecture Decision Record) 0007.

## Consequências

Positivas:

- Authorization Code + PKCE, refresh, revogação, descoberta e JWKS chegam prontos e testados
  por uma comunidade grande (Jazzband), em vez de escritos aqui.
- Applications, grants e tokens são modelos do ORM (Object-Relational Mapping): registro e
  inspeção de clients saem de graça pelo admin.
- O contrato com as relying parties (RPs) é OIDC Discovery 1.0, auto-descoberto: uma RP que
  siga esse padrão integra sem documentação manual nossa.
- Correções de segurança do protocolo chegam por upgrade de dependência.

Negativas:

- A superfície de configuração é grande (grants, scopes, chaves, políticas por application) e é
  possível configurar algo inseguro sem receber nenhum aviso; a documentação pressupõe
  conhecimento de OAuth2/OIDC.
- Há duas configurações incompletas cujo sinal não está onde se procura. Sem chave RSA
  (Rivest–Shamir–Adleman), o JWKS responde vazio com HTTP 200 e o único indício é o alg
  anunciado na discovery cair de RS256 (RSA com SHA-256) + HS256 para HS256 — falha silenciosa
  de ponta a ponta. Já uma Application com o campo algorithm em branco não é silenciosa nem
  falha onde se espera: /o/authorize/ emite o code normalmente, e é o POST em /o/token/ que
  devolve HTTP 500 sem token nenhum, porque a emissão do id_token pede a chave da Application
  sempre que o escopo inclui openid, e o campo em branco levanta ImproperlyConfigured. Procurar
  um id_token ausente numa resposta bem-sucedida é depurar o endpoint errado.
- O DOT 4.0 endurecerá a postura para OAuth 2.1 e o upgrade exigirá revisão deliberada, não
  bump de versão.
- O esquema de banco dos tokens é do DOT: as tabelas crescem e a limpeza periódica
  (cleartokens) passa a ser obrigação operacional nossa.
- O DOT deixa de ser dependência e passa a ser a definição do nosso contrato público; trocá-lo
  depois de haver RPs integradas é migração de protocolo, não refatoração.
- A introspecção não chega utilizável: a view exige o scope introspection, que o bloco SCOPES
  não declara, e nenhum token pode carregá-lo. /o/introspect/ segue roteado e anunciado como
  introspection_endpoint na metadata RFC 8414, e responde 403. Coerente com esta fase, que não
  tem resource server; vira pergunta de integração quando houver um.

## Alternativas consideradas

- **Authlib** — biblioteca excelente e mais flexível, mas fornece os blocos do protocolo, não
  um servidor pronto integrado ao ORM e ao admin. Teríamos de montar modelos, endpoints,
  descoberta e JWKS à mão, assumindo a conformidade.
- **Implementação própria do protocolo** — máximo controle, mas transferiria para este projeto
  a responsabilidade permanente de acompanhar as RFCs e de acertar detalhes cuja falha é
  silenciosa e explorável. Custo desproporcional ao objetivo.
- **Delegar a um IdP externo (Auth0, Keycloak, Cognito)** — eliminaria o problema, e também o
  produto: o objetivo declarado é ser o IdP.
