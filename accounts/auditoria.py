"""O que a trilha de auditoria afirma sobre quem autenticou.

Quatro receptores de sinal, um por evento, escrevendo no logger `audit` — arquivo próprio
e durável, fora do stdout do container (ADR — Architecture Decision Record — 0013). Moram
em `accounts` porque é o app dono da pessoa. O formato da linha e o `request_id` são de
`config/observabilidade.py`, que este módulo não importa.

Regra de desenho, sem exceção: nunca entram na trilha `code`, `code_verifier`,
`access_token`, `refresh_token`, `id_token`, senha, `SECRET_KEY` nem a chave privada RSA
(Rivest–Shamir–Adleman). A pessoa identifica-se pelo `sub`, nunca pelo e-mail.
"""

import hashlib
import logging

from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from oauth2_provider.signals import app_authorized

# A trilha: nível fixo em INFO e sem propagação para o console, declarados no LOGGING de
# `config/settings.py`.
trilha = logging.getLogger("audit")

# O log operacional deste módulo. É para onde grita a falha de um receptor.
logger = logging.getLogger(__name__)


def _origem(request):
    """Endereço de origem, de REMOTE_ADDR e nunca de X-Forwarded-For.

    Não há proxy à frente hoje: um cabeçalho que ninguém impõe é um cabeçalho que qualquer
    cliente forja, e a trilha registraria a origem que o atacante escolhesse.
    """
    # `request` é None quando authenticate() é chamado sem ele — fora de uma requisição
    # HTTP, por shell ou por comando de `manage.py`.
    if request is None:
        return None
    return request.META.get("REMOTE_ADDR")


def _resumo_do_identificador(identificador):
    """Resumo SHA-256 do identificador tentado, em hexadecimal completo.

    Calculado sobre o valor **como recebido**, sem `strip` e sem `lower`. A razão é do
    modelo: `accounts.User.email` é `unique=True` sob Postgres, cuja unicidade é sensível a
    caixa — `A@x.com` e `a@x.com` são contas distintas, e normalizar fundiria duas contas
    numa mesma linha da trilha. A consequência simétrica está aceita: duas tentativas
    contra a mesma conta com caixas diferentes produzem resumos diferentes.

    Hexadecimal completo, nunca truncado: truncar cria colisão sem comprar privacidade
    nenhuma — quem inverte o resumo inteiro por dicionário inverte o truncado do mesmo
    jeito, e a colisão faz duas contas distintas parecerem a mesma.
    """
    # None quando authenticate() é chamado com outro nome de credencial, sem `username`.
    if identificador is None:
        return None
    return hashlib.sha256(identificador.encode("utf-8")).hexdigest()


# Cada receptor abaixo tem o corpo inteiro capturado por um `except Exception` que grita no
# log operacional. `user_logged_in` é enviado de DENTRO de django.contrib.auth.login()
# (`django/contrib/auth/__init__.py:197`), e uma exceção no receptor sobe pela pilha do
# login: falhar em auditar não pode negar autenticação. A captura é silêncio, e por isso
# ela grita do outro lado.
#
# O que a captura NÃO alcança: erro de escrita do handler — disco cheio, volume desmontado
# — é engolido pelo próprio `logging`, que o manda para stderr. Ali a trilha para de
# receber linhas e o sistema segue atendendo, sem que nada aqui perceba. É a falha
# silenciosa desta decisão, e está na seção 14 de `docs/runbook.md`.


def registrar_login(sender, request, user, **kwargs):
    try:
        trilha.info(
            "autenticação bem-sucedida",
            extra={
                # `event` recebe o nome do sinal, e não um rótulo inventado: é o que leva
                # quem lê a trilha até o emissor por um `grep`.
                "event": "user_logged_in",
                # `sub` como string, igual à claim `sub` de todo id_token.
                "sub": str(user.pk),
                "ip": _origem(request),
                "outcome": "success",
            },
        )
    except Exception:
        logger.exception("auditoria: falha ao registrar user_logged_in")


def registrar_falha_de_login(sender, credentials, **kwargs):
    try:
        trilha.info(
            "falha de autenticação",
            extra={
                "event": "user_login_failed",
                # Sem pessoa: a autenticação falhou, e não há conta confirmada a nomear.
                "sub": None,
                # `credentials` chega saneado por _clean_credentials
                # (`django/contrib/auth/__init__.py:84`), que substitui por asteriscos toda
                # chave que compare com api|token|key|secret|password|signature. A chave
                # `username` não compara com nenhuma delas, e aqui ela carrega o e-mail
                # digitado em claro — daí o resumo.
                "identifier_sha256": _resumo_do_identificador(credentials.get("username")),
                "ip": _origem(kwargs.get("request")),
                "outcome": "failure",
            },
        )
    except Exception:
        logger.exception("auditoria: falha ao registrar user_login_failed")


def registrar_logout(sender, request, user, **kwargs):
    try:
        trilha.info(
            "encerramento de sessão",
            extra={
                "event": "user_logged_out",
                # `user` é None quando o logout parte de uma requisição sem sessão
                # autenticada. A linha é emitida assim mesmo, com o campo explicitamente
                # vazio: o evento aconteceu, e omiti-lo faria a trilha subdeclarar.
                "sub": str(user.pk) if user is not None else None,
                "ip": _origem(request),
                "outcome": "success",
            },
        )
    except Exception:
        logger.exception("auditoria: falha ao registrar user_logged_out")


def registrar_autorizacao_de_aplicacao(sender, request, token, **kwargs):
    # O sinal é emitido em `oauth2_provider/views/base.py:506`, na requisição de /o/token/,
    # que é autenticada por cliente e não por sessão — `request.user` ali é anônimo. Daí a
    # leitura de `token.user_id` e de `token.application.client_id`, e nunca de
    # `request.user`. O valor do token, `token.token`, não é lido em hipótese nenhuma.
    #
    # Esse mesmo caminho atende o grant de refresh: a trilha terá uma linha `app_authorized`
    # a cada renovação, e não só a cada consentimento. Quem contar linhas para contar
    # autorizações contará errado.
    try:
        trilha.info(
            "token concedido a uma relying party",
            extra={
                "event": "app_authorized",
                # None no grant de client credentials, que não tem pessoa associada.
                "sub": str(token.user_id) if token.user_id is not None else None,
                "client_id": token.application.client_id,
                "ip": _origem(request),
                "outcome": "success",
            },
        )
    except Exception:
        logger.exception("auditoria: falha ao registrar app_authorized")


def ligar_receptores():
    """Liga os quatro receptores. Chamada por `AccountsConfig.ready()`."""
    # Um dispatch_uid próprio por conexão: ready() pode rodar mais de uma vez, e sem ele o
    # mesmo receptor ficaria ligado duas vezes. O resultado seria linha duplicada na
    # trilha, indistinguível de duas tentativas de verdade.
    user_logged_in.connect(
        registrar_login,
        dispatch_uid="accounts.auditoria.registrar_login",
    )
    user_login_failed.connect(
        registrar_falha_de_login,
        dispatch_uid="accounts.auditoria.registrar_falha_de_login",
    )
    user_logged_out.connect(
        registrar_logout,
        dispatch_uid="accounts.auditoria.registrar_logout",
    )
    app_authorized.connect(
        registrar_autorizacao_de_aplicacao,
        dispatch_uid="accounts.auditoria.registrar_autorizacao_de_aplicacao",
    )
