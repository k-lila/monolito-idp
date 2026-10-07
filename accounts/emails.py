"""As seis mensagens de e-mail da conta, montadas e não enviadas (ADR 0031).

Cada função devolve um `EmailMessage` pronto para `accounts.envio.enfileirar`. Assunto e corpo
saem de `templates/emails/`, renderizados em português e no fuso `FUSO_DOS_EMAILS`, porque o
`LANGUAGE_CODE` do projeto é `en-us` e o `TIME_ZONE` é UTC.

Os links do IdP saem de `BASE_URL`, nunca de `request.get_host()` nem de
`build_absolute_uri()`: com o `Host` de quem pede, um cabeçalho forjado viraria um link de
phishing assinado pelo remetente do IdP.
"""

from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone, translation

from accounts import confirmacao as token_de_confirmacao


def confirmacao(user):
    """Boas-vindas e confirmação, num texto só: cadastro, "reenviar" e endereço novo."""
    link = _no_idp(reverse("api_conta_confirmar")) + "?" + urlencode(
        {"t": token_de_confirmacao.gerar(user)}
    )
    prazo_dias = token_de_confirmacao.PRAZO.days
    return _mensagem("confirmacao", user.email, {"link": link, "prazo_dias": prazo_dias})


def aviso_de_troca_de_email(email_antigo):
    """O aviso ao endereço que deixou de ser o da conta. Não leva o endereço novo."""
    return _mensagem("troca_de_email", email_antigo, {"quando": timezone.now()})


def redefinicao(contexto, destinatario):
    """A mensagem de redefinição, a partir do contexto que o `PasswordResetForm` monta.

    Do contexto, só `uid` e `token` são usados. `domain` e `protocol` vêm do `Host` da
    requisição, e por isso o link é montado aqui.
    """
    caminho = reverse(
        "password_reset_confirm",
        kwargs={"uidb64": contexto["uid"], "token": contexto["token"]},
    )
    # Do valor em vigor, para o texto não prometer um prazo que o token não cumpre.
    prazo_horas = settings.PASSWORD_RESET_TIMEOUT // 3600
    return _mensagem(
        "redefinicao", destinatario, {"link": _no_idp(caminho), "prazo_horas": prazo_horas}
    )


def senha_trocada(user):
    return _mensagem("senha_trocada", user.email, {"quando": timezone.now()})


def conta_desativada(user):
    return _mensagem("conta_desativada", user.email, {"quando": timezone.now()})


def conta_apagada(email):
    """Recebe o endereço, lido antes de a conta ser apagada."""
    return _mensagem("conta_apagada", email, {"quando": timezone.now()})


def _no_idp(caminho):
    return settings.BASE_URL.rstrip("/") + caminho


def _mensagem(nome, destinatario, contexto):
    with translation.override("pt-br"), timezone.override(ZoneInfo(settings.FUSO_DOS_EMAILS)):
        assunto = render_to_string(f"emails/{nome}_assunto.txt", contexto)
        corpo = render_to_string(f"emails/{nome}_corpo.txt", contexto)
    # Uma linha só: quebra de linha no assunto é injeção de cabeçalho, e o Django a recusa.
    assunto = "".join(assunto.splitlines())
    return EmailMessage(assunto, corpo, settings.DEFAULT_FROM_EMAIL, [destinatario])
