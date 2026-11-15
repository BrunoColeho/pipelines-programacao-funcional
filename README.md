# Pureza e Idempotência em Pipelines de Dados

Artefato do artigo final da disciplina de Introdução à Programação Funcional (mestrado). O estudo investiga quais práticas associadas à programação funcional contribuem para a idempotência e a testabilidade de pipelines de dados em lote.

O desenho completo do experimento, fixado antes das medições, está em [`ESPECIFICACAO.md`](ESPECIFICACAO.md).

## Estrutura

```
src/pipeline/
  config.py        fatores T, W, P, D e as 16 configurações
  dados.py         gerador sintético de eventos e gabarito independente
  nucleo.py        transformações (núcleo funcional e variantes que violam cada princípio)
  casca.py         relógio, origem, destino e ponto de entrada do job
  relogio.py       relógio simulado
  verificacao.py   oráculo: compara o destino com o gabarito
tests/
  test_fumaca.py   verificações do pipeline e do oráculo antes do experimento
```

## Como Executar

Requer Python 3.10 ou superior.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Licença

A definir.
