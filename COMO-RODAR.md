# Como rodar

Requisitos: **Python 3.10+** e as dependências de `solucao/requirements.txt`.

---

## 1. Instalação

```powershell
cd solucao
python -m pip install -r requirements.txt
```

---

## 2. Pipeline completo

```powershell
# usa o cache de extração em out/ (rápido)
python scripts/rodar_tudo.py

# reextrai as 1.387 DANFEs do pacote oficial e roda os testes
python scripts/rodar_tudo.py --reparse --testes

# só os testes
python -m pytest -q
```

Saídas:

- `solucao/saida/itens_classificados.csv`
- `solucao/saida/simulacao.json`
- `solucao/out/*.parquet`, `tribunal.json`, `baseline_exportacao*`

O pipeline é idempotente. Sem `--reparse`, ele reutiliza `out/itens.parquet` e
`out/notas.parquet`.

---

## 3. Painel

```powershell
cd solucao
streamlit run app/painel.py
```

Telas: veredito, onde ganha/perde, drill-down, tribunal, qualidade e simulador
"e se?". O painel lê `solucao/out/` e o cadastro do pacote oficial.

---

## 4. Validação

```powershell
cd solucao
python scripts/validar_entrega.py

# validador oficial do hackathon
python ..\pacote-times\templates-entrega\validar_entrega.py .\saida
```

Resultados esperados: `TUDO OK` e `FORMATO OK`.

---

## 5. Baseline do ICMS de exportação

```powershell
cd solucao
python scripts/baseline_exportacao.py
```

Gera:

- `out/baseline_exportacao.csv` — resumo por cenário.
- `out/baseline_exportacao_itens.csv` — os 447 itens de exportação (256 com ICMS
  afetado).
- `out/baseline_exportacao.json` — resumo + top itens.

Documento para a banca: `BASELINE-ICMS-EXPORTACAO.md`.

---

## 6. Alternar a leitura do ICMS de exportação

```yaml
# solucao/config/parametros.yaml
tratamento_exportacao:
  icms_zero: true    # true  = zero em CFOP 7xxx (decisão adotada)
                     # false = reproduz o ICMS destacado do template
```

Depois de alterar, rode novamente:

```powershell
python scripts/rodar_tudo.py
python scripts/baseline_exportacao.py
```

Impacto da troca: **R$ 43.827,17** em hoje/2027; 2033 não muda.

---

## 7. Recomeçar do zero

```powershell
cd solucao
Remove-Item -Recurse -Force out
python scripts/rodar_tudo.py --reparse --testes
```

O `out/` será recriado a partir das 1.387 DANFEs do pacote oficial.

---

## 8. Preparar a entrega

O LEIA-ME oficial pede **uma pasta com o nome da equipe contendo exatamente dois
arquivos**:

```powershell
$equipe = "NOME-DA-EQUIPE"
New-Item -ItemType Directory -Path "..\$equipe" -Force | Out-Null
Copy-Item .\saida\itens_classificados.csv "..\$equipe\"
Copy-Item .\saida\simulacao.json        "..\$equipe\"
python ..\pacote-times\templates-entrega\validar_entrega.py "..\$equipe"
```

O painel pode ser entregue como link, PDF ou app, separadamente.

---

## 9. Estrutura de dados

O `solucao/src/caminhos.py` procura, nesta ordem:

1. `pacote-times-*/pacote-times/dados` (pacote novo, quando existir);
2. `pacote-times/dados` (formato desta pasta);
3. `pacote-times/03-dados-alunos` (formato antigo);
4. `03-dados-alunos` (legado).

Nesta pasta, o pacote oficial está em `pacote-times/dados` e é lido
automaticamente. O `io_dados` aceita `.xlsx` (oficial) e `.csv` (legado).
