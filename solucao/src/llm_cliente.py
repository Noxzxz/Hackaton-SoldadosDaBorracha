"""Cliente LLM provedor-agnostico (compativel com a API OpenAI).

Toda a solucao conversa com o modelo por aqui. O modelo e o endpoint sao
definidos em `config/llm.yaml` -- nenhum nome de modelo ou chave fica no codigo.

- Provedor default: OpenCode Go (`https://opencode.ai/inference/go/openai/v1`),
  modelo `deepseek-v4.1-flash`.
- Credencial: variavel de ambiente `api_key_env`; se ausente, le o
  `auth.json` do opencode (sem gravar segredo no repositorio).
- Sem modelo/chave: `habilitado == False` e o pipeline cai em dry-run.

Sem dependencias novas: usa apenas `urllib` da biblioteca padrao.
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml

from .caminhos import CONFIG_DIR, OUT_DIR

logger = logging.getLogger(__name__)

USO_PATH = OUT_DIR / "uso_tokens.json"
AUTH_OPENCODE = Path.home() / ".local" / "share" / "opencode" / "auth.json"


@lru_cache(maxsize=None)
def carregar_config() -> dict:
    caminho = CONFIG_DIR / "llm.yaml"
    if not caminho.exists():
        return {}
    with open(caminho, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def recarregar_config() -> None:
    carregar_config.cache_clear()


def _chave_do_auth_opencode(provider: str) -> str:
    try:
        if AUTH_OPENCODE.exists():
            dados = json.loads(AUTH_OPENCODE.read_text(encoding="utf-8"))
            return str(dados.get(provider, {}).get("key", "") or "")
    except Exception as e:  # noqa: BLE001
        logger.warning("nao foi possivel ler auth.json do opencode (%s)", e)
    return ""


def resolver_chave(cfg: dict) -> str:
    """Resolve a chave nesta precedencia:

    1. variavel de ambiente `api_key_env`;
    2. arquivo `config/<api_key_arquivo>` (gitignored);
    3. `auth.json` do opencode (provider `provider_auth`).
    """
    nome_env = str(cfg.get("api_key_env", "") or "")
    if nome_env:
        chave = os.environ.get(nome_env, "")
        if chave:
            return chave
    arquivo = str(cfg.get("api_key_arquivo", "") or "")
    if arquivo:
        caminho = CONFIG_DIR / arquivo
        try:
            if caminho.exists():
                chave = caminho.read_text(encoding="utf-8").strip()
                if chave:
                    return chave
        except OSError as e:  # noqa: BLE001
            logger.warning("nao foi possivel ler %s (%s)", caminho, e)
    if cfg.get("auth_json_opencode", True):
        return _chave_do_auth_opencode(str(cfg.get("provider_auth", "opencode-go")))
    return ""


class LlmCliente:
    def __init__(self, cfg: Optional[dict] = None):
        self.cfg = dict(cfg if cfg is not None else carregar_config())
        self.modelo = str(self.cfg.get("modelo", "") or "")
        self.base_url = str(
            self.cfg.get("base_url", "") or "https://api.openai.com/v1"
        ).rstrip("/")
        self.api_key = resolver_chave(self.cfg)
        self.temperatura = float(self.cfg.get("temperatura", 0) or 0)
        self.max_tokens = int(self.cfg.get("max_tokens", 700) or 700)
        self.timeout = int(self.cfg.get("timeout_s", 60) or 60)
        self.saida_json = bool(self.cfg.get("saida_json_obrigatoria", True))
        self.user_agent = str(
            self.cfg.get("user_agent", "meridional-hackathon/1.0")
        )
        self.session_id = str(self.cfg.get("session_id", "meridional-hackathon"))
        self._uso = {
            "modelo": self.modelo,
            "base_url": self.base_url,
            "chamadas": 0,
            "tokens_entrada": 0,
            "tokens_saida": 0,
        }

    # ------------------------------------------------------------------ #
    @property
    def habilitado(self) -> bool:
        return bool(self.modelo and self.api_key)

    @property
    def uso(self) -> dict:
        return dict(self._uso)

    def salvar_uso(self) -> None:
        dados = dict(self._uso)
        dados["data"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        try:
            USO_PATH.write_text(
                json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8"
            )
        except OSError as e:  # noqa: BLE001
            logger.warning("nao foi possivel salvar uso de tokens (%s)", e)

    # ------------------------------------------------------------------ #
    def chat_json(self, prompt: str, system: str = "") -> Optional[dict]:
        """Chama chat/completions e devolve o JSON da resposta.

        Devolve None em qualquer falha (timeout, rede, JSON invalido, HTTP).
        NUNCA lanca excecao para o chamador.
        """
        if not self.habilitado:
            return None
        corpo: dict = {
            "model": self.modelo,
            "temperature": self.temperatura,
            "max_tokens": self.max_tokens,
            "messages": [],
        }
        if system:
            corpo["messages"].append({"role": "system", "content": system})
        corpo["messages"].append({"role": "user", "content": prompt})
        if self.saida_json:
            corpo["response_format"] = {"type": "json_object"}

        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(corpo).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": self.user_agent,
                "x-opencode-session": self.session_id,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                dados = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            logger.warning("chamada LLM falhou (%s)", e)
            return None

        uso = dados.get("usage", {}) or {}
        self._uso["chamadas"] += 1
        self._uso["tokens_entrada"] += int(uso.get("prompt_tokens", 0) or 0)
        self._uso["tokens_saida"] += int(uso.get("completion_tokens", 0) or 0)

        try:
            conteudo = dados["choices"][0]["message"]["content"]
            return json.loads(conteudo)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as e:
            logger.warning("resposta LLM nao e JSON valido (%s)", e)
            return None


def cliente_padrao() -> LlmCliente:
    return LlmCliente()


if __name__ == "__main__":
    c = LlmCliente()
    print("modelo:", c.modelo)
    print("base_url:", c.base_url)
    print("habilitado:", c.habilitado, "| chave presente:", bool(c.api_key))
