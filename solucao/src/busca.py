"""Busca top-5 (BM25 lexical) para apoiar o juiz LLM.

Implementacao BM25 pura (sem dependencias novas) sobre um corpus montado com:
  - as descricoes de exemplo oficiais (`exemplos_por_classe`);
  - a descricao reduzida de cada `cClassTrib`.

A recuperacao e deterministica e serve para enriquecer o prompt do juiz e para
registrar, na auditoria, por que a busca (sozinha) nao fechou a classe. Se
`usar_embeddings` estiver ligado, a recuperacao hibrida entra como hook futuro;
a assinatura nao muda.
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from functools import lru_cache

from .io_dados import cclasstrib, exemplos

K1 = 1.5
B = 0.75


def tokenizar(texto: str) -> list:
    s = unicodedata.normalize("NFKD", str(texto or ""))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return [t for t in re.split(r"[^a-z0-9]+", s) if t]


@lru_cache(maxsize=None)
def _corpus() -> tuple:
    """Corpus imutavel: ((doc_id, tokens), ...)."""
    docs: list = []
    try:
        for _, r in exemplos().iterrows():
            docs.append((str(r["cClassTrib"]).zfill(6), tokenizar(r["exemplo_de_descricao"])))
    except Exception:  # noqa: BLE001
        pass
    try:
        for _, r in cclasstrib().iterrows():
            txt = r.get("descricao_reduzida") or r.get("descricao") or ""
            if str(txt).strip():
                docs.append((str(r["cClassTrib"]).zfill(6), tokenizar(txt)))
    except Exception:  # noqa: BLE001
        pass
    return tuple(docs)


class IndiceBM25:
    def __init__(self, docs: tuple):
        self.docs = list(docs)
        self.n = len(self.docs)
        self.tf = [Counter(toks) for _, toks in self.docs]
        self.dl = [len(toks) for _, toks in self.docs]
        self.avgdl = (sum(self.dl) / self.n) if self.n else 0.0
        df = Counter()
        for _, toks in self.docs:
            for t in set(toks):
                df[t] += 1
        self.idf = {
            t: math.log(1 + (self.n - c + 0.5) / (c + 0.5)) for t, c in df.items()
        }

    def score(self, consulta: list, i: int) -> float:
        s = 0.0
        tf = self.tf[i]
        dl = self.dl[i] or 1
        for termo in consulta:
            f = tf.get(termo, 0)
            if f == 0:
                continue
            idf = self.idf.get(termo, 0.0)
            s += idf * (f * (K1 + 1)) / (f + K1 * (1 - B + B * dl / (self.avgdl or 1)))
        return s

    def top_k(self, texto: str, k: int = 5, classes_filtro=None) -> list:
        consulta = tokenizar(texto)
        filtro = set(str(c).zfill(6) for c in classes_filtro) if classes_filtro else None
        pontuados = []
        for i, (doc_id, _) in enumerate(self.docs):
            if filtro is not None and doc_id not in filtro:
                continue
            s = self.score(consulta, i)
            if s > 0:
                pontuados.append((s, doc_id, " ".join(self.docs[i][1])))
        pontuados.sort(key=lambda x: (-x[0], x[1]))
        return [
            {"cClassTrib": d, "exemplo": txt, "score": round(s, 4)}
            for s, d, txt in pontuados[:k]
        ]


@lru_cache(maxsize=1)
def _indice() -> IndiceBM25:
    return IndiceBM25(_corpus())


def top5(descricao: str, k: int = 5, classes_filtro=None) -> list:
    """Top-k exemplos/classe por BM25. Deterministico."""
    return _indice().top_k(descricao, k=k, classes_filtro=classes_filtro)


if __name__ == "__main__":
    for r in top5("ARROZ BRANCO TIPO 1 5KG", k=5):
        print(r)
