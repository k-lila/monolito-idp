"""TASK-019/T-04, T-05, T-12 — o admin de `Application` (`oauth2_provider.admin`), a única
superfície de gestão desde a ADR 0024 (`docs/adr/0024-montar-sob-o-so-as-listas-de-protocolo-do-django-oauth-toolkit.md`).

Nível integração nos três: o que está sob prova é a costura entre o formulário do admin, o
`clean()` de `AbstractApplication` (`oauth2_provider/models.py`) e `ALLOWED_REDIRECT_URI_SCHEMES`
— nenhuma delas é função isolável, e só a resposta HTTP revela o resultado da composição.

T-04 e T-05 moram na mesma classe, como o quality-assurance autorizou: as duas provam a MESMA
costura, sob os dois valores possíveis de `ALLOWED_REDIRECT_URI_SCHEMES` durante a suíte — o
endurecido (`override_settings`, T-04) e o neutro que `tests/runner.py` já aplica (T-05). É
proibido chegar ao endurecido por `override_settings(BEHIND_TLS_PROXY=True)`: essa variável
também muda `SECURE_SSL_REDIRECT` e a procedência do endereço (ADR 0018), e a composição do
issuer — alcançaria os três de propósito, quando o único valor sob prova aqui é o do formulário
e o de `/o/authorize/`. `override_settings(OAUTH2_PROVIDER={**settings.OAUTH2_PROVIDER,
"ALLOWED_REDIRECT_URI_SCHEMES": ["https"]})` muda só a chave sob teste.
"""

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from django.test import TestCase, override_settings
from oauth2_provider.models import get_application_model
from oauth2_provider.settings import oauth2_settings

from tests.oauth_helpers import authorize_and_get_code, make_pkce_pair

User = get_user_model()
Application = get_application_model()


def _dados_de_application(usuario, **overrides):
    """Um POST completo e válido para o form do admin de `Application` — nome, tipo de
    cliente, grant, algoritmo e usuário —, pronto para receber os campos que cada teste
    varia (`client_id` obrigatório e único, `redirect_uris`, `name`). Os campos booleanos
    (`hash_client_secret`, `skip_authorization`) ficam de fora de propósito: um checkbox
    ausente do POST é como o navegador envia "desmarcado", e nenhum destes testes depende
    do valor deles."""
    dados = {
        "client_id": "fixture-admin-app",
        "user": str(usuario.pk),
        "client_type": "public",
        "authorization_grant_type": "authorization-code",
        "redirect_uris": "https://previo.example/callback",
        "name": "fixture-admin-application",
        "algorithm": "RS256",
    }
    dados.update(overrides)
    return dados


class AdminApplicationRedirectUriSchemeTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            email="admin-t04@example.com", password="senha-forte-o-suficiente"
        )
        self.client.force_login(self.superuser)
        self.aplicacao_existente = Application.objects.create(
            name="fixture-t04-existente",
            client_id="fixture-t04-existente-client",
            client_type="public",
            authorization_grant_type="authorization-code",
            algorithm="RS256",
            redirect_uris="https://previo.example/callback",
            user=self.superuser,
        )

    def test_a_b_c_esquema_https_only_bloqueia_http_e_libera_https_e_o_authorize_segue(self):
        # A Application do enunciado do (c): já gravada com http:// — a validação do
        # `clean()` só roda no form do admin, nunca em `Application.objects.create()` —,
        # `skip_authorization=True` para que o GET de /o/authorize/ tente redirecionar
        # direto, sem tela de consentimento no meio.
        aplicacao_http_com_skip = Application.objects.create(
            name="fixture-t04c-http-skip",
            client_id="fixture-t04c-http-skip-client",
            client_type="public",
            authorization_grant_type="authorization-code",
            algorithm="RS256",
            redirect_uris="http://localhost:5173/callback",
            skip_authorization=True,
            user=self.superuser,
        )

        esquema_https_only = {
            **settings.OAUTH2_PROVIDER,
            "ALLOWED_REDIRECT_URI_SCHEMES": ["https"],
        }

        with override_settings(OAUTH2_PROVIDER=esquema_https_only):
            # (a) change com http:// é recusado: 200, erro em redirect_uris, valor
            # anterior mantido.
            resposta_change_http = self.client.post(
                f"/admin/oauth2_provider/application/{self.aplicacao_existente.pk}/change/",
                _dados_de_application(
                    self.superuser,
                    client_id=self.aplicacao_existente.client_id,
                    redirect_uris="http://localhost:5173/callback",
                ),
            )
            self.assertEqual(resposta_change_http.status_code, 200)
            self.assertIn(
                "redirect_uris", resposta_change_http.context["adminform"].form.errors
            )
            self.aplicacao_existente.refresh_from_db()
            self.assertEqual(
                self.aplicacao_existente.redirect_uris, "https://previo.example/callback"
            )

            # (a) add com http:// é recusado: 200, erro em redirect_uris, contagem
            # inalterada.
            contagem_antes_do_add = Application.objects.count()
            resposta_add_http = self.client.post(
                "/admin/oauth2_provider/application/add/",
                _dados_de_application(
                    self.superuser,
                    client_id="fixture-t04-add-http",
                    redirect_uris="http://localhost:5173/callback",
                ),
            )
            self.assertEqual(resposta_add_http.status_code, 200)
            self.assertIn(
                "redirect_uris", resposta_add_http.context["adminform"].form.errors
            )
            self.assertEqual(Application.objects.count(), contagem_antes_do_add)

            # (b) change com https:// é aceito: 302, gravado.
            resposta_change_https = self.client.post(
                f"/admin/oauth2_provider/application/{self.aplicacao_existente.pk}/change/",
                _dados_de_application(
                    self.superuser,
                    client_id=self.aplicacao_existente.client_id,
                    redirect_uris="https://spa.example/callback",
                ),
            )
            self.assertEqual(resposta_change_https.status_code, 302)
            self.aplicacao_existente.refresh_from_db()
            self.assertEqual(
                self.aplicacao_existente.redirect_uris, "https://spa.example/callback"
            )

            # (b) add com https:// é aceito: 302, gravado.
            resposta_add_https = self.client.post(
                "/admin/oauth2_provider/application/add/",
                _dados_de_application(
                    self.superuser,
                    client_id="fixture-t04-add-https",
                    redirect_uris="https://spa.example/callback",
                ),
            )
            self.assertEqual(resposta_add_https.status_code, 302)
            self.assertTrue(
                Application.objects.filter(client_id="fixture-t04-add-https").exists()
            )

            # (c) GET /o/authorize/ para a redirect_uri http:// já gravada: 400, sem
            # Location, sem "code=" no corpo. O comentário do enunciado do T-04 registra
            # que este GET grava um Grant antes de a exceção interromper o
            # redirecionamento — por isso nenhuma asserção aqui conta linhas de Grant.
            _verifier, challenge = make_pkce_pair()
            resposta_authorize = self.client.get(
                "/o/authorize/",
                {
                    "response_type": "code",
                    "client_id": aplicacao_http_com_skip.client_id,
                    "redirect_uri": "http://localhost:5173/callback",
                    "scope": "openid",
                    "state": "t04c-state",
                    "code_challenge": challenge,
                    "code_challenge_method": "S256",
                    "nonce": "t04c-nonce",
                },
            )
            self.assertEqual(resposta_authorize.status_code, 400)
            self.assertIsNone(resposta_authorize.get("Location"))
            self.assertNotIn("code=", resposta_authorize.content.decode())

        # (d) — fora do bloco: override_settings desfez a troca, e oauth2_settings
        # recarregou pelo mesmo sinal que o entrar já disparou.
        self.assertEqual(oauth2_settings.ALLOWED_REDIRECT_URI_SCHEMES, ["http", "https"])

    def test_e_sob_esquema_neutro_da_suite_http_e_aceito_e_o_authorize_emite_code(self):
        """T-05 — SEM `override_settings`: o valor vigente é o que `tests/runner.py`
        (T-01) já neutraliza para a suíte inteira, `["http", "https"]`."""
        resposta_change = self.client.post(
            f"/admin/oauth2_provider/application/{self.aplicacao_existente.pk}/change/",
            _dados_de_application(
                self.superuser,
                client_id=self.aplicacao_existente.client_id,
                redirect_uris="http://localhost:5173/callback",
            ),
        )
        self.assertEqual(resposta_change.status_code, 302)
        self.aplicacao_existente.refresh_from_db()
        self.assertEqual(
            self.aplicacao_existente.redirect_uris, "http://localhost:5173/callback"
        )

        self.client.force_login(self.superuser)
        code, _verifier, resposta_authorize = authorize_and_get_code(
            self.client,
            self.aplicacao_existente,
            redirect_uri="http://localhost:5173/callback",
            scope="openid",
        )
        self.assertIsNotNone(code)
        self.assertEqual(resposta_authorize.status_code, 302)
        self.assertIn("code=", resposta_authorize.get("Location", ""))


class AdminApplicationCrudTests(TestCase):
    """TASK-019/T-12 — as quatro views de gestão do admin (lista, add, change, delete)
    respondendo sob superusuário, e o preço de dívida aceito pela ADR 0024: o botão
    "View on site" (`viewsitelink`) do change renderiza, porque `view_on_site` do
    `ModelAdmin` segue `True` por default, mas o clique responde 500 — `Application.
    get_absolute_url()` reverte `oauth2_provider:detail`, rota que a ADR 0024 retirou do
    URLConf ao deixar `management_urlpatterns` fora do include. Não é comportamento
    desejado: é a dívida que a seção "Consequências negativas" daquela ADR registra e
    aceita explicitamente, sem desligar `view_on_site` — este caso existe só para que uma
    correção futura do 500 (ou uma regressão que o transforme em outra coisa, como um
    200 silencioso) não passe despercebida."""

    def setUp(self):
        self.superuser = User.objects.create_superuser(
            email="admin-t12@example.com", password="senha-forte-o-suficiente"
        )
        self.client.force_login(self.superuser)
        self.aplicacao = Application.objects.create(
            name="fixture-t12",
            client_id="fixture-t12-client",
            client_type="public",
            authorization_grant_type="authorization-code",
            algorithm="RS256",
            redirect_uris="https://previo.example/callback",
            user=self.superuser,
        )

    def test_lista_add_change_delete_respondem_200(self):
        caminhos = (
            "/admin/oauth2_provider/application/",
            "/admin/oauth2_provider/application/add/",
            f"/admin/oauth2_provider/application/{self.aplicacao.pk}/change/",
            f"/admin/oauth2_provider/application/{self.aplicacao.pk}/delete/",
        )
        for caminho in caminhos:
            with self.subTest(caminho=caminho):
                resposta = self.client.get(caminho)
                self.assertEqual(resposta.status_code, 200)

    def test_post_de_edicao_valida_redireciona(self):
        resposta = self.client.post(
            f"/admin/oauth2_provider/application/{self.aplicacao.pk}/change/",
            _dados_de_application(
                self.superuser,
                client_id=self.aplicacao.client_id,
                name="fixture-t12-renomeada",
            ),
        )
        self.assertEqual(resposta.status_code, 302)
        self.aplicacao.refresh_from_db()
        self.assertEqual(self.aplicacao.name, "fixture-t12-renomeada")

    def test_change_renderiza_o_link_view_on_site(self):
        # Classe CSS, não o texto: LANGUAGE_CODE="en-us" (config/settings.py) torna o
        # texto "View on site", e o marcador estrutural é o que sobrevive a uma tradução.
        resposta = self.client.get(
            f"/admin/oauth2_provider/application/{self.aplicacao.pk}/change/"
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertIn('class="viewsitelink"', resposta.content.decode())

    def test_o_clique_no_link_view_on_site_e_500_divida_aceita_pela_adr_0024(self):
        content_type_id = ContentType.objects.get_for_model(Application).pk
        # raise_request_exception=False: sem isso o test client propaga a exceção do
        # NoReverseMatch/erro de template para o próprio teste em vez de devolver a
        # resposta 500 que um navegador de verdade receberia.
        self.client.raise_request_exception = False

        resposta = self.client.get(f"/admin/r/{content_type_id}/{self.aplicacao.pk}/")

        self.assertEqual(resposta.status_code, 500)
