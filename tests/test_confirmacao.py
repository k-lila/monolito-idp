"""TASK-028/T-21 — o token do link de confirmação (`accounts/confirmacao.py`).

Demanda do quality-assurance. Nível unitário, sem banco: o usuário é um objeto com `sub` e
`email`, o único que `gerar` lê. O salt e o formato do payload são afirmados por literal e por
um token montado à mão com `signing.dumps`, e não por `confirmacao._SALT`: ler o salt do
próprio módulo faria o caso passar com qualquer salt.
"""

import uuid
from datetime import timedelta
from types import SimpleNamespace
from unittest import mock

from django.core import signing
from django.test import SimpleTestCase

from accounts import confirmacao

SALT = "accounts.confirmacao-de-email"


def _usuario(email="Fulana@Exemplo.com"):
    return SimpleNamespace(sub=uuid.uuid4(), email=email)


class TokenDeConfirmacaoTests(SimpleTestCase):
    def test_o_prazo_e_de_sete_dias(self):
        self.assertEqual(confirmacao.PRAZO, timedelta(days=7))

    def test_ida_e_volta_devolve_o_sub_e_o_resumo(self):
        user = _usuario()
        self.assertEqual(
            confirmacao.ler(confirmacao.gerar(user)),
            (str(user.sub), confirmacao.resumo_do_email(user.email)),
        )

    def test_o_resumo_de_outra_caixa_e_o_mesmo(self):
        self.assertEqual(
            confirmacao.resumo_do_email("Fulana@Exemplo.com"),
            confirmacao.resumo_do_email("fulana@exemplo.com"),
        )
        self.assertEqual(
            confirmacao.ler(confirmacao.gerar(_usuario("FULANA@EXEMPLO.COM")))[1],
            confirmacao.ler(confirmacao.gerar(_usuario("fulana@exemplo.com")))[1],
        )

    def test_o_conteudo_e_o_sub_e_o_resumo_e_nao_o_endereco(self):
        user = _usuario()
        dados = signing.loads(confirmacao.gerar(user), salt=SALT)
        self.assertEqual(
            dados, {"sub": str(user.sub), "h": confirmacao.resumo_do_email(user.email)}
        )
        self.assertNotIn("@", confirmacao.gerar(user))

    def test_outro_salt_adulterado_lixo_e_payload_sem_h_devolvem_none(self):
        user = _usuario()
        valido = confirmacao.gerar(user)
        # Troca um caractere da assinatura, sem mudar o tamanho.
        adulterado = valido[:-1] + ("A" if valido[-1] != "A" else "B")
        casos = {
            "outro salt": signing.dumps({"sub": str(user.sub), "h": "x"}, salt="outro.salt"),
            "adulterado": adulterado,
            "lixo": "isto-nao-e-um-token",
            "vazio": "",
            "sem h": signing.dumps({"sub": str(user.sub)}, salt=SALT),
            "sem sub": signing.dumps({"h": "x"}, salt=SALT),
        }
        for nome, token in casos.items():
            with self.subTest(nome):
                self.assertIsNone(confirmacao.ler(token))

    def test_o_token_montado_a_mao_com_o_salt_literal_e_aceito(self):
        token = signing.dumps({"sub": "abc", "h": "def"}, salt=SALT)
        self.assertEqual(confirmacao.ler(token), ("abc", "def"))

    def test_o_prazo_vale_ate_sete_dias_e_nao_alem(self):
        agora = 1_800_000_000
        with mock.patch("django.core.signing.time.time", return_value=agora):
            token = confirmacao.gerar(_usuario())
        prazo = int(timedelta(days=7).total_seconds())
        with mock.patch("django.core.signing.time.time", return_value=agora + prazo - 5):
            self.assertIsNotNone(confirmacao.ler(token))
        with mock.patch("django.core.signing.time.time", return_value=agora + prazo + 5):
            self.assertIsNone(confirmacao.ler(token))
