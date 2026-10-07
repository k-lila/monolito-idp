import uuid

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone


class UserManager(BaseUserManager):
    """Criação de usuário por e-mail: com `username = None`, o manager padrão não serve."""

    @classmethod
    def normalize_email(cls, email):
        # O endereço inteiro, e não só o domínio como na base: o `axes` conta falhas pelo
        # `username` como o recebe, e duas caixas do mesmo endereço seriam dois contadores.
        return super().normalize_email(email).lower()

    def create_user(self, email, password=None, **extra_fields):
        # createsuperuser --noinput sem DJANGO_SUPERUSER_EMAIL chega aqui (passo 11).
        if not email:
            raise ValueError("O e-mail é obrigatório.")
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


# Os campos cuja mudança de valor move `updated_at` (claim `updated_at`, scope `profile`).
_CAMPOS_DO_PERFIL = ("first_name", "last_name", "nickname", "email", "email_verified")


class User(AbstractUser):
    """Registro canônico sobre o qual todo token emitido faz afirmações.

    Herda de AbstractUser para preservar permissões, admin e o framework de
    autenticação — inclusive first_name/last_name, de onde sai a claim `name`.

    O `sub` das claims é o UUID, e não a chave primária, que fica interna (ADR 0031).
    As regras de escrita moram em `save()` para valer no admin, nas páginas, na API e no
    shell; `QuerySet.update()` passa por baixo delas, sem erro.
    """

    username = None
    email = models.EmailField("e-mail", unique=True)

    sub = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    nickname = models.CharField(max_length=150, blank=True)
    email_verified = models.BooleanField(default=False)
    email_verificado_em = models.DateTimeField(null=True, blank=True)
    senha_alterada_em = models.DateTimeField(null=True, blank=True)
    # Nunca auto_now: o login grava `last_login` pelo mesmo save(), e a claim mudaria a cada
    # entrada.
    updated_at = models.DateTimeField(default=timezone.now)
    desativada_em = models.DateTimeField(null=True, blank=True)
    desativada_por = models.CharField(
        max_length=20,
        choices=[("propria_pessoa", "a própria pessoa"), ("admin", "admin")],
        blank=True,
    )
    termos_versao = models.CharField(max_length=20, blank=True)
    termos_aceitos_em = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta(AbstractUser.Meta):
        constraints = [
            # `unique=True` no campo continua, porque o check auth.E003 o exige; é esta
            # restrição que recusa duas contas que só a caixa distingue.
            models.UniqueConstraint(
                Lower("email"),
                name="accounts_user_email_minusculas_unico",
                violation_error_message="Já existe uma conta com este e-mail.",
            ),
        ]

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        instance._retrato = instance._tirar_retrato()
        return instance

    def refresh_from_db(self, using=None, fields=None, from_queryset=None):
        super().refresh_from_db(using=using, fields=fields, from_queryset=from_queryset)
        # Só os campos relidos: um valor alterado em memória e não relido ainda é mudança.
        self._retrato = {
            **getattr(self, "_retrato", {}),
            **self._tirar_retrato(fields),
        }

    def _tirar_retrato(self, campos=None):
        """Os valores de perfil como estão no banco, para o save() comparar por valor."""
        adiados = self.get_deferred_fields()
        return {
            campo: getattr(self, campo)
            for campo in _CAMPOS_DO_PERFIL
            if campo not in adiados and (campos is None or campo in campos)
        }

    def save(self, *args, **kwargs):
        self.email = self.email.lower()
        update_fields = kwargs.get("update_fields")

        # (a) Lida antes do super(), que zera `_password` depois de gravar
        # (`django/contrib/auth/base_user.py:64-68`). A marca é atributo privado do Django:
        # set_password a liga, e o re-hash do login a zera antes de gravar
        # (`base_user.py:106-110`, "Password hash upgrades shouldn't be considered password
        # changes"). Um upgrade que a renomeie faz o carimbo parar, ou passar a marcar o
        # re-hash, sem erro nenhum: a subida do Django relê este ponto.
        senha_marcada = self._password is not None and (
            update_fields is None or "password" in update_fields
        )

        tocados = []
        retrato = getattr(self, "_retrato", None)
        if not self._state.adding and retrato:
            comparados = {
                campo: valor
                for campo, valor in retrato.items()
                if update_fields is None or campo in update_fields
            }
            # (b) Endereço novo não está verificado.
            if "email" in comparados and self.email != comparados["email"]:
                self.email_verified = False
                self.email_verificado_em = None
                tocados += ["email_verified", "email_verificado_em"]
            if any(getattr(self, campo) != valor for campo, valor in comparados.items()):
                self.updated_at = timezone.now()
                tocados.append("updated_at")

        # (c) Conta nova com senha também é carimbada; as contas anteriores ao campo ficam null.
        if senha_marcada:
            self.senha_alterada_em = timezone.now()
            tocados.append("senha_alterada_em")

        # (d) Sem isto, o que (b) e (c) tocaram ficaria só em memória.
        if update_fields is not None and tocados:
            kwargs["update_fields"] = {*update_fields, *tocados}

        # (e)
        super().save(*args, **kwargs)
        self._retrato = {**(retrato or {}), **self._tirar_retrato(kwargs.get("update_fields"))}
