"""Como uma linha de log é escrita, e como duas linhas se ligam.

Decide três coisas: o formato do registro — um objeto JSON por linha —, o identificador
que correlaciona as linhas de uma mesma requisição e a linha de acesso. Não afirma nada
sobre identidade: quem autenticou, de que origem e com que desfecho é da trilha de
auditoria, em `accounts/auditoria.py`. Nenhum dos dois módulos importa o outro.

O esquema dos campos é contrato de leitura, e a razão de cada escolha está na ADR
(Architecture Decision Record)
`docs/adr/0012-emitir-o-log-operacional-em-json-com-identificador-de-requisicao.md`.
"""

import json
import logging
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone

from django.conf import settings

# O identificador da requisição em curso. O default "-" significa uma coisa só: processo
# que ainda não atendeu requisição nenhuma — arranque, `migrate`, `collectstatic`, comando
# de `manage.py`. Depois da primeira requisição o valor nunca volta a ser "-" (ADR 0014).
_request_id = ContextVar("request_id", default="-")

_logger_acesso = logging.getLogger("access")

# Os atributos que o próprio `logging` põe em todo LogRecord, mais os dois que
# Formatter.format grava nele — `message` e `asctime`. O que sobra da diferença veio de um
# `extra=` e entra no objeto.
#
# `request` está na lista, e a exclusão não é cosmética:
# `django.core.handlers.exception.log_response` anexa
# `extra={"status_code": ..., "request": request}` a TODA resposta 4xx e 5xx. Sem excluí-lo,
# cada 404 e cada 500 despejariam o `repr` de um HttpRequest inteiro num campo do log.
# `status_code` fica, porque é escalar e é informação.
#
# A lista é nossa e envelhece com o Django: um atributo novo de LogRecord numa versão
# futura entra como campo solto no JSON até que alguém o acrescente aqui. A falha é
# visível — o campo aparece na linha —, e não silenciosa.
_ATRIBUTOS_DO_REGISTRO = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "request",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }
)


class FormatadorJSON(logging.Formatter):
    """Um objeto JSON por linha, no esquema fixado pela ADR 0012."""

    def format(self, record):
        extras = {
            chave: valor
            for chave, valor in record.__dict__.items()
            if chave not in _ATRIBUTOS_DO_REGISTRO
        }
        # As chaves fixas por último: um `extra=` acrescenta campo, nunca sobrescreve o
        # contrato de leitura.
        linha = {
            **extras,
            # datetime.fromtimestamp com fuso explícito, nunca self.formatTime: o
            # formatTime devolve hora local sem declarar fuso, e marca de tempo sem fuso
            # não se ordena contra nada nem se compara com a de outro processo.
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            # getattr com default, e não record.request_id: um handler acrescentado amanhã
            # sem a lista de `filters` produziria AttributeError dentro do `logging`, que
            # descarta o registro com uma linha em stderr. A linha some e nada acusa — é
            # esse silêncio que o default fecha.
            "request_id": getattr(record, "request_id", "-"),
            "msg": record.getMessage(),
        }
        if record.exc_info:
            # formatException formata a pilha SEM os locais de cada quadro. É o que impede
            # que um traceback de /o/token/ carregue o code_verifier para dentro do log.
            linha["exc"] = self.formatException(record.exc_info)
        # default=str fecha o único modo de falha real da serialização: um objeto não
        # serializável vindo de um `extra=`, que sem ele levantaria dentro do `logging` e
        # faria o registro ser descartado com uma linha em stderr. ensure_ascii=False
        # preserva o acento das mensagens do projeto, que são em português.
        return json.dumps(linha, default=str, ensure_ascii=False)


class FiltroRequestId(logging.Filter):
    """Injeta o identificador da requisição em curso no registro.

    Declarado nos handlers, e não em cada logger: as entradas de `LOGGING` desembocam em
    dois handlers, e duas declarações alcançam todas — inclusive `django.request`.
    """

    def filter(self, record):
        record.request_id = _request_id.get()
        return True


class ObservabilidadeMiddleware:
    """Gera o identificador da requisição e emite a linha de acesso.

    Um middleware só para as duas responsabilidades porque são o mesmo escopo: o
    identificador nasce com a requisição que a linha de acesso descreve, e vale até a
    entrada da requisição seguinte no mesmo contexto (ADR 0014). A posição dele no
    `MIDDLEWARE` é fixada em `config/settings.py`, com a razão.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # O identificador é sempre gerado aqui, nunca lido de cabeçalho de entrada: não há
        # proxy nem serviço a montante que já o tivesse gerado, e um cabeçalho que ninguém
        # impõe é um cabeçalho que qualquer cliente escreve — a correlação passaria a ser
        # escrita por terceiro.
        #
        # Não há reset na saída, e a razão é de tempo de vida (ADR 0014):
        # BaseHandler.get_response chama log_response para toda resposta de status igual ou
        # superior a 400 DEPOIS que a cadeia de middleware inteira retornou. Com reset,
        # aquela linha — o "Not Found: /caminho", o "Service Unavailable: /health", os 400
        # das guardas de /o/authorize/ — sairia com "-" e perderia o pedido a que pertence.
        # Nenhuma posição no MIDDLEWARE alcança esse ponto: ele roda acima da cadeia.
        #
        # O que substitui o reset é a sobrescrita: cada requisição põe um valor novo na
        # entrada, e requisições distintas continuam recebendo identificadores distintos —
        # que é a propriedade que o reset protegia.
        #
        # O silêncio que isso cria: num processo que já atendeu alguma requisição, uma linha
        # emitida FORA de requisição carrega o identificador da última. No container não
        # acontece, porque nada registra entre um pedido e o seguinte; acontece sob
        # `manage.py test`, em que Client.login() dispara user_logged_in fora de requisição
        # HTTP e há caso que chama view direto com RequestFactory. A linha parece
        # correlacionada e não está, e nada a distingue de uma correta.
        _request_id.set(uuid.uuid4().hex[:16])
        inicio = time.perf_counter()
        # Sem try/except em volta da chamada: exceção de view já é convertida em resposta
        # 500 por convert_exception_to_response, abaixo deste middleware, de modo que o que
        # chega aqui é status 500, e não exceção.
        resposta = self.get_response(request)
        duracao_ms = round((time.perf_counter() - inicio) * 1000, 2)
        # resolver_match só existe DEPOIS da chamada: antes dela a URL ainda não foi
        # resolvida. Requisição que não resolve rota — estático do WhiteNoise, 404, o 301 do
        # SecurityMiddleware — sai com "-", e a linha de acesso não diz que caminho foi
        # tentado; para o 404, o caminho está na linha que o próprio django.request emite,
        # com o mesmo request_id — é a emenda da ADR 0014 que sustenta essa igualdade.
        rota = request.resolver_match.view_name if request.resolver_match else "-"
        if rota not in settings.ACCESS_LOG_EXCLUDED_ROUTES:
            _logger_acesso.info(
                "requisição atendida",
                extra={
                    "route": rota,
                    "method": request.method,
                    "status": resposta.status_code,
                    "duration_ms": duracao_ms,
                },
            )
        return resposta
