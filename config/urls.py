"""URLs do projeto.

Nesta versao, so o admin: o include do DOT entra no passo 07, as rotas de autenticacao
e a home no passo 09, /health no passo 10.
"""

from django.contrib import admin
from django.urls import path

urlpatterns = [
    path("admin/", admin.site.urls),
]
