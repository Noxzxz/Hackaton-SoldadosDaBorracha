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

## 9. LLM obrigatorio: juiz cirurgico das excecoes
- Requisito do hackathon: **usar LLM/agente**. O LLM passa a ser uma etapa real do
  pipeline, mas **cirurgica**: decide apenas os produtos que a cascata nao fecha
  (mais de uma classe valida, ou condicao nao mapeada).
- `classificar.py`: `ambiguo = len(classes) > 1 or aval.ambiguidade_condicao`.
- **1 chamada por produto** (nunca por item): 10 produtos neste dataset → 10
  chamadas (depois, cache). Fila em `src/llm_juiz.py::resolver_fila`.
- Resposta **confinada** aos candidatos validados, `REVISAR` como saida segura,
  confianca `<= 0,90`, cache por SHA-256, fallback deterministico se indisponivel.
- Modelo/endpoint sao o **ponto unico de configuracao** (`config/llm.yaml`); sem
  modelo/chave o pipeline roda em dry-run. Ver `USO-DO-LLM.md`.
- Apesar de o pacote oficial novo ter removido a eficiencia (tokens) da rubrica, o
  LLM segue util para acuracia/rastreabilidade e atende ao requisito do evento.

## 10. Painel e simulador
- Streamlit local; a tabela `out/itens_simulados.parquet` usa float **apenas para
  exibicao** (entregaveis e calculos permanecem Decimal). O painel mostra a arvore
  de prova por item, o tribunal das 7 familias, o simulador "e se?" e a aba
  **Auditoria LLM**. A narrativa foi ajustada para nao afirmar "ganho/lucro".

## 11. ICMS de exportacao (pacote oficial novo)
- O enunciado novo diz que o ICMS nao incide em exportacao e que algumas DANFEs
  destacam ICMS por erro de geracao; o template oficial, porem, mostra 43,43 no
  item de exportacao.
- **Decisao:** tratar o ICMS destacado como erro de emissao e considerar **zero**
  em CFOP 7xxx (`tratamento_exportacao.icms_zero: true`). O template passa a
  divergir intencionalmente; o flag permite reproduzi-lo.
- Impacto: R$ 43.827,17 a menos nos debitos de hoje e 2027; 2033 nao muda.

## 12. Avaliacao do mapa antes morta, agora ativa
- Antes, `condicoes.yaml`, `excecoes.yaml` e `regras_operacao.yaml` existiam mas
  **nao eram lidos** pela cascata (a classificacao usava so `permissao`).
- Agora `avaliar_mapa` aplica `vigente`, `permissao == PERMITIDO`, `condicao`
  (predicados de `condicoes.yaml`) e `excecao`/precedencia (`excecoes.yaml`).
- Condicao **nao mapeada** nao e presumida: marca `ambiguidade_condicao` e vai ao
  juiz. Efeito no dataset: classes de insumos agropecuarios (200038/515001)
  eliminadas por regra; ambiguos caem de ~47 para 10.

## 13. CNAE contextual (camada 4)
- Antes o CNAE so aparecia na justificativa, sem afetar a decisao.
- Agora a descricao pobre verifica **aderencia ao CNAE esperado** da familia
  (`familias.yaml`): aderente → `000001` (conf 0,80); divergente → `REVISAR`
  (conf 0,55); nao verificavel → `000001` (conf 0,75).

## 14. Decomposicao da simulacao e transicao (bonus)
- O ICMS de exportacao entra como zero na simulacao (decisao #11).
- `src/transicao.py` calcula 2029–2032 (fracoes de ICMS de `parametros.yaml` +
  interpolacao linear de CBS/IBS) em artefato **separado**; nao altera os 3
  cenarios obrigatorios do `simulacao.json`.
