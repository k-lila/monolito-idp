"""URLs do projeto.

Nesta versao, admin e o servidor OAuth2/OIDC: as rotas do DOT entram sob `o/`, como vem,
sem namespace explicito — `oauth2_provider.urls` ja declara o seu, e a discovery monta cada
endpoint por reverse() nele. As rotas de autenticacao e a home entram no passo 09,
/health no passo 10.
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    # Sob prefixo, nunca na raiz: na raiz as views de gestao de applications e de tokens
    # cairiam no espaco de nomes do produto (ADR 0007).
    path("o/", include("oauth2_provider.urls")),
]
