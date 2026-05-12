# Plano pt21 — Fase 3 HRC + Beelink prep

Plano de execução para arrancar Fase 3 do pipeline HRC: watcher local 24/7
no Beelink GTR5 a conduzir o HRC Beta. Cobre 6 gaps técnicos identificados
em investigação read-only pós-pt20 + tarefas operacionais (limpeza Beelink,
backfill TSs históricos).

## 1. Contexto pós-pt20

Sessão pt20 fechou com 3 commits em main:

```
5465b32  Commit E    — sync-recent de lobbys + lobby_processing_log
af7e3c8  Backoffice  — /api/tournament-results/import (vanilla + PKO)
1665d1b  Docs        — fecho documental pt20
```

**Cobertura `tournament_payouts` em prod (12-Mai snapshot):**

- 7 rows totais (4 `discord_lobby_vision:` + 2 `backoffice_vision:` +
  1 source legacy/manual da FASE 1).
- Mãos elegíveis pelos filtros default de `/api/queue/hrc` (`tags=icm-pko,
  PKO SS, sqz-pko, ICM`, `study_state=new`, últimos 30 dias): **324**.
- Com `tournament_payouts` (entram no zip): **42** (13%).
- Sem `tournament_payouts` (`manifest.missing_payouts`): **282** (87%).
- Torneios distintos sem payouts: **112**, dos quais **0 têm TS
  importado** (`has_ts=False`).

A baixa cobertura é consequência operacional, não bug do pipeline.

## 2. Investigação HRC end-to-end (read-only pós-pt20)

Pipeline existente (resumo):

| Peça | Estado | Notas |
|---|---|---|
| Tabela `tournament_payouts` | ✅ | PK `(site, tn)`, blob HRC opaco |
| `POST /api/payouts` (upload manual blob) | ✅ | |
| Pipeline lobby Vision → payouts (Discord `#lobbys`) | ✅ | pt19+pt20 |
| Pipeline backoffice GG (vanilla+PKO) | ✅ | pt20 (`af7e3c8`) |
| Endpoint `GET /api/queue/hrc` (zip export) | ✅ | FASE 1 commit `d16f291` |
| `services/queue_export.py:build_queue_zip` | ✅ | manifest + estrutura |
| Conversor HH GG → PS-compat | ✅ | `_format_level_line`, `_replace_hashes` |
| **UI para descarregar zip** | ❌ ausente | só curl/browser directo |
| **Feedback endpoint (results back)** | ❌ ausente | watcher não devolve nada |
| **Tabela de jobs / state per hand** | ❌ ausente | filtro runtime, sem persistência |
| **Auth long-lived para watcher** | ❌ ausente | só cookie HttpOnly 7 dias |
| **Marcação `study_state` automática** | ❌ ausente | Rui marca manualmente |

Detalhe técnico das peças existentes em `docs/MAPA_ACOPLAMENTO.md` (§2.12
`tournament_summaries`, §2.13 `lobby_processing_log`) e nos próprios
módulos. O `_local_only/ANALYSIS.md` cobre análise estática do
`hrc_watcher.exe` do Baltazar (referência arquitectónica do watcher).

## 3. 6 gaps identificados

Ordenado por dependência (G3 → G4 → G2 → G5+G6 → G1 no Beelink):

| ID | Descrição | Esforço |
|---|---|---|
| **G1** | Adapter zip→pastas no Beelink — script Python que puxa `/api/queue/hrc` via HTTP, unzipa, coloca cada `<hand_id>/` em `QUEUE_DIR` que o watcher do Baltazar consome. Lado watcher, não toca a app. | ~30 min |
| **G2** | `POST /api/queue/hrc/results` — multipart com (zip HRC Complete Export + meta.json + hand_id). UPSERT em `hrc_jobs`. Validação básica (zip ≠ vazio, hand_id existe). | ~3h |
| **G3** | Tabela `hrc_jobs` — `(hand_db_id BIGINT FK, submitted_at, completed_at, result_zip_url, status, meta_json, error_text)`. Idempotente. Index em `(status, submitted_at)`. | ~1h |
| **G4** | API key / bearer token para watcher long-lived. Header `Authorization: Bearer <token>` aceite em paralelo ao cookie. Token gerado uma vez, gravado em env var do Beelink. Revogação simples. | ~1-2h |
| **G5** | UI button "Exportar queue HRC" em `Tournaments.jsx` ou `Dashboard.jsx`. Mostra contagem "X mãos elegíveis · Y com payouts · Z em missing". Click descarrega zip. | ~2h |
| **G6** | UI badge no `HandRow` com estado HRC (✓ resolvido / ⏳ em queue / ❌ falhou / ` ` n/a). Lê de `hrc_jobs`. | ~1h |

**Total estimado:** ~10h ≈ 1 sessão pt21 substancial.

## 4. Estado Beelink (= máquina futura do watcher)

Snapshot operacional do Rui:

- ✅ Ligado, login OK, desktop visível.
- ⚠️ Disco quase cheio: **35 GB livres de 463 GB** (~8% livre).
- ⚠️ McAfee instalado — lentidão extrema reportada.
- ⚠️ 3 anos de bloat: apps poker antigas, jogos, dev tools (Unity Hub, etc).

**Decisão pendente do Rui** antes do arranque pt21:

| Opção | Tempo | Risco |
|---|---|---|
| **(a) Reset PC com Win11 fresh** | ~2h reinstalação + reconfig | Limpo, mas perde apps Rui ainda quer |
| **(b) Limpeza in-place** | ~3-4h manual | Mais lento; risco de deixar bloat residual |

Recomendação operacional (Web): (a) **se** Rui confirmar que não tem
dados únicos no Beelink (a maioria das apps reinstala-se). (b) caso
contrário, mas exige inventário prévio cuidadoso.

## 5. Plano de execução pt21 (ordenado)

### Fase A — Beelink prep (Rui, manualmente, 1-2h)

1. Desinstalar McAfee (Painel de Controlo → Apps).
2. Inventário rápido das pastas-chave:
   - Hand Histories (`%LOCALAPPDATA%\PokerCraft\` ou similar GG).
   - Configs HM3 (`%APPDATA%\HoldemManager3\` se aplicável).
   - Licenças instaladas (HRC, GTOWizard, etc).
3. Backup do essencial para disco externo / cloud.
4. (Se opção (a)) reset Win11 e reinstalar Python 3.12 + HRC Beta.
5. Espaço alvo: ≥ 100 GB livres.

### Fase B — Backend Fase 3 core (Code + Web, 4-6h)

Ordem dependência:

1. **G3** — tabela `hrc_jobs` + `ensure_hrc_jobs_schema()` no lifespan.
2. **G4** — auth API key (helper `require_auth_or_api_key`, env var
   `HRC_WATCHER_API_KEY` revogável). Endpoint adminável para gerar
   tokens fica para pt22+ se necessário.
3. **G2** — `POST /api/queue/hrc/results` com auth API key,
   multipart upload + UPSERT em `hrc_jobs`.

Tests: ~10-12 novos. Suite 154 → ~165.

### Fase C — Backfill operacional (paralelo Rui + Web, 2-3h)

- Upload de TSs `.txt`/`.zip` históricos via `Tournaments.jsx`
  → popular os 112 tns sem `tournament_summaries`.
- (Onde aplicável) upload de backoffice SSs para popular
  `tournament_payouts`.
- Validar que cobertura sobe de 13% para % útil.

Independente do código — pode correr durante a Fase B.

### Fase D — UI + smoke (Code + Web, 3-4h)

1. **G5** — botão "Exportar queue HRC" + painel de contagem.
2. **G6** — badge no `HandRow` com estado HRC.
3. **G1** (lado Beelink) — script adapter Python:
   ```python
   while True:
       zip_bytes = http.get('/api/queue/hrc', headers={'Authorization': ...})
       unzip_to(QUEUE_DIR)
       sleep(60)
   ```
   E loop que reporta resultados via `POST /api/queue/hrc/results` quando
   o watcher do Baltazar mover para `DONE_DIR`.
4. Smoke end-to-end:
   - 1 mão elegível com payouts → exporta zip.
   - Beelink puxa, watcher resolve, devolve resultado.
   - UI badge muda para ✓.

## 6. Backfill operacional necessário

**112 torneios distintos** elegíveis sem `tournament_summaries`. Para
cobertura subir:

- Tipo de TSs a fazer upload: todos pós-`2026-01-01` que o Rui jogou.
- Caso PKO/Mystery: requer combinação TS + backoffice SS (para
  distribuição literal de prizes por posição).
- Mystery KO: parcialmente bloqueado por `#BACKOFFICE-MYSTERY`
  (backoffice fail-fast); usar lobby SS ou INSERT manual entretanto.

Estimativa de cobertura pós-backfill (se Rui fizer upload disciplinado
da semana): 60-80% das 282 mãos atualmente sem payouts.

## 7. Riscos identificados

| Risco | Mitigação |
|---|---|
| Beelink lento até McAfee sair + disco respirar | Fase A é pré-requisito; sem isto, watcher pode não conseguir correr HRC Beta em paralelo |
| Auth API key — segurança | Token gravado só em env var Railway (`HRC_WATCHER_API_KEY`) e Beelink env. Revogação = rotação da var. Scope limitado a 1 endpoint (`POST /results`) inicialmente |
| Idempotência feedback endpoint | UPSERT por `hand_db_id` em `hrc_jobs`. Re-uploads sobrescrevem campos result; `submitted_at` preservado |
| Edge cases HRC Structure Manager | Mystery KO já conhecido (#BACKOFFICE-MYSTERY); outros formatos (Microstakes, Spin&Go) ainda não explorados. Manter watcher tolerante a falhas (timeout export, malformed zip) |
| Watcher trava no Beelink | Reset manual via RDP. Sem auto-restart inicialmente; tech debt se ficar instável |
| Cookie auth + API key coexistência | `require_auth_or_api_key` aceita ambos. Cookie continua a funcionar para Rui na UI; API key para Beelink |

## 8. Decisões pendentes para o Web/Rui antes do arranque pt21

| # | Pergunta |
|---|---|
| D1 | Beelink: reset Win11 fresh ou limpeza in-place? |
| D2 | Auth: header `Authorization: Bearer` ou query param `?api_key=`? (Recomendação: header — não fica em logs) |
| D3 | `hrc_jobs.result_zip_url` — guardar URL externo (S3/Railway storage) ou bytes em coluna BYTEA? (Recomendação: URL, BYTEA cresce indefinidamente) |
| D4 | UI badge — apenas HRC, ou agrupar com outros badges existentes (origin, study_state)? |
| D5 | Tornar `study_state` automático quando HRC resolve, ou manter Rui a marcar "Revista" manualmente? (Recomendação: manter manual — HRC resolve ≠ Rui estudou) |

## 9. Carry-over de tech debts pt20

- **#BACKOFFICE-MYSTERY** — bloqueia Mystery via backoffice; usar lobby
  ou manual entretanto.
- **#SYNC-RECENT-RESPECT-MANUAL** — guard contra overwrite manual no
  lobby pipeline. Ataque oportuno durante Fase B.
- **#TS-RATIO-MYSTERY-CONFIRM** — clarificar com Rui regra GG Mystery
  (0.33 vs 25/75).
- **#TS-AUTO-PAYOUTS-ICM** — só se Rui pedir explicitamente (FUTURE).
- **#PYDANTIC-V1-VALIDATOR-DEPRECATION** — migrar 1 validator V1 → V2.

## 10. Próxima sessão

**pt21 — Fase 3 HRC arranque + Beelink prep.** Pré-requisitos:

1. Decisões D1-D5 fechadas pelo Web/Rui.
2. Beelink limpo (opção (a) ou (b)) — Rui faz Fase A antes do arranque
   da sessão técnica.
3. Confirmação visual de espaço livre ≥ 100 GB no Beelink.
4. Sessão de poker do Rui fechada (regra de ouro CLAUDE.md).

Sem isso, pt21 fica pendente em backend Fase B (G3+G4+G2) e UI Fase D
(G5+G6) — útil mas sem o watcher real a funcionar end-to-end.
