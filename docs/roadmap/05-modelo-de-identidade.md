# Passo 05 — Modelo de identidade

## Objetivo

Definir `accounts.User` — o registro canônico sobre o qual todo token emitido faz
afirmações — antes de existir qualquer migração.

## Depende de

Passo 04, porque `AUTH_USER_MODEL = "accounts.User"` já está apontado e `accounts` já está
em `INSTALLED_APPS`. O modelo tem de existir antes do passo 06, que é o ponto de não
retorno.

## Arquivos criados

- `accounts/__init__.py` — pacote do app.
- `accounts/apps.py` — `AppConfig`.
- `accounts/models.py` — `User` e `UserManager`.
- `accounts/admin.py` — registro do `User` no admin.
- `accounts/migrations/__init__.py` — pacote de migrations, **vazio**. A `0001` é gerada no
  passo 06, nunca escrita.

`accounts/views.py` **não** é criado: login e logout são views prontas do
`django.contrib.auth`. `accounts/managers.py` também não: um manager de cerca de dez
linhas mora em `models.py`.

## O que fazer

### `User`

Subclasse de `AbstractUser` com:

- `username = None`
- `email` unique, como `USERNAME_FIELD`
- `REQUIRED_FIELDS = []`

Herdar de `AbstractUser` preserva `is_staff`, `is_active`, permissões, admin e o framework
de autenticação inteiro funcionando.

Preserva também `first_name` e `last_name`, e com eles o `get_full_name()` — **é dele que
a claim `name` vai sair no passo 08**. Nenhum campo de nome é acrescentado aqui: usar o
que `AbstractUser` já traz evita um segundo lugar onde o nome da pessoa existe.

Consequência a registrar, porque ela aparece do lado da relying party: enquanto
`first_name` e `last_name` estiverem vazios — e eles nascem vazios, porque nada nesta fase
os pede —, `get_full_name()` devolve **string vazia** e a claim `name` chega vazia à RP. É
comportamento esperado, não defeito; preencher os campos pelo admin resolve caso a caso, e
um formulário de cadastro que os peça é fase seguinte.

### `UserManager`

Manager próprio com `create_user` e `create_superuser` por e-mail. É obrigatório: com
`username = None`, o manager padrão do Django não sabe criar usuário.

### `admin.py`

Registro do `User` no admin, ajustado para um modelo sem `username`. O admin é a interface
de gestão de usuários e, no passo 07, de registro de clients — ele é a única UI
administrativa desta fase.

### Sem `email_verified`

Nenhum campo especulativo entra agora. Em particular, **não** incluir `email_verified`:
sem fluxo de verificação implementado, a claim seria sempre falsa, e um IdP que afirma
falsidades sobre a identidade é pior que um que se cala. O campo entra junto com o fluxo
que o alimenta.

Consequência a registrar: nesta fase as relying parties **não distinguirão e-mail
verificado de não verificado**. É trabalho de fase seguinte.

## Proibições que incidem aqui

- **Não rodar `migrate` ainda.** A migração é o passo 06, depois de `makemigrations
  accounts`.
- **Não escrever migration à mão.** Migrations são geradas por `makemigrations`. Migration
  manual em modelo de usuário é como este tipo de projeto adquire divergência silenciosa
  entre schema e código.
- **Não adicionar campo especulativo** (`email_verified`, telefone, perfil). Cada um entra
  com o fluxo que o justifica.
- **Não coletar senha em nenhum lugar que não seja a máquina de autenticação do Django.**
  O modelo não ganha campo de credencial próprio nem lógica de verificação paralela.

## Riscos e sinais

- **`AUTH_USER_MODEL` divergente do app real** — sinal: `makemigrations` falha com erro de
  modelo não encontrado. Falha ruidosa e imediata.
- **Ausência de `UserManager`** — sinal: `createsuperuser` falha pedindo `username`, ou a
  criação programática de usuário quebra. Aparece no passo 06.

## Passo concluído quando

`python manage.py check` passa, `python manage.py makemigrations accounts --dry-run` mostra
a criação do modelo `User` e nenhuma migração foi aplicada ainda.
