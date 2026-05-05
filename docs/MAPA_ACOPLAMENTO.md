# MAPA DE ACOPLAMENTO

> **Atenção:** este documento tem aditamentos posteriores na §8.5 ("Aditamentos pós-26-Abr-2026"). Antes de tratar conteúdo das §§2-8 como definitivo, verifica se há evolução documentada lá.

Documento permanente que mapeia, para cada conceito-chave da app, **quem o produz**, **quem o consome** e **o que acontece quando muda**. Pensado para duas audiências:

1. **Rui (product owner, noob em código):** decidir mudanças sabendo o impacto sem ter de simular consequências na cabeça.
2. **Claude novo, em sessões futuras:** ler antes de tocar em código para não partir invariantes.

Última actualização: 2026-04-26.

---

## Índice

- [1. Como ler este documento](#1-como-ler-este-documento)
- [2. Estado / marcação de mãos](#2-estado--marcação-de-mãos)
  - [2.1 `match_method`](#21-match_method)
  - [2.2 `origin`](#22-origin)
  - [2.3 `hm3_tags`](#23-hm3_tags)
  - [2.4 `discord_tags`](#24-discord_tags)
  - [2.5 `tags`](#25-tags)
  - [2.6 `screenshot_url`](#26-screenshot_url)
  - [2.7 `study_state`](#27-study_state)
  - [2.8 `has_showdown`](#28-has_showdown)  *(adicionado ao índice)*
  - [2.9 `position_parse_failed`](#29-position_parse_failed)  *(adicionado ao índice)*
  - [2.10 `tournament_format` / `tournament_name` / `tournament_number` / `buy_in`](#210-tournament_format--tournament_name--tournament_number--buy_in)  *(adicionado ao índice)*
  - [2.11 `hand_attachments`](#211-hand_attachments)  *(adicionado pós-Bucket 1)*
- [3. Estado / marcação de entries](#3-estado--marcação-de-entries)
  - [3.1 `entry_type`](#31-entry_type)
  - [3.2 `source`](#32-source)
  - [3.3 `status`](#33-status)
  - [3.4 `raw_json` — keys críticas](#34-raw_json--keys-críticas)
- [4. Conceitos de origem (heros)](#4-conceitos-de-origem-heros)
  - [4.1 `HERO_NAMES` (Rui)](#41-hero_names-rui)
  - [4.2 `FRIEND_HEROES` (Karluz, flightrisk)](#42-friend_heroes-karluz-flightrisk)
  - [4.3 `HERO_NAMES_ALL` (união)](#43-hero_names_all-união)
  - [4.4 `HERO_NICKS_BY_SITE` / `FRIEND_NICKS_BY_SITE` / `ALL_NICKS_BY_SITE`](#44-hero_nicks_by_site--friend_nicks_by_site--all_nicks_by_site)
  - [4.5 `FRIEND_NICKS`](#45-friend_nicks)
- [5. Pipelines de ingest](#5-pipelines-de-ingest)
  - [5.1 `hh_import` (POST `/api/import` — ZIP/TXT HH)](#51-hh_import-post-apiimport--ziptxt-hh)
  - [5.2 `hm3` (POST `/api/hm3/import` — CSV)](#52-hm3-post-apihm3import--csv)
  - [5.3 `discord` (bot via POST `/api/discord/sync-and-process`)](#53-discord-bot-via-post-apidiscordsync-and-process)
  - [5.4 `ss_upload` (POST `/api/screenshots` — drag-and-drop UI)](#54-ss_upload-post-apiscreenshots--drag-and-drop-ui)
- [6. Visualização / filtros por página](#6-visualização--filtros-por-página)
  - [6.1 Estudo (`Hands.jsx`)](#61-estudo-handsjsx)
  - [6.2 Dashboard](#62-dashboard)
  - [6.3 Vilões (regras A∨B∨C)](#63-vilões-regras-abc)
  - [6.4 Discord](#64-discord)
  - [6.5 Torneios (GG: Com SS / Sem SS; HM3 tab)](#65-torneios-gg-com-ss--sem-ss-hm3-tab)
  - [6.6 HM3](#66-hm3)
  - [6.7 MTT > GG](#67-mtt--gg)
- [7. Regras de negócio transversais](#7-regras-de-negócio-transversais)
  - [7.1 Barreira pre-2026 (`is_pre_2026`)](#71-barreira-pre-2026-is_pre_2026)
  - [7.2 Auto-rematch retroactivo](#72-auto-rematch-retroactivo)
  - [7.3 `_link_second_discord_entry_to_existing_hand`](#73-_link_second_discord_entry_to_existing_hand)
  - [7.4 `apply_villain_rules` — função canónica](#74-apply_villain_rules--função-canónica)
  - [7.5 Call sites de `apply_villain_rules`](#75-call-sites-de-apply_villain_rules)
  - [7.6 `_create_placeholder_if_needed`](#76-_create_placeholder_if_needed)
  - [7.7 `_insert_hand` placeholder upgrade](#77-_insert_hand-placeholder-upgrade)
  - [7.8 `ON CONFLICT (discord_message_id) DO NOTHING`](#78-on-conflict-discord_message_id-do-nothing)
- [8. Artefactos de BD críticos](#8-artefactos-de-bd-críticos)
  - [8.1 Índices UNIQUE](#81-índices-unique)
  - [8.2 Tabelas que NUNCA são truncadas em reset](#82-tabelas-que-nunca-são-truncadas-em-reset)
- [9. Como manter este documento](#9-como-manter-este-documento)

---

## 1. Como ler este documento

Cada entrada tem o mesmo esqueleto:

- **Em linguagem simples:** uma frase curta, sem jargão.
- **O que é (humano):** um ou dois parágrafos a explicar para quê serve.
- **Detalhes (técnico):** tabelas Produzido / Consumido + valores possíveis.
- **Comportamento esperado quando muda:** o que ripple-out o sistema faz quando o valor é escrito/alterado.
- **Armadilhas conhecidas:** bugs já apanhados, ou cantos onde é fácil quebrar invariantes (omitido se não houver).
- **Quando alguém pergunta...:** FAQ adaptada ao conceito.
- **Cross-references:** outros conceitos aqui ligados.

Notação:

- `backend/app/...:linha` é um link que pode ser aberto no editor.
- “(localização aproximada — verificar)” marca posições derivadas indirectamente; conferir antes de editar.
- Quando este documento e o código discordarem, **o código ganha** — actualizar este documento na mesma sessão.

---

## 2. Estado / marcação de mãos

A tabela `hands` é o esqueleto da app. Cada linha cobre um momento de jogo. O que distingue uma da outra são marcadores escritos por diferentes pipelines em colunas diferentes — esta secção descreve cada marcador.

### 2.1 `match_method`

**Em linguagem simples:** rótulo que diz "como sabemos os nomes reais dos jogadores nesta mão".

**O que é (humano):** As mãos GGPoker chegam anonimizadas (jogadores aparecem como hashes tipo `89ef4cba`). Para saber os nicks reais usamos screenshots cruzados via Vision. O `match_method` regista qual pipeline produziu o cruzamento — útil para distinguir "dados Vision válidos" de "ainda à espera". Vive dentro de `hands.player_names ->> 'match_method'` (JSONB), não numa coluna própria.

**Detalhes (técnico):**

| Onde é produzido | Função |
|---|---|
| `backend/app/routers/screenshot.py:1322` | `_enrich_hand_from_orphan_entry` → escreve `"anchors_stack_elimination_v2"` |
| `backend/app/routers/screenshot.py:1102` | `_create_placeholder_if_needed` → escreve `"discord_placeholder_no_hh"` |
| `backend/app/routers/discord.py:652` | `backfill_ggdiscord` → escreve `"discord_placeholder_no_hh_backfill"` |
| `backend/app/routers/mtt.py:873` | `_promote_to_study` → escreve `"mtt_promote_v2"` |
| `backend/app/routers/mtt.py:1077` | `import_mtt` → escreve `"mtt_import_v3"` |
| `backend/app/routers/hands.py:1537` | `admin_refix_anonmap_execute` → escreve `"anchors_stack_elimination_v2_refix"` |
| `backend/app/services/hand_service.py:82` | `_insert_hand` placeholder upgrade → promove `discord_placeholder_*` para `"anchors_stack_elimination_v2"` quando há HH real e Vision data |

| Onde é consumido | Função |
|---|---|
| `backend/app/routers/hands.py:307` (filtro `STUDY_VIEW_GG_MATCH_FILTER`) | Página Estudo exclui GG sem `match_method` ou com `discord_placeholder_*` |
| `backend/app/routers/hands.py:611` (`/hands/stats` recent) | Excluir GG anonimizadas dos "últimos importados" |
| `backend/app/routers/hands.py:619` (`hand_stats`) | "GG sem match" não conta para o painel principal |
| `backend/app/routers/hands.py:670` (`/hands/ss-match-pending`) | Filtra placeholders `ss_upload` ainda sem HH |
| `backend/app/routers/villains.py:75-82` (`VILLAIN_ELIGIBILITY_CONDITION`) | Regras B e C exigem `match_method` populado |
| `backend/app/routers/mtt.py:1211, 1224, 1347, 1352` | Aba "Com SS" / "Sem SS" do MTT > GG |
| `backend/app/routers/screenshot.py:962` | Auto-rematch decide quando enriquecer |

| Valor | Significado |
|---|---|
| `null` | Mão GGPoker anonimizada sem qualquer cruzamento; ou mão de PS/WN/WPN (nicks vêm do raw, não precisa). |
| `anchors_stack_elimination_v2` | Match real: Vision deu nicks + cruzou com HH via stacks/eliminação. |
| `anchors_stack_elimination_v2_refix` | Reaplicação do match após bug do anon-map (42 mãos refixadas). |
| `mtt_promote_v2` | Promoção via fluxo MTT (`_promote_to_study`). |
| `mtt_import_v3` | Match feito durante `import_mtt`. |
| `discord_placeholder_no_hh` | Placeholder criado por SS Discord/upload sem HH ainda — não é match real. |
| `discord_placeholder_no_hh_backfill` | Idem mas via `/api/discord/backfill-ggdiscord`. |

**Comportamento esperado quando muda:**

- `null` → `anchors_stack_elimination_v2` ou `mtt_*`: mão entra automaticamente em Estudo (filtro `STUDY_VIEW_GG_MATCH_FILTER` deixa de a excluir) e fica elegível para regras B/C de villains.
- `discord_placeholder_*` → `anchors_stack_elimination_v2`: o `_insert_hand` (services/hand_service.py:82) faz a transição quando a HH real chega; placeholder é apagado e dados Vision (`players_list`) preservados.
- Se mudar para `discord_placeholder_*`: a mão **sai** da Estudo até a HH chegar.

**Armadilhas conhecidas:**

- 42 mãos GG ficaram com o `_meta` (bb/sb/ante) trocado com a chave de um nick por um bug iterativo em `_build_anon_to_real_map`. Detector e fix em `backend/app/routers/hands.py:1149` (`/admin/scope-anonmap-bug`) e `:1430` (`/admin/refix-anonmap-bug`).
- Invariante GG anonimizada coberto em `apply_villain_rules` linhas 73-76 (`services/villain_rules.py`): `site=GGPoker AND (match_method missing OR placeholder)` retorna `skipped_reason='gg_anon_no_match'`. Substitui o guard antigo do extinto `_create_hand_villains_hm3`. Não tirar.

**Quando alguém pergunta...**

- *"Porque é que esta mão GG não aparece em Estudo?"* → Provavelmente `match_method` é `null` ou começa por `discord_placeholder_`. Verificar `SELECT player_names ->> 'match_method' FROM hands WHERE id = ?`.
- *"Posso usar isto como flag de 'tem screenshot'?"* → Não exactamente. `screenshot_url` indica que existe o ficheiro. `match_method` indica que o cruzamento Vision↔HH **foi feito**.
- *"Quando a HH chega depois do SS, como é que o placeholder é substituído?"* → `_insert_hand` (services/hand_service.py:64) detecta o placeholder, captura metadados, faz DELETE+INSERT, depois UPDATE para reaplicar `origin`/`discord_tags`/`hm3_tags`/`entry_id`/`screenshot_url`/`player_names` e promover `match_method` para `anchors_stack_elimination_v2`.

**Cross-references:** [`origin`](#22-origin), [`screenshot_url`](#26-screenshot_url), [`_insert_hand` placeholder upgrade](#77-_insert_hand-placeholder-upgrade), [Vilões (regras A∨B∨C)](#63-vilões-regras-abc).

---

### 2.2 `origin`

**Em linguagem simples:** etiqueta a dizer "por que porta esta mão entrou na app".

**O que é (humano):** Coluna `TEXT` (sem CHECK constraint) que regista a fonte primária de cada mão. Existem 4 portas de entrada: HM3 (.bat), Discord (bot), upload manual de SS (UI), import de ZIP/TXT HH. O valor escrito é o do **primeiro ingress** — outras fontes adicionais ficam rastreadas via `discord_tags` / `hm3_tags`.

**Detalhes (técnico):**

| Onde é produzido | Função | Valor escrito |
|---|---|---|
| `backend/app/routers/hands.py:90` | `ensure_origin_column` | (cria coluna sem default) |
| `backend/app/routers/hm3.py:1074` | `import_hm3` (INSERT) | `'hm3'` |
| `backend/app/routers/hm3.py:1096` | `import_hm3` (ON CONFLICT) | `COALESCE(hands.origin, EXCLUDED.origin)` (preserva primeiro ingress) |
| `backend/app/routers/import_.py:311, 335` | `import_file` (HH ZIP/TXT) | `'hh_import'` |
| `backend/app/routers/screenshot.py:1141` | `_create_placeholder_if_needed` | `'discord'` (Discord) ou `'ss_upload'` (UI) |
| `backend/app/routers/discord.py:686` | `backfill_ggdiscord` | `'discord'` (literal) |
| `backend/app/discord_bot.py:252` | `_apply_channel_tags` | `COALESCE(origin, 'discord')` (só escreve se NULL) |
| `backend/app/services/hand_service.py:173` | `_insert_hand` (placeholder upgrade UPDATE) | `COALESCE(%(origin)s, origin)` (reverse: preserva placeholder origin sobre o INSERT) |

| Onde é consumido | Função |
|---|---|
| `backend/app/routers/hands.py:670` (`/hands/ss-match-pending`) | Filtra `origin = 'ss_upload'` para painel SSMatch |
| `backend/app/routers/hm3.py:1346-1356` (`/hm3/admin/audit-discord-state`) | Audita distribuição de origens em 2026+ |
| `backend/app/routers/hm3.py:1397` (índice `idx_hands_origin`) | Aceleração GROUP BY |
| Frontend não consome directamente; é metadata interna. |  |

| Valor | Significado |
|---|---|
| `'hm3'` | Veio do script `.bat` que lê BD do HM3 e faz POST. |
| `'discord'` | Bot Discord criou via sync ou placeholder. |
| `'ss_upload'` | Drag-and-drop de screenshot na UI. |
| `'hh_import'` | Upload manual de ZIP/TXT HH. |
| `null` | Mão legacy criada antes da coluna existir, ou path admin que não escreveu. |

**Comportamento esperado quando muda:**

- O valor é gravado **uma vez no primeiro ingress** e preservado por COALESCE. Não muda em sequência normal.
- Excepção: `_insert_hand` placeholder upgrade tem reverse-COALESCE — se um placeholder Discord (`origin='discord'`) é apagado para inserir a HH real (`hh_import`), o UPDATE pós-INSERT restaura `'discord'` para que o primeiro ingress mantenha autoridade.

**Armadilhas conhecidas:**

- Não há CHECK constraint, e o frontend nunca lê esta coluna directamente — typos não são detectados. Validação vive na lógica de aplicação.
- O bug audit em `/hm3/admin/audit-discord-state` mostrou que `discord` deveria existir no count mas o pipeline antigo não o escrevia. Resolvido com `_apply_channel_tags` e os placeholders.

**Quando alguém pergunta...**

- *"Como sei que esta mão veio do bot Discord?"* → `WHERE origin = 'discord'` (ou `entries.source = 'discord' WHERE entries.id = hands.entry_id`).
- *"Posso filtrar por origem na UI?"* → Hoje não: a UI só filtra por `study_state` / `hm3_tags` / `discord_tags`. Adicionar filtro por origin é trivial mas não foi pedido.
- *"E se a mesma mão vier do Discord e depois do HM3?"* → O `_apply_channel_tags` faz `COALESCE(origin, 'discord')` (só escreve se NULL). O HM3 também faz `COALESCE`. Quem chegar primeiro fica como origin; restantes ficam tracked via `discord_tags`/`hm3_tags`.

**Cross-references:** [`hm3_tags`](#23-hm3_tags), [`discord_tags`](#24-discord_tags), [Pipelines de ingest](#5-pipelines-de-ingest), [`_insert_hand` placeholder upgrade](#77-_insert_hand-placeholder-upgrade).

---

### 2.3 `hm3_tags`

**Em linguagem simples:** lista das etiquetas reais que o Rui pôs na mão dentro do Holdem Manager 3.

**O que é (humano):** O Rui usa o HM3 para classificar mãos durante/após sessão (ex: "nota++", "ICM PKO", "RFI PKO+"). Estas tags são puxadas via script `.bat` para a coluna `hands.hm3_tags TEXT[]`. Separadas das `tags` auto-geradas (showdown, nicks de vilões) — `hm3_tags` representa intenção humana de estudo, `tags` é metadata derivada do parser. A lista canónica está em `backend/app/routers/hands.py:200` (`HM3_REAL_TAGS`, 73 entradas).

**Detalhes (técnico):**

| Onde é produzido | Função |
|---|---|
| `backend/app/routers/hands.py:15` | `ensure_hm3_tags_column` cria coluna + índice GIN |
| `backend/app/routers/hm3.py:1077, 1094-1097` | `import_hm3` faz INSERT com `hm3_tags = hm3_tags_clean` (tags HM3 limpas) |
| `backend/app/routers/hm3.py:954, 992` | `import_hm3` (UPDATE existing) faz `merged_hm3 = list(set(existing_hm3 + hm3_tags_clean))` |
| `backend/app/routers/mtt.py:837, 909` | `_promote_to_study` e `import_mtt` escrevem `['GG Hands']` |
| `backend/app/routers/discord.py:694` | `backfill_ggdiscord` escreve `['GGDiscord']` (marker placeholder) |
| `backend/app/routers/screenshot.py:1143` | `_create_placeholder_if_needed` escreve `['GGDiscord']` para placeholders Discord |
| `backend/app/services/hand_service.py:182-185` | `_insert_hand` aplica `array_remove(..., 'GGDiscord')` ao reaplicar metadados — strip do marker interno |
| `backend/app/routers/hands.py:1097` | `/admin/migrate-hm3-tags` (one-shot) separa `tags` em `hm3_tags` retroactivamente |
| Frontend `frontend/src/components/TagEditor.jsx` (via PATCH `/api/hands/{id}`) | Editor manual em Hands.jsx |

| Onde é consumido | Função |
|---|---|
| `backend/app/routers/hands.py:341, 522, 527, 539` | Filtros `hm3_tag=...`, agrupamento `tag_source='auto'/'hm3'`, queries de listagem |
| `backend/app/routers/villains.py:71-73` | Regra A do `VILLAIN_ELIGIBILITY_CONDITION`: `hm3_tags ~ 'nota%'` |
| `backend/app/routers/hands.py:651` | `/hands/stats` conta `'GGDiscord' = ANY(hm3_tags)` para `orphan_screenshots` |
| `backend/app/routers/entries.py:84` | `entry_delete` apaga mãos com `'GGDiscord' = ANY(hm3_tags)` (placeholders) |
| `backend/app/routers/discord.py:751` | `fix_ggdiscord_played_at` filtra por `'GGDiscord' = ANY(hm3_tags)` |
| `backend/app/routers/mtt.py:982-996` | `import_mtt` detecta placeholder por `'GGDiscord' in hm3_tags` antes de DELETE |
| `frontend/src/pages/Dashboard.jsx:278-323` | Mostra `hm3_tags` como chips na lista recente |
| `frontend/src/pages/HM3.jsx:605` | Agrega contagens por tag HM3 |
| `frontend/src/components/HandRow.jsx:311` | Editor inline de `hm3_tags` |

| Valor (exemplos) | Significado |
|---|---|
| `nota`, `nota++`, `nota ex` | Marca para estudo de villain — dispara regra A. Lista canónica em `HM3_REAL_TAGS` ids 7, 8, 81. |
| `For Review`, `ICM`, `ICM PKO`, `MW PKO`, `bvB pre`, ... | Etiquetas temáticas de estudo. Ver `HM3_REAL_TAGS`. |
| `GGDiscord` | **Marker interno**: identifica placeholder Discord sem HH. Deve ser removido quando a HH chegar (feito automaticamente em `_insert_hand`). |
| `GG Hands` | Marca mão GGPoker promovida via fluxo MTT (`_promote_to_study` / `import_mtt`). |

**Comportamento esperado quando muda:**

- Adicionar `nota*`: torna a mão elegível para regra A de villains (ver `villains.py:71`). Após PATCH manual, correr `/api/villains/recalculate-hands` para refrescar `hands_seen`.
- Remover `GGDiscord`: aciona o `array_remove` em `_insert_hand`; sinaliza que o placeholder foi substituído pela HH real.
- Adicionar tag não-HM3 (ex: `'showdown'` que pertence a `tags`): o backend não bloqueia, mas vai aparecer em filtros/groupings de `hm3_tags` — verificar `HM3_REAL_TAG_NAMES` antes de adicionar tag nova.

**Armadilhas conhecidas:**

- A coluna `tags` (auto) e `hm3_tags` (humano) eram colunas misturadas no início. A migração `/admin/migrate-hm3-tags` separou-as. Mãos legacy podem ter `hm3_tags = NULL` mesmo com tags reais — verificar se a migração foi corrida em produção.
- O marker `GGDiscord` em `hm3_tags` **não** deve aparecer numa mão "real" — é só placeholder. Se aparecer, é porque o placeholder upgrade não rolou.
- HM3 só puxa tags activas para a mão — apagar uma tag no HM3 não apaga em PG. Há um `re_parse_all_hands` em `hm3.py:1597` que pode ajudar mas não é chamado automaticamente.

**Quando alguém pergunta...**

- *"Onde é a single source of truth da lista de tags HM3?"* → `HM3_REAL_TAGS` em `backend/app/routers/hands.py:200`. Sincronizado com a BD do HM3 via scan directo a `handmarkcategories`.
- *"Posso adicionar uma tag nova manualmente?"* → Sim via PATCH `/api/hands/{id}` (`backend/app/routers/hands.py:743`), mas `HM3_REAL_TAG_NAMES` não vai reconhecer — vai cair em `tags` se vier por `/admin/migrate-hm3-tags`.
- *"Porque é que `'GGDiscord'` aparece em `hm3_tags`?"* → Marker interno do placeholder — não tag de estudo. É apagado pelo `_insert_hand` ao substituir o placeholder.

**Cross-references:** [`tags`](#25-tags), [`discord_tags`](#24-discord_tags), [Vilões (regras A∨B∨C)](#63-vilões-regras-abc), [`_insert_hand` placeholder upgrade](#77-_insert_hand-placeholder-upgrade).

---

### 2.4 `discord_tags`

**Em linguagem simples:** lista dos canais Discord onde esta mão foi partilhada.

**O que é (humano):** Coluna `TEXT[] DEFAULT ARRAY[]::text[]`. Quando o bot Discord puxa uma mensagem de um canal monitorizado, o nome bruto do canal é acrescentado a `discord_tags` da mão correspondente. Crucial para regra C de villains (canal `'nota'` ⇒ villain elegível). Diferente de `tags` (que recebe o split-por-hifen do canal, ex: `'icm-pko'` → `['icm','pko']`); `discord_tags` mantém o nome bruto, ex: `['icm-pko']`.

**Detalhes (técnico):**

| Onde é produzido | Função |
|---|---|
| `backend/app/routers/hands.py:64` | `ensure_discord_tags_column` cria coluna + índice GIN |
| `backend/app/discord_bot.py:243-256` | `_apply_channel_tags` faz append idempotente do nome bruto via `ARRAY(SELECT DISTINCT unnest(...))` |
| `backend/app/routers/screenshot.py:809-817, 1380` | `_link_second_discord_entry_to_existing_hand` e `_enrich_hand_from_orphan_entry` fazem append do canal resolvido |
| `backend/app/routers/discord.py:699` | `backfill_ggdiscord` escreve canal resolvido na criação de placeholder |
| `backend/app/routers/screenshot.py:1133-1138` | `_create_placeholder_if_needed` resolve canal e escreve no INSERT |
| `backend/app/services/hand_service.py:178` | `_insert_hand` placeholder upgrade preserva `discord_tags` via `COALESCE(NULLIF(discord_tags, ARRAY[]::text[]), ...)` |

| Onde é consumido | Função |
|---|---|
| `backend/app/routers/hands.py:348, 522, 527, 539` | Filtro `discord_tag=...`, agrupamento `tag_source='auto'/'discord'` |
| `backend/app/routers/villains.py:79-82` | Regra C: `'nota' = ANY(COALESCE(h.discord_tags, '{}'))` |
| `backend/app/routers/hm3.py:1361-1364` | Audit distribuição |
| `backend/app/routers/screenshot.py:855` | Trigger regra C ao linkar 2ª entry |
| `frontend/src/components/HandRow.jsx:275-302` | Mostra como chips read-only na lista |
| `frontend/src/pages/Discord.jsx:312` | Agrupa mãos da página Discord por canal |

| Valor (exemplos) | Significado |
|---|---|
| `[]` (default) | Mão nunca foi partilhada em canal Discord monitorizado. |
| `['nota']` | Partilhada no canal `#nota` (ID 1410311700023869522) — gatilho da regra C de villains. |
| `['icm-pko', 'pko-pos']` | Partilhada em múltiplos canais. |
| `null` | Mão muito antiga, antes da coluna existir — interpretar como `[]`. |

**Comportamento esperado quando muda:**

- Adicionar `'nota'` a uma mão com `match_method` populado: passa a cumprir regra C. `recalculate-hands` actualiza counters de villains.
- Remover canal: write idempotente via `array_remove` (não usado actualmente — só append).
- O write é sempre **append**, nunca overwrite. `DISTINCT unnest` garante deduplicação.

**Armadilhas conhecidas:**

- Schema default é `ARRAY[]::text[]` (empty) **não** NULL. Por isso `_insert_hand` usa `NULLIF(discord_tags, ARRAY[]::text[])` antes do COALESCE — sem isto, o array vazio do INSERT venceria sempre o array do placeholder.
- Quando o bot puxa a mesma mão de múltiplos canais (acontece com forwards), há append de cada canal — a ordem é inserção, não cronológica.
- Resolver `channel_name` precisa de `discord_sync_state` populado. Se o canal nunca foi sincronizado, `_resolve_channel_name_for_entry` devolve `None` e nada é escrito.

**Quando alguém pergunta...**

- *"Porque é que esta mão tem `discord_tags = ['nota']` mas não aparece em Vilões?"* → Verifica `match_method`. Regra C exige **as duas**: `nota` em discord_tags **AND** `match_method` populado.
- *"E se eu apagar uma mão do canal Discord?"* → Não é detectado. `discord_tags` continua. Limpeza só via SQL manual.
- *"O nome do canal vem com `#`?"* → Não. Só o nome bruto, ex: `'nota'`, `'icm-pko'`.

**Cross-references:** [`tags`](#25-tags), [`hm3_tags`](#23-hm3_tags), [`match_method`](#21-match_method), [Vilões (regras A∨B∨C)](#63-vilões-regras-abc), [`_link_second_discord_entry_to_existing_hand`](#73-_link_second_discord_entry_to_existing_hand).

---

### 2.5 `tags`

**Em linguagem simples:** etiquetas auto-geradas pelo parser da mão (não confundir com tags HM3 humanas).

**O que é (humano):** Coluna `TEXT[]` legacy. Hoje usada para tags **derivadas do raw** — `'showdown'`, nicks de jogadores que mostraram cartas, `'PKO'`/`'KO'`/`'mystery'`/`'vanilla'` (também copiadas para `tournament_format`), `'6max'`/`'9max'`, `'Match SS'`, `'mtt'`, `'SSMatch'` (placeholder marker SS upload). Originalmente continha tudo (incluindo HM3 tags); a migração `/admin/migrate-hm3-tags` separou as duas.

**Detalhes (técnico):**

| Onde é produzido | Função |
|---|---|
| `backend/app/routers/hm3.py:931-938` | `import_hm3` extrai showdown villain nicks via `_extract_showdown_villain_tags` |
| `backend/app/routers/hm3.py:1109` | `import_hm3` INSERT com `auto_tags` |
| `backend/app/routers/mtt.py:836-845, 1054-1062` | `_promote_to_study` / `import_mtt` adicionam `tournament_format.lower()`, `f"{N}max"`, `'Match SS'` |
| `backend/app/routers/screenshot.py:1142` | `_create_placeholder_if_needed` escreve `['SSMatch']` para placeholders SS upload |
| `backend/app/discord_bot.py:73, 246` | `_channel_to_tags` (split por `-`) + `_apply_channel_tags` faz append |
| `backend/app/routers/hands.py:1097` | `/admin/migrate-hm3-tags` move tags HM3 para `hm3_tags` |
| Frontend PATCH `/api/hands/{id}` | Editor manual via TagEditor.jsx |

| Onde é consumido | Função |
|---|---|
| `backend/app/routers/hands.py:334, 363, 386` | Filtros `tag=...`, search livre |
| `backend/app/routers/hm3.py:1259, 1271` | `/hm3/nota-hands` filtra por substring `'nota'` em `tags` (legacy) |
| `backend/app/routers/screenshot.py:1289` | `'SSMatch' in tags` é fallback para detectar placeholder |
| `backend/app/services/hand_service.py:69` | `_insert_hand` detecta placeholder por `'SSMatch' in tags` |
| `frontend/src/components/HandRow.jsx` (chips) | Mostra tags como badges |
| `frontend/src/pages/Hands.jsx:1234` | Agrupamento por tag |

| Valor (exemplos) | Significado |
|---|---|
| `'showdown'` | Mão tem pelo menos um non-hero a mostrar cartas. |
| `<nick>` | Auto-tag com nome de villain que mostrou cartas. |
| `'PKO'` / `'KO'` / `'mystery'` / `'vanilla'` | Formato de torneio. Duplicado em `tournament_format` (canónica). |
| `'6max'`, `'9max'`, `'10max'` | Número de jogadores na mesa. |
| `'Match SS'` | Mão MTT que cruzou com screenshot. |
| `'SSMatch'` | **Marker interno**: placeholder SS upload sem HH. |
| `'mtt'` | Mão importada via fluxo bulk MTT. |

**Comportamento esperado quando muda:**

- Adicionar tag não conhecida: aparece em todos os filtros sem filtro/validação.
- Remover `'SSMatch'`: sinaliza que o placeholder foi substituído pela HH real.
- Os auto-tags são re-escritos em re-parses (`hm3_tags` é merged, mas `tags = EXCLUDED.tags` em `import_hm3:1076`).

**Armadilhas conhecidas:**

- A confusão histórica entre `tags` e `hm3_tags` ainda persiste em alguns scripts ad-hoc (`query_*.py`). O `migrate-hm3-tags` é idempotente mas só sobre rows com `hm3_tags=NULL` — re-correr é seguro.
- O frontend agrupa por `tags` ou `hm3_tags` consoante `tag_source` (`backend/app/routers/hands.py:516`); se enviares ambos os campos via PATCH, ambos são merged independentemente.

**Quando alguém pergunta...**

- *"Quero filtrar por `'nota'` na lista — que coluna?"* → Em mãos HM3 puras, `hm3_tags`. A página `/hm3/nota-hands` ainda lê `tags` por compatibilidade legacy.
- *"O `'SSMatch'` aparece como tag no UI — é bug?"* → Sim — é marker interno que não devia ser visível. Filtrar no front se precisar.

**Cross-references:** [`hm3_tags`](#23-hm3_tags), [`discord_tags`](#24-discord_tags), [`tournament_format`](#210-tournament_format--tournament_name--tournament_number--buy_in).

---

### 2.6 `screenshot_url`

**Em linguagem simples:** URL para a imagem do screenshot associado à mão.

**O que é (humano):** Coluna `TEXT`. Para mãos vindas do Discord (replayer GG), aponta para o `og:image` no CDN da GG (URL público). Para uploads manuais, fica `null` — a imagem vive em base64 dentro do `entries.raw_json.img_b64` e é servida via `/api/screenshots/image/{entry_id}`.

**Detalhes (técnico):**

| Onde é produzido | Função |
|---|---|
| `backend/app/routers/screenshot.py:1110-1123` | `_create_placeholder_if_needed` escreve `og_image_url` para Discord; `null` para upload manual |
| `backend/app/routers/discord.py:696` | `backfill_ggdiscord` escreve `og_image_url` |
| `backend/app/discord_bot.py:336` | `_create_placeholder_hand` (DEPRECATED) |
| `backend/app/routers/discord.py:266-268` | `resolve_replayers` faz UPDATE pós-extracção |
| `backend/app/services/hand_service.py:188` | `_insert_hand` placeholder upgrade preserva `screenshot_url` via COALESCE |
| `backend/app/routers/screenshot.py:1390-1392` | `_enrich_hand_from_orphan_entry` UPDATE com `screenshot_url` |

| Onde é consumido | Função |
|---|---|
| `backend/app/routers/hands.py:1075-1085` | `/admin/delete-gg-without-screenshot` |
| `backend/app/routers/mtt.py:1208-1224, 1346-1352` | Filtro Com SS / Sem SS |
| `backend/app/routers/screenshot.py:1586` (`/screenshots/hand/{hand_id}`) | Devolve `screenshot_url` + `player_names` |
| `frontend/src/pages/Hands.jsx:768` | Mostra imagem |
| `frontend/src/pages/Dashboard.jsx:701` | OrphanList combina `screenshot_url` (Discord CDN) ou `imageUrl(entry_id)` (upload b64) |

| Valor | Significado |
|---|---|
| `null` | Sem screenshot, **ou** screenshot guardado em base64 no entry. |
| URL `https://user.gg-global-cdn.com/.../<unix_ms>.png` | Discord replayer; pode-se extrair `played_at` do filename. |
| `https://i.gyazo.com/...` | (raro) Gyazo. |
| `/api/screenshots/image/{entry_id}` | Não é gravado aqui — calculado pelo frontend quando `entry_id` existe. |

**Comportamento esperado quando muda:**

- Mudar de `null` para URL: a UI passa a mostrar a imagem inline.
- Apagar a entry com a imagem b64: `entry_delete` (entries.py:78) limpa `entry_id` mas `screenshot_url` persiste — pode causar broken links. Se a mão for `'GGDiscord'`, a hand toda é apagada.

**Armadilhas conhecidas:**

- O `played_at` do `<unix_ms>.png` é mais fiável que `discord_posted_at`. `fix_ggdiscord_played_at` (`discord.py:729`) corrige mãos antigas que tinham `played_at = posted_at`.
- Imagens base64 podem chegar a 50KB cada — comprimir antes de gravar em PG (`_compress_image` em screenshot.py:730).

**Quando alguém pergunta...**

- *"Posso confiar que esta URL ainda funciona?"* → Para CDN da GG, sim — não vimos 404s nas mãos de 2026. Para Gyazo, depende.
- *"E quando a imagem está só em base64?"* → `entries.raw_json.img_b64`; servir via `GET /api/screenshots/image/{entry_id}`.

**Cross-references:** [`raw_json` keys](#34-raw_json--keys-críticas), [`origin`](#22-origin), [`_create_placeholder_if_needed`](#76-_create_placeholder_if_needed).

---

### 2.7 `study_state`

**Em linguagem simples:** em que ponto do ciclo de estudo a mão está.

**O que é (humano):** Coluna `TEXT NOT NULL DEFAULT 'new'` com CHECK em valores literais. É a "track" da mão — distingue inbox de arquivo. Mãos `mtt_archive` ficam fora da Inbox e da página Mãos. Mãos `new`/`review`/`studying`/`resolved` são as do track de estudo.

**Detalhes (técnico):**

| Onde é produzido | Função |
|---|---|
| `backend/app/main.py:88` | `ensure_entries_schema` cria coluna com default `'new'` |
| `backend/app/services/hand_service.py:31` (param `study_state`) | `_insert_hand` recebe `'mtt_archive'` por defeito |
| `backend/app/routers/import_.py:311, 335` | HH import força `study_state='new'` |
| `backend/app/routers/hm3.py:1073` | `import_hm3` força `'new'` no INSERT |
| `backend/app/routers/mtt.py:1064` | `import_mtt`: `'new'` se há SS, `'mtt_archive'` caso contrário |
| `backend/app/routers/mtt.py:904` | `_promote_to_study` força `'new'` |
| `backend/app/routers/screenshot.py:1370` | `_enrich_hand_from_orphan_entry` força `'new'` (promove de mtt_archive) |
| `backend/app/routers/hands.py:743` (`PATCH`) | Update manual via UI |
| `backend/app/routers/hands.py:986-1007` | `/admin/promote-archive` (one-shot) |
| `backend/app/routers/entries.py:88, 121` | `entry_delete` reverte para `'mtt_archive'` |

| Onde é consumido | Função |
|---|---|
| `backend/app/routers/hands.py:355, 437` | Filtro principal |
| `backend/app/routers/hands.py:579` (`/hands/stats`) | Counts por estado |
| `backend/app/routers/hands.py:750` | Auto-set `studied_at` quando vai para `'resolved'` |
| `backend/app/routers/hm3.py:1232` (`/hm3/stats`) | Counts por sala |
| `frontend/src/pages/Hands.jsx:1596` | Filtro UI |
| `frontend/src/pages/Dashboard.jsx:179, 308` | Badge por estado |
| `frontend/src/components/HandRow.jsx:168` | StateBadge |

| Valor | Significado |
|---|---|
| `'new'` | Inbox / chegou agora / ainda não vista. |
| `'review'` | Vista, marcada para rever. |
| `'studying'` | Em estudo activo. |
| `'resolved'` | Estudada, conclusão tirada. Auto-marca `studied_at`. |
| `'mtt_archive'` | Arquivo MTT bulk — não aparece em Inbox/Estudo, só em MTT > GG. |

**Comportamento esperado quando muda:**

- `'mtt_archive'` → `'new'`: mão entra na Estudo. Acontece automaticamente quando um SS faz match.
- `'new'` → `'resolved'`: backend escreve `studied_at = NOW()` automaticamente.
- O default em `_insert_hand` (services) é `'mtt_archive'` — paths que querem study_state `'new'` têm de o passar explicitamente.

**Armadilhas conhecidas:**

- Há **dois** `_insert_hand`: `backend/app/services/hand_service.py:31` (canónico, usado por imports) e `backend/app/hand_service.py:32` (legacy, usado pelo bot Discord para HH puro). O legacy ignora o param `origin` — qualquer HH puro chegado via Discord não tem `origin='discord'`.
- O CHECK constraint só permite os 4 valores do track de estudo + falta `'mtt_archive'` na lista do schema (`schema.sql:191`). Foi adicionado por `ensure_entries_schema` que **omite** o CHECK; em produção o CHECK histórico foi relaxado.
- `entry_delete` reverte para `'mtt_archive'` mas se a mão for `'GGDiscord'`, é apagada inteira.

**Quando alguém pergunta...**

- *"Como muda do estado quando carrego em 'Estudar'?"* → PATCH `/api/hands/{id}` com `{study_state: 'studying'}` (ou `'resolved'` quando termina). UI faz isto pelo `Hands.jsx:805`.
- *"Mãos `mtt_archive` ainda contam para `recalculate-hands`?"* → Não — o filtro 2026+ + regra A∨B∨C exclui-as efectivamente (não têm `match_method` nem `nota*` nem `discord_tags=['nota']`).

**Cross-references:** [`origin`](#22-origin), [`match_method`](#21-match_method), [Estudo (`Hands.jsx`)](#61-estudo-handsjsx).

---

### 2.8 `has_showdown`

**Em linguagem simples:** flag a dizer se algum jogador (não-hero) mostrou cartas no fim.

**O que é (humano):** `BOOLEAN DEFAULT FALSE`, indexado parcialmente (`WHERE has_showdown = TRUE`). Calculado no momento do INSERT/UPDATE iterando `all_players_actions` à procura de jogadores com `cards != None` e `is_hero=False`. Crucial para regra B de villains (showdown válido + match → villain).

**Detalhes (técnico):**

| Onde é produzido | Função |
|---|---|
| `backend/app/routers/hands.py:39` | `ensure_has_showdown_column` |
| `backend/app/services/hand_service.py:105-112` | Calculado em `_insert_hand` |
| `backend/app/routers/hm3.py:980-986, 1056-1062` | `import_hm3` calcula em INSERT/UPDATE |

| Onde é consumido | Função |
|---|---|
| `backend/app/routers/hands.py:399, 491` | Filtro `has_showdown=true/false` |
| `backend/app/routers/villains.py:76` | Regra B do `VILLAIN_ELIGIBILITY_CONDITION` |
| `backend/app/routers/hm3.py:1006, 1127` | Decide se cria `hand_villains` em modo showdown |
| `backend/app/routers/screenshot.py:886` | `_link_second_discord_entry_to_existing_hand` passa `showdown_only=row['has_showdown']` |
| `frontend/src/pages/Hands.jsx:1427` | Filtro UI "Com showdown" / "Sem showdown" |

| Valor | Significado |
|---|---|
| `TRUE` | Pelo menos um non-hero mostrou cartas. |
| `FALSE`/`NULL` | Não houve showdown (todos foldaram menos hero, ou não detectado). |

**Comportamento esperado quando muda:**

- `FALSE → TRUE`: promove `_street_reached` em `apply_villain_rules` para 5 (showdown) quando há cards reveladas no river. Filtro vilão principal (`_filter_to_furthest_street`) passa a ser estricter: só candidates que chegaram à street máxima passam. Regra B classification foi eliminada em #B8 (pt7) — showdown sozinho já não cria villains.
- `TRUE → FALSE`: candidates podem cair em street ≤ 4. Eligibility default (`has_cards ∨ has_vpip`) continua a filtrar; excepção #B19 (tag `nota`) aceita postflop-only.

**Armadilhas conhecidas:**

- Backfill SQL processou 5269 mãos antes do CLAUDE.md ser escrito — verificar se mãos antigas têm `has_showdown` populado.
- Detecção depende de `cards` estar preenchido em `all_players_actions` — em GG anonimizada antes de Vision, `cards` está sempre `None`, logo `has_showdown=FALSE` mesmo que houvesse showdown real. Re-detectar após enrichment.

**Quando alguém pergunta...**

- *"Posso fazer trust deste flag para análises de showdown?"* → Sim em mãos com `match_method` populado. Em GG anonimizada sem match, `has_showdown` é unreliable.

**Cross-references:** [`match_method`](#21-match_method), [Vilões](#63-vilões-regras-abc), [`apply_villain_rules`](#74-apply_villain_rules--função-canónica).

---

### 2.9 `position_parse_failed`

**Em linguagem simples:** flag a dizer "não consegui descobrir quem era o button nesta mão".

**O que é (humano):** `BOOLEAN DEFAULT FALSE`. Adicionado em `main.py:121` para casos onde nem a dedução por blinds nem o raw "Seat #X is the button" resolvem (típico de raws Winamax bugados onde o button aponta para seat vazio). A mão é importada na mesma com `all_players` esquelético (só nicks) para não perder a HH.

**Detalhes (técnico):**

| Onde é produzido | Função |
|---|---|
| `backend/app/main.py:121` | `ensure_entries_schema` cria coluna |
| `backend/app/routers/hm3.py:493, 500` | `_parse_hand` seta `True` quando deduction falha |

| Onde é consumido | Função |
|---|---|
| `backend/app/routers/hm3.py:989, 1089` | Persistido em INSERT/UPDATE |
| Não há UI/filtro hoje. Útil para queries diagnósticas. |  |

**Cross-references:** [HM3](#66-hm3).

---

### 2.10 `tournament_format` / `tournament_name` / `tournament_number` / `buy_in`

**Em linguagem simples:** quatro colunas que dizem em que torneio a mão foi jogada.

**O que é (humano):**

- `tournament_format TEXT` — `'PKO'` / `'KO'` / `'mystery'` / `'vanilla'` (case-sensitive, dual-accept legacy lower em alguns paths). NULL quando ainda não classificado.
- `tournament_name TEXT` — nome real limpo por sala. WN/GG têm nome real (sem buyin); WPN guarda prize-pool-string; PS fica NULL.
- `tournament_number TEXT` — string crua do raw (ex: `'3983883162'`). Separada de `tournament_id BIGINT` (FK para `tournaments`).
- `buy_in NUMERIC(10,2)` — buy-in numérico em moeda do torneio (sem conversão).

**Detalhes (técnico):**

| Onde é produzido | Função |
|---|---|
| `backend/app/routers/hands.py:116, 138, 164` | `ensure_buy_in_column` / `ensure_tournament_format_column` / `ensure_tournament_name_and_number_columns` |
| `backend/app/utils/tournament_format.py:detect_tournament_format` | Classifica formato (keyword no nome → fallback estrutural por sala) |
| `backend/app/parsers/gg_hands.py:316-339` | GG: extrai `tournament_id`, `tournament_name`, `buy_in`, `tournament_format` |
| `backend/app/routers/hm3.py:309-358` | WN/PS/WPN: extrai `tournament_number`, `tournament_name`, `buy_in`, `tournament_format` |
| `backend/app/routers/hm3.py:1090-1095` | INSERT/UPDATE com OVERWRITE de `tournament_name`/`number`/`buy_in` (deterministicos) |
| `backend/app/routers/mtt.py:828-833, 1047-1051` | `_promote_to_study` / `import_mtt` classificam com `has_player_bounty` da SS |

| Onde é consumido | Função |
|---|---|
| `backend/app/routers/mtt.py:1357-1361` | `/mtt/dates` filtra por `format=PKO/Vanilla` |
| `backend/app/routers/mtt.py:1244, 1265` | `/mtt/hands` SELECT |
| `backend/app/routers/hands.py:454, 615` | `list_hands` e `/hands/stats` SELECT |
| `frontend/src/components/HandRow.jsx:142` | Badge KO/NKO |
| `frontend/src/pages/Tournaments.jsx:390` | Header de torneio (TM · nome · $buyin · blinds · etc.) |
| `frontend/src/pages/HM3.jsx:572` | Display de formato |

**Comportamento esperado quando muda:**

- `tournament_format` é OVERWRITE no re-parse (não COALESCE) — propaga correcções de regex/lógica. `tournament_name`/`number`/`buy_in` idem (`hm3.py:1093-1095`).
- `tournament_id` (BIGINT FK) só é resolvido pelo `_get_or_create_tournament_pk` (`services/hand_service.py:10`) se a tabela `tournaments` já tiver o torneio.

**Armadilhas conhecidas:**

- Dual-accept legacy `'vanilla'` vs novo `'Vanilla'` (canónico) — comparar `.lower()` para evitar drift, ver `mtt.py:842, 1058`.
- WPN não tem padrão numérico de buyin — `buy_in` fica NULL.
- PS tem `tournament_name=NULL` por design — frontend compõe título via `buy_in + format + #tournament_number`.

**Cross-references:** [`tags`](#25-tags), [Torneios](#65-torneios-gg-com-ss--sem-ss-hm3-tab), [HM3](#66-hm3).

---

### 2.11 `hand_attachments`

**Em linguagem simples:** tabela que liga uma imagem Discord a uma mão como contexto, sem criar mão nova.

**O que é (humano):** quando o Rui partilha uma imagem num canal Discord (anexo `.png`/`.jpg`/`.webp`, link Gyazo) é contexto duma mão já partilhada (replayer link no mesmo canal ±90s) ou duma mão importada via HM3 (±90s, qualquer canal). A tabela `hand_attachments` representa essa ligação 1:1 entre uma entry image e a hand a que pertence.

A tabela existe porque imagens directas Discord **não devem** virar hands (regra de produto em CLAUDE.md "Imagens de contexto Discord"). Antes deste Bucket 1 (Abr 2026), o pipeline tentava processar imagens via Vision para extrair TM e criar placeholder — abordagem revertida em commit `ab1953e`. Modelo correcto: imagem → row em `hand_attachments` ligada a uma mão existente. Sem ligação possível, a imagem fica órfã (entry continua `status='new'`, sem row em `hand_attachments`).

**Detalhes (técnico):**

| Onde é produzido | Função |
|---|---|
| `backend/app/routers/attachments.py:288 _apply_match` | INSERT após match calculado por `_compute_match_candidates` |
| `backend/app/routers/discord.py:147 sync_and_process` | Trigger fire-and-forget via `asyncio.create_task` (Fase IV) |
| `backend/app/routers/hm3.py:1205 import_hm3` | Trigger fire-and-forget via `asyncio.create_task` (Fase IV) |
| `backfill_attach_orphan_images.py` | Backfill manual das 3 entries 13/17/87 (executado 26-Abr) |

| Onde é consumido | Função |
|---|---|
| `backend/app/routers/hands.py:543 list_hands` | subquery `attachment_count::int` em `GET /api/hands` |
| `backend/app/routers/hands.py:980 get_hand` | 2ª query devolve `attachments: [...]` em `GET /api/hands/{id}` |
| `frontend/src/components/HandRow.jsx:249-261` | Ícone `📎 N` se `hand.attachment_count > 0` |
| `frontend/src/pages/HandDetailPage.jsx:161-205` | Secção CONTEXTO com thumbnails 200px |

Schema (criado por `ensure_hand_attachments_schema()` em `hands.py:197`):

```sql
id            BIGSERIAL PK
hand_db_id    BIGINT NOT NULL FK hands(id) ON DELETE CASCADE
entry_id      BIGINT FK entries(id) ON DELETE SET NULL
image_url     TEXT          -- URL original (gyazo, discord cdn)
cached_url    TEXT          -- não usado actualmente
img_b64       TEXT          -- bytes base64 (cache só para Gyazo, decisão Q2 SPEC)
mime_type     TEXT
posted_at     TIMESTAMPTZ NOT NULL
channel_name  TEXT
match_method  TEXT NOT NULL
delta_seconds INTEGER       -- |posted_at - hand.played_at|, magnitude (sem sinal)
created_at    TIMESTAMPTZ DEFAULT NOW()
```

Índices: `idx_hand_attachments_hand` (hand_db_id), `idx_hand_attachments_entry` (entry_id), `uq_hand_attachments_hand_entry` UNIQUE parcial em `(hand_db_id, entry_id) WHERE entry_id IS NOT NULL`.

| Valor `match_method` | Significado |
|---|---|
| `discord_channel_temporal` | Match primário: entry image + entry replayer_link no mesmo `discord_channel` ±90s (sibling delta) |
| `hm3_temporal_fallback` | Match fallback: hand com `origin IN ('hm3','hh_import')` ±90s entre `played_at` e `discord_posted_at` (qualquer canal) |
| `manual` | Reservado para anexação manual via UI (não implementado) |

**Comportamento esperado quando muda:**

- INSERT: `attachment_count` na lista (`GET /api/hands`) incrementa em 1; `GET /api/hands/{id}` passa a incluir o novo attachment em `attachments[]` ordenado por `posted_at ASC, id ASC`. Frontend renderiza ícone na lista + secção CONTEXTO no detalhe.
- DELETE de hand: cascade apaga attachments (FK CASCADE).
- DELETE de entry: attachment fica órfão (`entry_id` SET NULL), `image_url` preservado.
- Janela ±90s: literal hard-coded em `_find_primary_match` e `_find_fallback_match`. Mexer abre risco de cross-talk entre mãos consecutivas (ver SPEC §1).
- `entries.status` **não** é tocado pelo worker (ver Armadilha 4 abaixo).

**Armadilhas conhecidas:**

1. **`PlaceholderHandRow` não mostra ícone 📎 nem link para detalhe.** Hands placeholder Discord (sem HH real) usam o componente `PlaceholderHandRow` em `frontend/src/pages/Hands.jsx:1444`, não `HandRow.jsx`. O ícone 📎 só está em `HandRow.jsx`. Resultado: as 3 attachments inseridas a 26-Abr (att_ids 58/59/60, ligadas a hands 117/115/67 que são placeholders) ficam invisíveis na UI até as HHs reais chegarem. Não-bloqueante; `_insert_hand` apaga placeholders quando HH chega e re-insere com `raw` populado, hand vira matched, e o `HandRow.jsx` passa a renderizar. **Subtileza:** ao apagar o placeholder, o ON DELETE CASCADE em `hand_db_id` apaga também as rows de `hand_attachments` associadas. `_insert_hand` re-insere a hand com novo id, `attachment_count` cai para 0 momentaneamente. O trigger retroactivo da Fase IV (`asyncio.create_task` em `sync_and_process`/`import_hm3`, depois do INSERT) corre `_compute_match_candidates` + `_apply_match` e reanexa via match primário (entries image continuam em `entries` com `status='new'`). Gap visual: milissegundos. Futuro Claude que veja `attachment_count=0` logo após import deve esperar pelo trigger antes de assumir bug.

2. **`img_b64` NULL inesperado.** `_fetch_entry_image_bytes` (`attachments.py:42`) engole erros silenciosamente — `logger.warning`, retorna None, e `_apply_match` insere a row com `img_b64=NULL` mesmo assim (frontend faz fallback para `image_url`). Sintoma observado a 26-Abr para entry 17: `image fetch: unexpected content-type text/html for https://gyazo.com/fd1a6adb7c99...` — possível causa: HEAD a `i.gyazo.com/<id>.png` falhou, fallback para URL HTML, content-type validation rejeitou. Investigar se padrão se repetir; sugestão de melhoria: enriquecer warnings com `resp.headers` para deixar rasto da causa concreta.

3. **`channel_name` é ID numérico, não nome resolvido.** `_apply_match` guarda `candidate["channel"]` que é `discord_channel` da entry (ID Discord, ex: `1484600506109267988`), não o nome (`icm-pko`). Frontend mostra ID na metadata por baixo do thumbnail — não user-friendly. Fix possível: resolver nome via JOIN com `discord_sync_state.channel_name` no INSERT ou no `get_hand` SELECT. Por agora cosmético.

4. **`entries.status` nunca toma o valor `'attached'`.** O CHECK constraint `entries_status_check` aceita apenas `new/processed/partial/failed/archived/resolved` — descoberto a 26-Abr durante backfill Fase VI quando o `_apply_match` original tentava `UPDATE entries SET status='attached'` e rebentava. Fix opção (C): worker não toca em `entries.status`. O estado "anexada" é representado **apenas** pela existência de row em `hand_attachments` (filtro `NOT IN` em `_pending_image_entries`). Se algum código futuro precisar de saber se uma entry image foi anexada, **não** verificar `entries.status` — verificar `EXISTS (SELECT 1 FROM hand_attachments WHERE entry_id = e.id)`.

**Cross-references:**
- [`match_method`](#21-match_method) — distinto do `hands.player_names ->> 'match_method'` (que rastreia match SS↔HH).
- [§5.3 `discord`](#53-discord-bot-via-post-apidiscordsync-and-process) — entries `image` Discord chegam aqui mas não criam mão.
- [§5.2 `hm3`](#52-hm3-post-apihm3import--csv) — hands `hm3` podem disparar match fallback retroactivo.
- CLAUDE.md secção "Imagens de contexto Discord — comportamento de produto".
- `docs/SPEC_BUCKET_1_anexos_imagem.md` — spec original com decisões Q1-Q5.

---

## 3. Estado / marcação de entries

`entries` é a inbox de inputs crus: cada mensagem Discord, screenshot, HH file, ou report HM3 aterra aí primeiro. O modelo é genérico — `(source, entry_type, raw_text, raw_json)`. Os campos abaixo são os classificadores.

### 3.1 `entry_type`

**Em linguagem simples:** que **tipo** de coisa é (texto de mão, link, imagem, ...).

**O que é (humano):** Coluna `TEXT NOT NULL` com CHECK explícito. Determina como o entry é processado — se é HH é parseado, se é replayer link é fetched, se é imagem é enviado para Vision.

**Detalhes (técnico):**

| Onde é produzido | Função |
|---|---|
| `backend/schema.sql:137` | CHECK constraint |
| `backend/app/services/entry_classifier.py:53` | `classify_entry` deduz a partir do conteúdo |
| `backend/app/discord_bot.py:159-164` (`entry_type_map`) | Bot Discord faz mapping `content_type → entry_type` |
| `backend/app/routers/screenshot.py:1248` | Upload manual cria `'screenshot'` (não na CHECK list — ver armadilha) |

| Onde é consumido | Função |
|---|---|
| `backend/app/routers/hands.py:642` | `'screenshot'` em `/hands/stats` |
| `backend/app/routers/screenshot.py:1447, 1488, 1502, 1527, 1557, 1635, 1671` | Filtros para Vision processing |
| `backend/app/routers/import_.py:380` | Auto-rematch query |
| `backend/app/routers/discord.py:303, 415, 539` | Filtros para `replayer_link` GG |
| `backend/app/routers/entries.py:60` | `entry_reprocess` exige `'hand_history'` |

| Valor | Significado |
|---|---|
| `'hand_history'` | Texto de HH completo. Parseado por `process_entry_to_hands`. |
| `'tournament_summary'` | Sumário de torneio (linha resumo, não HH). Não vai para hands. |
| `'tabular_report'` | Report tabular HM3-style. |
| `'image'` | Anexo de imagem (Discord/Gyazo). |
| `'replayer_link'` | URL `gg.gl` ou `pokercraft.com/embedded/...`. |
| `'note'` / `'text'` | Texto livre. |
| `'screenshot'` | Upload manual de SS pela UI. **Não está no CHECK** do schema mas é escrito mesmo assim — verificar produção. |

**Armadilhas conhecidas:**

- O CHECK em `schema.sql:137` lista 7 valores. Mas `screenshot.py:1248` escreve `'screenshot'` que **não** está na lista. Em produção, o CHECK foi relaxado (via `ensure_entries_schema` que não recria CHECK) ou nunca foi enforced. Confirmar antes de mexer.

**Cross-references:** [`source`](#32-source), [`status`](#33-status), [`raw_json` keys](#34-raw_json--keys-críticas).

---

### 3.2 `source`

**Em linguagem simples:** **de onde** a entry veio (canal de input).

**Detalhes (técnico):**

| Onde é produzido | Função |
|---|---|
| `backend/schema.sql:125` | CHECK: `discord`, `hm`, `gg_backoffice`, `hh_text`, `summary`, `report`, `manual` |
| `backend/app/discord_bot.py:168` | `'discord'` |
| `backend/app/routers/screenshot.py:1248` | `'screenshot'` (não no CHECK — ver armadilha) |
| `backend/app/routers/import_.py:267` | `'hh_text'` ou `'summary'` |

| Onde é consumido | Função |
|---|---|
| `backend/app/routers/hands.py:391` (`source` filter) | Filtra mãos pelo source da entry |
| `backend/app/routers/screenshot.py:1055-1058` | `_create_placeholder_if_needed` decide entre Discord e SS upload pelo source |
| `backend/app/routers/discord.py:174, 184, 305, 415, 539` | Filtros |
| `backend/app/routers/hm3.py:1370` | `via_discord_entries` count |

**Armadilhas conhecidas:** `'screenshot'` não está no CHECK do schema mas é escrito; CHECK relaxado em produção.

**Cross-references:** [`origin`](#22-origin) (que aplica a `hands`), [Pipelines de ingest](#5-pipelines-de-ingest).

---

### 3.3 `status`

**Em linguagem simples:** estado do processamento da entry (nova, processada, etc.).

**Detalhes (técnico):**

| Valor | Significado |
|---|---|
| `'new'` | Default. Ainda por processar. |
| `'processed'` | Processada com sucesso. |
| `'partial'` | Processada com erros mas algo foi feito. |
| `'failed'` | Falhou. |
| `'archived'` | Arquivada. |
| `'resolved'` | Aplicado a entries SS/Discord cuja mão foi criada/ligada. |
| `'error'` | Aplicado em alguns paths antigos. |

| Onde é produzido | Função |
|---|---|
| `backend/app/services/hand_service.py:244` (`process_entry_to_hands`) | Decide entre `'processed'`, `'partial'`, `'failed'` |
| `backend/app/routers/screenshot.py:825, 1187, 1403` | `'resolved'` em vários momentos do pipeline |
| `backend/app/routers/discord.py:230, 410, 540` | Filtra `'new'` para reprocess |

| Onde é consumido | Função |
|---|---|
| `backend/app/routers/import_.py:367-376` | Auto-rematch query (`status='new'` ou `'resolved'`) |
| `backend/app/routers/screenshot.py:1487` | Cleanup pre-2026 só toca `status='new'` |
| `backend/app/routers/hands.py:636` (`/hands/stats`) | Conta orfãos com `status='new'` |

**Cross-references:** [`source`](#32-source), [`_create_placeholder_if_needed`](#76-_create_placeholder_if_needed).

---

### 3.4 `raw_json` — keys críticas

**Em linguagem simples:** dicionário JSON onde ficam os dados ricos da entry (Vision data, imagens, metadata).

**O que é (humano):** Coluna `JSONB`. Forma livre, mas algumas keys são canónicas e consumidas por vários paths. Fonte primária do pipeline SS↔HH.

**Keys críticas:**

| Key | Quem escreve | Quem lê | Para quê |
|---|---|---|---|
| `vision_done` | `backend/app/routers/screenshot.py:941` (default `False` em `:1264`) | `screenshot.py:1632, 1651, 1668`, `discord.py:301, 416, 542`, `mtt.py:421` | Marca conclusão de Vision; gating para reprocessing |
| `tm` | `screenshot.py:929, 1255`, `discord_bot.py:175` (via raw_json content_type) | `screenshot.py:957, 1455, 1499`, `mtt.py:419, 444`, `import_.py:386, 393`, `hm3.py:1176` | TM number do torneio (`TM<digits>`) |
| `hero` | `screenshot.py:935`, `mtt.py:394` | `screenshot.py:1304, 1322`, `mtt.py:502, 866` | Nick do hero detectado por Vision |
| `players_list` | `screenshot.py:933, 1259` | `mtt.py:393, 499`, `screenshot.py:912, 1322` | Lista `[{name,stack,bounty_pct,country}]` extraída pelo Vision |
| `players_by_position` | `screenshot.py:934, 1260, 969` | `mtt.py:392, 510-511` | Mapping legacy posição→jogador |
| `vision_sb` / `vision_bb` | `screenshot.py:937-938, 1262-1263` | `screenshot.py:1325-1326`, `mtt.py:396-397, 500-501` | SB/BB do painel esquerdo do Vision |
| `vision_level` | `screenshot.py:939, 1100` | (display only) | Level do torneio |
| `board` | `screenshot.py:936` | `screenshot.py:1097, 1322` | Cartas do board lidas pelo Vision |
| `img_b64` | `screenshot.py:932, 1258`, `discord.py:467` | `screenshot.py:1564, 1610, 1635-1636`, `hands.py:798` | Imagem comprimida base64 |
| `mime_type` | `screenshot.py:931, 1257` | `screenshot.py:1568, 1615` | Para servir imagem |
| `file_meta` | `screenshot.py:930, 1256` | `screenshot.py:1305, 1328`, `mtt.py:444, 466`, `discord.py:651, 659` | Output do `_parse_filename`: `{date,time,blinds,tm,og_image_url,source_url,via,posted_at}` |
| `og_image_url` | `discord.py:488, 696`, `screenshot.py:1110-1123, 1170` | `screenshot.py:1112-1115`, `discord.py:659-668` | URL CDN GG; gera `played_at` por extracção do `<unix_ms>.png` |
| `source_url` | `discord.py:487` | (display) | URL Discord do replayer original |
| `content_type` | `discord_bot.py:175` | (legacy) | Subtipo do entry (`hh_text`, `gg_replayer`, ...) |
| `tags_from_channel` | `discord_bot.py:176` | (legacy) | Tags derivadas do nome do canal Discord |
| `gg_replayer_resolved` | `discord_bot.py:316`, `discord.py:260, 470` | (legacy) | Flag a dizer "já fizemos fetch do og:image" |
| `raw_vision` | `screenshot.py:940` | `screenshot.py:1358, 1498`, `hands.py:1358` | Texto raw do response Vision (debug + refix) |
| `anon_map` (em `player_names`, não em `raw_json`) | `screenshot.py:1327`, `hands.py:1532` | `screenshot.py` enrich, `hands.py:1180-1187` (refix) | `{hash_GG: nick_real}` — o cruzamento Vision↔HH |
| `match_method` (em `player_names`) | Ver [§2.1](#21-match_method) | Ver [§2.1](#21-match_method) | Marker de pipeline |

**Comportamento esperado quando muda:**

- `vision_done: false → true`: dispara qualquer auto-rematch com `WHERE (raw_json->>'vision_done')::boolean = true`.
- `img_b64` removido: `/api/screenshots/image/{entry_id}` devolve 404.
- `tm` ausente: nenhum auto-match acontece.

**Armadilhas conhecidas:**

- Quando se reprocessa uma entry, **toda** a `raw_json` é overwritten em `screenshot.py:944` — preserve keys importantes via merge (`COALESCE(raw_json, '{}'::jsonb) || %s`).
- Imagens grandes inflam a row — comprimir antes (`_compress_image`).

**Cross-references:** [`screenshot_url`](#26-screenshot_url), [`match_method`](#21-match_method), [Pipelines de ingest](#5-pipelines-de-ingest).

---

## 4. Conceitos de origem (heros)

Quem é "o herói" depende de duas listas: as contas do Rui (`HERO_NAMES`) e as contas dos amigos que partilham mãos (`FRIEND_HEROES`). Tudo vive em `backend/app/hero_names.py` — single source of truth, espelhado em `frontend/src/heroNames.js`.

### 4.1 `HERO_NAMES` (Rui)

**Em linguagem simples:** todas as contas do próprio Rui em todas as salas.

**Detalhes:**

| Localização | `backend/app/hero_names.py:25` |
|---|---|
| Tipo | `set[str]` |
| Valores | 49 nicks lowercase: `'thinvalium'`, `'lauro dermio'`, `'kabalaharris'`, `'misterpoker1973'`, ..., `'iuse2bspewer'`. Ver código para lista completa. |

**Onde é consumido (apenas `HERO_NAMES` puro):** Quase nenhum site — quase tudo usa `HERO_NAMES_ALL`. Os únicos casos directos de `HERO_NAMES` (não `_ALL`) seriam quando se queria distinguir "é o Rui especificamente". Hoje não há esse caso.

**Cross-references:** [`HERO_NAMES_ALL`](#43-hero_names_all-união), [`FRIEND_NICKS`](#45-friend_nicks).

---

### 4.2 `FRIEND_HEROES` (Karluz, flightrisk)

**Em linguagem simples:** amigos que partilham mãos próprias com o Rui — quando aparecem, **são** o herói da mão.

**Detalhes:**

| Localização | `backend/app/hero_names.py:78` |
|---|---|
| Tipo | `set[str]` |
| Valores | `{'karluz', 'flightrisk'}` |

**Comportamento:** Processados identicamente a `HERO_NAMES` no pipeline (Vision, parser, equity, match). Continuam excluídos da BD de villains via `FRIEND_NICKS`.

---

### 4.3 `HERO_NAMES_ALL` (união)

**Em linguagem simples:** "é alguém de quem queremos as mãos no estudo? sim/não".

**Detalhes:**

| Localização | `backend/app/hero_names.py:84` |
|---|---|
| Tipo | `set[str]` |
| Definição | `HERO_NAMES | FRIEND_HEROES` |

| Onde é consumido | Função |
|---|---|
| `backend/app/hero_names.py:142` (`is_hero`) | Helper case-insensitive |
| `backend/app/parsers/winamax.py` (via import) | (verificar — localização aproximada) |
| `backend/app/routers/hm3.py:402, 419, 64, 702` | Identifica hero por seat name |
| `backend/app/routers/screenshot.py:31, 509` | `_build_seat_to_name_map` |
| `backend/app/routers/mtt.py:24` | (import; verificar uso interno) |

**Quando alguém pergunta...**

- *"Adicionei uma conta nova — onde mexo?"* → Append a `HERO_NAMES`. Espelhar em `frontend/src/heroNames.js` (se o nome aparecer em chips/badges).

**Cross-references:** [`HERO_NICKS_BY_SITE`](#44-hero_nicks_by_site--friend_nicks_by_site--all_nicks_by_site), [`FRIEND_NICKS`](#45-friend_nicks).

---

### 4.4 `HERO_NICKS_BY_SITE` / `FRIEND_NICKS_BY_SITE` / `ALL_NICKS_BY_SITE`

**Em linguagem simples:** que nick(s) do Rui ou amigos esperar em cada sala.

**Detalhes:**

| Localização | `backend/app/hero_names.py:123, 130, 135` |
|---|---|

```python
HERO_NICKS_BY_SITE = {
    "PokerStars": ["kokonakueka", "misterpoker1973"],
    "Winamax":    ["thinvalium"],
    "WPN":        ["cringemeariver"],
    "GGPoker":    ["lauro dermio", "koumpounophobia"],
}
FRIEND_NICKS_BY_SITE = {"GGPoker": ["karluz", "flightrisk"]}
ALL_NICKS_BY_SITE = {site: HERO + FRIEND for site}
```

| Onde é consumido | Função |
|---|---|
| `backend/app/hero_names.py:184-187` | `detect_site_from_hh` — fallback para detectar sala via nicks no raw |
| `backend/app/routers/hm3.py:25, 896` | Reclassificação quando `site_id` HM3 vem errado |
| `backend/app/routers/screenshot.py:31, 205` | Lista de heroes GG no prompt do Vision (case-aware) |

**Comportamento esperado quando muda:**

- Adicionar nick → site no `HERO_NICKS_BY_SITE`: o `detect_site_from_hh` passa a poder reclassificar essa sala. O Vision GG recebe a lista actualizada no prompt.

---

### 4.5 `FRIEND_NICKS`

**Em linguagem simples:** "este nick é do nosso grupo (Rui ou amigos) — não pode entrar em villains".

**Detalhes:**

| Localização | `backend/app/hero_names.py:116` |
|---|---|
| Definição | `HERO_NAMES_ALL | _FRIEND_ONLY_NICKS` (este último com ~80 nicks de amigos que **não** são heroes) |

| Onde é consumido | Função |
|---|---|
| `backend/app/routers/villains.py:8, 19, 378-385` | Filtra friends de villain_notes em `recalculate-hands`; helper `_is_friend` |

**Comportamento esperado quando muda:**

- Adicionar nick: é apagado de `villain_notes` no próximo `recalculate-hands`. Mãos onde o nick aparece como villain perdem a row em `hand_villains` quando o recalc rodar.

**Armadilhas conhecidas:**

- O `_is_friend` usa `starts-with` para nicks ≥6 chars (`backend/app/routers/villains.py:32`) — pode dar false positives em nicks curtos similares.
- `FRIEND_NICKS` inclui heroes — não duplicar.

**Quando alguém pergunta...**

- *"Apareceu um amigo na lista de villains. Como tirar?"* → Adicionar a `_FRIEND_ONLY_NICKS` em `hero_names.py:88` e correr `POST /api/villains/recalculate-hands`.

**Cross-references:** [`HERO_NAMES_ALL`](#43-hero_names_all-união), [Vilões](#63-vilões-regras-abc).

---

## 5. Pipelines de ingest

Cada pipeline escreve um valor diferente em `hands.origin` e marca diferente. Estes são os 4 caminhos canónicos.

### 5.1 `hh_import` (POST `/api/import` — ZIP/TXT HH)

**Em linguagem simples:** "drag-and-drop de um ficheiro de HH bruta".

**Fluxo:**

1. `backend/app/routers/import_.py:242` (`import_file`) recebe o upload.
2. Detecta sala (`_detect_site` ou `_detect_site_from_zip`) e tipo (`classify_entry` / `_detect_zip_content_type`).
3. Cria entry com `source='hh_text'` ou `'summary'`.
4. Se for HH: chama `_parse_hh_file` (multi-site splitter), filtra `is_pre_2026`, e chama `_insert_hand` com `study_state='new'`, `origin='hh_import'`.
5. **Auto-rematch** retroactivo: para cada entry SS órfã (status `'new'` ou `'resolved'` com mão real) com TM, procura `hand_id=GG-{tm}` e enriquece via `_enrich_hand_from_orphan_entry`.
6. Resposta JSON com `hands_inserted`, `hands_rejected_pre_2026`, `rematched_screenshots`, `migrated_to_study`.

**O que escreve:**

- `entries.source='hh_text'`, `entry_type='hand_history'` ou `'tournament_summary'`.
- `hands.origin='hh_import'`, `study_state='new'`, mais campos do parser.

**Cross-references:** [`origin`](#22-origin), [Auto-rematch retroactivo](#72-auto-rematch-retroactivo), [`_insert_hand` placeholder upgrade](#77-_insert_hand-placeholder-upgrade).

---

### 5.2 `hm3` (POST `/api/hm3/import` — CSV)

**Em linguagem simples:** "o script .bat do HM3 puxa as mãos com tags e POSTa o CSV".

**Fluxo:**

1. `backend/app/routers/hm3.py:818` (`import_hm3`) recebe CSV (colunas: `gamenumber`, `site_id`, `tag`, `handtimestamp`, `tournament_number`, `handhistory`).
2. Agrupa por `(gamenumber, site_id)` para colapsar tags múltiplas.
3. Filtra por `days_back` / `nota_only` se passado.
4. Para cada mão:
   - Resolve sala via `SITE_MAP`. Se parse falha, fallback `detect_site_from_hh` (reclassifica via nicks).
   - `_parse_hand` extrai tudo (deduz button por blinds, posições, blinds, board, hero result, all_players_actions, tournament_format, tournament_name, tournament_number, buy_in).
   - Filtra `is_pre_2026`.
   - Separa tags do CSV (`hm3_tags_clean`) das auto-geradas (`auto_tags`: `'showdown'` + nicks).
   - INSERT com `origin='hm3'`, `study_state='new'`, `hm3_tags=hm3_tags_clean`, `tags=auto_tags`. ON CONFLICT atualiza preservando GG match (`all_players_actions = CASE ... WHEN match_method ...`).
   - Após INSERT/UPDATE: dispara `apply_villain_rules(hand_db_id)` (canónico desde refactor #B23, pt10). Aplica A∨C∨D + filtro vilão principal + Q6 guard.
5. **Auto-rematch** semelhante a `hh_import`.

**O que escreve:**

- `hands.origin='hm3'`, `hm3_tags`, `tags`, `tournament_*`, `buy_in`, `all_players_actions`, `has_showdown`, `position_parse_failed`.
- `hand_villains` + `villain_notes` via `apply_villain_rules` (regras A∨C∨D, idempotente, Q6 guard).

**Cross-references:** [`hm3_tags`](#23-hm3_tags), [`apply_villain_rules`](#74-apply_villain_rules--função-canónica), [HM3](#66-hm3).

---

### 5.3 `discord` (bot via POST `/api/discord/sync-and-process`)

**Em linguagem simples:** "puxa mensagens do Discord, processa replayers, cria placeholders para SS sem HH".

**Fluxo (manual; `DISCORD_AUTO_SYNC=false` por defeito):**

1. UI carrega "Sincronizar Agora" → `POST /api/discord/sync-and-process` (`discord.py:86`).
2. `_sync_guild_history` por servidor monitorizado puxa `channel.history(after=last_msg_id)`.
3. Para cada mensagem, `_detect_content_type` extrai items (HH text, gg_replayer link, gyazo, discord_image).
4. `_save_to_db` filtra `is_pre_2026`, cria entry com `source='discord'`. Se for HH text, dispara `process_entry_to_hands` + `_apply_channel_tags` (escreve `tags`, `discord_tags`, `origin='discord'` se NULL).
5. Após sync, `process_replayer_links` faz fetch do `og:image` (`_extract_gg_replayer_image`) e dispara `_run_vision_for_entry` em background.
6. `_run_vision_for_entry` chama Vision, escreve `vision_done=true`, e tenta match com `hands` (via TM) e com `mtt_hands`. Se nenhum match e está em `'discord'`, chama `_create_placeholder_if_needed` que cria mão placeholder com `origin='discord'`, `hm3_tags=['GGDiscord']`, `match_method='discord_placeholder_no_hh'`, `discord_tags=[channel_name]`, `screenshot_url=og_image_url`, `played_at=<unix_ms do PNG>`.
7. `backfill_ggdiscord` (chamado em sequência) cria placeholders para entries que tinham `vision_done=true` mas ainda sem mão.

**O que escreve:**

- `entries.source='discord'`, `entry_type='hand_history'` / `'replayer_link'` / `'image'`. UNIQUE por `discord_message_id` (silencia duplicados via ON CONFLICT).
- Para HH: `hands.origin='discord'` (via `_apply_channel_tags COALESCE`), `discord_tags`, `tags` derivadas do canal.
- Para SS sem HH: `hands` placeholder com `hm3_tags=['GGDiscord']`, `match_method='discord_placeholder_no_hh'`, `origin='discord'`.

**Cross-references:** [`_create_placeholder_if_needed`](#76-_create_placeholder_if_needed), [`_link_second_discord_entry_to_existing_hand`](#73-_link_second_discord_entry_to_existing_hand), [`ON CONFLICT (discord_message_id) DO NOTHING`](#78-on-conflict-discord_message_id-do-nothing), [Discord (UI)](#64-discord).

---

### 5.4 `ss_upload` (POST `/api/screenshots` — drag-and-drop UI)

**Em linguagem simples:** "drop manual de uma imagem .png na UI; placeholder até a HH chegar".

**Fluxo:**

1. `backend/app/routers/screenshot.py:1203` (`upload_screenshot`) recebe imagem.
2. `_parse_filename` extrai data/hora/blinds/TM. Filtra `is_pre_2026` se filename tem data clara.
3. Comprime e cria entry com `source='screenshot'`, `entry_type='screenshot'`, `raw_json={tm, file_meta, mime_type, img_b64, vision_done:false}`.
4. Em background, `_run_vision_for_entry` corre Vision, tenta match com `hands` (via TM `GG-{digits}`) e `mtt_hands`.
5. Se match: enriquece via `_enrich_hand_from_orphan_entry` e dispara `apply_villain_rules(hand_db_id)` (canónico desde refactor #B23, pt10).
6. Se nenhum match: `_create_placeholder_if_needed` cria mão com `origin='ss_upload'`, `tags=['SSMatch']`, `match_method='discord_placeholder_no_hh'`, `screenshot_url=null` (imagem em entry), `played_at=null` (filename pode não ter data fiável).

**O que escreve:**

- `entries.source='screenshot'`, `entry_type='screenshot'`, `raw_json` com Vision data.
- `hands.origin='ss_upload'`, `tags=['SSMatch']`, `match_method='discord_placeholder_no_hh'` (placeholder).
- Quando HH real chega depois: `_insert_hand` placeholder upgrade promove para `match_method='anchors_stack_elimination_v2'`.

**Cross-references:** [`_create_placeholder_if_needed`](#76-_create_placeholder_if_needed), [`_enrich_hand_from_orphan_entry`](#76-_create_placeholder_if_needed), [Dashboard](#62-dashboard) painel SSMatch.

---

## 6. Visualização / filtros por página

### 6.1 Estudo (`Hands.jsx`)

**Em linguagem simples:** página principal de estudo. Lista as mãos para rever.

**Filtro principal:** `study_view=true` → exclui GG anonimizada (sem `match_method`) ou com `discord_placeholder_*`. Adiciona ao filtro WHERE o `STUDY_VIEW_GG_MATCH_FILTER` (`backend/app/routers/hands.py:307`).

**Filtros UI:** `study_state`, `site`, `position`, `search`, `date_from`, `villain`, `sd_yes`/`sd_no` (mapeia para `has_showdown`), `tag` / `hm3_tag` / `discord_tag`.

**Endpoints:** `GET /api/hands?study_view=true&...` (`backend/app/routers/hands.py:407`), `GET /api/hands/tag-groups?study_view=true`.

**Mostra:** `study_state` (badge), `hm3_tags` (chips), `discord_tags` (read-only chips), `position`, `hero_cards`, `board`, `result`, `screenshot_url` (imagem inline), `tournament_format` (badge KO/NKO).

**Cross-references:** [`study_state`](#27-study_state), [`match_method`](#21-match_method), [`hm3_tags`](#23-hm3_tags).

---

### 6.2 Dashboard

**Em linguagem simples:** hub. Mostra contadores e mãos recentes.

**Endpoints:** `GET /api/hands/stats` (counts por estado, recentes, `orphan_screenshots`, `ss_match_pending`), `GET /api/study/week`, `GET /api/discord/stats`.

**Painéis específicos:**

- **Recent (5 mais novas):** Exclui `mtt_archive` e GG sem `match_method` (`hands.py:618-622`).
- **Orphan Screenshots:** Soma `orphan_ss_only` (entries SS órfãos) + GGDiscord placeholders. Lista via `GET /api/mtt/orphan-screenshots`.
- **SSMatch:** Lista placeholders SS upload via `GET /api/hands/ss-match-pending` (`origin='ss_upload' AND match_method='discord_placeholder_no_hh'`).

**Frontend:** `frontend/src/pages/Dashboard.jsx`.

**Cross-references:** [`origin`](#22-origin), [`match_method`](#21-match_method), [`screenshot_url`](#26-screenshot_url).

---

### 6.3 Vilões

**Em linguagem simples:** lista de jogadores adversários. Modal mostra mãos do villain.

**⚠️ Distinção crucial — UI filter vs classification logic:**

A app tem **duas regras separadas** com o mesmo prefixo "A/B/C/D":

1. **Classification** (decide o que entra em `hand_villains`): regras
   **A∨C∨D** em `_classify_villain_categories` (`hand_service.py`).
   Aplicado por `apply_villain_rules` ([§7.4](#74-apply_villain_rules--função-canónica)).
   Regra B (showdown sem tag) foi **eliminada em #B8 (pt7)**.

2. **UI filter** (decide o que aparece na lista Vilões): regras
   **A∨B∨C** em `VILLAIN_ELIGIBILITY_CONDITION` (`villains.py:67-85`).
   Branch B continua presente no SQL mas é **dead code** — nenhuma row
   em `hand_villains` é criada com base em showdown sozinho desde #B8.
   Mantido por opção (#B31 pt13): documentar em vez de mudar SQL.

**Regra de elegibilidade UI (canónica em `backend/app/routers/villains.py:67`):**

```sql
h.played_at >= '2026-01-01'
AND (
  -- (A) tag HM3 começa por 'nota'
  EXISTS (SELECT 1 FROM unnest(COALESCE(h.hm3_tags, '{}')) t WHERE t ILIKE 'nota%')
  OR
  -- (B) match SS↔HH válido + showdown  [DEAD branch pós-#B8 — ver nota acima]
  (h.player_names ->> 'match_method' IS NOT NULL AND h.has_showdown = TRUE)
  OR
  -- (C) canal Discord 'nota' + match SS↔HH
  ('nota' = ANY(COALESCE(h.discord_tags, '{}')) AND h.player_names ->> 'match_method' IS NOT NULL)
)
```

Nota: o filtro inclui A∨B∨C mas o JOIN com `hand_villains` (em
`recalculate_hands_seen` linha 471 e na search hands linha 394) limita
resultados a hands que tenham efectivamente row em `hand_villains` — o que
só acontece via classification A∨C∨D. Logo branch B é over-restrictive
mas inerte (filtra zero hands incrementais).

**Endpoints:**

- `GET /api/villains?search=...&site=...&sort=...` — lista villains com `hands_seen`.
- `GET /api/villains/search/hands?nick=...` — mãos do villain (JOIN `hand_villains` + filtro ABC).
- `POST /api/villains/recalculate-hands` — recalcula `hands_seen` aplicando ABC + apaga friends de `villain_notes`.

**Frontend:** `frontend/src/pages/Villains.jsx`. Auto-abre modal se URL tem `?nick=...`.

**Cross-references:** [`hm3_tags`](#23-hm3_tags), [`discord_tags`](#24-discord_tags), [`has_showdown`](#28-has_showdown), [`match_method`](#21-match_method), [`FRIEND_NICKS`](#45-friend_nicks).

---

### 6.4 Discord

**Em linguagem simples:** centro de operações para puxar mãos do Discord.

**Endpoints:**

- `GET /api/discord/status` — estado do bot.
- `GET /api/discord/sync-state` — última sync por canal.
- `GET /api/discord/stats` — counts por tipo/canal.
- `POST /api/discord/sync-and-process` — workflow completo (sync + replayer extract + Vision + backfill placeholders).
- `GET /api/discord/process-replayer-links/preview` + `POST /process-replayer-links?confirm=true`.
- `GET /api/discord/backfill-ggdiscord/preview` + `POST /backfill-ggdiscord?confirm=true`.
- `POST /api/discord/fix-ggdiscord-played-at?confirm=true` — corrige `played_at` de placeholders antigos (extrai do `<unix_ms>.png`).

**Frontend:** `frontend/src/pages/Discord.jsx`. Botão "Sincronizar Agora" único — único modo aceitável (manual). **Não mudar para auto sem autorização.**

**Mostra:** Mãos agrupadas por `discord_tags` (canal). `hm3_tags='GGDiscord'` é marker interno, não classificação.

**Cross-references:** [`discord_tags`](#24-discord_tags), [Pipelines de ingest](#5-pipelines-de-ingest), [`_create_placeholder_if_needed`](#76-_create_placeholder_if_needed).

---

### 6.5 Torneios (GG: Com SS / Sem SS; HM3 tab)

**Em linguagem simples:** mãos agrupadas por torneio.

**Tabs:**

- **GG**: `GET /api/mtt/dates?ss_filter=with|without|both&format=PKO|Vanilla&date_range=1d|3d|...&tm_search=...`. Lazy index por dia, com mãos paginadas via `GET /api/mtt/hands?ss_filter=...`.
  - "Com SS": `screenshot_url IS NOT NULL OR match_method IS NOT NULL`.
  - "Sem SS": `screenshot_url IS NULL AND match_method IS NULL`.
- **HM3**: ver §6.6.

**Filtros adicionais:** Excluir placeholders Discord (`from_discord_placeholder` em `_meta`), excluir mãos pre-2026.

**Frontend:** `frontend/src/pages/Tournaments.jsx`. Header de torneio: TM · nome · `$buy_in` · blinds · horas · contadores (mãos/SS/villains).

**Cross-references:** [`screenshot_url`](#26-screenshot_url), [`match_method`](#21-match_method), [`tournament_format`](#210-tournament_format--tournament_name--tournament_number--buy_in).

---

### 6.6 HM3

**Em linguagem simples:** centro de operações do script `.bat` HM3.

**Endpoints:**

- `POST /api/hm3/import` (CSV upload).
- `GET /api/hm3/stats` (counts por sala).
- `GET /api/hm3/nota-hands?page=N` (mãos com `'nota'` em `tags` — legacy).
- `GET /api/hm3/nota-stats`.
- `GET /api/hm3/admin/audit-discord-state` (read-only: dist por origin, with_discord_tags, via_discord_entries, sync_state).
- `POST /api/hm3/cleanup-old?before_date=...&dry_run=true&site=hm3|gg|all`.
- `POST /api/hm3/re-parse-all` (re-aplica parser).
- `POST /api/hm3/generate-auto-notes`.

**Frontend:** `frontend/src/pages/HM3.jsx`. Filtros: tag / data / PKO-NPKO / pré-flop vs pós-flop. Editor manual de tags com re-avaliação.

**Cross-references:** [`hm3_tags`](#23-hm3_tags), [Pipeline HM3](#52-hm3-post-apihm3import--csv).

---

### 6.7 MTT > GG

**Em linguagem simples:** drill-down por dia/torneio para todas as mãos GG.

**Endpoint principal:** `GET /api/mtt/dates`. Já documentado em §6.5.

Outros: `GET /api/mtt/hands` (lista mãos), `GET /api/mtt/hands/{id}` (detalhe), `GET /api/mtt/orphan-screenshots`, `POST /api/mtt/import` (legacy bulk MTT), `POST /api/mtt/rematch-screenshots`, `POST /api/mtt/re-enrich-all`.

**Cross-references:** [Torneios](#65-torneios-gg-com-ss--sem-ss-hm3-tab).

---

## 7. Regras de negócio transversais

### 7.1 Barreira pre-2026 (`is_pre_2026`)

**Em linguagem simples:** "qualquer mão jogada antes de 1 Jan 2026 é rejeitada na entrada".

**O que é:** Helper em `backend/app/ingest_filters.py:20`. Devolve `True` se `dt < 2026-01-01 UTC`. Aceita `None` (devolve `False`) para paths legítimos com `played_at` desconhecido (placeholder SS sem date).

**Aplicado em:**

- `backend/app/routers/import_.py:307, 332` — HH ZIP/TXT.
- `backend/app/routers/hm3.py:920` — CSV HM3.
- `backend/app/discord_bot.py:141` — Mensagens Discord.
- `backend/app/routers/screenshot.py:1129, 1232` — Placeholders e upload SS.
- `backend/app/services/hand_service.py:41` — Backstop final em `_insert_hand` legacy.

**Cross-references:** [Pipelines de ingest](#5-pipelines-de-ingest).

---

### 7.2 Auto-rematch retroactivo

**Em linguagem simples:** "depois de cada import, tentar de novo o cruzamento dos screenshots ainda sem mão".

**Como funciona:** Após `import_file` (HH bulk) e `import_hm3` correrem, é executada uma query que apanha entries com `entry_type='screenshot'` ou `(source='discord' AND entry_type IN ('replayer_link','image'))` em `status IN ('new', 'resolved')` que tenham `tm` em `raw_json`. Para cada uma, tenta match `WHERE hand_id = 'GG-{tm_digits}'`. Se houver hand, chama `_enrich_hand_from_orphan_entry` (idempotente — repeat no-op para hands já enriched).

**Localização:**

- `backend/app/routers/import_.py:347-411`.
- `backend/app/routers/hm3.py:1163-1203`.

**Cross-references:** [`match_method`](#21-match_method), [`_enrich_hand_from_orphan_entry`](#76-_create_placeholder_if_needed).

---

### 7.3 `_link_second_discord_entry_to_existing_hand`

**Em linguagem simples:** "quando um segundo SS Discord aparece para a mesma mão (ex: outro canal), liga-o em vez de criar duplicado".

**Localização:** `backend/app/routers/screenshot.py:780`.

**O que faz:**

1. Append do canal desta entry a `hands.discord_tags` (idempotente).
2. Marca entry como `'resolved'`.
3. Se a regra C passa a cumprir (`'nota'` em discord_tags + `match_method` populado + tem raw HH real + ainda sem `hand_villains`), dispara `apply_villain_rules(hand_db_id)` (canónico desde refactor #B23, pt10).

**Comportamento esperado quando muda:** Acrescentar canal `'nota'` a uma mão com match e showdown faz aparecer villain automaticamente.

**Cross-references:** [`discord_tags`](#24-discord_tags), [Vilões](#63-vilões-regras-abc).

---

### 7.4 `apply_villain_rules` — função canónica

**Em linguagem simples:** "depois de uma mão ter nicks reais, decide quais
adversários merecem entrar em Vilões e por que regra (A∨C∨D)".

**Localização:** `backend/app/services/villain_rules.py:45`.

**Substitui** (refactor #B23, pt10, commits `abb6d59` → `8476e87`):

- `mtt._create_villains_for_hand` (apagada na sua maioria; 4 call sites
  legacy mantidos com `mtt_hand_id` only — ver [§7.5](#75-call-sites-de-apply_villain_rules)
  e REGRAS §8).
- `mtt._create_ggpoker_villain_notes_for_hand` (apagada Onda 6).
- `hm3._create_hand_villains_hm3` (apagada Onda 6).
- `hm3._detect_vpip_hm3` (apagada Onda 6, #B27).
- `screenshot._maybe_create_rule_c_villain_for_hand` (apagada Onda 6).

**Signature:**

```python
apply_villain_rules(hand_db_id: int, *, conn=None) -> dict
```

**Inputs:**
- `hand_db_id` — id em `hands`.
- `conn` (opcional) — psycopg2 connection. Se `None`: abre/commita própria.
  Se fornecida: caller é dono da transacção.

**Output:**

```
{
    "n_villains_created":      int,    # rows inseridas em hand_villains
    "n_villain_notes_upserts": int,    # candidates 1ª vez (com Q6 guard)
    "skipped_reason":          str | None  # hand_not_found | gg_anon_no_match | no_candidates
}
```

**Algoritmo:**

1. `_read_hand` — SELECT atómico (site, raw, apa, has_showdown, hm3_tags,
   discord_tags, match_method, player_names).
2. **Invariante GG** — `site=GGPoker AND (match_method missing OR
   placeholder)` → skip com `skipped_reason='gg_anon_no_match'`. NUNCA cria
   villains em hands GG anonimizadas (REGRAS §6).
3. `_build_candidates` — lista non-hero do apa. Eligibility default
   `has_cards ∨ has_vpip`. Excepção #B19 (REGRAS §3.3): tag `'nota'`
   (HM3 ou canal Discord) aceita postflop-only (cobre BB-check-preflop a
   agir postflop sem VPIP).
4. `_filter_to_furthest_street` — mantém só candidates que chegaram à
   street máxima da hand (spec vilão principal, pt12). Hierarquia:
   `5=showdown(river+cards)`, `4=river`, `3=turn`, `2=flop`, `1=preflop`,
   `0=sem_dados`. Sem tie-break: empate na street máxima → todos passam.
   Edge case (max=0, apa placeholder): todos passam.
5. `_persist` — para cada candidate:
   - `_classify_villain_categories` (em `hand_service.py`) decide categorias
     aplicáveis (lista de A/C/D). Regra B foi eliminada em #B8 (pt7).
   - INSERT em `hand_villains` (1 row por categoria) — idempotente via
     partial UNIQUE `(hand_db_id, player_name, category) WHERE
     hand_db_id IS NOT NULL`.
   - **Q6 guard**: SELECT prévio em `hand_villains WHERE
     (hand_db_id, player_name)`. Se já existe (qualquer category), é
     repeat-call → skip UPSERT em `villain_notes` (evita duplo-incremento
     de `hands_seen`). Sem outros guards pós-#B29 (pt13).
   - UPSERT em `villain_notes(site, nick)` incrementa `hands_seen+1` na
     1ª chamada (idempotente nas seguintes via Q6).

**Regras de classificação** (delegadas a `_classify_villain_categories` em
`hand_service.py`):

- **A** — `hm3_tags` contém tag a começar por `'nota'` → `category='nota'`.
- **C** — `'nota' ∈ discord_tags` AND `match_method` real → `category='nota'`.
- **D** — `villain_nick ∈ FRIEND_HEROES` (Karluz, flightrisk) → `category='friend'`.

**Comportamento esperado quando muda:**

- Adicionar `'nota'` aos `discord_tags` de uma hand já matched faz
  aparecer villain via Regra C automaticamente (na próxima chamada).
- Mudar `hm3_tags` para incluir `'nota%'` faz aparecer via Regra A.
- Re-execução em hand já processada é no-op (Q6 guard + ON CONFLICT).
- Backfill manual: chamar via script (ver `backend/app/scripts/refix_villains.py`).

**Armadilhas conhecidas:**

- **Path bulk archive `mtt_hand_id` legacy** (REGRAS §8): 4 call sites em
  `mtt.py` (linhas 1162, 1782, 2098, 2193) ainda usam
  `_create_villains_for_hand(mtt_hand_id=X)` em vez de `apply_villain_rules`.
  Esses paths não passam por A∨C∨D e gravam `hand_db_id=NULL` em
  `hand_villains`. Pendente migração / deprecação.
- **Filtro SQL UI vs classification logic**: ver §6.3. `VILLAIN_ELIGIBILITY_CONDITION`
  em `villains.py:67-85` lista A∨B∨C, mas branch B é dead code pós-#B8.
- **#B29 (pt13) consolidou single source of truth**: `villain_notes.hands_seen`
  só é incrementado via `_persist` com Q6 guard. Outros 2 sítios
  (`mtt._create_villains_for_hand` legacy block, `mtt.re_enrich_all` loop)
  foram removidos. Inflação de `hands_seen` deixou de ser possível em
  paths normais.

**Cross-references:** [Vilões](#63-vilões-regras-abc), [`hm3_tags`](#23-hm3_tags),
[`discord_tags`](#24-discord_tags), [`match_method`](#21-match_method),
[`has_showdown`](#28-has_showdown), [`FRIEND_NICKS`](#45-friend_nicks),
[Call sites](#75-call-sites-de-apply_villain_rules), [REGRAS_NEGOCIO §3.3](REGRAS_NEGOCIO.md).

---

### 7.5 Call sites de `apply_villain_rules`

**Em linguagem simples:** "todos os sítios na app que disparam a função
canónica de criação de villains".

**Em produção (8 sítios):**

| Ficheiro:Linha | Contexto | Notas |
|---|---|---|
| `screenshot.py:869` | `_run_match_worker` (Bucket 1) | Fire-and-forget após match SS↔HH em background. |
| `screenshot.py:1479` | `_enrich_hand_from_orphan_entry` | Pipeline Discord/SS upload — após enrich completo. |
| `discord.py:851` | `backfill_ggdiscord` | Após placeholder Discord ganhar `discord_tags` populadas. |
| `hm3.py:930` | `import_hm3` (UPDATE branch) | Após UPDATE de hand existente (tags mudaram). |
| `hm3.py:1034` | `import_hm3` (INSERT branch) | Após INSERT de hand nova. |
| `mtt.py:1165` | `import_mtt` | Branch `hand_db_id` (não `mtt_hand_id`). |
| `mtt.py:1819` | `rematch_screenshots` | Endpoint admin, após enrich. |
| `mtt.py:1950` | `re_enrich_all` | Endpoint admin, após enrich. Loop UPSERT removido em #B29 (pt13). |

**Em scripts ad-hoc (2 sítios, manual):**

| Ficheiro:Linha | Contexto |
|---|---|
| `backend/app/scripts/backfill_showdown.py:96` | Backfill via Onda 5 #B23 refactor. Flag `showdown_only=True` deprecada — `apply_villain_rules` trata showdown via `_filter_to_furthest_street`. |
| `backend/app/scripts/refix_villains.py:147` | Refix manual; DELETE precedente preservado. |

**Caller pattern recomendado:**

```python
from app.services.villain_rules import apply_villain_rules

# Caso 1: caller possui transacção
with conn.cursor() as cur:
    # ... outras operações na mesma transacção ...
    result = apply_villain_rules(hand_db_id, conn=conn)
    # caller faz commit no fim

# Caso 2: chamada isolada
result = apply_villain_rules(hand_db_id)
# função abre/commita/fecha conn própria
```

**Comportamento esperado quando muda:**

- Adicionar novo trigger (futuro) que faça `discord_tags` mudar →
  chamar `apply_villain_rules(hand_db_id)` na transacção do trigger.
- Remover trigger existente: garantir que outro caller cobre o caso
  ou hands afectadas perdem cobertura A∨C∨D.

**Cross-references:** [§7.4 `apply_villain_rules`](#74-apply_villain_rules--função-canónica),
[Pipelines de ingest](#5-pipelines-de-ingest), [Vilões](#63-vilões-regras-abc).

---

### 7.6 `_create_placeholder_if_needed`

**Em linguagem simples:** "se chegou um SS mas a HH ainda não, cria uma 'mão fantasma' para não perder o screenshot".

**Localização:** `backend/app/routers/screenshot.py:1039`.

**O que faz:**

1. Se já existe uma hand para o `entry_id`, return.
2. Se `source` da entry é `'discord'` ou `'screenshot'`:
3. Se já existe hand `GG-{tm}`: chama `_link_second_discord_entry_to_existing_hand` (Discord) ou faz nothing (SS upload duplicado).
4. Caso contrário: INSERT placeholder com:
   - `origin='discord'` (Discord) ou `'ss_upload'` (UI).
   - `hm3_tags=['GGDiscord']` (Discord) ou `tags=['SSMatch']` (UI).
   - `match_method='discord_placeholder_no_hh'`.
   - `discord_tags=[channel_name]` (se Discord e canal resolvível).
   - `played_at` extraído do `<unix_ms>.png` (Discord) ou `null` (UI).
   - `screenshot_url=og_image_url` (Discord) ou `null` (UI; imagem em entry).
   - Filtra `is_pre_2026` defensivamente.
5. Marca entry como `'resolved'`.

**Comportamento esperado quando muda:** Quando a HH chegar via HH bulk ou HM3, `_insert_hand` placeholder upgrade detecta este placeholder e substitui pela HH real preservando metadados.

**Cross-references:** [`origin`](#22-origin), [`match_method`](#21-match_method), [`_insert_hand` placeholder upgrade](#77-_insert_hand-placeholder-upgrade), [`_link_second_discord_entry_to_existing_hand`](#73-_link_second_discord_entry_to_existing_hand).

---

### 7.7 `_insert_hand` placeholder upgrade

**Em linguagem simples:** "quando a HH real chega, substitui o placeholder e preserva tudo o que o screenshot já tinha trazido".

**Localização:** `backend/app/services/hand_service.py:31` (canónico). Versão legacy mais simples em `backend/app/hand_service.py:32`.

**Como detecta placeholder:**

- `raw` vazio **AND** uma de:
  - `match_method` começa por `'discord_placeholder_'` (canónico),
  - `'GGDiscord' in hm3_tags` (legado Discord),
  - `'SSMatch' in tags` (legado SS upload).

**O que faz:**

1. Captura `placeholder_metadata` (origin, discord_tags, hm3_tags, entry_id, player_names, screenshot_url, tags).
2. **Strip** do `match_method='discord_placeholder_*'` em `pn_clean`: se há `players_list` (Vision data) → promove para `'anchors_stack_elimination_v2'`; senão `pop`.
3. DELETE do placeholder.
4. INSERT da HH real.
5. UPDATE pós-INSERT para reaplicar metadados:
   - `origin = COALESCE(%(origin)s, origin)` — **reverse COALESCE**: preserva origin do placeholder sobre o INSERT.
   - `discord_tags`/`hm3_tags = COALESCE(NULLIF(...,'{}'),...)` — preserva, com strip do `'GGDiscord'`.
   - `entry_id = COALESCE(%(placeholder_entry_id)s, entry_id)` — reverse COALESCE.
   - `player_names`/`screenshot_url = COALESCE(...)` — preserva placeholder.
   - `tags` — merge dedup com NULLIF defensivo.

**Comportamento esperado quando muda:** Quebrar este UPDATE quebra **todo** o pipeline SS→HH — Discord/SSMatch placeholders deixam de subir para `anchors_stack_elimination_v2`, perdem-se em Estudo. **Não tirar.**

**Armadilhas conhecidas:**

- Schema default de `discord_tags` é `ARRAY[]::text[]` (empty), não NULL — daí o `NULLIF(...,'{}'::text[])` antes do COALESCE.
- `GGDiscord` em `hm3_tags` deve ser strippado: marker interno, não persiste no row final.
- Reverse COALESCE em `origin`/`entry_id`: primeiro ingress ganha; outras fontes ficam tracked via `discord_tags`/`hm3_tags`.

**Cross-references:** [`origin`](#22-origin), [`match_method`](#21-match_method), [`_create_placeholder_if_needed`](#76-_create_placeholder_if_needed), [Pipelines de ingest](#5-pipelines-de-ingest).

---

### 7.8 `ON CONFLICT (discord_message_id) DO NOTHING`

**Em linguagem simples:** "se já vimos esta mensagem do Discord, ignora silenciosamente".

**Localização:** `backend/app/services/entry_service.py:44`. Bate o partial unique index `uniq_entries_discord_message ON entries(discord_message_id) WHERE discord_message_id IS NOT NULL` (`backend/app/main.py:78`, `schema.sql:182`).

**Comportamento:**

- Re-sync após reset BD ou refresh manual: duplicados silenciados, sem `UniqueViolation`.
- `RETURNING` devolve zero rows quando há conflict — caller (`discord_bot.py:191`) trata `None` como "duplicado, OK".
- Para entries não-Discord (`discord_message_id IS NULL`), o partial index não cobre — INSERT normal sem conflict.

**Comportamento esperado quando muda:** Se removeres este ON CONFLICT, qualquer `_sync_guild_history` re-correr falha em massa.

**Cross-references:** [Pipeline Discord](#53-discord-bot-via-post-apidiscordsync-and-process), [Índices UNIQUE](#81-índices-unique).

---

## 8. Artefactos de BD críticos

### 8.1 Índices UNIQUE

| Index | Tabela | Localização (definição) | Para quê |
|---|---|---|---|
| `hands.hand_id` UNIQUE | `hands` | `schema.sql:55` | Deduplicação primária (`GG-{TM}`, `WN-{HID}`, etc.). Suporta o ON CONFLICT (hand_id) DO NOTHING / DO UPDATE em `import_hm3`, `import_mtt`, `_create_placeholder_if_needed`. |
| `villain_notes (site, nick)` UNIQUE | `villain_notes` | `schema.sql:90` | Suporta UPSERT em `apply_villain_rules._persist` (canónico pós-#B23/#B29). |
| `uniq_tournaments_with_tid (site, tid, date)` partial | `tournaments` | `schema.sql:41` | Dedup quando `tid` existe (WN/PS/WPN). |
| `uniq_tournaments_no_tid (site, name, date, buyin, position)` partial | `tournaments` | `schema.sql:47` | Dedup GG (sem tid fiável). `position` distingue re-entries. |
| `uniq_entries_discord_message` partial | `entries` | `schema.sql:182` / `main.py:78` | Silencia duplicados Discord via ON CONFLICT. **Crítico — não tirar.** |
| `uniq_mtt_hands_tm_time (tm_number, played_at)` | `mtt_hands` | `mtt.py:62` | Dedup mãos MTT bulk legacy. |
| `uq_hand_villains_hand_db_player (hand_db_id, player_name)` partial | `hand_villains` | `main.py:139` | Idempotência de `apply_villain_rules._persist` (canónico pós-#B23). Também usado pelo Q6 guard (SELECT prévio) para evitar duplo-incremento de `hands_seen`. |

**Comportamento esperado quando se tira:** ON CONFLICT clauses começam a explodir em `UniqueViolation` em re-imports.

---

### 8.2 Tabelas que NUNCA são truncadas em reset

**Endpoints destrutivos:**

- `POST /api/hands/admin/reset-all` (`hands.py:812`) — apaga `hand_villains`, `hands`, `entries`, `villain_notes`. **Mantém:** `tournaments`, `import_logs`, `discord_sync_state`, `study_sessions`, `users`, `mtt_hands`.
- `POST /api/hands/admin/reset-hm3` — apaga só `hands` Winamax/PS/WPN.
- `POST /api/hands/admin/reset-gg` — apaga `hand_villains`, `hands` GG, e **todas** as `entries`. Não apaga `discord_sync_state`.
- `POST /api/hands/admin/delete-before-2026` (`hands.py:1010`) — apaga `hand_villains` + `hands` com `played_at < 2026-01-01`.

**Tabelas seguras (nunca truncadas em fluxos normais):**

- `users` — auth.
- `tournaments` — pode ser regenerada via re-import P&L.
- `import_logs` — só CRIAR.
- `discord_sync_state` — guarda último `message_id` por canal; se apagar, próxima sync puxa **tudo**.
- `study_sessions` — histórico de tempo de estudo.

**Quando alguém pergunta...**

- *"Posso fazer reset total para reimportar?"* → Sim mas: `discord_sync_state` continua, então re-sync apanha desde o último `message_id` (não tudo). Se quiseres re-puxar tudo, TRUNCATE também `discord_sync_state` manualmente.

---

## 8.5 Aditamentos pós-26-Abr-2026

Esta secção é o **diff incremental** face ao snapshot original do MAPA. Substitui ou complementa entradas das §§2-8 onde indicado. Quando esta info estabilizar, integrar no corpo principal do MAPA em vez de viver como aditamento.

### 8.5.1 Regra de ouro evolucionada — placeholders Discord podem ir para Estudo

**Antes (§2.1, §6.1):** placeholders Discord (`match_method LIKE 'discord_placeholder_%'`) eram **sempre** excluídos da página Estudo via `STUDY_VIEW_GG_MATCH_FILTER`.

**Agora:** placeholders Discord não-`['nota']`-only podem entrar na vista **Por Tags** do Estudo, num enclave próprio chamado **"Discord — Só SS (sem HH)"**. Critério de elegibilidade extra:
- `match_method LIKE 'discord_placeholder_%'`
- AND `origin = 'discord'`
- AND `discord_tags` populado com pelo menos 1 elemento
- AND NÃO seja exclusivamente `['nota']` (essas continuam destinadas a Vilões via regra C quando HH chegar).

Outras vistas (Por Torneio, Cards, Tabela) continuam **sem** placeholders. A regra documentada em CLAUDE.md ("regra de ouro do Rui") está ampliada — não é "saem do Dashboard só com HH real" universal, mas sim "saem do Dashboard só com HH real **ou** entram no enclave dedicado da vista Por Tags".

### 8.5.2 Novo `STUDY_VIEW_GG_MATCH_FILTER_WITH_DISCORD_PLACEHOLDERS`

**Localização:** `backend/app/routers/hands.py:313-336`.

Constante SQL nova com 3 ramos disjuntos: (1) site != GGPoker; (2) GG com match real; (3) **GG placeholder Discord não-nota-only** (ramo novo). Variante do `STUDY_VIEW_GG_MATCH_FILTER` original (§2.1) que continua a ser usado quando `include_discord_placeholders=false`.

Aplicado em `/api/hands` (`hands.py:466-471`) e `/api/hands/tag-groups` (`hands.py:543-548`) condicionalmente conforme parâmetro novo.

### 8.5.3 Novo parâmetro `include_discord_placeholders`

**Localização:** parâmetro Query `bool = False` em:
- `/api/hands` — `hands.py:449`.
- `/api/hands/tag-groups` — `hands.py:524`.

Default `False` preserva 100% comportamento anterior. Quando `True` **e** `study_view=true`, aplica o filtro novo (§8.5.2) em vez do antigo.

Activado pelo frontend só na vista "Por Tags" do Estudo (`Hands.jsx:1617`) — outras vistas e outras páginas continuam a omitir o flag.

### 8.5.4 Novo endpoint `GET /api/hands/ss-without-match`

**Localização:** `backend/app/routers/hands.py:774-855`.

Lista unificada de **SSs sem match real** — universo `(source='screenshot' AND entry_type='screenshot') OR (source='discord' AND entry_type IN ('replayer_link','image'))`, filtrado por entries sem hand OR hand com `match_method` NULL/placeholder.

Cada item devolvido tem `type ∈ {'manual','replayer','image'}` (discriminador para badge UI). Mais campos: `entry_id`, `hand_db_id`, `tm`, `vision_done`, `hero`, `file_meta`, `screenshot_url`, `played_at`, `discord_posted_at`, `created_at`, `channel_name` (resolvido via subquery a `discord_sync_state`), `raw_json`.

Cobertura hoje: **157** items (vs **119** do `/api/mtt/orphan-screenshots` antigo, que cobria só placeholders GGDiscord). Endpoint antigo mantido **inalterado** (sem regressão noutros consumers, removível em fase de limpeza separada).

### 8.5.5 Novo objecto `ss_dashboard` em `/api/hands/stats`

**Localização:** `backend/app/routers/hands.py:687-756` (dentro de `hand_stats`).

Objecto JSON novo no response com 4 contadores mutuamente exclusivos:

```
ss_dashboard: {
    total:           <int>,
    with_match:      <int>,
    no_match_total:  <int>,                        # conveniência (soma 2 abaixo)
    no_match_manual: <int>,
    no_match_discord: { total, replayer, image }
}
```

Sanidade: `total = with_match + no_match_manual + no_match_replayer + no_match_image` (5 buckets disjuntos). Verificado em prod a 2026-04-26: 157 = 0 + 0 + 149 + 8.

Substitui semanticamente os campos antigos `total_screenshots` / `orphan_screenshots` / `ss_match_pending` (§6.2 Dashboard). Antigos **mantidos** no JSON para retro-compat até remoção planeada.

### 8.5.6 Novo componente frontend `PlaceholderHandRow`

**Localização:** `frontend/src/pages/Hands.jsx:1444-1573`.

Renderiza uma mão placeholder Discord no enclave "Discord — Só SS (sem HH)". Design: SS inline 200px à esquerda (clicável → nova aba via `<a target="_blank">` com `cursor: zoom-in`); coluna metadata com hora + chips de canais (azul claro #38bdf8) + hand_id curto + linha "Hero: <nick>" (roxo #818cf8) com stack + lista de nicks Vision do `players_list` (hero destacado roxo, restantes cinzentos); botão único "Apagar" à direita.

**Diferença vs `HandRow` matched:** **NÃO** mostra cartas/board/resultado/posição/badges showdown. Só mostra o que é conhecido sem HH (imagem + Vision data + tempo).

### 8.5.7 Bug-fix: agregador `tag-groups` colapsava placeholders

**Localização:** `backend/app/routers/hands.py:560-578`.

**Problema:** o CASE SQL do `tag_source='auto'` priorizava `hm3_tags` sobre `discord_tags`. Para placeholders Discord, `hm3_tags=['GGDiscord']` (marker interno) ofuscava `discord_tags=['pos-pko']` (canal real). Resultado: todos os 96 placeholders elegíveis colapsavam num grupo único `tags=['GGDiscord'], source='hm3'`.

**Fix:** cláusula nova nos 2 CASEs (tags + source). Quando `match_method LIKE 'discord_placeholder_%' AND origin='discord' AND discord_tags populado`, usar `discord_tags` como tema e `source='discord'`. Verificado em prod: 19 grupos por canal real após fix (`pos-pko`=34, `icm-pko`=11, `icm`=10, etc.).

4 condições defensivas mutuamente reforçadas evitam falso positivo.

### 8.5.8 Bug-fix: gate IIFE da vista Por Tags

**Localização:** `frontend/src/pages/Hands.jsx:1857`.

**Problema:** o gate de renderização do IIFE da vista Por Tags era `tagGroupsData.groups.length > 0` (assumption antiga: matched sempre existia). Com matched=0 e placeholders=N>0, o IIFE inteiro era saltado, e a secção "Discord — Só SS (sem HH)" (que **vive dentro do IIFE**) ficava invisível mesmo com `placeholderGroups` populado.

**Fix:** gate aceita também `placeholderGroups.length > 0`:
```js
{!loading && viewMode === 'tags' && (tagGroupsData.groups.length > 0 || placeholderGroups.length > 0) && (() => { ... })()}
```

Confirmado via logs temporários (commit `3ccc80f`, removidos em `4a4a024`).

### 8.5.9 Diagnóstico de discrepância 119↔157 entries Discord

Investigação a 2026-04-26 contra prod confirmou que a discrepância (119 hands placeholder vs 157 entries Discord `replayer_link`+`image`) decompõe-se em **3 buckets** com causas distintas:

| Bucket | N | Causa | Estado |
|---|---|---|---|
| 1 | 8 | Imagens directas Discord (`entry_type='image'`) nunca processadas pelo Vision; `process_replayer_links` filtrava só `replayer_link` | Bucket 1 redesign — ver §8.5.10 |
| 2 | 3 | Vision processou mas TM não detectado pela imagem; `_create_placeholder_if_needed` faz early return se `tm_final IS NULL` | Aceitar como falha ocasional do Vision |
| 3 | 27 | Cross-post: mesmo TM em múltiplos canais Discord → 1 hand por TM (UNIQUE em `hand_id`); `_link_second_discord_entry_to_existing_hand` agrega canais em `discord_tags` em vez de criar hand nova | **By design** — entries 2-N órfãs do JOIN mas agregadas via tags |

### 8.5.10 Tabela `hand_attachments` — implementada

**Estado:** implementado a 26-Abr-2026 (Bucket 1 fases I-VI). Ver entrada conceito completa em **[§2.11 `hand_attachments`](#211-hand_attachments)**.

Tabela criada via `ensure_hand_attachments_schema()` em `hands.py:197`. 3 attachments inseridos via backfill (att_ids 58/59/60, hands 117/115/67). 5 entries imagem continuam órfãs (sem mão sibling ±90s).

---

## 9. Como manter este documento

### Regras

1. **Qualquer mudança que produza ou consuma um conceito desta lista deve actualizar a entrada correspondente na mesma sessão.**
   - Exemplo: se adicionares uma rota nova que escreve em `origin`, actualiza a tabela "Onde é produzido" em [§2.2](#22-origin).
   - Exemplo: se mudares o filtro da página Estudo, actualiza [§6.1](#61-estudo-handsjsx).

2. **Bug novo descoberto vira entrada em "Armadilhas conhecidas".**
   - Anota o sintoma observável e a causa-raiz, não só o fix. Útil para próxima sessão evitar regressão.

3. **Quando adicionares um conceito que ainda não está mapeado, faz dele uma secção nova e mete-o no índice.** O índice é a primeira coisa que próxima Claude / Rui vê.

4. **Antes de afirmar produtor/consumidor, lê o código.** Não inventes linhas. Se não tens certeza absoluta, marca `(localização aproximada — verificar)`.

5. **Se este documento e o código discordarem, o código ganha.** Actualiza este documento na mesma sessão — não deixes para depois.

### Como reaplicar este formato

Cada entrada de conceito segue:

```
### N.M `nome_do_conceito`

**Em linguagem simples:** uma frase, sem jargão, para o Rui.

**O que é (humano):** 1-2 parágrafos.

**Detalhes (técnico):**

| Onde é produzido | Função |
| ... | ... |

| Onde é consumido | Função |
| ... | ... |

| Valor | Significado |
| ... | ... |

**Comportamento esperado quando muda:** ripple-out.

**Armadilhas conhecidas:** (omite se não houver)

**Quando alguém pergunta...** 3-5 perguntas + respostas curtas.

**Cross-references:** links internos.
```

### Conceitos adicionados ao índice original (registo)

A pedido do prompt, segue lista do que **foi acrescentado** face ao índice original:

- `2.8 has_showdown` — central para regra B de villains; merecia entrada própria.
- `2.9 position_parse_failed` — flag adicionada por `main.py:121`, só presente como nota.
- `2.10 tournament_format / tournament_name / tournament_number / buy_in` — quatro colunas relacionadas que vivem juntas.

Nada removido do índice original.
