"""TASK-027/T-02, T-04 a T-16 e T-18, e TASK-028/T-43 (`RevogarTests`) — o logout iniciado pela relying party (RP) em `/o/logout/`.

Demanda do quality-assurance. `accounts.logout_rp.LogoutPelaRPView` sombreia a rota do toolkit
(ADR 0030) e decide o que o toolkit sozinho não decide (ADR 0029): revoga só na Application que
pede, registra a revogação na trilha, trata como ausente o hint autêntico já sem linha e
responde 400, e não 500, a entradas forjadas.

Nível integração, salvo T-02 e T-15/T-16 (unitários sobre funções do módulo, que ainda assim
precisam do banco para fabricar tokens). Os tokens vêm do fluxo real, Authorization Code com
PKCE; a trilha é lida pelo arquivo real que o runner redireciona, e não por `assertLogs`, que
não vê o `request_id` (posto pelo filtro do handler). Todo destino de fixture é https
(`tests/logout_helpers.py`).
"""

import json
import uuid
from unittest import mock
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client, RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import resolve, reverse
from jwcrypto import jwk
from jwcrypto.common import base64url_encode
from oauth2_provider.exceptions import InvalidIDTokenError
from oauth2_provider.views.oidc import RPInitiatedLogoutView
from oauth2_provider.models import (
    get_access_token_model,
    get_application_model,
    get_id_token_model,
    get_refresh_token_model,
)

from accounts import auditoria, logout_rp, revogacao
from accounts.logout_rp import LogoutPelaRPView
from tests import runner
from tests.oauth_helpers import REDIRECT_URI
from tests.logout_helpers import (
    DESTINO,
    adulterar_assinatura,
    assinar,
    b64,
    chave_do_idp,
    claims_de_hint,
    criar_application,
    emitir_tokens,
    gerar_chave_rsa,
    linhas_da_trilha_desde,
    partes_do_token,
    status_refresh,
    status_userinfo,
    tamanho_da_trilha,
)

User = get_user_model()
Application = get_application_model()
AccessToken = get_access_token_model()
RefreshToken = get_refresh_token_model()
IDToken = get_id_token_model()

SENHA = "senha-forte-o-suficiente-logout"
TELA_DE_ERRO = "Não foi possível sair"
ESQUEMA_DA_LINHA = {
    "event", "sub", "client_id", "ip", "ip_src", "ip_edge", "outcome",
    "ts", "level", "logger", "request_id", "msg",
}  # fmt: skip


def _url(**parametros):
    return "/o/logout/?" + urlencode(parametros)


class RotaDoLogoutTests(SimpleTestCase):
    """T-02. A sombra tem de vir antes do include, e a rota do toolkit tem de continuar dentro
    dele: o `reverse()` do namespace é o que a descoberta usa para montar
    `end_session_endpoint`."""

    def test_reverse_do_toolkit_da_o_caminho_e_o_caminho_resolve_para_a_subclasse(self):
        caminho = reverse("oauth2_provider:rp-initiated-logout")

        self.assertEqual(caminho, "/o/logout/")
        self.assertIs(resolve(caminho).func.view_class, LogoutPelaRPView)

    def test_a_rota_resolvida_e_a_sombra_nomeada_logout_rp(self):
        self.assertEqual(resolve("/o/logout/").url_name, "logout_rp")


class _LogoutBase(TestCase):
    def setUp(self):
        self.a = User.objects.create_user(email="a-logout@example.com", password=SENHA)
        self.b = User.objects.create_user(email="b-logout@example.com", password=SENHA)
        self.app1 = criar_application(self.a, "SPA um")
        self.app2 = criar_application(self.a, "SPA dois")

    def vivos(self, dono, app):
        """Contagem de (access, id_token, refresh sem revoked) de `dono` em `app`."""
        filtro = {"user": dono, "application": app}
        return (
            AccessToken.objects.filter(**filtro).count(),
            IDToken.objects.filter(**filtro).count(),
            RefreshToken.objects.filter(revoked__isnull=True, **filtro).count(),
        )

    def assertSessaoDe(self, client, viva=True):
        self.assertEqual("_auth_user_id" in client.session, viva)

    def eventos(self, linhas, nome):
        return [linha for linha in linhas if linha["event"] == nome]


class SaidaComHintVivoTests(_LogoutBase):
    def test_t04_saida_com_hint_vivo_revoga_na_app_encerra_a_sessao_e_trilha_duas_linhas(self):
        client, tokens = emitir_tokens(self.a, self.app1)
        antes = tamanho_da_trilha()

        resposta = client.get(
            _url(
                id_token_hint=tokens["id_token"],
                post_logout_redirect_uri=DESTINO,
                state="s",
            )
        )

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta["Location"], DESTINO + "?state=s")
        self.assertSessaoDe(client, viva=False)
        self.assertIn("Nenhuma sessão ativa", client.get("/").content.decode())
        self.assertEqual(self.vivos(self.a, self.app1), (0, 0, 0))

        linhas = linhas_da_trilha_desde(antes)
        self.assertEqual([l["event"] for l in linhas], ["tokens_revogados", "user_logged_out"], linhas)
        revogacao, saida = linhas
        self.assertEqual(revogacao["sub"], str(self.a.sub))
        self.assertNotEqual(revogacao["sub"], str(self.a.pk))
        self.assertEqual(revogacao["client_id"], self.app1.client_id)
        self.assertEqual(revogacao["outcome"], "success")
        for chave in ("ip", "ip_src", "ip_edge"):
            self.assertIn(chave, revogacao)
        self.assertEqual(revogacao["request_id"], saida["request_id"])
        self.assertNotEqual(revogacao["request_id"], "-")
        # Esquema fixo, sem contagem, jti nem token.
        self.assertEqual(set(revogacao), ESQUEMA_DA_LINHA)

    def test_t05_o_que_a_saida_derrubou_fica_derrubado_e_o_hint_gasto_nao_revoga_de_novo(self):
        client, tokens = emitir_tokens(self.a, self.app1)
        client.get(
            _url(id_token_hint=tokens["id_token"], post_logout_redirect_uri=DESTINO, state="s1")
        )

        self.assertEqual(status_userinfo(tokens["access_token"]), 401)
        self.assertEqual(status_refresh(self.app1, tokens["refresh_token"]), 400)

        antes = tamanho_da_trilha()
        sem_sessao = Client().get(
            _url(id_token_hint=tokens["id_token"], post_logout_redirect_uri=DESTINO, state="s2")
        )
        self.assertEqual(sem_sessao.status_code, 302)
        self.assertEqual(sem_sessao["Location"], DESTINO + "?state=s2")
        self.assertEqual(self.eventos(linhas_da_trilha_desde(antes), "tokens_revogados"), [])

        nova = Client()
        nova.force_login(self.a)
        com_sessao = nova.get(
            _url(id_token_hint=tokens["id_token"], post_logout_redirect_uri=DESTINO, state="s3")
        )
        self.assertEqual(com_sessao.status_code, 200)
        self.assertIn("Sair?", com_sessao.content.decode())
        self.assertSessaoDe(nova)

    def test_t06_a_saida_na_app1_nao_toca_os_tokens_da_app2(self):
        client, tokens1 = emitir_tokens(self.a, self.app1)
        _, tokens2 = emitir_tokens(self.a, self.app2, client=client)

        client.get(
            _url(id_token_hint=tokens1["id_token"], post_logout_redirect_uri=DESTINO, state="s")
        )

        self.assertEqual(status_userinfo(tokens1["access_token"]), 401)
        self.assertEqual(status_userinfo(tokens2["access_token"]), 200)
        self.assertEqual(status_refresh(self.app2, tokens2["refresh_token"]), 200)

    def test_t06_controle_com_delete_tokens_ligada_a_app2_tambem_cai(self):
        """Controle: prova que o teste acima distingue a configuração de produção da que o
        toolkit usaria para revogar a conta inteira."""
        client, tokens1 = emitir_tokens(self.a, self.app1)
        _, tokens2 = emitir_tokens(self.a, self.app2, client=client)
        ligada = {
            **settings.OAUTH2_PROVIDER,
            "OIDC_RP_INITIATED_LOGOUT_DELETE_TOKENS": True,
        }

        with override_settings(OAUTH2_PROVIDER=ligada):
            client.get(
                _url(
                    id_token_hint=tokens1["id_token"],
                    post_logout_redirect_uri=DESTINO,
                    state="s",
                )
            )

        self.assertEqual(status_userinfo(tokens2["access_token"]), 401)


class DestinoTests(_LogoutBase):
    def _hint_vivo(self):
        client, tokens = emitir_tokens(self.a, self.app1)
        return client, tokens

    def _assertRecusa(self, client, tokens, resposta):
        self.assertEqual(resposta.status_code, 400)
        self.assertIn(TELA_DE_ERRO, resposta.content.decode())
        self.assertFalse(resposta.has_header("Location"))
        self.assertSessaoDe(client)
        self.assertEqual(status_userinfo(tokens["access_token"]), 200)

    def test_t07_destino_nao_cadastrado_ou_sem_a_barra_final_e_400_e_nada_muda(self):
        client, tokens = self._hint_vivo()
        antes = tamanho_da_trilha()

        for destino in ("https://evil.example/", "https://landing.example"):
            with self.subTest(destino=destino):
                resposta = client.get(
                    _url(
                        id_token_hint=tokens["id_token"],
                        post_logout_redirect_uri=destino,
                        state="s",
                    )
                )
                self._assertRecusa(client, tokens, resposta)

        self.assertEqual(self.eventos(linhas_da_trilha_desde(antes), "tokens_revogados"), [])

    def test_t08_destino_http_recusado_por_strict_e_por_esquema_e_aceito_no_controle(self):
        self.app1.post_logout_redirect_uris = "https://landing.example/ http://landing.example/"
        self.app1.save()
        client, tokens = self._hint_vivo()
        http = "http://landing.example/"
        consulta = _url(id_token_hint=tokens["id_token"], post_logout_redirect_uri=http, state="s")
        base = settings.OAUTH2_PROVIDER
        chave_strict = "OIDC_RP_INITIATED_LOGOUT_STRICT_REDIRECT_URIS"

        casos = (
            ("strict", {**base, chave_strict: True, "ALLOWED_REDIRECT_URI_SCHEMES": ["http", "https"]}),
            ("esquema", {**base, chave_strict: False, "ALLOWED_REDIRECT_URI_SCHEMES": ["https"]}),
        )
        for nome, configuracao in casos:
            with self.subTest(caso=nome), override_settings(OAUTH2_PROVIDER=configuracao):
                resposta = client.get(consulta)
                self._assertRecusa(client, tokens, resposta)

        controle = {**base, chave_strict: False, "ALLOWED_REDIRECT_URI_SCHEMES": ["http", "https"]}
        with override_settings(OAUTH2_PROVIDER=controle):
            resposta = client.get(consulta)
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta["Location"], http + "?state=s")


class ConfirmacaoTests(_LogoutBase):
    def test_t09_sem_hint_a_pessoa_confirma_e_so_o_allow_encerra(self):
        client, tokens = emitir_tokens(self.a, self.app1)
        pedido = {"client_id": self.app1.client_id, "post_logout_redirect_uri": DESTINO, "state": "s"}

        resposta = client.get(_url(**pedido))

        corpo = resposta.content.decode()
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("Sair?", corpo)
        self.assertIn(self.app1.name, corpo)
        self.assertEqual(corpo.count('name="allow"'), 1)
        self.assertIn("csrfmiddlewaretoken", corpo)
        from tests.oauth_helpers import extract_hidden_inputs

        ocultos = extract_hidden_inputs(corpo)
        for chave, valor in pedido.items():
            self.assertEqual(ocultos.get(chave), valor, chave)
        self.assertSessaoDe(client)
        self.assertEqual(status_userinfo(tokens["access_token"]), 200)

        # Sem token de CSRF (Cross-Site Request Forgery): 403 e sessão intacta.
        com_csrf = Client(enforce_csrf_checks=True)
        com_csrf.force_login(self.a)
        self.assertEqual(com_csrf.post("/o/logout/", {**pedido, "allow": "Sair"}).status_code, 403)
        self.assertSessaoDe(com_csrf)

        # Cancelar: o botão sem `name="allow"`.
        cancelada = client.post("/o/logout/", pedido)
        self.assertEqual(cancelada.status_code, 400)
        self.assertIn("Saída cancelada", cancelada.content.decode())
        self.assertSessaoDe(client)
        self.assertEqual(status_userinfo(tokens["access_token"]), 200)

        antes = tamanho_da_trilha()
        confirmada = client.post("/o/logout/", {**pedido, "allow": "Sair"})
        self.assertEqual(confirmada.status_code, 302)
        self.assertEqual(confirmada["Location"], DESTINO + "?state=s")
        self.assertSessaoDe(client, viva=False)
        self.assertEqual(status_userinfo(tokens["access_token"]), 401)
        revogadas = self.eventos(linhas_da_trilha_desde(antes), "tokens_revogados")
        self.assertEqual([l["sub"] for l in revogadas], [str(self.a.sub)])
        self.assertNotIn(str(self.a.pk), [l["sub"] for l in revogadas])

    def test_t09_sem_client_id_e_sem_destino_so_encerra_a_sessao(self):
        client, tokens = emitir_tokens(self.a, self.app1)
        antes = tamanho_da_trilha()

        resposta = client.post("/o/logout/", {"allow": "Sair"})

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta["Location"], "http://testserver/")
        self.assertSessaoDe(client, viva=False)
        self.assertEqual(status_userinfo(tokens["access_token"]), 200)
        self.assertEqual(self.eventos(linhas_da_trilha_desde(antes), "tokens_revogados"), [])

    def test_t10_hint_de_outra_conta_pede_confirmacao_e_revoga_a_do_hint_nao_a_da_sessao(self):
        cliente_a, tokens_a = emitir_tokens(self.a, self.app1)
        _, tokens_b = emitir_tokens(self.b, self.app1)
        pedido = {
            "id_token_hint": tokens_b["id_token"],
            "post_logout_redirect_uri": DESTINO,
            "state": "s",
        }

        conferencia = cliente_a.get(_url(**pedido))
        self.assertEqual(conferencia.status_code, 200)
        self.assertIn("Sair?", conferencia.content.decode())

        antes = tamanho_da_trilha()
        resposta = cliente_a.post("/o/logout/", {**pedido, "allow": "Sair"})

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(status_userinfo(tokens_b["access_token"]), 401)
        self.assertEqual(status_userinfo(tokens_a["access_token"]), 200)
        self.assertSessaoDe(cliente_a, viva=False)
        linhas = linhas_da_trilha_desde(antes)
        self.assertEqual([l["event"] for l in linhas], ["tokens_revogados", "user_logged_out"], linhas)
        self.assertEqual(linhas[0]["sub"], str(self.b.sub))
        self.assertEqual(linhas[1]["sub"], str(self.a.sub))
        self.assertNotEqual(linhas[0]["sub"], str(self.b.pk))
        self.assertNotEqual(linhas[1]["sub"], str(self.a.pk))
        self.assertEqual(linhas[0]["request_id"], linhas[1]["request_id"])


class HintForjadoTests(_LogoutBase):
    def setUp(self):
        super().setUp()
        self.cliente, self.tokens = emitir_tokens(self.a, self.app1)
        self.cabecalho, self.claims, self.assinatura = partes_do_token(self.tokens["id_token"])
        self.issuer = self.claims["iss"]

    def _hints_t11(self):
        h, p, s = self.tokens["id_token"].split(".")
        adulterada = dict(self.claims, sub="999")
        outra_chave = gerar_chave_rsa(self.cabecalho["kid"])
        do_idp = chave_do_idp()
        return {
            "assinatura adulterada": adulterar_assinatura(self.tokens["id_token"]),
            "carga adulterada": ".".join([h, b64(json.dumps(adulterada).encode()), s]),
            "chave anterior": assinar(
                outra_chave, self.cabecalho, claims_de_hint(self.issuer, self.app1.client_id)
            ),
            "iss diferente, jti com linha": assinar(
                do_idp,
                self.cabecalho,
                claims_de_hint("https://outro.example/o", self.app1.client_id, self.claims["jti"]),
            ),
            "iss diferente, jti aleatório": assinar(
                do_idp,
                self.cabecalho,
                claims_de_hint("https://outro.example/o", self.app1.client_id),
            ),
            "lixo": "abc",
        }

    def _assertRecusaSemEfeito(self, client, hint, resposta):
        corpo = resposta.content.decode()
        self.assertEqual(resposta.status_code, 400)
        self.assertIn(TELA_DE_ERRO, corpo)
        self.assertNotIn("ID Token is", corpo)
        self.assertNotIn(hint, corpo)

    def test_t11_hint_que_nao_e_deste_idp_e_400_sem_revogar_com_e_sem_sessao(self):
        antes = tamanho_da_trilha()
        for nome, hint in self._hints_t11().items():
            with self.subTest(hint=nome, sessao=False):
                resposta = Client().get(
                    _url(id_token_hint=hint, post_logout_redirect_uri=DESTINO, state="s")
                )
                self._assertRecusaSemEfeito(None, hint, resposta)

        hint = adulterar_assinatura(self.tokens["id_token"])
        with self.subTest(hint="assinatura adulterada", sessao=True):
            resposta = self.cliente.get(
                _url(id_token_hint=hint, post_logout_redirect_uri=DESTINO, state="s")
            )
            self._assertRecusaSemEfeito(self.cliente, hint, resposta)
            self.assertSessaoDe(self.cliente)

        self.assertEqual(status_userinfo(self.tokens["access_token"]), 200)
        self.assertEqual(self.vivos(self.a, self.app1), (1, 1, 1))
        self.assertEqual(self.eventos(linhas_da_trilha_desde(antes), "tokens_revogados"), [])

    def _hints_t12(self):
        h, p, s = self.tokens["id_token"].split(".")
        sem_algoritmo = criar_application(self.a, "sem algoritmo")
        sem_algoritmo.algorithm = ""
        sem_algoritmo.save()
        return {
            "nao json": ".".join([h, b64(b"not json"), s]),
            "carga 5": ".".join([h, b64(b"5"), s]),
            "aud 5": ".".join([h, b64(json.dumps(dict(self.claims, aud=5)).encode()), s]),
            "aud sem algoritmo": ".".join(
                [h, b64(json.dumps(dict(self.claims, aud=sem_algoritmo.client_id)).encode()), s]
            ),
            "carga nao utf8": ".".join([h, b64(b"\xff\xfe"), s]),
            "json sem payload": json.dumps({"protected": h, "signature": s}),
        }

    def test_t12_entrada_forjada_e_400_nunca_500_e_o_log_nao_traz_o_hint(self):
        for nome, hint in self._hints_t12().items():
            with self.subTest(hint=nome):
                with self.assertLogs("accounts.logout_rp", "WARNING") as capturado:
                    try:
                        resposta = self.cliente.get(
                            _url(id_token_hint=hint, post_logout_redirect_uri=DESTINO, state="s")
                        )
                    except Exception as erro:  # 500 no test client sobe como exceção
                        self.fail(f"o pedido levantou {type(erro).__name__}")
                self._assertRecusaSemEfeito(self.cliente, hint, resposta)
                for registro in capturado.records:
                    self.assertTrue(hasattr(registro, "error_class"))
                    self.assertNotIn(hint, registro.getMessage())
                    self.assertNotIn(hint, str(registro.__dict__))

        self.assertSessaoDe(self.cliente)
        self.assertEqual(self.vivos(self.a, self.app1), (1, 1, 1))

    def test_t12_client_id_inexistente_e_400_com_e_sem_destino(self):
        for parametros in (
            {"client_id": "nao-existe", "post_logout_redirect_uri": DESTINO},
            {"client_id": "nao-existe"},
        ):
            with self.subTest(parametros=parametros):
                resposta = Client().get(_url(**parametros))
                self.assertEqual(resposta.status_code, 400)
                self.assertIn(TELA_DE_ERRO, resposta.content.decode())


class EntradaForjadaAmpliadaTests(_LogoutBase):
    """TASK-027/AC-18 ampliado — entradas que o toolkit deixaria chegar a 500: NUL em
    `client_id` e em `aud`, destino que não se decompõe como URL e `jti` que não é UUID.

    `test_ii` e `test_v` provam o 400 diante do NUL, e nada além disso: o psycopg 3 recusa o
    NUL no CLIENTE, antes de a consulta chegar ao servidor, então a conexão nunca fica marcada
    e os dois passam com ou sem os `transaction.atomic()` da view. O savepoint é provado por
    `SavepointDaEntradaForjadaTests`, abaixo, com um `DataError` do SERVIDOR. A consulta a
    `GET /` depois do 400 fica aqui como conferência barata de que a conexão segue utilizável.
    """

    def setUp(self):
        super().setUp()
        self.cliente, self.tokens = emitir_tokens(self.a, self.app1)
        self.cabecalho, self.claims, _ = partes_do_token(self.tokens["id_token"])

    def _pedir(self, **parametros):
        try:
            return self.cliente.get(_url(**parametros))
        except Exception as erro:  # 500 no test client sobe como exceção
            self.fail(f"o pedido levantou {type(erro).__name__}: {erro}")

    def _assertRecusadoSemEfeito(self, resposta, antes):
        self.assertEqual(resposta.status_code, 400)
        self.assertIn(TELA_DE_ERRO, resposta.content.decode())
        # Consulta ao banco depois do 400: prova que a conexão continua utilizável.
        self.assertIn(self.a.email, self.cliente.get("/").content.decode())
        self.assertSessaoDe(self.cliente)
        self.assertEqual(status_userinfo(self.tokens["access_token"]), 200)
        self.assertEqual(self.vivos(self.a, self.app1), (1, 1, 1))
        self.assertEqual(self.eventos(linhas_da_trilha_desde(antes), "tokens_revogados"), [])

    def test_ii_client_id_com_nul(self):
        antes = tamanho_da_trilha()
        self._assertRecusadoSemEfeito(self._pedir(client_id="\x00"), antes)

    def test_v_hint_com_aud_nul(self):
        h, _, s = self.tokens["id_token"].split(".")
        hint = ".".join([h, b64(json.dumps({"aud": "\u0000"}).encode()), s])
        antes = tamanho_da_trilha()

        self._assertRecusadoSemEfeito(self._pedir(id_token_hint=hint), antes)

    def test_vi_e_vii_destino_que_nao_se_decompoe_como_url(self):
        antes = tamanho_da_trilha()
        for destino in ("https://[x", "https://x:99999/", "https://x:abc/"):
            with self.subTest(destino=destino):
                resposta = self._pedir(
                    client_id=self.app1.client_id, post_logout_redirect_uri=destino
                )
                self._assertRecusadoSemEfeito(resposta, antes)

    def test_viii_hint_hs256_com_jti_que_nao_e_uuid(self):
        # 32 bytes no mínimo: o jwcrypto exige 256 bits de chave para HS256.
        segredo = "segredo-hs256-do-teste-t-viii-com-mais-de-32-bytes"
        confidencial = Application.objects.create(
            name="confidencial HS256",
            client_type="confidential",
            authorization_grant_type="authorization-code",
            algorithm="HS256",
            redirect_uris=REDIRECT_URI,
            post_logout_redirect_uris=DESTINO,
            client_secret=segredo,
            hash_client_secret=False,
            user=self.a,
        )
        chave = jwk.JWK(kty="oct", k=base64url_encode(segredo))
        claims = claims_de_hint(self.claims["iss"], confidencial.client_id, jti="nao-e-uuid")
        hint = assinar(chave, {"alg": "HS256"}, claims)
        antes = tamanho_da_trilha()

        self._assertRecusadoSemEfeito(self._pedir(id_token_hint=hint), antes)


def _erro_de_dados_do_servidor(*args, **kwargs):
    """`DataError` que só o SERVIDOR levanta (divisão por zero): o psycopg 3 não a antecipa
    no cliente, como faz com o NUL, e por isso ela deixa a transação corrente marcada."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1/0")


class SavepointDaEntradaForjadaTests(_LogoutBase):
    """TASK-027/T-22 — prova dos três savepoints de `accounts/logout_rp.py`.

    `TestCase` roda dentro de um bloco atômico externo, o que reproduz o que um
    `ATOMIC_REQUESTS` futuro faria. Um `DataError` do servidor, capturado pela view FORA do
    savepoint, deixaria a conexão abortada, e a consulta seguinte (`GET /`) levantaria
    `InternalError` ("current transaction is aborted"). Com o savepoint, a view responde 400 e a conexão continua
    utilizável. Cada caso passa por UM savepoint só, e cai se o seu `transaction.atomic()`
    for removido.

    O alvo dos patches é `RPInitiatedLogoutView`, a classe do toolkit: o `super()` da
    subclasse a resolve em tempo de chamada, então o patch alcança a chamada que o savepoint
    envolve.
    """

    def setUp(self):
        super().setUp()
        self.cliente, self.tokens = emitir_tokens(self.a, self.app1)

    def _assertRecusadoComConexaoViva(self, resposta, antes):
        self.assertEqual(resposta.status_code, 400)
        self.assertIn(TELA_DE_ERRO, resposta.content.decode())
        # A consulta que só funciona se o savepoint desfez a transação abortada.
        self.assertIn(self.a.email, self.cliente.get("/").content.decode())
        self.assertSessaoDe(self.cliente)
        self.assertEqual(status_userinfo(self.tokens["access_token"]), 200)
        self.assertEqual(self.vivos(self.a, self.app1), (1, 1, 1))
        self.assertEqual(self.eventos(linhas_da_trilha_desde(antes), "tokens_revogados"), [])

    def test_a_savepoint_do_super_de_get_request_application(self):
        antes = tamanho_da_trilha()

        with mock.patch.object(
            RPInitiatedLogoutView,
            "get_request_application",
            side_effect=_erro_de_dados_do_servidor,
        ):
            resposta = self.cliente.get(_url(client_id=self.app1.client_id))

        self._assertRecusadoComConexaoViva(resposta, antes)

    def test_b_savepoint_do_super_de_validate_logout_request_user(self):
        antes = tamanho_da_trilha()

        with mock.patch.object(
            RPInitiatedLogoutView,
            "validate_logout_request_user",
            side_effect=_erro_de_dados_do_servidor,
        ):
            resposta = self.cliente.get(_url(id_token_hint="abc"))

        self._assertRecusadoComConexaoViva(resposta, antes)

    def test_c_savepoint_do_corpo_de_aplicacao_do_hint_sem_linha(self):
        cabecalho, claims, _ = partes_do_token(self.tokens["id_token"])
        # Autêntico e sem linha: chega ao desempate e à consulta de `aud`, que o patch derruba.
        hint = assinar(
            chave_do_idp(), cabecalho, claims_de_hint(claims["iss"], self.app1.client_id)
        )
        antes = tamanho_da_trilha()

        # O primeiro patch tira o savepoint (b) do caminho, para o erro só passar pelo (c).
        with (
            mock.patch.object(
                RPInitiatedLogoutView,
                "validate_logout_request_user",
                side_effect=InvalidIDTokenError(),
            ),
            mock.patch(
                "oauth2_provider.oauth2_validators.OAuth2Validator._get_client_by_audience",
                side_effect=_erro_de_dados_do_servidor,
            ),
        ):
            resposta = self.cliente.get(_url(id_token_hint=hint))

        self._assertRecusadoComConexaoViva(resposta, antes)


class HintVencidoTests(_LogoutBase):
    def _emitir_vencido(self):
        vencido = {**settings.OAUTH2_PROVIDER, "ID_TOKEN_EXPIRE_SECONDS": -3600}
        with override_settings(OAUTH2_PROVIDER=vencido):
            return emitir_tokens(self.a, self.app1)

    def test_t13_hint_vencido_sai_no_default_de_producao_e_e_recusado_sem_aceitar_vencidos(self):
        client, tokens = self._emitir_vencido()
        pedido = _url(
            id_token_hint=tokens["id_token"], post_logout_redirect_uri=DESTINO, state="s"
        )

        rigido = {
            **settings.OAUTH2_PROVIDER,
            "OIDC_RP_INITIATED_LOGOUT_ACCEPT_EXPIRED_TOKENS": False,
        }
        with override_settings(OAUTH2_PROVIDER=rigido):
            controle = client.get(pedido)
        self.assertEqual(controle.status_code, 400)
        self.assertSessaoDe(client)
        self.assertEqual(status_userinfo(tokens["access_token"]), 200)

        resposta = client.get(pedido)
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta["Location"], DESTINO + "?state=s")
        self.assertEqual(status_userinfo(tokens["access_token"]), 401)


class HintSemLinhaTests(_LogoutBase):
    def _pedido(self, tokens, **extra):
        return _url(
            id_token_hint=tokens["id_token"],
            post_logout_redirect_uri=DESTINO,
            state="s",
            **extra,
        )

    def test_t14a_sem_sessao_o_hint_vivo_revoga_o_dono_e_a_saida_sai_sem_sub(self):
        _, tokens = emitir_tokens(self.a, self.app1)
        antes = tamanho_da_trilha()

        resposta = Client().get(self._pedido(tokens))

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta["Location"], DESTINO + "?state=s")
        self.assertEqual(status_userinfo(tokens["access_token"]), 401)
        linhas = linhas_da_trilha_desde(antes)
        self.assertEqual([l["event"] for l in linhas], ["tokens_revogados", "user_logged_out"], linhas)
        self.assertEqual(linhas[0]["sub"], str(self.a.sub))
        self.assertNotEqual(linhas[0]["sub"], str(self.a.pk))
        self.assertEqual(linhas[0]["client_id"], self.app1.client_id)
        self.assertIsNone(linhas[1]["sub"])
        self.assertEqual(linhas[0]["request_id"], linhas[1]["request_id"])

    def test_t14bcd_hint_autentico_sem_linha_sai_mas_nao_revoga_e_o_client_id_tem_de_bater(self):
        cliente, tokens = emitir_tokens(self.a, self.app1)
        # É o teste que apaga a linha, para fabricar o hint autêntico sem linha. O
        # `cleartokens` não faz isso: só apaga IDToken com `access_token` nulo
        # (`oauth2_provider/models.py:1296-1300`).
        IDToken.objects.filter(application=self.app1).delete()
        antes = tamanho_da_trilha()

        sem_sessao = Client().get(self._pedido(tokens))

        self.assertEqual(sem_sessao.status_code, 302)
        self.assertEqual(sem_sessao["Location"], DESTINO + "?state=s")
        self.assertEqual(self.eventos(linhas_da_trilha_desde(antes), "tokens_revogados"), [])
        # O refresh continua sem revogação. Não se afirma 200 no /o/token/: com o AccessToken
        # apagado em cascata junto do IDToken, o toolkit recusa o refresh órfão por conta
        # própria (invalid_grant), e isso não é decisão desta view.
        self.assertEqual(
            RefreshToken.objects.filter(application=self.app1, revoked__isnull=True).count(), 1
        )

        divergente = Client().get(self._pedido(tokens, client_id=self.app2.client_id))
        self.assertEqual(divergente.status_code, 400)

        com_sessao = cliente.get(self._pedido(tokens))
        self.assertEqual(com_sessao.status_code, 200)
        self.assertIn("Sair?", com_sessao.content.decode())

    def test_t14e_hint_sem_linha_de_b_com_sessao_de_a_nunca_revoga_b(self):
        cliente_a, tokens_a = emitir_tokens(self.a, self.app1)
        _, tokens_b = emitir_tokens(self.b, self.app1)
        # Troca o jti da linha de B em vez de apagá-la: o hint continua autêntico e sem
        # linha, e os tokens de B seguem inteiros, o que permite afirmar 200 no refresh dele.
        IDToken.objects.filter(user=self.b).update(jti=uuid.uuid4())
        pedido = {
            "id_token_hint": tokens_b["id_token"],
            "post_logout_redirect_uri": DESTINO,
            "state": "s",
        }
        antes = tamanho_da_trilha()

        resposta = cliente_a.post("/o/logout/", {**pedido, "allow": "Sair"})

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(status_userinfo(tokens_a["access_token"]), 401)
        self.assertEqual(status_userinfo(tokens_b["access_token"]), 200)
        self.assertEqual(status_refresh(self.app1, tokens_b["refresh_token"]), 200)
        revogadas = self.eventos(linhas_da_trilha_desde(antes), "tokens_revogados")
        self.assertEqual([l["sub"] for l in revogadas], [str(self.a.sub)])
        self.assertNotIn(str(self.a.pk), [l["sub"] for l in revogadas])

    def test_t14f_so_client_id_sem_sessao_com_destino_sai_sem_revogar(self):
        _, tokens = emitir_tokens(self.a, self.app1)
        antes = tamanho_da_trilha()

        resposta = Client().get(
            _url(client_id=self.app1.client_id, post_logout_redirect_uri=DESTINO, state="s")
        )

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(status_userinfo(tokens["access_token"]), 200)
        self.assertEqual(self.eventos(linhas_da_trilha_desde(antes), "tokens_revogados"), [])


class RevogarTests(_LogoutBase):
    """T-15, ajustado por TASK-028/T-43. `accounts.revogacao._revogar(dono, aplicacao=None)`
    devolve a lista das Applications em que havia token, sem repetição, e `revogar_tokens`
    emite `tokens_revogados` uma vez por Application dessa lista."""

    def test_a_sem_tokens_devolve_lista_vazia(self):
        self.assertEqual(revogacao._revogar(self.a, self.app1), [])

    def test_b_revoga_os_tres_tipos_e_devolve_a_application(self):
        emitir_tokens(self.a, self.app1)

        self.assertEqual(revogacao._revogar(self.a, self.app1), [self.app1])
        self.assertEqual(self.vivos(self.a, self.app1), (0, 0, 0))

    def test_c_so_toca_o_par_dono_e_aplicacao(self):
        emitir_tokens(self.a, self.app1)
        emitir_tokens(self.a, self.app2)
        emitir_tokens(self.b, self.app1)

        revogacao._revogar(self.a, self.app1)

        self.assertEqual(self.vivos(self.a, self.app1), (0, 0, 0))
        self.assertEqual(self.vivos(self.a, self.app2), (1, 1, 1))
        self.assertEqual(self.vivos(self.b, self.app1), (1, 1, 1))

    def test_d_refresh_orfao_e_revogado(self):
        emitir_tokens(self.a, self.app1)
        IDToken.objects.filter(user=self.a).delete()
        AccessToken.objects.filter(user=self.a).delete()
        self.assertEqual(self.vivos(self.a, self.app1), (0, 0, 1))

        self.assertEqual(revogacao._revogar(self.a, self.app1), [self.app1])
        self.assertEqual(self.vivos(self.a, self.app1), (0, 0, 0))

    def test_e_sem_aplicacao_revoga_em_todas_e_devolve_cada_uma_uma_vez(self):
        """Vermelho se `aplicacao=None` passar a filtrar, ou se a lista repetir a Application
        (cada uma tem três tipos de token, e a deduplicação é o que a limita a uma emissão)."""
        emitir_tokens(self.a, self.app1)
        emitir_tokens(self.a, self.app2)
        emitir_tokens(self.b, self.app1)

        afetadas = revogacao._revogar(self.a)

        self.assertCountEqual(afetadas, [self.app1, self.app2])
        self.assertEqual(self.vivos(self.a, self.app1), (0, 0, 0))
        self.assertEqual(self.vivos(self.a, self.app2), (0, 0, 0))
        self.assertEqual(self.vivos(self.b, self.app1), (1, 1, 1))

    def _emissoes(self, chamada):
        emitidas = []

        def receptor(sender, **kwargs):
            emitidas.append(kwargs)

        revogacao.tokens_revogados.connect(receptor, weak=False, dispatch_uid="t43")
        try:
            chamada()
        finally:
            revogacao.tokens_revogados.disconnect(dispatch_uid="t43")
        return emitidas

    def test_f_revogar_tokens_emite_uma_vez_por_application_afetada(self):
        emitir_tokens(self.a, self.app1)
        emitir_tokens(self.a, self.app2)
        pedido = RequestFactory().get("/")

        emitidas = self._emissoes(lambda: revogacao.revogar_tokens(pedido, self.a))

        self.assertEqual(len(emitidas), 2, emitidas)
        self.assertCountEqual([e["application"] for e in emitidas], [self.app1, self.app2])
        for emissao in emitidas:
            self.assertIs(emissao["request"], pedido)
            self.assertEqual(emissao["user"], self.a)

    def test_g_revogar_tokens_com_aplicacao_emite_so_para_ela(self):
        emitir_tokens(self.a, self.app1)
        emitir_tokens(self.a, self.app2)

        emitidas = self._emissoes(
            lambda: revogacao.revogar_tokens(RequestFactory().get("/"), self.a, self.app1)
        )

        self.assertEqual([e["application"] for e in emitidas], [self.app1])
        self.assertEqual(self.vivos(self.a, self.app2), (1, 1, 1))

    def test_h_revogar_tokens_sem_tokens_nao_emite(self):
        emitidas = self._emissoes(
            lambda: revogacao.revogar_tokens(RequestFactory().get("/"), self.a)
        )

        self.assertEqual(emitidas, [])


class AplicacaoDoHintSemLinhaTests(_LogoutBase):
    """T-16. `accounts.logout_rp._aplicacao_do_hint_sem_linha(request, hint)`. Cada caso muda
    uma condição em relação ao positivo, todos assinados aqui com a chave do IdP."""

    def setUp(self):
        super().setUp()
        _, tokens = emitir_tokens(self.a, self.app1)
        self.cabecalho, self.claims, _ = partes_do_token(tokens["id_token"])
        self.issuer = self.claims["iss"]
        self.request = RequestFactory().get("/o/logout/")
        self.chave = chave_do_idp()

    def _resolver(self, hint):
        return logout_rp._aplicacao_do_hint_sem_linha(self.request, hint)

    def _hint(self, chave=None, **mudancas):
        claims = claims_de_hint(self.issuer, self.app1.client_id)
        claims.update(mudancas)
        return assinar(chave or self.chave, self.cabecalho, claims)

    def test_as_quatro_condicoes_verdadeiras_devolvem_a_application_do_aud(self):
        self.assertEqual(self._resolver(self._hint()), self.app1)

    def test_aud_desconhecido_devolve_none(self):
        self.assertIsNone(self._resolver(self._hint(aud="nao-existe")))

    def test_sem_aud_devolve_none(self):
        claims = claims_de_hint(self.issuer, self.app1.client_id)
        del claims["aud"]
        self.assertIsNone(self._resolver(assinar(self.chave, self.cabecalho, claims)))

    def test_assinatura_invalida_devolve_none(self):
        outra = gerar_chave_rsa(self.cabecalho["kid"])
        self.assertIsNone(self._resolver(self._hint(chave=outra)))

    def test_iss_diferente_devolve_none(self):
        self.assertIsNone(self._resolver(self._hint(iss="https://outro.example/o")))

    def test_jti_com_linha_devolve_none(self):
        self.assertIsNone(self._resolver(self._hint(jti=self.claims["jti"])))

    def test_carga_nao_json_devolve_none_sem_levantar(self):
        h, _, s = self._hint().split(".")
        self.assertIsNone(self._resolver(".".join([h, b64(b"not json"), s])))


class FalhaDaTrilhaTests(_LogoutBase):
    """T-18."""

    def test_falha_ao_gravar_a_trilha_nao_desfaz_a_saida_e_e_logada(self):
        client, tokens = emitir_tokens(self.a, self.app1)

        with mock.patch("accounts.auditoria.trilha.info", side_effect=RuntimeError("falhou")):
            with self.assertLogs("accounts.auditoria", "ERROR") as capturado:
                resposta = client.get(
                    _url(
                        id_token_hint=tokens["id_token"],
                        post_logout_redirect_uri=DESTINO,
                        state="s",
                    )
                )

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(status_userinfo(tokens["access_token"]), 401)
        self.assertSessaoDe(client, viva=False)
        self.assertTrue(
            any("falha ao registrar tokens_revogados" in r.getMessage() for r in capturado.records),
            [r.getMessage() for r in capturado.records],
        )

    def test_ligar_receptores_de_novo_nao_duplica_a_linha(self):
        auditoria.ligar_receptores()
        auditoria.ligar_receptores()
        client, tokens = emitir_tokens(self.a, self.app1)
        antes = tamanho_da_trilha()

        client.get(
            _url(id_token_hint=tokens["id_token"], post_logout_redirect_uri=DESTINO, state="s")
        )

        revogadas = self.eventos(linhas_da_trilha_desde(antes), "tokens_revogados")
        self.assertEqual(len(revogadas), 1, revogadas)


class ConstantesDeProducaoDoLogoutTests(SimpleTestCase):
    """T-03. As cinco chaves `OIDC_RP_INITIATED_LOGOUT_*` no dicionário que o runner guardou
    antes de neutralizar `settings.OAUTH2_PROVIDER` — nunca no dicionário em uso."""

    def test_as_cinco_chaves_de_producao(self):
        producao = runner.OAUTH2_PROVIDER_DE_PRODUCAO
        self.assertIsNotNone(producao, "o runner não guardou OAUTH2_PROVIDER de produção")

        self.assertIs(producao["OIDC_RP_INITIATED_LOGOUT_ENABLED"], True)
        self.assertIs(producao["OIDC_RP_INITIATED_LOGOUT_DELETE_TOKENS"], False)
        self.assertIs(producao["OIDC_RP_INITIATED_LOGOUT_ALWAYS_PROMPT"], False)
        self.assertIs(producao["OIDC_RP_INITIATED_LOGOUT_ACCEPT_EXPIRED_TOKENS"], True)
        self.assertEqual(
            producao["OIDC_RP_INITIATED_LOGOUT_STRICT_REDIRECT_URIS"],
            settings.BEHIND_TLS_PROXY,
        )
