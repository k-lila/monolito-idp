"""TASK-028/T-58 — os dois links da tela de login e a mensagem do POST vazio.

Demanda do quality-assurance. Nível integração: o `next` da `LoginView`, o filtro `urlencode` do
template e a tradução da página só se encontram na tela renderizada.

"Criar conta" leva o `next` conferido, codificado inteiro (o `?`, o `=` e o `&` do pedido
interrompido de `/o/authorize/` não podem se confundir com a query do próprio link), para o
cadastro devolver ao mesmo pedido. Com `next` hostil, o `LoginView` o descarta e o link sai com
`?next=` vazio. "Esqueci a senha" não leva `next`: o link chega por e-mail e a recuperação termina
na SPA. O POST vazio mostra "Este campo é obrigatório." nos dois campos, em português.

Vermelho se o `next` for omitido do "Criar conta", se sair sem codificar, se o hostil for repassado
ao cadastro, ou se a mensagem sair em inglês.
"""

import re
from urllib.parse import urlencode

from django.test import TestCase

URL = "/accounts/login/"


def _href(corpo, texto):
    achado = re.search(rf'<a href="([^"]*)">{texto}</a>', corpo)
    assert achado, f"link {texto!r} ausente"
    return achado.group(1)


class LinksDoLoginTests(TestCase):
    def test_criar_conta_leva_o_next_codificado_e_esqueci_a_senha_nao_leva(self):
        proximo = "/o/authorize/?a=1&b=2"

        corpo = self.client.get(f"{URL}?{urlencode({'next': proximo})}").content.decode()

        self.assertEqual(
            _href(corpo, "Criar conta"), "/accounts/registrar/?next=/o/authorize/%3Fa%3D1%26b%3D2"
        )
        self.assertEqual(_href(corpo, "Esqueci a senha"), "/accounts/password_reset/")

    def test_next_hostil_nao_chega_ao_cadastro(self):
        corpo = self.client.get(f"{URL}?{urlencode({'next': 'https://evil.com/'})}").content.decode()

        self.assertEqual(_href(corpo, "Criar conta"), "/accounts/registrar/?next=")
        self.assertNotIn("evil.com", corpo)

    def test_post_vazio_pede_os_dois_campos_em_portugues(self):
        resposta = self.client.post(URL, {})

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Este campo é obrigatório.", count=2)
