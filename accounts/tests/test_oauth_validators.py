"""T-01 — IdPOAuth2Validator: mapeamento de User para claims, sem HTTP e sem banco.

Demanda do quality-assurance, verbatim (TASK-006). User NAO salvo, request falso
portando só `.user` e `.scopes` — a única superfície que `get_oidc_claims` lê
(oauth2_validators.py:1358-1367 na 3.4.1 instalada).

Nível unitário: é a única lógica com decisão própria neste bloco, isolável sem
HTTP, banco ou fluxo OAuth.
"""

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase

from accounts.oauth_validators import IdPOAuth2Validator

User = get_user_model()


class FakeRequest:
    """Portador mínimo exigido por `get_oidc_claims`: `.user` e `.scopes`."""

    def __init__(self, user, scopes):
        self.user = user
        self.scopes = scopes


def _claims_for(scopes, first_name="", last_name=""):
    user = User(email="pessoa@example.com", first_name=first_name, last_name=last_name)
    request = FakeRequest(user=user, scopes=scopes)
    validator = IdPOAuth2Validator()
    return validator.get_oidc_claims(token=None, token_handler=None, request=request)


class GetOidcClaimsTests(SimpleTestCase):
    # SimpleTestCase: nada aqui toca banco, o User é construído e nunca salvo.

    def test_i_name_ausente_de_pessoa_e_erro_chave_tem_que_estar_presente_e_vazia(self):
        """AC-10: first_name/last_name em branco -> "name" PRESENTE com valor "".

        Ponto exato do AC-10: um dict.get("name") com default esconderia a
        ausência da chave. A asserção tem de provar presença, não só o valor.
        """
        claims = _claims_for(["openid", "profile", "email"], first_name="", last_name="")

        self.assertIn("name", claims)
        self.assertEqual(claims["name"], "")
        self.assertIn("sub", claims)
        self.assertIn("email", claims)

    def test_ii_name_concatena_first_e_last_name(self):
        claims = _claims_for(
            ["openid", "profile", "email"], first_name="Krishna", last_name="Lila"
        )

        self.assertEqual(claims["name"], "Krishna Lila")

    def test_iii_scope_openid_apenas_sub(self):
        claims = _claims_for(["openid"])

        self.assertIn("sub", claims)
        self.assertNotIn("name", claims)
        self.assertNotIn("email", claims)

    def test_iv_scope_profile_libera_name_nao_email(self):
        claims = _claims_for(["openid", "profile"])

        self.assertIn("name", claims)
        self.assertNotIn("email", claims)

    def test_v_scope_email_libera_email_nao_name(self):
        claims = _claims_for(["openid", "email"])

        self.assertIn("email", claims)
        self.assertNotIn("name", claims)

    def test_vi_email_verified_ausente_em_todos_os_cinco_casos(self):
        """Nenhum fluxo de verificação nesta fase.

        Guarda específica: o scope "email" isolado herdaria email_verified do
        mapa `oidc_claim_scope` da classe base (oauth2_validators.py:210,
        "email_verified": "email") se `get_additional_claims` alguma vez
        passasse a devolvê-la. Por isso o caso (v) é o mais importante dos
        cinco para esta asserção.
        """
        casos = [
            ["openid", "profile", "email"],
            ["openid", "profile", "email"],
            ["openid"],
            ["openid", "profile"],
            ["openid", "email"],
        ]
        for scopes in casos:
            with self.subTest(scopes=scopes):
                claims = _claims_for(scopes)
                self.assertNotIn("email_verified", claims)
