"""Infraestrutura compartilhada pelos testes da API de conta (TASK-028, ADR 0031).

Não é teste em si. Reúne o que `tests/test_api_conta*.py` repetiriam: a conta e as duas
Applications (a da SPA e outra qualquer), a `SPA_CLIENT_ID` apontada para a da SPA, o
`AccessToken` criado direto no banco — sem o fluxo de autorização, que não é o objeto aqui —,
a leitura crua da trilha e a fotografia da linha da conta, para provar que um 400 não gravou.
"""

import json
import os
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from oauth2_provider.models import AccessToken

from tests.logout_helpers import criar_application, handler_da_trilha

User = get_user_model()

ORIGEM_DA_SPA = "http://localhost:5173"
SENHA = "x-Senha-forte-123"
CAMINHO_CONTA = "/api/conta/"
CAMINHO_CONFIRMACAO = "/api/conta/confirmacao/"
CAMINHO_TERMOS = "/api/conta/termos/"
CAMINHOS_COM_BEARER = (CAMINHO_CONTA, CAMINHO_CONFIRMACAO, CAMINHO_TERMOS)


def criar_token(usuario, aplicacao, scope="openid conta", expira_em=3600):
    """O `AccessToken` direto no banco. `expira_em` negativo cria um token já expirado."""
    return AccessToken.objects.create(
        user=usuario,
        application=aplicacao,
        token=os.urandom(16).hex(),
        scope=scope,
        expires=timezone.now() + timedelta(seconds=expira_em),
    ).token


def bearer(token):
    """O argumento extra do test client que leva o cabeçalho `Authorization`."""
    return {"HTTP_AUTHORIZATION": "Bearer " + token}


def texto_da_trilha_desde(tamanho_antes):
    """O que a trilha ganhou desde `tamanho_antes`, como texto cru, sem interpretar."""
    with open(handler_da_trilha().baseFilename, "r", encoding="utf-8") as arquivo:
        arquivo.seek(tamanho_antes)
        return arquivo.read()


def linhas_do_evento(linhas, evento):
    return [linha for linha in linhas if linha.get("event") == evento]


def fotografia(usuario):
    """Todas as colunas da linha da conta, para comparar antes e depois."""
    return User.objects.filter(pk=usuario.pk).values().get()


class ApiDeContaTestCase(TestCase):
    """Uma conta, a Application da SPA e outra, e `SPA_CLIENT_ID` apontada para a da SPA."""

    @classmethod
    def setUpTestData(cls):
        cls.conta = User.objects.create_user(
            email="Pessoa@Exemplo.test",
            password=SENHA,
            first_name="Ana",
            last_name="Sobrenome",
        )
        cls.spa = criar_application(cls.conta, nome="SPA")
        cls.outra = criar_application(cls.conta, nome="Outra RP")

    def setUp(self):
        self.enterContext(override_settings(SPA_CLIENT_ID=self.spa.client_id))
        self.token = criar_token(self.conta, self.spa)
        self.cabecalho = bearer(self.token)

    def corpo_json(self, caminho, corpo, metodo="post", **extra):
        """Envia `corpo` (texto ou bytes crus, ou objeto a serializar) como JSON, com o Bearer."""
        if not isinstance(corpo, (str, bytes)):
            corpo = json.dumps(corpo)
        enviar = getattr(self.client, metodo)
        return enviar(caminho, corpo, content_type="application/json", **{**self.cabecalho, **extra})
