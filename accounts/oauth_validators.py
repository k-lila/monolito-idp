"""O que o IdP afirma sobre a pessoa: mapeamento do `accounts.User` para claims OIDC.

Mora em `accounts` porque é o app dono da identidade — quem define o que um token
afirma sobre a pessoa e quem possui a pessoa. Único ponto de customização de claims
(ADR 0002); o logout iniciado pela relying party (RP) é a subclasse da ADR 0030, em
`accounts/logout_rp.py`. O contrato com a settings é por string, resolvido em runtime:
caminho errado em OAUTH2_VALIDATOR_CLASS falha no boot.
"""

from oauth2_provider.oauth2_validators import OAuth2Validator


class IdPOAuth2Validator(OAuth2Validator):
    """Decide claims, não fluxo. Nenhum método de protocolo do DOT é sobrescrito aqui."""

    # Ancora contra mudança de default: na 3.4.1 as cinco já constam idênticas no mapa da base
    # (oauth2_validators.py:195, :199, :208, :209 e :210), de modo que a declaração não
    # acrescenta claim nenhuma hoje. Ela existe para que uma reorganização do mapa upstream
    # não remova em silêncio o scope que libera cada claim: claim mapeada para scope não
    # concedido apenas some do token, sem erro.
    oidc_claim_scope = {
        **OAuth2Validator.oidc_claim_scope,
        "name": "profile",
        "nickname": "profile",
        "updated_at": "profile",
        "email": "email",
        "email_verified": "email",
    }

    def get_additional_claims(self):
        """Forma agnóstica ao request: UM parâmetro, valores callables que recebem o request.

        A aridade é a interface. A base discrimina as duas assinaturas contando parâmetros
        (oauth2_validators.py:1330-1332); os callables são invocados em `get_oidc_claims`
        por `v(request) if callable(v) else v` (:1366). Só a forma agnóstica entra em
        `get_discovery_claims` (:1352-1356) — com a forma de dois parâmetros a discovery
        publicaria `claims_supported: ["sub"]` enquanto o servidor emite `sub`, `name` e
        `email`, um IdP subdeclarando o que afirma sem que nenhuma leitura do fluxo acuse.

        `sub` é o UUID da conta, e não a chave primária (ADR 0031). A base começa por
        `str(r.user.pk)` (:1339) e aplica este dicionário por cima, e é por isso que a troca
        mora aqui e não num método de protocolo. Retirada esta linha, o `sub` volta à chave
        primária sem erro nenhum, e cada RP passa a ver outra pessoa.

        `name` sai de `get_full_name()`, herdado de AbstractUser, e não de um campo novo:
        um segundo lugar guardando o nome seria um segundo lugar para ele divergir. Com
        first_name/last_name em branco a claim chega presente e vazia — não é defeito daqui.
        `nickname` também chega presente quando vazio. `updated_at` sai em segundos inteiros
        desde 1970, a forma que o OIDC Core fixa para a claim.
        """
        return {
            "sub": lambda request: str(request.user.sub),
            "name": lambda request: request.user.get_full_name(),
            "nickname": lambda request: request.user.nickname,
            "updated_at": lambda request: int(request.user.updated_at.timestamp()),
            "email": lambda request: request.user.email,
            "email_verified": lambda request: request.user.email_verified,
        }
