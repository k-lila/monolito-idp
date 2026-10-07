"""TASK-028/T-22 — as mensagens de aviso de `accounts/emails.py`.

Demanda do quality-assurance. Nível unitário, sem banco: as quatro funções leem só o `email` do
usuário e a hora. `timezone.now` fica fixo em 2026-01-15T02:30Z, que é 14/01/2026 às 23:30 em
Brasília: a data é outra, e é o que separa um fuso aplicado de um fuso ignorado.

O texto não leva dado que a jornada da conta (ADR 0031) não prevê: nenhum endereço, e em
particular o aviso de troca não traz o endereço novo, que não entra nem na assinatura da função.
Os assuntos são afirmados por literal, para o idioma também ficar preso.
"""

from datetime import datetime, timezone as fuso_utc
from types import SimpleNamespace
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase
from django.utils import timezone, translation

from accounts import emails

AGORA = datetime(2026, 1, 15, 2, 30, tzinfo=fuso_utc.utc)
DESTINATARIO = "antiga@exemplo.com"
USUARIO = SimpleNamespace(email=DESTINATARIO)

CASOS = {
    "aviso_de_troca_de_email": (
        lambda: emails.aviso_de_troca_de_email(DESTINATARIO),
        "O e-mail da sua conta foi trocado",
    ),
    "senha_trocada": (
        lambda: emails.senha_trocada(USUARIO),
        "A senha da sua conta foi trocada",
    ),
    "conta_desativada": (
        lambda: emails.conta_desativada(USUARIO),
        "A sua conta foi desativada",
    ),
    "conta_apagada": (
        lambda: emails.conta_apagada(DESTINATARIO),
        "A sua conta foi apagada",
    ),
}


class MensagensDeAvisoTests(SimpleTestCase):
    def test_hora_em_brasilia_assunto_remetente_e_destinatario(self):
        for nome, (montar, assunto) in CASOS.items():
            with self.subTest(nome), mock.patch("django.utils.timezone.now", return_value=AGORA):
                msg = montar()
                self.assertIn("14/01/2026 às 23:30 (horário de Brasília)", msg.body)
                self.assertEqual(msg.subject, assunto)
                self.assertNotIn("\n", msg.subject)
                self.assertEqual(msg.from_email, settings.DEFAULT_FROM_EMAIL)
                self.assertEqual(msg.to, [DESTINATARIO])

    def test_o_texto_nao_leva_endereco_nem_link(self):
        for nome, (montar, _) in CASOS.items():
            with self.subTest(nome), mock.patch("django.utils.timezone.now", return_value=AGORA):
                msg = montar()
                self.assertNotIn("@", msg.body)
                self.assertNotIn("http", msg.body)

    def test_idioma_e_fuso_nao_vazam(self):
        for nome, (montar, _) in CASOS.items():
            with self.subTest(nome), mock.patch("django.utils.timezone.now", return_value=AGORA):
                montar()
                self.assertEqual(translation.get_language(), "en-us")
                self.assertEqual(timezone.get_current_timezone_name(), "UTC")
