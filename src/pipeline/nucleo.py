"""Núcleo de transformações do pipeline (etapas 2 a 6 da especificação).

Os fatores P e D têm duas variantes cada; `montar_transformacao` escolhe entre
elas conforme a configuração. As variantes que violam o princípio estão
marcadas como tal e reproduzem defeitos comuns em código real.

Conceitos de programação funcional exigidos pela disciplina:
- funções de primeira classe: `compor`, `montar_transformacao`, `partial`;
- funções nomeadas e anônimas: as etapas e as lambdas em `montar_transformacao`;
- casamento de padrões: `compor` e `_campos`;
- recursão: `compor`;
- processamento de coleções: `map`, `filter`, `reduce`, `sorted`, `groupby`.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from functools import partial, reduce
from itertools import groupby
from operator import itemgetter
from typing import Any, Callable

from pipeline.config import Configuracao

Registro = dict[str, Any]
Etapa = Callable[[Any], Any]


# --- Composição -----------------------------------------------------------

def identidade(x: Any) -> Any:
    return x


def compor(*etapas: Etapa) -> Etapa:
    """Compõe as etapas da esquerda para a direita: compor(f, g)(x) == g(f(x))."""
    match etapas:
        case ():
            return identidade
        case (primeira, *resto):
            seguinte = compor(*resto)
            return lambda dados: seguinte(primeira(dados))


# --- Normalização ---------------------------------------------------------

def para_centavos(valor: Any) -> int | None:
    """Converte reais para centavos inteiros; devolve None se o valor for ilegível."""
    try:
        return int(Decimal(str(valor)) * 100)
    except (InvalidOperation, ValueError):
        return None


def _campos(bruto: Registro) -> tuple | None:
    """Extrai os campos dos formatos v1 (plano) e v2 (aninhado) por casamento de padrões."""
    match bruto:
        case {"versao": 1, "id_evento": ev, "id_pedido": ped, "id_cliente": str(cli),
              "valor": valor, "status": status, "ts": ts}:
            return ev, ped, cli, valor, status, ts
        case {"versao": 2, "id_evento": ev, "pedido": {"id": ped, "cliente": {"id": str(cli)}},
              "pagamento": {"valor": valor, "status": status}, "ts": ts}:
            return ev, ped, cli, valor, status, ts
        case _:
            return None


def _registro(ev, ped, cli, centavos, status, ts) -> Registro | None:
    if centavos is None:
        return None
    return {
        "id_evento": ev,
        "id_pedido": ped,
        "id_cliente": cli,
        "valor_centavos": centavos,
        "status": status,
        "data": datetime.fromisoformat(ts).date(),
    }


def normalizar(bruto: Registro) -> Registro | None:
    """[P=1] Devolve um registro novo; o registro recebido não é alterado."""
    match _campos(bruto):
        case None:
            return None
        case (ev, ped, cli, valor, status, ts):
            return _registro(ev, ped, cli, para_centavos(valor), status, ts)


def normalizar_no_lugar(bruto: Registro) -> Registro | None:
    """[P=0] Converte o valor para centavos no próprio registro recebido.

    Se o mesmo objeto for lido de novo (cache da origem no mesmo processo),
    o valor já em centavos é convertido outra vez e fica multiplicado por 100.
    """
    match bruto:
        case {"versao": 1, "valor": valor}:
            bruto["valor"] = para_centavos(valor)
        case {"versao": 2, "pagamento": {"valor": valor} as pagamento}:
            pagamento["valor"] = para_centavos(valor)
    match _campos(bruto):
        case None:
            return None
        case (ev, ped, cli, centavos, status, ts):
            return _registro(ev, ped, cli, centavos, status, ts)


# --- Validação, deduplicação e enriquecimento ------------------------------

def e_valido(registro: Registro) -> bool:
    return registro["status"] == "confirmado" and registro["valor_centavos"] >= 0


def _ordem_canonica(registro: Registro) -> tuple:
    return tuple(sorted((k, str(v)) for k, v in registro.items()))


def deduplicar(registros: list[Registro]) -> list[Registro]:
    """[D=1] Mantém um registro por id_evento, escolhido de forma determinística."""
    chave = itemgetter("id_evento")
    return [min(grupo, key=_ordem_canonica) for _, grupo in groupby(sorted(registros, key=chave), key=chave)]


def enriquecer(referencia: dict[str, str], registros: list[Registro]) -> list[Registro]:
    """[P=1] Devolve registros novos com o nível do cliente."""
    return [{**r, "nivel": referencia.get(r["id_cliente"], "desconhecido")} for r in registros]


def enriquecer_no_lugar(referencia: dict[str, str], registros: list[Registro]) -> list[Registro]:
    """[P=0] Acrescenta o nível alterando os próprios registros."""
    for r in registros:
        r["nivel"] = referencia.get(r["id_cliente"], "desconhecido")
    return registros


# --- Agregação -------------------------------------------------------------

def _linha(data: date, nivel: str, pedidos: int, receita: int) -> Registro:
    return {"data": data.isoformat(), "nivel": nivel, "pedidos": pedidos, "receita_centavos": receita}


def _acumular(totais: dict, registro: Registro) -> dict:
    chave = (registro["data"], registro["nivel"])
    pedidos, receita = totais.get(chave, (0, 0))
    return {**totais, chave: (pedidos + 1, receita + registro["valor_centavos"])}


def agregar(registros: list[Registro]) -> list[Registro]:
    """[P=1] Dobra (fold) imutável sobre os registros."""
    totais = reduce(_acumular, registros, {})
    return [_linha(d, n, p, c) for (d, n), (p, c) in sorted(totais.items())]


def agregar_com_estado(registros: list[Registro], data_alvo: date, _acumulado: dict = {}) -> list[Registro]:  # noqa: B006
    """[P=0] Usa um argumento padrão mutável como acumulador.

    O dicionário é criado uma única vez, quando o módulo é carregado, e
    sobrevive entre chamadas no mesmo processo: totais de execuções anteriores
    são somados aos da execução atual.
    """
    for r in registros:
        pedidos, receita = _acumulado.get(r["nivel"], (0, 0))
        _acumulado[r["nivel"]] = (pedidos + 1, receita + r["valor_centavos"])
    return [_linha(data_alvo, n, p, c) for n, (p, c) in sorted(_acumulado.items())]


# --- Montagem --------------------------------------------------------------

def montar_transformacao(cfg: Configuracao, referencia: dict[str, str], data_alvo: date) -> Etapa:
    """Monta o núcleo como composição de etapas, conforme os fatores P e D."""
    puro = cfg.transformacoes_puras
    normalizacao = normalizar if puro else normalizar_no_lugar
    return compor(
        lambda brutos: [r for r in map(normalizacao, brutos) if r is not None],
        lambda registros: list(filter(lambda r: e_valido(r) and r["data"] == data_alvo, registros)),
        deduplicar if cfg.dedup_por_chave else identidade,
        partial(enriquecer if puro else enriquecer_no_lugar, referencia),
        agregar if puro else partial(agregar_com_estado, data_alvo=data_alvo),
    )
