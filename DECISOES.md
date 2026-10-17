# Decisoes de implementacao

> **Caminhos:** relativos a `solucao/`.

Registro das decisoes nao obvias tomadas durante a construcao (agente autonomo).
Cada uma tem contexto, escolha e justificativa.

## 1. Fontes de dados e gabarito
- Li o **pacote publico** antigo (`03-dados-alunos/`) e, como contexto final
  oficial, o pacote `pacote-times-20261017T125844Z-1-001/pacote-times/`
  (documentos `.docx`, dados `.xlsx`, templates de entrega).
- **Nao abri nem usei `04-gabarito-organizacao/`.** A classificacao e derivavel das
  tabelas oficiais + regras do enunciado + `familias.yaml`. A unica informacao que
  vem da proposta vencedora (e que o proprio `PROPOSTA` especifica como politica
  configuravel) e a lista das 7 familias divergentes e suas classes alvo.
- Mantive as **duas politicas** implementadas: `mapa_estrito` (100% derivavel do
  pacote publico) e `alinhada_gabarito` (leitura tecnica dos Anexos I/VII, ativa por
  padrao). O painel mostra o custo em R$ de cada leitura.

## 2. Reconciliacao: modo "impresso" x modo "lei"
- O enunciado diz PIS/Cofins de exportacao = zero. Porem, nas **26 notas de
  exportacao (CFOP 7102) de produtos `tributado`**, o gerador sintetico imprimiu os
  totais de PIS/Cofins usando a regra do produto (ex.: `AMIDO`, vProd 339,39,
  PIS 4,59), apesar do texto "EXPORTACAO ... PIS E COFINS SEM INCIDENCIA".
- **Escolha:** `reconciliar()` usa o modo `impresso` (so a bonificacao zera) para
  fechar **1.387/1.387** notas contra os totais impressos; a **simulacao** usa o modo
  `lei` (exportacao = zero), que reproduz os exemplos/gabarito. As duas regras ficam
  explicitas em `parse_danfe.pis_cofins_item(..., modo=...)`.
- Justificativa: o gate de qualidade do parser e definido no DoD como "reconcilia
  contra os totais impressos da DANFE"; a regra de negocio do imposto e a do enunciado.

## 3. Perspectiva por chave (nao pelo JSON)
- `chave[6:20] == "51238476000104"` → venda. O pacote oficial novo corrigiu o
  `parametros.json` para `51238476000104` (o pacote antigo trazia `...187` por
  engano); mantivemos o CNPJ do cadastro/DANFEs (**51238476000104**), que agora
  coincide com o JSON oficial. Sempre derivei o CNPJ foco do cadastro.

## 4. Catalogo por (cProd, NCM) e familias NCM-first
- As 128 descricoes viram 95 pares (cProd, NCM) apos normalizacao (`- BONIFICACAO`
  removido). O catalogo e a unidade de decisao (10% do trabalho, 100% consistencia).
- `detectar_familia` e **NCM-first** com um unico desempate por descricao: o NCM
  `1905.90.90` (pao frances = cesta basica; bolo = regime padrao). Deteccao por
  palavra-chave foi evitada por falsos positivos (`MACA` em `MACARRAO`, `LARANJA`
  em `SUCO DE LARANJA`, `CENOURA` em `BOLO ... CENOURA`).

## 5. Guarda de prefixo e armadilhas
- So usado quando ha multiplos candidatos ou match por prefixo. Sem aderencia entre
  familia e anexo → `000001` (fonte `FALLBACK ... -> 000001`).
- Cobre 392690 (plasticos), 2009 (suco), 2202 (refrigerante), 4818 (papel higienico),
  340119 (sabao em po), 190531 (biscoito), 19059090 (bolo x pao), 38089411 (desinfetante).

## 6. Confianca derivada de metodo + medicao por mutacao
- Confianca base: tabela por origem (OP 0,98; NCM exato unico 0,95; exato com
  desempate 0,88; prefixo6 0,85; sem match 0,85; camada 4/CNAE 0,80; guarda 0,78;
  prefixo4 0,75; override de politica 0,72).
- **Confianca medida:** `src/mutacao.py` perturba a descricao (NCM fixo, pois o NCM e
  um campo duro da DANFE validado pela reconciliacao) e mede a fracao estavel; a
  confianca final e `min(metodo, 0,5 + 0,5·estabilidade)`.
- **Nao** rebaixamos produtos para `REVISAR` por instabilidade de descricao: pela
  matematica dos pesos (ganho `0,30·p` vs perda `0,10·(1−p)`), classificar compensa
  quando `p > 0,25`, e `REVISAR` nao conta como acerto. Isso mantem `REVISAR = 0`
  (dentro do alvo 0–1%) e evita perder acuracia. Ponto registrado para confirmacao
  com a organizacao (tambem listado no relatorio final).

## 7. Imposto Seletivo
- Sinalizado (`sim`) apenas, sem calculo: 497 itens (refrigerantes NCM 2202.10.00,
  incluindo as 2 bonificacoes `RFCLAR`). Regra: NCM inicia com `220210` **ou** familia
  `REFRIGERANTE`.

## 8. JSON sem float
- `simulacao.json` escreve Decimal com 2 casas como **numero** (nao string), via um
  sentinela interno (`__DEC__` → substituido por regex). Nenhum arredondamento por
  float no caminho do dinheiro; ha um teste de propriedade que verifica HALF_UP.

## 9. LLM: 0 tokens
- A cascata resolve os 128 produtos; `llm_juiz.py` existe (lote, cache em disco,
  validacao contra a tabela oficial) mas **nao e acionado**. Determinismo total
  (reexecucoes reproduzem a mesma saida).
- No pacote oficial novo a **eficiencia deixou de ser criterio** de avaliacao
  (acuracia 35%, simulacao 25%, calibracao 10%, painel 20%, pitch 10%).

## 10. Painel e simulador
- Streamlit local; a tabela `out/itens_simulados.parquet` usa float **apenas para
  exibicao** (entregaveis e calculos permanecem Decimal). O painel mostra a arvore
  de prova por item, o tribunal das 7 familias e o simulador "e se?" (aliquota,
  repasse, preco de equilibrio).

## 11. ICMS de exportacao (pacote oficial novo)
- O enunciado novo diz que o ICMS nao incide em exportacao e que algumas DANFEs
  destacam ICMS por erro de geracao; o template oficial, porem, mostra 43,43 no
  item de exportacao.
- **Decisao:** tratar o ICMS destacado como erro de emissao e considerar **zero**
  em CFOP 7xxx (`tratamento_exportacao.icms_zero: true`). O template passa a
  divergir intencionalmente; o flag permite reproduzi-lo.
- Impacto: R$ 43.827,17 a menos nos debitos de hoje e 2027; 2033 nao muda.
