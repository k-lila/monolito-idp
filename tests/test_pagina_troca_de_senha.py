"""TASK-028/T-47 — a troca de senha em `/accounts/password_change/`.

Demanda do quality-assurance. Nível integração: `FormularioDeTrocaDeSenha`, o `axes`, a
revogação, a sessão e o destino fixo da SPA só se encontram numa requisição.

Fica vermelho se a senha atual passar a ser conferida por `check_password` (o `axes` deixaria de
contar a falha), se o `success_url` passar a ler o `next` (redirecionamento aberto), se as
outras sessões sobreviverem à troca, se a sessão que trocou cair, ou se a revogação ou o aviso
saírem.
"""

from urllib.parse import urlencode

from axes.models import AccessAttempt
from django.core import mail

from tests.paginas_helpers import (
    EMAIL,
    NOVA,
    SENHA,
    PaginasDeContaTestCase,
    User,
    com_arroba,
    eventos,
    vivos,
)

URL = "/accounts/password_change/"


def _dados(atual=SENHA, nova=NOVA, **extra):
    return {"old_password": atual, "new_password1": nova, "new_password2": nova, **extra}


class TrocaDeSenhaTests(PaginasDeContaTestCase):
    def test_sem_sessao_vai_ao_login_com_o_next(self):
        resposta = self.client.get(URL)

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta["Location"], f"/accounts/login/?next={URL}")

    def test_senha_atual_errada_recusa_e_o_axes_conta_uma_falha_no_e_mail_minusculo(self):
        self.client.force_login(self.conta)
        antes = AccessAttempt.objects.filter(username=EMAIL).first()
        falhas_antes = antes.failures_since_start if antes else 0

        resposta = self.postar(self.client, URL, _dados(atual="errada-errada-1"))

        self.assertEqual(resposta.status_code, 200)
        erros = resposta.context["form"].errors.as_data()["old_password"]
        self.assertEqual([e.code for e in erros], ["password_incorrect"])
        self.assertContains(resposta, "incorretamente")
        tentativa = AccessAttempt.objects.get(username=EMAIL)
        self.assertEqual(tentativa.failures_since_start, falhas_antes + 1)
        self.assertFalse(AccessAttempt.objects.exclude(username=EMAIL).exists())
        self.assertTrue(User.objects.get(pk=self.conta.pk).check_password(SENHA))
        self.assertEqual(mail.outbox, [])

    def test_troca_valida_vai_a_spa_e_ignora_o_next_hostil(self):
        sessao = self.tokens_nas_duas()

        resposta = self.postar(
            sessao, f"{URL}?{urlencode({'next': 'https://evil.com'})}", _dados(next="https://evil.com")
        )

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta["Location"], f"{self.spa}/app/conta?aviso=senha-trocada")

    def test_troca_valida_mantem_a_sessao_atual_e_derruba_as_outras(self):
        sessao = self.tokens_nas_duas()
        outra = self.outra_sessao()

        self.postar(sessao, URL, _dados())

        self.assertTrue(User.objects.get(pk=self.conta.pk).check_password(NOVA))
        self.assertSessaoViva(sessao)
        self.assertSessaoDeslogada(outra)

    def test_troca_valida_revoga_os_tokens_de_todas_as_applications_e_registra(self):
        sessao = self.tokens_nas_duas()
        marca = self.trilha()

        self.postar(sessao, URL, _dados())

        for aplicacao in (self.app1, self.app2):
            self.assertEqual(vivos(self.conta, aplicacao), (0, 0, 0))
        linhas = marca()
        self.assertEqual(
            sorted(eventos(linhas)), ["senha_trocada", "tokens_revogados", "tokens_revogados"]
        )
        self.assertCountEqual(
            [l["client_id"] for l in linhas if l["event"] == "tokens_revogados"],
            [self.app1.client_id, self.app2.client_id],
        )
        self.assertEqual(com_arroba(linhas), [])

    def test_o_aviso_nao_sai_com_o_teto_dos_avisos_esgotado_e_a_senha_muda(self):
        """TASK-028/T-76 — com o teto dos avisos esgotado a senha muda e o aviso não sai."""
        self.esgotar_teto_de_avisos(EMAIL)
        self.client.force_login(self.conta)

        self.postar(self.client, URL, _dados())

        self.assertEqual(mail.outbox, [])
        self.conta.refresh_from_db()
        self.assertTrue(self.conta.check_password(NOVA))

    def test_o_aviso_sai_ao_endereco_da_conta_e_tambem_com_o_teto_das_confirmacoes_esgotado(self):
        self.esgotar_teto(EMAIL)
        self.client.force_login(self.conta)

        self.postar(self.client, URL, _dados())

        (aviso,) = mail.outbox
        self.assertEqual(aviso.to, [EMAIL])
        self.assertEqual(aviso.subject, "A senha da sua conta foi trocada")
