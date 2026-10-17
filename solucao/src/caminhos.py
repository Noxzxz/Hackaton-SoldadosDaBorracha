"""Caminhos absolutos do projeto.

Resolve a raiz do repositorio a partir do local deste arquivo
(solucao/src/caminhos.py -> raiz = parents[2]).
"""
from __future__ import annotations

from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
SOLUCAO_DIR = SRC_DIR.parent
RAIZ = SOLUCAO_DIR.parent


def _resolver_pacote() -> Path:
    """Localiza o pacote oficial das equipes.

    Preferencia: pacote novo (`pacote-times-*/pacote-times/dados`), depois o
    pacote `pacote-times` local e, por fim, o antigo `03-dados-alunos`.
    """
    candidatos = sorted(RAIZ.glob("pacote-times-*/pacote-times"), reverse=True)
    candidatos.append(RAIZ / "pacote-times")
    for p in candidatos:
        if (p / "dados" / "danfe").exists():
            return p
    for p in candidatos:
        if (p / "03-dados-alunos" / "danfe").exists():
            return p
    return RAIZ


PACOTE_DIR = _resolver_pacote()
if (PACOTE_DIR / "dados").exists():
    DATA_DIR = PACOTE_DIR / "dados"
elif (PACOTE_DIR / "03-dados-alunos").exists():
    DATA_DIR = PACOTE_DIR / "03-dados-alunos"
elif (PACOTE_DIR / "danfe").exists():
    DATA_DIR = PACOTE_DIR
else:
    DATA_DIR = RAIZ / "03-dados-alunos"
DANFE_DIR = DATA_DIR / "danfe"

CONFIG_DIR = SOLUCAO_DIR / "config"
OUT_DIR = SOLUCAO_DIR / "out"
SAIDA_DIR = SOLUCAO_DIR / "saida"
LOGS_DIR = SOLUCAO_DIR / "logs"

# CNPJ da empresa foco (Atacadista Meridional). O pacote oficial novo ja traz
# 51238476000104 no parametros.json, igual ao cadastro e as chaves das DANFEs.
CNPJ_FOCO = "51238476000104"

for _d in (OUT_DIR, SAIDA_DIR, LOGS_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def data_path(nome: str) -> Path:
    return DATA_DIR / nome
