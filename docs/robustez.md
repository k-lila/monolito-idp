# Robustez e prontidão para produção — Monólito IdP

Reforços que levam o núcleo — hoje sólido, mas dimensionado como **sandbox de host único** — a aguentar eventos reais de deploy e produção. Cada item é ancorado em algo concreto do repositório atual: a migração no boot assumindo réplica única, `CONN_MAX_AGE=0`, chave RSA única no `.env`, `/health` único, `cleartokens` não agendado e ausência de TLS próprio.

**Prioridade:** 🔴 alta · 🟡 média · ⚪ evolutiva

## Tabela de reforços

| Reforço | Evento de produção que mitiga | Ação concreta neste projeto | Prio |
|---|---|---|---|
| **Rate limiting na superfície de auth** | Força bruta / credential stuffing em login, `/o/token/`, `/o/authorize/` | `django-axes` no login + throttle nos endpoints de token; o Redis já está disponível como backend | 🔴 |
| **Terminação TLS + reverse proxy** | Exposição fora de localhost; OIDC exige HTTPS — sem isso, senha em claro | Nginx/Caddy/Traefik à frente setando `X-Forwarded-Proto`; ligar `BEHIND_TLS_PROXY=1` (as flags de hardening já existem) | 🔴 |
| **Custódia da chave RSA fora do `.env`** | Vazamento da chave privada = comprometimento total (ela assina todos os `id_token`) | Docker secrets / Vault / KMS injetando `OIDC_RSA_PRIVATE_KEY`, em vez de arquivo versionável | 🔴 |
| **Backup e restore testados do Postgres** | Perda ou corrupção de dados: usuários, *clients*, grants | `pg_dump` agendado ou PITR via WAL; ensaiar o **restore**, não só o backup | 🔴 |
| **Separar a migração do boot do app** | O entrypoint migra no boot e assume 1 réplica — hoje isso barra escalar e deploy *rolling* seguro | Migração como passo dedicado (fase de *release* / init container / job); o app sobe já migrado e stateless | 🔴 (destrava deploy) |
| **Erro rastreado + logs estruturados + auditoria** | Diagnóstico de incidente; um IdP precisa de trilha de quem logou e que token emitiu | Sentry para exceções; logs JSON com *request-id*; log de auditoria de login, emissão e consentimento | 🔴 |
| **Liveness vs readiness separados** | `/health` único checa banco+cache — um soluço de dependência reiniciaria o container em vez de só tirá-lo do balanceador | Liveness raso (processo vivo) + readiness profundo (deps), sobretudo sob orquestrador | 🟡 |
| **Agendar `cleartokens`** | A tabela de tokens do DOT cresce sem limite e degrada o banco | Cron / systemd timer / cronjob rodando `manage.py cleartokens` periodicamente | 🟡 |
| **Tuning do gunicorn + limites de recurso** | Vazamento de memória, worker preso, *thundering herd* | `--max-requests`/`--max-requests-jitter` e `--timeout` explícitos; limites de CPU/memória no compose | 🟡 |
| **Pool de conexões do banco** | `CONN_MAX_AGE=0` abre conexão por request; sob N workers estoura `too many connections` | PgBouncer à frente do Postgres, ou `CONN_MAX_AGE` ajustado com critério | 🟡 |
| **Plano de rotação de chave** | Chave comprometida ou rotação programada; hoje há uma só e a troca é destrutiva (invalida tokens vivos e o JWKS cacheado nas RPs) | Rotação com sobreposição: publicar a nova chave no JWKS e manter a antiga durante a janela de expiração dos tokens | 🟡 |
| **CI/CD + varredura de dependências e imagem** | Regressão em produção; dependência ou imagem com CVE | Pipeline rodando a suíte (que já é ampla) + `pip-audit` + scan de imagem (Trivy); build e deploy *gated* | 🟡 |
| **Container não-root + imagem endurecida** | Raio de dano em caso de escape do container | `USER` dedicado (o Dockerfile já sinaliza o adiamento), *filesystem* read-only, *drop* de capabilities | 🟡 |
| **`manage.py check --deploy` como gate** | Subir com config insegura (cookie, HSTS, `DEBUG`) sem perceber | Rodar no CI e/ou no boot — falha cedo, não em produção | ⚪ |

## Sequência recomendada

As seis 🔴 são o que separa "roda na minha máquina" de "pode ficar de pé exposto".

Dentro delas, a **separação da migração do boot** é a peça-chave: é ela que remove a premissa de réplica única e destrava tudo o que é *rolling deploy*, escala horizontal e readiness/liveness — sem isso, vários dos itens 🟡 não têm como existir.

Depois dela:

1. **TLS + reverse proxy** e **rate limiting** fecham a exposição de borda.
2. **Backup/restore testados** e **erro rastreado + auditoria** cobrem o "quando algo der errado".
3. **Custódia da chave RSA** protege o segredo do qual todo o resto depende.

Com as 🔴 no lugar, os itens 🟡 passam a ser refinamentos incrementais de resiliência e operação, e os ⚪ são higiene contínua que o CI automatiza.
