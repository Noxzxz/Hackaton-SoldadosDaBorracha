"""Pipeline ponta a ponta, idempotente.

Uso:
    python scripts/rodar_tudo.py            # usa cache de extracao
    python scripts/rodar_tudo.py --reparse  # reextrai as 1.387 DANFEs
    python scripts/rodar_tudo.py --testes   # roda pytest ao final
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reparse", action="store_true", help="reextrai os PDFs")
    ap.add_argument("--testes", action="store_true", help="roda os testes no final")
    ap.add_argument(
        "--sem-llm",
        action="store_true",
        help="nao aciona o juiz LLM (dry-run; mantem a decisao deterministica)",
    )
    ap.add_argument(
        "--workers",
        type=int,
        default=None,
        help="numero de processos para o parseamento (default: min(8, cpus))",
    )
    args = ap.parse_args()

    t0 = time.time()
    print("[1/6] extracao + reconciliacao das 1.387 DANFEs")
    from src.exportar import exportar_tudo
    from src.extrair import extrair_tudo

    itens, notas = extrair_tudo(force=args.reparse, workers=args.workers)
    n_ok = int(notas["reconciliada"].astype(bool).sum())
    print(f"      itens={len(itens)} notas={len(notas)} reconciliadas={n_ok}/{len(notas)}")
    if n_ok != len(notas):
        print("      ERRO: gate de reconciliacao falhou")
        return 2

    print("[2/6] catalogo + cascata de classificacao + simulacao + exportacao")
    info = exportar_tudo(salvar_painel=True, usar_llm=not args.sem_llm)
    print(f"      itens simulados={info['n_itens']} politica={info['politica']}")
    fila = info.get("fila_llm")
    if fila:
        estado = "habilitado" if fila["habilitado"] else "dry-run (sem modelo/chave)"
        print(
            f"      juiz LLM [{estado}]: fila={fila['n_fila']} llm={fila['n_llm']} "
            f"revisar={fila['n_revisar']} regra={fila['n_regra']} "
            f"chamadas={fila['chamadas']} tokens={fila['tokens_entrada']}/{fila['tokens_saida']}"
        )
    elif args.sem_llm:
        print("      juiz LLM desativado por --sem-llm")

    print("[3/6] resumo por cenario")
    for r in info["resumo"]:
        print(
            f"      {r['cenario']:>5}: debitos={r['debitos_vendas']} "
            f"creditos={r['creditos_compras']} liquido={r['imposto_liquido']} "
            f"variacao={r['variacao_vs_hoje']}"
        )

    print("[4/6] entregaveis")
    from src.caminhos import SAIDA_DIR

    print(f"      {SAIDA_DIR / 'itens_classificados.csv'}")
    print(f"      {SAIDA_DIR / 'simulacao.json'}")

    print("[5/6] trilha de auditoria e tribunal")
    print(f"      {RAIZ / 'out' / 'trilha.parquet'}")
    print(f"      {RAIZ / 'out' / 'tribunal.json'}")

    codigo = 0
    if args.testes:
        print("[6/6] pytest")
        import pytest

        codigo = pytest.main(["-q", str(RAIZ / "tests")])

    print(f"concluido em {time.time() - t0:.1f}s (exit={codigo})")
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
