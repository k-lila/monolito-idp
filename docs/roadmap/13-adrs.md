# Passo 13 — ADRs

## Objetivo

Reunir, prontas para gravação, as sete ADRs de fundação que registram as decisões tomadas
nesta rota.

## Depende de

Nada em termos de execução: as ADRs registram decisões já tomadas, não decisões a tomar.
Ficam por último na ordem porque a implementação as confirma; se algum passo tivesse
contrariado uma delas, o texto teria de ser revisto antes da gravação.

## Aviso — gravar é trabalho de outra fase

**Esta fase não escreve nada em `docs/adr/`.** O diretório não é tocado aqui. Os sete
textos abaixo são o conteúdo a ser gravado quando a fase de implementação chegar a este
passo, e cada bloco já vem com o nome exato do arquivo de destino.

## Como gravar

- Um arquivo por ADR, com o nome de destino indicado acima de cada bloco, seguindo
  `docs/adr/NNNN-slug-em-kebab-case.md`.
- **Reproduzir o texto como está.** As ADRs foram redigidas pelo `architect`; quem grava,
  grava — não reescreve, não resume, não reordena.
- Cada bloco abaixo está delimitado por uma cerca de código apenas para preservar o texto
  intacto. O conteúdo do arquivo é o que está **dentro** da cerca, sem ela.
- Formato conforme `docs/adr/template-adr.md`. Os textos já o seguem.
- **ADR aceita é imutável.** Decisão que mudar vira ADR nova, e a antiga recebe status
  `Substituído por ADR-NNNN` — essa troca de status é a única edição permitida nela.

## Proibições que incidem aqui

- **Não reescrever, resumir nem "melhorar" o texto de nenhuma ADR.** O valor de uma ADR
  está em registrar a decisão como ela foi tomada, com as negativas que quem decidiu
  reconheceu.
- **Não editar uma ADR já gravada.** Ver imutabilidade, acima.
- **Não acrescentar ADR nova nesta fase.** As sete cobrem as decisões desta rota; decisão
  nova exige quem a decida.

## Riscos e sinais

- **ADR reescrita na gravação** — sinal: nenhum automático. A perda é silenciosa e só
  aparece meses depois, quando alguém procura a razão de uma escolha e encontra uma
  paráfrase sem as negativas.
- **ADR não gravada** — sinal: nenhum. As decisões continuam valendo no código e sem
  registro; a próxima pessoa lê o código e supõe que foi acidente.

## Passo concluído quando

Os onze arquivos existem em `docs/adr/`, com os nomes indicados. As ADRs 0001 a 0007 vêm dos
blocos deste documento; as 0008 a 0011 não estão aqui: foram redigidas nos blocos E e F, e o
texto de origem delas está em `.claude/memory/decisions.md`.

Sete ADRs foram alteradas antes da gravação, com autorização explícita do usuário: 0002,
0004, 0005, 0006, 0008, 0009 e 0011. As alterações corrigem afirmações que a implementação
falsificou. Para 0002, 0004, 0005 e 0006 os blocos deste documento foram atualizados no mesmo
movimento, e as duas cópias voltaram a coincidir; para 0008, 0009 e 0011 não há segunda cópia
a sincronizar, porque a origem é o arquivo de memória.

Cada ADR gravada ganha uma linha no índice de `.claude/memory/decisions.md` — isso é
procedimento do orquestrador.

---

## As sete ADRs

### Destino: `docs/adr/0001-adotar-django-5-2-lts-sobre-python-3-14.md`

A plataforma: Django 5.2 LTS sobre Python 3.14, com a contrapartida de não usar recurso exclusivo da série. Incide nos passos 01 e 11.

```markdown
# 0001. Adotar Django 5.2 LTS sobre Python 3.14 como plataforma do monólito

## Status

Aceito — 2026-08-29

## Contexto

O produto é um Identity Provider que renderiza as próprias telas de login e
consentimento, autentica credenciais e emite tokens. Isso impõe três exigências
simultâneas à plataforma: renderização server-side de primeira classe, uma máquina de
sessão e autenticação madura, e um ecossistema com implementação confiável de
OAuth2/OIDC. A renderização não é acessório de apresentação — é onde a senha é digitada,
e portanto parte da fronteira de segurança.

Um IdP é infraestrutura de longa vida: outras aplicações passam a depender dele para
autenticar, e sobressaltos de upgrade custam caro. Esse argumento é frequentemente lido
como "escolher sempre o mais conservador", mas ele não se aplica igualmente aos dois
eixos da plataforma. Um upgrade de major do framework toca código de aplicação, sinais,
APIs internas e comportamento de terceiros; um upgrade de minor do runtime é, na prática,
uma linha de imagem base, desde que nenhum código dependa de recurso exclusivo da série.
Os dois eixos têm custos de reversão de ordens diferentes, e a decisão precisa tratá-los
de forma diferente em vez de aplicar a mesma postura aos dois.

A escolha de série do Python foi verificada contra o PyPI em 2026-08-29, e não herdada de
suposição: django-oauth-toolkit 3.4.1 declara Python 3.14 e Django 5.2/6.0; a série Django
5.2 está em 5.2.17 e declara Python 3.14, com a compatibilidade tendo entrado por patch da
série (piso 5.2.8, não 5.2.0); psycopg-binary 3.3.4 publica wheels cp314; cryptography
50.0.1 e argon2-cffi-bindings 26.1.0 publicam wheels abi3 que rodam em 3.14 sem
recompilação; django-environ 0.14.0 declara 3.14. Toda a árvore de dependências com
extensão em C do projeto está coberta por wheel hoje.

## Decisão

Vamos construir o IdP em Python 3.14 com Django 5.2 LTS, usando os templates do Django
para as telas de login e consentimento e o django.contrib.auth como base da autenticação
e da sessão.

O Django é pinado em 5.2.17, e o requirements.txt registra por comentário que 5.2.8 é o
piso de compatibilidade com Python 3.14 — o piso não pode viver apenas nesta ADR, porque
quem instala lê o requirements. A imagem base é python:3.14-slim.

Como contrapartida explícita da escolha do runtime mais recente, o código não usa sintaxe
nem stdlib exclusivos de 3.14. Isso mantém a descida para 3.13 ao custo de uma linha de
FROM, e é o que torna a decisão reversível.

O modo de execução é síncrono (WSGI); recursos assíncronos do Django não são usados. A
série Django 6.x fica fora até que exista uma nova LTS.

## Consequências

Positivas:

- As telas de login e consentimento são código de primeira classe no mesmo processo que
  valida a credencial: a senha nunca cruza uma fronteira de rede interna.
- django.contrib.auth entrega hashing, sessão, backends de autenticação e proteção CSRF
  sem que nada disso precise ser escrito ou auditado do zero.
- O admin dá, sem custo, a interface de registro de clients e de gestão de usuários que o
  MVP precisa.
- A janela LTS do Django, com segurança até cerca de 2028, permite planejar upgrades em
  vez de reagir a fim de suporte.
- A série 3.14 é a que tem a janela de suporte mais longa pela frente, o que adia o
  próximo upgrade de runtime.
- A restrição de não usar recursos exclusivos de 3.14 mantém uma saída de emergência
  barata e verificável.

Negativas:

- O risco do runtime recente não está na árvore atual, que foi verificada, mas nas
  dependências ainda não escolhidas. O primeiro item da fase seguinte — rate limiting —
  chega por biblioteca de terceiro cuja matriz de suporte a 3.14 ninguém conferiu. É lá
  que o custo desta decisão será cobrado, não neste scaffold.
- Menos material de comunidade para bugs específicos da série 3.14, o que alonga
  diagnóstico quando algo dá errado no runtime e não na aplicação.
- O upgrade LTS -> LTS do Django é um evento grande, com revisão de deprecations
  concentrada, em vez de uma sequência de passos pequenos.
- Ficamos amarrados ao modelo síncrono; concorrência alta terá de ser resolvida por
  número de workers, não por async.
- Django impõe suas convenções (ORM, apps, settings globais); fugir delas em qualquer
  ponto custa mais do que segui-las.
- A proibição de usar recursos exclusivos de 3.14 é disciplina, não mecanismo: nada a
  impõe automaticamente.

## Alternativas consideradas

- **Python 3.13** — a escolha conservadora coerente com o argumento de infraestrutura de
  longa vida: uma série a mais de rodagem, cobertura de ecossistema máxima e nenhum risco
  de dependência futura sem suporte. Descartada porque a verificação mostrou toda a árvore
  atual já suportada em 3.14, porque 3.14 tem a janela de suporte mais longa pela frente,
  e porque a proibição de usar recursos exclusivos da série mantém a descida para 3.13
  barata caso uma dependência futura obrigue. A conservação foi comprada por disciplina
  em vez de por versão.
- **Django 6.0** — traz melhorias mais recentes e também é suportado pelo DOT 3.4.1, mas
  não tem janela LTS. Para a peça de infraestrutura de que outras aplicações dependerão
  para autenticar, previsibilidade de suporte vale mais que recência.
- **FastAPI + Authlib** — mais leve e assíncrono, mas não traz sessão, admin nem camada
  de templates. Um IdP com telas próprias teria de reconstruir exatamente a parte que o
  Django entrega madura, ampliando muito a superfície de segurança escrita à mão.
- **Keycloak (IdP pronto)** — resolveria o protocolo inteiro sem código, mas o objetivo é
  possuir a identidade dentro da própria aplicação; adotá-lo trocaria o produto por uma
  integração.
```


### Destino: `docs/adr/0002-usar-django-oauth-toolkit-como-servidor-de-autorizacao.md`

O servidor de autorização: django-oauth-toolkit, incluído como vem, com PKCE exigido. Incide nos passos 07, 08 e 09.

```markdown
# 0002. Usar django-oauth-toolkit como servidor de autorização OAuth2/OIDC

## Status

Aceito — 2026-08-29

## Contexto

O núcleo do produto é um authorization server OpenID Connect: precisa suportar
Authorization Code com PKCE, emitir e renovar tokens, revogar, publicar documento de
descoberta e JWKS, registrar clients com allowlist de redirect_uri e expor /userinfo.

Cada um desses elementos é uma superfície onde um erro sutil vira vulnerabilidade real:
redirect_uri comparado por prefixo em vez de igualdade exata, code sem uso único, PKCE
aceito como opcional, state não verificado. São erros que não aparecem em teste funcional
— o fluxo continua fechando — e só aparecem quando alguém os explora.

A alternativa a adotar uma implementação existente é escrever a máquina de estados do
protocolo, o que significa assumir a manutenção permanente de conformidade com uma
família de RFCs em evolução.

## Decisão

Vamos usar django-oauth-toolkit 3.4.1 como authorization server, instalado sem extra — o
jwcrypto, que é quem viabiliza a assinatura de id_token e o JWKS, entra como dependência
incondicional do pacote —, com PKCE exigido e não meramente oferecido.

As rotas do DOT são incluídas como vêm: não reescrevemos, envelopamos nem duplicamos
endpoint de protocolo. A única customização permitida no comportamento do servidor é o
OAUTH2_VALIDATOR_CLASS, que define quais claims sobre o usuário o IdP afirma. Override de
template — a tela de consentimento — é permitido e esperado, e não é a mesma coisa que
override de view.

O ponto de montagem das rotas e o issuer resultante são decisão própria, registrada na
ADR 0007.

## Consequências

Positivas:

- Authorization Code + PKCE, refresh, revogação, descoberta e JWKS chegam prontos e
  testados por uma comunidade grande (Jazzband), em vez de escritos aqui.
- Applications, grants e tokens são modelos do ORM: registro e inspeção de clients saem
  de graça pelo admin.
- O contrato com as relying parties é OIDC Discovery 1.0, auto-descoberto: uma RP que
  siga esse padrão integra sem documentação manual nossa.
- Correções de segurança do protocolo chegam por upgrade de dependência.

Negativas:

- A superfície de configuração é grande (grants, scopes, chaves, políticas por
  application) e é possível configurar algo inseguro sem receber nenhum aviso; a
  documentação pressupõe conhecimento de OAuth2/OIDC.
- Há duas configurações incompletas cujo sinal não está onde se procura. Sem chave RSA, o
  JWKS responde vazio com HTTP 200 e o único indício é o alg anunciado na discovery cair
  de RS256+HS256 para HS256 — silenciosa de ponta a ponta. Já uma Application com o campo
  algorithm em branco não é silenciosa nem falha onde se espera: /o/authorize/ emite o
  code normalmente, e é o POST em /o/token/ que devolve HTTP 500 sem token nenhum, porque
  a emissão do id_token pede a chave da Application sempre que o escopo inclui openid, e o
  campo em branco levanta ImproperlyConfigured. Procurar um id_token ausente numa resposta
  bem-sucedida é depurar o endpoint errado.
- O DOT 4.0 endurecerá a postura para OAuth 2.1 e o upgrade exigirá revisão deliberada,
  não bump de versão.
- O esquema de banco dos tokens é do DOT: as tabelas crescem e a limpeza periódica
  (cleartokens) passa a ser obrigação operacional nossa.
- O DOT deixa de ser dependência e passa a ser a definição do nosso contrato público;
  trocá-lo depois de haver RPs integradas é migração de protocolo, não refatoração.
- A introspecção não chega utilizável: a view exige o scope introspection, que o bloco
  SCOPES não declara, e nenhum token pode carregá-lo. /o/introspect/ segue roteado e
  anunciado como introspection_endpoint na metadata RFC 8414, e responde 403. Coerente
  com esta fase, que não tem resource server; vira pergunta de integração quando houver
  um.

## Alternativas consideradas

- **Authlib** — biblioteca excelente e mais flexível, mas fornece os blocos do protocolo,
  não um servidor pronto integrado ao ORM e ao admin. Teríamos de montar modelos,
  endpoints, descoberta e JWKS à mão, assumindo a conformidade.
- **Implementação própria do protocolo** — máximo controle, mas transferiria para este
  projeto a responsabilidade permanente de acompanhar as RFCs e de acertar detalhes cuja
  falha é silenciosa e explorável. Custo desproporcional ao objetivo.
- **Delegar a um IdP externo (Auth0, Keycloak, Cognito)** — eliminaria o problema, e
  também o produto: o objetivo declarado é ser o IdP.
```


### Destino: `docs/adr/0003-modelar-identidade-em-user-customizado-com-email-como-identificador.md`

O modelo de identidade: User customizado com e-mail como identificador, antes da primeira migração. Incide nos passos 04, 05 e 06.

```markdown
# 0003. Modelar a identidade em um User customizado com e-mail como identificador

## Status

Aceito — 2026-08-29

## Contexto

O IdP é o dono da identidade: o modelo de usuário é o registro canônico sobre o qual todo
token emitido faz afirmações. Em OIDC, as claims padrão de um sujeito são sub, email, name
e correlatas — o e-mail não é atributo secundário, é o identificador que as relying
parties esperam ver.

O modelo default do Django usa username como identificador e traz email como campo comum,
sem unicidade. Isso desalinha o modelo do vocabulário do protocolo e permite dois usuários
com o mesmo e-mail, o que num IdP é ambiguidade de identidade.

A restrição decisiva é temporal: AUTH_USER_MODEL é resolvido em tempo de migration e
referenciado por chave estrangeira por django.contrib.admin e por todas as tabelas do
django-oauth-toolkit, e gravado como tipo de modelo pelo contenttypes. Trocar o modelo
depois da primeira migração é uma das operações mais caras do ecossistema Django. A decisão
precisa ser tomada antes de existir qualquer banco.

## Decisão

Vamos definir accounts.User como subclasse de AbstractUser com username = None, email
unique como USERNAME_FIELD, REQUIRED_FIELDS vazio e um UserManager próprio para
create_user e create_superuser por e-mail. AUTH_USER_MODEL aponta para ele desde a
primeira linha de settings, antes de qualquer migrate. A chave primária é um
BigAutoField, fixado por DEFAULT_AUTO_FIELD nas settings, e é ela que vai na claim sub.

Nenhum campo especulativo entra agora. Em particular, não incluímos email_verified: sem
fluxo de verificação implementado, a claim seria sempre falsa, e um IdP que afirma
falsidades sobre a identidade é pior que um que se cala. O campo entra junto com o fluxo
que o alimenta.

## Consequências

Positivas:

- O identificador da conta coincide com a claim que as RPs consomem; não há tradução nem
  ambiguidade entre o modelo e o protocolo.
- Unicidade de e-mail no nível do banco elimina uma classe inteira de confusão de
  identidade.
- Ganhamos o ponto de extensão natural para claims futuras (e-mail verificado, telefone,
  perfil) sem tocar em AUTH_USER_MODEL de novo.
- Herdar de AbstractUser preserva is_staff, is_active, permissões, admin e o framework de
  autenticação inteiro funcionando.

Negativas:

- Exige um UserManager próprio e cuidado com todo código que assuma a existência de
  username; bibliotecas de terceiros que presumam esse campo podem quebrar.
- Prende o projeto a AbstractUser: migrar mais tarde para um AbstractBaseUser mais enxuto
  significaria descartar campos com dados.
- O e-mail passa a ser credencial de login e chave natural de identidade. O sub emitido
  nos tokens é a chave primária do usuário e não muda com o e-mail, mas permitir troca de
  e-mail ainda exigirá decidir o que acontece com sessões vivas e com RPs que tenham
  correlacionado a conta pelo endereço.
- Carrega first_name/last_name herdados, que não são o modelo de nome mais rico possível
  para OIDC.

## Alternativas consideradas

- **User default do Django** — nenhum custo inicial, mas a troca posterior é notoriamente
  cara e, num IdP, seria inevitável. Adiar essa dor não a reduz.
- **AbstractBaseUser puro** — modelo mínimo, sem herança desnecessária, mas exigiria
  reimplementar permissões e integração com o admin, gastando esforço em algo que o
  AbstractUser entrega correto.
- **UUID como identificador de login** — mais estável que e-mail, porém ninguém digita
  UUID numa tela de login; o e-mail continuaria necessário e único de qualquer forma.
```


### Destino: `docs/adr/0004-assinar-tokens-com-rs256-e-custodiar-a-chave-privada-no-ambiente.md`

A assinatura: RS256 com a chave privada custodiada no ambiente, sem rotação nesta fase. Incide nos passos 03 e 07.

```markdown
# 0004. Assinar tokens com RS256 e custodiar a chave privada no ambiente

## Status

Aceito — 2026-08-29

## Contexto

A razão de existir de um IdP é que terceiros confiem no que ele afirma. Essa
confiança se materializa na assinatura do token: a relying party precisa poder
verificar, por conta própria, que aquele id_token foi emitido por nós e não foi
adulterado — sem chamar o IdP a cada request e sem compartilhar segredo conosco.

Um segredo simétrico compartilhado inverteria a propriedade essencial: quem pode
verificar um token também pode forjá-lo. Numa federação com múltiplas RPs, isso
significa que qualquer cliente comprometido passaria a poder emitir identidades em
nosso nome.

Do outro lado, uma chave assimétrica cria uma obrigação nova: alguém precisa gerar,
guardar e eventualmente rotacionar a chave privada. Ela é o segredo mais crítico do
sistema — quem a possui é o IdP, para todos os efeitos práticos.

O projeto é um sandbox exploratório, sem infraestrutura de gestão de segredos
disponível, e roda em container com configuração 12-factor.

## Decisão

Vamos assinar os tokens com RS256 e publicar a chave pública correspondente no
endpoint JWKS do django-oauth-toolkit, de modo que qualquer RP valide o token com
material público obtido por discovery.

A chave privada é custodiada como variável de ambiente OIDC_RSA_PRIVATE_KEY,
injetada via .env e lida com django-environ em modo multiline. Ela nunca entra no
repositório nem na imagem Docker. Chaves de desenvolvimento são geradas por
scripts/gen_dev_key.sh e são descartáveis por definição.

Nesta fundação existe uma única chave ativa, sem conjunto de rotação.

## Consequências

Positivas:

- Verificar um token não exige segredo algum: a federação funciona com material
  público, que é a propriedade que torna um IdP útil.
- Nenhuma RP pode forjar um token, nem mesmo aquelas com quem já nos integramos.
- A chave sai do código e da imagem, e passa a ser rotacionável por redeploy sem
  alteração de código.
- O JWKS estabelece o caminho para rotação futura (chave nova ativa, chave antiga
  ainda publicada) sem invalidar tokens vivos.

Negativas:

- Assumimos a custódia do segredo mais crítico do sistema; um .env mal protegido ou
  um dump de variáveis de ambiente em log compromete tudo, sem sinal visível.
- Trocar a chave hoje invalida na prática as sessões de token em curso, porque não
  há conjunto de rotação — a rotação real será uma decisão posterior, com ADR própria.
- PEM em variável de ambiente é formato hostil: precisa de escape de quebra de linha
  e falha de maneiras confusas quando mal formatado.
- RS256 é mais caro em CPU que HMAC na assinatura, e a dependência de cryptography
  adiciona extensão em C ao build.
- Os dois modos de falha da variável são opostos, e o perigoso é o menos evidente.
  Ausente, ela falha na leitura das settings nomeando a si mesma: o processo não sobe,
  o container entra em crash-loop e o erro está na primeira linha do log. Presente e
  vazia, o sistema sobe inteiro, o JWKS responde 200 com um conjunto vazio de chaves e
  o único indício é o alg anunciado na discovery cair de RS256+HS256 para HS256 —
  silenciosa de ponta a ponta, e só percebida do lado da relying party, que não
  encontra chave com que verificar assinatura nenhuma.

## Alternativas consideradas

- **HS256 com segredo compartilhado** — mais simples e sem custódia de par de chaves,
  mas quem valida pode forjar. Inadequado para federar com terceiros, que é o ponto
  do produto.
- **ES256 (curva elíptica)** — chaves e assinaturas menores e mais rápidas, e
  igualmente assimétrico; descartado apenas por interoperabilidade: RS256 é o
  algoritmo que toda biblioteca de RP suporta sem configuração extra.
- **Chave em arquivo montado por volume** — evita o problema de escape do PEM e
  reduz o risco de vazar em log de ambiente, mas acopla o deploy à existência do
  volume e afasta a configuração do padrão 12-factor usado no resto do projeto.
- **Gerar a chave no boot do container** — dispensaria custódia, mas cada reinício
  invalidaria todos os tokens emitidos e quebraria o cache de JWKS das RPs.
  Proibido explicitamente.
```


### Destino: `docs/adr/0005-manter-a-sessao-sso-em-sessao-django-com-backend-cached-db.md`

A sessão SSO: sessão do Django com backend cached_db sobre Redis. Incide nos passos 04 e 10.

```markdown
# 0005. Manter a sessão SSO em sessão Django com backend cached_db sobre Redis

## Status

Aceito — 2026-08-29

## Contexto

O IdP tem dois tipos de estado de autenticação que coexistem por desenho, e ambos são
server-side. O estado dos tokens vive nas tabelas do django-oauth-toolkit: o access_token
entregue à relying party é uma string opaca gravada em banco, e só o id_token é JWT
assinado, que a RP valida sozinha. A consequência prática é que a RP que precise validar o
access_token não tem introspecção — o endpoint anunciado responde 403 (ADR 0002) — e recai
sobre /o/userinfo/, uma chamada ao IdP por request, que é justamente o custo que a
assinatura da ADR 0004 existe para evitar. A sessão de login é o outro estado, e é ela que
faz o single sign-on existir — é ela que permite ao usuário chegar a uma segunda relying
party e não redigitar a senha. O que a distingue do estado dos tokens não é ser
server-side: é ser lida em todo request autenticado. Ela está no caminho quente, e por
isso onde ela mora é decisão de desempenho e não só de durabilidade.

Essa sessão é comportamento de produto, não detalhe de infraestrutura. Perdê-la não causa
erro visível: causa um pedido de senha inesperado, que é exatamente a experiência que o
SSO existe para evitar.

O stack já prevê Redis para cache e, mais adiante, rate limiting. Surge a questão de onde
a sessão vive: apenas em Redis, apenas no banco, ou nos dois. Cabe distinguir três modos
de falha que costumam ser confundidos: perda de dados do cache (flush ou eviction),
reinício do serviço de cache com memória vazia, e indisponibilidade de conexão. Os
backends de sessão respondem de forma diferente a cada um, e a escolha só faz sentido se
essa distinção estiver explícita.

## Decisão

Vamos manter a sessão de login como sessão do Django com SESSION_ENGINE =
django.contrib.sessions.backends.cached_db: Postgres como armazenamento durável e Redis
como camada de leitura quente, usando o backend Redis nativo do Django
(django.core.cache.backends.redis.RedisCache), sem django-redis.

A vantagem que estamos comprando é precisa e limitada: sobreviver a perda de dados e a
reinício do Redis. Não estamos comprando tolerância a indisponibilidade de conexão.

Redis segue como cache geral da aplicação e base para o rate limiting futuro.

## Consequências

Positivas:

- A leitura de sessão, que acontece em todo request autenticado, é servida por Redis; o
  Postgres não vira gargalo do caminho quente.
- Flush, eviction ou reinício do Redis não deslogam ninguém: a sessão é reidratada do
  banco. Num serviço de cache que também guarda outras coisas, isso não é hipótese
  remota.
- Usa a máquina de sessão do Django, madura, com expiração, rotação de chave no login e
  invalidação por troca de senha já resolvidas.
- Sem django-redis: o backend Redis é do próprio Django desde a 4.0. A única dependência
  acrescentada é o cliente redis, que o backend nativo importa, e ela está pinada.

Negativas:

- Redis continua sendo dependência dura do IdP. O backend nativo propaga ConnectionError,
  e SessionStore toca o cache em todo request: com o Redis inalcançável, todo request
  autenticado falha, inclusive o admin, e /health responde 503. Em disponibilidade,
  cached_db e sessão em cache puro empatam. Redis deve ser orçado como serviço crítico,
  não como acelerador dispensável.
- Toda criação e modificação de sessão escreve no Postgres, e a tabela django_session
  cresce; clearsessions vira obrigação operacional.
- Há dois lugares onde a sessão existe, e portanto uma janela de incoerência possível
  entre eles.
- O SSO permanece preso ao cookie de sessão de um domínio; federação entre domínios
  distintos exigirá decisão nova.

## Alternativas consideradas

- **Sessão apenas em cache (backends.cache)** — a configuração mais simples e a mais
  rápida, e igual ao cached_db diante de indisponibilidade de conexão. Descartada porque
  perde para ele nos outros dois modos de falha: um flush ou um reinício do Redis
  desloga todo mundo, inclusive as sessões administrativas.
- **Sessão apenas em banco (backends.db)** — durabilidade máxima e uma peça a menos no
  caminho crítico, o que a torna a escolha certa caso Redis se mostre instável na
  prática. Descartada agora por levar ao Postgres uma leitura por request autenticado,
  no caminho mais quente do IdP.
- **django-redis com IGNORE_EXCEPTIONS** — daria a tolerância a indisponibilidade que o
  backend nativo não dá, ao custo de engolir erros de cache. Para sessão isso é o pior
  dos mundos: uma escrita de sessão perdida em silêncio é um logout mudo, sem erro,
  sem log e sem causa aparente. Preferimos falhar alto.
- **Sessão em cookie assinado** — dispensa armazenamento, mas impede revogação
  server-side de sessão, o que é inaceitável para um provedor de identidade.
```


### Destino: `docs/adr/0006-empacotar-o-idp-como-container-unico-orquestrado-por-docker-compose.md`

O empacotamento: container único com compose, BEHIND_TLS_PROXY e LOGGING explícito. Incide nos passos 02, 04, 10 e 11.

```markdown
# 0006. Empacotar o IdP como container único orquestrado por docker-compose

## Status

Aceito — 2026-08-29

## Contexto

O sistema é um monólito deliberado: telas de login, servidor de autorização, admin e
modelo de identidade vivem no mesmo processo, com uma fronteira de segurança só. O
empacotamento precisa refletir essa escolha em vez de contrariá-la.

Quatro exigências operacionais acompanham essa forma. As migrations precisam estar
aplicadas antes do primeiro request, incluindo as tabelas do django-oauth-toolkit, sem as
quais nenhum fluxo funciona. Os arquivos estáticos das telas de login precisam ser
servidos de verdade, porque uma tela de credencial sem CSS é uma tela que ninguém confia.
O orquestrador precisa de um sinal honesto de prontidão. E o container precisa ser
observável: um IdP cujos erros não aparecem no log é um IdP que falha em silêncio, o que
é justamente o modo de falha característico deste domínio.

Duas armadilhas do Django merecem registro porque o ambiente do compose as ativa por
default. A primeira: atrelar cookies seguros e HSTS ao valor de DEBUG faz a aplicação
descartar o cookie de sessão quando ela roda sem TLS, e o login passa a falhar com 302
silencioso, sem erro em lugar nenhum. DEBUG é variável sobre diagnóstico; cookie seguro
depende de transporte. A segunda: o DEFAULT_LOGGING do Django prende o handler de console
ao filtro require_debug_true e roteia erro de django.request para mail_admins. Com
DEBUG=False e sem e-mail configurado, um 500 no endpoint de token simplesmente desaparece.

Há ainda o risco de boot: entrypoint que roda migration sem cuidado executa migrations
concorrentes se houver mais de uma réplica.

## Decisão

Vamos empacotar a aplicação como um único container, construído por Dockerfile
multi-stage, servido por Gunicorn (WSGI) com WhiteNoise para arquivos estáticos, e
orquestrá-la com docker-compose ao lado de PostgreSQL 17 e Redis 7.

O boot é responsabilidade de um entrypoint que executa migrate, collectstatic e a criação
condicional de superusuário antes de fazer exec no Gunicorn. collectstatic roda em
runtime, não no build, para que as settings nunca precisem importar sem ambiente durante
a construção da imagem.

A espera pelas dependências é do compose, via depends_on com condition: service_healthy
sobre healthchecks de Postgres e Redis — não via laço de polling no shell. A aplicação
expõe /health, que verifica banco e cache de verdade e serve de healthcheck do próprio
serviço; o healthcheck é executado pelo interpretador Python que já está na imagem, via
urllib da stdlib, porque imagens slim não trazem curl nem wget e instalar um cliente HTTP
só para isso é engordar a imagem por um contrato que a stdlib já cumpre.

Contra as duas armadilhas: o endurecimento de transporte (cookies seguros, HSTS, redirect
para HTTPS, SECURE_PROXY_SSL_HEADER) é governado por uma variável própria,
BEHIND_TLS_PROXY, e nunca por DEBUG; e as settings trazem um bloco LOGGING explícito que
manda tudo para stdout independentemente de DEBUG, sem require_debug_true e sem
mail_admins. O .env.example sai com DEBUG=False e BEHIND_TLS_PROXY=False, de modo que o
ambiente que sobe por default é o de diagnóstico endurecido e mesmo assim o fluxo fecha
sobre http em localhost.

O compose declara uma réplica da aplicação. TLS é responsabilidade de um proxy à frente,
fora deste escopo — e é exatamente por isso que o endurecimento é opt-in por variável.

## Consequências

Positivas:

- Uma unidade implantável, uma fronteira de segurança, um lugar para olhar quando algo
  falha.
- O ambiente inteiro sobe reprodutível com um comando, o que torna o fluxo OIDC
  demonstrável de ponta a ponta sem preparação manual.
- Ordem de boot determinística: nenhum request chega antes das migrations.
- Há uma configuração só, e não um "modo de desenvolvimento" separado que nunca é
  exercitado: o compose executa o mesmo caminho de código que se pretende usar depois. O
  ganho é do arranjo de settings única, não do arranjo inteiro — o endurecimento de
  transporte é opt-in e fica de fora, conforme a última Negativa.
- Logs de erro aparecem em docker logs desde o primeiro boot, o que importa num sistema
  cujos modos de falha característicos são silenciosos.
- O healthcheck funciona na imagem enxuta sem dependência adicional.
- WhiteNoise elimina a necessidade de Nginx no MVP sem abrir mão de estáticos reais.

Negativas:

- Migrations no entrypoint só são seguras com uma réplica. Escalar horizontalmente sem
  antes separar a migração do boot causa migrations concorrentes — dívida contratada
  conscientemente, com vencimento no dia em que houver pressa para escalar.
- BEHIND_TLS_PROXY é uma variável a mais e um erro a mais possível: deixá-la em False
  atrás de um proxy real significa cookies sem flag Secure em produção, sem nenhum aviso.
- docker-compose é ferramenta de host único: não é o modelo de produção real e precisará
  ser substituído se o projeto sair do sandbox.
- Gunicorn é síncrono e não termina TLS; um proxy é obrigatório em qualquer uso real, já
  que tudo num IdP trafega sob HTTPS.
- Estado (Postgres, Redis) em containers exige disciplina de volumes e backup que o
  compose não impõe.
- WhiteNoise concentra no app a entrega de estáticos e não escala para tráfego alto.
- collectstatic em runtime alonga levemente o tempo de boot.
- Log em stdout sem coleta externa some quando o container é recriado.
- O endurecimento de transporte é a parte desta decisão que o compose não exercita: ele
  sobe com BEHIND_TLS_PROXY=False, e foi ligar a variável que revelou que a probe interna
  do HEALTHCHECK recebe 301 do SecurityMiddleware e morre no handshake TLS contra um
  Gunicorn em texto claro — container eternamente unhealthy com a aplicação atendendo
  normalmente. A isenção que fecha isso está na ADR 0010. A segunda condição, ALLOWED_HOSTS
  continuar listando 127.0.0.1, não tem mecanismo nenhum e vive só no README.

## Alternativas consideradas

- **Serviços separados (auth server, telas, API)** — fronteiras mais claras a longo
  prazo, mas multiplicaria deploys, latência e superfícies de segurança para um sistema
  que cabe inteiro num processo. Contraria a escolha de monólito.
- **Endurecimento atrelado a DEBUG** — uma variável a menos, e é o que a maioria dos
  tutoriais faz. Descartado porque acopla duas dimensões independentes e produz o pior
  modo de falha possível neste projeto: login que não funciona sem erro visível.
- **Proxy TLS no compose** — mais próximo de produção e dispensaria BEHIND_TLS_PROXY, mas
  acrescenta certificado, configuração e uma peça a manter num estágio em que o objetivo
  é demonstrar o fluxo OIDC.
- **Migration como job separado do boot** — o que se deve fazer ao escalar, mas hoje
  acrescentaria orquestração sem nenhuma réplica extra para justificá-la.
- **curl na imagem para o healthcheck** — trivial de escrever, mas engorda a imagem e
  falha de forma confusa (serviço unhealthy para sempre, com a aplicação funcionando) se
  alguém trocar a imagem base por uma sem ele.
- **Uvicorn/ASGI** — abriria caminho para async, mas o Django 5.2 aqui é síncrono e nenhum
  endpoint do fluxo se beneficiaria.
```


### Destino: `docs/adr/0007-fixar-o-issuer-do-idp-em-base-url-barra-o.md`

O issuer: {BASE_URL}/o, com as urls do DOT sob /o/. Incide no passo 07.

```markdown
# 0007. Fixar o issuer do IdP em {BASE_URL}/o

## Status

Aceito — 2026-08-29

## Contexto

O issuer é a identidade pública do IdP. Ele vai na claim iss de todo id_token emitido, é a
raiz a partir da qual as relying parties montam a URL do documento de descoberta, e fica
cacheado na configuração de cada RP integrada. Diferente de quase tudo neste projeto,
mudá-lo depois não é uma alteração de código: é reconfiguração simultânea de todas as RPs
e invalidação do iss de todo token vivo.

O django-oauth-toolkit publica seus endpoints sob o prefixo em que suas urls forem
incluídas, e deriva o issuer desse prefixo. Montá-lo na raiz do host publicaria também
suas views de gestão de applications e de tokens autorizados no espaço de nomes raiz,
misturando superfície administrativa da biblioteca com o espaço de rotas do produto.

Há ainda uma divergência entre especificações que só importa quando o issuer tem
componente de path. A OIDC Discovery 1.0 manda concatenar: issuer +
/.well-known/openid-configuration. A RFC 8414, para metadados de authorization server,
manda inserir o segmento well-known antes do path do issuer. Com issuer na raiz, as duas
formas coincidem; com issuer sob um path, não.

## Decisão

Vamos fixar o issuer do IdP em {BASE_URL}/o, montando as urls do django-oauth-toolkit sob
o prefixo /o/ e definindo OIDC_ISS_ENDPOINT coerente com ele.

O documento de descoberta responde, portanto, em
{BASE_URL}/o/.well-known/openid-configuration, que é a forma da OIDC Discovery 1.0. O
README documenta essa URL exata.

Esta é uma decisão deliberada e não uma consequência da escolha de roteamento. Ela deve
ser confirmada antes da primeira relying party integrar; depois disso, é permanente para
efeitos práticos.

## Consequências

Positivas:

- O espaço de rotas do produto fica livre: /login/, /admin/, / e o que vier depois não
  disputam nomes com a biblioteca, e as views administrativas do DOT ficam contidas sob
  um prefixo identificável.
- O prefixo /o/ é a convenção documentada do DOT, o que faz a configuração coincidir com
  os exemplos da biblioteca e reduz a chance de erro sutil.
- A separação entre superfície de protocolo e superfície de produto fica legível na URL,
  o que ajuda em proxy, log e regra de rate limiting mais adiante.

Negativas:

- O issuer passa a ter componente de path, e com isso as formas de descoberta da OIDC
  Discovery 1.0 e da RFC 8414 deixam de coincidir. Uma RP que implemente estritamente a
  RFC 8414 procurará em {BASE_URL}/.well-known/oauth-authorization-server/o e hoje
  receberá 404 — consequência da montagem atual, um único include sob /o/, e não do
  prefixo em si: o DOT exporta metadata_urlpatterns e documenta que deployment sob
  prefixo deve montá-la também na raiz do servidor, onde a forma path-component da RFC
  8414 reflete o sufixo de volta no issuer. Esta fase não a montou: não prometemos essa
  forma de descoberta e documentamos a URL correta. A escolha fica em aberto.
- A string do issuer torna-se irreversível assim que a primeira RP integra. Levar o IdP
  para a raiz do host depois exige janela coordenada com todas elas.
- Uma URL de login com prefixo técnico ("/o/authorize") é menos apresentável que uma na
  raiz, num fluxo em que o usuário vê a barra de endereços no momento em que decide
  confiar.

## Alternativas consideradas

- **Montar na raiz do host (issuer = {BASE_URL})** — faria OIDC Discovery e RFC 8414
  coincidirem, eliminando de vez a divergência, e daria a URL pública mais limpa.
  Descartada porque publicaria as views de gestão do DOT na raiz e colocaria o espaço de
  nomes do produto em disputa permanente com o da biblioteca — um custo de acoplamento
  diário contra um risco de interoperabilidade ocasional e documentável.
- **Subdomínio dedicado (issuer = https://idp.exemplo)** — a separação mais limpa
  possível, com raiz livre e sem componente de path. Descartada nesta fase por exigir DNS
  e certificado próprios, que estão fora do escopo de um compose de host único; continua
  sendo o destino natural se o IdP for exposto de verdade, e é a razão pela qual a string
  do issuer deve ser confirmada antes da primeira integração.
- **Montar metadata_urlpatterns também na raiz, mantendo o issuer em {BASE_URL}/o** —
  atenderia a RP estrita da RFC 8414 sem mover o issuer nem publicar as views de gestão
  do DOT na raiz, compondo listas que a própria biblioteca exporta para esse fim. Não
  adotada nesta fase: nenhuma RP a exige ainda, e a raiz ganharia rotas .well-known antes
  de haver quem as consulte. Permanece disponível.
```
