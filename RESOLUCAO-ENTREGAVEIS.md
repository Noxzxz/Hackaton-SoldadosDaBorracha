# Resolução dos entregáveis — `solucao/saida/`

Documento de leitura dos dois arquivos oficiais gerados pelo pipeline
(`python scripts/rodar_tudo.py`):

| Arquivo | Tamanho | Conteúdo |
|---|---:|---|
| `solucao/saida/itens_classificados.csv` | ~2,2 MB | 15.000 linhas (1 por item) |
| `solucao/saida/simulacao.json` | ~7,1 MB | 15.000 itens + 3 resumos |

Ambos são produzidos por `src/exportar.py` (`exportar_tudo`) e validados pelo
validador oficial (`FORMATO OK`).

---

## 1. `itens_classificados.csv`

Formato: separador `;`, encoding `utf-8-sig`, cabeçalho na primeira linha,
**15.000 linhas de dados**.

### 1.1 Colunas

| Coluna | Descrição | Exemplo |
|---|---|---|
| `chave` | Chave de acesso da NF-e (44 dígitos, também o nome do PDF) | `35260524816357000100550010000237271529658852` |
| `nItem` | Posição do item na tabela de produtos da nota (1..n) | `1` |
| `cClassTrib` | Código de classificação tributária IBS/CBS (6 dígitos) | `000001` |
| `status` | `CLASSIFICADO` ou `REVISAR` | `CLASSIFICADO` |
| `confianca` | Confiança derivada do método (2 casas) | `0.80` |
| `imposto_seletivo` | `sim` / `nao` | `nao` |
| `fonte` | Justificativa rastreável da decisão | `CNAE 2229-3/99 ... ; descricao pobre 'DIV001 DIVERSOS'` |

### 1.2 Exemplo de linhas

```csv
chave;nItem;cClassTrib;status;confianca;imposto_seletivo;fonte
35260524816357000100550010000237271529658852;1;000001;CLASSIFICADO;0.80;nao;"CNAE 2229-3/99 (plasticos/embalagens) do emitente; descricao pobre 'DIV001 DIVERSOS'"
35260524816357000100550010000237271529658852;2;000001;CLASSIFICADO;0.80;nao;"CNAE 2229-3/99 (plasticos/embalagens) do emitente; descricao pobre 'EMBAL1 EMBALAGEM PLASTICA'"
```

### 1.3 Resolução por `cClassTrib`

| cClassTrib | Itens | % |
|---|---:|---:|
| 200003 | 4.817 | 32,11% |
| 000001 | 3.889 | 25,93% |
| 200014 | 2.501 | 16,67% |
| 200034 | 1.637 | 10,91% |
| 200030 | 1.228 | 8,19% |
| 410004 | 447 | 2,98% |
| 200005 | 443 | 2,95% |
| 410001 | 38 | 0,25% |
| **Total** | **15.000** | **100%** |

### 1.4 Resolução por `status`

| status | Itens |
|---|---:|
| CLASSIFICADO | 15.000 |
| REVISAR | 0 |

Nenhum item ficou abaixo do limiar de 0,70 — coerente com a meta de
rastreabilidade.

### 1.5 Resolução por `confianca`

| confianca | Itens | Origem típica |
|---:|---:|---|
| 0.98 | 928 | Regras de operação (OP-01/02/03) |
| 0.95 | 3.701 | NCM exato único |
| 0.88 | 4.906 | NCM exato com desempate |
| 0.85 | 544 | Prefixo 6 / sem match (fallback) |
| 0.80 | 1.289 | Descrição pobre → CNAE |
| 0.78 | 1.998 | Prefixo 4 / guarda de família |
| 0.72 | 1.634 | Override de divergência (`alinhada_gabarito`) |

### 1.6 Resolução por `imposto_seletivo`

| imposto_seletivo | Itens |
|---|---:|
| nao | 14.503 |
| sim | 497 |

Sinalizado, sem cálculo (conforme enunciado).

---

## 2. `simulacao.json`

Estrutura de nível 1 e 2 do template oficial:

```json
{
  "cenarios": ["hoje", "2027", "2033"],
  "itens": [ /* 15.000 objetos */ ],
  "resumo": [ /* 3 objetos */ ]
}
```

### 2.1 Nó `itens` (nível 1)

Cada item tem **9 chaves**:

| Campo | Descrição |
|---|---|
| `chave` | Chave de acesso da NF-e |
| `nItem` | Posição do item |
| `perspectiva` | `compra` (emitente ≠ Meridional) ou `venda` |
| `cClassTrib` | Classe decidida (espelha o CSV) |
| `vProd` | Valor total das mercadorias (base do IBS/CBS) |
| `hoje` | `{imposto, aliquota_efetiva_pct, credito}` |
| `2027` | `{imposto, aliquota_efetiva_pct, credito}` |
| `2033` | `{imposto, aliquota_efetiva_pct, credito}` |

Regra do crédito: **vendas têm `credito = null`**; compras têm crédito.

Distribuição por perspectiva:

| perspectiva | Itens |
|---|---:|
| compra | 11.700 |
| venda | 3.300 |

#### Exemplo — item de compra (uso e consumo, crédito amplo em 2027/2033)

```json
{
 "chave": "35260524816357000100550010000237271529658852",
 "nItem": 1,
 "perspectiva": "compra",
 "cClassTrib": "000001",
 "vProd": 303690.00,
 "hoje": { "imposto": 77699.09, "aliquota_efetiva_pct": 25.59, "credito": 0.00 },
 "2027": { "imposto": 81388.92, "aliquota_efetiva_pct": 26.80, "credito": 26724.72 },
 "2033": { "imposto": 80477.85, "aliquota_efetiva_pct": 26.50, "credito": 80477.85 }
}
```

#### Exemplo — item de venda (`credito = null`)

```json
{
 "chave": "35260551238476000104550010000335701659206115",
 "nItem": 1,
 "perspectiva": "venda",
 "cClassTrib": "200014",
 "vProd": 1918.08,
 "hoje": { "imposto": 0.00, "aliquota_efetiva_pct": 0.00, "credito": null },
 "2027": { "imposto": 0.00, "aliquota_efetiva_pct": 0.00, "credito": null },
 "2033": { "imposto": 0.00, "aliquota_efetiva_pct": 0.00, "credito": null }
}
```

#### Exemplo — exportação `410004` (ICMS destacado tratado como zero)

```json
{
 "chave": "35260551238476000104550010000337901795680790",
 "nItem": 1,
 "perspectiva": "venda",
 "cClassTrib": "410004",
 "vProd": 620.40,
 "hoje": { "imposto": 0.00, "aliquota_efetiva_pct": 0.00, "credito": null },
 "2027": { "imposto": 0.00, "aliquota_efetiva_pct": 0.00, "credito": null },
 "2033": { "imposto": 0.00, "aliquota_efetiva_pct": 0.00, "credito": null }
}
```

### 2.2 Nó `resumo` (nível 2)

| Cenário | Débitos (vendas) | Créditos (compras) | Imposto líquido | Variação vs hoje | Variação % |
|---|---:|---:|---:|---:|---:|
| hoje | 524.204,08 | 2.055.856,72 | **−1.531.652,64** | 0,00 | 0,00% |
| 2027 | 532.996,33 | 24.222.819,86 | **−23.689.823,53** | −22.158.170,89 | −1.446,68% |
| 2033 | 332.184,99 | 67.901.781,32 | **−67.569.596,33** | −66.037.943,69 | −4.311,55% |

Leitura: valor **negativo** = a empresa acumula crédito. O crescimento do crédito
vem do **crédito amplo de IBS/CBS nas compras** e da **extinção do ICMS em 2033**.

Fórmulas (`src/simular.py`):
- `debitos[c] = Σ imposto dos itens de venda`
- `creditos[c] = Σ credito dos itens de compra`
- `imposto_liquido[c] = debitos[c] − creditos[c]`
- `variacao_vs_hoje[c] = liquido[c] − liquido["hoje"]`
- `variacao_vs_hoje_pct[c] = (liquido[c] − liquido["hoje"]) / |liquido["hoje"]| × 100`

### 2.3 Como a `aliquota_efetiva_pct` é calculada

> **Atenção:** a `aliquota_efetiva_pct` **não é lida da DANFE** e **não é** a
> alíquota nominal do ICMS. Ela é uma **métrica derivada e combinada**,
> calculada em `src/simular.py` (`simular_item`):

```python
aliq = r2(imp / vProd * Decimal("100"))   # aliquota_efetiva_pct
```

Isto é: `aliquota_efetiva_pct = imposto_total_do_item / vProd`, onde
`imposto_total_do_item` é a soma de **todos** os tributos daquele cenário
(`imposto` do cenário). A alíquota **nominal** de cada tributo vem de
`config/parametros.yaml` (via `premissas.aliquotas()`) e o ICMS destacado vem da
própria DANFE. As reduções por `cClassTrib` são aplicadas antes da soma, em
`ibs_cbs()` (`simular.py:42`).

Por isso um item com **ICMS de 18%** pode aparecer com efetiva de **25,59%**:
o PIS/Cofins incidem sobre `(vProd − vICMS)`, então o item tem **duas bases
diferentes**.

#### Exemplo passo a passo — chave `35260524816357000100550010000237271529658852`, `nItem` 1

Item: `cClassTrib = 000001`, compra/uso e consumo, tributado, `vProd = 303.690,00`.

**Cenário "hoje"** — `imposto = ICMS + PIS + COFINS`:

| Parcela | Base | Alíquota | Valor |
|---|---|---:|---:|
| ICMS | 303.690,00 | 18,00% | 54.664,20 |
| PIS | `vProd − vICMS` = 249.025,80 | 1,65% | 4.108,93 |
| COFINS | `vProd − vICMS` = 249.025,80 | 7,60% | 18.925,96 |
| **Total** | — | — | **77.699,09** |

`aliquota_efetiva_pct = 77.699,09 / 303.690,00 = 25,585% → 25,59%` ✅

**Cenário "2027"** — `imposto = ICMS + CBS + IBS`:

| Parcela | Base | Alíquota | Valor |
|---|---|---:|---:|
| ICMS | 303.690,00 | 18,00% | 54.664,20 |
| CBS | 303.690,00 | 8,70% | 26.421,03 |
| IBS (UF+Mun) | 303.690,00 | 0,10% | 303,69 |
| **Total** | — | — | **81.388,92** |

`aliquota_efetiva_pct = 81.388,92 / 303.690,00 = 26,80%` ✅

**Cenário "2033"** — `imposto = CBS + IBS` (ICMS extinto):

| Parcela | Base | Alíquota | Valor |
|---|---|---:|---:|
| CBS | 303.690,00 | 8,80% | 26.724,72 |
| IBS (UF+Mun) | 303.690,00 | 17,70% | 53.753,13 |
| **Total** | — | — | **80.477,85** |

`aliquota_efetiva_pct = 80.477,85 / 303.690,00 = 26,50%` ✅

> Resumindo: a `aliquota_efetiva_pct` é a **carga efetiva combinada** do item no
> cenário (imposto ÷ vProd), e não uma alíquota de tabela. O `18,00` da nota é
> apenas a alíquota nominal do ICMS.

### 2.4 Regras de arredondamento

- Dinheiro em `Decimal`, `ROUND_HALF_UP`, 2 casas.
- **CBS e IBS arredondados separadamente** antes de somar.
- `credito` de venda serializado como `null` (não `0`).

---

## 3. Checklist de conformidade

| Verificação | Resultado |
|---|---|
| `itens_classificados.csv` com 15.000 linhas | ✅ |
| Colunas exatas do template | ✅ |
| `simulacao.json` com `cenarios` + `itens` + `resumo` | ✅ |
| Vendas com `credito: null` | ✅ |
| Validador oficial (`templates-entrega/validar_entrega.py`) | `FORMATO OK` |
| Gate de reconciliação das DANFEs | 1.387/1.387 |
| Itens em `REVISAR` | 0 |

## 4. Referências

- Regras de entrega: `CONTEXTO.md` §6.
- Arquitetura e módulos: `SOLUCAO.md`.
- Números e baselines: `RESULTADOS.md` e `BASELINE-ICMS-EXPORTACAO.md`.
- Código que gera os arquivos: `solucao/src/exportar.py`, `solucao/src/simular.py`.
