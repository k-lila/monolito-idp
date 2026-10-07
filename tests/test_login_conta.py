"""TASK-028/T-09 — POST em `/accounts/login/`: caixa do e-mail, conta desativada, teto por conta.

Demanda do quality-assurance (TASK-028). Nível integração: o que está sob prova é a costura
entre `FormularioDeLogin`, o `authenticate()`, o `axes` e a resposta de bloqueio, e nenhuma
peça sozinha a revela.

O teto do `axes` é por conta e por origem. Os casos que contam falhas variam o `REMOTE_ADDR`
a cada tentativa para que só o contador da conta chegue a cinco, e o último POST, com a senha
certa, vem de mais um endereço: o 429 que ele recebe só pode ser da conta. O (f) fica vermelho
se o `.lower()` sair de `clean_username`, ou for para depois do `authenticate()`: cada caixa
do mesmo endereço passaria a ser um contador à parte, e o teto deixaria de valer.
"""

from axes.models import AccessAttempt
from django.contrib.auth import get_user_model
from django.test import TestCase

User = get_user_model()

SENHA = "senha-forte-o-suficiente"
DESATIVADA = "Esta conta está desativada"
GENERICA = "E-mail ou senha incorretos."


class LoginDaContaTests(TestCase):
    def _login(self, username, password, addr=None):
        extra = {"REMOTE_ADDR": addr} if addr else {}
        return self.client.post(
            "/accounts/login/", {"username": username, "password": password}, **extra
        )

    def _cinco_falhas(self, caixas, prefixo):
        for i, caixa in enumerate(caixas):
            self._login(caixa, "senha-errada", f"{prefixo}.{i + 1}")

    def test_a_caixa_diferente_da_gravada_entra(self):
        User.objects.create_user("h@x.com", SENHA)

        resposta = self._login("H@X.COM", SENHA)

        self.assertEqual(resposta.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)

    def test_b_conta_desativada_com_a_senha_certa_ve_a_mensagem_e_conta_uma_falha(self):
        User.objects.create_user("i@x.com", SENHA, is_active=False)

        resposta = self._login("I@X.com", SENHA)

        self.assertContains(resposta, DESATIVADA)
        self.assertContains(resposta, "fale com quem administra")
        tentativa = AccessAttempt.objects.get(username="i@x.com")
        self.assertEqual(tentativa.failures_since_start, 1)
        self.assertFalse(AccessAttempt.objects.filter(username="I@X.com").exists())

    def test_c_conta_desativada_com_senha_errada_ve_a_generica(self):
        User.objects.create_user("j@x.com", SENHA, is_active=False)

        resposta = self._login("j@x.com", "senha-errada")

        self.assertContains(resposta, GENERICA)
        self.assertNotContains(resposta, "desativada")

    def test_d_conta_inexistente_ve_a_mesma_generica(self):
        resposta = self._login("ninguem@x.com", "senha-errada")

        self.assertContains(resposta, GENERICA)
        self.assertNotContains(resposta, "desativada")

    def test_e_conta_desativada_bloqueada_ve_o_bloqueio_e_nao_a_desativada(self):
        User.objects.create_user("k@x.com", SENHA, is_active=False)
        self._cinco_falhas(["k@x.com"] * 5, "10.8.0")

        resposta = self._login("k@x.com", SENHA, "10.8.1.1")

        self.assertEqual(resposta.status_code, 429)
        self.assertNotContains(resposta, "desativada", status_code=429)

    def test_f_cinco_caixas_do_mesmo_endereco_contam_na_mesma_conta(self):
        User.objects.create_user("l@x.com", SENHA)
        caixas = ["L@x.com", "l@X.com", "L@X.COM", "l@x.COM", "L@x.Com"]
        self._cinco_falhas(caixas, "10.9.0")

        resposta = self._login("l@x.com", SENHA, "10.9.1.1")

        self.assertEqual(resposta.status_code, 429)
        self.assertNotIn("_auth_user_id", self.client.session)
