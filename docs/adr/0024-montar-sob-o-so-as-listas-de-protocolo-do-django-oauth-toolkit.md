# 0024. Montar sob /o/ só as listas de protocolo do django-oauth-toolkit

## Status

Aceito — 2026-09-22

Emenda à ADR (Architecture Decision Record) 0002, que **permanece aceita e em vigor**. Esta
decisão substitui uma única frase daquela — "As rotas do DOT são incluídas como vêm" — no que ela
diz sobre **quais** rotas entram. O que a mesma frase proíbe continua proibido: nenhum endpoint de
protocolo é reescrito, envelopado nem duplicado, e a única customização de comportamento do
servidor segue sendo o `OAUTH2_VALIDATOR_CLASS`. A ADR 0007 não é emendada: o prefixo `/o/` e o
issuer `{BASE_URL}/o` ficam como estão.

## Contexto

`config/urls.py` monta o `django-oauth-toolkit` (DOT) 3.4.1 com um `include("oauth2_provider.urls")`
sob `o/`. A `urlpatterns` padrão da biblioteca é a soma de cinco listas nomeadas, que o próprio
módulo exporta (`oauth2_provider/urls.py`):

- `metadata_urlpatterns` — os metadados da RFC 8414 e da RFC 9728;
- `base_urlpatterns` — `authorize/`, `token/`, `revoke_token/`, `introspect/` e as quatro rotas do
  device grant;
- `management_urlpatterns` — `applications/…` e `authorized_tokens/…`, a gestão de clientes e de
  tokens por formulário;
- `oidc_urlpatterns` — a descoberta OpenID Connect (OIDC), o JSON Web Key Set (JWKS), `userinfo/`
  e `logout/`;
- `dcr_urlpatterns` — `register/…`, o registro dinâmico de cliente da RFC 7591.

As views de `management_urlpatterns` exigem só sessão autenticada, sem `is_staff` nem permissão.
Qualquer conta com senha neste provedor de identidade (IdP, de _Identity Provider_) registra uma
`Application` com a `redirect_uri` e o grant que quiser, inclusive `implicit` e `password`, que a
RFC 9700 deprecia. Enquanto a única conta era a de quem opera, isso era inerte; `docs/seguranca.md`
registrou a lacuna na seção 3 e a deixou como decisão aberta na 7.1, e o passo 5 de
`docs/plano-contrato-backend.md` a fecha antes de o IdP sair de `localhost`. O registro de
`Application` deste projeto sempre foi o admin (`docs/integracao-rp.md` §3), que exige `is_staff`.

A ADR 0002 decidiu incluir as rotas "como vêm". A razão dela é não reescrever a máquina de estados
do protocolo: rota envelopada ou duplicada é código nosso no caminho do protocolo, e é ali que um
erro sutil vira vulnerabilidade. Retirar uma lista inteira não põe código nosso nesse caminho, mas
contraria a letra da frase, e ADR aceita não se edita.

Um fato decide a forma da montagem: o DOT resolve os próprios endpoints por `reverse()` no
namespace `oauth2_provider`, e as duas descobertas reagem de modo diferente à falta dele. A
descoberta OIDC pede cada endpoint com `required=True` e responde 500 — falha ruidosa. A da
RFC 8414 (`OAuthServerMetadataView`, `oauth2_provider/views/metadata.py:53-66`) engole o
`NoReverseMatch` e **omite** o endpoint: o documento sai sem `authorization_endpoint` nem
`token_endpoint`, com 200.

## Decisão

Vamos montar sob `o/` apenas três das cinco listas do DOT — `metadata_urlpatterns`,
`base_urlpatterns` e `oidc_urlpatterns`, nessa ordem —, num único `include` e com o namespace
`oauth2_provider`, que é o `app_name` declarado pelo próprio módulo. `management_urlpatterns` e
`dcr_urlpatterns` ficam fora do URLConf.

- **A unidade é a lista, nunca a rota.** O URLConf compõe listas que a biblioteca exporta para
  serem compostas — o mesmo mecanismo que ela documenta para montar `metadata_urlpatterns` na
  raiz —, e não copia `path()` da biblioteca nem escolhe rota a rota. Rota que um upgrade
  acrescente a uma lista montada entra sozinha, como entrava com o `include` inteiro. Por isso o
  device grant, `revoke_token/` e `introspect/` continuam publicados: estão em
  `base_urlpatterns`, e retirá-los exigiria copiar rotas, que é a duplicação que a ADR 0002
  proíbe.
- **O namespace é parte do contrato público.** Sem ele, a descoberta da RFC 8414 perde endpoints
  em silêncio. A montagem o declara, e a suíte prova a presença e o valor de cada endpoint nas
  duas descobertas, não só o status 200.
- **A gestão de `Application` e de tokens é só do admin.** `/admin/oauth2_provider/…` já lista,
  cria, edita e apaga, sob `is_staff`.
- **O registro dinâmico fica fechado duas vezes.** `DCR_ENABLED` segue no default `False`, e a
  rota deixa de existir. Ligar o registro dinâmico passa a exigir as duas coisas, e é decisão com
  ADR própria.

Nada muda para a relying party (RP): issuer, descoberta, JWKS, claims e Cross-Origin Resource
Sharing (CORS) sob `/o/` ficam iguais. Por isso esta decisão não tem contraparte na
`nova_api_SPA`.

## Consequências

Positivas:

- Nenhuma conta, com ou sem `is_staff`, registra `Application`, edita a própria ou lista e revoga
  tokens por formulário fora do admin: as sete rotas de gestão respondem 404, com ou sem sessão.
- Nenhuma linha de código de produção nova: o controle é a ausência da rota, verificável pela
  suíte tanto quanto uma recusa seria.
- A decisão aberta 7.1 de `docs/seguranca.md` fecha, e "restrição de quem pode registrar
  Application" sai da lista da fronteira.
- O prefixo `/o/` passa a delimitar só superfície de protocolo, e é nessa propriedade que
  `CORS_URLS_REGEX = r"^/o/"` se apoia, no mesmo passo 5 do plano.

Negativas:

- `Application.get_absolute_url()` faz `reverse("oauth2_provider:detail")`, rota que deixa de
  existir (`oauth2_provider/models.py:425-426`). A página de edição do admin renderiza e mostra o
  botão "Ver no site"; o clique responde 500. Aceito e registrado como dívida, sem desligar
  `view_on_site`.
- A pessoa usuária perde o autosserviço de `/o/authorized_tokens/`: revogar o acesso de uma RP
  passa a ser só de quem opera (`docs/runbook.md`, "Revogar o acesso de uma pessoa").
- O DOT não sabe da montagem parcial. Um upgrade que mova um endpoint de protocolo para uma lista
  não montada, ou para uma lista nova, tira o endpoint do ar e, na descoberta da RFC 8414, do
  documento, sem erro. Só a suíte o acusa, e só porque confere o valor de cada endpoint. O
  upgrade para o DOT 4.0, que a ADR 0002 já trata como revisão deliberada, passa a incluir a
  releitura das cinco listas.
- Device grant, revogação e introspecção continuam publicados sem uso, pela regra da unidade: a
  superfície encolhe, mas não até o mínimo.
- A ADR 0007 justificou o prefixo, entre outras razões, por conter as views de gestão do DOT
  fora da raiz. Essa razão perde o objeto; a decisão da 0007 não depende só dela — o issuer é
  permanente depois da primeira RP — e não muda, mas quem a ler precisa desta ADR para saber que
  as views de gestão já não são montadas.
- A decisão vive numa emenda, e não no arquivo que o leitor abre primeiro; o índice de
  `docs/arquitetura.md` marca a 0002 como emendada.

## Alternativas consideradas

- **Manter o `include` inteiro e restringir as views de gestão a `is_staff`**, por decorator ou
  middleware — preservaria a letra da ADR 0002. Descartada: envelopa view do DOT com código nosso,
  que é o que a 0002 proíbe no espírito, para proteger uma superfície que o projeto não usa e que
  duplica o que o admin já oferece sob `is_staff`.
- **Montar rota a rota só o que a relying party consome** — `authorize/`, `token/`, `userinfo/` e
  as duas `.well-known`, a superfície mínima. Descartada: copia `path()` da biblioteca para dentro
  de `config/urls.py`, e cada upgrade passa a exigir comparar as duas listas à mão; rota nova de
  protocolo não entraria, e rota renomeada deixaria uma cópia órfã.
- **Montar tudo e barrar `/o/applications/` e `/o/authorized_tokens/` no proxy**, sem tocar o
  URLConf. Descartada: o controle dependeria de o tráfego atravessar o Caddy, a jornada de
  construção, que não tem proxy, ficaria aberta, e a suíte não o alcançaria.
- **Manter a montagem e aceitar o risco até haver mais de uma conta** — custo zero hoje.
  Descartada: é exatamente a condição que o passo 5 existe para fechar antes da exposição, e a
  abertura dependeria de alguém se lembrar dela no dia em que a segunda conta nascer.
