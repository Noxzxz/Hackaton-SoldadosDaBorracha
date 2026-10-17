"""Baseline da tributacao de exportacao: ICMS destacado (errado) x ICMS zero (correto).

Gera:
  - out/baseline_exportacao.csv        (resumo por cenario)
  - out/baseline_exportacao_itens.csv  (447 itens de exportacao)
  - out/baseline_exportacao.json       (resumo + metadados + top itens)

Reproduz o mesmo codigo de simulacao, alternando apenas a leitura do flag
`tratamento_exportacao.icms_zero` (via patch), para que as duas baselines sejam
comparaveis e auditaveis.
"""
from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src import premissas
from src.caminhos import OUT_DIR
from src.extrair import extrair_tudo
from src.io_dados import cadastro as carregar_cadastro
from src.simular import resumo as calc_resumo
from src.simular import simular_dataframe

CENARIOS = ("hoje", "2027", "2033")


def _d(x) -> Decimal:
    return Decimal(str(x))


def _resumo_dict(sim: list) -> dict:
    return {r["cenario"]: r for r in calc_resumo(sim)}


def main() -> None:
    itens, _ = extrair_tudo()
    cad = carregar_cadastro()
    cls = pd.read_parquet(OUT_DIR / "classificados.parquet")

    with patch.object(premissas, "exportacao_icms_zero", return_value=False):
        sim_errada = simular_dataframe(itens, cls, cad)
    with patch.object(premissas, "exportacao_icms_zero", return_value=True):
        sim_correta = simular_dataframe(itens, cls, cad)

    res_e = _resumo_dict(sim_errada)
    res_c = _resumo_dict(sim_correta)

    # ---------------- resumo por cenario ----------------
    linhas = []
    for c in CENARIOS:
        e, k = res_e[c], res_c[c]
        linhas.append(
            {
                "cenario": c,
                "debitos_icms_destacado": _d(e["debitos_vendas"]),
                "debitos_icms_zero": _d(k["debitos_vendas"]),
                "diferenca_debitos": _d(e["debitos_vendas"]) - _d(k["debitos_vendas"]),
                "creditos_compras": _d(k["creditos_compras"]),
                "liquido_icms_destacado": _d(e["imposto_liquido"]),
                "liquido_icms_zero": _d(k["imposto_liquido"]),
                "diferenca_liquido": _d(e["imposto_liquido"]) - _d(k["imposto_liquido"]),
                "variacao_icms_destacado": _d(e["variacao_vs_hoje"]),
                "variacao_icms_zero": _d(k["variacao_vs_hoje"]),
            }
        )
    resumo = pd.DataFrame(linhas)
    resumo.to_csv(OUT_DIR / "baseline_exportacao.csv", sep=";", index=False, encoding="utf-8-sig")

    # ---------------- itens de exportacao ----------------
    it = itens.copy()
    it["nItem"] = it["nItem"].astype(int)
    exp = it[(it["perspectiva"] == "venda") & (it["CFOP"].astype(str).str.startswith("7"))].copy()
    sim_e = {(s["chave"], int(s["nItem"])): s for s in sim_errada}
    sim_c = {(s["chave"], int(s["nItem"])): s for s in sim_correta}

    det = []
    for _, r in exp.iterrows():
        k = (r["chave"], int(r["nItem"]))
        e, c = sim_e[k], sim_c[k]
        det.append(
            {
                "chave": r["chave"],
                "nItem": int(r["nItem"]),
                "NCM": r["NCM"],
                "xProd": r["xProd"],
                "CFOP": r["CFOP"],
                "vProd": _d(r["vProd"]),
                "vICMS_destacado": _d(r["vICMS"]),
                "imposto_hoje_icms_destacado": _d(e["hoje"]["imposto"]),
                "imposto_hoje_icms_zero": _d(c["hoje"]["imposto"]),
                "diferenca_hoje": _d(e["hoje"]["imposto"]) - _d(c["hoje"]["imposto"]),
                "imposto_2027_icms_destacado": _d(e["2027"]["imposto"]),
                "imposto_2027_icms_zero": _d(c["2027"]["imposto"]),
                "diferenca_2027": _d(e["2027"]["imposto"]) - _d(c["2027"]["imposto"]),
                "imposto_2033_icms_destacado": _d(e["2033"]["imposto"]),
                "imposto_2033_icms_zero": _d(c["2033"]["imposto"]),
            }
        )
    itens_df = pd.DataFrame(det).sort_values("vICMS_destacado", ascending=False)
    for col in itens_df.columns:
        if itens_df[col].map(lambda x: isinstance(x, Decimal)).any():
            itens_df[col] = itens_df[col].map(lambda x: f"{x:.2f}")
    itens_df.to_csv(
        OUT_DIR / "baseline_exportacao_itens.csv", sep=";", index=False, encoding="utf-8-sig"
    )

    # ---------------- metadados / top itens ----------------
    total_vprod = sum(_d(x) for x in exp["vProd"])
    total_icms = sum(_d(x) for x in exp["vICMS"])
    # "afetado" = item/nota com ICMS destacado positivo; os demais ja eram zero.
    itens_afetados = int((exp["vICMS"].map(_d) > 0).sum())
    notas_afetadas = int(exp.loc[exp["vICMS"].map(_d) > 0, "chave"].nunique())
    top = itens_df.head(10).copy()
    payload = {
        "descricao": "Baseline ICMS de exportacao: valor destacado (errado) x zero (correto)",
        "itens_exportacao": int(len(exp)),
        "itens_afetados": itens_afetados,
        "notas_exportacao": int(exp["chave"].nunique()),
        "notas_afetadas": notas_afetadas,
        "vProd_total": f"{total_vprod:.2f}",
        "icms_destacado_total": f"{total_icms:.2f}",
        "aliquota_icms_efetiva_pct": f"{(total_icms / total_vprod * 100):.2f}" if total_vprod else "0.00",
        "resumo": [
            {k: (f"{v:.2f}" if isinstance(v, Decimal) else v) for k, v in row.items()}
            for row in resumo.to_dict(orient="records")
        ],
        "top_itens_por_icms": top.to_dict(orient="records"),
    }
    (OUT_DIR / "baseline_exportacao.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"=== BASELINE EXPORTACAO ({len(exp)} itens) ===")
    print(resumo.to_string(index=False))
    print(f"\nvProd exportacoes: {total_vprod:.2f}")
    print(f"ICMS destacado total: {total_icms:.2f} ({total_icms / total_vprod * 100:.2f}% do vProd)")
    print(f"Itens de exportacao: {len(exp)} ({itens_afetados} com ICMS > 0)")
    print(f"Notas de exportacao: {exp['chave'].nunique()} ({notas_afetadas} afetadas)")
    print("\nArquivos:")
    for nome in (
        "baseline_exportacao.csv",
        "baseline_exportacao_itens.csv",
        "baseline_exportacao.json",
    ):
        print(" ", OUT_DIR / nome)


if __name__ == "__main__":
    main()
