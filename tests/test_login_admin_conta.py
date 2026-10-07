"""TASK-028/T-12 — POST em `/admin/login/`: caixa do e-mail, teto por conta, recusa de não-staff.

Demanda do quality-assurance (TASK-028). Nível integração: a propriedade está na costura entre
`admin.site.login_form`, o `authenticate()` e o `axes`, e um teste do formulário sozinho
passaria sem a ligação. O (a) e o (b) ficam vermelhos com `admin.site.login_form` trocado por
`AdminAuthenticationForm`: a caixa deixa de entrar e cada caixa vira um contador à parte. O (c)
fica vermelho se o formulário do admin perder a recusa de quem não é staff.

Como no login comum, as cinco falhas do (b) vêm de endereços diferentes, para que só o
contador da conta chegue ao teto, e a tentativa final, de um sexto endereço, só pode ser
barrada por ele.
"""

from axes.models import AccessAttempt
from django.contrib.auth import get_user_model
from django.test import TestCase

User = get_user_model()

SENHA = "senha-forte-o-suficiente"


class LoginDoAdminTests(TestCase):
    def _login(self, username, password, addr="10.20.0.1"):
        return self.client.post(
            "/admin/login/?next=/admin/",
            {"username": username, "password": password},
            REMOTE_ADDR=addr,
        )

    def test_a_staff_com_outra_caixa_e_a_senha_certa_entra(self):
        User.objects.create_user("st@x.com", SENHA, is_staff=True)

        resposta = self._login("ST@X.Com", SENHA)

        self.assertEqual(resposta.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)

    def test_b_cinco_caixas_de_cinco_enderecos_contam_na_mesma_conta(self):
        User.objects.create_user("st2@x.com", SENHA, is_staff=True)
        caixas = ["ST2@x.com", "st2@X.com", "St2@x.COM", "sT2@x.com", "ST2@X.COM"]
        for i, caixa in enumerate(caixas):
            self._login(caixa, "senha-errada", f"10.21.0.{i + 1}")

        resposta = self._login("st2@x.com", SENHA, "10.21.1.1")

        self.assertEqual(resposta.status_code, 429)
        self.assertNotIn("_auth_user_id", self.client.session)
        tentativas = AccessAttempt.objects.all()
        self.assertTrue(tentativas.exists())
        for tentativa in tentativas:
            self.assertEqual(tentativa.username, "st2@x.com")

    def test_c_conta_sem_staff_com_outra_caixa_e_a_senha_certa_nao_entra(self):
        User.objects.create_user("ns@x.com", SENHA, is_staff=False)

        resposta = self._login("NS@x.com", SENHA)

        self.assertEqual(resposta.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
