"""Views de borda do projeto: a home e o /health.

Não há app para elas — não afirmam nada sobre identidade e não tocam o modelo de
usuário. Login e logout continuam sendo as views prontas do django.contrib.auth.
"""

import logging

from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render

logger = logging.getLogger(__name__)

# Chave da sonda: escrita e relida a cada request de /health, sem colidir com uso real.
_CHAVE_SONDA = "health:probe"


def home(request):
    """Home pública: é o destino de LOGIN_REDIRECT_URL e de LOGOUT_REDIRECT_URL.

    Sem login_required de propósito: com ele, o redirect do logout cairia em
    /accounts/login/?next=/ em vez da própria home. Quem está logado aparece pelo
    `user` do context processor.
    """
    return render(request, "home.html")


def health(request):
    """Prontidão real: uma query no banco e um round-trip no cache.

    Não toca request.user nem request.session, não renderiza template e não usa
    messages: qualquer um deles carregaria a sessão pelo Redis, e o health passaria a
    falhar pelo mesmo motivo que deveria apenas reportar. Um try por componente, nunca
    um só envolvendo os dois — com um só, a falha do banco esconde o estado do cache e
    o corpo mente por omissão. O except loga: o corpo de três chaves não carrega a
    causa, e o LOGGING do projeto manda tudo para stdout.
    """
    componentes = {"database": "ok", "cache": "ok"}

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        logger.exception("health: banco inalcançável")
        componentes["database"] = "error"

    try:
        cache.set(_CHAVE_SONDA, "ok", 10)
        # Comparar o lido com o gravado: cache que aceita conexão e não devolve o que
        # gravou está quebrado, e um `set` sozinho não percebe isso.
        if cache.get(_CHAVE_SONDA) != "ok":
            raise RuntimeError("cache não devolveu o valor gravado")
    except Exception:
        logger.exception("health: cache inalcançável ou inconsistente")
        componentes["cache"] = "error"

    saudavel = all(estado == "ok" for estado in componentes.values())
    corpo = {"status": "ok" if saudavel else "error", **componentes}
    return JsonResponse(corpo, status=200 if saudavel else 503)
