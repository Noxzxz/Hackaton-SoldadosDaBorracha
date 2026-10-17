"""Testes de propriedade (hypothesis) sobre a aritmetica e as invariantes."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from hypothesis import given, settings
from hypothesis import strategies as st

from src import premissas
from src.simular import SEM_INCIDENCIA, ibs_cbs, r2, simular_item

D = Decimal

vprods = st.decimals(min_value=D("0.01"), max_value=D("2000000"), places=2)
classes = st.sampled_from(sorted(premissas.reducoes().keys()))
cfops = st.sampled_from(["5101", "5102", "5910", "7102"])
perspectivas = st.sampled_from(["compra", "venda"])
finalidades = st.sampled_from(["revenda", "uso_consumo", ""])
tratamentos = st.sampled_from(["tributado", "aliquota_zero", "monofasico"])


@settings(max_examples=200)
@given(vprods)
def test_r2_half_up(x):
    assert r2(x) == x.quantize(D("0.01"), rounding=ROUND_HALF_UP)
    assert r2(x).as_tuple().exponent == -2


@settings(max_examples=200)
@given(vprods, classes)
def test_sem_incidencia_zera_ibscbs(vp, cl):
    cbs, ibs = ibs_cbs(vp, cl, "2033")
    if cl in SEM_INCIDENCIA or premissas.reducoes().get(cl) == D("1"):
        assert cbs == D("0") and ibs == D("0")
    assert cbs >= 0 and ibs >= 0


@settings(max_examples=200)
@given(vprods, classes, cfops, perspectivas, finalidades, tratamentos)
def test_credito_null_em_vendas(vp, cl, cfop, persp, fin, trat):
    s = simular_item(vp, D("0"), cl, cfop, persp, fin, trat)
    for c in ("hoje", "2027", "2033"):
        if persp == "venda":
            assert s[c]["credito"] is None
        else:
            assert s[c]["credito"] is not None
            assert s[c]["credito"] >= D("0")
        # aliquota efetiva coerente
        assert s[c]["aliquota_efetiva_pct"] == r2(s[c]["imposto"] / vp * D("100"))


@settings(max_examples=100)
@given(vprods, classes, cfops, perspectivas, finalidades, tratamentos)
def test_idempotencia(vp, cl, cfop, persp, fin, trat):
    a = simular_item(vp, D("1.23"), cl, cfop, persp, fin, trat)
    b = simular_item(vp, D("1.23"), cl, cfop, persp, fin, trat)
    assert a == b


@settings(max_examples=100)
@given(vprods, classes)
def test_percentual_100_zera(vp, cl):
    red = premissas.reducoes().get(cl)
    cbs, ibs = ibs_cbs(vp, cl, "2027")
    if red == D("1"):
        assert cbs == D("0") and ibs == D("0")


def test_arredondamento_por_tributo():
    """CBS e IBS sao arredondados separadamente antes de somar."""
    vp = D("1677.50")
    cbs = r2(vp * D("0.087") * D("1"))
    ibs = r2(vp * D("0.001") * D("1"))
    assert cbs == D("145.94")
    assert ibs == D("1.68")
    assert cbs + ibs == D("147.62")  # nao o mesmo que r2(145.9425)+r2(1.6775)
