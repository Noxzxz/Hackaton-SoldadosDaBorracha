"""Checklist de aceitacao (code freeze). Sai com codigo != 0 se algo falhar."""
from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import pandas as pd  # noqa: E402

from src.caminhos import OUT_DIR, SAIDA_DIR  # noqa: E402
from src.io_dados import classes_vigentes  # noqa: E402


def main() -> int:
    falhas = []
    avisos = []

    # ---------------- itens_classificados.csv ----------------
    csv = pd.read_csv(SAIDA_DIR / "itens_classificados.csv", sep=";", encoding="utf-8-sig", dtype=str)
    if list(csv.columns) != ["chave", "nItem", "cClassTrib", "status", "confianca", "imposto_seletivo", "fonte"]:
        falhas.append(f"colunas do CSV: {list(csv.columns)}")
    if len(csv) != 15000:
        falhas.append(f"CSV tem {len(csv)} linhas (esperado 15000)")
    if not csv["chave"].str.fullmatch(r"\d{44}").all():
        falhas.append("chave fora do padrao 44 digitos")
    if not csv["cClassTrib"].str.fullmatch(r"\d{6}").all():
        falhas.append("cClassTrib nao tem 6 digitos")
    vig = classes_vigentes()
    invalidas = set(csv["cClassTrib"]) - vig
    if invalidas:
        falhas.append(f"cClassTrib fora da tabela vigente: {invalidas}")
    if not set(csv["status"]).issubset({"CLASSIFICADO", "REVISAR"}):
        falhas.append("status invalido")
    if not csv["imposto_seletivo"].isin(["sim", "nao"]).all():
        falhas.append("imposto_seletivo invalido")

    # ---------------- simulacao.json ----------------
    sim = json.loads((SAIDA_DIR / "simulacao.json").read_text(encoding="utf-8"))
    if sim.get("cenarios") != ["hoje", "2027", "2033"]:
        falhas.append("cenarios != [hoje,2027,2033]")
    if len(sim["itens"]) != 15000:
        falhas.append(f"simulacao tem {len(sim['itens'])} itens (esperado 15000)")
    if len(sim["resumo"]) != 3:
        falhas.append("resumo != 3 cenarios")
    vendas_ok = all(
        i[c]["credito"] is None
        for i in sim["itens"]
        if i["perspectiva"] == "venda"
        for c in ("hoje", "2027", "2033")
    )
    if not vendas_ok:
        falhas.append("venda com credito != null")
    if any(i["perspectiva"] not in ("compra", "venda") for i in sim["itens"]):
        falhas.append("perspectiva invalida")

    resumo = {r["cenario"]: r for r in sim["resumo"]}
    if Decimal(str(resumo["hoje"]["variacao_vs_hoje"])) != Decimal("0"):
        falhas.append("variacao_vs_hoje(hoje) != 0")
    for c, r in resumo.items():
        if abs(Decimal(str(r["debitos_vendas"])) - Decimal(str(r["creditos_compras"])) - Decimal(str(r["imposto_liquido"]))) > Decimal("0.01"):
            falhas.append(f"identidade liquido quebrada em {c}")
    if resumo["2033"]["imposto_liquido"] == resumo["2027"]["imposto_liquido"]:
        avisos.append("liquido 2033 igual ao 2027")

    # ---------------- reconciliacao ----------------
    notas = pd.read_parquet(OUT_DIR / "notas.parquet")
    n_ok = int(notas["reconciliada"].astype(bool).sum())
    if n_ok != 1387:
        falhas.append(f"notas reconciliadas {n_ok}/1387")

    # ---------------- relatorio ----------------
    print("=== VALIDACAO DE ENTREGA ===")
    print(f"CSV itens ............. {len(csv)} linhas")
    print(f"simulacao itens ....... {len(sim['itens'])}")
    print(f"notas reconciliadas ... {n_ok}/1387")
    print(f"classes vigentes uso .. {sorted(set(csv['cClassTrib']))}")
    print(f"REVISAR ............... {int((csv['status'] == 'REVISAR').sum())}")
    print(f"Imposto Seletivo ...... {int((csv['imposto_seletivo'] == 'sim').sum())}")
    for c in ("hoje", "2027", "2033"):
        r = resumo[c]
        print(
            f"  {c:>5}: debitos={r['debitos_vendas']:>15,.2f} "
            f"creditos={r['creditos_compras']:>15,.2f} "
            f"liquido={r['imposto_liquido']:>16,.2f} "
            f"variacao={r['variacao_vs_hoje']:>16,.2f}"
        )
    if avisos:
        print("avisos:", avisos)
    if falhas:
        print("FALHAS:")
        for f in falhas:
            print("  -", f)
        return 1
    print("TUDO OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
