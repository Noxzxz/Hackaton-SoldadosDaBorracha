# Solução proposta (retificada)

Motor **determinístico** em Python: lê as 1.387 DANFEs do pacote oficial,
classifica os 15.000 itens, simula três cenários com aritmética exata, gera os
dois entregáveis, a trilha de auditoria, o tribunal de premissas, o painel e a
baseline do ICMS de exportação.

**Sem LLM no caminho principal** (0 tokens): a cascata resolve o catálogo e o
resultado é reprodutível. `llm_juiz.py` fica como reserva para produtos novos.

---

## 1. Arquitetura

```
pacote-times/dados/ (XLSX + PDFs)
        │
        ▼
caminhos + io_dados ──► parse_danfe ──► gate de reconciliação por nota
        │                                      │
        │                                      ▼
        │                            extrair (cache parquet em out/)
        ▼
contexto (perspectiva pela chave, cadastro, PIS/Cofins)
        │
        ▼
catálogo (95 pares cProd × NCM) ◄── famílias + guarda + overrides
        │
        ▼
classificar (OP-01/02/03 → catálogo/mapa → CNAE → REVISAR)
        │
        ▼
simular (Decimal/ROUND_HALF_UP; hoje/2027/2033; créditos; resumo)
        │
        ├──► trilha (árvore de prova por número)
        ├──► tribunal (mapa estrito × leitura técnica)
        ├──► equilíbrio (preço de equilíbrio — bônus)
        └──► baseline de exportação (ICMS errado × correto)
        │
        ▼
exportar ──► solucao/saida/itens_classificados.csv
             solucao/saida/simulacao.json
             solucao/out/*.parquet + tribunal.json
```

### Módulos

| Módulo | Responsabilidade |
|---|---|
| `src/caminhos.py` | Resolve o pacote oficial (`pacote-times/dados`) com fallback. |
| `src/io_dados.py` | Lê CSV **ou** XLSX e normaliza NCM/cClassTrib/CST. |
| `src/parse_danfe.py` | Extrai itens e totais da DANFE; gate de reconciliação. |
| `src/extrair.py` | Processa as 1.387 notas em paralelo e cacheia em parquet. |
| `src/ncm_match.py` | Casa NCM exato → prefixo 6 → prefixo 4; respeita VEDADO. |
| `src/classificar.py` | Cascata de decisão, catálogo, famílias e overrides. |
| `src/mutacao.py` | Mede estabilidade da classificação (confiança medida). |
| `src/simular.py` | Tributos por item e resumo por cenário (Decimal). |
| `src/equilibrio.py` | Preço de equilíbrio por produto (nível 3/bônus). |
| `src/trilha.py` | Liga `chave + nItem` a cada grandeza e sua fonte. |
| `src/tribunal.py` | Recalcula sob duas leituras e mostra o custo. |
| `src/exportar.py` | Gera CSV/JSON oficiais e a base do painel. |
| `app/painel.py` | Painel Streamlit (veredito, drill-down, tribunal, simulador). |
| `scripts/baseline_exportacao.py` | Gera as baselines errada × correta de ICMS. |

---

## 2. Classificação

Ordem fixa:

1. **OP-01** CFOP 5910 → `410001` (bonificação).
2. **OP-02** CFOP 7102 / exterior → `410004` (exportação).
3. **OP-03** dispositivo médico + órgão público → `200005`.
4. Catálogo de produto (por `cProd × NCM`) → classe-base.
5. NCM no mapa (exato → prefixo 6 → prefixo 4) + guarda de família.
6. Descrição pobre → CNAE do emitente → `000001`.
7. Nada defensável → `REVISAR`.

**Confiança** é derivada do método e ajustada por estabilidade (mutações de
descrição), nunca autodeclarada. O limiar do enunciado (0,70) é configurável em
`config/politica.yaml`.

O catálogo cobre 95 pares `cProd × NCM`; as famílias (`config/familias.yaml`)
desempatam NCMs compartilhados e as 7 divergências mapa × leitura técnica têm
override explícito (`config/overrides_divergencia.yaml`).

---

## 3. Simulação

- Dinheiro sempre em `Decimal` com `ROUND_HALF_UP`, 2 casas, **CBS e IBS
  arredondados separadamente** antes de somar.
- Base do IBS/CBS = `vProd`.
- Compra para revenda gera crédito de ICMS/PIS/Cofins hoje; IBS/CBS novo é
  crédito amplo (inclusive uso e consumo).
- Vendas têm `credito = null`.
- Resumo: `débitos − créditos`, com `variacao_vs_hoje` e
  `variacao_vs_hoje_pct` (alinhado ao template oficial).

---

## 4. Correções e retificações aplicadas

### 4.1 ICMS de exportação = zero (achado principal)

O pacote oficial diz que exportação é imune e que algumas DANFEs destacam ICMS
por erro de geração. A solução adota **ICMS zero em CFOP 7xxx**
(`tratamento_exportacao.icms_zero: true`).

Resultado: **256 notas** com ICMS indevido, **R$ 43.827,17** apurados a mais em
hoje/2027. Detalhes em `BASELINE-ICMS-EXPORTACAO.md`. O flag permite voltar ao
valor destacado se a organização exigir o template.

### 4.2 Robustez (auditoria multi-agente)

- cache de YAML invalidado por `mtime` e `recarregar_config()`;
- limiar de `REVISAR` configurável (0,70);
- tribunal sem mutação de estado global (`contextvars`);
- `logging` nos fallbacks (estabilidade e parsing);
- import estático, índice na trilha, flag `--workers`;
- decomposição do painel separa débito de venda × imposto de compra;
- serialização de `confianca` e `reconciliada` corrigida;
- testes negativos e de coerência adicionados.

Detalhes em `QUALIDADE-E-CORRECOES.md` e `DECISOES.md`.

### 4.3 Pacote oficial novo

- leitura de `.xlsx` além de `.csv`, com normalização de zeros à esquerda;
- resolução automática de `pacote-times/dados`;
- painel sem caminho fixo para o pacote antigo;
- `variacao_vs_hoje_pct` no resumo;
- CNPJ foco agora coincide com o `parametros.json` oficial (`...104`).

Detalhes em `IMPACTO-PACOTE-OFICIAL.md`.

---

## 5. Tribunal de premissas

Sete famílias divergem entre o mapa oficial e a leitura técnica dos Anexos I/VII
(creme de leite, queijo minas, queijos 0406.90, lentilha, óleo de soja, amido e
fubá). A política ativa é `alinhada_gabarito`; o painel mostra o custo da leitura
`mapa_estrito` (diferença de R$ 70.877,71 no líquido de 2033). O tribunal
recalcula as duas leituras sem contaminar a classificação ativa.

---

## 6. Rastreabilidade

`out/trilha.parquet` liga cada `chave + nItem` a cada grandeza
(`cClassTrib`, `vProd`, `vICMS`, `imposto_*`, `credito_*`) com fórmula e fonte
(`danfe` / `mapa` / `regra` / `premissa`). No painel, o drill-down mostra a árvore
de prova do item.

---

## 7. Painel

Seis telas:

1. **Veredito** (nível 2): débitos, créditos, líquido e variação.
2. **Onde ganha/perde**: decomposição por família, classe, produto e fornecedor.
3. **Drill-down**: árvore de prova por item (com busca por chave/nItem).
4. **Tribunal**: as 7 divergências e o custo de cada leitura.
5. **Qualidade**: reconciliação, confiança e Imposto Seletivo.
6. **Simulador "e se?"**: alíquota e repasse ao vivo + preço de equilíbrio.

A baseline de ICMS está em `BASELINE-ICMS-EXPORTACAO.md` e nos arquivos
`solucao/out/baseline_exportacao*.csv/json`.

---

## 8. Testes e validação

- `python -m pytest -q` → **27 testes verdes**.
- 6 golden tests do enunciado (incluindo R$ 100 → R$ 10,60).
- Testes de propriedade (HALF_UP, sem incidência, idempotência, crédito null).
- Gate de reconciliação: **1.387/1.387** notas.
- `scripts/validar_entrega.py` → `TUDO OK`.
- Validador oficial do pacote → `FORMATO OK`.
- `ruff check --select F,E9` → sem erros.

---

## 9. Entregáveis

- `solucao/saida/itens_classificados.csv` — 15.000 linhas.
- `solucao/saida/simulacao.json` — 15.000 itens + 3 resumos.
- `solucao/out/` — base do painel, trilha, tribunal, equilíbrio e baselines.
- `solucao/app/painel.py` — painel Streamlit.
