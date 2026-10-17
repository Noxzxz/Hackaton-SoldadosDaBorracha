"""Testes de regressao e dos exemplos verificados do enunciado."""
from __future__ import annotations

from decimal import Decimal

import pandas as pd

from src.classificar import construir_catalogo, classificar_itens
from src.extrair import extrair_tudo
from src.io_dados import cadastro as carregar_cadastro
from src.simular import ibs_cbs, pis_cofins_hoje, r2, simular_dataframe, simular_item

D = Decimal


def test_round_half_up():
    assert r2(D("32.775")) == D("32.78")
    assert r2(D("32.774")) == D("32.77")
    assert r2(D("0.335")) == D("0.34")


def test_exemplo_enunciado_100_reais():
    """R$ 100,00, classe 200034, 2033 -> 10,60."""
    cbs, ibs = ibs_cbs(D("100.00"), "200034", "2033")
    assert cbs + ibs == D("10.60")


def test_golden_pft500():
    s = simular_item(D("1677.50"), D("301.95"), "200034", "5102", "compra", "revenda", "tributado")
    assert s["hoje"]["imposto"] == D("429.19")
    assert s["2027"]["imposto"] == D("361.00")
    assert s["2027"]["credito"] == D("361.00")
    assert s["2033"]["imposto"] == D("177.82")


def test_golden_bisch():
    s = simular_item(D("176.70"), D("31.81"), "000001", "5102", "venda", "", "tributado")
    assert s["hoje"]["imposto"] == D("45.21")
    assert s["2027"]["imposto"] == D("47.36")
    assert s["2033"]["imposto"] == D("46.83")
    assert s["hoje"]["credito"] is None


def test_golden_div001():
    s = simular_item(D("303690.00"), D("54664.20"), "000001", "5102", "compra", "uso_consumo", "tributado")
    assert s["hoje"]["imposto"] == D("77699.09")
    assert s["hoje"]["credito"] == D("0.00")
    assert s["2027"]["credito"] == D("26724.72")
    assert s["2033"]["imposto"] == D("80477.85")


def test_golden_uvait():
    s = simular_item(D("1918.08"), D("0"), "200014", "5102", "venda", "", "aliquota_zero")
    assert all(s[c]["imposto"] == D("0.00") for c in ("hoje", "2027", "2033"))


def test_golden_macarpe():
    """Exportacao: ICMS destacado e erro de emissao; vale zero em todos os cenarios."""
    s = simular_item(D("620.40"), D("43.43"), "410004", "7102", "venda", "", "tributado")
    assert s["hoje"]["imposto"] == D("0.00")
    assert s["2027"]["imposto"] == D("0.00")
    assert s["2033"]["imposto"] == D("0.00")


def test_exportacao_icms_template_fallback(monkeypatch):
    """Com o flag desligado, reproduz o ICMS destacado do template oficial."""
    from src import premissas

    monkeypatch.setattr(premissas, "exportacao_icms_zero", lambda: False)
    s = simular_item(D("620.40"), D("43.43"), "410004", "7102", "venda", "", "tributado")
    assert s["hoje"]["imposto"] == D("43.43")
    assert s["2027"]["imposto"] == D("43.43")
    assert s["2033"]["imposto"] == D("0.00")


def test_golden_rfclar():
    s = simular_item(D("49.46"), D("0"), "410001", "5910", "venda", "", "monofasico")
    assert all(s[c]["imposto"] == D("0.00") for c in ("hoje", "2027", "2033"))


def test_pis_exportacao_zero():
    assert pis_cofins_hoje(D("100"), D("10"), "7102", "tributado") == (D("0"), D("0"))
    assert pis_cofins_hoje(D("100"), D("10"), "5910", "tributado") == (D("0"), D("0"))


def test_distribuicao_classificacao():
    itens, _ = extrair_tudo()
    cad = carregar_cadastro()
    cat = construir_catalogo(itens, cad)
    cls = classificar_itens(itens, cad, cat)
    vc = cls["cClassTrib"].value_counts().to_dict()
    # 8 classes do case
    assert vc.get("200003") == 4817
    assert vc.get("000001") == 3889
    assert vc.get("200014") == 2501
    assert vc.get("200034") == 1637
    assert vc.get("200030") == 1228
    assert vc.get("410004") == 447
    assert vc.get("200005") == 443
    assert vc.get("410001") == 38
    assert (cls["status"] == "REVISAR").sum() == 0


def test_imposto_seletivo_497():
    itens, _ = extrair_tudo()
    cad = carregar_cadastro()
    cls = classificar_itens(itens, cad)
    assert (cls["imposto_seletivo"] == "sim").sum() == 497


def test_resumo_identidade_e_variacao():
    itens, _ = extrair_tudo()
    cad = carregar_cadastro()
    cls = classificar_itens(itens, cad)
    sim = simular_dataframe(itens, cls, cad)
    from src.simular import resumo

    res = resumo(sim)
    assert res[0]["cenario"] == "hoje"
    assert res[0]["variacao_vs_hoje"] == D("0.00")
    for r in res:
        assert r["imposto_liquido"] == r["debitos_vendas"] - r["creditos_compras"]


def test_coerencia_catalogo_itens():
    """P25: valida a regra, nao o snapshot.

    Todo item deve seguir a classe-base do catalogo, exceto quando uma regra de
    operacao (OP-01 CFOP 5910, OP-02 exportacao, OP-03 dispositivo + orgao) muda
    a classe antes do produto.
    """
    itens, _ = extrair_tudo()
    cad = carregar_cadastro()
    cat = construir_catalogo(itens, cad)
    cls = classificar_itens(itens, cad, cat)
    cat_map = cat.set_index(["cProd", "NCM"])["cClassTrib"].to_dict()
    op = cls["CFOP"].isin(["5910", "7102"]) | (
        (cls["familia"] == "DISPOSITIVO_MEDICO") & (cls["tipo_cliente"] == "orgao_publico")
    )
    esperado = pd.Series(
        [cat_map[(r.cProd, r.NCM)] for r in cls.itertuples()], index=cls.index
    )
    divergentes = cls[(~op) & (cls["cClassTrib"] != esperado)]
    assert divergentes.empty, divergentes[["chave", "nItem", "cClassTrib"]].head().to_dict()
