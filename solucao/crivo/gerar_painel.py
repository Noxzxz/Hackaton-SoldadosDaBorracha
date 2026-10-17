"""
Crivo · gerador de dados da plataforma.

Lê a extração das DANFEs (pasta "Extrator Notas Ficais") e as tabelas do case
(pasta "dados"), classifica cada item, calcula a simulação hoje × 2027 × 2033 e
grava o arquivo que a plataforma lê:

    crivo/plataforma/dados/crivo_painel.js   (window.CRIVO = {...})
    crivo/plataforma/dados/crivo_painel.json (mesmo conteúdo, para inspeção)

Ponto de conexão com o motor
----------------------------
Por padrão a classificação é a PROVISÓRIA deste arquivo (regras determinísticas).
Quando o motor do time estiver pronto, rode:

    python crivo/gerar_painel.py --classificacao caminho/itens_classificados.csv

O CSV do motor (separador ';') precisa ter: chave, nItem, cClassTrib, status,
confianca, imposto_seletivo, fonte. Colunas opcionais: peneira, regra.
A simulação é sempre recalculada aqui a partir da classe, com as regras do enunciado.

Uso:
    python crivo/gerar_painel.py                 # classificação provisória
    python crivo/gerar_painel.py --raiz .        # raiz do repositório (padrão: pasta acima de crivo/)
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Parâmetros fixos do case (conferidos com dados/parametros.json na carga)
# ---------------------------------------------------------------------------
FATOR = {  # 1 − redução
    "000001": 1.0, "200003": 0.0, "200014": 0.0, "200005": 0.0,
    "200034": 0.4, "200030": 0.4, "410001": 0.0, "410004": 0.0,
}
NOME_CLASSE = {
    "000001": "Regime padrão",
    "200003": "Cesta Básica Nacional (Anexo I)",
    "200014": "Hortícolas, frutas e ovos (Anexo XV)",
    "200034": "Alimentos do Anexo VII",
    "200030": "Dispositivos médicos (Anexo IV)",
    "200005": "Dispositivos médicos a órgão público",
    "410001": "Bonificação",
    "410004": "Exportação",
}
PENEIRAS = [
    {"id": 1, "nome": "Operação", "pergunta": "O CFOP ou o cliente decidem a classe?",
     "detalhe": "CFOP 5910 → 410001 · CFOP 7102 → 410004 · dispositivo do Anexo IV a órgão público → 200005"},
    {"id": 2, "nome": "Mapa da lei", "pergunta": "O NCM tem linha válida nos anexos da LC 214?",
     "detalhe": "mapa_ncm_cclasstrib: linhas vigentes e PERMITIDO; condição e texto do anexo decidem entre classes"},
    {"id": 3, "nome": "Fornecedor", "pergunta": "Descrição pobre? O CNAE do emitente confirma o que é",
     "detalhe": "cadastro_empresas → cnae. Não cria benefício: confirma o regime padrão"},
    {"id": 4, "nome": "Julgamento", "pergunta": "A regra não decide sozinha: o produto cabe no texto do anexo?",
     "detalhe": "Grupos ambíguos, julgados uma vez por chave de decisão"},
    {"id": 5, "nome": "Fora do mapa", "pergunta": "NCM fora dos anexos → regime padrão",
     "detalhe": "Regra do enunciado: NCM fora do mapa → 000001"},
]
# As DANFEs não destacam PIS/Cofins em itens de bonificação (CFOP 5910) e o enunciado é omisso.
# Com True, o cálculo segue a nota (13 notas passam a bater com o cabeçalho). Confirmar com a organização.
ZERAR_PIS_BONIFICACAO = True

DESCRICOES_POBRES = re.compile(r"^(DIVERSOS|MATERIAL DIVERSO|MATERIAL CONF PED.*|EMBALAGEM PLASTICA)$")


def sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", str(s)) if not unicodedata.combining(c)).upper()


def ler_tabela(pasta: Path, nome: str) -> pd.DataFrame:
    """Lê <nome>.csv (sep ';') ou <nome>.xlsx, sempre como texto."""
    csv, xlsx = pasta / f"{nome}.csv", pasta / f"{nome}.xlsx"
    if csv.exists():
        return pd.read_csv(csv, sep=";", dtype=str, encoding="utf-8-sig").fillna("")
    return pd.read_excel(xlsx, dtype=str).fillna("")


def regra_para_peneira(regra: str, ambiguo: bool = False) -> int:
    """Traduz a `regra` do pipeline do time para a peneira (1 a 5) que o Crivo mostra."""
    regra = str(regra or "")
    if regra.startswith("OP-"):
        return 1
    if regra.startswith("CAMADA_4") or regra == "CNAE":
        return 3
    if regra in ("OVERRIDE_DIVERGENCIA", "GUARDA") or ambiguo:
        return 4
    if regra == "SEM_MATCH":
        return 5
    return 2


def carregar_pipeline(sol: Path):
    """Lê as saídas do pipeline (`rodar_tudo.py`) e devolve itens, notas e a classificação no formato do Crivo."""
    from types import SimpleNamespace
    out = sol / "out"
    faltam = [n for n in ("itens", "notas", "classificados") if not (out / f"{n}.parquet").exists()]
    if faltam:
        raise SystemExit(f"Faltam {', '.join(faltam)}.parquet em {out}. Rode antes: python scripts/rodar_tudo.py")
    it = pd.read_parquet(out / "itens.parquet").astype(str).fillna("")
    nt = pd.read_parquet(out / "notas.parquet")
    cl = pd.read_parquet(out / "classificados.parquet")
    desc = [str(x).replace(str(c), "", 1).strip() or str(x) for x, c in zip(it["xProd"], it["cProd"])]
    itens = pd.DataFrame({
        "chave_acesso": it["chave"], "n_item": it["nItem"], "codigo_produto": it["cProd"],
        "descricao_produto": desc, "ncm": it["NCM"].str.replace(r"\D", "", regex=True).str.zfill(8), "cfop": it["CFOP"],
        "valor_produto": it["vProd"], "valor_icms": it["vICMS"], "quantidade": it["qtd"], "unidade": it["un"],
        "emitente_cnpj": it["emitente_cnpj"], "destinatario_cnpj": it["destinatario_cnpj"], "perspectiva": it["perspectiva"]})
    itens["descricao_base"] = itens["descricao_produto"].str.replace(r"\s*-\s*BONIFICACAO$", "", regex=True)
    notas = pd.DataFrame({
        "chave_acesso": nt["chave"].astype(str), "emitente_cnpj": nt["emitente_cnpj"].astype(str),
        "destinatario_cnpj": nt["destinatario_cnpj"].astype(str),
        "data_emissao": ["20" + c[2:4] + "-" + c[4:6] for c in nt["chave"].astype(str)],
        "perspectiva": nt["perspectiva"].astype(str),
        "valor_pis": nt["v_pis_doc"].astype(str), "valor_cofins": nt["v_cofins_doc"].astype(str),
        "reconciliada": nt["reconciliada"].astype(bool)})
    motor, extra = {}, {}
    for r in cl.itertuples(index=False):
        k = (str(r.chave), str(int(r.nItem)))
        motor[k] = SimpleNamespace(
            cClassTrib=str(r.cClassTrib), status=str(r.status), confianca=str(r.confianca), fonte=str(r.fonte),
            peneira=str(regra_para_peneira(r.regra, bool(r.ambiguo))), regra=str(r.regra),
            imposto_seletivo=str(r.imposto_seletivo))
        extra[k] = {"fam": str(r.familia), "classe_mapa": str(r.classe_mapa), "divergente": bool(r.divergente)}
    return itens, notas, motor, extra


def r2(x: float) -> float:
    """Arredonda para 2 casas, meio para cima (evita o arredondamento bancário do round)."""
    return float(f"{x + (1e-9 if x >= 0 else -1e-9):.2f}")


# ---------------------------------------------------------------------------
# Carga
# ---------------------------------------------------------------------------
def carregar(raiz: Path, dados: Path = None, pipeline: Path = None):
    dados = dados or raiz / "dados"
    extr = raiz / "Extrator Notas Ficais"

    if pipeline:
        itens, notas, _, _ = carregar_pipeline(pipeline)
    else:
        itens = pd.read_csv(extr / "itens.csv", sep=";", dtype=str, encoding="utf-8-sig").fillna("")
        notas = pd.read_csv(extr / "notas.csv", sep=";", dtype=str, encoding="utf-8-sig").fillna("")

    cad = ler_tabela(dados, "cadastro_empresas")
    pis = ler_tabela(dados, "pis_cofins_hoje")
    mapa = ler_tabela(dados, "mapa_ncm_cclasstrib")
    params = json.loads((dados / "parametros.json").read_text(encoding="utf-8"))

    # O Excel remove zeros à esquerda: NCM tem 8 dígitos e cClassTrib tem 6.
    mapa["NCM"] = mapa["NCM"].str.replace(r"\D", "", regex=True).str.zfill(8)
    mapa["cClassTrib"] = mapa["cClassTrib"].str.replace(r"\D", "", regex=True).str.zfill(6)
    pis["NCM"] = pis["NCM"].str.replace(r"\D", "", regex=True).str.zfill(8)
    itens["ncm"] = itens["ncm"].str.replace(r"\D", "", regex=True).str.zfill(8)
    return itens, notas, cad, pis, mapa, params


# ---------------------------------------------------------------------------
# Classificação provisória (substituível pelo CSV do motor)
# ---------------------------------------------------------------------------
def montar_indice_mapa(mapa: pd.DataFrame):
    validas = mapa[(mapa["vigente"].str.lower() == "sim")]
    idx = defaultdict(list)
    for r in validas.itertuples(index=False):
        idx[r.NCM].append({
            "classe": r.cClassTrib, "permissao": r.permissao, "condicao": r.condicao,
            "excecao": r.excecao, "item": r.item_do_anexo, "anexo": r.anexo_lc214,
        })
    return idx


def classificar_produto(desc: str, ncm: str, idx_mapa) -> dict:
    """Classe do PRODUTO, sem olhar a operação. Retorna classe, peneira, confiança, fonte."""
    d = sem_acento(desc)
    linhas = idx_mapa.get(ncm, [])
    permitidas = [l for l in linhas if l["permissao"].upper() == "PERMITIDO"]

    if not linhas:
        if DESCRICOES_POBRES.match(d):
            return dict(classe="000001", peneira=3, conf=0.80, status="CLASSIFICADO",
                        fonte=f"NCM {ncm} fora do mapa; descrição pobre confirmada pelo CNAE do emitente",
                        regra="fora_do_mapa_cnae")
        return dict(classe="000001", peneira=5, conf=0.95, status="CLASSIFICADO",
                    fonte=f"NCM {ncm} fora do mapa → 000001 (regra do enunciado)", regra="fora_do_mapa")

    # Casos em que o texto do anexo cobre só parte do NCM
    if ncm == "19059090":  # o anexo cobre só o pão francês
        if "PAO FRANCES" in d and "BISNAG" not in d:
            return dict(classe="200003", peneira=2, conf=0.90, status="CLASSIFICADO",
                        fonte="Mapa: NCM 19059090 → 200003, item do anexo restrito ao pão francês",
                        regra="mapa_condicao")
        if "BISNAG" in d:
            return dict(classe="000001", peneira=4, conf=0.60, status="REVISAR",
                        fonte="Descrição cita pão francês, mas bisnaguinha não é o pão do anexo (1905.90.90)",
                        regra="julgamento")
        return dict(classe="000001", peneira=2, conf=0.90, status="CLASSIFICADO",
                    fonte="Mapa: NCM 19059090 só tem benefício para pão francês; produto fica no regime padrão",
                    regra="mapa_condicao")

    candidatas = sorted({l["classe"] for l in permitidas if l["classe"] in FATOR and l["classe"] != "200005"})
    # 200030 e 200005 convivem no mesmo NCM: fora da regra de órgão público, vale 200030
    if not candidatas:
        fora = sorted({l["classe"] for l in permitidas})
        return dict(classe="000001", peneira=2, conf=0.85, status="CLASSIFICADO",
                    fonte=f"Mapa lista {', '.join(fora) or 'só linhas VEDADO'} para o NCM {ncm}; "
                          f"nenhuma se aplica a este produto → 000001",
                    regra="mapa_sem_classe_aplicavel")
    if len(candidatas) == 1:
        c = candidatas[0]
        unica = len({l["classe"] for l in permitidas}) == 1
        item = next(l for l in permitidas if l["classe"] == c)
        return dict(classe=c, peneira=2, conf=0.95 if unica else 0.90, status="CLASSIFICADO",
                    fonte=f"Mapa: NCM {ncm} → {c} ({item['condicao'].strip().capitalize() or 'sem condição'})",
                    regra="mapa_linha_unica" if unica else "mapa_condicao")
    return dict(classe=candidatas[0], peneira=4, conf=0.60, status="REVISAR",
                fonte=f"NCM {ncm} admite {', '.join(candidatas)}; julgamento necessário", regra="julgamento")


def aplicar_operacao(base: dict, cfop: str, persp: str, tipo_cliente: str, ncm: str, idx_mapa) -> dict:
    if cfop == "5910":
        return dict(base, classe="410001", peneira=1, conf=0.98, status="CLASSIFICADO",
                    fonte="CFOP 5910: bonificação no próprio documento → 410001 (LC 214, art. 5º)",
                    regra="cfop_bonificacao")
    if cfop.startswith("7"):
        return dict(base, classe="410004", peneira=1, conf=0.98, status="CLASSIFICADO",
                    fonte=f"CFOP {cfop}: exportação → 410004 (LC 214, art. 8º)", regra="cfop_exportacao")
    tem_200005 = any(l["classe"] == "200005" and l["permissao"].upper() == "PERMITIDO"
                     for l in idx_mapa.get(ncm, []))
    if persp == "venda" and tipo_cliente == "orgao_publico" and tem_200005:
        return dict(base, classe="200005", peneira=1, conf=0.98, status="CLASSIFICADO",
                    fonte="Dispositivo do Anexo IV vendido a órgão público → 200005", regra="orgao_publico")
    return base


# ---------------------------------------------------------------------------
# Simulação (regras do enunciado, arredondamento por tributo e por item)
# ---------------------------------------------------------------------------
def simular(vprod: float, vicms: float, classe: str, tributado: bool, exportacao: bool,
            persp: str, revenda: bool, bonificacao: bool = False) -> dict:
    f = FATOR.get(classe, 1.0)
    base_pc = vprod - vicms
    # PIS/Cofins zero: produto não tributado, exportação (enunciado) e bonificação (evidência das DANFEs)
    incide_pc = tributado and not exportacao and not (bonificacao and ZERAR_PIS_BONIFICACAO)
    pis = r2(base_pc * 0.0165) if incide_pc else 0.0
    cof = r2(base_pc * 0.076) if incide_pc else 0.0
    cbs27, ibs27 = r2(vprod * 0.087 * f), r2(vprod * 0.001 * f)
    cbs33, ibs33 = r2(vprod * 0.088 * f), r2(vprod * 0.177 * f)
    s = {
        "pis": pis, "cofins": cof, "icms": vicms,
        "cbs27": cbs27, "ibs27": ibs27, "cbs33": cbs33, "ibs33": ibs33,
        "hoje": r2(vicms + pis + cof), "2027": r2(vicms + cbs27 + ibs27), "2033": r2(cbs33 + ibs33),
    }
    if persp == "compra":
        s["cred_hoje"] = r2((vicms if revenda else 0) + ((pis + cof) if (revenda and tributado) else 0))
        s["cred_2027"] = r2((vicms if revenda else 0) + cbs27 + ibs27)
        s["cred_2033"] = r2(cbs33 + ibs33)
    return s


# ---------------------------------------------------------------------------
# Principal
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raiz", default=None, help="raiz do projeto (com --pipeline: a pasta acima de solucao/)")
    ap.add_argument("--classificacao", help="itens_classificados.csv do motor (sep ';')")
    ap.add_argument("--saida", default=None, help="pasta de saída (padrão: crivo/plataforma/dados)")
    ap.add_argument("--pipeline", nargs="?", const="AUTO", help="pasta solucao/ do pipeline do time (usa out/ e saida/ como fonte de verdade); sem valor, usa a pasta acima de crivo/")
    ap.add_argument("--dados", help="pasta com os xlsx e parametros.json (padrão: <raiz>/dados)")
    a = ap.parse_args()

    aqui = Path(__file__).resolve().parent
    pipe = (aqui.parent if a.pipeline == "AUTO" else Path(a.pipeline).resolve()) if a.pipeline else None
    raiz = Path(a.raiz) if a.raiz else (pipe.parent if pipe else aqui.parent)
    dados = Path(a.dados) if a.dados else (raiz / "pacote-times" / "dados" if pipe else None)
    itens, notas, cad, pis, mapa, params = carregar(raiz, dados, pipe)
    exp_zero = bool(pipe) and bool(params.get("tratamento_exportacao", {}).get("icms_zero", True))
    idx_mapa = montar_indice_mapa(mapa)

    foco = params.get("empresa_foco", {}).get("cnpj", "")
    cnpj_cad = cad.loc[cad["papel"] == "empresa_foco", "cnpj_ou_id"].iloc[0]
    premissas = []
    if foco != cnpj_cad:
        premissas.append({"tema": "CNPJ da Meridional",
                          "decisao": f"Usamos {cnpj_cad} (DANFEs e cadastro); parametros.json traz {foco}",
                          "fonte": "cadastro_empresas, DANFEs"})

    cad_idx = cad.set_index("cnpj_ou_id")
    trib = dict(zip(pis["cProd"], pis["tratamento"]))
    motor, extra = None, {}
    if pipe:
        _, _, motor, extra = carregar_pipeline(pipe)
    elif a.classificacao:
        m = pd.read_csv(a.classificacao, sep=";", dtype=str, encoding="utf-8-sig").fillna("")
        motor = {(r.chave, str(int(r.nItem))): r for r in m.itertuples(index=False)}

    # ---- itens -----------------------------------------------------------------
    cache_prod = {}
    linhas = []
    for r in itens.itertuples(index=False):
        persp = r.perspectiva
        contraparte = r.destinatario_cnpj if persp == "venda" else r.emitente_cnpj
        cp = cad_idx.loc[contraparte] if contraparte in cad_idx.index else None
        tipo_cliente = (cp["tipo_cliente"] if cp is not None else "") or ("exterior" if r.cfop.startswith("7") else "")
        finalidade = (cp["finalidade_compra"] if (cp is not None and persp == "compra") else "")

        if motor is not None:
            mm = motor.get((r.chave_acesso, str(int(r.n_item))))
            if mm is None:
                raise SystemExit(f"Item sem classificação no CSV do motor: {r.chave_acesso} #{r.n_item}")
            cl = dict(classe=mm.cClassTrib.zfill(6), status=mm.status, conf=float(mm.confianca.replace(",", ".")),
                      fonte=mm.fonte, peneira=int(getattr(mm, "peneira", "") or 0) or None,
                      regra=getattr(mm, "regra", "") or "motor", is_sel=(mm.imposto_seletivo == "sim"))
        else:
            chave_prod = (r.descricao_produto, r.ncm)
            if chave_prod not in cache_prod:  # deduplicação: uma decisão por produto
                cache_prod[chave_prod] = classificar_produto(r.descricao_produto, r.ncm, idx_mapa)
            cl = aplicar_operacao(dict(cache_prod[chave_prod]), r.cfop, persp, tipo_cliente, r.ncm, idx_mapa)
            d = sem_acento(r.descricao_produto)
            cl["is_sel"] = r.ncm.startswith("2202") and ("REFRI" in d)

        vprod, vicms_doc = float(r.valor_produto), float(r.valor_icms)
        vicms = 0.0 if (exp_zero and r.cfop.startswith("7")) else vicms_doc  # premissa do enunciado: ICMS de exportação = 0
        if pipe:
            ex = extra[(r.chave_acesso, str(int(r.n_item)))]
            cl.update(fam=ex["fam"], classe_mapa=ex["classe_mapa"], divergente=ex["divergente"])
        tributado = trib.get(r.codigo_produto, "") == "tributado"
        sim = simular(vprod, vicms, cl["classe"], tributado, r.cfop.startswith("7"), persp, finalidade == "revenda",
                      bonificacao=(r.cfop == "5910"))
        linhas.append(dict(r=r, vicms_doc=vicms_doc, persp=persp, contraparte=contraparte, tipo_cliente=tipo_cliente,
                           finalidade=finalidade, cl=cl, sim=sim, tributado=tributado, vprod=vprod, vicms=vicms))

    # ---- resumo por cenário ----------------------------------------------------
    def soma(f, cond):
        return r2(sum(f(x) for x in linhas if cond(x)))

    vendas = lambda x: x["persp"] == "venda"
    compras = lambda x: x["persp"] == "compra"
    resumo = []
    for c in ("hoje", "2027", "2033"):
        deb = soma(lambda x: x["sim"][c], vendas)
        cre = soma(lambda x: x["sim"][f"cred_{c}"], compras)
        resumo.append({"cenario": c, "debitos": deb, "creditos": cre, "liquido": r2(deb - cre)})
    for x in resumo:
        x["variacao"] = r2(x["liquido"] - resumo[0]["liquido"])

    # Ponte hoje → cenário, por tributo (soma exata das parcelas)
    def ponte(c):
        V, C = vendas, compras
        icms_v = soma(lambda x: x["sim"]["icms"], V)
        pc_v = soma(lambda x: x["sim"]["pis"] + x["sim"]["cofins"], V)
        novo_v = soma(lambda x: x["sim"][f"cbs{c[2:]}"] + x["sim"][f"ibs{c[2:]}"], V)
        cred_icms = soma(lambda x: x["sim"]["icms"] if x["finalidade"] == "revenda" else 0, C)
        cred_pc = soma(lambda x: (x["sim"]["pis"] + x["sim"]["cofins"]) if (x["finalidade"] == "revenda" and x["tributado"]) else 0, C)
        cred_novo = soma(lambda x: x["sim"][f"cbs{c[2:]}"] + x["sim"][f"ibs{c[2:]}"], C)
        passos = [{"rotulo": "PIS/Cofins nas vendas deixa de existir", "valor": -pc_v}]
        if c == "2033":
            passos.append({"rotulo": "ICMS nas vendas deixa de existir", "valor": -icms_v})
        passos.append({"rotulo": "CBS/IBS nas vendas", "valor": novo_v})
        passos.append({"rotulo": "Perde o crédito de PIS/Cofins", "valor": cred_pc})
        if c == "2033":
            passos.append({"rotulo": "Perde o crédito de ICMS", "valor": cred_icms})
        passos.append({"rotulo": "Ganha o crédito de CBS/IBS", "valor": -cred_novo})
        return [{"rotulo": p["rotulo"], "valor": r2(p["valor"])} for p in passos]

    pontes = {"2027": ponte("2027"), "2033": ponte("2033")}

    # Agregados para sensibilidade da alíquota e transição ano a ano (sem arredondamento por item)
    agg = {
        "icms_vendas": soma(lambda x: x["vicms"], vendas),
        "base_reduzida_vendas": soma(lambda x: x["vprod"] * FATOR.get(x["cl"]["classe"], 1), vendas),
        "icms_compras_revenda": soma(lambda x: x["vicms"] if x["finalidade"] == "revenda" else 0, compras),
        "base_reduzida_compras": soma(lambda x: x["vprod"] * FATOR.get(x["cl"]["classe"], 1), compras),
    }

    # ---- produtos ----------------------------------------------------------------
    prod = defaultdict(lambda: {"itens": 0, "v_venda": 0.0, "v_compra": 0.0,
                                "imp_v": {"hoje": 0.0, "2027": 0.0, "2033": 0.0},
                                "cred_c": {"hoje": 0.0, "2027": 0.0, "2033": 0.0},
                                "classes": defaultdict(int)})
    for x in linhas:
        p = prod[x["r"].codigo_produto]
        p["itens"] += 1
        p["desc"] = x["r"].descricao_base or x["r"].descricao_produto
        p["ncm"] = x["r"].ncm
        p["classes"][x["cl"]["classe"]] += 1
        if x["persp"] == "venda":
            p["v_venda"] += x["vprod"]
            for c in ("hoje", "2027", "2033"):
                p["imp_v"][c] += x["sim"][c]
        else:
            p["v_compra"] += x["vprod"]
            for c in ("hoje", "2027", "2033"):
                p["cred_c"][c] += x["sim"][f"cred_{c}"]
    produtos = []
    for cprod, p in prod.items():
        classe_principal = max(p["classes"].items(), key=lambda kv: kv[1])[0]
        ef = {c: (r2(100 * p["imp_v"][c] / p["v_venda"]) if p["v_venda"] else None) for c in ("hoje", "2027", "2033")}
        impacto = {c: r2((p["imp_v"][c] - p["imp_v"]["hoje"]) - (p["cred_c"][c] - p["cred_c"]["hoje"]))
                   for c in ("2027", "2033")}
        produtos.append({
            "cProd": cprod, "desc": p["desc"], "ncm": p["ncm"], "classe": classe_principal,
            "classes": dict(p["classes"]), "itens": p["itens"], "tributado": trib.get(cprod, ""),
            "valor_vendas": r2(p["v_venda"]), "valor_compras": r2(p["v_compra"]),
            "aliquota_efetiva": ef,
            "debito": {c: r2(v) for c, v in p["imp_v"].items()},
            "credito": {c: r2(v) for c, v in p["cred_c"].items()},
            "impacto_liquido": impacto,
        })
    produtos.sort(key=lambda p: p["impacto_liquido"]["2033"])

    # ---- motor -------------------------------------------------------------------
    funil = []
    for pen in PENEIRAS:
        sel = [x for x in linhas if x["cl"].get("peneira") == pen["id"]]
        funil.append({**pen, "itens": len(sel),
                      "produtos": len({x["r"].codigo_produto for x in sel})})
    conf_hist = defaultdict(int)
    for x in linhas:
        conf_hist[f"{x['cl']['conf']:.2f}"] += 1
    fila = [x for x in linhas if x["cl"]["status"] == "REVISAR"]

    # ---- conferências automáticas -----------------------------------------------------
    conferencias = []
    # 1) PIS/Cofins calculado por item × total do cabeçalho da DANFE
    pc_nota = defaultdict(lambda: [0.0, 0.0, False])
    for x in linhas:
        k = x["r"].chave_acesso
        pc_nota[k][0] += x["sim"]["pis"]
        pc_nota[k][1] += x["sim"]["cofins"]
        pc_nota[k][2] |= x["r"].cfop.startswith("7")
    ok = exp = outros = 0
    for n in notas.itertuples(index=False):
        p, c, e = pc_nota[n.chave_acesso]
        bate = abs(p - float(n.valor_pis or 0)) <= 0.05 and abs(c - float(n.valor_cofins or 0)) <= 0.05
        if bate:
            ok += 1
        elif e:
            exp += 1
        else:
            outros += 1
    conferencias.append({"nome": "PIS/Cofins por nota × cabeçalho da DANFE",
                         "resultado": f"{ok} de {len(notas)} notas batem",
                         "detalhe": f"{exp} divergências em exportação (regra do enunciado zera o PIS/Cofins); "
                                    f"{outros} divergências em outras notas",
                         "ok": outros == 0})
    # 2) Extração reconciliada com os totais da nota (relatório do extrator)
    q = raiz / "Extrator Notas Ficais" / "qualidade_extracao.csv"
    if q.exists():
        qe = pd.read_csv(q, sep=";", dtype=str, encoding="utf-8-sig").fillna("")
        rec = int((qe["status_reconciliacao"] == "OK").sum())
        conferencias.append({"nome": "Extração × totais da DANFE (valor, base e ICMS)",
                             "resultado": f"{rec} de {len(qe)} notas reconciliadas",
                             "detalhe": "Tolerância de R$ 0,05 por nota (qualidade_extracao.csv)", "ok": rec == len(qe)})
    # 3) Itens do template oficial de entrega
    t = raiz / "templates-entrega" / "simulacao.json"
    if t.exists():
        tpl = json.loads(t.read_text(encoding="utf-8"))
        by = {(x["r"].chave_acesso, int(x["r"].n_item)): x for x in linhas}
        acertos, total = 0, 0
        for it in tpl.get("itens", []):
            x = by.get((it["chave"], int(it["nItem"])))
            if x is None:
                continue
            total += 1
            bate = x["cl"]["classe"] == it["cClassTrib"]
            for c in ("hoje", "2027", "2033"):
                bate &= abs(x["sim"][c] - it[c]["imposto"]) <= 0.05
                cr = x["sim"].get(f"cred_{c}")
                esp = it[c]["credito"]
                bate &= (cr is None and esp is None) or (cr is not None and esp is not None and abs(cr - esp) <= 0.05)
            acertos += bate
        conferencias.append({"nome": "Itens do template oficial (templates-entrega/simulacao.json)",
                             "resultado": f"{acertos} de {total} itens idênticos",
                             "detalhe": "Classe, imposto e crédito nos três cenários, tolerância de R$ 0,05",
                             "ok": acertos == total})

    # 4) Pipeline do time: reconciliação das notas e paridade item a item com saida/simulacao.json
    pipe_extra = {}
    if pipe:
        rec = int(notas["reconciliada"].sum())
        conferencias.append({"nome": "Extração × totais da DANFE (pipeline do time)", "resultado": f"{rec} de {len(notas)} notas reconciliadas",
                             "detalhe": "Gate de reconciliação do pipeline: valor, base e ICMS por nota", "ok": rec == len(notas)})
        sj = pipe / "saida" / "simulacao.json"
        if sj.exists():
            ref = json.loads(sj.read_text(encoding="utf-8"))
            by = {(x["r"].chave_acesso, int(x["r"].n_item)): x for x in linhas}
            comp = bate_n = 0
            piores = []
            for it in ref.get("itens", []):
                x = by.get((it["chave"], int(it["nItem"])))
                if x is None:
                    continue
                comp += 1
                dmax = 0.0
                ok_cl = x["cl"]["classe"] == it["cClassTrib"]
                for c in ("hoje", "2027", "2033"):
                    dmax = max(dmax, abs(x["sim"][c] - it[c]["imposto"]))
                    cr, esp = x["sim"].get(f"cred_{c}"), it[c].get("credito")
                    if (cr is None) != (esp is None):
                        dmax = max(dmax, 1e9)
                    elif cr is not None:
                        dmax = max(dmax, abs(cr - esp))
                if ok_cl and dmax <= 0.005:
                    bate_n += 1
                else:
                    piores.append((dmax, it["chave"][-8:], it["nItem"]))
            piores.sort(reverse=True)
            conferencias.append({"nome": "Simulação do Crivo × saida/simulacao.json do pipeline",
                                 "resultado": f"{bate_n} de {comp} itens idênticos (classe, imposto e crédito nos três cenários)",
                                 "detalhe": "Tolerância de R$ 0,005 por valor. " + ("Sem divergências." if not piores else "Maiores desvios: " + "; ".join(f"…{c} #{n}: {d:,.2f}" for d, c, n in piores[:3])),
                                 "ok": comp > 0 and bate_n == comp})
            rr = {r["cenario"]: r for r in ref.get("resumo", [])}
            if rr:
                dif = max(abs(rr[c["cenario"]]["imposto_liquido"] - c["liquido"]) for c in resumo if c["cenario"] in rr)
                conferencias.append({"nome": "Imposto líquido do painel × resumo do pipeline", "resultado": f"diferença máxima de R$ {dif:,.2f}",
                                     "detalhe": "Só se compara quando o painel e o pipeline têm o mesmo conjunto de itens",
                                     "ok": dif <= 0.05 or len(ref.get("itens", [])) != len(linhas)})
        for nome, fn in (("equilibrio", "equilibrio.parquet"), ("transicao", "transicao_2029_2032.parquet")):
            f = pipe / "out" / fn
            if f.exists():
                df = pd.read_parquet(f).astype(str)
                pipe_extra[nome] = df.to_dict(orient="records")

    # ---- serialização compacta ------------------------------------------------------
    notas_idx = {ch: i for i, ch in enumerate(sorted(itens["chave_acesso"].unique()))}
    nota_info = notas.set_index("chave_acesso")
    notas_out = []
    for ch in sorted(notas_idx, key=notas_idx.get):
        n = nota_info.loc[ch]
        notas_out.append([ch, n["emitente_cnpj"], n["destinatario_cnpj"], n["data_emissao"], n["perspectiva"],
                          float(n["valor_pis"] or 0), float(n["valor_cofins"] or 0)])
    COLS = ["nota", "nItem", "cProd", "desc", "ncm", "cfop", "vProd", "vICMS", "persp", "contraparte",
            "classe", "status", "conf", "peneira", "regra", "fonte", "is_sel",
            "pis", "cofins", "cbs27", "ibs27", "cbs33", "ibs33", "hoje", "2027", "2033",
            "cred_hoje", "cred_2027", "cred_2033", "quant", "un", "fin", "trib", "vICMS_doc", "classe_mapa", "fam", "tfam"]
    tribunal = json.loads((pipe / "out" / "tribunal.json").read_text(encoding="utf-8")) if pipe and (pipe / "out" / "tribunal.json").exists() else None
    tfams = {f["familia"] for f in (tribunal or {}).get("familias", [])}
    itens_out = []
    for x in linhas:
        r, cl, s = x["r"], x["cl"], x["sim"]
        itens_out.append([notas_idx[r.chave_acesso], int(r.n_item), r.codigo_produto, r.descricao_produto, r.ncm,
                          r.cfop, x["vprod"], x["vicms"], 1 if x["persp"] == "venda" else 0, x["contraparte"],
                          cl["classe"], cl["status"], cl["conf"], cl.get("peneira"), cl.get("regra"), cl["fonte"],
                          1 if cl.get("is_sel") else 0,
                          s["pis"], s["cofins"], s["cbs27"], s["ibs27"], s["cbs33"], s["ibs33"],
                          s["hoje"], s["2027"], s["2033"],
                          s.get("cred_hoje"), s.get("cred_2027"), s.get("cred_2033"),
                          float(r.quantidade or 0), r.unidade, x["finalidade"], 1 if x["tributado"] else 0,
                          x["vicms_doc"], cl.get("classe_mapa", ""), cl.get("fam", ""),
                          cl["fam"] if (cl.get("divergente") and cl["fam"] in tfams) else ""])

    ncms_usados = {x["r"].ncm for x in linhas}
    mapa_out = {n: idx_mapa[n] for n in sorted(ncms_usados) if n in idx_mapa}
    empresas = {row["cnpj_ou_id"]: {k: row[k] for k in ("papel", "razao_social", "cnae", "cnae_descricao",
                                                         "tipo_cliente", "finalidade_compra")}
                for _, row in cad.iterrows()}

    premissas += [
        {"tema": "Exportação (CFOP 7102)", "decisao": "PIS/Cofins = 0, como manda o enunciado, mesmo com valor destacado na DANFE",
         "fonte": "enunciado, seção 3"},
        {"tema": "PIS/Cofins na bonificação (CFOP 5910)",
         "decisao": "Zero, como nas DANFEs; o enunciado não trata o caso" if ZERAR_PIS_BONIFICACAO
         else "Cobrado pela regra geral; as DANFEs mostram zero", "fonte": "13 DANFEs com bonificação de produto tributado"},
        {"tema": "ICMS na exportação", "decisao": ("Zero, como no pipeline do time: o enunciado trata o ICMS destacado nas DANFEs de exportação como erro de geração (o avaliador aceita as duas leituras)" if exp_zero
         else "Mantido como destacado na DANFE (hoje e 2027)"), "fonte": "enunciado, ressalvas; parametros.json → tratamento_exportacao"},
        {"tema": "NCM fora do mapa", "decisao": "Classe 000001, sem busca por posição de NCM", "fonte": "enunciado, seção 4"},
        {"tema": "Alíquotas 2027 e 2033", "decisao": "CBS 8,7% + IBS 0,1% (2027); CBS 8,8% + IBS 17,7% (2033)",
         "fonte": "parametros.json (premissas)"},
        {"tema": "Transição 2029–2032", "decisao": "ICMS × fração do ano; IBS = 17,7% × (1 − fração); CBS 8,8%. Sem arredondamento por item",
         "fonte": "parametros.json → transicao_icms_bonus"},
        {"tema": "Classificação", "decisao": "PROVISÓRIA (regras deste gerador) até o motor entregar itens_classificados.csv"
         if motor is None else ("Saída do pipeline do time (solucao/out), lida sem recalcular a classe" if pipe else "Saída do motor do time"),
         "fonte": "crivo/gerar_painel.py"},
    ]

    out = {
        "meta": {"gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "classificacao": "provisoria" if motor is None else "motor", "origem": "pipeline" if pipe else ("csv" if motor is not None else "gerador"),
                 "politica_tribunal": (tribunal or {}).get("politica_ativa"),
                 "n_notas": len(notas_out), "n_itens": len(itens_out), "n_produtos": len(produtos),
                 "empresa_foco": cnpj_cad,
                 "decisoes_unicas": len(cache_prod) if motor is None else None,
                 "tokens_ia": 0 if motor is None else None},
        "resumo": resumo, "pontes": pontes, "agregados": agg,
        "transicao": params.get("transicao_icms_bonus", {}),
        "produtos": produtos,
        "motor": {"peneiras": funil, "confianca": dict(sorted(conf_hist.items())), "fila_revisao": len(fila)},
        "classes": NOME_CLASSE, "fatores": FATOR,
        "notas": notas_out, "colunas_item": COLS, "itens": itens_out,
        "mapa": mapa_out, "empresas": empresas, "premissas": premissas,
        "conferencias": conferencias,
        "tribunal": tribunal, "pipeline": pipe_extra,
    }

    saida = Path(a.saida) if a.saida else Path(__file__).resolve().parent / "plataforma" / "dados"
    saida.mkdir(parents=True, exist_ok=True)
    js = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    (saida / "crivo_painel.json").write_text(js, encoding="utf-8")
    (saida / "crivo_painel.js").write_text("window.CRIVO=" + js + ";\n", encoding="utf-8")

    print(f"{len(itens_out)} itens · {len(produtos)} produtos · {len(notas_out)} notas")
    for x in resumo:
        print(f"  {x['cenario']:>5}: débitos {x['debitos']:>16,.2f}  créditos {x['creditos']:>16,.2f}  líquido {x['liquido']:>16,.2f}")
    print(f"  fila de revisão: {len(fila)} itens · decisões únicas: {out['meta']['decisoes_unicas']}")
    print(f"  gravado em {saida}")


if __name__ == "__main__":
    main()
