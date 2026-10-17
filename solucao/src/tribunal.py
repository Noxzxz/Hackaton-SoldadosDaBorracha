"""Tribunal de premissas: recalcula o resumo sob as duas leituras das familias
divergentes (mapa estrito x leitura tecnica dos anexos).

Devolve as duas leituras e o custo em R$ de cada uma, alem dos itens afetados.
"""
from __future__ import annotations

from decimal import Decimal

import pandas as pd

from .classificar import (
    classificar_itens,
    construir_catalogo,
    overrides_cfg,
    politica,
    usar_politica,
)
from .simular import resumo as calc_resumo
from .simular import simular_item


def _reclassificar(itens: pd.DataFrame, cadastro: pd.DataFrame, politica_nome: str) -> pd.DataFrame:
    """Reclassifica sob uma politica sem mutar o cache global (P21)."""
    with usar_politica(politica_nome):
        cat = construir_catalogo(itens, cadastro)
        cls = classificar_itens(itens, cadastro, cat)
    return cls


def resolver_itens(itens, classificados, cadastro):
    """Simula os itens sob uma dada classificacao (sem depender da politica global)."""
    from .io_dados import tratamento_por_produto

    trat = tratamento_por_produto()
    cad = cadastro.set_index("cnpj_ou_id")
    cls = classificados.set_index(["chave", "nItem"])
    saida = []
    for _, r in itens.iterrows():
        base = cls.loc[(r["chave"], int(r["nItem"]))]
        emit = r["emitente_cnpj"]
        fin = cad.loc[emit, "finalidade_compra"] if emit in cad.index else ""
        sim = simular_item(
            vProd=Decimal(str(r["vProd"])),
            vICMS=Decimal(str(r["vICMS"])),
            cclass=str(base["cClassTrib"]),
            cfop=str(r["CFOP"]),
            perspectiva=str(r["perspectiva"]),
            finalidade=str(fin),
            tratamento=str(trat.get(r["cProd"], "")),
        )
        saida.append(
            {"chave": r["chave"], "nItem": int(r["nItem"]),
             "perspectiva": r["perspectiva"], "cClassTrib": str(base["cClassTrib"]),
             "vProd": Decimal(str(r["vProd"])), **sim}
        )
    return saida


def julgar(itens: pd.DataFrame, cadastro: pd.DataFrame) -> dict:
    ativa = None

    pol = politica()
    leituras = {}
    classes_por_leitura = {}
    for nome in ("alinhada_gabarito", "mapa_estrito"):
        cls = _reclassificar(itens, cadastro, nome)
        sim = resolver_itens(itens, cls, cadastro)
        classes_por_leitura[nome] = cls.set_index(["chave", "nItem"])["cClassTrib"]
        leituras[nome] = {
            "resumo": calc_resumo(sim),
            "distribuicao": cls["cClassTrib"].value_counts().to_dict(),
        }
        if nome == pol:
            ativa = nome

    # itens afetados pelas 7 familias (NCMs divergentes)
    overrides = {o["ncm"]: o for o in overrides_cfg()}
    afetados = int(itens["NCM"].isin(overrides).sum())

    # itens efetivamente reclassificados entre as duas leituras
    a = classes_por_leitura["alinhada_gabarito"]
    b = classes_por_leitura["mapa_estrito"]
    comuns = a.index.intersection(b.index)
    reclassificados = int((a.loc[comuns] != b.loc[comuns]).sum())

    def liq(leitura, cen):
        for r in leitura["resumo"]:
            if r["cenario"] == cen:
                return r["imposto_liquido"]
        return Decimal("0")

    resultado = {
        "politica_ativa": ativa,
        "itens_afetados": afetados,
        "itens_reclassificados": reclassificados,
        "familias": overrides_cfg(),
        "leituras": leituras,
        "custo_por_leitura": {
            "alinhada_gabarito": {c: str(liq(leituras["alinhada_gabarito"], c)) for c in ("hoje", "2027", "2033")},
            "mapa_estrito": {c: str(liq(leituras["mapa_estrito"], c)) for c in ("hoje", "2027", "2033")},
        },
    }
    return resultado


if __name__ == "__main__":
    from .extrair import extrair_tudo
    from .io_dados import cadastro

    itens, _ = extrair_tudo()
    r = julgar(itens, cadastro())
    print("politica ativa:", r["politica_ativa"], "afetados:", r["itens_afetados"])
    print("liquido 2033 alinhada:", r["custo_por_leitura"]["alinhada_gabarito"]["2033"])
    print("liquido 2033 estrito :", r["custo_por_leitura"]["mapa_estrito"]["2033"])
