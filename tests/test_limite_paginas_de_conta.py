"""TASK-028/T-59 — o teto de requisição do cadastro e do pedido de recuperação, e a ausência dele
no link de redefinição.

Demanda do quality-assurance. Nível integração. `RATE_LIMIT_POR_CAMINHO` compara o caminho por
igualdade, e por isso o link `/accounts/reset/<uid>/<token>/`, que muda a cada pedido, não tem
teto: o que o protege é o token de uso único e de uma hora (ADR 0031). O runner zera o dicionário
para a suíte; os casos o religam com o valor de produção, por `override_settings`, e com
`REMOTE_ADDR` próprio, e apagam as chaves no `tearDown`, nunca por `cache.clear()`.

O teto é lido do dicionário de produção, e não escrito aqui: o número não é asserção de teste
nenhum, de propósito (com o valor atual, 60, o 429 é a 61ª requisição). Vermelho se um dos dois
caminhos sair do dicionário de produção, ou se uma chave de `/accounts/reset/` entrar nele:
setenta GETs no link nunca recebem 429, e o dicionário não tem chave que comece por esse prefixo.
"""

from django.core.cache import cache
from django.test import TestCase, override_settings

from config.limites import chave_do_contador
from tests import runner

ORIGENS = {
    "/accounts/registrar/": "10.59.0.1",
    "/accounts/password_reset/": "10.59.0.2",
    "/accounts/reset/MQ/x/": "10.59.0.3",
    "/accounts/password_change/": "10.59.0.4",
    "/accounts/email/": "10.59.0.5",
    "/accounts/excluir/": "10.59.0.6",
}


class LimiteDasPaginasDeContaTests(TestCase):
    def setUp(self):
        self.assertIsNotNone(
            runner.RATE_LIMIT_DE_PRODUCAO,
            "o runner não guardou o teto de produção: a suíte rodou sem passar pelo setup?",
        )
        self.enterContext(override_settings(RATE_LIMIT_POR_CAMINHO=runner.RATE_LIMIT_DE_PRODUCAO))
        for caminho, origem in ORIGENS.items():
            self.addCleanup(cache.delete, chave_do_contador(caminho, origem))

    def _get(self, caminho):
        return self.client.get(caminho, REMOTE_ADDR=ORIGENS[caminho]).status_code

    def test_a_61a_requisicao_ao_cadastro_e_ao_pedido_de_recuperacao_e_429(self):
        for caminho in ("/accounts/registrar/", "/accounts/password_reset/"):
            with self.subTest(caminho=caminho):
                teto = runner.RATE_LIMIT_DE_PRODUCAO[caminho]
                dentro = [self._get(caminho) for _ in range(teto)]
                self.assertNotIn(429, dentro)

                self.assertEqual(self._get(caminho), 429)

    def test_as_tres_paginas_de_conta_logada_tem_o_teto_de_60_como_o_login(self):
        """TASK-028/T-74 — o POST confere a senha por `authenticate()` (Argon2), e o teto por
        origem limita o custo que uma origem impõe. Vermelho se um dos três sair do dicionário
        de produção, ou se o teto de um deles deixar de ser o do login."""
        for caminho in ("/accounts/password_change/", "/accounts/email/", "/accounts/excluir/"):
            with self.subTest(caminho=caminho):
                self.assertEqual(runner.RATE_LIMIT_DE_PRODUCAO[caminho], 60)
                self.assertEqual(
                    runner.RATE_LIMIT_DE_PRODUCAO[caminho],
                    runner.RATE_LIMIT_DE_PRODUCAO["/accounts/login/"],
                )
                dentro = [self._get(caminho) for _ in range(60)]
                self.assertNotIn(429, dentro)

                self.assertEqual(self._get(caminho), 429)

    def test_o_link_de_redefinicao_nunca_recebe_429(self):
        caminho = "/accounts/reset/MQ/x/"

        estados = {self._get(caminho) for _ in range(70)}

        self.assertEqual(estados, {200})

    def test_nenhuma_chave_de_producao_comeca_por_reset(self):
        self.assertEqual(
            [c for c in runner.RATE_LIMIT_DE_PRODUCAO if c.startswith("/accounts/reset/")], []
        )
