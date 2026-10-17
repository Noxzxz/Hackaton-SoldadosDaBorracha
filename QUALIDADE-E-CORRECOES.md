# Qualidade e correções aplicadas

Resumo da auditoria multi-agente e das correções incorporadas à solução. Os
relatórios detalhados originais (`AVALIACAO-MULTI-AGENTE.md`, `CORRECOES.md`,
`PARECER-CORRECOES.md`) ficaram fora desta pasta para evitar duplicidade; o
essencial está consolidado aqui e em `DECISOES.md`.

---

## 1. Auditoria em quatro perspectivas

| Avaliador | Foco | Principais achados |
|---|---|---|
| Arquiteto de software | Código, testes, dívida técnica | cache YAML, import dinâmico, O(n²) na trilha, código morto |
| Fiscalista tributário | Regras, classificação, simulação | `REVISAR` nunca usado, overrides sem referência legal, ICMS de exportação |
| Analista de negócio | Painel, rastreabilidade, pitch | débito × crédito misturados, gráfico ilegível, drill-down limitado |
| QA / riscos | Robustez, calibração, falhas silenciosas | `except` silencioso, race condition no tribunal, parsing mascarado |

Total: **27 defeitos** (5 altos, 11 médios, 11 baixos).

---

## 2. Correções de maior impacto

| ID | Correção | Efeito |
|---|---|---|
| P1 | Cache de YAML invalidado por `mtime` + `recarregar_config()` | editar config sem reiniciar o processo |
| P8 | Limiar de `REVISAR` configurável (0,70) | conformidade com o enunciado |
| P14 | Decomposição separa débito de venda × imposto de compra | clareza para a banca |
| P20 | `logging.warning` no fallback de estabilidade | falha deixa de ser silenciosa |
| P21 | Tribunal com `contextvars`, sem mutar cache global | sem race condition / estado contaminado |
| P2/P3/P4 | `--workers`, import estático, índice na trilha | robustez e performance |
| P9 | `referencia_legal` nos 7 overrides | defesa técnica |
| P11 | Desempate em `config/desempates.yaml` | configuração em vez de hardcode |
| P22/P23/P24 | logs no parsing, serialização de confiança e booleano | menos falhas silenciosas |
| P15/P16/P17/P18 | gráficos, créditos no simulador, busca, projeção | painel mais claro |

As correções não alteraram a classificação dos 15.000 itens. A única mudança de
resultado foi intencional: ICMS de exportação = zero.

---

## 3. Calibração

- Confiança derivada do método (OP 0,98; NCM exato único 0,95; exato com
  desempate 0,88; prefixo6 0,85; sem match 0,85; CNAE 0,80; guarda 0,78;
  prefixo4 0,75; override 0,72).
- Confiança ajustada por estabilidade a mutações de descrição.
- Resultado atual: **0 `REVISAR`**, mínimo 0,72, média 0,865.
- O limiar do enunciado está aplicado; se algum item futuro cair abaixo de 0,70,
  ele vai para `REVISAR`.

---

## 4. Testes e validação

| Verificação | Resultado |
|---|---|
| `pytest` | **28 testes verdes** |
| Golden tests do enunciado | 6 cenários (inclui R$ 100 → R$ 10,60) |
| Propriedades (hypothesis) | HALF_UP, sem incidência, idempotência, crédito null |
| Gate de reconciliação | **1.387/1.387** notas |
| `scripts/validar_entrega.py` | **TUDO OK** |
| Validador oficial | **FORMATO OK** |
| `ruff check --select F,E9` | **All checks passed** |

Testes novos relevantes:

- `test_reconciliacao_detecta_nota_corrompida` — caminho negativo do gate.
- `test_coerencia_catalogo_itens` — item segue o catálogo salvo regra de operação.
- `test_exportacao_icms_template_fallback` — flag reproduz o template quando
  desligado.
- `test_simulador_e_se_repasse` — o repasse muda preço/débito quando a alíquota
  difere de 26,5%.

---

## 5. Riscos residuais

1. **Contradição oficial:** o template mostra ICMS 43,43 na exportação; adotamos
   zero por decisão de negócio. Se a banca usar o template, **256 itens** divergem
   em hoje/2027 (dos 447 exportados; 191 já tinham ICMS zero).
2. **`REVISAR`:** nenhum item cai abaixo de 0,70 hoje; se a organização exigir
   revisão forçada, o limiar pode ser elevado.
3. **Dados sintéticos:** os valores simulam o case e não uma empresa real.
4. **Acurácia oficial:** só a organização mede contra o gabarito; não acessamos
   `04-gabarito-organizacao`.

---

## 6. Conclusão

A solução está determinística, testada e auditável. As falhas silenciosas foram
substituídas por logs e testes; o estado global mutável foi removido; o painel
ficou legível; e o erro de ICMS de exportação foi identificado, quantificado e
corrigido.
