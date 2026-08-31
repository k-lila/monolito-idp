from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    """Criacao de usuario por e-mail: com `username = None`, o manager padrao nao serve."""

    def create_user(self, email, password=None, **extra_fields):
        # createsuperuser --noinput sem DJANGO_SUPERUSER_EMAIL chega aqui (passo 11).
        if not email:
            raise ValueError("O e-mail e obrigatorio.")
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Registro canonico sobre o qual todo token emitido faz afirmacoes.

    Herda de AbstractUser para preservar permissoes, admin e o framework de
    autenticacao — inclusive first_name/last_name, de onde sai a claim `name`.
    Nenhum campo especulativo: email_verified so entra com o fluxo que o alimenta.
    """

    username = None
    email = models.EmailField("email address", unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()
