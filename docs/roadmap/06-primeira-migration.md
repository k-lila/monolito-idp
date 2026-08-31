# Passo 06 — Primeira migration

> ## PONTO DE NÃO RETORNO
>
> **Este é o único ponto de não retorno interno de toda a ordem de implementação.** Todo
> o resto desta sequência é reordenável a custo de depuração; este não é.
>
> A ordem é: `makemigrations accounts` **primeiro**, `migrate` **depois**. Nunca o
> inverso, nunca `migrate` isolado antes de a `0001` de `accounts` existir.

## Objetivo

Gerar a migração inicial de `accounts` e aplicar o primeiro `migrate` contra um banco
vazio, com `AUTH_USER_MODEL` já resolvido para `accounts.User`.

## Depende de

- Passo 04, por `AUTH_USER_MODEL = "accounts.User"` nas settings.
- Passo 05, pelo modelo existir de fato.
- Passo 02, pelo Postgres de pé — **e vazio**.

Estas três dependências são a razão de este passo ser o sexto e não antes. Não são
preferência de organização: são a condição para o banco nascer certo.

## Arquivos criados

- `accounts/migrations/0001_initial.py` — **GERADA** por `makemigrations accounts`. Não é
  escrita à mão, não é editada depois.

## O que fazer

Nesta ordem, sem inverter:

```
python manage.py makemigrations accounts
python manage.py migrate
```

Conferir, antes do `migrate`, que a `0001_initial.py` foi gerada e cria o modelo `User` em
`accounts`.

Depois do `migrate`, conferir no banco que existe a tabela de `accounts` e que **não**
existe `auth_user`.

Criar o superusuário com `python manage.py createsuperuser` — o e-mail é o identificador,
não há `username`.

## Por que é irreversível

`AUTH_USER_MODEL` é resolvido em tempo de migration e referenciado por chave estrangeira
por dois consumidores distintos:

- `django.contrib.admin`, cujas entradas de log apontam FK ao usuário;
- **todas as tabelas do django-oauth-toolkit** — `Application`, `AccessToken`, `Grant`,
  `RefreshToken`, `IDToken` e `DeviceGrant` — que resolvem `settings.AUTH_USER_MODEL` na
  própria migração.

Há um terceiro consumidor que não é FK: o `django.contrib.contenttypes` **grava o tipo do
modelo** de usuário. `django_content_type` não tem chave estrangeira para tabela de
usuário nenhuma — a linha `accounts | user` ali é sinal de ancoragem, não referência.

Rodar `migrate` antes de a `0001` de `accounts` existir ancora os três no User padrão do
Django. Depois disso, o schema e as settings discordam permanentemente, e trocar o modelo
de usuário é uma das operações mais caras do ecossistema Django.

## Saída, em greenfield

Não há reparo elegante. **A saída realista é apagar o volume do Postgres e recomeçar do
passo 02.** Enquanto não houver dado nenhum de valor no banco, isso custa um comando; é
por isso que este passo vem antes de qualquer coisa interessante existir.

## Proibições que incidem aqui

- **Não rodar `migrate` antes de `accounts.User` existir e de `AUTH_USER_MODEL` estar
  apontado.** É o único erro deste scaffold cuja correção é apagar o banco.
- **Não escrever migration à mão.** Nem esta, nem nenhuma outra.
- **Não editar a `0001_initial.py` depois de gerada.** Mudança de modelo gera migração
  nova.

## Riscos e sinais

- **`migrate` executado antes de `AUTH_USER_MODEL` existir** — sinal: **a tabela
  `auth_user` aparece no banco**, ou `makemigrations` acusa dependência inconsistente de
  `contenttypes`. Este é o sinal a procurar ativamente logo depois do primeiro `migrate`;
  ele não se anuncia sozinho.
- **Volume do Postgres reaproveitado** — sinal: o mesmo acima, com a agravante de o banco
  parecer saudável. Antes de migrar, confirmar que o volume é novo.
- **Ausência de `UserManager`** — sinal: `createsuperuser` falha pedindo `username`.

## Passo concluído quando

`python manage.py migrate` completa sem erro; a tabela de usuários de `accounts` existe e
`auth_user` **não** existe; `createsuperuser` cria uma conta por e-mail e essa conta
autentica em `/admin/`.
