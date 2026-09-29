"""TASK-025/T-02 — a chave que `scripts/gen_env_secrets.sh --so-chave-rsa` gera atravessa a
leitura de settings e sai publicada no JWKS (JSON Web Key Set) com 3072 bits.

Demanda do quality-assurance. Nível integração: o defeito que interessa é a costura entre o
escape do PEM em uma linha (`\\n` literal) e o `env.str(..., multiline=True)` que o desfaz em
`config/settings.py`; um tamanho errado ou um escape que quebre a leitura só aparecem na
resposta da view. O `oauth2_settings` do toolkit recarrega no sinal `setting_changed` quando a
setting é `OAUTH2_PROVIDER`, então `override_settings` basta.

O `n` publicado é comparado ao módulo da chave gerada, e não só ao tamanho: se o
`override_settings` deixasse de surtir efeito e o .env tivesse uma chave de 3072 bits, o
tamanho sozinho passaria medindo a chave errada.

Nenhuma mensagem de asserção contém a chave ou o módulo.
"""

import base64
import subprocess
from pathlib import Path

import environ
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from django.conf import settings
from django.test import TestCase, override_settings

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "gen_env_secrets.sh"


def base64url_decode(texto):
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


class ChaveGeradaNoJwksTests(TestCase):
    def test_chave_do_script_publicada_com_3072_bits(self):
        res = subprocess.run(
            ["bash", str(SCRIPT), "--so-chave-rsa"], capture_output=True, text=True
        )
        self.assertEqual(res.returncode, 0, "o script falhou; stderr: " + res.stderr)

        # Mesma leitura de config/settings.py: o valor do .env passa por env.str multiline.
        # A decodificação é a do próprio django-environ, lida de um ambiente efêmero.
        linha = res.stdout.rstrip("\n")
        nome, _, bruto = linha.partition("=")
        self.assertEqual(nome, "OIDC_RSA_PRIVATE_KEY")
        env = environ.Env()
        env.ENVIRON = {nome: bruto}
        pem = env.str(nome, multiline=True)
        self.assertTrue(pem.startswith("-----BEGIN PRIVATE KEY-----\n"), "o PEM não foi desescapado")

        provider = {**settings.OAUTH2_PROVIDER, "OIDC_RSA_PRIVATE_KEY": pem}
        with override_settings(OAUTH2_PROVIDER=provider):
            response = self.client.get("/o/.well-known/jwks.json")

        self.assertEqual(response.status_code, 200)
        chaves = response.json()["keys"]
        self.assertEqual(len(chaves), 1)
        chave = chaves[0]
        self.assertEqual(chave["kty"], "RSA")
        self.assertEqual(chave["alg"], "RS256")
        self.assertTrue(chave["kid"])
        publicado = base64url_decode(chave["n"])
        self.assertEqual(len(publicado) * 8, 3072)
        modulo = load_pem_private_key(pem.encode(), password=None).public_key().public_numbers().n
        self.assertTrue(
            int.from_bytes(publicado, "big") == modulo,
            "o n do JWKS não é o módulo da chave gerada pelo script (valores omitidos)",
        )
