# Crivo conectado ao pipeline

O Crivo (painel de decisão) lê as saídas do pipeline do time. Ele não reclassifica nada: classe, confiança, fonte e regra de cada item vêm de `solucao/out/classificados.parquet`.

## Como rodar

```bash
cd solucao
python scripts/rodar_tudo.py                 # gera out/ e saida/
python crivo/gerar_painel.py --pipeline      # gera crivo/plataforma/dados/crivo_painel.js
# abrir crivo/plataforma/index.html no navegador
```

Pasta esperada: `solucao/crivo/` (este conteúdo) ao lado de `solucao/out` e `solucao/saida`, com o pacote oficial em `pacote-times/dados`.

## O que vem de onde

| No Crivo | Fonte no pipeline |
| --- | --- |
| Classe, confiança, fonte, regra | `out/classificados.parquet` (regra vira peneira 1 a 5) |
| Itens e notas | `out/itens.parquet`, `out/notas.parquet` |
| Fila de decisões | 7 famílias de `out/tribunal.json` (uma decisão por família) e itens em REVISAR |
| Conferência de paridade | compara o cálculo do Crivo com `saida/simulacao.json`, item a item |
| Transição 2029–2032 | `out/transicao_2029_2032.parquet` |
| Cadastro, mapa, PIS/Cofins hoje | `pacote-times/dados/*.xlsx` |

## Premissas alinhadas ao pipeline

- ICMS de exportação (CFOP 7xxx) é zero no cálculo (`tratamento_exportacao.icms_zero`); a DANFE original continua visível na evidência do item.
- PIS/Cofins é zero em exportação e na bonificação (CFOP 5910).
- Decisões do fiscal são locais ao navegador e recalculam o painel; para valer na entrega, devem voltar ao pipeline como override.

## Conferir

Na tela **Motor e conferências**, a linha "Simulação do Crivo × saida/simulacao.json" deve dizer que todos os itens são idênticos. Se houver divergência, ela mostra os maiores desvios.
