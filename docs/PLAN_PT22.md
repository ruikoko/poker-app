# Plano pt22 — Adapter Beelink G1 + UI G5/G6 + smoke real

Sessão de fecho end-to-end da Fase 3 HRC. Pré-requisito: backend Fase B (G3+G4+G2) deployed em pt21 ✓. Falta apenas adapter no Beelink + UI no browser do Rui + smoke real ponta-a-ponta com zip real do `hrc_watcher.exe`.

## §1. Contexto pós-pt21

**Backend Fase B em main:**

```
5b9c10a  G3 — tabela hrc_jobs schema
764b53e  G4 — auth dual-path cookie + Bearer
2fa1f60  G2 — POST /api/queue/hrc/results
```

Suite 154 → 172 PASSED. Smokes G4+G2 validados em prod. `HRC_WATCHER_API_KEY` em Railway (service `poker-app`).

**Beelink em pt22 entry state:**

- Reset PC nuclear ✓ (conta local `riand`).
- Python 3.12 instalado ✓.
- HRC reinstalado ✓.
- `hrc_watcher.exe` (30.5 MB PyInstaller) copiado do PC principal ✓.
- `C:\hrc\queue\` e `C:\hrc\done\` **por criar**.
- `hrc_watcher.exe --help` **por correr** (output desconhecido até pt22).

**Pendente backend:** G1 (adapter no Beelink), G5 (UI botão exportar), G6 (UI badge HRC), smoke real end-to-end.

## §2. Sequência proposta pt22

### Passo 1 — Validação setup Beelink (Rui manual, ~15 min)

Antes de qualquer escrita de código:

```powershell
python --version              # esperado: Python 3.12.x
New-Item -ItemType Directory C:\hrc\queue
New-Item -ItemType Directory C:\hrc\done
.\hrc_watcher.exe --help      # capturar output COMPLETO e colar ao Web
```

O `--help` do watcher é crucial — define a interface real (argumentos esperados, paths, variáveis, etc.). Web valida antes do Code arrancar G1.

**Critério para avançar:** `python --version` mostra 3.12.x, ambas as pastas criadas, output do `--help` capturado.

### Passo 2 — G1 adapter Python no Beelink (Code, ~3-4h)

**Função:** cose API REST (poker-app) ↔ filesystem (`hrc_watcher.exe` no Beelink).

**Loop principal:**

```python
# Pseudocódigo — implementação final depende do --help do watcher
import time, zipfile, requests, pathlib, os, io

API_BASE = "https://poker-app-production-34a7.up.railway.app"
KEY = os.environ["HRC_WATCHER_API_KEY"]  # em env do Beelink
QUEUE_DIR = pathlib.Path(r"C:\hrc\queue")
DONE_DIR = pathlib.Path(r"C:\hrc\done")
POLL_INTERVAL_S = 60  # configurável

def pull_queue():
    r = requests.get(
        f"{API_BASE}/api/queue/hrc",
        headers={"Authorization": f"Bearer {KEY}"},
        params={"include_no_payout": "false"},
        timeout=120,
    )
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        for name in zf.namelist():
            if name == "manifest.json":
                continue
            target = QUEUE_DIR / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(name) as src, open(target, "wb") as dst:
                dst.write(src.read())

def push_results():
    for done_zip in DONE_DIR.glob("*.zip"):
        hand_id = done_zip.stem  # ex: "GG-281416137"
        with open(done_zip, "rb") as fp:
            r = requests.post(
                f"{API_BASE}/api/queue/hrc/results",
                params={"hand_id": hand_id, "status": "done"},
                files={"file": ("result.zip", fp, "application/zip")},
                headers={"Authorization": f"Bearer {KEY}"},
                timeout=120,
            )
        if r.status_code == 200:
            done_zip.unlink()  # cleanup
            # opcional: move para C:\hrc\archive\
        else:
            log_error(hand_id, r.status_code, r.text)

while True:
    pull_queue()
    push_results()
    time.sleep(POLL_INTERVAL_S)
```

**Decisões D pendentes para abrir no início do Passo 2:**

- D1: linguagem? **Python 3.12** (mesma da app, sem dependências exóticas).
- D2: localização do script no Beelink? Default: `C:\hrc\adapter\hrc_adapter.py`.
- D3: arrancar como service Windows / scheduled task / interactive console? Recomendação: **scheduled task** com restart-on-fail.
- D4: logging? `C:\hrc\adapter\logs\YYYY-MM-DD.log` rotacionado por dia.
- D5: poll interval default? **60s** (config via env var `HRC_POLL_INTERVAL_S`).
- D6: handling de falhas `.failed` marker do watcher? Detectar + POST com `status=failed&error=...`.
- D7: dedup — guardar quais `hand_id` já processados para não re-puxar? Sim, em `C:\hrc\adapter\state.json`.

### Passo 3 — Smoke real end-to-end (~30 min)

- Rui activa o adapter no Beelink (interactive).
- Rui activa o `hrc_watcher.exe`.
- Adapter puxa 1 mão real (a mais antiga elegível).
- Watcher processa (~minutos no HRC Beta).
- Adapter detecta o zip em `C:\hrc\done\<hand_id>.zip`.
- Adapter faz POST → `hrc_jobs` row criada com `status='done'`, `result_zip` populado.
- Code valida BD: `SELECT hand_db_id, status, result_zip_size, meta_json FROM hrc_jobs ORDER BY submitted_at DESC LIMIT 1`.

**Critério de sucesso:** row em `hrc_jobs` com `status='done'`, `result_zip_size > 0`, `meta_json->>'rank'` not null.

### Passo 4 — G5 UI botão exportar queue (~2h)

**Onde:** `frontend/src/pages/Tournaments.jsx` (já tem botões de upload TS e backoffice; secção HRC fica natural ao lado) **ou** `frontend/src/pages/Dashboard.jsx` (mais visível).

**Decisões D pendentes para abrir no início do Passo 4:**

- D1: localização (Tournaments vs Dashboard)?
- D2: mostrar contagem antes do click? (X mãos elegíveis, Y com payouts, Z em missing). Recomendação: **sim**, GET preview `?dry_run=1` se aceitarmos adicionar param.
- D3: download directo (browser save dialog) ou modal de confirmação? Recomendação: directo.

### Passo 5 — G6 UI badge HRC no `HandRow` (~1h)

**Onde:** componente `HandRow` em `frontend/src/components/` (ou similar).

**Comportamento:**

- Sem row em `hrc_jobs` → sem badge (estado neutro).
- `submitted` → ⏳ pequena.
- `done` → ✓ verde.
- `failed` → ❌ vermelho (hover mostra `error`).
- `expired` → reservado.

**Endpoint necessário:** já existe `query` directa via row em `hrc_jobs`. Pode ser exposto como `GET /api/hrc-jobs/by-hand/:hand_id` ou anexado ao `GET /api/hands/...` existente. **Decisão D7 pt22**: anexar a `/api/hands` (sem endpoint novo).

### Passo 6 — Fecho pt22 documental

JOURNAL, MAPA, CLAUDE.md, TECH_DEBTS, REGRAS_NEGOCIO §13 update, eventual PLAN_PT23.

## §3. Operacional paralelo Rui — Fase C backfill TSs históricos

Em paralelo ao trabalho Code, Rui pode:

- Upload de TSs (`.txt`/`.zip`) históricos via `Tournaments.jsx`.
- Para 112 torneios sem `tournament_summaries`. Objectivo: subir cobertura de 13% para ~60-80%.
- PKO/Mystery: requer combinação TS + backoffice SS para popular `tournament_payouts`. Mystery KO ainda em `#BACKOFFICE-MYSTERY`.

Esta fase é **independente do código** — pode correr em paralelo a qualquer passo.

## §4. Tech debts a tentar fechar em pt22

Se houver tempo após Passos 1-6:

- `#SYNC-RECENT-RESPECT-MANUAL` — guard contra overwrite manual/backoffice no lobby pipeline. ~1h.
- `#PYDANTIC-V1-VALIDATOR-DEPRECATION` — migrar `@validator` V1 → `@field_validator` V2 em `routers/lobbys.py:34`. ~15 min.

Os 3 tech debts FUTURE de pt21 (`#HRC-JOBS-HISTORY-SUBSEQUENT`, `#HRC-RESULT-STORAGE-MIGRATION`, `#HRC-AUTH-MULTI-KEY`) ficam para quando houver evidência prática (2º watcher, volume alto, etc.).

## §5. Riscos / incógnitas

| Risco | Mitigação |
|---|---|
| **Interface `hrc_watcher.exe --help` desconhecida** — pode exigir argumentos não previstos, env vars específicas, ou comportamento diferente do que `ANALYSIS.md` derivou por bytecode. | Passo 1 captura output real. Web revê antes de Code escrever G1. Pode forçar D1-D7 do Passo 2 a mudar. |
| **Watcher hardcoded ao path `C:\Users\Administrator\Documents\Teste completo\` (vimos em ANALYSIS).** | Substituído pela conta `riand` no Beelink novo. Watcher pode falhar com `FileNotFoundError`. Plano B: criar symlink `C:\Users\Administrator → C:\Users\riand` ou recompilar watcher (não vamos). |
| **Script HRC Pro custom (`mtt_advanced_*.js`) hardcoded.** | Rui tem o script no PC principal — copiar manualmente para o Beelink no path esperado pelo watcher. Confirmar no Passo 1. |
| **DPI / layout HRC drift entre PC origem e Beelink** — clicks rel hardcoded podem falhar. | Smoke real (Passo 3) detecta. Se falhar, ajustar resolução do Beelink para bater na do PC origem (manual Rui). |
| **`hrc_watcher.exe` é o ficheiro produzido por Baltazar com username `Administrator` hardcoded** (ANALYSIS §"Working dir hardcoded"). | Se quebrar, plano C: descompilar e recompilar com paths novos. Fora de scope pt22; ficaria em tech debt. |
| **Smoke real pode demorar > 15 min** (HRC Beta solve pode ser longo, +export +adapter detect). | Aceitar; é a primeira vez. Pt22 tem buffer para isto. |
| **Cobertura `tournament_payouts` ainda 13%** — smoke pode escolher mão sem payouts. | Filtrar smoke para 1 das 42 mãos com payouts. Confirmar via SQL antes do Rui clicar. |

---

**Pré-requisitos antes do arranque pt22:**

1. Rui correr Passo 1 (validação setup Beelink) e colar output de `--help`.
2. Confirmação de espaço livre no Beelink ≥ 100 GB.
3. Sessão de poker do Rui fechada (regra de ouro CLAUDE.md).
4. Web valida o output de `--help` e abre/ajusta decisões D1-D7 do Passo 2.

Sem isto, pt22 fica pendente em UI (G5+G6 podem arrancar sem o Beelink, mas o smoke real é o ponto-chave).
