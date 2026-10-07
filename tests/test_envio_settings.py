"""TASK-028/T-13 — o runner neutraliza o teto e o envio em thread, e os literais de produção
ficam de pé.

Demanda do quality-assurance. Nível unitário, sem banco. Dois fios num caso só: durante a suíte
valem `None` e `False` (falha se o runner deixar de neutralizá-los), e os valores guardados em
`tests.runner` são os literais de produção (falha se alguém os mudar). Os literais são lidos
dos atributos de módulo do runner, nunca de `settings`, que vale a cópia neutralizada.
"""

from django.conf import settings
from django.test import SimpleTestCase

from tests import runner


class EnvioNeutralizadoPeloRunnerTests(SimpleTestCase):
    def test_a_suite_roda_sem_teto_e_sem_thread(self):
        """TASK-028/T-76 — o runner neutraliza também o teto dos avisos de segurança."""
        self.assertIsNone(settings.TETO_DE_ENVIOS_POR_DESTINATARIO)
        self.assertIsNone(settings.TETO_DE_AVISOS_POR_DESTINATARIO)
        self.assertIs(settings.ENVIO_DE_EMAIL_EM_SEGUNDO_PLANO, False)

    def test_os_valores_guardados_sao_os_literais_de_producao(self):
        """TASK-028/T-76 — o literal de produção do teto dos avisos é vinte."""
        self.assertEqual(runner.TETO_DE_ENVIOS_DE_PRODUCAO, 5)
        self.assertEqual(runner.TETO_DE_AVISOS_DE_PRODUCAO, 20)
        self.assertIs(runner.ENVIO_EM_SEGUNDO_PLANO_DE_PRODUCAO, True)
        # Os outros dois literais do bloco não são neutralizados: valem os de produção.
        self.assertEqual(settings.JANELA_DO_TETO_DE_ENVIOS_SEGUNDOS, 3600)
        self.assertEqual(settings.FUSO_DOS_EMAILS, "America/Sao_Paulo")
