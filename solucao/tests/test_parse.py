"""Gate de reconciliacao e extracao das 1.387 DANFEs."""
from __future__ import annotations

from decimal import Decimal


from src.caminhos import DANFE_DIR
from src.extrair import extrair_tudo
from src.parse_danfe import Item, Nota, Totais, parse_pdf


def test_parser_amostra_reconcilia():
    """Cada nota da amostra fecha vProd, vICMS, PIS e COFINS."""
    from src.io_dados import tratamento_por_produto

    trat = tratamento_por_produto()
    arquivos = sorted(DANFE_DIR.glob("*.pdf"))[:12]
    assert arquivos, "pacote de DANFEs nao encontrado"
    for p in arquivos:
        nota = parse_pdf(p, trat)
        rec = nota.reconciliacao()
        assert rec.ok, (p.name, rec.divergencias())
        assert len(nota.itens) >= 1


def test_todas_as_notas_reconciliam():
    itens, notas = extrair_tudo()
    assert len(notas) == 1387
    assert int(notas["reconciliada"].astype(bool).sum()) == 1387


def test_contagens_de_extracao():
    itens, notas = extrair_tudo()
    assert len(itens) == 15000
    assert itens["chave"].str.len().eq(44).all()
    assert itens["NCM"].str.len().eq(8).all()
    # perspectiva pela chave
    assert (itens["perspectiva"] == "compra").sum() == 11700
    assert (itens["perspectiva"] == "venda").sum() == 3300
    # nItem comeca em 1 e nao pula
    g = itens.groupby("chave")["nItem"].apply(lambda s: sorted(s.astype(int).tolist()))
    for chave, itens_n in g.items():
        assert itens_n == list(range(1, len(itens_n) + 1)), chave


def test_cfop_esperado():
    itens, _ = extrair_tudo()
    vc = itens["CFOP"].value_counts().to_dict()
    assert vc.get("5102") == 11516
    assert vc.get("5101") == 2999
    assert vc.get("5910") == 38
    assert vc.get("7102") == 447


def test_reconciliacao_detecta_nota_corrompida():
    """P26: o gate precisa falhar quando os totais impressos nao fecham."""
    chave = "1" * 44
    item = Item(
        chave=chave,
        nItem=1,
        cProd="TESTE",
        xProd="Produto Teste",
        NCM="12345678",
        CST="000",
        CFOP="5102",
        un="UN",
        qtd=Decimal("1"),
        vUnit=Decimal("100.00"),
        vProd=Decimal("100.00"),
        vICMS=Decimal("18.00"),
        bCalcICMS=Decimal("100.00"),
    )
    nota = Nota(
        chave=chave,
        emitente_cnpj="12345678000190",
        destinatario_cnpj="12345678000191",
        cfop_nota="5102",
        perspectiva="compra",
        itens=[item],
        totais=Totais(v_produtos=Decimal("200.00")),  # divergente de proposito
        tratamento={"TESTE": "tributado"},
    )
    rec = nota.reconciliacao()
    assert not rec.ok
    nomes = [d[0] for d in rec.divergencias()]
    assert "vProd" in nomes
