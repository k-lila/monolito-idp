"""T-01 (TASK-014/bloco B) — `config.origem.origem_da_requisicao`, a tabela inteira de
resolução. T-01 (TASK-015/Fase 7) — `config.origem.origem_e_procedencia`, o PAR inteiro,
inclusive o rótulo que a ADR (Architecture Decision Record) 0018 introduziu. T-19
(TASK-015/Fase 7b) — `config.origem.origem_completa` e `_alcance_do_endereco`, o campo
`ip_edge` que a ADR 0020 acrescentou à tripla.

Nível unitário nas três demandas: a função é pura, sem I/O e sem estado — `RequestFactory`
mais `override_settings` bastam para exercitar as decisões dela. Levá-la a integração pagaria
banco, sessão e cadeia de middleware para provar uma escolha de string, e diluiria o
diagnóstico: aqui, quando uma alínea falhar, o que falhou é a regra de leitura, e nada mais.
A exceção é `_gateway_padrao`, que lê `/proc/net/route` — deixa de ser pura, e é por isso que
`OrigemCompletaTests` substitui o mundo por um arquivo temporário, no lugar de ler a rota de
verdade da máquina que roda a suíte.

`OrigemDaRequisicaoTests` cobre a PROJEÇÃO — `origem_da_requisicao`, contrato de string do
`django-axes` — no primeiro elemento do par; `OrigemEProcedenciaTests` cobre o PAR inteiro, e
é onde o rótulo de procedência ganha a primeira asserção de toda a suíte; `OrigemCompletaTests`
cobre a TRIPLA, e é onde o alcance do endereço — gateway, peer ou unknown — ganha a primeira
asserção de toda a suíte.
"""

import os
import tempfile
from ipaddress import IPv4Address
from unittest import mock

from django.test import RequestFactory, SimpleTestCase, override_settings

from config import origem as origem_modulo
from config.origem import (
    _alcance_do_endereco,
    origem_completa,
    origem_da_requisicao,
    origem_e_procedencia,
)


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


def _hex_do_gateway(endereco):
    """O campo Gateway tal como `/proc/net/route` o publica: hexadecimal little-endian.

    Calculado a partir de `IPv4Address`, e não escrito de cabeça — é o próprio valor que
    `_gateway_padrao` desfaz com `int.from_bytes(bytes.fromhex(campo), "little")`."""
    return int(IPv4Address(endereco)).to_bytes(4, "little").hex()


# Cabeçalho de uma linha só, no formato de `/proc/net/route`: `_gateway_padrao` o descarta com
# `next(tabela)` sem olhar o conteúdo, e por isso ele não precisa reproduzir os nomes de coluna
# de verdade.
_CABECALHO_DA_TABELA = "Iface\tDestination\tGateway\tFlags\tRefCnt\tUse\tMetric\tMask\tMTU\n"


def _tabela_com_rota_default(gateway):
    """Uma tabela de rotas com uma única rota default, apontando para `gateway`."""
    return (
        _CABECALHO_DA_TABELA
        + f"eth0\t00000000\t{_hex_do_gateway(gateway)}\t0003\t0\t0\t0\t00000000\t0\n"
    )


# Uma linha de rota não-default (destino diferente de `00000000`) só, sem nenhuma linha
# default: reproduz o caso real de uma tabela que existe e se lê, mas não tem gateway a
# comparar.
_TABELA_SEM_ROTA_DEFAULT = (
    _CABECALHO_DA_TABELA
    + "eth0\tAC120000\t00000000\t0001\t0\t0\t0\tFFFFFF00\t0\n"
)


class OrigemCompletaTests(SimpleTestCase):
    """T-19 (TASK-015/Fase 7b). `origem_completa` e `_alcance_do_endereco` — o campo
    `ip_edge` que a ADR 0020 acrescentou à trilha, e a propriedade de composição que a
    justifica: os dois primeiros elementos da tripla nunca divergem do par de
    `origem_e_procedencia` para a mesma requisição, porque são o mesmo cálculo.

    O mundo aqui não é a rota de verdade da máquina que roda a suíte — variaria por ambiente
    e por execução, e o teste passaria a medir o host, não a regra —, e sim uma tabela escrita
    por este arquivo, no formato de `/proc/net/route`, com `config.origem._TABELA_DE_ROTAS`
    apontada para ela via `mock.patch.object`. Os casos sobre o próprio alcance (tabela sem
    rota default, tabela inexistente, endereço IPv6) chamam `_alcance_do_endereco` direto: a
    pergunta ali é só sobre a leitura da tabela, e montar uma requisição para isso não
    acrescentaria prova nenhuma, só ritual.
    """

    def setUp(self):
        self.factory = RequestFactory()

    def _apontar_tabela_para(self, conteudo):
        """Escreve `conteudo` num arquivo temporário e aponta `_TABELA_DE_ROTAS` para ele,
        os dois desfeitos ao fim do teste corrente — nunca ao fim da classe, para que um
        teste não veja a tabela deixada por outro."""
        arquivo = tempfile.NamedTemporaryFile(
            mode="w", suffix=".route", delete=False, encoding="ascii"
        )
        arquivo.write(conteudo)
        arquivo.close()
        self.addCleanup(os.unlink, arquivo.name)
        patcher = mock.patch.object(origem_modulo, "_TABELA_DE_ROTAS", arquivo.name)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_a_sem_requisicao_devolve_a_tripla_none(self):
        """`request is None`: sem endereço não há alcance a calcular, e a tripla inteira é
        `(None, None, None)` — não só o endereço e a procedência."""
        self.assertEqual(origem_completa(None), (None, None, None))

    def test_b_endereco_igual_ao_gateway_tem_alcance_gateway(self):
        gateway = "172.18.0.1"
        self._apontar_tabela_para(_tabela_com_rota_default(gateway))
        request = self.factory.get("/qualquer", REMOTE_ADDR=gateway)

        self.assertEqual(origem_completa(request), (gateway, "remote_addr", "gateway"))

    def test_c_endereco_diferente_do_gateway_tem_alcance_peer(self):
        self._apontar_tabela_para(_tabela_com_rota_default("172.18.0.1"))
        request = self.factory.get("/qualquer", REMOTE_ADDR="172.18.0.5")

        self.assertEqual(
            origem_completa(request), ("172.18.0.5", "remote_addr", "peer")
        )

    def test_d_tabela_sem_rota_default_tem_alcance_unknown(self):
        self._apontar_tabela_para(_TABELA_SEM_ROTA_DEFAULT)

        self.assertEqual(_alcance_do_endereco("172.18.0.5"), "unknown")

    def test_e_tabela_inexistente_tem_alcance_unknown_sem_excecao(self):
        """O preço de um `/proc` ausente é `unknown`, nunca uma exceção que subiria até o
        receptor de sinal e apagaria a linha inteira da trilha (docstring de
        `_gateway_padrao`)."""
        patcher = mock.patch.object(
            origem_modulo, "_TABELA_DE_ROTAS", "/caminho/que/nao/existe"
        )
        patcher.start()
        self.addCleanup(patcher.stop)

        self.assertEqual(_alcance_do_endereco("172.18.0.5"), "unknown")

    def test_f_endereco_ipv6_tem_alcance_unknown_mesmo_com_gateway_legivel(self):
        """A rota lida é a IPv4; comparar famílias diferentes afirmaria "não é o gateway"
        sem ter olhado o gateway daquela família — daí `unknown`, e não `peer`, mesmo com
        uma rota default legível na tabela."""
        self._apontar_tabela_para(_tabela_com_rota_default("172.18.0.1"))

        self.assertEqual(_alcance_do_endereco("2001:db8::1"), "unknown")

    def test_g_os_dois_primeiros_elementos_da_tripla_batem_com_origem_e_procedencia(self):
        """A propriedade de composição que a ADR 0020 compra: para a MESMA requisição, os
        dois primeiros elementos de `origem_completa` nunca divergem do par que
        `origem_e_procedencia` devolveria, nos dois ramos de `BEHIND_TLS_PROXY`. Os três
        valores nunca divergem porque não há aqui uma segunda leitura de `REMOTE_ADDR` ou de
        cabeçalho — é um cálculo só, projetado duas vezes."""
        self._apontar_tabela_para(_TABELA_SEM_ROTA_DEFAULT)

        with override_settings(BEHIND_TLS_PROXY=False):
            request = self.factory.get("/qualquer", REMOTE_ADDR="172.18.0.5")
            par = origem_e_procedencia(request)
            tripla = origem_completa(request)
        self.assertEqual(tripla[:2], par)

        with override_settings(BEHIND_TLS_PROXY=True, TRUSTED_PROXY_COUNT=1):
            request = self.factory.get(
                "/qualquer",
                REMOTE_ADDR="172.16.0.1",
                HTTP_X_FORWARDED_FOR="203.0.113.7",
            )
            par = origem_e_procedencia(request)
            tripla = origem_completa(request)
        self.assertEqual(tripla[:2], par)
