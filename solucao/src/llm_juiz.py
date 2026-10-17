"""Juiz LLM (agente obrigatorio) para os produtos ambiguos.

Fluxo:
  1. a cascata deterministica resolve a maioria dos produtos;
  2. produtos com mais de uma classe permitida (ou condicao nao mapeada) entram
     na `fila`;
  3. para cada produto da fila, o juiz monta um prompt com os candidatos + top-5
     BM25 + regras eliminadas e pede uma decisao em JSON;
  4. a resposta e validada: so vale classe entre os candidatos (ou 000001);
     `REVISAR` e resposta valida; resposta invalida/sem modelo -> None;
  5. a decisao entra no catalogo com confianca <= 0.90 e metodo="llm".

Uma chamada por PRODUTO distinto (nunca por item). Cache por SHA-256 do prompt
+ modelo. Sem modelo/chave: `habilitado == False` -> dry-run (mantem a regra).
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from .busca import top5 as busca_top5
from .caminhos import OUT_DIR
from .io_dados import cclasstrib, classes_vigentes
from .llm_cliente import LlmCliente, carregar_config

logger = logging.getLogger(__name__)

CACHE_PATH = OUT_DIR / "cache_llm.json"
LIMIAR_CONF_LLM = 0.90


@dataclass
class RespostaJuiz:
    cClassTrib: str
    confianca: float
    justificativa: str
    fonte: str = "llm"
    cache_hit: bool = False


def _hash(prompt: str, modelo: str) -> str:
    return hashlib.sha256(f"{modelo}|{prompt}".encode("utf-8")).hexdigest()


def _carregar_cache() -> dict:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def _salvar_cache(cache: dict) -> None:
    try:
        CACHE_PATH.write_text(
            json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    except OSError as e:  # noqa: BLE001
        logger.warning("nao foi possivel salvar cache LLM (%s)", e)


def _descricao_classe(classe: str) -> str:
    try:
        d = cclasstrib()
        sel = d[d["cClassTrib"] == str(classe).zfill(6)]
        if len(sel):
            return str(sel.iloc[0].get("descricao_reduzida") or sel.iloc[0].get("descricao") or "")
    except Exception:  # noqa: BLE001
        pass
    return ""


class LlmJuiz:
    def __init__(self, cliente: Optional[LlmCliente] = None):
        self.cliente = cliente or LlmCliente()
        self.modelo = self.cliente.modelo or "sem-modelo"
        self.cache = _carregar_cache()

    # ------------------------------------------------------------------ #
    def montar_prompt(
        self,
        xprod_norm: str,
        ncm: str,
        cfop: str,
        cnae: str,
        classe_tentativa: str,
        candidatos: list,
        top5: list,
        eliminados: str,
        evidencia: str,
    ) -> str:
        linhas = [
            "Voce e um auditor fiscal da LC 214/2025 (reforma tributaria).",
            "Escolha o cClassTrib correto para o produto abaixo.",
            f'Produto: "{xprod_norm}" | NCM {ncm} | CFOP {cfop} | CNAE emitente {cnae or "n/d"}',
            "",
            "Classes candidatas VALIDAS (escolha SOMENTE um destes IDs, ou REVISAR):",
        ]
        for c in candidatos:
            linhas.append(f"  [{c}] {_descricao_classe(c)}")
        linhas.append("  [000001] Regime padrao (produto nao listado em anexo)")
        linhas.append(f"Decisao deterministica preliminar (familia): [{classe_tentativa}]")
        if eliminados:
            linhas.append(f"Classes ja eliminadas pelas regras: {eliminados}")
        if evidencia:
            linhas.append(f"Evidencia do mapa: {evidencia}")
        if top5:
            linhas.append("Exemplos oficiais similares (BM25):")
            for e in top5:
                linhas.append(f"  [{e['cClassTrib']}] {e['exemplo']}")
        linhas.append("")
        linhas.append(
            "Responda APENAS um JSON com as chaves "
            '{"cClassTrib","confianca","justificativa","fonte_ids"}.'
        )
        linhas.append(
            'Use {"cClassTrib":"REVISAR","confianca":0.4,...} se nao houver '
            "evidencia suficiente. Nao invente classes fora da lista."
        )
        return "\n".join(linhas)

    def _validar(self, classe: str, candidatos: list) -> bool:
        classe = str(classe).zfill(6) if str(classe).isdigit() else str(classe)
        if str(classe).upper() == "REVISAR":
            return True
        if classe not in classes_vigentes():
            return False
        return classe in (set(candidatos) | {"000001"})

    def decidir_produto(self, **kw) -> Optional[RespostaJuiz]:
        prompt = self.montar_prompt(**kw)
        chave = _hash(prompt, self.modelo)
        if chave in self.cache:
            return RespostaJuiz(**self.cache[chave], cache_hit=True)
        if not self.cliente.habilitado:
            return None
        bruto = self.cliente.chat_json(prompt)
        if not bruto:
            return None
        classe = str(bruto.get("cClassTrib", "")).strip()
        if not self._validar(classe, kw.get("candidatos", [])):
            logger.warning("juiz devolveu classe invalida %r; rejeitada", classe)
            return None
        classe = str(classe).zfill(6) if classe.isdigit() else classe.upper()
        try:
            conf = float(bruto.get("confianca", 0.6))
        except (TypeError, ValueError):
            conf = 0.6
        conf = max(0.0, min(1.0, conf))
        resp = RespostaJuiz(
            cClassTrib=classe,
            confianca=conf,
            justificativa=str(bruto.get("justificativa", ""))[:300],
            fonte="llm",
            cache_hit=False,
        )
        self.cache[chave] = {
            "cClassTrib": resp.cClassTrib,
            "confianca": resp.confianca,
            "justificativa": resp.justificativa,
            "fonte": resp.fonte,
        }
        return resp

    def salvar_cache(self) -> None:
        _salvar_cache(self.cache)


# --------------------------------------------------------------------------- #
# Orquestracao da fila
# --------------------------------------------------------------------------- #


@dataclass
class ResultadoFila:
    n_fila: int = 0
    n_llm: int = 0
    n_revisar: int = 0
    n_regra: int = 0
    chamadas: int = 0
    tokens_entrada: int = 0
    tokens_saida: int = 0
    habilitado: bool = False
    auditoria: list = field(default_factory=list)


def resolver_fila(catalogo, cliente: Optional[LlmCliente] = None, top5_fn=None) -> tuple:
    """Resolve a fila de produtos ambiguos do catalogo.

    Devolve (catalogo_atualizado, ResultadoFila).
    """
    from .classificar import limiar_revisar

    top5_fn = top5_fn or busca_top5
    cliente = cliente or LlmCliente()
    juiz = LlmJuiz(cliente)
    comportamento = str(carregar_config().get("comportamento_sem_llm", "usar_regra"))
    limiar = limiar_revisar()

    cat = catalogo.copy()
    res = ResultadoFila(habilitado=cliente.habilitado)

    fila = cat.index[cat["ambiguo"].astype(bool)].tolist()
    res.n_fila = len(fila)

    for idx in fila:
        r = cat.loc[idx]
        candidatos = [c for c in str(r.get("candidatos_classe", "")).split(";") if c]
        t5 = top5_fn(str(r.get("xProd_norm", "")), k=5, classes_filtro=candidatos or None)
        classe_regra = str(r["cClassTrib"])

        resp = juiz.decidir_produto(
            xprod_norm=str(r.get("xProd_norm", "")),
            ncm=str(r["NCM"]),
            cfop="",
            cnae=str(r.get("cnae", "")),
            classe_tentativa=classe_regra,
            candidatos=candidatos,
            top5=t5,
            eliminados=str(r.get("eliminados", "")),
            evidencia=str(r.get("evidencia_mapa", "")),
        )

        linha_aud = {
            "cProd": r["cProd"],
            "NCM": r["NCM"],
            "xProd_norm": r.get("xProd_norm", ""),
            "classe_regra": classe_regra,
            "candidatos": ";".join(candidatos),
            "eliminados": r.get("eliminados", ""),
            "top5_bm25": " | ".join(f"{e['cClassTrib']}:{e['exemplo']}" for e in t5),
            "fonte_origem": r.get("fonte", ""),
        }

        if resp is not None and resp.cClassTrib.upper() == "REVISAR":
            conf = min(resp.confianca, limiar - 0.01)
            cat.at[idx, "confianca"] = round(conf, 2)
            cat.at[idx, "status"] = "REVISAR"
            cat.at[idx, "metodo"] = "llm_revisar"
            cat.at[idx, "fonte"] = f"{r.get('fonte','')} | JUIZ LLM (REVISAR): {resp.justificativa}"
            res.n_revisar += 1
            linha_aud.update(
                {
                    "decisao_final": classe_regra,
                    "classe_llm": "REVISAR",
                    "confianca": round(conf, 2),
                    "metodo": "llm_revisar",
                    "justificativa": resp.justificativa,
                    "cache_hit": resp.cache_hit,
                }
            )
        elif resp is not None:
            conf = min(resp.confianca, LIMIAR_CONF_LLM)
            cat.at[idx, "cClassTrib"] = resp.cClassTrib
            cat.at[idx, "confianca"] = round(conf, 2)
            cat.at[idx, "status"] = "REVISAR" if conf < limiar else "CLASSIFICADO"
            cat.at[idx, "metodo"] = "llm"
            cat.at[idx, "fonte"] = f"JUIZ LLM: {resp.justificativa} | regra: {r.get('fonte','')}"
            res.n_llm += 1
            linha_aud.update(
                {
                    "decisao_final": resp.cClassTrib,
                    "classe_llm": resp.cClassTrib,
                    "confianca": round(conf, 2),
                    "metodo": "llm",
                    "justificativa": resp.justificativa,
                    "cache_hit": resp.cache_hit,
                }
            )
        else:
            # sem LLM (dry-run) ou resposta rejeitada
            if comportamento == "revisar" and cliente.habilitado:
                cat.at[idx, "status"] = "REVISAR"
                cat.at[idx, "confianca"] = round(min(float(r.get("confianca", 0.72)), limiar - 0.01), 2)
                cat.at[idx, "metodo"] = "llm_rejeitado"
            else:
                cat.at[idx, "metodo"] = "regra_ambiguo"
            res.n_regra += 1
            linha_aud.update(
                {
                    "decisao_final": classe_regra,
                    "classe_llm": "",
                    "confianca": float(cat.at[idx, "confianca"]),
                    "metodo": cat.at[idx, "metodo"],
                    "justificativa": "LLM indisponivel/rejeitado; mantida a decisao deterministica",
                    "cache_hit": False,
                }
            )
        res.auditoria.append(linha_aud)

    juiz.salvar_cache()
    cliente.salvar_uso()
    uso = cliente.uso
    res.chamadas = int(uso.get("chamadas", 0))
    res.tokens_entrada = int(uso.get("tokens_entrada", 0))
    res.tokens_saida = int(uso.get("tokens_saida", 0))
    return cat, res


if __name__ == "__main__":
    from .classificar import construir_catalogo
    from .extrair import extrair_tudo
    from .io_dados import cadastro as carregar_cadastro

    itens, _ = extrair_tudo()
    cad = carregar_cadastro()
    cat = construir_catalogo(itens, cad)
    cat, res = resolver_fila(cat)
    print("habilitado:", res.habilitado, "| fila:", res.n_fila)
    print("llm:", res.n_llm, "| revisar:", res.n_revisar, "| regra:", res.n_regra)
    print("chamadas:", res.chamadas, "tokens:", res.tokens_entrada, "/", res.tokens_saida)
