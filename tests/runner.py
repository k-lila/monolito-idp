"""O executor que impede a suíte de escrever na trilha de auditoria do ambiente.

`config/settings.py` declara `LOGGING` uma vez só, sem separação entre desenvolvimento e
produção: um `if TESTING:` ali criaria um segundo `LOGGING` e faria do ramo de produção o
caminho que a suíte nunca exercitaria — a inversão que o próprio docstring das settings recusa.
O isolamento é feito aqui, no executor, pelo mesmo precedente com que o `DiscoverRunner` padrão
já isola `DATABASES`: cria e destrói `test_<dbname>` sem que o código de produção saiba disso.

O que se troca é um valor só — o `filename` do handler `audit`, redirecionado para um arquivo
dentro de um diretório temporário — e não o mecanismo. Formatador, filtro, handler
(`WatchedFileHandler`) e os quatro receptores de `accounts/auditoria.py` continuam sendo os
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
"""

import copy
import logging.config
import shutil
import tempfile
from pathlib import Path

from django.conf import settings
from django.test.runner import DiscoverRunner


class RunnerComTrilhaIsolada(DiscoverRunner):
    """`DiscoverRunner` padrão, com o handler `audit` redirecionado durante a suíte.

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

        super().teardown_test_environment(**kwargs)
