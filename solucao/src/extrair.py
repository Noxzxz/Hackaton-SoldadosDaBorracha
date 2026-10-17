"""Extrai todos os itens das DANFEs, com cache em disco (parquet).

Devolve dois DataFrames:
  - itens: uma linha por item extraido da tabela de produtos;
  - notas: uma linha por nota, com totais impressos e resultado da reconciliacao.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Optional

import pandas as pd

from .caminhos import DANFE_DIR, OUT_DIR
from .parse_danfe import Nota

ITENS_PARQUET = OUT_DIR / "itens.parquet"
NOTAS_PARQUET = OUT_DIR / "notas.parquet"

COLS_ITEM = [
    "chave",
    "nItem",
    "cProd",
    "xProd",
    "NCM",
    "CST",
    "CFOP",
    "un",
    "qtd",
    "vUnit",
    "vProd",
    "vICMS",
    "bCalcICMS",
    "emitente_cnpj",
    "destinatario_cnpj",
    "perspectiva",
    "arquivo",
]


def _nota_para_linhas(nota: Nota) -> list:
    linhas = []
    for it in nota.itens:
        linhas.append(
            {
                "chave": it.chave,
                "nItem": it.nItem,
                "cProd": it.cProd,
                "xProd": it.xProd,
                "NCM": it.NCM,
                "CST": it.CST,
                "CFOP": it.CFOP,
                "un": it.un,
                "qtd": str(it.qtd),
                "vUnit": str(it.vUnit),
                "vProd": str(it.vProd),
                "vICMS": str(it.vICMS),
                "bCalcICMS": str(it.bCalcICMS),
                "emitente_cnpj": it.emitente_cnpj,
                "destinatario_cnpj": it.destinatario_cnpj,
                "perspectiva": it.perspectiva,
                "arquivo": it.arquivo,
            }
        )
    return linhas


def _nota_resumo(nota: Nota) -> dict:
    rec = nota.reconciliacao()
    return {
        "chave": nota.chave,
        "perspectiva": nota.perspectiva,
        "emitente_cnpj": nota.emitente_cnpj,
        "destinatario_cnpj": nota.destinatario_cnpj,
        "cfop_nota": nota.cfop_nota,
        "n_itens": len(nota.itens),
        "v_produtos_calc": str(rec.soma_produtos),
        "v_produtos_doc": str(rec.totais_produtos),
        "v_icms_calc": str(rec.soma_icms),
        "v_icms_doc": str(rec.totais_icms),
        "v_pis_calc": str(rec.soma_pis),
        "v_pis_doc": str(rec.totais_pis),
        "v_cofins_calc": str(rec.soma_cofins),
        "v_cofins_doc": str(rec.totais_cofins),
        "reconciliada": rec.ok,
    }


def _parse_one(caminho_str: str) -> tuple:
    """Worker de processo: parseia uma nota e devolve (linhas, resumo)."""
    from pathlib import Path

    from .io_dados import tratamento_por_produto
    from .parse_danfe import parse_pdf

    trat = tratamento_por_produto()
    nota = parse_pdf(Path(caminho_str), trat)
    return _nota_para_linhas(nota), _nota_resumo(nota)


def extrair_tudo(
    danfe_dir: Optional[Path] = None, force: bool = False, workers: Optional[int] = None
) -> tuple:
    if not force and ITENS_PARQUET.exists() and NOTAS_PARQUET.exists():
        itens = pd.read_parquet(ITENS_PARQUET).astype(str)
        notas = pd.read_parquet(NOTAS_PARQUET)
        # P24: preserva booleano quando o parquet ja o guarda; cai no mapa apenas
        # para caches antigos gravados como texto.
        if notas["reconciliada"].dtype == object:
            notas["reconciliada"] = notas["reconciliada"].astype(str).map(
                {"True": True, "False": False}
            )
        else:
            notas["reconciliada"] = notas["reconciliada"].astype(bool)
        return itens, notas

    import os
    from concurrent.futures import ProcessPoolExecutor

    danfe_dir = Path(danfe_dir or DANFE_DIR)
    arquivos = sorted(str(p) for p in danfe_dir.glob("*.pdf"))
    if workers is None:
        workers = max(1, min(8, (os.cpu_count() or 4)))

    linhas: list = []
    resumos: list = []
    if workers <= 1:
        for caminho in arquivos:
            l, r = _parse_one(caminho)
            linhas.extend(l)
            resumos.append(r)
    else:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            for i, (l, r) in enumerate(ex.map(_parse_one, arquivos), 1):
                linhas.extend(l)
                resumos.append(r)
                if i % 200 == 0:
                    print(f"  ... {i} notas", flush=True)

    itens = pd.DataFrame(linhas, columns=COLS_ITEM)
    notas = pd.DataFrame(resumos)
    if len(notas):
        notas["reconciliada"] = notas["reconciliada"].astype(bool)
    itens.to_parquet(ITENS_PARQUET, index=False)
    notas.to_parquet(NOTAS_PARQUET, index=False)
    return itens, notas


def para_decimal(df: pd.DataFrame, cols: list) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            df[c] = df[c].map(lambda x: Decimal(str(x)))
    return df


if __name__ == "__main__":
    itens, notas = extrair_tudo(force=True)
    print("itens", itens.shape)
    print("notas", notas.shape)
    print("reconciliadas", notas["reconciliada"].sum(), "de", len(notas))
    print(itens["perspectiva"].value_counts())
    print("CFOP", itens["CFOP"].value_counts().to_dict())
