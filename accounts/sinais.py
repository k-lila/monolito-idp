"""Os sinais de conta que a trilha de auditoria registra (ADR 0031).

Definidos aqui, e não em quem os emite, porque mais de um módulo emite o mesmo evento e nenhum
deles é dono do sinal. Os receptores estão em `accounts/auditoria.py`, e `event` na trilha
recebe o nome do sinal (ADR 0013).

Todos são enviados com `request` e `user`, salvo `conta_apagada`, que leva o `sub` da conta
que já não existe. E só depois de a gravação ter sido confirmada: a trilha é arquivo, não volta
com o rollback, e um sinal emitido antes do commit registraria o que o banco desfez.
"""

from django.dispatch import Signal

# O cadastro pela página do IdP. A conta criada pelo admin não emite.
conta_criada = Signal()

# A primeira confirmação do e-mail atual. O segundo clique no mesmo link não emite.
email_confirmado = Signal()

# A edição do perfil pela API. Argumento extra: `campos`, a lista dos nomes que mudaram de valor,
# nunca os valores. Edição que não muda nada não emite.
conta_editada = Signal()

# O aceite dos termos. Argumento extra: `termos_versao`, a versão aceita.
termos_aceitos = Signal()

# A troca do e-mail pela página do IdP. A troca pelo admin não emite. Nenhum dos dois endereços
# vai junto.
email_trocado = Signal()

# A troca de senha pela página do IdP, com a senha atual.
senha_trocada = Signal()

# O pedido de recuperação que enfileirou um link. Sem conta, ou com o envio suprimido pelo teto,
# não emite.
recuperacao_pedida = Signal()

# A senha nova escolhida pelo link de redefinição.
senha_redefinida = Signal()

# A desativação pela própria pessoa. A do admin não emite.
conta_desativada = Signal()

# A exclusão pela própria pessoa. Argumento: `sub`, em texto, no lugar de `user`.
conta_apagada = Signal()
