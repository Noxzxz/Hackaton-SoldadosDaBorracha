# Uso do LLM no projeto — explicação ponta a ponta

**Resposta curta:** sim. O LLM **não** classifica os 15.000 itens. Ele é acionado
apenas como **juiz de exceção**: decide somente os **produtos** que a cascata
determinística **não consegue fechar sozinha** (mais de uma classe permitida, ou
uma condição do mapa que não está mapeada). Todo o resto — a esmagadora maioria —
é resolvido por regras, sem nenhuma chamada ao modelo.

Neste dataset: **95 produtos → 10 vão ao juiz → 10 chamadas de LLM**, para
15.000 itens. Ou seja, ~0,07% dos itens dependem do modelo.

---

## 1. Princípio: regras primeiro, LLM só na sobra

```
                        ┌─────────────────────────────────────────┐
DANFE (PDF)  ──►  extrai itens  ──►  catalogo (95 produtos únicos) │
                        └─────────────────────────────────────────┘
                                          │
                                          ▼
        ┌─────────── CLASSIFICAÇÃO DETERMINÍSTICA (0 tokens) ───────────┐
        │ 1. Regras de operação: CFOP 5910→410001, 7102/exterior→410004, │
        │    dispositivo médico + órgão público→200005                   │
        │ 2. avaliar_mapa(): vigente + PERMITIDO + condição + exceção    │
        │ 3. Desempate por família (config/familias.yaml)                │
        │ 4. Descrição pobre → CNAE (camada 4)                           │
        │ 5. Nada defensável → 000001                                    │
        └───────────────────────────────────────────────────────────────┘
                                          │
                     resultado é UMA classe? ─── sim ──► pronto (metodo="regra")
                                          │
                                          não  (2+ classes válidas, ou condição não mapeada)
                                          ▼
                    ┌─────────── FILA DO JUIZ LLM ───────────┐
                    │  1 chamada por PRODUTO distinto         │
                    │  candidatos + top-5 BM25 + regras já     │
                    │  eliminadas → resposta JSON validada     │
                    └──────────────────────────────────────────┘
```

O gatilho exato está em `src/classificar.py:397`:

```python
ambiguo = len(classes) > 1 or aval.ambiguidade_condicao
```

- `len(classes) > 1`: **sobrou mais de uma classe permitida** depois de aplicar
  vigência, permissão, condição e exceção. O mapa sozinho não decide.
- `ambiguidade_condicao`: apareceu uma **condição do mapa que não está mapeada**
  em `config/condicoes.yaml`. Em vez de presumir "aplica/não aplica", o produto
  é marcado como ambíguo e encaminhado ao juiz.

Os produtos do catálogo com `ambiguo = True` formam a fila (`llm_juiz.py:207`).

---

## 2. Quando o LLM **NÃO** é chamado

A grande maioria. O produto é resolvido 100% por regra quando:

| Situação | Regra determinística | Método |
|---|---|---|
| Bonificação no documento | CFOP 5910 → `410001` | `OP-01` |
| Exportação | CFOP 7102 / destinatário exterior → `410004` | `OP-02` |
| Dispositivo médico a órgão público | → `200005` | `OP-03` |
| NCM com **uma única** classe permitida | mapa → classe | `regra` |
| NCM com duas classes, mas uma eliminada por **condição** | `condicoes.yaml` decide | `regra` |
| Classes com **exceção/precedência** (ex.: Anexo I remove Anexo VII) | `excecoes.yaml` decide | `regra` |
| Descrição pobre resolvida por CNAE | camada 4 → `000001` | `regra` |
| NCM fora do mapa | regra 3 → `000001` | `regra` |

Em nenhum desses casos o cliente do modelo é instanciado para decidir — a fila
fica vazia para o produto.

---

## 3. Quando o LLM **É** chamado (o fluxo do juiz)

### 3.1 Um produto entra na fila
Ex.: um **dispositivo médico** cujo NCM tem duas classes permitidas no mapa —
`200005` (dispositivo médico do Anexo IV **vendido a órgão público**) e `200030`
(dispositivo médico do Anexo IV, operação comum). O mapa não decide sozinho
porque depende da **operação/destino**.

### 3.2 Monta-se o prompt (`llm_juiz.py:montar_prompt`)
O prompt é fechado: o modelo **só pode escolher entre os candidatos já validados**.

```text
Voce e um auditor fiscal da LC 214/2025 (reforma tributaria).
Escolha o cClassTrib correto para o produto abaixo.
Produto: "LUVCIR LUVA CIRURGICA ESTERIL M" | NCM 40151100 | CFOP  | CNAE emitente ...

Classes candidatas VALIDAS (escolha SOMENTE um destes IDs, ou REVISAR):
  [200005] <descricao reduzida da classe 200005>
  [200030] <descricao reduzida da classe 200030>
  [000001] Regime padrao (produto nao listado em anexo)
Decisao deterministica preliminar (familia): [200030]
Classes ja eliminadas pelas regras: 200038: condicao nao satisfeita: INSUMOS...
Evidencia do mapa: 200030: condicao satisfeita 'DISPOSITIVOS MEDICOS'
Exemplos oficiais similares (BM25):
  [200030] luva cirurgica esteril ...
Responda APENAS um JSON com as chaves {"cClassTrib","confianca","justificativa","fonte_ids"}.
Use {"cClassTrib":"REVISAR","confianca":0.4,...} se nao houver evidencia suficiente.
Nao invente classes fora da lista.
```

O **top-5 BM25** (`src/busca.py`) enriquece o prompt com exemplos oficiais
similares, recuperados por similaridade lexical (sem dependências externas).

### 3.3 Chamada ao modelo
`LlmCliente.chat_json` (`src/llm_cliente.py`) faz um POST compatível com a API
OpenAI (`/chat/completions`), `temperature=0`, `response_format=json_object`,
timeout e retorno `None` em qualquer falha (nunca lança exceção).

### 3.4 Validação rígida (`llm_juiz.py:_validar`)
A resposta só é aceita se **todas** as condições valerem:

1. a classe está entre os **candidatos fornecidos** ou `000001`; e
2. a classe é **vigente** na tabela oficial; ou então é `"REVISAR"`.

Falha de validação, JSON inválido, timeout, sem chave → **`None`** → o produto
volta para a decisão determinística (nunca uma classe inventada).

### 3.5 Aplicação da decisão (`llm_juiz.py:resolver_fila`)
| Resposta do juiz | Efeito | `metodo` |
|---|---|---|
| Classe válida | usa a classe, `confianca = min(conf_llm, 0.90)` | `llm` |
| `REVISAR` | `status = REVISAR`, confiança < 0,70 | `llm_revisar` |
| `None` (indisponível/rejeitada) | mantém a decisão por família | `regra_ambiguo` |

A decisão do LLM **nunca supera** um mapa exato: o teto de confiança é 0,90
(`LIMIAR_CONF_LLM`). E **1 produto = 1 decisão**: a réplica do produto em ~158
itens não conta como validações independentes.

---

## 4. Como o modelo está configurado

`config/llm.yaml` é o **ponto único de encaixe** (nenhum modelo/chave no código):

```yaml
provedor: openai_compativel
base_url: "https://opencode.ai/inference/go/openai/v1"   # OpenCode Go
modelo: "deepseek-v4.1-flash"
api_key_env: OPENCODE_GO_API_KEY
api_key_arquivo: "llm_key.txt"      # gitignored (nao commitar)
temperatura: 0
max_tokens: 2000                    # DeepSeek V4.1 Flash "pensa" antes do JSON
comportamento_sem_llm: usar_regra   # dry-run mantem a decisao deterministica
```

- **Precedência da chave:** variável de ambiente → `config/llm_key.txt`
  (gitignored) → `auth.json` do opencode.
- **Sem modelo/chave:** `cliente.habilitado == False` → *dry-run*. O pipeline
  roda inteiro e a fila permanece com a decisão determinística (`regra_ambiguo`).
- **Trocar de modelo/provedor:** editar só este arquivo (ex.: Ollama local,
  vLLM, OpenAI). O restante do código não muda.

---

## 5. Garantias de projeto

1. **Cirúrgico:** uma chamada por **produto** distinto, nunca por item.
2. **Cache:** chave `sha256(modelo | prompt)` em `out/cache_llm.json` — repetir o
   pipeline não gasta tokens.
3. **Confinado:** o modelo só escolhe entre candidatos pré-validados; não cria
   fundamento legal nem classe nova.
4. **Seguro por padrão:** qualquer problema → `REVISAR`/regra determinística.
5. **Auditável:** cada decisão registra candidatos, BM25, justificativa e se veio
   do cache.
6. **Determinístico por fora:** `temperature=0`; o resultado final é reprodutível.

---

## 6. Números reais deste dataset

| Etapa | Quantidade |
|---|---:|
| Itens | 15.000 |
| Produtos únicos (`cProd × NCM`) | 95 |
| Produtos com **>1 candidato bruto** no mapa | ~47–51 |
| **Resolvidos por condição/exceção** (sem LLM) | a maioria |
| **Fila do juiz LLM** (ambíguos reais) | **10** |
| Chamadas ao modelo | **10** (depois, 0 por cache) |
| `REVISAR` | **0** |

Os 10 ambíguos são todos **dispositivos médicos** (`200005` × `200030`); o juiz
confirmou `200030` em 10/10, com justificativa. A distribuição final de classes
ficou **idêntica** à versão 100% determinística — o LLM **ratificou** a decisão,
não a bagunçou.

Exemplo real (`out/auditoria_ambiguos.csv`):

| cProd | NCM | candidatos | classe regra | classe LLM | justificativa (resumo) |
|---|---|---|---|---|---|
| LUVCIR | 40151100 | 200005;200030 | 200030 | 200030 | dispositivo médico do Anexo IV; sem indício de venda a órgão público → afasta 200005 |
| SRING10 | 90183100 | 200005;200030 | 200030 | 200030 | seringa descartável; operação comum, não a órgão público |
| CURATH | 30059090 | 200005;200030 | 200030 | 200030 | curativo hidrocoloide; Anexo IV, venda comum |

---

## 7. Artefatos gerados pelo LLM

| Arquivo | Conteúdo |
|---|---|
| `solucao/out/auditoria_ambiguos.csv` | 1 linha por produto da fila: candidatos, eliminados, top-5 BM25, decisão, justificativa, `cache_hit` |
| `solucao/out/cache_llm.json` | cache por hash do prompt+modelo |
| `solucao/out/uso_tokens.json` | `modelo`, `chamadas`, `tokens_entrada`, `tokens_saida`, `data` |

---

## 8. Como rodar

```powershell
cd solucao

# com o juiz LLM (usa cache se ja rodou):
python scripts\rodar_tudo.py --reparse --llm --testes

# sem LLM (dry-run; tudo determinístico):
python scripts\rodar_tudo.py --sem-llm

# empacotar e validar a entrega:
python scripts\empacotar_entrega.py --nome SoldadosDaBorracha
```

No painel (`streamlit run app/painel.py`), a aba **"Auditoria LLM"** mostra a
fila, as justificativas, o `cache_hit` e o consumo de tokens.

---

## 9. Em uma frase

> A classificação é **determinística por padrão**; o LLM é um **juiz de
> exceção** chamado só quando sobra mais de uma classe válida (ou uma condição
> não mapeada), **uma vez por produto**, sempre **confinado aos candidatos já
> validados**, com **validação, cache e fallback** — nunca a fonte primária da
> classificação.
