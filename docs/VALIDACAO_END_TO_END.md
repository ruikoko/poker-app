# Validação end-to-end — poker-app

**Última actualização:** 26 Abril 2026
**Âmbito:** mapa completo do estado de validação pós-sessões 23-24 Abr (4 bugs + wipe), 24 Abr (Discord workflow + GG anon Estudo + refactor Tags) e 26 Abr (consolidação SSs + Bucket 1 anexos imagem)

---

## Legenda

- ✅ Implementado e validado em prod
- ⚠️ Implementado mas validação parcial / conhecido gap
- ❌ Bug conhecido ou feature em falta
- ❓ Não verificado

---

## 1. Ingestão de mãos (4 fontes)

| Fonte | Entra com origem correcta? | Match auto? | Cria villains quando aplicável? |
|---|---|---|---|
| HM3 `.bat` (WN/PS/WPN/GG) | ✅ `origin='hm3'` | ✅ HH→SS auto-rematch (`072f57a`) | ✅ non-GG via VPIP/showdown; GG: skip puro (SS pipeline trata, fix `6aefc95`) |
| Discord (replayer / HH texto / image) | ✅ `origin='discord'` + `discord_tags`. Imagens directas (Bucket 1) NÃO criam mão. | ✅ SS→HH auto após Vision; 2ª entry duplicada agrega via `_link_second_discord_entry_to_existing_hand` (`f8a8238`) | ✅ regra A∨B∨C |
| Upload manual SS | ✅ entry `source='manual_upload', entry_type='screenshot'`; Vision processa, match_method correcto | ✅ match por TM | ⚠️ `screenshot_url=NULL` (stub `_upload_screenshot_to_storage` grava em /tmp ephemeral; `img_b64` servido via `/api/screenshots/image/{entry_id}` funciona como fallback) |
| Import ZIP/TXT HH | ✅ `origin='hh_import'` (fix `2844b94` + backfill 1146 mãos) | ✅ auto-rematch SS→HH expandido para Discord `replayer_link`/`image` (`c452e12`) | ✅ |

---

## 2. Match SS↔HH

| Cenário | Auto-dispara? | Validado? |
|---|---|---|
| SS chega primeiro, HH já existia | ✅ Vision dispara rematch | 23/04 |
| HH via import ZIP, SS Discord pendente | ✅ `import_.py:340-363` (replayer_link + image) | 23/04 (19 mãos) + 24/04 wipe (81/81 enriched via `c452e12`) |
| HH via HM3 `.bat`, SS Discord pendente | ✅ `import_hm3` ganha bloco auto-rematch (`072f57a`) | 23-24/04 |
| HM3 import dispara worker anexos (Bucket 1) | ✅ `asyncio.create_task` em `import_hm3` (`06bbb9a`) | 26/04 |
| `sync-and-process` Discord dispara worker anexos | ✅ `asyncio.create_task` em `sync_and_process` (`06bbb9a`) | 26/04 |
| Forçar match bidireccional global | ✅ `/api/mtt/rematch` | 23/04 |
| Forçar match individual por SS | ✅ `/api/screenshot/orphans/{id}/rematch` | ❓ não testado explicitamente |
| Forçar match individual por HH | ❓ endpoint pode não existir | A verificar |
| 2ª entry Discord para mesmo TM | ✅ append idempotente `discord_tags` + condicional `_create_villains_for_hand` (`f8a8238`) | 24/04 (cohort 23) |

---

## 3. Persistência de metadados

| Comportamento | Estado |
|---|---|
| Placeholder Discord → HH real preserva metadados | ✅ fix `823a9f4` + NULLIF defensivo `7de889f` (descoberto pós-wipe que `ARRAY[]::text[] DEFAULT` não é NULL para COALESCE) |
| `hand_villains` idempotente (ON CONFLICT) | ✅ fix `0b01d11` |
| `hand_villains` criado em rematch SS↔HH | ✅ fix `0b01d11` + backfill `af563a8` (44 mãos pós-wipe) + `ef1cb64` (32 mãos sessão 24/04) |
| `hand_villains` criado em HM3 `.bat` GG | ✅ skip puro em `_create_hand_villains_hm3` para GGPoker (SS pipeline trata) — fix `6aefc95` |
| `hand_villains` criado em HM3 `.bat` non-GG | ✅ via VPIP/showdown directo (`6aefc95`) |
| `hand_villains` criado em upload manual SS | ⚠️ via path partilhado com `_enrich_hand_from_orphan_entry`; não verificado explicitamente end-to-end (cohort 89 SSs uploadadas 24/04 não tinha novos vilões medidos isoladamente) |
| ON CONFLICT preserva `all_players_actions` enriquecido (HM3 GG) | ✅ `CASE WHEN site='GGPoker' THEN COALESCE(...)` em `6aefc95` |
| Anexos imagem preservados em substituição placeholder→matched | ⚠️ `ON DELETE CASCADE` apaga attachments quando placeholder é apagado; trigger retroactivo Fase IV reanexa em milissegundos (gap visual aceitável) — ver MAPA §2.11 Armadilha 1 |

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
| Anexos imagem visíveis na lista | Ícone `📎 N` em `HandRow.jsx` | ✅ 26/04 parte 2 (`a543629`) — só renderizado para mãos matched, não para `PlaceholderHandRow` (gap conhecido, ver MAPA §2.11 Armadilha 1) |
| Anexos imagem visíveis no detalhe | Secção CONTEXTO em `HandDetailPage.jsx` com thumbnail 200px | ✅ 26/04 parte 2 (`a543629`) |

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
| Helper `_link_second_discord_entry_to_existing_hand` (2ª entry duplicada) | ✅ 24/04 (`f8a8238`) |
| Auto-rematch Discord pós-import expandido (`replayer_link` + `image`) | ✅ 24/04 (`c452e12`) |
| Filtro `study_view` exclui GG anonimizada | ✅ 24/04 (`07059f8`) |
| Tag agrupamento Discord vs HM3 distinto (3 secções) | ✅ 24/04 (`ed663d0`) |
| Tabela `hand_attachments` + endpoint `/api/attachments` (Bucket 1) | ✅ 26/04 parte 2 (fases I-VI; commits `ab1953e`→`d9d6f44`) — 3 attachments inseridos (att_ids 58/59/60) |
| Triggers retroactivos `asyncio.create_task` em sync_and_process / import_hm3 | ✅ 26/04 parte 2 (`06bbb9a`) |
| UI ícone `📎 N` + secção CONTEXTO + thumbnails 200px | ✅ 26/04 parte 2 (`a543629`) |
| Anexos imagem ↔ mão (Bucket 1) end-to-end | ⚠️ implementado e validado em BD, validação visual UI bloqueada (placeholders Discord não mostram CONTEXTO até HH chegar) |

---

## 6. Pendentes por validar (prioridade decrescente)

1. **Backfill estendido às 110 mãos absorvidas** — placeholders Discord que matcharam HHs reais perderam `discord_tags` antes do fix `7de889f`. Filtro precisa de incluir `entry_id IN (SELECT id FROM entries WHERE source='discord')` em vez de só `origin='discord'`.
2. **Pesquisa MTT 10 dígitos numéricos → abrir modal mão directamente** (Opção A pré-aprovada 24/04, não implementada).
3. **Página Discord: agrupar por canal real** (`#nota`, `#pos-pko`, etc.) em vez de `#GGDiscord` + `#sem-tag` (detectado 24/04 PARTE 10, não atacado).
4. **Validação visual UI Bucket 1** — depende de chegada de HH real (substitui placeholder Discord) para `HandRow.jsx` renderizar 📎 + CONTEXTO. Hands 117/115/67 ficam invisíveis até lá.
5. **Investigar `img_b64` NULL silencioso** — entry 17 falhou fetch Gyazo durante backfill 26/04. Padrão a observar.
6. **Forçar match individual por HH** — confirmar se endpoint existe.
7. **HH GG sem SS aparece em Torneios > GG > Sem SS** — fluxo não testado explicitamente nos journals.
8. **Sessão B UI** (`position_parse_failed` com edição manual).
9. **Migração painel "SSs à espera" do Dashboard para Discord**.

---

## 7. Bugs conhecidos não corrigidos

| # | Bug | Severidade | Esforço |
|---|---|---|---|
| 1 | Pesquisa MTT 10 dígitos filtra torneio inteiro em vez de abrir modal mão (Opção A aprovada, código não escrito) | UX | ~30min |
| 2 | Página Discord agrupa por `#GGDiscord`/`#sem-tag` em vez de canais reais | UX | ~1h |
| 3 | `screenshot_url=NULL` em uploads manuais SS (stub `/tmp` ephemeral); `img_b64` via `/api/screenshots/image/{entry_id}` mitiga | Cosmético | ~1h |
| 4 | `img_b64` NULL silencioso para entry 17 (Bucket 1, fetch Gyazo `unexpected content-type text/html`) — frontend tem fallback | Funcional mitigado | ~2h diagnose |
| 5 | `channel_name` em `hand_attachments` é ID numérico, não nome resolvido — frontend mostra ID na metadata do thumbnail | Cosmético | ~30min |
| 6 | `PlaceholderHandRow` não mostra ícone 📎 nem link para detalhe (componente diferente do `HandRow.jsx`) | UX (não-bloqueante; resolve-se quando HH chega) | ~1h se quisermos mostrar 📎 também em placeholders |

**Os 4 bugs antigos da validação 22-23 Abr foram TODOS resolvidos** (Bug #1 GG villains via skip `6aefc95`; Bug #2 origin via `2844b94`; Bug #3 auto-rematch HM3 via `072f57a`; Bug #4 coluna TAGS via `e77b5cf`).

---

## 8. Trabalho futuro (não-bug)

| Item | Estado | Esforço |
|---|---|---|
| Reorganização página Discord (2 listas + botões) | Spec fixa, pronto a arrancar | ~3-4h |
| Sessão B UI (badge ⚠ + edição manual) | Spec conhecida | ~2-3h |
| Logos salas como banner esbatido | Mockup validado | ~2-3h |
| Dashboard — colunas blind level + origem em "Últimas mãos importadas" | Ideia simples | ~1h |
| Backfill 110 mãos absorvidas (cleanup wipe) | Filtro a corrigir | ~1-2h |
| Filtros derivados Estudo (HU/3-way/MW) | Pendente histórico | ~2h |
| Notas vilões — botão na vista mão Discord | Pendente histórico | ~1h |
| Suporte Winamax replayer HTML | 49/246 SSs falham | ~3-4h |

---

## 9. Conclusão do estado por pipeline

| Pipeline | Estado global |
|---|---|
| Discord (replayer + HH texto) | ✅ completo e validado (24/04 + 26/04 parte 1) |
| HM3 `.bat` | ✅ 3 bugs corrigidos (villains GG skip, auto-rematch HH→SS, ON CONFLICT preserve enrichment) |
| Import ZIP/TXT HH | ✅ funcional + origin reparado + auto-rematch Discord expandido |
| Upload manual SS | ⚠️ funcional mas `screenshot_url=NULL` (stub /tmp); UI mostra "Vision ainda não processou" por cache stale — cosmético |
| Anexos imagem ↔ mão (Bucket 1) | ⚠️ funcional e validado em BD; validação UI parcial (placeholders Discord não mostram CONTEXTO até HH chegar — gap conhecido, não bloqueante) |

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
