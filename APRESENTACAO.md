# Documento de apresentação — Atacadista Meridional × Reforma Tributária

> **Para que serve este documento**
> Explicar, etapa por etapa, como a solução funciona, de onde vem cada número e o
> que pode ser dito com segurança na banca. Serve como fonte única para montar os
> slides, o roteiro de fala e o ensaio do pitch.
>
> **Fonte dos números:** execução atual com o pacote oficial
> (`pacote-times/dados`), validada em 2026-10-17. Onde uma documentação anterior
> divergir (ex.: "28 testes" ou confiança média 0,865), vale este documento.
> Números-chave conferidos: **42 testes**, reconciliação **1.387/1.387**,
> **0 REVISAR**, confiança mínima **0,72** e média **0,878**,
> validador oficial **FORMATO OK**.

---

## 0. O pitch em 60 segundos (texto pronto)

> "A Meridional compra e vende 15.000 itens em 1.387 notas. Construímos um motor
> determinístico que lê as DANFEs, prova que a extração fecha contra o documento
> (1.387 de 1.387 notas) e classifica cada item no `cClassTrib` com origem
> rastreável. Deduplicamos o raciocínio, não os fatos: 15.000 itens viram 95
> produtos classificados uma vez. Regras resolvem 85 produtos; um juiz de LLM
> decide apenas as 10 ambiguidades reais, sempre confinado a candidatos válidos.
> A simulação mostra a Meridional acumulando crédito no regime novo. E encontramos
> um erro silencioso: 256 notas de exportação traziam ICMS que não existe —
> **R$ 43.827,17** apurados a maior. Cada número tem árvore de prova."

**Mensagem em uma linha:**
> _Regras primeiro, evidência sempre, LLM só na exceção — e um achado de
> R$ 43,8 mil que o processo anterior não via._

---

## 1. O desafio (o que a banca pede)

A **Atacadista Meridional** (fictícia) compra e vende alimentos, produtos médicos
e de limpeza. A reforma substitui PIS/Cofins/ICMS por **CBS/IBS** e cria o
**Imposto Seletivo** entre 2026 e 2033. Pede-se:

1. Separar notas de **compra** e de **venda** (vêm misturadas; o nome não diz qual é qual).
2. Classificar cada item no **`cClassTrib`** (6 dígitos), com confiança e fonte.
3. Simular a carga em **hoje × 2027 × 2033**, por item e por empresa.
4. Explicar em painel se a empresa **ganha ou perde**, com a origem de cada número.

**Identidade oficial:** a nota é a **chave de acesso** (44 dígitos); o item é o
**`nItem`** (posição na tabela de produtos).

### Régua de avaliação (pesos oficiais)

| Critério | Peso | Como atacamos |
|---|---:|---|
| Acurácia da classificação | 35% | cascata derivada do mapa oficial + famílias + condições/exceções |
| Simulação correta | 25% | `Decimal` + `ROUND_HALF_UP`, testes golden do enunciado |
| Calibração | 10% | confiança por método + estabilidade a mutações |
| Painel e rastreabilidade | 20% | 7 abas + trilha de 135.000 linhas com fonte por grandeza |
| Pitch | 10% | achado do ICMS de exportação + narrativa honesta |

**Eficiência (tokens) saiu da rubrica.** Por isso o discurso não é "gastamos 0
tokens", e sim "acertamos, calibramos e rastreamos".

### Entregáveis exigidos

Uma pasta com o nome da equipe contendo **exatamente** dois arquivos:

- `itens_classificados.csv` (separador `;`): `chave`, `nItem`, `cClassTrib`, `status`, `confianca`, `imposto_seletivo`, `fonte`.
- `simulacao.json`: `cenarios`, `itens` (nível 1) e `resumo` (nível 2); vendas com `credito = null`.

---

## 2. Visão geral da solução

**Tese:** um motor **determinístico** em Python lê o pacote oficial, classifica os
15.000 itens, simula os três cenários com aritmética exata e produz os dois
entregáveis, a trilha de auditoria, o painel e a baseline do ICMS de exportação.

```
pacote-times/dados (XLSX + 1.387 PDFs)
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
        ├──► juiz LLM (só ambíguos; 10 produtos; cache)
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

### As 12 etapas

| # | Etapa | Entrada | Saída | Módulo principal |
|---|---|---|---|---|
| 0 | Resolver pacote e ler tabelas | XLSX/CSV | DataFrames normalizados | `src/caminhos.py`, `src/io_dados.py` |
| 1 | Extrair DANFEs | 1.387 PDFs | 15.000 itens | `src/parse_danfe.py` |
| 2 | Reconciliar notas | itens + totais | 1.387/1.387 O.K. | `src/parse_danfe.py` |
| 3 | Paralelizar e cachear | PDFs | `out/itens.parquet` | `src/extrair.py` |
| 4 | Deduplicar | 15.000 itens | 95 produtos | `src/classificar.py` |
| 5 | Classificar | produto + contexto | `cClassTrib` + fonte | `src/classificar.py` |
| 6 | Julgar ambíguos (LLM) | fila de produtos | decisão validada | `src/llm_juiz.py` |
| 7 | Calibrar confiança | catálogo | confiança 0,72–0,98 | `src/mutacao.py` |
| 8 | Simular | itens + classes | 3 cenários | `src/simular.py` |
| 9 | Baseline exportação | vICMS CFOP 7xxx | R$ 43.827,17 | `scripts/baseline_exportacao.py` |
| 10 | Trilha de auditoria | tudo | 135.000 linhas | `src/trilha.py` |
| 11 | Tribunal de premissas | 2 políticas | custo em R$ | `src/tribunal.py` |

---

## 3. Etapa 0 — Entrada e tabelas oficiais

**O que entra** (pacote oficial `pacote-times/`):

| Fonte | Formato | Uso |
|---|---|---|
| 1.387 DANFEs | PDF | itens e totais das notas |
| Cadastro de empresas | XLSX | CNAE, tipo de cliente, finalidade |
| Mapa NCM → cClassTrib | XLSX | classificação fiscal (4.193 linhas) |
| Tabela cClassTrib | XLSX | vigência e CST |
| CST IBS/CBS | XLSX | validação de CST |
| PIS/Cofins hoje | XLSX | tratamento por produto |
| Parâmetros | JSON/YAML | alíquotas e reduções |

**Como o código resolve os caminhos:** `src/caminhos.py:15` procura, em ordem,
`pacote-times-*/pacote-times/dados`, `pacote-times/dados` e o pacote antigo
(`03-dados-alunos`). Nada de caminho fixo. O CNPJ foco é
`51238476000104` (`src/caminhos.py:50`), igual ao cadastro, ao
`parametros.json` oficial e à chave das DANFEs.

**Leitura defensiva** (`src/io_dados.py`):

- aceita `.csv` **ou** `.xlsx` (`io_dados.py:20`);
- lê tudo como texto (`dtype=str`) para não perder zeros;
- **normaliza zeros à esquerda**: `NCM` → 8 dígitos, `cClassTrib` → 6, `CST` → 3
  (`io_dados.py:38-80`). Sem isso, `000001` viraria `1` no XLSX;
- `lru_cache` evita reler tabelas.

**Frase de pitch:** _"Não inventamos dados — lemos o pacote oficial e provamos que
a extração bate com o documento."_

---

## 4. Etapa 1 — Extração das DANFEs

Tudo em `src/parse_danfe.py`. A extração é defensiva porque PDF não tem schema.

1. **Só a 1ª página**, com `pdfplumber` (`parse_pdf`, `parse_danfe.py:390`).
2. **Filtro de ruído:** descarta caracteres grandes (>20pt), que são a marca
   d'água; sem isso o texto sai poluído (`_filtrar_ruido`, `parse_danfe.py:138`).
3. **Identidade pela chave de acesso:** o nome do arquivo (44 dígitos) é a chave.
   O emitente vem das posições 6–20 da própria chave. Se o emitente for a
   Meridional → **venda**; senão → **compra** (`parse_danfe.py:401-403`).
   Isso é mais confiável que ler CNPJ do texto.
4. **Parsing por âncora de regex** (`_RE_ITEM`, `parse_danfe.py:144`): a linha é
   `descrição + NCM(8) + CST(3) + CFOP(4) + UN + 8 números pt-BR`.
5. **Continuação de descrição:** linha sem NCM é juntada ao item anterior
   (`_extrair_itens`, `parse_danfe.py:259`); cabeçalhos/rodapés são ignorados.
6. **Números em `Decimal`** (`parse_br`, `parse_danfe.py:156`): converte pt-BR
   (`1.234,56` → `1234.56`) sem passar por `float`; zero erro de centavo.
7. **Descrição normalizada** (`normalizar_xprod`, `parse_danfe.py:176`):
   maiúsculas, sem acento, sem o sufixo `- BONIFICACAO`, espaços colapsados.

**Resultado da extração:**

| Métrica | Valor |
|---|---:|
| Notas | 1.387 |
| Itens | 15.000 |
| Compras / vendas | 720 / 667 notas (11.700 / 3.300 itens) |
| CFOP 5102 / 5101 / 7102 / 5910 | 11.516 / 2.999 / 447 / 38 |

---

## 5. Etapa 2 — Gate de reconciliação (a prova de extração)

Para cada nota, o sistema **soma os itens** e compara com os **totais impressos**
da DANFE: `vProd`, `vICMS`, PIS e COFINS, com tolerância de **R$ 0,05**
(`Nota.reconciliacao`, `parse_danfe.py:75`; `divergencias`, `parse_danfe.py:115`).

**Resultado: 1.387/1.387 notas reconciliadas (100%).**

Se uma nota não bate, o pipeline **para** (`rodar_tudo.py:45-47`) — não se entrega
número sem prova.

### Nuance técnica honesta (importante para a banca)

O gerador sintético imprimiu PIS/Cofins de exportação **como se o produto fosse
tributado**, mesmo escrevendo "EXPORTACAO ... SEM INCIDENCIA". Por isso existem
dois modos em `pis_cofins_item` (`parse_danfe.py:192`):

- **`modo="impresso"`** — só zera bonificação; usado **no gate** para fechar
  contra o documento (é o que o gerador imprimiu).
- **`modo="lei"`** — exportação (CFOP 7xxx) = zero; usado **na simulação**, que
  segue o enunciado.

Isso está documentado em `DECISOES.md` (§2). Em produção real (XML), o gate
deveria usar `modo="lei"`; aqui o artefato do dataset é conhecido e assumido.

**Frase de pitch:** _"Somos o único passo que começa provando que leu direito:
1.387 de 1.387 notas fecham centavo a centavo contra o PDF."_

---

## 6. Etapa 3 — Paralelismo e cache

`extrair_tudo` (`src/extrair.py:102`) processa as 1.387 notas com
`ProcessPoolExecutor` (até 8 processos, `extrair.py:134`) e grava:

- `out/itens.parquet` — 15.000 itens;
- `out/notas.parquet` — 1.387 notas com totais e status de reconciliação.

Sem `--reparse`, as execuções seguintes **nem reabrem os PDFs**: reprodutível e
rápido. É o que permite abrir o painel na hora.

---

## 7. Etapa 4 — Tratamento e deduplicação

**Regra de ouro:** _deduplicar a decisão, nunca o fato._

### Camadas de deduplicação

| Camada | Chave | Antes → Depois |
|---|---|---:|
| Item (fato) | `(chave, nItem)` | 15.000 → **15.000** (unicidade; nada descartado) |
| Produto (decisão) | `(cProd, NCM)` | 15.000 → **95** (`classificar.py:498`) |
| Mapa NCM | `(NCM, cClassTrib, permissao, condicao, excecao)` | 4.193 → **3.792** (−401) (`io_dados.py:77`) |
| Tratamento PIS | `cProd` (dict) | last-write-wins (`io_dados.py:52`) |
| Joins | `set_index` | chave única |

Classificamos **95 produtos uma vez** e religamos o resultado aos 15.000 itens.
Cada produto é reaproveitado ~158 vezes. É **reuso de raciocínio**, não de dados:
os valores de cada item continuam intactos.

### Por que não agregar as linhas

Somar/agrupar itens repetidos quebraria o formato oficial (que exige uma linha por
`(chave, nItem)`), mudaria a base de cálculo e destruiria a rastreabilidade.
**Extraímos 100% dos fatos; deduplicamos só a classificação.**

**Frase de pitch:** _"Tratamos os 15.000 itens como fatos e deduplicamos apenas o
raciocínio — 95 decisões."_

---

## 8. Etapa 5 — Cascata de classificação

O coração está em `src/classificar.py`. A ordem é fixa (`classificar_produto`,
`classificar.py:341`; regras de operação em `classificar.py:635`):

1. **OP-01** CFOP 5910 → `410001` (bonificação).
2. **OP-02** CFOP 7102 / destinatário exterior → `410004` (exportação).
3. **OP-03** dispositivo médico + órgão público → `200005`.
4. **Catálogo do produto** por `(cProd, NCM)` → classe-base (95 produtos).
5. **Mapa oficial** (`avaliar_mapa`, `classificar.py:141`):
   - só linhas **PERMITIDO** (VEDADO exclui), casamento **exato → prefixo 6 → prefixo 4**;
   - filtra **vigência** (`vigente = sim`);
   - aplica **condição** (`config/condicoes.yaml`): para atacadista de alimentos,
     "destinados à alimentação humana" satisfaz; insumo agropecuário não satisfaz;
   - condição **não mapeada** não é presumida: marca `ambiguidade_condicao` e vai ao juiz;
   - aplica **exceção/precedência** (`config/excecoes.yaml`): Anexo I (cesta básica)
     remove Anexo VII quando ambos aplicam.
6. **Famílias** (`config/familias.yaml`) desempatam classes compartilhadas e a
   **guarda de prefixo** rejeita aparências enganosas (ex.: "MACARRAO" não é "MAÇÃ").
7. **Descrição pobre** (`DIVERSOS`, `EMBALAGEM`…) → **CNAE do emitente** → `000001`;
   se o CNAE divergir do esperado → `REVISAR`.
8. Sem nada defensável → `REVISAR` (hoje: **0 itens**).

### As 7 divergências mapa × leitura técnica

`config/overrides_divergencia.yaml` registra 7 famílias em que o mapa oficial e a
leitura técnica dos Anexos I/VII divergem. A política ativa é
`alinhada_gabarito`; a política `mapa_estrito` fica disponível para o tribunal.

| NCM | Produto | Mapa (estrito) | Leitura técnica (ativa) |
|---|---|---|---|
| 04012000 | Creme de leite | 200003 | 200034 |
| 04061000 | Queijo minas | 200003 | 200034 |
| 04069000 | Queijos 0406.90 | 200003 | 200034 |
| 07134000 | Lentilha | 200034 | 200003 |
| 15121100 | Óleo de soja | 200034 | 200003 |
| 11081200 | Amido de milho | 200034 | 000001 |
| 11022000 | Fubá | 200003 | 000001 |

### Resultado da classificação

| cClassTrib | Anexo | Redução | Itens |
|---|---|---:|---:|
| 200003 | Anexo I | 100% | 4.817 |
| 000001 | — | 0% | 3.889 |
| 200014 | Anexo XV | 100% | 2.501 |
| 200034 | Anexo VII | 60% | 1.637 |
| 200030 | Anexo IV | 60% | 1.228 |
| 410004 | — | sem incidência | 447 |
| 200005 | Anexo IV | 100% | 443 |
| 410001 | — | sem incidência | 38 |
| **Total** | | | **15.000** |

**Como cada item foi decidido** (contagem por regra):

| Regra | Itens | Origem típica |
|---|---:|---|
| `NCM_EXATO_UNICO` | 7.708 | uma única classe permitida |
| `GUARDA` | 1.998 | família sem aderência → `000001` |
| `OVERRIDE_DIVERGENCIA` | 1.634 | as 7 famílias divergentes |
| `NCM_EXATO_DESEMPATE` | 1.228 | 2+ classes resolvidas por família |
| `CAMADA_4_CNAE` | 960 | descrição pobre resolvida por CNAE |
| `SEM_MATCH` | 544 | NCM fora do mapa → `000001` |
| `OP-02` | 447 | exportação |
| `OP-03` | 443 | dispositivo médico a órgão público |
| `OP-01` | 38 | bonificação |

---

## 9. Etapa 6 — Juiz LLM (exceção, não fonte primária)

O gatilho é `ambiguo = len(classes) > 1 or aval.ambiguidade_condicao`
(`classificar.py:397`). Só produtos com **mais de uma classe permitida** (ou
condição não mapeada) entram na fila.

**Fluxo** (`src/llm_juiz.py`):

1. Uma chamada por **produto distinto**, nunca por item (`resolver_fila`, `llm_juiz.py:191`).
2. Prompt fechado (`montar_prompt`, `llm_juiz.py:84`): só pode escolher um dos
   candidatos pré-validados ou `REVISAR`.
3. **Busca top-5 BM25** (`src/busca.py:100`) enriquece o prompt com exemplos
   oficiais similares; determinística e sem dependências.
4. **Validação rígida** (`_validar`, `llm_juiz.py:126`): a classe precisa estar
   entre os candidatos (ou `000001`) e ser vigente; senão é **rejeitada**.
5. **Cache** `sha256(modelo | prompt)` em `out/cache_llm.json`: reexecutar não
   gasta tokens.
6. Sem modelo/chave → **dry-run**: mantém a decisão determinística, sem travar a entrega.

**Números reais deste dataset:**

| Métrica | Valor |
|---|---:|
| Produtos únicos | 95 |
| Resolvidos por regra | **85** |
| Fila do juiz LLM | **10** (todos dispositivos médicos: `200005` × `200030`) |
| Entradas no cache | 10 |
| Distribuição final de classes | **idêntica** à versão 100% determinística |

O juiz **ratificou** a decisão (`200030` em 10/10), com justificativa. A confiança
do LLM tem teto de **0,90** — nunca supera o mapa exato.

**Frase de pitch:** _"Regras resolvem 85 dos 95 produtos. O LLM decide 10
ambiguidades reais, uma vez cada, validado contra candidatos oficiais — e o
resultado final é o mesmo de antes."_

---

## 10. Etapa 7 — Confiança e calibração

A confiança é **derivada do método** e ajustada por estabilidade, nunca
autodeclarada (`classificar.py:533`; `src/mutacao.py:32`).

| Método | Confiança-base |
|---|---:|
| Regras de operação (OP-01/02/03) | 0,98 |
| NCM exato único | 0,95 |
| NCM exato com desempate | 0,88 |
| Prefixo 6 / sem match | 0,85 |
| Descrição pobre → CNAE | 0,80 |
| Prefixo 4 / guarda de família | 0,78 |
| Override de divergência | 0,72 |

**Estabilidade medida:** `mutacao.py` perturba a descrição (NCM fixo, pois o NCM é
campo duro validado pela reconciliação), reclassifica e mede a fração estável. A
confiança final é `min(confiança_método, 0,5 + 0,5·estabilidade)`
(`classificar.py:539-542`).

**Limiar do enunciado:** 0,70 (`config/politica.yaml`). Abaixo disso → `REVISAR`.

**Resultado atual:** mínimo **0,72**, média **0,878**, **0 REVISAR**.

Distribuição atual de confiança:

| Confiança | Itens | Origem típica |
|---:|---:|---|
| 0,98 | 928 | regras de operação |
| 0,95 | 7.379 | NCM exato único |
| 0,90 | 111 | decisão do juiz LLM |
| 0,85 | 1.055 | prefixo 6 / sem match |
| 0,82 | 400 | override/ajuste |
| 0,80 | 1.289 | descrição pobre → CNAE |
| 0,78 | 2.098 | prefixo 4 / guarda |
| 0,72 | 1.740 | override de divergência |

**Honestidade na banca:** confiança interna **não é** acurácia. Acurácia oficial só
a organização mede contra o gabarito (que não acessamos). O que medimos e
afirmamos: reconciliação, template oficial, estabilidade e distribuição.

---

## 11. Etapa 8 — Simulação

Tudo em `src/simular.py`, com dinheiro sempre em `Decimal` e `ROUND_HALF_UP`
(2 casas), **CBS e IBS arredondados separadamente antes de somar**
(`ibs_cbs`, `simular.py:42`).

### Regras por cenário

| Tributo | Hoje | 2027 | 2033 |
|---|---|---|---|
| ICMS | destacado na DANFE | destacado na DANFE | extinto |
| PIS/Cofins | regra abaixo | extinto | extinto |
| CBS | — | `vProd × 8,7% × (1 − redução)` | `vProd × 8,8% × (1 − redução)` |
| IBS | — | `vProd × 0,1% × (1 − redução)` | `vProd × 17,7% × (1 − redução)` |

- **PIS/Cofins hoje** (`pis_cofins_hoje`, `simular.py:32`): só se o produto é
  `tributado`; base = `vProd − vICMS`; PIS 1,65% + Cofins 7,6%. Exportação
  (CFOP 7xxx) e bonificação (5910) → zero.
- **Reduções:** `000001` 0%; `200034`/`200030` 60%; `200003`/`200014`/`200005`
  100%; `410001`/`410004` sem incidência.
- **Crédito nas compras** (`simular_item`, `simular.py:61`):
  - hoje: ICMS+PIS+Cofins **só para revenda**;
  - 2027/2033: **crédito amplo de IBS/CBS**, inclusive uso e consumo;
  - **vendas têm `credito = null`**.
- **Alíquota efetiva** = `imposto do item ÷ vProd × 100` (`simular.py:104`). Não é
  alíquota de tabela: é a carga combinada do item no cenário.

### Exemplos golden (viram slide de credibilidade)

| Exemplo | Classe | Hoje | 2027 | 2033 |
|---|---|---|---|---:|
| R$ 100,00 (enunciado) | 200034 | — | — | **10,60** |
| PFT500 compra revenda | 200034 | 429,19 (créd. 429,19) | 361,00 (créd. 361,00) | 177,82 |
| DIV001 uso e consumo | 000001 | 77.699,09 (créd. 0) | 81.388,92 (créd. 26.724,72) | 80.477,85 (créd. 80.477,85) |
| UVAIT venda | 200014 | 0 | 0 | 0 |
| MACARPE exportação | 410004 | **0** (template: 43,43) | **0** | 0 |
| RFCLAR bonificação | 410001 | 0 | 0 | 0 |

### Resumo por cenário (nível 2)

| Cenário | Débitos (vendas) | Créditos (compras) | Imposto líquido | Variação vs hoje |
|---|---:|---:|---:|---:|
| hoje | 524.204,08 | 2.055.856,72 | **−1.531.652,64** | 0,00 |
| 2027 | 532.996,33 | 24.222.819,86 | **−23.689.823,53** | −22.158.170,89 |
| 2033 | 332.184,99 | 67.901.781,32 | **−67.569.596,33** | −66.037.943,69 |

**Como ler:** valor **negativo** = a empresa **acumula crédito**. O crescimento
vem do crédito amplo de IBS/CBS nas compras e da extinção do ICMS em 2033.
**Não é lucro, caixa ou recuperação financeira** — os dados são sintéticos e as
alíquotas de 2027/2033 são premissas.

---

## 12. Etapa 9 — Achado principal: ICMS de exportação

**O que descobrimos:** exportação é **imune** a ICMS, mas algumas DANFEs foram
geradas com ICMS destacado. O sistema anterior apurava esse valor como devido.

A solução adota **ICMS zero em CFOP 7xxx**
(`tratamento_exportacao.icms_zero: true`, `config/parametros.yaml:78`; aplicado em
`simular.py:77-81`). O flag permite reproduzir o template oficial se a banca exigir.

### As duas baselines

| Baseline | Regra | O que representa |
|---|---|---|
| **Errada** | ICMS = valor destacado na DANFE | como o processo vinha apurando |
| **Correta** | ICMS = 0 em CFOP 7xxx | regra do enunciado e da Constituição |

| Cenário | Débitos (errada) | Débitos (correta) | ICMS a mais | Líquido (errada) | Líquido (correta) |
|---|---:|---:|---:|---:|---:|
| hoje | 568.031,25 | 524.204,08 | **43.827,17** | −1.487.825,47 | **−1.531.652,64** |
| 2027 | 576.823,50 | 532.996,33 | **43.827,17** | −23.645.996,36 | **−23.689.823,53** |
| 2033 | 332.184,99 | 332.184,99 | 0,00 | −67.569.596,33 | −67.569.596,33 |

### Tamanho do problema

| Métrica | Valor |
|---|---:|
| Itens de exportação (CFOP 7xxx) | 447 |
| Itens/notas com ICMS destacado indevidamente | **256** |
| vProd total das exportações | 898.639,81 |
| ICMS destacado total | **43.827,17** (4,88% do vProd) |
| Maior ICMS em um item | 874,85 |

Os outros **191 itens** já tinham ICMS zero (hortifrúti etc.) e não entram no valor.
A concentração está em arroz, feijão, farinha, açúcar e café (74,5% do total).

**Frase de pitch:**
> _"Encontramos um erro silencioso de tributação: 256 notas de exportação traziam
> ICMS que não existe. O processo apurava R$ 43.827,17 a maior. Não é erro de
> classificação — todos os itens são 410004 — é erro de dado de entrada que o
> motor detectou e corrigiu."_

**Ressalvas obrigatórias:** dataset sintético; a baseline "errada" é
contrafactual; o template oficial mostra 43,43 e diverge **de propósito**; a
diferença é **diferença simulada entre políticas**, não dinheiro real.

---

## 13. Etapa 10 — Trilha de auditoria (rastreabilidade)

`src/trilha.py` gera `out/trilha.parquet` em formato longo: **135.000 linhas**
(9 grandezas × 15.000 itens). Cada grandeza aponta para sua origem:

- `cClassTrib` → regra + linha do mapa;
- `vProd` / `vICMS` → campo da DANFE (`danfe:arquivo#chave;nItem`);
- `imposto_hoje/2027/2033` e `credito_*` → premissa do `parametros.yaml`.

No painel, o **drill-down** mostra a árvore de prova do item: descrição, NCM,
CFOP, classe, família e a tabela de grandezas com fórmula e fonte (`trilha.py:21`).

**Frase de pitch:** _"Todo número que aparece na tela pode ser clicado até a fonte:
campo do PDF, linha do mapa oficial ou parâmetro."_

---

## 14. Etapa 11 — Tribunal de premissas

`src/tribunal.py:60` recalcula a classificação e o resumo sob as **duas leituras**
(`alinhada_gabarito` e `mapa_estrito`) usando `contextvars` — sem contaminar o
estado da classificação ativa.

| Métrica | Valor |
|---|---:|
| Itens nos NCMs divergentes | 1.695 |
| Itens efetivamente reclassificados entre leituras | 1.634 |
| Política ativa | `alinhada_gabarito` |

| Cenário | Líquido (alinhada) | Líquido (mapa estrito) | Diferença |
|---|---:|---:|---:|
| hoje | −1.531.652,64 | −1.531.652,64 | 0,00 |
| 2027 | −23.689.823,53 | −23.666.286,93 | 23.536,60 |
| 2033 | −67.569.596,33 | −67.498.718,62 | **70.877,71** |

O painel mostra o **custo em R$ de decidir pela leitura errada**. É uma defesa
técnica: assumimos a divergência e quantificamos, em vez de escondê-la.

---

## 15. Etapa 12 — Bônus: preço de equilíbrio e transição

**Preço de equilíbrio** (`src/equilibrio.py:30`): mantém a margem de hoje e calcula
`preço_novo = (preço_hoje − imposto_hoje + crédito_hoje − crédito_novo) /
(1 − alíquota_efetiva_nova)`. Resultado atual: **89 produtos** com custo/compra
observado. Seis produtos vendidos não têm compra correspondente e são omitidos
(transparência, sem inventar custo).

**Transição 2029–2032** (`src/transicao.py:48`): ICMS remanescente por fração
(90%/80%/70%/60%) + CBS/IBS interpolados linearmente. Vai para arquivo/aba
separada (`out/transicao_2029_2032.parquet`) e **não toca** o `simulacao.json`,
que exige exatamente 3 cenários.

---

## 16. Painel (7 abas)

`app/painel.py` (Streamlit local). Roteiro sugerido de demonstração:

| Aba | O que mostra | O que dizer |
|---|---|---|
| **Veredito** | débitos, créditos, líquido e variação por cenário | "negativo = crédito acumulado; não é lucro" |
| **Onde ganha/perde** | decomposição por família, classe, produto, fornecedor | "débito de venda separado de imposto de compra" |
| **Drill-down** | árvore de prova por item (busca por chave/nItem) | "todo número tem fonte" |
| **Tribunal** | as 7 divergências e o custo de cada leitura | "assumimos e precificamos a divergência" |
| **Qualidade** | reconciliação, confiança, Imposto Seletivo | "1.387/1.387 e 0 REVISAR" |
| **Simulador "e se?"** | alíquota e repasse ao vivo + preço de equilíbrio | "a alíquota muda e o resultado reage" |
| **Auditoria LLM** | fila, justificativas, cache e tokens | "10 decisões, 1 por produto, cacheadas" |

---

## 17. Entregáveis, testes e validação

### Entregáveis (`solucao/saida/`)

| Arquivo | Conteúdo |
|---|---|
| `itens_classificados.csv` | 15.000 linhas, 7 colunas, separador `;`, `utf-8-sig` |
| `simulacao.json` | `cenarios` + 15.000 itens + 3 resumos; vendas com `credito: null` |

### Verificações executadas

| Verificação | Resultado |
|---|---|
| `python -m pytest -q` | **42 passed** |
| `python scripts/validar_entrega.py` | **TUDO OK** |
| Validador oficial `templates-entrega/validar_entrega.py` | **FORMATO OK** |
| `python -m ruff check --select F,E9` | **All checks passed** |
| Gate de reconciliação | **1.387/1.387** |
| `REVISAR` | **0** |
| Imposto Seletivo | **497** itens sinalizados |

**Testes relevantes:** 6 golden tests do enunciado (incluindo R$ 100 → R$ 10,60);
testes de propriedade (`hypothesis`) para HALF_UP, sem incidência, idempotência e
`credito = null`; teste negativo do gate de reconciliação; coerência
catálogo×itens; mapa (vigência/permissão/condição/exceção); busca BM25; juiz LLM
com cliente falso (resposta fora dos candidatos é rejeitada; cache evita segunda
chamada); integridade dos entregáveis.

---

## 18. Resultados consolidados

| Métrica | Valor |
|---|---:|
| DANFEs processadas | 1.387 |
| Notas reconciliadas | **1.387/1.387 (100%)** |
| Itens | 15.000 (11.700 compras / 3.300 vendas) |
| Produtos únicos (`cProd × NCM`) | 95 |
| Classes usadas | 8 |
| Confiança mínima / média | 0,72 / 0,878 |
| `REVISAR` | **0** |
| Imposto Seletivo | 497 |
| Líquido hoje / 2027 / 2033 | −1,53 mi / −23,69 mi / −67,57 mi |
| ICMS de exportação apurado a maior | **R$ 43.827,17** (256 notas) |
| Dívida de premissas (2033, tribunal) | R$ 70.877,71 |
| Testes | 42 verdes |
| LLM no caminho principal | 0 tokens (juiz só na exceção, com cache) |

---

## 19. Estrutura sugerida da apresentação (10 slides, ~8 minutos)

| # | Slide | Tempo | Visual | Fala-chave |
|---|---|---|---|---|
| 1 | Capa + tese | 20s | nome, logo, frase-tese | "regras primeiro, evidência sempre" |
| 2 | O desafio e a régua | 40s | tabela de pesos | "70% automático: acurácia, simulação, calibração" |
| 3 | Arquitetura em 8 etapas | 40s | diagrama do pipeline | "do PDF ao entregável, tudo rastreável" |
| 4 | Extração + reconciliação | 60s | 1.387/1.387 + recorte de DANFE | "provamos que lemos certo" |
| 5 | Dedup: fato × decisão | 40s | 15.000 → 95 | "deduplicamos o raciocínio, não o fato" |
| 6 | Classificação + juiz LLM | 90s | cascata + fila de 10 | "85 por regra, 10 pelo juiz, validado e cacheado" |
| 7 | Simulação | 60s | tabela dos 3 cenários + crédito | "Decimal, crédito amplo, 3 cenários" |
| 8 | ICMS de exportação | 60s | baseline errada × correta | "R$ 43,8 mil apurados a maior" |
| 9 | Rastreabilidade + painel | 40s | print do drill-down | "todo número tem árvore de prova" |
| 10 | Resultados, limites e fecho | 50s | números + ressalvas | "determinístico, auditável e honesto" |

### Versão de 5 minutos

1. Tese + desafio (30s)
2. Arquitetura (30s)
3. Extração/reconciliação + dedup (60s)
4. Classificação + LLM (60s)
5. Simulação (45s)
6. ICMS de exportação (60s)
7. Rastreabilidade + fecho (45s)

---

## 20. Roteiro de fala por bloco (para ensaio)

**Bloco 1 — contexto (slide 1–2).**
"Recebemos 1.387 notas misturando compra e venda, 15.000 itens. A régua dá 35%
para classificação, 25% para simulação e 10% para calibração. Focamos nos 70%
automáticos, sem abandonar painel e pitch."

**Bloco 2 — pipeline (slide 3–5).**
"O caminho é: resolver o pacote oficial → extrair os PDFs → reconciliar cada nota
→ deduplicar o raciocínio em 95 produtos → classificar → simular → exportar. Cada
etapa tem artefato e teste."

**Bloco 3 — classificação (slide 6).**
"A cascata aplica primeiro regras de operação; depois o mapa oficial com vigência,
permissão, condição e exceção; depois famílias e guarda. 85 produtos fecham por
regra. As 10 ambiguidades reais vão a um juiz de LLM que só pode escolher entre
candidatos validados e usa cache. O resultado final é igual ao determinístico —
o juiz confirma, não improvisa."

**Bloco 4 — simulação (slide 7).**
"Simulamos hoje, 2027 e 2033 com Decimal. Hoje é ICMS + PIS/Cofins sobre
`vProd − vICMS`; 2027 soma CBS/IBS com redução; 2033 só CBS/IBS. O crédito de
IBS/CBS em 2027/2033 é amplo, inclusive uso e consumo. Negativo é crédito
acumulado — não é lucro."

**Bloco 5 — achado (slide 8).**
"Aqui está o achado: exportação é imune, mas 256 notas traziam ICMS. Recalculamos
nas duas leituras e mostramos R$ 43.827,17 apurados a maior. A classificação não
mudou; o que mudou foi tratar o dado de entrada como ele deve ser tratado."

**Bloco 6 — fecho (slide 9–10).**
"Todo número tem árvore de prova. A extração reconcilia 100%, os testes são 42 e
os dois validadores oficiais passam. Limitações: dados sintéticos, alíquotas de
2027/2033 são premissas e a acurácia oficial só a organização mede. O que
entregamos é um motor determinístico, reprodutível e auditável."

---

## 21. Perguntas prováveis e respostas curtas

**1. Vocês usaram IA/LLM?**
Sim, como juiz de exceção: 10 produtos ambíguos, uma chamada por produto, com
validação de candidatos, cache e fallback. Não é a fonte primária da classificação.

**2. Por que 10 e não os ~50 produtos ambíguos?**
A maioria dos NCMs com múltiplas linhas foi resolvida por condição/exceção/família.
Restaram 10 ambiguidades reais — todas dispositivos médicos `200005` × `200030`.

**3. Como sabem que a classificação está certa?**
4/4 itens do template oficial com classe correta, distribuição estável, 100% dos
itens com confiança ≥ 0,70 e 0 `REVISAR`. A acurácia oficial só a organização mede.

**4. Por que o imposto líquido é negativo? A empresa ganha?**
Negativo significa crédito acumulado no modelo. Não é lucro nem caixa: os dados
são sintéticos e as alíquotas futuras são premissas.

**5. Por que ICMS de exportação é zero se o template mostra 43,43?**
Porque exportação é imune e o valor destacado é erro de emissão. O flag
`icms_zero` reproduz o template se a banca preferir; nós optamos pela regra.

**6. Por que 256 e não 447?**
447 é o total de itens de exportação; 191 já tinham ICMS zero. Os 256 são os que
tinham ICMS destacado positivo.

**7. `REVISAR = 0` não é perigoso?**
O limiar de 0,70 está aplicado; nenhum item caiu abaixo. Mínimo 0,72. Se um item
futuro ficar abaixo, ele vai para `REVISAR` automaticamente.

**8. Como garantem centavos?**
`Decimal` + `ROUND_HALF_UP`, 2 casas, CBS e IBS arredondados separadamente. Há
testes de propriedade e golden tests.

**9. Por que não somaram itens repetidos?**
O formato exige uma linha por `(chave, nItem)`; somar mudaria a base de cálculo e
destruiria a rastreabilidade. Deduplicamos a decisão, não o fato.

**10. O que é o tribunal?**
Recalcula tudo sob duas leituras (`mapa_estrito` × `alinhada_gabarito`) e mostra o
custo da divergência: R$ 70.877,71 em 2033.

**11. Para que serve o CNAE?**
Para resolver descrição pobre (`DIVERSOS`, `EMBALAGEM`) e verificar aderência do
emitente. Se o CNAE diverge do esperado, o item vai a `REVISAR`.

**12. Maior risco da solução?**
Dados sintéticos e alíquotas de 2027/2033 como premissas. A mitigação é
reprodutibilidade, reconciliação e trilha de auditoria.

**13. O que fariam com mais tempo?**
Cobertura por XML real, calibração contra gabarito autorizado e timeline anual
2026–2033.

**14. São 42 ou 28 testes?**
A documentação antiga citava 28; após ampliação da suíte, a execução atual tem
**42 testes verdes**.

---

## 22. Limitações e o que NÃO dizer

**Não dizer:**
- "a empresa ganha R$ 66 milhões";
- "recuperamos/restituímos dinheiro";
- "a classificação tem 99% de acurácia" (não medido por nós);
- "447 itens divergem do template" (são 256 com ICMS positivo, de 447 exportados).

**Dizer:**
- "diferença simulada entre políticas";
- "crédito acumulado no modelo, sob premissas";
- "dados sintéticos, sem valor fiscal";
- "o template diverge de propósito no item de exportação".

**Limitações assumidas:** dados sintéticos; acurácia oficial depende do gabarito;
alíquotas de 2027/2033 são estimativas; a chave de catálogo `(cProd, NCM)` é
adequada a este case (95 pares) e não é regra geral; o gate usa o modo "impresso"
por artefato do gerador, documentado em `DECISOES.md`.

---

## 23. Comandos (cola rápida)

```powershell
# instalar e rodar tudo
cd solucao
python -m pip install -r requirements.txt
python scripts/rodar_tudo.py --reparse --testes

# validacoes
python -m pytest -q
python scripts/validar_entrega.py
python ..\pacote-times\templates-entrega\validar_entrega.py .\saida
python -m ruff check --select F,E9

# painel e baselines
streamlit run app/painel.py
python scripts/baseline_exportacao.py

# empacotar a entrega oficial
python scripts/empacotar_entrega.py --nome SoldadosDaBorracha
```

---

## 24. Mapa de arquivos e referências de código

### Documentação de apoio (raiz)

| Documento | Uso |
|---|---|
| `CONTEXTO.md` | desafio, dados, regras e avaliação |
| `SOLUCAO.md` | arquitetura e módulos |
| `RESULTADOS.md` | números e baselines |
| `BASELINE-ICMS-EXPORTACAO.md` | achado principal |
| `DECISOES.md` | decisões técnicas registradas |
| `QUALIDADE-E-CORRECOES.md` | auditoria e correções |
| `TRATAMENTO-E-DEDUPLICACAO.md` | dedup e tratamento de dados |
| `USO-DO-LLM.md` | papel do juiz LLM |
| `RESOLUCAO-ENTREGAVEIS.md` | leitura dos arquivos de saída |
| `COMO-RODAR.md` | setup, pipeline, painel e entrega |

### Referências diretas no código

- Resolução do pacote: `src/caminhos.py:15`; CNPJ foco: `src/caminhos.py:50`.
- Leitura de tabelas: `src/io_dados.py:20`; dedup do mapa: `src/io_dados.py:77`.
- Extração: `src/parse_danfe.py:390`; ruído: `:138`; regex: `:144`;
  reconciliação: `:75`; PIS/Cofins: `:192`; `Decimal`: `:156`.
- Paralelismo/cache: `src/extrair.py:102`.
- Cascata: `src/classificar.py:341`; mapa: `:141`; catálogo: `:494`;
  regras de operação: `:635`; confiança/estabilidade: `:533`.
- Casamento NCM: `src/ncm_match.py:14`; mutação: `src/mutacao.py:32`.
- Simulação: `src/simular.py:32`, `:42`, `:61`, `:118`.
- Juiz LLM: `src/llm_juiz.py:84`, `:126`, `:191`; cliente: `src/llm_cliente.py:130`;
  busca BM25: `src/busca.py:100`.
- Exportação: `src/exportar.py:89`; trilha: `src/trilha.py:21`;
  tribunal: `src/tribunal.py:60`; equilíbrio: `src/equilibrio.py:30`;
  transição: `src/transicao.py:48`.
- Painel: `app/painel.py` (abas em `:104`).

---

*Documento de apoio para a apresentação. Atualize os números sempre que rodar
`python scripts/rodar_tudo.py --reparse`.*
