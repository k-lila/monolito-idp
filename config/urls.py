"""URLs do projeto.

Nesta versão, admin e o servidor OAuth2/OIDC: sob `o/` entram só as listas de protocolo do DOT,
compostas num include com o namespace que o próprio módulo declara (ADR 0024). Login, logout e
home usam as views prontas do Django e a view de borda em config.views.
"""

from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import include, path
from oauth2_provider import urls as oauth2_urls

from config.views import health, home

urlpatterns = [
    path("admin/", admin.site.urls),
    # Sob prefixo, nunca na raiz: o prefixo compõe o issuer `{BASE_URL}/o` (ADR 0007) e delimita
    # a superfície de protocolo — é nele que CORS_URLS_REGEX, em config/settings.py, se apoia.
    #
    # Três das cinco listas do DOT, na ordem dele, e nunca rota a rota (ADR 0024).
    # `management_urlpatterns` fica fora: /o/applications/ e /o/authorized_tokens/ respondiam a
    # qualquer sessão autenticada, sem is_staff, e a gestão é do admin. `dcr_urlpatterns` também:
    # /o/register/ é 404 por ausência de rota, e não só por DCR_ENABLED=False.
    #
    # O namespace é contrato, e sua falta é silenciosa: o DOT monta cada endpoint das duas
    # descobertas por reverse() em `oauth2_provider`. A OIDC responde 500 sem ele; a da RFC 8414
    # engole o NoReverseMatch e responde 200 sem authorization_endpoint nem token_endpoint.
    #
    # O preço aceito: Application.get_absolute_url() reverte `oauth2_provider:detail`, que já
    # não existe, e o botão "Ver no site" da edição de Application no admin responde 500.
    path(
        "o/",
        include(
            (
                oauth2_urls.metadata_urlpatterns
                + oauth2_urls.base_urlpatterns
                + oauth2_urls.oidc_urlpatterns,
                oauth2_urls.app_name,
            ),
            namespace=oauth2_urls.app_name,
        ),
    ),
    # Uma rota de cada vez, sem `django.contrib.auth.urls`: o include inteiro publicaria
    # quatro rotas de recuperação de senha sem template, cada uma um 500 esperando um
    # clique. Fora daqui, /accounts/password_reset/ é um 404 do próprio Django.
    path("accounts/login/", LoginView.as_view(), name="login"),
    path("accounts/logout/", LogoutView.as_view(), name="logout"),
    # Sem barra final: é a URL do HEALTHCHECK do container, e APPEND_SLASH só acrescenta
    # barra, nunca remove — /health com barra registrada aqui responderia 404 a ele.
    path("health", health, name="health"),
    path("", home, name="home"),
]
