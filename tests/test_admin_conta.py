"""TASK-028/T-11 e T-61 — o admin de conta (`accounts/admin.py`), com superusuário logado.

Demanda do quality-assurance (TASK-028). Nível integração: o formulário do admin, o
`save_model` e o `save()` do modelo só se encontram numa requisição, e a asserção é sempre
sobre o que ficou no banco, nunca sobre a resposta.

O formulário de alteração carrega `date_joined` em campos separados de data e hora, e o POST
os repete com os valores iniciais: o admin os considera inalterados, e `changed_data` fica com
o que cada caso muda de propósito.

T-61: trocar o e-mail da conta no admin esquece o histórico de login do endereço antigo nas três
tabelas do `axes`, em duas caixas, e deixa o de outro endereço. Salvar mudando só o nome não
apaga nada. Vermelho se o `save_model` deixar de chamar `esquecer_tentativas` na troca, ou se
passar a chamá-la em toda edição.

T-65: mudar só a caixa do e-mail (`L@X.com` para a conta `l@x.com`) também não apaga: o endereço
gravado continua o mesmo, e o histórico das duas caixas fica.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.utils import timezone

from tests.paginas_helpers import contagem_axes, semear_axes

User = get_user_model()

SENHA = "senha-forte-o-suficiente"


class AdminDeContaTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("adm@x.com", SENHA)
        self.client.force_login(self.admin)
        self.verificado_em = timezone.now() - timedelta(days=10)
        self.conta = User.objects.create_user("l@x.com", SENHA)
        User.objects.filter(pk=self.conta.pk).update(
            email_verified=True, email_verificado_em=self.verificado_em
        )
        self.url = f"/admin/accounts/user/{self.conta.pk}/change/"

    def _do_banco(self):
        return User.objects.get(pk=self.conta.pk)

    def _post(self, **mudancas):
        # Os campos de data repetem o valor inicial, para o admin não os ver alterados.
        iniciais = self._do_banco().date_joined
        dados = {
            "email": "l@x.com",
            "first_name": "",
            "last_name": "",
            "nickname": "",
            "is_active": "on",
            "date_joined_0": iniciais.strftime("%Y-%m-%d"),
            "date_joined_1": iniciais.strftime("%H:%M:%S"),
            "initial-date_joined_0": iniciais.strftime("%Y-%m-%d"),
            "initial-date_joined_1": iniciais.strftime("%H:%M:%S"),
        }
        dados.update(mudancas)
        dados = {chave: valor for chave, valor in dados.items() if valor is not None}
        resposta = self.client.post(self.url, dados)
        self.assertEqual(resposta.status_code, 302, getattr(resposta, "context", None))
        return self._do_banco()

    def test_get_mostra_o_estado_da_conta_sem_campo_editavel_de_sub_e_verificacao(self):
        resposta = self.client.get(self.url)

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Estado da conta")
        self.assertNotContains(resposta, 'name="sub"')
        self.assertNotContains(resposta, 'name="email_verified"')

    def test_desmarcar_is_active_grava_quem_e_quando_desativou(self):
        conta = self._post(is_active=None)

        self.assertFalse(conta.is_active)
        self.assertEqual(conta.desativada_por, "admin")
        self.assertIsNotNone(conta.desativada_em)

    def test_reativar_e_trocar_o_email_zera_desativada_e_verificacao_sem_enviar_email(self):
        User.objects.filter(pk=self.conta.pk).update(
            is_active=False, desativada_por="admin", desativada_em=timezone.now()
        )

        conta = self._post(is_active="on", email="m@x.com")

        self.assertTrue(conta.is_active)
        self.assertEqual(conta.desativada_por, "")
        self.assertIsNone(conta.desativada_em)
        self.assertEqual(conta.email, "m@x.com")
        self.assertIs(conta.email_verified, False)
        self.assertIsNone(conta.email_verificado_em)
        self.assertEqual(len(mail.outbox), 0)

    def test_mudar_so_a_caixa_do_email_mantem_a_verificacao(self):
        conta = self._post(email="L@X.com")

        self.assertEqual(conta.email, "l@x.com")
        self.assertIs(conta.email_verified, True)
        self.assertEqual(conta.email_verificado_em, self.verificado_em)

    def test_adicionar_conta_com_email_que_so_difere_na_caixa_e_recusado(self):
        resposta = self.client.post(
            "/admin/accounts/user/add/",
            {
                "email": "L@X.com",
                "usable_password": "true",
                "password1": "Xy9-s3nha-l0nga",
                "password2": "Xy9-s3nha-l0nga",
            },
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertIn(
            "Já existe uma conta com este e-mail.",
            resposta.context["adminform"].form.errors.get("__all__", []),
        )
        self.assertEqual(User.objects.filter(email__iexact="l@x.com").count(), 1)

    def _semear_historicos(self):
        for caixa, ip in (("l@x.com", "10.0.0.1"), ("L@X.com", "10.0.0.2")):
            semear_axes(caixa, ip)
        semear_axes("outro@x.com", "10.0.0.3")

    def test_trocar_o_email_apaga_o_historico_do_antigo_nas_tres_tabelas_e_so_dele(self):
        """T-61."""
        self._semear_historicos()
        outro = contagem_axes("outro@x.com")
        self.assertEqual(contagem_axes("l@x.com"), (2, 2, 2))

        self._post(email="m@x.com")

        self.assertEqual(contagem_axes("l@x.com"), (0, 0, 0))
        self.assertEqual(contagem_axes("outro@x.com"), outro)

    def test_mudar_so_a_caixa_do_email_nao_apaga_o_historico(self):
        """T-65. Vermelho se a mudança de caixa passar por troca de endereço."""
        self._semear_historicos()

        conta = self._post(email="L@X.com")

        self.assertEqual(conta.email, "l@x.com")
        self.assertEqual(contagem_axes("l@x.com"), (2, 2, 2))
        self.assertEqual(contagem_axes("outro@x.com"), (1, 1, 1))

    def test_salvar_mudando_so_o_nome_nao_apaga_o_historico(self):
        """T-61."""
        self._semear_historicos()

        conta = self._post(first_name="Nova")

        self.assertEqual(conta.first_name, "Nova")
        self.assertEqual(contagem_axes("l@x.com"), (2, 2, 2))
        self.assertEqual(contagem_axes("outro@x.com"), (1, 1, 1))
