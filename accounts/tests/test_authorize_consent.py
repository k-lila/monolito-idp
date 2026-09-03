"""TASK-007/T-07 — tela de consentimento e o ramo de recusa, usuário já logado.

Demanda do quality-assurance (bloco E). Nível integração: o ramo de recusa não
tinha guarda nenhuma na suíte (a D só cobre o `allow`), e ele depende do botão
"Recusar" continuar sem atributo `name` no template.
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.tests.oauth_helpers import (
    REDIRECT_URI,
    create_public_rs256_application,
    extract_hidden_inputs,
    make_pkce_pair,
)

User = get_user_model()


class AuthorizeConsentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="consentimento@example.com", password="senha-forte-o-suficiente"
        )
        self.application = create_public_rs256_application(self.user)
        self.client.force_login(self.user)

        _verifier, challenge = make_pkce_pair()
        self.params = {
            "response_type": "code",
            "client_id": self.application.client_id,
            "redirect_uri": REDIRECT_URI,
            "scope": "openid profile email",
            "state": "consentimento-state",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "nonce": "consentimento-nonce",
        }

    def test_tela_de_consentimento_mostra_as_tres_descricoes_e_os_dois_submits(self):
        response = self.client.get("/o/authorize/", self.params)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()

        # Comparado contra a própria settings, não contra literal duplicado: se
        # a descrição de um scope mudar em OAUTH2_PROVIDER["SCOPES"], o teste
        # acompanha em vez de travar numa string congelada.
        scopes = settings.OAUTH2_PROVIDER["SCOPES"]
        for scope_name in ("openid", "profile", "email"):
            self.assertIn(scopes[scope_name], html)

        self.assertIn('name="allow"', html)
        # O botão "Recusar" é um <input type="submit"> sem atributo name — e essa
        # ausência que faz o POST de recusa não carregar "allow" no corpo.
        self.assertIn('value="Recusar"', html)

    def test_post_sem_allow_recusa_e_redireciona_com_access_denied(self):
        get_response = self.client.get("/o/authorize/", self.params)
        self.assertEqual(get_response.status_code, 200)

        hidden = extract_hidden_inputs(get_response.content.decode())
        # extract_hidden_inputs só pega <input type="hidden">: os dois submits
        # (allow/Recusar) não entram aqui, então post_data já nasce sem "allow" —
        # é exatamente o corpo que o clique em "Recusar" enviaria.
        post_data = dict(hidden)
        self.assertNotIn("allow", post_data)

        post_response = self.client.post("/o/authorize/", post_data)
        self.assertEqual(post_response.status_code, 302)
        location = post_response.get("Location", "")
        self.assertTrue(location.startswith(REDIRECT_URI))
        self.assertIn("error=access_denied", location)
