"""TASK-028/T-44 — o pedido de recuperação em `/accounts/password_reset/`.

Demanda do quality-assurance. Nível integração: o que está sob prova é a costura entre a view
do Django, `FormularioDeRecuperacao`, `accounts/emails.py`, o teto de envios e o sinal
`recuperacao_pedida`, e a resposta a quem pede tem de ser a mesma com e sem conta (ADR 0031).

Cinco endereços pedem: a conta ativa, a mesma em outra caixa, o inexistente, o da conta inativa
e o da conta sem senha utilizável. A resposta (o `Location` do 302 e o corpo da página seguinte)
é igual nos cinco; e-mail e linha de trilha só saem para os dois primeiros, ao endereço em
minúsculas. Com o teto do destinatário esgotado a resposta continua igual, e não sai nem e-mail
nem linha: quem dispara contra um endereço alheio não aprende que o teto foi atingido.

Fica vermelho se a resposta distinguir os casos, se o e-mail sair para conta inativa ou sem
senha utilizável, se o sinal sair sem e-mail enfileirado ou o e-mail sem sinal, ou se o teto
mudar a resposta.
"""

from django.core import mail

from tests.paginas_helpers import (
    PaginasDeContaTestCase,
    User,
    com_arroba,
    eventos,
)

URL = "/accounts/password_reset/"
FEITO = "/accounts/password_reset/done/"


class PedidoDeRecuperacaoTests(PaginasDeContaTestCase):
    def setUp(self):
        super().setUp()
        User.objects.create_user("inativa@ex.com", "x-Senha-forte-123", is_active=False)
        User.objects.create_user("semsenha@ex.com", None)

    def _pedir(self, endereco):
        marca = self.trilha()
        antes = len(mail.outbox)
        resposta = self.postar(self.client, URL, {"email": endereco})
        corpo = self.client.get(resposta["Location"]).content.decode()
        return resposta, corpo, mail.outbox[antes:], eventos(marca())

    def test_mesma_resposta_nos_cinco_casos_e_e_mail_so_para_os_dois_primeiros(self):
        casos = [
            ("pessoa@ex.com", True),
            ("PESSOA@ex.com", True),
            ("ninguem@ex.com", False),
            ("inativa@ex.com", False),
            ("semsenha@ex.com", False),
        ]
        respostas = []
        for endereco, envia in casos:
            with self.subTest(endereco=endereco):
                resposta, corpo, enviados, linhas = self._pedir(endereco)

                self.assertEqual(resposta.status_code, 302)
                respostas.append((resposta["Location"], corpo))
                if envia:
                    self.assertEqual(len(enviados), 1)
                    self.assertEqual(enviados[0].to, ["pessoa@ex.com"])
                    self.assertEqual(enviados[0].subject, "Redefinição de senha")
                    self.assertEqual(linhas, ["recuperacao_pedida"])
                else:
                    self.assertEqual(enviados, [])
                    self.assertEqual(linhas, [])

        self.assertEqual({local for local, _ in respostas}, {FEITO})
        self.assertEqual(len({corpo for _, corpo in respostas}), 1)

    def test_conta_da_equipe_nao_recebe_e_a_resposta_e_a_de_endereco_sem_conta(self):
        """TASK-028/T-72 — `is_staff` ou `is_superuser` não gera e-mail, linha de supressão nem
        `recuperacao_pedida`, e a resposta é byte a byte a do endereço sem conta."""
        User.objects.create_user("staff@ex.com", "x-Senha-forte-123", is_staff=True)
        User.objects.create_user("super@ex.com", "x-Senha-forte-123", is_superuser=True)
        resposta_sem_conta, corpo_sem_conta, _, _ = self._pedir("ninguem@ex.com")

        for endereco in ("staff@ex.com", "super@ex.com", "dono@ex.com"):
            with self.subTest(endereco=endereco):
                resposta, corpo, enviados, linhas = self._pedir(endereco)

                self.assertEqual(resposta.status_code, resposta_sem_conta.status_code)
                self.assertEqual(resposta["Location"], resposta_sem_conta["Location"])
                self.assertEqual(corpo, corpo_sem_conta)
                self.assertEqual(enviados, [])
                self.assertEqual(linhas, [])

    def test_a_trilha_do_pedido_nao_leva_e_mail(self):
        marca = self.trilha()

        self.postar(self.client, URL, {"email": "PESSOA@ex.com"})

        self.assertEqual(com_arroba(marca()), [])

    def test_com_o_teto_do_destinatario_esgotado_a_resposta_nao_muda_e_nada_sai(self):
        _, corpo_normal, _, _ = self._pedir("ninguem@ex.com")
        self.esgotar_teto("pessoa@ex.com")
        marca = self.trilha()

        resposta = self.postar(self.client, URL, {"email": "pessoa@ex.com"})
        corpo = self.client.get(resposta["Location"]).content.decode()

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta["Location"], FEITO)
        self.assertEqual(corpo, corpo_normal)
        self.assertEqual(mail.outbox, [])
        self.assertEqual(marca(), [])
