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
pytest                                   # testes de fumaça e dos cenários
python -m pipeline.experimento           # QP1: 16 configurações x 6 cenários x 30 sementes (~1 min)
```

Os resultados são gravados em `resultados/`:

- `qp1_bruto.csv`: uma linha por execução (configuração, cenário, semente, acerto e razão de receita);
- `qp1_resumo.csv`: proporção de acertos por configuração e cenário, com a previsão da Seção 8 da especificação.

A coluna `razao_receita` é uma medida exploratória, não pré-registrada.

## Histórico do Experimento

A tag `especificacao-v1.0` marca o commit em que a especificação foi registrada, antes de qualquer medição. Os resultados foram gerados em commits posteriores.

## Licença

A definir.
