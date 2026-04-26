# SPEC — Bucket 1: Imagens directas Discord como anexos a mãos

**Status:** spec aprovada, implementação adiada para sessão dedicada.
**Última revisão:** 2026-04-26.
**Autor desta versão:** sessão 26-Abr (Rui + Claude). Decisões Q1-Q5 confirmadas pelo Rui.

---

## 1. Contexto e regra de produto

A regra de produto está documentada permanentemente em `CLAUDE.md` na secção **"Imagens de contexto Discord — comportamento de produto"** — fonte de verdade. Esta spec é a tradução operacional dessa regra.

Resumo aplicável aqui:

- Imagens directas Discord (anexos `.png/.jpg/.webp`, links Gyazo) são **anexos a mãos**, não mãos por si.
- Match: mesmo canal Discord + janela ±90s. Fallback: ±90s em qualquer canal Discord do mesmo torneio (mãos via HM3).
- UI: imagem **inline** ao lado da mão durante estudo, sem clicks extras.
- Pipeline **não** deve criar hand placeholders a partir de `entry_type='image'`.

Estado actual em produção (2026-04-26): há **8 entries `image`** em BD, todas órfãs (`vision_done=null`, sem hand associada). Pipeline anterior (`bf0d9de`) tentou tratá-las como mãos disparando Vision; reconhecido como errado, decisão é reverter e implementar modelo novo.

## 2. Decisões tomadas pelo Rui (Q1-Q5)

Confirmadas em conversa de 26-Abr:

| Q | Decisão | Razão |
|---|---|---|
| **Q1 — Como reverter `bf0d9de`?** | Revert inteiro do commit antes de implementar. Helper `_fetch_entry_image_bytes` re-introduzido limpo no commit do worker novo. | Reduz drift entre commits, deixa o histórico legível. |
| **Q2 — Cache local dos bytes?** | Sim — `img_b64` em `hand_attachments` para imagens Gyazo (link rot real). Para imagens Discord CDN, considerar URL apenas (Discord CDN é estável). | Trade-off storage vs link rot. Gyazo tem casos comprovados de links a morrer; Discord CDN não. |
| **Q3 — Cross-post da mesma imagem em múltiplos canais?** | **N/A.** Confirmado pelo Rui que na prática não acontece — quando posta a mesma imagem em 2 canais é por engano e raro. Lógica de dedupe **opcional**, não bloqueante. | Caso real visto (cluster 24-Mar 03:31, 3 entries) é a única ocorrência em 8 imagens. |
| **Q4 — UI** | Lista compacta (`HandRow`): ícone "📎 N" indicando contagem de anexos. Detalhe (`HandDetailPage`): thumbnails 200px inline, click → nova aba (mesmo padrão do `PlaceholderHandRow`). | Lista densa não comporta thumbnails sem perder densidade. Detalhe tem espaço. |
| **Q5 — Quando dispara o worker?** | 4 momentos: (1) após `sync-and-process` Discord, (2) após `import_hm3` (CSV), (3) endpoint manual `POST /api/attachments/match` para forçar, (4) após criação de qualquer mão nova com `played_at` próximo de imagens órfãs. | Cobre todas as ordens de chegada (imagem antes/depois/ao mesmo tempo da mão). |

## 3. Schema proposto

`backend/app/routers/<novo>.py` ou em `hands.py` via `ensure_hand_attachments_schema()`:

```sql
CREATE TABLE IF NOT EXISTS hand_attachments (
    id            BIGSERIAL PRIMARY KEY,
    hand_db_id    BIGINT NOT NULL REFERENCES hands(id) ON DELETE CASCADE,
    entry_id      BIGINT REFERENCES entries(id) ON DELETE SET NULL,
    image_url     TEXT,                                    -- URL original (gyazo, discord cdn)
    cached_url    TEXT,                                    -- URL local servido pelo backend (opcional)
    img_b64       TEXT,                                    -- bytes base64 (cache para Gyazo)
    mime_type     TEXT,
    posted_at     TIMESTAMPTZ NOT NULL,                    -- quando a imagem foi postada
    channel_name  TEXT,                                    -- canal Discord (NULL se outro source)
    match_method  TEXT NOT NULL,                           -- 'discord_channel_temporal' | 'hm3_temporal_fallback' | 'manual'
    delta_seconds INTEGER,                                 -- |posted_at - hand.played_at| em segundos
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_hand_attachments_hand  ON hand_attachments(hand_db_id);
CREATE INDEX IF NOT EXISTS idx_hand_attachments_entry ON hand_attachments(entry_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_hand_attachments_hand_entry
    ON hand_attachments(hand_db_id, entry_id) WHERE entry_id IS NOT NULL;
```

Notas:
- `ON DELETE CASCADE` em `hand_db_id`: apagar a mão apaga os anexos.
- `ON DELETE SET NULL` em `entry_id`: apagar o entry preserva o anexo (URL ainda válido).
- UNIQUE parcial impede mesma `(hand, entry)` duplicada se o worker reprocessar.
- `delta_seconds` = `|posted_at - hand.played_at|` em segundos, **uniforme em ambos os paths** (primário e fallback). É a magnitude da distância temporal entre a imagem postada e a mão jogada — métrica de qualidade do match. Sinal pode reconstruir-se de `posted_at - hand.played_at` se necessário.
  - **Distinção importante:** a *janela* de match primário é definida pelo sibling delta (entry image vs entry replayer_link no mesmo canal, ±90s — ver §4); o *valor* `delta_seconds` guardado é image-to-played_at. Os dois números podem diferir (ver §6 — entry 13 tem sibling delta 7s mas image-to-played_at 18s).

## 4. Pipeline em 3 fases

### Fase Ingest (sem mudança no bot Discord)
O bot continua a registar entries `image` como hoje (`source='discord'`, `entry_type='image'`, `raw_text=URL`, `discord_posted_at`, `discord_channel`). **Nenhuma chamada a Vision para `image`.** A entry fica `status='new'` à espera do worker.

### Fase Worker (novo)
Endpoint `POST /api/attachments/match` (e versão `/preview` GET sem efeitos). Itera entries `image` pendentes (sem row em `hand_attachments`):

1. **Match primário:** `SELECT hands` JOIN `entries` onde `e.discord_channel = img.discord_channel` AND `ABS(EXTRACT(EPOCH FROM (e.discord_posted_at - img.discord_posted_at))) <= 90`. Se houver candidatos, escolher o **mais próximo temporalmente**.
2. **Match fallback:** se primário falhou, `SELECT hands` onde `origin IN ('hm3','hh_import')` AND `ABS(EXTRACT(EPOCH FROM (h.played_at - img.discord_posted_at))) <= 90`. Mesma lógica de tiebreaker.
3. **Se 1 ou 2 acertou:** download dos bytes (helper `_fetch_entry_image_bytes` reintroduzido) → INSERT em `hand_attachments` com `match_method` apropriado, `delta_seconds`, `img_b64` cacheado se Gyazo. Marcar entry `status='attached'`.
4. **Se nenhum acertou:** entry fica `status='new'`. Worker re-tenta no próximo trigger.

### Fase Retroactivo (triggers existentes)
Após `sync-and-process` (Discord), após `import_hm3` (CSV), e (Q5) após qualquer criação de hand nova com `played_at` próximo, executar query: "há entries `image` em ±90s sem anexo? Cria attachment." Mesmo padrão dos auto-rematch existentes em `import_.py:347` e `hm3.py:1163`.

## 5. Edge cases mapeados

1. **Imagem ±90s de DUAS mãos no mesmo canal** (caso real entry 13). Tiebreaker: **mais próxima temporalmente**. Empate exacto → mais antiga. Anexar a **uma só**.
2. **Imagem postada antes da mão** (`Δ` negativo, pré-anúncio). Match retroactivo funciona porque o worker corre após `import_hm3` também. Janela ±90s simétrica.
3. **Mão HM3 chega depois da imagem.** Worker retroactivo trata. Cobre o cenário "imagem 19:48, HM3 import nessa noite".
4. **Apagar uma mão com anexos.** `ON DELETE CASCADE` — anexos vão atrás. Apagar entry preserva o anexo (`SET NULL` em `entry_id`).
5. **Cross-post múltiplo da mesma imagem.** Decisão Q3: **N/A** na prática. Lógica de dedupe por URL fica opcional (não bloqueante para v1).
6. **Imagem sem `discord_channel` ou sem `discord_posted_at`.** Match falha (sem janela temporal). Fica órfã. Aceitável.
7. **Replayer link **e** image no mesmo canal ±90s.** Replayer já vira hand placeholder; image junta-se como attachment dessa mesma hand. Sem conflito.

## 6. Estado real das 8 entries existentes

Verificado em prod a 2026-04-26 com query `±90s`. Janela é sibling delta (entry image vs entry replayer_link irmã); valor `delta_seconds` armazenado é image-to-played_at (uniforme com fallback path):

| entry_id | canal | posted_at (UTC) | URL gyazo | match candidato | sibling Δ | image→played_at Δ (`delta_seconds`) | resultado |
|---|---|---|---|---|---|---|---|
| 6 | icm-pko | 2026-03-23 19:48:39 | `00bd8eea48b6e9...` | nenhum | — | — | órfã |
| 7 | icm-pko | 2026-03-24 03:31:42 | `c0871ebc6529...` | nenhum | — | — | órfã (cross-post 1/3) |
| 46 | pos-pko | 2026-03-24 03:31:45 | `c0871ebc6529...` | nenhum | — | — | órfã (cross-post 2/3) |
| 133 | nota | 2026-03-24 03:31:48 | `c0871ebc6529...` | nenhum | — | — | órfã (cross-post 3/3) |
| 13 | icm-pko | 2026-03-25 20:29:21 | `4a776e1922de...` | hand 117 (sibling 7s) ✓ / hand 85 (sibling 64s) | 7s | **18s** | **match** com hand 117 (sibling mais próximo) |
| 17 | icm-pko | 2026-03-25 21:27:35 | `fd1a6adb7c99...` | hand 115 (sibling 10s) | 10s | **23s** | **match** com hand 115 |
| 87 | pos-pko | 2026-04-23 16:57:55 | `f77335e1ccb1...` | hand 67 (sibling 65s) | 65s | **78s** | **match** com hand 67 |
| 35 | icm | 2026-04-23 19:33:23 | `f6e9f5afbc30...` | nenhum | — | — | órfã |

**Resumo:** 3 das 8 (38%) entram com a regra ±90s. 5 das 8 (62%) ficam órfãs hoje — destas, 3 são a mesma URL cross-postada (1 imagem real + 2 cross-posts). Apenas **1 imagem genuinamente órfã** (entry 6) + **1 imagem com cross-posts órfã** (cluster 24-Mar) + **1 imagem órfã** (entry 35).

**Nota sobre os dois deltas:** o "sibling Δ" valida que a entry image é vizinha temporal de uma entry replayer_link no mesmo canal (regra de match primário, janela ±90s). O `delta_seconds` armazenado em `hand_attachments` é o image-to-played_at — métrica uniforme com o fallback path. Confirmado via `_compute_match_candidates(100)` em prod a 2026-04-27.

## 7. Plano de implementação ordenado

### Fase I — Revert `bf0d9de`
- **Ficheiros:** `backend/app/routers/discord.py` (único modificado pelo `bf0d9de`).
- **Acção:** `git revert bf0d9de`. Confirma que `process_replayer_links` volta a `entry_type='replayer_link'` puro e que `_fetch_entry_image_bytes` desaparece.
- **Riscos:** zero — `bf0d9de` é commit puro de adição. Revert é matemático.
- **Dependência:** nenhuma. Primeira fase.

### Fase II — Migração `hand_attachments`
- **Ficheiros:** `backend/app/routers/hands.py` (adicionar `ensure_hand_attachments_schema()`) + `backend/app/main.py` (chamar a função no `lifespan`).
- **Acção:** novo `CREATE TABLE` + 3 índices conforme §3. Idempotente via `IF NOT EXISTS`.
- **Riscos:** baixos — tabela nova, sem alterar tabelas existentes. Único risco real é typo no schema; testar via fresh boot Railway antes de avançar.
- **Dependência:** **pré-requisito de I (revert primeiro para evitar histórico contraditório)**. III/IV/V dependem desta tabela existir.

### Fase III — Worker `/api/attachments/match`
- **Ficheiros:** novo `backend/app/routers/attachments.py` (router) + registar em `backend/app/main.py`. Helper `_fetch_entry_image_bytes` reintroduzido neste novo ficheiro (não em `discord.py`).
- **Acção:** endpoints `GET /preview` e `POST /match?confirm=true&limit=N`. Lógica de match primário + fallback + INSERT em `hand_attachments`.
- **Riscos:** se a query SQL do match estiver mal, pode anexar errado massivamente. Mitigação: `/preview` obrigatório antes de `?confirm=true`; `delta_seconds` na tabela permite auditoria pós-facto; `match_method` permite diff por modo.
- **Dependência:** II (tabela tem que existir).

### Fase IV — Triggers retroactivos
- **Ficheiros:** `backend/app/routers/discord.py` (`sync_and_process` ganha chamada extra ao worker), `backend/app/routers/hm3.py` (`import_hm3` ganha igual), `backend/app/services/hand_service.py` (após `_insert_hand` opcionalmente).
- **Acção:** chamar `attachments.run_match()` (helper interno chamado pelo endpoint da Fase III, refactorado para reuso) com `limit` razoável.
- **Riscos:** corre em **caminho síncrono** dos endpoints existentes — pode tornar `import_hm3` mais lento. Mitigação: `asyncio.create_task` para não bloquear response. Risco secundário: se worker tiver bug, partial state em prod.
- **Dependência:** III (worker tem que existir como função reusable).

### Fase V — UI: ícone na lista + thumbnails no detalhe
- **Ficheiros:** `frontend/src/components/HandRow.jsx` (adicionar ícone "📎 N" se `hand.attachment_count > 0`), `frontend/src/pages/HandDetailPage.jsx` (secção "Contexto" com thumbnails 200px).
- **Backend complementar:** `GET /api/hands/{id}` passa a devolver `attachments: [...]`; `GET /api/hands` (lista) passa a devolver `attachment_count` agregado por mão (subquery LEFT JOIN COUNT).
- **Riscos:** `GET /api/hands` é hot path — adicionar subquery COUNT em todas as rows pode degradar performance se a lista for grande. Mitigação: índice `idx_hand_attachments_hand` já planeado; medir tempo antes/depois.
- **Dependência:** III (precisa de dados em `hand_attachments` para mostrar). IV ajuda mas não é estritamente bloqueante (pode-se popular manualmente via Fase VI).

### Fase VI — Backfill das 3 entries que matcham hoje
- **Ficheiros:** novo script `backfill_attach_orphan_images.py` na raiz (padrão dos outros backfills).
- **Acção:** dry-run + `--execute`. Para entries 13, 17, 87 (ver §6), criar attachment com `match_method='discord_channel_temporal'`. Snapshot CSV antes.
- **Riscos:** baixos — 3 rows. Dry-run obriga a inspecção visual antes.
- **Dependência:** III (worker existir) — script chama o helper interno do worker em vez de duplicar lógica.

### Fase VII — Actualizar MAPA + CLAUDE.md
- **Ficheiros:** `docs/MAPA_ACOPLAMENTO.md` (nova entrada secção §2 ou §8 para tabela `hand_attachments`), `CLAUDE.md` (actualizar secção "Imagens de contexto Discord" para apontar para implementação real).
- **Acção:** documentar tabela nova, novo endpoint, novos triggers, mudança UI.
- **Riscos:** nenhum (só docs).
- **Dependência:** todas as anteriores (documentar o que existe).

---

## Notas de implementação para sessão dedicada

- Cada fase deve fechar com commit próprio. Revert (Fase I) num commit; tabela (Fase II) noutro; etc.
- Antes de qualquer chamada `confirm=true` em prod, correr `/preview` e mostrar ao Rui.
- Manter `bf0d9de` em prod até à Fase I — não há urgência em tirar (não está a fazer mal porque o filtro `site='GGPoker'` impede que apanhe imagens).
- Se `entry_type='image'` chegar a hands inadvertidamente em qualquer momento, marcar isso como bug crítico — viola a regra de produto.
