"""O que o IdP afirma sobre a pessoa: mapeamento do `accounts.User` para claims OIDC.

Mora em `accounts` porque é o app dono da identidade — quem define o que um token
afirma sobre a pessoa e quem possui a pessoa. Único ponto em que o comportamento do
servidor de autorização é customizado (ADR 0002), e o contrato com a settings é por
string, resolvido em runtime: caminho errado em OAUTH2_VALIDATOR_CLASS falha no boot.
"""

from oauth2_provider.oauth2_validators import OAuth2Validator


class IdPOAuth2Validator(OAuth2Validator):
    """Decide claims, não fluxo. Nenhum método de protocolo do DOT é sobrescrito aqui."""

    # Ancora contra mudança de default: na 3.4.1 `name -> profile` e `email -> email` já
    # constam idênticos no mapa da base (oauth2_validators.py:195 e :209), de modo que a
    # declaração não acrescenta claim nenhuma hoje. Ela existe para que uma reorganização
    # do mapa upstream não remova em silêncio o scope que libera as duas claims: claim
    # mapeada para scope não concedido apenas some do token, sem erro.
    oidc_claim_scope = {**OAuth2Validator.oidc_claim_scope, "name": "profile", "email": "email"}

    def get_additional_claims(self):
        """Forma agnóstica ao request: UM parâmetro, valores callables que recebem o request.

        A aridade é a interface. A base discrimina as duas assinaturas contando parâmetros
        (oauth2_validators.py:1330-1332); os callables são invocados em `get_oidc_claims`
        por `v(request) if callable(v) else v` (:1366). Só a forma agnóstica entra em
        `get_discovery_claims` (:1352-1356) — com a forma de dois parâmetros a discovery
        publicaria `claims_supported: ["sub"]` enquanto o servidor emite `sub`, `name` e
        `email`, um IdP subdeclarando o que afirma sem que nenhuma leitura do fluxo acuse.

        `name` sai de `get_full_name()`, herdado de AbstractUser, e não de um campo novo:
        um segundo lugar guardando o nome seria um segundo lugar para ele divergir. Com
        first_name/last_name em branco a claim chega presente e vazia — não é defeito daqui.

        Sem `email_verified`: não há fluxo de verificação nesta fase, e a claim seria uma
        afirmação que o IdP não sustenta.
        """
        return {
            "name": lambda request: request.user.get_full_name(),
            "email": lambda request: request.user.email,
        }
