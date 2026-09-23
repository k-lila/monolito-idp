"""O teto de requisições de `/o/token/`, de `/o/authorize/`, de `/o/device-authorization/` e de
`/accounts/login/`.

Mecanismo, e nada além dele: conta requisições por origem e por caminho numa janela fixa e
recusa o que passa do teto. Não conhece pessoa nem conta. Na tela de login este teto convive
com o `django-axes`, e a divisão é clara: a semântica de segurança — quem está bloqueado, por
quanto tempo, por conta ou por origem — é toda do axes, que age no caminho de
`authenticate()` e não passa por aqui; o que este módulo limita ali é só o CUSTO de cada
tentativa. As escolhas, os números e o que elas custam estão na ADR (Architecture Decision
Record) `docs/adr/0016-limitar-a-taxa-na-superficie-de-autenticacao.md`; o teto de
`/o/device-authorization/` veio depois, sem ADR, e a razão dele está ao lado do número, em
`config/settings.py`.

A origem vem de `config/origem.py`, que é a única leitura de origem do sistema (ADR 0015):
o valor contado aqui e o valor gravado no campo `ip` da trilha de auditoria são o mesmo.
"""

import logging

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
# Renomeadas no import de propósito: `redis.exceptions.ConnectionError` e
# `redis.exceptions.TimeoutError` têm o nome de duas exceções embutidas do Python e NÃO
# descendem delas. Importadas com o nome original, sombreariam as embutidas neste módulo, e um
# `except ConnectionError` futuro pegaria uma coisa acreditando pegar outra.
from redis.exceptions import ConnectionError as ErroDeConexaoRedis
from redis.exceptions import TimeoutError as TempoEsgotadoRedis

from config.origem import origem_da_requisicao

logger = logging.getLogger(__name__)


def chave_do_contador(caminho, origem):
    """A chave em cache do contador de um caminho e uma origem.

    Uma chave por caminho e por origem: os tetos dos quatro caminhos limitados são separados, e
    o excesso de um não recusa os outros.

    Pública de propósito, e não `_privada`: é por ela que a suíte apaga o contador que ela
    mesma encheu, sem `cache.clear()` — que o `RedisCache` implementa como `FLUSHDB` e
    levaria junto a cópia quente das sessões (ADR 0005). É a função de produção, não um
    atalho de teste.
    """
    return f"throttle:{caminho}:{origem}"


def _contagem_na_janela(chave, janela):
    """Quantas requisições esta chave já somou na janela em curso, contando esta.

    Janela fixa, montada sobre duas operações do RedisCache do Django: `add` é
    `SET ... EX ... NX` (cria com prazo, e não sobrescreve a janela em curso) e `incr` é o
    `INCR` nativo, que preserva o prazo — verificado em
    `django/core/cache/backends/redis.py:87-96` e `:133-137`. O `RedisSerializer` não
    serializa inteiro (`:16-22`, "For better incr() and decr() atomicity"); sem essa
    propriedade o `INCR` falharia sobre um valor serializado.

    Levanta o que o cliente de Redis levantar: quem decide o que fazer com cache indisponível
    é quem chama.
    """
    if cache.add(chave, 1, timeout=janela):
        return 1
    try:
        return cache.incr(chave)
    except ValueError:
        # A chave pode expirar entre o `add` e o `incr`, e o `incr` do RedisCache levanta
        # ValueError sobre chave inexistente. É janela real de microssegundos, não cenário
        # impossível: sem esta captura, o final de cada janela produziria um 500 esporádico.
        # A janela recomeça.
        cache.add(chave, 1, timeout=janela)
        return 1


class LimiteDeTaxaMiddleware:
    """Recusa com 429 o que passa do teto declarado em `RATE_LIMIT_POR_CAMINHO`.

    As duas settings são lidas a cada requisição, e nunca no import: é o que faz
    `override_settings` valer na suíte. Caminho ausente do dicionário é o caminho de toda
    requisição fora dos quatro limitados, de modo que `RATE_LIMIT_POR_CAMINHO={}` desliga o
    limitador pela mesma trilha que já se percorre, sem ramo especial.

    A posição dele no `MIDDLEWARE` é fixada em `config/settings.py`, com as razões.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        teto = settings.RATE_LIMIT_POR_CAMINHO.get(request.path)
        if teto is None:
            return self.get_response(request)

        janela = settings.RATE_LIMIT_JANELA_SEGUNDOS
        origem = origem_da_requisicao(request)
        chave = chave_do_contador(request.path, origem)

        try:
            contagem = _contagem_na_janela(chave, janela)
        except (ErroDeConexaoRedis, TempoEsgotadoRedis):
            # FALHA ABERTA, e é escolha: com o Redis inalcançável a requisição segue sem
            # teto nenhum enquanto durar a queda. O que se troca é disponibilidade por
            # limitação — e a troca só existe porque o preço da outra opção é alto e novo:
            # até este limitador existir, `/o/token/` não tocava o Redis (é autenticado por
            # credencial de cliente e nunca lê `request.session`, de modo que o
            # `SessionMiddleware` com `cached_db` não chegava a ler nada), e deixar a exceção
            # subir transformaria toda queda de cache em 500 num endpoint que antes
            # atravessava a queda inteiro.
            #
            # As duas exceções do cliente de Redis, e nunca `Exception`: o `RedisCache` do
            # Django não embrulha erro nenhum (`django/core/cache/backends/redis.py` só
            # captura `ValueError`, na desserialização), de modo que o que chega aqui é o que
            # o `redis` levanta — `ConnectionError` quando a conexão é recusada e
            # `TimeoutError` quando o servidor aceita e não responde. As duas descendem de
            # `RedisError`, e capturar o ancestral levaria junto `ResponseError`, que é
            # comando errado, isto é, defeito nosso — e defeito nosso não merece silêncio.
            logger.warning(
                "limitador inativo: cache indisponível",
                extra={
                    "path": request.path,
                    "ip": origem,
                    "outcome": "throttle_unavailable",
                },
            )
            return self.get_response(request)

        if contagem > teto:
            logger.warning(
                "requisição recusada por excesso",
                extra={
                    # `path`, e nunca `route`: este middleware roda antes da resolução da
                    # URL, e `request.resolver_match` ainda é None aqui — `route` sairia "-"
                    # em toda linha e colidiria com a semântica que a linha de acesso já
                    # fixou.
                    "path": request.path,
                    "ip": origem,
                    "outcome": "throttled",
                },
            )
            resposta = JsonResponse(
                {
                    "error": "temporarily_unavailable",
                    # Sem acento, e a razão é do protocolo: a RFC 6749 §5.2 restringe o
                    # `error_description` a um conjunto de caracteres que não inclui os
                    # acentuados, e em `/o/token/` quem consome este corpo é a relying party.
                    # O mesmo corpo de máquina chega a quem visita `/o/authorize/` e
                    # `/accounts/login/` pelo navegador — está registrado como consequência
                    # negativa na ADR 0016.
                    "error_description": "Limite de taxa excedido. Tente de novo em instantes.",
                },
                status=429,
            )
            # A janela inteira, e não o tempo que resta: o RedisCache do Django não expõe o
            # prazo restante de uma chave. É limite superior — quem esperar por ele espera
            # demais, e nunca de menos.
            resposta["Retry-After"] = str(janela)
            return resposta

        return self.get_response(request)
