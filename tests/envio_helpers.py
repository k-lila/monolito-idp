"""Infraestrutura compartilhada pelos testes do envio de e-mail (TASK-028).

Não é teste em si. Reúne o que `tests/test_envio.py` repetiria: a captura das linhas de
`accounts.envio` pelo `FormatadorJSON` real, com o `FiltroRequestId` real (é o filtro, rodando
no contexto de quem emite, que põe o `request_id` na linha), e dois backends de e-mail falsos
importáveis por `override_settings(EMAIL_BACKEND=...)`.

Os backends guardam o estado em atributo de classe, porque o Django os instancia sozinho a cada
envio. Quem os usa o repõe no `finally`.
"""

import json
import logging
import threading
from contextlib import contextmanager

from django.core.mail.backends.base import BaseEmailBackend

from config.observabilidade import FiltroRequestId, FormatadorJSON


@contextmanager
def capturar_envio():
    """As linhas de `accounts.envio`, serializadas pelo formatador de produção.

    Devolve a lista de linhas (texto JSON), que o chamador lê depois do bloco. O logger deixa
    de propagar durante a captura, para a suíte não imprimir o que provoca de propósito.
    """
    linhas = []

    class Guarda(logging.Handler):
        def emit(self, record):
            linhas.append(self.format(record))

    handler = Guarda()
    handler.setFormatter(FormatadorJSON())
    handler.addFilter(FiltroRequestId())
    logger = logging.getLogger("accounts.envio")
    nivel, propagava = logger.level, logger.propagate
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    try:
        yield linhas
    finally:
        logger.removeHandler(handler)
        logger.setLevel(nivel)
        logger.propagate = propagava


def campos(linha):
    return json.loads(linha)


class BackendQueLevanta(BaseEmailBackend):
    """Levanta `ERRO` em todo envio. `ERRO` é posto pelo teste e reposto por ele."""

    ERRO = None

    def send_messages(self, email_messages):
        raise self.ERRO


class BackendQueBloqueia(BaseEmailBackend):
    """Espera `LIBERADO` e então grava em `ENVIADAS`, ou levanta `ERRO` se ele estiver posto."""

    LIBERADO = threading.Event()
    ENVIADAS = []
    ERRO = None

    @classmethod
    def reiniciar(cls):
        cls.LIBERADO = threading.Event()
        cls.ENVIADAS = []
        cls.ERRO = None

    def send_messages(self, email_messages):
        # Com limite: um teste que esqueça de liberar não pendura a suíte.
        self.LIBERADO.wait(timeout=10)
        if self.ERRO is not None:
            raise self.ERRO
        self.ENVIADAS.extend(email_messages)
        return len(email_messages)
