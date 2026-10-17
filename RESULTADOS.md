# Resultados da solução

Todos os números abaixo vêm da execução com o **pacote oficial novo**
(`pacote-times/dados`), solução retificada e ICMS de exportação = zero.

---

## 1. Extração e qualidade

| Métrica | Valor |
|---|---:|
| Notas | 1.387 |
| Notas reconciliadas (vProd, vICMS, PIS, COFINS) | **1.387/1.387 (100%)** |
| Itens | 15.000 |
| Compras / vendas | 720 / 667 notas (11.700 / 3.300 itens) |
| CFOP 5102 / 5101 / 7102 / 5910 | 11.516 / 2.999 / 447 / 38 |
| `REVISAR` | **0** |
| Confiança mínima / média | 0,72 / 0,878 |
| Itens com Imposto Seletivo | 497 |

---

## 2. Classificação

| cClassTrib | Anexo | Redução | Itens |
|---|---|---:|---:|
| 200003 | I | 100% | 4.817 |
| 000001 | — | 0% | 3.889 |
| 200014 | XV | 100% | 2.501 |
| 200034 | VII | 60% | 1.637 |
| 200030 | IV | 60% | 1.228 |
| 410004 | — | sem incidência | 447 |
| 200005 | IV | 100% | 443 |
| 410001 | — | sem incidência | 38 |

Todas as 8 classes são vigentes e têm CST válido. Os 447 itens de exportação são
todos `410004`.

### 2.1 Juiz LLM (exceções)

Aplicado `avaliar_mapa` (vigência/permissão/condição/exceção), restaram **10
produtos ambíguos** (todos dispositivos médicos `200005` × `200030`). O juiz LLM
decidiu **10/10** com justificativa, `confianca ≤ 0,90`, **0 `REVISAR`** e a
distribuição de classes **inalterada**.

| Etapa | Quantidade |
|---|---:|
| Produtos únicos (`cProd × NCM`) | 95 |
| Produtos com >1 candidato bruto no mapa | ~47 |
| **Fila do juiz LLM** | **10** |
| Chamadas (1ª execução) | **10** (~3.683 tokens de entrada / 5.583 de saída) |
| Chamadas seguintes (cache) | 0 |

Artefatos: `out/auditoria_ambiguos.csv`, `out/cache_llm.json`,
`out/uso_tokens.json`. Detalhes em `USO-DO-LLM.md`.

---

## 3. Simulação (nível 2)

| Cenário | Débitos (vendas) | Créditos (compras) | Imposto líquido | Variação vs hoje |
|---|---:|---:|---:|---:|
| hoje | 524.204,08 | 2.055.856,72 | **−1.531.652,64** | 0,00 |
| 2027 | 532.996,33 | 24.222.819,86 | **−23.689.823,53** | −22.158.170,89 |
| 2033 | 332.184,99 | 67.901.781,32 | **−67.569.596,33** | −66.037.943,69 |

Leitura: negativo = crédito acumulado. O crédito amplo de IBS/CBS nas compras e
a extinção do ICMS em 2033 explicam a trajetória.

---

## 4. Destaque: ICMS de exportação apurado a maior

| Cenário | Líquido com ICMS destacado (errado) | Líquido com ICMS zero (correto) | ICMS a mais |
|---|---:|---:|---:|
| hoje | −1.487.825,47 | **−1.531.652,64** | **43.827,17** |
| 2027 | −23.645.996,36 | **−23.689.823,53** | **43.827,17** |
| 2033 | −67.569.596,33 | −67.569.596,33 | 0,00 |

- **256 notas** de exportação com ICMS destacado indevidamente.
- **R$ 43.827,17** apurados a mais em hoje/2027 (4,88% do vProd das exportações).
- Como o líquido é negativo, o erro **reduzia o crédito em R$ 43.827,17**
  (equivalente a imposto pago/compensado a maior).
- Em 2033 o ICMS é extinto; as baselines coincidem.

Detalhes e narrativa de pitch: `BASELINE-ICMS-EXPORTACAO.md`.

---

## 5. Comparação com o template oficial

| Item | Classe | Hoje | 2027 | 2033 |
|---|---|---|---|---|
| Arroz (compra revenda) | 200003 | 168,13 / créd. 168,13 | 168,13 / créd. 168,13 | 0 / 0 |
| DIVERSOS (uso e consumo) | 000001 | 77.699,09 / créd. 0 | 81.388,92 / créd. 26.724,72 | 80.477,85 / créd. 80.477,85 |
| Exportação | 410004 | **0** (template: 43,43) | **0** (template: 43,43) | 0 |
| Dispositivo médico a órgão público | 200005 | 0 | 0 | 0 |

**3 dos 4 itens batem integralmente.** O item de exportação diverge de propósito:
o template oficial carrega o ICMS destacado, que é justamente o erro de emissão
identificado. A classificação dos 4 itens é idêntica.

---

## 6. Validação

| Verificação | Resultado |
|---|---|
| `python -m pytest -q` | **42 passed** |
| `python scripts/validar_entrega.py` | **TUDO OK** |
| Validador oficial (`templates-entrega/validar_entrega.py`) | **FORMATO OK** |
| `ruff check --select F,E9` | **All checks passed** |
| Distribuição de classes | idêntica à execução anterior |
| Números do resumo | estáveis e reconciliados |

---

## 7. Sobre acurácia

A acurácia oficial só pode ser medida pela organização contra o gabarito
(`04-gabarito-organizacao`, fora desta pasta e não utilizada). O que é possível
afirmar com os artefatos oficiais:

- **Classificação:** 4/4 itens do template com classe correta; distribuição
  estável; 100% dos itens com confiança ≥ 0,70; 0 `REVISAR`.
- **Simulação:** 3/4 itens do template exatos; o item de exportação segue a
  decisão de ICMS zero.
- **Exposição:** se a banca usar o ICMS destacado do template como referência,
  os **256 itens com ICMS positivo** (1,71% dos 15.000) divergem em hoje/2027;
  os 447 são exportações no total, das quais 191 já tinham ICMS zero. Se usar a
  regra do enunciado, estão corretos.

---

## 8. Resumo para o pitch

> A Meridional acumula crédito no regime novo: o líquido vai de −R$ 1,53 mi hoje
> para −R$ 23,69 mi em 2027 e −R$ 67,57 mi em 2033. Além disso, corrigimos um erro
> silencioso: 256 notas de exportação tinham ICMS indevido, R$ 43,8 mil a maior.
> A classificação está estável, sem itens em revisão, e todo número tem origem
> rastreável.
