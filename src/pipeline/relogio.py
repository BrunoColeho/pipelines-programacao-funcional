"""Relógio do mundo simulado.

Em produção, `agora()` corresponderia a `datetime.now()`. Aqui o experimento
ajusta o instante para reproduzir execuções agendadas, reexecuções e backfills.
"""

from __future__ import annotations

from datetime import datetime

_instante: datetime | None = None


def ajustar(instante: datetime) -> None:
    global _instante
    _instante = instante


def agora() -> datetime:
    if _instante is None:
        raise RuntimeError("relógio simulado não ajustado")
    return _instante
