"""O esquecimento e o desbloqueio das tentativas de login de um endereço (ADR 0031).

O `axes` guarda o `username` tentado em `AccessAttempt`, `AccessFailureLog` e `AccessLog`, sem
chave estrangeira para a conta. Quando o endereço deixa de ser o de uma conta, pela troca de
e-mail na página ou no admin, ou pela exclusão, as linhas dele continuariam ali, e a conta
apagada não o seria de todo. O histórico de login do endereço se perde; a trilha de auditoria
fica.
"""

from axes.handlers.database import AxesDatabaseHandler
from axes.helpers import get_client_username
from axes.models import AccessAttempt, AccessFailureLog, AccessLog


class TentativasPorConta(AxesDatabaseHandler):
    """O handler de banco do `axes`, com o zeramento do login restrito à conta (ADR 0031).

    O da biblioteca apaga no login bem-sucedido as falhas de cada filtro de
    `AXES_LOCKOUT_PARAMETERS`: as da conta e as da origem. Com o cadastro público, quem ataca
    uma conta entraria na própria, pela mesma origem, e apagaria as falhas que a origem acumulou
    contra a vítima.

    Depende de um método interno da biblioteca: `user_logged_in` chama `reset_user_attempts`
    (`axes/handlers/database.py:314-316`, definido em `:432-445`, na 8.3.1). O SILÊNCIO é o da
    subida do `axes`: se uma versão nova renomear o método ou passar a zerar por outro caminho,
    o zeramento da origem volta sem erro nenhum.
    """

    def reset_user_attempts(self, request, credentials=None):
        return desbloquear(get_client_username(request, credentials))


def esquecer_tentativas(email):
    # Sem distinção de caixa: as linhas anteriores à ADR 0031 trazem o endereço como foi
    # digitado. Isto é limpeza, e não autenticação, que continua comparando por igualdade.
    for modelo in (AccessAttempt, AccessFailureLog, AccessLog):
        modelo.objects.filter(username__iexact=email).delete()


def desbloquear(email):
    """Apaga as falhas da conta, de toda origem, e devolve quantas linhas apagou.

    Preserva `AccessFailureLog` e `AccessLog`: o endereço continua sendo da conta, e o histórico
    de login dele também. O login bem-sucedido a chama por `TentativasPorConta`; a redefinição
    de senha, direto, para a senha nova entrar sem esperar o prazo.

    A linha de `AccessAttempt` guarda a conta e a origem juntas, e por isso as falhas contra
    esta conta saem também da contagem de cada origem.
    """
    apagadas, _ = AccessAttempt.objects.filter(username__iexact=email).delete()
    return apagadas
