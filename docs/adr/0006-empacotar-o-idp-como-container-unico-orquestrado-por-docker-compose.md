# 0006. Empacotar o IdP como container único orquestrado por docker-compose

## Status

Aceito — 2026-08-29

## Contexto

O sistema é um monólito deliberado: telas de login, servidor de autorização, admin e modelo de
identidade vivem no mesmo processo, com uma fronteira de segurança só. O empacotamento precisa
refletir essa escolha em vez de contrariá-la.

Quatro exigências operacionais acompanham essa forma. As migrations precisam estar aplicadas
antes do primeiro request, incluindo as tabelas do django-oauth-toolkit, sem as quais nenhum
fluxo funciona. Os arquivos estáticos das telas de login precisam ser servidos de verdade,
porque uma tela de credencial sem CSS é uma tela em que ninguém confia. O orquestrador precisa
de um sinal honesto de prontidão. E o container precisa ser observável: um IdP (Identity
Provider) cujos erros não aparecem no log é um IdP que falha em silêncio, o que é justamente o
modo de falha característico deste domínio.

Duas armadilhas do Django merecem registro porque o ambiente do compose as ativa por default. A
primeira: atrelar cookies seguros e HSTS (HTTP Strict Transport Security) ao valor de DEBUG faz
a aplicação descartar o cookie de sessão quando ela roda sem TLS (Transport Layer Security), e
o login passa a falhar com 302 silencioso, sem erro em lugar nenhum. DEBUG é variável sobre
diagnóstico; cookie seguro depende de transporte. A segunda: o DEFAULT_LOGGING do Django prende
o handler de console ao filtro require_debug_true e roteia erro de django.request para
mail_admins. Com DEBUG=False e sem e-mail configurado, um 500 no endpoint de token simplesmente
desaparece.

Há ainda o risco de boot: entrypoint que roda migration sem cuidado executa migrations
concorrentes se houver mais de uma réplica.

## Decisão

Vamos empacotar a aplicação como um único container, construído por Dockerfile multi-stage,
servido por Gunicorn (WSGI, Web Server Gateway Interface) com WhiteNoise para arquivos
estáticos, e orquestrá-la com docker-compose ao lado de PostgreSQL 17 e Redis 7.

O boot é responsabilidade de um entrypoint que executa migrate, collectstatic e a criação
condicional de superusuário antes de fazer exec no Gunicorn. collectstatic roda em runtime, não
no build, para que as settings nunca precisem importar sem ambiente durante a construção da
imagem.

A espera pelas dependências é do compose, via depends_on com condition: service_healthy sobre
healthchecks de Postgres e Redis — não via laço de polling no shell. A aplicação expõe /health,
que verifica banco e cache de verdade e serve de healthcheck do próprio serviço; o healthcheck
é executado pelo interpretador Python que já está na imagem, via urllib da stdlib, porque
imagens slim não trazem curl nem wget e instalar um cliente HTTP só para isso é engordar a
imagem por um contrato que a stdlib já cumpre.

Contra as duas armadilhas: o endurecimento de transporte (cookies seguros, HSTS, redirect para
HTTPS, SECURE_PROXY_SSL_HEADER) é governado por uma variável própria, BEHIND_TLS_PROXY, e nunca
por DEBUG; e as settings trazem um bloco LOGGING explícito que manda tudo para stdout
independentemente de DEBUG, sem require_debug_true e sem mail_admins. O .env.example sai com
DEBUG=False e BEHIND_TLS_PROXY=False, de modo que o ambiente que sobe por default é o de
diagnóstico endurecido e mesmo assim o fluxo fecha sobre http em localhost.

O compose declara uma réplica da aplicação. TLS é responsabilidade de um proxy à frente, fora
deste escopo — e é exatamente por isso que o endurecimento é opt-in por variável.

## Consequências

Positivas:

- Uma unidade implantável, uma fronteira de segurança, um lugar para olhar quando algo falha.
- O ambiente inteiro sobe reprodutível com um comando, o que torna o fluxo OIDC (OpenID
  Connect) demonstrável de ponta a ponta sem preparação manual.
- Ordem de boot determinística: nenhum request chega antes das migrations.
- Há uma configuração só, e não um "modo de desenvolvimento" separado que nunca é exercitado: o
  compose executa o mesmo caminho de código que se pretende usar depois. O ganho vem de haver
  um único módulo de settings, não do arranjo inteiro — o endurecimento de transporte é opt-in
  e fica de fora, conforme a última Negativa.
- Logs de erro aparecem em docker logs desde o primeiro boot, o que importa num sistema cujos
  modos de falha característicos são silenciosos.
- O healthcheck funciona na imagem enxuta sem dependência adicional.
- WhiteNoise elimina a necessidade de Nginx no MVP (Minimum Viable Product) sem abrir mão de
  estáticos reais.

Negativas:

- Migrations no entrypoint só são seguras com uma réplica. Escalar horizontalmente sem antes
  separar a migração do boot causa migrations concorrentes — dívida contratada conscientemente,
  com vencimento no dia em que houver pressa para escalar.
- BEHIND_TLS_PROXY é uma variável a mais e um erro a mais possível: deixá-la em False atrás de
  um proxy real significa cookies sem flag Secure em produção, sem nenhum aviso.
- docker-compose é ferramenta de host único: não é o modelo de produção real e precisará ser
  substituído se o projeto sair do sandbox.
- Gunicorn é síncrono e não termina TLS; um proxy é obrigatório em qualquer uso real, já que
  tudo num IdP trafega sob HTTPS.
- Estado (Postgres, Redis) em containers exige disciplina de volumes e backup que o compose não
  impõe.
- WhiteNoise concentra no app a entrega de estáticos e não escala para tráfego alto.
- collectstatic em runtime alonga o tempo de boot.
- Log em stdout sem coleta externa some quando o container é recriado.
- O endurecimento de transporte é a parte desta decisão que o compose não exercita: ele sobe
  com BEHIND_TLS_PROXY=False, e foi ligar a variável que revelou que a probe interna do
  HEALTHCHECK recebe 301 do SecurityMiddleware e morre no handshake TLS contra um Gunicorn em
  texto claro — container eternamente unhealthy com a aplicação atendendo normalmente. A
  isenção que fecha isso está na ADR (Architecture Decision Record) 0010. A segunda condição,
  ALLOWED_HOSTS continuar listando 127.0.0.1, não tem mecanismo nenhum e vive só no README.

## Alternativas consideradas

- **Serviços separados (auth server, telas, API — Application Programming Interface)** —
  fronteiras mais claras a longo prazo, mas multiplicaria deploys, latência e superfícies de
  segurança para um sistema que cabe inteiro num processo. Contraria a escolha de monólito.
- **Endurecimento atrelado a DEBUG** — uma variável a menos, e é o que a maioria dos tutoriais
  faz. Descartado porque acopla duas dimensões independentes e produz o pior modo de falha
  possível neste projeto: login que não funciona sem erro visível.
- **Proxy TLS no compose** — mais próximo de produção e dispensaria BEHIND_TLS_PROXY, mas
  acrescenta certificado, configuração e uma peça a manter num estágio em que o objetivo é
  demonstrar o fluxo OIDC.
- **Migration como job separado do boot** — o que se deve fazer ao escalar, mas hoje
  acrescentaria orquestração sem nenhuma réplica extra para justificá-la.
- **curl na imagem para o healthcheck** — trivial de escrever, mas engorda a imagem e falha de
  forma confusa (serviço unhealthy para sempre, com a aplicação funcionando) se alguém trocar a
  imagem base por uma sem ele.
- **Uvicorn/ASGI (Asynchronous Server Gateway Interface)** — abriria caminho para async, mas o
  Django 5.2 aqui é síncrono e nenhum endpoint do fluxo se beneficiaria.
