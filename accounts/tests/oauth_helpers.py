"""Infraestrutura compartilhada pelos testes de integração do servidor OAuth2/OIDC.

Não é teste em si: é o que os T-04 e T-05 reusam para não duplicar fixture nem o
ritual do fluxo Authorization Code + PKCE (redirect_uri fixa, Application pública
RS256, geração de code_verifier/code_challenge, repostagem dos campos ocultos da
tela de consentimento). Ver nota do orquestrador no prompt de invocação sobre a
forma do form de `/o/authorize/`.
"""

import base64
import hashlib
import json
import os
import re
from urllib.parse import parse_qs, urlsplit

from oauth2_provider.models import get_application_model

# redirect_uri registrada na Application fixture: não precisa existir de verdade,
# só precisa bater por igualdade exata com a enviada em /o/authorize/.
REDIRECT_URI = "http://localhost:8000/noop"

_HIDDEN_INPUT_RE = re.compile(
    r'<input[^>]*type="hidden"[^>]*name="([^"]+)"[^>]*value="([^"]*)"'
)


def make_pkce_pair():
    """Gera (code_verifier, code_challenge) válido para o método S256 (RFC 7636)."""
    verifier = base64.urlsafe_b64encode(os.urandom(40)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def create_public_rs256_application(user):
    """Application fixture do enunciado: client público, RS256, redirect_uri fixa.

    Nunca a linha do banco de dev (TASK-006) — sempre criada pelo teste, no banco
    de teste do runner.
    """
    Application = get_application_model()
    return Application.objects.create(
        name="fixture-oauth-client",
        client_type="public",
        authorization_grant_type="authorization-code",
        algorithm="RS256",
        redirect_uris=REDIRECT_URI,
        user=user,
    )


def extract_hidden_inputs(html):
    """Le os `<input type="hidden">` do form de consentimento do DOT.

    Comportamento verificado contra o test client (nota do orquestrador): GET em
    /o/authorize/ com parâmetros válidos devolve 200 com este form, cujos campos
    ocultos precisam ser repostados integralmente no POST de consentimento.
    """
    return dict(_HIDDEN_INPUT_RE.findall(html))


def authorize_and_get_code(client, application, redirect_uri=REDIRECT_URI, **extra_params):
    """Fecha o GET+POST de /o/authorize/ e devolve (code, code_verifier) ou (None, verifier).

    `code` vem None quando o servidor recusa antes de emitir code — guarda que T-05
    precisa distinguir de um code de verdade. `state` fixo simplifica a leitura do
    Location; não faz parte do que os T's pedem verificar.
    """
    verifier, challenge = make_pkce_pair()
    params = {
        "response_type": "code",
        "client_id": application.client_id,
        "redirect_uri": redirect_uri,
        "scope": "openid",
        "state": "fixture-state",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "nonce": "fixture-nonce",
    }
    params.update(extra_params)

    get_response = client.get("/o/authorize/", params)
    if get_response.status_code != 200:
        # Recusa antes da tela de consentimento (ex.: redirect_uri fora da allowlist,
        # code_challenge ausente que a view rejeita direto no GET).
        return None, verifier, get_response

    hidden = extract_hidden_inputs(get_response.content.decode())
    post_data = dict(hidden)
    post_data["allow"] = "Authorize"
    post_response = client.post("/o/authorize/", post_data)

    location = post_response.get("Location")
    if not location:
        return None, verifier, post_response

    query = parse_qs(urlsplit(location).query)
    code = query.get("code", [None])[0]
    return code, verifier, post_response


def exchange_code_for_tokens(client, application, code, verifier, redirect_uri=REDIRECT_URI):
    """POST em /o/token/ com o code_verifier. Client público: sem client_secret."""
    response = client.post(
        "/o/token/",
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": application.client_id,
            "code_verifier": verifier,
        },
    )
    return response


def _b64url_decode(segment):
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


def decode_jwt(token):
    """Decodifica header e payload de um JWT compacto, sem verificar assinatura.

    Suficiente para os T's: nenhuma demanda pede verificação criptográfica da
    assinatura, só leitura de header (alg, kid) e payload (claims). Não acrescenta
    dependência nova — só base64/json da stdlib.
    """
    header_segment, payload_segment, _signature = token.split(".")
    header = json.loads(_b64url_decode(header_segment))
    payload = json.loads(_b64url_decode(payload_segment))
    return header, payload
