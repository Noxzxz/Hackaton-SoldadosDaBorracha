# Tratamento de dados e deduplicação — base para o pitch

Documento de apoio para a banca: explica **como os dados entram, são limpos,
validados e deduplicados** na solução. Serve como roteiro para o membro que
apresenta a parte técnica do pitch.

> **Ideia central do pitch:** tratamos **fatos** e **decisões** de forma
> separada. Os 15.000 itens são fatos e **nunca** são descartados; o que
> deduplicamos é o **raciocínio de classificação** (95 produtos) e as **tabelas
> oficiais**. Determinístico, rastreável e com 0 tokens.

---

## 1. Fontes de dados (o que entra)

Tudo vem do pacote oficial `pacote-times/`, resolvido automaticamente por
`src/caminhos.py` (sem caminho fixo). A solução aceita `.csv` **ou** `.xlsx`.

| Fonte | Formato | Uso |
|---|---|---|
| 1.387 DANFEs | PDF | itens e totais das notas |
| Cadastro de empresas | XLSX | CNAE, tipo_cliente, finalidade |
| Mapa NCM → cClassTrib | XLSX | classificação fiscal (4.193 linhas) |
| Tabela cClassTrib | XLSX | vigência e CST |
| CST IBS/CBS | XLSX | validação de CST |
| PIS/Cofins hoje | XLSX | tratamento por produto |
| Parâmetros | JSON/YAML | alíquotas e reduções |
| Templates + validador | — | formato oficial de entrega |

**Frase de pitch:** *"Não inventamos dados — lemos o pacote oficial e provamos
que a extração bate com o documento."*

---

## 2. Tratamento dos dados (o que fazemos com eles)

### 2.1 Normalização das tabelas (`src/io_dados.py`)
- Leitura defensiva com `dtype=str` e `encoding="utf-8-sig"`.
- **Zeros à esquerda preservados**: `NCM` → 8 dígitos, `cClassTrib` → 6, `CST` → 3.
  Isso é essencial porque o XLSX remove zeros (`000001` viraria `1`).
- Cache em memória (`lru_cache`) para não reler a cada uso.

### 2.2 Leitura das DANFEs (`src/parse_danfe.py`)
- Extração com `pdfplumber`, só a 1ª página.
- **Filtro de ruído**: descarta caracteres grandes (>20pt), que são a marca
  d'água; sem isso o texto sai poluído.
- **Identidade pela chave de acesso** (o nome do arquivo, 44 dígitos):
  perspectiva = `venda` se o emitente for a Meridional, senão `compra`.
- **Parsing por âncora de regex**: descrição + `NCM(8) + CST(3) + CFOP(4) + UN`
  + 8 números pt-BR. Linhas sem NCM são continuação da descrição do item.
- **Números em `Decimal`** (`parse_br`), nunca `float` — zero erro de centavo.

### 2.3 Gate de reconciliação por nota (controle de qualidade)
Cada nota é **reconciliada**: somamos os itens e comparamos com os totais
impressos (`vProd`, `vICMS`, PIS, COFINS), tolerância de R$ 0,05.

> **Resultado: 1.387/1.387 notas reconciliadas (100%).**

Se uma nota não bate, o pipeline **para** (`rodar_tudo.py` retorna erro) — não
entregamos número sem prova.

### 2.4 Processamento paralelo + cache (`src/extrair.py`)
- 1.387 notas em `ProcessPoolExecutor` (até 8 processos).
- Resultado cacheado em `out/itens.parquet` e `out/notas.parquet`.
- **Reprodutível**: as execuções seguintes nem reabrem os PDFs (0 tokens).

### 2.5 Dinheiro sempre exato (`src/simular.py`)
- `Decimal` + `ROUND_HALF_UP`, 2 casas.
- **CBS e IBS arredondados separadamente** antes de somar.

---

## 3. Deduplicação (o coração técnico)

A deduplicação acontece em **camadas**, cada uma com uma chave própria. A regra
de ouro: **deduplicar a decisão, nunca o fato.**

### 3.1 Identidade do item — `(chave, nItem)` — **não deduplica**
`nItem` é a posição do item na nota, atribuída sequencialmente. O par
`(chave, nItem)` é a identidade oficial do item e é **único**:

> **15.000 itens → 15.000 pares únicos (0 duplicados).**

Aqui **não se descarta nada**: cada linha da nota é um fato.

### 3.2 Catálogo de produtos — `cProd × NCM` — **a dedup principal**
`classificar.py:319` faz `drop_duplicates(subset=["cProd","NCM"])`. Em vez de
classificar 15.000 vezes, classificamos **95 produtos únicos** e religamos o
resultado a todos os itens.

> **15.000 itens → 95 pares `cProd × NCM`** (52 NCMs distintos).
> Cada produto é decidido uma vez e reaproveitado ~158 vezes.

É reuso de **raciocínio**, não de **dados**: os valores de cada item continuam
intactos.

### 3.3 Mapa NCM → cClassTrib — dedup semântica (`io_dados.py:77`)
```python
df = df.drop_duplicates(subset=["NCM","cClassTrib","permissao","condicao","excecao"])
```
> **4.193 linhas → 3.792** (remove 401 linhas idênticas).

A chave **não** é só o NCM: um NCM pode apontar para classes diferentes conforme
`permissao`, `condicao` e `excecao`. Só removemos linhas **semanticamente
idênticas**, preservando as variações legítimas.

### 3.4 Dedup implícita por dicionário (last-write-wins)
`tratamento_por_produto()` (`io_dados.py:51`) monta
`dict(zip(df["cProd"], df["tratamento"]))`: se um `cProd` se repetir, a última
ocorrência vence.

### 3.5 Índices para religar (unicidade garantida)
`set_index` sobre `(cProd, NCM)` e `(chave, nItem)` permite o `.loc` direto e
rápido nos joins de classificação, simulação e trilha.

### Quadro-resumo da deduplicação

| Camada | Chave | Antes → Depois |
|---|---|---:|
| Item | `(chave, nItem)` | 15.000 → 15.000 (unicidade) |
| Produto | `(cProd, NCM)` | 15.000 → **95** |
| Mapa NCM | `(NCM, cClassTrib, permissao, condicao, excecao)` | 4.193 → 3.792 (−401) |
| Tratamento PIS | `cProd` (dict) | last-write-wins |
| Joins | `set_index` | chave única |

---

## 4. Por que deduplicar a decisão e não o fato

Uma alternativa comum seria **agrupar/somar** linhas repetidas (`groupby` +
`sum`) para reduzir volume. **Rejeitamos essa abordagem** porque:

1. **Quebra o formato oficial.** O entregável exige uma linha por `(chave,
   nItem)` — 15.000 linhas. Agregar por código de produto fundiria itens e
   perderia o `nItem`.
2. **Altera os fatos.** Somar `VALOR ICMS`/`VALOR TOTAL` de linhas diferentes
   muda a base de cálculo e corrompe a tributação se CFOP/CST/classe divergirem.
3. **Perde rastreabilidade.** Sem granularidade, não há árvore de prova por item.

**Nossa regra:** extrair 100% dos itens (fatos), deduplicar só a classificação
(95 decisões). Assim temos escala **e** precisão.

---

## 5. Encerramento — números para fechar o pitch

| Métrica | Valor |
|---|---:|
| DANFEs processadas | 1.387 |
| Notas reconciliadas | **1.387/1.387 (100%)** |
| Itens | 15.000 (11.700 compras / 3.300 vendas) |
| Pares `(chave, nItem)` únicos | 15.000 |
| Produtos únicos (`cProd × NCM`) | 95 |
| Mapa deduplicado | 4.193 → 3.792 |
| Itens em `REVISAR` | 0 |
| Testes | 28 verdes |
| LLM no caminho principal | 0 tokens |

**Mensagem final sugerida:**
> *"Tratamos cada um dos 15.000 itens como fato, com prova de reconciliação em
> 100% das notas. Deduplicamos apenas o raciocínio — 95 produtos classificados
> uma vez. O resultado é reprodutível, auditável e sem custo de LLM."*

---

## 6. Referências de código

- `src/io_dados.py` — leitura e normalização das tabelas.
- `src/parse_danfe.py` — extração das DANFEs e reconciliação.
- `src/extrair.py` — paralelismo e cache.
- `src/classificar.py` — catálogo (dedup `cProd × NCM`) e cascata.
- `src/ncm_match.py` — casamento NCM (exato → prefixo 6 → prefixo 4).
- `src/simular.py` — simulação com `Decimal`.
- `RESOLUCAO-ENTREGAVEIS.md` — leitura dos arquivos de saída.
