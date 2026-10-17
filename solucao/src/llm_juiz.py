"""Juiz LLM cirurgico (Abordagem B) - so entra no que sobrou da cascata.

P5: RESERVA PARA EXPANSAO FUTURA. Este modulo nao e acionado no pipeline atual
(a cascata deterministica resolve as 128 descricoes com 0 tokens). Mantido para
produtos novos que a cascata nao resolver; ver DECISOES.md secao 9.

Neste dataset a cascata resolve as 128 descricoes com 0 chamadas (eficiencia
maxima, <= 3 chamadas no orcamento). O modulo fica pronto para produtos novos:

  - chamado por descricao (nunca por item) e em lote;
  - candidatos restritos (classes do mapa/familia + 000001);
  - cache em disco por sha256 do prompt;
  - validacao obrigatoria contra a tabela oficial (classe vigente, CST valido).
  - sem API key configurada, devolve None (o chamador mantem a decisao da regra).

Uso: `juiz = LlmJuiz(); juiz.decidir(descricao, ncm, cfop, candidatos)`.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Optional

from .caminhos import OUT_DIR
from .io_dados import classes_vigentes

CACHE_PATH = OUT_DIR / "cache_llm.json"
USO_PATH = OUT_DIR / "uso_tokens.json"


@dataclass
class RespostaLLM:
    cClassTrib: str
    confianca: float
    justificativa: str
    fonte: str = "llm"


class LlmJuiz:
    def __init__(self, modelo: str = "gpt-4o-mini", api_key: Optional[str] = None):
        self.modelo = modelo
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._cache = self._carregar_cache()
        self._uso = {"chamadas": 0, "tokens_entrada": 0, "tokens_saida": 0}

    # ------------------------------------------------------------------ #
    @staticmethod
    def _carregar_cache() -> dict:
        if CACHE_PATH.exists():
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        return {}

    def _salvar_cache(self) -> None:
        CACHE_PATH.write_text(json.dumps(self._cache, ensure_ascii=False, indent=1), encoding="utf-8")

    @staticmethod
    def _hash(prompt: str) -> str:
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    def _montar_prompt(self, descricao, ncm, cfop, cnae, candidatos) -> str:
        linhas = [f"Produto: \"{descricao}\" | NCM {ncm} | CFOP {cfop} | emitente CNAE {cnae}",
                  "Candidatos (so estes, ou 000001):"]
        for c in candidatos:
            linhas.append(f"  [{c['cClassTrib']}] {c['descricao']}")
        linhas.append("  [000001] Regime padrao (produto nao listado em anexo)")
        linhas.append('Responda JSON: {"cClassTrib","confianca","justificativa"}')
        return "\n".join(linhas)

    def _validar(self, classe: str, candidatos: list) -> bool:
        if classe not in classes_vigentes():
            return False
        validas = {c["cClassTrib"] for c in candidatos} | {"000001"}
        return classe in validas

    # ------------------------------------------------------------------ #
    def decidir(self, descricao, ncm, cfop, cnae, candidatos) -> Optional[RespostaLLM]:
        prompt = self._montar_prompt(descricao, ncm, cfop, cnae, candidatos)
        chave = self._hash(prompt)
        if chave in self._cache:
            dados = self._cache[chave]
            return RespostaLLM(**dados)
        if not self.api_key:
            return None  # sem credencial: mantem a decisao deterministica
        try:
            resposta = self._chamar_api(prompt)  # pragma: no cover - requer rede
        except Exception:  # noqa: BLE001
            return None
        if not resposta or not self._validar(resposta["cClassTrib"], candidatos):
            return None
        self._cache[chave] = resposta
        self._salvar_cache()
        USO_PATH.write_text(json.dumps(self._uso, ensure_ascii=False), encoding="utf-8")
        return RespostaLLM(**resposta)

    def _chamar_api(self, prompt: str) -> Optional[dict]:  # pragma: no cover
        """Chamada real (OpenAI/Anthropic). Mantida isolada para teste/dry-run."""
        import urllib.request

        corpo = json.dumps(
            {
                "model": self.modelo,
                "temperature": 0,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
            }
        ).encode()
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=corpo,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            dados = json.loads(resp.read().decode())
        self._uso["chamadas"] += 1
        self._uso["tokens_entrada"] += dados.get("usage", {}).get("prompt_tokens", 0)
        self._uso["tokens_saida"] += dados.get("usage", {}).get("completion_tokens", 0)
        return json.loads(dados["choices"][0]["message"]["content"])


if __name__ == "__main__":
    j = LlmJuiz()
    print("api_key configurada:", bool(j.api_key), "| cache:", len(j._cache))
