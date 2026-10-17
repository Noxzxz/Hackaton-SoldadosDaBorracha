"""Nivel 3 (bonus): preco de equilibrio por produto.

mantem a margem de hoje: margem = preco - imposto_da_venda - (custo - credito_compra).
No regime novo o imposto e proporcional ao preco, entao:
    preco_novo = (preco_hoje - imposto_hoje + credito_hoje - credito_novo)
                 / (1 - aliquota_efetiva_nova)
usando custo e credito unitarios medios ponderados por quantidade das compras
do mesmo cProd.
"""
from __future__ import annotations

import logging
from decimal import Decimal, ROUND_HALF_UP

import pandas as pd

logger = logging.getLogger(__name__)


def r2(x: Decimal) -> Decimal:
    return Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _media_ponderada(somas: Decimal, qtot: Decimal) -> Decimal:
    if qtot == 0:
        return Decimal("0")
    return somas / qtot


def precos_equilibrio(
    itens: pd.DataFrame, classificados: pd.DataFrame, simulados: list, cadastro: pd.DataFrame
) -> pd.DataFrame:
    sim_por_item = {(s["chave"], s["nItem"]): s for s in simulados}

    # custo/credito unitario por cProd (compras), ponderado por quantidade
    custo_prod = {}
    for _, r in itens[itens["perspectiva"] == "compra"].iterrows():
        s = sim_por_item.get((r["chave"], int(r["nItem"])))
        if s is None:
            continue
        q = Decimal(str(r["qtd"]))
        if q == 0:
            continue
        agg = custo_prod.setdefault(r["cProd"], {"custo": Decimal("0"), "q": Decimal("0"),
                                                 "cred_hoje": Decimal("0"),
                                                 "cred_2027": Decimal("0"),
                                                 "cred_2033": Decimal("0")})
        agg["custo"] += Decimal(str(r["vProd"]))
        agg["q"] += q
        for c in ("hoje", "2027", "2033"):
            cred = s[c]["credito"] or Decimal("0")
            agg["cred_" + c] += cred

    # preco de venda medio por cProd
    vendas = itens[itens["perspectiva"] == "venda"]
    linhas = []
    for cprod, g in vendas.groupby("cProd"):
        qtot = Decimal(str(g["qtd"].map(lambda x: Decimal(str(x))).sum()))
        if qtot == 0:
            continue
        preco_u = Decimal(str(g["vProd"].map(lambda x: Decimal(str(x))).sum())) / qtot
        imp_u = {c: Decimal("0") for c in ("hoje", "2027", "2033")}
        for _, r in g.iterrows():
            s = sim_por_item.get((r["chave"], int(r["nItem"])))
            if s is None:
                continue
            q = Decimal(str(r["qtd"]))
            for c in ("hoje", "2027", "2033"):
                aliq = s[c]["aliquota_efetiva_pct"] / Decimal("100")
                imp_u[c] += aliq * preco_u * (q / qtot)

        agg = custo_prod.get(cprod)
        if agg is None:
            continue
        custo_u = _media_ponderada(agg["custo"], agg["q"])
        cred_u = {c: _media_ponderada(agg["cred_" + c], agg["q"]) for c in ("hoje", "2027", "2033")}

        row = {"cProd": cprod, "preco_hoje": r2(preco_u), "custo_u": r2(custo_u)}
        for c in ("2027", "2033"):
            denom = Decimal("1") - (imp_u[c] / preco_u if preco_u else Decimal("0"))
            num = preco_u - imp_u["hoje"] + cred_u["hoje"] - cred_u[c]
            row[f"credito_u_{c}"] = r2(cred_u[c])
            row[f"preco_equilibrio_{c}"] = r2(num / denom) if denom > 0 else None
            row[f"variacao_pct_{c}"] = (
                r2((row[f"preco_equilibrio_{c}"] / preco_u - Decimal("1")) * Decimal("100"))
                if row[f"preco_equilibrio_{c}"] is not None and preco_u
                else None
            )
        linhas.append(row)

    df = pd.DataFrame(linhas)
    # P19: transparencia sobre produtos vendidos sem compra correspondente
    # (nao entram no preco de equilibrio por falta de custo/credito unitario).
    produtos_sem_compra = sorted(set(vendas["cProd"].unique()) - set(custo_prod))
    if produtos_sem_compra:
        logger.info(
            "produtos vendidos sem compra correspondente (fora do equilibrio): %s",
            produtos_sem_compra,
        )
    if len(df):
        df = df.sort_values("variacao_pct_2033", ascending=False)
    return df


if __name__ == "__main__":
    from .classificar import classificar_itens
    from .extrair import extrair_tudo
    from .io_dados import cadastro
    from .simular import simular_dataframe

    itens, _ = extrair_tudo()
    cad = cadastro()
    cls = classificar_itens(itens, cad)
    sim = simular_dataframe(itens, cls, cad)
    eq = precos_equilibrio(itens, cls, sim, cad)
    print(eq.head(10).to_string())
