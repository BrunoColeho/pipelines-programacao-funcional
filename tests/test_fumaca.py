"""Testes de fumaça: confirmam que o pipeline e o oráculo funcionam antes do experimento.

Não substituem as suítes da QP2, que terão protocolo próprio (ESPECIFICACAO.md, Seção 1).
"""

from datetime import date, datetime, timedelta

import pytest

from pipeline import casca, dados, nucleo, relogio
from pipeline.config import Configuracao, todas_configuracoes
from pipeline.verificacao import confere

DIA = date(2026, 3, 2)


# --- Composição -----------------------------------------------------------

def test_compor_sem_etapas_e_identidade():
    assert nucleo.compor()(42) == 42


def test_compor_aplica_da_esquerda_para_a_direita():
    assert nucleo.compor(lambda x: x + 1, lambda x: x * 10)(2) == 30


# --- Normalização ---------------------------------------------------------

V1 = {"versao": 1, "id_evento": "E1", "id_pedido": "P1", "id_cliente": "C001",
      "valor": "12.34", "status": "confirmado", "ts": "2026-03-02T10:00:00"}
V2 = {"versao": 2, "id_evento": "E2", "pedido": {"id": "P2", "cliente": {"id": "C002"}},
      "pagamento": {"valor": "5.00", "status": "confirmado"}, "ts": "2026-03-02T11:00:00"}


@pytest.mark.parametrize("bruto, esperado", [(V1, 1234), (V2, 500)])
def test_normalizar_aceita_os_dois_formatos(bruto, esperado):
    registro = nucleo.normalizar(bruto)
    assert registro["valor_centavos"] == esperado
    assert registro["data"] == DIA


@pytest.mark.parametrize("bruto", [
    {k: v for k, v in V1.items() if k != "id_cliente"},       # sem cliente
    {k: v for k, v in V1.items() if k != "valor"},            # sem valor
    {**V1, "valor": "n/d"},                                   # valor ilegível
    {**V2, "pedido": {"id": "P2"}},                           # v2 sem cliente
    {"versao": 3, "id_evento": "E9"},                         # formato desconhecido
])
def test_normalizar_descarta_registros_defeituosos(bruto):
    assert nucleo.normalizar(bruto) is None


def test_normalizar_nao_altera_a_entrada():
    bruto = {**V1}
    nucleo.normalizar(bruto)
    assert bruto == V1


# --- Mecanismos das variantes P=0 (documentam o defeito, não o corrigem) ----

def test_normalizar_no_lugar_reconverte_valor_ja_convertido():
    bruto = {**V1}
    assert nucleo.normalizar_no_lugar(bruto)["valor_centavos"] == 1234
    assert nucleo.normalizar_no_lugar(bruto)["valor_centavos"] == 123_400


def test_agregar_com_estado_acumula_entre_chamadas():
    import importlib
    importlib.reload(nucleo)
    registros = [{"nivel": "ouro", "valor_centavos": 100}]
    assert nucleo.agregar_com_estado(registros, DIA)[0]["pedidos"] == 1
    assert nucleo.agregar_com_estado(registros, DIA)[0]["pedidos"] == 2


# --- Gerador ----------------------------------------------------------------

def test_gerador_e_deterministico():
    assert dados.gerar(7) == dados.gerar(7)


def test_verdade_independe_de_duplicatas_e_atrasos():
    limpo = dados.gerar(3)
    sujo = dados.gerar(3, fracao_duplicatas=0.1, fracao_atrasos=0.1)
    assert limpo.gabarito == sujo.gabarito
    assert len(sujo.chegadas) > len(limpo.chegadas)


# --- Pipeline de ponta a ponta -------------------------------------------------

def _executar_dias_agendados(cfg, lote, destino):
    for dia in lote.dias:
        relogio.ajustar(dados.instante_agendado(dia))
        casca.executar_job(cfg, dia, casca.novo_processo(lote), destino, lote.referencia_clientes)


@pytest.mark.parametrize("cfg", todas_configuracoes(), ids=lambda c: c.rotulo)
@pytest.mark.parametrize("semente", range(5))
def test_caminho_feliz_todas_as_configuracoes(cfg, semente, tmp_path):
    """Condição de validade (cenário C0): sem reexecução, os fatores não podem fazer diferença."""
    lote = dados.gerar(semente)
    destino = casca.Destino(tmp_path)
    _executar_dias_agendados(cfg, lote, destino)
    assert confere(destino, lote)


@pytest.mark.parametrize("semente", range(10))
def test_configuracao_completa_com_dados_sujos(semente, tmp_path):
    """1111 com duplicatas e atrasos, executado depois que todos os dados chegaram."""
    lote = dados.gerar(semente, fracao_duplicatas=0.1, fracao_atrasos=0.1)
    destino = casca.Destino(tmp_path)
    relogio.ajustar(datetime.combine(lote.dias[-1] + timedelta(days=2), datetime.min.time()))
    origem = casca.novo_processo(lote)
    for dia in lote.dias:
        casca.executar_job(Configuracao(), dia, origem, destino, lote.referencia_clientes)
    assert confere(destino, lote)


def test_oraculo_detecta_linha_duplicada(tmp_path):
    lote = dados.gerar(0)
    destino = casca.Destino(tmp_path)
    _executar_dias_agendados(Configuracao(), lote, destino)
    primeira = lote.dias[0]
    linhas = destino.ler_tudo()[primeira.isoformat()]
    destino.escrever(primeira, linhas[:1], sobrescrever=False)
    assert not confere(destino, lote)
