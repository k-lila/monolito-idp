"""Views de borda do projeto: a home e o /health.

Nao ha app para elas — nao afirmam nada sobre identidade e nao tocam o modelo de
usuario. Login e logout continuam sendo as views prontas do django.contrib.auth.
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
    """Home publica: e o destino de LOGIN_REDIRECT_URL e de LOGOUT_REDIRECT_URL.

    Sem login_required de proposito: com ele, o redirect do logout cairia em
    /accounts/login/?next=/ em vez da propria home. Quem esta logado aparece pelo
    `user` do context processor.
    """
    return render(request, "home.html")


def health(request):
    """Prontidao real: uma query no banco e um round-trip no cache.

    Nao toca request.user nem request.session, nao renderiza template e nao usa
    messages: qualquer um deles carregaria a sessao pelo Redis, e o health passaria a
    falhar pelo mesmo motivo que deveria apenas reportar. Um try por componente, nunca
    um so envolvendo os dois — com um so, a falha do banco esconde o estado do cache e
    o corpo mente por omissao. O except loga: o corpo de tres chaves nao carrega a
    causa, e o LOGGING do projeto manda tudo para stdout.
    """
    componentes = {"database": "ok", "cache": "ok"}

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        logger.exception("health: banco inalcancavel")
        componentes["database"] = "error"

    try:
        cache.set(_CHAVE_SONDA, "ok", 10)
        # Comparar o lido com o gravado: cache que aceita conexao e nao devolve o que
        # gravou esta quebrado, e um `set` sozinho nao percebe isso.
        if cache.get(_CHAVE_SONDA) != "ok":
            raise RuntimeError("cache nao devolveu o valor gravado")
    except Exception:
        logger.exception("health: cache inalcancavel ou inconsistente")
        componentes["cache"] = "error"

    saudavel = all(estado == "ok" for estado in componentes.values())
    corpo = {"status": "ok" if saudavel else "error", **componentes}
    return JsonResponse(corpo, status=200 if saudavel else 503)
