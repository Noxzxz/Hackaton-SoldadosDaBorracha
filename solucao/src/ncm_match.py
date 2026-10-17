"""Casamento de NCM contra o mapa oficial.

Ordem: NCM exato -> prefixo de 6 -> prefixo de 4 -> sem match.
Mantem somente linhas PERMITIDO (VEDADO exclui a classe).
Devolve (DataFrame de candidatos, tipo_match).
"""
from __future__ import annotations

import pandas as pd

from .io_dados import mapa


def candidatos(ncm: str, mapa_df: pd.DataFrame = None, tipo: str = None) -> tuple:
    m = mapa() if mapa_df is None else mapa_df
    ncm = str(ncm).zfill(8)
    ex = m[(m["NCM"] == ncm) & (m["permissao"] == "PERMITIDO")]
    if len(ex):
        return ex.reset_index(drop=True), "exato"
    p6 = m[(m["NCM"].str.startswith(ncm[:6])) & (m["permissao"] == "PERMITIDO")]
    if len(p6):
        return p6.reset_index(drop=True), "prefixo6"
    p4 = m[(m["NCM"].str.startswith(ncm[:4])) & (m["permissao"] == "PERMITIDO")]
    if len(p4):
        return p4.reset_index(drop=True), "prefixo4"
    return m.iloc[0:0].reset_index(drop=True), "sem_match"


def linhas_vedadas(ncm: str, mapa_df: pd.DataFrame = None) -> pd.DataFrame:
    m = mapa() if mapa_df is None else mapa_df
    ncm = str(ncm).zfill(8)
    return m[(m["NCM"] == ncm) & (m["permissao"] == "VEDADO")]


def numero_linha(ncm: str, cclasstrib: str, mapa_df: pd.DataFrame = None):
    """Numero de linha (1-based, com cabecalho) da decisao no mapa deduplicado."""
    m = mapa() if mapa_df is None else mapa_df
    ncm = str(ncm).zfill(8)
    sel = m[(m["NCM"] == ncm) & (m["cClassTrib"] == cclasstrib)]
    if len(sel):
        return int(sel.index[0]) + 2
    return None
