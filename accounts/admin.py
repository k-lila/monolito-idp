from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils import timezone

from .formularios import FormularioDeLoginDoAdmin
from .models import User
from .tentativas import esquecer_tentativas

# O /admin/login/ também confere a senha por authenticate(), e sem isto o `axes` contaria cada
# caixa do mesmo e-mail à parte. O admin carrega este módulo no arranque, antes da primeira
# requisição.
admin.site.login_form = FormularioDeLoginDoAdmin

_ESTADO_DA_CONTA = (
    "sub",
    "email_verified",
    "email_verificado_em",
    "senha_alterada_em",
    "updated_at",
    "desativada_em",
    "desativada_por",
    "termos_versao",
    "termos_aceitos_em",
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """UserAdmin ajustado a um modelo sem `username`.

    Os cinco lugares em que a classe base nomeia `username` precisam ser sobrescritos;
    faltando um, o próprio `manage.py check` acusa.
    """

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "nickname")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
        ("Estado da conta", {"fields": _ESTADO_DA_CONTA}),
    )
    # Escritos só pelas regras do modelo e pelos fluxos da própria pessoa. Trocar o e-mail
    # aqui zera a verificação pelo save() do modelo, e não envia e-mail nenhum.
    readonly_fields = _ESTADO_DA_CONTA
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "usable_password", "password1", "password2"),
            },
        ),
    )
    list_display = ("email", "first_name", "last_name", "is_staff")
    search_fields = ("email", "first_name", "last_name")
    ordering = ("email",)

    def save_model(self, request, obj, form, change):
        if "is_active" in form.changed_data:
            if obj.is_active:
                obj.desativada_em = None
                obj.desativada_por = ""
            else:
                obj.desativada_em = timezone.now()
                obj.desativada_por = "admin"
        super().save_model(request, obj, form, change)
        # O changed_data distingue caixa, e o modelo grava o e-mail em minúsculas: só a
        # comparação depois do save() diz se o endereço deixou de ser desta conta.
        if change and "email" in form.changed_data and form.initial["email"] != obj.email:
            esquecer_tentativas(form.initial["email"])
