# Roteiro de mudanças para a solução do hackathon

> **Status (2026-10-17): este roteiro foi implementado.** Vários itens de P0/P1
> já estavam resolvidos antes da execução (1.1, 1.2, 2.4, slider de repasse) e os
> demais foram implementados com **LLM obrigatório**. O plano detalhado e o
> resultado estão em `PLANO-IMPLEMENTACAO-LLM.md`, e o funcionamento do juiz LLM
> em `USO-DO-LLM.md`. Os documentos `SOLUCAO.md`, `RESULTADOS.md`,
> `COMO-RODAR.md`, `DECISOES.md`, `QUALIDADE-E-CORRECOES.md`, `MANIFESTO.md`,
> `IMPACTO-PACOTE-OFICIAL.md`, `CONTEXTO.md` e `README.md` já refletem a versão
> atual.

## Objetivo

Levar a solução atual de uma entrega tecnicamente funcional para uma entrega **alinhada ao pipeline esperado, defensável na classificação, correta nos cenários exigidos e clara para a banca** — sem aumentar o escopo além do que contribui para a avaliação.

O roteiro separa o que é essencial do que é bônus. A prioridade é proteger os **70% avaliados automaticamente** (acurácia, simulação e calibração) e os **30% avaliados pela banca** (painel/rastreabilidade e pitch).

> **Premissa de segurança:** usar apenas os dados sintéticos e as fontes permitidas pelo evento. Não usar gabarito restrito nem declarar acurácia ou ganho financeiro que não tenha sido medido.

## Resumo executivo das prioridades

| Prioridade | Mudança | Motivo |
|---|---|---|
| **P0 — antes de entregar** | Corrigir teste executável de `src.simular`, corrigir números da baseline, validar pasta final | Remove defeitos e afirmações contraditórias fáceis de detectar. |
| **P1 — maior impacto na nota** | Aplicar condições/exceções do mapa e tornar os casos ambíguos auditáveis | A classificação vale 35% e hoje o fluxo não usa essas colunas de forma geral. |
| **P1 — maior impacto na nota** | Definir confiança/revisão com critério defensável; criar caminho humano para `REVISAR` | A calibração vale 10%; erro confiante é penalizado. |
| **P1 — banca** | Corrigir painel e narrativa de “ganho”; corrigir repasse sem efeito | Evita conclusões econômicas indevidas e controles que não funcionam. |
| **P2 — alinhar ao pipeline** | Implementar busca top-5 e juiz LLM para ambiguidades, ou documentar e demonstrar alternativa determinística | Aproxima a solução do slide 8 sem chamar LLM sem necessidade. |
| **P2 — bônus** | Implementar transição 2029–2032, completar cobertura do preço de equilíbrio e agente explicador | Pode melhorar a demonstração, mas não deve atrasar os requisitos mínimos. |

---

## Fase 0 — Congelar uma referência reproduzível

Antes de mudar código, guardar uma cópia imutável da entrega atual e registrar:

- hash/versão do ZIP e das tabelas oficiais usadas;
- configuração ativa (inclusive `tratamento_exportacao.icms_zero` e política de divergências);
- saída atual dos validadores, testes, distribuição de classes e resumo por cenário;
- quais arquivos são fonte e quais são artefatos gerados.

Criar uma branch ou cópia de trabalho para as mudanças. Não sobrescrever a saída que passou nos validadores até que a nova versão passe também.

**Critério de aceite:** outra pessoa consegue repetir os comandos a partir do ZIP e identificar qual conjunto de dados e configuração produziu os resultados.

## Fase 1 — Corrigir problemas de baixo custo e alta visibilidade (P0)

### 1.1 Corrigir o comando executável do simulador

**Problema:** `python -m src.simular` falha porque a asserção de exportação espera ICMS diferente de zero, enquanto a política ativa considera zero.

**Mudança:** alinhar o exemplo executável à configuração default e manter a reprodução do template como um caso separado, com o flag de exportação desligado. Evitar que o exemplo tenha premissas ocultas diferentes da configuração ativa.

**Critério de aceite:** ambos funcionam sem erro:

```bash
python -m src.simular
python -m pytest -q
```

Adicionar teste que execute o modo atual e o modo alternativo do template.

### 1.2 Corrigir contagem e rótulos da baseline

- Distinguir **447 exportações** de **256 itens/notas com ICMS destacado positivo**.
- Corrigir `RESULTADOS.md`, o texto do script `baseline_exportacao.py` e qualquer slide/pitch que diga que 447 itens divergem.
- Informar que os 191 itens restantes já têm ICMS destacado zero.
- Não chamar a diferença simulada de imposto efetivamente pago, restituição ou valor que volta ao caixa.

**Critério de aceite:** contagens calculadas a partir do CSV de itens, não digitadas manualmente; texto de relatório e saída de terminal concordam.

### 1.3 Criar a pasta de submissão

O LEIA-ME pede uma pasta com o nome da equipe contendo exatamente os dois arquivos obrigatórios. Manter o código e os relatórios em outro pacote de apoio, se desejado.

```text
NOME-DA-EQUIPE/
  itens_classificados.csv
  simulacao.json
```

Rodar o validador oficial apontando para essa pasta final, não apenas para `solucao/saida`.

**Critério de aceite:** pasta contém exatamente dois arquivos e o validador oficial retorna `FORMATO OK`.

---

## Fase 2 — Tornar a classificação realmente orientada pelo mapa (P1)

### 2.1 Reestruturar a chave de classificação

Separar a **decisão de produto** da **decisão de operação**:

1. normalizar descrição;
2. agrupar itens que compartilham produto e evidência;
3. buscar candidatos válidos no mapa;
4. avaliar NCM, condição, exceção, descrição, cliente e finalidade quando aplicável;
5. resolver a classe do produto;
6. aplicar regra de operação no nível do item;
7. registrar confiança, status e evidências.

Para catálogo, considerar uma chave baseada em algo como:

```text
(NCM, descrição normalizada, contexto relevante do produto)
```

Não depender exclusivamente de `(cProd, NCM)`: códigos diferentes podem descrever o mesmo produto e o mesmo código pode aparecer com contexto diferente. Manter os 95 produtos atuais como caso de regressão.

### 2.2 Aplicar condições, exceções e permissões

Implementar uma função única e testável que recebe a linha/candidatos do mapa e avalia:

- permissão `PERMITIDO` versus `VEDADO`;
- vigência na data/ano escolhido;
- condição do anexo;
- exceção e item do anexo;
- contexto de destino/uso, quando indicado;
- precedência entre classes quando mais de uma se aplica.

Os arquivos `condicoes.yaml` e `excecoes.yaml` não devem ficar como documentação morta. Se uma condição não puder ser decidida com os dados disponíveis, marcar como ambígua e enviar para julgamento ou `REVISAR`; não presumir silenciosamente que se aplica ou não se aplica.

**Critério de aceite:** testes individuais para cada condição/exceção presente nos itens do case; toda classe final é permitida e vigente e a evidência identifica a regra que eliminou as alternativas.

### 2.3 Resolver os casos ambíguos com evidência

Há 51 produtos com mais de uma classe permitida entre os candidatos mapeados na inspeção. Para cada um, produzir uma tabela de auditoria:

| Campo | Exemplo de conteúdo |
|---|---|
| Produto | código, NCM, descrição normalizada |
| Candidatos | classes permitidas e respectivos textos do mapa |
| Condição/exceção | regra aplicada e evidência usada |
| Decisão | classe escolhida e motivo |
| Fonte | chave estável da linha, NCM, classe, condição, exceção e anexo |
| Confiança/status | método que fundamenta a nota; `REVISAR` quando não resolvido |

Não elevar a confiança por ter muitos itens repetidos: a mesma decisão de catálogo replicada 500 vezes não equivale a 500 validações independentes.

### 2.4 Corrigir referências de fonte

Em `numero_linha()`, correspondências por prefixo não podem depender de busca por NCM exato. Preservar a linha original do arquivo oficial ou usar uma referência estável composta por campos oficiais, por exemplo:

```text
NCM + cClassTrib + permissão + condição + exceção + item/anexo
```

**Critério de aceite:** nenhuma referência `LNone`; qualquer fonte exibida pode ser localizada no pacote de entrada sem depender da ordem de um DataFrame deduplicado.

---

## Fase 3 — Escolher uma das três abordagens de busca/LLM

A banca descreve o pipeline esperado como regras → busca (BM25 + embeddings, top-5) → LLM juiz nos casos restantes → fallback/revisão. Há mais de uma maneira de implementar isso. Escolher conscientemente, não adicionar IA apenas por aparência.

### Opção A — Determinística e explicável (menor risco, recomendada como base)

- Filtrar primeiro candidatos com NCM, vigência, permissão, condição e exceção.
- Usar regras declarativas para operações e precedência de anexos.
- Usar busca lexical BM25 apenas quando a descrição precisar diferenciar produtos/candidatos.
- Não chamar LLM quando uma regra legal resolve de forma inequívoca.
- Enviar ambiguidades sem evidência suficiente para `REVISAR`.

**Vantagens:** barata, reproduzível, rápida, simples de auditar. **Limitação:** pode ficar aquém da expectativa literal do slide sobre embeddings/LLM e precisa explicar como resolve os casos difíceis.

### Opção B — Híbrida fiel ao slide (mais alinhada à arquitetura esperada)

- Restringir candidatos pelo mapa e contexto.
- Recuperar top-5 exemplos por BM25 e embeddings.
- Chamar um LLM juiz **em lote por descrição distinta**, não por linha da nota, apenas quando regras e busca não fecharem a classe.
- Permitir ao modelo selecionar somente um ID entre os candidatos fornecidos ou devolver `REVISAR`.
- Exigir JSON estruturado com classe, confiança, justificativa e IDs/fontes utilizados.
- Validar classe na tabela oficial vigente; rejeitar respostas sem fonte ou fora dos candidatos.
- Cachear por versão dos dados, prompt, contexto e candidatos; registrar modelo, data, hash e uso.

**Vantagens:** corresponde ao slide e trata casos semânticos. **Riscos:** custo/latência, comportamento não determinístico e falsa segurança. O LLM não deve inventar fundamento legal nem substituir regras explícitas.

### Opção C — Híbrida sem LLM no conjunto atual (compromisso de prazo)

Se, após aplicar condições/exceções e busca, todos os produtos estiverem realmente resolvidos por regras, manter zero chamadas LLM. Ainda assim:

- executar e registrar a busca de candidatos;
- demonstrar por que não restaram casos para o juiz;
- manter o juiz ligado para produtos novos/ambíguos;
- não alegar que o pipeline executou uma etapa que não foi chamada.

**Recomendação:** implementar a Opção A primeiro e, dentro do prazo, adicionar a Opção B somente para a fila de ambiguidades. Isso constrói segurança e alinhamento com o slide sem tornar o LLM a fonte primária da classificação.

---

## Fase 4 — Fallback CNAE, revisão e calibração (P1)

### Fallback CNAE

Hoje a descrição pobre termina em `000001`, e o CNAE é incluído na justificativa, mas não altera a decisão. Escolher uma destas políticas:

- **Fallback contextual:** usar CNAE para restringir a família plausível e, em seguida, comparar com NCM/mapa; documentar por que a classe padrão é adequada.
- **Fallback conservador:** se CNAE + descrição não identificarem o produto, devolver `REVISAR` com confiança abaixo de 0,70.
- **Regra fixa específica do case:** se os fornecedores de plásticos e os itens efetivamente forem todos regime padrão, escrever uma regra específica, citar cadastro/NCM/mapa e demonstrar que CNAE foi verificado — sem sugerir generalização automática.

### Revisão humana

Criar uma aba/lista no painel com:

- produtos e itens com `REVISAR`;
- candidatos e motivo da dúvida;
- campos da DANFE e cadastro usados;
- fonte do mapa;
- campo de decisão humana e justificativa auditável.

Se não houver nenhum item para revisar, exibir a métrica e explicar por que cada caso ambíguo foi resolvido. Não forçar `REVISAR = 0` apenas para melhorar a aparência.

### Confiança

Separar as métricas:

- **estabilidade:** classe preservada sob mutações artificiais da descrição;
- **confiança estimada:** regra interna que deve ser validada;
- **calibração avaliada:** proporção real de acertos, calculável somente com referência autorizada.

**Critério de aceite:** todos os itens com baixa evidência são revisáveis; os níveis de confiança são avaliados por faixa quando houver rótulos autorizados; nenhuma alegação de calibração usa apenas estabilidade de mutação.

---

## Fase 5 — Fechar a aderência tributária e a transição (P1/P2)

### 5.1 Preservar os três cenários obrigatórios

Manter no arquivo oficial os cenários exigidos pelo validador:

```json
["hoje", "2027", "2033"]
```

Não adicionar 2029–2032 ao `simulacao.json` se isso quebrar o esquema do avaliador. A simulação atual deve preservar:

- hoje: ICMS + PIS/Cofins sobre `vProd − ICMS`, com regras de zero;
- 2027: ICMS + CBS/IBS calculados separadamente, com reduções;
- 2033: somente CBS/IBS após as reduções;
- créditos conforme finalidade e cenário.

Adicionar testes com valores-limite, cada redução, tratamento monofásico/alíquota zero, venda, compra para revenda, compra para uso/consumo, bonificação e exportação.

### 5.2 Resolver a política de exportação de forma transparente

Manter cenários comparativos:

- **Política principal:** ICMS zero em CFOP 7xxx, seguindo a ressalva do enunciado detalhado sobre dados sintéticos.
- **Sensibilidade/template:** ICMS conforme DANFE, para explicar a diferença com o template e o quadro resumido do slide.

No painel e no pitch, rotular como **diferença simulada entre políticas**, não como pagamento, recuperação ou ganho real. O slide 12 declara que todos os dados são sintéticos.

### 5.3 Implementar transição 2029–2032 somente como bônus

As frações estão em `config/parametros.yaml`, mas não são consumidas. Para o bônus:

- calcular cada ano com a fração de ICMS configurada (90%, 80%, 70%, 60%);
- explicitar as premissas de CBS/IBS aplicáveis em cada ano e a fonte delas;
- gerar resultados em aba/arquivo separado para não alterar o esquema dos três cenários obrigatórios;
- substituir a interpolação linear do painel por estes cálculos, ou manter a interpolação apenas identificada como ilustração não tributária.

**Critério de aceite:** testes para as quatro frações, coerência com 2027 e 2033 e rótulos de premissa no painel.

---

## Fase 6 — Painel, preço de equilíbrio e narrativa (P1/P2)

### Corrigir o simulador do painel

O slider de repasse cria `vProd_repasse`, mas essa coluna não é usada nos números exibidos. Escolher uma opção:

1. ligar repasse a preço, margem e imposto recalculado e mostrar os novos resultados; ou
2. remover o slider até o recálculo estar implementado.

A alteração da alíquota deve recalcular os valores de forma verificável, incluindo efeitos coerentes em vendas e créditos. Não aplicar um fator genérico a componentes que não variam com essa taxa sem explicar o modelo.

### Tornar a rastreabilidade navegável

No drill-down, permitir selecionar compras e vendas, não só vendas. Mostrar a decomposição por item:

```text
vProd → ICMS/PIS/Cofins ou CBS/IBS → redução da classe → imposto do item → crédito → débito/crédito agregado
```

Cada valor deve apontar a campo de DANFE, cadastro, linha/chave do mapa ou parâmetro. Informar também política de exportação, arredondamento e cenário.

### Preço de equilíbrio

O cálculo está presente, mas há 89 linhas para 95 produtos vendidos; seis produtos não têm compra correspondente e não recebem preço de equilíbrio. Para tornar o bônus completo:

- manter os 89 cálculos com custo/credito observado;
- listar os seis excluídos e motivo;
- não inventar custo para cobrir a lacuna;
- se houver uma proxy aprovada, rotulá-la como premissa e mostrar sensibilidade;
- permitir download da tabela completa, não apenas top 15.

### Ajustar a narrativa

Substituir “a empresa ganha R$ 66 milhões” por linguagem como:

> “No dataset sintético e sob estas premissas, o líquido simulado fica R$ X mais negativo em 2033, refletindo créditos de IBS/CBS maiores que os débitos simulados. Isso não equivale a lucro, caixa disponível ou recuperação financeira.”

A banca pergunta “ganha ou perde”; responder com resultado do modelo e imediatamente distinguir resultado tributário simulado de rentabilidade/caixa.

---

## Fase 7 — Testes de aceitação e code freeze

### Testes automatizados

1. `normalizar_xprod`: acentos, espaços, sufixo de bonificação, abreviações previstas.
2. deduplicação: 15.000 linhas não geram decisões por item; agrupamento preserva contexto distinto.
3. mapa: exato/prefixo, permitido/vedado, vigente, condição, exceção e precedência.
4. operações: 5910, 7102/exterior e dispositivo médico + órgão público.
5. fallback CNAE e encaminhamento para revisão.
6. LLM: só recebe candidatos permitidos; resposta fora da lista é rejeitada; falha de API cai para revisão, não para classe inventada.
7. simulação: testes golden do slide 9 e do enunciado, compras/vendas, créditos e arredondamento.
8. exportação: política principal e política alternativa.
9. rastreabilidade: toda fonte usada é resolvível.
10. painel: slider muda saída, preço de equilíbrio documentado, anos intermediários correspondem às frações quando implementados.

### Comandos finais

```bash
python -m pytest -q
python scripts/rodar_tudo.py --reparse --testes
python scripts/validar_entrega.py
python ../pacote-times/templates-entrega/validar_entrega.py ../NOME-DA-EQUIPE
```

Também executar o painel no ambiente da apresentação e percorrer um caso de compra, um de venda, um ambíguo, uma exportação e um item `REVISAR` (se houver).

**Critério de code freeze:** testes e validadores passam; resultados regenerados; nenhuma mensagem contraditória; painel acessível; pitch ensaiado em até cinco minutos.

---

## Sequência recomendada por prazo

### Se houver poucas horas

1. Corrigir a asserção de exportação.
2. Corrigir 447 versus 256 e a linguagem de ganho/recuperação.
3. Criar a pasta final com os dois arquivos e validar.
4. Corrigir o slider ou removê-lo; preparar painel local confiável.
5. Fazer revisão manual/documentada dos 51 grupos com múltiplas classes candidatas.
6. Preparar um pitch que explique a ressalva das exportações e a natureza sintética dos dados.

### Se houver um dia ou mais

1. Implementar condições/exceções e fonte estável no classificador.
2. Criar busca top-5; conectar juiz LLM apenas aos casos que permanecerem ambíguos.
3. Criar fila de `REVISAR` e corrigir confiança.
4. Acrescentar testes por condição, exceção e contexto.
5. Completar os bônus: transição anual, tabela integral de equilíbrio e explicador com fontes.

## Checklist final para a equipe

- [ ] Toda classificação é resultado de regra/fonte identificável, inclusive quando há várias classes no mapa.
- [ ] Condição, exceção, permissão e vigência são efetivamente avaliadas.
- [ ] Busca e LLM estão implementados como etapa real ou a alternativa sem LLM está explicitamente demonstrada.
- [ ] O CNAE é usado para decidir algo, ou a regra fixa está justificada sem alegar inferência por CNAE.
- [ ] Confiança é descrita honestamente; ambiguidades podem ir para revisão humana.
- [ ] Fórmulas, créditos, cenários e política de exportação estão testados e explicados.
- [ ] Não há alegação de dinheiro real/recuperação em dados sintéticos.
- [ ] A projeção anual não é confundida com a interpolação ilustrativa.
- [ ] Painel abre, links/arquivos funcionam e cada valor tem origem rastreável.
- [ ] Pasta da equipe contém exatamente CSV e JSON; validadores oficiais passam.
- [ ] Pitch de cinco minutos está ensaiado e cobre decisão, impacto modelado, evidências e limitações.
