# 0019. Criar o superusuário por comando explícito, fora do boot

## Status

Aceito — 2026-09-13

## Contexto

A ADR (Architecture Decision Record) 0006 descreveu o boot do container como "um entrypoint que
executa migrate, collectstatic e a criação condicional de superusuário antes de fazer exec no
Gunicorn". A criação é condicional a duas variáveis, `DJANGO_SUPERUSER_EMAIL` e
`DJANGO_SUPERUSER_PASSWORD`, que saem comentadas do `.env.example` e que, quando definidas,
põem a senha de administrador em texto claro num arquivo lido pelo docker compose e herdado
pelo ambiente do processo — inclusive por qualquer `docker compose exec` posterior.

`docs/seguranca.md` registra isso duas vezes: na seção 4, como controle ausente, e na seção 6,
como item da lista do que muda antes de expor o IdP (Identity Provider) fora de `localhost`. O
Bloco C é essa lista.

O mecanismo que substitui a automação já existe e não custa nada: a guarda `[ "$#" -gt 0 ]` do
`docker/entrypoint.sh` executa comando avulso sem a sequência de boot, e é ela que faz
`docker compose run --rm app python manage.py createsuperuser` funcionar hoje.

## Decisão

Vamos remover a criação de superusuário do `docker/entrypoint.sh` e as duas variáveis do
`.env.example`. A conta administrativa passa a ser criada por comando explícito e interativo,
`docker compose run --rm app python manage.py createsuperuser`, cuja senha é digitada num
prompt e não fica em arquivo nenhum.

Esta decisão emenda a alínea correspondente da ADR 0006 e não a substitui: o entrypoint
continua migrando, coletando estáticos e fazendo `exec` no gunicorn.

## Consequências

Positivas:

- Nenhuma senha de administrador é lida do `.env` nem do ambiente do processo, que é o que a
  seção 4 de `docs/seguranca.md` pedia.
- O `.env` deixa de ter uma linha cuja presença, sozinha, transforma um arquivo de configuração
  em credencial.
- O entrypoint encolhe: some o único bloco dele que engolia código de saída, e com ele a
  necessidade de explicar por que `createsuperuser` pode falhar sem derrubar o boot.

Negativas:

- Um ambiente novo sobe sem conta administrativa nenhuma, e `docker compose up --wait` verde
  deixa de significar "pronto para usar". O `README.md` já traz o comando no arranque mínimo,
  mas quem automatizar o primeiro boot perde o gancho que tinha.
- A criação passa a exigir terminal interativo, o que não serve a provisionamento não
  supervisionado. Quem precisar disso terá de decidir outra coisa — e essa decisão não está
  tomada aqui.
- A senha continua digitada num host cujo modelo de ameaças admite "alguém com acesso ao host";
  o que a decisão remove é a persistência dela em arquivo, não a exposição a esse adversário.

## Alternativas consideradas

- **Manter as variáveis e documentar que devem ficar comentadas** — é o estado de hoje, custo
  zero. Descartada porque a proteção é disciplina de quem edita o `.env`, e o arquivo é
  untracked, sem revisão e sem cópia: ninguém vê o descomentar.
- **Ler a senha de um segredo montado em arquivo** — tiraria a senha do ambiente sem perder a
  automação. Descartada porque introduz o segundo caminho de leitura que a ADR 0011 recusou
  para a `DATABASE_URL` e que a ficha 2.3 de `docs/robustez-info.md` volta a recusar para a
  chave RSA, e porque a senha continuaria em arquivo — só que noutro.
- **Criar a conta por migração de dados com senha aleatória impressa no log** — dispensaria o
  passo manual. Descartada porque o log vai para o `stdout` do container, que é lido por
  qualquer `docker logs` e que a ADR 0013 justamente separou da trilha por não ser durável nem
  restrito.
