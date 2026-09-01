"""URLs do projeto.

Nesta versao, admin e o servidor OAuth2/OIDC: as rotas do DOT entram sob `o/`, como vem,
sem namespace explicito — `oauth2_provider.urls` ja declara o seu, e a discovery monta cada
endpoint por reverse() nele. Login, logout e home usam as views prontas do Django e a view
de borda em config.views.
"""

from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import include, path

from config.views import home

urlpatterns = [
    path("admin/", admin.site.urls),
    # Sob prefixo, nunca na raiz: na raiz as views de gestao de applications e de tokens
    # cairiam no espaco de nomes do produto (ADR 0007).
    path("o/", include("oauth2_provider.urls")),
    # Uma rota de cada vez, sem `django.contrib.auth.urls`: o include inteiro publicaria
    # quatro rotas de recuperacao de senha sem template, cada uma um 500 esperando um
    # clique. Fora daqui, /accounts/password_reset/ e um 404 do proprio Django.
    path("accounts/login/", LoginView.as_view(), name="login"),
    path("accounts/logout/", LogoutView.as_view(), name="logout"),
    path("", home, name="home"),
]
