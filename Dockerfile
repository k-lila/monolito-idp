# Imagem da aplicacao: multi-stage sobre python:3.14-slim.
#
# O que o multi-stage compra aqui e o que ele nao compra: a TASK-002 verificou que toda a
# arvore de requirements.txt instala sem compilacao local — psycopg-binary tem wheel cp314,
# cryptography e argon2-cffi-bindings publicam abi3 —, entao NAO ha build-essential a
# esconder e a imagem final nao encolhe por causa dele. O que a separacao preserva e o
# wheelhouse e os metadados de pip fora da camada final, e a costura pronta para o dia em
# que uma dependencia parar de publicar wheel: o toolchain entra no estagio 1 e nada muda
# no estagio 2.

FROM python:3.14-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip wheel -r requirements.txt -w /wheels


FROM python:3.14-slim

# Nao e cosmetico: o LOGGING do projeto escreve em `ext://sys.stdout`, e stdout ligado a
# pipe — que e o que `docker logs` da — e bufferizado em bloco. Sem esta linha, o traceback
# de um 500 fica retido e o gate do passo 11 reprova por um sintoma que parece do Django.
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# requirements.txt antes do resto do codigo: a camada de dependencias so e invalidada
# quando ele muda, e nao a cada edicao de template.
COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN pip install --no-index --find-links=/wheels -r requirements.txt

COPY . .

# Depois do COPY: o bit de execucao do repositorio nao atravessa todo contexto de build, e
# perde-lo produz `permission denied` no boot — mensagem que nao menciona chmod.
RUN chmod +x docker/entrypoint.sh

EXPOSE 8000

# Probe pelo interpretador da propria imagem: python:*-slim nao traz curl nem wget, e a
# stdlib ja cumpre o contrato.
#
# O HTTPError do 503 propaga de proposito: o processo sai com codigo 1, que e o unhealthy
# do Docker, e a mensagem fica em `.State.Health.Log`. Captura-lo para imprimir "503"
# custaria escapes dentro de uma string e daria a mesma informacao.
#
# 127.0.0.1 e nao localhost: em Debian slim o nome resolve ::1 primeiro, e cada probe
# gastaria uma tentativa recusada antes do fallback IPv4.
#
# timeout=7 interno sob `timeout: 8s` externo, para que a mensagem saia antes do
# machado do Docker. Os 7s sao o teto da view (ADR 0011) mais folga: 2s de
# connect_timeout do banco, mais 4s do cache — socket_connect_timeout e
# socket_timeout sao ADITIVOS dentro de uma unica operacao
# (redis/connection.py:1598-1604) —, mais 1s para o resto do request. O `get` da
# view nao entra na conta: ele compartilha o `try` do `set` e nao executa quando o
# `set` levanta. O 8s externo e a folga de 1s sobre a probe; `--interval` segue em
# 10s, que ja acomoda os 8s.
# start-period=30s cobre migrate + collectstatic antes de qualquer veredito.
HEALTHCHECK --interval=10s --timeout=8s --start-period=30s --retries=3 \
  CMD ["python", "-c", "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=7).status == 200 else 1)"]

# Sem USER dedicado, deliberadamente: sandbox de host unico, uma replica, porta publicada
# em loopback. Dar ownership de /app/staticfiles ao usuario que roda o collectstatic
# acrescentaria superficie sem consumidor. Revisar na primeira exposicao fora de localhost.

# Caminho absoluto: o ENTRYPOINT nao depende do WORKDIR vigente nem do PATH.
ENTRYPOINT ["/app/docker/entrypoint.sh"]
