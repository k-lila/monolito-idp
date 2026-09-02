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
