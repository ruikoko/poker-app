# Plano pt23 — Descompilar watcher + tag-based equity model

Sessão de desbloqueio dos 3 bugs A/B/C do `hrc_watcher.exe` (Baltazar) descobertos em pt22. Pré-requisito para fechar Fase 3 HRC (G5/G6 UI + smoke funcional).

## §1. Contexto pós-pt22

- Adapter G1 deployed (`cc93698` + fix `67761a0`).
- Pipeline mecânico ponta-a-ponta validado (pull → unzip → watcher → HRC wizard).
- **3 bugs funcionais** impedem o uso real do output:
  - **A** — equity model fixo (Malmuth-Harville sempre, sem FGS)
  - **B** — max players estático (seats da HH em vez de jogadores relevantes à decisão)
  - **C** — nome do JS hardcoded → tree >20GB → OOM crash do HRC
- Baltazar (autor do exe) emigrou, sem contacto. Sem fonte Python original.
- Decisão pt22: Opção 2 (descompilar + fix cirúrgico + recompilar).

## §2. Sequência proposta pt23

### Passo 1 — Rotação token defensiva (~5 min)

`HRC_WATCHER_API_KEY` (mask `Z10Soz9...37zSZ`) foi exposto numa screenshot Railway durante debug pt22. Rotação:

```
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Rui cola no Railway dashboard → service `poker-app` → variables → save + redeploy. Code valida via CLI que mask mudou. Rui `.bat` no Desktop actualizado, transferir para Beelink, duplo-clique.

### Passo 2 — Descompilar `hrc_watcher.exe` (~3-4h)

Material existente:

- `_local_only/hrc_watcher.exe` (30.5 MB PyInstaller 6.x, Python 3.12)
- `_local_only/extracted/hrc_watcher.exe_extracted/` (já com bytecode raw extraído via `pyinstxtractor`)
- `_local_only/tools/pyinstxtractor.py` (cópia local)
- `_local_only/ANALYSIS.md` (~80% do bytecode já mapeado por análise estática)

**Sub-passos:**

1. Validar `.pyc` files no extracted: `hrc_watcher_apr19_launcher.pyc` (16 KB launcher monkey-patcher) + `hrc_watcher_apr19.pyc` (46 KB main module).
2. Tentar descompilação com **`pycdc`** (suporta Python 3.12 nativo). Fallback: `uncompyle6` (tipicamente para ≤3.8), `decompyle3` (até 3.9).
3. Se nenhum descompilador moderno aguentar 3.12, fazer **disassembly verbose** com `dis` da stdlib + bytecode reading. ANALYSIS.md já cobre arquitectura — completar gaps.
4. Salvar source recuperado em `_local_only/decompiled/` (gitignored).

**Pontos exactos para identificar:**

- `set_equity_model(stage, ...)` — função que carrega Malmuth-Harville. Adicionar branch para `Multi-Table FGS` baseado em `equity_model` hint do `payouts.json`.
- `get_player_count_from_hh(hh_text)` — regex de seats. Substituir por parsing real da decisão: `last_raiser_position` → `hero_position` + `players_after_hero_still_active`.
- `setup_scripting()` — load do `mtt_advanced_..._bvb.js`. Nome literal hardcoded. Tornar configurável via env var `HRC_SCRIPT_PATH` ou via metadata da mão.

### Passo 3 — Fix cirúrgico + recompilação (~3h)

Para cada bug:

1. Alterar função no source recuperado.
2. Testar standalone (se possível) com `python hrc_watcher.py` em VM/sandbox.
3. Recompilar com `pyinstaller --onefile hrc_watcher.py` (matching original spec).
4. Smoke isolado no Beelink: 1 mão controlada, validar comportamento esperado.

**Atenção a manter:**

- Monkey-patcher launcher externo (`hrc_watcher_apr19_launcher.pyc`) força `MAX_CONCURRENT=1` e patcha `export_strategies` com BM_CLICK. **Não fundir** sem garantir paridade.
- Win32 ctypes calls (EnumWindows, SendMessage BM_CLICK) — preservar.
- Heurística de calc-done por mem stability (`tasklist` + 3 polls estáveis). Funciona; não tocar.

### Passo 4 — Smoke pós-recompilação (~30 min)

- Rui substitui `hrc_watcher.exe` no Beelink pelo recompilado.
- Adapter G1 puxa 1-2 mãos test reais (controlled — uma mid-game MTT, uma FT bubble se houver).
- Valida no HRC:
  - Bug A: equity model é FGS para a mid-game MTT.
  - Bug B: árvore tem só jogadores relevantes à decisão (visual no HRC).
  - Bug C: tree size razoável (<5 GB), sem OOM.
- POST `/api/queue/hrc/results` → BD `hrc_jobs.status='done'` + `result_zip` populado.

### Passo 5 — Tag-based equity model (cadeia completa)

Implementação da proposta `REGRAS_NEGOCIO.md §14`:

**a. Backend** (`backend/app/services/queue_export.py`):

- `build_queue_zip` aceita parâmetro `equity_model_by_hand: dict[str, str]` — mapa `hand_id → "malmuth_harville_icm" | "multi_table_fgs"`.
- Inclui hint no `payouts.json` de cada mão (key `equity_model`).

**b. Backend** (`backend/app/services/ingest_filters.py` — ficheiro novo se ainda não existe):

- Função `derive_equity_model(hand: dict) -> str` baseada em:
  - `discord_tags` contém `'icm-ft'` ou `'icm-pko-ft'` → `malmuth_harville_icm`
  - `hm3_tags` contém tags correspondentes → `malmuth_harville_icm`
  - Default → `multi_table_fgs`

**c. Discord** (canais novos):

- `#icm-ft` — Rui partilha mãos FT (equity model ICM strict).
- `#icm-pko-ft` — Rui partilha mãos FT PKO.
- Bot Discord recolhe → `discord_tags` populado.

**d. HM3** (`backend/app/routers/hm3.py:HM3_REAL_TAGS`):

- Adicionar tags `FT` (ou `ICM FT`) e `FT PKO` à lista canónica.
- Rui marca essas tags no HM3; importer transfere para `hm3_tags`.

**e. Watcher** (recompilado em Passo 3):

- Lê `equity_model` do `payouts.json` da mão.
- Branch em `set_equity_model()`:
  - `"malmuth_harville_icm"` → typeahead `M` (default actual)
  - `"multi_table_fgs"` → typeahead `M` + arrow down (selecciona FGS na lista)
- Fallback se hint ausente → `multi_table_fgs` (mais comum).

### Passo 6 — Fecho pt23 documental

JOURNAL, CLAUDE.md, TECH_DEBTS, MAPA (§2.15 actualizada com hints equity_model), REGRAS (§14 com referências reais aos commits), PLAN_PT24 se necessário.

## §3. Operacional paralelo Rui — Fase C backfill TSs

Em paralelo ao trabalho Code:

- Upload de TSs (`.txt`/`.zip`) históricos via `Tournaments.jsx`.
- ~112 torneios sem `tournament_summaries`. Objectivo: subir cobertura de ~13% para ~70%.
- PKO/Mystery: requer combinação TS + backoffice SS para popular `tournament_payouts`.

Independente do código — pode correr a qualquer momento.

## §4. Tech debts a tentar fechar em pt23

Se houver tempo após Passos 1-6:

- `#HRC-WATCHER-PATH-BETA-LEGACY` — paths configuráveis (entra naturalmente na recompilação).
- `#HRC-RESET-PRESERVATION` — clonar `Teste completo\` para `riand` (mitigação até paths configuráveis).
- `#HRC-ADAPTER-SCHEDULED-TASK` — Rui configura task no Beelink (~15 min, README tem instruções).
- `#SERVER-FILTER-HRC-STATUS` — adicionar `WHERE NOT EXISTS (... hrc_jobs.status='done')` em `routers/queue.py:export_queue` (~1h).

Os 3 tech debts pt21 FUTURE (`#HRC-JOBS-HISTORY-SUBSEQUENT`, `#HRC-RESULT-STORAGE-MIGRATION`, `#HRC-AUTH-MULTI-KEY`) ficam para quando houver evidência prática.

## §5. Riscos / incógnitas

| Risco | Mitigação |
|---|---|
| **`pycdc` falha em Python 3.12 bytecode** | Fallback para disassembly manual via `dis` + ANALYSIS.md como guia. |
| **Source recuperado tem partes ofuscadas / mypyc** | ANALYSIS §"81d243bd2c585b0f4821__mypyc.cp312-win_amd64.pyd" — extensão mypyc presente é third-party (provavelmente `pygetwindow` compilado). Funções do autor não vêm de mypyc — devem ser recuperáveis. |
| **Recompilação PyInstaller perde patch do launcher** | Manter launcher externo intacto OU integrar patch in-place no main; documentar escolha. |
| **DPI / coords drift entre recompilada e original** | Manter offsets `click_rel(dx, dy)` literais. Smoke confirma. |
| **Watcher após recompilação tem regression em fluxo mecânico** | Smoke isolado em Passo 4 antes de pôr em loop com adapter. |
| **Tag-based equity exige UI changes para Rui marcar `FT`** | Rui pode marcar manualmente em `Hands.jsx` (tags editáveis) — não bloqueia. |

---

**Pré-requisitos antes do arranque pt23:**

1. Rotação token (Passo 1) executada.
2. `pyinstxtractor` confirmado em PATH ou venv (já temos cópia em `_local_only/tools/`).
3. `pycdc` build local ou Docker image (testar antes de arrancar).
4. Sessão de poker do Rui fechada (regra de ouro CLAUDE.md).

Pt23 é a sessão **mais longa** projectada até agora (~10-15h split em 2 dias?). Web orquestra, Code descompila + edita + recompila.
