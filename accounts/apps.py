from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = "accounts"

    def ready(self):
        # Import aqui dentro, e não no topo do módulo: `accounts.auditoria` importa os
        # sinais do toolkit, e o AppConfig é carregado antes de o registro de apps estar
        # pronto. ready() é o momento em que o Django garante os modelos carregados.
        from accounts.auditoria import ligar_receptores

        ligar_receptores()
