"""Os formulários das páginas do IdP.

Toda senha é conferida por `authenticate()`, com o e-mail já em minúsculas no argumento
`username`: é dali que o `axes` lê a conta (`axes/helpers.py:150-174`). Com `email=`, ou com
a caixa ajustada depois, cada caixa do mesmo endereço vira um contador à parte, e o teto por
conta deixa de valer sem erro nenhum.
"""

from django import forms
from django.conf import settings
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth import authenticate
from django.contrib.auth.forms import (
    AuthenticationForm,
    BaseUserCreationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
)
from django.core.exceptions import ValidationError
from django.utils import timezone

from accounts import emails, envio
from accounts.models import User
from accounts.sinais import recuperacao_pedida

_EMAIL_EM_USO = "Já existe uma conta com este e-mail."


class _EmailEmMinusculas:
    def clean_username(self):
        # Antes do authenticate() do clean(), que é quem entrega o `username` ao `axes`.
        return self.cleaned_data["username"].lower()


class FormularioDeLoginDoAdmin(_EmailEmMinusculas, AdminAuthenticationForm):
    pass


class FormularioDeLogin(_EmailEmMinusculas, AuthenticationForm):
    error_messages = {
        # A mensagem da base afirma que os campos distinguem caixa, o que o e-mail já não faz.
        "invalid_login": "E-mail ou senha incorretos.",
        "inactive": "Esta conta está desativada. Para reativá-la, fale com quem administra.",
    }

    def clean(self):
        try:
            return super().clean()
        except ValidationError:
            if self._conta_desativada():
                raise ValidationError(self.error_messages["inactive"], code="inactive")
            raise

    def _conta_desativada(self):
        """Só quem acerta a senha de uma conta inativa, sem bloqueio, sabe que ela existe.

        O `ModelBackend` recusa a conta inativa com o mesmo `None` da senha errada, e a falha
        já foi contada pelo `axes`. Conta bloqueada vê a tela de bloqueio, que o middleware do
        `axes` põe no lugar desta resposta. O segundo `check_password` só corre para conta
        inativa existente, e o tempo de resposta a distingue de "sem conta" para quem mede
        (ADR 0031).
        """
        if getattr(self.request, "axes_locked_out", False):
            return False
        conta = User.objects.filter(email=self.cleaned_data.get("username")).first()
        return (
            conta is not None
            and not conta.is_active
            and conta.check_password(self.cleaned_data.get("password"))
        )


def _senha_confere(request, conta, senha):
    return authenticate(request, username=conta.email, password=senha) is not None


class FormularioDeRecuperacao(PasswordResetForm):
    """O pedido de link de redefinição. A resposta é a mesma com e sem conta.

    Só conta ativa, com senha utilizável e fora da equipe, recebe o link. A equipe troca a senha
    por `manage.py changepassword`.
    """

    def get_users(self, email):
        return (u for u in super().get_users(email) if not (u.is_staff or u.is_superuser))

    def save(self, request=None, **kwargs):
        # Guardado para o sinal: `send_mail` não recebe a requisição.
        self.request = request
        return super().save(request=request, **kwargs)

    def send_mail(self, subject_template_name, email_template_name, context, *args, **kwargs):
        # Os templates e o remetente que a view passa ficam sem uso: a mensagem é a de
        # `accounts/emails.py`, com o link sobre `BASE_URL`, e não sobre `domain`, que vem do
        # `Host` da requisição.
        destinatario = context["email"]
        mensagem = emails.redefinicao(context, destinatario)
        if envio.enfileirar(mensagem, "redefinicao", aviso=False):
            recuperacao_pedida.send(
                sender=type(self), request=self.request, user=context["user"]
            )


class FormularioDeRedefinicao(SetPasswordForm):
    def set_password_and_save(self, user, password_field_name="password1", commit=True):
        user.set_password(self.cleaned_data[password_field_name])
        # Quem abriu o link leu a caixa de entrada do endereço: ele está confirmado.
        user.email_verified = True
        user.email_verificado_em = timezone.now()
        if commit:
            user.save(update_fields=["password", "email_verified", "email_verificado_em"])
        return user


class FormularioDeTrocaDeSenha(PasswordChangeForm):
    def __init__(self, request, *args, **kwargs):
        self.request = request
        super().__init__(*args, **kwargs)

    def clean_old_password(self):
        senha = self.cleaned_data["old_password"]
        # Por `authenticate()`, e não por `check_password`, para o `axes` contar a falha.
        if not _senha_confere(self.request, self.user, senha):
            raise ValidationError(
                self.error_messages["password_incorrect"], code="password_incorrect"
            )
        return senha

    def set_password_and_save(self, user, password_field_name="password1", commit=True):
        user.set_password(self.cleaned_data[password_field_name])
        if commit:
            # Só a senha: o objeto foi lido no início da requisição, e uma edição do admin no
            # mesmo instante não é sobrescrita pelo valor antigo dos outros campos.
            user.save(update_fields=["password"])
        return user


class FormularioDeCadastro(BaseUserCreationForm):
    aceite = forms.BooleanField(
        error_messages={
            "required": "Para criar a conta, aceite os termos de uso e a política de privacidade."
        }
    )
    # A versão que a página mostrou. Se mudou entre o GET e o POST, o aceite foi de outro texto.
    termos_versao = forms.CharField(widget=forms.HiddenInput)

    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "nickname")

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email=email).exists():
            raise ValidationError(_EMAIL_EM_USO, code="unique")
        return email

    def clean_termos_versao(self):
        versao = self.cleaned_data["termos_versao"]
        if versao != settings.TERMOS_VERSAO_VIGENTE:
            raise ValidationError(
                "Os termos mudaram desde que esta página foi aberta. Leia a versão nova e "
                "aceite de novo.",
                code="termos_desatualizados",
            )
        return versao

    def save(self, commit=True):
        self.instance.termos_versao = self.cleaned_data["termos_versao"]
        self.instance.termos_aceitos_em = timezone.now()
        return super().save(commit)


class _ComSenhaAtual(forms.Form):
    """Formulário da conta da sessão que pede a senha atual."""

    senha = forms.CharField(
        strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "current-password"})
    )

    def __init__(self, request, *args, **kwargs):
        self.request = request
        self.user = request.user
        super().__init__(*args, **kwargs)

    def clean_senha(self):
        senha = self.cleaned_data["senha"]
        if not _senha_confere(self.request, self.user, senha):
            raise ValidationError("Senha incorreta.", code="password_incorrect")
        return senha


class FormularioDeTrocaDeEmail(_ComSenhaAtual):
    novo_email = forms.EmailField(max_length=254)

    field_order = ["novo_email", "senha"]

    def clean_novo_email(self):
        email = self.cleaned_data["novo_email"].lower()
        if email == self.user.email:
            raise ValidationError("Este já é o e-mail da conta.", code="mesmo_email")
        if User.objects.filter(email=email).exists():
            raise ValidationError(_EMAIL_EM_USO, code="unique")
        return email


class FormularioDeExclusao(_ComSenhaAtual):
    modo = forms.ChoiceField(
        choices=[("desativar", "Desativar a conta"), ("apagar", "Apagar a conta")],
        widget=forms.RadioSelect,
        error_messages={"required": "Escolha entre desativar e apagar."},
    )
    confirmo = forms.BooleanField(
        error_messages={"required": "Marque a confirmação para continuar."}
    )

    field_order = ["modo", "confirmo", "senha"]

    def __init__(self, request, *args, pode_apagar=True, **kwargs):
        super().__init__(request, *args, **kwargs)
        self.pode_apagar = pode_apagar
        if not pode_apagar:
            # Sem a opção, "apagar" enviado assim mesmo cai na validação da escolha.
            modo = self.fields["modo"]
            modo.choices = [("desativar", "Desativar a conta")]
            modo.error_messages["invalid_choice"] = (
                "Esta conta é dona de uma aplicação cadastrada e só pode ser desativada. "
                "Para apagá-la, fale com quem administra."
            )
