"""TASK-028/T-56 — os sinais da trilha saem fora de bloco atômico, e o rollback não deixa rastro.

Demanda do quality-assurance. Nível integração, em `TransactionTestCase`: o `TestCase` envolve
cada caso numa transação, e `connection.in_atomic_block` seria sempre verdadeiro, de modo que a
prova que se quer, "o sinal sai depois de a gravação estar confirmada", não se faria.

Um receptor em cada sinal de `accounts/sinais.py` e em `tokens_revogados` guarda o valor de
`in_atomic_block` no instante da emissão. O percurso passa por cadastro, pedido de recuperação,
redefinição, troca de senha, troca de e-mail, desativação e apagamento, e passa também pelo link
de confirmação, pelo PATCH do perfil e pelo aceite dos termos da API (T-67). Toda emissão tem de
ser `False`. A trilha é arquivo e não volta com o rollback: um sinal emitido dentro do bloco
registraria o que o banco desfez (ADR 0031).

Rollback: com `esquecer_tentativas` trocado por um que levanta, a troca de e-mail dá erro, o
endereço continua o antigo, e não saem a linha `email_trocado` nem o e-mail, porque o envio parte
de `on_commit` e a emissão do sinal vem depois do bloco.

Vermelho se qualquer emissão passar a ocorrer dentro de um `atomic()`, ou se o envio ou o sinal
da troca de e-mail saírem antes do commit.
"""

from unittest import mock

from django.conf import settings
from django.core import mail
from django.db import connection
from django.test import Client, TransactionTestCase, override_settings

from accounts import confirmacao, sinais
from accounts.revogacao import tokens_revogados
from tests.api_conta_helpers import bearer, criar_token
from tests.logout_helpers import (
    criar_application,
    emitir_tokens,
    linhas_da_trilha_desde,
    tamanho_da_trilha,
)
from tests.paginas_helpers import (
    dados_de_cadastro,
    NOVA,
    SENHA,
    User,
    caminho_do_link,
    eventos,
    link_do_email,
)

SINAIS = {
    "conta_criada": sinais.conta_criada,
    "email_confirmado": sinais.email_confirmado,
    "conta_editada": sinais.conta_editada,
    "termos_aceitos": sinais.termos_aceitos,
    "email_trocado": sinais.email_trocado,
    "senha_trocada": sinais.senha_trocada,
    "recuperacao_pedida": sinais.recuperacao_pedida,
    "senha_redefinida": sinais.senha_redefinida,
    "conta_desativada": sinais.conta_desativada,
    "conta_apagada": sinais.conta_apagada,
    "tokens_revogados": tokens_revogados,
}


class _Base(TransactionTestCase):
    def setUp(self):
        self.dono = User.objects.create_superuser("dono@ex.com", SENHA)
        self.app = criar_application(self.dono, "SPA")
        self.addCleanup(mail.outbox.clear)

    def conta(self, email):
        """Uma conta com sessão e tokens na Application. Devolve `(conta, client)`."""
        conta = User.objects.create_user(email, SENHA)
        client, _ = emitir_tokens(conta, self.app)
        return conta, client


class SinaisForaDoBlocoAtomicoTests(_Base):
    def setUp(self):
        super().setUp()
        self.emissoes = []
        self.receptores = []
        for nome, sinal in SINAIS.items():
            def receptor(sender, _nome=nome, **kwargs):
                self.emissoes.append((_nome, connection.in_atomic_block))

            self.receptores.append(receptor)
            sinal.connect(receptor, weak=False, dispatch_uid=f"t56.{nome}")
            self.addCleanup(sinal.disconnect, dispatch_uid=f"t56.{nome}")

    def test_toda_emissao_do_percurso_sai_fora_de_bloco_atomico(self):
        # Cadastro.
        Client().post("/accounts/registrar/", dados_de_cadastro("nova@ex.com", next=None))

        # Pedido de recuperação e redefinição pelo link do e-mail.
        redefine, _ = self.conta("redefine@ex.com")
        mail.outbox.clear()
        navegador = Client()
        navegador.post("/accounts/password_reset/", {"email": "redefine@ex.com"})
        (mensagem,) = mail.outbox
        passo1 = navegador.get(caminho_do_link(link_do_email(mensagem)))
        navegador.post(passo1["Location"], {"new_password1": NOVA, "new_password2": NOVA})

        # Troca de senha, troca de e-mail, desativação e apagamento, cada uma na sua conta.
        _, client = self.conta("senha@ex.com")
        client.post(
            "/accounts/password_change/",
            {"old_password": SENHA, "new_password1": NOVA, "new_password2": NOVA},
        )
        _, client = self.conta("email@ex.com")
        client.post("/accounts/email/", {"novo_email": "email2@ex.com", "senha": SENHA})
        _, client = self.conta("desativa@ex.com")
        client.post("/accounts/excluir/", {"modo": "desativar", "confirmo": "on", "senha": SENHA})
        _, client = self.conta("apaga@ex.com")
        client.post("/accounts/excluir/", {"modo": "apagar", "confirmo": "on", "senha": SENHA})

        # Link de confirmação, PATCH do perfil e aceite dos termos, pela API com Bearer.
        conta, _ = self.conta("api@ex.com")
        token = criar_token(conta, self.app)
        with override_settings(SPA_CLIENT_ID=self.app.client_id):
            Client().get("/api/conta/confirmar/", {"t": confirmacao.gerar(conta)})
            Client().patch(
                "/api/conta/",
                '{"nickname": "novo"}',
                content_type="application/json",
                **bearer(token),
            )
            Client().post(
                "/api/conta/termos/",
                {"versao": settings.TERMOS_VERSAO_VIGENTE},
                content_type="application/json",
                **bearer(token),
            )

        emitidos = {nome for nome, _ in self.emissoes}
        self.assertEqual(
            emitidos,
            {
                "conta_criada",
                "email_confirmado",
                "conta_editada",
                "termos_aceitos",
                "recuperacao_pedida",
                "senha_redefinida",
                "senha_trocada",
                "email_trocado",
                "conta_desativada",
                "conta_apagada",
                "tokens_revogados",
            },
        )
        dentro = [nome for nome, atomico in self.emissoes if atomico]
        self.assertEqual(dentro, [], self.emissoes)


class RollbackDaTrocaDeEmailTests(_Base):
    def test_falha_no_bloco_desfaz_o_endereco_e_nao_deixa_linha_nem_e_mail(self):
        conta, client = self.conta("troca@ex.com")
        mail.outbox.clear()
        antes = tamanho_da_trilha()

        with mock.patch(
            "accounts.paginas.esquecer_tentativas", side_effect=RuntimeError("falhou")
        ):
            with self.assertRaises(RuntimeError):
                client.post("/accounts/email/", {"novo_email": "novo@ex.com", "senha": SENHA})

        self.assertEqual(User.objects.get(pk=conta.pk).email, "troca@ex.com")
        self.assertNotIn("email_trocado", eventos(linhas_da_trilha_desde(antes)))
        self.assertEqual(mail.outbox, [])
