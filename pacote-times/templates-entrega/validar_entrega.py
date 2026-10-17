"""
Valida o formato dos dois arquivos de entrega antes do code freeze.

Uso: python validar_entrega.py <pasta_da_equipe>
     (a pasta deve conter itens_classificados.csv e simulacao.json)
"""
import csv, json, re, sys
from pathlib import Path

CENARIOS = ["hoje", "2027", "2033"]


def main(pasta):
    pasta = Path(pasta)
    erros, avisos = [], []
    # --- itens_classificados.csv
    p = pasta / "itens_classificados.csv"
    if not p.exists():
        erros.append("itens_classificados.csv não encontrado")
        linhas = []
    else:
        with open(p, encoding="utf-8-sig", newline="") as f:
            rd = csv.DictReader(f, delimiter=";")
            cols = rd.fieldnames or []
            linhas = list(rd)
        obrig = ["chave", "nItem", "cClassTrib", "status", "confianca", "imposto_seletivo", "fonte"]
        falt = [c for c in obrig if c not in cols]
        if falt:
            erros.append(f"itens_classificados.csv: colunas ausentes {falt} (separador ';'; cabeçalho exato)")
        else:
            vistos = set()
            for i, r in enumerate(linhas, 2):
                ch = r["chave"].replace(" ", "")
                if not re.fullmatch(r"\d{44}", ch):
                    erros.append(f"linha {i}: chave inválida '{r['chave']}' (44 dígitos)")
                if not r["nItem"].strip().isdigit():
                    erros.append(f"linha {i}: nItem não inteiro '{r['nItem']}'")
                if not re.fullmatch(r"\d{6}", r["cClassTrib"].strip()):
                    erros.append(f"linha {i}: cClassTrib '{r['cClassTrib']}' deve ter 6 dígitos")
                if r["status"].strip().upper() not in ("CLASSIFICADO", "REVISAR"):
                    erros.append(f"linha {i}: status '{r['status']}' (CLASSIFICADO ou REVISAR)")
                try:
                    c = float(r["confianca"].replace(",", "."))
                    if not 0 <= c <= 1:
                        raise ValueError
                    if r["status"].strip().upper() == "REVISAR" and c >= 0.70:
                        avisos.append(f"linha {i}: REVISAR com confiança {c} ≥ 0,70")
                except ValueError:
                    erros.append(f"linha {i}: confianca '{r['confianca']}' deve estar entre 0 e 1")
                if r["imposto_seletivo"].strip().lower() not in ("sim", "nao"):
                    erros.append(f"linha {i}: imposto_seletivo '{r['imposto_seletivo']}' (sim ou nao)")
                if not r["fonte"].strip():
                    avisos.append(f"linha {i}: fonte vazia")
                k = (ch, r["nItem"].strip())
                if k in vistos:
                    erros.append(f"linha {i}: (chave, nItem) duplicado")
                vistos.add(k)
            if len(linhas) < 15000:
                avisos.append(f"{len(linhas)} itens classificados; o pacote tem 15.000 (item ausente conta como erro)")
    # --- simulacao.json
    p = pasta / "simulacao.json"
    if not p.exists():
        erros.append("simulacao.json não encontrado")
    else:
        try:
            s = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            erros.append(f"simulacao.json inválido: {e}")
            s = {}
        itens = s.get("itens")
        if not isinstance(itens, list):
            erros.append("simulacao.json: 'itens' ausente ou não é lista")
            itens = []
        for i, it in enumerate(itens):
            for k in ("chave", "nItem", "perspectiva", "cClassTrib", "vProd", *CENARIOS):
                if k not in it:
                    erros.append(f"itens[{i}]: falta o campo '{k}'")
                    break
            else:
                if it["perspectiva"] not in ("compra", "venda"):
                    erros.append(f"itens[{i}]: perspectiva '{it['perspectiva']}' (compra ou venda)")
                for c in CENARIOS:
                    b = it[c]
                    if not isinstance(b, dict) or "imposto" not in b or "credito" not in b or "aliquota_efetiva_pct" not in b:
                        erros.append(f"itens[{i}].{c}: precisa de imposto, aliquota_efetiva_pct e credito")
                        break
                    if it["perspectiva"] == "venda" and b["credito"] is not None:
                        avisos.append(f"itens[{i}].{c}: credito deve ser null nas vendas")
            if len(erros) > 50:
                break
        res = s.get("resumo")
        if not isinstance(res, list):
            erros.append("simulacao.json: 'resumo' ausente ou não é lista")
        else:
            cen = {str(r.get("cenario")) for r in res if isinstance(r, dict)}
            for c in CENARIOS:
                if c not in cen:
                    erros.append(f"resumo: falta o cenário '{c}'")
            for r in res:
                for k in ("debitos_vendas", "creditos_compras", "imposto_liquido", "variacao_vs_hoje"):
                    if isinstance(r, dict) and k not in r:
                        erros.append(f"resumo[{r.get('cenario')}]: falta '{k}'")
        if isinstance(itens, list) and len(itens) < 15000:
            avisos.append(f"simulacao.json tem {len(itens)} itens; o pacote tem 15.000")
    for e in erros[:60]:
        print("ERRO  ", e)
    for a in avisos[:20]:
        print("AVISO ", a)
    if len(erros) > 60:
        print(f"... e mais {len(erros) - 60} erros")
    print("\nRESULTADO:", "FORMATO OK" if not erros else f"{len(erros)} erro(s) — corrijam antes de entregar")
    sys.exit(0 if not erros else 1)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
