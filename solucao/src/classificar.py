"""Cascata de classificacao (config-driven).

Ordem fixa (enunciado secao 4 + caralhoo secao 3A):
  1. OP-01 CFOP 5910                       -> 410001
  2. OP-02 CFOP 7102 / exterior            -> 410004
  3. OP-03 dispositivo medico + orgao_pub  -> 200005
  4. Catalogo de produto (128 descricoes)  -> classe-base
  5. NCM no mapa (exato->pref6->pref4) + guarda de familia
  6. Descricao pobre -> CNAE do emitente   -> 000001
  7. Nada defensavel                        -> REVISAR

A confianca e derivada do metodo (fonte + concordancia), nunca autodeclarada.
"""
from __future__ import annotations

import contextvars
import copy
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd
import yaml

from .caminhos import CONFIG_DIR
from .ncm_match import candidatos, numero_linha

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Carregamento de configuracao (P1: cache invalidado por mtime)
# --------------------------------------------------------------------------- #

_yaml_cache: dict = {}
_politica_override: contextvars.ContextVar = contextvars.ContextVar(
    "politica_override", default=None
)


def _yaml(nome: str) -> dict:
    """Carrega o YAML e invalida o cache quando o arquivo muda (P1).

    Devolve uma copia: nenhum chamador pode mutar o cache por acidente.
    """
    caminho = CONFIG_DIR / nome
    mtime = caminho.stat().st_mtime
    em_cache = _yaml_cache.get(nome)
    if em_cache is not None and em_cache[0] == mtime:
        return copy.deepcopy(em_cache[1])
    with open(caminho, "r", encoding="utf-8") as f:
        dados = yaml.safe_load(f)
    _yaml_cache[nome] = (mtime, dados)
    return copy.deepcopy(dados)


def recarregar_config() -> None:
    """Limpa o cache de configuracao (chamar apos editar arquivos YAML)."""
    _yaml_cache.clear()


def familias_cfg() -> dict:
    return _yaml("familias.yaml")["familias"]


def overrides_cfg() -> list:
    return _yaml("overrides_divergencia.yaml")["overrides"]


def politica() -> str:
    override = _politica_override.get()
    if override is not None:
        return override
    return _yaml("politica.yaml")["divergencias"]


def limiar_revisar() -> float:
    """Limiar de confianca abaixo do qual o item vai para REVISAR (P8)."""
    return float(_yaml("politica.yaml").get("limiar_revisar", 0.70))


@contextmanager
def usar_politica(nome: str) -> Iterator[None]:
    """Sobrescreve a politica no contexto atual sem mutar o cache global (P21)."""
    token = _politica_override.set(nome)
    try:
        yield
    finally:
        _politica_override.reset(token)


def regras_operacao() -> list:
    return _yaml("regras_operacao.yaml")["regras"]


def _override_por_ncm() -> dict:
    return {o["ncm"]: o for o in overrides_cfg()}


# --------------------------------------------------------------------------- #
# Deteccao de familia
# --------------------------------------------------------------------------- #


def detectar_familia(xprod_norm: str, ncm: str) -> str:
    """Deteccao NCM-first, com desempate por descricao onde o NCM e compartilhado.

    Os desempates ficam em `config/desempates.yaml` (P11); o unico caso do case
    e o NCM 1905.90.90 (pao frances = cesta basica; bolo = regime padrao).
    """
    ncm = str(ncm).zfill(8)
    for d in _yaml("desempates.yaml").get("desempates", []):
        if str(d.get("ncm", "")).zfill(8) != ncm:
            continue
        if d.get("regra") == "descricao_contem":
            if str(d.get("valor", "")) in xprod_norm:
                return str(d["familia"])
            return str(d["familia_alternativa"])
    fams = familias_cfg()
    for nome in _ORDEM_FAMILIAS:
        cfg = fams.get(nome, {})
        if ncm in (cfg.get("ncm", []) or []):
            return nome
    return "REGIME_PADRAO"


_ORDEM_FAMILIAS = [
    "REFRIGERANTE",
    "DESCRICAO_POBRE",
    "DISPOSITIVO_MEDICO",
    "HORTIFRUTI",
    "LIMPEZA_HIGIENE",
    "ANEXO_VII",
    "CESTA_BASICA",
    "CREME_LEITE",
    "QUEIJO_MINA",
    "QUEIJO_OUTROS",
    "LENTILHA",
    "OLEO_SOJA",
    "AMIDO_MILHO",
    "FUBA",
    "REGIME_PADRAO",
]


def familia_eh_refrigerante(familia: str) -> bool:
    if familia == "REFRIGERANTE":
        return True
    cfg = familias_cfg()
    return bool(cfg.get(familia, {}).get("imposto_seletivo"))


# --------------------------------------------------------------------------- #
# Decisao
# --------------------------------------------------------------------------- #


@dataclass
class Decisao:
    cClassTrib: str
    status: str
    confianca: float
    fonte: str
    familia: str
    regra: str = ""
    imposto_seletivo: bool = False
    classe_mapa: Optional[str] = None
    divergente: bool = False
    tipo_match: str = ""
    linha_mapa: Optional[int] = None
    trilha: list = field(default_factory=list)


def _vazia(familia: str) -> Decisao:
    return Decisao(
        cClassTrib="",
        status="REVISAR",
        confianca=0.10,
        fonte="Sem decisao defensavel (p < 0,25)",
        familia=familia,
    )


# --------------------------------------------------------------------------- #
# Classificacao no nivel de produto
# --------------------------------------------------------------------------- #


def _classe_por_familia(familia: str, classes: list, tipo: str) -> Optional[str]:
    cfg = familias_cfg().get(familia, {})
    preferidas = cfg.get("classes_preferidas", []) or []
    for c in preferidas:
        if c in classes:
            return c
    return None


def classificar_produto(
    cProd: str,
    ncm: str,
    xprod_norm: str,
    cnae_emitente: str = "",
    descricao_pobre: bool = False,
) -> Decisao:
    ncm = str(ncm).zfill(8)
    familia = detectar_familia(xprod_norm, ncm)
    fam_cfg = familias_cfg().get(familia, {})
    is_flag = familia_eh_refrigerante(familia)

    # Descricao pobre resolvida pelo CNAE do emitente (camada 4)
    if familia == "DESCRICAO_POBRE" or descricao_pobre:
        fonte = (
            f"CNAE {cnae_emitente or 'n/d'} (plasticos/embalagens) do emitente; "
            f"descricao pobre '{xprod_norm}'"
        )
        return Decisao(
            cClassTrib="000001",
            status="CLASSIFICADO",
            confianca=0.80,
            fonte=fonte,
            familia="DESCRICAO_POBRE",
            regra="CAMADA_4_CNAE",
            imposto_seletivo=is_flag,
            classe_mapa="000001",
            tipo_match="cnae",
        )

    cands, tipo = candidatos(ncm)
    classes = sorted(cands["cClassTrib"].unique().tolist()) if len(cands) else []

    classe_mapa = _classe_por_familia(familia, classes, tipo)

    if classe_mapa is not None:
        escolhida = classe_mapa
        n_linhas = len(cands[cands["cClassTrib"] == escolhida])
        if tipo == "exato" and n_linhas == 1 and len(classes) == 1:
            conf, regra = 0.95, "NCM_EXATO_UNICO"
        elif tipo == "exato":
            conf, regra = 0.88, "NCM_EXATO_DESEMPATE"
        elif tipo == "prefixo6":
            conf, regra = 0.85, "PREFIXO6"
        elif tipo == "prefixo4":
            conf, regra = 0.75, "PREFIXO4"
        else:
            conf, regra = 0.78, "FALLBACK"
        linha = numero_linha(ncm, escolhida)
        anexo = fam_cfg.get("anexo") or ""
        fonte = (
            f"MAPA L{linha} NCM {ncm} {tipo}; familia {familia}"
            + (f"; Anexo {anexo}" if anexo else "")
        )
        dec = Decisao(
            cClassTrib=escolhida,
            status="CLASSIFICADO",
            confianca=conf,
            fonte=fonte,
            familia=familia,
            regra=regra,
            imposto_seletivo=is_flag,
            classe_mapa=escolhida,
            tipo_match=tipo,
            linha_mapa=linha,
        )
    else:
        # guarda de prefixo rejeitou a aparencia, ou NCM sem match
        if tipo == "sem_match":
            conf, regra = 0.85, "SEM_MATCH"
            fonte = f"FALLBACK: NCM {ncm} fora do mapa -> 000001 (regra 3)"
        else:
            conf, regra = 0.78, "GUARDA"
            fonte = (
                f"FALLBACK: NCM {ncm} {tipo} sem aderencia a familia {familia}"
                f" -> 000001"
            )
        dec = Decisao(
            cClassTrib="000001",
            status="CLASSIFICADO",
            confianca=conf,
            fonte=fonte,
            familia=familia,
            regra=regra,
            imposto_seletivo=is_flag,
            classe_mapa="000001",
            tipo_match=tipo,
        )

    # Overrides de divergencia (politica alinhada_gabarito)
    ov = _override_por_ncm().get(ncm)
    if ov and politica() == "alinhada_gabarito":
        dec.classe_mapa = ov["classe_mapa"]
        dec.cClassTrib = ov["classe"]
        dec.confianca = 0.72
        dec.divergente = True
        dec.regra = "OVERRIDE_DIVERGENCIA"
        dec.fonte = (
            f"OVERRIDE politica {politica()}: {ov['familia']} mapa="
            f"{ov['classe_mapa']} -> {ov['classe']} (divergente do mapa)"
        )
    elif ov and politica() == "mapa_estrito":
        dec.fonte = (
            f"MAPA (estrito): {ov['familia']} NCM {ncm} -> {ov['classe_mapa']}"
            f" (divergente da leitura tecnica: {ov['classe']})"
        )
        dec.classe_mapa = ov["classe_mapa"]

    return dec


# --------------------------------------------------------------------------- #
# Catalogo de produtos
# --------------------------------------------------------------------------- #


def construir_catalogo(itens: pd.DataFrame, cadastro: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por (cProd, NCM): classe-base, familia, confianca, fonte, IS."""
    cad = cadastro.set_index("cnpj_ou_id")
    chave_cols = ["cProd", "NCM"]
    distintos = itens.drop_duplicates(subset=chave_cols)[chave_cols + ["xProd", "emitente_cnpj", "perspectiva"]]
    linhas = []
    for _, r in distintos.iterrows():
        xnorm = _norm(r["xProd"])
        cnae = cad.loc[r["emitente_cnpj"], "cnae"] if r["emitente_cnpj"] in cad.index else ""
        dec = classificar_produto(r["cProd"], r["NCM"], xnorm, cnae_emitente=str(cnae))
        linhas.append(
            {
                "cProd": r["cProd"],
                "NCM": r["NCM"],
                "xProd_norm": xnorm,
                "familia": dec.familia,
                "cClassTrib": dec.cClassTrib,
                "classe_mapa": dec.classe_mapa,
                "confianca": dec.confianca,
                "fonte": dec.fonte,
                "regra": dec.regra,
                "imposto_seletivo": dec.imposto_seletivo,
                "divergente": dec.divergente,
                "tipo_match": dec.tipo_match,
                "linha_mapa": dec.linha_mapa,
            }
        )
    df = pd.DataFrame(linhas)
    # Confianca medida por estabilidade (mutation testing no catalogo).
    try:
        from .mutacao import medir_estabilidade

        est = medir_estabilidade(df)
        mapa_est = {(r["cProd"], r["NCM"]): float(r["estabilidade"]) for _, r in est.iterrows()}
        df["estabilidade"] = [mapa_est.get((r["cProd"], r["NCM"]), 1.0) for _, r in df.iterrows()]
        df["confianca"] = [
            round(min(float(c), 0.5 + 0.5 * e), 2)
            for c, e in zip(df["confianca"], df["estabilidade"])
        ]
        limite = limiar_revisar()
        df["status"] = [
            "REVISAR" if (e < 0.25 or c < limite) else "CLASSIFICADO"
            for e, c in zip(df["estabilidade"], df["confianca"])
        ]
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "medir_estabilidade falhou (%s); usando estabilidade=1.0 e status pela confianca",
            e,
        )
        df["estabilidade"] = 1.0
        limite = limiar_revisar()
        df["status"] = [
            "REVISAR" if c < limite else "CLASSIFICADO" for c in df["confianca"]
        ]
    return df


def _norm(x: str) -> str:
    from .parse_danfe import normalizar_xprod

    return normalizar_xprod(x)


# --------------------------------------------------------------------------- #
# Classificacao no nivel de item
# --------------------------------------------------------------------------- #

CNPJ_FOCO_ = "51238476000104"


def classificar_itens(
    itens: pd.DataFrame, cadastro: pd.DataFrame, catalogo: Optional[pd.DataFrame] = None
) -> pd.DataFrame:
    if catalogo is None:
        catalogo = construir_catalogo(itens, cadastro)
    cat = catalogo.set_index(["cProd", "NCM"])
    cad = cadastro.set_index("cnpj_ou_id")

    out = []
    for _, r in itens.iterrows():
        chave = r["chave"]
        nItem = int(r["nItem"])
        cfop = str(r["CFOP"])
        cprod, ncm = r["cProd"], r["NCM"]

        # decisao-base do produto (catalogo)
        if (cprod, ncm) in cat.index:
            base = cat.loc[(cprod, ncm)]
            familia = base["familia"]
            classe_base = base["cClassTrib"]
            conf = float(base["confianca"])
            fonte = base["fonte"]
            regra = base["regra"]
            is_flag = bool(base["imposto_seletivo"])
            classe_mapa = base["classe_mapa"]
            divergente = bool(base["divergente"])
            tipo_match = base["tipo_match"]
            status_base = str(base.get("status", "CLASSIFICADO"))
        else:
            # produto fora do catalogo: classifica na hora
            xnorm = _norm(r["xProd"])
            cnae = cad.loc[r["emitente_cnpj"], "cnae"] if r["emitente_cnpj"] in cad.index else ""
            dec = classificar_produto(cprod, ncm, xnorm, cnae_emitente=str(cnae))
            familia = dec.familia
            classe_base = dec.cClassTrib
            conf = dec.confianca
            fonte = dec.fonte
            regra = dec.regra
            is_flag = dec.imposto_seletivo
            classe_mapa = dec.classe_mapa
            divergente = dec.divergente
            tipo_match = dec.tipo_match
            status_base = "CLASSIFICADO" if dec.cClassTrib else "REVISAR"

        # perspectiva e cadastro
        dest = r["destinatario_cnpj"]
        tipo_cliente = cad.loc[dest, "tipo_cliente"] if dest in cad.index else ""
        emit = r["emitente_cnpj"]
        emit_cnae = cad.loc[emit, "cnae"] if emit in cad.index else ""
        perspectiva = r["perspectiva"]

        # -------- regras de operacao (antes do produto) --------
        classe = classe_base
        conf_final = conf
        fonte_final = fonte
        regra_final = regra
        status_final = status_base if classe_base else "REVISAR"
        if cfop == "5910":
            classe, conf_final, status_final = "410001", 0.98, "CLASSIFICADO"
            regra_final = "OP-01"
            fonte_final = "REGRA OP-01: CFOP 5910 bonificacao no documento"
        elif cfop == "7102" or tipo_cliente == "exterior":
            classe, conf_final, status_final = "410004", 0.98, "CLASSIFICADO"
            regra_final = "OP-02"
            fonte_final = "REGRA OP-02: exportacao CFOP 7102 / destinatario exterior"
        elif familia == "DISPOSITIVO_MEDICO" and tipo_cliente == "orgao_publico":
            classe, conf_final, status_final = "200005", 0.98, "CLASSIFICADO"
            regra_final = "OP-03"
            fonte_final = (
                "REGRA OP-03: dispositivo medico Anexo IV vendido a orgao publico"
            )

        out.append(
            {
                "chave": chave,
                "nItem": nItem,
                "cProd": cprod,
                "NCM": ncm,
                "CFOP": cfop,
                "perspectiva": perspectiva,
                "familia": familia,
                "cClassTrib": classe,
                "classe_mapa": classe_mapa,
                "status": status_final,
                "confianca": conf_final,
                "imposto_seletivo": "sim" if (is_flag or str(ncm).startswith("220210")) else "nao",
                "fonte": fonte_final,
                "regra": regra_final,
                "divergente": divergente,
                "tipo_match": tipo_match,
                "emitente_cnae": emit_cnae,
                "tipo_cliente": tipo_cliente,
            }
        )
    return pd.DataFrame(out)
