"""A API de conta, consumida pela SPA com o `access_token` dela (ADR 0031).

Três recursos sob Bearer com o scope `conta`, sobre `RecursoDaConta`, e o endpoint anônimo do
link de confirmação. Tudo o que recebe senha é página do IdP, em `accounts/paginas.py`; daqui
não sai nem entra senha.

A API fala inglês: `LANGUAGE_CODE` é `en-us`, e não há `translation.override` aqui. A
`mensagem` de cada erro é para quem depura; a SPA exibe pelo `codigo`.

Todo 400 tem a forma `{"erros": {"<campo>": [{"codigo": ..., "mensagem": ...}]}}`, com `geral`
para o corpo que não é objeto JSON.
"""

import json

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from oauth2_provider.views.generic import ScopedProtectedResourceMetadataView

from accounts import confirmacao as token_de_confirmacao
from accounts import emails, envio
from accounts.sinais import conta_editada, email_confirmado, termos_aceitos


# A isenção de CSRF depende de uma condição: a API não aceita sessão. Ela lê a conta só do
# token, nunca de `request.user` nem de `request.session`, e o cookie de sessão sozinho recebe
# 401. No dia em que a API ler a sessão, um site qualquer faz o navegador da pessoa editar a
# conta dela, e nada acusa.
@method_decorator(csrf_exempt, name="dispatch")
class RecursoDaConta(ScopedProtectedResourceMetadataView):
    """A base dos recursos: Bearer válido, scope `conta`, token da SPA e conta ativa.

    O 401 e o 403 de scope são os do toolkit, com o desafio `WWW-Authenticate: Bearer` e o
    parâmetro `resource_metadata`, que aponta para `/o/.well-known/oauth-protected-resource` no
    host do pedido (`build_absolute_uri`). O `resource` desse documento é `/o` no mesmo host, e
    não a API; a SPA o ignora.
    """

    required_scopes = ["conta"]

    def dispatch(self, request, *args, **kwargs):
        # A preflight da origem da SPA já foi respondida pelo CorsMiddleware; a de outra origem
        # chega aqui e recebe a resposta comum de OPTIONS, sem cabeçalho de CORS.
        if request.method.upper() == "OPTIONS":
            return View.dispatch(self, request, *args, **kwargs)
        # Só o cabeçalho `Authorization`: o oauthlib, quando ele falta, lê o token de
        # `?access_token=` e do corpo form-urlencoded, e um token na URL vai para o log da borda e
        # para o Referer. Presente o cabeçalho, o oauthlib lê só dele, seja qual for o esquema.
        if "HTTP_AUTHORIZATION" not in request.META:
            return self.unauthenticated_response(request)
        valido, r = self.verify_request(request)
        if not valido:
            return self.unauthenticated_response(request, r)
        token = r.access_token
        # O toolkit não tem scope por Application: toda RP que peça `conta`, ou que omita
        # `scope`, recebe-o. É esta comparação que restringe a API à SPA.
        if token.application.client_id != settings.SPA_CLIENT_ID:
            return JsonResponse({"codigo": "aplicacao_nao_autorizada"}, status=403)
        # Token sem conta é de client_credentials: só chega aqui se `SPA_CLIENT_ID` apontar por
        # engano para uma Application desse tipo.
        if token.user is None:
            return JsonResponse({"codigo": "aplicacao_nao_autorizada"}, status=403)
        # O toolkit não confere `is_active` no Bearer: o token de uma conta desativada pelo
        # admin continua válido até expirar.
        if not token.user.is_active:
            return JsonResponse({"codigo": "conta_inativa"}, status=403)
        self.token = token
        request.resource_owner = token.user
        # `View.dispatch` direto, pulando o `ProtectedResourceMixin.dispatch`, que verificaria o
        # token uma segunda vez. A subida do toolkit relê este método contra o dele.
        return View.dispatch(self, request, *args, **kwargs)


class _Texto(forms.CharField):
    """`CharField` que recusa o que não é texto no JSON.

    O `CharField` converte por `str()`, e `5` ou `["a"]` virariam o texto `"5"` ou `"['a']"`.
    `null` passa, e vale como texto vazio.
    """

    def to_python(self, value):
        if value is not None and not isinstance(value, str):
            raise ValidationError("Enter a string.", code="invalid")
        return super().to_python(value)


class _Perfil(forms.Form):
    first_name = _Texto(max_length=150, required=False)
    last_name = _Texto(max_length=150, required=False)
    nickname = _Texto(max_length=150, required=False)


class _Termos(forms.Form):
    # Sem `strip`: vale a versão como enviada, e `" 1 "` não é a vigente `"1"`.
    versao = _Texto(strip=False)

    def clean_versao(self):
        versao = self.cleaned_data["versao"]
        if versao != settings.TERMOS_VERSAO_VIGENTE:
            raise ValidationError(
                "This is not the current version of the terms.", code="termos_desatualizados"
            )
        return versao


class Conta(RecursoDaConta):
    def get(self, request):
        return JsonResponse(_corpo(self.token.user))

    def patch(self, request):
        dados = _objeto_json(request)
        if dados is None:
            return _json_invalido()
        # Só as chaves da lista fechada, e só as presentes: a ausente não é apagada.
        presentes = {campo: dados[campo] for campo in _Perfil.base_fields if campo in dados}
        formulario = _Perfil(presentes)
        if not formulario.is_valid():
            return _erros(formulario)
        conta = self.token.user
        alterados = [
            campo
            for campo in presentes
            if formulario.cleaned_data[campo] != getattr(conta, campo)
        ]
        if alterados:
            for campo in alterados:
                setattr(conta, campo, formulario.cleaned_data[campo])
            # Só os campos alterados: uma edição do admin em outro campo, no mesmo instante, não
            # é sobrescrita pelo valor antigo que este objeto carrega.
            conta.save(update_fields=alterados)
            conta_editada.send(sender=type(self), request=request, user=conta, campos=alterados)
        return JsonResponse(_corpo(conta))


class ReenvioDaConfirmacao(RecursoDaConta):
    def post(self, request):
        conta = self.token.user
        # A resposta é a mesma com ou sem envio, e também quando o teto por destinatário o
        # suprime.
        if not conta.email_verified:
            envio.enfileirar(emails.confirmacao(conta), "confirmacao", aviso=False)
        return HttpResponse(status=204)


class AceiteDosTermos(RecursoDaConta):
    def post(self, request):
        dados = _objeto_json(request)
        if dados is None:
            return _json_invalido()
        formulario = _Termos(dados)
        if not formulario.is_valid():
            return _erros(formulario)
        conta = self.token.user
        conta.termos_versao = formulario.cleaned_data["versao"]
        conta.termos_aceitos_em = timezone.now()
        conta.save(update_fields=["termos_versao", "termos_aceitos_em"])
        termos_aceitos.send(
            sender=type(self), request=request, user=conta, termos_versao=conta.termos_versao
        )
        return HttpResponse(status=204)


@require_GET
def confirmar(request):
    """O link de confirmação do e-mail: sem autenticação, sempre redireciona à SPA.

    Válido, a conta existe e está ativa, e o resumo bate com o e-mail atual: `confirmado`. O
    segundo clique também, sem carimbo novo nem linha nova na trilha. Qualquer outro caso:
    `invalido`, sem mudança.
    """
    lido = token_de_confirmacao.ler(request.GET.get("t", ""))
    if lido is None:
        return _para_a_spa("invalido")
    sub, resumo = lido
    with transaction.atomic():
        # Travada até o commit: dois cliques simultâneos, ou o de um antivírus junto com o da
        # pessoa, confirmariam duas vezes e deixariam duas linhas na trilha.
        conta = get_user_model().objects.select_for_update().filter(sub=sub).first()
        if (
            conta is None
            or not conta.is_active
            or token_de_confirmacao.resumo_do_email(conta.email) != resumo
        ):
            return _para_a_spa("invalido")
        primeira_vez = not conta.email_verified
        if primeira_vez:
            conta.email_verified = True
            conta.email_verificado_em = timezone.now()
            conta.save(update_fields=["email_verified", "email_verificado_em"])
    # Fora do bloco: a trilha não volta com o rollback, e só registra o que já foi gravado.
    if primeira_vez:
        email_confirmado.send(sender=confirmar, request=request, user=conta)
    return _para_a_spa("confirmado")


def _corpo(conta):
    return {
        "sub": str(conta.sub),
        "email": conta.email,
        "email_verified": conta.email_verified,
        "first_name": conta.first_name,
        "last_name": conta.last_name,
        "nickname": conta.nickname,
        "date_joined": conta.date_joined.isoformat(),
        "updated_at": conta.updated_at.isoformat(),
        "senha_alterada_em": (
            conta.senha_alterada_em.isoformat() if conta.senha_alterada_em else None
        ),
        "termos_versao": conta.termos_versao,
        "termos_versao_vigente": settings.TERMOS_VERSAO_VIGENTE,
    }


def _objeto_json(request):
    """O corpo como dicionário, ou `None` se ele não é um objeto JSON."""
    try:
        dados = json.loads(request.body)
    # ValueError cobre o JSON malformado e o corpo que não é UTF-8; RecursionError, o aninhamento
    # profundo, que o decodificador recusa estourando a pilha.
    except (ValueError, RecursionError):
        return None
    return dados if isinstance(dados, dict) else None


def _json_invalido():
    return JsonResponse(
        {
            "erros": {
                "geral": [
                    {
                        "codigo": "json_invalido",
                        "mensagem": "The request body must be a JSON object.",
                    }
                ]
            }
        },
        status=400,
    )


def _erros(formulario):
    return JsonResponse(
        {
            "erros": {
                campo: [{"codigo": erro["code"], "mensagem": erro["message"]} for erro in lista]
                for campo, lista in formulario.errors.get_json_data().items()
            }
        },
        status=400,
    )


def _para_a_spa(desfecho):
    return HttpResponseRedirect(f"{settings.SPA_URL}/?email={desfecho}")
