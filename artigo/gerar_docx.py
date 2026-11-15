"""Gera artigo.docx a partir das mesmas fontes do PDF (resumo.tex, corpo.tex, referencias.bib).

O pandoc não numera tabelas nem listagens; este script numera as legendas e
resolve as referências cruzadas numa cópia temporária antes da conversão.
Uso: python3 gerar_docx.py   (requer pandoc)
"""

import re
import subprocess
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent


def preparar(corpo: str) -> str:
    rotulos: dict[str, str] = {}

    def numerar(ambiente: str, prefixo: str, texto: str) -> str:
        n = 0

        def legenda(m: re.Match) -> str:
            nonlocal n
            n += 1
            bloco = m.group(0)
            rotulo = re.search(r"\\label\{([^}]*)\}", bloco)
            if rotulo:
                rotulos[rotulo.group(1)] = str(n)
            return re.sub(r"\\caption\{", lambda _: f"\\caption{{{prefixo} {n}: ", bloco, count=1)

        return re.sub(rf"\\begin\{{{ambiente}\}}.*?\\end\{{{ambiente}\}}", legenda, texto, flags=re.S)

    corpo = numerar("table", "Tabela", corpo)

    n_lst = 0

    def listagem(m: re.Match) -> str:
        nonlocal n_lst
        n_lst += 1
        opcoes, codigo = m.group(1), m.group(2)
        titulo = re.search(r"caption=\{([^}]*)\}", opcoes).group(1)
        rotulos[re.search(r"label=\{([^}]*)\}", opcoes).group(1)] = str(n_lst)
        return f"\\textbf{{Listagem {n_lst}: {titulo}}}\n\n\\begin{{verbatim}}{codigo}\\end{{verbatim}}"

    corpo = re.sub(r"\\begin\{lstlisting\}\[([^\]]*)\](.*?)\\end\{lstlisting\}", listagem, corpo, flags=re.S)
    return re.sub(r"\\ref\{([^}]*)\}", lambda m: rotulos.get(m.group(1), "\\ref{" + m.group(1) + "}"), corpo)


def main() -> None:
    corpo = preparar((AQUI / "corpo.tex").read_text(encoding="utf-8"))
    resumo = (AQUI / "resumo.tex").read_text(encoding="utf-8")
    fonte = rf"""\documentclass{{article}}
\newcommand{{\ok}}{{✓}}
\newcommand{{\falha}}{{✗}}
\title{{Pureza Não Basta: Quais Práticas Tornam um Pipeline de Dados Seguro para Reexecução}}
\author{{Bruno Cesar Coelho da Silva}}
\begin{{document}}
\maketitle
\begin{{abstract}}
{resumo}
\end{{abstract}}

\textbf{{Palavras-chave:}} Programação Funcional, Pipelines de Dados, Idempotência, Engenharia de Dados, Experimento Controlado.

{corpo}

\section*{{Referências}}
\end{{document}}
"""
    with tempfile.NamedTemporaryFile("w", suffix=".tex", encoding="utf-8", delete=False) as tmp:
        tmp.write(fonte)
    subprocess.run(
        ["pandoc", tmp.name, "-f", "latex", "-t", "docx", "--citeproc",
         "--bibliography", str(AQUI / "referencias.bib"),
         "-M", "lang=pt-BR", "-M", "abstract-title=Resumo", "-M", "link-citations=true",
         "-o", str(AQUI / "artigo.docx")],
        check=True,
    )
    Path(tmp.name).unlink()


if __name__ == "__main__":
    main()
