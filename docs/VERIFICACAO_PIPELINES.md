# Verificação de Pipelines — Poker App

Playbook reusável para validar end-to-end os 5 pipelines de ingestão da app. Substitui `docs/VALIDACAO_END_TO_END.md` e `docs/PIPELINE_VERIFICATION_GUIDE.txt`. Estes 2 documentos estavam datados de 26/29 Abril 2026 (pré-pt7) e foram ultrapassados por 7 sessões: refactor #B23 (`apply_villain_rules` única fonte de criação de vilões), regra B do showdown eliminada (#B8), Bucket 1 automático substituído por galeria manual (#B9), `study_state` simplificado para 3 estados (pt13), Inbox eliminada, `tournaments_meta` canónica (pt12), excepção #B19 estendida a Discord (pt10), entre outras.

## Propósito e âmbito

A app conjuga 4 pipelines de **ingestão** (HM3, Import ZIP/TXT HH, Discord, Upload manual SS) com 1 pipeline de **anexação** (Galeria manual de imagens). Cada um deixa marca diferente em `hands.origin`. Este playbook valida que cada pipeline produz o estado esperado em base de dados e na UI, respeitando as regras duras documentadas em `docs/REGRAS_NEGOCIO.md §6`.

Cada secção é independente — pode ler-se 1 pipeline isolado sem percorrer os outros. A secção final "Última validação ponta-a-ponta" é um snapshot preenchível, datado, que regista o último ciclo completo executado.

## Princípios gerais

### Quando validar

Usa este playbook após qualquer fix que toque um pipeline (parser, enrich, classification de vilões, schema). Faz uma corrida completa após imports grandes que envolvam várias origens em simultâneo (ZIP HH + Discord sync + SSs no mesmo dia). Mensalmente corre os 5 pipelines em ciclo para detectar regressões silenciosas.

### Como validar (ordem BD → UI)

Sempre dois passos: primeiro confirma o estado em base de dados via queries SQL, depois confirma a UI na app. A BD não mente; a UI pode ter cache, race conditions, ou render bugs que mascaram dados correctos. **Princípio invariante GG anonimizada**: nunca deve existir row em `hand_villains` para uma `hand` cujo `match_method` esteja NULL ou comece por `discord_placeholder_*`.

### Critério de sucesso

Um pipeline está validado quando:

- Pré-condições cumpridas.
- Cada Etapa devolve o esperado em SQL.
- A UI mostra o resultado correcto em todos os locais relevantes (Dashboard, Estudo, Vilões, página de origem).
- Validações cross-cutting (X1-X5) não detectam regressões nas 4 regras duras.

### Convenções deste playbook

- Placeholders em queries: `<TM>` para um `tournament_number` (ex: `5891409707`); `<TM_TESTE>` quando vais querer a hand inteira `GG-<TM>`.
- Filtro permanente de 2026: queries críticas incluem explicitamente `played_at >= '2026-01-01'` (regra dura `REGRAS_NEGOCIO.md §5`/R12). Histórico anterior existe em prod mas é ruído para qualquer análise actual.
- Janelas temporais: `created_at >= NOW() - INTERVAL '<N> minutes'` como fence para hands recentes.
- Ciclos limpos: apaga dados de teste **antes** de re-correr o pipeline, em vez de tentar corrigir estado parcial.
- Comparações `match_method`: usa `(player_names ->> 'match_method')` — vive em JSONB, não em coluna própria.

## Mapa dos 5 pipelines

| # | Pipeline | Endpoint principal | `origin` | O que produz |
|---|---|---|---|---|
| 1 | HM3 `.bat` | `POST /api/hm3/import` | `'hm3'` | Mãos Winamax/WPN/PokerStars com `hm3_tags` reais. Nunca trás GG. |
| 2 | Import ZIP/TXT HH | `POST /api/import` | `'hh_import'` | Mãos GG (anonimizadas, ZIP) ou outras salas (TXT). Popula `tournaments_meta` para GG. |
| 3 | Discord sync | `POST /api/discord/sync-and-process` | `'discord'` | Replayer-links + imagens + HH text. Cria placeholders GGDiscord para SSs sem HH ainda. |
| 4 | Upload manual SS | `POST /api/screenshots` | `'ss_upload'` | Placeholder com `tags=['SSMatch']` à espera de HH. |
| 5 | Galeria manual de imagens | `GET /api/images/gallery` + `POST /api/hands/{hand_db_id}/images` + `DELETE /api/hands/{hand_db_id}/images/{ha_id}` | n/a (anexação, não ingestão) | Row em `hand_attachments` ligando entry image ↔ hand. |

## Pré-condições partilhadas

- Frontend e backend deployed (sem deploys pendentes em Railway).
- BD ligada (Railway CLI configurado para o projecto Postgres).
- Vision API configurada (`OPENAI_API_KEY` em env).
- `HERO_NAMES_BY_SITE` e `FRIEND_HEROES` actualizados em `backend/app/hero_names.py` se houver heroes ou amigos novos.
- Filtro permanente: todas as queries ad-hoc incluem `played_at >= '2026-01-01'` quando filtram `hands`.

---

## Pipeline 1 — HM3 `.bat`

### Descrição

O `.bat` no PC do Rui lê a BD do HoldemManager 3, extrai HHs com tags HM3 dentro do período pedido, e faz POST para `/api/hm3/import`. Backend insere com `origin='hm3'`, parse de raw text, extracção de campos canónicos. Cria vilões via `apply_villain_rules` (canónica desde refactor #B23 / pt10). HM3 só importa Winamax / WPN / PokerStars — nunca trás GGPoker (que entra exclusivamente via Pipeline 2 ou Pipeline 3 + Pipeline 4).

### Pré-condições

- HM3 instalado e funcional no PC do Rui.
- Script `.bat` configurado com URL backend correcto.
- Tags HM3 configuradas (ver `HM3_REAL_TAGS` em `backend/app/routers/hands.py`).
- Pré-condições partilhadas cumpridas.

### Etapa A — Limpeza opcional (ciclo limpo)

```sql
-- Identificar mãos HM3 do dia em teste:
SELECT id, hand_id, site, played_at, hm3_tags
FROM hands
WHERE origin = 'hm3' AND played_at >= '2026-01-01'
  AND created_at >= '<data>'
ORDER BY played_at DESC;

-- Apagar (ON DELETE CASCADE em hand_villains.hand_db_id):
DELETE FROM hands WHERE id IN (<lista>);
```

`villain_notes` **não** se apaga: é incremental via UPSERT.

### Etapa B — Correr o `.bat`

1. Abrir terminal Windows na pasta do `.bat`.
2. Executar `hm3_export.bat` (ou nome equivalente).
3. Aguardar resposta (output mostra "X mãos inseridas, Y ignoradas, Z villains criados").

### Etapa C — Validar Fase 1 (mãos inseridas)

```sql
-- Q1.1 mãos HM3 recentes
SELECT id, hand_id, site, origin, hm3_tags, tags,
       played_at, tournament_name, tournament_number, buy_in,
       position, result, hero_cards,
       (raw IS NOT NULL AND raw <> '') AS has_raw
FROM hands
WHERE origin = 'hm3' AND played_at >= '2026-01-01'
  AND created_at >= NOW() - INTERVAL '30 minutes'
ORDER BY created_at DESC
LIMIT 50;

-- Q1.2 distribuição por site
SELECT site, COUNT(*) AS n
FROM hands
WHERE origin = 'hm3' AND created_at >= NOW() - INTERVAL '30 minutes'
GROUP BY site
ORDER BY site;

-- Q1.3 distribuição por hm3_tags
SELECT unnest(hm3_tags) AS tag, COUNT(*) AS n
FROM hands
WHERE origin = 'hm3' AND created_at >= NOW() - INTERVAL '30 minutes'
GROUP BY tag
ORDER BY n DESC;

-- Q1.4 invariante: zero mãos GG via HM3
SELECT COUNT(*) AS gg_via_hm3 FROM hands
WHERE origin = 'hm3' AND site = 'GGPoker'
  AND created_at >= NOW() - INTERVAL '30 minutes';
-- Esperado: 0. HM3 nunca trás GG (regra dura, REGRAS_NEGOCIO.md §1.1).
```

**Esperado:** Q1.1 com `has_raw=true` em todas, todos os campos canónicos populados; Q1.2 distribuição realista (Winamax + PokerStars + WPN); Q1.3 só tags HM3 reais (não tags Discord); Q1.4 = 0.

### Etapa D — Validar Fase 2 (vilões via `apply_villain_rules`)

```sql
-- Q1.5 vilões criados nas mãos HM3 recentes
SELECT h.hand_id, h.site, h.hm3_tags, hv.category, COUNT(hv.id) AS n_villains
FROM hands h
LEFT JOIN hand_villains hv ON hv.hand_db_id = h.id
WHERE h.origin = 'hm3' AND h.created_at >= NOW() - INTERVAL '30 minutes'
GROUP BY h.id, h.hand_id, h.site, h.hm3_tags, hv.category
ORDER BY h.created_at DESC
LIMIT 30;

-- Q1.6 sanity FRIEND_HEROES — entram só por Regra D (category='friend'), nunca como Regra A
-- Karluz/flightrisk podem ter category='nota' SE a hand também cair em Regra A
-- (hm3_tags ~ 'nota%') ou C (discord_tags inclui 'nota'). As categorias são
-- aditivas via set — uma hand com tag 'nota' onde Karluz aparece como non-hero
-- gera 2 rows: ('friend' por D) + ('nota' por A). Nunca devem aparecer como
-- 'sd' (Regra B eliminada em #B8 pt7).
SELECT hv.player_name, hv.category, COUNT(*) AS n
FROM hand_villains hv
JOIN hands h ON h.id = hv.hand_db_id
WHERE h.origin = 'hm3' AND h.created_at >= NOW() - INTERVAL '30 minutes'
  AND LOWER(hv.player_name) IN ('karluz', 'flightrisk')
GROUP BY hv.player_name, hv.category;
-- Esperado: rows com category='friend' (sempre que aparecem como non-hero
-- numa hand HM3 com nicks reais) e/ou category='nota' (apenas se a hand
-- também cair em Regra A — hm3_tags ~ 'nota%'). NUNCA category='sd'.

-- Q1.7 villain_notes incrementos (não double-count após #B29 pt13)
SELECT COUNT(*) AS total_villain_notes,
       (SELECT COUNT(*) FROM villain_notes WHERE updated_at >= NOW() - INTERVAL '30 minutes') AS recent
FROM villain_notes;
```

**Esperado:** Q1.5 mãos com tag `nota%` ou friend nick têm villains (regras A∨D); outras têm 0 (regra B do showdown foi eliminada em pt7 #B8). Q1.6 ver nota inline acima. Q1.7 `recent > 0` quando o `.bat` correu, sem inflação face a `total`.

### Etapa E — Auto-rematch SS órfãs

HM3 importa raras vezes mãos relevantes para SSs Discord pendentes (HM3 só trás non-GG; Discord só recebe GG). Cenário possível mas raro. Se o `.bat` reportar `rematched_screenshots > 0`, validar com a mesma query do Pipeline 3 Etapa E.

### Critério de sucesso Pipeline 1

- Q1.1-Q1.4: mãos inseridas com origin/site/tags coerentes; zero GG.
- Q1.5: vilões criados só por A (tag `nota%`) ou D (friend) — nunca B (showdown sozinho).
- Q1.6: FRIEND_HEROES nunca entram como Regra B (category='sd').
- UI: Dashboard "Últimas mãos importadas" mostra as mãos novas (linha `created_at`); Estudo agrupa por tag normalizada (1 chip por nome, `OriginBadge=HM3`); Vilões mostra os nicks classificados.

### Troubleshooting Pipeline 1

| Sintoma | Causa provável | Verificar |
|---|---|---|
| 0 mãos inseridas | Filtro de dias muito apertado, BD HM3 vazia | Output do `.bat` |
| Mãos GG aparecem com `origin='hm3'` | HM3 export configurado errado | Filter no `.bat`; regra dura R6 viola |
| `position` errada | Botão dealer detectado mal | `_compute_positions_v2` em `parsers/hm3.py` |
| Hero aparece como villain | `HERO_NAMES_BY_SITE` não tem o nick | `backend/app/hero_names.py:123` |
| Villains não criados em hands com tag `nota%` | Race condition em criação de vilões via conexões cruzadas (resolvida em pt9 — ver INVENTARIO #B23 e fixes anteriores) | `services/villain_rules.py:apply_villain_rules` é a única fonte canónica; `_create_hand_villains_hm3` foi apagada no refactor #B23 |
| Nicks com espaço truncados (`la louffe` → `la`) | Parser regex não-greedy sem âncora | Resolvido em pt7 (regex universal `seat_nicks` em `parsers/hm3.py`); confirmar deploy |

---

## Pipeline 2 — Import ZIP/TXT HH

### Descrição

Drag-and-drop de um ZIP de HHs GG ou TXT de qualquer sala em "+ Importar". Backend detecta sala via `_detect_site` / `_detect_site_from_zip`, classifica entries (`hand_history` / `tournament_summary`), e insere via `_insert_hand` com `origin='hh_import'`, `study_state='new'`. Para GG, popula `tournaments_meta` (PK `(site, tournament_number)`, restrito a GG via guard explícito em `services/tournament_meta.py:upsert_tournament_meta`). Auto-rematch retroactivo apanha SSs Discord órfãs cujo TM bate com hands acabadas de importar; cada hand enriched dispara `apply_villain_rules`.

### Pré-condições

- ZIP HH em mãos (ZIP de torneio GG completo, ou TXT individual).
- Pré-condições partilhadas cumpridas.

### Etapa A — Limpeza opcional

```sql
-- Hands hh_import recentes:
SELECT id, hand_id, site, played_at, tournament_number
FROM hands
WHERE origin = 'hh_import' AND played_at >= '2026-01-01'
  AND created_at >= '<data>'
ORDER BY created_at DESC;

DELETE FROM hands WHERE id IN (<lista>);
```

Se quiseres re-popular `tournaments_meta` com hands novas, podes apagar selectivamente:

```sql
DELETE FROM tournaments_meta
WHERE site = 'GGPoker' AND tournament_number IN (<lista>);
```

### Etapa B — Drag-and-drop ZIP/TXT

1. Abrir app → "+ Importar".
2. Drag-and-drop do ficheiro.
3. Aguardar response: "X mãos inseridas · Y ignoradas pré-2026 · Z screenshots matched".

### Etapa C — Validar Fase 1 (mãos inseridas)

```sql
-- Q2.1 mãos hh_import recentes
SELECT id, hand_id, origin, site, played_at, tournament_name, tournament_number,
       (player_names ->> 'match_method') AS mm,
       cardinality(COALESCE(discord_tags, '{}'::text[])) AS n_discord_tags
FROM hands
WHERE origin = 'hh_import' AND played_at >= '2026-01-01'
  AND created_at >= NOW() - INTERVAL '30 minutes'
ORDER BY created_at DESC
LIMIT 50;

-- Q2.2 placeholders Discord substituídos (placeholder upgrade #B23/_insert_hand)
-- Confirma que placeholders pré-existentes ao import passaram para HH real:
SELECT h.hand_id, (h.player_names ->> 'match_method') AS mm,
       h.discord_tags, h.origin
FROM hands h
WHERE h.hand_id LIKE 'GG-%'
  AND h.created_at >= NOW() - INTERVAL '30 minutes'
  AND cardinality(COALESCE(h.discord_tags, '{}'::text[])) > 0
ORDER BY h.created_at DESC
LIMIT 30;
-- Esperado: discord_tags preservados pós-substituição. mm pode estar v2 (se SS já foi processada) ou NULL (GG anon ainda).

-- Q2.3 cross-post: discord_tags não perdeu canais (R4)
SELECT hand_id, discord_tags, origin, (player_names ->> 'match_method') AS mm
FROM hands
WHERE created_at >= NOW() - INTERVAL '30 minutes'
  AND cardinality(COALESCE(discord_tags, '{}'::text[])) >= 2
ORDER BY hand_id;
```

**Esperado:** Q2.1 com `origin='hh_import'`, mãos GG têm `mm` NULL (anonimizadas) ou `'anchors_stack_elimination_v2'` (se SS bateu auto-rematch); Q2.2 placeholders preservam `discord_tags`; Q2.3 todos os canais Discord propagaram (helper `append_discord_channel_to_hand` #B12 pt9).

### Etapa D — Validar `tournaments_meta` populada

```sql
-- Q2.4 tournaments_meta para TMs GG da nova importação
SELECT tournament_number, site, tournament_name, buy_in, currency,
       tournament_format, starting_stack, hand_count, updated_at
FROM tournaments_meta
WHERE site = 'GGPoker'
  AND updated_at >= NOW() - INTERVAL '30 minutes'
ORDER BY updated_at DESC;

-- Q2.5 sanity Stack Inicial (não é stack mid-tournament)
SELECT tournament_number, starting_stack, tournament_name
FROM tournaments_meta
WHERE site = 'GGPoker'
  AND updated_at >= NOW() - INTERVAL '30 minutes'
  AND (starting_stack IS NULL OR starting_stack < 1000)
ORDER BY tournament_number;
-- Esperado: zero rows. Stack Inicial GG são tipicamente 10k-30k (Bounty Hunters / ICM / etc.).

-- Q2.6 invariante: zero rows non-GG em tournaments_meta
SELECT COUNT(*) FROM tournaments_meta WHERE site != 'GGPoker';
-- Esperado: 0. Guard explícito em upsert_tournament_meta (pt12).
```

**Esperado:** Q2.4 1 row por TM GG na ZIP; Q2.5 `starting_stack` razoável; Q2.6 = 0.

### Etapa E — Validar enrich SS↔HH retroactivo + `apply_villain_rules`

Se havia SSs Discord órfãs cujo TM bate com hands da ZIP, o auto-rematch (`import_.py` chama `_enrich_hand_from_orphan_entry`) deve ter promovido essas hands a `mm='anchors_stack_elimination_v2'` com `anon_map` populado e disparado `apply_villain_rules`.

```sql
-- Q2.7 hands ZIP que ganharam mm v2 retroactivamente
SELECT h.hand_id, (h.player_names ->> 'match_method') AS mm,
       jsonb_typeof(h.player_names -> 'anon_map') AS anon_type,
       h.discord_tags
FROM hands h
WHERE h.origin = 'hh_import'
  AND h.created_at >= NOW() - INTERVAL '30 minutes'
  AND (h.player_names ->> 'match_method') = 'anchors_stack_elimination_v2'
LIMIT 5;

-- Q2.8 anon_map nunca vazio quando mm='v2' (#B32 fix pt10)
SELECT h.hand_id,
       jsonb_typeof(h.player_names -> 'anon_map') AS anon_type,
       (h.player_names -> 'anon_map') = '{}'::jsonb AS is_empty_object
FROM hands h
WHERE (h.player_names ->> 'match_method') = 'anchors_stack_elimination_v2'
  AND h.created_at >= NOW() - INTERVAL '30 minutes'
  AND (
    (h.player_names -> 'anon_map') IS NULL
    OR jsonb_typeof(h.player_names -> 'anon_map') != 'object'
    OR (h.player_names -> 'anon_map') = '{}'::jsonb
  );
-- Esperado: zero rows. Defesa-em-camadas #B32 pt10:
--   (1) screenshot.py só promove mm='v2' quando anon_map populado;
--   (2) guard idempotência em _enrich exige anon_map populado para early-return.

-- Q2.9 vilões criados nas hands enriched (Regra C: discord_tags inclui 'nota')
SELECT h.hand_id, h.discord_tags, hv.category, hv.player_name
FROM hands h
JOIN hand_villains hv ON hv.hand_db_id = h.id
WHERE h.origin = 'hh_import'
  AND h.created_at >= NOW() - INTERVAL '30 minutes'
  AND 'nota' = ANY(h.discord_tags)
ORDER BY h.hand_id;
-- Esperado: ≥1 villain por hand (pré-#B33 falhava silenciosamente para entries onde Vision omitia prefixo TM).
```

### Critério de sucesso Pipeline 2

- Q2.1-Q2.3: mãos inseridas com `origin='hh_import'`; placeholders Discord preservados; cross-post intacto.
- Q2.4-Q2.6: `tournaments_meta` populada para TMs GG; `starting_stack` razoável; zero rows non-GG.
- Q2.7-Q2.9: enrich retroactivo dispara em hands com SSs órfãs prévias; `anon_map` nunca vazio para `mm='v2'`; Regra C dispara em canais `nota` com match real.
- UI: Torneios > GG mostra novas mãos; Estudo "Por Tags" agrupa torneios por `tournament_number` (chave `tm:${number}`); Vilões mostra novos nicks classificados.

### Troubleshooting Pipeline 2

| Sintoma | Causa provável | Verificar |
|---|---|---|
| `tournament_name` NULL em hands | Parser não detectou nome no header HH | `parsers/gg_hands.py` ou `parsers/winamax.py` |
| `starting_stack` corrupto (mid-tournament) em `tournaments_meta` | hand pré-existente do TM em BD não era a 1ª real do torneio | Recorrer ao TM completo via re-import; `upsert_tournament_meta` lê 1ª hand cronológica |
| `mm='v2'` mas `anon_map` vazio | Regressão do enrich SS↔HH em que `match_method='v2'` era gravado com `anon_map` vazio (resolvida em pt10 — ver INVENTARIO #B32) | Confirmar deploy; ler `screenshot.py:_enrich_hand_from_orphan_entry` |
| Villains zero em hand canal `nota` com match | Regressão do regex TM em que Vision sem prefixo literal `TM` produzia `tm=NULL` (resolvida em pt12 — ver INVENTARIO #B33) | Confirmar deploy; `screenshot.py:307` deve usar regex `\b(\d{8,12})\b` |
| `discord_tags` perdidos em substituição placeholder→matched | Helper centralizado para propagação de canais Discord não correu (resolvido em pt9 — ver INVENTARIO #B12) | `services/hand_service.py:append_discord_channel_to_hand` é a única fonte canónica de propagação |

---

## Pipeline 3 — Discord sync

### Descrição

Bot Discord ligado em modo manual (`DISCORD_AUTO_SYNC=false` em produção). Utilizador carrega "Sincronizar" na página `/discord`; UI mostra painel inline com janelas pré-definidas (24h/72h/sem/15d/mês) e custom (De/Até). Backend faz `POST /api/discord/sync-and-process` com body `{window?, from?, to?}`. Bot puxa `channel.history` respeitando precedência de cursor (snowflake > datetime > `APP_EPOCH_CUTOFF=1 Jan 2026 Lisbon`). Para cada mensagem cria entries `source='discord'` com `entry_type` em `{hand_history, replayer_link, image}`. Replayer-links disparam Vision em background; SSs sem HH ainda viram placeholders em `hands` (`origin='discord'`, `match_method='discord_placeholder_no_hh'`, `hm3_tags=['GGDiscord']`). Quando HH chegar (Pipeline 2), `_insert_hand` apaga o placeholder e insere a HH real preservando metadados.

### Pré-condições

- Bot Discord ligado e subscrito aos canais (`DISCORD_BOT_TOKEN` válido).
- `DISCORD_AUTO_SYNC=false` em prod (regra de negócio Rui).
- Pré-condições partilhadas cumpridas.

### Etapa A — Limpeza opcional

```sql
-- Identificar entries Discord do dia em teste:
SELECT id, discord_channel, discord_posted_at, entry_type
FROM entries
WHERE source = 'discord' AND discord_posted_at >= '<data>'
ORDER BY id;

-- Apagar (FK ON DELETE CASCADE em hand_attachments via entry_id):
DELETE FROM hands WHERE entry_id IN (<lista entries>);
DELETE FROM entries WHERE id IN (<lista entries>);

-- Reset cursores se quiseres re-sync limpo:
UPDATE discord_sync_state
SET last_message_id = NULL, last_sync_at = NULL, messages_synced = 0;
```

### Etapa B — Sincronizar (janela escolhida + cutoff 2026)

UI: chip pré-definido (ex: 24h) ou painel custom. Botão de envio dispara `POST /api/discord/sync-and-process`. Body opcional:

```json
{"window": "24h"}
{"from": "2026-05-01T00:00:00Z", "to": "2026-05-04T23:59:59Z"}
```

Cutoff `APP_EPOCH_CUTOFF=1 Jan 2026 Lisbon` é hardcoded e prevalece silenciosamente — `from` antes do cutoff é clampado.

### Etapa C — Validar Fase 1 (entries + placeholders)

```sql
-- Q3.1 entries Discord recentes
SELECT id, entry_type, discord_channel, discord_posted_at, status,
       raw_json->>'tm' AS tm,
       (raw_json->>'vision_done')::boolean AS vd,
       raw_json->>'hero' AS hero
FROM entries
WHERE source = 'discord' AND created_at >= NOW() - INTERVAL '15 minutes'
ORDER BY created_at DESC
LIMIT 50;

-- Q3.2 placeholders Discord criados (via _create_placeholder_if_needed + backfill_ggdiscord)
SELECT h.id, h.hand_id, h.origin, h.hm3_tags, h.discord_tags,
       (h.player_names ->> 'match_method') AS mm
FROM hands h
WHERE h.origin = 'discord' AND h.created_at >= NOW() - INTERVAL '15 minutes'
ORDER BY h.created_at DESC
LIMIT 30;

-- Q3.3 cutoff 2026 respeitado (zero entries pré-cutoff)
SELECT COUNT(*) AS pre_cutoff
FROM entries
WHERE source = 'discord' AND discord_posted_at < '2026-01-01 00:00:00+00'
  AND created_at >= NOW() - INTERVAL '15 minutes';
-- Esperado: 0. Bot ignora mensagens pré-cutoff (regra dura, fix #B7 pt8).
```

**Esperado:** Q3.1 entries com `vd=true` e `tm` populado para `replayer_link`; Q3.2 placeholders com `hm3_tags=['GGDiscord']` e `mm='discord_placeholder_no_hh'`; Q3.3 = 0.

### Etapa D — Cross-post 2 canais (append `discord_tags`)

```sql
-- Q3.4 TMs com 2+ entries Discord (cross-post real)
SELECT raw_json->>'tm' AS tm, COUNT(*) AS n_entries,
       array_agg(DISTINCT discord_channel) AS channels
FROM entries
WHERE source = 'discord' AND raw_json->>'tm' IS NOT NULL
  AND created_at >= NOW() - INTERVAL '15 minutes'
GROUP BY raw_json->>'tm'
HAVING COUNT(*) >= 2;

-- Q3.5 hand correspondente tem todos os canais em discord_tags (R4 — não perde canais)
WITH cross_tms AS (
  SELECT raw_json->>'tm' AS tm,
         COUNT(*) AS n_entries,
         array_agg(DISTINCT discord_channel) AS channels
  FROM entries
  WHERE source = 'discord' AND raw_json->>'tm' IS NOT NULL
    AND created_at >= NOW() - INTERVAL '15 minutes'
  GROUP BY raw_json->>'tm'
  HAVING COUNT(*) >= 2
)
SELECT h.hand_id, h.discord_tags, h.origin,
       cardinality(COALESCE(h.discord_tags, '{}'::text[])) AS n_discord_tags,
       cross_tms.n_entries AS n_entries_discord
FROM cross_tms
JOIN hands h ON h.hand_id = 'GG-' || cross_tms.tm
ORDER BY h.hand_id;
-- Esperado: para cada TM cross-postado em N canais, cardinality(discord_tags) >= N
-- (helper append_discord_channel_to_hand #B12 garante propagação).
```

### Etapa E — Match retroactivo HH→Discord (`apply_villain_rules` + Regra C)

Quando HH chega depois (Pipeline 2 ou 4), `_insert_hand` substitui placeholder por hand real e dispara `apply_villain_rules`. Regra C: `'nota' ∈ discord_tags AND match_method` real → category=`'nota'`.

```sql
-- Q3.6 hands ex-Discord agora matched (mm='v2'), preservando discord_tags
SELECT h.hand_id, (h.player_names ->> 'match_method') AS mm,
       h.discord_tags, h.origin,
       (h.raw IS NOT NULL AND h.raw <> '') AS has_raw
FROM hands h
WHERE h.discord_tags && ARRAY['nota','icm','pos-pko','icm-pko','pos','speed-racer']
  AND h.created_at >= NOW() - INTERVAL '30 minutes'
ORDER BY h.hand_id;

-- Q3.7 Regra C disparou para canais 'nota' com match real
SELECT h.hand_id, h.discord_tags, hv.player_name, hv.category
FROM hands h
JOIN hand_villains hv ON hv.hand_db_id = h.id
WHERE 'nota' = ANY(h.discord_tags)
  AND (h.player_names ->> 'match_method') IS NOT NULL
  AND (h.player_names ->> 'match_method') NOT LIKE 'discord_placeholder_%'
  AND h.created_at >= NOW() - INTERVAL '30 minutes';
-- Esperado: ≥1 row por hand canal nota com match. category='nota'.

-- Q3.8 invariante GG anon (princípio invariante): zero villains em hands sem match
SELECT COUNT(*) AS bad_villains
FROM hand_villains hv
JOIN hands h ON h.id = hv.hand_db_id
WHERE h.site = 'GGPoker'
  AND ((h.player_names ->> 'match_method') IS NULL
       OR (h.player_names ->> 'match_method') LIKE 'discord_placeholder_%')
  AND h.played_at >= '2026-01-01';
-- Esperado: 0. Princípio invariante (REGRAS_NEGOCIO.md §3.3 + MAPA §2.1 armadilhas).
```

### Critério de sucesso Pipeline 3

- Q3.1-Q3.3: entries criadas com `vision_done=true`; placeholders correctos; cutoff 2026 respeitado.
- Q3.4-Q3.5: cross-post propagou todos os canais em `discord_tags`.
- Q3.6-Q3.8: enrich retroactivo dispara; Regra C correcta; princípio invariante GG anon = 0.
- UI: página Discord mostra novas entries agrupadas por canal; Estudo "Por Tags" agrega tags HM3 + Discord por nome normalizado (1 chip por nome, `OriginBadge=Discord` ou `HM3+D`).

### Troubleshooting Pipeline 3

| Sintoma | Causa provável | Verificar |
|---|---|---|
| Bot varre toda a história em vez de respeitar cutoff | `last_message_id` NULL e `last_sync_at` ignorado pelo cursor (resolvido em pt8 — ver INVENTARIO #B7); precedência (a) snowflake > (b) datetime > (c) `APP_EPOCH_CUTOFF` deve estar deployed | `discord.py:_get_sync_cursor` |
| Cross-post não popula `discord_tags` na 2ª entry | Helper centralizado para propagação de canais Discord não correu (resolvido em pt9 — ver INVENTARIO #B12) | Confirmar `services/hand_service.py:append_discord_channel_to_hand` no path de ingestão de entries |
| Contadores `n_links/m_canais/k_match_hh` desalinhados com lista de mãos | Contadores medem entries criadas, não trabalho útil (tech debt aberto — ver INVENTARIO #B13). Decisão pt13: manter como está | Documento, não bloqueia |
| Entry `replayer_link` com `tm=NULL` | Vision omitiu prefixo `TM` antes do regex word-boundary; ou Vision falhou (regex tolerante introduzido em pt12 — ver INVENTARIO #B33) | Verificar `screenshot.py:307` deve usar regex `\b(\d{8,12})\b` |
| Villains zero em hands canal `nota` GG anon (sem match) | Comportamento correcto. Princípio invariante: nunca criar villain em GG anon | Validar com Q3.8 |
| `apa` só com `_meta` em enrich | Estado degenerado em que `_build_anon_to_real_map` recebia apa só com `_meta` (assert defensivo introduzido em pt13 — ver INVENTARIO #B-NOVO-2) | Logs Railway buscar `ValueError` em `_enrich_hand_from_orphan_entry` |

---

## Pipeline 4 — Upload manual SS

### Descrição

Drag-and-drop de screenshots GG na UI. `POST /api/screenshots` cria entries `source='screenshot'`, `entry_type='screenshot'`, parse de filename (data/hora/blinds/TM determinístico — fonte de verdade para esses campos). Vision processa em background, extrai seats e identifica Hero. Se há HH em BD para `GG-{TM}`, enriquece via `_enrich_hand_from_orphan_entry` e dispara `apply_villain_rules`. Se não, cria placeholder com `origin='ss_upload'`, `tags=['SSMatch']`, `match_method='discord_placeholder_no_hh'`, à espera de HH. Aparece no painel SSMatch do Dashboard via `GET /api/hands/ss-match-pending`.

### Pré-condições

- SSs com TM extraível (ex: nome `2026-03-31_10-17_PM_$10_$20_#5775900015.png` ou TM extraível por Vision do header da imagem).
- `FRIEND_HEROES` actualizado se hero da SS é Karluz/flightrisk (não Rui).
- Pré-condições partilhadas cumpridas.

### Etapa A — Limpeza opcional

```sql
-- Entries SS do hero em teste:
SELECT id, file_name FROM entries
WHERE source = 'screenshot' AND raw_json->>'hero' IN ('Karluz','karluz','lauro dermio')
  AND created_at >= '<data>'
ORDER BY id;

-- Hands ss_upload do mesmo período:
SELECT id, hand_id FROM hands
WHERE origin = 'ss_upload' AND created_at >= '<data>';

-- Apagar:
DELETE FROM hands WHERE id IN (<lista hands>);
DELETE FROM entries WHERE id IN (<lista entries>);
```

### Etapa B — Drag-and-drop SSs

1. Abrir app → "+ Importar".
2. Drag-and-drop das N SSs.
3. Aguardar Vision (~60s, depende do número).

### Etapa C — Validar Fase 1 (entry + placeholder ss_upload)

```sql
-- Q4.1 entries criadas com Vision concluído
SELECT id, file_name, status,
       raw_json->>'tm' AS tm,
       (raw_json->>'vision_done')::boolean AS vd,
       raw_json->>'hero' AS hero,
       jsonb_array_length(COALESCE(raw_json->'players_list', '[]'::jsonb)) AS n_players
FROM entries
WHERE source = 'screenshot' AND created_at >= NOW() - INTERVAL '15 minutes'
ORDER BY created_at DESC;

-- Q4.2 placeholders ss_upload (matched=NO, à espera HH)
SELECT h.id, h.hand_id, h.origin, h.tags, h.hm3_tags,
       (h.player_names ->> 'match_method') AS mm
FROM hands h
WHERE h.origin = 'ss_upload' AND h.created_at >= NOW() - INTERVAL '15 minutes'
ORDER BY h.created_at DESC;

-- Q4.3 painel SSMatch counter
SELECT COUNT(*) AS ss_match_pending
FROM hands
WHERE origin = 'ss_upload'
  AND (player_names ->> 'match_method') = 'discord_placeholder_no_hh';
```

**Esperado:** Q4.1 entries com `vd=true`, `tm` preenchido, `n_players > 0`, `status='resolved'`; Q4.2 hands com `tags=['SSMatch']`, `mm='discord_placeholder_no_hh'`; Q4.3 valor sobe N (ou estabiliza se já há hands matched a entrar).

### Etapa D — Import HH (substituição placeholder → matched)

1. Abrir app → "+ Importar".
2. Drag-and-drop do ZIP com as HHs correspondentes.
3. Aguardar response.

### Etapa E — Validar Fase 2 (`anchors_stack_v2` + vilões A∨C∨D)

```sql
-- Q4.4 estado pós-substituição: matched (mm='v2', has_raw) ou placeholder (ainda no_hh)
SELECT h.id, h.hand_id, h.origin, h.tags,
       h.played_at, h.tournament_name, h.position, h.result, h.hero_cards,
       (h.player_names ->> 'match_method') AS mm,
       (h.raw IS NOT NULL AND h.raw <> '') AS has_raw
FROM hands h
WHERE h.hand_id IN ('GG-<TM1>','GG-<TM2>','GG-<TM3>')
ORDER BY h.hand_id;

-- Q4.5 hashes resolvidos (zero hashes em apa pós-enrich)
SELECT h.hand_id,
       (SELECT array_agg(k) FROM jsonb_object_keys(h.all_players_actions) k
        WHERE k != '_meta' AND k ~ '^[0-9a-f]{8}$') AS hashes_remaining
FROM hands h
WHERE h.hand_id IN ('GG-<TM1>','GG-<TM2>','GG-<TM3>');
-- Esperado: hashes_remaining = NULL (zero hashes restantes).

-- Q4.6 anon_map populado quando mm='v2' (#B32 guard)
SELECT h.hand_id,
       jsonb_typeof(h.player_names -> 'anon_map') AS anon_type,
       (h.player_names -> 'anon_map') IS NOT NULL AS has_anon
FROM hands h
WHERE h.hand_id IN ('GG-<TM1>','GG-<TM2>','GG-<TM3>')
  AND (h.player_names ->> 'match_method') = 'anchors_stack_elimination_v2';
-- Esperado: anon_type='object' (não null), has_anon=true.

-- Q4.7 vilões criados via apply_villain_rules (A∨C∨D, vilão principal por street máxima)
SELECT h.hand_id, hv.player_name, hv.category
FROM hands h
JOIN hand_villains hv ON hv.hand_db_id = h.id
WHERE h.hand_id IN ('GG-<TM1>','GG-<TM2>','GG-<TM3>')
ORDER BY h.hand_id, hv.player_name;
-- Esperado: vilões só por A (hm3_tags nota%), C (discord_tags nota), ou D (FRIEND_HEROES). Nunca B (showdown sozinho — eliminado em #B8).

-- Q4.8 vilão principal: nenhum candidate filtrado tem street > principais (sanity)
-- Verificação semantica (não trivial via SQL puro). Manual: na hand com 2+ pré-vilões,
-- confirmar via UI Vilões que o(s) com estrelinha são quem chegou mais longe.
```

### Critério de sucesso Pipeline 4

- Q4.1-Q4.3: entries SSs uploaded com Vision feito; placeholders criados; counter SSMatch sobe.
- Q4.4-Q4.6: pós-import HH, hands ex-placeholder ganham `mm='anchors_stack_v2'`, `has_raw=true`, hashes zero, `anon_map` populado.
- Q4.7-Q4.8: vilões criados respeitam A∨C∨D estritos (sem regra B); vilão principal correcto por street máxima.
- UI: Dashboard SSMatch counter desce; HandDetailPage de hand matched mostra detalhe completo (não PlaceholderView); hand visível em Estudo (se `has_raw=true` + tags) e Vilões (se A∨C∨D).

### Troubleshooting Pipeline 4

| Sintoma | Causa provável | Verificar |
|---|---|---|
| `hero` ≠ esperado | hero não está em `HERO_NAMES` nem `FRIEND_HEROES` | `backend/app/hero_names.py` |
| `vision_done=false` 5min depois | Vision API timeout/erro | Logs Railway; retry |
| Match não acontece após import HH | `_insert_hand` placeholder upgrade não correu | Confirmar `services/hand_service.py:_insert_hand` |
| Hashes não substituídos pós-enrich | `_build_anon_to_real_map` falhou; ou `apa` só tinha `_meta` no momento da chamada (assert defensivo introduzido em pt13 — ver INVENTARIO #B-NOVO-2) | Logs Railway buscar `ValueError` em `_enrich_hand_from_orphan_entry` |
| `mm='v2'` mas `anon_map` vazio | Regressão do enrich SS↔HH em que `match_method='v2'` era gravado com `anon_map` vazio (resolvida em pt10 — ver INVENTARIO #B32) | Confirmar deploy de `screenshot.py:_enrich_hand_from_orphan_entry` |
| Zero villains após match em mão com tag `nota%` | Race condition em criação de vilões via conexões cruzadas (resolvida em pt9 — ver INVENTARIO #B23) ou `apply_villain_rules` skipped | Logs Railway buscar `apply_villain_rules:`; `services/villain_rules.py:apply_villain_rules` é a única fonte canónica |
| Stack matching falha em micro-stacks | Tolerância rígida 2.0% em micro-stacks (resolvida em pt7 com tolerância dinâmica `max(20, 2%)` — ver INVENTARIO #B1) | Confirmar deploy de `screenshot.py` |

---

## Pipeline 5 — Galeria manual de imagens

### Descrição

Imagens directas Discord (anexos `.png`/`.jpg`/`.webp` + links Gyazo) são **contexto de mãos, não mãos por si** (regra de produto em `CLAUDE.md` "Imagens de contexto Discord"). Entram via Pipeline 3 como entries `source='discord' entry_type='image'` e ficam órfãs até o utilizador as anexar manualmente a uma mão via galeria. O Bucket 1 automático (match temporal ±90s + canal) foi substituído por anexação manual em pt7 (#B9, commits `f98f8c8`→`cc2161c`) porque falhava sistematicamente quando o Rui joga múltiplos torneios em paralelo. O endpoint do worker antigo (`run_match_worker`) ainda corre em triggers retroactivos mas é hoje redundante face à galeria manual; o utilizador anexa explicitamente cada imagem à mão correcta.

### Pré-condições

- Pelo menos 1 entry com `source='discord' AND entry_type='image'` em BD (proveniente de Pipeline 3).
- Hand alvo já existe em `hands`.
- Pré-condições partilhadas cumpridas.

### Etapa A — Listagem de imagens órfãs

UI: página `/discord` → tag `#imagens` → ver lista paginada. Endpoint correspondente:

```
GET /api/images/gallery?channel=<nome>&date=YYYY-MM-DD&page=1&page_size=40
```

Devolve items com `entry_id`, `image_url`, `channel_name`, `posted_at`, `author`, `discord_message_url`, e `attached_to[]` (mãos a que cada imagem já está anexada).

```sql
-- Q5.1 entries image órfãs (sem row em hand_attachments)
SELECT e.id AS entry_id, e.discord_channel, d.channel_name,
       e.discord_posted_at AS posted_at, e.discord_author AS author
FROM entries e
LEFT JOIN discord_sync_state d ON d.channel_id = e.discord_channel
WHERE e.source = 'discord' AND e.entry_type = 'image'
  AND e.id NOT IN (SELECT entry_id FROM hand_attachments WHERE entry_id IS NOT NULL)
ORDER BY e.discord_posted_at DESC NULLS LAST
LIMIT 40;
```

### Etapa B — Operação anexar imagem a mão

UI: na galeria, escolher imagem → escolher hand alvo (selector com filtro por TM/data/canal) → confirmar. Endpoint:

```
POST /api/hands/{hand_db_id}/images
Body: {"entry_id": <int>}
```

Cria row em `hand_attachments` com `match_method='manual'`, `delta_seconds=NULL`. Para Gyazo URLs, faz fetch e cacheia bytes em `img_b64` (link rot defesa).

Validações backend:
- `hand_db_id` existe.
- `entry_id` existe E `entry_type='image'`.
- Não há row pré-existente `(hand_db_id, entry_id)` (UNIQUE parcial impede duplicação).

### Etapa C — Operação remover anexo

UI: HandDetailPage / modal de mão → secção CONTEXTO → `×` no thumbnail. Endpoint:

```
DELETE /api/hands/{hand_db_id}/images/{ha_id}
```

Apaga row em `hand_attachments`. Entry image preservada (`ON DELETE SET NULL` em `entry_id`).

### Etapa D — Validar BD pós-anexo

```sql
-- Q5.2 row criada com match_method='manual'
SELECT id AS ha_id, hand_db_id, entry_id, channel_name, posted_at,
       match_method, delta_seconds,
       img_b64 IS NOT NULL AS has_b64, mime_type
FROM hand_attachments
WHERE entry_id = <entry_id_anexada>;
-- Esperado: 1 row, match_method='manual', delta_seconds=NULL.

-- Q5.3 lista anexos de uma mão
SELECT ha.id AS ha_id, ha.entry_id, ha.channel_name, ha.posted_at,
       ha.match_method, ha.img_b64 IS NOT NULL AS has_b64
FROM hand_attachments ha
WHERE ha.hand_db_id = <hand_db_id>
ORDER BY ha.posted_at DESC NULLS LAST;

-- Q5.4 detach: row apagada mas entry preservada
SELECT
  (SELECT COUNT(*) FROM hand_attachments WHERE id = <ha_id>) AS ha_remaining,
  (SELECT COUNT(*) FROM entries WHERE id = <entry_id>) AS entry_remaining;
-- Esperado: ha_remaining=0, entry_remaining=1.

-- Q5.5 invariante: imagens NUNCA criam mãos
SELECT COUNT(*) FROM hands h
WHERE EXISTS (
  SELECT 1 FROM entries e
  WHERE e.id = h.entry_id AND e.entry_type = 'image'
);
-- Esperado: 0. Regra de produto (CLAUDE.md "Imagens de contexto Discord").
-- Promoção desta regra para REGRAS_NEGOCIO.md §6 está registada como Tech Debt N3.
```

### Critério de sucesso Pipeline 5

- Q5.1: entries image visíveis na galeria, paginação funcional.
- Q5.2: anexação cria row com `match_method='manual'`.
- Q5.3: HandDetailPage / `HandRow` mostra ícone `📎 N` + thumbnail 200px na secção CONTEXTO.
- Q5.4: detach apaga row mas preserva entry image.
- Q5.5: zero `hands` criadas a partir de `entry_type='image'`.

### Troubleshooting Pipeline 5

| Sintoma | Causa provável | Verificar |
|---|---|---|
| `img_b64` NULL em row Gyazo | `_fetch_entry_image_bytes` engole erro silenciosamente; HEAD a `i.gyazo.com/<id>.png` falhou | Logs Railway buscar `image fetch:` warnings; UI cai em fallback `image_url`. |
| `channel_name` mostra ID numérico em vez de nome | `discord_sync_state.channel_name` não populado para esse canal | Re-sync Discord; fallback cosmético. |
| Anexo "duplicado" rejeitado com 409 | UNIQUE parcial `(hand_db_id, entry_id) WHERE entry_id IS NOT NULL` | Comportamento esperado: 1 imagem por mão única. |
| `entries.status='attached'` esperado mas não muda | **Comportamento correcto.** Worker NÃO escreve `entries.status`. Estado "anexada" representa-se via `EXISTS row em hand_attachments` | MAPA §2.11 Armadilha 4. Validar via `EXISTS`, NUNCA via `entries.status`. |
| Bucket 1 automático ainda dispara matches | `run_match_worker` continua activo via triggers em `discord.py`/`hm3.py`/`import_.py`; resultados são redundantes mas não conflituantes com galeria manual | Decisão pt7 #B9: aceitar, não desactivar. |

---

## Validações cross-cutting

Correr depois de qualquer pipeline para detectar regressões nas regras duras (ver `docs/REGRAS_NEGOCIO.md §6`).

### X1. Estudo respeita as 4 regras duras

```sql
-- X1.1 R1: zero hands GG sem match_method real em Estudo
SELECT COUNT(*) FROM hands h
WHERE h.played_at >= '2026-01-01'
  AND h.site = 'GGPoker'
  AND h.study_state IN ('new', 'resolved')
  AND ((h.player_names ->> 'match_method') IS NULL
       OR (h.player_names ->> 'match_method') LIKE 'discord_placeholder_%');
-- Esperado: 0.

-- X1.2 R3: zero hands sem HH em Estudo
SELECT COUNT(*) FROM hands h
WHERE h.played_at >= '2026-01-01'
  AND h.study_state IN ('new', 'resolved')
  AND (h.raw IS NULL OR h.raw = '');
-- Esperado: 0.

-- X1.3 R2: zero hands só com tag 'nota' em Estudo
SELECT COUNT(*) FROM hands h
WHERE h.played_at >= '2026-01-01'
  AND h.study_state IN ('new', 'resolved')
  AND NOT EXISTS (
    SELECT 1 FROM unnest(COALESCE(h.hm3_tags, '{}')) t WHERE t NOT ILIKE 'nota%'
  )
  AND NOT EXISTS (
    SELECT 1 FROM unnest(COALESCE(h.discord_tags, '{}')) t WHERE t != 'nota'
  );
-- Esperado: 0. Mãos com 'nota' + outra tag não são apanhadas por esta query
-- (têm tag de estudo válida).

-- X1.4 R12: queries do playbook respeitam played_at >= 2026 (verificação self-test)
-- Confirmar que a totalidade de SQL usado neste playbook contém este filtro
-- onde aplicável.
```

### X2. Vilões — `apply_villain_rules` única fonte; A∨C∨D estrita; vilão principal

```sql
-- X2.1 distribuição por category em hand_villains
SELECT category, COUNT(*) FROM hand_villains hv
JOIN hands h ON h.id = hv.hand_db_id
WHERE h.played_at >= '2026-01-01'
GROUP BY category
ORDER BY category;
-- Esperado: 'nota' e 'friend' presentes; 'sd' = histórico ou zero (regra B eliminada em #B8 pt7).

-- X2.2 vilão principal: hands com 2+ candidates devem ter villains coerentes
-- (Sanity manual via UI Vilões: hand com 2 villains pré-filtragem deve mostrar
--  só quem chegou mais longe na mão ou empate na street máxima.)

-- X2.3 princípio invariante GG anonimizada: zero villains
SELECT COUNT(*) FROM hand_villains hv
JOIN hands h ON h.id = hv.hand_db_id
WHERE h.site = 'GGPoker'
  AND ((h.player_names ->> 'match_method') IS NULL
       OR (h.player_names ->> 'match_method') LIKE 'discord_placeholder_%')
  AND h.played_at >= '2026-01-01';
-- Esperado: 0. Aplica-se às 3 regras (REGRAS_NEGOCIO.md §3.3 + MAPA §2.1 armadilhas).
```

### X3. Cross-post Discord não perdeu canais (R4)

```sql
-- X3.1 hands com 2+ canais Discord
SELECT hand_id, discord_tags, origin, (player_names ->> 'match_method') AS mm
FROM hands
WHERE played_at >= '2026-01-01'
  AND cardinality(COALESCE(discord_tags, '{}'::text[])) >= 2
ORDER BY hand_id DESC LIMIT 30;

-- X3.2 sanity TMs com 2+ entries Discord vs cardinality(discord_tags) >= 2
WITH cross_tms AS (
  SELECT raw_json->>'tm' AS tm, COUNT(*) AS n_entries
  FROM entries
  WHERE source = 'discord' AND raw_json->>'tm' IS NOT NULL
  GROUP BY raw_json->>'tm'
  HAVING COUNT(*) >= 2
)
SELECT 'GG-' || tm AS hand_id_expected, n_entries
FROM cross_tms
LEFT JOIN hands h ON h.hand_id = 'GG-' || cross_tms.tm
WHERE h.id IS NULL OR cardinality(COALESCE(h.discord_tags, '{}'::text[])) < 2;
-- Esperado: zero rows (todos os cross-posts reflectidos em discord_tags).
```

### X4. Dashboard counters coerentes

```sql
-- X4.1 study_breakdown (novo pt13)
-- GET /api/hands/stats — confirmar shape:
--   {"study_breakdown": {
--      "total": <int>,                       -- = result.new
--      "tags": [{"display_name": "...", "count": int}, ...],  -- top 3
--      "sites": {"GGPoker": int, "PokerStars": int, "Winamax": int, "WPN": int}
--   }, ...}

-- X4.2 ss_match_pending counter (Pipeline 4)
SELECT COUNT(*) FROM hands
WHERE origin = 'ss_upload'
  AND (player_names ->> 'match_method') = 'discord_placeholder_no_hh';
-- Comparar com card SSMatch do Dashboard.

-- X4.3 GG Discord placeholders (Pipeline 3)
SELECT COUNT(*) FROM hands
WHERE 'GGDiscord' = ANY(hm3_tags);
```

### X5. Health checks gerais

```sql
-- X5.1 distribuição mãos por origin (2026)
SELECT origin, COUNT(*) AS n
FROM hands
WHERE played_at >= '2026-01-01'
GROUP BY origin
ORDER BY origin;

-- X5.2 distribuição study_state (CHECK constraint pt13: only 3 valores)
SELECT study_state, COUNT(*) FROM hands
WHERE played_at >= '2026-01-01'
GROUP BY study_state;
-- Esperado: só 'new', 'resolved', 'mtt_archive'.

-- X5.3 entries por (source, entry_type)
SELECT source, entry_type, COUNT(*) FROM entries
GROUP BY source, entry_type
ORDER BY source, entry_type;

-- X5.4 hand_villains UNIQUE composto (hand_db_id, player_name, category) — sem duplicados
SELECT hand_db_id, player_name, category, COUNT(*)
FROM hand_villains
GROUP BY hand_db_id, player_name, category
HAVING COUNT(*) > 1;
-- Esperado: zero rows.

-- X5.5 villain_notes hands_seen sanity (não inflado pós-#B29 pt13)
SELECT COUNT(*) AS notes_total,
       COUNT(*) FILTER (WHERE hands_seen > 0) AS notes_active,
       SUM(hands_seen) AS sum_hands_seen
FROM villain_notes;
```

---

## Anexo — Queries de diagnóstico

Snapshot completo, útil ao começar uma sessão para perceber estado actual.

```sql
-- A1. Counts gerais BD (2026)
SELECT
  (SELECT COUNT(*) FROM hands WHERE played_at >= '2026-01-01') AS hands_2026,
  (SELECT COUNT(*) FROM entries WHERE created_at >= '2026-01-01') AS entries_2026,
  (SELECT COUNT(*) FROM hand_villains hv
    JOIN hands h ON h.id=hv.hand_db_id
    WHERE h.played_at >= '2026-01-01') AS hand_villains_2026,
  (SELECT COUNT(*) FROM villain_notes WHERE hands_seen > 0) AS villain_notes_active,
  (SELECT COUNT(*) FROM hand_attachments) AS hand_attachments_total,
  (SELECT COUNT(*) FROM tournaments_meta WHERE site='GGPoker') AS tournaments_meta_gg,
  (SELECT COUNT(*) FROM discord_sync_state) AS discord_channels;

-- A2. Snapshot Dashboard (todos os counters)
SELECT
  (SELECT COUNT(*) FROM hands WHERE 'GGDiscord' = ANY(hm3_tags)) AS gg_discord_placeholders,
  (SELECT COUNT(*) FROM hands WHERE origin='ss_upload'
    AND (player_names->>'match_method') = 'discord_placeholder_no_hh') AS ss_match_pending,
  (SELECT COUNT(*) FROM hands WHERE origin='ss_upload'
    AND (player_names->>'match_method') = 'anchors_stack_elimination_v2') AS ss_upload_matched;

-- A3. Health check enrichment SS↔HH
SELECT COUNT(*) FROM hands h
WHERE origin='ss_upload'
  AND (player_names->>'match_method') = 'anchors_stack_elimination_v2'
  AND NOT EXISTS (
    SELECT 1 FROM jsonb_object_keys(h.all_players_actions) k
    WHERE k != '_meta' AND k ~ '^[0-9a-f]{8}$'
  );
-- Esperado: igual a ss_upload_matched (zero hashes residuais pós-enrich).

-- A4. Hands enriched: anon_map populado quando mm='v2' (#B32 fix)
SELECT
  COUNT(*) FILTER (WHERE (player_names->>'match_method')='anchors_stack_elimination_v2')
    AS total_v2,
  COUNT(*) FILTER (WHERE (player_names->>'match_method')='anchors_stack_elimination_v2'
                     AND (player_names->'anon_map') IS NOT NULL
                     AND jsonb_typeof(player_names->'anon_map')='object')
    AS v2_with_anon_populated
FROM hands
WHERE site='GGPoker' AND played_at >= '2026-01-01';
-- Esperado: total_v2 = v2_with_anon_populated.
```

---

## Última validação ponta-a-ponta

**Data:** A preencher em pt14 Fase 3
**Sessão:** —
**Snapshot BD:** —
**Tag git:** —
**Operador:** Rui (visual) + Code (queries)

### Estado por pipeline

| Pipeline | Estado | Notas |
|---|---|---|
| 1. HM3 `.bat` | ❓ | — |
| 2. Import ZIP/TXT HH | ❓ | — |
| 3. Discord sync | ❓ | — |
| 4. Upload manual SS | ❓ | — |
| 5. Galeria manual de imagens | ❓ | — |

### Validações cross-cutting

| Validação | Estado | Notas |
|---|---|---|
| X1. Estudo respeita as 4 regras duras (R1/R2/R3/R12) | ❓ | — |
| X2. Vilões A∨C∨D estritos + vilão principal | ❓ | — |
| X3. Cross-post Discord preserva canais (R4) | ❓ | — |
| X4. Dashboard counters coerentes | ❓ | — |
| X5. Health checks gerais | ❓ | — |

### Counts BD

| Tabela | Valor |
|---|---|
| `hands` (2026) | — |
| `entries` (2026) | — |
| `hand_villains` (2026) | — |
| `villain_notes` (`hands_seen > 0`) | — |
| `hand_attachments` | — |
| `tournaments_meta` (GG) | — |
| `discord_sync_state` (canais activos) | — |

### Anomalias detectadas

(Lista vazia até preenchimento.)

### Decisão final

❓ A preencher.

---

**Legenda:** ✅ validado · ⚠️ parcial · ❌ falha · ❓ não corrido

---

## Manutenção deste documento

Mantém o playbook actualizado quando:
- Um pipeline novo for adicionado.
- Um pipeline existente mudar comportamento canónico (parser, enrich, criação de vilões, schema).
- Uma regra dura nova for promovida em `docs/REGRAS_NEGOCIO.md §6`.

Sempre que correres um ciclo completo, actualiza a secção "Última validação ponta-a-ponta" com data, snapshot BD, tag git, e estado de cada pipeline + cross-cutting. Se detectaste uma anomalia que não bloqueia validação mas merece atenção, regista-a na secção "Anomalias detectadas" com link para journal/INVENTARIO.

Cada commit/fix mencionado neste documento deve ter hash hard-link verificado contra `git log` na sessão em que for adicionado.
