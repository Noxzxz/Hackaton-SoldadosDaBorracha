"""Trilha de auditoria: toda grandeza aponta para a sua origem.

Formato longo, uma linha por (item, grandeza, fonte). E o esqueleto do produto
futuro e a base do painel (20% da nota).
"""
from __future__ import annotations

from decimal import Decimal

import pandas as pd

from .caminhos import OUT_DIR

TRILHA_PARQUET = OUT_DIR / "trilha.parquet"


def _fmt(x: Decimal) -> str:
    return f"{Decimal(x):.2f}"


def construir_trilha(
    itens: pd.DataFrame,
    classificados: pd.DataFrame,
    simulados: list,
    notas: pd.DataFrame,
) -> pd.DataFrame:
    cls = classificados.set_index(["chave", "nItem"])
    itens_idx = itens.assign(nItem=itens["nItem"].astype(int)).set_index(["chave", "nItem"])
    rows = []
    for it in simulados:
        chave, nItem = it["chave"], it["nItem"]
        base = cls.loc[(chave, nItem)]
        cclass = str(it["cClassTrib"])
        arquivo = chave + ".pdf"
        origem_danfe = f"danfe:{arquivo}#chave={chave};nItem={nItem}"

        rows.append(
            dict(
                chave=chave,
                nItem=nItem,
                grandeza="cClassTrib",
                valor=cclass,
                formula=f"classe {cclass} ({base['regra']})",
                fonte_tipo="mapa" if "MAPA" in str(base["fonte"]) else "regra",
                fonte_ref=str(base["fonte"]),
            )
        )
        rows.append(
            dict(
                chave=chave,
                nItem=nItem,
                grandeza="vProd",
                valor=_fmt(it["vProd"]),
                formula="campo VALOR TOTAL do item",
                fonte_tipo="danfe",
                fonte_ref=f"{origem_danfe};campo=VALOR TOTAL",
            )
        )
        try:
            r = itens_idx.loc[(chave, nItem)]
            if isinstance(r, pd.DataFrame):
                r = r.iloc[0]
        except KeyError:
            r = None
        if r is not None:
            rows.append(
                dict(
                    chave=chave,
                    nItem=nItem,
                    grandeza="vICMS",
                    valor=_fmt(Decimal(str(r["vICMS"]))),
                    formula="campo VALOR ICMS do item (CST icms)",
                    fonte_tipo="danfe",
                    fonte_ref=f"{origem_danfe};campo=VALOR ICMS",
                )
            )
        for cen in ("hoje", "2027", "2033"):
            rows.append(
                dict(
                    chave=chave,
                    nItem=nItem,
                    grandeza=f"imposto_{cen}",
                    valor=_fmt(it[cen]["imposto"]),
                    formula=f"imposto do item no cenario {cen}",
                    fonte_tipo="premissa",
                    fonte_ref=f"premissa:parametros.cenarios.{cen}",
                )
            )
            cred = it[cen]["credito"]
            rows.append(
                dict(
                    chave=chave,
                    nItem=nItem,
                    grandeza=f"credito_{cen}",
                    valor="null" if cred is None else _fmt(cred),
                    formula=f"credito do item no cenario {cen}",
                    fonte_tipo="premissa",
                    fonte_ref=f"premissa:parametros.cenarios.{cen}",
                )
            )
    return pd.DataFrame(rows)


def salvar_trilha(df: pd.DataFrame) -> None:
    df.to_parquet(TRILHA_PARQUET, index=False)


if __name__ == "__main__":
    from .extrair import extrair_tudo

    itens, notas = extrair_tudo()
    print("ok", itens.shape)
