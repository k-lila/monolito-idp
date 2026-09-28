"""TASK-023/T-01, T-02 — o endereço fixo do `cloudflared` na rede `borda` bate, literal
por literal, entre `docker/Caddyfile` e `docker-compose.prod.yml` (T-01), e esse mesmo
endereço fica dentro da `subnet` e fora do `ip_range` — a faixa de alocação dinâmica —
declarados para a rede `borda` no override de produção (T-02).

Demanda do quality-assurance (T-01): os dois arquivos guardam o mesmo endereço IPv4 sem
variável que os una — `docker/Caddyfile` mesmo o registra, no comentário sobre
`trusted_proxies`: "O literal é o `ipv4_address` do `cloudflared` na rede `borda` e vive
também em `docker-compose.prod.yml`, sincronizado à mão. [...] Trocar um sem o outro
produz o silêncio abaixo." O silêncio que se segue, sob "O SILÊNCIO DESTA CONFIANÇA" no
mesmo arquivo, é o que este teste guarda: com os dois literais divergentes, toda linha da
trilha de auditoria sai com o mesmo `ip`, `ip_src` = `forwarded` e `ip_edge` = `peer`,
cada uma com a forma de uma linha correta — nada dá erro —, e o limitador de taxa de
`/o/` e o `django-axes` contam o tráfego inteiro numa chave só, de modo que o primeiro
cliente que os aciona tranca todos os outros. A ADR (Architecture Decision Record) 0027
nomeia a duplicação em "Literal duplicado": não há variável que una os dois arquivos, e
por isso a única guarda possível é a comparação textual entre eles.

Demanda do quality-assurance (T-02, R4 do senso-crítico): a igualdade textual do T-01
não basta. Se alguém trocar os dois literais — `trusted_proxies` no Caddyfile e
`ipv4_address` no override — para um mesmo endereço dentro do `ip_range` da rede `borda`
(por exemplo `10.203.14.50`, dentro de `10.203.14.0/25`), o T-01 continua verde: os dois
arquivos concordam entre si. O comentário da rede `borda`, em `docker-compose.prod.yml`
("o `.200` fica fora dela de propósito, e o `proxy` nunca o toma"), registra a garantia
que esse acordo sozinho não prova. O SILÊNCIO GUARDADO aqui: num recreate ou reboot, o
Docker pode entregar ao `proxy` — que também está na rede `borda` e não tem endereço
fixo — um endereço da faixa dinâmica antes de o `cloudflared` subir; se esse endereço for
o mesmo que o conector reivindica, o `cloudflared` não sobe (endereço em uso). Sob
`restart: unless-stopped`, essa falha de início não é reparada — a política reage a
processo que sai, não a processo que nunca chega a subir —, e a borda da Cloudflare
responde 1033 sem nenhum sinal no host, fora dos logs do `cloudflared`. Este teste fecha
essa lacuna: prova que o endereço fixo do conector cai fora da faixa que o Docker pode
entregar a outro serviço, e que a própria faixa dinâmica não extrapola a sub-rede
declarada — checagem que nenhuma comparação textual entre dois literais faz sozinha.

Nível unitário (`SimpleTestCase`, sem banco): os arquivos são lidos como texto puro, a
partir de `settings.BASE_DIR`, e comparados por regex — sem PyYAML, que não está em
`requirements.txt`, e sem carregar Docker Compose nem Caddy de verdade. Não depende de
banco, rede nem contêiner, e a divergência que cada teste guarda não aparece em nenhum
outro nível: nenhum outro mecanismo — nem o `config` do Compose, nem o Caddy ao subir —
compara os literais ou confere a relação entre `ip_range` e `subnet`.

Forma: as regex são ancoradas em início e fim de linha (`re.MULTILINE`), para que os
comentários que citam o endereço ou a sub-rede — há vários, nos dois arquivos — não
entrem na contagem. Cada extração tem de achar **exatamente uma** ocorrência: exigir
exatamente uma faz o teste acusar alto nos dois sentidos — zero (a diretiva que mudou de
forma, a chave renomeada no override) ou duas ou mais (um segundo par confiável no
Caddyfile, `ipv4_address` duplicado no override, uma segunda rede com `ipam` no arquivo)
— em vez de escolher a primeira em silêncio. Hoje há só uma rede com `ipam` declarado em
`docker-compose.prod.yml`, a `borda`; se um dia houver uma segunda, a extração acusa alto
em vez de escolher uma das duas em silêncio. Nenhum dos valores é fixado no teste: o que
está sob prova, no T-01, é a igualdade entre os dois arquivos, e no T-02, a relação de
contenção entre o endereço, o `ip_range` e a `subnet` — não os valores de hoje
(`10.203.14.200`, `10.203.14.0/25`, `10.203.14.0/24`).
"""

import ipaddress
import re

from django.conf import settings
from django.test import SimpleTestCase

_CAMINHO_CADDYFILE = settings.BASE_DIR / "docker" / "Caddyfile"
_CAMINHO_OVERRIDE_PROD = settings.BASE_DIR / "docker-compose.prod.yml"

# Ancoradas em início e fim de linha: um comentário que cite o endereço no meio de uma
# frase não bate com nenhuma das duas, porque a diretiva de verdade ocupa a linha inteira
# (mais espaço em branco de indentação, que \s* absorve).
REGEX_TRUSTED_PROXIES = re.compile(
    r"^\s*trusted_proxies\s+static\s+(\d{1,3}(?:\.\d{1,3}){3})/32\s*$", re.MULTILINE
)
REGEX_IPV4_ADDRESS = re.compile(
    r"^\s*ipv4_address:\s*(\d{1,3}(?:\.\d{1,3}){3})\s*$", re.MULTILINE
)

# As duas chaves do `ipam.config` da rede `borda`, no mesmo espírito das anteriores:
# ancoradas em início e fim de linha, para que o comentário acima delas (que cita as
# duas, "O `ip_range` é a faixa de alocação dinâmica...") não entre na contagem. O `-`
# de `subnet` é opcional na regex porque é YAML de lista (`- subnet: ...`), e
# `ip_range:` vem na linha seguinte, sem ele.
REGEX_SUBNET_BORDA = re.compile(
    r"^\s*-?\s*subnet:\s*(\d{1,3}(?:\.\d{1,3}){3}/\d{1,2})\s*$", re.MULTILINE
)
REGEX_IP_RANGE_BORDA = re.compile(
    r"^\s*ip_range:\s*(\d{1,3}(?:\.\d{1,3}){3}/\d{1,2})\s*$", re.MULTILINE
)


def extrair_ocorrencias(texto, regex):
    """Todas as capturas de `regex` em `texto`, na ordem em que aparecem.

    Função pura, sem `TestCase` nenhum: devolve a lista crua, e é a chamadora — o caso de
    teste abaixo — quem decide o que fazer com uma contagem diferente de um. Separar
    extração de asserção é o que permite provar o teste vermelho sem escrever num arquivo
    versionado: uma cópia do texto com um literal trocado passa pelas mesmas duas funções.
    """
    return regex.findall(texto)


class BordaDoTunelTests(SimpleTestCase):
    """TASK-023/T-01, T-02. O endereço do `cloudflared` tem de ser o mesmo nos dois
    arquivos que o guardam sem variável que os una (T-01), e esse endereço tem de cair
    fora da faixa de alocação dinâmica que o Docker pode entregar a outro serviço da
    mesma rede (T-02) — ver docstring do módulo."""

    def test_endereco_do_caddyfile_bate_com_o_do_override_de_producao(self):
        texto_caddyfile = _CAMINHO_CADDYFILE.read_text(encoding="utf-8")
        texto_override = _CAMINHO_OVERRIDE_PROD.read_text(encoding="utf-8")

        ocorrencias_caddyfile = extrair_ocorrencias(texto_caddyfile, REGEX_TRUSTED_PROXIES)
        ocorrencias_override = extrair_ocorrencias(texto_override, REGEX_IPV4_ADDRESS)

        self.assertEqual(
            len(ocorrencias_caddyfile),
            1,
            f"docker/Caddyfile: esperava exatamente uma ocorrência de "
            f"'trusted_proxies static ...  /32', achou {ocorrencias_caddyfile!r}.",
        )
        self.assertEqual(
            len(ocorrencias_override),
            1,
            f"docker-compose.prod.yml: esperava exatamente uma ocorrência de "
            f"'ipv4_address: ...', achou {ocorrencias_override!r}.",
        )

        endereco_caddyfile = ocorrencias_caddyfile[0]
        endereco_override = ocorrencias_override[0]

        self.assertEqual(
            endereco_caddyfile,
            endereco_override,
            "docker/Caddyfile tem 'trusted_proxies static "
            f"{endereco_caddyfile}/32', docker-compose.prod.yml tem 'ipv4_address: "
            f"{endereco_override}' — os dois endereços divergem, e o silêncio "
            "descrito em docker/Caddyfile ('O SILÊNCIO DESTA CONFIANÇA') e na ADR 0027 "
            "('Literal duplicado') passa a valer.",
        )

    def test_endereco_do_conector_fica_fora_da_faixa_dinamica_do_ip_range(self):
        """TASK-023/T-02. A igualdade entre os dois literais (T-01) não garante que o
        endereço fixo do `cloudflared` seja alcançável: se ele cair dentro do
        `ip_range` — a faixa de onde o Docker aloca endereço dinâmico para o `proxy`,
        também na rede `borda` —, um recreate ou reboot pode entregar esse endereço ao
        `proxy` antes de o conector subir. Sob esse conflito o `cloudflared` não sobe
        (endereço em uso), `restart: unless-stopped` não repara falha de início, e a
        borda responde 1033 sem sinal nenhum no host — ver docstring do módulo, "T-02,
        R4 do senso-crítico". Confere também que o `ip_range` está contido na `subnet`
        declarada: um `ip_range` que a extrapolasse tornaria a checagem anterior
        incompleta, porque o Docker não aloca de fora da `subnet` mesmo que o
        `ip_range` diga o contrário."""
        texto_override = _CAMINHO_OVERRIDE_PROD.read_text(encoding="utf-8")

        ocorrencias_ipv4 = extrair_ocorrencias(texto_override, REGEX_IPV4_ADDRESS)
        ocorrencias_subnet = extrair_ocorrencias(texto_override, REGEX_SUBNET_BORDA)
        ocorrencias_ip_range = extrair_ocorrencias(texto_override, REGEX_IP_RANGE_BORDA)

        self.assertEqual(
            len(ocorrencias_ipv4),
            1,
            f"docker-compose.prod.yml: esperava exatamente uma ocorrência de "
            f"'ipv4_address: ...', achou {ocorrencias_ipv4!r}.",
        )
        self.assertEqual(
            len(ocorrencias_subnet),
            1,
            f"docker-compose.prod.yml: esperava exatamente uma ocorrência de "
            f"'subnet: ...' na rede 'borda', achou {ocorrencias_subnet!r} — hoje só há "
            "uma rede com 'ipam' declarado no arquivo; uma segunda rede com 'ipam', ou "
            "a chave renomeada, muda essa contagem.",
        )
        self.assertEqual(
            len(ocorrencias_ip_range),
            1,
            f"docker-compose.prod.yml: esperava exatamente uma ocorrência de "
            f"'ip_range: ...' na rede 'borda', achou {ocorrencias_ip_range!r}.",
        )

        endereco_conector = ipaddress.ip_address(ocorrencias_ipv4[0])
        subnet_borda = ipaddress.ip_network(ocorrencias_subnet[0], strict=False)
        ip_range_borda = ipaddress.ip_network(ocorrencias_ip_range[0], strict=False)

        self.assertIn(
            endereco_conector,
            subnet_borda,
            f"docker-compose.prod.yml: o ipv4_address do cloudflared "
            f"({endereco_conector}) não está dentro da subnet declarada para a rede "
            f"'borda' ({subnet_borda}) — um endereço fixo fora da sub-rede do Docker "
            "não é alcançável por ela.",
        )
        self.assertNotIn(
            endereco_conector,
            ip_range_borda,
            f"docker-compose.prod.yml: o ipv4_address do cloudflared "
            f"({endereco_conector}) cai dentro do ip_range da rede 'borda' "
            f"({ip_range_borda}), a faixa de alocação dinâmica de onde o Docker pode "
            "atribuir endereço ao 'proxy' — num recreate ou reboot o 'proxy' pode "
            "receber esse mesmo endereço antes de o cloudflared subir, o conector não "
            "sobe (endereço em uso), 'restart: unless-stopped' não repara falha de "
            "início, e a borda responde 1033 sem sinal nenhum no host (ver docstring "
            "do módulo, T-02).",
        )
        self.assertTrue(
            ip_range_borda.subnet_of(subnet_borda),
            f"docker-compose.prod.yml: o ip_range da rede 'borda' ({ip_range_borda}) "
            f"não está contido na subnet declarada ({subnet_borda}) — a faixa de "
            "alocação dinâmica extrapola a sub-rede fixa, e a checagem acima, sozinha, "
            "não bastaria para provar que o proxy nunca toma o endereço do conector.",
        )
