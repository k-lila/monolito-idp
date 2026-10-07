"""TASK-028/T-26 a T-33, T-39 e T-40 — a API de conta de `accounts/api.py` sob `/api/conta/`
(ADR 0031).

Demanda do quality-assurance. Nível integração: o que está sob prova é a costura entre o
`RecursoDaConta.dispatch`, o `AccessToken` real no banco, o `CorsMiddleware`, o limitador, os
receptores da trilha e o envio de e-mail, e só a resposta HTTP de verdade a revela.

Todo caso usa `override_settings(SPA_CLIENT_ID=<client_id da Application de teste>)` (em
`ApiDeContaTestCase.setUp`): o `.env.example` traz um valor que não existe no banco de teste.
O token é um `AccessToken` criado direto, com `scope="openid conta"` e `expires` futuro.
O envio de e-mail só acontece no commit: `captureOnCommitCallbacks(execute=True)`.

A ordem das recusas de `RecursoDaConta.dispatch` é o que T-27, T-28, T-39 e T-40 fixam, uma
guarda por vez: cada caso falha se a guarda a que ele se dirige sair do código.
"""

import json
from datetime import datetime, timedelta

from django.conf import settings
from django.core import mail
from django.core.cache import cache
from django.db.models.signals import pre_save
from django.test import Client, override_settings
from django.urls import reverse
from oauth2_provider.models import AccessToken, Application
from django.utils import timezone

from accounts.envio import chave_do_envio
from tests.api_conta_helpers import (
    CAMINHO_CONFIRMACAO,
    CAMINHO_CONTA,
    CAMINHO_TERMOS,
    CAMINHOS_COM_BEARER,
    ApiDeContaTestCase,
    User,
    bearer,
    criar_token,
    fotografia,
    linhas_do_evento,
    texto_da_trilha_desde,
)
from tests.logout_helpers import linhas_da_trilha_desde, tamanho_da_trilha

CHAVES_DO_CORPO = {
    "sub",
    "email",
    "email_verified",
    "first_name",
    "last_name",
    "nickname",
    "date_joined",
    "updated_at",
    "senha_alterada_em",
    "termos_versao",
    "termos_versao_vigente",
}


class LeituraDaContaTests(ApiDeContaTestCase):
    """T-26 — o GET devolve o conjunto exato de chaves, com os tipos que a SPA lê."""

    def test_get_devolve_o_conjunto_exato_de_chaves(self):
        resposta = self.client.get(CAMINHO_CONTA, **self.cabecalho)

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(set(resposta.json()), CHAVES_DO_CORPO)

    def test_valores_da_conta(self):
        corpo = self.client.get(CAMINHO_CONTA, **self.cabecalho).json()

        self.assertEqual(corpo["sub"], str(self.conta.sub))
        self.assertEqual(corpo["email"], "pessoa@exemplo.test")
        self.assertIs(corpo["email_verified"], False)
        self.assertEqual(corpo["first_name"], "Ana")
        self.assertEqual(corpo["last_name"], "Sobrenome")
        self.assertEqual(corpo["nickname"], "")
        self.assertEqual(corpo["termos_versao"], "")
        self.assertEqual(corpo["termos_versao_vigente"], settings.TERMOS_VERSAO_VIGENTE)

    def test_datas_sao_iso_8601_com_fuso(self):
        # `create_user` com senha carimba `senha_alterada_em`: as três datas vêm preenchidas.
        corpo = self.client.get(CAMINHO_CONTA, **self.cabecalho).json()

        for campo in ("date_joined", "updated_at", "senha_alterada_em"):
            with self.subTest(campo=campo):
                lida = datetime.fromisoformat(corpo[campo])
                self.assertIsNotNone(lida.tzinfo)

    def test_senha_alterada_em_nula_vira_null(self):
        # `QuerySet.update` passa por baixo do `save()`, que carimbaria o campo.
        User.objects.filter(pk=self.conta.pk).update(senha_alterada_em=None)

        corpo = self.client.get(CAMINHO_CONTA, **self.cabecalho).json()

        self.assertIsNone(corpo["senha_alterada_em"])

    def test_termos_nunca_aceitos_sao_200_e_versao_vazia(self):
        resposta = self.client.get(CAMINHO_CONTA, **self.cabecalho)

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()["termos_versao"], "")


class SemCredencialTests(ApiDeContaTestCase):
    """T-27 — sem Bearer válido, 401 em todo método, e a sessão sozinha não autentica."""

    METODOS = ("get", "head", "post", "patch", "put", "delete")

    def _requisicoes(self, cliente, caminho, **extra):
        for metodo in self.METODOS:
            yield metodo, getattr(cliente, metodo)(caminho, **extra)
        yield "propfind", cliente.generic("PROPFIND", caminho, **extra)

    def _confere_desafio(self, resposta, rotulo, erro=None):
        self.assertEqual(resposta.status_code, 401, rotulo)
        desafio = resposta["WWW-Authenticate"]
        self.assertTrue(desafio.startswith("Bearer"), rotulo)
        self.assertIn("resource_metadata=", desafio, rotulo)
        if erro:
            self.assertIn(f'error="{erro}"', desafio, rotulo)

    def test_sem_authorization(self):
        for caminho in CAMINHOS_COM_BEARER:
            for metodo, resposta in self._requisicoes(Client(enforce_csrf_checks=True), caminho):
                with self.subTest(caminho=caminho, metodo=metodo):
                    self._confere_desafio(resposta, f"{metodo} {caminho}")

    def test_bearer_inexistente(self):
        for caminho in CAMINHOS_COM_BEARER:
            for metodo, resposta in self._requisicoes(
                Client(enforce_csrf_checks=True), caminho, HTTP_AUTHORIZATION="Bearer nao-existe"
            ):
                with self.subTest(caminho=caminho, metodo=metodo):
                    self._confere_desafio(resposta, f"{metodo} {caminho}", "invalid_token")

    def test_bearer_expirado(self):
        expirado = criar_token(self.conta, self.spa, expira_em=-10)
        for caminho in CAMINHOS_COM_BEARER:
            for metodo, resposta in self._requisicoes(
                Client(enforce_csrf_checks=True), caminho, HTTP_AUTHORIZATION="Bearer " + expirado
            ):
                with self.subTest(caminho=caminho, metodo=metodo):
                    self._confere_desafio(resposta, f"{metodo} {caminho}", "invalid_token")

    def test_so_cookie_de_sessao(self):
        # Falha se a API passar a ler `request.user`: a isenção de CSRF depende de a sessão
        # não valer aqui. Com a verificação de CSRF ligada, um 403 de CSRF também falharia.
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.conta)
        for caminho in CAMINHOS_COM_BEARER:
            for metodo, resposta in self._requisicoes(cliente, caminho):
                with self.subTest(caminho=caminho, metodo=metodo):
                    self._confere_desafio(resposta, f"{metodo} {caminho}")

    def test_patch_so_com_sessao_nao_grava(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.conta)

        resposta = cliente.patch(
            CAMINHO_CONTA, '{"first_name": "Invasor"}', content_type="application/json"
        )

        self.assertEqual(resposta.status_code, 401)
        self.conta.refresh_from_db()
        self.assertEqual(self.conta.first_name, "Ana")

    def test_options_sem_origin_e_200_sem_corpo_e_sem_consulta(self):
        for caminho in CAMINHOS_COM_BEARER:
            with self.subTest(caminho=caminho):
                with self.assertNumQueries(0):
                    resposta = Client().options(caminho)

                self.assertEqual(resposta.status_code, 200)
                self.assertEqual(resposta.content, b"")
                self.assertNotIn(b"email", resposta.content)


class RecusaDoTokenValidoTests(ApiDeContaTestCase):
    """T-28 — token válido e de dono ativo, recusado pelo scope, pela Application ou pela conta
    inativa, nos três recursos. Nada é gravado e nenhum e-mail sai."""

    def _requisicoes(self, token):
        """As três chamadas, com o corpo que cada uma aceitaria se o token valesse."""
        cabecalho = bearer(token)
        with self.captureOnCommitCallbacks(execute=True):
            yield "GET conta", self.client.get(CAMINHO_CONTA, **cabecalho)
            yield "POST confirmacao", self.client.post(CAMINHO_CONFIRMACAO, **cabecalho)
            yield "POST termos", self.client.post(
                CAMINHO_TERMOS,
                json.dumps({"versao": settings.TERMOS_VERSAO_VIGENTE}),
                content_type="application/json",
                **cabecalho,
            )

    def _nada_gravado(self):
        self.conta.refresh_from_db()
        self.assertEqual(self.conta.termos_versao, "")
        self.assertIsNone(self.conta.termos_aceitos_em)
        self.assertEqual(mail.outbox, [])

    def test_sem_o_scope_conta_e_403_insufficient_scope_e_corpo_vazio(self):
        token = criar_token(self.conta, self.spa, scope="openid profile")

        for rotulo, resposta in self._requisicoes(token):
            with self.subTest(recurso=rotulo):
                self.assertEqual(resposta.status_code, 403)
                self.assertIn('error="insufficient_scope"', resposta["WWW-Authenticate"])
                self.assertEqual(resposta.content, b"")
        self._nada_gravado()

    def test_token_de_outra_application_e_403_aplicacao_nao_autorizada(self):
        token = criar_token(self.conta, self.outra)

        for rotulo, resposta in self._requisicoes(token):
            with self.subTest(recurso=rotulo):
                self.assertEqual(resposta.status_code, 403)
                self.assertEqual(resposta.json(), {"codigo": "aplicacao_nao_autorizada"})
                self.assertNotIn("WWW-Authenticate", resposta)
        self._nada_gravado()

    def test_conta_inativa_da_spa_e_403_conta_inativa(self):
        User.objects.filter(pk=self.conta.pk).update(is_active=False)

        for rotulo, resposta in self._requisicoes(self.token):
            with self.subTest(recurso=rotulo):
                self.assertEqual(resposta.status_code, 403)
                self.assertEqual(resposta.json(), {"codigo": "conta_inativa"})
                self.assertNotIn("WWW-Authenticate", resposta)
        self._nada_gravado()


class EdicaoDoPerfilTests(ApiDeContaTestCase):
    """T-29 — o PATCH grava só `first_name`, `last_name` e `nickname`, só o que mudou de valor,
    e a trilha registra os nomes dos campos, nunca os valores."""

    def setUp(self):
        super().setUp()
        self.cliente = Client(enforce_csrf_checks=True)

    def _patch(self, corpo):
        return self.corpo_json(CAMINHO_CONTA, corpo, metodo="patch")

    # `corpo_json` usa `self.client`; aqui a verificação de CSRF precisa estar ligada.
    def corpo_json(self, caminho, corpo, metodo="post", **extra):
        if not isinstance(corpo, (str, bytes)):
            corpo = json.dumps(corpo)
        return getattr(self.cliente, metodo)(
            caminho, corpo, content_type="application/json", **{**self.cabecalho, **extra}
        )

    def test_so_first_name_muda_e_a_trilha_nao_leva_o_valor(self):
        antes = fotografia(self.conta)
        inicio = tamanho_da_trilha()

        resposta = self._patch(
            {
                "first_name": "Nova",
                "email": "x@y.z",
                "sub": "00000000-0000-0000-0000-000000000000",
                "is_staff": True,
                "email_verified": True,
            }
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json(), self.client.get(CAMINHO_CONTA, **self.cabecalho).json())
        depois = fotografia(self.conta)
        diferentes = {campo for campo in antes if antes[campo] != depois[campo]}
        self.assertEqual(diferentes, {"first_name", "updated_at"})
        self.assertEqual(depois["first_name"], "Nova")
        self.assertGreater(depois["updated_at"], antes["updated_at"])
        linhas = linhas_da_trilha_desde(inicio)
        editadas = linhas_do_evento(linhas, "conta_editada")
        self.assertEqual(len(editadas), 1)
        self.assertEqual(editadas[0]["campos"], ["first_name"])
        self.assertNotIn("Nova", texto_da_trilha_desde(inicio))

    def test_patch_com_o_mesmo_valor_nao_grava_nem_registra(self):
        self._patch({"first_name": "Nova"})
        antes = fotografia(self.conta)
        inicio = tamanho_da_trilha()

        resposta = self._patch({"first_name": "Nova"})

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(fotografia(self.conta), antes)
        self.assertEqual(linhas_do_evento(linhas_da_trilha_desde(inicio), "conta_editada"), [])

    def test_patch_de_objeto_vazio_nao_grava_nem_registra(self):
        antes = fotografia(self.conta)
        inicio = tamanho_da_trilha()

        resposta = self._patch({})

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(fotografia(self.conta), antes)
        self.assertEqual(linhas_do_evento(linhas_da_trilha_desde(inicio), "conta_editada"), [])

    def test_null_grava_texto_vazio_e_registra_o_campo(self):
        inicio = tamanho_da_trilha()

        resposta = self._patch({"last_name": None})

        self.assertEqual(resposta.status_code, 200)
        self.conta.refresh_from_db()
        self.assertEqual(self.conta.last_name, "")
        self.assertEqual(resposta.json()["last_name"], "")
        editadas = linhas_do_evento(linhas_da_trilha_desde(inicio), "conta_editada")
        self.assertEqual(len(editadas), 1)
        self.assertEqual(editadas[0]["campos"], ["last_name"])


class CorpoInvalidoTests(ApiDeContaTestCase):
    """T-30 — todo 400 tem a forma `{"erros": {campo: [{"codigo", "mensagem"}]}}`, em inglês
    e só ASCII, e não grava nada."""

    def _confere_forma(self, resposta):
        self.assertEqual(resposta.status_code, 400)
        corpo = resposta.json()
        self.assertEqual(list(corpo), ["erros"])
        self.assertTrue(corpo["erros"])
        for campo, lista in corpo["erros"].items():
            self.assertTrue(lista, campo)
            for erro in lista:
                self.assertEqual(set(erro), {"codigo", "mensagem"})
                self.assertTrue(erro["mensagem"], campo)
                self.assertTrue(erro["mensagem"].isascii(), erro["mensagem"])
        return corpo["erros"]

    def _recusa(self, caminho, corpo, metodo, **extra):
        antes = fotografia(self.conta)
        inicio = tamanho_da_trilha()
        resposta = self.corpo_json(caminho, corpo, metodo=metodo, **extra)
        erros = self._confere_forma(resposta)
        self.assertEqual(fotografia(self.conta), antes)
        self.assertEqual(linhas_da_trilha_desde(inicio), [])
        return erros

    def test_nickname_de_151_e_max_length(self):
        erros = self._recusa(CAMINHO_CONTA, {"nickname": "a" * 151}, "patch")

        self.assertEqual(list(erros), ["nickname"])
        self.assertEqual(erros["nickname"][0]["codigo"], "max_length")

    def test_nickname_de_150_e_aceito(self):
        resposta = self.corpo_json(CAMINHO_CONTA, {"nickname": "a" * 150}, metodo="patch")

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()["nickname"], "a" * 150)

    def test_valor_que_nao_e_texto_e_invalid(self):
        for corpo, campo in (
            ({"nickname": 5}, "nickname"),
            ({"first_name": True}, "first_name"),
            ({"last_name": ["a"]}, "last_name"),
        ):
            with self.subTest(corpo=corpo):
                erros = self._recusa(CAMINHO_CONTA, corpo, "patch")

                self.assertEqual(list(erros), [campo])
                self.assertEqual(erros[campo][0]["codigo"], "invalid")

    def test_corpo_que_nao_e_objeto_json_e_json_invalido(self):
        corpos = [
            "[1]",
            "{",
            "",
            "null",
            b"\xff\xfe",
            # Falha se `RecursionError` deixar de ser capturado: o decodificador estoura a pilha.
            "[" * 100000,
        ]
        for corpo in corpos:
            with self.subTest(corpo=repr(corpo)[:30]):
                erros = self._recusa(CAMINHO_CONTA, corpo, "patch")

                self.assertEqual(list(erros), ["geral"])
                self.assertEqual(erros["geral"][0]["codigo"], "json_invalido")

    def test_post_de_termos_com_lista_e_json_invalido(self):
        erros = self._recusa(CAMINHO_TERMOS, "[]", "post")

        self.assertEqual(list(erros), ["geral"])
        self.assertEqual(erros["geral"][0]["codigo"], "json_invalido")

    def test_mensagem_segue_em_ingles_com_accept_language_pt_br(self):
        for caminho, corpo, metodo in (
            (CAMINHO_CONTA, {"nickname": "a" * 151}, "patch"),
            (CAMINHO_CONTA, {"nickname": 5}, "patch"),
            (CAMINHO_CONTA, "{", "patch"),
            (CAMINHO_TERMOS, {"versao": "2"}, "post"),
            (CAMINHO_TERMOS, {}, "post"),
        ):
            with self.subTest(caminho=caminho, corpo=corpo):
                self._recusa(caminho, corpo, metodo, HTTP_ACCEPT_LANGUAGE="pt-br")


class EscritaConcorrenteTests(ApiDeContaTestCase):
    """T-31 — o `save()` do PATCH grava só o campo alterado: outra coluna da mesma conta,
    mudada no banco depois de a view carregá-la, não é sobrescrita pelo valor antigo."""

    def test_campo_alterado_por_fora_no_meio_do_patch_sobrevive(self):
        pk = self.conta.pk
        disparos = []

        def receptor(sender, instance, **kwargs):
            # O `pre_save` roda depois de a view ter lido a conta e antes do UPDATE.
            if instance.pk == pk:
                disparos.append(kwargs.get("update_fields"))
                User.objects.filter(pk=pk).update(termos_versao="X")

        pre_save.connect(receptor, sender=User, dispatch_uid="tests.t31", weak=False)
        self.addCleanup(pre_save.disconnect, sender=User, dispatch_uid="tests.t31")

        resposta = self.corpo_json(CAMINHO_CONTA, {"first_name": "Nova"}, metodo="patch")

        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(disparos, "o receptor não rodou: o caso não provou nada")
        self.conta.refresh_from_db()
        self.assertEqual(self.conta.first_name, "Nova")
        # Falha se o `save()` da view perder `update_fields`: gravaria o "" que a view leu.
        self.assertEqual(self.conta.termos_versao, "X")


class ReenvioDaConfirmacaoTests(ApiDeContaTestCase):
    """T-32 — o POST reenvia a confirmação só a conta não confirmada, e a resposta é a mesma
    com ou sem envio."""

    def _reenviar(self):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(CAMINHO_CONFIRMACAO, **self.cabecalho)

    def test_conta_nao_confirmada_recebe_um_email_com_o_link(self):
        resposta = self._reenviar()

        self.assertEqual(resposta.status_code, 204)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.conta.email])
        self.assertIn(settings.BASE_URL + reverse("api_conta_confirmar"), mail.outbox[0].body)

    def test_conta_confirmada_nao_recebe_email_e_a_resposta_e_a_mesma(self):
        com_envio = self._reenviar()
        User.objects.filter(pk=self.conta.pk).update(email_verified=True)
        mail.outbox.clear()

        sem_envio = self._reenviar()

        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(sem_envio.status_code, com_envio.status_code)
        self.assertEqual(sem_envio.content, com_envio.content)

    def test_teto_por_destinatario_suprime_o_segundo_envio_sem_mudar_a_resposta(self):
        chave = chave_do_envio(self.conta.email)
        cache.delete(chave)
        self.addCleanup(cache.delete, chave)
        with override_settings(TETO_DE_ENVIOS_POR_DESTINATARIO=1):
            primeira = self._reenviar()
            segunda = self._reenviar()

        self.assertEqual(primeira.status_code, 204)
        self.assertEqual(segunda.status_code, 204)
        self.assertEqual(primeira.content, segunda.content)
        self.assertEqual(len(mail.outbox), 1)


class AceiteDosTermosTests(ApiDeContaTestCase):
    """T-33 — só a versão vigente, exatamente como enviada, é aceita."""

    def _aceitar(self, corpo):
        return self.corpo_json(CAMINHO_TERMOS, corpo)

    def test_versao_vigente_e_204_grava_e_registra(self):
        inicio = tamanho_da_trilha()

        resposta = self._aceitar({"versao": settings.TERMOS_VERSAO_VIGENTE})

        self.assertEqual(resposta.status_code, 204)
        self.conta.refresh_from_db()
        self.assertEqual(self.conta.termos_versao, settings.TERMOS_VERSAO_VIGENTE)
        self.assertIsNotNone(self.conta.termos_aceitos_em)
        aceites = linhas_do_evento(linhas_da_trilha_desde(inicio), "termos_aceitos")
        self.assertEqual(len(aceites), 1)
        self.assertEqual(aceites[0]["termos_versao"], settings.TERMOS_VERSAO_VIGENTE)

    def test_versao_desatualizada_ou_com_espacos_e_termos_desatualizados(self):
        for versao in ("2", f" {settings.TERMOS_VERSAO_VIGENTE} "):
            with self.subTest(versao=versao):
                inicio = tamanho_da_trilha()

                resposta = self._aceitar({"versao": versao})

                self.assertEqual(resposta.status_code, 400)
                erros = resposta.json()["erros"]
                self.assertEqual(erros["versao"][0]["codigo"], "termos_desatualizados")
                self.conta.refresh_from_db()
                self.assertEqual(self.conta.termos_versao, "")
                self.assertIsNone(self.conta.termos_aceitos_em)
                self.assertEqual(
                    linhas_do_evento(linhas_da_trilha_desde(inicio), "termos_aceitos"), []
                )

    def test_ausente_ou_nula_e_required(self):
        for corpo in ({}, {"versao": None}):
            with self.subTest(corpo=corpo):
                resposta = self._aceitar(corpo)

                self.assertEqual(resposta.status_code, 400)
                self.assertEqual(resposta.json()["erros"]["versao"][0]["codigo"], "required")

    def test_numero_e_invalid(self):
        resposta = self._aceitar({"versao": 1})

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.json()["erros"]["versao"][0]["codigo"], "invalid")


class BearerForaDoCabecalhoTests(ApiDeContaTestCase):
    """T-39 — o token vale só no cabeçalho `Authorization`: na URL ele iria para o log da borda
    e para o `Referer`. Falha se a guarda de ausência do cabeçalho sair de
    `RecursoDaConta.dispatch`, porque o oauthlib, sem o cabeçalho, lê o token da query e do
    corpo form-urlencoded."""

    def test_token_na_query_sem_cabecalho_e_401_igual_ao_do_token_ausente(self):
        ausente = self.client.get(CAMINHO_CONTA)

        resposta = self.client.get(CAMINHO_CONTA + "?access_token=" + self.token)

        self.assertEqual(resposta.status_code, 401)
        self.assertEqual(resposta["WWW-Authenticate"], ausente["WWW-Authenticate"])

    def test_token_no_corpo_form_sem_cabecalho_e_401_igual_ao_do_token_ausente(self):
        ausente = self.client.post(CAMINHO_TERMOS)

        resposta = self.client.post(
            CAMINHO_TERMOS,
            "access_token=" + self.token,
            content_type="application/x-www-form-urlencoded",
        )

        self.assertEqual(resposta.status_code, 401)
        self.assertEqual(resposta["WWW-Authenticate"], ausente["WWW-Authenticate"])

    def test_cabecalho_basic_com_token_valido_na_query_e_401(self):
        resposta = self.client.get(
            CAMINHO_CONTA + "?access_token=" + self.token, HTTP_AUTHORIZATION="Basic xxx"
        )

        self.assertEqual(resposta.status_code, 401)


class TokenSemContaTests(ApiDeContaTestCase):
    """T-40 — com `SPA_CLIENT_ID` apontando por engano para uma Application
    `client-credentials`, o token dela não tem dono: 403, nunca 500. Falha se a verificação
    de `token.user is None` sair de `RecursoDaConta.dispatch`."""

    def test_token_de_client_credentials_com_user_none_e_403(self):
        servico = Application.objects.create(
            client_id="servico-client-credentials",
            client_type="confidential",
            authorization_grant_type="client-credentials",
            name="servico",
        )
        token = AccessToken.objects.create(
            user=None,
            application=servico,
            token="token-sem-dono",
            scope="conta",
            expires=timezone.now() + timedelta(hours=1),
        )

        with override_settings(SPA_CLIENT_ID=servico.client_id):
            resposta = self.client.get(CAMINHO_CONTA, **bearer(token.token))

        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(resposta.json(), {"codigo": "aplicacao_nao_autorizada"})
