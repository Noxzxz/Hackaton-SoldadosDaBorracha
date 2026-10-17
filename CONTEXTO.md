# Contexto geral do desafio

**Fonte oficial:** `pacote-times/` (documentação `.docx`, dados `.xlsx`, 1.387
DANFEs e templates de entrega). O pacote antigo (`02-enunciado/`,
`03-dados-alunos/`) foi descartado desta pasta por ser substituído.

---

## 1. O desafio

A **Atacadista Meridional** (fictícia) compra e vende produtos alimentícios,
médicos e de limpeza. A reforma tributária troca PIS/Cofins/ICMS por CBS/IBS e
cria o Imposto Seletivo entre 2026 e 2033. A equipe deve:

1. **Separar** notas de compra e de venda (vêm misturadas; o nome do arquivo não
   diz qual é qual).
2. **Classificar** cada item no `cClassTrib` (6 dígitos), com confiança e fonte.
3. **Simular** a carga de impostos hoje × 2027 × 2033, por item e por empresa.
4. **Explicar** num painel se a empresa ganha ou perde, com a origem de cada
   número.

A identificação da nota é a **chave de acesso** (44 dígitos); a do item é o
`nItem` (posição na tabela de produtos).

---

## 2. Dados oficiais

| Item | Volume |
|---|---:|
| DANFEs | 1.387 notas |
| Itens | 15.000 |
| Empresas no cadastro | 29 linhas (1 foco + fornecedores + clientes) |
| Produtos distintos | 95 pares `cProd × NCM` (128 descrições) |
| Catálogo usado | 52 NCMs distintos |
| Classes efetivamente usadas | 8 |
| Tabela cClassTrib | 173 linhas |
| Mapa NCM → cClassTrib | 4.193 linhas |
| CST IBS/CBS | 18 |

Camadas de dificuldade dos itens: NCM específico (~50%), NCM genérico (~20%),
depende da operação (~15%), descrição pobre (~10%) e armadilha (~5%).

---

## 3. Tributos e regras

### Hoje

- **ICMS**: como destacado na DANFE, item a item.
- **PIS/Cofins**: lucro real. `tributado` → 1,65% + 7,6% sobre
  `(vProd − vICMS)`; `aliquota_zero`/`monofasico` → zero; exportação (CFOP 7xxx)
  e bonificação (CFOP 5910) → zero.
- A soma por nota bate com os totais impressos; isso é usado como gate de
  extração.

### Regime novo

| Tributo | Hoje | 2027 | 2033 |
|---|---|---|---|
| ICMS | destacado | destacado | extinto |
| PIS/Cofins | regra acima | extinto | extinto |
| CBS | — | `vProd × 8,7% × (1 − redução)` | `vProd × 8,8% × (1 − redução)` |
| IBS | — | `vProd × 0,1% × (1 − redução)` | `vProd × 17,7% × (1 − redução)` |

`redução`: 000001 = 0%; 200034/200030 = 60%; 200003/200014/200005 = 100%;
410001/410004 = sem incidência (zero).

**Crédito nas compras:** ICMS/PIS/Cofins só para revenda (PIS/Cofins também exige
produto tributado); IBS/CBS de 2027 em diante é crédito amplo, inclusive uso e
consumo.

**Imposto Seletivo:** apenas sinalizado (`sim`/`nao`), sem cálculo.

---

## 4. Como classificar (ordem do enunciado)

1. Regras de operação antes do produto:
   - CFOP 5910 → `410001`
   - CFOP 7102 / destinatário exterior → `410004`
   - dispositivo médico do Anexo IV vendido a órgão público → `200005`
2. NCM no mapa: usar linhas `vigente = sim`, respeitando `condicao`, `excecao`,
   `item_do_anexo` e `permissao` (VEDADO exclui).
3. NCM fora do mapa → `000001` (regime padrão).
4. Descrição pobre (`DIVERSOS`, etc.) → CNAE do emitente.
5. Sem segurança → `REVISAR` com confiança abaixo de 0,70.
6. Imposto Seletivo → sinalizar os itens sujeitos.

---

## 5. Avaliação oficial (pacote novo)

| Critério | Peso |
|---|---:|
| Acurácia da classificação | **35%** |
| Simulação correta | **25%** |
| Calibração | **10%** |
| Painel e rastreabilidade | **20%** |
| Pitch | **10%** |

O automático é **70% = 35 + 25 + 10**. A antiga rubrica de **eficiência (tokens)
foi removida**; o esforço deve ir para acerto, calibração e rastreabilidade.

O uso de **LLM/agente é obrigatório**. A solução entra com um **juiz LLM
cirúrgico**, acionado apenas nas exceções (produtos com mais de uma classe
válida), sempre confinado aos candidatos do mapa e com validação/cache. Neste
dataset: 10 chamadas para 15.000 itens. Ver `USO-DO-LLM.md`.

---

## 6. Formato de entrega

Pasta com o nome da equipe contendo **exatamente** dois arquivos:

- `itens_classificados.csv` (separador `;`): `chave`, `nItem`, `cClassTrib`,
  `status`, `confianca`, `imposto_seletivo`, `fonte`.
- `simulacao.json`: `cenarios`, `itens` (nível 1) e `resumo` (nível 2). Nas
  vendas, `credito` é `null`.

O template oficial e o validador estão em
`pacote-times/templates-entrega/`. Entrega fora do formato não é avaliada.

---

## 7. O que mudou no pacote oficial novo

1. **Empacotamento:** documentos em `.docx`; dados em `.xlsx`; templates e
   validador; DANFEs em `dados/danfe/`.
2. **Pesos:** acurácia 35%, simulação 25%, calibração 10%, painel 20%, pitch 10%;
   eficiência removida.
3. **Ressalvas novas:**
   - exportação é imune a ICMS; algumas DANFEs destacam ICMS por erro de geração;
   - bonificação (CFOP 5910) tem PIS/Cofins zero, mesmo que o total impresso
     inclua esses itens.
4. **Dados:** 1.387 DANFEs idênticas; cadastro/PIS/CST/cClassTrib/exemplos
   equivalentes; mapa com **+19 linhas** (apenas reforçam as escolhas por
   família); `parametros.json` corrigiu o CNPJ foco para `...104`.
5. **Decisão adotada:** ICMS de exportação = **zero** (erro de emissão). Ver
   `BASELINE-ICMS-EXPORTACAO.md` e `DECISOES.md#11`.

---

## 8. O que é real e o que é sintético

| Real (oficial) | Sintético (case) |
|---|---|
| Leiaute da DANFE / NF-e | Empresas, CNPJs, valores e notas |
| Tabelas CST e cClassTrib | ICMS e PIS/Cofins de cada item |
| Listas de NCM da LC 214/2025 | Alíquotas de 2027/2033 (premissas) |
| Regra de PIS/Cofins e Tema 69 | Cronograma simplificado |

Nenhuma nota, CNPJ ou valor é real.

---

## 9. Leitura recomendada

- Regras completas: `pacote-times/enunciado_e_regras.md.docx`.
- Visão de entrega: `pacote-times/LEIA-ME.md.docx` e
  `pacote-times/templates-entrega/README.md.docx`.
- Aplicação na solução: `SOLUCAO.md` e `RESULTADOS.md`.
