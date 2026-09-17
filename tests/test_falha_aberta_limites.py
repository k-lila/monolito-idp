"""T-15 — a falha aberta de `config/limites.py` quando o Redis do teto de requisição está
inalcançável: a requisição segue sem limite algum, e uma linha WARNING documenta o silêncio
(ver o comentário do `except` em `config/limites.py`, que explica a troca de disponibilidade
por limitação).

Demanda do quality-assurance (TASK-014, 3ª passagem). Nível integração: o objeto do teste é o
contrato entre três camadas de terceiro — o que o cliente `redis` levanta, o que o
`RedisCache` do Django deixa passar sem embrulhar, e o que o `except` do middleware captura.
Nenhuma delas é nossa, e só a pilha inteira em execução prova alguma coisa; um unitário teria
de fabricar a exceção, e fabricar a exceção é assumir a resposta.

SEM `patch` em `cache.add`, de propósito: a exceção tem de vir de um cliente de Redis de
verdade. Com mock, o teste passaria igual se o `except` capturasse a classe errada — foi o
critério que separa este caminho de INTESTÁVEL.

DOIS casos, e um não cobre o outro: em `redis` 8.1.0, `TimeoutError.__mro__` é
`(TimeoutError, RedisError, Exception, BaseException)` — ela NÃO descende de
`ConnectionError`. Um caso só deixaria metade do `except` sem guarda, e a metade sem guarda é
justamente a do Redis que aceita a conexão e não responde, o modo de falha que o comentário
de `config/settings.py` chama de caro.

O caminho usado para exercitar o middleware é `/accounts/login/`, com `RATE_LIMIT_POR_CAMINHO`
reduzido a essa única entrada por `override_settings` — o mesmo precedente do T-07 e do T-14:
não há razão para envolver `/o/` neste caso, e uma chave só simplifica a leitura do teto (0,
para provocar `_contagem_na_janela` na primeira requisição, já que o ponto do caso é o `except`
da falha de conexão, não a contagem em si)."""

import socket
import threading

from django.core.cache import cache
from django.test import TestCase, override_settings

from config.limites import chave_do_contador

ORIGEM_T15_CONEXAO = "10.70.0.1"
ORIGEM_T15_TIMEOUT = "10.70.0.2"


def _caches_redis_quebrado(porta, timeout=0.25):
    """As settings de `CACHES` apontando para uma porta sem Redis de verdade atrás dela, com
    timeout baixo o bastante para o caso não pendurar a suíte. `socket_connect_timeout` e
    `socket_timeout` explícitos, como em produção — só o valor muda, nunca o mecanismo."""
    return {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": f"redis://127.0.0.1:{porta}/1",
            "OPTIONS": {
                "socket_connect_timeout": timeout,
                "socket_timeout": timeout,
            },
        }
    }


class FalhaAbertaDoLimiteDeLoginTests(TestCase):
    """T-15 — os dois modos de falha do Redis do teto de requisição, e a prova de que a
    requisição segue apesar deles, com o silêncio registrado em log."""

    def tearDown(self):
        # A exceção interrompe `_contagem_na_janela` antes de qualquer `cache.add` chegar a
        # completar contra o Redis quebrado, e os dois casos abaixo nunca chegam a escrever
        # a chave no Redis real do ambiente (`CACHES` está sob `override_settings` durante a
        # única requisição de cada caso). A limpeza aqui é só disciplina do bloco — nunca
        # `cache.clear()`, que o `RedisCache` implementa como `FLUSHDB` e levaria junto a
        # cópia quente das sessões (ADR 0005).
        cache.delete(chave_do_contador("/accounts/login/", ORIGEM_T15_CONEXAO))
        cache.delete(chave_do_contador("/accounts/login/", ORIGEM_T15_TIMEOUT))

    def test_a_conexao_recusada_segue_a_requisicao_e_loga_o_silencio(self):
        """`redis.exceptions.ConnectionError` — porta reservada e fechada, sem ninguém do
        outro lado: a conexão é recusada na hora (medido: 0,027 s pelo QA)."""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        porta = s.getsockname()[1]
        s.close()

        with override_settings(
            CACHES=_caches_redis_quebrado(porta),
            RATE_LIMIT_POR_CAMINHO={"/accounts/login/": 0},
            RATE_LIMIT_JANELA_SEGUNDOS=60,
        ):
            with self.assertLogs("config.limites", level="WARNING") as captura:
                resposta = self.client.get("/accounts/login/", REMOTE_ADDR=ORIGEM_T15_CONEXAO)

        # A requisição SEGUIU: 200 de verdade, e não apenas "não é 429".
        self.assertEqual(resposta.status_code, 200)
        self._assert_uma_linha_de_throttle_unavailable(captura, ORIGEM_T15_CONEXAO)

    def test_b_servidor_mudo_segue_a_requisicao_e_loga_o_silencio(self):
        """`redis.exceptions.TimeoutError` — um socket que aceita a conexão e a segura
        aberta sem responder: o timeout ocorre na leitura do handshake, não na conexão em si
        (medido: 0,264 s pelo QA, com `socket_timeout` em 0,25 s)."""
        servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        servidor.bind(("127.0.0.1", 0))
        porta = servidor.getsockname()[1]
        servidor.listen(1)

        conexoes_aceitas = []
        parar = threading.Event()

        def aceitar_e_segurar():
            # Timeout curto no accept(), só para poder reler `parar` periodicamente; não é
            # o timeout sob teste — esse é o do cliente Redis contra a conexão já aceita,
            # que nunca recebe resposta nenhuma daqui.
            servidor.settimeout(0.5)
            while not parar.is_set():
                try:
                    conexao, _ = servidor.accept()
                    conexoes_aceitas.append(conexao)
                except socket.timeout:
                    continue
                except OSError:
                    break

        thread = threading.Thread(target=aceitar_e_segurar, daemon=True)
        thread.start()

        try:
            with override_settings(
                CACHES=_caches_redis_quebrado(porta),
                RATE_LIMIT_POR_CAMINHO={"/accounts/login/": 0},
                RATE_LIMIT_JANELA_SEGUNDOS=60,
            ):
                with self.assertLogs("config.limites", level="WARNING") as captura:
                    resposta = self.client.get(
                        "/accounts/login/", REMOTE_ADDR=ORIGEM_T15_TIMEOUT
                    )
        finally:
            # Parar a thread, fechar as conexões aceitas e o socket num `finally`: nada disto
            # pode sobreviver ao caso, sob pena de vazar um socket em LISTEN que disputaria
            # porta com o próximo caso da suíte ou com outro processo da máquina.
            parar.set()
            for conexao in conexoes_aceitas:
                conexao.close()
            servidor.close()
            thread.join(timeout=2)

        self.assertEqual(resposta.status_code, 200)
        self._assert_uma_linha_de_throttle_unavailable(captura, ORIGEM_T15_TIMEOUT)

    def _assert_uma_linha_de_throttle_unavailable(self, captura, origem):
        # `assertLogs` guarda cada `LogRecord`; as chaves de `extra={...}` do `logger.warning`
        # de produção viram atributo direto do record, não um subdicionário.
        self.assertEqual(len(captura.records), 1, captura.output)
        registro = captura.records[0]
        self.assertEqual(registro.outcome, "throttle_unavailable")
        self.assertEqual(registro.path, "/accounts/login/")
        self.assertEqual(registro.ip, origem)
