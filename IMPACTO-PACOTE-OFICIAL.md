# Impacto do Pacote Oficial Novo

> **Caminhos de código/config:** relativos a `solucao/`. O pacote oficial nesta
> pasta está em `pacote-times/`.

**Data:** 2026-10-17
**Contexto final:** `pacote-times/` (cópia oficial do pacote
`pacote-times-20261017T125844Z-1-001`)
**Comparado com:** pacote antigo usado até então (`02-enunciado/`, `03-dados-alunos/`)

---

## 1. Veredito

**A solução continua válida e não precisa ser refeita.** O pacote novo muda o
empacotamento (DOCX/XLSX/templates), os pesos da avaliação e adiciona duas
ressalvas; os dados são semanticamente os mesmos. A **classificação** dos 15.000
itens não mudou. A **simulação** muda apenas nos 256 itens de exportação com ICMS
destacado (dos 447 exportados; os outros 191 já eram zero), por decisão de tratar
o ICMS como erro de emissão.

Evidências após `rodar_tudo.py --reparse` lendo o pacote oficial:

| Métrica | Antes | Depois do pacote novo |
|---|---:|---:|
| Notas reconciliadas | 1.387/1.387 | **1.387/1.387** |
| Itens | 15.000 | **15.000** |
| Distribuição 200003/000001/200014/200034/200030/410004/200005/410001 | 4.817/3.889/2.501/1.637/1.228/447/443/38 | **idêntica** |
| REVISAR | 0 | **0** |
| Confiança mínima / média | 0,72 / 0,86 | **0,72 / 0,878** |
| Imposto Seletivo | 497 | **497** |
| Líquido hoje / 2027 / 2033 | −1.487.825,47 / −23.645.996,36 / −67.569.596,33 | **−1.531.652,64 / −23.689.823,53 / −67.569.596,33** (ICMS de exportação = zero) |
| Testes | 26 verdes | **42 verdes** |
| Validador oficial | — | **FORMATO OK** |

Além disso, **3 dos 4 itens do template oficial** batem exatamente com a nossa
saída; o item de exportação diverge **intencionalmente** (ICMS tratado como erro
de emissão), conforme seção 3.

---

## 2. O que mudou no pacote oficial

### 2.1 Empacotamento

| Item | Pacote antigo | Pacote oficial novo |
|---|---|---|
| Enunciado / LEIA-ME | `.md` | `.md.docx` |
| Dados | `03-dados-alunos/*.csv` | `dados/*.xlsx` + `dados/parametros.json` |
| DANFEs | `03-dados-alunos/danfe/` | `dados/danfe/` (mesmos 1.387 arquivos) |
| Templates | não havia | `templates-entrega/` (`itens_classificados.xlsx`, `simulacao.json`, `validar_entrega.py`, `README.md.docx`) |
| Apresentação | `.pptx` | `abertura-...pdf` |

**Inconsistência do pacote:** o enunciado e o LEIA-ME citam `dados/*.csv`, mas os
arquivos entregues são `.xlsx`. O validador e os templates usam os mesmos nomes
lógicos. Nossa leitura aceita **CSV ou XLSX**, então funciona nos dois formatos.

### 2.2 Pesos da avaliação (mudança relevante de estratégia)

| Critério | Antes | Agora |
|---|---:|---:|
| Acurácia da classificação | 30% | **35%** |
| Simulação correta | 20% | **25%** |
| Eficiência (tokens) | 10% | **removido** |
| Calibração | 10% | **10%** |
| Painel e rastreabilidade | 20% | **20%** |
| Pitch | 10% | **10%** |

- O automático agora é **70% = 35 + 25 + 10** ("as três primeiras linhas").
- **Eficiência não é mais critério.** Gastar poucos tokens de LLM deixa de pontuar
  diretamente; o esforço deve ir para acurácia, simulação e calibração. O evento,
  porém, **exige** LLM — usamos um juiz cirúrgico só nas exceções (~10 produtos).
- A mensagem do pitch deve priorizar **acerto por camada, calibração e
  rastreabilidade**, não economia de tokens.

### 2.3 Ressalvas novas no enunciado (seção 3)

1. **Exportação:** o ICMS não incide (imunidade). Algumas DANFEs destacam ICMS por
   erro de geração; o texto manda considerar zero, "como diz o campo de
   informações complementares". O avaliador aceita as duas leituras.
2. **Bonificação (CFOP 5910):** PIS/Cofins é zero. Em algumas notas o total
   impresso inclui esses itens; **prevalece a regra**.

Nossa solução já zera PIS/Cofins em 5910 e em exportação (`modo="lei"`), e o gate
de reconciliação usa `modo="impresso"` apenas para fechar contra os totais do
gerador sintético. Nada a corrigir nesse ponto.

**Decisão (2026-10-17):** o ICMS destacado nessas DANFEs de exportação é **erro de
emissão** e deve ser considerado **zero** em CFOP 7xxx. O template oficial mostra
43,43 e passa a divergir **intencionalmente**; o flag
`tratamento_exportacao.icms_zero` permite reproduzir o template se necessário.

Quantificação: **256 notas** de exportação com ICMS destacado, **R$ 43.827,17** a
maior em hoje e 2027 (4,88% do vProd das exportações). Baseline completa em
`BASELINE-ICMS-EXPORTACAO.md`; reproducao em `scripts/baseline_exportacao.py`.

### 2.4 Dados: o que realmente mudou

| Tabela | Linhas antigas | Linhas novas | Situação |
|---|---:|---:|---|
| `cadastro_empresas` | 29 | 29 | idêntica |
| `pis_cofins_hoje` | 95 | 95 | idêntica (após `zfill(8)` no NCM) |
| `tabela_cst_ibscbs` | 18 | 18 | idêntica (após `zfill(3)` no CST) |
| `tabela_cclasstrib` | 173 | 173 | idêntica (após `zfill(6)`) |
| `exemplos_por_classe` | 15 | 15 | idêntica (após `zfill(6)`) |
| `mapa_ncm_cclasstrib` | 4.174 | **4.193** | **+19 linhas** |
| DANFEs | 1.387 | 1.387 | conjunto idêntico |

As diferenças visíveis em CSV×XLSX são perda de zeros à esquerda e datas com
`00:00:00` — corrigidas na leitura, não são mudanças de conteúdo.

**As 19 linhas novas do mapa** afetam somente NCMs que já estão no nosso catálogo:

| NCM | Classes adicionadas |
|---|---|
| 04012000 (creme de leite) | 200003 |
| 04061000 (queijo minas) | 200003 |
| 04069000 (queijos 0406.90) | 200003 |
| 07031000 (cebola) | 200014, 200034 (VEDADO), 200038, 515001 |
| 07134000 (lentilha) | 200034, 200038, 515001 |
| 15121100 (óleo de soja) | 200034, 200038, 515001 |
| 40151100 (luvas) | 200005, 200030 |
| 90183100 (seringas) | 200005, 200030 |
| 90183900 (agulhas/cateter) | 200005, 200030 |

Elas **reforçam** as escolhas que já fazíamos por família/override (por exemplo,
200014 para hortifruti, 200003 para cesta básica, 200005/200030 para dispositivos
médicos). Resultado: distribuição de classes inalterada. A confiança média subiu
de 0,86 para 0,878 porque alguns NCMs passaram a ter desempate explícito e o
juiz LLM ajustou a confiança das ambiguidades.

### 2.5 `parametros.json`

O pacote novo **corrigiu o CNPJ da empresa foco** de `51238476000187` para
`51238476000104`. É exatamente o valor que já usávamos (cadastro + chave das
DANFEs). Nenhuma ação necessária; apenas removemos a nota de "JSON incorreto".

---

## 3. Template oficial × nossa solução

Os 4 itens do `templates-entrega/simulacao.json` foram comparados com a nossa
saída. **3 batem exatamente**; o de exportação diverge por decisão (ICMS zero).

| Item | Classe | Hoje | 2027 | 2033 |
|---|---|---|---|---|
| Arroz (compra revenda) | 200003 | 168,13 / créd. 168,13 | 168,13 / créd. 168,13 | 0 / 0 |
| DIVERSOS (uso e consumo) | 000001 | 77.699,09 / créd. 0 | 81.388,92 / créd. 26.724,72 | 80.477,85 / créd. 80.477,85 |
| Exportação | 410004 | **0** (template: 43,43) | **0** (template: 43,43) | 0 |
| Dispositivo médico a órgão público | 200005 | 0 | 0 | 0 |

O validador oficial rodou contra `solucao/saida/` e retornou **FORMATO OK**.

Observação: no `itens_classificados.xlsx` do template, o `cClassTrib` do item
"DIVERSOS" aparece como `1` (célula numérica). O CSV oficial exige 6 dígitos; o
nosso CSV grava `000001`, que é o formato aceito pelo validador.

---

## 4. Adaptações aplicadas ao código

| Arquivo | Adaptação |
|---|---|
| `src/caminhos.py` | Resolve automaticamente `pacote-times-*/pacote-times/dados`; fallback para `pacote-times/03-dados-alunos` e `03-dados-alunos` antigo. |
| `src/io_dados.py` | `_ler` aceita `.csv` **ou** `.xlsx`; normaliza NCM (8), cClassTrib (6), CST (3) e exemplos. |
| `app/painel.py` | Cadastro carregado por `io_dados.cadastro()` (sem caminho fixo para `03-dados-alunos`). |
| `tests/test_parse.py` | Usa `caminhos.DANFE_DIR` (pacote oficial). |
| `src/simular.py` | Adiciona `variacao_vs_hoje_pct` ao resumo, igual ao template oficial. |
| `config/parametros.yaml`, `src/premissas.py`, `src/simular.py` | Flag `tratamento_exportacao.icms_zero` (default `true` = zero; `false` = template). |
| `config/parametros.yaml`, `src/caminhos.py`, `DECISOES.md` | Nota do CNPJ atualizada para o valor oficial `...104`. |
| `tests/test_simulacao.py` | Golden de exportação para zero, fallback do template e teste do simulador de repasse. |
| `src/classificar.py` | `avaliar_mapa` passa a aplicar vigência/condição/exceção das tabelas oficiais. |
| `src/llm_cliente.py`, `src/busca.py`, `src/llm_juiz.py`, `config/llm.yaml` | Juiz LLM das ambiguidades (ponto único de configuração; ver `USO-DO-LLM.md`). |
| `src/transicao.py`, `scripts/empacotar_entrega.py` | Bônus 2029–2032 e empacotamento automático da entrega. |

### Como alternar a leitura de exportação

```yaml
# config/parametros.yaml
tratamento_exportacao:
  icms_zero: true    # true  = ICMS zero em CFOP 7xxx (decisão adotada)
                     # false = reproduz o template (ICMS 43,43)
```

Impacto de **desligar** o flag (voltar ao ICMS destacado: 256 itens afetados, dos
447 exportados):

| Cenário | Líquido com ICMS zero (atual) | Líquido com ICMS destacado |
|---|---:|---:|
| hoje | **−1.531.652,64** | −1.487.825,47 |
| 2027 | **−23.689.823,53** | −23.645.996,36 |
| 2033 | −67.569.596,33 | −67.569.596,33 (sem ICMS) |

A diferença é R$ 43.827,17 de ICMS destacado nas exportações.

---

## 5. O que ainda precisa de decisão humana

1. **Exportação (ICMS): resolvido** em 2026-10-17 — adotamos zero (erro de
   emissão). O template diverge intencionalmente; use o flag apenas se a
   organização exigir o valor do template.
2. **`REVISAR`:** o limite de 0,70 agora está configurado; nenhum item cai
   abaixo disso hoje. Confirmar com a organização se querem itens forçados a
   `REVISAR` mesmo com classificação correta (penaliza acurácia).
3. **Entrega:** o LEIA-ME novo pede **uma pasta com o nome da equipe contendo
   exatamente os dois arquivos**. Use `python scripts/empacotar_entrega.py
   --nome SoldadosDaBorracha`: ele cria a pasta e roda o validador oficial.
4. **Pitch:** mesmo com a eficiência fora da rubrica, o evento **exige LLM**. O
   juiz LLM (DeepSeek V4.1 Flash via OpenCode Go) entra só nas exceções (~10
   chamadas); o pitch deve reforçar acurácia por camada, calibração,
   rastreabilidade e o uso cirúrgico do modelo.

---

## 6. Comandos de verificação

```powershell
cd solucao
python scripts/rodar_tudo.py --reparse      # le o pacote oficial (XLSX) + juiz LLM
python scripts/validar_entrega.py           # checklist interno
python -m pytest -q                         # 42 testes
python scripts/empacotar_entrega.py --nome SoldadosDaBorracha   # FORMATO OK
```

---

*Relatório gerado em 2026-10-17 com base no pacote oficial `pacote-times-20261017T125844Z-1-001`.*
