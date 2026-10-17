"""Leitura defensiva das tabelas oficiais.

Regras nao negociaveis:
  - aceita CSV (pacote antigo) ou XLSX (pacote oficial novo);
  - encoding="utf-8-sig", separador ";", dtype=str no CSV;
  - NCM zfill(8), cClassTrib zfill(6), CST zfill(3) como string;
  - dedup do mapa por (NCM, cClassTrib, permissao, condicao, excecao).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pandas as pd

from .caminhos import data_path


def _ler(nome: str) -> pd.DataFrame:
    """Le a tabela pelo nome logico, priorizando .csv e caindo para .xlsx.

    O pacote oficial novo entrega as mesmas tabelas em XLSX; nesse formato as
    colunas numericas perdem zeros a esquerda, por isso todo loader normaliza
    NCM/cClassTrib/CST antes de usar.
    """
    base = Path(nome).stem
    csv = data_path(f"{base}.csv")
    xlsx = data_path(f"{base}.xlsx")
    if csv.exists():
        return pd.read_csv(csv, sep=";", encoding="utf-8-sig", dtype=str)
    if xlsx.exists():
        return pd.read_excel(xlsx, dtype=str)
    raise FileNotFoundError(f"tabela nao encontrada: {csv} ou {xlsx}")


@lru_cache(maxsize=None)
def cadastro() -> pd.DataFrame:
    df = _ler("cadastro_empresas.csv").fillna("")
    df["cnpj_ou_id"] = df["cnpj_ou_id"].astype(str).str.replace(r"\D", "", regex=True)
    return df


@lru_cache(maxsize=None)
def pis_cofins() -> pd.DataFrame:
    df = _ler("pis_cofins_hoje.csv").fillna("")
    df["NCM"] = df["NCM"].str.zfill(8)
    return df


@lru_cache(maxsize=None)
def tratamento_por_produto() -> dict:
    df = pis_cofins()
    return dict(zip(df["cProd"], df["tratamento"]))


@lru_cache(maxsize=None)
def cst_ibscbs() -> pd.DataFrame:
    df = _ler("tabela_cst_ibscbs.csv").fillna("")
    df["CST"] = df["CST"].astype(str).str.zfill(3)
    return df


@lru_cache(maxsize=None)
def cclasstrib() -> pd.DataFrame:
    df = _ler("tabela_cclasstrib.csv").fillna("")
    df["cClassTrib"] = df["cClassTrib"].str.zfill(6)
    df["CST"] = df["cClassTrib"].str[:3]
    return df


@lru_cache(maxsize=None)
def mapa() -> pd.DataFrame:
    df = _ler("mapa_ncm_cclasstrib.csv").fillna("")
    df["NCM"] = df["NCM"].str.zfill(8)
    df["cClassTrib"] = df["cClassTrib"].str.zfill(6)
    df = df.drop_duplicates(
        subset=["NCM", "cClassTrib", "permissao", "condicao", "excecao"]
    ).reset_index(drop=True)
    return df


@lru_cache(maxsize=None)
def exemplos() -> pd.DataFrame:
    df = _ler("exemplos_por_classe.csv").fillna("")
    df["cClassTrib"] = df["cClassTrib"].astype(str).str.zfill(6)
    return df


@lru_cache(maxsize=None)
def parametros() -> dict:
    with open(data_path("parametros.json"), "r", encoding="utf-8") as f:
        return json.load(f)


def classes_vigentes() -> set:
    df = cclasstrib()
    return set(df.loc[df["vigente"] == "sim", "cClassTrib"])


def pesos_reducao() -> dict:
    """Mapeia cClassTrib -> reducao de aliquota (0..1). Sem incidencia -> 1."""
    p = parametros()["reducao_pct_por_cclasstrib"]
    out = {}
    for k, v in p.items():
        if isinstance(v, str):
            out[k.zfill(6)] = 1  # sem incidencia (nao usado no calculo)
        else:
            out[k.zfill(6)] = float(v) / 100.0
    return out


def carga_quantidade() -> float:
    """Fator de carga usada pela regra do mapa (IBS/CBS sobre vProd)."""
    return 1.0


if __name__ == "__main__":
    print("cadastro", cadastro().shape)
    print("pis", pis_cofins().shape)
    print("cst", cst_ibscbs().shape)
    print("cclasstrib", cclasstrib().shape, "vigentes", len(classes_vigentes()))
    print("mapa", mapa().shape)
    print("exemplos", exemplos().shape)
    print("reducoes", pesos_reducao())
