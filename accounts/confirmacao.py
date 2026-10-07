"""O token do link de confirmação de e-mail (ADR 0031).

Assinado por `django.core.signing`, sem tabela: carrega o `sub` e o resumo SHA-256 do e-mail,
e não o endereço, que iria em claro na URL e em todo log de borda. O resumo é o que invalida o
link quando o e-mail muda. Quem lê confere o resto: que a conta existe, está ativa e tem o
e-mail cujo resumo veio no token.
"""

import hashlib
from datetime import timedelta

from django.core import signing

# Próprio deste token: uma assinatura feita com a SECRET_KEY para outro fim não vale aqui.
_SALT = "accounts.confirmacao-de-email"
PRAZO = timedelta(days=7)


def resumo_do_email(email):
    """O resumo SHA-256, em hexadecimal, do e-mail em minúsculas."""
    return hashlib.sha256(email.lower().encode("utf-8")).hexdigest()


def gerar(user):
    return signing.dumps({"sub": str(user.sub), "h": resumo_do_email(user.email)}, salt=_SALT)


def ler(t):
    """O par `(sub, resumo)` do token, ou `None` se ele é expirado, adulterado ou malformado."""
    try:
        dados = signing.loads(t, salt=_SALT, max_age=PRAZO)
        return dados["sub"], dados["h"]
    except (signing.BadSignature, ValueError, KeyError):
        return None
