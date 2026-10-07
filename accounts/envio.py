"""O envio de e-mail: os tetos por destinatário, o commit e a thread (ADR 0031).

São dois tetos, com contadores separados. O de confirmações e links é baixo, porque qualquer um
os dispara contra um endereço alheio. O dos avisos de segurança é próprio e alto: sem teto,
quem tem a sessão e a senha de alguém lotaria a caixa dela; com teto de vinte, suprimir um aviso
exige vinte trocas na mesma hora, e cada uma delas já chega à dona.

Recebe a mensagem já montada por `accounts/emails.py` e não sabe o que ela diz. O envio parte
de `transaction.on_commit`: operação desfeita não envia. Corre numa thread do processo, e o
SMTP lento não segura a resposta nem desfaz a operação. A thread não é fila durável: se o
worker morrer durante o envio, a mensagem se perde, e a saída da pessoa é "reenviar" ou
"pedir outro link".

Nenhum endereço sai daqui: nem no log, nem na chave do Redis.
"""

import contextvars
import functools
import hashlib
import logging
import smtplib
import threading
import traceback

from django.conf import settings
from django.db import transaction
from redis.exceptions import ConnectionError as ErroDeConexaoRedis
from redis.exceptions import TimeoutError as TempoEsgotadoRedis

from config.limites import contagem_na_janela

logger = logging.getLogger(__name__)


def _resumo(destinatario):
    return hashlib.sha256(destinatario.lower().encode("utf-8")).hexdigest()


def chave_do_envio(destinatario):
    """A chave do contador de confirmações e links de um destinatário.

    Pública pela mesma razão de `config.limites.chave_do_contador`: é por ela que a suíte
    apaga o contador que encheu, sem `cache.clear()`.
    """
    return f"throttle:envio:{_resumo(destinatario)}"


def chave_do_aviso(destinatario):
    """A chave do contador de avisos de segurança de um destinatário, pública como a de cima."""
    return f"throttle:aviso:{_resumo(destinatario)}"


def enfileirar(mensagem, tipo, *, aviso):
    """Agenda o envio de `mensagem` para depois do commit, e diz se agendou.

    `mensagem` tem um destinatário só, que é o que o teto conta. `tipo` nomeia a mensagem no
    log. `aviso` escolhe o teto: verdadeiro nos avisos de segurança, que têm teto próprio e
    alto, e falso nas confirmações e nos links. Sem default, para que nenhuma chamada caia num
    teto sem tê-lo escolhido.
    """
    (destinatario,) = mensagem.to
    if aviso:
        teto = settings.TETO_DE_AVISOS_POR_DESTINATARIO
        chave, desfecho = chave_do_aviso(destinatario), "aviso_suprimido"
    else:
        teto = settings.TETO_DE_ENVIOS_POR_DESTINATARIO
        chave, desfecho = chave_do_envio(destinatario), "envio_suprimido"
    if not _cabe_no_teto(teto, chave, tipo, desfecho):
        return False
    # O contexto da requisição, capturado agora: no callback, e mais ainda na thread, o
    # `request_id` já não é o desta requisição, e a linha de falha sairia sem ele.
    contexto = contextvars.copy_context()
    transaction.on_commit(functools.partial(_despachar, mensagem, tipo, contexto))
    return True


_MENSAGEM_DA_SUPRESSAO = {
    "envio_suprimido": "envio suprimido pelo teto do destinatário",
    "aviso_suprimido": "aviso suprimido pelo teto do destinatário",
}


def _cabe_no_teto(teto, chave, tipo, desfecho):
    if teto is None:
        return True
    try:
        contagem = contagem_na_janela(chave, settings.JANELA_DO_TETO_DE_ENVIOS_SEGUNDOS)
    except (ErroDeConexaoRedis, TempoEsgotadoRedis):
        # Falha aberta, como no limitador por caminho (ADR 0016): com o Redis fora, o envio
        # sai sem teto enquanto durar a queda.
        logger.warning(
            "teto de envio inativo: cache indisponível",
            extra={"tipo": tipo, "outcome": "throttle_unavailable"},
        )
        return True
    if contagem > teto:
        # A resposta à pessoa não muda: quem dispara contra um endereço alheio não aprende
        # que o teto foi atingido.
        logger.warning(_MENSAGEM_DA_SUPRESSAO[desfecho], extra={"tipo": tipo, "outcome": desfecho})
        return False
    return True


def _despachar(mensagem, tipo, contexto):
    if settings.ENVIO_DE_EMAIL_EM_SEGUNDO_PLANO:
        # Não daemon: na saída normal do interpretador, o Python espera a thread terminar, e
        # um daemon seria cortado no meio do envio.
        threading.Thread(
            target=contexto.run, args=(_enviar, mensagem, tipo), daemon=False
        ).start()
    else:
        contexto.run(_enviar, mensagem, tipo)


def _enviar(mensagem, tipo):
    try:
        mensagem.send()
    except (smtplib.SMTPException, OSError) as erro:
        # Sem `exc_info` e sem `str(erro)`: a resposta do SMTP pode trazer o endereço, como em
        # `SMTPRecipientsRefused`. A classe basta para separar rede, autenticação e recusa.
        logger.error(
            "falha no envio de e-mail",
            extra={"tipo": tipo, "outcome": "envio_falhou", "error_class": type(erro).__name__},
        )
    except Exception as erro:
        # Defeito nosso, e não do SMTP. Na thread não há 500 que o mostre, e sem esta linha ele
        # sumiria no stderr do `threading.excepthook`. Sem `exc_info` e sem `str(erro)`: as
        # exceções de endereço do Django, como `BadHeaderError` e o `ValueError` de
        # `sanitize_address`, trazem o endereço na mensagem. A pilha vai só com arquivo, linha
        # e código de cada quadro; a mensagem e a cadeia encadeada ficam fora do log.
        logger.error(
            "defeito no envio de e-mail",
            extra={
                "tipo": tipo,
                "outcome": "envio_defeito",
                "error_class": type(erro).__name__,
                "pilha": "".join(traceback.format_tb(erro.__traceback__)),
            },
        )
