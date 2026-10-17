"""Exporta os entregaveis oficiais e a base do painel.

  - saida/itens_classificados.csv  (15.000 linhas; ';')
  - saida/simulacao.json           (15.000 itens + 3 resumos)
  - out/*.parquet                  (base do painel: itens, catalogo, trilha)
  - out/tribunal.json              (as duas leituras das familias divergentes)
"""
from __future__ import annotations

import json
import re
from decimal import Decimal

import pandas as pd

from .caminhos import OUT_DIR, SAIDA_DIR
from .classificar import classificar_itens, construir_catalogo, politica
from .equilibrio import precos_equilibrio
from .extrair import extrair_tudo
from .io_dados import cadastro as carregar_cadastro
from .llm_juiz import resolver_fila
from .simular import resumo as calc_resumo
from .simular import simular_dataframe
from .trilha import construir_trilha, salvar_trilha
from .tribunal import julgar

CSV_COLS = ["chave", "nItem", "cClassTrib", "status", "confianca", "imposto_seletivo", "fonte"]

_RE_DEC = re.compile(r'"__DEC__(-?\d+\.\d{2})__"')


def _conv(obj):
    if isinstance(obj, Decimal):
        return f"__DEC__{obj:.2f}__"
    if isinstance(obj, dict):
        return {k: _conv(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_conv(v) for v in obj]
    return obj


def dumps_decimal(payload: dict, indent: int = 1) -> str:
    """Serializa JSON mantendo Decimal com 2 casas como numero (nunca float)."""
    texto = json.dumps(_conv(payload), ensure_ascii=False, indent=indent)
    return _RE_DEC.sub(r"\1", texto)


def _salvar_simulados(itens, classificados, simulados) -> None:
    """Tabela achatada para o painel: item + tributacao nos 3 cenarios."""
    itens = itens.copy()
    itens["nItem"] = itens["nItem"].astype(int)
    idx = itens.set_index(["chave", "nItem"])
    cls = classificados.set_index(["chave", "nItem"])
    rows = []
    for s in simulados:
        k = (s["chave"], int(s["nItem"]))
        base = idx.loc[k]
        c = cls.loc[k]
        row = {
            "chave": s["chave"],
            "nItem": int(s["nItem"]),
            "cProd": base["cProd"],
            "xProd": base["xProd"],
            "NCM": base["NCM"],
            "CFOP": base["CFOP"],
            "perspectiva": s["perspectiva"],
            "familia": c["familia"],
            "cClassTrib": s["cClassTrib"],
            "status": c["status"],
            "confianca": float(c["confianca"]),
            "imposto_seletivo": c["imposto_seletivo"],
            "fonte": c["fonte"],
            "regra": c["regra"],
            "divergente": bool(c["divergente"]),
            "emitente_cnpj": base["emitente_cnpj"],
            "destinatario_cnpj": base["destinatario_cnpj"],
            "vProd": float(s["vProd"]),
            "vICMS": float(base["vICMS"]),
        }
        for cen in ("hoje", "2027", "2033"):
            row[f"imposto_{cen}"] = float(s[cen]["imposto"])
            row[f"aliquota_{cen}"] = float(s[cen]["aliquota_efetiva_pct"])
            cred = s[cen]["credito"]
            row[f"credito_{cen}"] = None if cred is None else float(cred)
        rows.append(row)
    pd.DataFrame(rows).to_parquet(OUT_DIR / "itens_simulados.parquet", index=False)


def exportar_tudo(salvar_painel: bool = True, usar_llm: bool = True) -> dict:
    itens, notas = extrair_tudo()
    cad = carregar_cadastro()

    catalogo = construir_catalogo(itens, cad)
    fila = None
    if usar_llm:
        catalogo, fila = resolver_fila(catalogo)
        if fila is not None and fila.auditoria:
            pd.DataFrame(fila.auditoria).to_csv(
                OUT_DIR / "auditoria_ambiguos.csv",
                sep=";",
                index=False,
                encoding="utf-8-sig",
            )
    classificados = classificar_itens(itens, cad, catalogo)
    simulados = simular_dataframe(itens, classificados, cad)
    resumo = calc_resumo(simulados)

    # ---------------- CSV ----------------
    csv = classificados[CSV_COLS].copy()
    csv["nItem"] = csv["nItem"].astype(int)
    csv["confianca"] = csv["confianca"].map(lambda x: f"{x:.2f}")
    csv = csv[CSV_COLS]
    (SAIDA_DIR / "itens_classificados.csv").parent.mkdir(parents=True, exist_ok=True)
    csv.to_csv(SAIDA_DIR / "itens_classificados.csv", sep=";", index=False, encoding="utf-8-sig")

    # ---------------- JSON ----------------
    payload = {
        "cenarios": ["hoje", "2027", "2033"],
        "itens": simulados,
        "resumo": resumo,
    }
    with open(SAIDA_DIR / "simulacao.json", "w", encoding="utf-8") as f:
        f.write(dumps_decimal(payload, indent=1))

    if salvar_painel:
        # base do painel
        itens.to_parquet(OUT_DIR / "itens.parquet", index=False)
        catalogo.to_parquet(OUT_DIR / "catalogo.parquet", index=False)
        classificados.to_parquet(OUT_DIR / "classificados.parquet", index=False)
        _salvar_simulados(itens, classificados, simulados)
        trilha = construir_trilha(itens, classificados, simulados, notas)
        salvar_trilha(trilha)
        try:
            eq = precos_equilibrio(itens, classificados, simulados, cad)
            eq.to_parquet(OUT_DIR / "equilibrio.parquet", index=False)
        except Exception as e:  # noqa: BLE001
            print("aviso: equilibrio falhou:", e)
        try:
            trib = julgar(itens, cad)
            with open(OUT_DIR / "tribunal.json", "w", encoding="utf-8") as f:
                f.write(dumps_decimal(trib, indent=1))
        except Exception as e:  # noqa: BLE001
            print("aviso: tribunal falhou:", e)

    return {
        "n_itens": len(simulados),
        "resumo": resumo,
        "politica": politica(),
        "reconciliadas": int(notas["reconciliada"].astype(bool).sum()),
        "n_notas": len(notas),
        "fila_llm": (
            {
                "habilitado": fila.habilitado,
                "n_fila": fila.n_fila,
                "n_llm": fila.n_llm,
                "n_revisar": fila.n_revisar,
                "n_regra": fila.n_regra,
                "chamadas": fila.chamadas,
                "tokens_entrada": fila.tokens_entrada,
                "tokens_saida": fila.tokens_saida,
            }
            if fila is not None
            else None
        ),
    }


if __name__ == "__main__":
    info = exportar_tudo()
    print("itens:", info["n_itens"], "politica:", info["politica"])
    for r in info["resumo"]:
        print(r["cenario"], {k: str(v) for k, v in r.items() if k != "cenario"})
