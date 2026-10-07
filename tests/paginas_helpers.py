"""Infraestrutura compartilhada pelos testes das páginas de conta do IdP (TASK-028, ADR 0031).

Não é teste em si. Reúne o que `tests/test_pagina_*.py` repetiriam: a conta com duas
Applications que não são dela, a semeadura e a contagem das três tabelas do `axes`, a contagem
dos tokens vivos, a leitura da trilha e o teto de envios esgotado.

As Applications têm outra pessoa como dona (`dono`). Quem é `user` de uma Application não pode
apagar a conta pela página (ADR 0031), e os casos de apagamento precisam de tokens sem essa
trava; os de T-64 criam a Application da própria conta de propósito.

O contador de envios vive no Redis e não volta com o rollback do `TestCase`. Quem o enche apaga a
chave por `config`/`accounts.envio.chave_do_envio` no fim, nunca por `cache.clear()`, que é
`FLUSHDB` e levaria junto a cópia quente das sessões (ADR 0005).
"""

import json
import re
from urllib.parse import parse_qs, urlsplit

from axes.models import AccessAttempt, AccessFailureLog, AccessLog
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from oauth2_provider.models import AccessToken, IDToken, RefreshToken

from accounts.envio import chave_do_aviso, chave_do_envio
from tests.logout_helpers import (
    criar_application,
    emitir_tokens,
    linhas_da_trilha_desde,
    tamanho_da_trilha,
)

User = get_user_model()

SENHA = "x-Senha-forte-123"
NOVA = "Outra-Senha-forte-456"
EMAIL = "pessoa@ex.com"


NEXT_ABSOLUTO = "http://testserver/o/authorize/?client_id=abc&state=s"


def dados_de_cadastro(email="Nova@Ex.COM", **mudancas):
    """O corpo válido do cadastro; `chave=None` tira o campo, e `next=None` tira o destino."""
    dados = {
        "email": email,
        "first_name": "Nova",
        "last_name": "Pessoa",
        "nickname": "nov",
        "password1": NOVA,
        "password2": NOVA,
        "aceite": "on",
        "termos_versao": settings.TERMOS_VERSAO_VIGENTE,
        "next": NEXT_ABSOLUTO,
    }
    dados.update(mudancas)
    return {chave: valor for chave, valor in dados.items() if valor is not None}


def semear_axes(email, ip="10.0.0.1", falhas=1):
    """Uma linha em cada tabela do `axes` para `email`, tal como veio digitado.

    `falhas` fica abaixo do teto (cinco): o semeado não pode bloquear a conta, ou o caso passaria
    a provar o bloqueio. O `axes` 8.3.1 não grava `AccessFailureLog` nem `AccessLog` numa falha,
    e por isso as três são escritas à mão.
    """
    AccessAttempt.objects.create(
        username=email, ip_address=ip, failures_since_start=falhas, get_data="", post_data=""
    )
    AccessFailureLog.objects.create(username=email, ip_address=ip)
    AccessLog.objects.create(username=email, ip_address=ip)


def contagem_axes(email):
    """`(AccessAttempt, AccessFailureLog, AccessLog)` do endereço, sem distinção de caixa."""
    return (
        AccessAttempt.objects.filter(username__iexact=email).count(),
        AccessFailureLog.objects.filter(username__iexact=email).count(),
        AccessLog.objects.filter(username__iexact=email).count(),
    )


def vivos(conta, aplicacao=None):
    """`(AccessToken, IDToken, RefreshToken sem revoked)` da conta, em uma Application ou em todas."""
    filtro = {"user": conta}
    if aplicacao is not None:
        filtro["application"] = aplicacao
    return (
        AccessToken.objects.filter(**filtro).count(),
        IDToken.objects.filter(**filtro).count(),
        RefreshToken.objects.filter(revoked__isnull=True, **filtro).count(),
    )


def eventos(linhas):
    return [linha["event"] for linha in linhas]


def com_arroba(linhas):
    """As linhas da trilha que carregam um endereço de e-mail, em qualquer campo."""
    return [linha for linha in linhas if "@" in json.dumps(linha)]


def link_do_email(mensagem):
    """O link de redefinição ou de confirmação do corpo da mensagem."""
    achados = re.findall(r"https?://\S+", mensagem.body)
    assert len(achados) == 1, achados
    return achados[0]


def caminho_do_link(link):
    """Caminho e query de um link absoluto, para o test client."""
    partes = urlsplit(link)
    return partes.path + ("?" + partes.query if partes.query else "")


def consulta(url):
    return parse_qs(urlsplit(url).query)


class PaginasDeContaTestCase(TestCase):
    """Uma conta `pessoa@ex.com`, o `dono` das duas Applications e `postar`, que roda o commit."""

    def setUp(self):
        self.dono = User.objects.create_superuser("dono@ex.com", SENHA)
        self.conta = User.objects.create_user(EMAIL, SENHA)
        self.app1 = criar_application(self.dono, "SPA um")
        self.app2 = criar_application(self.dono, "SPA dois")
        self.addCleanup(mail.outbox.clear)

    def tokens_nas_duas(self, conta=None, client=None):
        """Sessão da conta com tokens em app1 e em app2. Devolve o client da sessão."""
        conta = conta or self.conta
        client, _ = emitir_tokens(conta, self.app1, client)
        emitir_tokens(conta, self.app2, client)
        return client

    def outra_sessao(self, conta=None):
        client = Client()
        client.force_login(conta or self.conta)
        return client

    def postar(self, client, url, dados=None, **extra):
        """POST com os callbacks de commit executados, para o e-mail estar em `mail.outbox`."""
        with self.captureOnCommitCallbacks(execute=True):
            return client.post(url, dados or {}, **extra)

    def esgotar_teto(self, *enderecos):
        """O teto de envios esgotado para todo destinatário, e as chaves apagadas no fim.

        O teto zero recusa já a primeira contagem. Cada chave tocada sai por `chave_do_envio`.
        """
        self.enterContext(override_settings(TETO_DE_ENVIOS_POR_DESTINATARIO=0))
        for endereco in enderecos:
            self.addCleanup(cache.delete, chave_do_envio(endereco))

    def esgotar_teto_de_avisos(self, *enderecos):
        """TASK-028/T-76 — o teto dos avisos de segurança esgotado, e as chaves apagadas no fim.

        É outro contador que o de `esgotar_teto`: confirmações e links não gastam o dos avisos.
        """
        self.enterContext(override_settings(TETO_DE_AVISOS_POR_DESTINATARIO=0))
        for endereco in enderecos:
            self.addCleanup(cache.delete, chave_do_aviso(endereco))

    def trilha(self):
        """Marca o ponto atual da trilha; o retorno lê o que veio depois."""
        marca = tamanho_da_trilha()
        return lambda: linhas_da_trilha_desde(marca)

    def assertSessaoDeslogada(self, client):
        resposta = client.get("/accounts/password_change/")
        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(resposta["Location"].startswith("/accounts/login/"), resposta["Location"])

    def assertSessaoViva(self, client):
        self.assertEqual(client.get("/accounts/password_change/").status_code, 200)

    @property
    def spa(self):
        return settings.SPA_URL
