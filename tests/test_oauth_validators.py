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

UUID_V4 = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"


class FakeRequest:
    """Portador mínimo exigido por `get_oidc_claims`: `.user` e `.scopes`."""

    def __init__(self, user, scopes):
        self.user = user
        self.scopes = scopes


# `pk` fixo e diferente do `sub`: sem ele o User não salvo teria `pk` nulo, e a asserção de que o
# `sub` não é a chave primária compararia com "None".
def _user_e_claims(scopes, first_name="", last_name=""):
    user = User(pk=42, email="pessoa@example.com", first_name=first_name, last_name=last_name)
    request = FakeRequest(user=user, scopes=scopes)
    validator = IdPOAuth2Validator()
    claims = validator.get_oidc_claims(token=None, token_handler=None, request=request)
    return user, claims


def _claims_for(scopes, first_name="", last_name=""):
    return _user_e_claims(scopes, first_name, last_name)[1]


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

    def test_vi_claims_por_conjunto_de_scopes_e_email_verified_presente_com_email(self):
        """TASK-028/T-06. Cada claim sai com o scope que a libera e só com ele.

        `openid`: só o `sub`, o UUID da conta (ADR 0031), nunca a chave primária. `profile`
        acrescenta `name`, `nickname` — presente e vazia — e `updated_at` em segundos inteiros.
        `email` acrescenta `email` e `email_verified`, booleano. `given_name` e `family_name`
        não saem em combinação nenhuma: `name` vem de `get_full_name()`, e um segundo lugar
        para o nome divergiria. O segundo caso de `openid profile email` traz nome preenchido.
        """
        casos = [
            (["openid", "profile", "email"], {}),
            (["openid", "profile", "email"], {"first_name": "Krishna", "last_name": "Lila"}),
            (["openid"], {}),
            (["openid", "profile"], {}),
            (["openid", "email"], {}),
        ]
        for scopes, nomes in casos:
            with self.subTest(scopes=scopes, nomes=nomes):
                user, claims = _user_e_claims(scopes, **nomes)

                esperadas = {"sub"}
                if "profile" in scopes:
                    esperadas |= {"name", "nickname", "updated_at"}
                if "email" in scopes:
                    esperadas |= {"email", "email_verified"}
                self.assertEqual(set(claims), esperadas)
                self.assertNotIn("given_name", claims)
                self.assertNotIn("family_name", claims)

                self.assertEqual(claims["sub"], str(user.sub))
                self.assertRegex(claims["sub"], UUID_V4)
                self.assertNotEqual(claims["sub"], str(user.pk))

                if "profile" in scopes:
                    self.assertEqual(claims["name"], user.get_full_name())
                    self.assertEqual(claims["nickname"], "")
                    self.assertIsInstance(claims["updated_at"], int)
                    self.assertEqual(claims["updated_at"], int(user.updated_at.timestamp()))
                if "email" in scopes:
                    self.assertEqual(claims["email"], user.email)
                    self.assertIs(claims["email_verified"], False)

    def test_vi_b_email_verified_e_nickname_saem_do_usuario_e_nao_de_valor_fixo(self):
        """TASK-028/T-06b. Os dois valores do `User` chegam ao claim: o caso padrão só prova
        `False` e `""`, que um valor fixo também devolveria."""
        user = User(pk=42, email="bia@example.com", email_verified=True, nickname="Bia")
        request = FakeRequest(user=user, scopes=["openid", "profile", "email"])

        claims = IdPOAuth2Validator().get_oidc_claims(
            token=None, token_handler=None, request=request
        )

        self.assertIs(claims["email_verified"], user.email_verified)
        self.assertIs(claims["email_verified"], True)
        self.assertEqual(claims["nickname"], user.nickname)
        self.assertEqual(claims["nickname"], "Bia")
