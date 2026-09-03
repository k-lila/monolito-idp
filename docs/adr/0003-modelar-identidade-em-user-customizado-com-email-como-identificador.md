# 0003. Modelar a identidade em um User customizado com e-mail como identificador

## Status

Aceito — 2026-08-29

## Contexto

O IdP (Identity Provider) é o dono da identidade: o modelo de usuário é o registro canônico
sobre o qual todo token emitido faz afirmações. Em OIDC (OpenID Connect), as claims padrão de
um sujeito são sub, email, name e correlatas — o e-mail não é atributo secundário, é o
identificador que as relying parties (RPs) esperam ver.

O modelo default do Django usa username como identificador e traz email como campo comum, sem
unicidade. Isso desalinha o modelo do vocabulário do protocolo e permite dois usuários com o
mesmo e-mail, o que num IdP é ambiguidade de identidade.

A restrição decisiva é temporal: AUTH_USER_MODEL é resolvido em tempo de migration e
referenciado por chave estrangeira por django.contrib.admin e por todas as tabelas do
django-oauth-toolkit, e gravado como tipo de modelo pelo contenttypes. Trocar o modelo depois
da primeira migração significa refazer esse conjunto inteiro de referências. A decisão precisa
ser tomada antes de existir qualquer banco.

## Decisão

Vamos definir accounts.User como subclasse de AbstractUser com username = None, email unique
como USERNAME_FIELD, REQUIRED_FIELDS vazio e um UserManager próprio para create_user e
create_superuser por e-mail. AUTH_USER_MODEL aponta para ele desde a primeira linha de
settings, antes de qualquer migrate. A chave primária é um BigAutoField, fixado por
DEFAULT_AUTO_FIELD nas settings, e é ela que vai na claim sub.

Nenhum campo especulativo entra agora. Em particular, não incluímos email_verified: sem fluxo
de verificação implementado, a claim seria sempre falsa, e um IdP que afirma falsidades sobre a
identidade é pior que um que se cala. O campo entra junto com o fluxo que o alimenta.

## Consequências

Positivas:

- O identificador da conta coincide com a claim que as RPs consomem; não há tradução nem
  ambiguidade entre o modelo e o protocolo.
- Unicidade de e-mail no nível do banco elimina uma classe inteira de confusão de identidade.
- Ganhamos o ponto de extensão natural para claims futuras (e-mail verificado, telefone,
  perfil) sem tocar em AUTH_USER_MODEL de novo.
- Herdar de AbstractUser preserva is_staff, is_active, permissões, admin e o framework de
  autenticação inteiro funcionando.

Negativas:

- Exige um UserManager próprio e cuidado com todo código que assuma a existência de username;
  bibliotecas de terceiros que presumam esse campo podem quebrar.
- Prende o projeto a AbstractUser: migrar mais tarde para um AbstractBaseUser mais enxuto
  significaria descartar campos com dados.
- O e-mail passa a ser credencial de login e chave natural de identidade. O sub emitido nos
  tokens é a chave primária do usuário e não muda com o e-mail, mas permitir troca de e-mail
  ainda exigirá decidir o que acontece com sessões vivas e com RPs que tenham correlacionado a
  conta pelo endereço.
- Carrega first_name/last_name herdados, que não são o modelo de nome mais rico possível para
  OIDC.

## Alternativas consideradas

- **User default do Django** — nenhum custo inicial, mas a troca posterior é notoriamente cara
  e, num IdP, seria inevitável. Adiar essa dor não a reduz.
- **AbstractBaseUser puro** — modelo mínimo, sem herança desnecessária, mas exigiria
  reimplementar permissões e integração com o admin, gastando esforço em algo que o
  AbstractUser entrega correto.
- **UUID como identificador de login** — mais estável que e-mail, porém ninguém digita UUID
  numa tela de login; o e-mail continuaria necessário e único de qualquer forma.
