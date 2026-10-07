"""TASK-028/T-62 — `accounts/tentativas.py`, o esquecimento e o desbloqueio do `axes`.

Demanda do quality-assurance. Nível unitário sobre duas funções, que ainda assim precisam do
banco: o que se afirma é o que ficou nas três tabelas do `axes`.

`esquecer_tentativas` apaga o endereço em qualquer caixa nas três tabelas e preserva outro
endereço: as linhas anteriores à ADR 0031 trazem o e-mail como foi digitado. `desbloquear` apaga
só `AccessAttempt` (o contador do bloqueio), em duas caixas, e preserva `AccessFailureLog` e
`AccessLog`: a redefinição não tira o endereço da conta, e o histórico dele continua sendo dela.

Vermelho se `desbloquear` voltar a apagar o histórico, se `esquecer_tentativas` deixar uma das
três tabelas, ou se a comparação deixar de ignorar a caixa.
"""

from axes.handlers.proxy import AxesProxyHandler
from axes.models import AccessAttempt
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from accounts.tentativas import TentativasPorConta, desbloquear, esquecer_tentativas
from tests.paginas_helpers import contagem_axes, semear_axes


class TentativasTests(TestCase):
    def setUp(self):
        semear_axes("Pessoa@Ex.com", "10.0.0.1")
        semear_axes("pessoa@ex.com", "10.0.0.2")
        semear_axes("outro@ex.com", "10.0.0.3")

    def test_esquecer_apaga_as_duas_caixas_nas_tres_tabelas_e_preserva_outro_endereco(self):
        esquecer_tentativas("pessoa@ex.com")

        self.assertEqual(contagem_axes("pessoa@ex.com"), (0, 0, 0))
        self.assertEqual(contagem_axes("outro@ex.com"), (1, 1, 1))

    def test_desbloquear_apaga_so_o_contador_e_preserva_o_historico(self):
        desbloquear("pessoa@ex.com")

        self.assertEqual(contagem_axes("pessoa@ex.com"), (0, 2, 2))
        self.assertEqual(contagem_axes("outro@ex.com"), (1, 1, 1))

    def test_desbloquear_devolve_quantas_linhas_apagou(self):
        self.assertEqual(desbloquear("pessoa@ex.com"), 2)
        self.assertEqual(desbloquear("pessoa@ex.com"), 0)


class HandlerDoAxesTests(TestCase):
    """TASK-028/T-71 — o login bem-sucedido zera só as falhas da própria conta (ADR 0031).

    Integração: o handler configurado, o `axes` e o formulário de login se encontram no POST.
    A vítima V leva duas falhas da origem X; a origem X entra então na conta A, a sua. Com o
    handler do projeto, as falhas de X contra V ficam; com o de banco da biblioteca, o login as
    apaga (`ip_address` é um dos filtros de `AXES_LOCKOUT_PARAMETERS`). O caso de mutação prova
    que o teste distingue os dois. Vermelho se `AXES_HANDLER` voltar ao da biblioteca, se
    `reset_user_attempts` deixar de ser sobrescrito, ou se a conta entrada deixar de ser zerada.
    """

    SENHA = "senha-forte-o-suficiente-t71"
    X = "10.71.0.1"

    def setUp(self):
        User = get_user_model()
        self.vitima = User.objects.create_user(email="vitima@ex.com", password=self.SENHA)
        self.conta_a = User.objects.create_user(email="a@ex.com", password=self.SENHA)

    def _post(self, email, senha, ip=None):
        return self.client.post(
            "/accounts/login/",
            {"username": email, "password": senha},
            REMOTE_ADDR=ip or self.X,
        )

    def _cenario(self):
        for _ in range(2):
            self.assertEqual(self._post("vitima@ex.com", "errada-errada").status_code, 200)
        self.assertEqual(self._post("a@ex.com", "errada-errada").status_code, 200)
        self.assertEqual(self._post("a@ex.com", self.SENHA).status_code, 302)

    def _falhas_contra_a_vitima(self):
        return list(
            AccessAttempt.objects.filter(username="vitima@ex.com", ip_address=self.X).values_list(
                "failures_since_start", flat=True
            )
        )

    def test_o_axes_resolve_o_handler_do_projeto(self):
        self.assertIsInstance(AxesProxyHandler.get_implementation(), TentativasPorConta)

    def test_o_login_na_conta_a_mantem_as_falhas_da_origem_contra_a_vitima(self):
        self._cenario()

        self.assertEqual(self._falhas_contra_a_vitima(), [2])
        # E zera as da própria conta entrada: o desbloqueio de A continua funcionando.
        self.assertFalse(AccessAttempt.objects.filter(username="a@ex.com").exists())

    @override_settings(AXES_HANDLER="axes.handlers.database.AxesDatabaseHandler")
    def test_mutacao_com_o_handler_da_biblioteca_as_falhas_da_vitima_somem(self):
        self.assertNotIsInstance(AxesProxyHandler.get_implementation(), TentativasPorConta)

        self._cenario()

        self.assertEqual(self._falhas_contra_a_vitima(), [])

    def test_o_login_da_propria_vitima_zera_as_falhas_dela_de_toda_origem(self):
        self._post("vitima@ex.com", "errada-errada", ip="10.71.0.2")
        self._post("vitima@ex.com", "errada-errada", ip="10.71.0.3")

        self.assertEqual(self._post("vitima@ex.com", self.SENHA, ip="10.71.0.4").status_code, 302)

        self.assertFalse(AccessAttempt.objects.filter(username="vitima@ex.com").exists())
