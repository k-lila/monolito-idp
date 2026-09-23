"""O executor que impede a suíte de escrever na trilha de auditoria do ambiente.

`config/settings.py` declara `LOGGING` uma vez só, sem separação entre desenvolvimento e
produção: um `if TESTING:` ali criaria um segundo `LOGGING` e faria do ramo de produção o
caminho que a suíte nunca exercitaria — a inversão que o próprio docstring das settings recusa.
O isolamento é feito aqui, no executor, pelo mesmo precedente com que o `DiscoverRunner` padrão
já isola `DATABASES`: cria e destrói `test_<dbname>` sem que o código de produção saiba disso.

O que se troca é um valor só — o `filename` do handler `audit`, redirecionado para um arquivo
dentro de um diretório temporário — e não o mecanismo. Formatador, filtro, handler
(`WatchedFileHandler`) e os cinco receptores de `accounts/auditoria.py` continuam sendo os
mesmos objetos sob teste e em produção; a escrita é real, em arquivo real, o que é o que permite
a um teste futuro varrer a trilha em busca de campo proibido (AC-10) — um `NullHandler` não
permitiria.

A troca é desfeita no teardown, e não deixada por conta do fim do processo: o dictConfig de
produção é reaplicado ali, de modo que o handler `audit` volta a apontar para o arquivo do
ambiente. A razão está no comentário de `teardown_test_environment`.

A ADR (Architecture Decision Record) que registra esta decisão e as alternativas descartadas é
`docs/adr/0013-registrar-a-trilha-de-auditoria-dos-quatro-sinais-em-arquivo-duravel.md`.

O nome do módulo e da classe são contrato já gravado em `config/settings.py`
(`TEST_RUNNER = "tests.runner.RunnerComTrilhaIsolada"`); não renomear nenhum dos dois sem
atualizar aquela linha.

TASK-014/T-10, revisado por T-13 — o mesmo executor passou a desligar o limitador de taxa
(`config/limites.py`) para a suíte inteira, pela mesma razão e pelo mesmo precedente do bloco
acima: o contador de cada caminho vive no Redis do ambiente, não volta com o rollback do
`TestCase` e não é tocado por `DATABASES` nem por `LOGGING`. O desligamento esvazia o
DICIONÁRIO INTEIRO — hoje as quatro chaves de `RATE_LIMIT_POR_CAMINHO`, `/o/token/`,
`/o/authorize/`, `/accounts/login/` e `/o/device-authorization/` (TASK-019/T-14, a última a
entrar) —, e não apenas as que existiam quando o T-10 foi escrito: o contador de login tem as
mesmas três propriedades que já condenavam os de `/o/`, e
a folga dele é pior. Medido: cinco execuções consecutivas da suíte em menos de sessenta
segundos já somavam ao contador do `runserver` da jornada de construção com só `/o/` ligado,
porque o `REMOTE_ADDR` default do test client (`127.0.0.1`) é a MESMA chave que ele usa —
120 requisições em 24 execuções davam cinco de sobra antes do teto de `/o/authorize/`. Com o
login somado, a chave `127.0.0.1` recebeu 11 das 64 requisições de uma execução completa, e a
folga caiu: 60 em 13 dão só quatro execuções na origem `10.30.0.1`
(`PrazoDoBloqueioTests`), e quatro execuções de 7,3 s cabem folgadamente dentro da janela de
60 segundos configurada. O sintoma de deixar o teto de login ligado seria pior que o de
`/o/`: não um teste de fluxo OIDC caindo, mas um caso do `django-axes` devolvendo 429 do
middleware onde o teste espera 200 (ou o contrário) — falha que aponta para o mecanismo
errado.

TASK-015/T-04 — o mesmo executor passou a guardar e zerar `settings.SECURE_SSL_REDIRECT` no
setup e a repô-lo no teardown, terceiro valor a seguir o precedente do `filename` do handler
`audit` e do `RATE_LIMIT_POR_CAMINHO`: `docker-compose.yml` (Bloco C, ADR 0018) passou a
sobrescrever `BEHIND_TLS_PROXY=True` no serviço `app`, e `SECURE_SSL_REDIRECT = BEHIND_TLS_PROXY`
(`config/settings.py`) segue essa variável — a jornada de container liga o redirecionamento
para HTTPS (Hypertext Transfer Protocol Secure) e o `Client` de teste do Django fala HTTP
simples, sem TLS (Transport Layer Security) nenhum. Sem esta troca todo `self.client.get(...)`
contra uma rota não isenta devolveria 301 antes de a view sob teste rodar, e é isso que produzia
49 das 51 falhas medidas pelo QA (`quality-assurance`) na simulação da jornada de container — o
301 engole a asserção de conteúdo, e o diagnóstico aponta para o endurecimento em vez de para
qualquer defeito real.

A escolha, e por que não é "cliente seguro por default": zerar `SECURE_SSL_REDIRECT` para a
aplicação sob teste, e não desligar `BEHIND_TLS_PROXY`. As duas settings são independentes em
`config/settings.py` — a segunda não deriva da primeira —, e é `BEHIND_TLS_PROXY` que decide qual
procedência `config.origem.origem_e_procedencia` lê (ADR 0018) e qual esquema `OIDC_ISS_ENDPOINT`
carrega (T-03, `tests/test_issuer.py`): neutralizá-la apagaria o próprio Bloco C da cobertura da
suíte na jornada que existe para exercitá-lo. `SECURE_SSL_REDIRECT`, ao contrário, é mecanismo
de transporte que este projeto não implementa (o TLS é do proxy reverso, fora do escopo do
sandbox — ver `CLAUDE.md`) e que a suíte nunca teve como testar em HTTP puro; zerá-lo tira do
caminho um redirecionamento que nenhum teste desta suíte quer provar, sem tocar em nada que o
Bloco C acrescentou. `override_settings(SECURE_SSL_REDIRECT=True)` continua funcionando por cima
do zeramento — é o que `tests/test_health.py` (`HealthRedirectExemptionTests`) exercita, porque
o `Client` que o `_pre_setup` do `TestCase` cria a cada teste lê a settings no momento da
requisição, e não no import deste módulo.

Por que não preservar o teto de login ligado na suíte: preservá-lo não verificaria nada — o
número 60 não é assertado por teste nenhum, deliberadamente (T-16 assere a RELAÇÃO entre os
dois tetos, não o literal) — e importaria a fragilidade inteira descrita acima. O preço de
desligar é o mesmo que já se pagava para `/o/`, e quem o pagou primeiro foi `T-17`, que provava
— na época, com as três chaves então declaradas em `RATE_LIMIT_POR_CAMINHO` — que o dicionário
de produção ainda alcançava o middleware. TASK-019/T-14 ampliou a mesma prova para a quarta
chave, `/o/device-authorization/`, sem trocar o mecanismo (`tests/test_limite_oauth.py`).

Por que aqui, e por que `RATE_LIMIT_POR_CAMINHO = {}` em vez de limpeza de chave caso a caso:
a limpeza protegeria só os módulos que se lembrassem dela, e nada faria contra o tráfego do
próprio ambiente escrevendo na mesma chave enquanto a suíte roda. Com o dicionário vazio,
nenhum teste que não se importe com limitação PODE ser afetado — por construção, e não por
disciplina de quem escreve teste depois —, e a suíte volta a poder passar em qualquer ordem
e em qualquer frequência. `RATE_LIMIT_POR_CAMINHO={}` não abre ramo dormente: é o caminho que
toda requisição fora dos quatro caminhos limitados já percorre em produção
(`config/limites.py`, `.get(request.path)` devolvendo `None`); o middleware continua na
cadeia e continua executando.

Por que não isolar o `CACHES` inteiro num banco Redis à parte: alcançaria também a sessão e a
sonda do `/health`, que este bloco não tem mandato para tocar, e ainda assim deixaria as
requisições de uma única execução se acumulando dentro dela — escopo maior, problema menor
resolvido. O contador do limitador de taxa é o único ponto com este defeito (o QA
(`quality-assurance`) varreu a superfície e não achou um segundo).

O valor de produção é guardado num atributo de módulo, não perdido: `T-17`, ampliado por
`TASK-019/T-14`, o lê de volta por `tests.runner.RATE_LIMIT_DE_PRODUCAO` para provar que o
caminho até o middleware continua existindo hoje para os quatro caminhos declarados em
`RATE_LIMIT_POR_CAMINHO` (`config/settings.py`). Os casos que testam o limitador com um teto
próprio (`T-07`, `T-09`, `T-14`) o reativam por `override_settings`, sempre com `REMOTE_ADDR`
forjado, apagando as próprias chaves ao fim.

TASK-015/T-18 (gate adversarial do `senso-critico`, sobre o próprio T-04 acima) — o zeramento de
`SECURE_SSL_REDIRECT` guardava o valor da jornada num atributo de INSTÂNCIA
(`self._secure_ssl_redirect_da_jornada`), e não de módulo. Funcionava para o teardown — a mesma
instância que zerou é a que repõe —, mas não sobrava nada legível de fora: nenhum teste podia
provar que o valor zerado era mesmo `BEHIND_TLS_PROXY`, e não outra coisa qualquer. Era exatamente
o defeito que a justificativa do T-17 (acima) nomeia: "sem ele, `RATE_LIMIT_POR_CAMINHO = {}`
deixado por engano passaria com tudo verde" — aqui, apagar ou inverter
`SECURE_SSL_REDIRECT = BEHIND_TLS_PROXY` em `config/settings.py:333` também passaria com tudo
verde, porque o único teste que a jornada de container tinha para a igualdade era o 301 em massa
que a PRÓPRIA neutralização apaga da suíte. O atributo virou `SECURE_SSL_REDIRECT_DE_PRODUCAO`,
de módulo, pelo mesmo mecanismo de `RATE_LIMIT_DE_PRODUCAO`: `T-18`
(`tests/test_endurecimento_transporte.py`) o lê de fora para provar a igualdade contra o valor
de produção — nunca contra `settings.SECURE_SSL_REDIRECT`, que é sempre `False` durante a
suíte inteira, por construção deste mesmo runner.

TASK-019/T-01 — o mesmo executor passou a guardar e corrigir `settings.OAUTH2_PROVIDER` no
setup e a repô-lo no teardown, quarto valor a seguir o mesmo precedente: com
`BEHIND_TLS_PROXY` ligado (jornada de container), `ALLOWED_REDIRECT_URI_SCHEMES`
(`config/settings.py`) vale `["https"]`, e as fixtures de `tests/oauth_helpers.py` registram
`redirect_uri` em `http://` — sem a correção, o 302 de `/o/authorize/` vira 400
(`DisallowedRedirect`) em todo teste de fluxo, o mesmo sintoma que o T-04 já descreveu acima
para `SECURE_SSL_REDIRECT`, e pela mesma razão: o `Client` de teste fala HTTP simples.

A diferença mecânica em relação aos três valores anteriores: `settings.OAUTH2_PROVIDER` não é
lido direto pela biblioteca a cada requisição — `oauth2_provider.settings.oauth2_settings`
(`django-oauth-toolkit`, DOT) lê o dicionário uma vez, no import, e guarda
`ALLOWED_REDIRECT_URI_SCHEMES` em cache por atributo. Reatribuir `settings.OAUTH2_PROVIDER`
sozinho, como as três linhas acima fazem com `RATE_LIMIT_POR_CAMINHO` e
`SECURE_SSL_REDIRECT`, não invalidaria esse cache: o DOT seguiria lendo `["https"]` até o fim
do processo. Por isso a troca aqui tem duas partes — a reatribuição da settings E o disparo de
`django.test.signals.setting_changed` com `setting="OAUTH2_PROVIDER"` —, e é o mesmo canal que
`override_settings` usa para acionar `oauth2_settings.reload()`
(`oauth2_provider/settings.py`). A cópia é sempre `{**original, "ALLOWED_REDIRECT_URI_SCHEMES":
["http", "https"]}`, nunca uma mutação do dicionário original no lugar: mutar
`OAUTH2_PROVIDER_DE_PRODUCAO` destruiria o próprio valor que `T-02`
(`tests/test_endurecimento_transporte.py`) lê de volta para provar a igualdade contra
`BEHIND_TLS_PROXY`.

Por que o sinal, e não um `setattr` direto em `oauth2_settings.ALLOWED_REDIRECT_URI_SCHEMES` no
lugar dele: não é porque um `setattr` "não chegaria a um segundo processo" — `setting_changed`
também é local ao processo que o dispara, a mesma limitação, e não distingue as duas
abordagens. A razão real é outra, e verificada com uma sonda no próprio runner: quando
`setup_test_environment()` roda, `ALLOWED_REDIRECT_URI_SCHEMES` ainda NÃO está em
`_cached_attrs` — nenhum código do processo o leu ainda. A primeira leitura acontece só dentro
de `run_suite()`, isto é, DURANTE a execução dos testes: `oauth2_provider/models.py`
(`AbstractApplication.clean()`, chamado pela validação do form do admin) é o primeiro a chamar
`oauth2_settings.ALLOWED_REDIRECT_URI_SCHEMES`, e o próprio `T-04`
(`tests/test_admin_oauth2_application.py`) é quem o dispara primeiro, dentro do seu próprio
`override_settings(OAUTH2_PROVIDER=esquema_https_only)`. É por isso que um `setattr` direto
seria pior do que "desfeito pelo próximo reload": como só `__getattr__` acrescenta um atributo
a `_cached_attrs` (`oauth2_provider/settings.py`), um `setattr` feito no setup deste runner —
ANTES de qualquer leitura real — criaria o atributo de instância direto, sem nunca passar por
`__getattr__`. Nenhum `reload()` futuro, nem o do próprio T-04, encontraria esse nome em
`_cached_attrs` para apagá-lo: a busca de atributo do Python encontra o valor já presente na
instância e nunca chega a chamar `__getattr__` de novo. O `setattr` sobreviveria a TODOS os
`reload()` da suíte inteira, sem exceção, e mascararia o próprio `T-04` — o teste que existe
para provar que `["https"]` rejeita `http://` no formulário do admin leria sempre
`["http", "https"]` do `setattr` nunca invalidado, e passaria mesmo se a rejeição não
acontecesse. O sinal deste runner, ao contrário, passa pelo mesmo `reload_oauth2_settings`
(conectado a `setting_changed`, que chama `oauth2_settings.reload()`) que qualquer
`override_settings(OAUTH2_PROVIDER=...)` dispara — nenhum atributo de instância sobra para
trás, e a primeira leitura real, seja de T-04 seja de qualquer outro teste, sempre parte de
`_user_settings` limpo.

Silêncio à parte, registrado e não resolvido aqui: as quatro neutralizações deste runner —
trilha de auditoria, `RATE_LIMIT_POR_CAMINHO`, `SECURE_SSL_REDIRECT` e `OAUTH2_PROVIDER` — só
valem no processo em que `setup_test_environment()` roda. `manage.py test --parallel` com
`multiprocessing.get_start_method() == "spawn"` (o default fora do Linux, e disponível nele por
opção) faz cada worker refazer `django.setup()` e chamar
`django.test.utils.setup_test_environment()` — a função do Django, não o método desta classe —
diretamente na função `_init_worker` (`django/test/runner.py`), no ramo `if start_method ==
"spawn":`, por volta das linhas 426-432 do Django instalado neste ambiente. Nenhuma das quatro
neutralizações chega aos workers spawnados: a trilha de
auditoria voltaria a escrever no arquivo do ambiente, os tetos de taxa e o redirecionamento TLS
valeriam os de produção contra um `Client` que fala HTTP puro, e `OAUTH2_PROVIDER` manteria
`ALLOWED_REDIRECT_URI_SCHEMES` de produção contra as fixtures em `http://` de
`tests/oauth_helpers.py`. Hoje a suíte roda sem `--parallel` (`README.md`), e o sintoma nunca
se manifestou; o dia em que alguém acrescentar a flag, os quatro efeitos voltam de uma vez, sem
aviso.
"""

import copy
import logging.config
import shutil
import tempfile
from pathlib import Path

from django.conf import settings
from django.test.runner import DiscoverRunner
from django.test.signals import setting_changed

# Guarda o teto de produção (hoje quatro chaves — ver docstring do módulo) enquanto a suíte
# roda com o limitador desligado. Atributo de módulo, e não de instância: é o que permite a
# `tests/test_limite_oauth.py` lê-lo de fora, sem precisar segurar uma referência ao runner em
# execução.
RATE_LIMIT_DE_PRODUCAO = None

# Guarda `SECURE_SSL_REDIRECT` da jornada em curso (produção, para quem chama `manage.py test`
# sem variável nenhuma) enquanto a suíte roda com a chave zerada (TASK-015/T-18, ver docstring
# do módulo). Atributo de módulo, e não de instância, pela mesma razão de `RATE_LIMIT_DE_PRODUCAO`
# logo acima: é o que permite a `tests/test_endurecimento_transporte.py` lê-lo de fora, sem
# depender de uma referência à instância do runner em execução — o defeito que a versão anterior
# desta guarda tinha, e que o gate adversarial do `senso-critico` apontou.
SECURE_SSL_REDIRECT_DE_PRODUCAO = None

# Guarda `settings.OAUTH2_PROVIDER` da jornada em curso enquanto a suíte roda com
# `ALLOWED_REDIRECT_URI_SCHEMES` neutralizado para as duas letras (TASK-019/T-01, ver
# docstring do módulo). Atributo de módulo, e não de instância, pela mesma razão de
# `RATE_LIMIT_DE_PRODUCAO` e `SECURE_SSL_REDIRECT_DE_PRODUCAO` acima: é o que permite a
# `tests/test_endurecimento_transporte.py` (T-02) lê-lo de fora, sem depender de uma
# referência à instância do runner em execução, e provar que a neutralização segue
# `BEHIND_TLS_PROXY` de produção — nunca `settings.OAUTH2_PROVIDER`, que vale a cópia
# neutralizada do início ao fim da suíte inteira, por construção deste mesmo runner.
OAUTH2_PROVIDER_DE_PRODUCAO = None


class RunnerComTrilhaIsolada(DiscoverRunner):
    """`DiscoverRunner` padrão, com o handler `audit` redirecionado durante a suíte, o teto de
    requisição desligado, `SECURE_SSL_REDIRECT` neutralizado e `OAUTH2_PROVIDER` corrigido —
    quatro valores da jornada em curso que a suíte não pode herdar sem se tornar dependente
    dela.

    `DiscoverRunner.run_tests` chama `setup_test_environment()` antes de `build_suite()`, que é
    quem descobre e importa os módulos de teste (`django/test/runner.py`, método `run_tests`).
    O redirecionamento acontece, portanto, antes de qualquer `test_*.py` ser importado — nenhuma
    linha emitida durante a suíte, nem por um receptor de sinal disparado na importação de um
    módulo, chega a escrever no arquivo do ambiente.
    """

    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        # Um diretório por execução, não um arquivo fixo: duas suítes concorrentes na mesma
        # máquina — jornada de construção e clonar-e-rodar, cada uma no seu próprio processo —
        # não disputam o mesmo caminho nem se misturam.
        self._diretorio_trilha_de_teste = tempfile.mkdtemp(prefix="nova_api-trilha-teste-")

        # copy.deepcopy, e não um dict novo com update raso: `LOGGING` tem dicionário dentro de
        # dicionário (handlers -> audit -> filename), e uma cópia rasa compartilharia o
        # subdicionário `audit` entre a configuração de produção e a de teste — escrever no
        # campo `filename` da cópia mutaria o `settings.LOGGING` original também.
        configuracao = copy.deepcopy(settings.LOGGING)
        configuracao["handlers"]["audit"]["filename"] = str(
            Path(self._diretorio_trilha_de_teste) / "audit.log"
        )
        # Reaplica o dictConfig inteiro sobre a configuração modificada. Formatador, filtro,
        # handler e loggers continuam declarados exatamente como em produção; só o `filename` do
        # handler `audit` muda. `disable_existing_loggers` já é False no dicionário original, e
        # segue False aqui — os loggers abertos por `django.setup()` continuam vivos.
        logging.config.dictConfig(configuracao)

        # TASK-014/T-10, revisado por T-13 e por TASK-019/T-14 — guarda o teto de produção e
        # desliga o limitador para a suíte inteira, ESVAZIANDO O DICIONÁRIO INTEIRO (hoje
        # quatro chaves: as duas de `/o/` do T-10 original, `/accounts/login/` que o T-13
        # acrescentou e `/o/device-authorization/` que o T-14 acrescentou depois — nunca só as
        # que existiam quando cada um foi escrito). A razão completa está no docstring do
        # módulo; aqui, só a mecânica: `global`, e não um atributo de instância, porque o valor
        # guardado precisa ser legível de fora do runner (T-17, em
        # `tests/test_limite_oauth.py`) sem depender de uma referência à instância em execução.
        global RATE_LIMIT_DE_PRODUCAO
        RATE_LIMIT_DE_PRODUCAO = settings.RATE_LIMIT_POR_CAMINHO
        settings.RATE_LIMIT_POR_CAMINHO = {}

        # TASK-015/T-04, corrigido por T-18 (gate adversarial do `senso-critico`) — guarda o
        # valor da jornada em curso e zera `SECURE_SSL_REDIRECT` para a suíte inteira. `global`,
        # e não atributo de instância, pelo MESMO argumento de `RATE_LIMIT_DE_PRODUCAO` duas
        # linhas acima: o valor guardado precisa ser legível de fora do runner (T-18, em
        # `tests/test_endurecimento_transporte.py`), sem depender de uma referência à instância
        # em execução. A versão original desta guarda (T-04) usava atributo de instância porque,
        # à época, nenhum teste precisava lê-lo — mas isso deixava o zeramento sem nenhum teste
        # que provasse a igualdade `SECURE_SSL_REDIRECT == BEHIND_TLS_PROXY` contra o valor de
        # produção, o mesmo defeito que o comentário de `RATE_LIMIT_DE_PRODUCAO` acima já nomeia.
        # A razão completa de zerar este valor, e não `BEHIND_TLS_PROXY`, está no docstring do
        # módulo.
        global SECURE_SSL_REDIRECT_DE_PRODUCAO
        SECURE_SSL_REDIRECT_DE_PRODUCAO = settings.SECURE_SSL_REDIRECT
        settings.SECURE_SSL_REDIRECT = False

        # TASK-019/T-01 — guarda o dicionário de produção e põe no lugar uma CÓPIA com
        # `ALLOWED_REDIRECT_URI_SCHEMES` fixado nas duas letras. A razão completa está no
        # docstring do módulo: com `BEHIND_TLS_PROXY` ligado (jornada de container),
        # `ALLOWED_REDIRECT_URI_SCHEMES` de produção é `["https"]`, e as fixtures de
        # `tests/oauth_helpers.py` registram `redirect_uri` em `http://` — o 302 de
        # `/o/authorize/` viraria 400 (`DisallowedRedirect`) em todo teste de fluxo.
        # `global`, pela mesma razão dos dois valores acima: o dicionário de produção
        # precisa ser legível de fora do runner (T-02, em
        # `tests/test_endurecimento_transporte.py`), sem depender de uma referência à
        # instância em execução.
        global OAUTH2_PROVIDER_DE_PRODUCAO
        OAUTH2_PROVIDER_DE_PRODUCAO = settings.OAUTH2_PROVIDER
        # Cópia, e nunca mutação no lugar: `{**original, ...}` constrói um dicionário novo,
        # e o original guardado acima continua intacto. Mutar `OAUTH2_PROVIDER_DE_PRODUCAO`
        # diretamente destruiria o próprio valor que T-02 lê de volta para provar a
        # igualdade contra `BEHIND_TLS_PROXY`.
        oauth2_provider_de_teste = {
            **OAUTH2_PROVIDER_DE_PRODUCAO,
            "ALLOWED_REDIRECT_URI_SCHEMES": ["http", "https"],
        }
        settings.OAUTH2_PROVIDER = oauth2_provider_de_teste
        # O sinal, e nunca um `setattr` em `oauth2_settings`: o objeto de settings do
        # toolkit (`oauth2_provider.settings.oauth2_settings`) guarda referência ao
        # dicionário lido no import e faz cache por atributo — trocar
        # `settings.OAUTH2_PROVIDER` sozinho não invalida esse cache, e
        # `ALLOWED_REDIRECT_URI_SCHEMES` continuaria a leitura de produção até o fim da
        # suíte. `setting_changed` é o mesmo canal que `override_settings` usa para
        # disparar `oauth2_settings.reload()` (`oauth2_provider/settings.py`), e é isso
        # que mantém a suíte independente de ordem: um teste que rode antes de outro não
        # deixa cache velho para trás.
        setting_changed.send(
            sender=self.__class__,
            setting="OAUTH2_PROVIDER",
            value=oauth2_provider_de_teste,
            enter=True,
        )

    def teardown_test_environment(self, **kwargs):
        # O diretório é removido ANTES do super(): teardown_test_environment() do DiscoverRunner
        # não toca em LOGGING, então a ordem entre as duas linhas não afeta o handler — mas
        # remover primeiro garante que o diretório temporário desapareça mesmo se um teardown
        # futuro, de uma reimplementação desta classe, vier a levantar exceção depois desta
        # linha.
        shutil.rmtree(self._diretorio_trilha_de_teste, ignore_errors=True)

        # Repõe a configuração de produção, desfazendo o dictConfig do setup. `settings.LOGGING`
        # continua íntegro porque o setup modificou uma cópia profunda, nunca o original — é
        # este o valor que `django.setup()` já aplicara no arranque, e é a ele que o handler
        # `audit` volta a apontar.
        #
        # Sem esta linha o silêncio seria este: passado o teardown, o handler `audit` seguiria
        # apontando para um arquivo dentro do diretório temporário que a linha acima acabou de
        # apagar. Nada acusa no ato — o handler só toca o disco no próximo `emit`, e ali o
        # WatchedFileHandler faz `stat` do caminho, não o encontra, tenta reabrir, e o
        # FileNotFoundError é engolido pelo `logging` numa linha em stderr. A linha de auditoria
        # some sem que ninguém a perca. Hoje o processo da suíte morre logo depois e nada
        # emite; a reposição é o que mantém isso verdadeiro para quem chame `run_tests()` de
        # dentro de um processo que continua vivo — outro runner, um script, um `manage.py`
        # embutido.
        #
        # Depois do rmtree, e não antes: o dictConfig fecha os handlers antigos, e `close()`
        # apenas descarrega e fecha o descritor já aberto, sem tocar no caminho — um arquivo
        # cujo diretório sumiu fecha sem erro. A ordem inversa também funcionaria, mas
        # enfraqueceria a garantia comentada acima.
        logging.config.dictConfig(settings.LOGGING)

        # TASK-014/T-10, revisado por T-13 e por TASK-019/T-14 — repõe o teto de produção (hoje
        # quatro chaves), com a mesma disciplina do dictConfig acima: nenhuma configuração fica
        # trocada além da duração da suíte, nem para quem chame `run_tests()` de dentro de um
        # processo que continua vivo.
        settings.RATE_LIMIT_POR_CAMINHO = RATE_LIMIT_DE_PRODUCAO

        # TASK-015/T-04, corrigido por T-18 — repõe `SECURE_SSL_REDIRECT` da jornada em curso,
        # pela mesma disciplina das duas linhas acima. Lida do `global`, e não de um atributo de
        # instância (ver razão completa em `setup_test_environment`).
        settings.SECURE_SSL_REDIRECT = SECURE_SSL_REDIRECT_DE_PRODUCAO

        # TASK-019/T-01 — repõe `OAUTH2_PROVIDER` de produção e refaz o `reload()` do
        # toolkit pelo mesmo sinal do setup, com `enter=False`: sem isso, `oauth2_settings`
        # continuaria com o cache da cópia de teste depois do teardown, para quem chame
        # `run_tests()` de dentro de um processo que continua vivo — o mesmo silêncio que
        # o comentário do `dictConfig`, acima, já nomeia para a trilha de auditoria.
        settings.OAUTH2_PROVIDER = OAUTH2_PROVIDER_DE_PRODUCAO
        setting_changed.send(
            sender=self.__class__,
            setting="OAUTH2_PROVIDER",
            value=OAUTH2_PROVIDER_DE_PRODUCAO,
            enter=False,
        )

        super().teardown_test_environment(**kwargs)
