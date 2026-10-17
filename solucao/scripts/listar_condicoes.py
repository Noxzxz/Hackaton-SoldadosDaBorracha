"""Lista os valores distintos das colunas `condicao` e `excecao` do mapa.

Serve para manter config/condicoes.yaml e config/excecoes.yaml em dia quando o
mapa oficial e atualizado. Nao classifica nada.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.io_dados import mapa  # noqa: E402


def main() -> None:
    m = mapa()
    for col in ("condicao", "excecao"):
        print(f"=== {col} ({m[col].nunique()} distintos) ===")
        for valor, n in m[m[col] != ""][col].value_counts().items():
            print(f"  {n:5d}  {valor}")


if __name__ == "__main__":
    main()
