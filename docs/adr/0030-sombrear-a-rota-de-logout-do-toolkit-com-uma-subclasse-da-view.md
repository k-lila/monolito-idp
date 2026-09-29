# 0030. Sombrear a rota de logout do toolkit com uma subclasse da view, montada antes do include

## Status

Proposto — 2026-09-29

Emenda à ADR (Architecture Decision Record) 0002, que **permanece aceita e em vigor**, e à ADR 0024,
na frase em que ela reafirma a 0002. Só para `/o/logout/`, esta decisão substitui duas afirmações. A
primeira, da 0002: "não reescrevemos, envelopamos nem duplicamos endpoint de protocolo". A segunda,
que as duas ADRs fazem: "a única customização permitida no comportamento do servidor é o
`OAUTH2_VALIDATOR_CLASS`". Para todo outro endpoint, as duas continuam valendo. A unidade da
montagem da 0024, a lista, não muda.

## Contexto

A ADR 0029 liga o logout iniciado pela relying party (RP) e exige quatro comportamentos que a view
do django-oauth-toolkit (DOT) 3.4.1, `RPInitiatedLogoutView`, não oferece por configuração:

- **Revogar só na Application que pediu.** A view revoga os tokens da conta em todas as
  Applications, filtrando por usuário e por atributos de classe
  (`oauth2_provider/views/oidc.py:224-234` e `:437-441`).
- **Registrar a revogação na trilha.** O toolkit não emite sinal ao revogar; o único sinal dele é
  `app_authorized`.
- **Tratar como ausente o hint autêntico já revogado.** `_load_id_token` junta num mesmo `(None,
  None)` o hint malformado, o de assinatura inválida, o vencido e o que não tem mais linha no banco
  (`:170-201`).
- **Responder 4xx às entradas forjadas que hoje dão 500.** São elas:
  - `client_id` inexistente (`:347`) ou com o caractere NUL, que o driver (psycopg 3) recusa com
    `DataError` na mesma linha;
  - hint com forma de JWS e carga que não é JSON (`oauth2_validators.py:1484`), com `aud` de
    Application sem algoritmo (`models.py:477`) ou com `aud` contendo NUL
    (`oauth2_validators.py:1499`);
  - `post_logout_redirect_uri` que não se decompõe como URL, como um colchete aberto no host ou uma
    porta impossível (`:312`; `models.py:1415` e `:1487`).

O validador não alcança nenhum desses pontos: ele não vê a revogação nem a escolha da Application, e
o contrato dele neste projeto é decidir claims, não fluxo (`accounts/oauth_validators.py`). O
toolkit não tem setting para trocar a classe da view de logout. Dois fatos do Django e do toolkit
tornam a troca possível sem copiar rota. O Django resolve pela primeira rota que casa. O toolkit
monta os endpoints das descobertas por `reverse()` no namespace `oauth2_provider`, e não pela view
que atende.

## Decisão

Vamos atender `/o/logout/` com `LogoutPelaRPView`, uma subclasse de `RPInitiatedLogoutView` em
`accounts/logout_rp.py`. Ela é montada em `config/urls.py` numa rota própria, `o/logout/` com nome
`logout_rp`, declarada antes do `include` de `o/`.

- **Sombra, e não cópia.** A rota do toolkit continua dentro do `include`, na lista
  `oidc_urlpatterns`, sem `path()` copiado. `reverse("oauth2_provider:rp-initiated-logout")`
  continua dando `/o/logout/`, e esse caminho resolve para a subclasse. A descoberta não muda.
- **A menor sobrescrita que cumpre a 0029: quatro métodos, cada um chamando o `super()`.**
  - `validate_logout_request_user` converte em recusa as exceções de entrada forjada e distingue o
    hint autêntico sem linha.
  - `get_request_application` converte em recusa o `client_id` inexistente, ou recusado pelo
    banco, e usa a Application do hint sem linha quando não há outra.
  - `validate_post_logout_redirect_uri` converte o destino que não se decompõe como URL numa
    recusa do próprio toolkit (`InvalidOIDCRedirectURIError`). As regras de destino continuam
    sendo as do toolkit.
  - `do_logout` revoga só na Application e emite o sinal da trilha, e então delega ao toolkit o
    encerramento da sessão e o redirecionamento.
  - Tudo o mais é herdado: a leitura do pedido, a decisão de perguntar, a resposta de erro e o
    template.
- **Captura nomeada e local.** Cada exceção capturada é nomeada, com a linha do toolkit ou do
  driver que a levanta. O erro de banco só é capturado em volta das consultas que usam `client_id`
  ou `aud`, e dentro de um savepoint próprio, para que a conexão continue utilizável quando houver
  um bloco atômico externo. Erro de banco que não vem da entrada, como banco fora do ar, sai como
  500.
- **Dependência declarada de API privada do toolkit:** `_get_key_for_token` e
  `_get_client_by_audience`, do validador.
- **Uma revogação só.** `OIDC_RP_INITIATED_LOGOUT_DELETE_TOKENS` fica falsa: a do toolkit não roda,
  e a da subclasse é a única.
- **Em `accounts`, e não em `config`:** a subclasse decide o que acontece com os tokens de uma
  pessoa e anuncia isso à trilha. `config` não afirma nada sobre identidade.
- **A guarda na suíte:** o caminho devolvido pelo `reverse` no namespace resolve para a subclasse.

Nada muda para a RP. Por isso esta decisão não tem contraparte na `nova_api_SPA`.

## Consequências

Positivas:

- A ADR 0029 fica possível sem tirar do toolkit a máquina do protocolo: validação do pedido,
  pergunta, destino e redirecionamento continuam dele.
- A exceção tem limite: uma rota e quatro métodos, com a guarda na suíte.

Negativas:

- É o primeiro código deste projeto no caminho de um endpoint de protocolo. A subida para o DOT 4.0,
  que a 0002 já trata como revisão deliberada, passa a incluir a releitura dos quatro métodos, das
  duas APIs privadas e das exceções enumeradas.
- **A falha da sombra é silenciosa.** A rota declarada depois do `include`, ou um upgrade que
  renomeie o caminho do toolkit, entrega a view original. Com `DELETE_TOKENS` falsa, essa view
  encerra a sessão, redireciona normalmente e não revoga nada. Só a guarda da suíte acusa.
- Ligar `DELETE_TOKENS` volta a revogar a conta inteira, depois da subclasse, sem erro nenhum.
- A revogação deixa de ser a do toolkit. Correções futuras do bloco de revogação dele não chegam
  aqui.
- `accounts` passa a depender do módulo de views do toolkit, e `config/urls.py` passa a importar de
  `accounts`.
- **A cerca cresceu uma vez depois do primeiro desenho.** A primeira versão sobrescrevia três
  métodos. O gate adversarial de 2026-09-29 achou mais três 500: destino que não se decompõe, e NUL
  em `client_id` e em `aud`. A promessa de 400 depende de enumerar exceções do toolkit e do driver,
  então uma exceção nova num upgrade volta a sair como 500. Isso é de propósito, pela regra da
  captura nomeada.

## Alternativas consideradas

- **Middleware ou decorator em volta da view do toolkit** — a mesma violação da 0002, e pior:
  interceptaria a requisição fora da view, com o estado dela inacessível.
- **Copiar `oidc_urlpatterns` trocando a rota de logout** — quebra a unidade de montagem da 0024 e
  cria cópia órfã a cada upgrade.
- **Customizar pelo validador** — ele não vê a revogação nem a escolha da Application, e o contrato
  dele é claims.
- **`post_delete` em `AccessToken` para a trilha** — dispara em toda revogação, inclusive na rotação
  de refresh e no `cleartokens`, e não resolve o alcance, o hint revogado nem os 500.
- **Aplicar patch no toolkit instalado** — some no próximo `pip install`.
- **Manter a view do toolkit como vem** — possível. Descartada porque fixaria a revogação por conta,
  deixaria a revogação fora da trilha, mandaria o hint revogado para a tela de erro e deixaria os
  500.
- **Capturar `Exception` no despacho da view** — fecharia todo 500 de uma vez. Descartada:
  transformaria em 400 também o defeito do toolkit ou o nosso, como uma API privada renomeada, e
  esse defeito tem de aparecer.
- **Recusar NUL na entrada, antes de consultar** — evitaria o erro de banco em vez de capturá-lo.
  Descartada: o `aud` é lido dentro do toolkit, onde a subclasse não valida antes; só a captura
  cobre os dois pontos.
