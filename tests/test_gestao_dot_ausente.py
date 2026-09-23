"""TASK-019/T-06 — as sete rotas de gestão do `django-oauth-toolkit` (DOT) e o registro
dinâmico de cliente (DCR, Dynamic Client Registration) não existem sob `/o/`, para nenhuma
identidade — anônima, conta comum, conta `is_staff` e superusuário.

Demanda do quality-assurance (TASK-019/Fase 7). Nível integração: `management_urlpatterns` e
`dcr_urlpatterns` estão fora do `include` de `config/urls.py`, por decisão da ADR 0024
(`docs/adr/0024-montar-sob-o-so-as-listas-de-protocolo-do-django-oauth-toolkit.md`), e o que
está sob prova é a AUSÊNCIA de rota no URLConf — não uma permissão negada por view, que
devolveria 403, e não um redirecionamento para o login, que devolveria 302. Só o cliente de
teste, batendo contra a URL de verdade, revela qual das três é a resposta real.

`pk` de objetos reais nas rotas que exigem `<slug:pk>`: uma `Application` e um `AccessToken`
gravados por este módulo — um `pk` inexistente provaria só que o objeto não existe, nunca que a
ROTA não existe, e as duas causas de 404 não podem ser confundidas aqui."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from oauth2_provider.models import get_access_token_model, get_application_model

User = get_user_model()
Application = get_application_model()
AccessToken = get_access_token_model()


class RotasDeGestaoDoDotEDcrAusentesTests(TestCase):
    """Uma `subTest` por (identidade, rota): 4 identidades x 8 rotas GET, mais o POST de
    registro como conta comum."""

    @classmethod
    def setUpTestData(cls):
        cls.dono = User.objects.create_user(
            email="t06-dono@example.com", password="senha-forte-o-suficiente"
        )
        cls.aplicacao = Application.objects.create(
            name="fixture-t06",
            client_id="fixture-t06-client",
            client_type="public",
            authorization_grant_type="authorization-code",
            algorithm="RS256",
            redirect_uris="https://previo.example/callback",
            user=cls.dono,
        )
        cls.token = AccessToken.objects.create(
            user=cls.dono,
            application=cls.aplicacao,
            token="fixture-t06-access-token",
            expires=timezone.now() + timedelta(hours=1),
            scope="openid",
        )

        cls.usuario_comum = User.objects.create_user(
            email="t06-comum@example.com", password="senha-forte-o-suficiente"
        )
        cls.usuario_staff = User.objects.create_user(
            email="t06-staff@example.com",
            password="senha-forte-o-suficiente",
            is_staff=True,
        )
        cls.superusuario = User.objects.create_superuser(
            email="t06-super@example.com", password="senha-forte-o-suficiente"
        )

    def _rotas(self):
        return (
            "/o/applications/",
            "/o/applications/register/",
            f"/o/applications/{self.aplicacao.pk}/",
            f"/o/applications/{self.aplicacao.pk}/update/",
            f"/o/applications/{self.aplicacao.pk}/delete/",
            "/o/authorized_tokens/",
            f"/o/authorized_tokens/{self.token.pk}/delete/",
            "/o/register/",
        )

    def _identidades(self):
        # (rótulo, e-mail ou None para anônimo)
        return (
            ("anônimo", None),
            ("conta comum", self.usuario_comum.email),
            ("conta is_staff", self.usuario_staff.email),
            ("superusuário", self.superusuario.email),
        )

    def test_get_e_404_sem_location_para_toda_identidade_e_toda_rota(self):
        for rotulo, email in self._identidades():
            self.client.logout()
            if email is not None:
                self.client.force_login(User.objects.get(email=email))

            for rota in self._rotas():
                with self.subTest(identidade=rotulo, rota=rota):
                    resposta = self.client.get(rota)
                    self.assertEqual(resposta.status_code, 404)
                    self.assertIsNone(resposta.get("Location"))

    def test_post_de_registro_como_conta_comum_e_404_sem_gravar_application(self):
        self.client.force_login(self.usuario_comum)
        contagem_antes = Application.objects.count()

        resposta = self.client.post(
            "/o/applications/register/",
            {
                "name": "fixture-t06-tentativa-de-registro",
                "client_type": "public",
                "authorization_grant_type": "authorization-code",
                "redirect_uris": "https://spa.example/callback",
            },
        )

        self.assertEqual(resposta.status_code, 404)
        self.assertEqual(Application.objects.count(), contagem_antes)
