"""O que a trilha de auditoria afirma sobre quem autenticou e sobre o que mudou na conta.

Dezesseis receptores de sinal, um por evento, escrevendo no logger `audit` — arquivo próprio
e durável, fora do stdout do container (ADR — Architecture Decision Record — 0013). Moram
em `accounts` porque é o app dono da pessoa. O formato da linha e o `request_id` são de
`config/observabilidade.py`, que este módulo não importa.

O quinto evento, `user_locked_out`, entrou com o limitador de taxa e amplia o conjunto da
ADR 0013 sem tocar no esquema de campos dela (ADR 0016). O sexto, `tokens_revogados`,
entrou com o logout iniciado pela relying party (RP) e amplia o mesmo conjunto do mesmo jeito
(ADR 0029). O sinal é deste projeto, e não de biblioteca: o toolkit não emite nada ao revogar.
Os dez seguintes, os eventos de conta de `accounts/sinais.py`, entraram com a API e as páginas de
conta e ampliam o mesmo conjunto (ADR 0031). Cada um traz no máximo um campo novo, só dele:
`campos` em `conta_editada` e `termos_versao` em `termos_aceitos`.

Regra de desenho, sem exceção: nunca entram na trilha `code`, `code_verifier`,
`access_token`, `refresh_token`, `id_token`, senha, `SECRET_KEY` nem a chave privada RSA
(Rivest–Shamir–Adleman). A pessoa identifica-se pelo `sub`, nunca pelo e-mail.
"""

import hashlib
import logging

from axes.signals import user_locked_out
from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from oauth2_provider.signals import app_authorized

from accounts.revogacao import tokens_revogados
from accounts.sinais import (
    conta_apagada,
    conta_criada,
    conta_desativada,
    conta_editada,
    email_confirmado,
    email_trocado,
    recuperacao_pedida,
    senha_redefinida,
    senha_trocada,
    termos_aceitos,
)
from config.origem import origem_completa

# A trilha: nível fixo em INFO e sem propagação para o console, declarados no LOGGING de
# `config/settings.py`.
trilha = logging.getLogger("audit")

# O log operacional deste módulo. É para onde grita a falha de um receptor.
logger = logging.getLogger(__name__)


def _origem(request):
    """Tripla `(ip, ip_src, ip_edge)` para a linha da trilha, delegada a `config.origem`.

    O valor que a trilha grava e o valor que o limitador de taxa conta são o mesmo fato, e
    duas leituras do mesmo fato divergem sem emitir sinal. A regra de leitura, o ramo de
    proxy e o que cada um cala estão lá; aqui não se lê `REMOTE_ADDR` nem cabeçalho nenhum
    (ADR 0015).

    Os três valores vêm juntos e do mesmo cálculo porque a trilha é um arquivo append-only.
    `ip_src` declara de onde o endereço saiu: ligar `BEHIND_TLS_PROXY` troca o significado
    de `ip` sem deixar marca (ADR 0018). `ip_edge` declara o que aquele endereço é para este
    processo: publicar o `proxy` fora de `127.0.0.1` troca o significado de `ip` de novo, e
    a partir dali as duas populações coexistem por requisição, não por período (ADR 0020).

    A regra de leitura das três populações de linha:

    - sem `ip_src`: escrita antes da ADR 0018; o `ip` é `REMOTE_ADDR`;
    - com `ip_src` e sem `ip_edge`: escrita entre a ADR 0018 e esta decisão. O `ip` NÃO
      identifica cliente nenhum — é endereço da rede do compose (o gateway da bridge sob
      `forwarded`, o endereço do próprio Caddy sob `remote_addr_fallback`) ou `127.0.0.1`
      na jornada de construção. O que sustenta: a única publicação que este repositório já
      teve é `127.0.0.1`, expor exige editar à mão um arquivo versionado (ADR 0017), e a
      proibição desta decisão trava essa edição até o campo existir;
    - com `ip_edge`: responde sozinha.
    """
    return origem_completa(request)


def _resumo_do_identificador(identificador):
    """Resumo SHA-256 do identificador tentado, em hexadecimal completo.

    Calculado em minúsculas e sem `strip` (ADR 0031). O e-mail é gravado em minúsculas e o
    banco recusa duas contas que só a caixa distingue, de modo que duas caixas do mesmo
    endereço são a mesma conta e devem dar o mesmo resumo. As linhas anteriores à ADR 0031
    trazem o resumo do valor como recebido, e ficam como estão.

    Hexadecimal completo, nunca truncado: truncar cria colisão sem comprar privacidade
    nenhuma — quem inverte o resumo inteiro por dicionário inverte o truncado do mesmo
    jeito, e a colisão faz duas contas distintas parecerem a mesma.
    """
    # None quando authenticate() é chamado com outro nome de credencial, sem `username`.
    if identificador is None:
        return None
    return hashlib.sha256(identificador.lower().encode("utf-8")).hexdigest()


# Cada receptor abaixo tem o corpo inteiro capturado por um `except Exception` que grita no
# log operacional. `user_logged_in` é enviado de DENTRO de django.contrib.auth.login()
# (`django/contrib/auth/__init__.py:197`), e uma exceção no receptor sobe pela pilha do
# login: falhar em auditar não pode negar autenticação. A captura é silêncio, e por isso
# ela grita do outro lado.
#
# O que a captura NÃO alcança: erro de escrita do handler — disco cheio, volume desmontado
# — é engolido pelo próprio `logging`, que o manda para stderr. Ali a trilha para de
# receber linhas e o sistema segue atendendo, sem que nada aqui perceba. É a falha
# silenciosa desta decisão, e está na seção 14 do runbook, hoje histórico:
# `git show 8caf117:docs/runbook.md`.


def registrar_login(sender, request, user, **kwargs):
    try:
        ip, ip_src, ip_edge = _origem(request)
        trilha.info(
            "autenticação bem-sucedida",
            extra={
                # `event` recebe o nome do sinal, e não um rótulo inventado: é o que leva
                # quem lê a trilha até o emissor por um `grep`.
                "event": "user_logged_in",
                # `sub` como string, igual à claim `sub` de todo id_token: o UUID da conta. As
                # linhas anteriores à ADR 0031 trazem a chave primária, e ficam como estão.
                "sub": str(user.sub),
                "ip": ip,
                "ip_src": ip_src,
                "ip_edge": ip_edge,
                "outcome": "success",
            },
        )
    except Exception:
        logger.exception("auditoria: falha ao registrar user_logged_in")


def registrar_falha_de_login(sender, credentials, **kwargs):
    try:
        ip, ip_src, ip_edge = _origem(kwargs.get("request"))
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
                "ip": ip,
                "ip_src": ip_src,
                "ip_edge": ip_edge,
                "outcome": "failure",
            },
        )
    except Exception:
        logger.exception("auditoria: falha ao registrar user_login_failed")


def registrar_logout(sender, request, user, **kwargs):
    try:
        ip, ip_src, ip_edge = _origem(request)
        trilha.info(
            "encerramento de sessão",
            extra={
                "event": "user_logged_out",
                # `user` é None quando o logout parte de uma requisição sem sessão
                # autenticada. A linha é emitida assim mesmo, com o campo explicitamente
                # vazio: o evento aconteceu, e omiti-lo faria a trilha subdeclarar.
                "sub": str(user.sub) if user is not None else None,
                "ip": ip,
                "ip_src": ip_src,
                "ip_edge": ip_edge,
                "outcome": "success",
            },
        )
    except Exception:
        logger.exception("auditoria: falha ao registrar user_logged_out")


def registrar_autorizacao_de_aplicacao(sender, request, token, **kwargs):
    # O sinal é emitido em `oauth2_provider/views/base.py:506`, na requisição de /o/token/,
    # que é autenticada por cliente e não por sessão — `request.user` ali é anônimo. Daí a
    # leitura de `token.user` e de `token.application.client_id`, e nunca de
    # `request.user`. O valor do token, `token.token`, não é lido em hipótese nenhuma.
    #
    # Esse mesmo caminho atende o grant de refresh: a trilha terá uma linha `app_authorized`
    # a cada renovação, e não só a cada consentimento. Quem contar linhas para contar
    # autorizações contará errado.
    try:
        ip, ip_src, ip_edge = _origem(request)
        trilha.info(
            "token concedido a uma relying party",
            extra={
                "event": "app_authorized",
                # None no grant de client credentials, que não tem pessoa associada.
                "sub": str(token.user.sub) if token.user_id is not None else None,
                "client_id": token.application.client_id,
                "ip": ip,
                "ip_src": ip_src,
                "ip_edge": ip_edge,
                "outcome": "success",
            },
        )
    except Exception:
        logger.exception("auditoria: falha ao registrar app_authorized")


def registrar_bloqueio(sender, request, username, **kwargs):
    # O sinal é enviado pelo handler do axes em `axes/handlers/database.py:259`, na mesma
    # requisição que estourou o teto de tentativas.
    #
    # O `ip` sai de `_origem(request)` e NUNCA do `ip_address` que o sinal entrega em
    # `kwargs`, mesmo que os dois valores coincidam: aceitar o de terceiro reabriria a
    # segunda leitura de origem que a ADR 0015 fecha, e ela divergiria sem emitir sinal.
    try:
        ip, ip_src, ip_edge = _origem(request)
        trilha.info(
            "conta ou origem bloqueada por tentativas em excesso",
            extra={
                "event": "user_locked_out",
                # Sem pessoa: o bloqueio conta tentativas falhas, e não há conta confirmada
                # a nomear — o identificador tentado pode nem existir.
                "sub": None,
                "identifier_sha256": _resumo_do_identificador(username),
                "ip": ip,
                "ip_src": ip_src,
                "ip_edge": ip_edge,
                "outcome": "blocked",
            },
        )
    except Exception:
        logger.exception("auditoria: falha ao registrar user_locked_out")


def registrar_revogacao(sender, request, user, application, **kwargs):
    # O sinal é emitido por `accounts/revogacao.py`, uma vez por Application com ao menos um
    # token revogado (ADR 0031). No logout pela RP sai antes do `user_logged_out` da mesma
    # requisição, e `user` é o dono dos tokens revogados, que pode não ser a conta da sessão:
    # com o hint de outra conta, ou sem sessão nenhuma, a linha seguinte de `user_logged_out`
    # traz outro `sub`, ou nenhum (ADR 0029).
    #
    # Sem contagem, sem `jti` e sem valor de token: a linha diz de quem e de qual RP, e o
    # esquema da ADR 0013 não ganha campo.
    try:
        ip, ip_src, ip_edge = _origem(request)
        trilha.info(
            "tokens revogados",
            extra={
                "event": "tokens_revogados",
                "sub": str(user.sub),
                "client_id": application.client_id,
                "ip": ip,
                "ip_src": ip_src,
                "ip_edge": ip_edge,
                "outcome": "success",
            },
        )
    except Exception:
        logger.exception("auditoria: falha ao registrar tokens_revogados")


def _registrar_na_conta(evento, mensagem, request, sub, **campos):
    """A linha de um evento de conta: a pessoa é a dona da conta, e o desfecho é sucesso.

    `sub` vem do chamador, e não da conta, porque a conta apagada já não existe. `campos` são os
    do evento, que nunca trazem e-mail nem valor de perfil.
    """
    try:
        ip, ip_src, ip_edge = _origem(request)
        trilha.info(
            mensagem,
            extra={
                "event": evento,
                "sub": str(sub),
                **campos,
                "ip": ip,
                "ip_src": ip_src,
                "ip_edge": ip_edge,
                "outcome": "success",
            },
        )
    except Exception:
        logger.exception("auditoria: falha ao registrar %s", evento)


def registrar_conta_criada(sender, request, user, **kwargs):
    _registrar_na_conta("conta_criada", "conta criada pelo cadastro", request, user.sub)


def registrar_email_confirmado(sender, request, user, **kwargs):
    _registrar_na_conta("email_confirmado", "e-mail da conta confirmado", request, user.sub)


def registrar_conta_editada(sender, request, user, campos, **kwargs):
    # Os nomes, e nunca os valores: nome e apelido são dado pessoal, e a trilha não os guarda.
    _registrar_na_conta(
        "conta_editada", "perfil da conta editado", request, user.sub, campos=list(campos)
    )


def registrar_termos_aceitos(sender, request, user, termos_versao, **kwargs):
    _registrar_na_conta(
        "termos_aceitos", "termos aceitos", request, user.sub, termos_versao=termos_versao
    )


def registrar_email_trocado(sender, request, user, **kwargs):
    _registrar_na_conta("email_trocado", "e-mail da conta trocado", request, user.sub)


def registrar_senha_trocada(sender, request, user, **kwargs):
    _registrar_na_conta("senha_trocada", "senha trocada", request, user.sub)


def registrar_recuperacao_pedida(sender, request, user, **kwargs):
    _registrar_na_conta(
        "recuperacao_pedida", "link de redefinição de senha pedido", request, user.sub
    )


def registrar_senha_redefinida(sender, request, user, **kwargs):
    _registrar_na_conta("senha_redefinida", "senha redefinida pelo link", request, user.sub)


def registrar_conta_desativada(sender, request, user, **kwargs):
    _registrar_na_conta(
        "conta_desativada", "conta desativada pela própria pessoa", request, user.sub
    )


def registrar_conta_apagada(sender, request, sub, **kwargs):
    _registrar_na_conta("conta_apagada", "conta apagada pela própria pessoa", request, sub)


def ligar_receptores():
    """Liga os dezesseis receptores. Chamada por `AccountsConfig.ready()`."""
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
    user_locked_out.connect(
        registrar_bloqueio,
        dispatch_uid="accounts.auditoria.registrar_bloqueio",
    )
    tokens_revogados.connect(
        registrar_revogacao,
        dispatch_uid="accounts.auditoria.registrar_revogacao",
    )
    email_confirmado.connect(
        registrar_email_confirmado,
        dispatch_uid="accounts.auditoria.registrar_email_confirmado",
    )
    conta_editada.connect(
        registrar_conta_editada,
        dispatch_uid="accounts.auditoria.registrar_conta_editada",
    )
    termos_aceitos.connect(
        registrar_termos_aceitos,
        dispatch_uid="accounts.auditoria.registrar_termos_aceitos",
    )
    conta_criada.connect(
        registrar_conta_criada,
        dispatch_uid="accounts.auditoria.registrar_conta_criada",
    )
    email_trocado.connect(
        registrar_email_trocado,
        dispatch_uid="accounts.auditoria.registrar_email_trocado",
    )
    senha_trocada.connect(
        registrar_senha_trocada,
        dispatch_uid="accounts.auditoria.registrar_senha_trocada",
    )
    recuperacao_pedida.connect(
        registrar_recuperacao_pedida,
        dispatch_uid="accounts.auditoria.registrar_recuperacao_pedida",
    )
    senha_redefinida.connect(
        registrar_senha_redefinida,
        dispatch_uid="accounts.auditoria.registrar_senha_redefinida",
    )
    conta_desativada.connect(
        registrar_conta_desativada,
        dispatch_uid="accounts.auditoria.registrar_conta_desativada",
    )
    conta_apagada.connect(
        registrar_conta_apagada,
        dispatch_uid="accounts.auditoria.registrar_conta_apagada",
    )
