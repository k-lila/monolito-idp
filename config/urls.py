"""URLs do projeto.

Nesta versão, admin, o servidor OAuth2/OIDC e a API de conta: sob `o/` entram só as listas de
protocolo do DOT, compostas num include com o namespace que o próprio módulo declara (ADR 0024),
e uma rota que sombreia a de logout do toolkit (ADR 0030); sob `api/conta/`, os quatro caminhos
de `accounts/api.py` (ADR 0031). Sob `accounts/`, as páginas de `accounts/paginas.py`, em
português: o login, que é a LoginView do Django com formulário próprio, o cadastro, as quatro de
recuperação de senha, a troca de senha, a troca de e-mail e a exclusão (ADR 0031). Logout e home
usam a view pronta do Django e a view de borda em config.views.
"""

from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.urls import include, path
from oauth2_provider import urls as oauth2_urls

from accounts import api, paginas
from accounts.formularios import FormularioDeLogin
from accounts.logout_rp import LogoutPelaRPView
from config.views import health, home

urlpatterns = [
    path("admin/", admin.site.urls),
    # Sombra deliberada da rota `rp-initiated-logout` do toolkit, que continua dentro do include
    # abaixo (ADR 0030). O Django atende pela primeira rota que casa, e a descoberta monta
    # end_session_endpoint por reverse() no namespace, que segue dando /o/logout/. A ordem é o
    # contrato: declarada depois do include, ou se um upgrade renomear o caminho do toolkit,
    # /o/logout/ volta à view original, que com OIDC_RP_INITIATED_LOGOUT_DELETE_TOKENS falsa
    # encerra a sessão, redireciona e não revoga nada. Sem erro nenhum; só a guarda da suíte,
    # que resolve o caminho do reverse(), acusa.
    path("o/logout/", LogoutPelaRPView.as_view(), name="logout_rp"),
    # Sob prefixo, nunca na raiz: o prefixo compõe o issuer `{BASE_URL}/o` (ADR 0007) e delimita
    # a superfície de protocolo — é nele, e em `api/conta/` abaixo, que CORS_URLS_REGEX, em
    # config/settings.py, se apoia.
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
    # Os caminhos da API de conta são fixos: cada um é uma chave de RATE_LIMIT_POR_CAMINHO, que
    # compara por igualdade, e o prefixo `api/conta/` é o de CORS_URLS_REGEX. Mudar um caminho
    # aqui sem mudar as duas settings tira o teto ou o CORS dele sem erro.
    path("api/conta/", api.Conta.as_view(), name="api_conta"),
    path(
        "api/conta/confirmacao/",
        api.ReenvioDaConfirmacao.as_view(),
        name="api_conta_confirmacao",
    ),
    path("api/conta/termos/", api.AceiteDosTermos.as_view(), name="api_conta_termos"),
    path("api/conta/confirmar/", api.confirmar, name="api_conta_confirmar"),
    # Uma rota de cada vez, sem `django.contrib.auth.urls`: o include publicaria rotas sem
    # template próprio, em inglês e fora de `EmPortugues`, e `password_change_done`, que aqui
    # não existe porque a troca de senha volta à SPA.
    path(
        "accounts/login/",
        paginas.PaginaDeLogin.as_view(authentication_form=FormularioDeLogin),
        name="login",
    ),
    # O nome `registrar` é o de OIDC_RP_INITIATED_REGISTRATION_URL, em config/settings.py: é
    # por ele que o `prompt=create` do toolkit chega aqui.
    path("accounts/registrar/", paginas.PaginaDeCadastro.as_view(), name="registrar"),
    # Os quatro nomes são os do Django: `PasswordResetView` e `PasswordResetConfirmView`
    # redirecionam por eles, e `accounts/emails.py` monta o link pelo terceiro.
    path(
        "accounts/password_reset/",
        paginas.PaginaDeRecuperacao.as_view(),
        name="password_reset",
    ),
    path(
        "accounts/password_reset/done/",
        paginas.PaginaDeRecuperacaoPedida.as_view(),
        name="password_reset_done",
    ),
    # Sem teto de requisição: o caminho muda a cada link, e RATE_LIMIT_POR_CAMINHO compara por
    # igualdade. O que a protege é o token de uso único e de uma hora (ADR 0031).
    path(
        "accounts/reset/<uidb64>/<token>/",
        paginas.PaginaDeRedefinicao.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "accounts/reset/done/",
        paginas.PaginaDeRedefinicaoConcluida.as_view(),
        name="password_reset_complete",
    ),
    path(
        "accounts/password_change/",
        paginas.PaginaDeTrocaDeSenha.as_view(),
        name="password_change",
    ),
    path("accounts/email/", paginas.PaginaDeTrocaDeEmail.as_view(), name="troca_de_email"),
    path("accounts/excluir/", paginas.PaginaDeExclusao.as_view(), name="exclusao"),
    path("accounts/logout/", LogoutView.as_view(), name="logout"),
    # Sem barra final: é a URL do HEALTHCHECK do container, e APPEND_SLASH só acrescenta
    # barra, nunca remove — /health com barra registrada aqui responderia 404 a ele.
    path("health", health, name="health"),
    path("", home, name="home"),
]
