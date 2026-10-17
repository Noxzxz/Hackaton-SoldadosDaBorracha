"""Integridade dos entregaveis oficiais (roda sobre saida/)."""
from __future__ import annotations

import json
from decimal import Decimal

import pandas as pd
import pytest

from src.caminhos import SAIDA_DIR
from src.io_dados import classes_vigentes

CSV = SAIDA_DIR / "itens_classificados.csv"
JSON = SAIDA_DIR / "simulacao.json"


pytestmark = pytest.mark.skipif(
    not (CSV.exists() and JSON.exists()),
    reason="rode `python scripts/rodar_tudo.py` antes",
)


def test_csv_shape_e_colunas():
    df = pd.read_csv(CSV, sep=";", encoding="utf-8-sig", dtype=str)
    assert list(df.columns) == [
        "chave", "nItem", "cClassTrib", "status", "confianca", "imposto_seletivo", "fonte",
    ]
    assert len(df) == 15000
    assert df["chave"].str.fullmatch(r"\d{44}").all()
    assert df["cClassTrib"].str.fullmatch(r"\d{6}").all()
    assert set(df["cClassTrib"]).issubset(classes_vigentes())
    assert set(df["status"]).issubset({"CLASSIFICADO", "REVISAR"})
    assert set(df["imposto_seletivo"]).issubset({"sim", "nao"})
    conf = df["confianca"].astype(float)
    assert conf.between(0, 1).all()


def test_json_shape_e_regras():
    sim = json.loads(JSON.read_text(encoding="utf-8"))
    assert sim["cenarios"] == ["hoje", "2027", "2033"]
    assert len(sim["itens"]) == 15000
    assert len(sim["resumo"]) == 3
    for i in sim["itens"]:
        assert i["perspectiva"] in ("compra", "venda")
        assert len(i["cClassTrib"]) == 6
        if i["perspectiva"] == "venda":
            for c in ("hoje", "2027", "2033"):
                assert i[c]["credito"] is None
    res = {r["cenario"]: r for r in sim["resumo"]}
    assert Decimal(str(res["hoje"]["variacao_vs_hoje"])) == Decimal("0")
    for r in sim["resumo"]:
        assert abs(
            Decimal(str(r["debitos_vendas"]))
            - Decimal(str(r["creditos_compras"]))
            - Decimal(str(r["imposto_liquido"]))
        ) <= Decimal("0.01")
