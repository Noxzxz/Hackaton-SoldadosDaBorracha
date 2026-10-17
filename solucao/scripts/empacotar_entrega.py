"""Empacota a entrega oficial e roda o validador do pacote.

Cria uma pasta com o nome da equipe contendo EXATAMENTE os dois arquivos
exigidos (`itens_classificados.csv` e `simulacao.json`) e roda o validador
oficial em `pacote-times/templates-entrega/validar_entrega.py` apontando para
essa pasta.

Uso:
    python scripts/empacotar_entrega.py                       # nome padrao
    python scripts/empacotar_entrega.py --nome SoldadosDaBorracha
    python scripts/empacotar_entrega.py --destino ..\\entrega --sem-validar
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.caminhos import PACOTE_DIR, RAIZ as REPO_RAIZ, SAIDA_DIR  # noqa: E402

ARQUIVOS = ("itens_classificados.csv", "simulacao.json")
NOME_PADRAO = "SoldadosDaBorracha"


def _localizar_validador() -> Path | None:
    candidatos = [
        PACOTE_DIR / "templates-entrega" / "validar_entrega.py",
        REPO_RAIZ / "pacote-times" / "templates-entrega" / "validar_entrega.py",
    ]
    for c in candidatos:
        if c.exists():
            return c
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Empacota a entrega e valida o formato.")
    ap.add_argument("--nome", default=NOME_PADRAO, help="nome da pasta da equipe")
    ap.add_argument("--destino", default=str(REPO_RAIZ), help="pasta onde criar a entrega")
    ap.add_argument("--sem-validar", action="store_true", help="nao roda o validador oficial")
    args = ap.parse_args()

    faltando = [a for a in ARQUIVOS if not (SAIDA_DIR / a).exists()]
    if faltando:
        print("ERRO: rode antes `python scripts/rodar_tudo.py`. Faltando:", faltando)
        return 2

    destino = Path(args.destino).resolve() / args.nome
    destino.mkdir(parents=True, exist_ok=True)

    for a in ARQUIVOS:
        shutil.copy2(SAIDA_DIR / a, destino / a)

    conteudo = sorted(p.name for p in destino.iterdir() if p.is_file())
    print(f"Entrega criada em: {destino}")
    print("Arquivos:", conteudo)
    if conteudo != sorted(ARQUIVOS):
        print("ERRO: a pasta deve conter exatamente", sorted(ARQUIVOS))
        return 3

    if args.sem_validar:
        print("(validador oficial ignorado por --sem-validar)")
        return 0

    validador = _localizar_validador()
    if validador is None:
        print("AVISO: validador oficial nao encontrado em pacote-times/templates-entrega.")
        return 0

    print(f"\nRodando validador oficial: {validador}")
    ret = subprocess.run([sys.executable, str(validador), str(destino)])
    return ret.returncode


if __name__ == "__main__":
    raise SystemExit(main())
