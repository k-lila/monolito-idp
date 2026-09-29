"""TASK-025/T-01 — a saída de `scripts/gen_env_secrets.sh`, o gerador único dos segredos do
.env (ADR 0028).

Demanda do quality-assurance. Nível integração: o que pode quebrar é a costura entre o shell,
o `openssl` e a gramática do .env, e só o subprocess a revela. O script é invocado por
`bash <caminho>`, não pelo bit de execução, que o `Dockerfile` registra como não confiável no
build. Não há skip condicional ao `openssl`: sem ele o teste tem de falhar, porque o script
também falharia.

Nenhuma mensagem de asserção contém o valor gerado. Uma falha aparece em log de terminal e de
integração, e uma chave privada ali seria um vazamento causado pelo próprio teste; por isso as
comparações são feitas em booleano e a mensagem diz só qual regra caiu.

Custo: três gerações de chave RSA (Rivest–Shamir–Adleman) de 3072 bits, uma por invocação que
imprime a chave, feitas uma vez por classe.
"""

import os
import re
import subprocess
from pathlib import Path

from django.test import SimpleTestCase

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "gen_env_secrets.sh"

CHAVES_NA_ORDEM = [
    "SECRET_KEY",
    "OIDC_RSA_PRIVATE_KEY",
    "POSTGRES_PASSWORD",
    "REDIS_PASSWORD",
    "DATABASE_URL",
    "REDIS_URL",
]


def rodar(*args, extra_env=None):
    """Executa o script com o ambiente limpo de POSTGRES_* e REDIS_PORT.

    O ambiente de quem roda a suíte pode ter essas variáveis (a jornada de container as
    tem), e elas mudariam as URLs impressas em silêncio.
    """
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("POSTGRES_") and k != "REDIS_PORT"
    }
    env.update(extra_env or {})
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        env=env,
        capture_output=True,
        text=True,
    )


def como_dicionario(stdout):
    """Quebra as linhas `CHAVE=valor` em (chaves na ordem, dicionário)."""
    linhas = stdout.splitlines()
    pares = [linha.split("=", 1) for linha in linhas]
    return [p[0] for p in pares], {p[0]: p[1] for p in pares}


class SaidaSemArgumentoTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = rodar()
        cls.chaves, cls.valores = como_dicionario(cls.res.stdout)

    def test_sai_com_zero(self):
        self.assertEqual(self.res.returncode, 0, "o script falhou; stderr: " + self.res.stderr)

    def test_seis_linhas_na_ordem(self):
        self.assertEqual(len(self.res.stdout.splitlines()), 6)
        self.assertEqual(self.chaves, CHAVES_NA_ORDEM)

    def test_formato_das_tres_senhas(self):
        for chave, padrao in (
            ("SECRET_KEY", r"[0-9a-f]{96}"),
            ("POSTGRES_PASSWORD", r"[0-9a-f]{48}"),
            ("REDIS_PASSWORD", r"[0-9a-f]{64}"),
        ):
            with self.subTest(chave=chave):
                self.assertTrue(
                    re.fullmatch(padrao, self.valores[chave]) is not None,
                    f"{chave} não casa {padrao} (valor omitido de propósito)",
                )

    def test_urls_derivam_das_senhas_das_proprias_linhas(self):
        esperado_db = f"postgres://nova_api:{self.valores['POSTGRES_PASSWORD']}@localhost:5432/nova_api"
        esperado_redis = f"redis://:{self.valores['REDIS_PASSWORD']}@localhost:6379/0"
        self.assertTrue(
            self.valores["DATABASE_URL"] == esperado_db,
            "DATABASE_URL diverge do padrão com a POSTGRES_PASSWORD da própria saída",
        )
        self.assertTrue(
            self.valores["REDIS_URL"] == esperado_redis,
            "REDIS_URL diverge do padrão com a REDIS_PASSWORD da própria saída",
        )


class SaidaComAmbienteTests(SimpleTestCase):
    def test_urls_refletem_o_ambiente(self):
        res = rodar(
            extra_env={
                "POSTGRES_USER": "outro_usuario",
                "POSTGRES_DB": "outro_banco",
                "POSTGRES_PORT": "5433",
                "REDIS_PORT": "6380",
            }
        )
        self.assertEqual(res.returncode, 0, "o script falhou; stderr: " + res.stderr)
        _, valores = como_dicionario(res.stdout)
        esperado_db = (
            f"postgres://outro_usuario:{valores['POSTGRES_PASSWORD']}@localhost:5433/outro_banco"
        )
        esperado_redis = f"redis://:{valores['REDIS_PASSWORD']}@localhost:6380/0"
        self.assertTrue(
            valores["DATABASE_URL"] == esperado_db,
            "DATABASE_URL não reflete POSTGRES_USER, POSTGRES_DB e POSTGRES_PORT",
        )
        self.assertTrue(
            valores["REDIS_URL"] == esperado_redis,
            "REDIS_URL não reflete REDIS_PORT",
        )


class SoChaveRsaTests(SimpleTestCase):
    def test_uma_linha_so_com_a_chave(self):
        """AC-05: a opção não pode trazer nada além da linha que se quer trocar, porque
        quem cola o bloco inteiro troca também as senhas e o erro aparece longe da causa."""
        res = rodar("--so-chave-rsa")
        self.assertEqual(res.returncode, 0, "o script falhou; stderr: " + res.stderr)
        self.assertEqual(len(res.stdout.splitlines()), 1)
        self.assertTrue(
            res.stdout.startswith("OIDC_RSA_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\\n"),
            "a linha não começa com OIDC_RSA_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\\n",
        )
        # O nome é conferido no início da linha: o base64 do PEM é aleatório e contém "URL" ou
        # "PASSWORD" por acaso, então substring sobre a saída inteira daria falso vermelho.
        for proibido in (
            "SECRET_KEY=",
            "POSTGRES_PASSWORD=",
            "REDIS_PASSWORD=",
            "DATABASE_URL=",
            "REDIS_URL=",
        ):
            with self.subTest(proibido=proibido):
                self.assertFalse(
                    any(linha.startswith(proibido) for linha in res.stdout.splitlines()),
                    f"a saída traz uma linha {proibido}",
                )


class ArgumentoInvalidoTests(SimpleTestCase):
    def test_sai_com_2_e_stdout_vazio(self):
        for args in (("--x",), ("--so-chave-rsa", "extra"), ("",)):
            with self.subTest(args=args):
                res = rodar(*args)
                self.assertEqual(res.returncode, 2)
                self.assertTrue(res.stdout == "", "stdout não vazio (conteúdo omitido)")
