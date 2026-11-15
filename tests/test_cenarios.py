"""Verificações dos cenários: a configuração completa passa em todos, e o controle C0 em todas as configurações."""

import pytest

from pipeline.config import Configuracao, todas_configuracoes
from pipeline.experimento import CENARIOS, executar, previsto_passar


@pytest.mark.parametrize("cenario", CENARIOS)
@pytest.mark.parametrize("semente", range(3))
def test_configuracao_completa_passa_em_todos_os_cenarios(cenario, semente):
    assert executar(Configuracao(), cenario, semente).correto


@pytest.mark.parametrize("cfg", todas_configuracoes(), ids=lambda c: c.rotulo)
def test_controle_c0_passa_em_todas_as_configuracoes(cfg):
    assert executar(cfg, "C0", 0).correto


def test_previsao_isolada_por_fator():
    assert not previsto_passar(Configuracao.de_rotulo("0111"), "C2")
    assert previsto_passar(Configuracao.de_rotulo("0111"), "C4")
    assert not previsto_passar(Configuracao.de_rotulo("1110"), "C4")
