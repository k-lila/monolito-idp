# 0025. Congelar o issuer de produção na forma `https://<PUBLIC_HOST>/o`

## Status

Aceito — 2026-09-23

Cumpre a condição da ADR (Architecture Decision Record) 0007, que **não é emendada**: o issuer
continua `{BASE_URL}/o`. Esta ADR é a confirmação que a 0007 pediu "antes da primeira relying
party integrar".

## Contexto

O issuer é a identidade pública deste provedor de identidade (IdP, de _Identity Provider_): vai
na claim `iss` de todo `id_token` e fica cacheado na configuração de cada relying party (RP). A
ADR 0007 fixou a forma `{BASE_URL}/o` e condicionou a permanência dela a uma confirmação explícita
antes da primeira RP. A primeira RP é a `nova_api_SPA`, aplicação de página única (SPA, de
_Single-Page Application_) que já fecha o fluxo em desenvolvimento contra este IdP e vai para
produção na Vercel.

O código já deriva o issuer de uma variável só. O `docker-compose.yml` compõe
`BASE_URL=https://${PUBLIC_HOST}` e aborta o `up` se `PUBLIC_HOST` faltar; `config/settings.py`
publica `OIDC_ISS_ENDPOINT = f"{BASE_URL.rstrip('/')}/o"`. O `.env` de desenvolvimento tem
`PUBLIC_HOST=idp.localhost`. O de produção ainda não existe: nasce na instância, no passo 8 de
`docs/plano-contrato-backend.md`.

Três fatos tornam a escolha do nome irreversível na prática:

- a SPA compara `iss` byte a byte com `VITE_OIDC_ISSUER`, valor fixo no painel da Vercel, e não
  o lê da descoberta (ADR 0017 da SPA);
- `SECURE_HSTS_SECONDS` vale 31536000 sob `BEHIND_TLS_PROXY`: o primeiro navegador que visitar o
  nome por HTTPS o marca por um ano com HSTS (HTTP Strict Transport Security), como registra a
  ADR 0017 deste projeto;
- o nome atribuído pela AWS (Amazon Web Services), `*.amazonaws.com`, é reciclável para outro
  cliente e não recebe certificado público.

Resta decidir quanto do valor entra no repositório. A ADR 0017 deste projeto já decidiu que o
nome público é valor de implantação e que nenhum arquivo versionado o aprende, exceto o exemplo
do `.env.example`.

## Decisão

Vamos congelar a **forma** do issuer de produção em `https://<PUBLIC_HOST>/o`, e não o nome. O
nome vive só em dois lugares, ambos fora do repositório: o `.env` de produção, gerado na
instância, e a variável `VITE_OIDC_ISSUER` do ambiente Production no painel da Vercel. Nenhum
arquivo versionado traz o domínio de produção como literal. O `.env` de desenvolvimento continua
com `PUBLIC_HOST=idp.localhost`.

O nome e o valor cumprem cinco regras:

1. **Domínio próprio**, sob controle do dono do projeto. Nunca um nome atribuído pela AWS
   (`*.amazonaws.com`), que é reciclável e não recebe certificado público.
2. **Esquema `https`, sufixo `/o`, sem barra final e sem porta**, derivado de `PUBLIC_HOST` pelo
   compose e por `OIDC_ISS_ENDPOINT`, e nunca escrito à mão em `BASE_URL`. `PUBLIC_HOST` leva só
   o host, em minúsculas: sem esquema, porta, path nem barra.
3. **Permanente a partir do primeiro login de produção.** Dali em diante o issuer está cacheado
   na SPA e nos `id_token` vivos. A marca de HSTS começa antes, na primeira visita por navegador,
   que é a verificação do passo 8. Trocar de nome exige ADR nova, reconfigurar a SPA com redeploy
   e conviver com o HSTS do nome anterior em cada navegador que o visitou.
4. **Conferência byte a byte antes da entrega.** O `issuer` publicado em
   `https://<PUBLIC_HOST>/o/.well-known/openid-configuration` de produção é comparado com o
   `VITE_OIDC_ISSUER` do painel da Vercel antes de o `client_id` de produção ser entregue à SPA.
   Uma diferença de um caractere é erro de configuração, e na SPA só aparece como falha no
   callback.
5. **A escolha concreta do domínio é item do passo 8**, e não desta ADR.

Contraparte: a ADR 0017 da `nova_api_SPA`
(`../../../nova_api_SPA/docs/adr/0017-fixar-vite-oidc-issuer-de-producao-em-https-dominio-do-idp-barra-o-sem-barra-final.md`)
fixa a mesma forma do lado de quem consome e aceita `{BASE_URL}/o` como permanente. Nenhuma linha
de código muda nos dois lados.

## Consequências

Positivas:

- A pendência da ADR 0007 fecha: os dois lados confirmam a forma, cada um numa ADR que aponta
  para a outra.
- Um clone do repositório não carrega o domínio de produção, e o ambiente de desenvolvimento não
  muda.
- A regra 4 reduz a pergunta "o issuer confere?" a uma comparação entre duas strings, feita uma
  vez, antes de haver pessoa usuária.

Negativas:

- O valor de produção não tem fonte versionada. Vive em dois lugares que divergem sem diff, o
  `.env` da instância e o painel da Vercel, e a única conferência é a manual da regra 4. Uma
  troca posterior em um dos dois só aparece quando o próximo callback falhar.
- A permanência começa antes do primeiro login, porque a primeira visita por navegador já grava
  o HSTS. Um nome escolhido com pressa no passo 8 custa o mesmo que um escolhido com cuidado.
- A forma herda da ADR 0007, agora em definitivo, a divergência entre a OpenID Connect Discovery
  1.0 e a RFC 8414: uma RP que siga estritamente a RFC 8414 continua recebendo 404.
- `docs/integracao-rp.md` não pode declarar o issuer de produção por extenso. Uma RP que integre
  depois da SPA recebe o valor por entrega, e não por documento.

## Alternativas consideradas

- **Versionar o domínio como literal**, em `docs/integracao-rp.md` ou no `.env.example`. Daria
  uma fonte conferível por `grep`. Descartada: a ADR 0017 deste projeto fez do nome um valor de
  implantação, e um literal num repositório clonável ensinaria a quem copia o `.env.example` um
  host que não é dele.
- **Issuer na raiz de um subdomínio dedicado, sem `/o`.** É a alternativa que a ADR 0007
  descartou naquela fase e deixou como "destino natural se o IdP for exposto de verdade".
  Descartada: mudaria a forma que a SPA já aceitou na ADR 0017 dela e montaria o protocolo na
  raiz do host, que a 0007 recusou pelo espaço de nomes do produto. O domínio próprio já dá o que
  aquela alternativa oferecia, DNS (Domain Name System) e certificado próprios, sem mover o
  issuer.
- **Usar o nome da AWS agora e o domínio próprio depois.** Dispensaria registrar um domínio antes
  do primeiro deploy. Descartada: o issuer congela no primeiro login e o HSTS na primeira visita,
  de modo que "depois" seria trocar o issuer, o que esta ADR existe para evitar. Além disso, o
  nome da AWS não recebe certificado público.
