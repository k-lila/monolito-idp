"""As páginas do IdP, em português.

`LANGUAGE_CODE` continua `en-us`: com ele em `pt-br`, o `error_description` do protocolo sairia
acentuado, fora do conjunto de caracteres da RFC 6749 (ADR 0031). O português vale só aqui,
por `EmPortugues`.

Tudo o que recebe senha é página daqui. O login segue o `next` como a `LoginView` do Django; o
cadastro o confere do mesmo jeito. As demais nunca leem o `next` do pedido: cada uma volta a um
destino fixo da SPA, e um `next` externo não as transforma em redirecionamento aberto.

Os sinais da trilha saem depois de a gravação estar confirmada, e por isso a revogação, que
emite o próprio sinal, nunca é chamada dentro de um bloco atômico daqui.
"""

from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.password_validation import password_validators_help_texts
from django.contrib.auth.views import (
    LoginView,
    PasswordChangeView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
    RedirectURLMixin,
)
from django.db import transaction
from django.http import HttpResponseRedirect
from django.utils import timezone, translation
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.generic import FormView
from oauth2_provider.models import get_application_model

from accounts import emails, envio
from accounts.formularios import (
    FormularioDeCadastro,
    FormularioDeExclusao,
    FormularioDeRecuperacao,
    FormularioDeRedefinicao,
    FormularioDeTrocaDeEmail,
    FormularioDeTrocaDeSenha,
)
from accounts.revogacao import revogar_tokens
from accounts.sinais import (
    conta_apagada,
    conta_criada,
    conta_desativada,
    email_trocado,
    senha_redefinida,
    senha_trocada,
)
from accounts.tentativas import desbloquear, esquecer_tentativas


class EmPortugues:
    """Atende a página em português, com a resposta renderizada dentro do bloco.

    O `TemplateResponse` renderiza depois de o `dispatch` retornar, já fora do `override`, e
    as mensagens preguiçosas dos formulários sairiam em inglês, sem erro nenhum.
    """

    def dispatch(self, request, *args, **kwargs):
        with translation.override("pt-br"):
            resposta = super().dispatch(request, *args, **kwargs)
            if hasattr(resposta, "render") and not resposta.is_rendered:
                resposta.render()
        return resposta


class _NaSPA:
    """Põe no contexto a origem da SPA, para os links de "cancelar", dos termos e da volta."""

    def get_context_data(self, **kwargs):
        return super().get_context_data(spa_url=settings.SPA_URL, **kwargs)


class _ComRequisitosDeSenha:
    """Põe no contexto os requisitos de senha, montados a partir de `AUTH_PASSWORD_VALIDATORS`."""

    def get_context_data(self, **kwargs):
        return super().get_context_data(requisitos=password_validators_help_texts(), **kwargs)


def _na_spa(caminho):
    return HttpResponseRedirect(f"{settings.SPA_URL}{caminho}")


class PaginaDeLogin(EmPortugues, LoginView):
    pass


@method_decorator(sensitive_post_parameters(), name="dispatch")
@method_decorator(never_cache, name="dispatch")
class PaginaDeCadastro(EmPortugues, _NaSPA, _ComRequisitosDeSenha, RedirectURLMixin, FormView):
    """O cadastro, aberto pelo `prompt=create` do toolkit ou direto.

    O toolkit manda um `next` absoluto para o mesmo `/o/authorize/`, e o `RedirectURLMixin` o
    confere contra o `Host` do pedido, como no login. Sem `next` válido, a raiz da SPA.
    """

    form_class = FormularioDeCadastro
    template_name = "registration/cadastro.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return HttpResponseRedirect(self.get_success_url())
        return super().dispatch(request, *args, **kwargs)

    def get_default_redirect_url(self):
        return f"{settings.SPA_URL}/"

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            next=self.get_redirect_url(),
            termos_versao_vigente=settings.TERMOS_VERSAO_VIGENTE,
            **kwargs,
        )

    def form_valid(self, form):
        conta = form.save()
        conta_criada.send(sender=type(self), request=self.request, user=conta)
        envio.enfileirar(emails.confirmacao(conta), "confirmacao", aviso=False)
        # O backend nomeado: com dois em `AUTHENTICATION_BACKENDS`, `login()` sem ele recusa a
        # conta que não passou por `authenticate()`.
        login(self.request, conta, backend="django.contrib.auth.backends.ModelBackend")
        return HttpResponseRedirect(self.get_success_url())


class PaginaDeRecuperacao(EmPortugues, PasswordResetView):
    form_class = FormularioDeRecuperacao


class PaginaDeRecuperacaoPedida(EmPortugues, PasswordResetDoneView):
    pass


class PaginaDeRedefinicao(EmPortugues, _ComRequisitosDeSenha, PasswordResetConfirmView):
    """A senha nova pelo link. O token sai da barra na primeira resposta, pelo Django.

    Sem `post_reset_login`: quem tem o link não ganha sessão, e a página final leva à SPA.

    O link de uma conta que é da equipe no momento do uso cai na página de link inválido, mesmo
    emitido antes de ela entrar na equipe: a equipe troca a senha por `manage.py changepassword`.
    """

    form_class = FormularioDeRedefinicao
    post_reset_login = False

    def get_user(self, uidb64):
        conta = super().get_user(uidb64)
        if conta is not None and (conta.is_staff or conta.is_superuser):
            return None
        return conta

    def form_valid(self, form):
        resposta = super().form_valid(form)
        conta = form.user
        # As sessões abertas caem sozinhas: o hash de sessão do Django deriva da senha.
        revogar_tokens(self.request, conta)
        # O axes só zera as falhas no login bem-sucedido; sem isto, a senha nova esperaria o
        # fim do bloqueio (ADR 0031). O histórico de login fica: o endereço ainda é da conta.
        desbloquear(conta.email)
        senha_redefinida.send(sender=type(self), request=self.request, user=conta)
        envio.enfileirar(emails.senha_trocada(conta), "senha_trocada", aviso=True)
        return resposta


class PaginaDeRedefinicaoConcluida(EmPortugues, _NaSPA, PasswordResetCompleteView):
    pass


class PaginaDeTrocaDeSenha(EmPortugues, _NaSPA, _ComRequisitosDeSenha, PasswordChangeView):
    """A troca com a senha atual. Mantém a sessão desta requisição e derruba as outras."""

    form_class = FormularioDeTrocaDeSenha

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "request": self.request}

    def get_success_url(self):
        # No lugar de `password_change_done`, que não é publicada.
        return f"{settings.SPA_URL}/app/conta?aviso=senha-trocada"

    def form_valid(self, form):
        resposta = super().form_valid(form)
        conta = form.user
        revogar_tokens(self.request, conta)
        senha_trocada.send(sender=type(self), request=self.request, user=conta)
        envio.enfileirar(emails.senha_trocada(conta), "senha_trocada", aviso=True)
        return resposta


@method_decorator(sensitive_post_parameters(), name="dispatch")
@method_decorator(never_cache, name="dispatch")
class PaginaDeTrocaDeEmail(LoginRequiredMixin, EmPortugues, _NaSPA, FormView):
    """A troca vale na hora e mantém o `sub` e as sessões.

    A confirmação vai ao endereço novo, com teto; o aviso vai ao antigo, sob o teto alto dos
    avisos.
    """

    form_class = FormularioDeTrocaDeEmail
    template_name = "registration/troca_de_email.html"

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "request": self.request}

    def form_valid(self, form):
        conta = self.request.user
        antigo = conta.email
        conta.email = form.cleaned_data["novo_email"]
        with transaction.atomic():
            # O `save()` zera a verificação e move `updated_at`, e acrescenta os campos.
            conta.save(update_fields=["email"])
            esquecer_tentativas(antigo)
        envio.enfileirar(emails.confirmacao(conta), "confirmacao", aviso=False)
        envio.enfileirar(emails.aviso_de_troca_de_email(antigo), "troca_de_email", aviso=True)
        email_trocado.send(sender=type(self), request=self.request, user=conta)
        return _na_spa("/app/conta?aviso=email-trocado")


@method_decorator(sensitive_post_parameters(), name="dispatch")
@method_decorator(never_cache, name="dispatch")
class PaginaDeExclusao(LoginRequiredMixin, EmPortugues, _NaSPA, FormView):
    """Desativar ou apagar a própria conta. Conta da equipe sai pelo admin.

    A recusa a `is_staff` e a `is_superuser` vale em GET e em POST, sem formulário: apagar a
    última conta de admin pela página deixaria o IdP sem quem o administre.

    Conta dona de Application só desativa: o `delete()` levaria em cascata a Application e os
    tokens de toda a RP (ADR 0031).
    """

    form_class = FormularioDeExclusao
    template_name = "registration/exclusao.html"

    def get(self, request, *args, **kwargs):
        if self._da_equipe():
            return self._recusa()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if self._da_equipe():
            return self._recusa()
        return super().post(request, *args, **kwargs)

    def _da_equipe(self):
        return self.request.user.is_staff or self.request.user.is_superuser

    def _recusa(self):
        contexto = self.get_context_data(form=None, recusada=True)
        return self.render_to_response(contexto, status=403)

    def _pode_apagar(self):
        return not get_application_model().objects.filter(user=self.request.user).exists()

    def get_form_kwargs(self):
        return {
            **super().get_form_kwargs(),
            "request": self.request,
            "pode_apagar": self._pode_apagar(),
        }

    def form_valid(self, form):
        if form.cleaned_data["modo"] == "desativar":
            return self._desativar(self.request.user)
        return self._apagar(self.request.user)

    def _desativar(self, conta):
        conta.is_active = False
        conta.desativada_em = timezone.now()
        conta.desativada_por = "propria_pessoa"
        conta.save(update_fields=["is_active", "desativada_em", "desativada_por"])
        revogar_tokens(self.request, conta)
        envio.enfileirar(emails.conta_desativada(conta), "conta_desativada", aviso=True)
        conta_desativada.send(sender=type(self), request=self.request, user=conta)
        logout(self.request)
        return _na_spa("/?conta=desativada")

    def _apagar(self, conta):
        # Lidos antes: depois do `delete()` a conta não existe, e o aviso e a trilha precisam
        # dos dois.
        email, sub = conta.email, str(conta.sub)
        revogar_tokens(self.request, conta)
        with transaction.atomic():
            esquecer_tentativas(email)
            conta.delete()
        envio.enfileirar(emails.conta_apagada(email), "conta_apagada", aviso=True)
        conta_apagada.send(sender=type(self), request=self.request, sub=sub)
        logout(self.request)
        return _na_spa("/?conta=apagada")
