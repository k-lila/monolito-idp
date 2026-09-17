# 0017. Terminar o TLS num proxy declarado no compose e publicar só ele

## Status

Aceito — 2026-09-13

## Contexto

A ADR (Architecture Decision Record) 0006 empacotou o IdP (Identity Provider) como container
único e decidiu que "TLS (Transport Layer Security) é responsabilidade de um proxy à frente,
fora deste escopo". Descartou por escrito a alternativa "Proxy TLS no compose", e a razão foi
de estágio: acrescentaria certificado e configuração "num estágio em que o objetivo é
demonstrar o fluxo OIDC (OpenID Connect)". O objetivo mudou. O Bloco C de
`docs/implementacao-robustez.md` é a fronteira — o conjunto do que muda quando o bind em
loopback deixa de ser a única barreira —, e ele não tem o que demonstrar se o proxy não
existir em lugar nenhum que este repositório alcance.

Quatro fatos do terreno decidem o desenho.

O primeiro é uma armadilha que nenhum documento do projeto catalogava antes da ficha 2.2 de
`docs/robustez-info.md`: `SECURE_PROXY_SSL_HEADER` faz o Django confiar em
`X-Forwarded-Proto` **de qualquer origem**. Enquanto a porta do serviço `app` for alcançável,
um cliente desliga o redirecionamento para HTTPS escrevendo um cabeçalho. O proxy tem de ser o
único caminho até aquela porta, e isso é propriedade de topologia, não de configuração da
aplicação.

O segundo está registrado como consequência negativa da própria ADR 0006: a segunda condição
para o container continuar `healthy` sob TLS — `ALLOWED_HOSTS` seguir listando `127.0.0.1` —
"não tem mecanismo nenhum e vive só no README".

O terceiro é da ADR 0015, que concentrou a leitura de origem num ponto único e registrou como
negativa que "o ramo de proxy é código que não roda no ambiente atual", exercitado só por
`override_settings`, de modo que "o proxy de verdade pode escrever o cabeçalho de outro jeito".
O literal `TRUSTED_PROXY_COUNT = 1` é, nas palavras daquela ADR, "um número que ninguém pode
conferir hoje".

O quarto é do repositório: há duas jornadas, elas leem o mesmo `.env`, e o `docker-compose.yml`
já sobrescreve três variáveis — `DATABASE_URL`, `REDIS_URL` e `AUDIT_LOG_PATH` — porque o valor
da jornada de construção não serve dentro do container. O endurecimento de transporte tem
exatamente essa forma: faz sentido atrás do proxy e não faz sentido no `runserver` do host, que
fala texto claro.

Some-se a restrição de que o nome público é valor de implantação, e não literal de
repositório: ele vive no `.env`, que é untracked.

## Decisão

Vamos declarar o proxy de terminação TLS como um serviço do `docker-compose.yml`, torná-lo o
único serviço com porta publicada, e derivar de uma única variável de implantação o nome que
ele atende e as três variáveis de fronteira da aplicação.

**O serviço.** `proxy`, imagem `caddy:2`, com `docker/Caddyfile` montado somente-leitura e dois
volumes nomeados. O Caddyfile não traz literal de host: o nome vem por placeholder de ambiente.
O certificado sai da autoridade certificadora interna do Caddy por default, guardada em volume
nomeado para não ser regerada a cada `up`. Trocar isso por um certificado de verdade é trocar
uma diretiva.

**A publicação.** O serviço `app` perde o bloco `ports:` inteiro. Quem publica é o `proxy`, em
`127.0.0.1:80` e `127.0.0.1:443`, pelo mesmo argumento de DNAT que já governa as outras
publicações. Expor fora de loopback é **editar esse endereço à mão**, e não ligar uma variável:
exposição é decisão, e uma variável convida a flipá-la sem decidir.

**A variável.** `PUBLIC_HOST`, no `.env`, lida pelo compose e nunca por `config/settings.py`.
Dela saem o nome que o Caddyfile atende e as três sobrescritas do serviço `app`:
`BASE_URL=https://${PUBLIC_HOST}`, `ALLOWED_HOSTS=${PUBLIC_HOST},127.0.0.1` e
`BEHIND_TLS_PROXY=True`. Ausente, `${PUBLIC_HOST:?}` aborta o `up` nomeando a variável — o
precedente da ADR 0004 aplicado ao compose. O endurecimento passa a ser, portanto, propriedade
da jornada de container; o `.env` continua carregando os valores da jornada de construção.

**O que não muda.** `config/settings.py` não recebe uma linha. A fronteira inteira cabe em
variáveis que ele já lê, e o issuer continua sendo `{BASE_URL}/o` como a ADR 0007 fixou.

**Relação com a ADR 0006.** Esta decisão emenda a alínea "TLS é responsabilidade de um proxy à
frente, fora deste escopo" e adota a alternativa que aquela ADR descartou. Não a substitui: o
container único, o entrypoint, a réplica única e o endurecimento por variável dedicada seguem
valendo. A ADR 0006 não é editada.

## Consequências

Positivas:

- A fronteira passa a ser exercitável a partir de um clone. Descoberta sob o issuer
  definitivo, fluxo completo por HTTPS, sonda verde e cookie `Secure` deixam de ser promessa de
  documento e passam a ser coisa que se roda.
- "O proxy é o único caminho" vira propriedade estrutural: sem `ports:` no `app`, não existe
  por onde um cliente escrever `X-Forwarded-Proto` e receber resposta da aplicação.
- `127.0.0.1` em `ALLOWED_HOSTS` deixa de depender de alguém lembrar do README: é o compose que
  o compõe, junto do nome público, na mesma linha.
- O ramo de proxy de `config/origem.py` passa a ser atravessado por um proxy de verdade, e
  `TRUSTED_PROXY_COUNT = 1` passa a ser conferível — era a negativa mais aguda da ADR 0015.
- O nome público aparece uma vez só, numa variável do `.env`. Nenhum arquivo versionado
  aprende o host, exceto o exemplo de `.env.example`.
- A premissa "portas publicadas em `127.0.0.1`" do `README.md` continua verdadeira. Este bloco
  constrói a fronteira; não realiza a exposição.

Negativas:

- Contraria a ADR 0006 na alínea do escopo, e o custo que ela previu é real: uma peça a mais no
  compose, uma imagem a mais, dois volumes a mais e um arquivo de configuração de terceiro a
  manter.
- A jornada de construção passa a ser a única que não exercita o endurecimento — e é a que o
  desenvolvedor usa todo dia. É incoerência deliberada, pelo mesmo argumento com que o compose
  já sobrescreve três variáveis, mas é uma divergência entre jornadas que ninguém verifica.
- `docker compose down -v` passa a destruir também a autoridade certificadora local, junto de
  `pgdata`, `redisdata` e `auditlog`. Quem confiou no certificado no navegador terá de confiar
  de novo.
- HSTS (HTTP Strict Transport Security) de um ano passa a valer para o nome configurado assim
  que alguém o visitar por navegador. `SECURE_HSTS_SECONDS` já era 31536000 sob
  `BEHIND_TLS_PROXY`; o que muda é que agora há um nome que recebe a marca. Sem
  `includeSubDomains` e sem `preload`, o estrago fica contido em um nome — mas trocar de nome
  depois exige limpar o estado de HSTS de cada navegador que visitou o anterior.
- **A porta publicada em loopback passa pelo proxy de userland do Docker, que reescreve o
  endereço de origem.** Requisições vindas do host chegam ao Caddy com o endereço do gateway da
  bridge, e não com o endereço real: `X-Forwarded-For` traz um valor só para todos, o campo
  `ip` da trilha colapsa e a chave do limitador de taxa também. É a falha que a ADR 0015 existe
  para impedir, reaparecendo por caminho de rede em vez de por caminho de código. Sob exposição
  real, com publicação fora de loopback, o DNAT preserva a origem e o defeito não ocorre — o
  que significa que ele existe justamente no modo em que se vai verificar.
- A suíte na jornada de container passa a rodar com `SECURE_SSL_REDIRECT` ligado, o que devolve
  301 a toda requisição do test client. O executor de testes precisa neutralizar a chave, e
  isso é um terceiro valor de produção que só a suíte vê.
- Um sexto contêiner a subir alonga o `docker compose up --wait`.

## Alternativas consideradas

- **Manter o proxy fora do repositório, como a ADR 0006 decidiu** — é o que honra a ADR aceita
  ao pé da letra e não custa peça nenhuma. Descartada porque cinco dos doze critérios de aceite
  deste bloco não teriam onde ser exercitados: a fronteira ficaria descrita e não construída,
  e o repositório continuaria provando contra o documento que descreve o código em vez de
  contra o código, que é o que o `CLAUDE.md` proíbe.
- **Publicar a porta do `app` junto com a do proxy, "só para depurar"** — preservaria o
  `curl http://localhost:8000/...` de toda a documentação. Descartada porque é literalmente a
  terceira armadilha da ficha 2.2: com a porta alcançável, qualquer cliente do host desliga o
  redirecionamento para HTTPS escrevendo um cabeçalho.
- **Pôr `BASE_URL`, `ALLOWED_HOSTS` e `BEHIND_TLS_PROXY` no `.env`, e não no compose** — daria
  uma configuração só para as duas jornadas, que é o que o docstring de `config/settings.py`
  defende. Descartada porque quebraria a jornada de construção de um jeito confuso: o
  `runserver` passaria a devolver 301 para o nome público, que é servido pelo container, e o
  desenvolvedor veria em pé o código que não editou.
- **`nginx` com certificado gerado por script** — é a peça mais conhecida e não traz automação
  de certificado nenhuma para desligar. Descartada porque acrescenta um script de geração e um
  arquivo de configuração maior, e porque esquecer `proxy_set_header X-Forwarded-Proto` é
  defeito comum; a economia de uma dependência não paga.
- **Uma variável para o endereço de publicação do proxy** — tornaria a exposição um passo de
  configuração. Descartada de propósito: a primeira exposição é a decisão que este bloco
  inteiro existe para preparar, e não deve caber num valor de ambiente.
