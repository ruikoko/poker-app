# Validação end-to-end — poker-app

**Última actualização:** 27 Abril 2026
**Âmbito:** mapa completo do estado de validação pós-sessões 23-24 Abr (4 bugs + wipe), 24 Abr (Discord workflow + GG anon Estudo + refactor Tags), 26 Abr (consolidação SSs + Bucket 1 anexos imagem) **+ verificação ponta-a-ponta dos 5 pipelines pós-Bucket 1 (sessão 27-Abr)**

---

## Legenda

- ✅ Implementado e validado em prod
- ⚠️ Implementado mas validação parcial / conhecido gap
- ❌ Bug conhecido ou feature em falta
- ❓ Não verificado

---

## 1. Ingestão de mãos (4 fontes + Bucket 1)

| Fonte | Entra com origem correcta? | Match auto? | Cria villains quando aplicável? |
|---|---|---|---|
| HM3 `.bat` (WN/PS/WPN/GG) | ✅ `origin='hm3'` | ✅ HH→SS auto-rematch (`072f57a`) | ✅ non-GG via VPIP/showdown; GG: skip puro (SS pipeline trata, fix `6aefc95`). **Validado 27-Abr Fase 5: 130 hands, 0 GG, 88 villain rows** |
| Discord (replayer / HH texto / image) | ✅ `origin='discord'` + `discord_tags`. Imagens directas (Bucket 1) NÃO criam mão. | ✅ SS→HH auto após Vision; 2ª entry duplicada agrega via `_link_second_discord_entry_to_existing_hand` (`f8a8238`) | ✅ regra A∨B∨C. **Validado 27-Abr Fase 2: 61 entries, 48 hands, 12 cross-posts agregados** |
| Upload manual SS | ✅ entry `source='screenshot', entry_type='screenshot'`; Vision processa, match_method correcto. **Validado 27-Abr Fase 6: 2 SSs Rui + 10 Karluz, 12 entries resolved** | ✅ match por TM | ⚠️ `screenshot_url=NULL` (stub `_upload_screenshot_to_storage` grava em /tmp ephemeral; `img_b64` servido via `/api/screenshots/image/{entry_id}` funciona como fallback) |
| Import ZIP/TXT HH | ✅ `origin='hh_import'` (fix `2844b94` + backfill 1146 mãos). **Validado 27-Abr Fase 4: 13737 mãos importadas, 48 placeholders Discord substituídos** | ✅ auto-rematch SS→HH expandido para Discord `replayer_link`/`image` (`c452e12`) | ✅ |
| **Bucket 1 anexos imagem ↔ mão** | ✅ entries image NÃO criam hand; ligadas via `hand_attachments`. **Validado 27-Abr Fase 3: 4/4 imagens anexadas via `discord_channel_temporal`** | ✅ trigger Fase IV em `discord.py` + `hm3.py` (mas **não** em `import_.py` — Tech Debt #3) | n/a |

---

## 2. Match SS↔HH

| Cenário | Auto-dispara? | Validado? |
|---|---|---|
| SS chega primeiro, HH já existia | ✅ Vision dispara rematch | 23/04 + 27/04 Fase 6 (entries 92/93 anchors_stack_elimination_v2) |
| HH via import ZIP, SS Discord pendente | ✅ `import_.py:340-363` (replayer_link + image) | 23/04 (19 mãos) + 24/04 wipe (81/81) + **27/04 Fase 4 (48/48 placeholders Discord substituídos)** |
| HH via HM3 `.bat`, SS Discord pendente | ✅ `import_hm3` ganha bloco auto-rematch (`072f57a`) | 23-24/04 + 27/04 Fase 5 |
| HM3 import dispara worker anexos (Bucket 1) | ✅ `asyncio.create_task` em `import_hm3` (`06bbb9a`) | 26/04 + 27/04 Fase 5 (log `[import_hm3] attachments worker: 0 applied`) |
| `sync-and-process` Discord dispara worker anexos | ✅ `asyncio.create_task` em `sync_and_process` (`06bbb9a`) | 26/04 + 27/04 Fase 2 (4 applied) |
| **Karluz friend_alias hero** | ✅ `FRIEND_HEROES` reconhece como hero | **27/04 teste extra: 10 hands hero=Karluz, 0 cross-contamination** |
| `import_.py` dispara worker anexos retroactivo | ❌ **Tech Debt #3** — falta `asyncio.create_task` | Detectado 27/04 Fase 4 (4 attachments perdidos via CASCADE) |
| Forçar match bidireccional global | ✅ `/api/mtt/rematch` | 23/04 |
| Forçar match individual por SS | ✅ `/api/screenshot/orphans/{id}/rematch` | ❓ não testado explicitamente |
| Forçar match individual por HH | ❓ endpoint pode não existir | A verificar |
| 2ª entry Discord para mesmo TM | ✅ append idempotente `discord_tags` + condicional `_create_villains_for_hand` (`f8a8238`) | 24/04 + **27/04 Fase 2 (12 cross-posts em prod)** |

---

## 3. Persistência de metadados

| Comportamento | Estado |
|---|---|
| Placeholder Discord → HH real preserva metadados | ✅ fix `823a9f4` + NULLIF defensivo `7de889f` (descoberto pós-wipe que `ARRAY[]::text[] DEFAULT` não é NULL para COALESCE). **Re-validado 27-Abr Fase 4 (48/48 com discord_tags + screenshot_url + cross-posts preservados)** |
| `hand_villains` idempotente (ON CONFLICT) | ✅ fix `0b01d11` |
| `hand_villains` criado em rematch SS↔HH | ✅ fix `0b01d11` + backfill `af563a8` (44 mãos pós-wipe) + `ef1cb64` (32 mãos sessão 24/04) |
| `hand_villains` criado em HM3 `.bat` GG | ✅ skip puro em `_create_hand_villains_hm3` para GGPoker (SS pipeline trata) — fix `6aefc95` |
| `hand_villains` criado em HM3 `.bat` non-GG | ✅ via VPIP/showdown directo (`6aefc95`). **Validado 27-Abr Fase 5: 88 rows / 79 hands** |
| `hand_villains` criado em upload manual SS | ✅ via path partilhado com `_enrich_hand_from_orphan_entry`. **Validado 27-Abr Fase 6: +2 villains** |
| Regra A∨B∨C strictamente aplicada em villain creation | ⚠️ **Tech Debt #4** — `mtt.py:_create_villains_for_hand` usa VPIP legacy; 18 hands "OUTRO" + 1 hand `has_showdown=false` na Fase 6 com villain criado |
| ON CONFLICT preserva `all_players_actions` enriquecido (HM3 GG) | ✅ `CASE WHEN site='GGPoker' THEN COALESCE(...)` em `6aefc95` |
| Anexos imagem preservados em substituição placeholder→matched (sync_and_process / import_hm3) | ✅ trigger retroactivo Fase IV reanexa em milissegundos. **Validado 27-Abr Fase 4 + Recovery (4 attachments → 0 → 4 via re-sync)** |
| Anexos imagem preservados em substituição via `import_.py` (ZIP HH) | ❌ **Tech Debt #3** — sem trigger; recovery passa por novo sync Discord |

---

## 4. Roteamento UI

| Condição | Destino esperado | Validado? |
|---|---|---|
| `hm3_tags` contém `nota*` | Vilões | ✅ |
| `hm3_tags` outras tags | Estudo agrupado por tag | ✅ |
| `discord_tags` contém `nota` + match | Vilões (regra C) | ✅ 24/04 (regra C dispara, UI Tags consolidada via `ed663d0`) |
| `discord_tags` outros canais + match | Estudo, secção "Canais Discord" (azul `#5865F2`) | ✅ 24/04 (`e77b5cf` + `ed663d0`: pills azul Discord, agrupamento separado HM3/Discord/sem-tag) |
| Mãos sem hm3_tags em vista Tags | Grupo "(sem tag)" | ✅ 24/04 (`08a27be` — fix Tags vs Torneios mesmo número) |
| SS sem HH | Dashboard painel "SSs à espera" + secção "Discord — Só SS (sem HH)" no Estudo (vista Por Tags, 26/04 parte 1) | ✅ |
| HH GG sem SS | Torneios > GG > Sem SS (NÃO em Estudo) | ✅ 24/04 (`07059f8`: filtro `STUDY_VIEW_GG_MATCH_FILTER`) |
| HH PS/WN/WPN sem SS | Estudo directo (nicks reais) | ✅ |
| Mãos GG anonimizadas | Excluídas de Estudo | ✅ 24/04 (`07059f8`: 48.341 → 414 com filtro apertado) |
| Anexos imagem visíveis na lista (matched hands) | Ícone `📎 N` em `HandRow.jsx` | ✅ 26/04 parte 2 (`a543629`) |
| Anexos imagem visíveis na lista (placeholders Discord) | Ícone `📎 N` + thumbnails 120px em `PlaceholderHandRow` | ✅ **27/04 commit `a2ac5e5` (Tech Debt #1 fechado)** |
| Anexos imagem visíveis no detalhe | Secção CONTEXTO em `HandDetailPage.jsx` com thumbnail 200px | ✅ 26/04 parte 2 (`a543629`) |
| HAND HISTORY no detalhe usa nicks reais (não hashes) | ❌ **Tech Debt #5** — mostra `89ef4cba: ...` em vez de aplicar `player_names.anon_map` |

---

## 5. Funcionalidades específicas

| Feature | Estado |
|---|---|
| `/api/villains/search/hands` regra A∨B∨C | ✅ |
| Villain `villain_result` (sinal correcto) | ✅ 23/04 Fase 2 |
| Tournament name/number extracção | ✅ 23/04 |
| Tournament format canonicalisation | ✅ 23/04 |
| `buy_in` WN/PS/WPN | ✅ 23/04 Fase 1 |
| Parser WPN `\r\r\n` | ✅ 22/04 |
| Parser WPN stacks decimais | ✅ 21/04 |
| Parser Winamax nicks com `.` final | ✅ 21/04 |
| Helper `_link_second_discord_entry_to_existing_hand` (2ª entry duplicada) | ✅ 24/04 (`f8a8238`) **+ re-validado 27/04 Fase 2 (12 cross-posts)** |
| Auto-rematch Discord pós-import expandido (`replayer_link` + `image`) | ✅ 24/04 (`c452e12`) |
| Filtro `study_view` exclui GG anonimizada | ✅ 24/04 (`07059f8`) |
| Tag agrupamento Discord vs HM3 distinto (3 secções) | ✅ 24/04 (`ed663d0`) |
| Tabela `hand_attachments` + endpoint `/api/attachments` (Bucket 1) | ✅ 26/04 parte 2 (fases I-VI; commits `ab1953e`→`d9d6f44`) |
| Triggers retroactivos `asyncio.create_task` em sync_and_process / import_hm3 | ✅ 26/04 parte 2 (`06bbb9a`); **lacuna identificada em `import_.py` — Tech Debt #3** |
| UI ícone `📎 N` + secção CONTEXTO + thumbnails 200px (HandRow + HandDetailPage) | ✅ 26/04 parte 2 (`a543629`) |
| **UI 📎 N + thumbnails 120px em PlaceholderHandRow** | ✅ **27/04 commit `a2ac5e5` (Tech Debt #1 fechado)** |
| Anexos imagem ↔ mão (Bucket 1) end-to-end | ✅ **27/04 Fase 3 + Recovery: 4/4 anexadas, validado em BD + UI** |
| **Friend_aliases robustos (Karluz não villain quando Rui hero, Rui não villain quando Karluz hero)** | ✅ **27/04 teste extra: 0 cross-contamination** |

---

## 6. Pendentes por validar (prioridade decrescente)

1. **Backfill estendido às 110 mãos absorvidas** — placeholders Discord que matcharam HHs reais perderam `discord_tags` antes do fix `7de889f`. Filtro precisa de incluir `entry_id IN (SELECT id FROM entries WHERE source='discord')` em vez de só `origin='discord'`. (anterior à sessão 27-Abr; pós-wipe da sessão 27-Abr o estado está limpo)
2. **Pesquisa MTT 10 dígitos numéricos → abrir modal mão directamente** (Opção A pré-aprovada 24/04, não implementada).
3. **Página Discord: agrupar por canal real** (`#nota`, `#pos-pko`, etc.) em vez de `#GGDiscord` + `#sem-tag` (detectado 24/04 PARTE 10, não atacado).
4. Tech Debt #2 — investigar `img_b64=NULL` Gyazo (entries 17 e 31 confirmaram padrão).
5. Tech Debt #3 — adicionar trigger Fase IV em `import_.py`.
6. Tech Debt #4 — refundir villain creation com regra A∨B∨C strict.
7. Tech Debt #5 — aplicar `anon_map` em HandDetailPage HAND HISTORY.
8. Tech Debt #6 — endurecer race condition `asyncio.sleep(10)` em `discord.py:140`.
9. Tech Debt #7 — investigar 3 entries `hh_text/new` com `raw_text=None`.
10. **Forçar match individual por HH** — confirmar se endpoint existe.
11. **Sessão B UI** (`position_parse_failed` com edição manual).
12. **Migração painel "SSs à espera" do Dashboard para Discord**.

---

## 7. Bugs conhecidos não corrigidos

### 7.1 Tech Debts da sessão 27-Abr

| # | Bug | Severidade | Esforço |
|---|---|---|---|
| 1 | (FECHADO 27-Abr commit `a2ac5e5`) PlaceholderHandRow não mostrava 📎 N nem thumbnails | UX | ✅ feito |
| 2 | `img_b64=NULL` silencioso quando Gyazo serve HTML em vez de imagem (padrão repete-se entries 17 e 31). Frontend tem fallback para `image_url` mas thumbnail visualmente partido | Cosmético | ~1h investigação |
| 3 | `import_.py` (`POST /api/import` para ZIP HH) não tem trigger Fase IV. Quando placeholder Discord é substituído por HH real, `ON DELETE CASCADE` apaga `hand_attachments` sem reanexação automática. Recovery passa por novo sync Discord. Padrão a copiar: `discord.py:163` ou `hm3.py:1222` | UX (auto-recoverável) | ~10min código + 5min deploy |
| 4 | `_create_villains_for_hand` em `mtt.py` (path enrichment SS↔HH) usa regra VPIP preflop legacy, não regra canónica A∨B∨C documentada em MAPA §4. 18 hands "OUTRO" + 1 hand `has_showdown=false` na Fase 6 | Funcional / incoerência | ~1h investigação |
| 5 | HandDetailPage mostra hashes GG (`89ef4cba: ...`) na secção HAND HISTORY em vez de aplicar `player_names.anon_map` para mostrar nicks reais | Funcional grave (UX bloqueante para estudo de mãos) | ~1-2h |
| 6 | Race condition trigger Bucket 1: `asyncio.sleep(10)` em `discord.py:140` insuficiente para batch Vision >20 entries. Workaround: re-clicar "Sincronizar Agora" | UX | ~30min |
| 7 | 3 entries `hh_text/hand_history/new` com `raw_text=None` criadas durante a sessão (entries 90, 91, 104). Origem por identificar — provável upload UI com payload vazio ou bug em path específico | Funcional (não-bloqueante) | ~30min investigação |

### 7.2 Bugs persistentes (UX/cosméticos pré-sessão 27-Abr)

| Letra | Bug | Severidade | Esforço |
|---|---|---|---|
| A | Pesquisa MTT 10 dígitos filtra torneio inteiro em vez de abrir modal mão (Opção A aprovada, código não escrito) | UX | ~30min |
| B | Página Discord agrupa por `#GGDiscord`/`#sem-tag` em vez de canais reais | UX | ~1h |
| C | `screenshot_url=NULL` em uploads manuais SS (stub `/tmp` ephemeral); `img_b64` via `/api/screenshots/image/{entry_id}` mitiga. **Confirmado 27-Abr Fase 6 (2/2 entries 92/93 com screenshot_url=NULL)** | Cosmético | ~1h |
| D | `channel_name` em `hand_attachments` é ID numérico, não nome resolvido — frontend mostra ID na metadata do thumbnail | Cosmético | ~30min |

**Os 4 bugs antigos da validação 22-23 Abr foram TODOS resolvidos** (Bug #1 GG villains via skip `6aefc95`; Bug #2 origin via `2844b94`; Bug #3 auto-rematch HM3 via `072f57a`; Bug #4 coluna TAGS via `e77b5cf`).

---

## 8. Trabalho futuro (não-bug)

| Item | Estado | Esforço |
|---|---|---|
| Reorganização página Discord (2 listas + botões) | Spec fixa, pronto a arrancar | ~3-4h |
| Sessão B UI (badge ⚠ + edição manual) | Spec conhecida | ~2-3h |
| Logos salas como banner esbatido | Mockup validado | ~2-3h |
| Dashboard — colunas blind level + origem em "Últimas mãos importadas" | Ideia simples | ~1h |
| Backfill 110 mãos absorvidas (cleanup wipe) | Filtro a corrigir; estado actual pós-wipe limpo | ~1-2h |
| Filtros derivados Estudo (HU/3-way/MW) | Pendente histórico | ~2h |
| Notas vilões — botão na vista mão Discord | Pendente histórico | ~1h |
| Suporte Winamax replayer HTML | 49/246 SSs falham | ~3-4h |
| **Centralizar trigger Fase IV em `hand_service.py`** (em vez de duplicar em discord/hm3/import) | Tech Debt #3 sugere | ~2h |

---

## 9. Conclusão do estado por pipeline

| Pipeline | Estado global |
|---|---|
| Discord (replayer + HH texto) | ✅ completo e validado (24/04 + 26/04 + **27/04 Fase 2: 61 entries, 12 cross-posts**) |
| HM3 `.bat` | ✅ 3 bugs corrigidos (villains GG skip, auto-rematch HH→SS, ON CONFLICT preserve). **Re-validado 27/04 Fase 5 (130 hands, 88 villains, 0 GG)** |
| Import ZIP/TXT HH | ✅ funcional + origin reparado + auto-rematch Discord expandido. **Re-validado 27/04 Fase 4 (13737 hands, 48/48 placeholders Discord substituídos)**. ⚠️ Tech Debt #3: falta trigger Bucket 1 Fase IV |
| Upload manual SS | ✅ **Promovido de ⚠️ para ✅ em 27/04 Fase 6 (2 SSs Rui + 10 Karluz, anchors_stack_elimination_v2 funcional)**. Bug C `screenshot_url=NULL` mitigado por endpoint `/api/screenshots/image/{entry_id}` |
| Anexos imagem ↔ mão (Bucket 1) | ✅ **Promovido de ⚠️ para ✅ em 27/04 Fase 3 + Recovery (4/4 anexadas, trigger retroactivo funcional, validação BD + UI)** |

---

## 10. Commits de referência

### Sessão 22-23 Abril (validação inicial)

| Commit | Descrição |
|---|---|
| `8b60710` | Opção X — HH texto live path |
| `87c79c2` | Opção X — 3 call-sites placeholders |
| `45d9168` | Arquivar scripts backfill standalone |
| `5bbbffb` | Match bidireccional SS↔HH |
| `823a9f4` | Fix `_insert_hand` preserva metadados Discord |
| `434c6ec` | Backfill TEMP metadados (19 mãos) |
| `a89265d` | Cleanup TEMP metadados |
| `3f4f15d` | Audit extension `backfilled_19abr_villains` |
| `0b01d11` | Fix helper `_create_ggpoker_villain_notes_for_hand` + ON CONFLICT |
| `b135af1` | Backfill TEMP hand_villains retroactivo (16 mãos) |
| `f43161c` | Cleanup final — 3 TEMPs removidos |

### Sessão 23-24 Abril (4 bugs + wipe)

| Commit | Descrição |
|---|---|
| `2844b94` | Bug #2 fix — `origin='hh_import'` no import ZIP |
| `b29913f` | Arquivar scripts diagnose |
| `6aefc95` | Bug #1 fix — skip GG em villains HM3 + ON CONFLICT preserve |
| `072f57a` | Bug #3 fix — auto-rematch HH→SS no HM3 `.bat` |
| `e77b5cf` | Bug #4 fix — pills `discord_tags` na coluna TAGS |
| `7de889f` | Wipe — fix NULLIF discord_tags (DEFAULT array vazio ≠ NULL) |
| `f5dbc16` | Wipe — TEMP backfill empty discord_tags (74/74) |
| `af563a8` | Wipe — TEMP backfill missing hand_villains (42 hands, 68 villain rows) |
| `3ff6473` | Empty commit (forçar redeploy Railway) |
| `584cab2` | Cleanup 2 TEMPs (-301 linhas) |

### Sessão 24 Abril (Discord workflow + GG anon Estudo + refactor Tags)

| Commit | Descrição |
|---|---|
| `0058327` | `/mtt/dates` lazy + índice parcial |
| `2b6b179` | Frontend lazy loading Sem SS + pills |
| `6bab7f1` | Umbrella KO + Vanilla |
| `f8e0b0b` | Strip $N + colunas fixas + tooltip |
| `ed5b13e` | Fix tourneyKey TM |
| `be2198d` | `villain_count` per-tournament + TZ Lisbon |
| `7be2cb5` | Lazy Com SS + cleanBlinds + HandRow cross-page |
| `2f0ee8d` | `tm_search` OR + índice tournament_number |
| `f8a8238` | Live fix 2ª entry duplicada |
| `11845a6` | TEMP backfill duplicates |
| `c452e12` | Auto-rematch Discord expandido (`replayer_link`+`image`) |
| `85b3473` | TEMP rematch-discord-after-hh |
| `ef1cb64` | TEMP backfill missing villains |
| `8811b39` | Cleanup 3 TEMPs (-455 linhas) |
| `07059f8` | `study_view` filter + `migrated_to_study` counter |
| `08a27be` | `tag_groups` inclui `no_tag` bucket |
| `ed663d0` | `tag_source='auto'` + secções separadas Discord/HM3/Sem-tag |

### Sessão 26 Abril parte 1 (consolidação SSs + spec Bucket 1)

| Commit | Descrição |
|---|---|
| `d81dbf1` | docs: add docs/MAPA_ACOPLAMENTO.md + link em CLAUDE.md |
| `834c2b6` | Fix: placeholders Discord não passam como match real |
| `7fd32ce` | Feat(stats): novo endpoint `/hands/ss-without-match` |
| `a4a47d5` | Feat(stats): adiciona `ss_dashboard` com 4 contadores SS |
| `0652b4d` | Feat(dashboard): 4 painéis SS + lista unificada |
| `fa0b372` | Feat(hands): filtro Estudo aceita placeholders Discord não-nota-only |
| `f0bfd19` | Feat(estudo): secção 'Discord — Só SS (sem HH)' na vista Por Tags |
| `e789063` | Fix(tag-groups): placeholders Discord agrupam por canal real |
| `4a4a024` | Fix(estudo): vista Por Tags renderiza secção placeholders quando matched=0 |
| `26fe0bc` | Feat(estudo): SS na PlaceholderHandRow abre em nova aba |
| `5a314fa` | Docs(claude): regra de produto - imagens Discord são anexos, não mãos |
| `5eb9f4c` | Docs: spec Bucket 1 + diário sessão 26-Abr + aditamento MAPA |

### Sessão 26 Abril parte 2 (implementação Bucket 1)

| Commit | Descrição |
|---|---|
| `ab1953e` | Revert `bf0d9de` (Fase I) |
| `320ec2f` | Tabela `hand_attachments` + lifespan migration (Fase II) |
| `66a071c` | Worker `/api/attachments` (Fase III) |
| `d97bd33` | Uniformiza `delta_seconds` para image-to-played_at (fix Opção B) |
| `06bbb9a` | Triggers retroactivos `sync_and_process` + `import_hm3` (Fase IV) |
| `a543629` | UI ícone `HandRow` + secção CONTEXTO em `HandDetailPage` (Fase V) |
| `b9f0753` | Fix CHECK constraint `entries.status` + script backfill (Fase VI parte 1) |
| `d9d6f44` | Fix `RealDictCursor` `inserted["id"]` (Fase VI parte 2) |
| `0155157` | docs(bucket-1): Fase VII — actualização documental completa pós-Bucket 1 |

### Sessão 27 Abril (verificação ponta-a-ponta + Tech Debt #1)

| Commit | Descrição |
|---|---|
| `a2ac5e5` | feat(attachments): PlaceholderHandRow mostra 📎 N + thumbnails inline (Bucket 1 Tech Debt #1) |
| _[a gerar]_ | docs(verification): sessão 27-Abr fecho — 5 pipelines validados ponta-a-ponta |
