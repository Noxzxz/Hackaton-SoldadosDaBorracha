# Manifesto da pasta final

Esta pasta foi montada para conter **apenas** o necessário para entender, rodar,
validar e apresentar a solução. Tudo que era duplicado, obsoleto, gerado em
execução ou restrito ficou de fora.

---

## 1. O que entrou

### Documentação oficial

`pacote-times/` — pacote oficial final, copiado de
`pacote-times-20261017T125844Z-1-001/pacote-times/`:

- `enunciado_e_regras.md.docx`
- `LEIA-ME.md.docx`
- `abertura-hackathon-espm-reforma-tributaria.pdf`
- `dados/` (6 tabelas `.xlsx`, `parametros.json`, 1.387 DANFEs)
- `templates-entrega/` (`itens_classificados.xlsx`, `simulacao.json`,
  `validar_entrega.py`, `README.md.docx`)

### Solução

`solucao/` — código e artefatos necessários:

- `src/`, `scripts/`, `app/`, `config/`, `tests/`
- `out/` (cache de extração, base do painel, trilha, tribunal, equilíbrio e
  baselines)
- `saida/` (os dois entregáveis oficiais)
- `requirements.txt`, `.gitignore`

### Contextualização (nova)

- `README.md` — visão geral e início rápido.
- `CONTEXTO.md` — desafio, dados, regras e avaliação oficial.
- `SOLUCAO.md` — arquitetura, módulos e decisões.
- `RESULTADOS.md` — números, baselines e validação.
- `COMO-RODAR.md` — setup, pipeline, painel, validação e entrega.
- `QUALIDADE-E-CORRECOES.md` — auditoria multi-agente e correções.
- `MANIFESTO.md` — este arquivo.

### Documentos de apoio preservados

- `BASELINE-ICMS-EXPORTACAO.md` — achado principal para o pitch.
- `IMPACTO-PACOTE-OFICIAL.md` — o que mudou no pacote novo e como adaptamos.
- `DECISOES.md` — registro técnico das decisões.

---

## 2. O que ficou de fora e por quê

| Item excluído | Motivo |
|---|---|
| `02-enunciado/` | enunciado antigo, substituído pelo `.docx` oficial |
| `03-dados-alunos/` | dados antigos em CSV, substituídos pelos `.xlsx` oficiais |
| `pacote-times/` (root) | cópia antiga do pacote (só CSV), substituída |
| `04-gabarito-organizacao/` | restrito à organização; não pode ser usado pelas equipes |
| `01-apresentacao/` | PPTX antigo; o pacote oficial traz a abertura em PDF |
| `PastasSoluc/` | propostas e planejamentos antigos, superados pela solução |
| `brainstorm-solucoes-divergentes.md` | rascunho de ideação |
| `caralhoo.md` | notas de planejamento antigas |
| `LEIA-ME.md` (root) | substituído pelo `README.md` e pelo LEIA-ME oficial |
| `rodar-a-noite.ps1` | automação antiga, não usada no fluxo final |
| `opencode.json`, `.opencode/` | configuração de ferramenta, não faz parte da entrega |
| `.opencode/` (52 MB) | tooling, sem relação com a solução |
| `solucao/logs/` | logs de execução, não reprodutíveis/necessários |
| `solucao/.pytest_cache/`, `.ruff_cache/`, `.hypothesis/`, `__pycache__/` | caches de ferramentas |
| `solucao/runner*.log` | logs de execução |
| `solucao/FIM.flag`, `PROGRESSO.md` | artefatos de processo |
| `solucao/AVALIACAO-MULTI-AGENTE.md`, `CORRECOES.md`, `PARECER-CORRECOES.md` | auditoria detalhada; resumida em `QUALIDADE-E-CORRECOES.md` |
| `solucao/RELATORIO-FINAL.md` | substituído por `RESULTADOS.md` e `SOLUCAO.md` |

Nenhum arquivo foi apagado da pasta original; esta é uma cópia limpa.

---

## 3. Critérios de limpeza

1. **Fonte única da verdade:** só o pacote oficial novo.
2. **Sem duplicatas:** uma cópia do pacote, uma da solução, uma de cada documento.
3. **Sem artefatos de execução:** logs, caches e flags ficaram fora.
4. **Sem material restrito:** o gabarito não foi copiado nem utilizado.
5. **Reprodutibilidade:** o que é necessário para rodar e validar foi mantido.

---

## 4. Verificação rápida

```powershell
cd solucao
python scripts/validar_entrega.py
python -m pytest -q
python ..\pacote-times\templates-entrega\validar_entrega.py .\saida
```

Esperado:

- `TUDO OK`
- `28 passed`
- `FORMATO OK`

---

## 5. Observação sobre tamanho

O pacote oficial inclui 1.387 DANFEs em PDF e a solução inclui os caches em
parquet. Isso mantém a pasta **auto-suficiente**: o painel abre sem reprocessar os
PDFs e o pipeline pode ser reexecutado com `--reparse` quando necessário.
