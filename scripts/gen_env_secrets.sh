#!/usr/bin/env bash
# Gerador único dos segredos do .env: OIDC_RSA_PRIVATE_KEY, SECRET_KEY, POSTGRES_PASSWORD e
# REDIS_PASSWORD, mais DATABASE_URL e REDIS_URL já derivadas das duas senhas. Imprime as linhas
# prontas para colar. Nenhum outro script do repositório gera esses valores.
#
#   ./scripts/gen_env_secrets.sh                 as seis linhas, para um .env novo
#   ./scripts/gen_env_secrets.sh --so-chave-rsa  só a OIDC_RSA_PRIVATE_KEY, para trocar a chave
#
# O script não escreve no .env nem cria arquivo: quem cola as linhas é uma pessoa. Escrita
# automática sobrescreveria sem confirmação valores possivelmente em uso, e cada um quebra uma
# coisa. Trocar a chave invalida todo id_token vivo e quebra o JWKS cacheado das relying parties
# (ADR 0004). Trocar a SECRET_KEY invalida toda sessão viva. Trocar POSTGRES_PASSWORD num .env
# cujo volume pgdata já existe não muda a senha no banco, porque o Postgres só a lê na primeira
# inicialização, e o app passa a falhar na autenticação.
#
# --so-chave-rsa existe por essa última razão. Quem troca a chave e cola o bloco inteiro troca
# também as três senhas, e o erro só aparece depois, longe da causa. Com a opção, a saída não
# contém nada além da linha que se quer trocar.
#
# A chave tem 3072 bits fixos, sem parâmetro, e é a mesma em desenvolvimento e em produção
# (ADR 0028). 3072 bits dão 128 de segurança, o nível do SHA-256 do RS256. 2048 dão 112, que o
# NIST (National Institute of Standards and Technology) aceita só até 2030, e a chave de
# produção vive até a primeira troca, que sem conjunto de rotação é disruptiva. Um tamanho só é
# um caminho só: a chave de produção sai do mesmo comando que o desenvolvimento exercita. Nada
# fora daqui confere o tamanho: uma chave de 2048 colada à mão sobe o IdP sem aviso.
#
# O PEM sai em uma linha, com as quebras escapadas como \n — o formato que
# env.str(..., multiline=True) desfaz em config/settings.py.
#
# Tudo é hexadecimal, por construção. O .env atravessa três gramáticas — a do django-environ, a
# da interpolação do docker compose e a de URL (docs/receita.md) — e hexadecimal não tem
# nenhum caractere especial em nenhuma delas: sem `$`, que o compose trunca em silêncio, e sem
# `@`, `:`, `/` ou `#`, que quebram a URL com um erro que fala de host ou de porta, nunca de
# senha.
#
# As URLs saem com o usuário, o banco e as portas do .env.example. Quem usa outros valores os
# passa pelo ambiente, por exemplo `POSTGRES_PORT=5433 ./scripts/gen_env_secrets.sh`; sem isso,
# a URL impressa diverge do .env em silêncio, e a divergência só aparece na primeira conexão.
#
# Tudo é gerado antes de qualquer linha ser impressa: se o openssl falhar no meio, a saída fica
# vazia, e não metade de um .env que alguém cole achando que está inteiro.
set -euo pipefail

case "$#:${1-}" in
    0:) so_chave=false ;;
    1:--so-chave-rsa) so_chave=true ;;
    *) printf 'uso: %s [--so-chave-rsa]\n' "$0" >&2; exit 2 ;;
esac

pem=$(openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 | awk '{printf "%s\\n", $0}')

# printf, nunca echo: o tratamento de escapes no echo varia por shell.
if [ "$so_chave" = true ]; then
    printf 'OIDC_RSA_PRIVATE_KEY=%s\n' "$pem"
    exit 0
fi

postgres_user=${POSTGRES_USER:-nova_api}
postgres_db=${POSTGRES_DB:-nova_api}
postgres_port=${POSTGRES_PORT:-5432}
redis_port=${REDIS_PORT:-6379}

secret_key=$(openssl rand -hex 48)
postgres_password=$(openssl rand -hex 24)
redis_password=$(openssl rand -hex 32)

printf 'SECRET_KEY=%s\n' "$secret_key"
printf 'OIDC_RSA_PRIVATE_KEY=%s\n' "$pem"
printf 'POSTGRES_PASSWORD=%s\n' "$postgres_password"
printf 'REDIS_PASSWORD=%s\n' "$redis_password"
printf 'DATABASE_URL=postgres://%s:%s@localhost:%s/%s\n' \
    "$postgres_user" "$postgres_password" "$postgres_port" "$postgres_db"
# Usuário vazio de propósito: o Redis sob requirepass autentica só por senha.
printf 'REDIS_URL=redis://:%s@localhost:%s/0\n' "$redis_password" "$redis_port"
