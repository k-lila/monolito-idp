# Implementação dos reforços — blocos e sequência

> **Estado: guia, não procedimento.** Os Blocos A, B e C estão implantados; o último item do C, a
> confirmação do issuer, fechou com a ADR 0025, que congela a forma `https://<PUBLIC_HOST>/o`. Para
> o que está implantado, `docs/receita.md` e `docs/runbook.md` já trazem o comando exato e o sinal
> de que deu certo. Do Bloco D em diante nada foi exercitado, e nenhum dos dois documentos cobre
> esses reforços. Cada bloco descreve o que entra junto, por que junto, o que quebra e como se sabe
> que terminou. Os fatos que sustentam cada agrupamento estão levantados em `docs/robustez-info.md`,
> e é lá que estão os `arquivo:linha` — com a ressalva da ficha 2.2, cuja linha "nenhuma ADR nova
> para o transporte" o Bloco C desmentiu com três.

`docs/robustez.md` diz **o que** reforçar. `docs/robustez-info.md` diz **o que é preciso saber
antes** de encostar em cada reforço. Este documento diz **com o que cada um vai junto e em que
ordem** — e por que a ordem não é livre. Ele não repete as fichas: cada bloco cita a ficha de
origem pelo número.

Os pontos vêm dos três inventários de `docs/robustez-info.md`: as quatorze fichas da seção 2,
os sete controles da seção 3 e os sete avisos do toolkit da seção 4.

## Como ler este documento

| A que pergunta você quer responder | Seção |
| --- | --- |
| Por que a ordem é essa, e não outra | [1](#1-as-três-regras-que-ordenam-tudo) |
| O que entra em cada bloco, e por que junto | [2](#2-os-oito-blocos) |
| Em que ordem, e o que pode andar em paralelo | [3](#3-a-sequência) |
| Por que meu ponto favorito não está em bloco nenhum | [4](#4-os-três-pontos-fora-de-bloco) |
| Em que bloco caiu o ponto que eu procuro | [5](#5-de-onde-veio-cada-ponto) |

---

## 1. As três regras que ordenam tudo

A sequência não sai da prioridade 🔴 🟡 ⚪ de `docs/robustez.md`. Sai de três regras, e cada uma
nasceu de um caso concreto deste repositório.

- **Decisão que encarece depois vem antes.** A escolha da chave de contagem do limitador de
  taxa é reversível hoje e cara depois: com o proxy de pé antes dela, o limitador conta o IP do
  proxy, a suíte continua verde e o defeito só aparece quando alguém tranca a tela de login
  para todo mundo. É o adiado de `.claude/memory/decisions.md`, e é a única ordem que o
  repositório já registrou por escrito.
- **Instrumento antes da mudança.** Os blocos seguintes mexem no boot e no transporte, que são
  as duas superfícies cujo defeito característico é silencioso. Hoje o log não tem marca de
  tempo, nível nem nome de logger, e recriar o container apaga o histórico. Diagnosticar um
  boot novo com o instrumento velho custa mais do que trocar o instrumento primeiro.
- **Quebra de contrato numa janela só.** Trocar a string do issuer, declarar tempo de vida de
  refresh token e publicar um conjunto de chaves são três mudanças que alcançam a relying party
  (RP), não só este repositório. Espalhadas, são três coordenações; agrupadas por vizinhança,
  são duas — e enquanto não houver RP integrada, custam zero. É o argumento mais forte para
  fazê-las cedo.

---

## 2. Os oito blocos

Cada bloco traz cinco campos. **Entra** é o conteúdo; **Por que junto** é o que os prende um ao
outro; **Quebra** é o que fica vermelho ou o que muda para terceiro; **Exige antes** é o
pré-requisito; **Pronto quando** é o critério observável de fim.

Teste é demanda do bloco, nunca subproduto: quem escreve teste neste projeto é o `tester`, e
quem escreve código e documento é o `writer`.

### Bloco A — Instrumento

**Entra.** As fatias 1 e 2 de `docs/gaps/observabilidade.md`: formatador de log em JSON,
identificador de requisição, log de acesso próprio e o logger de auditoria com os quatro sinais
(ficha 2.6).

**Por que junto.** As duas fatias compartilham o `LOGGING` e o middleware novo, e nenhuma das
duas custa dependência nem container. Separá-las significaria editar `config/settings.py` duas
vezes pela mesma razão.

**Quebra.** O boot de todo ambiente já montado, até que `AUDIT_LOG_PATH` entre no `.env`. A
variável não tem default no código, deliberadamente, e ausente ela derruba o processo na leitura
das settings nomeando a si mesma — o desenho herdado do precedente de
`docs/adr/0004-assinar-tokens-com-rs256-e-custodiar-a-chave-privada-no-ambiente.md`. Na jornada de
construção qualquer `manage.py` aborta, a suíte inclusive; no container, o `app` morre no boot. O
`.env` é untracked e não tem cópia, de modo que a linha entra à mão: o procedimento está no
`README.md`, em `docs/receita.md` e na seção 15 de `docs/runbook.md`. Fora disso, é acréscimo.

**Exige antes.** Nada. É o único bloco sem pré-requisito.

**Pronto quando.** Uma requisição qualquer produz linha JSON com marca de tempo, nível, nome de
logger e identificador de requisição; e um login bem-sucedido produz linha de auditoria
nomeando quem autenticou e qual RP recebeu token.

### Bloco B — A chave de contagem

**Entra.** Limitação de taxa em `/accounts/login/`, `/o/token/` e `/o/authorize/` (ficha 2.1),
e com ela a decisão de como o cliente é identificado atrás de um proxy.

**Por que junto.** O limitador e a chave de contagem são a mesma decisão: escolher a biblioteca
sem escolher a chave é adiar a metade que não emite sinal. E o toolkit não traz limitação
nenhuma, de modo que a tela de login e os dois endpoints de `/o/` precisam de mecanismos
distintos decididos na mesma conversa.

**Quebra.** `tests/test_login_view.py` espera 200 com `errorlist` no corpo, e a resposta de
bloqueio não é isso. Um teto por IP nos endpoints de `/o/` encosta nos cinco `POST` de
authorize e nos dois de token que `tests/oauth_helpers.py` dispara sem espera. Se o contador
for para o cache, ele não volta com o rollback do `TestCase` e a suíte fica dependente de
ordem.

**Exige antes.** ADR (Architecture Decision Record) nova, com três escolhas: biblioteca, chave
de contagem e backend do contador. Mais a primeira declaração de `AUTHENTICATION_BACKENDS` na
história do projeto, que precisa manter o backend padrão do Django ao lado do novo.

**Pronto quando.** Tentativas em excesso são barradas por conta e por origem, e a suíte está
verde com os testes ajustados. `manage.py check` não serve de critério: os checks do axes são
`Warning`, e o comando os imprime saindo com código zero — só reprovam com
`--fail-level WARNING`.

### Bloco C — A fronteira

**Entra.** Terminação TLS (Transport Layer Security) com proxy à frente e a confirmação da string do
issuer (ficha 2.2) — fechada pela ADR 0025, que congela a forma e deixa o nome fora do repositório;
`requirepass` no Redis, com o healthcheck corrigido; criação de superusuário fora do `.env`; `USER`
dedicado no container, com posse de `/app/staticfiles` (metade da ficha 2.13); e a publicação da
porta só pelo proxy.

**Por que junto.** É a fronteira que `docs/seguranca.md` já nomeia: o conjunto do que muda
quando o bind em loopback deixa de ser a barreira. Cada item de fora dessa lista é inofensivo
enquanto o serviço só responde ao próprio host, e todos deixam de ser no mesmo instante. O
`USER` dedicado entra aqui e não no bloco G porque é o próprio `Dockerfile` que marca a revisão
para a primeira exposição, e porque sozinho ele não exige mexer no boot: basta dar posse do
diretório de estáticos ao usuário que roda o `collectstatic`.

**Quebra.** Dois testes fixam o issuer por igualdade literal e ficam vermelhos com o `BASE_URL`
novo. Para as RPs, a claim `iss` muda, e `docs/integracao-rp.md` promete comparação por
igualdade exata de string.

**Exige antes.** O bloco B, pela primeira regra da seção 1. E uma decisão de qual será a string
definitiva do issuer, que `docs/seguranca.md` já pede que seja tomada antes de a primeira RP
integrar. E mais uma, que a ADR 0015 impõe a este bloco: ligar `BEHIND_TLS_PROXY` muda, na
mesma tecla, a semântica do campo `ip` da trilha de auditoria e a chave do limitador de taxa. A
trilha é um arquivo append-only, e nada na linha distingue as duas populações, porque o
instante da troca não fica gravado — **este bloco não pode ligar a variável sem antes decidir o
versionamento da linha da trilha**.

**Pronto quando.** O IdP (Identity Provider) responde pelo proxy em HTTPS e o container
continua `healthy`, com `127.0.0.1` ainda em `ALLOWED_HOSTS`; a descoberta publica o issuer
novo; o healthcheck do Redis compara a saída com `PONG` em vez de confiar no código de saída; e
o processo dentro do container não é `root`.

**O que este bloco deixou para depois, e como fechou.** A forma do issuer é `https://<nome
público>/o`, fixada pela ADR 0017; a string ficou em aberto, porque o nome público é valor de
implantação. A ADR 0025 fechou o item: congela a forma `https://<PUBLIC_HOST>/o` e deixa o nome fora
do repositório, só no `.env` da instância e no painel da Vercel.

### Bloco D — Conformidade do servidor de autorização

**Entra.** Os sete avisos da RFC 9700 que o `manage.py check --deploy` emite hoje; a declaração
de `REFRESH_TOKEN_EXPIRE_SECONDS` e o agendamento de `cleartokens` e `clearsessions`
(ficha 2.8); e a restrição de quem pode registrar Application.

**Por que junto.** Os três são o mesmo assunto visto de três ângulos, e dois deles se anulam se
forem separados. Ligar a detecção de reuso de refresh token sem declarar a expiração faz o
`cleartokens` parar de recolher até os revogados, isto é, piora a limpeza em nome da
conformidade. E dois dos avisos — grant implícito e grant de senha — só são alcançáveis porque
o formulário de registro de Application é público para quem tem conta: desligar os grants sem
fechar o registro trata o sintoma, e fechar o registro sem desligar os grants deixa a porta
destrancada para quem já tem aplicação registrada.

**Quebra.** Declarar tempo de vida de refresh token muda a tabela que
`docs/integracao-rp.md` promete, e nenhum teste cobre expiração — a suíte não vai avisar.
Proibir `redirect_uri` em `http` bloqueia também o retorno em `127.0.0.1` de aplicação nativa,
permitido pela RFC 8252. Guardar token com digest alcança as linhas já gravadas.

**Exige antes.** O bloco C, porque proibir `redirect_uri` em texto claro só faz sentido depois
que o próprio IdP fala HTTPS. E ADR, porque tempo de vida de token é contrato com a RP.

**Pronto quando.** `manage.py check --deploy` não emite mais nenhum aviso do toolkit, o
`cleartokens` remove linhas de verdade em vez de sair no modo degradado, e uma conta comum não
consegue registrar aplicação com grant depreciado.

### Bloco E — Custódia e rotação da chave

**Entra.** Tirar a `OIDC_RSA_PRIVATE_KEY` do `.env` para um segredo montado (ficha 2.3) e
publicar conjunto de rotação com chave ativa e chaves inativas (ficha 2.11).

**Por que junto.** Os dois mexem no mesmo caminho de leitura, na mesma variável e no mesmo
script de geração, e os dois contrariam a mesma ADR aceita. Separados, são duas emendas à
ADR 0004 e duas passagens pelo trecho de settings que monta a chave; juntos, são uma decisão só
sobre como a chave entra no processo e quantas entram.

**Quebra.** Dois testes fixam o formato de chave única: um afirma que o conjunto publicado tem
exatamente uma chave, o outro amarra o `kid` do cabeçalho do `id_token` à primeira chave da
lista, que deixa de ser determinística. Para as RPs, a rotação com sobreposição é melhoria (é
justamente ela que elimina a janela de dano descrita em `docs/runbook.md`), mas muda o que
`docs/integracao-rp.md` afirma hoje sobre não haver conjunto.

**Exige antes.** Emenda à ADR 0004, cobrindo custódia e conjunto numa peça só.

**Pronto quando.** O JWKS (JSON Web Key Set) publica duas chaves com identificadores distintos,
um `id_token` novo verifica contra a ativa, um emitido antes da troca ainda verifica contra a
inativa, e a chave privada não está mais no `.env`.

### Bloco F — Durabilidade

**Entra.** Backup e restore ensaiados do Postgres, e o segredo junto (ficha 2.4).

**Por que junto com nada, mas depois de E.** O que precisa de cópia não é só o banco: é o par
banco mais segredo. Enquanto a chave morar no `.env`, o procedimento de cópia é um; depois do
bloco E, é outro. Escrever o procedimento antes de E significa escrevê-lo duas vezes.

**Quebra.** Nada no código.

**Exige antes.** O bloco E, pela razão acima.

**Pronto quando.** Um restore ensaiado — não o backup, o restore — sobe um IdP que assina com a
mesma chave e responde à descoberta com o mesmo issuer que o original.

### Bloco G — Boot e imagem endurecida

**Entra.** Tirar a migração do boot, com passo de release dedicado (ficha 2.5); mover o
`collectstatic` para o build; sistema de arquivos read-only e descarte de capabilities (a outra
metade da ficha 2.13).

**Por que junto.** As três mudanças são a mesma: retirar do boot tudo o que escreve. O
`collectstatic` sai porque o sistema de arquivos read-only não o admite, e a migração sai
porque é passo de release. Feitas em separado, são duas reestruturações do
`docker/entrypoint.sh` e duas rededuções do `start-period` do healthcheck, que hoje está
dimensionado para cobrir exatamente esses dois comandos.

**Quebra.** Nenhum teste, e é esse o risco: o `docker/entrypoint.sh` não tem cobertura nenhuma,
e este é o bloco que mais mexe nele.

**Exige antes.** Emenda à ADR 0006, que registra a réplica única como premissa da migração no
boot. E o bloco C, que já terá tocado o compose e o `Dockerfile` — fazer os dois ao mesmo tempo
é colidir no mesmo arquivo por razões diferentes.

**Pronto quando.** `docker compose up --wait` fica verde com o app subindo já migrado, o
container roda com o sistema de arquivos travado, e a migração é um passo que se vê no log
separado do passo que sobe o servidor.

### Bloco H — O pipeline e o gate

**Entra.** O ambiente de integração contínua rodando a suíte; varredura de dependências e de
imagem, com o pin das transitivas que hoje divergem entre o `requirements.txt` e o que a imagem
embarca (ficha 2.12); e o `manage.py check --deploy` como gate (ficha 2.14).

**Por que junto, e por que em dois tempos.** O gate precisa de um lugar para rodar, e esse
lugar é o pipeline — mas os dois **não** são o mesmo passo, e é isso que a tabela de
`docs/robustez.md` esconde ao pôr um em 🟡 e o outro em ⚪. O pipeline pode existir desde cedo e
só ganha valor quanto mais cedo existir. O gate, não: ligado hoje, ele reprova por onze avisos,
sete dos quais só o bloco D resolve e quatro dos quais o bloco C resolve **apenas onde
`BEHIND_TLS_PROXY` é verdadeira**. Gate vermelho no primeiro dia é gate desligado no segundo.

**Onde o gate roda é parte do gate.** `BEHIND_TLS_PROXY=True` é ligada num lugar só — o
`environment:` do serviço `app`, no `docker-compose.yml` (ADR 0017) —, de modo que os quatro
avisos de transporte somem em `docker compose exec app`, e só ali. Rodado na jornada de
construção, ou por um ambiente de integração contínua que leia um `.env` no formato do
`.env.example` (que sai com `BEHIND_TLS_PROXY=False`), o comando continua emitindo
`security.W004`, `W008`, `W012` e `W016` depois de o bloco C ter fechado. Quem montar o gate
sobre a premissa de que o C os resolveu descobre isso no primeiro vermelho.

**Quebra.** Nada.

**Exige antes.** O pipeline, nada. O gate, os blocos C e D.

**Pronto quando.** O pipeline roda a suíte com Postgres e Redis de pé a cada push; a varredura
mira a imagem construída, e não só o arquivo de requisitos; e `manage.py check --deploy
--fail-level WARNING` sai com código zero **dentro do container**, que é o único ambiente em
que a fronteira de transporte está ligada.

---

## 3. A sequência

```
A ──> B ──> C ──┬──> D ──> H(gate)     A, B e C implantados
                └──> G

E ──> F                      a partir de A, sem esperar por B nem por C
H(pipeline)                  a partir de A
```

O caminho crítico era `A → B → C`, e as três razões estão na seção 1. Com os três implantados,
o que resta são frentes que não dependem umas das outras — e `G` perdeu a única restrição que
tinha, porque o compose e o `Dockerfile` que ele disputava com `C` já foram editados:

| Frente | Pode andar em paralelo com | Não pode, e por quê |
| --- | --- | --- |
| D — Conformidade | E, F, G | — |
| E → F — Chave e durabilidade | tudo, desde A | F depende de E: o que se copia muda com a custódia |
| G — Boot e imagem | D, E, F | — (a colisão era com C, já implantado) |
| H — pipeline | tudo, desde A | O **gate** espera C e D |

Uma observação sobre D e E, que são os dois blocos que alcançam terceiro. Se houver RP
próxima de integrar, E sobe na fila e D vem imediatamente depois de C, porque as duas mudanças
ficam mais caras depois da primeira integração. Se não houver, a ordem entre eles é
indiferente, e vale começar pelo que tiver a ADR mais fácil de escrever.

---

## 4. Os três pontos fora de bloco

Não entram na sequência porque o gatilho deles não é a conclusão de outro bloco: é uma
condição que o projeto ainda não tem.

- **Liveness e readiness separados (ficha 2.7).** O gatilho é passar a existir um orquestrador
  que aja sobre o veredito. Hoje `unhealthy` não reinicia nada, e a separação acrescentaria uma
  rota que precisa entrar na isenção de redirecionamento para HTTPS sem ninguém para consumir a
  distinção. Quando entrar, entra com a rota de métricas da fatia 3 de
  `docs/gaps/observabilidade.md`, que tem exatamente o mesmo requisito.
- **Pool de conexões (ficha 2.10).** O gatilho é a escala, que só o bloco G destrava. Antes
  disso são três workers síncronos contra um limite de cem conexões. E a mudança invalida a
  premissa de uma ADR aceita, o que é caro demais para um evento que não se materializa.
- **Tuning do gunicorn (ficha 2.9).** O gatilho é uma medição que ainda não existe: sem o
  bloco A não há como saber se algum worker vaza memória ou trava. Quando houver, entra junto
  com a fatia 3 de `docs/gaps/observabilidade.md`, que já prevê o mesmo arquivo de configuração
  do gunicorn.

Os três esperam por coisas diferentes: o primeiro por um orquestrador, o segundo pela escala
que o bloco G destrava, o terceiro pela medição que o bloco A produz. Nenhum dos três espera
por decisão de pessoa, e é isso que os tira da sequência em vez de pô-los no fim dela.

---

## 5. De onde veio cada ponto

| Ponto, em `docs/robustez-info.md` | Bloco |
| --- | --- |
| 2.1 Rate limiting | B |
| 2.2 Terminação TLS, e o issuer | C |
| 2.3 Custódia da chave | E |
| 2.4 Backup e restore | F |
| 2.5 Separar a migração do boot | G |
| 2.6 Erro rastreado e auditoria | A |
| 2.7 Liveness e readiness | fora de bloco |
| 2.8 `cleartokens` e `clearsessions` | D |
| 2.9 Tuning do gunicorn | fora de bloco |
| 2.10 Pool de conexões | fora de bloco |
| 2.11 Rotação de chave | E |
| 2.12 CI/CD e varredura | H, primeiro tempo |
| 2.13 Container endurecido | dividido: `USER` em C, read-only em G |
| 2.14 Gate do `check --deploy` | H, segundo tempo |
| Seção 3 — Redis sem `requirepass` | C |
| Seção 3 — superusuário fora do `.env` | C |
| Seção 3 — pin das transitivas | H, primeiro tempo |
| Seção 3 — restrição do registro de Application | D |
| Seção 3 — confirmação do issuer | C, e é a única linha do bloco que não fechou |
| Seção 3 — `email_verified` e revogação | nenhum: é contrato, e não robustez |
| Seção 3 — posição do `CorsMiddleware` | B, que acrescenta middleware à mesma lista |
| Seção 4 — os sete avisos da RFC 9700 | D |

Duas linhas dessa tabela merecem explicação. A ficha 2.13 é o único ponto **dividido**: o
`USER` dedicado é da fronteira e o sistema de arquivos read-only é da reestruturação do boot,
e tratá-los como um item só obrigaria a adiantar o segundo ou atrasar o primeiro. E
`email_verified` com revogação efetiva não é reforço de robustez: é ampliação do contrato com a
RP, e o dono desse assunto é `docs/integracao-rp.md`.

---

## 6. O que este guia não decide

Não decide **se** algum bloco será feito, nem quando. Não escolhe a biblioteca do bloco B, o
proxy do bloco C, nem a forma de custódia do bloco E: as opções e o custo de cada uma estão nas
fichas de `docs/robustez-info.md`, e a escolha é de ADR, não de guia. Não escreve nenhuma das
quatro ADRs que a sequência exige — uma nova no bloco B, emendas à 0004 no E, à 0006 no G e à
0011 se o pool sair de fora de bloco. E não é procedimento: quando um bloco for executado, o
comando e o sinal de que deu certo entram em `docs/receita.md`, e o que fazer quando falhar
entra em `docs/runbook.md`.

A sequência aqui é derivada, não convencionada: cada seta da seção 3 tem uma razão escrita, e
uma razão que deixe de valer desfaz a seta. Se a premissa mudar (uma RP integrando antes do
previsto, uma segunda réplica, um incidente), a ordem se recalcula a partir das três regras da
seção 1, não deste desenho.
