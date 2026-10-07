"""A revogação dos tokens de uma conta e o sinal que a anuncia à trilha (ADR 0029 e ADR 0031).

Serve o logout iniciado pela relying party (RP), que revoga só na Application que pede, e as
páginas de conta, que revogam em todas: troca de senha, redefinição e exclusão. A ordem de
revogação mora só aqui.

O sinal é deste projeto, e não de biblioteca: o toolkit não emite nada ao revogar.
"""

from django.db import transaction
from django.dispatch import Signal
from oauth2_provider.models import (
    get_access_token_model,
    get_id_token_model,
    get_refresh_token_model,
)

# Uma emissão por Application com ao menos um token revogado. Argumentos: `request`, `user` (o
# dono dos tokens revogados) e `application`. O receptor é
# `accounts.auditoria.registrar_revogacao`, e `event` na trilha recebe o nome deste sinal
# (ADR 0013).
tokens_revogados = Signal()


def revogar_tokens(request, dono, aplicacao=None):
    """Revoga os tokens de `dono` em `aplicacao`, ou em todas as Applications se ela for None.

    O sinal sai depois do bloco atômico desta função, e por isso ela não é chamada dentro de
    outro bloco: a trilha não volta com o rollback, e registraria uma revogação desfeita.
    """
    for application in _revogar(dono, aplicacao):
        tokens_revogados.send(
            sender=revogar_tokens, request=request, user=dono, application=application
        )


def _revogar(dono, aplicacao=None):
    """Revoga e devolve as Applications em que havia token de `dono`, sem repetição.

    Filtra por conta e, se houver, por Application, e não a partir dos access tokens, como o
    toolkit (`oauth2_provider/views/oidc.py:434-454`). Com isso também pega o refresh órfão, sem
    access token. O toolkit já recusa esse refresh (`oauth2_validators.py:1296-1298`) e o
    `cleartokens` o apaga (`models.py:1269-1272`), então marcá-lo revogado só o encerra mais
    cedo, sem mudar o que ele pode fazer. A ordem segue as ligações: `RefreshToken.revoke()`
    apaga o access token ligado, e apagar um id_token apaga em cascata o access token que o
    referencia (`AccessToken.id_token`). Cada lista é lida depois de a anterior ter sido
    revogada.

    SILÊNCIO: um refresh validado antes desta revogação e gravado depois dela nasce vivo. O
    toolkit valida fora de trava e, ao gravar, não reconfere a revogação
    (`oauth2_validators.py:997-1038`). Nada aqui alcança esse intervalo.
    """
    filtro = {"user": dono}
    if aplicacao is not None:
        filtro["application"] = aplicacao
    afetadas = {}
    with transaction.atomic():
        for modelo, extra in (
            (get_refresh_token_model(), {"revoked__isnull": True}),
            (get_id_token_model(), {}),
            (get_access_token_model(), {}),
        ):
            for token in modelo.objects.filter(**filtro, **extra).select_related("application"):
                afetadas.setdefault(token.application_id, token.application)
                token.revoke()
    return list(afetadas.values())
