"""Views de borda do projeto: a home.

Nao ha app para ela — nao afirma nada sobre identidade e nao toca o modelo de
usuario. Login e logout continuam sendo as views prontas do django.contrib.auth.
"""

from django.shortcuts import render


def home(request):
    """Home publica: e o destino de LOGIN_REDIRECT_URL e de LOGOUT_REDIRECT_URL.

    Sem login_required de proposito: com ele, o redirect do logout cairia em
    /accounts/login/?next=/ em vez da propria home. Quem esta logado aparece pelo
    `user` do context processor.
    """
    return render(request, "home.html")
