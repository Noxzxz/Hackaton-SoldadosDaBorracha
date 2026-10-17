# Hackathon ESPM — IA na Reforma Tributária (entrega final)

Solução completa para a **Atacadista Meridional**: classificação fiscal de 15.000
itens, simulação de hoje × 2027 × 2033, painel interativo, trilha de auditoria e
baseline do ICMS de exportação apurado a maior.

**Status:** pacote oficial novo aplicado, solução retificada, **juiz LLM ativo**
(DeepSeek V4.1 Flash via OpenCode Go), **42 testes verdes**, validador oficial
`FORMATO OK`.

---

## Estrutura da pasta

```
hackathon-espm-final/
├── README.md                         este arquivo
├── CONTEXTO.md                       desafio, dados, regras e avaliação
├── SOLUCAO.md                        arquitetura e o que foi construído
├── RESULTADOS.md                     números, baselines e validação
├── COMO-RODAR.md                     setup, pipeline, painel e entrega
├── MANIFESTO.md                      o que entrou/saiu e por quê
├── QUALIDADE-E-CORRECOES.md          auditoria multi-agente e correções
├── BASELINE-ICMS-EXPORTACAO.md       destaque de pitch (ICMS a maior)
├── IMPACTO-PACOTE-OFICIAL.md         mudanças do pacote oficial novo
├── DECISOES.md                       decisões técnicas registradas
├── USO-DO-LLM.md                     como o juiz LLM funciona (ponta a ponta)
├── PLANO-IMPLEMENTACAO-LLM.md        plano de implementação com LLM obrigatório
├── TRATAMENTO-E-DEDUPLICACAO.md      tratamento de dados e deduplicação (pitch)
├── RESOLUCAO-ENTREGAVEIS.md          leitura dos arquivos de saída
├── pacote-times/                     documentação e dados OFICIAIS
└── solucao/                          código, config, testes e entregáveis
```

O pacote `pacote-times/` é a **fonte oficial final** (enunciado em `.docx`,
dados em `.xlsx`, 1.387 DANFEs, templates e validador). O `solucao/` lê esse
pacote automaticamente.

---

## Início rápido

```powershell
cd solucao
python -m pip install -r requirements.txt
python scripts/rodar_tudo.py --testes   # pipeline (com juiz LLM) + testes
python scripts/validar_entrega.py       # checklist interno
streamlit run app/painel.py             # painel + simulador
```

O modelo do juiz LLM é o **ponto único de configuração** em
`solucao/config/llm.yaml` (modelo + endpoint + chave). Sem chave, o pipeline roda
em *dry-run* e mantém a decisão determinística. Para empacotar a entrega:

```powershell
python scripts/empacotar_entrega.py --nome SoldadosDaBorracha
```

Validação oficial do formato:

```powershell
python ..\pacote-times\templates-entrega\validar_entrega.py ..\SoldadosDaBorracha
```

Entrega: a pasta `solucao/saida/` contém exatamente os dois arquivos exigidos
(`itens_classificados.csv` e `simulacao.json`). Use
`scripts/empacotar_entrega.py` para criar a pasta com o nome da equipe e validar
no code freeze.

---

## Resultado em uma linha

Com o crédito amplo de IBS/CBS nas compras, a Meridional **acumula crédito**:

| Cenário | Imposto líquido |
|---|---:|
| hoje | −R$ 1.531.652,64 |
| 2027 | −R$ 23.689.823,53 |
| 2033 | −R$ 67.569.596,33 |

Além disso, **256 notas de exportação** tinham ICMS destacado indevidamente:
**R$ 43.827,17** apurados a mais em hoje/2027. Ver
`BASELINE-ICMS-EXPORTACAO.md`.

A classificação é determinística por padrão; o **juiz LLM** é acionado apenas nas
exceções (produtos com mais de uma classe válida). Neste dataset: **10 chamadas**
para 15.000 itens, **0 `REVISAR`**. Ver `USO-DO-LLM.md`.

---

## Documentos recomendados para a banca

1. `CONTEXTO.md` — leitura do desafio e das regras oficiais.
2. `SOLUCAO.md` — arquitetura e decisões.
3. `RESULTADOS.md` — números e validação.
4. `BASELINE-ICMS-EXPORTACAO.md` — achado principal do pitch.
5. `USO-DO-LLM.md` — como o LLM entra (só nas exceções) e o ponto de configuração.
6. `TRATAMENTO-E-DEDUPLICACAO.md` — tratamento de dados e deduplicação.
7. `QUALIDADE-E-CORRECOES.md` — robustez e testes.
