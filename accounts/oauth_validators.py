"""O que o IdP afirma sobre a pessoa: mapeamento do `accounts.User` para claims OIDC.

Mora em `accounts` porque e o app dono da identidade — quem define o que um token
afirma sobre a pessoa e quem possui a pessoa. Unico ponto em que o comportamento do
servidor de autorizacao e customizado (ADR 0002), e o contrato com a settings e por
string, resolvido em runtime: caminho errado em OAUTH2_VALIDATOR_CLASS falha no boot.
"""

from oauth2_provider.oauth2_validators import OAuth2Validator


class IdPOAuth2Validator(OAuth2Validator):
    """Decide claims, nao fluxo. Nenhum metodo de protocolo do DOT e sobrescrito aqui."""

    # Ancora contra mudanca de default: na 3.4.1 `name -> profile` e `email -> email` ja
    # constam identicos no mapa da base (oauth2_validators.py:195 e :209), de modo que a
    # declaracao nao acrescenta claim nenhuma hoje. Ela existe para que uma reorganizacao
    # do mapa upstream nao remova em silencio o scope que libera as duas claims: claim
    # mapeada para scope nao concedido apenas some do token, sem erro.
    oidc_claim_scope = {**OAuth2Validator.oidc_claim_scope, "name": "profile", "email": "email"}

    def get_additional_claims(self):
        """Forma agnostica ao request: UM parametro, valores callables que recebem o request.

        A aridade e a interface. A base discrimina as duas assinaturas contando parametros
        (oauth2_validators.py:1330-1332); os callables sao invocados em `get_oidc_claims`
        por `v(request) if callable(v) else v` (:1366). So a forma agnostica entra em
        `get_discovery_claims` (:1352-1356) — com a forma de dois parametros a discovery
        publicaria `claims_supported: ["sub"]` enquanto o servidor emite `sub`, `name` e
        `email`, um IdP subdeclarando o que afirma sem que nenhuma leitura do fluxo acuse.

        `name` sai de `get_full_name()`, herdado de AbstractUser, e nao de um campo novo:
        um segundo lugar guardando o nome seria um segundo lugar para ele divergir. Com
        first_name/last_name em branco a claim chega presente e vazia — nao e defeito daqui.

        Sem `email_verified`: nao ha fluxo de verificacao nesta fase, e a claim seria uma
        afirmacao que o IdP nao sustenta.
        """
        return {
            "name": lambda request: request.user.get_full_name(),
            "email": lambda request: request.user.email,
        }
