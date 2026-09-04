"""T-04 — Authorization Code + PKCE (S256) completo, Application fixture RS256.

Demanda do quality-assurance (TASK-006), cinco asserções contra o mesmo fluxo.
Nível integração: é a costura onde settings, validador, Application e as views
do DOT se encontram — nenhuma peça sozinha revela o resultado.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from tests.oauth_helpers import (
    authorize_and_get_code,
    create_public_rs256_application,
    decode_jwt,
    exchange_code_for_tokens,
)

User = get_user_model()

# Claims injetadas automaticamente pelo oauthlib no id_token (get_id_token_dictionary,
# oauth2_validators.py), descontadas antes de comparar com claims_supported da
# discovery — são mecânica de protocolo, não afirmação de identidade.
AUTO_CLAIMS = {"aud", "iat", "exp", "jti", "auth_time", "at_hash", "nonce", "c_hash", "iss"}


class AuthorizationCodePkceFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="fluxo@example.com",
            password="senha-forte-o-suficiente",
            first_name="Krishna",
            last_name="Lila",
        )
        self.application = create_public_rs256_application(self.user)
        self.client.force_login(self.user)

    def test_i_ii_iv_v_scope_completo_id_token_userinfo_e_acoplamento_com_discovery(self):
        code, verifier, _ = authorize_and_get_code(
            self.client, self.application, scope="openid profile email"
        )
        self.assertIsNotNone(code, "consentimento não produziu code")

        token_response = exchange_code_for_tokens(self.client, self.application, code, verifier)
        self.assertEqual(token_response.status_code, 200)
        body = token_response.json()

        # (i) id_token PRESENTE: ausente reprova - é o alçapão do `algorithm` da
        # Application: o fluxo fecha, o access_token chega, e nenhum id_token vem.
        self.assertIn("id_token", body)

        header, payload = decode_jwt(body["id_token"])
        self.assertEqual(header["alg"], "RS256")

        jwks_response = self.client.get("/o/.well-known/jwks.json")
        published_kid = jwks_response.json()["keys"][0]["kid"]
        self.assertEqual(header["kid"], published_kid)

        for claim in ("sub", "name", "email"):
            self.assertIn(claim, payload)
        self.assertEqual(payload["iss"], "http://localhost:8000/o")

        # (iv) email_verified ausente do id_token: sem fluxo de verificação nesta fase.
        self.assertNotIn("email_verified", payload)

        # (ii) userinfo com o mesmo access_token: igualdade, não só presença.
        userinfo_response = self.client.get(
            "/o/userinfo/", HTTP_AUTHORIZATION=f"Bearer {body['access_token']}"
        )
        self.assertEqual(userinfo_response.status_code, 200)
        userinfo = userinfo_response.json()

        for claim in ("sub", "name", "email"):
            self.assertEqual(userinfo[claim], payload[claim])

        # (iv) email_verified também ausente do userinfo.
        self.assertNotIn("email_verified", userinfo)

        # (v) ACOPLAMENTO: claims de identidade do id_token (descontadas as
        # automáticas do oauthlib) têm de bater exatamente com claims_supported
        # da discovery. Guarda contra get_additional_claims(self, request) —
        # troca de aridade que faz o id_token continuar certo e a discovery
        # subdeclarar em silêncio.
        identity_claims = set(payload.keys()) - AUTO_CLAIMS
        discovery_response = self.client.get("/o/.well-known/openid-configuration")
        claims_supported = set(discovery_response.json()["claims_supported"])
        self.assertEqual(identity_claims, claims_supported)

    def test_iii_iv_scope_openid_apenas_sub(self):
        code, verifier, _ = authorize_and_get_code(
            self.client, self.application, scope="openid"
        )
        self.assertIsNotNone(code, "consentimento não produziu code")

        token_response = exchange_code_for_tokens(self.client, self.application, code, verifier)
        self.assertEqual(token_response.status_code, 200)
        body = token_response.json()

        _header, payload = decode_jwt(body["id_token"])
        self.assertNotIn("name", payload)
        self.assertNotIn("email", payload)
        # (iv) email_verified ausente também neste caso.
        self.assertNotIn("email_verified", payload)

        userinfo_response = self.client.get(
            "/o/userinfo/", HTTP_AUTHORIZATION=f"Bearer {body['access_token']}"
        )
        self.assertEqual(userinfo_response.status_code, 200)
        # userinfo == {"sub": ...} - só a chave sub, mais nenhuma.
        self.assertEqual(set(userinfo_response.json().keys()), {"sub"})
