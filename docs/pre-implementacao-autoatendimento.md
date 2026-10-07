# Pré-implementação — autoatendimento de conta no IdP

| Campo | Valor |
| --- | --- |
| Natureza | documento de trabalho do provedor de identidade (IdP, de _Identity Provider_); relatório antes do código, não decisão de arquitetura |
| Data | 2026-09-30, com o código conferido nessa data; revisto no mesmo dia contra o toolkit 3.4.1, o Django 5.2 e o `axes` 8.3.1 |
| Estado | decisões fechadas (§4); é a entrada da tarefa de implementação pelo `/dev` |
| Fontes | `../jornada-usuario.md` e `../dominio-usuario.md`, documentos de trabalho comuns ao IdP e à aplicação de página única (SPA, de _Single-Page Application_) |
| Escopo | o lado do IdP; cada passo diz o efeito na SPA |
| Aposentadoria | sai quando a ADR (Architecture Decision Record) do autoatendimento e a §3 de `docs/nucleo-idp.md` absorverem o conteúdo. Nenhuma ADR cita este arquivo |

Onde este relatório e as fontes divergirem, vale este relatório: as divergências estão na §3, e
as decisões que as resolvem, na §4.

---

## 1. Escopo e o que muda no núcleo

A jornada dá à pessoa usuária o CRUD (_Create, Read, Update, Delete_) da própria conta e a
recuperação da senha, no **recorte B**:

- tudo o que recebe senha é página do IdP: cadastro, troca de senha, troca de e-mail, exclusão
  e recuperação;
- o resto é tela da SPA, sobre uma interface de programação (API, de _Application Programming
  Interface_) JSON do IdP em `/api/conta/`: ler a conta, editar nome, sobrenome e apelido,
  aceitar os termos e reenviar a confirmação de e-mail.

O domínio troca o `sub` por um UUID (_Universally Unique Identifier_) público e acrescenta
`nickname`, `email_verified`, `updated_at`, os carimbos internos e os campos de termos.

**O que a proposta desfaz no IdP**, e que por isso pede ADR:

| Afetado | Hoje diz |
| --- | --- |
| N4 de `docs/nucleo-idp.md` e ADR 0023 | contas nascem no admin; não há cadastro nem edição de perfil |
| §3 de `docs/nucleo-idp.md` (contrato com toda relying party, ou RP) | scopes exatamente `openid`, `profile`, `email`; sem `email_verified`; `sub` é a chave primária; CORS (_Cross-Origin Resource Sharing_) só em `^/o/` |
| ADR 0003, na parte do `sub` | a chave primária vai na claim `sub` |
| ADR 0013 | o resumo do identificador na trilha é calculado sobre o valor como recebido (D13) |
| ADR 0016 | o teto de taxa cobre caminhos fixos; a confirmação da redefinição fica fora (D12) |
| `docs/seguranca.md:64` | a ausência de recuperação de senha figura como controle |
| `config/urls.py` e `tests/test_password_reset_urls.py` | `/accounts/password_reset/` é 404 deliberado |
| `templates/registration/login.html` | conta desativada recebe o mesmo erro de senha errada; o e-mail é comparado com a caixa digitada |

**O que se preserva:** o fato de base da §1 do núcleo ("a senha só trafega dentro do IdP"), a N3
(login e consentimento, e agora as outras telas com senha, são telas do IdP) e a N6 (o cadastro
entra pelo `prompt=create` nativo do toolkit).

A ADR 0023 já fixou, nesta ordem, as pré-condições de um cadastro público:

1. validadores de senha declarados, já cumprido em `config/settings.py:282`;
2. teto de requisição no caminho de cadastro;
3. verificação de e-mail;
4. só então a claim `email_verified`.

Com a implantação única (D17), as quatro entram em produção juntas. A ordem interna da §5 ainda
as respeita: a claim nasce `false` para toda conta, e `false` não afirma posse, o que cumpre a
ADR 0003 ("um IdP que afirma falsidades… é pior que um que se cala").

---

## 2. Fatos reconferidos no código

A §8 da jornada confere com o código. Os pontos de maior peso, relidos:

- **`prompt=create`.** `handle_prompt_create` está em `oauth2_provider/views/base.py:325`.
  Desligado por default (`OIDC_RP_INITIATED_REGISTRATION_ENABLED` falso e
  `OIDC_RP_INITIATED_REGISTRATION_URL` `None`, em `oauth2_provider/settings.py:107-108`), ele
  responde `400 invalid_request`. Ligado, a descoberta acrescenta `create` a
  `prompt_values_supported` (`oauth2_provider/views/oidc.py:99-100`). A URL de cadastro aceita
  nome de rota, caminho ou URL absoluta, como `LOGIN_URL`.
- **Claim `sub`.** `get_claim_dict` (`oauth2_provider/oauth2_validators.py:1337-1348`) põe
  `{"sub": lambda r: str(r.user.pk)}` e aplica `get_additional_claims()` por cima. Devolver
  `"sub"` em `accounts/oauth_validators.py` troca o valor sem sobrescrever método de protocolo.
- **Mapa de claims por scope.** O mapa da base já liga `nickname` e `updated_at` a `profile`, e
  `email_verified` a `email` (`oauth2_validators.py:199`, `:208` e `:210`). Basta devolver as
  claims; o mapa não muda.
- **E-mail.** `UserManager.create_user` (`accounts/models.py:12`) usa `normalize_email`, que só
  põe o domínio em minúsculas.
- **Configuração.** Não há `EMAIL_*` em `config/settings.py` nem em `.env.example`;
  `LANGUAGE_CODE` é `"en-us"` (`config/settings.py:615`); não há DRF em `requirements.txt`.
- **Rotas.** `config/urls.py:53-57` monta login e logout um a um, sem
  `django.contrib.auth.urls`.
- **Bearer e conta inativa.** O toolkit só confere `is_active` na validação de usuário por
  senha (`oauth2_validators.py:1225`), não no Bearer. A API precisa conferir.
- **Efeitos que vêm de graça:**
  - conta desativada perde as outras sessões: o `ModelBackend.get_user` recusa conta inativa;
  - troca de e-mail invalida o link de redefinição pendente: o token do Django inclui o e-mail;
  - `PasswordResetForm.get_users` já compara com `__iexact` e escolhe só contas ativas com senha
    utilizável (`django/contrib/auth/forms.py:440-459`).

---

## 3. Divergências e riscos achados na conferência

Nenhum destes pontos está nas fontes, e cada um muda o que se implementa.

### 3.a A view de recurso responde `403` seco

A jornada (§6, item 9) propõe a API sobre `ScopedProtectedResourceView`. Na 3.4.1, essa view
responde a toda falha com `HttpResponseForbidden()` (`oauth2_provider/views/mixins.py:213-223`).
Ela não separa `401` de `403` e não manda `WWW-Authenticate`, e a §5.2 da jornada exige as duas
coisas: é por elas que a SPA dispara novo login.

O toolkit tem a variante certa, `ScopedProtectedResourceMetadataView`
(`oauth2_provider/views/generic.py:63`). Ela responde `401` para token ausente ou inválido e
`403` para `insufficient_scope`, ambos com o desafio Bearer
(`oauth2_provider/views/mixins.py:371-381`, `oauth2_provider/www_authenticate.py:31-40`). O
validador já marca a falta de scope como `insufficient_scope` (`oauth2_validators.py:405`). O
desafio leva também o parâmetro `resource_metadata` do RFC 9728, que aqui aponta para
`/o/.well-known/oauth-protected-resource`, porque as listas de metadados do toolkit estão
montadas sob `o/` (ADR 0024).

O `dispatch` continua sobrescrito, porque `ProtectedResourceMixin.dispatch` (`mixins.py:254-265`)
guarda só o usuário. Ele não precisa consultar o token de novo: `validate_bearer_token` já o põe
em `r.access_token` (`oauth2_validators.py:683`). A partir dele, o `dispatch` confere a
`Application` e `is_active`, e devolve o `403 aplicacao_nao_autorizada` e o de conta inativa.

**Efeito na SPA:** o cabeçalho traz `resource_metadata`, e o fake de testes da SPA deve imitá-lo
ou ignorá-lo.

### 3.b O limitador de taxa casa o caminho exato

`config/limites.py:90` busca `request.path` em `RATE_LIMIT_POR_CAMINHO`, por igualdade. A rota de
confirmação da redefinição leva `uidb64` e o token no caminho, e nenhuma entrada a alcança. Cada
subcaminho de `/api/conta/` precisa de entrada própria. Decidido em D12.

### 3.c `senha_alterada_em` nasce no `save()`

O lugar óbvio para o carimbo seria `User.set_password`, e ele está errado: no login de uma conta
com hash legado, `check_password` regrava o hash por `set_password` seguido de `save` (o projeto
mantém hashes legados em `config/settings.py:263-269` para esse re-hash). Carimbado ali, um login
comum marcaria "senha trocada em…".

O Django já separa as duas coisas. O `setter` de `check_password` zera `_password` depois do
re-hash, com o comentário "Password hash upgrades shouldn't be considered password changes"
(`django/contrib/auth/base_user.py:106-110`). O `save()` só avisa os validadores de senha quando
`_password` não é `None`. Carimbar no `save()` pela mesma marca cobre admin, `changepassword`,
troca e redefinição, e exclui o re-hash (D14).

O preço é depender de `_password`, que é atributo privado do Django. O comentário ao lado do
carimbo registra isso, e um upgrade do Django relê esse ponto.

### 3.d O resumo do identificador na trilha supõe caixa sensível

O docstring de `_resumo_do_identificador` (`accounts/auditoria.py:68-80`) justifica resumir o
e-mail "como recebido" pela unicidade sensível a caixa do Postgres. Com o e-mail em minúsculas
em todo lugar e a restrição sobre `Lower(email)` (D15), a razão deixa de valer. Decidido em D13.

### 3.e Comentários que passam a mentir

A regra do projeto é que o comentário registra o silêncio. Estes deixam de ser verdade no mesmo
ato da mudança e mudam junto:

- `config/settings.py:148`: "A PK do User é o `sub` de todo id_token";
- `config/settings.py:306-308`: "Este projeto não tem rota de recuperação de senha";
- `config/settings.py:36-43`: o CORS age só sob `/o/`;
- `accounts/models.py:28`: "email_verified só entra com o fluxo que o alimenta";
- `accounts/oauth_validators.py:37-38`: "Sem `email_verified`";
- `accounts/auditoria.py:68-80`: o docstring do resumo (§3.d);
- `accounts/auditoria.py:109`: "`sub` como string, igual à claim `sub`", que segue verdade só se
  a trilha passar ao UUID no mesmo ato;
- `config/urls.py:53-55`: "/accounts/password_reset/ é um 404".

### 3.f A suíte presa ao `sub` igual à chave primária

Afirmam `sub == str(pk)`: `tests/test_auditoria.py:172-181`, `tests/test_logout_rp.py` (linhas
135, 300, 336, 653 e 705) e `tests/logout_helpers.py:130`. `tests/test_password_reset_urls.py`
afirma hoje que a recuperação é 404, e passa a afirmar as rotas novas. A suíte não depende do
idioma: `tests/test_login_view.py:88` e `tests/test_admin_oauth2_application.py:262` evitam
comparar texto de propósito.

### 3.g Variável de ambiente nova sem default derruba o boot

O projeto não tem default no código, e uma variável ausente derruba a instância e a suíte de todo
clone cujo `.env` não a tenha (o precedente é `AUDIT_LOG_PATH`). Entram duas famílias:

- `EMAIL_*`, que guarda segredo e varia por ambiente;
- o `client_id` da SPA, que varia por ambiente: uma `Application` por ambiente, núcleo §4.2
  (D16).

A versão vigente dos termos é literal no código, pela razão escrita em `RATE_LIMIT_POR_CAMINHO`
(`config/settings.py:401-404`): não é segredo, e muda junto com o texto da SPA num ato de código.

A ordem é: `.env.example` atualizado e aviso a quem opera **antes** do merge. O `.env` é de quem
opera.

### 3.h O envio em segundo plano

O envio numa thread do processo precisa partir de `transaction.on_commit`; sem isso, um e-mail
sai para uma operação que o banco desfez. A suíte precisa de um modo síncrono, ou os testes
afirmam sobre uma caixa ainda vazia. No Gunicorn de três workers síncronos, a thread morre com o
worker: é o risco já aceito na §9 da jornada.

### 3.i A N6 precisa nomear a view de recurso

A N6 diz que nenhum método de protocolo do toolkit é sobrescrito, com uma exceção: `/o/logout/`
(ADR 0030). Sobrescrever o `dispatch` de uma view de recurso protegido não é método de protocolo,
mas quem ler a N6 ao lado do código verá um `dispatch` sobrescrito. A ADR do autoatendimento diz
isso, e a N6 ganha a frase.

### 3.j Achado paralelo: `../pre-deploy.md` não existe

O arquivo não está no disco e é citado em `docs/nucleo-idp.md:194`, `docs/seguranca.md:8` e
`:245`, `docs/receita.md:473` e `CLAUDE.md:44`, `:47` e `:105`. Fora do escopo desta tarefa;
fica apontado.

### 3.k A API precisa de `csrf_exempt` explícito

`ProtectedResourceView` (`oauth2_provider/views/generic.py:12`) é uma `View` comum, sem isenção
de CSRF (_Cross-Site Request Forgery_). Um `PATCH` ou `POST` da SPA chega sem cookie de CSRF e
leva `403` do `CsrfViewMiddleware` antes de o Bearer ser lido. A isenção é segura porque a API
não aceita sessão (jornada §5.2), e a ADR registra essa dependência: se um dia a API aceitar
sessão, a isenção vira falha.

### 3.l `login()` no cadastro precisa de `backend=`

Com dois `AUTHENTICATION_BACKENDS` (`config/settings.py:297-300`), `login(request, user)` sem
backend levanta `ValueError`, porque a conta recém-criada não passou por `authenticate()`. O
cadastro passa `backend="django.contrib.auth.backends.ModelBackend"`.

### 3.m "Apagar" alcança três tabelas do `axes`

`AccessAttempt`, `AccessFailureLog` e `AccessLog` (`axes/models.py`) guardam `username`, isto é,
o e-mail digitado. O `AccessLog` vem ligado por default (`AXES_DISABLE_ACCESS_LOG` falso,
`axes/conf.py:91`) e grava o e-mail a cada login bem-sucedido, de modo que toda conta que já
entrou tem linha ali. As linhas antigas guardam a caixa como foi digitada, e por isso a remoção
filtra por `username__iexact`.

### 3.n A migração do `sub` não pode usar default com `unique`

`AddField` com `default=uuid.uuid4` e `unique=True` calcula o default uma vez e dá o mesmo valor a
todas as linhas: a migração falha na restrição única. A ordem é:

1. `AddField` anulável, sem `unique`;
2. `RunPython` com um UUID por conta;
3. `AlterField` para único e não nulo, com o default para as contas novas.

### 3.o A revogação reusa `_revogar`

`_revogar` (`accounts/logout_rp.py:122-151`) já revoga refresh, id_token e access token na ordem
das ligações, por conta e `Application`, dentro de uma transação. A revogação "em todas as
Applications" da troca de senha, da redefinição e da exclusão generaliza essa função (aplicação
opcional) e emite `tokens_revogados`, em vez de duplicar a ordem.

### 3.p O toolkit traduz o protocolo

O toolkit traz tradução `pt_BR`. Com `LANGUAGE_CODE` global em `pt-br`, o `error_description` de
`/o/token/` e o do `WWW-Authenticate` sairiam em português acentuado, fora do conjunto de
caracteres do RFC 6749 §5.2. É a mesma razão pela qual `config/limites.py:143-149` escreve o 429
sem acento. Decidido em D2.

---

## 4. Decisões fechadas

Fechadas pela pessoa usuária em 2026-09-30. Entram na ADR do autoatendimento.

| # | Decisão |
| --- | --- |
| D1 | Nomes de caminhos, campos, configurações e sinais em português, como o código já faz (`auditoria`, `limites`, `desativada_em`); os caminhos propostos na §5.1 da jornada servem |
| D2 | `pt-br` ativado só nas views e nos e-mails de conta (`translation.override`); `LANGUAGE_CODE` continua `"en-us"`, e o protocolo não muda (§3.p) |
| D3 | `nickname` com no máximo 150 caracteres, como `first_name` e `last_name` |
| D4 | Sem `given_name` e `family_name` nesta fase |
| D5 | `post_reset_login` falso: a página final leva a `{SPA_URL}/`, e a entrada passa pelo login |
| D6 | "Criar conta" na tela de login, levando ao cadastro com o `next` preservado |
| D7 | Cadastro sem `next` válido cria a conta, abre a sessão e redireciona a `{SPA_URL}/` |
| D8 | A mensagem de conta desativada só aparece depois do bloqueio do `axes`: conta bloqueada vê a tela de bloqueio, como hoje |
| D9 | A falta de aceite dos termos não bloqueia nada no IdP; o bloqueio é da SPA |
| D10 | Tetos: cadastro e redefinição a 60 por minuto por origem, como o login; API a 120, como `/o/`; cinco envios por destinatário por hora |
| D11 | Carimbos somente leitura, num grupo próprio do `fieldsets` do admin |
| D12 | Teto só nas rotas de caminho fixo; a confirmação da redefinição fica sem teto, protegida pelo token de uso único de uma hora, e a ADR registra a lacuna (§3.b) |
| D13 | Resumo do identificador na trilha calculado em minúsculas, com linha de revisão na ADR 0013 (§3.d) |
| D14 | `senha_alterada_em` carimbado no `save()`, pela marca `_password` do Django (§3.c) |
| D15 | Restrição única sobre `Lower(email)` no banco, além da normalização no código |
| D16 | `client_id` da SPA por variável de ambiente, sem default; o `.env` de cada ambiente recebe o valor antes do merge (§3.g) |
| D17 | Implementação inteira numa tarefa só, pelo `/dev`, e uma implantação só |

---

## 5. Ordem de implementação

A tarefa tem 22 itens na §6 da jornada. Pela D17, todos entram numa tarefa só e numa implantação
só. A ordem abaixo é interna: cada passo deixa a suíte verde antes do seguinte, e cada um se apoia
no anterior. Nenhum passo é implantado sozinho.

### Passo 0 — Decisão, sem código

- A ADR "autoatendimento de conta":
  - substitui a 0023 e a parte da 0003 sobre o `sub`;
  - emenda a N4 e a N6 (§3.i);
  - registra as decisões da §4, a isenção de CSRF da API (§3.k), a lacuna de teto da D12 e os
    riscos aceitos da §9 da jornada;
  - aponta para a ADR par da SPA.
- Linhas de revisão nas ADRs 0013 (D13) e 0016 (D12), ou emendas, conforme a regra de
  imutabilidade.
- **SPA:** escreve a ADR par ("telas de conta", que substitui a 0012 dela). As duas mudam de
  status no mesmo ato.

### Passo 1 — Modelo e contrato de claims

| O quê | Onde |
| --- | --- |
| Campos novos: `sub` (UUID, único, não editável), `nickname` (150), `email_verified`, `email_verificado_em`, `senha_alterada_em`, `updated_at`, `desativada_em`, `desativada_por`, `termos_versao`, `termos_aceitos_em` | `accounts/models.py` |
| Migração do `sub` em três etapas (§3.n); `updated_at = date_joined` para as contas atuais | `accounts/migrations/` |
| Migração do e-mail em minúsculas, que **para** com erro se duas contas colidirem; depois dela, a restrição única sobre `Lower(email)` (D15) | `accounts/migrations/`, `accounts/models.py` |
| Manager grava o e-mail inteiro em minúsculas | `accounts/models.py` |
| Carimbo de `senha_alterada_em` no `save()` (D14) | `accounts/models.py` |
| Admin: campos novos, carimbos somente leitura (D11), reativação zera `desativada_*` | `accounts/admin.py` |
| Claims `sub` (UUID), `email_verified`, `nickname` e `updated_at` em segundos desde 1970 | `accounts/oauth_validators.py` |
| Scope `conta` em `OAUTH2_PROVIDER["SCOPES"]`, com descrição em português | `config/settings.py` |
| Trilha grava o `sub` UUID; resumo do identificador em minúsculas (D13) | `accounts/auditoria.py` |
| Formulário de login próprio: e-mail em minúsculas e mensagem de conta desativada (jornada §4.9, D8), passado ao `LoginView` por `authentication_form` | módulo novo em `accounts/`, `config/urls.py` |
| Comentários da §3.e que tocam este passo | `config/settings.py`, `accounts/models.py`, `accounts/oauth_validators.py`, `accounts/auditoria.py` |
| Testes: §3.f; descoberta lista `conta`, `email_verified`, `nickname`, `updated_at`; colisão de caixa na migração; restrição sobre `Lower(email)`; mensagem de desativada só com a senha certa; `senha_alterada_em` não muda no re-hash; `updated_at` não muda com login nem troca de senha | `tests/` |

### Passo 2 — Envio de e-mail

| O quê | Onde |
| --- | --- |
| `EMAIL_*` pelo `django-environ`, sem default no código, com `EMAIL_TIMEOUT`; backend de console em desenvolvimento | `config/settings.py`, `.env.example` |
| Envio em segundo plano, a partir de `transaction.on_commit`, com modo síncrono na suíte; falha vai ao log operacional (§3.h) | módulo novo em `accounts/` |
| Teto de cinco envios por destinatário por hora (D10), com contador no Redis e chave no formato de `config/limites.py` | módulo novo em `accounts/` |
| Token de confirmação por `django.core.signing`, salt próprio, prazo de 7 dias, carregando `sub` e e-mail | módulo novo em `accounts/` |
| Os seis e-mails da jornada §5.4, em português (D2), no fuso `America/Sao_Paulo` | `templates/` |

### Passo 3 — API de conta

| O quê | Onde |
| --- | --- |
| `GET` e `PATCH /api/conta/`, `POST /api/conta/confirmacao/`, `POST /api/conta/termos/`, sobre `ScopedProtectedResourceMetadataView` com scope `conta` (§3.a) e `csrf_exempt` (§3.k) | módulo novo em `accounts/`, `config/urls.py` |
| `dispatch` que lê `r.access_token`, confere a `Application` da SPA e recusa conta inativa | mesmo módulo |
| `GET /api/conta/confirmar/?t=` sem autenticação: confirma e redireciona a `{SPA_URL}/?email=confirmado` ou `?email=invalido` | mesmo módulo |
| Erros `400` no formato `{"erros": {campo: [{codigo, mensagem}]}}`; lista fechada de campos no `PATCH` | mesmo módulo |
| `client_id` da SPA por ambiente (D16); versão vigente dos termos como literal | `config/settings.py`, `.env.example` |
| `CORS_URLS_REGEX` cobrindo `^/api/conta/`; tetos da API, um por subcaminho (D10, D12) | `config/settings.py` |
| Sinais `email_confirmado`, `conta_editada`, `termos_aceitos` | `accounts/auditoria.py` |
| Testes: `401` e `403 insufficient_scope` com `WWW-Authenticate`; `PATCH` sem CSRF aceito com Bearer; token de outra `Application`; conta inativa; campo fora da lista; termos desatualizados; link expirado e link de e-mail já trocado; CORS na rota nova | `tests/` |

### Passo 4 — Páginas do IdP

Na ordem do menor para o maior risco. Cada página tem template, CSRF, requisitos de senha
visíveis (`password_validators_help_texts`), destino de volta fixo, `pt-br` ativado (D2) e sinal
na trilha:

1. **Recuperação de senha:** as quatro rotas do Django, uma a uma; `PasswordResetForm` com envio
   em segundo plano e teto; `PASSWORD_RESET_TIMEOUT` de uma hora; `post_reset_login` falso (D5).
   Ao concluir: revoga os tokens (§3.o) e põe `email_verified = true`.
2. **Troca de senha:** `PasswordChangeView` com o formulário estendido para conferir por
   `authenticate()`, de modo que o `axes` conte as falhas; revoga os tokens (§3.o).
3. **Cadastro:** liga `OIDC_RP_INITIATED_REGISTRATION_ENABLED` e a URL; página que valida, cria a
   conta, faz `login()` com `backend=` (§3.l) e segue o `next` conferido como o `LoginView`
   confere, ou vai a `{SPA_URL}/` sem ele (D7).
4. **Troca de e-mail:** senha atual por `authenticate()`, minúsculas, unicidade, `email_verified`
   zerado, confirmação ao endereço novo e aviso ao antigo.
5. **Exclusão:** recusa conta `is_staff` ou `is_superuser` na exibição e no envio; e-mail
   enfileirado antes de apagar; revoga os tokens (§3.o); desativar, ou apagar removendo as três
   tabelas do `axes` por `username__iexact` (§3.m); encerra a sessão.

Também: tetos das rotas públicas de caminho fixo (D10, D12); link "Esqueci a senha" e "Criar
conta" (D6) na tela de login; `tests/test_password_reset_urls.py` invertido; o restante da §3.e.

### Passo 5 — Documentação e implantação

- Atualizar `docs/nucleo-idp.md` (§2 e §3), `docs/integracao-rp.md`, `docs/seguranca.md`,
  `docs/testes.md`, `docs/receita.md` e `docs/observabilidade.md`.
- Implantação única do IdP. Logo depois dela, as sessões abertas da SPA mostram "Não foi possível
  obter o userinfo" até o reload (domínio §6.3).
- Conferir na descoberta `conta` em `scopes_supported`, `email_verified` em `claims_supported` e
  `create` em `prompt_values_supported`.
- **Efeito na SPA:** só depois disso a SPA implanta. Implantada antes, o pedido com `conta`
  falharia com `invalid_scope`, e "Criar conta" receberia `400`.

---

## 6. Critério de pronto e pendências

O lado do IdP está pronto quando:

- a suíte cobre cada linha das §4 e §5 da jornada, com os casos do item 22 da §6 dela e os testes
  listados na §5 deste relatório;
- a descoberta implantada confere (passo 5).

A jornada só está integrada quando o roteiro da §11 dela fecha contra o IdP real, primeiro em
desenvolvimento e depois em produção.

**Pendências fora do código:**

- **Pessoa dona do sistema:**
  - termos de uso e política de privacidade, versão 1;
  - conta SMTP (_Simple Mail Transfer Protocol_), que no Gmail pede verificação em duas etapas e
    senha de app;
  - remetente exibido.
- **Quem opera:** `EMAIL_*` e o `client_id` da SPA no `.env` de cada ambiente, antes do merge.

**Entrada:** a tarefa abre pelo `/dev`, com este relatório como fonte, e começa pelo passo 0.
