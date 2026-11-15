"""Oráculo: compara o conteúdo completo do destino com o gabarito (ESPECIFICACAO.md, Seção 6)."""

from __future__ import annotations

import hashlib
import json

from pipeline.casca import Destino
from pipeline.dados import Lote


def canonico(particoes: dict[str, list[dict]]) -> str:
    """Serialização canônica: partições ordenadas, linhas tratadas como multiconjunto."""
    ordenadas = {
        data: sorted(json.dumps(linha, sort_keys=True) for linha in linhas)
        for data, linhas in sorted(particoes.items())
    }
    return json.dumps(ordenadas, sort_keys=True)


def resumo(particoes: dict[str, list[dict]]) -> str:
    return hashlib.sha256(canonico(particoes).encode("utf-8")).hexdigest()


def confere(destino: Destino, lote: Lote) -> bool:
    return resumo(destino.ler_tudo()) == resumo(lote.gabarito)
