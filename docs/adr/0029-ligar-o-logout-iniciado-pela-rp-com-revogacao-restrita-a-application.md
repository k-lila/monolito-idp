# 0029. Ligar o logout iniciado pela RP, com revogação restrita à Application e retorno só a destino cadastrado

## Status

Proposto — 2026-09-29

Passa a Aceito quando a ADR (Architecture Decision Record) 0019 da aplicação de página única
(SPA, de _Single-Page Application_), a contraparte, estiver gravada. O caminho dela entra na seção Decisão nesse mesmo ato. Amplia o conjunto de eventos
da ADR 0013 sem tocar no esquema de campos dela, como a 0016 já fez. O mecanismo, uma subclasse da
view do toolkit, é a ADR 0030.

## Contexto

O "Sair" da SPA só esquece os tokens na memória da página (ADR 0010 da SPA). A sessão
Django do provedor de identidade (IdP, de _Identity Provider_) continua viva, o "Entrar" seguinte
volta sem senha pelo SSO (_single sign-on_) da ADR 0005, e o `access_token` segue aceito em
`/o/userinfo/` por até dez horas.

O django-oauth-toolkit (DOT) 3.4.1 implementa o OpenID Connect (OIDC) RP-Initiated Logout 1.0 em
`/o/logout/`. Hoje a rota responde 404, porque `OIDC_RP_INITIATED_LOGOUT_ENABLED` está declarada
falsa, decisão sem ADR. Cinco chaves governam a view, e a biblioteca anuncia defaults que mudam na
4.0. Ligada como vem, a view traz quatro limitações:

- revoga os tokens da conta em todas as Applications;
- não deixa rastro da revogação;
- manda para a tela de erro quem reapresenta um hint já revogado, o que acontece, por exemplo, ao
  sair numa segunda aba;
- responde 500 a entradas forjadas: `client_id` inexistente ou com NUL; hint com carga que não é
  JSON, com `aud` de Application sem algoritmo ou com `aud` contendo NUL; e destino que não se
  decompõe como URL.

A confirmação e o erro saem de um template em inglês.

A trilha de auditoria (ADR 0013) já escuta `user_logged_out`, que a view dispara ao encerrar a
sessão. A 0013 deixou a revogação de token de fora por falta de sinal.

## Decisão

Vamos ligar o logout iniciado pela relying party (RP) em `/o/logout/`, atendido pela subclasse da
ADR 0030.

| Chave | Valor | Default 3.4.1 |
| --- | --- | --- |
| `OIDC_RP_INITIATED_LOGOUT_ENABLED` | `True` | `False` |
| `OIDC_RP_INITIATED_LOGOUT_DELETE_TOKENS` | `False` | `True` |
| `OIDC_RP_INITIATED_LOGOUT_ALWAYS_PROMPT` | `False` | `True` |
| `OIDC_RP_INITIATED_LOGOUT_ACCEPT_EXPIRED_TOKENS` | `True` | `True` |
| `OIDC_RP_INITIATED_LOGOUT_STRICT_REDIRECT_URIS` | `BEHIND_TLS_PROXY` | `False` |

**Que Application.** Com `id_token_hint` vivo, é a do `id_token`. Com `client_id`, é a dele:
`client_id` inexistente responde 400, e divergente do hint também. Com hint autêntico sem linha no
banco, é a do `aud` verificado. Sem nenhum dos três, não há Application: o pedido com destino é
recusado, e o pedido sem destino só encerra a sessão.

**O que se revoga.** Os `access_token`, `refresh_token` e `id_token` da conta dona do hint vivo
naquela Application, e só nela. Sem hint vivo, a conta é a da sessão, depois da confirmação. Sem
Application, ou sem conta, nada é revogado. A sessão do navegador no IdP termina inteira em toda
saída que não é recusada.

**Hint sem linha.** Hint com assinatura válida e issuer deste IdP, cuja linha já não existe, é
tratado como ausente. A razão da ausência pode ser uma saída anterior ou o `cleartokens`. Sem
sessão, o pedido vai ao destino e nada é revogado; com sessão, a view pergunta. Esse hint nunca
autoriza revogação. Assinatura inválida, outro issuer, forma malformada e hint assinado por chave
anterior respondem 400.

**Entradas forjadas.** Respondem 400, com a tela de erro, e nenhuma delas encerra sessão nem revoga
token:

- `client_id` inexistente ou com o caractere NUL;
- hint com carga que não é JSON, com `aud` de Application sem algoritmo, com `aud` contendo NUL ou,
  se assinado por segredo de cliente HS256, com `jti` que não é UUID;
- `post_logout_redirect_uri` que não se decompõe como URL.

A lista é fechada: entrada nova que dê 500 é defeito a registrar, e não recusa por omissão.

**Pergunta.** Não há pergunta quando o hint vivo é da conta da sessão. Há pergunta quando o hint
falta, não tem linha ou é de outra conta. É o que a especificação exige, e uma requisição forjada
sem o `id_token` da vítima não encerra nada.

**Destino.** Só o cadastrado em `post_logout_redirect_uris` da Application, por ambiente, pelo
admin: a landing da SPA com a barra final, literal ao que a SPA envia. O esquema segue a ADR 0006:
`STRICT_REDIRECT_URIS` acompanha `BEHIND_TLS_PROXY`, como `ALLOWED_REDIRECT_URI_SCHEMES`. Atrás do
proxy, `http` é recusado; na jornada de construção, a SPA de desenvolvimento volta a
`http://localhost:5173/`.

**Trilha: amplia a ADR 0013.** A subclasse define e emite o sinal `tokens_revogados`, e `event`
recebe esse nome, pela regra da 0013. O evento sai uma vez por saída que revogou ao menos um token,
depois da revogação e antes do `user_logged_out`, que continua. Campos: `sub` do dono dos tokens
revogados, `client_id`, `ip`, `ip_src`, `ip_edge` e `outcome` igual a `success`. Nenhum valor de
token entra na linha, e o esquema não muda. O receptor vive em `accounts/auditoria.py`, com a mesma
captura dos outros: falhar em auditar não impede a saída.

**Tela.** `templates/oauth2_provider/logout_confirm.html` é sobrescrito em português, no estilo do
IdP, pelo precedente de `authorize.html`. Preserva do original o ramo de erro, o CSRF (Cross-Site
Request Forgery), o laço de campos ocultos e o `name="allow"`. O erro é dito pelo código, nunca pela
descrição em inglês da biblioteca.

**Teto e o outro "Sair".** `/o/logout/` ganha teto de 120 requisições por minuto por origem, pelo
mecanismo da ADR 0016. `/accounts/logout/` não muda: só POST, encerra a sessão e não revoga.

A descoberta OIDC passa a publicar `end_session_endpoint`, igual ao issuer seguido de `/logout/`. É
mudança de contrato público. O documento da RFC 8414 não o publica.

Contraparte: a ADR 0019 da SPA, a gravar. O caminho dela, interno à SPA, entra aqui na aceitação.

## Consequências

Positivas:

- "Sair" encerra a sessão no IdP e revoga os tokens da RP que pediu: o `access_token` anterior
  recebe 401, e o "Entrar" seguinte pede senha.
- Uma segunda RP não perde os tokens quando a primeira sai.
- A trilha passa a dizer de quem e de qual RP foram revogados tokens, inclusive na saída sem sessão.
- O retorno vai só a destino cadastrado. Entrada forjada recebe 400, nunca 500; a lista está na
  seção Decisão, e o mecanismo, na ADR 0030.
- As cinco chaves declaradas tiram da 4.0 o poder de mudar o comportamento em silêncio.

Negativas:

- **O contrato público cresce, e voltar atrás é quebra.** A SPA passa a depender da chave nova a
  partir da ADR 0019 dela.
- **Confirmada com hint de outra conta, a saída revoga os tokens dessa conta na Application e
  encerra a sessão do navegador,** enquanto os tokens da conta da sessão sobrevivem. A tela não pode
  nomear a conta do hint.
- **A revogação é por conta e Application, em todos os dispositivos da conta,** e não pela sessão.
  As outras RPs mantêm os tokens, mas perdem a volta sem senha, porque a sessão de SSO termina
  inteira.
- **Sem sessão, o `id_token` vivo é credencial de revogação:** quem o tem revoga os tokens do dono
  naquela Application sem pergunta.
- **O hint sem linha, reapresentado sem sessão, redireciona ao destino cadastrado sem revogar
  nada.** Os tokens que a conta tenha naquela Application, por um login posterior, sobrevivem a
  essa saída.
- **Um refresh em curso durante a saída pode sobreviver a ela.** O toolkit valida o
  `refresh_token` fora de trava e, ao gravar o par novo, não reconfere se ele foi revogado
  (`oauth2_validators.py:997-1038`). Se a validação acontece antes da saída e a gravação depois, o
  par novo nasce vivo. Na ordem inversa, o refresh que sobra fica sem access token, e o toolkit o
  recusa. Fechar a janela exige mexer em `/o/token/`, fora desta decisão.
- **O `id_token_hint` viaja na query string.** Nenhum log deste projeto o grava hoje. Ligar log de
  acesso com a URL completa passa a gravar `id_token`. O log de erro do Caddy, o `cloudflared` e a
  borda da Cloudflare não foram medidos.
- **A troca da chave de assinatura faz os hints em circulação responderem 400.**
- **Recusar a confirmação responde 400,** o status que o toolkit dá a `LogoutDenied`.
- **O admin não valida `post_logout_redirect_uris`.** Um cadastro esquecido, em `http` ou sem a
  barra, só aparece no primeiro "Sair".
- **Há dois "Sair" com efeitos diferentes:** o do topo do IdP encerra só a sessão; o da RP encerra a
  sessão e revoga os tokens.
- **Atrás do proxy, `STRICT_REDIRECT_URIS` não tem efeito observável,** e na suíte o valor dela
  segue a jornada.
- **`DELETE_TOKENS` falsa lê como "não revoga".** A revogação é a da subclasse, e ligar essa chave
  alarga o alcance em silêncio (ADR 0030).

## Alternativas consideradas

- **Manter desligado** — "Sair" continuaria sem sair.
- **Revogar por conta, como o toolkit faz** — sair de uma RP derrubaria as outras.
- **Hint revogado como erro, como o toolkit faz** — a saída numa segunda aba terminaria na tela de
  erro.
- **Uma linha de trilha por token** — os tokens não têm identificador publicável na trilha, e as
  linhas se multiplicariam.
- **Chamar a trilha direto da view, sem sinal** — rompe a regra de `event` igual ao nome do sinal e
  acopla a view à trilha.
- **`ALWAYS_PROMPT` verdadeiro** — perguntaria a cada saída da RP de primeira parte (ADR 0021), sem
  exigência da especificação.
- **`STRICT_REDIRECT_URIS` literal** — verdadeira, recusaria a SPA de desenvolvimento; falsa,
  afirmaria que `http` é aceito atrás do proxy.
- **`ACCEPT_EXPIRED_TOKENS` falsa** — a aba aberta há mais de dez horas não sairia.
