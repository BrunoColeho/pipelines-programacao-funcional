"""Cenários C0 a C5 da QP1 (ESPECIFICACAO.md, Seções 7 e 8).

Uso:
    python -m pipeline.experimento            # 30 sementes, grava em resultados/
    python -m pipeline.experimento --sementes 5

Cada cenário recebe uma configuração, uma semente e um diretório vazio para o
destino, executa o job como um orquestrador faria e devolve o destino final.
"""

from __future__ import annotations

import argparse
import csv
import random
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Callable

from pipeline import casca, dados, relogio
from pipeline.config import Configuracao, todas_configuracoes
from pipeline.verificacao import confere

Cenario = Callable[[Configuracao, int, Path], tuple[casca.Destino, dados.Lote]]

# Cenários em que cada fator, violado isoladamente, deve falhar (Seção 8).
FALHAS_PREVISTAS = {
    "T": {"C2", "C5"},
    "W": {"C1", "C3", "C5"},
    "P": {"C1", "C2"},
    "D": {"C4"},
}


def _rodar(cfg: Configuracao, dia: date, instante: datetime, origem: casca.Origem,
           destino: casca.Destino, lote: dados.Lote, **kwargs) -> None:
    relogio.ajustar(instante)
    casca.executar_job(cfg, dia, origem, destino, lote.referencia_clientes, **kwargs)


# --- Cenários ----------------------------------------------------------------

def c0_controle(cfg, semente, raiz):
    lote, destino = dados.gerar(semente), casca.Destino(raiz)
    for dia in lote.dias:
        _rodar(cfg, dia, dados.instante_agendado(dia), casca.novo_processo(lote), destino, lote)
    return destino, lote


def c1_execucao_duplicada(cfg, semente, raiz):
    """Cada dia roda às 02:00 e de novo às 02:05, no mesmo processo (ex.: célula reexecutada)."""
    lote, destino = dados.gerar(semente), casca.Destino(raiz)
    for dia in lote.dias:
        origem = casca.novo_processo(lote)
        _rodar(cfg, dia, dados.instante_agendado(dia), origem, destino, lote)
        _rodar(cfg, dia, dados.instante_agendado(dia) + timedelta(minutes=5), origem, destino, lote)
    return destino, lote


def c2_backfill(cfg, semente, raiz):
    """O pipeline é implantado depois; um laço processa os 5 dias no mesmo processo."""
    lote, destino = dados.gerar(semente), casca.Destino(raiz)
    instante = datetime.combine(lote.dias[-1] + timedelta(days=5), time(9, 0))
    origem = casca.novo_processo(lote)
    for dia in lote.dias:
        _rodar(cfg, dia, instante, origem, destino, lote)
    return destino, lote


def c3_falha_parcial(cfg, semente, raiz):
    """Num dia sorteado, a escrita falha após k linhas; a tarefa é reexecutada às 02:10."""
    lote, destino = dados.gerar(semente), casca.Destino(raiz)
    sorteio = random.Random(f"falha-{semente}")
    dia_falha = sorteio.choice(lote.dias)
    n_linhas = len(lote.gabarito[dia_falha.isoformat()])
    k = sorteio.randint(1, max(1, n_linhas - 1))
    for dia in lote.dias:
        if dia != dia_falha:
            _rodar(cfg, dia, dados.instante_agendado(dia), casca.novo_processo(lote), destino, lote)
            continue
        try:
            _rodar(cfg, dia, dados.instante_agendado(dia), casca.novo_processo(lote), destino, lote, falhar_apos=k)
        except casca.FalhaInjetada:
            pass
        _rodar(cfg, dia, dados.instante_agendado(dia) + timedelta(minutes=10),
               casca.novo_processo(lote), destino, lote)
    return destino, lote


def c4_entrega_duplicada(cfg, semente, raiz):
    lote, destino = dados.gerar(semente, fracao_duplicatas=0.10), casca.Destino(raiz)
    for dia in lote.dias:
        _rodar(cfg, dia, dados.instante_agendado(dia), casca.novo_processo(lote), destino, lote)
    return destino, lote


def c5_dados_atrasados(cfg, semente, raiz):
    """Execução agendada (sem os atrasados) e reprocessamento de todos os dias em (último + 2) às 09:00."""
    lote, destino = dados.gerar(semente, fracao_atrasos=0.10), casca.Destino(raiz)
    for dia in lote.dias:
        _rodar(cfg, dia, dados.instante_agendado(dia), casca.novo_processo(lote), destino, lote)
    instante = datetime.combine(lote.dias[-1] + timedelta(days=2), time(9, 0))
    for dia in lote.dias:
        _rodar(cfg, dia, instante, casca.novo_processo(lote), destino, lote)
    return destino, lote


CENARIOS: dict[str, Cenario] = {
    "C0": c0_controle,
    "C1": c1_execucao_duplicada,
    "C2": c2_backfill,
    "C3": c3_falha_parcial,
    "C4": c4_entrega_duplicada,
    "C5": c5_dados_atrasados,
}


# --- Previsão e execução -------------------------------------------------------

def previsto_passar(cfg: Configuracao, cenario: str) -> bool:
    """Hipótese aditiva: falha se algum fator violado falharia isoladamente no cenário."""
    violados = [f for f, ok in zip("TWPD", cfg.rotulo) if ok == "0"]
    return not any(cenario in FALHAS_PREVISTAS[f] for f in violados)


@dataclass(frozen=True)
class Resultado:
    configuracao: str
    cenario: str
    semente: int
    correto: bool
    razao_receita: float  # exploratória, não pré-registrada: receita no destino / receita esperada


def _receita_total(particoes: dict[str, list[dict]]) -> int:
    return sum(linha["receita_centavos"] for linhas in particoes.values() for linha in linhas)


def executar(cfg: Configuracao, cenario: str, semente: int) -> Resultado:
    with tempfile.TemporaryDirectory() as tmp:
        destino, lote = CENARIOS[cenario](cfg, semente, Path(tmp))
        razao = _receita_total(destino.ler_tudo()) / _receita_total(lote.gabarito)
        return Resultado(cfg.rotulo, cenario, semente, confere(destino, lote), razao)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sementes", type=int, default=30)
    parser.add_argument("--saida", type=Path, default=Path("resultados"))
    args = parser.parse_args()
    args.saida.mkdir(parents=True, exist_ok=True)

    resultados = [
        executar(cfg, cenario, semente)
        for cfg in todas_configuracoes()
        for cenario in CENARIOS
        for semente in range(args.sementes)
    ]

    with (args.saida / "qp1_bruto.csv").open("w", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        escritor.writerow(["configuracao", "cenario", "semente", "correto", "razao_receita"])
        for r in resultados:
            escritor.writerow([r.configuracao, r.cenario, r.semente, int(r.correto), f"{r.razao_receita:.4f}"])

    with (args.saida / "qp1_resumo.csv").open("w", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        escritor.writerow(["configuracao", "cenario", "proporcao_correta", "previsto_passar", "confere_previsao"])
        divergencias = 0
        for cfg in todas_configuracoes():
            for cenario in CENARIOS:
                grupo = [r for r in resultados if r.configuracao == cfg.rotulo and r.cenario == cenario]
                proporcao = sum(r.correto for r in grupo) / len(grupo)
                previsto = previsto_passar(cfg, cenario)
                confere_previsao = proporcao == (1.0 if previsto else 0.0)
                divergencias += not confere_previsao
                escritor.writerow([cfg.rotulo, cenario, f"{proporcao:.2f}", int(previsto), int(confere_previsao)])

    print(f"{len(resultados)} execuções; {divergencias} célula(s) divergente(s) da previsão.")


if __name__ == "__main__":
    main()
