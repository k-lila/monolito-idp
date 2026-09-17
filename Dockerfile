# Imagem da aplicação: multi-stage sobre python:3.14-slim.
#
# O que o multi-stage compra aqui e o que ele não compra: a TASK-002 verificou que toda a
# árvore de requirements.txt instala sem compilação local — psycopg-binary tem wheel cp314,
# cryptography e argon2-cffi-bindings publicam abi3 —, então NÃO há build-essential a
# esconder e a imagem final não encolhe por causa dele. O que a separação preserva é o
# wheelhouse e os metadados de pip fora da camada final, e a costura pronta para o dia em
# que uma dependência parar de publicar wheel: o toolchain entra no estágio 1 e nada muda
# no estagio 2.

FROM python:3.14-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip wheel -r requirements.txt -w /wheels


FROM python:3.14-slim

# Não é cosmético: o LOGGING do projeto escreve em `ext://sys.stdout`, e stdout ligado a
# pipe — que é o que `docker logs` dá — é bufferizado em bloco. Sem esta linha, o traceback
# de um 500 fica retido e o gate do passo 11 reprova por um sintoma que parece do Django.
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# requirements.txt antes do resto do código: a camada de dependências só é invalidada
# quando ele muda, e não a cada edição de template.
COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN pip install --no-index --find-links=/wheels -r requirements.txt

COPY . .

# Depois do COPY: o bit de execução do repositório não atravessa todo contexto de build, e
# perde-lo produz `permission denied` no boot — mensagem que não menciona chmod.
RUN chmod +x docker/entrypoint.sh

# UID e GID FIXOS, e não os que o sistema atribuir: o volume nomeado `auditlog` guarda posse
# NUMÉRICA, e um identificador que mude entre builds órfã o volume — a trilha para de ser
# escrita e a mensagem fala de permissão de arquivo, nunca de UID.
#
# Os dois diretórios são criados aqui, na imagem, e não no boot: é da imagem que o Docker
# copia dono e modo ao inicializar um volume nomeado VAZIO. Ambiente que já rodou tem o
# volume populado e de posse de `root`, e para volume não vazio o Docker não recopia nada —
# ali é preciso o passo avulso de `docs/receita.md`, uma vez só.
RUN groupadd --gid 10001 nova_api \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin nova_api \
    && mkdir -p /app/staticfiles /var/log/nova_api \
    && chown nova_api:nova_api /app/staticfiles /var/log/nova_api

EXPOSE 8000

# Probe pelo interpretador da própria imagem: python:*-slim não traz curl nem wget, e a
# stdlib já cumpre o contrato.
#
# O HTTPError do 503 propaga de propósito: o processo sai com código 1, que é o unhealthy
# do Docker, e a mensagem fica em `.State.Health.Log`. Capturá-lo para imprimir "503"
# custaria escapes dentro de uma string e daria a mesma informação.
#
# 127.0.0.1 e não localhost: em Debian slim o nome resolve ::1 primeiro, e cada probe
# gastaria uma tentativa recusada antes do fallback IPv4.
#
# timeout=7 interno sob `timeout: 8s` externo, para que a mensagem saia antes do
# machado do Docker. Os 7s são o teto da view (ADR 0011) mais folga: 2s de
# connect_timeout do banco, mais 4s do cache — socket_connect_timeout e
# socket_timeout são ADITIVOS dentro de uma única operação
# (redis/connection.py:1598-1604) —, mais 1s para o resto do request. O `get` da
# view não entra na conta: ele compartilha o `try` do `set` e não executa quando o
# `set` levanta. O 8s externo é a folga de 1s sobre a probe; `--interval` segue em
# 10s, que já acomoda os 8s.
# start-period=30s cobre migrate + collectstatic antes de qualquer veredito.
HEALTHCHECK --interval=10s --timeout=8s --start-period=30s --retries=3 \
  CMD ["python", "-c", "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=7).status == 200 else 1)"]

# A revisão que este arquivo marcava para "a primeira exposicao fora de localhost" é o
# Bloco C, e ela é esta linha. O processo deixa de ser root; os dois diretórios que ele
# escreve — estáticos do collectstatic e a trilha de auditoria da ADR 0013 — já saíram do
# passo acima com a posse certa.
#
# O USER vale também para `docker compose run`, inclusive o `createsuperuser` que a ADR 0019
# tornou o único caminho da conta administrativa. Tarefa que precise de root pede `--user
# root` explicitamente, e o entrypoint não escala privilégio nenhum por conta própria.
USER nova_api

# Caminho absoluto: o ENTRYPOINT não depende do WORKDIR vigente nem do PATH.
ENTRYPOINT ["/app/docker/entrypoint.sh"]
