#!/usr/bin/env bash
# Boot do container: migracao, coleta de estaticos, superusuario condicional, gunicorn.
#
# Sem laco de polling esperando Postgres ou Redis — a espera e do `depends_on` do compose,
# com `condition: service_healthy`.
set -euo pipefail

# O ENTRYPOINT vale para toda execucao da imagem, nao so para o boot do servico:
# sem esta guarda, `docker compose run --rm app python manage.py migrate` teria o
# comando descartado em silencio e veria um gunicorn subir. Comando explicito roda
# sozinho, sem a sequencia de boot — que e o que se quer numa tarefa avulsa.
if [ "$#" -gt 0 ]; then
    exec "$@"
fi

python manage.py migrate --noinput
python manage.py collectstatic --noinput

# `${VAR:-}` e obrigatorio sob `set -u`: as duas variaveis saem comentadas do .env.example,
# e uma referencia nua abortaria o boot com `unbound variable`.
#
# O `||` cobre o unico modo de falha realista depois de um migrate bem-sucedido:
# createsuperuser com e-mail ja existente levanta CommandError e sai com codigo 1, que sob
# `set -e` derrubaria o container. Engolimos o codigo de saida, nunca a mensagem — o
# CommandError sai em stderr e aparece imediatamente acima da nossa linha em `docker logs`.
if [ -n "${DJANGO_SUPERUSER_EMAIL:-}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
    python manage.py createsuperuser --noinput \
        || echo "entrypoint: createsuperuser nao criou conta — a mensagem acima diz por que; boot segue"
fi

# `exec` para que o gunicorn receba os sinais do container diretamente, sem o bash no meio.
#
# --workers 3 nao e derivado: e o default convencional, e nada neste projeto
# distingue 3 de 2 ou de 4. Derivado e o PISO. Worker sync atende uma requisicao
# por vez: com --workers 1 a probe do HEALTHCHECK espera na fila atras de qualquer
# requisicao em voo — inclusive de uma presa nos tetos de 2s durante degradacao — e
# passaria a medir a fila em vez dos componentes. O que mais de um worker NAO
# compra: manter o IdP de pe durante a degradacao. Com SESSION_ENGINE cached_db e
# toda view tocando o banco, na degradacao toda requisicao bloqueia nos mesmos dois
# componentes.
#
# Sem --access-logfile: uma linha a cada 10s de probe afogaria o `docker logs` onde a falha
# de migrate e o traceback de 500 precisam ser vistos.
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3
