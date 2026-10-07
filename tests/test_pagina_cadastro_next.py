"""TASK-028/T-51 — o `next` do cadastro não é redirecionamento aberto.

Demanda do quality-assurance. Nível integração. O cadastro é a única página de conta que lê o
`next` do pedido (as outras voltam a destinos fixos da SPA), e o confere como o `LoginView`
confere: contra o `Host` do pedido, pelo `RedirectURLMixin`. Cada `next` hostil aparece no GET,
pela query, e no POST, só pelo corpo. No GET o campo oculto sai vazio; no POST válido a resposta
é exatamente `{SPA_URL}/`.

Os aceitos seguem: o caminho do próprio IdP, e o absoluto do mesmo `Host` em `https` quando o
pedido é seguro. Com sessão, o GET com `next` hostil também vai a `{SPA_URL}/`.

Vermelho se a conferência do `next` sair do cadastro, se o oculto devolver o valor hostil ou se
o POST seguir para fora. O POST de cada hostil é um cadastro de verdade, e por isso cada um
leva um e-mail próprio.
"""

import html
import re
from urllib.parse import urlencode

from tests.paginas_helpers import PaginasDeContaTestCase, User, dados_de_cadastro

URL = "/accounts/registrar/"

HOSTIS = [
    "//evil.com",
    "\\\\evil.com",
    "/\\evil.com",
    "\\/evil.com",
    "https://evil.com/",
    "javascript:alert(1)",
    "http://testserver@evil.com/",
    "http://evil.com\\@testserver/",
    "https:evil.com",
    " //evil.com",
    "\t//evil.com",
    "///evil.com",
    "http:///evil.com",
    "data:text/html,x",
    "HTTP://EVIL.COM",
    "https://testserver.evil.com/",
    "http://testserver:8000/x",
    "ftp://testserver/x",
]


def _oculto(corpo):
    achado = re.search(r'<input type="hidden" name="next" value="([^"]*)"', corpo)
    assert achado, "o campo oculto `next` não está na página"
    return html.unescape(achado.group(1))


class NextHostilTests(PaginasDeContaTestCase):
    def test_get_com_next_hostil_deixa_o_oculto_vazio(self):
        for hostil in HOSTIS:
            with self.subTest(next=hostil):
                resposta = self.client.get(f"{URL}?{urlencode({'next': hostil})}")

                self.assertEqual(resposta.status_code, 200)
                self.assertEqual(_oculto(resposta.content.decode()), "")

    def test_post_valido_com_next_hostil_so_no_corpo_vai_a_raiz_da_spa(self):
        for i, hostil in enumerate(HOSTIS):
            with self.subTest(next=hostil):
                resposta = self.client.post(URL, dados_de_cadastro(f"hostil{i}@ex.com", next=hostil))

                self.assertEqual(resposta.status_code, 302)
                self.assertEqual(resposta["Location"], f"{self.spa}/")
                self.assertTrue(User.objects.filter(email=f"hostil{i}@ex.com").exists())
                self.client.logout()

    def test_sem_next_vai_a_raiz_da_spa(self):
        resposta = self.client.post(URL, dados_de_cadastro(next=None))

        self.assertEqual(resposta["Location"], f"{self.spa}/")

    def test_aceitos_aparecem_no_get_e_sao_seguidos_no_post(self):
        casos = [
            ("https://testserver/o/authorize/", {"secure": True}),
            ("/o/authorize/?x=1", {}),
        ]
        for i, (aceito, extra) in enumerate(casos):
            with self.subTest(next=aceito):
                pagina = self.client.get(f"{URL}?{urlencode({'next': aceito})}", **extra)
                self.assertEqual(_oculto(pagina.content.decode()), aceito)

                resposta = self.client.post(
                    URL, dados_de_cadastro(f"aceito{i}@ex.com", next=aceito), **extra
                )

                self.assertEqual(resposta.status_code, 302)
                self.assertEqual(resposta["Location"], aceito)
                self.client.logout()

    def test_com_sessao_o_get_com_next_hostil_vai_a_raiz_da_spa(self):
        self.client.force_login(self.conta)

        resposta = self.client.get(f"{URL}?{urlencode({'next': '//evil.com'})}")

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta["Location"], f"{self.spa}/")
