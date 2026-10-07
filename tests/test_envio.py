"""TASK-028/T-16 a T-20 — o envio de e-mail de `accounts/envio.py`.

Demandas do quality-assurance. T-16 e T-19 são integração (banco e thread reais), T-20 também
(Redis real), T-17 e T-18 são unitários na intenção: o que se prova é o que o ramo de erro
escreve no log. As linhas são capturadas pelo `FormatadorJSON` de produção
(`tests/envio_helpers.py`), e a regra de todas as de falha é a mesma: nenhum `@` em lugar
nenhum. O endereço é o dado que o log não pode levar (ADR 0031).

O runner desliga o teto e o envio em thread (`tests/runner.py`); os casos que os querem os
reativam por `override_settings`. As chaves do Redis que um caso enche saem por
`chave_do_envio`, no `finally` — nunca `cache.clear()`, que é `FLUSHDB`.
"""

import hashlib
import smtplib
import threading
import uuid
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.mail import EmailMessage
from django.db import transaction
from django.test import TestCase, TransactionTestCase, override_settings
from redis.exceptions import ConnectionError as ErroDeConexaoRedis
from redis.exceptions import TimeoutError as TempoEsgotadoRedis

from accounts import envio
from config import observabilidade
from tests.envio_helpers import BackendQueBloqueia, BackendQueLevanta, campos, capturar_envio

REMETENTE = "IdP <nao-responda@exemplo.com>"
CAMINHO_FALSO = "tests.envio_helpers."


def _msg(destinatario="fulana@exemplo.com"):
    return EmailMessage("assunto", "corpo", REMETENTE, [destinatario])


class _ComRequestId:
    """Põe o `request_id` da origem no ContextVar e o repõe no fim."""

    def _por_request_id(self, valor):
        token = observabilidade._request_id.set(valor)
        self.addCleanup(observabilidade._request_id.reset, token)


class DepoisDoCommitTests(TestCase):
    """T-16 — o envio parte de `on_commit`. Vermelho se sair fora dele."""

    def test_rollback_nao_envia(self):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            with transaction.atomic():
                envio.enfileirar(_msg(), "t", aviso=False)
                transaction.set_rollback(True)
        self.assertEqual(callbacks, [])
        self.assertEqual(mail.outbox, [])

    def test_commit_envia_so_depois_do_bloco(self):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            with transaction.atomic():
                self.assertTrue(envio.enfileirar(_msg(), "t", aviso=False))
                self.assertEqual(mail.outbox, [])
            # O atomic confirmou, mas o `TestCase` segura o commit real: o callback espera o
            # fim da captura.
            self.assertEqual(mail.outbox, [])
        self.assertEqual(len(callbacks), 1)
        self.assertEqual(len(mail.outbox), 1)


class DepoisDoCommitRealTests(TransactionTestCase):
    """T-16, sem o `TestCase` no meio: o commit é o do banco."""

    def test_rollback_nao_envia_e_commit_envia_ao_sair_do_bloco(self):
        with transaction.atomic():
            envio.enfileirar(_msg(), "t", aviso=False)
            transaction.set_rollback(True)
        self.assertEqual(mail.outbox, [])

        with transaction.atomic():
            envio.enfileirar(_msg(), "t", aviso=False)
            self.assertEqual(mail.outbox, [])
        self.assertEqual(len(mail.outbox), 1)


class FalhaDeSmtpTests(_ComRequestId, TestCase):
    """T-17 — SMTP recusa ou a rede cai: uma linha ERROR sem endereço, e a transação vive."""

    def _envia_e_captura(self, erro):
        self._por_request_id("rid-origem-0001")
        BackendQueLevanta.ERRO = erro
        self.addCleanup(setattr, BackendQueLevanta, "ERRO", None)
        User = get_user_model()
        with override_settings(EMAIL_BACKEND=CAMINHO_FALSO + "BackendQueLevanta"):
            with capturar_envio() as linhas:
                with self.captureOnCommitCallbacks(execute=True):
                    with transaction.atomic():
                        User.objects.create_user(email="gravada@exemplo.com", password="x")
                        envio.enfileirar(_msg(), "cadastro", aviso=False)
        self.assertTrue(User.objects.filter(email="gravada@exemplo.com").exists())
        return linhas

    def _confere(self, linhas, classe):
        self.assertEqual(len(linhas), 1)
        for linha in linhas:
            self.assertNotIn("@", linha)
        dados = campos(linhas[0])
        self.assertEqual(dados["level"], "ERROR")
        self.assertEqual(dados["outcome"], "envio_falhou")
        self.assertEqual(dados["tipo"], "cadastro")
        self.assertEqual(dados["error_class"], classe)
        self.assertEqual(dados["request_id"], "rid-origem-0001")
        self.assertNotIn("exc", dados)

    def test_destinatario_recusado(self):
        erro = smtplib.SMTPRecipientsRefused(
            {"fulana@exemplo.com": (550, b"fulana@exemplo.com rejected")}
        )
        self._confere(self._envia_e_captura(erro), "SMTPRecipientsRefused")

    def test_conexao_recusada(self):
        self._confere(self._envia_e_captura(ConnectionRefusedError()), "ConnectionRefusedError")


class DefeitoNoEnvioTests(TestCase):
    """T-18 — exceção que não é do SMTP: linha ERROR com a pilha seca, sem mensagem."""

    def test_bad_header_error_nao_vaza_o_endereco_nem_na_pilha(self):
        with capturar_envio() as linhas:
            envio._enviar(_msg("fulana@exemplo.com\n"), "cadastro")  # nao propaga
        self.assertEqual(len(linhas), 1)
        self.assertNotIn("@", linhas[0])
        dados = campos(linhas[0])
        self.assertEqual(dados["level"], "ERROR")
        self.assertEqual(dados["tipo"], "cadastro")
        self.assertEqual(dados["outcome"], "envio_defeito")
        self.assertEqual(dados["error_class"], "BadHeaderError")
        self.assertNotIn("exc", dados)
        self.assertIn("File", dados["pilha"])

    def test_a_pilha_nao_traz_a_cadeia_nem_as_mensagens(self):
        # O erro é montado aqui, e `raise self.ERRO` no backend: a linha-fonte que a pilha
        # copia não pode conter o texto que o caso quer ver ausente.
        erro = RuntimeError("falha com " + "outro" + "@" + "exemplo.com")
        erro.__cause__ = ValueError("causa de " + "fulana" + "@" + "exemplo.com")
        BackendQueLevanta.ERRO = erro
        self.addCleanup(setattr, BackendQueLevanta, "ERRO", None)
        with override_settings(EMAIL_BACKEND=CAMINHO_FALSO + "BackendQueLevanta"):
            with capturar_envio() as linhas:
                envio._enviar(_msg(), "cadastro")
        self.assertEqual(len(linhas), 1)
        linha = linhas[0]
        self.assertNotIn("@", linha)
        for fragmento in ("outro", "fulana", "causa de", "falha com", "direct cause", "ValueError"):
            self.assertNotIn(fragmento, linha)
        dados = campos(linha)
        self.assertEqual(dados["error_class"], "RuntimeError")
        self.assertEqual(dados["outcome"], "envio_defeito")
        self.assertNotIn("exc", dados)


@override_settings(ENVIO_DE_EMAIL_EM_SEGUNDO_PLANO=True)
class EmSegundoPlanoTests(_ComRequestId, TestCase):
    """T-19 — a thread: o callback retorna com o envio pendente, ela não é daemon, e leva o
    contexto da chamada."""

    def setUp(self):
        BackendQueBloqueia.reiniciar()
        self.addCleanup(BackendQueBloqueia.reiniciar)
        self._por_request_id("rid-origem-0002")

    def _enfileira(self):
        antes = set(threading.enumerate())
        with override_settings(EMAIL_BACKEND=CAMINHO_FALSO + "BackendQueBloqueia"):
            with self.captureOnCommitCallbacks(execute=True):
                envio.enfileirar(_msg(), "cadastro", aviso=False)
        novas = set(threading.enumerate()) - antes
        self.assertEqual(len(novas), 1)
        (thread,) = novas
        self.addCleanup(BackendQueBloqueia.LIBERADO.set)
        return thread

    def test_o_callback_retorna_pendente_e_a_thread_nao_e_daemon(self):
        thread = self._enfileira()
        self.assertFalse(thread.daemon)
        self.assertTrue(thread.is_alive())
        self.assertEqual(BackendQueBloqueia.ENVIADAS, [])
        self.assertEqual(mail.outbox, [])

        BackendQueBloqueia.LIBERADO.set()
        thread.join(timeout=10)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(BackendQueBloqueia.ENVIADAS), 1)

    def test_a_falha_na_thread_traz_o_request_id_da_chamada(self):
        BackendQueBloqueia.ERRO = ConnectionRefusedError()
        with capturar_envio() as linhas:
            thread = self._enfileira()
            # O contexto de quem chamou muda depois: a linha leva o capturado, e não este.
            observabilidade._request_id.set("rid-posterior")
            BackendQueBloqueia.LIBERADO.set()
            thread.join(timeout=10)
        self.assertEqual(len(linhas), 1)
        dados = campos(linhas[0])
        self.assertEqual(dados["outcome"], "envio_falhou")
        self.assertEqual(dados["request_id"], "rid-origem-0002")


@override_settings(TETO_DE_ENVIOS_POR_DESTINATARIO=5)
class TetoPorDestinatarioTests(TestCase):
    """T-20 — cinco por hora por endereço, contados sem distinguir a caixa, no Redis real.

    T-75 — os avisos de segurança têm teto próprio (vinte), chave `throttle:aviso:` separada da
    das confirmações e linha `aviso_suprimido` no vigésimo primeiro. Vermelho se a chave do aviso
    voltar a ser a do envio, ou se `aviso=True` voltar a passar sem contar."""

    def setUp(self):
        self.endereco = f"t20-{uuid.uuid4().hex}@exemplo.com"
        # `chave_do_envio` e não `cache.clear()`: o `RedisCache` o implementa como `FLUSHDB`.
        self.addCleanup(cache.delete, envio.chave_do_envio(self.endereco))

    def _enfileira(self, destinatario=None, aviso=False):
        with self.captureOnCommitCallbacks(execute=True):
            return envio.enfileirar(_msg(destinatario or self.endereco), "cadastro", aviso=aviso)

    def test_o_sexto_e_suprimido_com_aviso_sem_endereco(self):
        caixas = [self.endereco, self.endereco.upper()]
        for i in range(5):
            self.assertTrue(self._enfileira(caixas[i % 2]))
        self.assertEqual(len(mail.outbox), 5)

        with capturar_envio() as linhas:
            self.assertFalse(self._enfileira(caixas[1]))
        self.assertEqual(len(mail.outbox), 5)
        self.assertEqual(len(linhas), 1)
        self.assertNotIn("@", linhas[0])
        dados = campos(linhas[0])
        self.assertEqual(dados["level"], "WARNING")
        self.assertEqual(dados["outcome"], "envio_suprimido")
        self.assertEqual(dados["tipo"], "cadastro")

    @override_settings(TETO_DE_AVISOS_POR_DESTINATARIO=20)
    def test_o_aviso_tem_chave_propria_e_o_teto_de_cinco_nao_o_suprime(self):
        self.addCleanup(cache.delete, envio.chave_do_aviso(self.endereco))
        with capturar_envio():  # o sexto gera a linha de supressão, que aqui não é o objeto
            for _ in range(6):
                self._enfileira()
        self.assertEqual(len(mail.outbox), 5)

        self.assertTrue(self._enfileira(aviso=True))

        self.assertEqual(len(mail.outbox), 6)
        # O aviso contou na chave dele, e a das confirmações ficou onde estava.
        self.assertEqual(cache.get(envio.chave_do_aviso(self.endereco)), 1)
        self.assertEqual(cache.get(envio.chave_do_envio(self.endereco)), 6)
        self.assertNotEqual(envio.chave_do_aviso(self.endereco), envio.chave_do_envio(self.endereco))

    @override_settings(TETO_DE_AVISOS_POR_DESTINATARIO=20)
    def test_o_vigesimo_primeiro_aviso_e_suprimido_com_linha_aviso_suprimido(self):
        self.addCleanup(cache.delete, envio.chave_do_aviso(self.endereco))
        for _ in range(20):
            self.assertTrue(self._enfileira(aviso=True))
        self.assertEqual(len(mail.outbox), 20)

        with capturar_envio() as linhas:
            self.assertFalse(self._enfileira(aviso=True))

        self.assertEqual(len(mail.outbox), 20)
        self.assertEqual(len(linhas), 1)
        self.assertNotIn("@", linhas[0])
        dados = campos(linhas[0])
        self.assertEqual(dados["level"], "WARNING")
        self.assertEqual(dados["outcome"], "aviso_suprimido")
        self.assertEqual(dados["tipo"], "cadastro")
        # A chave das confirmações não foi tocada pelos avisos.
        self.assertIsNone(cache.get(envio.chave_do_envio(self.endereco)))

    @override_settings(TETO_DE_AVISOS_POR_DESTINATARIO=None)
    def test_sem_teto_de_avisos_a_chave_do_aviso_nao_e_criada(self):
        self.assertTrue(self._enfileira(aviso=True))
        self.assertIsNone(cache.get(envio.chave_do_aviso(self.endereco)))

    @override_settings(TETO_DE_AVISOS_POR_DESTINATARIO=20)
    def test_redis_fora_o_aviso_sai_com_linha_throttle_unavailable(self):
        with mock.patch("accounts.envio.contagem_na_janela", side_effect=ErroDeConexaoRedis("x")):
            with capturar_envio() as linhas:
                self.assertTrue(self._enfileira(aviso=True))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(campos(linhas[0])["outcome"], "throttle_unavailable")

    def test_a_chave_do_aviso_e_o_resumo_do_endereco_em_minusculas(self):
        x = "Fulana@Exemplo.com"
        resumo = hashlib.sha256(x.lower().encode("utf-8")).hexdigest()
        self.assertEqual(envio.chave_do_aviso(x), "throttle:aviso:" + resumo)
        self.assertEqual(envio.chave_do_aviso(x), envio.chave_do_aviso(x.upper()))
        self.assertNotIn("@", envio.chave_do_aviso(x))

    def test_a_chave_e_o_resumo_do_endereco_em_minusculas(self):
        x = "Fulana@Exemplo.com"
        resumo = hashlib.sha256(x.lower().encode("utf-8")).hexdigest()
        self.assertEqual(envio.chave_do_envio(x), "throttle:envio:" + resumo)
        self.assertEqual(envio.chave_do_envio(x), envio.chave_do_envio(x.upper()))
        self.assertNotIn("@", envio.chave_do_envio(x))
        self._enfileira()
        self.assertEqual(cache.get(envio.chave_do_envio(self.endereco)), 1)

    @override_settings(TETO_DE_ENVIOS_POR_DESTINATARIO=None)
    def test_sem_teto_a_chave_nao_e_criada(self):
        self.assertTrue(self._enfileira())
        self.assertIsNone(cache.get(envio.chave_do_envio(self.endereco)))

    def test_redis_fora_a_falha_e_aberta_com_aviso(self):
        for erro in (ErroDeConexaoRedis("x"), TempoEsgotadoRedis("x")):
            with self.subTest(erro=type(erro).__name__):
                mail.outbox.clear()
                with mock.patch("accounts.envio.contagem_na_janela", side_effect=erro):
                    with capturar_envio() as linhas:
                        self.assertTrue(self._enfileira())
                self.assertEqual(len(mail.outbox), 1)
                self.assertEqual(len(linhas), 1)
                self.assertNotIn("@", linhas[0])
                dados = campos(linhas[0])
                self.assertEqual(dados["level"], "WARNING")
                self.assertEqual(dados["outcome"], "throttle_unavailable")
                self.assertEqual(dados["tipo"], "cadastro")
