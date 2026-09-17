# 0015. Resolver a origem do cliente num ponto único

## Status

Aceito — 2026-09-10

## Contexto

Duas peças do IdP (Identity Provider) precisam responder à mesma pergunta: de que endereço veio
esta requisição. A trilha de auditoria já a responde desde a ADR (Architecture Decision Record)
0013, no campo `ip` de cada linha, lendo `REMOTE_ADDR` em `accounts/auditoria.py`. O limitador de
taxa que este bloco introduz precisa da mesma resposta para saber o que contar. São o mesmo fato
lido em dois lugares, e dois lugares divergem sem emitir sinal.

A pergunta muda de resposta no dia em que houver um proxy à frente, e o projeto sabe que haverá:
é o Bloco C de `docs/implementacao-robustez.md`. Com o proxy de pé, `REMOTE_ADDR` passa a valer o
endereço do proxy para toda requisição externa. Para a trilha, isso significa um campo que deixa
de dizer algo. Para o limitador, significa um contador só para o mundo inteiro: o primeiro
atacante que estourar o teto tranca a tela de login para todos, a suíte continua verde e o
defeito só aparece no incidente. É a armadilha registrada em `.claude/memory/decisions.md:112-122`
e a única ordem que este repositório já pôs por escrito — decidir a chave de contagem **antes** de
o proxy existir, porque com `BEHIND_TLS_PROXY=False` o defeito não se manifesta.

Há um contrapeso simétrico, e é o que impede a solução ingênua. `X-Forwarded-For` é um cabeçalho
que qualquer cliente escreve. Lê-lo sem um proxy que o imponha entrega ao atacante a escolha da
própria chave de contagem: ele escapa do limitador trocando uma string, e a trilha registra a
origem que ele quiser. A ficha 2.2 de `docs/robustez-info.md` cataloga a mesma classe de erro em
`SECURE_PROXY_SSL_HEADER`.

O repositório já tem precedente para condicionar comportamento a `BEHIND_TLS_PROXY`: as quatro
chaves de endurecimento de transporte de `config/settings.py` derivam dela, e a ADR 0010 aceita
uma configuração inerte enquanto a variável for falsa.

## Decisão

Vamos concentrar a resolução da origem numa função única, `origem_da_requisicao(request)`, em
`config/origem.py`, e fazer dela a **única** leitura de origem do sistema.

**Quem a consome, e como.** Três consumidores, e nenhum outro: `accounts/auditoria.py`, por import
direto, para o campo `ip` de toda linha da trilha; o middleware de limitação de taxa de
`config/limites.py`, por import direto, para a chave do contador; e o `django-axes`, por contrato
de string em `AXES_CLIENT_IP_CALLABLE` — o mesmo padrão de `OAUTH2_VALIDATOR_CLASS`. A igualdade
que o critério de aceite exige entre o valor contado e o valor auditado não é verificada: ela é
estrutural, porque não há duas leituras a comparar.

**O que a função devolve.** Com `BEHIND_TLS_PROXY` falso — hoje —, `REMOTE_ADDR`, que é
exatamente o que a trilha já grava: esta decisão não muda um único valor de campo. Com a variável
verdadeira, o salto de `X-Forwarded-For` contado **a partir da direita**, na posição declarada em
`TRUSTED_PROXY_COUNT` (literal, hoje 1). Nunca o primeiro elemento da lista: o primeiro é escrito
pelo cliente, o último é escrito pelo proxy imediatamente à frente, e só o último não é forjável.
Cabeçalho ausente, ou com menos saltos que o declarado, cai em `REMOTE_ADDR`. A variável é lida em
tempo de execução, e não no import, o que torna o ramo de proxy exercitável por `override_settings`
antes de existir proxy.

**O que esta decisão obriga o Bloco C a fazer.** Ligar `BEHIND_TLS_PROXY` passa a mudar, na mesma
tecla, a semântica do campo `ip` da trilha e a chave do limitador. A trilha é um arquivo
append-only, e nada na linha distingue as duas populações, porque o instante da troca não está
gravado. **O Bloco C não pode ligar essa variável sem antes decidir o versionamento da linha da
trilha**, pela mesma regra que produziu esta ADR: decisão que encarece depois vem antes.

## Consequências

Positivas:

- A pergunta "de onde veio" tem uma resposta só, num arquivo só. Trocá-la no dia do proxy é editar
  uma função, e não caçar leituras de `REMOTE_ADDR` espalhadas.
- A divergência entre o que se audita e o que se conta deixa de ser possível por construção, e não
  por vigilância.
- A regra de leitura do cabeçalho fica escrita e testável antes de existir proxy, que é a única
  janela em que ela é barata.
- Nada muda no comportamento de hoje: nenhum campo troca de valor, nenhum teste de auditoria
  precisa de ajuste.

Negativas:

- O ramo de proxy é código que não roda no ambiente atual. Fica exercitado só por
  `override_settings`, e um teste que exercita configuração inexistente prova a função, não o
  sistema — o proxy de verdade pode escrever o cabeçalho de outro jeito.
- `TRUSTED_PROXY_COUNT` é um número que ninguém pode conferir hoje. Errado, ele devolve o salto
  errado, e o erro é silencioso: um contador por proxy, ou uma chave escolhida pelo cliente.
- **Com o proxy de pé e o cabeçalho ausente, a função devolve o endereço do proxy para todo mundo**
  — exatamente a falha que ela existe para impedir, agora escondida atrás de uma configuração de
  proxy em vez de uma linha de código. Está no catálogo da seção 14 de `docs/runbook.md`.
- `accounts` passa a importar de `config`, o que inverte a direção usual entre app e composição. É
  uma função pura, sem estado e sem import de volta, mas é uma dependência nova numa fronteira que
  `docs/arquitetura.md` descreve como nítida.
- Ao usar o callable do axes em vez do `ipware` que ele traz, abre-se mão da validação de endereço
  daquela biblioteca — endereço privado ou malformado entra na chave como veio.

## Alternativas consideradas

- **Configurar o axes pelo `ipware` (`AXES_IPWARE_PROXY_COUNT` e
  `AXES_IPWARE_META_PRECEDENCE_ORDER`)** — é o caminho nativo da biblioteca e traz validação de
  endereço pronta. Descartada porque cria um segundo caminho de resolução, ao lado do da trilha:
  os dois concordariam hoje e divergiriam no dia em que um dos dois fosse ajustado, sem que nada
  emitisse sinal. É a divergência que esta ADR existe para fechar.
- **Ler `X-Forwarded-For` sempre, sem condicionar a `BEHIND_TLS_PROXY`** — dispensaria o ramo e o
  literal. Descartada porque entrega ao cliente a escolha da própria chave de contagem enquanto
  não houver proxy que imponha o cabeçalho.
- **Manter `REMOTE_ADDR` puro e adiar tudo para o Bloco C** — é o mais simples e o que o escopo
  desta tarefa quase permitia. Descartada pela primeira regra da seção 1 de
  `docs/implementacao-robustez.md`: com o proxy de pé primeiro, a decisão sai mais cara e o
  defeito não emite sinal.
- **Pôr a função em `config/observabilidade.py`** — evitaria um módulo novo. Descartada porque
  aquele módulo decide como uma linha de log é escrita, e a origem de uma requisição não é isso;
  e porque `accounts/auditoria.py` declara por escrito que não importa aquele módulo.
- **Pôr a função em `accounts/`** — evitaria a inversão de dependência. Descartada porque origem é
  fato de transporte, lido na borda, e `accounts` é o app da pessoa: o limitador de `/o/token/`,
  que não conhece pessoa nenhuma, passaria a importar do app de identidade.
