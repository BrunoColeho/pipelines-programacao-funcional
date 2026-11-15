"""Gerador sintético de eventos de pedidos e cálculo independente do gabarito.

O gabarito é calculado a partir da verdade gerada, por código que não
compartilha nenhuma função com o pipeline (ESPECIFICACAO.md, Seção 6).
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

DATA_INICIAL = date(2026, 3, 2)
NIVEIS = ("bronze", "prata", "ouro")
HORA_AGENDADA = time(2, 0)  # a execução de D ocorre em D+1 às 02:00

DEFEITOS = (None, "sem_cliente", "valor_negativo", "valor_ausente", "valor_ilegivel")
PESOS_DEFEITOS = (85, 4, 4, 4, 3)


@dataclass(frozen=True)
class Evento:
    """Um evento verdadeiro, antes de ser serializado na origem."""

    id_evento: str
    id_pedido: str
    id_cliente: str
    valor_centavos: int
    status: str
    ts: datetime
    defeito: str | None


@dataclass(frozen=True)
class Lote:
    """Tudo o que um cenário precisa: chegadas na origem, referência e gabarito."""

    chegadas: tuple[tuple[datetime, str], ...]  # (instante de chegada, registro bruto em JSON)
    referencia_clientes: dict[str, str]
    gabarito: dict[str, list[dict]]             # data ISO -> linhas esperadas
    dias: tuple[date, ...]


def instante_agendado(dia: date) -> datetime:
    return datetime.combine(dia + timedelta(days=1), HORA_AGENDADA)


def gerar(
    semente: int,
    *,
    n_dias: int = 5,
    eventos_por_dia: int = 150,
    n_clientes: int = 40,
    fracao_duplicatas: float = 0.0,
    fracao_atrasos: float = 0.0,
) -> Lote:
    # Dois geradores: a verdade não muda quando mudam duplicatas e atrasos.
    rng_verdade = random.Random(f"verdade-{semente}")
    rng_entrega = random.Random(f"entrega-{semente}")

    clientes = [f"C{i:03d}" for i in range(n_clientes)]
    referencia = {c: rng_verdade.choice(NIVEIS) for c in clientes}
    dias = tuple(DATA_INICIAL + timedelta(days=i) for i in range(n_dias))

    eventos: list[Evento] = []
    for dia in dias:
        for _ in range(eventos_por_dia):
            n = len(eventos) + 1
            defeito = rng_verdade.choices(DEFEITOS, weights=PESOS_DEFEITOS)[0]
            centavos = rng_verdade.randrange(500, 50_001)
            eventos.append(
                Evento(
                    id_evento=f"E{n:06d}",
                    id_pedido=f"P{n:06d}",
                    id_cliente=rng_verdade.choice(clientes),
                    valor_centavos=-centavos if defeito == "valor_negativo" else centavos,
                    status="cancelado" if rng_verdade.random() < 0.05 else "confirmado",
                    ts=datetime.combine(dia, time()) + timedelta(seconds=rng_verdade.randrange(86_400)),
                    defeito=defeito,
                )
            )

    chegadas: list[tuple[datetime, str]] = []
    for ev in eventos:
        bruto = json.dumps(_serializar(ev, versao=rng_verdade.choice((1, 2))), sort_keys=True)
        chegada = ev.ts + timedelta(minutes=rng_entrega.randint(1, 30))
        if rng_entrega.random() < fracao_atrasos:
            inicio = datetime.combine(ev.ts.date() + timedelta(days=1), time(10, 0))
            chegada = inicio + timedelta(minutes=rng_entrega.randrange(600))
        chegadas.append((chegada, bruto))
        if rng_entrega.random() < fracao_duplicatas:
            chegadas.append((chegada + timedelta(minutes=rng_entrega.randint(1, 20)), bruto))

    chegadas.sort(key=lambda par: par[0])
    return Lote(
        chegadas=tuple(chegadas),
        referencia_clientes=referencia,
        gabarito=_calcular_gabarito(eventos, referencia, dias),
        dias=dias,
    )


def _formatar_valor(centavos: int) -> str:
    sinal = "-" if centavos < 0 else ""
    return f"{sinal}{abs(centavos) // 100}.{abs(centavos) % 100:02d}"


def _serializar(ev: Evento, versao: int) -> dict:
    valor = "n/d" if ev.defeito == "valor_ilegivel" else _formatar_valor(ev.valor_centavos)
    if versao == 1:
        bruto = {
            "versao": 1,
            "id_evento": ev.id_evento,
            "id_pedido": ev.id_pedido,
            "id_cliente": ev.id_cliente,
            "valor": valor,
            "status": ev.status,
            "ts": ev.ts.isoformat(),
        }
        if ev.defeito == "sem_cliente":
            del bruto["id_cliente"]
        if ev.defeito == "valor_ausente":
            del bruto["valor"]
        return bruto

    pedido: dict = {"id": ev.id_pedido}
    if ev.defeito != "sem_cliente":
        pedido["cliente"] = {"id": ev.id_cliente}
    pagamento: dict = {"status": ev.status}
    if ev.defeito != "valor_ausente":
        pagamento["valor"] = valor
    return {"versao": 2, "id_evento": ev.id_evento, "pedido": pedido, "pagamento": pagamento, "ts": ev.ts.isoformat()}


def _calcular_gabarito(eventos: list[Evento], referencia: dict[str, str], dias: tuple[date, ...]) -> dict[str, list[dict]]:
    totais: dict[tuple[date, str], tuple[int, int]] = {}
    for ev in eventos:
        if ev.defeito is not None or ev.status != "confirmado":
            continue
        chave = (ev.ts.date(), referencia[ev.id_cliente])
        pedidos, receita = totais.get(chave, (0, 0))
        totais[chave] = (pedidos + 1, receita + ev.valor_centavos)

    gabarito: dict[str, list[dict]] = {}
    for dia in dias:
        linhas = [
            {"data": dia.isoformat(), "nivel": nivel, "pedidos": p, "receita_centavos": c}
            for (d, nivel), (p, c) in totais.items()
            if d == dia
        ]
        gabarito[dia.isoformat()] = sorted(linhas, key=lambda linha: linha["nivel"])
    return gabarito
