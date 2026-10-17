# Plano de implementação — roteiro de mudanças com LLM obrigatório

Plano agregado e detalhado de **como implementar** as modificações do
`Roteiro de mudanças`, ajustado à nova premissa: **o uso de LLM/agente é
obrigatório** no hackathon. O desenho garante que, no final, **basta preencher
um único campo de configuração (o modelo + a chave)** para tudo rodar.

> **Princípios do desenho**
> 1. **LLM cirúrgico, não geral:** chamadas por **produto distinto ambíguo**
>    (~40–51), nunca por item (15.000). Estimativa: **≤ 51 chamadas**.
> 2. **Regras primeiro:** NCM, vigência, permissão, condição, exceção e
>    operação resolvem sozinhos sempre que possível; o LLM só julga o que sobrar.
> 3. **LLM nunca inventa fundamento:** só pode escolher ID entre os candidatos
>    fornecidos (ou `REVISAR`); resposta fora da lista é **rejeitada**.
> 4. **Determinístico por fora:** temperatura 0, cache por SHA-256, log de uso;
>    sem modelo configurado o pipeline roda em *dry-run* (ambíguos → `REVISAR`).
> 5. **Fatos intocáveis:** continua sem agregação/soma de itens; `(chave, nItem)`
>    preservado; `Decimal` no dinheiro.

---

## 0. O que muda em relação ao roteiro original

| Roteiro dizia | Agora (LLM obrigatório) |
|---|---|
| Opção A/B/C; recomendava A sem LLM | **Opção B cirúrgica obrigatória** (Fase 3 do roteiro), com *dry-run* sem modelo |
| `llm_juiz.py` como reserva | Vira **etapa ativa** do pipeline (`rodar_tudo.py --llm`, default ligado) |
| Pitch "0 tokens" | Pitch novo: **"51 chamadas cirúrgicas, validadas e cacheadas"** |
| Fase 2.1 trocar chave do catálogo | **Mantida `(cProd, NCM)`** (1:1 nos dados; 95 produtos = regressão). A evidência nova fica na trilha/auditoria |

Itens do roteiro **já resolvidos** (não reimplantar): 1.1 (`python -m src.simular`
roda), 1.2 (447×256 já distinto), 2.4 (0 fontes `LNone`), 6-slider (`vProd_repasse`
já é usado), 6-equilíbrio (89/89 vendidos com compra — o roteiro estava errado).

---

## 1. Ponto único de encaixe do modelo (o que a equipe preenche depois)

Novo arquivo **`config/llm.yaml`** — a única coisa a configurar no final:

```yaml
# PLUG POINT: preencha apenas isto na entrega
provedor: openai_compativel      # openai_compativel (serve p/ OpenAI, Ollama, vLLM, LiteLLM)
base_url: ""                    # vazio = https://api.openai.com/v1 ; ou http://localhost:11434/v1
modelo: ""                      # ex.: "gpt-4o-mini", "llama3.1:8b", "claude-...-via-proxy"
api_key_env: OPENAI_API_KEY     # nome da variável de ambiente com a chave

# parâmetros fixos (não mexer)
temperatura: 0
max_tokens: 600
timeout_s: 40
usar_embeddings: false         # true se o endpoint tiver /v1/embeddings
saida_json_obrigatoria: true
```

- **Sem `modelo`/chave** → *dry-run*: pipeline completo, ambíguos caem em `REVISAR`
  com aviso `LLM indisponível` (não trava a entrega).
- **Com `modelo`/chave** → juiz roda a fila ambígua automaticamente.
- Nenhuma outra parte do código menciona modelo/chave: tudo passa por
  `LlmCliente` (abaixo). Trocar de fornecedor = trocar 2 linhas deste YAML.

---

## 2. Arquitetura final do pipeline

```
pacote-times/dados (XLSX/DANFEs)
        │
        ▼
extrair (pdfplumber, 1.387 notas, gate 1.387/1.387, cache parquet)
        │
        ▼
avaliar_mapa  ◄── NOVO: vigente + permissao + condicao + excecao + item_do_anexo + precedência
        │            (consome config/condicoes.yaml e config/excecoes.yaml — hoje mortos)
        ▼
catálogo (cProd × NCM = 95) ──► resolvidos por regra (conf. 0.95/0.88/…)
        │
        ├── ambíguos (>1 classe permitida pós-regras)  → Fila LLM (~40–51)
        │        │
        │        ▼
        │   busca top-5 (BM25 local sobre exemplos_por_classe)   ◄── NOVO src/busca.py
        │        │
        │        ▼
        │   LlmJuiz (lote por produto distinto; JSON estruturado;
        │   validação contra candidatos; cache; uso de tokens)   ◄── rework src/llm_juiz.py
        │        │
        │        ▼  rejeitado/indisponível/inválido → REVISAR (nunca classe inventada)
        ▼
classificar_itens (OP-01/02/03 antes do produto) ──► 15.000 itens
        │
        ▼
simular (Decimal; hoje/2027/2033) ──► exportar ──► NOME-DA-EQUIPE/{itens_classificados.csv, simulacao.json}
        │
        ├── out/auditoria_ambiguos.csv   (os 51: candidatos, condição, decisão, fonte)
        ├── out/auditoria_llm.json      (prompts, respostas, cache, tokens)
        └── out/transicao_2029_2032.parquet  (bônus, fora do simulacao.json)
```

---

## 3. Especificação módulo a módulo

### 3.1 `src/llm_cliente.py` (NOVO) — cliente provedor-agnóstico

Sem dependências novas (usa `urllib`, como o `llm_juiz.py` atual).

```python
class LlmCliente:
    """Cliente chat-completions compatível com OpenAI (OpenAI/Ollama/vLLM/LiteLLM)."""
    def __init__(self, cfg: dict = None): ...      # lê config/llm.yaml
    @property
    def habilitado(self) -> bool: ...             # modelo+chave presentes
    def chat_json(self, prompt: str, schema_hint: str) -> dict | None:
        """POST /chat/completions; temperature=0; response_format=json_object.
        Timeout/rede/JSON inválido -> None (chamador decide fallback)."""
    def embed(self, textos: list[str]) -> list[list[float]] | None:
        """Opcional (usar_embeddings=true) -> /v1/embeddings; senão None."""
```

Regras: nunca logar a chave; registro de uso em `out/uso_tokens.json`
(`modelo`, `chamadas`, `tokens_entrada`, `tokens_saida`, `data`, hash do prompt).

### 3.2 `src/busca.py` (NOVO) — top-5 BM25 local, sem dependências

- Índice BM25 simples (k1=1,5; b=0,75) sobre `exemplos_por_classe.xlsx`
  (tokenização: minúsculas, sem acento, bigramas opcional).
- `top5(descricao_normalizada, ncm) -> list[{classe, exemplo, score}]`.
- Determinístico (mesmo índice → mesmo top-5). Serve para dois fins:
  1. enriquecer o prompt do juiz com exemplos oficiais;
  2. registrar na auditoria por que o BM25 não fechou sozinho.
- `usar_embeddings: true` → recuperação híbrida (média de ranks BM25+embedding),
  senão só BM25. Nada muda na assinatura.

### 3.3 `src/llm_juiz.py` (REWORK) — o agente obrigatório

Mantém o esqueleto atual (cache SHA-256, validação contra `classes_vigentes()`)
e passa a:

1. **Entrada:** um produto ambíguo (não um item): `decidir_produto(cProd, NCM,
   xProd_norm, cnae, cfop_típico, candidatos, top5)` — chamado **uma vez por
   produto distinto** da fila, nunca por item.
2. **Prompt (modelo fixo, template versionado em `config/prompt_juiz.yaml`):**

```
Você é auditor fiscal da LC 214/2025. Escolha o cClassTrib correto.
Produto: "ARROZ..." | NCM 10063021 | CFOP típico 5102 | emitente CNAE 4639-1/01
Candidatos VÁLIDOS (somente estes IDs, ou REVISAR):
  [200003] Anexo I — cesta básica — condição: DESTINADOS À ALIMENTAÇÃO HUMANA (satisfeita: atacadista de alimentos)
  [000001] Regime padrão
Exceções aplicadas: "Produtos relacionados no Anexo I" remove [200034] quando existe [200003]
Top-5 exemplos oficiais (BM25): [200003] "arroz polido..."; ...
Responda SOMENTE JSON:
{"cClassTrib":"...","confianca":0.0-1.0,"justificativa":"...","fonte_ids":["mapa:NCM=...;classe=...;cond=..."]}
Sem evidência suficiente -> {"cClassTrib":"REVISAR","confianca":<0.5,"justificativa":"..."}
```

3. **Validação rígida (rejeita e cai para `REVISAR`):**
   - classe ∉ candidatos ∪ {`000001`, `REVISAR`} → rejeitada;
   - `fonte_ids` vazio ou inexistente no prompt → rejeitada;
   - `confianca` fora de [0,1] → clamp; se < `limiar_revisar` (0,70) → `REVISAR`;
   - JSON malformado/timeout/sem chave → `REVISAR` (nunca classe inventada).
4. **Saída:** `RespostaLLM(cClassTrib, confianca, justificativa, fonte="llm+mapa")`;
   confiança final = `min(confianca_llm, 0.90)` (o LLM não supera o mapa exato).
5. **Cache:** `out/cache_llm.json` por `sha256(prompt + modelo)` — rerun = 0 chamadas.
6. **Uso:** `out/uso_tokens.json` somado por execução (número para o pitch).

### 3.4 `src/classificar.py` — `avaliar_mapa()` (NOVO) e cascata revisada

```python
def avaliar_mapa(ncm: str, contexto: dict) -> AvaliacaoMapa:
    """Filtra candidatos do mapa: vigente=='sim' AND permissao=='PERMITIDO';
    aplica condicoes.yaml (predicados por string exata, _default=false);
    aplica excecoes.yaml (remove_classe quando_existe) e item_do_anexo;
    devolve (candidatos, eliminados[com motivo], precedencia_anexo)."""
```

- **Consome** `condicoes.yaml`/`excecoes.yaml` (hoje mortos) e passa a usar a
  coluna `vigente` (hoje não filtrada — 0 linhas `vigente!=sim`, mas o filtro
  passa a existir).
- `classificar_produto()` passa a chamar `avaliar_mapa` no lugar do
  `candidatos()` cru; classes preferidas por família continuam como desempate
  **antes** do LLM (se a família + condições fecharem 1 classe, sem chamada).
- Ambíguo persistente → entra na `fila_llm` com os candidatos pós-filtro.
- `regras_operacao.yaml`: ou passa a ser lido em `classificar_itens` (OP-01/02/03
  data-driven) ou é removido — decidir na implementação (evitar config morta).

### 3.5 Auditoria dos ambíguos (Fase 2.3 do roteiro)

`out/auditoria_ambiguos.csv` — uma linha por produto ambíguo:

`cProd, NCM, xProd_norm, candidatos(exatos), condicoes, excecoes, top5_bm25,
decisao(regra|llm|REVISAR), confianca, justificativa, fonte_ids, cache_hit`

- Gerada no `exportar_tudo()` a partir do catálogo + fila; alimenta o painel.
- **Não eleva confiança por repetição:** 1 produto = 1 decisão; a réplica em
  ~158 itens não conta como validação (regra do roteiro mantida).

### 3.6 Fase 4 — CNAE, `REVISAR` e confiança

- **Fallback CNAE "contextual":** na branch `DESCRICAO_POBRE`, o CNAE passa a
  **verificar** aderência (fornecedores de plásticos/embalagens → família
  `REGIME_PADRAO` plausível) antes de aceitar `000001`; sem aderência →
  `REVISAR` com confiança 0,55. Deixa de ser decorativo.
- **Aba "Fila de revisão" no painel:** itens/produtos `REVISAR` (ou métrica
  "0 pendentes, 51 resolvidos pelo juiz") com candidatos e motivo — caminho
  humano auditável.
- **Confiança:** continua derivada do método + estabilidade (`mutacao.py`);
  decisões LLM entram com confiança limitada (≤0,90) e só quando ≥0,70 viram
  `CLASSIFICADO`. Calibração real só com gabarito (não alegar).

### 3.7 Fase 1.3 — `scripts/empacotar_entrega.py` (NOVO)

- Lê `solucao/saida/` → cria `NOME-DA-EQUIPE/` com **exatamente** os 2 arquivos;
- roda o validador oficial apontando para a pasta final;
- imprime `FORMATO OK` ou falha com diff.

### 3.8 Fase 5.3 — `src/transicao.py` (NOVO, bônus)

- Consome `transicao_icms_bonus` (2029: 90%, 2030: 80%, 2031: 70%, 2032: 60%);
- saída **separada**: `out/transicao_2029_2032.parquet` + aba no painel
  (substitui a interpolação linear, que passa a ser rotulada "ilustrativa");
- **não toca** no `simulacao.json` (validador exige 3 cenários).

### 3.9 Painel — correções

- Nova aba **"Auditoria LLM"**: fila, prompts, justificativas, cache, tokens.
- `painel.py:109`: trocar `ganha` por "diferença simulada entre políticas"
  (alinhado com `RESULTADOS.md`; sem alegação de caixa/lucro).

### 3.10 `rodar_tudo.py`

- Flag `--llm` (default: **on** se cliente habilitado): imprime
  `[x/7] fila LLM: N produtos, M chamadas, K tokens`; sem modelo →
  `dry-run: N ambíguos -> REVISAR`.

---

## 4. Fluxo de execução (duas situações)

**Dry-run (sem modelo, para dev/testes):**
```
python scripts/rodar_tudo.py --reparse --testes
# ambíguos -> REVISAR; tudo mais idêntico; pytest verde (testes com cliente falso)
```

**Com modelo (entrega): só preencher `config/llm.yaml` (`modelo`, `base_url`,
`api_key_env`) + exportar a chave; então:**
```
python scripts/rodar_tudo.py --reparse --llm --testes
python scripts/validar_entrega.py
python scripts/empacotar_entrega.py          # cria NOME-DA-EQUIPE/ e roda validador oficial
```

---

## 5. Testes (novos; atuais 28 continuam)

| Teste | Garante |
|---|---|
| `test_avaliar_mapa.py` | cada `condicao`/`excecao` presente no case; PERMITIDO×VEDADO; vigente; precedência Anexo I>VII |
| `test_llm_juiz.py` (cliente falso via monkeypatch) | resposta fora dos candidatos é rejeitada; sem chave/falha/JSON ruim → `REVISAR`; cache hit não chama API; confiança ≤0,90 |
| `test_busca.py` | top-5 determinístico; ordem estável |
| `test_fila_llm.py` | 1 chamada por produto distinto (51 produtos ≠ 51×158 chamadas); réplica não eleva confiança |
| `test_dry_run.py` | sem modelo: pipeline completo, ambíguos → `REVISAR`, entregáveis válidos |
| `test_transicao.py` | frações 90/80/70/60% coerentes com 2027 e 2033 |
| snapshot `test_distribuicao_classificacao` | **regenerar** após 3.4: rodar, comparar, atualizar contadores esperados e documentar o diff em `DECISOES.md` |

---

## 6. Ordem de implementação e critérios de aceite

| # | Etapa | Entrega | Aceite | Risco |
|---|---|---|---|---|
| 1 | `empacotar_entrega.py` (1.3) | pasta final + validador | `FORMATO OK`, exatamente 2 arquivos | trivial |
| 2 | `avaliar_mapa()` + consumo dos YAMLs (2.2) | condições/exceções ativas | cada classe final permitida+vigente+com evidência; snapshot regenerado e diff documentado | **médio** (pode mudar distribuição/números) |
| 3 | `auditoria_ambiguos.csv` (2.3) | tabela dos 51 | toda decisão com candidatos+motivo+fonte | baixo |
| 4 | `llm_cliente.py` + `busca.py` | plug point + top-5 | dry-run sem chave; BM25 determinístico | baixo |
| 5 | rework `llm_juiz.py` + fila (3) | juiz obrigatório | ≤51 chamadas; rejeição fora da lista; cache; `uso_tokens.json` | médio |
| 6 | CNAE contextual + aba revisão (4) | política aplicada | CNAE verificado; `REVISAR` audável | baixo |
| 7 | `transicao.py` + painel + narrativa (5.3/6) | bônus + termos | 3 cenários intactos no JSON; sem "ganha R$ X" | baixo |
| 8 | code freeze | tudo acima | `pytest -q` verde + 2 validadores + painel no notebook da banca | — |

**Se o prazo apertar:** ordem 1→2→3→5 já cumpre o essencial (LLM obrigatório +
condições/exceções + auditoria); 4 pode rodar só com BM25; 6/7 são refinamento.

---

## 7. Riscos e mitigação

1. **Mudança de distribuição/classes** ao ativar condições/exceções (quebra
   snapshot e muda o −R$ 67 mi) → rodar 2 antes de tudo, documentar diff em
   `DECISOES.md`, regenerar entregáveis e revalidar.
2. **LLM não determinístico** → temperatura 0, cache, validação de candidatos,
   `REVISAR` como saída segura; o que vale é a decisão auditável, não o token.
3. **Custo/latência** → ≤51 chamadas × ~600 tokens; rerun = 0 (cache).
4. **Alegar calibração** → confiança interna ≠ acurácia; só afirmar o que é
   mensurável (reconciliação 1.387/1.387, templates 3/4, auditoria 51).
5. **Dependência de rede na demo** → cache garantido pelo `--reparse` prévio +
   dry-run de emergência documentado.

---

## 8. Checklist final (code freeze)

- [ ] `config/llm.yaml` com modelo preenchido; chave só em variável de ambiente
- [ ] `rodar_tudo.py --reparse --llm --testes` verde com fila LLM executada
- [ ] `out/auditoria_ambiguos.csv` com os ~51 e decisão por candidato
- [ ] `out/uso_tokens.json` com contagem real de chamadas/tokens
- [ ] condições/exceções/vigência/permissão aplicadas e testadas
- [ ] snapshots regenerados; diff documentado em `DECISOES.md`
- [ ] painel sem "ganha R$ X"; aba Auditoria LLM funcionando
- [ ] `NOME-DA-EQUIPE/` com exatamente 2 arquivos; validador oficial `FORMATO OK`
- [ ] pitch: "regras resolvem 44/95; juiz LLM decide ~51 com validação e cache;
      15.000 itens sem chamada por item"
