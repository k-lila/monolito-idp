"""T-01 (TASK-014/bloco B) — `config.origem.origem_da_requisicao`, a tabela inteira de
resolução. T-01 (TASK-015/Fase 7) — `config.origem.origem_e_procedencia`, o PAR inteiro,
inclusive o rótulo que a ADR (Architecture Decision Record) 0018 introduziu.

Nível unitário nas duas demandas: a função é pura, sem I/O e sem estado — `RequestFactory`
mais `override_settings` bastam para exercitar as decisões dela. Levá-la a integração pagaria
banco, sessão e cadeia de middleware para provar uma escolha de string, e diluiria o
diagnóstico: aqui, quando uma alínea falhar, o que falhou é a regra de leitura, e nada mais.

`OrigemDaRequisicaoTests` cobre a PROJEÇÃO — `origem_da_requisicao`, contrato de string do
`django-axes` — no primeiro elemento do par; `OrigemEProcedenciaTests` cobre o PAR inteiro, e
é onde o rótulo de procedência ganha a primeira asserção de toda a suíte.
"""

from django.test import RequestFactory, SimpleTestCase, override_settings

from config.origem import origem_da_requisicao, origem_e_procedencia


class OrigemDaRequisicaoTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_a_sem_requisicao_devolve_none(self):
        """`request is None` acontece quando `authenticate()` é chamado fora de uma
        requisição HTTP — por shell ou por comando de `manage.py`."""
        self.assertIsNone(origem_da_requisicao(None))

    @override_settings(BEHIND_TLS_PROXY=False)
    def test_b_sem_proxy_o_cabecalho_e_ignorado(self):
        """A guarda contra a forja: com `BEHIND_TLS_PROXY` falso, `X-Forwarded-For` é
        cabeçalho que qualquer cliente escreve, e é IGNORADO — nunca lido, mesmo presente.
        É a alínea que uma "melhoria" futura (ler o cabeçalho incondicionalmente) derrubaria
        em silêncio."""
        request = self.factory.get(
            "/qualquer",
            REMOTE_ADDR="10.0.0.5",
            HTTP_X_FORWARDED_FOR="1.2.3.4",
        )

        self.assertEqual(origem_da_requisicao(request), "10.0.0.5")

    @override_settings(BEHIND_TLS_PROXY=True, TRUSTED_PROXY_COUNT=1)
    def test_c_com_proxy_confiavel_le_o_salto_declarado(self):
        request = self.factory.get(
            "/qualquer",
            REMOTE_ADDR="172.16.0.1",
            HTTP_X_FORWARDED_FOR="203.0.113.7",
        )

        self.assertEqual(origem_da_requisicao(request), "203.0.113.7")

    @override_settings(BEHIND_TLS_PROXY=True, TRUSTED_PROXY_COUNT=1)
    def test_d_saltos_multiplos_le_o_da_direita_nunca_o_forjado_pelo_cliente(self):
        """O cliente forjou o primeiro elemento (`1.2.3.4`); o proxy anexou o real à
        direita. O valor lido tem de ser o do proxy, NUNCA o do cliente."""
        request = self.factory.get(
            "/qualquer",
            REMOTE_ADDR="172.16.0.1",
            HTTP_X_FORWARDED_FOR="1.2.3.4, 203.0.113.7",
        )

        origem = origem_da_requisicao(request)

        self.assertEqual(origem, "203.0.113.7")
        self.assertNotEqual(origem, "1.2.3.4")

    @override_settings(BEHIND_TLS_PROXY=True, TRUSTED_PROXY_COUNT=1)
    def test_e_cabecalho_ausente_cai_no_remote_addr(self):
        request = self.factory.get("/qualquer", REMOTE_ADDR="172.16.0.1")

        self.assertEqual(origem_da_requisicao(request), "172.16.0.1")

    @override_settings(BEHIND_TLS_PROXY=True, TRUSTED_PROXY_COUNT=2)
    def test_f_menos_saltos_que_proxies_declarados_cai_no_remote_addr(self):
        """Cabeçalho de um salto só, com dois proxies declarados: o valor não é confiável —
        o número de saltos não bate com o que se supõe que o cabeçalho tenha percorrido —, e
        a queda é para o endereço direto."""
        request = self.factory.get(
            "/qualquer",
            REMOTE_ADDR="172.16.0.1",
            HTTP_X_FORWARDED_FOR="203.0.113.7",
        )

        self.assertEqual(origem_da_requisicao(request), "172.16.0.1")


class OrigemEProcedenciaTests(SimpleTestCase):
    """T-01 (TASK-015/Fase 7). O PAR inteiro — endereço e procedência — nos quatro
    desfechos de `origem_e_procedencia` (ADR 0018).

    Cada caso assere a tupla inteira, nunca só o endereço: uma asserção sobre o primeiro
    elemento repetiria `OrigemDaRequisicaoTests` sem provar nada sobre o rótulo, que é
    exatamente o que esta classe existe para cobrir.
    """

    def setUp(self):
        self.factory = RequestFactory()

    def test_a_sem_requisicao_devolve_o_par_none_none(self):
        """`request is None` fora de uma requisição HTTP: sem endereço não há procedência a
        declarar, e o par inteiro é `(None, None)` — não só o endereço."""
        self.assertEqual(origem_e_procedencia(None), (None, None))

    @override_settings(BEHIND_TLS_PROXY=False)
    def test_b_sem_proxy_devolve_remote_addr_com_procedencia_remote_addr(self):
        """`X-Forwarded-For` presente e IGNORADO — a mesma guarda de
        `OrigemDaRequisicaoTests.test_b` —, agora com o rótulo `remote_addr` asserido junto
        do endereço."""
        request = self.factory.get(
            "/qualquer",
            REMOTE_ADDR="10.0.0.5",
            HTTP_X_FORWARDED_FOR="1.2.3.4",
        )

        self.assertEqual(origem_e_procedencia(request), ("10.0.0.5", "remote_addr"))

    @override_settings(BEHIND_TLS_PROXY=True, TRUSTED_PROXY_COUNT=1)
    def test_c_com_proxy_e_saltos_suficientes_devolve_o_salto_da_direita_com_procedencia_forwarded(
        self,
    ):
        request = self.factory.get(
            "/qualquer",
            REMOTE_ADDR="172.16.0.1",
            HTTP_X_FORWARDED_FOR="1.2.3.4, 203.0.113.7",
        )

        self.assertEqual(origem_e_procedencia(request), ("203.0.113.7", "forwarded"))

    @override_settings(BEHIND_TLS_PROXY=True, TRUSTED_PROXY_COUNT=1)
    def test_d_proxy_declarado_e_cabecalho_ausente_cai_no_remote_addr_fallback(self):
        request = self.factory.get("/qualquer", REMOTE_ADDR="172.16.0.1")

        self.assertEqual(
            origem_e_procedencia(request), ("172.16.0.1", "remote_addr_fallback")
        )

    @override_settings(BEHIND_TLS_PROXY=True, TRUSTED_PROXY_COUNT=2)
    def test_e_saltos_insuficientes_cai_no_remote_addr_fallback_mesmo_endereco_procedencia_oposta(
        self,
    ):
        """O ponto todo desta classe. `TRUSTED_PROXY_COUNT=2` com um salto só no cabeçalho
        devolve o MESMO endereço (`172.16.0.1`) que `BEHIND_TLS_PROXY=False` devolveria para
        a mesma requisição — mas com procedência OPOSTA: `remote_addr_fallback` aqui é o
        proxy fazendo-se passar por cliente porque o cabeçalho não trouxe saltos
        suficientes; `remote_addr` em `test_b` é o endereço direto do cliente, sem proxy
        nenhum no meio. Só a procedência distingue as duas leituras — se a asserção
        cobrisse só o endereço, os dois casos seriam indistinguíveis."""
        request = self.factory.get(
            "/qualquer",
            REMOTE_ADDR="172.16.0.1",
            HTTP_X_FORWARDED_FOR="203.0.113.7",
        )

        par_com_proxy_e_fallback = origem_e_procedencia(request)
        self.assertEqual(
            par_com_proxy_e_fallback, ("172.16.0.1", "remote_addr_fallback")
        )

        with override_settings(BEHIND_TLS_PROXY=False):
            par_sem_proxy = origem_e_procedencia(request)
        self.assertEqual(par_sem_proxy, ("172.16.0.1", "remote_addr"))

        self.assertEqual(par_com_proxy_e_fallback[0], par_sem_proxy[0])
        self.assertNotEqual(par_com_proxy_e_fallback[1], par_sem_proxy[1])
