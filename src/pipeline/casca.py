"""Casca de efeitos do pipeline: relógio, origem, destino e o ponto de entrada.

Concentra todo o contato com o mundo externo (etapas 1 e 7 da especificação).
"""

from __future__ import annotations

import importlib
import json
from datetime import date, datetime, timedelta
from pathlib import Path

from pipeline import nucleo, relogio
from pipeline.config import Configuracao
from pipeline.dados import Lote


class Origem:
    """Área de chegada dos eventos. Uma instância por processo.

    Os registros desserializados ficam em cache durante a vida do processo,
    como um DataFrame em cache numa sessão (ESPECIFICACAO.md, Seção 4).
    """

    def __init__(self, chegadas: tuple[tuple[datetime, str], ...]):
        self._chegadas = chegadas
        self._cache: list[tuple[datetime, dict]] | None = None

    def ler(self, data_alvo: date, visivel_em: datetime) -> list[dict]:
        if self._cache is None:
            self._cache = [(chegada, json.loads(bruto)) for chegada, bruto in self._chegadas]
        prefixo = data_alvo.isoformat()
        return [r for chegada, r in self._cache if chegada <= visivel_em and r["ts"][:10] == prefixo]


class FalhaInjetada(RuntimeError):
    """Falha simulada durante a escrita de uma partição."""


class Destino:
    """Tabela de saída particionada por data, um arquivo JSON Lines por partição."""

    def __init__(self, raiz: Path):
        self.raiz = Path(raiz)
        self.raiz.mkdir(parents=True, exist_ok=True)

    def _arquivo(self, data: date) -> Path:
        return self.raiz / f"data={data.isoformat()}" / "parte.jsonl"

    def escrever(self, data: date, linhas: list[dict], *, sobrescrever: bool, falhar_apos: int | None = None) -> None:
        """[W=1] substitui a partição; [W=0] anexa linhas a ela.

        Com `falhar_apos=k`, a escrita é interrompida depois de k linhas,
        deixando a partição parcialmente gravada.
        """
        arquivo = self._arquivo(data)
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        with arquivo.open("w" if sobrescrever else "a", encoding="utf-8") as saida:
            for i, linha in enumerate(linhas):
                if falhar_apos is not None and i == falhar_apos:
                    raise FalhaInjetada(f"falha após {i} linha(s) na partição {data}")
                saida.write(json.dumps(linha, sort_keys=True) + "\n")

    def ler_tudo(self) -> dict[str, list[dict]]:
        particoes: dict[str, list[dict]] = {}
        for arquivo in sorted(self.raiz.glob("data=*/parte.jsonl")):
            data = arquivo.parent.name.removeprefix("data=")
            linhas = arquivo.read_text(encoding="utf-8").splitlines()
            particoes[data] = [json.loads(linha) for linha in linhas if linha]
        return particoes


def novo_processo(lote: Lote) -> Origem:
    """Simula o início de um processo Python: estado de módulo do núcleo zerado e cache vazio."""
    importlib.reload(nucleo)
    return Origem(lote.chegadas)


def executar_job(
    cfg: Configuracao,
    data_logica: date,
    origem: Origem,
    destino: Destino,
    referencia: dict[str, str],
    *,
    falhar_apos: int | None = None,
) -> date:
    """Ponto de entrada chamado pelo orquestrador. Devolve a data efetivamente processada."""
    if cfg.tempo_injetado:
        data_alvo = data_logica                                  # [T=1] data recebida do orquestrador
    else:
        data_alvo = relogio.agora().date() - timedelta(days=1)   # [T=0] "ontem" segundo o relógio

    # O instante atual define apenas quais dados já chegaram: é o estado do mundo, não uma escolha do código.
    brutos = origem.ler(data_alvo, visivel_em=relogio.agora())
    transformar = nucleo.montar_transformacao(cfg, referencia, data_alvo)
    destino.escrever(data_alvo, transformar(brutos), sobrescrever=cfg.sobrescrita, falhar_apos=falhar_apos)
    return data_alvo
