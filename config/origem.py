"""De que endereço veio esta requisição — a única resposta do sistema.

Três peças precisam do mesmo valor: a trilha de auditoria, no campo `ip` de cada linha
(`accounts/auditoria.py`); o limitador de taxa de `/o/`, na chave do contador
(`config/limites.py`); e o `django-axes`, por contrato de string em
`AXES_CLIENT_IP_CALLABLE`. São o mesmo fato, e dois lugares que o leem divergem sem emitir
sinal — daí uma função só, que este módulo não compartilha com nenhuma outra
responsabilidade. A razão completa e as alternativas descartadas estão na ADR (Architecture
Decision Record)
`docs/adr/0015-resolver-a-origem-do-cliente-num-ponto-unico.md`.

A trilha grava também a procedência do valor, e é `origem_e_procedencia` quem a calcula, no
mesmo percurso do endereço (ADR 0018). Endereço e procedência não podem divergir porque são
o mesmo cálculo — a propriedade que a ADR 0015 comprou para o endereço, estendida.

A trilha grava ainda o alcance do endereço — se ele é o gateway padrão deste processo, que é
a borda em que o `docker-proxy` colapsa tudo que vem do host (ADR 0020). Para responder isso
o módulo lê `/proc/net/route`, e com essa leitura deixa de ser puro. Não é segunda
responsabilidade: a pergunta continua sendo uma só, "de que endereço veio", agora incluindo o
que aquele endereço é para este processo. É `origem_completa` quem entrega os três valores,
pela mesma razão de sempre — composto num cálculo só, o alcance não tem como divergir do
endereço sobre o qual foi calculado.

Este módulo não importa nada do projeto, e `accounts` importa dele: a direção é sempre
`accounts` -> `config.origem`, nunca a inversa.
"""

import ipaddress

from django.conf import settings

# A tabela de rotas do kernel, tal como o procfs a publica. Constante e não setting: não é
# escolha de implantação, é o caminho que o Linux fixa.
_TABELA_DE_ROTAS = "/proc/net/route"


def origem_e_procedencia(request):
    """Par `(endereço, procedência)` do cliente, ou `(None, None)` fora de requisição HTTP.

    A procedência declara de onde o endereço saiu, e é o que permite ler a trilha depois de
    `BEHIND_TLS_PROXY` mudar de valor: o arquivo é append-only e o instante da troca não
    fica gravado em lugar nenhum (ADR 0018). São três valores, um por desfecho:

    `remote_addr`           — `BEHIND_TLS_PROXY` falso: o endereço é o da conexão;
    `forwarded`             — proxy declarado e saltos suficientes no cabeçalho;
    `remote_addr_fallback`  — proxy declarado e cabeçalho ausente ou curto demais.

    Com `BEHIND_TLS_PROXY` falso — a configuração da jornada de construção —, devolve
    `REMOTE_ADDR` e nada mais: `X-Forwarded-For` é cabeçalho que qualquer cliente escreve, e
    lê-lo sem um proxy que o imponha entregaria ao atacante a escolha da própria chave de
    contagem e da origem que a trilha registra.

    Com a variável verdadeira, devolve o salto de `X-Forwarded-For` contado a partir da
    direita, na posição de `TRUSTED_PROXY_COUNT`. Nunca o primeiro elemento da lista: o
    primeiro é escrito pelo cliente e é forjável; o último é escrito pelo proxy
    imediatamente à frente e não é.

    As duas settings são lidas a cada chamada, e não no import: é o que torna o ramo de
    proxy exercitável por `override_settings`.
    """
    # `request` é None quando authenticate() é chamado sem ele — fora de uma requisição
    # HTTP, por shell ou por comando de `manage.py`. Sem endereço não há procedência a
    # declarar, e um rótulo aqui afirmaria uma leitura que não houve.
    if request is None:
        return None, None

    endereco_direto = request.META.get("REMOTE_ADDR")

    if not settings.BEHIND_TLS_PROXY:
        return endereco_direto, "remote_addr"

    # O SILÊNCIO DESTE RAMO, e é ele a razão de esta função existir: com o proxy de pé e o
    # cabeçalho ausente ou mal configurado, cai-se no `REMOTE_ADDR`, que passa a valer o
    # endereço do proxy para toda requisição externa. O contador soma o tráfego inteiro numa
    # chave só, o primeiro atacante tranca a tela de login para todos, e a trilha registra o
    # mesmo endereço em todas as linhas — sem erro e sem log. O que rompe o silêncio é a
    # procedência: `remote_addr_fallback` em toda linha de uma implantação atrás de proxy
    # denuncia o cabeçalho que não chega, e é o único sinal que essa falha emite. Está no
    # catálogo da seção 14 de `docs/runbook.md`.
    saltos = [
        salto.strip()
        for salto in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")
        if salto.strip()
    ]
    # Menos saltos que os proxies declarados significa cabeçalho que não passou por onde se
    # supõe: o valor não é confiável, e a queda é para o endereço direto.
    if len(saltos) < settings.TRUSTED_PROXY_COUNT:
        return endereco_direto, "remote_addr_fallback"
    return saltos[-settings.TRUSTED_PROXY_COUNT], "forwarded"


def origem_da_requisicao(request):
    """Endereço de origem do cliente, ou None fora de uma requisição HTTP.

    Projeção de `origem_e_procedencia` no primeiro elemento — a regra de resolução inteira
    está lá. Esta assinatura não muda: ela é contrato de string do `django-axes` em
    `AXES_CLIENT_IP_CALLABLE` e import direto de `config/limites.py`.
    """
    endereco, _ = origem_e_procedencia(request)
    return endereco


def _gateway_padrao():
    """Endereço do gateway padrão deste processo, ou None quando a rota não se deixa ler.

    O destino `00000000` é a rota default; o campo Gateway vem em hexadecimal
    little-endian, na ordem em que o kernel guarda o endereço — daí o
    `int.from_bytes(..., "little")`, e não um `int(campo, 16)` direto.

    Sem cache e sem leitura no import: ler no import amarra o valor ao instante do boot e
    some sob teste, e cache de módulo é estado que ninguém invalida. O preço é um `open` de
    procfs por linha da trilha, e a trilha tem cinco eventos — não uma linha por requisição.
    """
    # A CAPTURA É LARGA DE PROPÓSITO, e não é tratamento de cenário impossível: exceção que
    # escape daqui sobe até o `except Exception` do receptor de sinal em
    # `accounts/auditoria.py`, que a converte em "auditoria: falha ao registrar" e a LINHA
    # INTEIRA SE PERDE. O preço de um `/proc` ausente, de um arquivo truncado ou de um campo
    # ilegível não pode ser uma linha de auditoria a menos — é `unknown` naquela linha, e
    # nada mais.
    try:
        with open(_TABELA_DE_ROTAS, "r", encoding="ascii") as tabela:
            next(tabela)                      # cabeçalho
            for linha in tabela:
                campos = linha.split()
                if len(campos) > 2 and campos[1] == "00000000":
                    return str(ipaddress.IPv4Address(
                        int.from_bytes(bytes.fromhex(campos[2]), "little")
                    ))
    except (OSError, ValueError, StopIteration):
        return None
    # Tabela lida e sem rota default: o processo não tem gateway a que comparar o endereço.
    return None


def _alcance_do_endereco(endereco):
    """O que o endereço é para este processo, ou None fora de uma requisição HTTP.

    O campo que a trilha chama `ip_edge`, com três valores (ADR 0020):

    `gateway` — o endereço é o gateway padrão do processo. É nele que colapsa tudo que veio
        pelo `docker-proxy`, e a origem real não está no arquivo nem em lugar nenhum;
    `peer`    — o endereço difere do gateway padrão. NÃO afirma que identifique um cliente
        único: afirma só que não é a borda em que o host colapsa;
    `unknown` — a rota padrão não pôde ser lida, ou o endereço não é IPv4.

    A ordem é endereço primeiro, arquivo depois: endereço impróprio não paga leitura de
    arquivo.

    IPv6 devolve `unknown`, e não `peer`: a rota lida é a IPv4, e comparar famílias
    diferentes afirmaria "não é o gateway" sem ter olhado o gateway daquela família.
    """
    if endereco is None:
        return None
    try:
        candidato = ipaddress.ip_address(endereco)
    except ValueError:
        return "unknown"
    if candidato.version != 4:
        return "unknown"
    gateway = _gateway_padrao()
    if gateway is None:
        return "unknown"
    return "gateway" if str(candidato) == gateway else "peer"


def origem_completa(request):
    """Tripla `(endereço, procedência, alcance)`, ou `(None, None, None)` fora de requisição.

    O que a trilha grava em `ip`, `ip_src` e `ip_edge`. A regra de resolução do endereço e
    da procedência é de `origem_e_procedencia`; o alcance é calculado **sobre o endereço que
    aquela chamada devolveu**, e é isso que compra a propriedade de os três nunca
    divergirem. A propriedade é da composição, e não de disciplina de quem chama: não há
    aqui uma segunda leitura de `REMOTE_ADDR` ou de cabeçalho que pudesse discordar da
    primeira (ADRs 0015 e 0020).
    """
    endereco, procedencia = origem_e_procedencia(request)
    return endereco, procedencia, _alcance_do_endereco(endereco)
