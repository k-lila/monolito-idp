#!/usr/bin/env bash
# Gera o par RSA de desenvolvimento e imprime a linha pronta para o .env, com as quebras
# de linha do PEM escapadas como \n — o formato que env.str(..., multiline=True) desfaz.
#
# O script nao escreve no .env: quem cola a linha e uma pessoa. Escrita automatica
# sobrescreveria sem confirmacao uma chave possivelmente em uso, e trocar a chave invalida
# todo token vivo e quebra o JWKS cacheado das relying parties (ADR 0004).
#
# 2048 bits e fixo, sem parametro: e o piso aceito para RS256 e o que toda biblioteca de
# relying party valida sem configuracao. A chave de producao nao sai daqui.
set -euo pipefail

pem=$(openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 | awk '{printf "%s\\n", $0}')

# printf, nunca echo: o tratamento de \n no echo varia por shell.
printf 'OIDC_RSA_PRIVATE_KEY=%s\n' "$pem"
