"""Premissas carregadas de config/parametros.yaml (copia com CNPJ corrigido)."""
from __future__ import annotations

from decimal import Decimal
from functools import lru_cache

import yaml

from .caminhos import CONFIG_DIR


@lru_cache(maxsize=None)
def cfg() -> dict:
    with open(CONFIG_DIR / "parametros.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def reducoes() -> dict:
    """cClassTrib -> reducao (Decimal 0..1). Sem incidencia -> None (tratado a parte)."""
    p = cfg()["reducao_pct_por_cclasstrib"]
    out = {}
    for k, v in p.items():
        k = str(k).zfill(6)
        if v == "sem incidencia":
            out[k] = None
        else:
            out[k] = Decimal(str(v)) / Decimal("100")
    return out


def cnpj_foco() -> str:
    return cfg()["empresa_foco"]["cnpj"]


def pis_pct() -> Decimal:
    return Decimal(str(cfg()["pis_cofins_hoje"]["pis_pct"])) / Decimal("100")


def cofins_pct() -> Decimal:
    return Decimal(str(cfg()["pis_cofins_hoje"]["cofins_pct"])) / Decimal("100")


def exportacao_icms_zero() -> bool:
    """Se true, zera o ICMS destacado em itens de exportacao (CFOP 7xxx).

    Decisao do case: o ICMS impresso nessas notas e erro de emissao, entao o
    default e true (zero). O flag permite reproduzir o template oficial, que
    mostra o ICMS destacado. Ver config/parametros.yaml.
    """
    return bool(cfg().get("tratamento_exportacao", {}).get("icms_zero", True))


def aliquotas(cenario: str) -> dict:
    """Devolve {'cbs': Decimal, 'ibs': Decimal} do cenario. IBS somado (UF+Mun)."""
    c = cfg()["cenarios"][cenario]
    if cenario == "2027":
        ibs = Decimal(str(c["ibs_uf_pct"])) + Decimal(str(c["ibs_mun_pct"]))
        ibs = ibs / Decimal("100")
        return {"cbs": Decimal(str(c["cbs_pct"])) / Decimal("100"), "ibs": ibs}
    return {
        "cbs": Decimal(str(c["cbs_pct"])) / Decimal("100"),
        "ibs": Decimal(str(c["ibs_pct"])) / Decimal("100"),
    }
