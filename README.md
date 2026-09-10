# nova_api

Provedor de identidade (IdP, de *Identity Provider*) OpenID Connect (OIDC) sobre Django e
`django-oauth-toolkit`: fecha o fluxo Authorization Code + PKCE (Proof Key for Code Exchange),
publica descoberta e JWKS (JSON Web Key Set), e emite `id_token` assinado em RS256 (RSA, de
Rivest–Shamir–Adleman, com SHA-256).

## O escopo é o de sandbox exploratório

Tudo o que está decidido neste repositório descansa sobre uma premissa única:

- host único, orquestrado por `docker-compose.yml`;
- uma réplica da aplicação;
- portas publicadas em `127.0.0.1`, para a aplicação, o Postgres e o Redis;
- sem TLS (Transport Layer Security) próprio — o Gunicorn fala texto claro;
- nenhuma pessoa usuária além de quem opera a máquina.

Isso não é provisório por descuido: é premissa de várias decisões registradas. O que o IdP
protege hoje, o que não protege e o que muda antes de expô-lo a alguém está em
`docs/seguranca.md`.

## As duas jornadas

A escolha entre elas é o passo zero, e as duas leem o mesmo `.env`.

- **Clonar-e-rodar** — a aplicação sobe no container `app`, ao lado do Postgres e do Redis. O
  host só precisa de Docker com o plugin `compose`. Serve para ver o IdP funcionando.
- **Construção** — a aplicação roda em `runserver` no host, contra o Postgres e o Redis do
  compose, e exige Python 3.14 com ambiente virtual. Serve para editar código e ver o efeito
  sem rebuild de imagem.

A diferença que importa está em `DATABASE_URL` e `REDIS_URL`: o `.env` guarda os endereços da
jornada de construção, em `localhost`, e é o `docker-compose.yml` que sobrescreve as duas
quando a aplicação roda em container.

## Arranque mínimo

Clonar-e-rodar, do zero ao `/admin/` aberto:

```bash
cp .env.example .env       # preencha SECRET_KEY, POSTGRES_PASSWORD e DATABASE_URL
./scripts/gen_dev_key.sh   # cole a linha impressa na OIDC_RSA_PRIVATE_KEY vazia
docker compose up --wait
docker compose exec app python manage.py createsuperuser
```

Os dois primeiros passos exigem editar o `.env` à mão, e a chave RSA tem de estar lá **antes**
de o stack subir: sem ela o IdP responde normalmente e não assina `id_token` nenhum. Cada
passo, com as regras de caracteres do `.env` e o sinal de que deu certo, está em
`docs/receita.md` — inclusive o registro da Application e o fluxo PKCE fechado à mão.

### Se você já tem um `.env`

**Não rode o `cp` acima.** O `.env` é untracked e não tem cópia: ele guarda a única chave privada
RSA e a única `SECRET_KEY` deste IdP, e sobrescrevê-lo destrói as duas sem que nenhum `git
reset` as devolva.

O que falta ao seu arquivo é uma linha, que tem de ser acrescentada **à mão e antes de subir** —
sem ela nada sobe, e a mensagem nomeia a variável:

```
AUDIT_LOG_PATH=logs/audit.log
```

É o caminho da trilha de auditoria na jornada de construção. Dentro do container o
`docker-compose.yml` o sobrescreve por um caminho em volume nomeado.

## Os demais documentos

| Documento | A que pergunta responde |
| --- | --- |
| `docs/arquitetura.md` | que módulos existem, onde passa a fronteira entre eles e por onde caminha um pedido |
| `docs/receita.md` | como subir o stack passo a passo, o que rodar no dia a dia e o que falta decidir para produção |
| `docs/runbook.md` | quebrou: qual o sintoma, qual a causa, qual a correção; e como operar o que já está de pé |
| `docs/integracao-rp.md` | o que uma relying party — a aplicação que delega a autenticação a este IdP — precisa saber para integrar |
| `docs/seguranca.md` | o que o IdP protege, o que não protege e o que muda antes de ele sair de `localhost` |
| `docs/testes.md` | o que a suíte cobre, em que nível, com que rastreabilidade, e o que ficou de fora |
| `docs/esboco.md` | o que é um IdP e por que cada tecnologia do núcleo, com prós e contras |
| `CLAUDE.md` | as regras de trabalho deste repositório |

As decisões de arquitetura vivem em `docs/adr/`, uma por arquivo e imutáveis depois de aceitas.
O índice das quatorze está em `docs/arquitetura.md`; o formato, em `docs/adr/template-adr.md`.
