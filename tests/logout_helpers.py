"""Infraestrutura compartilhada pelos testes do logout iniciado pela relying party (RP).

Não é teste em si. Reúne o que `tests/test_logout_rp.py` e os arquivos que o TASK-027
estendeu repetiriam: a emissão de tokens pelo fluxo real, a leitura da trilha pelo arquivo
para onde o runner a redireciona (no molde de `tests/test_auditoria.py`), e o assinador de
hints forjados.

Todo destino de fixture é https: com `BEHIND_TLS_PROXY` ligado o runner não neutraliza
`OIDC_RP_INITIATED_LOGOUT_STRICT_REDIRECT_URIS`, e um destino http passaria na jornada de
construção e cairia na de container.
"""

import base64
import json
import logging
import os
import uuid
from datetime import timedelta

from django.test import Client
from django.utils import timezone
from jwcrypto import jwk, jwt
from oauth2_provider.models import get_application_model
from oauth2_provider.settings import oauth2_settings

from tests.oauth_helpers import (
    REDIRECT_URI,
    authorize_and_get_code,
    decode_jwt,
    exchange_code_for_tokens,
)

DESTINO = "https://landing.example/"


def criar_application(dono, nome="SPA", post_logout_redirect_uris=DESTINO):
    """Application pública RS256, sem `skip_authorization`, com destino de logout."""
    return get_application_model().objects.create(
        name=nome,
        client_type="public",
        authorization_grant_type="authorization-code",
        algorithm="RS256",
        redirect_uris=REDIRECT_URI,
        post_logout_redirect_uris=post_logout_redirect_uris,
        user=dono,
    )


def emitir_tokens(usuario, aplicacao, client=None):
    """Sessão do `usuario` e tokens dele na `aplicacao`. Devolve `(client, corpo_do_token)`."""
    client = client or Client()
    client.force_login(usuario)
    code, verifier, resposta = authorize_and_get_code(client, aplicacao)
    assert code, f"consentimento não produziu code: {resposta.status_code}"
    token = exchange_code_for_tokens(client, aplicacao, code, verifier)
    assert token.status_code == 200, token.content
    return client, token.json()


def status_userinfo(access_token):
    return Client().get(
        "/o/userinfo/", HTTP_AUTHORIZATION="Bearer " + access_token
    ).status_code


def status_refresh(aplicacao, refresh_token):
    return Client().post(
        "/o/token/",
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": aplicacao.client_id,
        },
    ).status_code


def handler_da_trilha():
    return logging.getLogger("audit").handlers[0]


def tamanho_da_trilha():
    return os.path.getsize(handler_da_trilha().baseFilename)


def linhas_da_trilha_desde(tamanho_antes):
    with open(handler_da_trilha().baseFilename, "r", encoding="utf-8") as arquivo:
        arquivo.seek(tamanho_antes)
        return [json.loads(linha) for linha in arquivo if linha.strip()]


def b64(dados):
    return base64.urlsafe_b64encode(dados).rstrip(b"=").decode()


def partes_do_token(id_token):
    """`(header, claims, assinatura_b64)` de um id_token real."""
    cabecalho, carga = decode_jwt(id_token)
    return cabecalho, carga, id_token.split(".")[2]


def adulterar_assinatura(id_token):
    """Troca um caractere do meio da assinatura: nunca o final, que carrega bits de
    preenchimento do base64 e poderia continuar válido."""
    h, p, s = id_token.split(".")
    meio = len(s) // 2
    troca = "A" if s[meio] != "A" else "B"
    return ".".join([h, p, s[:meio] + troca + s[meio + 1 :]])


def gerar_chave_rsa(kid):
    return jwk.JWK.generate(kty="RSA", size=2048, kid=kid)


def chave_do_idp():
    return jwk.JWK.from_pem(oauth2_settings.OIDC_RSA_PRIVATE_KEY.encode("utf8"))


def assinar(chave, cabecalho, claims):
    """JWS compacto RS256 com `chave`, o `cabecalho` e as `claims` dadas."""
    token = jwt.JWT(header=cabecalho, claims=claims)
    token.make_signed_token(chave)
    return token.serialize()


def claims_de_hint(issuer, client_id, jti=None, sub="1"):
    agora = timezone.now()
    return {
        "iss": issuer,
        "aud": client_id,
        "sub": sub,
        "jti": jti or uuid.uuid4().hex,
        "iat": int(agora.timestamp()),
        "exp": int((agora + timedelta(hours=1)).timestamp()),
    }
