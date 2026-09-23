"""TASK-019/T-08 — a política de senha (`AUTH_PASSWORD_VALIDATORS`, `config/settings.py`) nas
quatro superfícies em que uma senha é ESCOLHIDA: o formulário de adicionar conta do admin, o de
trocar senha do admin, `changepassword` e `createsuperuser` interativo.

Demanda do quality-assurance (TASK-019/Fase 7). Nível integração: as quatro superfícies são
comandos e views prontas de `django.contrib.auth`, e o que está sob prova é a COSTURA entre elas
e a lista de validadores — nunca a lista isolada, que um teste unitário só repetiria.

Toda asserção de recusa é pelo `code` do `ValidationError` de
`django.contrib.auth.password_validation` — `password_too_short`, `password_too_common`,
`password_entirely_numeric`, `password_too_similar` —, nunca pelo texto da mensagem, que muda
com correção de i18n (mesmo precedente de `tests/test_login_view.py`, sobre "errorlist").
"""

import sys
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

User = get_user_model()

# As quatro senhas fracas do enunciado, uma por validador, e a razão de cada escolha:
SENHA_CURTA = "Ab1!x"  # 5 caracteres: MinimumLengthValidator (mínimo 8).
SENHA_COMUM = "password"  # 8 caracteres — passa o mínimo —, mas está na lista de comuns.
SENHA_NUMERICA_NAO_COMUM = "83920174659"  # 11 dígitos, fora da lista de comuns
# ("1234567890" está na lista, e o enunciado pede uma que não esteja).
SENHA_FORTE = "Trilha-Auditoria-2026!"  # cumpre os quatro validadores para qualquer e-mail
# usado nestes testes — nenhum deles usa "trilha", "auditoria" nem "2026" no e-mail.


def _codigos_do_erro(form, campo):
    """Os `code` de cada `ValidationError` sob `campo`, nunca o texto — ver docstring do
    módulo. `errors.as_data()` devolve a lista já achatada: `validate_password` levanta um
    `ValidationError` só, mas com uma lista de sub-erros dentro (um por validador que
    reprovou), e `add_error` desempacota essa lista em entradas individuais."""
    return {erro.code for erro in form.errors.as_data().get(campo, [])}


class AdminAdicionarContaPoliticaDeSenhaTests(TestCase):
    """(a) — POST /admin/accounts/user/add/, uma senha por validador, mais uma que cumpre
    os quatro."""

    def setUp(self):
        self.superuser = User.objects.create_superuser(
            email="admin-t08a@example.com", password="senha-forte-o-suficiente"
        )
        self.client.force_login(self.superuser)

    def _dados(self, email, senha):
        return {"email": email, "password1": senha, "password2": senha}

    def test_curta_comum_numerica_e_parecida_com_email_sao_recusadas(self):
        casos = (
            ("curta-t08a@example.com", SENHA_CURTA, "password_too_short"),
            ("comum-t08a@example.com", SENHA_COMUM, "password_too_common"),
            (
                "numerica-t08a@example.com",
                SENHA_NUMERICA_NAO_COMUM,
                "password_entirely_numeric",
            ),
        )
        for email, senha, codigo_esperado in casos:
            with self.subTest(email=email):
                contagem_antes = User.objects.count()
                resposta = self.client.post(
                    "/admin/accounts/user/add/", self._dados(email, senha)
                )
                self.assertEqual(resposta.status_code, 200)
                codigos = _codigos_do_erro(resposta.context["adminform"].form, "password2")
                self.assertIn(codigo_esperado, codigos)
                self.assertEqual(User.objects.count(), contagem_antes)

        # A quarta: senha igual ao próprio e-mail que está sendo cadastrado —
        # `UserAttributeSimilarityValidator` compara contra `email` (config/settings.py).
        email_similaridade = "parecida-com-a-senha-t08a@example.com"
        contagem_antes = User.objects.count()
        resposta = self.client.post(
            "/admin/accounts/user/add/", self._dados(email_similaridade, email_similaridade)
        )
        self.assertEqual(resposta.status_code, 200)
        codigos = _codigos_do_erro(resposta.context["adminform"].form, "password2")
        self.assertIn("password_too_similar", codigos)
        self.assertEqual(User.objects.count(), contagem_antes)

    def test_senha_que_cumpre_os_quatro_validadores_cria_a_conta(self):
        email = "forte-t08a@example.com"
        resposta = self.client.post("/admin/accounts/user/add/", self._dados(email, SENHA_FORTE))

        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(User.objects.filter(email=email).exists())


class AdminTrocarSenhaPoliticaDeSenhaTests(TestCase):
    """(b) — POST /admin/accounts/user/<pk>/password/."""

    def setUp(self):
        self.superuser = User.objects.create_superuser(
            email="admin-t08b@example.com", password="senha-forte-o-suficiente"
        )
        self.client.force_login(self.superuser)
        self.alvo = User.objects.create_user(
            email="alvo-t08b@example.com", password="senha-original-forte-o-suficiente"
        )

    def test_senha_parecida_com_o_email_da_conta_e_recusada_e_a_antiga_continua_valendo(self):
        resposta = self.client.post(
            f"/admin/accounts/user/{self.alvo.pk}/password/",
            {"password1": self.alvo.email, "password2": self.alvo.email},
        )

        self.assertEqual(resposta.status_code, 200)
        codigos = _codigos_do_erro(resposta.context["form"], "password2")
        self.assertIn("password_too_similar", codigos)

        self.alvo.refresh_from_db()
        self.assertTrue(self.alvo.check_password("senha-original-forte-o-suficiente"))

    def test_senha_forte_e_aceita(self):
        resposta = self.client.post(
            f"/admin/accounts/user/{self.alvo.pk}/password/",
            {"password1": SENHA_FORTE, "password2": SENHA_FORTE},
        )

        self.assertEqual(resposta.status_code, 302)
        self.alvo.refresh_from_db()
        self.assertTrue(self.alvo.check_password(SENHA_FORTE))


class ChangepasswordPoliticaDeSenhaTests(TestCase):
    """(c) — `call_command("changepassword", email)`, `getpass.getpass` mockado."""

    def setUp(self):
        self.usuario = User.objects.create_user(
            email="changepassword-t08c@example.com",
            password="senha-original-forte-o-suficiente",
        )

    def test_tres_senhas_fracas_esgotam_as_tentativas_e_nao_mudam_a_senha(self):
        # MAX_TRIES=3 no comando (django/contrib/auth/management/commands/changepassword.py):
        # cada tentativa lê dois getpass (p1, "de novo"), e a mesma senha fraca nas duas
        # tentativas de cada rodada evita o desvio por "não bate" — o que se quer exercitar
        # é a recusa do VALIDADOR, não a de digitação divergente.
        with mock.patch("getpass.getpass", side_effect=[SENHA_CURTA] * 6):
            with self.assertRaises(CommandError):
                call_command("changepassword", self.usuario.email, stdout=StringIO(), stderr=StringIO())

        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password("senha-original-forte-o-suficiente"))

    def test_uma_senha_forte_e_aplicada(self):
        with mock.patch("getpass.getpass", side_effect=[SENHA_FORTE, SENHA_FORTE]):
            call_command(
                "changepassword", self.usuario.email, stdout=StringIO(), stderr=StringIO()
            )

        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(SENHA_FORTE))


class CreatesuperuserInterativoPoliticaDeSenhaTests(TestCase):
    """(d) — `call_command("createsuperuser", interactive=True)`, com `sys.stdin.isatty`
    mockado para `True`: sem isso, o comando sai cedo com "Superuser creation skipped... not
    running in a TTY" (`NotRunningInTTYException`), e nenhum `getpass` chega a ser chamado —
    é o comportamento real do runner de teste, cujo `stdin` não é um terminal."""

    def _stdin_de_terminal_falso(self):
        stdin = mock.MagicMock()
        stdin.isatty.return_value = True
        return stdin

    def test_fraca_com_bypass_recusado_reabre_o_pedido_e_forte_cria_a_conta(self):
        email = "createsuperuser-t08d-bypass@example.com"
        stderr = StringIO()

        with mock.patch("sys.stdin", self._stdin_de_terminal_falso()), mock.patch(
            "getpass.getpass", side_effect=[SENHA_CURTA, SENHA_CURTA, SENHA_FORTE, SENHA_FORTE]
        ), mock.patch("builtins.input", side_effect=["N"]):
            call_command(
                "createsuperuser",
                interactive=True,
                email=email,
                stdout=StringIO(),
                stderr=stderr,
            )

        # A recusa da senha fraca escreveu em stderr antes do prompt de bypass.
        self.assertTrue(stderr.getvalue().strip())

        criado = User.objects.get(email=email)
        self.assertTrue(criado.is_superuser)
        self.assertTrue(criado.check_password(SENHA_FORTE))

    def test_so_fracas_sem_bypass_nao_cria_a_conta(self):
        email = "createsuperuser-t08d-sem-bypass@example.com"

        with mock.patch("sys.stdin", self._stdin_de_terminal_falso()), mock.patch(
            # A terceira chamada de getpass nunca precisa devolver senha nenhuma: o
            # `KeyboardInterrupt` interrompe o laço no mesmo ponto em que um Ctrl-C
            # interromperia um operador real recusando repetidamente o bypass — o comando
            # não tem teto de tentativas próprio (diferente de `changepassword`), e é essa
            # ausência de teto que este caso prova sem entrar em laço infinito.
            "getpass.getpass",
            side_effect=[SENHA_CURTA, SENHA_CURTA, KeyboardInterrupt()],
        ), mock.patch("builtins.input", side_effect=["N"]):
            with self.assertRaises(SystemExit):
                call_command(
                    "createsuperuser",
                    interactive=True,
                    email=email,
                    stdout=StringIO(),
                    stderr=StringIO(),
                )

        self.assertFalse(User.objects.filter(email=email).exists())
