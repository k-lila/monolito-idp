#!/usr/bin/env bash
# Boot do container: migração, coleta de estáticos, superusuário condicional, gunicorn.
#
# Sem laço de polling esperando Postgres ou Redis — a espera é do `depends_on` do compose,
# com `condition: service_healthy`.
set -euo pipefail

# O ENTRYPOINT vale para toda execução da imagem, não só para o boot do serviço:
# sem esta guarda, `docker compose run --rm app python manage.py migrate` teria o
# comando descartado em silêncio e veria um gunicorn subir. Comando explícito roda
# sozinho, sem a sequência de boot — que é o que se quer numa tarefa avulsa.
if [ "$#" -gt 0 ]; then
    exec "$@"
fi

python manage.py migrate --noinput
python manage.py collectstatic --noinput

# `${VAR:-}` é obrigatório sob `set -u`: as duas variáveis saem comentadas do .env.example,
# e uma referência nua abortaria o boot com `unbound variable`.
#
# O `||` cobre o único modo de falha realista depois de um migrate bem-sucedido:
# createsuperuser com e-mail já existente levanta CommandError e sai com código 1, que sob
# `set -e` derrubaria o container. Engolimos o código de saída, nunca a mensagem — o
# CommandError sai em stderr e aparece imediatamente acima da nossa linha em `docker logs`.
if [ -n "${DJANGO_SUPERUSER_EMAIL:-}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
    python manage.py createsuperuser --noinput \
        || echo "entrypoint: createsuperuser não criou conta — a mensagem acima diz por quê; boot segue"
fi

# `exec` para que o gunicorn receba os sinais do container diretamente, sem o bash no meio.
#
# --workers 3 não é derivado: é o default convencional, e nada neste projeto
# distingue 3 de 2 ou de 4. Derivado é o PISO. Worker sync atende uma requisição
# por vez: com --workers 1 a probe do HEALTHCHECK espera na fila atrás de qualquer
# requisição em voo — inclusive de uma presa nos tetos de 2s durante degradação — e
# passaria a medir a fila em vez dos componentes. O que mais de um worker NÃO
# compra: manter o IdP de pé durante a degradação. Com SESSION_ENGINE cached_db e
# toda view tocando o banco, na degradação toda requisição bloqueia nos mesmos dois
# componentes.
#
# Sem --access-logfile: uma linha a cada 10s de probe afogaria o `docker logs` onde a falha
# de migrate e o traceback de 500 precisam ser vistos.
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3
