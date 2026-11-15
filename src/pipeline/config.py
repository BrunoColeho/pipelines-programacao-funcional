"""Configurações experimentais: os quatro fatores binários (ver ESPECIFICACAO.md, Seção 3)."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product


@dataclass(frozen=True)
class Configuracao:
    tempo_injetado: bool = True        # T: data recebida como parâmetro (1) ou derivada do relógio (0)
    sobrescrita: bool = True           # W: partição substituída (1) ou linhas anexadas (0)
    transformacoes_puras: bool = True  # P: etapas sem efeitos colaterais (1) ou com estado mutável (0)
    dedup_por_chave: bool = True       # D: um registro por id_evento (1) ou sem deduplicação (0)

    @property
    def rotulo(self) -> str:
        """Sequência T W P D, por exemplo '1111' ou '0111'."""
        fatores = (self.tempo_injetado, self.sobrescrita, self.transformacoes_puras, self.dedup_por_chave)
        return "".join("1" if f else "0" for f in fatores)

    @classmethod
    def de_rotulo(cls, rotulo: str) -> "Configuracao":
        return cls(*(c == "1" for c in rotulo))


def todas_configuracoes() -> list[Configuracao]:
    """As 2^4 = 16 combinações, de 0000 a 1111."""
    return [Configuracao(*bits) for bits in product((False, True), repeat=4)]
