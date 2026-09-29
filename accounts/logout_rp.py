"""O logout iniciado pela relying party (RP): a view do toolkit, com quatro métodos sobrescritos.

`LogoutPelaRPView` atende `/o/logout/` sombreando a rota do toolkit, montada antes do `include`
de `o/` em `config/urls.py` (ADR — Architecture Decision Record — 0030). O que ela decide, e
o toolkit sozinho não decide, está na ADR 0029: revogar só na Application que pede, registrar a
revogação na trilha, tratar como ausente o hint autêntico já sem linha e responder 400, e não
500, às entradas forjadas enumeradas em `_ENTRADA_FORJADA`.

Herdado sem sobrescrita: `get`, `post`, `form_valid`, `must_prompt`, `validate_logout_request`,
`error_response`, `dispatch`, o template e o redirecionamento. Cada método sobrescrito só
envolve o `super()`, e a subida do toolkit relê os quatro, as exceções enumeradas e as duas
APIs privadas do validador de que o desempate depende, `_get_key_for_token` e
`_get_client_by_audience`.

Mora em `accounts` porque decide o que acontece com os tokens de uma pessoa e anuncia isso à
trilha; `config` não afirma nada sobre identidade. O sinal mora com quem o emite, como
`app_authorized` no toolkit.
"""

import json
import logging

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import DataError, transaction
from django.dispatch import Signal
from jwcrypto import jwt
from jwcrypto.common import JWException
from oauth2_provider.exceptions import (
    ClientIdMissmatch,
    InvalidIDTokenError,
    InvalidOIDCClientError,
    InvalidOIDCRedirectURIError,
)
from oauth2_provider.models import (
    get_access_token_model,
    get_application_model,
    get_id_token_model,
    get_refresh_token_model,
)
from oauth2_provider.settings import oauth2_settings
from oauth2_provider.views.oidc import RPInitiatedLogoutView

logger = logging.getLogger(__name__)

# Uma emissão por saída que revogou ao menos um token. Argumentos: `request`, `user` (o dono
# dos tokens revogados) e `application`. O receptor é `accounts.auditoria.registrar_revogacao`,
# e `event` na trilha recebe o nome deste sinal (ADR 0013).
tokens_revogados = Signal()

# As exceções que uma entrada forjada faz o toolkit levantar sem capturar, e que sem esta
# lista chegam ao navegador como 500:
# - ValueError: carga de JWS que não é JSON, ou não é UTF-8, no `json.loads` de
#   `_get_key_for_token` (`oauth2_provider/oauth2_validators.py:1484`);
# - KeyError: JWS em serialização JSON sem `payload`, na mesma linha;
# - TypeError: carga JSON que não é objeto, em `"aud" not in claims` (`:1485`), ou `aud` de
#   tipo que não se itera, em `_get_client_by_audience` (`:1497-1499`);
# - ImproperlyConfigured: `aud` de Application sem algoritmo de assinatura, em
#   `application.jwk_key` (`oauth2_provider/models.py:477`), lido em `:1489`;
# - DataError: o caractere NUL em `client_id` ou em `aud`, que o psycopg 3 recusa em campo de
#   texto. Sai de `.objects.get(client_id=...)` (`oauth2_provider/views/oidc.py:347`) e de
#   `filter(client_id__in=aud)` (`oauth2_validators.py:1499`), alcançado por
#   `_get_key_for_token` (`:1487`) e pelo desempate abaixo;
# - ValidationError: `jti` que não é UUID, em `IDToken.objects.get(jti=...)`
#   (`oauth2_provider/views/oidc.py:198`) e no desempate. Só alcançável com um hint assinado
#   de verdade, isto é, por quem tem o segredo de um cliente HS256.
# Nomeadas uma a uma e nunca `Exception`, `DatabaseError` ou `Error`: um AttributeError aqui é
# API privada do toolkit que mudou, e banco fora do ar é OperationalError; os dois têm de subir
# como 500, e não virar recusa silenciosa.
#
# As duas exceções de banco só são capturadas FORA de um `transaction.atomic()` próprio,
# em volta das três chamadas que consultam com entrada do pedido. O Django só admite capturar
# erro de banco fora do bloco atômico que contém a consulta que falhou: sem o savepoint, dentro
# de um bloco externo (o do TestCase, ou um ATOMIC_REQUESTS futuro), o erro do servidor aborta a
# transação no Postgres sem que o Django saiba, e a consulta seguinte sai como InternalError
# ("current transaction is aborted"), isto é, 500. O savepoint também tira a dependência de o
# driver recusar o NUL no cliente ou no servidor.
_ENTRADA_FORJADA = (
    ValueError,
    KeyError,
    TypeError,
    ImproperlyConfigured,
    DataError,
    ValidationError,
)


def _aplicacao_do_hint_sem_linha(request, hint):
    """A Application do `aud` de um hint autêntico cuja linha já não existe, ou None.

    Autêntico quer dizer as quatro condições juntas: a chave sai do `aud`, a assinatura
    confere com a mesma regra de validade do toolkit (`oauth2_provider/views/oidc.py:181-190`),
    o `iss` é este issuer e o `jti` não tem linha. É o que distingue a saída repetida, numa
    segunda aba, do hint forjado, que o toolkit junta num mesmo `(None, None)` em
    `_load_id_token` (`:161-201`).

    Qualquer condição falsa, ou exceção de entrada forjada, devolve None, e quem chama recusa
    o pedido.
    """
    validator = oauth2_settings.OAUTH2_VALIDATOR_CLASS()
    try:
        # Savepoint: o `aud` e o `jti` vêm do pedido e chegam ao banco (ver `_ENTRADA_FORJADA`).
        with transaction.atomic():
            chave = validator._get_key_for_token(hint)
            if not chave:
                return None
            # Com ACCEPT_EXPIRED_TOKENS, `check_claims={}` deixa de fora `exp` e `nbf`, como no
            # toolkit: a aba aberta há mais de dez horas também sai.
            aceita_vencido = oauth2_settings.OIDC_RP_INITIATED_LOGOUT_ACCEPT_EXPIRED_TOKENS
            verificado = jwt.JWT(key=chave, jwt=hint, check_claims={} if aceita_vencido else None)
            claims = json.loads(verificado.claims)
            if not isinstance(claims, dict) or "jti" not in claims:
                return None
            if claims.get("iss") != validator.get_oidc_issuer_endpoint(request):
                return None
            if get_id_token_model().objects.filter(jti=claims["jti"]).exists():
                return None
            return validator._get_client_by_audience(claims["aud"])
    except (JWException, *_ENTRADA_FORJADA):
        return None


def _revogar(dono, aplicacao):
    """Revoga os tokens de `dono` em `aplicacao`, e só nela. Devolve se revogou algum.

    Filtra por conta e Application, que é o recorte decidido na ADR 0029, e não a partir dos
    access tokens, como o toolkit (`oauth2_provider/views/oidc.py:434-454`). Com isso também
    pega o refresh órfão, sem access token. O toolkit já recusa esse refresh
    (`oauth2_validators.py:1296-1298`) e o `cleartokens` o apaga (`models.py:1269-1272`), então
    marcá-lo revogado só o encerra mais cedo, sem mudar o que ele pode fazer. A ordem segue as
    ligações: `RefreshToken.revoke()` apaga o access token ligado, e apagar um id_token apaga em
    cascata o access token que o referencia (`AccessToken.id_token`). Cada lista é lida depois
    de a anterior ter sido revogada.

    SILÊNCIO: um refresh validado antes desta saída e gravado depois dela nasce vivo. O toolkit
    valida fora de trava e, ao gravar, não reconfere a revogação
    (`oauth2_validators.py:997-1038`). Nada aqui alcança esse intervalo.
    """
    filtro = {"user": dono, "application": aplicacao}
    with transaction.atomic():
        refresh_tokens = list(
            get_refresh_token_model().objects.filter(revoked__isnull=True, **filtro)
        )
        for token in refresh_tokens:
            token.revoke()
        id_tokens = list(get_id_token_model().objects.filter(**filtro))
        for token in id_tokens:
            token.revoke()
        access_tokens = list(get_access_token_model().objects.filter(**filtro))
        for token in access_tokens:
            token.revoke()
    return bool(refresh_tokens or id_tokens or access_tokens)


class LogoutPelaRPView(RPInitiatedLogoutView):
    # Estado por requisição: `validate_logout_request_user` o regrava a cada pedido, e o
    # default de classe é só None, nunca objeto mutável compartilhado entre requisições.
    aplicacao_do_hint_sem_linha = None

    def validate_logout_request_user(self, id_token_hint, client_id):
        self.aplicacao_do_hint_sem_linha = None
        try:
            # Savepoint: o toolkit consulta o banco com o `aud` e o `jti` do hint.
            with transaction.atomic():
                return super().validate_logout_request_user(id_token_hint, client_id)
        except InvalidIDTokenError:
            pass
        except _ENTRADA_FORJADA as erro:
            # Só o nome da classe: o hint é credencial de revogação e nunca entra em log.
            logger.warning(
                "logout pela RP: hint recusado",
                extra={"error_class": type(erro).__name__},
            )
        aplicacao = _aplicacao_do_hint_sem_linha(self.request, id_token_hint)
        if aplicacao is None:
            raise InvalidIDTokenError()
        if client_id and client_id != aplicacao.client_id:
            raise ClientIdMissmatch()
        # Hint sem linha é tratado como ausente: nenhum `token_user`, e por isso nunca autoriza
        # revogação por si. A Application dele só vale para validar o destino e, com sessão
        # e confirmação, para revogar os tokens da conta da sessão.
        self.aplicacao_do_hint_sem_linha = aplicacao
        return None

    def get_request_application(self, id_token, client_id):
        try:
            # Savepoint: o toolkit consulta o banco com o `client_id` do pedido.
            with transaction.atomic():
                aplicacao = super().get_request_application(id_token, client_id)
        except (get_application_model().DoesNotExist, DataError):
            # O toolkit faz `.objects.get` sem captura (`oauth2_provider/views/oidc.py:347`).
            raise InvalidOIDCClientError() from None
        if aplicacao is None:
            return self.aplicacao_do_hint_sem_linha
        return aplicacao

    def validate_post_logout_redirect_uri(self, application, post_logout_redirect_uri):
        # O destino que não se decompõe como URL levanta ValueError dentro do toolkit, sem
        # captura: `urlparse` com colchete aberto no host, "Invalid IPv6 URL"
        # (`oauth2_provider/views/oidc.py:312`), e, em `check_redirect_to_uri_allowed`,
        # `urlsplit` (`oauth2_provider/models.py:1415`) e `.port` com porta não numérica ou
        # acima de 65535 (`:1487`). Vira a recusa de destino do próprio toolkit. Sem log, como
        # as recusas de destino do toolkit, e sem banco nesse caminho.
        try:
            return super().validate_post_logout_redirect_uri(application, post_logout_redirect_uri)
        except ValueError:
            raise InvalidOIDCRedirectURIError() from None

    def do_logout(
        self, application=None, post_logout_redirect_uri=None, state=None, token_user=None
    ):
        dono = token_user or self.request.user
        if application is not None and dono.is_authenticated and _revogar(dono, application):
            tokens_revogados.send(
                sender=type(self),
                request=self.request,
                user=dono,
                application=application,
            )
        # O toolkit encerra a sessão e redireciona. A revogação dele não roda porque
        # OIDC_RP_INITIATED_LOGOUT_DELETE_TOKENS é falsa (`oauth2_provider/views/oidc.py:434`);
        # verdadeira, ela revogaria a conta inteira depois desta, sem erro nenhum.
        return super().do_logout(application, post_logout_redirect_uri, state, token_user)
