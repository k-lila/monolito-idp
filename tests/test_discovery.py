"""T-02 — GET /o/.well-known/openid-configuration.

Demanda do quality-assurance (TASK-006). Nível integração: o que pode quebrar
mora na costura entre OIDC_ISS_ENDPOINT, o prefixo do include em config/urls.py
é o reverse() do namespace do DOT — não em uma função isolável.

TASK-015/T-03 revisou `test_issuer_e_endpoints_obrigatorios`: o valor esperado deixou de ser o
literal `http://localhost:8000/o`, que só valia sob o `BASE_URL` da jornada de construção e
fazia este caso falhar sob qualquer outro (a jornada de container, com `BASE_URL` apontando
para `PUBLIC_HOST`, é uma delas). A expressão abaixo deriva de `settings.BASE_URL` — nunca de
`OAUTH2_PROVIDER["OIDC_ISS_ENDPOINT"]`, que é o próprio valor sob teste — e falha exatamente
para os defeitos que uma implantação de verdade pode introduzir na composição do issuer:
sufixo `/o` ausente, barra dobrada, barra final sobrando. O que esta forma NÃO pega — um
issuer bem formado apontando para o host errado — é lacuna documentada em `docs/testes.md` e
verificada à mão pelo procedimento de `docs/receita.md`.
"""

from django.conf import settings
from django.test import TestCase


class DiscoveryDocumentTests(TestCase):
    def test_issuer_e_endpoints_obrigatorios(self):
        response = self.client.get("/o/.well-known/openid-configuration")

        self.assertEqual(response.status_code, 200)
        body = response.json()

        # Igualdade exata, não substring: pega tanto {BASE_URL} sem o sufixo /o
        # quanto uma barra final indevida (rstrip ausente em OIDC_ISS_ENDPOINT).
        # Derivado de settings.BASE_URL por expressão independente — não do literal de uma
        # única jornada, nem da própria settings sob teste (T-03).
        self.assertEqual(body["issuer"], f"{settings.BASE_URL.rstrip('/')}/o")

        for key in (
            "authorization_endpoint",
            "token_endpoint",
            "userinfo_endpoint",
            "jwks_uri",
        ):
            self.assertIn(key, body)
            self.assertTrue(body[key])

    def test_end_session_endpoint_ausente(self):
        """OIDC_RP_INITIATED_LOGOUT_ENABLED=False (settings): guarda contra flip
        silencioso no upgrade do DOT — o próprio default da lib está programado
        para virar True na 4.0 (comentário em config/settings.py)."""
        response = self.client.get("/o/.well-known/openid-configuration")

        self.assertNotIn("end_session_endpoint", response.json())

    def test_discovery_na_raiz_do_host_e_404(self):
        """As rotas do DOT vivem sob /o/ (ADR 0007) — na raiz não há view nenhuma."""
        response = self.client.get("/.well-known/openid-configuration")

        self.assertEqual(response.status_code, 404)

    def test_todos_os_endpoints_da_discovery_oidc_batem_o_issuer_composto(self):
        """TASK-019/T-07 — complementa `test_issuer_e_endpoints_obrigatorios`: aquele caso
        só confere presença (`assertIn` + truthy); este confere o VALOR exato dos quatro
        endpoints, cada um o issuer mais o sufixo fixo do próprio protocolo — nunca por
        `reverse()`, que resolveria contra o mesmo URLConf sob prova e não pegaria um
        sufixo composto errado dentro de `config/urls.py`."""
        response = self.client.get("/o/.well-known/openid-configuration")
        self.assertEqual(response.status_code, 200)
        body = response.json()

        issuer = f"{settings.BASE_URL.rstrip('/')}/o"
        self.assertEqual(body["issuer"], issuer)
        self.assertEqual(body["authorization_endpoint"], issuer + "/authorize/")
        self.assertEqual(body["token_endpoint"], issuer + "/token/")
        self.assertEqual(body["userinfo_endpoint"], issuer + "/userinfo/")
        self.assertEqual(body["jwks_uri"], issuer + "/.well-known/jwks.json")

    def test_registration_endpoint_ausente_na_discovery_oidc(self):
        """DCR (Dynamic Client Registration) está fechado duas vezes pela ADR 0024:
        `DCR_ENABLED` no default `False` E a rota `/o/register/` fora do URLConf. Sem
        `DCR_ENABLED`, a biblioteca já omite `registration_endpoint`; este caso é o que
        cairia se algum dia `DCR_ENABLED=True` fosse ligado sem repor a rota — o endpoint
        voltaria a ser anunciado apontando para um 404."""
        response = self.client.get("/o/.well-known/openid-configuration")

        self.assertNotIn("registration_endpoint", response.json())


class OAuthAuthorizationServerMetadataDocumentTests(TestCase):
    """TASK-019/T-07 — GET /o/.well-known/oauth-authorization-server, a descoberta da
    RFC 8414. Ao contrário da OIDC, `OAuthServerMetadataView`
    (`oauth2_provider/views/metadata.py`) ENGOLE o `NoReverseMatch` de um endpoint sem rota
    e OMITE a chave, respondendo 200 — é a razão pela qual a ADR 0024 monta
    `metadata_urlpatterns` e `base_urlpatterns` no mesmo include de `oidc_urlpatterns`: sem
    os três juntos, esta descoberta sairia incompleta sem nenhum erro que a acusasse."""

    def test_endpoints_obrigatorios_batem_o_issuer_composto(self):
        response = self.client.get("/o/.well-known/oauth-authorization-server")
        self.assertEqual(response.status_code, 200)
        body = response.json()

        issuer = f"{settings.BASE_URL.rstrip('/')}/o"
        self.assertEqual(body["issuer"], issuer)
        self.assertEqual(body["authorization_endpoint"], issuer + "/authorize/")
        self.assertEqual(body["token_endpoint"], issuer + "/token/")
        self.assertEqual(body["jwks_uri"], issuer + "/.well-known/jwks.json")
        self.assertEqual(body["revocation_endpoint"], issuer + "/revoke_token/")
        self.assertEqual(body["introspection_endpoint"], issuer + "/introspect/")

    def test_registration_e_end_session_endpoint_ausentes(self):
        """`registration_endpoint`: mesma razão do par OIDC, `DCR_ENABLED=False` e a rota
        fora do URLConf. `end_session_endpoint`: a RFC 8414 nem declara esta chave — não é
        vocabulário dela —, e a guarda aqui é simétrica à de
        `DiscoveryDocumentTests.test_end_session_endpoint_ausente`, para o documento que
        aquele caso não cobre."""
        response = self.client.get("/o/.well-known/oauth-authorization-server")
        body = response.json()

        self.assertNotIn("registration_endpoint", body)
        self.assertNotIn("end_session_endpoint", body)


class JwksDocumentTests(TestCase):
    """TASK-019/T-07 — complementa `tests/test_jwks.py` (que já prova `kty` e `kid`) com o
    campo que aquele arquivo não confere: `alg`. RS256 é o único algoritmo que
    `create_public_rs256_application` (`tests/oauth_helpers.py`) e o `OIDC_RSA_PRIVATE_KEY`
    de `config/settings.py` sustentam — HS256 não teria chave pública para publicar aqui."""

    def test_uma_chave_com_kid_e_alg_rs256(self):
        response = self.client.get("/o/.well-known/jwks.json")

        self.assertEqual(response.status_code, 200)
        body = response.json()

        self.assertEqual(len(body["keys"]), 1)
        key = body["keys"][0]
        self.assertTrue(key["kid"])
        self.assertEqual(key["alg"], "RS256")
