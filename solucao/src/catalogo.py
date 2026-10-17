"""Catalogo de produtos (o ativo central).

95 pares (cProd, NCM) = 128 descricoes normalizadas. Uma decisao de catalogo e
replicada para todos os itens daquela descricao. Reexporta a construcao
config-driven implementada em classificar.py e le/grava o catalogo em parquet.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .caminhos import OUT_DIR
from .classificar import classificar_produto, construir_catalogo  # noqa: F401
from .io_dados import cadastro as carregar_cadastro

CATALOGO_PARQUET = OUT_DIR / "catalogo.parquet"


def carregar_catalogo(caminho: Path = None) -> pd.DataFrame:
    caminho = Path(caminho or CATALOGO_PARQUET)
    return pd.read_parquet(caminho)


def construir_e_salvar(itens: pd.DataFrame, cadastro: pd.DataFrame = None) -> pd.DataFrame:
    cad = cadastro if cadastro is not None else carregar_cadastro()
    cat = construir_catalogo(itens, cad)
    cat.to_parquet(CATALOGO_PARQUET, index=False)
    return cat


if __name__ == "__main__":
    from .extrair import extrair_tudo

    itens, _ = extrair_tudo()
    cat = construir_e_salvar(itens)
    print(f"catalogo: {len(cat)} pares (cProd, NCM)")
    print(cat[["cProd", "NCM", "familia", "cClassTrib", "confianca", "estabilidade"]].to_string())
