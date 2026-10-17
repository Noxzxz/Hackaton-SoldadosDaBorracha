"""Testes da busca BM25 (deterministica, sem dependencias externas)."""
from __future__ import annotations

from src.busca import tokenizar, top5


def test_tokenizar_remove_acento():
    assert tokenizar("Arroz Ção") == ["arroz", "cao"]


def test_top5_deterministico():
    a = top5("ARROZ BRANCO TIPO 1 5KG")
    b = top5("ARROZ BRANCO TIPO 1 5KG")
    assert a == b
    assert any(r["cClassTrib"] == "200003" for r in a)


def test_top5_respeita_filtro_de_classes():
    r = top5("ARROZ", k=5, classes_filtro=["200003"])
    assert all(x["cClassTrib"] == "200003" for x in r)


def test_top5_vazio_para_texto_sem_match():
    assert top5("zzzzzzzqqqq") == []
