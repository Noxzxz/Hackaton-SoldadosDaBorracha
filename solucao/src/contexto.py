"""Contexto das notas e itens: perspectiva, joins de cadastro e PIS/Cofins.

A perspectiva vem da chave de acesso (fonte de verdade validada):
    chave[6:20] == CNPJ da empresa foco  -> venda; caso contrario -> compra.
"""
from __future__ import annotations

import pandas as pd

from .caminhos import CNPJ_FOCO
from .io_dados import cadastro as _cadastro
from .io_dados import tratamento_por_produto
from .parse_danfe import normalizar_xprod


def perspectiva(chave: str, cnpj_foco: str = CNPJ_FOCO) -> str:
    return "venda" if str(chave)[6:20] == cnpj_foco else "compra"


def juntar_cadastro(itens: pd.DataFrame, cadastro: pd.DataFrame = None) -> pd.DataFrame:
    """Anexa CNAE/tipo_cliente/finalidade_compra do emitente e do destinatario."""
    cad = (cadastro if cadastro is not None else _cadastro()).set_index("cnpj_ou_id")
    df = itens.copy()
    df["emitente_cnae"] = df["emitente_cnpj"].map(lambda c: cad["cnae"].get(c, ""))
    df["emitente_finalidade"] = df["emitente_cnpj"].map(
        lambda c: cad["finalidade_compra"].get(c, "")
    )
    df["destinatario_tipo_cliente"] = df["destinatario_cnpj"].map(
        lambda c: cad["tipo_cliente"].get(c, "")
    )
    return df


def juntar_pis(itens: pd.DataFrame) -> pd.DataFrame:
    df = itens.copy()
    trat = tratamento_por_produto()
    df["tratamento_pis_cofins"] = df["cProd"].map(lambda c: trat.get(c, ""))
    return df


def xprod_normalizado(itens: pd.DataFrame) -> pd.DataFrame:
    df = itens.copy()
    df["xProd_norm"] = df["xProd"].map(normalizar_xprod)
    return df


if __name__ == "__main__":
    from .caminhos import DANFE_DIR

    chave = next(DANFE_DIR.glob("*.pdf")).stem
    print(chave, "->", perspectiva(chave))
