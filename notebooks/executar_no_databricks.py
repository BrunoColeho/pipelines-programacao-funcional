# Databricks notebook source
# MAGIC %md
# MAGIC # Execução do experimento no Databricks
# MAGIC
# MAGIC Alternativa à execução local. Pré-requisitos:
# MAGIC 1. O repositório publicado no GitHub ou Codeberg.
# MAGIC 2. No Databricks: **Workspace → Create → Git folder**, informando a URL do repositório.
# MAGIC 3. Abrir este notebook dentro da Git folder e executar as células em ordem.
# MAGIC
# MAGIC O código usa apenas a biblioteca padrão do Python (3.10 ou superior). Os resultados
# MAGIC são gravados em `/tmp/resultados` no driver e exibidos ao final.

# COMMAND ----------

# MAGIC %pip install pytest

# COMMAND ----------

import os
import sys
from pathlib import Path

# Numa Git folder, o diretório de trabalho é a pasta deste notebook.
RAIZ = Path(os.getcwd()).parent
sys.path.insert(0, str(RAIZ / "src"))
print("Python", sys.version.split()[0], "| raiz do repositório:", RAIZ)
assert sys.version_info >= (3, 10), "o pipeline usa casamento de padrões (match), disponível a partir do Python 3.10"

# COMMAND ----------

# MAGIC %md ## 1. Testes (devem passar antes do experimento)

# COMMAND ----------

import pytest

codigo = pytest.main(["-q", "-p", "no:cacheprovider", str(RAIZ / "tests")])
assert codigo == 0, "há testes falhando; não execute o experimento"

# COMMAND ----------

# MAGIC %md ## 2. QP1: 16 configurações x 6 cenários x 30 sementes (cerca de 1 a 2 minutos)

# COMMAND ----------

from pipeline import experimento

SAIDA = Path("/tmp/resultados")
divergencias = experimento.rodar(sementes=30, saida=SAIDA)

# COMMAND ----------

import pandas as pd

resumo = pd.read_csv(SAIDA / "qp1_resumo.csv", dtype={"configuracao": str})
matriz = resumo.pivot(index="configuracao", columns="cenario", values="proporcao_correta").sort_index(ascending=False)
display(matriz.reset_index())
print("Células divergentes da previsão:", divergencias)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Conferência com os resultados do repositório
# MAGIC
# MAGIC O experimento é determinístico: o resumo gerado aqui deve ser idêntico a `resultados/qp1_resumo.csv`.

# COMMAND ----------

original = pd.read_csv(RAIZ / "resultados" / "qp1_resumo.csv", dtype={"configuracao": str})
print("Idêntico ao do repositório:", original.equals(resumo))
