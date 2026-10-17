"""Simulacao tributaria hoje x 2027 x 2033.

Dinheiro SEMPRE com Decimal + ROUND_HALF_UP, 2 casas, arredondado por tributo
(CBS e IBS separadamente) ANTES de somar. Nunca float no caminho do dinheiro.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

import pandas as pd

from . import premissas
from .io_dados import tratamento_por_produto

CENARIOS = ["hoje", "2027", "2033"]
SEM_INCIDENCIA = {"410001", "410004"}


def r2(x: Decimal) -> Decimal:
    return Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _D(x) -> Decimal:
    return Decimal(str(x))


# --------------------------------------------------------------------------- #
# Tributos por item
# --------------------------------------------------------------------------- #


def pis_cofins_hoje(vProd: Decimal, vICMS: Decimal, cfop: str, tratamento: str) -> tuple:
    """Regra do enunciado: tributado -> base = vProd - vICMS; export/5910 = 0."""
    if tratamento != "tributado":
        return Decimal("0"), Decimal("0")
    if str(cfop).startswith("7") or str(cfop) == "5910":
        return Decimal("0"), Decimal("0")
    base = vProd - vICMS
    return r2(base * premissas.pis_pct()), r2(base * premissas.cofins_pct())


def ibs_cbs(vProd: Decimal, cclass: str, cenario: str) -> tuple:
    """(CBS, IBS) arredondados separadamente. Sem incidencia -> (0, 0)."""
    if cclass in SEM_INCIDENCIA:
        return Decimal("0"), Decimal("0")
    red = premissas.reducoes().get(cclass)
    if red is None:
        return Decimal("0"), Decimal("0")
    fator = Decimal("1") - red
    aliq = premissas.aliquotas(cenario)
    cbs = r2(vProd * aliq["cbs"] * fator)
    ibs = r2(vProd * aliq["ibs"] * fator)
    return cbs, ibs


# --------------------------------------------------------------------------- #
# Simulacao por item
# --------------------------------------------------------------------------- #


def simular_item(
    vProd: Decimal,
    vICMS: Decimal,
    cclass: str,
    cfop: str,
    perspectiva: str,
    finalidade: str,
    tratamento: str,
) -> dict:
    compra = perspectiva == "compra"
    revenda = compra and finalidade == "revenda"

    pis, cof = pis_cofins_hoje(vProd, vICMS, cfop, tratamento)
    # Ressalva de exportacao (enunciado novo): o ICMS impresso e erro de
    # emissao e deve ser considerado zero em CFOP 7xxx. O flag permite voltar
    # ao valor destacado (template oficial).
    icms = (
        Decimal("0")
        if str(cfop).startswith("7") and premissas.exportacao_icms_zero()
        else vICMS
    )
    cbs27, ibs27 = ibs_cbs(vProd, cclass, "2027")
    cbs33, ibs33 = ibs_cbs(vProd, cclass, "2033")

    imposto = {
        "hoje": icms + pis + cof,
        "2027": icms + cbs27 + ibs27,
        "2033": cbs33 + ibs33,
    }
    credito = None
    if compra:
        # P13: credito amplo de IBS/CBS (LC 214) vale inclusive para uso e consumo.
        # A ausencia de `finalidade_compra` no cadastro nao retira o credito novo;
        # apenas o credito de hoje (ICMS/PIS/COFINS) depende de revenda.
        credito = {
            "hoje": (icms + pis + cof) if revenda else Decimal("0"),
            "2027": (icms if revenda else Decimal("0")) + cbs27 + ibs27,
            "2033": cbs33 + ibs33,
        }

    out = {}
    for c in CENARIOS:
        imp = imposto[c]
        aliq = r2(imp / vProd * Decimal("100")) if vProd != 0 else Decimal("0")
        out[c] = {
            "imposto": imp,
            "aliquota_efetiva_pct": aliq,
            "credito": None if credito is None else credito[c],
        }
    return out


# --------------------------------------------------------------------------- #
# Resumo por cenario
# --------------------------------------------------------------------------- #


def resumo(itens_simulados: list) -> list:
    debitos = {c: Decimal("0") for c in CENARIOS}
    creditos = {c: Decimal("0") for c in CENARIOS}
    for it in itens_simulados:
        if it["perspectiva"] == "venda":
            for c in CENARIOS:
                debitos[c] += it[c]["imposto"]
        else:
            for c in CENARIOS:
                cred = it[c]["credito"] or Decimal("0")
                creditos[c] += cred
    liquido = {c: debitos[c] - creditos[c] for c in CENARIOS}
    base = liquido["hoje"]
    return [
        {
            "cenario": c,
            "debitos_vendas": debitos[c],
            "creditos_compras": creditos[c],
            "imposto_liquido": liquido[c],
            "variacao_vs_hoje": liquido[c] - base,
            "variacao_vs_hoje_pct": (
                r2((liquido[c] - base) / abs(base) * Decimal("100"))
                if base != 0
                else Decimal("0")
            ),
        }
        for c in CENARIOS
    ]


# --------------------------------------------------------------------------- #
# API de alto nivel
# --------------------------------------------------------------------------- #


def simular_dataframe(itens: pd.DataFrame, classificados: pd.DataFrame, cadastro: pd.DataFrame) -> list:
    """Cruza itens + classificacao + cadastro e simula todos os itens."""
    cls = classificados.set_index(["chave", "nItem"])
    cad = cadastro.set_index("cnpj_ou_id")
    trat = tratamento_por_produto()

    saida = []
    for _, r in itens.iterrows():
        chave, nItem = r["chave"], int(r["nItem"])
        base = cls.loc[(chave, nItem)]
        emitente = r["emitente_cnpj"]
        finalidade = cad.loc[emitente, "finalidade_compra"] if emitente in cad.index else ""
        sim = simular_item(
            vProd=_D(r["vProd"]),
            vICMS=_D(r["vICMS"]),
            cclass=str(base["cClassTrib"]),
            cfop=str(r["CFOP"]),
            perspectiva=str(r["perspectiva"]),
            finalidade=str(finalidade),
            tratamento=str(trat.get(r["cProd"], "")),
        )
        saida.append(
            {
                "chave": chave,
                "nItem": nItem,
                "perspectiva": r["perspectiva"],
                "cClassTrib": str(base["cClassTrib"]),
                "vProd": _D(r["vProd"]),
                **sim,
            }
        )
    return saida


if __name__ == "__main__":
    # Testes golden do enunciado (PLANEJAMENTO secao 7.5)
    # PFT500 compra revenda, 200034, vProd 1677.50, vICMS 301.95, tributado
    s = simular_item(
        Decimal("1677.50"), Decimal("301.95"), "200034", "5102", "compra", "revenda", "tributado"
    )
    print("PFT500", {k: {kk: str(vv) for kk, vv in v.items()} for k, v in s.items()})
    assert s["hoje"]["imposto"] == Decimal("429.19")
    assert s["2027"]["imposto"] == Decimal("361.00")
    assert s["2033"]["imposto"] == Decimal("177.82")
    assert s["2027"]["credito"] == Decimal("361.00")
    # BISCH venda, 000001, 176.70, 31.81
    s = simular_item(Decimal("176.70"), Decimal("31.81"), "000001", "5102", "venda", "", "tributado")
    assert s["hoje"]["imposto"] == Decimal("45.21"), s
    assert s["2027"]["imposto"] == Decimal("47.36")
    assert s["2033"]["imposto"] == Decimal("46.83")
    assert s["hoje"]["credito"] is None
    # DIV001 compra uso_consumo, 000001, 303690.00, 54664.20
    s = simular_item(
        Decimal("303690.00"), Decimal("54664.20"), "000001", "5102", "compra", "uso_consumo", "tributado"
    )
    assert s["hoje"]["imposto"] == Decimal("77699.09"), s
    assert s["hoje"]["credito"] == Decimal("0.00")
    assert s["2027"]["credito"] == Decimal("26724.72"), s
    assert s["2033"]["imposto"] == Decimal("80477.85"), s
    # UVAIT venda 200014, 1918.08, 0
    s = simular_item(Decimal("1918.08"), Decimal("0"), "200014", "5102", "venda", "", "aliquota_zero")
    assert s["hoje"]["imposto"] == Decimal("0.00")
    assert s["2027"]["imposto"] == Decimal("0.00")
    assert s["2033"]["imposto"] == Decimal("0.00")
    # MACARPE export 410004, 620.40, 43.43
    s = simular_item(Decimal("620.40"), Decimal("43.43"), "410004", "7102", "venda", "", "tributado")
    assert s["hoje"]["imposto"] == Decimal("43.43"), s
    assert s["2027"]["imposto"] == Decimal("43.43")
    assert s["2033"]["imposto"] == Decimal("0.00")
    # RFCLAR bonificacao 410001, 49.46, 0
    s = simular_item(Decimal("49.46"), Decimal("0"), "410001", "5910", "venda", "", "monofasico")
    assert s["hoje"]["imposto"] == Decimal("0.00")
    print("golden OK")
