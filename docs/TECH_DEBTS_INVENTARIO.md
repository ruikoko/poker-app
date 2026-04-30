# Inventário Tech Debts — 30-Abr 2026 pt8 (fechada)

Compilação read-only baseada em journals (23-24 Abr → 29-Abr pt6), VALIDACAO_END_TO_END §6/§7/§11, MAPA_ACOPLAMENTO, git log, e leitura directa do código.

Substitui os fragmentos espalhados pelos vários docs como **single source of truth** sobre tech debts pendentes. Para descrição detalhada de cada fix fechado, consultar journal/commit correspondente.

---

## Estado actual (30-Abr fim pt8)

- **Total Tech Debts numerados detectados:** 25 (#1–#22, sem #19; +#UX1; +#B12 pt8; +#B13 pt8)
- **Fechados pt8:** 3 (#18 validado empiricamente, #15 fix Dashboard, #B7 cursor Discord)
- **Fechados pt7:** 9 (#10, #21, #B1, #B2, #B4, #B8, #B9, #12, #UX1) + 17 anteriores = **29 totais fechados** (incl. #18+#15+#B7 pt8)
- **Pendentes numerados:** #11, #13c, #B10, #B11, #B12, #B13, #B-edge
- **Bugs latentes não-numerados detectados em pt7:** 4 (registados §3 abaixo)
- **Feature nova pt8:** sincronização Discord manual com janelas (24h/72h/1sem/15d/1mês/custom) — substitui botão "Sincronizar Agora"

### Sumário pt7 (9 Tech Debts fechados)

| # | Hash(es) | Descrição |
|---|---|---|
| **#21** ✅ | `d61a241` | Idempotência `_enrich_hand_from_orphan_entry` |
| **#10** ✅ | `e74df0c` | Parser HM3 nicks com espaço (regex universal seat_nicks) |
| **#B1** ✅ | `c90b1b9` | Stack matching tolerância dinâmica `max(20, 2%)` |
| **#B2** ✅ | `0c0a1d3` | Anchor SB/BB via `difflib.SequenceMatcher` ratio≥0.85 |
| **#B4** ✅ | `82afcd7` | Phase 3 elimination brute-force optimal assignment |
| **#B8** ✅ | `ce56d59` | Regra B (auto-create cat='sd' showdown) removida + cleanup BD |
| **#B9** ✅ | `f98f8c8`→`cc2161c` (6 commits) | Bucket 1 automático → galeria manual de imagens |
| **#12** ✅ | `8871d1b`→`3c7dc13` (7 commits) | Refactor modal villain (layout, alinhamento, cores per-acção) |
| **#UX1** ✅ | (incluído `#12`) | Cards villain mostradas (não Hero) — fix bug pt6 |

### Tech Debts fechados pt8 (3 total)

| # | Hash | Data | Validação | Descrição |
|---|---|---|---|---|
| **#18** ✅ | (docs only) | 2026-04-30 | Empírica BD prod | Não-determinismo cross-post resolvido estruturalmente pelo guard #21. 1 hand cross-post real (1115) com APA coerente, 23 hands enriched protegidas pelo guard, 0 divergências. Sem fix de código necessário. |
| **#15** ✅ | `8919840` | 2026-04-30 | Visual frontend | Dashboard "Últimas mãos" passa a mostrar created_at (data import) + linha secundária "jogada DD Mmm" só quando played_at é dia diferente. Backend já ordenava por created_at desde 16-Abr; fix foi à apresentação. |
| **#B7** ✅ | `9d57b2b` | 2026-04-30 | Code + audit | `_get_sync_cursor` devolve `(last_message_id, last_sync_at)`; precedência (a) snowflake > (b) datetime > (c) APP_EPOCH_CUTOFF (1 Jan 2026 Lisbon hardcoded). Fix afecta `/sync` e `/sync-and-process`. |

### Feature nova pt8

| Hash | Descrição |
|---|---|
| `7ad41d4` | UI Discord painel inline com chips de janela (24h/72h/1sem/15d/1mês) + custom (De/Até). Endpoint POST `/api/discord/sync-and-process` aceita body opcional `{window?, from?, to?}`. Override de `discord_sync_state` antes do sync (`last_message_id=NULL, last_sync_at=from_clamped, messages_synced=0`) — usa precedência (b) do #B7. Response ganha `last_sync` com {window_label, from, to, n_links, m_canais, k_match_hh}. Banner "⟳ A sincronizar..." durante sync; sub-linha "Última sync: agora · janela X · N · M · K" persistente após. |

### Tech Debts pendentes para sessão pt9 (ordem prioridade)

| ID | Título | Severidade | Esforço |
|---|---|---|---|
| **#B12** | Hands GG anonimizadas com cross-post Discord não recebem `discord_tags` populado | 🟡 Funcional menor | ~1h investigação |
| **#B13** | Contadores `last_sync` (N/M/K) medem entries criadas em vez de trabalho útil | 🟢 UX | ~1h |
| **#11** | Botão eliminar villain manualmente do modal HandDetailPage | 🟡 UX | ~2-3h |
| **#B11** | Auto-tag mãos via LLM (ideia exploratória pt7) | 🟢 Feature | ~3-4h |
| **#B10** | Vision não extrai `tournament_name` da imagem na galeria | 🟢 UX | ~2-3h |
| **#B-edge** | Hero detection seat não-central (1/23 = 4.3% taxa) | 🟢 Edge case | ~30 min |
| **#13c** | Housekeeping aliases SITE_COLORS legacy | 🟢 Housekeeping | ~10-15 min |

#### Tech Debts pré-existentes mantidos (não atacados pt7)

| ID | Título | Severidade | Notas |
|---|---|---|---|
| **#22** | (consolidado em fixes #B1+#B2+#B4 — ver §3 abaixo) | — | Considera-se dissolvido nos fixes preventivos pt7 (validado 117/117 + 32/32 OK FASE 2) |
| **#13c** | Housekeeping aliases legacy SITE_COLORS | 🟢 | (idem cima) |

---

## §2. Bugs latentes detectados nesta auditoria pt7 (read-only código)

Identificados por leitura directa do código + cross-check com docs. **Não documentados em journals anteriores** — registo aqui para decisão Rui sobre numeração formal.

### #B1 — Stack matching tolerância rígida 2.0% em micro-stacks
- **File:** `screenshot.py:637-639`
- **Vector:** `if pct < 2.0 and diff < best_diff` — para stack_esperado=51 chips, 2% = 1.02 chip; diff inteiro de 2 já reprova. Stacks deep (>10k) nunca falham; stacks <500 falham frequentemente (false negatives).
- **Severidade:** Funcional (perde fold matches em micro-stacks; cai em Fase 3 elimination que é menos fiável).
- **Fix proposto:** `pct < 2.0 OR diff <= 2` (absoluto) — mantém deep stack tight, relaxa micro.
- **Esforço:** ~15 min + 1 backfill validação.

### #B2 — Hero/SB/BB matching frágil por `startswith(name[:6])`
- **File:** `screenshot.py:569, 582, 595`
- **Vector:** Quando 2 Vision nicks começam pelo mesmo prefixo de 6 chars ("Ander..."), o primeiro encontrado ganha. Sem Levenshtein, sem suffix check.
- **Severidade:** Funcional (false positive raro mas existe).
- **Fix proposto:** Levenshtein distance ≤2 vs vision_sb/bb completo, ou Jaro-Winkler.
- **Esforço:** ~30 min + biblioteca `python-Levenshtein` ou implementação ad-hoc.

### #B3 — Fallback silencioso quando vision_sb/bb=None
- **File:** `screenshot.py:586-588, 599-601`
- **Vector:** Se Vision falha em ler painel esquerdo, `vision_sb=None`. Branch `if player_key not in anon_map: anon_map[player_key] = vision_sb` insere `None` como nome. Downstream `_enrich_all_players_actions` trata como string vazia → APA com chave `None` ou `""`.
- **Severidade:** Funcional (silently broken APA quando Vision parcial).
- **Fix proposto:** Skip atribuição se sb/bb None. Logger.warning("Vision SB/BB None, deixar para Fase 3").
- **Esforço:** ~15 min.

### #B4 — Fase 3 greedy sem tie-breaking nem optimal assignment
- **File:** `screenshot.py:659-683`
- **Vector:** Para cada unmapped HH (na ordem do dict, não-determinística entre Python versions/imports), busca vision com diff mínimo. Sem tie-breaking quando 2 vision têm `diff` igual; sem Hungarian algorithm que minimiza diff total.
- **Severidade:** Funcional (potencialmente origina #22 quando combinado com keys-corruptas).
- **Fix proposto:** Hungarian algorithm via `scipy.optimize.linear_sum_assignment`. Custo ~20 linhas.
- **Esforço:** ~1-2h + dependência scipy (já em requirements? confirmar).

### #B5 — Heartbeat blocked durante Vision pesado
- **File:** logging async não confirmado, mas mencionado em sessão pt6 indirectamente
- **Vector:** Vision sync chamada (call OpenAI) bloqueia event loop FastAPI durante ~3-10s; durante esse período, healthcheck Railway pode falhar.
- **Severidade:** Operacional (Railway pode reciclar replica em healthcheck timeout).
- **Fix proposto:** confirmar se Vision call está em `BackgroundTasks` ou `asyncio.create_task` (já está em `_run_vision_for_entry` linha 1280-1286 com BackgroundTasks). Se sim, bug pode ser falso positivo. Validar logs Railway por entries `vision_ms > 5000ms`.
- **Esforço:** ~30 min (audit + ajuste threshold).

### #B9 — Bucket 1 não valida `tournament_name` ao fazer match imagem ↔ hand ✅ RESOLVIDO via substituição

- **File original do bug:** `backend/app/routers/attachments.py:180-248` (`_find_primary_match`, `_find_fallback_match`)
- **Vector:** Match temporal ±90s assume 1 torneio activo por janela. Quando jogador corre N torneios em paralelo (caso Rui = 9 torneios concorrentes), match falha sistematicamente. Fallback `hm3_temporal_fallback` é ainda pior — ignora canal e tournament_name, só compara timestamps.
- **Severidade:** Funcional grave (data corruption: imagens anexadas a mãos erradas).
- **Magnitude pt7:** 1/3 attachments confirmado errado pelo Rui (image `$88 Daily Hyper Special` anexada a hand `$525 Bounty Hunters HR`). Audit BD revelou 7-9 torneios distintos com mãos activas dentro de ±5min em cada caso → match temporal sem cruzamento de tournament_name é estatisticamente garantido a falhar.
- **Solução escolhida (29-Abr pt7):** **substituição completa por anexação manual** em vez de fix algorítmico. Bucket 1 automático é desactivado; utilizador escolhe explicitamente que imagem anexar a que mão via galeria UI.
  - Backend: novos endpoints `GET /api/images/gallery`, `POST /api/hands/{id}/images`, `DELETE /api/hands/{id}/images/{ha_id}`. Triggers Bucket 1 (`_find_primary_match`, `_find_fallback_match`) descontinuados.
  - Frontend: tag #imagens na página Discord, secção "Imagens anexadas (N)" no modal de mão, popup galeria com filtros canal+data.
- **Cleanup BD:** 3 hand_attachments rows apagados (entries image preservadas).

### #B10 — Vision não extrai `tournament_name` da imagem da galeria (futuro)

- **File:** `backend/app/routers/attachments.py` (futuro: helper `_extract_tournament_from_image`)
- **Vector:** A galeria manual de imagens (#B9 fix) deixa o utilizador escolher 1 imagem da lista, mas a lista não tem o `tournament_name` da imagem visível — só metadata Discord (canal, hora, autor). Para Rui filtrar/encontrar imagem certa, precisa abrir thumbnail e ver header. Vision (GPT-4o-mini) extrair `tournament_name` automaticamente do header da imagem permitiria filtragem na galeria por torneio.
- **Severidade:** UX (não bloqueia, melhora ergonomia).
- **Esforço estimado:** ~2-3h (helper Vision + threading + persistir em entries.raw_json).
- **Custo operacional:** ~$0.005 por image processada (~16 imagens actuais = $0.08).
- **Status:** Adiado para sessão futura. Galeria manual #B9 funciona sem isto.

### #B8 — Regra B (auto-create villain cat='sd' via showdown) era falso positivo ✅ RESOLVIDO

- **File:** `backend/app/services/hand_service.py:74-76` (removido)
- **Vector:** `_classify_villain_categories` regra B criava `category='sd'` automaticamente quando `has_real_match AND has_showdown AND has_cards`. Heurística partiu da assunção "showdown + cards reveladas = villain interessante", mas regra de negócio real é "tag `nota` explícita → entra em Vilões". Showdown sem tag não interessa para Vilões. Detectado pt7 quando NemoTT (mostrou cards em hand `GG-5885208311` no canal `#icm-pko`) apareceu como villain cat='sd' sem o Rui ter marcado a mão para estudo.
- **Severidade:** Funcional grave (data-pollution Vilões com mãos não marcadas).
- **Magnitude pré-fix pt7:** 22/22 cat='sd' = 100% falsos positivos (sample FASE 1 com 1175 hh_import + 50 hm3). Em BD pré-wipe pt7 eram 115 cat='sd' — provavelmente todos falsos positivos.
- **Fix aplicado** (commit `ce56d59`, 29-Abr pt7):
  - Removido bloco regra B (3 linhas)
  - Docstring actualizado (regras agora A∨C∨D, removido B)
  - Pré-condição `has_cards or has_vpip` (linha 60) preservada como safety net
  - Cleanup BD: `DELETE FROM hand_villains WHERE category='sd' AND hand sem tag nota` (defensivo) — 22 rows apagados
- **Pendente futuro:** tab "Mãos com SD" em `frontend/src/pages/Villains.jsx` deixada por agora — vai aparecer vazia. Será removida em Tech Debt #12 (re-arquitectura modal Vilões).

### #B7 — Discord bot ignora `last_sync_at` quando `last_message_id` é NULL

- **File:** `backend/app/discord_bot.py` (função `_sync_guild_history` ou `fetch_messages_for_channel`, a confirmar)
- **Vector:** Detectado pt7 ao popular `discord_sync_state` com cutoff `-1d` pós-wipe TOTAL. Bot ignora `last_sync_at` completamente quando `last_message_id` está NULL → varre TODA a história do canal (Março+). Volume idêntico pt6 com cutoff -3d (277 entries) confirma que cutoff temporal nunca foi respeitado em nenhum dos dois casos — os últimos 3d/1d apenas coincidiram com a janela onde havia mensagens novas.
- **Severidade:** Funcional (bloqueia controlo fino de cutoff em qualquer reset BD).
- **Magnitude observada pt7:** sync com cutoff -1d → 277 entries criadas → 156 placeholders Discord (apanhou Março, 19-26 Abril, 28-29 Abril). Esperado para -1d: ~50-100 entries (apenas 28-29 Abr). Erro factor: 3-5×.
- **Workaround temporário:** SQL DELETE selectivo de `hands.origin='discord'` pré-cutoff data desejada. Não é destrutivo (placeholders órfãos, sem `hand_villains` associadas).
- **Fix proposto:** quando `last_message_id` é NULL, em vez de fetch de toda a história, passar `after=<datetime do last_sync_at>` ao `discord.py.TextChannel.history()`. discord.py aceita ambos `before/after` como `Snowflake|datetime`.
- **Esforço:** ~30-60 min (ler código bot + identificar onde fetch é construído + 1 condicional).

### #B6 — Discord sync race overlap
- **File:** `discord_bot.py:189-192` (a confirmar exacto via leitura)
- **Vector:** `discord_message_id` UNIQUE com `ON CONFLICT DO NOTHING`. Se restart bot + auto-sync ligado simultâneo, 2 fetches paralelos podem fazer overlap em `after=last_message_id`. Conflict resolve dedup, mas se write-state-cursor lento, contagem reportada está errada.
- **Severidade:** Cosmético (count UI mostra menos do que real, dedup não falha).
- **Fix proposto:** advisory lock `pg_advisory_xact_lock` em `_sync_guild_history`. Ou simples: `DISCORD_AUTO_SYNC=False` (default actual — manter).
- **Esforço:** ~1h se decidirem.

### #B12 — Hands GG anonimizadas com cross-post Discord não recebem `discord_tags` populado

- **File provável:** `backend/app/routers/screenshot.py` (`_link_second_discord_entry_to_existing_hand:831`) ou path de ingestão de entries Discord órfãs (sem hand ligada).
- **Origem:** Achado lateral durante validação empírica do #18 (pt8, 30-Abr).
- **Vector:** Quando o Rui partilha a mesma mão em 2 canais Discord (cross-post), só **1/17 TMs** observados têm `discord_tags` populado na hand correspondente. As restantes 16 hands têm `discord_tags=[]` apesar de existirem 2 entries Discord em canais distintos. Padrão comum: estas 16 hands têm `match_method=null` (HH GG anonimizada sem match SS), enquanto a única que ficou correcta (hand 1115) tem `match_method=anchors_stack_elimination_v2`. Hipótese: `_link_second_discord_entry_to_existing_hand` só dispara quando a 1ª entry já tem hand ligada via enrich; em hands GG anon, a 1ª entry fica órfã e a 2ª também — `discord_tags` nunca recebe append.
- **Severidade:** 🟡 Funcional menor. Não corrompe dados; só impede UI de mostrar tags Discord em hands GG anonimizadas. Não toca em `hand_villains` (regra de negócio impede villains em hands sem `match_method`).
- **Magnitude pt8:** 16/17 TMs com cross-post Discord (94%) afectados.
- **Fix proposto:** investigar trigger de append `discord_tags` independente de existir match SS↔HH. Possível solução: ao ingerir entry Discord, tentar localizar hand pelo `hand_id` (TM number) e fazer append directo de `discord_tags` mesmo que não haja enrich.
- **Esforço:** ~1h investigação + ~30min fix se confirmado.

### #B13 — Contadores `last_sync` (N links/M canais/K match HH) medem entries criadas em vez de trabalho útil

- **File:** `backend/app/routers/discord.py` (CTE `new_entries` no fim de `sync_and_process`).
- **Origem:** Achado pt8 durante teste da feature nova de sincronização com janelas (commit `7ad41d4`).
- **Sintoma:** Utilizador faz sync de janela já totalmente importada e vê `n_links=0` mas a lista de mãos cresce de 23 para 150 (placeholders `GGDiscord` criados por `backfill_ggdiscord`, processamento Vision de entries antigas que faltavam imagem, matches feitos retroactivamente, etc.). Os contadores afirmam "esta janela trouxe X coisas novas", mas o pipeline `sync-and-process` faz muito mais do que ingerir mensagens novas — opera globalmente sobre entries pré-existentes.
- **Causa:** A query CTE filtra `entries WHERE source='discord' AND entry_type IN ('replayer_link','image') AND created_at >= sync_started_at`. Não captura: (a) processamento Vision de entries pré-existentes a `sync_started_at`, (b) placeholders criados em `hands` por `backfill_ggdiscord`, (c) matches SS↔HH feitos por `run_match_worker` (Bucket 1 attachments), (d) anexação de imagens órfãs.
- **Severidade:** 🟢 UX. Não corrompe dados. Mensagem na UI desalinhada com a realidade observada pelo utilizador.
- **Possíveis abordagens (a investigar pt9):**
  - **(a)** substituir contadores por "entries processadas + placeholders criados + matches feitos nesta sync" — instrumentar cada subtask para reportar contadores.
  - **(b)** acrescentar contadores adicionais sem remover os actuais — mantém compat com UI actual.
  - **(c)** deixar os contadores como estão e mudar texto da UI para "Mensagens novas: N · Canais: M · Match HH: K" — mais honesto sobre o que medem.
- **Bloqueado por:** nada. Investigação isolada.
- **Esforço:** ~1h.

---

## §3a. UX bugs detectados em validação pt7 (Bloco B Fase 1)

| ID | Bug | File (provável) | Severidade | Esforço | Notas |
|---|---|---|---|---|---|
| **#UX1** | Modal villain "MÃOS EM COMUM" mostra cards do Hero em vez do villain | `frontend/src/pages/Villains.jsx` ou `components/HandHistoryViewer.jsx` | 🟡 Cosmético-Funcional (pode confundir interpretação) | ~30 min frontend | Detectado 29-Abr pt7 quando Rui validou Pipeline 1 cutoff 1d. Comportamento esperado: se villain mostrou cards no showdown → cards villain; senão → "—" ou "Foldou". Decisão Rui: anotar + seguir; ataque sessão futura junto com #11/#12 (UX block). |

---

## §3. Bugs em parsers detectados (auditoria estática Agent A)

Relevância variável; alguns são edge cases raros, outros podem afectar produção. **Magnitude não medida** — precisava audit empírico cruzando com BD.

| ID | Bug | File:Line | Severidade | Esforço |
|---|---|---|---|---|
| **#P1** | Nicks com parênteses truncados ("Karluz (ex)") | `gg_hands.py:385`, `hm3.py:386, 407` | Funcional | 15 min |
| **#P2** | Stacks fraccionários EUR/US ambiguidade silenciosa | `winamax.py:49`, `gg_hands.py:388` | Cosmético→Funcional se moedas mistas | 30 min audit |
| **#P3** | Heads-up + 3-max position logic não testada | `gg_hands.py:33-64`, `hm3.py:89-126` | Funcional (raro) | 30 min + tests |
| **#P4** | Antes/straddle não extraído (silently 0) | `gg_hands.py:474`, `hm3.py:632-641` | Funcional grave (result em BB divergente quando hero folda preflop) | 30 min |
| **#P5** | "mucks hand" não capturado como showdown | `gg_hands.py:300` | Cosmético (cards None expected) | 15 min |
| **#P6** | Hero sitting out — posição calculada com seats activos errados | `gg_hands.py:384-404` (sem filtro vs `hm3.py:435-456` que filtra) | Funcional | 45 min unify |
| **#P7** | Side pots multi-way all-in: lógica presume HU | `gg_hands.py:439-446`, `hm3.py:547-567` | Funcional grave em torneios PKO multi-way | 1h |
| **#P8** | Idempotência parser GG anon_map (Padrão 2 dependente seat order) | `gg_hands.py:141-243` | Mitigado por #20 mas Padrão 2 ainda existe quando Hero é único nick real | 30 min |

---

## §4. Workarounds e dívida técnica (não-bugs)

| Item | Tipo | Esforço | Notas |
|---|---|---|---|
| Backfill 110 mãos absorvidas Discord (filtro entry_id) | Limpeza | ~1-2h | Pós-wipe pt5/pt6 estado actual já limpo — re-aplicar só se necessário |
| Pesquisa MTT 10 dígitos → modal directo | Feature | 30 min | Opção A aprovada 24-Abr |
| Página Discord: 2 listas + botão "Forçar Match" individual | Feature | 3-4h | Spec fixa |
| Gyazo pipeline Case 1/2 (±2min canal + WPN lobby 1min) | Feature | 4-5h | Vision integration |
| Centralizar trigger Fase IV em hand_service.py (refactor) | Refactor | 2h | Padrão duplicado em 3 routers |
| Endpoint legacy `/api/villains` (housekeeping) | Cleanup | 30 min | Bloqueado por #12 |
| Consolidação 8-9 PokerCard locais no partilhado | Refactor | 4-5h | Componente partilhado já existe (29-Abr); risco moderado |
| `_upload_screenshot_to_storage` stub /tmp ephemeral | Tech Debt | 1h | Mitigado por `/api/screenshots/image/{entry_id}` |
| Sessão B UI (`position_parse_failed` badge + edição manual) | Feature | 2-3h | Spec conhecida |
| Logos salas como banner esbatido | Feature | 2-3h | Mockup validado |
| Persistência viewMode Estudo (localStorage) | Feature | 5 min | Default 'tags' actual sem persistência |
| Validação SQL hand 253 (Upstakes_io villain sd) pós-Pipelines 2-5 | Validação | 15 min | Estado actual provável já limpo |

---

## §5. Análise dependências entre Tech Debts pendentes

```
#22 (data corruption hand 923) ──┐
                                 ├── desbloqueia validação UI Vilões SD
#21 (FECHADO) ───────────────────┘    (blocker actual)

#15 (datas anómalas) ── independente, quick win

#10 (parser WN truncamento) ── decisão Rui Opção A vs B
                                  └── pode revelar más assignments hands 102/126

#18 (FECHADO pt8 30-Abr) ── validado empíricamente: guard #21 elimina vector
                              └── 1 hand cross-post real (1115) APA coerente
                                  + 23 hands enriched protegidas + 0 divergências

#15 (FECHADO pt8 30-Abr 8919840) ── Dashboard mostra created_at + linha "jogada"

#B7 (FECHADO pt8 30-Abr 9d57b2b) ── precedência tripla cursor Discord +
                                     APP_EPOCH_CUTOFF 1 Jan 2026 Lisbon

feat sync windows (pt8 30-Abr 7ad41d4) ── usa #B7 path (b); UI inline + endpoint estendido

#B12 (cross-post Discord não popula discord_tags em hands GG anon) ── achado lateral pt8
                              └── 16/17 TMs afectados; investigação ~1h

#B13 (contadores last_sync medem entries em vez de trabalho útil) ── achado pt8 pós-feature
                              └── n_links=0 quando pipeline ainda processou Vision/backfill/matches

#12 (modal Vilões re-arquit) ──┐
                               ├── bloqueia /api/villains housekeeping
#11 (botão × villain) ─────────┘   bloqueia uso pleno modal

#13c (aliases SITE_COLORS) ── independente, trivial
```

---

## §6. Plano sequencial de fix proposto

Ordem maximiza valor entregue por hora + minimiza risco. **Fase Wipe + re-teste pequeno volume** após Bloco A.

### Bloco A — Críticos (~5h)

1. **#15 Dashboard datas** — 10 min. Quick win, isolado.
2. **#22 Mapping baralhado pós-enrich** — 3-4h. Opção A recomendada (re-parse raw + reset apa para hashes + 1 enrich limpo). Magnitude conhecida (38 hands). Inclui validação SQL pós-fix das 38 hands.
3. **#18 Validar não-determinismo** — 30 min. Sample 2-3 hands cross-post + audit hand_villains stable cross run. Esperado: já resolvido pelo #21.

### Bloco B — Wipe + re-teste (controlado, ~2h)

4. **Wipe parcial:** 38 hands afectadas por #22 + dependentes (apenas se Opção A não for aplicável) — OU continuar com BD actual se Opção A re-enrich corrigir tudo in-place.
5. **Re-import 1 ZIP pequeno** (10-20 mãos sample) para validar pipelines pós-fix #22 sem ruído de 1175 hands.
6. **Pipelines 4 e 5** (Upload SS + Bucket 1 standalone) — pendentes da pt6.

### Bloco C — Funcional latente (~2h)

7. **#10 Parser WN truncamento** — 1h fix + 10 min backfill (espera decisão Opção A vs B Rui).
8. **#B1 Tolerância stack micro-stacks** — 15 min. Reduz false negatives Fase 2.
9. **#B3 Fallback silencioso vision_sb=None** — 15 min. Hardening sem custo.

### Bloco D — Hardening enrich (~3h)

10. **#B4 Hungarian algorithm Fase 3** — 1-2h. Substituir greedy por óptimo (scipy.optimize). Reduz risco de #22 voltar com inputs novos.
11. **#B2 Levenshtein âncoras** — 30 min. Reduz false positives Fase 1.
12. **#P4 Antes/straddle extraction** — 30 min. Result em BB mais correcto.

### Bloco E — UX/Feature (~10-12h, sessão dedicada)

13. **#11 Botão × villain** — 2-3h.
14. **#UX1 Modal villain mostra cards Hero em vez de villain** — 30 min.
15. **#12 Re-arquitectura modal Vilões** — 6-8h.
16. **#13c Aliases housekeeping** — 10 min (após #12 valida paleta estável).

### Bloco F — Parsers edge cases (~3h, opcional)

16. **#P1 nicks com parênteses, #P3 heads-up, #P6 sitting out, #P7 side pots, #P8 idempotência GG Padrão 2** — fix incremental quando aparecerem em produção. Manter como issue tracker.

---

## §7. Esforço total estimado

| Bloco | Min h | Max h |
|---|---|---|
| A — Críticos | 4 | 5 |
| B — Wipe + re-teste | 2 | 3 |
| C — Funcional latente | 2 | 3 |
| D — Hardening enrich | 2 | 3 |
| E — UX/Feature | 9 | 12 |
| F — Parsers edge cases | 2 | 4 |
| **TOTAL** | **21** | **30** |

**Mínimo viável (Blocos A+B+C):** ~9-11h para BD actual válida + validação 5 pipelines.

---

## §8. Riscos identificados

1. **Fix #22 Opção A pode tocar 38 hands** — risco regressão moderado. Mitigação: backup defensivo antes + audit pós-fix.
2. **Hungarian algorithm (#B4) pode mudar mapping em hands não-afectadas** — diferença óptimo vs greedy. Mitigação: validar 90 hands cat='sd' produzem mesmo mapping após fix.
3. **#10 Opção A vs B em parser WN** — Opção A mais defensiva mas pode ter false negatives noutros sites. Mitigação: testar sample real.
4. **Modal Vilões #12 é re-arquitectura grande** — 6-8h sem entregar valor incremental. Mitigação: dividir em sub-tarefas, entregar layout primeiro.

---

## §9. Decisões pendentes Rui

1. **#22 Opção A (re-parse raw + reset) vs Opção B (Hungarian in-place) vs Opção C (wipe parcial 38 hands + re-import)?**
2. **#10 Opção A defensiva (validar actor) vs B cirúrgica (regex keyword poker)?**
3. **#11 comportamento re-import: blacklist persistida ou re-criar villain?**
4. Aceitar plano sequencial Blocos A→F ou priorizar diferente?
5. Bloco F (parsers edge cases) — fix proactivo ou só reactivo quando produção mostra?

---

## §10. Notas para próxima sessão

- Backup defensivo recomendado **antes** do fix #22 (3 ZIPs Pipeline 2 + 38 hands afectadas).
- Audit script `investigate_techdebt22_magnitude.py` (a criar) — para cada hand pós-fix #22, recalcular mapping óptimo via Hungarian e comparar com actual; reporta divergências.
- Pipelines 4 e 5 ficam para Bloco B (após #22 fechado, com BD limpa).
- Considerar adicionar **integration test** mínimo em CI para #22 (mocking apa pós-enrich + raw e validar mapping correcto). Hoje não há suite de testes — quebrar este precedente para pipeline crítico tem retorno alto.
