"""Painel Streamlit - Atacadista Meridional x Reforma Tributaria.

Telas:
  1. Veredito (nivel 2): debitos, creditos, liquido e variacao por cenario.
  2. Onde: decomposicao por familia/categoria, produto e fornecedor.
  3. Drill-down: todo numero leva a arvore de prova (item -> campo -> mapa -> premissa).
  4. Tribunal: as 7 familias divergentes e o custo de cada leitura.
  5. Qualidade: reconciliacao, confianca, Imposto Seletivo.
  6. Simulador "e se?": aliquota de referencia e repasse de preco ao vivo.

Rodar:  streamlit run app/painel.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.caminhos import OUT_DIR  # noqa: E402
from src.io_dados import cadastro as carregar_cadastro  # noqa: E402

CENARIOS = ["hoje", "2027", "2033"]


# --------------------------------------------------------------------------- #
# Dados
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner=False)
def carregar():
    dados = {}
    p = OUT_DIR / "itens_simulados.parquet"
    if not p.exists():
        st.error("Rode `python scripts/rodar_tudo.py` antes de abrir o painel.")
        st.stop()
    dados["itens"] = pd.read_parquet(p)
    dados["catalogo"] = pd.read_parquet(OUT_DIR / "catalogo.parquet")
    if (OUT_DIR / "trilha.parquet").exists():
        dados["trilha"] = pd.read_parquet(OUT_DIR / "trilha.parquet")
    if (OUT_DIR / "tribunal.json").exists():
        dados["tribunal"] = json.loads((OUT_DIR / "tribunal.json").read_text(encoding="utf-8"))
    if (OUT_DIR / "equilibrio.parquet").exists():
        dados["equilibrio"] = pd.read_parquet(OUT_DIR / "equilibrio.parquet")
    dados["notas"] = pd.read_parquet(OUT_DIR / "notas.parquet")
    dados["cadastro"] = carregar_cadastro()
    return dados


def resumo(itens: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for c in CENARIOS:
        deb = itens.loc[itens["perspectiva"] == "venda", f"imposto_{c}"].sum()
        cred = itens.loc[itens["perspectiva"] == "compra", f"credito_{c}"].fillna(0).sum()
        rows.append({"cenario": c, "debitos_vendas": deb, "creditos_compras": cred,
                     "imposto_liquido": deb - cred})
    df = pd.DataFrame(rows)
    base = df.loc[df["cenario"] == "hoje", "imposto_liquido"].iloc[0]
    df["variacao_vs_hoje"] = df["imposto_liquido"] - base
    return df


def brl(x: float) -> str:
    return f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# --------------------------------------------------------------------------- #
# Layout
# --------------------------------------------------------------------------- #
st.set_page_config(page_title="Meridional x Reforma Tributaria", layout="wide")
dados = carregar()
itens = dados["itens"]
res = resumo(itens)

st.title("Atacadista Meridional - Simulador da Reforma Tributaria")
st.caption(
    "Cada numero tem origem: campo da DANFE, linha do mapa oficial, regra de operacao, "
    "artigo/anexo da LC 214 ou premissa do parametros.yaml."
)

notas = dados["notas"]
n_ok = int(notas["reconciliada"].astype(bool).sum())
c1, c2, c3, c4 = st.columns(4)
c1.metric("Notas reconciliadas", f"{n_ok}/{len(notas)}")
c2.metric("Itens classificados", f"{len(itens):,}".replace(",", "."))
c3.metric("Imposto Seletivo (itens)", int((itens["imposto_seletivo"] == "sim").sum()))
conf_min = itens["confianca"].min()
c4.metric("Confianca minima", f"{conf_min:.2f}")

aba = st.tabs(["Veredito", "Onde ganha/perde", "Drill-down", "Tribunal", "Qualidade", "Simulador e se?"])

# ---------------- Veredito ----------------
with aba[0]:
    st.subheader("Nivel 2 - imposto liquido da empresa (debitos - creditos)")
    show = res.copy()
    show["debitos_vendas"] = show["debitos_vendas"].map(brl)
    show["creditos_compras"] = show["creditos_compras"].map(brl)
    show["imposto_liquido"] = show["imposto_liquido"].map(brl)
    show["variacao_vs_hoje"] = show["variacao_vs_hoje"].map(brl)
    st.dataframe(show, width="stretch", hide_index=True)

    var_2033 = res.loc[res["cenario"] == "2033", "variacao_vs_hoje"].iloc[0]
    verbo = "ganha" if var_2033 < 0 else "perde"
    st.info(
        f"Leitura: com o credito amplo de IBS/CBS nas compras, a Meridional **{verbo}** "
        f"{brl(abs(var_2033))} em 2033 frente a hoje (imposto liquido negativo = credito acumulado)."
    )
    st.caption(
        "Premissas: aliquotas de 2027 e 2033 sao estimativas (nao oficiais), "
        "conforme `config/parametros.yaml`."
    )

    # P15: escala legivel (R$ milhoes) em vez de valores absolutos no eixo.
    chart = res.set_index("cenario")[
        ["debitos_vendas", "creditos_compras", "imposto_liquido"]
    ] / 1_000_000
    st.bar_chart(chart)
    st.caption("Valores em R$ milhoes.")

    # P18: projecao da carga tributaria entre os pontos conhecidos.
    st.subheader("Evolucao da carga tributaria (projecao)")
    hoje = float(res.loc[res["cenario"] == "hoje", "imposto_liquido"].iloc[0])
    v27 = float(res.loc[res["cenario"] == "2027", "imposto_liquido"].iloc[0])
    v33 = float(res.loc[res["cenario"] == "2033", "imposto_liquido"].iloc[0])
    anos = [2026, 2027, 2028, 2029, 2030, 2031, 2032, 2033]
    valores = [
        hoje + (v27 - hoje) * (ano - 2026) if ano <= 2027
        else v27 + (v33 - v27) * ((ano - 2027) / 6)
        for ano in anos
    ]
    serie = pd.DataFrame(
        {"ano": anos, "imposto_liquido_milhoes": [v / 1_000_000 for v in valores]}
    )
    st.line_chart(serie.set_index("ano"))
    st.caption("Interpolacao linear entre hoje, 2027 e 2033 - projecao ilustrativa.")

# ---------------- Onde ----------------
with aba[1]:
    st.subheader("Decomposicao")
    dim = st.radio("Dimensao", ["familia", "cClassTrib", "cProd", "fornecedor"], horizontal=True)
    det = itens.copy()
    if dim == "fornecedor":
        mapa_nome = dados["cadastro"].set_index("cnpj_ou_id")["razao_social"].to_dict()
        det["chave_dim"] = det["emitente_cnpj"].map(mapa_nome).fillna(det["emitente_cnpj"])
    else:
        det["chave_dim"] = det[dim]
    # P14: separa debito (venda) de imposto incidente (compra) e credito.
    vendas = det[det["perspectiva"] == "venda"]
    compras = det[det["perspectiva"] == "compra"]
    agg_vendas = vendas.groupby("chave_dim").agg(
        itens_venda=("nItem", "count"),
        debito_2033=("imposto_2033", "sum"),
        vProd_venda=("vProd", "sum"),
    )
    agg_compras = compras.groupby("chave_dim").agg(
        itens_compra=("nItem", "count"),
        imposto_compras_2033=("imposto_2033", "sum"),
        credito_2027=("credito_2027", "sum"),
    )
    agg = agg_vendas.join(agg_compras, how="outer").fillna(0)
    agg = agg.sort_values("debito_2033", ascending=False)
    st.dataframe(agg.head(40), width="stretch")
    st.caption(
        "`debito_2033` = imposto das vendas; `imposto_compras_2033` = imposto "
        "incidente nas compras (nao e debito da empresa); `credito_2027` = credito "
        "de IBS/CBS nas compras."
    )

# ---------------- Drill-down ----------------
with aba[2]:
    st.subheader("Arvore de prova: item -> campo da DANFE -> mapa -> premissa")
    vendas = itens[itens["perspectiva"] == "venda"].reset_index(drop=True)
    vendas = vendas.assign(rotulo=vendas["chave"].str[:12] + " #" + vendas["nItem"].astype(str))
    # P17: busca por chave/nItem em vez de limitar a 300 itens.
    busca = st.text_input("Filtrar por chave (prefixo) ou nItem", "")
    base = vendas
    if busca.strip():
        termo = busca.strip()
        base = vendas[
            vendas["chave"].str.contains(termo, case=False, na=False)
            | vendas["nItem"].astype(str).eq(termo)
        ]
    if base.empty:
        st.warning("Nenhum item de venda encontrado para o filtro.")
        st.stop()
    rotulo = st.selectbox("Escolha um item de venda", base["rotulo"])
    sel = base[base["rotulo"] == rotulo].iloc[0]
    st.write(
        f"**{sel['xProd']}**  ·  NCM {sel['NCM']}  ·  CFOP {sel['CFOP']}  ·  "
        f"classe **{sel['cClassTrib']}** ({sel['familia']})"
    )
    st.markdown(f"**Fonte da classificacao:** {sel['fonte']}")
    if "trilha" in dados:
        t = dados["trilha"]
        sub = t[(t["chave"] == sel["chave"]) & (t["nItem"] == int(sel["nItem"]))]
        st.dataframe(sub[["grandeza", "valor", "formula", "fonte_tipo", "fonte_ref"]],
                     width="stretch", hide_index=True)

# ---------------- Tribunal ----------------
with aba[3]:
    st.subheader("Tribunal de premissas - familias divergentes mapa x anexos")
    trib = dados.get("tribunal")
    if not trib:
        st.warning("tribunal.json nao encontrado.")
    else:
        st.markdown(
            f"Politica ativa: **{trib['politica_ativa']}** · itens em NCMs divergentes: "
            f"**{trib['itens_afetados']}**"
        )
        custo = pd.DataFrame(trib["custo_por_leitura"])
        st.dataframe(custo, width="stretch")
        st.caption(
            "Leitura A = mapa estrito (segue o mapa oficial). "
            "Leitura B = leitura tecnica dos Anexos I/VII (politica ativa). "
            "A diferenca em 2033 e o custo em R$ de decidir errado."
        )
        st.dataframe(pd.DataFrame(trib["familias"]), width="stretch", hide_index=True)

# ---------------- Qualidade ----------------
with aba[4]:
    st.subheader("Qualidade da extracao e calibracao")
    pct_ok = 100.0 * n_ok / len(notas)
    st.progress(min(1.0, pct_ok / 100.0), text=f"{pct_ok:.1f}% das notas reconciliadas (vProd, vICMS, PIS, COFINS)")
    st.write("Distribuicao de confianca:")
    st.bar_chart(itens["confianca"].value_counts().sort_index())
    st.write("Distribuicao de classes:")
    st.bar_chart(itens["cClassTrib"].value_counts())
    st.write("Itens com Imposto Seletivo:", int((itens["imposto_seletivo"] == "sim").sum()))

# ---------------- Simulador ----------------
with aba[5]:
    st.subheader("Simulador 'e se?' - recálculo ao vivo")
    aliq = st.slider("Aliquota de referencia total (CBS + IBS), %", 24.0, 28.0, 26.5, 0.1)
    repasse = st.slider("Repasse da variacao ao preco de venda, %", 0, 100, 0, 5)
    st.caption(
        "O recálculo escala CBS e IBS pela razao entre a aliquota escolhida e a de referencia "
        "(26,5%) e aplica o repasse sobre o preco de venda de 2033."
    )
    fator = aliq / 26.5
    det = itens.copy()
    for c in ("2027", "2033"):
        det[f"imposto_{c}"] = det[f"imposto_{c}"] * fator
        # P16: escala os creditos na mesma proporcao para manter a coerencia.
        if f"credito_{c}" in det.columns:
            det[f"credito_{c}"] = det[f"credito_{c}"].astype(float) * fator
    det["vProd_repasse"] = det["vProd"] * (1 + (repasse / 100.0) * (fator - 1))
    deb = det.loc[det["perspectiva"] == "venda", "imposto_2033"].sum()
    cred = det.loc[det["perspectiva"] == "compra", "credito_2033"].fillna(0).sum()
    st.metric("Imposto liquido 2033 (simulado)", brl(deb - cred))
    st.metric("Debitos (vendas) 2033", brl(deb))
    st.metric("Creditos (compras) 2033", brl(cred))

    eq = dados.get("equilibrio")
    if eq is not None and len(eq):
        st.subheader("Produtos que mais precisam subir preco")
        cols = [c for c in ["cProd", "preco_hoje", "preco_equilibrio_2033", "variacao_pct_2033"] if c in eq.columns]
        st.dataframe(eq[cols].head(15), width="stretch", hide_index=True)

st.caption("Documento sintetico para hackathon - sem valor fiscal. Fonte: LC 214/2025 (tabelas oficiais) + premissas do case.")
