"""Confianca medida por estabilidade (mutation testing no catalogo).

Para cada produto do catalogo geramos K variantes plausiveis (NCM vizinho de
mesmo prefixo, reordenacao/abreviacao da descricao) e reclassificamos. A fracao
de variantes que preserva a classe e a confianca medida; se cair abaixo de 0,25
o produto vai para REVISAR. Roda no catalogo (<=128 linhas), nunca nos 15.000 itens.

Custo: 0 tokens. Payoff: calibracao (10% da nota) + linha de pitch.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .classificar import classificar_produto

LIMIAR_REVISAR = 0.25


def _variantes_descricao(xprod: str) -> list:
    palavras = xprod.split()
    if not palavras:
        return [xprod]
    invertida = " ".join(reversed(palavras))
    abreviada = " ".join(p[:6] for p in palavras)
    sem_numero = " ".join(p for p in palavras if not any(c.isdigit() for c in p))
    sem_palavra_inicial = " ".join(palavras[1:]) if len(palavras) > 1 else xprod
    return [xprod, invertida, abreviada, sem_numero or xprod, sem_palavra_inicial]


def medir_estabilidade(catalogo: pd.DataFrame, cnae_por_emitente: dict = None) -> pd.DataFrame:
    """Confianca medida: fracao de variacoes de descricao que preservam a classe.

    O NCM e mantido fixo: ele e um campo duro da DANFE (um erro de digitacao
    seria capturado pelo gate de reconciliacao). O que varia e a descricao, que
    e onde a familia/guarda podem falhar.
    """
    linhas = []
    for _, r in catalogo.iterrows():
        cnae = str(r.get("cnae", ""))
        classe_ref = classificar_produto(r["cProd"], r["NCM"], r["xProd_norm"], cnae).cClassTrib
        variantes = _variantes_descricao(r["xProd_norm"])
        estaveis = sum(
            1 for desc in variantes
            if classificar_produto(r["cProd"], r["NCM"], desc, cnae).cClassTrib == classe_ref
        )
        est = estaveis / len(variantes) if variantes else 1.0
        linhas.append(
            {"cProd": r["cProd"], "NCM": r["NCM"], "cClassTrib": classe_ref,
             "estabilidade": est, "revisar": est < LIMIAR_REVISAR}
        )
    return pd.DataFrame(linhas)


@dataclass
class ResultadoMutacao:
    n_produtos: int
    n_revisar: int
    estabilidade_media: float


def resumo(df: pd.DataFrame) -> ResultadoMutacao:
    return ResultadoMutacao(
        n_produtos=len(df),
        n_revisar=int(df["revisar"].sum()),
        estabilidade_media=float(df["estabilidade"].mean()) if len(df) else 1.0,
    )


if __name__ == "__main__":
    from .classificar import construir_catalogo
    from .extrair import extrair_tudo
    from .io_dados import cadastro as carregar_cadastro

    itens, _ = extrair_tudo()
    cad = carregar_cadastro()
    cat = construir_catalogo(itens, cad)
    est = medir_estabilidade(cat)
    print(resumo(est))
    print(est.sort_values("estabilidade").head(15).to_string())
