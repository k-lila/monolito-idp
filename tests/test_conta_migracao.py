"""TASK-028/T-14 e T-15 — a migração do e-mail e do `sub`, de `accounts.0001_initial` até a folha
atual do grafo, sob Postgres.

Demanda do quality-assurance (TASK-028). Nível integração: o que está sob prova é a transação
e o DDL (Data Definition Language) do banco real, e nem SQLite nem mock os reproduzem.

A folha é derivada do grafo, e não escrita: uma migração nova de `accounts` não quebra este
módulo. O que se conserva é a travessia da 0004, irreversível, no caminho até ela.

A 0002 só mexe em dados e vem antes do esquema da 0003 de propósito: a colisão de caixa para
a migração antes de qualquer escrita, sem estado parcial. O caso fica vermelho se a verificação
de colisão for movida para depois do `update`. A separação em 0002 e 0003 não é provada
aqui: sob Postgres o DDL da migração atômica também é desfeito, e fundi-las daria o mesmo
resultado.

Schema isolado, e não `migrate` para trás: a 0004 é irreversível (o UUID sorteado por conta não
se refaz, e a trilha ficaria órfã), e por isso não há caminho de volta ao estado anterior à
0002 pelo grafo. Cada caso cria um schema Postgres próprio, aponta o `search_path` da conexão
para ele e migra do zero ali: contenttypes, auth e accounts 0001, com o `django_migrations` do
próprio schema. O `public`, onde vive o banco de teste da suíte, não é tocado. O `finally`
devolve o `search_path` e apaga o schema; nada sobra num nem noutro.

`TransactionTestCase`, porque a migração faz DDL e o `TestCase` a envolveria numa transação
que ela não pode ter.
"""

import uuid
from contextlib import contextmanager

from django.core.management import call_command
from django.db import connection
from django.db.migrations.exceptions import IrreversibleError
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.loader import MigrationLoader
from django.test import TransactionTestCase

ANTES = [("accounts", "0001_initial")]
_FOLHAS = [
    no for no in MigrationLoader(None, ignore_no_migrations=True).graph.leaf_nodes()
    if no[0] == "accounts"
]
assert len(_FOLHAS) == 1, _FOLHAS
DEPOIS = _FOLHAS
ULTIMA = _FOLHAS[0][1]


@contextmanager
def schema_isolado():
    """Um schema novo no `search_path` da conexão, apagado na saída com o `search_path` devolvido."""
    nome = f"t028_{uuid.uuid4().hex[:12]}"
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE SCHEMA {nome}")
            cursor.execute(f"SET search_path TO {nome}")
        yield nome
    finally:
        with connection.cursor() as cursor:
            cursor.execute("SET search_path TO DEFAULT")
            cursor.execute(f"DROP SCHEMA IF EXISTS {nome} CASCADE")


def _aplicadas():
    return sorted(
        nome
        for (app, nome) in MigrationExecutor(connection).recorder.applied_migrations()
        if app == "accounts"
    )


def _executor():
    # Um executor novo a cada passo: o grafo e o estado aplicado são lidos na construção.
    return MigrationExecutor(connection)


def _nome_da_0004():
    return next(
        nome
        for app, nome in _executor().loader.graph.forwards_plan(DEPOIS[0])
        if app == "accounts" and nome.startswith("0004_")
    )


def _restricoes():
    """As restrições e os índices de `accounts_user` no schema da conexão, por nome."""
    with connection.cursor() as cursor:
        return connection.introspection.get_constraints(cursor, "accounts_user")


def _sub_e_unico():
    return any(
        info["unique"] and info["columns"] == ["sub"] for info in _restricoes().values()
    )


def _tem_unicidade_do_email_em_minusculas():
    # O nome vem da própria restrição do modelo, e não de um literal repetido aqui.
    nome = next(
        c.name for c in _modelo_user()._meta.constraints
        if c.name.startswith("accounts_user_email")
    )
    return nome in _restricoes()


def _modelo_user():
    from accounts.models import User

    return User


def _colunas():
    with connection.cursor() as cursor:
        descricao = connection.introspection.get_table_description(cursor, "accounts_user")
    return [coluna.name for coluna in descricao]


class MigracaoDoEmailEDoSubTests(TransactionTestCase):
    def test_colisao_de_caixa_para_sem_estado_parcial_e_resolvida_migra_tudo(self):
        with schema_isolado():
            _executor().migrate(ANTES)
            antes = _executor().loader.project_state(ANTES).apps.get_model("accounts", "User")
            dup_maiuscula = antes.objects.create(email="Dup@x.com", password="!")
            dup_minuscula = antes.objects.create(email="dup@x.com", password="!")
            outro = antes.objects.create(email="Outro@X.com", password="!")

            with self.assertRaises(RuntimeError) as contexto:
                _executor().migrate(DEPOIS)

            # Os dois `id` e nenhum e-mail: a mensagem vai ao log do entrypoint.
            mensagem = str(contexto.exception)
            self.assertIn(str(dup_maiuscula.pk), mensagem)
            self.assertIn(str(dup_minuscula.pk), mensagem)
            self.assertNotIn(str(outro.pk), mensagem)
            self.assertNotIn("dup@", mensagem.lower())
            self.assertNotIn("outro@", mensagem.lower())

            # Nenhuma escrita antes da falha, e o esquema da 0003 não chegou a existir.
            self.assertEqual(
                sorted(antes.objects.values_list("email", flat=True)),
                ["Dup@x.com", "Outro@X.com", "dup@x.com"],
            )
            self.assertNotIn("sub", _colunas())

            antes.objects.filter(pk=dup_maiuscula.pk).delete()
            _executor().migrate(DEPOIS)

            depois = _executor().loader.project_state(DEPOIS).apps.get_model("accounts", "User")
            linhas = list(
                depois.objects.values(
                    "pk", "email", "sub", "updated_at", "date_joined", "email_verified"
                )
            )
            self.assertEqual(
                sorted(linha["email"] for linha in linhas), ["dup@x.com", "outro@x.com"]
            )
            self.assertEqual(
                sorted(linha["pk"] for linha in linhas),
                sorted([dup_minuscula.pk, outro.pk]),
            )
            subs = [linha["sub"] for linha in linhas]
            self.assertNotIn(None, subs)
            self.assertEqual(len(set(subs)), len(subs))
            for linha in linhas:
                self.assertEqual(linha["updated_at"], linha["date_joined"])
                self.assertIs(linha["email_verified"], False)

        self._confere_que_nada_sobrou()

    def test_a_0004_e_irreversivel_e_um_migrate_seguinte_volta_a_folha(self):
        """T-15 — vermelho se alguém devolver `reverse_code` à 0004. A folha é a do grafo, e o
        caminho até ela atravessa a 0004: sem isso o caso provaria irreversibilidade de nada."""
        with schema_isolado():
            _executor().migrate(ANTES)
            plano = _executor().loader.graph.forwards_plan(DEPOIS[0])
            self.assertTrue(
                any(app == "accounts" and nome.startswith("0004_") for app, nome in plano),
                plano,
            )
            _executor().migrate(DEPOIS)
            self.assertEqual(_aplicadas()[-1], ULTIMA)

            with self.assertRaises(IrreversibleError) as contexto:
                call_command("migrate", "accounts", "0003", verbosity=0, interactive=False)
            self.assertIn("0004", str(contexto.exception))

            # O estado intermediário que `docs/receita.md` descreve: as migrações posteriores à
            # 0004 foram desfeitas (cada uma atômica), a 0004 ficou, e com ela caíram a
            # unicidade do `sub` e o índice sobre `Lower(email)`, que a 0005 criou.
            posteriores = {
                nome
                for app, nome in _executor().loader.graph.forwards_plan(DEPOIS[0])
                if app == "accounts" and nome > _nome_da_0004()
            }
            self.assertIn(ULTIMA, posteriores)
            aplicadas = set(_aplicadas())
            self.assertIn(_nome_da_0004(), aplicadas)
            self.assertEqual(aplicadas & posteriores, set())
            self.assertFalse(_sub_e_unico())
            self.assertFalse(_tem_unicidade_do_email_em_minusculas())

            call_command("migrate", "accounts", ULTIMA, verbosity=0, interactive=False)
            self.assertEqual(_aplicadas()[-1], ULTIMA)
            self.assertTrue(posteriores <= set(_aplicadas()))
            self.assertTrue(_sub_e_unico())
            self.assertTrue(_tem_unicidade_do_email_em_minusculas())

        self._confere_que_nada_sobrou()

    def _confere_que_nada_sobrou(self):
        with connection.cursor() as cursor:
            cursor.execute("SHOW search_path")
            self.assertNotIn("t028_", cursor.fetchone()[0])
            cursor.execute(
                "SELECT count(*) FROM information_schema.schemata WHERE schema_name LIKE 't028_%'"
            )
            self.assertEqual(cursor.fetchone()[0], 0)
        # O `public` segue com as folhas do grafo aplicadas e sem as contas do caso.
        self.assertEqual(_aplicadas()[-1], ULTIMA)
        self.assertNotIn("dup@x.com", self._emails_do_public())

    def _emails_do_public(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT email FROM public.accounts_user")
            return [linha[0] for linha in cursor.fetchall()]
