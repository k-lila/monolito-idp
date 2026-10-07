"""TASK-028/T-34, T-38 e T-63 — o link de confirmação de e-mail, `GET /api/conta/confirmar/?t=...`
(`accounts/api.confirmar`, ADR 0031).

Demanda do quality-assurance. Nível integração: o token é o de `accounts.confirmacao.gerar`,
a leitura passa pela assinatura real de `django.core.signing`, e a conta, a `select_for_update`
e a trilha são as de verdade. O endpoint é anônimo e sempre redireciona à SPA.

O relógio do `signing` é trocado só dentro do módulo `django.core.signing`, e não o `time.time`
do processo: o resto da requisição continua no tempo real.

T-63: o GET válido executa um SELECT da conta com `FOR UPDATE`, a trava que impede dois cliques
simultâneos de confirmarem duas vezes e deixarem duas linhas na trilha. Vermelho se o
`select_for_update()` sair de `confirmar`: nada mais no resultado da requisição o acusa.
"""

import re
import time
from unittest import mock
from urllib.parse import urlsplit

from django.conf import settings
from django.core import signing
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import resolve

from accounts import api, confirmacao, emails
from tests.api_conta_helpers import SENHA, User, linhas_do_evento, texto_da_trilha_desde
from tests.logout_helpers import linhas_da_trilha_desde, tamanho_da_trilha

CAMINHO = "/api/conta/confirmar/"


def _criar_conta(email):
    return User.objects.create_user(email=email, password=SENHA)


class ConfirmarTests(TestCase):
    """T-34 — primeira vez confirma, segunda é idempotente, e todo o resto é `invalido`."""

    def setUp(self):
        self.conta = _criar_conta("confirma@exemplo.test")
        self.t = confirmacao.gerar(self.conta)
        self.sucesso = f"{settings.SPA_URL}/?email=confirmado"
        self.falha = f"{settings.SPA_URL}/?email=invalido"

    def _confirmar(self, t=None):
        return Client().get(CAMINHO, {"t": self.t if t is None else t})

    def _intacta(self, conta=None):
        conta = conta or self.conta
        conta.refresh_from_db()
        self.assertFalse(conta.email_verified)
        self.assertIsNone(conta.email_verificado_em)

    def test_primeira_vez_confirma_e_registra_sem_o_email(self):
        inicio = tamanho_da_trilha()

        resposta = self._confirmar()

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta["Location"], self.sucesso)
        self.conta.refresh_from_db()
        self.assertTrue(self.conta.email_verified)
        self.assertIsNotNone(self.conta.email_verificado_em)
        linhas = linhas_da_trilha_desde(inicio)
        self.assertEqual(len(linhas_do_evento(linhas, "email_confirmado")), 1)
        self.assertNotIn(self.conta.email, texto_da_trilha_desde(inicio))

    def test_segunda_vez_e_confirmado_sem_carimbo_novo_nem_linha_nova(self):
        self._confirmar()
        self.conta.refresh_from_db()
        carimbo = self.conta.email_verificado_em
        inicio = tamanho_da_trilha()

        resposta = self._confirmar()

        self.assertEqual(resposta["Location"], self.sucesso)
        self.conta.refresh_from_db()
        self.assertEqual(self.conta.email_verificado_em, carimbo)
        self.assertEqual(linhas_da_trilha_desde(inicio), [])

    def test_token_vazio_ausente_ou_adulterado_e_invalido(self):
        adulterado = self.t[:-1] + ("A" if self.t[-1] != "A" else "B")
        casos = {
            "vazio": Client().get(CAMINHO, {"t": ""}),
            "ausente": Client().get(CAMINHO),
            "adulterado": self._confirmar(adulterado),
        }
        for rotulo, resposta in casos.items():
            with self.subTest(caso=rotulo):
                self.assertEqual(resposta.status_code, 302)
                self.assertEqual(resposta["Location"], self.falha)
        self._intacta()

    def test_token_expirado_e_invalido(self):
        no_futuro = mock.Mock(time=lambda: time.time() + 8 * 86400)
        with mock.patch.object(signing, "time", no_futuro):
            resposta = self._confirmar()

        self.assertEqual(resposta["Location"], self.falha)
        self._intacta()

    def test_email_trocado_depois_de_gerar_o_link_e_invalido(self):
        self.conta.email = "outro@exemplo.test"
        self.conta.save()

        resposta = self._confirmar()

        self.assertEqual(resposta["Location"], self.falha)
        self._intacta()

    def test_conta_inativa_e_invalida(self):
        User.objects.filter(pk=self.conta.pk).update(is_active=False)

        resposta = self._confirmar()

        self.assertEqual(resposta["Location"], self.falha)
        self._intacta()

    def test_conta_apagada_e_invalida(self):
        self.conta.delete()

        resposta = self._confirmar()

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta["Location"], self.falha)

    def test_o_get_valido_le_a_conta_com_for_update(self):
        """T-63."""
        with CaptureQueriesContext(connection) as consultas:
            resposta = self.client.get(CAMINHO, {"t": self.t})

        self.assertEqual(resposta["Location"], self.sucesso)
        travadas = [
            c["sql"]
            for c in consultas.captured_queries
            if c["sql"].lstrip().upper().startswith("SELECT")
            and "FOR UPDATE" in c["sql"].upper()
            and '"accounts_user"' in c["sql"]
        ]
        self.assertEqual(len(travadas), 1, travadas)

    def test_post_e_head_sao_405(self):
        self.assertEqual(Client().post(CAMINHO, {"t": self.t}).status_code, 405)
        self.assertEqual(Client().head(CAMINHO, {"t": self.t}).status_code, 405)
        self._intacta()


class LinkDoEmailTests(TestCase):
    """T-38 — o link que o e-mail carrega, aberto como a pessoa o abriria: sai de `BASE_URL`,
    resolve para `api.confirmar` e confirma; um link anterior à troca do e-mail não."""

    def _link(self, conta):
        corpo = emails.confirmacao(conta).body
        achado = re.search(r"https?://\S+confirmar/\?t=\S+", corpo)
        self.assertIsNotNone(achado, corpo)
        return achado.group(0)

    def _abrir(self, link):
        partes = urlsplit(link)
        return Client().get(partes.path + "?" + partes.query)

    def test_link_confirma_a_conta(self):
        conta = _criar_conta("link@exemplo.test")
        link = self._link(conta)

        self.assertTrue(link.startswith(settings.BASE_URL))
        self.assertNotIn("testserver", link)
        self.assertIs(resolve(urlsplit(link).path).func, api.confirmar)
        resposta = self._abrir(link)
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta["Location"], f"{settings.SPA_URL}/?email=confirmado")
        conta.refresh_from_db()
        self.assertTrue(conta.email_verified)

    def test_link_gerado_antes_de_trocar_o_email_e_invalido(self):
        conta = _criar_conta("antes@exemplo.test")
        link = self._link(conta)
        conta.email = "depois@exemplo.test"
        conta.save()

        resposta = self._abrir(link)

        self.assertEqual(resposta["Location"], f"{settings.SPA_URL}/?email=invalido")
        conta.refresh_from_db()
        self.assertFalse(conta.email_verified)
