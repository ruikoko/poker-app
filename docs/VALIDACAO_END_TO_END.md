# Validação end-to-end — poker-app

**Última actualização:** 29 Abril 2026
**Âmbito:** mapa completo do estado de validação pós-sessões 23-24 Abr (4 bugs + wipe), 24 Abr (Discord workflow + GG anon Estudo + refactor Tags), 26 Abr (consolidação SSs + Bucket 1 anexos imagem), 27 Abr (verificação ponta-a-ponta dos 5 pipelines pós-Bucket 1), sessão Tech Debts 28-Abr (6 Tech Debts fechados + Tags default + re-arquitectura Vilões em 4 partes), sessão 29-Abr Tech Debt #8 (Uniformização HH em todos os componentes — fechado), Pipeline 1 verificação ponta-a-ponta (HM3) + Tech Debt #9 fechado (race condition cross-connection hm3+mtt) + 4 Tech Debts pendentes (#10/#11/#12/#13) + 1 nota explicativa (TZ display) **+ sessão 29-Abr pt3 (4 itens backlog fechados: #5 race latente mtt.py + #7 dead code HM3.jsx + #13a centralizar SITE_COLORS + #13b paleta unificada + filtros multi-select)**

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
| HM3 `.bat` (WN/PS/WPN/GG) | ✅ `origin='hm3'` | ✅ HH→SS auto-rematch (`072f57a`) | ✅ non-GG via VPIP/showdown; GG: skip puro (SS pipeline trata, fix `6aefc95`). **Validado 27-Abr Fase 5: 130 hands, 0 GG, 88 villain rows**. **28-Abr: refundido com regra A∨B∨C∨D + categoria via helper centralizado (`8ca3d88`)** |
| Discord (replayer / HH texto / image) | ✅ `origin='discord'` + `discord_tags`. Imagens directas (Bucket 1) NÃO criam mão. | ✅ SS→HH auto após Vision; 2ª entry duplicada agrega via `_link_second_discord_entry_to_existing_hand` (`f8a8238`) | ✅ regra A∨B∨C. **Validado 27-Abr Fase 2: 61 entries, 48 hands, 12 cross-posts agregados** |
| Upload manual SS | ✅ entry `source='screenshot', entry_type='screenshot'`; Vision processa, match_method correcto. **Validado 27-Abr Fase 6: 2 SSs Rui + 10 Karluz, 12 entries resolved** | ✅ match por TM | ⚠️ `screenshot_url=NULL` (stub `_upload_screenshot_to_storage` grava em /tmp ephemeral; `img_b64` servido via `/api/screenshots/image/{entry_id}` funciona como fallback) |
| Import ZIP/TXT HH | ✅ `origin='hh_import'` (fix `2844b94` + backfill 1146 mãos). **Validado 27-Abr Fase 4: 13737 mãos importadas, 48 placeholders Discord substituídos**. **28-Abr: entry meta-record marcada `resolved` após import bem-sucedido (`b233b9b`)** | ✅ auto-rematch SS→HH expandido para Discord `replayer_link`/`image` (`c452e12`) | ✅ |
| **Bucket 1 anexos imagem ↔ mão** | ✅ entries image NÃO criam hand; ligadas via `hand_attachments`. **Validado 27-Abr Fase 3: 4/4 imagens anexadas via `discord_channel_temporal`** | ✅ trigger Fase IV em `discord.py` + `hm3.py` + **`import_.py` (`b789c60`, Tech Debt #3 fechado 28-Abr)**; `discord.py` agora dispara T1+T2 (`eb00939`, Tech Debt #6 fechado 28-Abr) | n/a |

---

## 2. Match SS↔HH

| Cenário | Auto-dispara? | Validado? |
|---|---|---|
| SS chega primeiro, HH já existia | ✅ Vision dispara rematch | 23/04 + 27/04 Fase 6 (entries 92/93 anchors_stack_elimination_v2) |
| HH via import ZIP, SS Discord pendente | ✅ `import_.py:340-363` (replayer_link + image) | 23/04 (19 mãos) + 24/04 wipe (81/81) + **27/04 Fase 4 (48/48 placeholders Discord substituídos)** |
| HH via HM3 `.bat`, SS Discord pendente | ✅ `import_hm3` ganha bloco auto-rematch (`072f57a`) | 23-24/04 + 27/04 Fase 5 |
| HM3 import dispara worker anexos (Bucket 1) | ✅ `asyncio.create_task` em `import_hm3` (`06bbb9a`) | 26/04 + 27/04 Fase 5 (log `[import_hm3] attachments worker: 0 applied`) |
| `sync-and-process` Discord dispara worker anexos | ✅ T1 imediato + T2 delay 90s (`eb00939`, Tech Debt #6 fechado 28-Abr); idempotência via `_pending_image_entries` | 26/04 + 27/04 Fase 2 (4 applied) + 28/04 deploy live |
| **Karluz friend_alias hero** | ✅ `FRIEND_HEROES` reconhece como hero | **27/04 teste extra: 10 hands hero=Karluz, 0 cross-contamination** |
| `import_.py` dispara worker anexos retroactivo | ✅ **Tech Debt #3 fechado 28-Abr** (`b789c60`) — `asyncio.create_task` adicionado entre auto-rematch e response | 28/04 deploy live; CASCADE recovery real adiado para próximo import ZIP orgânico com placeholders pendentes |
| Forçar match bidireccional global | ✅ `/api/mtt/rematch` | 23/04 |
| Forçar match individual por SS | ✅ `/api/screenshot/orphans/{id}/rematch` | ❓ não testado explicitamente |
| Forçar match individual por HH | ❓ endpoint pode não existir | A verificar |
| 2ª entry Discord para mesmo TM | ✅ append idempotente `discord_tags` + condicional `_create_villains_for_hand` (`f8a8238`) | 24/04 + **27/04 Fase 2 (12 cross-posts em prod)** |

---

## 3. Persistência de metadados

| Comportamento | Estado |
|---|---|
| Placeholder Discord → HH real preserva metadados | ✅ fix `823a9f4` + NULLIF defensivo `7de889f` (descoberto pós-wipe que `ARRAY[]::text[] DEFAULT` não é NULL para COALESCE). **Re-validado 27-Abr Fase 4 (48/48 com discord_tags + screenshot_url + cross-posts preservados)** |
| `hand_villains` idempotente (ON CONFLICT) | ✅ fix `0b01d11` + UNIQUE composto `(hand_db_id, player_name, category)` (`8ca3d88`, 28-Abr) |
| `hand_villains` criado em rematch SS↔HH | ✅ fix `0b01d11` + backfill `af563a8` (44 mãos pós-wipe) + `ef1cb64` (32 mãos sessão 24/04) |
| `hand_villains` criado em HM3 `.bat` GG | ✅ skip puro em `_create_hand_villains_hm3` para GGPoker (SS pipeline trata) — fix `6aefc95` (preservado em `8ca3d88`) |
| `hand_villains` criado em HM3 `.bat` non-GG | ✅ via VPIP/showdown directo (`6aefc95`). **Validado 27-Abr Fase 5: 88 rows / 79 hands**. **28-Abr: refundido com helper centralizado A∨B∨C∨D (`8ca3d88`)** |
| `hand_villains` criado em upload manual SS | ✅ via path partilhado com `_enrich_hand_from_orphan_entry`. **Validado 27-Abr Fase 6: +2 villains** |
| Regra A∨B∨C∨D strictamente aplicada em villain creation | ✅ **Tech Debt #4 fechado 28-Abr** (`8ca3d88` + backfill + `c409677` + `bf75150` + `45051ec`) — helper `_classify_villain_categories` em `services/hand_service.py`; coluna `category TEXT` em `hand_villains` com CHECK `('sd','nota','friend')`; backfill 175 → 117 rows (49 sd + 54 nota + 0 friend nicks únicos = 91 únicos com 12 overlap) |
| ON CONFLICT preserva `all_players_actions` enriquecido (HM3 GG) | ✅ `CASE WHEN site='GGPoker' THEN COALESCE(...)` em `6aefc95` |
| Anexos imagem preservados em substituição placeholder→matched (sync_and_process / import_hm3) | ✅ trigger retroactivo Fase IV reanexa em milissegundos. **Validado 27-Abr Fase 4 + Recovery (4 attachments → 0 → 4 via re-sync)** |
| Anexos imagem preservados em substituição via `import_.py` (ZIP HH) | ✅ **Tech Debt #3 fechado 28-Abr** (`b789c60`) — trigger Fase IV adicionado |
| `entries` ZIP HH meta-record marcada `resolved` após import | ✅ **Tech Debt #7 fechado 28-Abr** (`b233b9b` + backfill SQL ad-hoc) — entries 90/91/104 actualizadas; novos imports marcam automaticamente |
| `hand_attachments.img_b64` para imagens Gyazo JPEG | ✅ **Tech Debt #2 fechado 28-Abr** (`9baec67` + backfill `att_id=8`) — helper Gyazo agora tenta `.png/.jpg/.gif`, retorna None em vez de fallback HTML silencioso |
| Helper `formatBB(bb)` global para arredondamento BB | ✅ **NOVO 29-Abr Tech Debt #8** (`38ae653`) — `lib/handParser.js` exporta helper canónico: inteiro `"Nbb"` / decimal `"N.Xbb"` (1 casa). Aplica-se em toda a app (HH, pots, dashboards, listas) |
| Helper `formatActionLabel(source, bb)` canónico (Fold/Check/calls/bets/raises/collected) | ✅ **NOVO 29-Abr Tech Debt #8** (`38ae653`) — produz strings canónicas conforme spec: `"Fold"`/`"Check"`/`"calls X (Ybb)"`/`"raises X to Y (Zbb)"`/`"collected X (Ybb)"` + sufixo `" (all-in)"`. 5 campos novos por step de acção populados em parseHH (aditivos, não breaking) |

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
| HAND HISTORY no detalhe usa nicks reais (não hashes) | ✅ **Tech Debt #5 fechado 28-Abr** (`400eb10` + `98330ec`) — backend pré-resolve hashes em campo `hand.raw_resolved`; 5 componentes consomem (`HandDetailPage`, modal Estudo `Hands.jsx`, `ReplayerPage`, `Replayer`, `HM3.jsx`); `hand.raw` original preservado para "Copiar HH" |
| Página Estudo aterra em vista por defeito | ✅ **NOVO 28-Abr** (`90a6205`) — default mudado de `'tournament'` para `'tags'`; sem persistência (consistente com restante app) |
| Página Vilões com tabs por categoria | ✅ **NOVO 28-Abr Tech Debt #4 Parte D** (`45051ec`) — 4 tabs (Todos / Mãos com SD default / Notas / Amigos) consumindo `/api/villains/categorized`; cores por sala; modal `VillainProfile` reusado via adapter |
| HandDetailPage (`/hand/:id`) renderiza HH em formato canónico | ✅ **NOVO 29-Abr Tech Debt #8 fechado** (`c3b3dbf`) — bloco MESA+ACÇÕES inline (~130 linhas) substituído por `<HandHistoryViewer hand={hand}/>`. Stacks `"X,XXX (Y BB)"` + posições antes do nick + acções canónicas + bloco SHOWDOWN dedicado |
| Modal Estudo (Hands.jsx) renderiza HH em formato canónico | ✅ **NOVO 29-Abr Tech Debt #8 fechado** (`c411a37`) — `<ParsedHandHistory>` + `parseRawHH` local (~340 linhas) substituídos por `<HandHistoryViewer hand={hand}/>`. Bug histórico do `seat_to_name` inexistente eliminado |
| Modal HM3 renderiza HH em formato canónico | ✅ **NOVO 29-Abr Tech Debt #8 fechado** (`1136e2b`) — `parseRawHH` local + bloco render inline (~270 linhas) substituídos por `<HandHistoryViewer hand={hand}/>` |
| Bloco MESA legacy duplicado removido (Hands.jsx + HM3.jsx) | ✅ **NOVO 29-Abr Tech Debt #8** — bloco IIFE "Players table" (~52 linhas em cada ficheiro) que duplicava MESA acima do `<HandHistoryViewer>`. Apagado em `Hands.jsx:579-630` (hotfix `b869c12`) e `HM3.jsx:299-349` (commit `1136e2b`) |

---

## 5. Funcionalidades específicas

| Feature | Estado |
|---|---|
| `/api/villains/search/hands` regra A∨B∨C | ✅ |
| `/api/villains/categorized` com filtros category+site+search+page | ✅ **NOVO 28-Abr Tech Debt #4 Parte C** (`c409677`) — devolve nick + sd_count + nota_count + friend_count + total_count + last_seen + sites + dates por nick único; legacy `/api/villains` intacto para housekeeping futuro |
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
| Triggers retroactivos `asyncio.create_task` em sync_and_process / import_hm3 / **import_.py** | ✅ 26/04 parte 2 (`06bbb9a`) **+ 28/04 cobertura `import_.py` (`b789c60`)** |
| Trigger Bucket 1 com retry T1+T2 (race condition Vision lenta) | ✅ **NOVO 28-Abr Tech Debt #6** (`eb00939`) — `discord.py:sync_and_process` agora dispara T1 imediato + T2 delay 90s; helper `_spawn_background()` mantém referência forte a tasks |
| Helper `_classify_villain_categories` (regras A∨B∨C∨D centralizadas) | ✅ **NOVO 28-Abr Tech Debt #4 Parte A** (`8ca3d88`) — função pura em `services/hand_service.py` partilhada por `mtt.py` e `hm3.py` |
| Helper `_resolve_hashes_in_raw` (backend pré-resolve hashes GG) | ✅ **NOVO 28-Abr Tech Debt #5** (`400eb10`) — função pura em `services/hand_service.py` consumida por `GET /api/hands/{id}` |
| Helper Gyazo com fallback `.png/.jpg/.gif` | ✅ **NOVO 28-Abr Tech Debt #2** (`9baec67`) — `attachments.py:_fetch_entry_image_bytes` itera extensões; sem silent fallback para HTML |
| UI ícone `HandRow` + secção CONTEXTO em `HandDetailPage` (Fase V) | ✅ 26/04 parte 2 (`a543629`) |
| **UI 📎 N + thumbnails 120px em PlaceholderHandRow** | ✅ **27/04 commit `a2ac5e5` (Tech Debt #1 fechado)** |
| Anexos imagem ↔ mão (Bucket 1) end-to-end | ✅ **27/04 Fase 3 + Recovery: 4/4 anexadas, validado em BD + UI** |
| **Friend_aliases robustos (Karluz não villain quando Rui hero, Rui não villain quando Karluz hero)** | ✅ **27/04 teste extra: 0 cross-contamination**. **28-Abr: FRIEND_HEROES (Karluz/flightrisk) agora INCLUÍDOS como villain com `category='friend'` quando aparecem em mãos do Rui** (`8ca3d88`) |
| Componente `PokerCard` partilhado (variantes sm/md/lg + faceDown) | ✅ **NOVO 29-Abr Tech Debt #8** (`870024e`) — `frontend/src/components/PokerCard.jsx`. Paleta polida red/blue/green/slate da HandDetailPage:15. Faceup placeholder `?`, faceDown gradient azul/púrpura. Consumido por `HandHistoryViewer`; consolidação dos 8 callers locais (HandRow/Dashboard/Discord/Hands/HM3/Tournaments/ReplayerPage/Replayer) fica como housekeeping futuro |
| Componente `HandHistoryViewer` (renderer único Mesa+Acções+Showdown) | ✅ **NOVO 29-Abr Tech Debt #8** (`a0903d8`) — `frontend/src/components/HandHistoryViewer.jsx`. Consome `parseHH` canónico + `formatBB` + `formatActionLabel` + `PokerCard` partilhado. Implementa toda a spec aprovada Rui (5 decisões + arredondamento BB) |
| Helper `formatBB(bb)` global | ✅ **NOVO 29-Abr Tech Debt #8** (`38ae653`) — exportado de `handParser.js`. Inteiro `"Nbb"` / decimal `"N.Xbb"` / null `""`. Aplicação em toda a app (HH, pots, dashboards, listas) |
| Helper `formatActionLabel(source, bb)` canónico | ✅ **NOVO 29-Abr Tech Debt #8** (`38ae653`) — exportado de `handParser.js`. Produz `"Fold"`/`"Check"`/`"calls X (Ybb)"`/`"raises X to Y (Zbb)"`/`"collected X (Ybb)"` + sufixo `" (all-in)"`. Aceita shape de step (parseHH) ou de action (parseStreetsForDisplay) |
| Hotfix MESA usa `startStack` em vez de `stack` (parseHH devolve pState mutado) | ✅ **NOVO 29-Abr Tech Debt #8 hotfix** (`b869c12`) — bug detectado por Rui em validação visual: jogador all-in aparecia com `"0 (0 BB)"` no MESA porque `parseHH` devolve `pState` (estado mutado) como `players`. Fix 1-line: `HandHistoryViewer.jsx:147` usa `p.startStack` (intacto desde init em parseHH:141) |

---

## 6. Pendentes por validar (prioridade decrescente)

1. **Verificação ponta-a-ponta dos 5 pipelines pós Tech Debts 28-29 Abr** — Pipeline 1 HM3 ✅ validado 29-Abr (Tech Debt #9 fechado). Pipelines 2-5 (Import ZIP / Discord sync / Upload manual SS / Bucket 1 retroactivo) por validar.
2. **Tech Debt #10 — bug parser truncamento nicks Winamax** (NOVO 29-Abr, **causa raiz CONFIRMADA pt3**) — Hand 102 (`la louffe`) e Hand 126 (`La m3nace`) confirmadas pelo Rui via SELECT raw HH. Padrão: nicks com espaço. Vector exacto: regex `hm3.py:688` non-greedy sem âncora forte (`r"^(.+?)(?::)?\s+(.+)$"`) + check `hm3.py:717` `"all-in" in action_text` (em vez de `startswith`). Linha disparadora típica: `"la louffe goes all-in 12000"` → actor="la", action_text contém "all-in" → INSERT espúrio. Severidade: Funcional. Esforço: ~1h fix + 10 min backfill SQL cleanup. **Pré-requisito:** decisão Rui Opção A defensiva (validar actor contra seats) vs B cirúrgica (regex com keyword poker).
3. **Tech Debt #11 — botão × eliminar villain de mão** (NOVO 29-Abr) — Pedido Rui durante verificação ponta-a-ponta. Use case: "na primeira mão temos 2 vilões associados, mas só quero tirar nota de um, a jogada só merece reparo num jogador, no outro foi standard". Spec aprovada: botão SÓ na página `/hand/X` (HandDetailPage), na secção MESA, apenas players que SÃO villains nesta mão. Apaga 1 row em `hand_villains` para `(hand_id, player_name)` directo sem confirmação. Pendente decisão técnica: comportamento em re-import (volta a criar villain? blacklist persistida?). Backend: endpoint `DELETE /api/hands/{hand_id}/villains/{player_name}`. Frontend: HandHistoryViewer.jsx — adicionar prop `deletable` + handler `onDeleteVillain`. Esforço: ~2h (Opção A) / ~3h (Opção B).
4. **Tech Debt #12 — re-arquitectura modal Vilões** (NOVO 29-Abr) — Pedido Rui sessão dedicada. Spec completa aprovada: layout (eliminar painéis Notas+Tags, alargar Mãos Comuns), lista colapsada (cards Hero NUNCA, cards villain entre data e pos só se reveladas, BB delta = lucro/perda do VILLAIN, posição villain vs Hero), mão expandida split 1/3 + 2/3 (MESA cronológica esquerda com ★ villain + HERO Hero; ACÇÕES 4 colunas Pre-flop/Flop/Turn/River com notação compacta F/x/C/b/R/3b/4b/AI em bbs, sem nicks, board cards no header). Severidade: UX major (re-arquitectura). Esforço: ~6-8h. Pendentes na implementação: heads-up edge cases, all-in pré-flop, paleta cor exacta destaque villain, decisão Rui acções repetidas concatenar vs última.
5. **Anomalia hand 253 — Upstakes_io villain `sd` sem cards revelados** (29-Abr) — Bug histórico no backfill Tech Debt #4 Parte B; helper `_classify_villain_categories` actual já filtra correctamente. Validação Opção A aprovada pt3: query SQL pós Pipelines 2-5 confirma 0 rows espúrios. Esforço: ~15 min validação SQL.
6. **Backfill estendido às 110 mãos absorvidas** — placeholders Discord que matcharam HHs reais perderam `discord_tags` antes do fix `7de889f`. Filtro precisa de incluir `entry_id IN (SELECT id FROM entries WHERE source='discord')` em vez de só `origin='discord'`. (anterior à sessão 27-Abr; pós-wipe da sessão 27-Abr o estado está limpo)
7. **Pesquisa MTT 10 dígitos numéricos → abrir modal mão directamente** (Opção A pré-aprovada 24/04, não implementada).
8. **Página Discord: agrupar por canal real** (`#nota`, `#pos-pko`, etc.) em vez de `#GGDiscord` + `#sem-tag` (detectado 24/04 PARTE 10, não atacado).
9. **Forçar match individual por HH** — confirmar se endpoint existe.
10. **Sessão B UI** (`position_parse_failed` com edição manual).
11. **Migração painel "SSs à espera" do Dashboard para Discord**.
12. **Housekeeping endpoint legacy `/api/villains`** — **BLOQUEADO POR Tech Debt #12** (modal Vilões re-arquitectado elimina painel Notas+Tags → endpoint legacy deixa de ter callers). Pós-#12 fica trivial (~30 min). Análise completa em `docs/analysis/PROXIMA_SESSAO_ANALISE.md`.
13. **Consolidação 9 PokerCard locais** (revisto pt3) — refactor opcional ~4-5h. `PokerCard.jsx` partilhado existe (commit `870024e`); 9 callers locais (HandRow/Dashboard/Discord/Hands/HM3/Tournaments/ReplayerPage/Replayer com RCard/HandDetailPage com RCard) ficam intactos. 6/9 são drop-in compatíveis; 1/9 idêntico (HandDetailPage); 2/9 com sizes custom (`board`/`xl` em ReplayerPage; 24×33 fixo em Dashboard).
14. **Tech Debt #13c — housekeeping aliases legacy** (NOVO pt3) — `siteColors.js` mantém aliases `SITE_COLORS_VILLAINS/_DASHBOARD/_HANDROW` apontando para `SITE_COLORS` por retrocompatibilidade da transição. Pós-paleta estabilizada, migrar 2 callers (`Dashboard.jsx`, `HandRow.jsx`) para import directo `SITE_COLORS` e remover aliases. Esforço: ~15 min.

---

## 7. Bugs conhecidos não corrigidos

### 7.1 Tech Debts da sessão 27-Abr (TODOS FECHADOS na sessão 28-Abr)

| # | Bug | Severidade | Status |
|---|---|---|---|
| 1 | PlaceholderHandRow não mostrava 📎 N nem thumbnails | UX | ✅ FECHADO 27-Abr commit `a2ac5e5` |
| 2 | `img_b64=NULL` silencioso quando Gyazo serve HTML em vez de imagem (padrão repete-se entries 17 e 31) | Cosmético | ✅ FECHADO 28-Abr commit `9baec67` + backfill `att_id=8` |
| 3 | `import_.py` (`POST /api/import` para ZIP HH) não tem trigger Fase IV | UX (auto-recoverável) | ✅ FECHADO 28-Abr commit `b789c60` |
| 4 | `_create_villains_for_hand` em `mtt.py` usa regra VPIP preflop legacy, não regra canónica A∨B∨C | Funcional / incoerência | ✅ FECHADO 28-Abr em 4 partes (`8ca3d88` + backfill SQL ad-hoc + `c409677` + `bf75150` + `45051ec`) |
| 5 | HandDetailPage mostra hashes GG (`89ef4cba: ...`) na secção HAND HISTORY em vez de nicks reais | Funcional grave | ✅ FECHADO 28-Abr commits `400eb10` (backend pré-resolve) + `98330ec` (follow-up 5 componentes cobertos) |
| 6 | Race condition trigger Bucket 1: `asyncio.sleep(10)` insuficiente para batch Vision >20 entries | UX | ✅ FECHADO 28-Abr commit `eb00939` (T1+T2 trigger) |
| 7 | 3 entries `hh_text/hand_history/new` com `raw_text=None` (entries 90, 91, 104) | Funcional (não-bloqueante) | ✅ FECHADO 28-Abr commit `b233b9b` + backfill SQL ad-hoc |

### 7.2 Bugs persistentes (UX/cosméticos pré-sessão 27-Abr)

| Letra | Bug | Severidade | Esforço |
|---|---|---|---|
| A | Pesquisa MTT 10 dígitos filtra torneio inteiro em vez de abrir modal mão (Opção A aprovada, código não escrito) | UX | ~30min |
| B | Página Discord agrupa por `#GGDiscord`/`#sem-tag` em vez de canais reais | UX | ~1h |
| C | `screenshot_url=NULL` em uploads manuais SS (stub `/tmp` ephemeral); `img_b64` via `/api/screenshots/image/{entry_id}` mitiga. **Confirmado 27-Abr Fase 6 (2/2 entries 92/93 com screenshot_url=NULL)** | Cosmético | ~1h |
| D | `channel_name` em `hand_attachments` é ID numérico, não nome resolvido — frontend mostra ID na metadata do thumbnail | Cosmético | ~30min |

**Os 4 bugs antigos da validação 22-23 Abr foram TODOS resolvidos** (Bug #1 GG villains via skip `6aefc95`; Bug #2 origin via `2844b94`; Bug #3 auto-rematch HM3 via `072f57a`; Bug #4 coluna TAGS via `e77b5cf`).

### 7.3 Tech Debt — sessão 28-Abr (FECHADO na sessão 29-Abr)

| # | Bug | Severidade | Status |
|---|---|---|---|
| 8 | **Uniformização HH em todos os componentes** — 3 parsers distintos com lógicas divergentes (descoberto durante investigação Tech Debt #5). Sub-problemas: (a) hashes GG resolvidos só onde `raw_resolved` é usado; (b) stacks/acções inconsistentes (fichas vs BB) entre vistas; (c) posições GG não enriquecidas em alguns paths; (d) cards de showdown apresentados diferentemente; (e) spec canónica única ainda por escrever. Parsers afectados: `frontend/src/lib/handParser.js:parseHH` (canónico), `frontend/src/pages/Hands.jsx:parseRawHH`, `frontend/src/pages/HM3.jsx:parseRawHH` | Funcional grave / arquitectural | ✅ **FECHADO 29-Abr** em 6 commits + 1 hotfix (`870024e` PokerCard + `38ae653` helpers + `a0903d8` HandHistoryViewer + `c3b3dbf` HandDetailPage + `c411a37` modal Estudo + `b869c12` hotfix startStack + `1136e2b` modal HM3). 1 parser canónico + 1 renderer único + 1 Card partilhado. Net -480 linhas no frontend. Replayer/ReplayerPage permanecem intactos por design. Detalhes completos em `docs/JOURNAL_2026-04-29.md` |

### 7.4 Tech Debts da sessão 29-Abr (continuação — Pipeline 1 verificação)

| # | Bug | Severidade | Status |
|---|---|---|---|
| 9 | **Race condition cross-connection em villain creation** — `hm3.py:_create_hand_villains_hm3` e `mtt.py:_create_villains_for_hand` usavam `_q()` (`app.db.query`) que abre conexão SEPARADA via `with get_conn() as conn`. PostgreSQL com isolation `read committed` não vê dados não-committed da conexão original. Durante batch import HM3 `.bat` (transação atómica que insere hand + chama villain creation antes do commit), a query `SELECT hm3_tags... FROM hands WHERE id=%s` retornava `[]` porque a hand recém-inserida ainda não estava visível na conexão separada. Consequência: `hand_meta = {}` → helper `_classify_villain_categories` devolvia `cats=[]` → INSERT skipped silenciosamente. Detectado em verificação ponta-a-ponta sessão 29-Abr: 159 hands HM3 importadas via `.bat`, 68 com `hm3_tags='nota%'`, mas `hand_villains=0`. | Funcional grave | ✅ **FECHADO 29-Abr** commit `630dc73` — substituir `_q()` por `cur.execute()` directo (hm3) e `with conn.cursor() as _cur` (mtt, preventivo). 4 linhas em `hm3.py:763-772` + 4 linhas em `mtt.py:660-668`. Validação: re-wipe + re-import → `hand_villains: 0 → 92` (66/68 mãos com nota-tag têm villain, 97% cobertura, 69 nicks únicos). Bug latente em `mtt.py:786` (outra função) **não corrigido** — registado como pendente §6 item 16. Detalhes em `docs/JOURNAL_2026-04-29-pt2.md` |

### 7.5 Tech Debts da sessão 29-Abr parte 3 (implementação backlog)

| # | Bug | Severidade | Status |
|---|---|---|---|
| 5 | **Bug latente `mtt.py:786` (`_create_ggpoker_villain_notes_for_hand`)** — mesmo padrão `_q()` cross-connection do Tech Debt #9. Função recebe `conn` como parâmetro mas usa `from app.db import query as _q` para ler `all_players_actions, raw FROM hands WHERE id=%s`. Não se manifesta em prod hoje porque os 3 call-sites (screenshot.py:1445 + mtt.py:1860/1993) passam por `_enrich_hand_from_orphan_entry` que faz commit intermédio. Risco: call-sites futuros podem não comitar antes. | Latente | ✅ **FECHADO 29-Abr pt3** commit `b85c974` — substituir `_q()` por `with conn.cursor() as _cur` na transacção activa. Mecanicamente idêntico ao Tech Debt #9. Comentário rastreável a `630dc73`. Detalhes em `docs/JOURNAL_2026-04-29-pt3.md` |
| 7 | **Dead code HM3.jsx** — `ACTION_COLORS` (linhas 27-34), `actionStyle()` (103-112), `ActionBadge()` (114-117). Confirmado dead via grep no projecto inteiro: zero callers fora destas linhas. Pré-existente à sessão 29-Abr Tech Debt #8; não removido nesse commit para limitar scope. | Cosmético | ✅ **FECHADO 29-Abr pt3** commit `b85c974` — apagados os 3 blocos (~24 linhas removidas). Sem outras alterações. Hands.jsx tem cópias suas que ainda usa internamente (analisar separadamente em #8). |
| 13 | **Paleta sites + filtros multi-select + landing tab Vilões** — 3 paletas distintas em `Villains.jsx`, `Dashboard.jsx`, `HandRow.jsx` (cada sala com cor diferente em cada ecrã). Spec aprovada: paleta unificada nova (Winamax vermelho / WPN verde / GG azul / PS amarelo) + landing default tab "Todos" + filtros multi-select com pills coloridas + persistência localStorage + 0 salas → página vazia. | UX | ✅ **FECHADO 29-Abr pt3** em 2 commits. **#13a** (`1698390`): centralizar 3 paletas em `lib/siteColors.js` preservando-as distintas + aliases `SITE_COLORS_VILLAINS/_DASHBOARD/_HANDROW`. Zero risco visual. **#13b** (`48a98d3`): unificar para 1 só `SITE_COLORS` (paleta nova) — aliases passam a apontar para a mesma const → mudança colateral em Dashboard/HandRow (efeito desejado). Backend `villains.py:/categorized` aceita CSV multi-site (`?site=Winamax,WPN`). Validação visual Rui em prod 9/9 OK. Detalhes em `docs/JOURNAL_2026-04-29-pt3.md` |

### Notas explicativas (não-bugs)

| Nota | Descrição |
|---|---|
| TZ display BD vs UI | `hands.played_at` é `timestamptz` armazenado em UTC (raw HH dos torneios usa UTC literalmente). Frontend `HandRow.jsx:131-139` converte para hora local do browser via `new Date(...).getHours()` — comentário no código confirma intenção: "para bater com as horas a que o utilizador jogou". Diferença típica visível ao utilizador português = +1h em DST Verão (UTC+1 Lisbon WEST) ou +0h em DST Inverno (UTC). Coerência: BD canónica em UTC (filtros `played_at >= '2026-01-01'`, comparações cross-TZ); UI Lisbon (relógio na mesa de jogo). Não é bug. |

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
| **Centralizar trigger Fase IV em `hand_service.py`** (em vez de duplicar em discord/hm3/import) | Padrão duplicado em 3 ficheiros pós-`b789c60`; refactor opcional | ~2h |
| **Housekeeping endpoint legacy `/api/villains`** | Substituído pelo `/categorized`; pode ser removido após Parte D estável | ~30min |
| **Persistência viewMode página Estudo (localStorage)** | Sem persistência hoje (default `'tags'`); follow-up trivial se necessário | ~5min |
| **Consolidação 8 PokerCard locais no partilhado** | `PokerCard.jsx` partilhado existe (29-Abr); 8 callers locais ficam intactos. Risco moderado em layouts estáveis | ~2h |
| **Limpeza dead code HM3.jsx** (`ACTION_COLORS`/`actionStyle`/`ActionBadge`) | Pré-existente à sessão 29-Abr | ~5min |

---

## 9. Conclusão do estado por pipeline

| Pipeline | Estado global |
|---|---|
| Discord (replayer + HH texto) | ✅ completo e validado (24/04 + 26/04 + 27/04 Fase 2: 61 entries, 12 cross-posts). **28/04 ganhou T1+T2 trigger anexos (Tech Debt #6)** |
| HM3 `.bat` | ✅ 3 bugs corrigidos (villains GG skip, auto-rematch HH→SS, ON CONFLICT preserve). **Re-validado 27/04 Fase 5 (130 hands, 88 villains, 0 GG)**. **28/04 villain creation refundido com regras A∨B∨C∨D + categoria** |
| Import ZIP/TXT HH | ✅ funcional + origin reparado + auto-rematch Discord expandido. **Re-validado 27/04 Fase 4 (13737 hands, 48/48 placeholders Discord substituídos)**. **28/04 ganhou trigger Bucket 1 (Tech Debt #3) + entry meta-record marcada `resolved` (Tech Debt #7)** |
| Upload manual SS | ✅ Promovido de ⚠️ para ✅ em 27/04 Fase 6 (2 SSs Rui + 10 Karluz, anchors_stack_elimination_v2 funcional). Bug C `screenshot_url=NULL` mitigado por endpoint `/api/screenshots/image/{entry_id}` |
| Anexos imagem ↔ mão (Bucket 1) | ✅ Promovido de ⚠️ para ✅ em 27/04 Fase 3 + Recovery (4/4 anexadas, trigger retroactivo funcional, validação BD + UI). **28/04 Tech Debt #2 fechado (Gyazo JPEG fix + backfill `att_id=8`)** |

⚠️ **Verificação ponta-a-ponta pós Tech Debts 28-29 Abr pendente** — validar via fluxo orgânico que todos os fixes funcionam end-to-end. Decisão Rui: pausar sem fazer, fica para sessão dedicada futura.

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
| `b55a822` | docs(verification): sessão 27-Abr fecho — 5 pipelines validados ponta-a-ponta |

### Sessão 28 Abril (Tech Debts + Tags + Vilões)

| Commit | Descrição |
|---|---|
| `b789c60` | feat(attachments): import_.py dispara trigger Bucket 1 Fase IV (Tech Debt #3) |
| `eb00939` | fix(attachments): trigger Bucket 1 dispara 2x para cobrir Vision lenta (Tech Debt #6) |
| `b233b9b` | fix(import): marcar entry meta-record ZIP como resolved após import (Tech Debt #7) |
| `9baec67` | fix(attachments): tentar .png/.jpg/.gif para imagens Gyazo (Tech Debt #2) |
| `400eb10` | fix(hands): backend pré-resolve hashes GG anonimizados no raw HH (Tech Debt #5) |
| `98330ec` | fix(hands): aplicar raw_resolved em todos os consumidores de HH (Tech Debt #5 follow-up) |
| `90a6205` | feat(estudo): página Estudo aterra em vista 'Por Tags' por defeito |
| `8ca3d88` | feat(villains): refundir _create_villains_for_hand com regras canónicas A∨B∨C∨D + categoria (Tech Debt #4 parte A) |
| `c409677` | feat(villains): endpoint /api/villains/categorized aceita filter ?category= (Tech Debt #4 parte C) |
| `bf75150` | chore(villains): remover migration legacy do índice UNIQUE antigo |
| `45051ec` | feat(villains): página Vilões com 4 sub-secções + filtro sala (Tech Debt #4 parte D) |
| `127b47a` | docs(verification): sessão 28-Abr fecho — 6 Tech Debts fechados + re-arquitectura Vilões |

### Sessão 29 Abril (Tech Debt #8 — Uniformização HH)

| Commit | Descrição |
|---|---|
| `870024e` | feat(hh): novo componente PokerCard partilhado (Tech Debt #8 commit 1/6) |
| `38ae653` | feat(hh): helpers formatBB + formatActionLabel canónicos em handParser.js (Tech Debt #8 commit 2/6) |
| `a0903d8` | feat(hh): novo componente HandHistoryViewer (Tech Debt #8 commit 3/6) |
| `c3b3dbf` | refactor(hh): HandDetailPage usa HandHistoryViewer (Tech Debt #8 commit 4/6) |
| `c411a37` | refactor(hh): modal Estudo usa HandHistoryViewer + remove parser local (Tech Debt #8 commit 5/6) |
| `b869c12` | fix(hh): MESA mostra startStack em vez de stack final + remove bloco legacy duplicado (Tech Debt #8 hotfix) |
| `1136e2b` | refactor(hh): modal HM3 usa HandHistoryViewer + remove parser local + bloco legacy (Tech Debt #8 commit 6/6 + final) |
| `d12d7a5` | docs(verification): sessão 29-Abr fecho — Tech Debt #8 (Uniformização HH) fechado em pleno |

### Sessão 29 Abril continuação (Pipeline 1 verificação + Tech Debt #9)

| Commit | Descrição |
|---|---|
| `630dc73` | fix(villains): hm3+mtt usam transação actual em vez de conexão nova para ler hand_meta (Tech Debt #9) |
| `66e91e6` | docs(verification): sessão 29-Abr continuação — Pipeline 1 fechado + Tech Debt #9 + 4 pendentes registados |

### Sessão 29 Abril parte 3 (backlog fechado — 4 itens)

| Commit | Descrição |
|---|---|
| `efdb348` | docs(analysis): análise quick scan dos 9 itens em backlog para próximas sessões |
| `b85c974` | fix(villains): corrigir race condition latente em _create_ggpoker_villain_notes_for_hand + remover dead code HM3.jsx (Tech Debts #5 + #7) |
| `1698390` | refactor(theme): centralizar SITE_COLORS em lib/siteColors.js (Tech Debt #13a) |
| `48a98d3` | feat(villains): paleta unificada + filtros multi-select por sala (Tech Debt #13b) |
| _[a gerar]_ | docs(verification): sessão 29-Abr pt3 fecho — 4 itens backlog fechados (#5/#7/#13a/#13b) |
