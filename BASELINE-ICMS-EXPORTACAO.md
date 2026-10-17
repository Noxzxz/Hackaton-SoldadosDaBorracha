# Baseline — ICMS de Exportação: Errado × Correto

> **Caminhos:** comandos e arquivos (`scripts/...`, `out/...`, `config/...`) são
> relativos a `solucao/`.

**Destaque para a apresentação:** o escritório de contabilidade estava apurando
**R$ 43.827,17 de ICMS a mais** em 256 notas de exportação. Exportação é imune;
o valor correto é **zero**. O erro não é de classificação (todos os itens são
`410004`), é de **tributação**: o ICMS destacado na DANFE foi tratado como
devido.

**Arquivo gerado por:** `python scripts/baseline_exportacao.py`
**Dados:** `out/baseline_exportacao.csv`, `out/baseline_exportacao_itens.csv`,
`out/baseline_exportacao.json`

---

## 1. As duas baselines

| Baseline | Regra aplicada | O que representa |
|---|---|---|
| **Errada** | ICMS = valor destacado na DANFE (CFOP 7xxx) | Como o sistema/contabilidade vinha apurando |
| **Correta** | ICMS = 0 em CFOP 7xxx (imunidade) | Regra do enunciado oficial e da Constituição |

A única diferença entre as duas é o ICMS dos itens de exportação. PIS/Cofins já
é zero nesses itens; a classificação (`410004`) é a mesma. Em 2033 o ICMS é
extinto, então as baselines coincidem.

---

## 2. Resultado por cenário

| Cenário | Débitos (errada) | Débitos (correta) | ICMS a mais | Créditos | Líquido (errada) | Líquido (correta) | Efeito no líquido |
|---|---:|---:|---:|---:|---:|---:|---:|
| hoje | 568.031,25 | 524.204,08 | **43.827,17** | 2.055.856,72 | −1.487.825,47 | −1.531.652,64 | **43.827,17** |
| 2027 | 576.823,50 | 532.996,33 | **43.827,17** | 24.222.819,86 | −23.645.996,36 | −23.689.823,53 | **43.827,17** |
| 2033 | 332.184,99 | 332.184,99 | 0,00 | 67.901.781,32 | −67.569.596,33 | −67.569.596,33 | 0,00 |

Leitura: a baseline errada apura **R$ 43.827,17 mais débito** em hoje e 2027.
Como o imposto líquido é negativo (crédito acumulado), o erro **reduz o crédito
em R$ 43.827,17** — equivalente a imposto pago/compensado a maior.

Variação vs. hoje:

| Cenário | Variação (errada) | Variação (correta) |
|---|---:|---:|
| hoje | 0,00 | 0,00 |
| 2027 | −22.158.170,89 | −22.158.170,89 |
| 2033 | −66.081.770,86 | −66.037.943,69 |

A diferença de R$ 43.827,17 aparece na variação de 2033 porque ela é medida
contra o "hoje" inflado.

---

## 3. Tamanho do problema

| Métrica | Valor |
|---|---:|
| Itens de exportação (CFOP 7xxx) | 447 |
| Itens com ICMS destacado indevidamente | **256** |
| Notas afetadas | **256** |
| vProd total das exportações | 898.639,81 |
| ICMS destacado total | **43.827,17** |
| ICMS médio por item afetado | 171,20 |
| Maior ICMS em um item | 874,85 |
| ICMS / vProd das exportações | **4,88%** |
| ICMS / débitos corretos (hoje) | **8,36%** |
| ICMS / crédito acumulado correto (hoje) | **2,86%** |

Os outros 191 itens de exportação já tinham ICMS zero (hortifruti etc.), por isso
não entram no valor.

---

## 4. Onde o erro se concentra (por NCM)

| NCM | Itens | vProd | ICMS destacado |
|---|---:|---:|---:|
| 10063021 — arroz | 39 | 131.369,19 | 9.196,12 |
| 07133319 — feijão | 43 | 113.968,09 | 7.977,98 |
| 11010010 — farinha de trigo | 24 | 93.755,91 | 6.563,11 |
| 17011400 — açúcar | 21 | 72.714,37 | 5.090,16 |
| 09011110 — café | 22 | 54.626,38 | 3.823,96 |
| 15121100 — óleo de soja | 13 | 36.865,95 | 2.580,70 |
| 19021900 — massas | 37 | 34.771,55 | 2.434,08 |
| 11081200 — amido | 17 | 12.236,45 | 2.202,56 |
| 07134000 — lentilha | 15 | 19.145,07 | 1.340,21 |
| 11062000 — fécula | 12 | 17.767,32 | 1.243,74 |
| 11022000 — fubá | 9 | 6.453,31 | 1.161,59 |
| 25010020 — sal | 4 | 3.042,19 | 212,96 |

Os cinco primeiros NCMs concentram **R$ 32.651,33 (74,5%)** do ICMS indevido.

### Maiores itens individuais

| NCM | Produto | vProd | ICMS destacado |
|---|---|---:|---:|
| 07133319 | FEIJAO CARIOCA TIPO 1 PCT 5KG | 12.497,48 | 874,85 |
| 10063021 | ARROZ PARBOILIZADO T1 PCT 5KG | 9.931,11 | 695,20 |
| 07133319 | FEIJAO CARIOCA TIPO 1 PCT 5KG | 9.606,90 | 672,50 |
| 10063021 | ARROZ PARBOILIZADO T1 PCT 5KG | 9.076,80 | 635,39 |
| 10063021 | ARROZ BRANCO T1 PCT 5KG | 8.844,93 | 619,16 |

A lista completa dos 447 itens (com chave, nItem, NCM, vProd e as duas
baselines) está em `out/baseline_exportacao_itens.csv`.

---

## 5. Narrativa para o pitch

> **"Encontramos um erro silencioso de tributação: 256 notas de exportação
> traziam ICMS destacado, mas exportação é imune. O sistema estava apurando
> R$ 43.827,17 de ICMS que não existe — imposto pago/compensado a maior.
> Corrigimos para zero, sem mudar a classificação fiscal dos itens. É dinheiro
> real que volta para o caixa da empresa."**

Sugestão de sequência no painel:

1. Mostrar as duas baselines lado a lado (tabela da seção 2).
2. Mostrar os 256 itens/notas e o total de R$ 43.827,17 (seção 3).
3. Mostrar a concentração por NCM (arroz, feijão, farinha, açúcar, café).
4. Fechar com a frase: "não é erro de IA, é erro de dado de entrada — e o motor
   detectou e corrigiu".

---

## 6. Ressalvas importantes

- O dataset é **sintético**: o valor representa a apuração do case, não uma
  empresa real.
- A baseline "errada" é **contrafactual**: reproduz o ICMS como impresso na
  DANFE. A baseline "correta" é a política adotada (`icms_zero: true`).
- O template oficial de entrega ainda mostra **43,43** no item de exportação —
  exatamente o valor do ICMS destacado. Isso ajuda a explicar a origem do erro,
  mas **não** deve ser usado como regra de cálculo.
- O gate de reconciliação continua usando os totais impressos da DANFE; ele
  valida a **extração**, não a regra tributária. Por isso o erro passava
  despercebido: os números "fechavam" contra a nota, mas a nota estava errada.
- A classificação dos 447 itens é **410004** e não muda entre as baselines.

---

*Gerado em 2026-10-17. Reproduza com `python scripts/baseline_exportacao.py`.*
