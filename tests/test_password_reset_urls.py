"""TASK-007/T-05, invertido por TASK-028/T-42 — as rotas de recuperação de senha existem, em
português, uma a uma.

Demanda do quality-assurance. Nível integração. Até a TASK-028 a proibição era não incluir
`django.contrib.auth.urls`, e as duas rotas de recuperação respondiam 404. A ADR 0031 as
publicou, uma de cada vez, com templates próprios e dentro de `EmPortugues`. O que se guarda
agora é o contrário: cada uma responde 200 com a página em português, e o que o include
publicaria a mais continua ausente.

Fica vermelho se `django.contrib.auth.urls` voltar (as rotas cairiam em template do admin, em
inglês), se uma das quatro rotas perder o template próprio ou o idioma, ou se
`password_change_done` for publicada: a troca de senha volta à SPA e a rota não existe.
"""

from django.test import TestCase
from django.urls import NoReverseMatch, reverse

# (caminho, `<h1>` da página, template próprio).
PAGINAS = [
    ("/accounts/password_reset/", "Esqueci a senha", "registration/password_reset_form.html"),
    (
        "/accounts/password_reset/done/",
        "Confira o e-mail",
        "registration/password_reset_done.html",
    ),
    ("/accounts/reset/MQ/x/", "Link inválido", "registration/password_reset_confirm.html"),
    ("/accounts/reset/done/", "Senha trocada", "registration/password_reset_complete.html"),
]


class RotasDeRecuperacaoTests(TestCase):
    def test_cada_rota_responde_200_em_portugues_com_titulo_e_template_proprios(self):
        for caminho, titulo, template in PAGINAS:
            with self.subTest(caminho=caminho):
                resposta = self.client.get(caminho)

                self.assertEqual(resposta.status_code, 200)
                corpo = resposta.content.decode()
                self.assertIn('<html lang="pt-br">', corpo)
                self.assertIn(f"<h1>{titulo}</h1>", corpo)
                self.assertTemplateUsed(resposta, template)
                # O include do Django cairia no template do admin, em inglês.
                self.assertNotIn("Django administration", corpo)
                self.assertNotIn("Password reset", corpo)

    def test_password_change_done_nao_e_publicada(self):
        self.assertEqual(self.client.get("/accounts/password_change/done/").status_code, 404)
        with self.assertRaises(NoReverseMatch):
            reverse("password_change_done")
