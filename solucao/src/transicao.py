"""Bonus: transicao da reforma 2029-2032 (fora do simulacao.json oficial).

Premissas explicitas:
  - ICMS remanescente = fracao de ICMS configurada em `parametros.yaml`
    (`transicao_icms_bonus`), aplicada ao ICMS liquido de hoje; 2033 = 0.
  - CBS/IBS interpolados linearmente entre os totais de 2027 e 2033 (premissa
    do case; as aliquotas anuais nao sao fixadas pelo Senado).

Nao altera os tres cenarios obrigatorios (`hoje`, `2027`, `2033`). Serve para a
aba de bonus do painel.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

import pandas as pd

from .caminhos import OUT_DIR
from .premissas import cfg

ANOS = [2029, 2030, 2031, 2032]


def r2(x: Decimal) -> Decimal:
    return Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _D(x) -> Decimal:
    return Decimal(str(x))


def _fracao_icms_bonus() -> dict:
    tabela = cfg().get("transicao_icms_bonus", {}) or {}
    return {int(k): float(v) for k, v in tabela.items() if str(k).isdigit()}


def _icms_liquido_hoje(itens: pd.DataFrame, exportacao_zero: bool = True) -> Decimal:
    total = Decimal("0")
    for _, r in itens.iterrows():
        cfop = str(r["CFOP"])
        v = _D(r["vICMS"])
        if exportacao_zero and cfop.startswith("7"):
            v = Decimal("0")
        total += v if str(r["perspectiva"]) == "venda" else -v
    return total


def calcular_transicao(itens: pd.DataFrame, resumo: list) -> pd.DataFrame:
    """Tabela de bonus 2029-2032 (valores liquidos por ano)."""
    from .premissas import exportacao_icms_zero

    liquido = {r["cenario"]: _D(r["imposto_liquido"]) for r in resumo}
    icms_hoje = _icms_liquido_hoje(itens, exportacao_icms_zero())
    # CBS/IBS puros: 2027 = liquido2027 - ICMS (mantido em 2027); 2033 = liquido2033
    cbs_ibs_2027 = liquido["2027"] - icms_hoje
    cbs_ibs_2033 = liquido["2033"]

    fracoes = _fracao_icms_bonus()
    linhas = []
    for ano in ANOS:
        frac = Decimal(str(fracoes.get(ano, 0.0)))
        icms_ano = r2(icms_hoje * frac)
        # interpolacao linear de CBS/IBS entre 2027 (t=0) e 2033 (t=1)
        t = Decimal(str((ano - 2027) / (2033 - 2027)))
        cbs_ibs_ano = r2(cbs_ibs_2027 + (cbs_ibs_2033 - cbs_ibs_2027) * t)
        linhas.append(
            {
                "ano": ano,
                "fracao_icms": float(frac),
                "icms_liquido": str(icms_ano),
                "cbs_ibs_liquido": str(cbs_ibs_ano),
                "imposto_liquido": str(icms_ano + cbs_ibs_ano),
                "premissa": "ICMS=fraq*hoje; CBS/IBS=interp linear 2027-2033",
            }
        )
    return pd.DataFrame(linhas)


def salvar(df: pd.DataFrame) -> None:
    df.to_parquet(OUT_DIR / "transicao_2029_2032.parquet", index=False)


if __name__ == "__main__":
    from .extrair import extrair_tudo
    from .simular import resumo as calc_resumo, simular_dataframe
    from .classificar import classificar_itens
    from .io_dados import cadastro as carregar_cadastro

    itens, _ = extrair_tudo()
    cad = carregar_cadastro()
    cls = classificar_itens(itens, cad)
    sim = simular_dataframe(itens, cls, cad)
    print(calcular_transicao(itens, calc_resumo(sim)).to_string(index=False))
