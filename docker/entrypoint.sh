#!/usr/bin/env bash
# Boot do container: migração, coleta de estáticos, gunicorn.
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

# Sem criação de superusuário: ela saiu daqui com a ADR 0019, e a conta administrativa nasce
# de `docker compose run --rm app python manage.py createsuperuser`, interativo, atendido
# pela guarda de `$#` acima. A senha passou a ser digitada num prompt em vez de ficar em
# texto claro no `.env`, lida pelo compose e herdada por todo `exec` posterior.
#
# A consequência é de operação: ambiente novo sobe SEM conta nenhuma, e `up --wait` verde
# deixou de significar "pronto para usar". O comando está no arranque mínimo do `README.md`.

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
