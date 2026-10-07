"""TASK-028/T-02, T-03, T-04 e T-05 — o modelo `accounts.User`: a restrição de e-mail no banco,
o manager, o carimbo `senha_alterada_em` e as regras de `updated_at` e da verificação.

Demanda do quality-assurance (TASK-028). T-02 é integração: a restrição `Lower(email)` só se
prova no banco, por escritas que passam por baixo do `save()`. T-03 a T-05 são unitárias e
leem sempre do banco, nunca da instância, porque o que se afirma é o que ficou gravado.

`QuerySet.update()` prepara o estado de cada caso (`senha_alterada_em` nulo, `updated_at`
antigo, hash legado) justamente por passar por baixo das regras do `save()`: com o `save()`
as regras sob prova moveriam o que o caso quer observar parado.
"""

import io
import uuid
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import PBKDF2PasswordHasher
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

User = get_user_model()

SENHA = "senha-forte-o-suficiente"
SENHA_NOVA = "Trilha-Auditoria-2026!"


def _do_banco(user):
    return User.objects.get(pk=user.pk)


class RestricaoDeEmailNoBancoTests(TestCase):
    """T-02. A restrição `Lower(email)` recusa, no banco, o que o `save()` não viu."""

    def setUp(self):
        User.objects.create_user("a@x.com", SENHA)
        self.outra = User.objects.create_user("b@x.com", SENHA)

    def test_update_que_so_difere_pela_caixa_levanta_integrity_error(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.filter(pk=self.outra.pk).update(email="A@x.com")

        self.assertEqual(_do_banco(self.outra).email, "b@x.com")

    def test_bulk_create_que_so_difere_pela_caixa_levanta_integrity_error(self):
        # `bulk_create` não chama o `save()`, de modo que a caixa chega ao banco como veio.
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.bulk_create([User(email="A@x.com")])

        self.assertEqual(User.objects.filter(email__iexact="a@x.com").count(), 1)


class ManagerESaveDoEmailTests(TestCase):
    """T-03. O e-mail inteiro em minúsculas, no manager e no `save()`, e o `sub` da conta."""

    def test_normalize_email_baixa_o_endereco_inteiro(self):
        # Sozinho, para ficar vermelho se o `.lower()` sair do manager mesmo que o `save()`
        # continue a baixar a caixa na gravação.
        self.assertEqual(User.objects.normalize_email("Fulano@Exemplo.COM"), "fulano@exemplo.com")

    def test_create_user_e_create_superuser_gravam_em_minusculas_com_sub_uuid4(self):
        comum = User.objects.create_user("Fulano@Exemplo.COM", SENHA)
        admin = User.objects.create_superuser("Adm@X.com", SENHA)

        self.assertEqual(_do_banco(comum).email, "fulano@exemplo.com")
        self.assertEqual(_do_banco(admin).email, "adm@x.com")
        for conta in (comum, admin):
            conta = _do_banco(conta)
            self.assertIsInstance(conta.sub, uuid.UUID)
            self.assertEqual(conta.sub.version, 4)
            self.assertIs(conta.email_verified, False)
            self.assertIsNotNone(conta.senha_alterada_em)
        self.assertNotEqual(_do_banco(comum).sub, _do_banco(admin).sub)
        self.assertIs(User._meta.get_field("sub").editable, False)

    def test_save_baixa_o_endereco_mesmo_sem_passar_pelo_manager(self):
        conta = User.objects.create_user("antes@x.com", SENHA)
        conta.email = "X@Y.com"
        conta.save()

        self.assertEqual(_do_banco(conta).email, "x@y.com")

        direta = User(email="Direta@X.COM")
        direta.save()
        self.assertEqual(_do_banco(direta).email, "direta@x.com")


class CarimboDaSenhaTests(TestCase):
    """T-04. `senha_alterada_em` marca a troca de senha e só ela; `updated_at` não se move.

    A marca vem de `_password`, atributo privado do Django que `set_password` liga e que o
    re-hash do login zera antes de gravar. Os casos (e) e (f) são o outro lado dessa mesma
    fronteira: um upgrade do Django que a mude carimba o re-hash, ou deixa de carimbar a troca.
    """

    def setUp(self):
        self.conta = User.objects.create_user("carimbo@x.com", SENHA)
        self.antigo = timezone.now() - timedelta(days=30)
        # `update()` passa por baixo do `save()`: parte-se de nulo e de `updated_at` antigo.
        User.objects.filter(pk=self.conta.pk).update(
            senha_alterada_em=None, updated_at=self.antigo
        )

    def _confere(self, carimbada):
        conta = _do_banco(self.conta)
        if carimbada:
            self.assertIsNotNone(conta.senha_alterada_em)
        else:
            self.assertIsNone(conta.senha_alterada_em)
        self.assertEqual(conta.updated_at, self.antigo)
        return conta

    def test_a_set_password_e_save_carimba(self):
        conta = _do_banco(self.conta)
        conta.set_password(SENHA_NOVA)
        conta.save()

        self._confere(carimbada=True)

    def test_b_set_password_e_save_so_do_password_persiste_o_carimbo(self):
        conta = _do_banco(self.conta)
        conta.set_password(SENHA_NOVA)
        conta.save(update_fields=["password"])

        self._confere(carimbada=True)

    def test_c_changepassword_carimba(self):
        with mock.patch("getpass.getpass", return_value=SENHA_NOVA):
            call_command("changepassword", "carimbo@x.com", stdout=io.StringIO())

        self.assertTrue(_do_banco(self.conta).check_password(SENHA_NOVA))
        self._confere(carimbada=True)

    def test_d_troca_de_senha_pelo_admin_carimba(self):
        admin = User.objects.create_superuser("adm-carimbo@x.com", SENHA)
        self.client.force_login(admin)

        resposta = self.client.post(
            f"/admin/accounts/user/{self.conta.pk}/password/",
            {"password1": SENHA_NOVA, "password2": SENHA_NOVA},
        )

        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(_do_banco(self.conta).check_password(SENHA_NOVA))
        self._confere(carimbada=True)

    def test_e_rehash_no_login_nao_carimba(self):
        legado = PBKDF2PasswordHasher().encode(SENHA, "saltsalt", iterations=1000)
        User.objects.filter(pk=self.conta.pk).update(password=legado)

        conta = _do_banco(self.conta)
        self.assertTrue(conta.check_password(SENHA))

        # Pré-condição: sem o re-hash o caso passaria por vacuidade, sem exercitar o setter.
        self.assertNotEqual(_do_banco(self.conta).password, legado, "o re-hash não aconteceu")
        self._confere(carimbada=False)

    def test_f_login_bem_sucedido_nao_carimba(self):
        resposta = self.client.post(
            "/accounts/login/", {"username": "carimbo@x.com", "password": SENHA}
        )

        self.assertEqual(resposta.status_code, 302)
        self.assertIsNotNone(_do_banco(self.conta).last_login)
        self._confere(carimbada=False)


class RegrasDeUpdatedAtEDaVerificacaoTests(TestCase):
    """T-05. O que move `updated_at` e o que zera a verificação do e-mail, no `save()`."""

    def setUp(self):
        self.conta = User.objects.create_user("regras@x.com", SENHA, first_name="Ana")
        self.antigo = timezone.now() - timedelta(days=30)
        self.verificado_em = timezone.now() - timedelta(days=10)
        # `updated_at` antigo para a diferença ser observável.
        User.objects.filter(pk=self.conta.pk).update(
            updated_at=self.antigo, email_verified=True, email_verificado_em=self.verificado_em
        )

    def _conta(self):
        return _do_banco(self.conta)

    def test_mudar_um_dos_cinco_campos_move_updated_at(self):
        mudancas = {
            "first_name": "Beatriz",
            "last_name": "Souza",
            "nickname": "Bia",
            "email": "outro@x.com",
            "email_verified": False,
        }
        for campo, valor in mudancas.items():
            with self.subTest(campo=campo):
                User.objects.filter(pk=self.conta.pk).update(
                    updated_at=self.antigo, email_verified=True
                )
                conta = self._conta()
                setattr(conta, campo, valor)
                conta.save()

                self.assertGreater(self._conta().updated_at, self.antigo)
                User.objects.filter(pk=self.conta.pk).update(email="regras@x.com")

    def test_o_que_nao_e_perfil_nao_move_updated_at(self):
        def login(conta):
            conta.last_login = timezone.now()
            conta.save(update_fields=["last_login"])

        def senha(conta):
            conta.set_password(SENHA_NOVA)
            conta.save()

        def termos(conta):
            conta.termos_versao = "2026-01"
            conta.termos_aceitos_em = timezone.now()
            conta.save()

        def desativa(conta):
            conta.is_active = False
            conta.desativada_em = timezone.now()
            conta.desativada_por = "admin"
            conta.save()

        def sem_mudanca(conta):
            conta.save()

        def relido(conta):
            conta.refresh_from_db()
            conta.save()

        def so_a_caixa(conta):
            conta.email = "REGRAS@X.com"
            conta.save()

        casos = {
            "login": login,
            "set_password": senha,
            "termos": termos,
            "is_active e desativada_*": desativa,
            "save sem mudança": sem_mudanca,
            "refresh_from_db e save": relido,
            "e-mail diferente só na caixa": so_a_caixa,
        }
        for nome, acao in casos.items():
            with self.subTest(nome):
                acao(self._conta())

                conta = self._conta()
                self.assertEqual(conta.updated_at, self.antigo)
                self.assertEqual(conta.email, "regras@x.com")
                self.assertIs(conta.email_verified, True)
                self.assertEqual(conta.email_verificado_em, self.verificado_em)

    def test_email_novo_zera_a_verificacao_e_move_updated_at(self):
        conta = self._conta()
        conta.email = "novo@x.com"
        conta.save()

        conta = self._conta()
        self.assertEqual(conta.email, "novo@x.com")
        self.assertIs(conta.email_verified, False)
        self.assertIsNone(conta.email_verificado_em)
        self.assertGreater(conta.updated_at, self.antigo)

    def test_update_fields_sem_email_nao_zera_nem_grava_o_endereco(self):
        conta = self._conta()
        conta.email = "novo@x.com"
        conta.first_name = "Carla"
        conta.save(update_fields=["first_name"])

        gravada = self._conta()
        self.assertEqual(gravada.email, "regras@x.com")
        self.assertIs(gravada.email_verified, True)
        self.assertEqual(gravada.email_verificado_em, self.verificado_em)
        self.assertEqual(gravada.first_name, "Carla")
        self.assertGreater(gravada.updated_at, self.antigo)

    def test_update_fields_com_email_zera_a_verificacao_e_grava_o_endereco(self):
        conta = self._conta()
        conta.email = "novo@x.com"
        conta.save(update_fields=["email"])

        gravada = self._conta()
        self.assertEqual(gravada.email, "novo@x.com")
        self.assertIs(gravada.email_verified, False)
        self.assertIsNone(gravada.email_verificado_em)
        self.assertGreater(gravada.updated_at, self.antigo)
