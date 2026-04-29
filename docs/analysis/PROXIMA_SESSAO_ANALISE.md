# Próxima sessão (pt7) — plano detalhado

**Data planeada:** 29-Abr 2026 noite ou 30-Abr
**Predecessor:** sessão pt6 (`docs/JOURNAL_2026-04-29-pt6.md`) — Wipe TOTAL + Pipelines 1/2/3 OK + Tech Debts #16/#17/#20 fechados + Tech Debt #21 detectado
**Objectivo:** fechar Tech Debt #21 + completar Pipelines 4-5 (Upload SS manual + Bucket 1 standalone) + audit final

## Estado de partida (pré-pt7)

| Tabela | Counts |
|---|---|
| hands | 16847 (16429 hh_import + 209 hm3 + 209 discord) |
| entries | 280 |
| hand_attachments | 12 |
| hand_villains | 284 (217 nota + 67 sd, pós cleanup 63 stale na pt6) |
| villain_notes | 304 |
| discord_sync_state | 14 canais com cutoff `2026-04-26 00:25:57` UTC |

Backups defensivos disponíveis:
- `backups/pre_wipe_29abr_pt6_20260429_012027/` — pré-wipe pt6 (76 MB)
- `backups/pre_techdebt17_20260429_002748/` — pré-Tech Debt #17 fix

## Plano sessão pt7

### Step 1 — Recap e leitura do contexto Tech Debt #21 (~10 min)

**Causa raiz:**
- `import_.py:411` em `import_file` itera `orphan_rows` (entries Discord órfãs com `tm` extraído via Vision)
- Para cada órfã, chama `_enrich_hand_from_orphan_entry(orphan_id, hand_id, raw)` em `screenshot.py:1297`
- `_enrich_hand_from_orphan_entry` lê `hands.all_players_actions` actual da BD (que pode já estar enriched do call anterior)
- Algoritmo `_build_anon_to_real_map` (screenshot.py:520) trabalha com input já enriched (keys=nicks, não hashes) → mappings divergentes
- INSERT em hand_villains com nicks novos (ON CONFLICT só dedup nicks exactos) → acumulação stale

**Magnitude confirmada (pt6):**
- 38 hands distintas afectadas
- 63 villains stale (18% do total villains visíveis pré-cleanup)
- Pior caso: hand 1196 (UTG1, action=Ks) com 6 villains acumulados

**Sintoma Rui (TM5884107821 / hand 923):**
- 3 villains BTN raise: Joao Coelho, QuincasBorba, Anbem
- HH text mostra: BTN seat 1 (hash 294c45d2) ganhou pot uncalled
- Real Vision mapping pelo stack: seat 1 ≈ PikkuHUMPPA (51 BB×200=10200 chips, único disponível)
- Joao Coelho/QuincasBorba/Anbem correspondem aos seats 8/4/5 (foldados)

### Step 2 — Aplicar fix Tech Debt #21 Opção A (~15-20 min)

**Localização:** `backend/app/routers/screenshot.py:1297-1463` (`_enrich_hand_from_orphan_entry`)

**Pseudo-fix proposto** (após linha 1315, antes da fase de algoritmo v2):

```python
# Tech Debt #21: idempotência. Se hand já foi enriched (match_method actual e
# raw populado), pular re-execução. Sem este guard, _build_anon_to_real_map
# trabalha com apa pós-enrich (keys=nicks em vez de hashes) e produz mapping
# divergente, criando villains stale no hand_villains.
matched_hand = dict(hand_rows[0])
existing_pn = matched_hand.get("player_names") or {}
if isinstance(existing_pn, str):
    try:
        existing_pn = json.loads(existing_pn)
    except (ValueError, TypeError):
        existing_pn = {}
existing_mm = existing_pn.get("match_method") if isinstance(existing_pn, dict) else None
has_real_hh = bool((matched_hand.get("raw") or "").strip())

if existing_mm == "anchors_stack_elimination_v2" and has_real_hh:
    # Já enriched — apenas marcar entry como resolved e retornar.
    # Não re-correr algoritmo (input apa não tem hashes, mapping divergente).
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE entries SET status = 'resolved' WHERE id = %s", (entry_id,))
        conn.commit()
    finally:
        conn.close()
    return {
        "status": "already_enriched",
        "hand_id": hand_db_id,
        "players_mapped": 0,
        "anon_map": {},
    }
```

**Validação técnica:**
- Detecção idempotência via `match_method == 'anchors_stack_elimination_v2'` + `raw` populado (ambos só presentes pós-enrich bem-sucedido)
- Marca entry como resolved (semântica preservada)
- Retorna `status='already_enriched'` para callers distinguirem (auto-rematch loop em import_.py pode contar separadamente se quiser)
- Não chama `_create_ggpoker_villain_notes_for_hand` → não cria villains stale

**Risco regressão:**
- Cross-post 2ª entry Discord (mesmo TM): primeiro enrich processa correctamente, segundo skip. `_link_second_discord_entry_to_existing_hand` (screenshot.py:780-?) já trata `discord_tags` append separadamente — não quebra.
- Pode haver caso onde Vision data segunda entry é melhor que primeira — perde-se. Mitigação futura: sempre processar mas comparar quality scores. Por agora skip é seguro.

**Estimativa esforço:** 15-20 min escrita + 10-15 min validação.

### Step 3 — Re-validação 38 hands afectadas (~15 min)

**Estratégia:** após fix deployed, re-importar pelo menos 1 dos 3 ZIPs e auditar:
- Hand 923 (TM5884107821) deve manter apenas 1 villain BTN raise (não acumulado)
- Hands 1196, 1514 (top stale) idem
- Audit script: contar combinações `(hand_db_id, position, vpip_action)` com >1 villain — esperar **0**

```sql
SELECT COUNT(*) FROM (
  SELECT hand_db_id, position, vpip_action
  FROM hand_villains
  WHERE position IS NOT NULL
  GROUP BY hand_db_id, position, vpip_action
  HAVING COUNT(*) > 1
) sub
-- esperado: 0
```

**Critério sucesso Step 3:**
- 0 combinações stale
- Hand 923 com exactamente 1 villain BTN
- Counts hand_villains coerentes (redução ou estável vs pt6)

### Step 4 — Pipeline 4 Upload SS manual (~15-20 min)

**Não testado em pt6.** Rui faz 1 upload de SS manual via UI:

1. Sidebar → Importar → Upload screenshot
2. Aguarda Vision processing
3. Verifica match SS↔HH:
   - Se TM extraído via Vision bate com hand existente: `_enrich_hand_from_orphan_entry` chamado → match_method='anchors_stack_elimination_v2'
   - Se não bate: hand fica órfã (`status='new'` na entry screenshot)

**Validação SQL:**
```sql
SELECT id, source, entry_type, status, raw_json->>'tm' AS tm
FROM entries
WHERE entry_type = 'screenshot'
ORDER BY id DESC LIMIT 5;
```

**Critério sucesso:**
- Entry created com `entry_type='screenshot'`, `source='manual'` (ou similar)
- Vision processou (`raw_json->>'vision_done'` = true)
- Se match: hand correspondente tem `match_method='anchors_stack_elimination_v2'`

### Step 5 — Pipeline 5 Bucket 1 retroactivo standalone (~10 min)

Bucket 1 já foi parcialmente testado durante Pipeline 2 (12 hand_attachments criados via trigger automático). Para teste standalone:

**Estratégia:** chamar endpoint admin directamente (verificar se existe `/api/attachments/match-retroactive` ou similar) ou fazer SQL UPDATE para forçar trigger.

**Verificação:**
- Listar entries `image / status='new'` actuais
- Confirmar quais já fizeram match retroactivo via `hand_attachments`
- Se houver imagens órfãs (entries image sem hand match), trigger deve resolvê-las

**Critério sucesso:**
- 0 ERROR no trigger background
- `hand_attachments` count estável ou crescente (sem regressão)

### Step 6 — Validação visual Rui + audit final (~15 min)

Checklist:
1. **Vilões → tab "Mãos com SD"** — clicar 2-3 villains aleatórios, confirmar que tinham cards no replayer (sem fantasmas pós-fix #21)
2. **Vilões → tab "Notas"** — 217 villains cat=nota, sample 2-3 confirma legitimidade
3. **Estudo > Por Tags** — secções `nota (31)`, `pos-pko (54+)`, cross-posts (`nota+pos-pko`, etc.)
4. **Torneios → GG → Com SS** — populado, navegação OK
5. **Dashboard** — totals coerentes pós-fix
6. **Discord** — 14 canais, sync history visível

### Step 7 — Fecho sessão pt7

- Criar `docs/JOURNAL_2026-04-29-pt7.md` (ou `JOURNAL_2026-04-30.md`)
- Update `VALIDACAO_END_TO_END.md` §11 (ou criar §12)
- Commit + push
- Reportar a Rui

## Comandos exactos para arranque pt7

### Verificar ponto de partida

```bash
# Posição git
git log --oneline -10

# Ler journal pt6
cat docs/JOURNAL_2026-04-29-pt6.md

# Ler plano pt7 (este ficheiro)
cat docs/analysis/PROXIMA_SESSAO_ANALISE.md

# Counts BD actuais
railway service Postgres
railway run python -c "
import os
for k in list(os.environ):
    if k.startswith('PG'): del os.environ[k]
import psycopg2
dsn = os.environ['DATABASE_PUBLIC_URL']
try: dsn = dsn.encode('cp1252').decode('utf-8')
except: pass
conn = psycopg2.connect(dsn)
cur = conn.cursor()
for tbl in ['hands', 'entries', 'hand_attachments', 'hand_villains', 'villain_notes', 'discord_sync_state']:
    cur.execute(f'SELECT COUNT(*) FROM {tbl}')
    print(f'  {tbl}: {cur.fetchone()[0]}')
conn.close()
"
```

### Aplicar fix Tech Debt #21 (após aprovação plano)

```bash
# Editar screenshot.py:1297 — adicionar guard idempotência após hand_rows fetch
# Localização exacta: backend/app/routers/screenshot.py:1297-1316

# Mostrar diff antes de commit
git diff backend/app/routers/screenshot.py

# Commit (após aprovação Rui)
git add backend/app/routers/screenshot.py
git commit -m "fix(enrich): idempotencia em _enrich_hand_from_orphan_entry (Tech Debt #21)

..."

git push origin main
```

### Re-validar Step 3 pós-deploy

```bash
# Esperar deploy (Application startup complete)
# Re-correr audit Tech Debt #21 (mesmo script da pt6)
railway run python investigate_techdebt21_magnitude.py
# Esperar: 0 combinações stale

# Re-importar 1 ZIP (Rui via UI)
# Re-correr audit
```

## Critérios de sucesso pt7

| Step | Critério |
|---|---|
| 1 | Contexto absorvido (5 min de leitura) |
| 2 | Diff aplicado + 2 aprovações Rui (plano + diff) + commit + deploy |
| 3 | 0 combinações stale (`(hand, pos, vpip_action)` com >1 villain) |
| 4 | 1 upload SS manual processado com sucesso (Vision OK + match ou órfão correctamente) |
| 5 | Bucket 1 trigger não falha (manual ou automático) |
| 6 | Validação visual 6/6 OK |
| 7 | JOURNAL pt7 commited + push |

## Pontos de atenção

### NÃO fazer

- Wipe TOTAL — não há motivo, fix #21 é cirúrgico
- Re-importar todos os 3 ZIPs — 1 ZIP chega para validar fix
- Cleanup adicional — 63 stale já apagados na pt6

### Riscos identificados

1. **Fix #21 rompe cross-post 2ª entry** — mitigação: `_link_second_discord_entry_to_existing_hand` trata `discord_tags` separadamente, não depende de re-enrich
2. **Vision quality second entry > first** — mitigação aceite: skip é seguro, perda marginal de qualidade
3. **Tech Debt #18 (não-determinismo cross-post) fica resolvido?** — provável sim (skip elimina divergência), mas validar pós-fix

### Decisões pendentes Rui

- Fix Tech Debt #15 (Dashboard datas anómalas) na pt7 ou adiar? — esforço 10 min, baixo risco
- Tech Debt #10 (parser Winamax `la/La`) na pt7 ou adiar? — independente, 15-20 min

## Anexos

### Comandos railway úteis

```bash
# Switch service para BD (queries SQL)
railway service Postgres

# Switch service para app (logs)
railway service poker-app

# Logs filtrados
timeout 15 railway logs 2>&1 | grep -iE "import|villain|enrich|error" | tail -20

# Variáveis serviço actual
railway variables
```

### Ficheiros relevantes para fix #21

- `backend/app/routers/screenshot.py:1297-1463` (`_enrich_hand_from_orphan_entry`)
- `backend/app/routers/import_.py:411-422` (auto-rematch loop)
- `backend/app/routers/screenshot.py:520-687` (`_build_anon_to_real_map`)
- `backend/app/routers/mtt.py:766-860` (`_create_ggpoker_villain_notes_for_hand`)
- `backend/app/routers/mtt.py:632-763` (`_create_villains_for_hand`)

### Helpers já fechados (para referência)

- Tech Debt #16 fix em `mtt.py:854` (commit `6765f44`)
- Tech Debt #17 fix em `mtt.py:677` (commit `f818da6`)
- Tech Debt #20 fix em `gg_hands.py:160` (commit `429833a`)
