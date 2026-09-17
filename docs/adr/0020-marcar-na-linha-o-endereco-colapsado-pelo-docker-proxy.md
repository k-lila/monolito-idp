# 0020. Marcar na linha o endereço colapsado pelo docker-proxy

## Status

Aceito — 2026-09-14

## Contexto

A ADR (Architecture Decision Record) 0018 acrescentou `ip_src` a cada linha da trilha de
auditoria para que o arquivo dissesse, sozinho, de onde saiu o `ip` daquela linha. O campo
versiona o caminho de código — `remote_addr`, `forwarded`, `remote_addr_fallback` —, e não o
significado do endereço.

Falta uma distinção que o caminho de código não alcança. A ADR 0017 registrou que a
publicação em loopback passa pelo `docker-proxy`, um processo de userland que abre até o
container uma conexão própria: o Caddy recebe todas as conexões do gateway da bridge e
escreve esse endereço em `X-Forwarded-For`, corretamente. Hoje, portanto, toda requisição
vinda do host produz `{"ip": "172.18.0.1", "ip_src": "forwarded"}` — uma chave só para o
host inteiro. No dia em que alguém editar `127.0.0.1:443:443` para `0.0.0.0:443:443`, a
linha continua byte a byte idêntica para quem vier do host e passa a trazer o endereço real
para quem vier de fora. As duas populações ficam no mesmo arquivo append-only, sem retenção
e sem poda, e nada na linha as distingue. O erro que isso produz é o mesmo com que a
ADR 0018 abre e que ela não registrou ter recriado: uma investigação que conte origens
distintas sobre o arquivo inteiro soma duas grandezas diferentes, e o erro não tem sintoma.

Um fato agrava o problema e decide o desenho: **depois da exposição as duas populações
coexistem por requisição, e não por período.** Quem chega pelo `127.0.0.1` do próprio host
continua atravessando o `docker-proxy` mesmo com a porta publicada sem endereço; quem chega
de fora tem a origem preservada pelo DNAT. Não há instante que separe as duas, o que
descarta por impossibilidade — e não por preferência — toda solução baseada em lembrar uma
data, inclusive a de anotá-la em `docs/runbook.md`, que a ADR 0018 já havia descartado por
outro motivo.

Três restrições cercam a solução. A ADR 0013 fixou o esquema de campos da linha e é
imutável. A ADR 0018 é imutável. A ADR 0017 recusou de propósito uma variável de ambiente
para a exposição, "porque exposição é decisão, e uma variável convida a invertê-la sem
decidir".

## Decisão

Vamos acrescentar a cada linha da trilha um terceiro campo de origem, `ip_edge`, que declara
a relação entre o `ip` daquela linha e o gateway padrão do processo que a escreveu, com três
valores: `gateway`, `peer` e `unknown`.

**O que cada valor afirma.** `gateway` — o `ip` é o endereço do gateway padrão do processo:
é nele que colapsa toda requisição encaminhada pelo `docker-proxy`, e a origem real não está
no arquivo nem em lugar nenhum. `peer` — o `ip` difere do gateway padrão, e o campo não
afirma mais do que isso; em particular, não afirma que o endereço identifique um cliente
único. `unknown` — o processo não conseguiu ler a própria rota padrão, ou o `ip` não é
IPv4: a distinção não está disponível naquela linha, e a linha o declara em vez de calar.

**De onde o sistema tira a resposta.** Da sua própria tabela de rotas, `/proc/net/route`,
lida a cada linha. Não de variável nova, não do compose, não de inspeção do `REMOTE_ADDR`.
A pergunta que o processo sabe responder com exatidão é "este endereço é o meu gateway
padrão?", e é a pergunta certa: vale por requisição, continua correta dos dois lados da
exposição, e não exige que o container saiba o que o serviço `proxy` publica — coisa que ele
não pode observar.

**Onde o valor nasce.** Em `config/origem.py`, em `origem_completa(request)`, que devolve a
tripla `(endereço, procedência, alcance)` compondo o par da ADR 0018 com o alcance calculado
**sobre o endereço que aquele par devolveu**. `origem_e_procedencia` e `origem_da_requisicao`
não mudam de assinatura nem de valor; a segunda continua sendo contrato de string do
`django-axes` em `AXES_CLIENT_IP_CALLABLE`.

**Quem grava.** `accounts/auditoria.py`, nos cinco receptores, ao lado de `ip` e `ip_src`. O
campo é escrito em toda linha, em qualquer ramo: um campo que só aparecesse sob `forwarded`
faria a ausência dele voltar a ser ambígua. O log operacional continua sem os três campos,
pela razão da ADR 0018 — ele não sobrevive ao container.

**O que a ausência do campo significa.** São três populações, e cada uma tem o que a
sustenta. Linha sem `ip_src`: escrita antes da ADR 0018, e o seu `ip` é `REMOTE_ADDR`. Linha
com `ip_src` e sem `ip_edge`: escrita entre a ADR 0018 e esta decisão, e o seu `ip` **não
identifica cliente nenhum** — é endereço da rede do compose, o gateway da bridge sob
`forwarded` ou o endereço do próprio Caddy sob `remote_addr_fallback`, ou `127.0.0.1` na
jornada de construção. O que sustenta essa afirmação não é memória de alguém: a única
publicação que este repositório já teve é em `127.0.0.1`, expor exige editar à mão um
arquivo versionado (ADR 0017), e esta decisão proíbe essa edição antes de o campo existir —
a mesma forma da proibição com que a ADR 0018 sustentou a sua própria regra. Linha com
`ip_edge`: responde sozinha.

**Relação com a ADR 0018.** Esta decisão **emenda** a 0018 na alínea "a resposta é por
linha, e não por posição no arquivo ... não há instante a lembrar nem documento a
consultar", verdadeira para a escolha entre os três rótulos e falsa para o significado do
endereço sob `forwarded`. Não a substitui: o campo `ip_src`, os seus três valores e a regra
da linha sem o campo seguem valendo na íntegra, e a ADR 0018 não é editada. O vocabulário
dela também não recebe valor novo: acrescentar um quarto rótulo estreitaria o significado de
`forwarded` nas linhas novas sem tocar nas antigas, recriando dentro do campo a mesma
terceira população que este texto acabou de nomear.

## Consequências

Positivas:

- A pergunta "este endereço é real ou é a borda em que o host colapsa?" passa a ter resposta
  na própria linha, dos dois lados do dia da exposição e para o tráfego misto que existe
  depois dele.
- A resposta continua sendo por linha, e não por posição no arquivo: sobrevive a
  concatenação, a cópia parcial, a rotação externa e à ordem de escrita de três workers.
- O alcance não pode divergir do endereço: é calculado sobre o valor que a mesma chamada
  devolveu, sem reler cabeçalho nenhum — a propriedade da ADR 0015, estendida uma vez mais.
- Nenhuma variável de ambiente nova. A exposição continua sendo edição à mão no
  `docker-compose.yml`, como a ADR 0017 quis, e o campo não espelha configuração: observa,
  por requisição, a consequência dela.
- O dia da exposição ganha um sinal certo. `docs/seguranca.md` mandava conferir
  `remote_addr_fallback`, que com o Caddy à frente nunca aparecerá; o sinal é a primeira
  linha `peer`.

Negativas:

- `config/origem.py` deixa de ser função pura: passa a ler um arquivo do sistema a cada
  linha da trilha. Acopla-se ao Linux e ao `procfs`, e numa jornada de construção sobre host
  que não os tenha o campo sai `unknown` em toda linha.
- O caso `gateway` não é alcançável pela suíte: os testes constroem requisições sintéticas e
  a tabela de rotas de verdade não é a do cenário. O que a suíte cobre é a função contra uma
  tabela de fixture; o caso real verifica-se à mão, com um `curl` do host e um `jq` na
  trilha, uma vez.
- Um terceiro campo de origem, e a pergunta passa a exigir `ip`, `ip_src` e `ip_edge` lidos
  juntos: `peer` sob `remote_addr_fallback` é endereço interno que não identifica cliente
  nenhum, e quem ler só `ip_edge` conclui errado.
- Enquanto ninguém expuser, o campo é constante — `gateway` em toda linha vinda do host.
  Paga-se hoje por um leitor que talvez só exista daqui a seis meses.
- Mais bytes por linha, num arquivo que já cresce sem poda decidida: a negativa da ADR 0013,
  que a 0018 agravou e esta agrava de novo.
- O campo marca o colapso; não o desfaz. O endereço perdido pelo `docker-proxy` continua
  perdido, e a chave do limitador de taxa continua colapsando junto — nada aqui muda isso.
- A regra da população do meio vale por uma proibição respeitada. Se alguém já tiver
  publicado fora de loopback, aquelas linhas são indistinguíveis e não há como recuperá-las.

## Alternativas consideradas

- **Uma variável de ambiente que declare o modo de exposição** — custo quase zero e legível.
  Descartada por duas razões independentes: reintroduz no ambiente a decisão que a ADR 0017
  tirou dele de propósito, e um valor que espelha o compose diverge dele em silêncio no
  primeiro esquecimento — o resultado é uma linha de auditoria que mente, pior que uma
  ambígua. Seria ainda o dado errado: depois da exposição o modo é por requisição, e a
  variável rotularia como real o tráfego que veio do próprio host.
- **Inspecionar o `REMOTE_ADDR`** — não custa leitura de arquivo nenhuma. Descartada porque
  `REMOTE_ADDR` atrás do proxy é o endereço do container do Caddy, igual antes e depois da
  exposição: não carrega sinal nenhum sobre a pergunta.
- **Gravar o endereço do gateway na linha, em vez do veredito** — mais informação e nenhum
  julgamento a errar. Descartada porque transfere ao leitor o conhecimento de que é o
  `docker-proxy` quem colapsa naquele endereço; o veredito nomeado é o que se lê por `grep`,
  e é a forma que `ip_src` já estabeleceu.
- **Um quarto valor em `ip_src`, do tipo `forwarded_gateway`** — não acrescentaria campo.
  Descartada porque estreitaria o significado de `forwarded` nas linhas novas sem tocar nas
  antigas, que é exatamente a ambiguidade que se está fechando, e porque o vocabulário da
  ADR 0018 é imutável.
- **Classificar o endereço por faixa — pública, privada, loopback** — dispensaria ler a
  tabela de rotas. Descartada porque é função pura do campo `ip`, que já está na linha: não
  acrescenta informação que o leitor não possa calcular sozinho, e erra por completo numa
  implantação de rede local, em que o cliente real também é privado.
- **Anotar o instante da exposição em `docs/runbook.md`** — custo zero. Descartada pelo que
  a ADR 0018 já dizia e por uma razão mais forte: não existe instante que separe as
  populações, porque depois da exposição elas coexistem por requisição.
