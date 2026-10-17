"""Testes do juiz LLM (fila de ambiguidades) sem tocar a rede.

Usa um cliente falso e isola o cache em um diretorio temporario.
"""
from __future__ import annotations

import pandas as pd
import pytest

from src import llm_juiz


class FakeCliente:
    def __init__(self, resposta, habilitado=True):
        self.modelo = "fake-modelo"
        self._resposta = resposta
        self._habilitado = habilitado
        self.n = 0
        self._uso = {
            "modelo": "fake-modelo",
            "base_url": "",
            "chamadas": 0,
            "tokens_entrada": 0,
            "tokens_saida": 0,
        }

    @property
    def habilitado(self):
        return self._habilitado

    def chat_json(self, prompt, system=""):
        self.n += 1
        self._uso["chamadas"] += 1
        self._uso["tokens_entrada"] += 10
        self._uso["tokens_saida"] += 5
        return self._resposta

    @property
    def uso(self):
        return dict(self._uso)

    def salvar_uso(self):
        pass


def _catalogo(ambiguo=True, classe="200030", candidatos="200005;200030"):
    return pd.DataFrame(
        [
            {
                "cProd": "X1",
                "NCM": "40151900",
                "xProd_norm": "LUVA PROCEDIMENTO LATEX",
                "cnae": "",
                "familia": "DISPOSITIVO_MEDICO",
                "cClassTrib": classe,
                "classe_mapa": classe,
                "confianca": 0.72,
                "status": "CLASSIFICADO",
                "fonte": "MAPA L1 NCM 40151900 exato",
                "regra": "NCM_EXATO_DESEMPATE",
                "imposto_seletivo": False,
                "divergente": False,
                "tipo_match": "exato",
                "linha_mapa": 1,
                "ambiguo": ambiguo,
                "ambiguidade_condicao": False,
                "candidatos_classe": candidatos,
                "candidatos_brutos": candidatos,
                "evidencia_mapa": "",
                "eliminados": "",
                "metodo": "regra",
            }
        ]
    )


@pytest.fixture(autouse=True)
def cache_isolado(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_juiz, "CACHE_PATH", tmp_path / "cache_llm.json")
    yield


def test_decisao_llm_valida():
    fake = FakeCliente(
        {"cClassTrib": "200005", "confianca": 0.8, "justificativa": "venda a orgao publico"}
    )
    cat, res = llm_juiz.resolver_fila(_catalogo(), cliente=fake, top5_fn=lambda *a, **k: [])
    assert res.n_llm == 1
    assert cat.iloc[0]["cClassTrib"] == "200005"
    assert cat.iloc[0]["metodo"] == "llm"
    assert float(cat.iloc[0]["confianca"]) <= 0.90


def test_resposta_fora_dos_candidatos_e_rejeitada():
    fake = FakeCliente({"cClassTrib": "999999", "confianca": 0.9, "justificativa": "x"})
    cat, res = llm_juiz.resolver_fila(_catalogo(), cliente=fake, top5_fn=lambda *a, **k: [])
    assert res.n_llm == 0
    assert res.n_regra == 1
    assert cat.iloc[0]["cClassTrib"] == "200030"
    assert cat.iloc[0]["metodo"] == "regra_ambiguo"


def test_resposta_revisar():
    fake = FakeCliente({"cClassTrib": "REVISAR", "confianca": 0.4, "justificativa": "duvida"})
    cat, res = llm_juiz.resolver_fila(_catalogo(), cliente=fake, top5_fn=lambda *a, **k: [])
    assert res.n_revisar == 1
    assert cat.iloc[0]["status"] == "REVISAR"
    assert float(cat.iloc[0]["confianca"]) < 0.70


def test_dry_run_sem_modelo():
    fake = FakeCliente({}, habilitado=False)
    cat, res = llm_juiz.resolver_fila(_catalogo(), cliente=fake, top5_fn=lambda *a, **k: [])
    assert res.habilitado is False
    assert fake.n == 0
    assert cat.iloc[0]["cClassTrib"] == "200030"
    assert cat.iloc[0]["metodo"] == "regra_ambiguo"


def test_cache_evita_segunda_chamada():
    fake = FakeCliente({"cClassTrib": "200005", "confianca": 0.8, "justificativa": "x"})
    llm_juiz.resolver_fila(_catalogo(), cliente=fake, top5_fn=lambda *a, **k: [])
    assert fake.n == 1
    # segunda execucao do mesmo prompt -> cache
    fake2 = FakeCliente({"cClassTrib": "200005", "confianca": 0.8, "justificativa": "x"})
    cat2, res2 = llm_juiz.resolver_fila(_catalogo(), cliente=fake2, top5_fn=lambda *a, **k: [])
    assert fake2.n == 0
    assert cat2.iloc[0]["cClassTrib"] == "200005"
    assert res2.n_llm == 1
