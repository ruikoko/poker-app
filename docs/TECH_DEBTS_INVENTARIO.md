# Inventário Tech Debts — 4-Mai 2026 pt13 (fechada)

Compilação read-only baseada em journals (23-24 Abr → 29-Abr pt6), VALIDACAO_END_TO_END §6/§7/§11, MAPA_ACOPLAMENTO, git log, e leitura directa do código.

Substitui os fragmentos espalhados pelos vários docs como **single source of truth** sobre tech debts pendentes. Para descrição detalhada de cada fix fechado, consultar journal/commit correspondente.

---

## Estado actual (7 Maio 2026 fim pt16)

pt16 atacou 3 itens num único arco de sessão. Sem journal próprio ainda — registo neste inventário substitui temporariamente.

- **#5 / #B26** (TAGS Discord vazia em Estudo): verificado em prod já resolvido. Chips Discord azul e `OriginBadge` (HM3 amarelo / Discord azul / HM3+D roxo) implementados em #B17 (pt9, commit `7806d33`) e reforçados em pt15. Sem código novo; backlog estava desactualizado.
- **#6** (status inconsistency Discord ao re-linkar via Vision): mãos `'resolved'` (Revista) voltavam a `'new'` (Nova) sempre que Vision corria enrichment. Causa: `screenshot.py:1432` forçava `study_state='new'` incondicionalmente. Fix em 3 fases num só commit (`be0b9c3`):
  - **Fase 1** — `screenshot.py` deixa de força `'new'`: passa a `CASE WHEN study_state = 'mtt_archive' THEN 'new' ELSE study_state END` (preserva `resolved`).
  - **Fase 2** — `match_state` computado por SQL CASE em 8 endpoints (`hands.py` × 3, `mtt.py` × 2, `tournaments.py`, `villains.py`, `hm3.py`). 5 valores: `archive` > `orphan` > `pending` > `matched`.
  - **Fase 3** — badge unificado de 5 estados (Nova azul / Revista verde / Pendente âmbar / Arquivo cinza / Órfã vermelho discreto) em `HandRow.jsx`, `Hands.jsx`, `Discord.jsx`, `Dashboard.jsx`, `HM3.jsx`. Botão "Marcar Revista" guarded para `match_state='matched'` (placeholders/arquivo/órfãs não estudáveis). Princípio invariante registado: linkagem é precondição obrigatória para o eixo Estudo.
- **Bug "Copiar HH"** (rejeitado pelo HRC com "No valid hand-history found"): regex `re.split(r"(?=(?:Poker\s+)?Hand\s*#)")` em `gg_hands.py:536` matcheia 2 vezes por hand (uma com `Poker `, outra sem) — `re.split` corta em ambos os pontos, descartando o prefixo `Poker ` para fora do bloco. Magnitude prod: 100% das 15.809 hands GG 2026. Fix (commit `0d18c52`): split ancorado em `^Poker\s+Hand\s*#` com `re.MULTILINE`. Validado: novo regex produz blocos com prefixo intacto; antigo produz `["", "Poker ", "Hand #..."]`.
- **Bug HRC concatenar BB+ante**: confirmado externo. App reproduz exactamente o input do GG; HRC interpreta `Level12(3,500/7,000(1,000))` agregando BB+ante quando colado directo do ZIP HH original. Sem acção do nosso lado.

### Tech Debts fechados pt16

| # | Hash | Descrição |
|---|---|---|
| **#B26** ✅ | (verificação) | Investigar cor das TAGS na secção Estudo. Verificado em prod (2026-05-07): vista 'tags' mostra chips Discord (azul `#5865F2`) e `OriginBadge` (HM3 amarelo / Discord azul / HM3+D roxo) — implementado em #B17 (pt9). Backlog desactualizado, sem código novo. |
| **#6** ✅ | `be0b9c3` | Status inconsistency Discord ao re-linkar via Vision. Backend: `screenshot.py:1432` preserva `resolved` (só promove `mtt_archive→new`); 8 endpoints adicionam coluna computada `match_state` por SQL CASE. Frontend: badge unificado de 5 estados; botão "Revista" guarded. Princípio: linkagem é precondição para Estudo. |
| **Bug "Copiar HH"** ✅ | `0d18c52` | Parser GG `gg_hands.py:536` re-split com lookahead `(?:Poker\s+)?Hand\s*#` matcheia 2× por hand, descartando `Poker `. Fix: split ancorado `^Poker\s+Hand\s*#` MULTILINE. 100% das 15.809 hands GG 2026 afectadas — wipe BD + re-import ZIP HM3 GG → 15.811 hands restauradas com prefixo correcto. Bug HRC ao interpretar BB(ante) registado como problema externo. |

### Operações pt16 (sem código)

- **Wipe BD**: 15.815 hands GG + 88 `hand_villains` apagadas. 305 entries Discord revertidas para `status='new'` para re-processamento. Tudo em transacção única; validações intra-transacção todas zero (órfãs, hands GG residuais).
- **Re-import ZIP HM3 GG**: 15.811 hands restauradas com `raw` começando em `Poker Hand #`. Confirmado em prod via SQL: `prefix 'Poker Hand #' = 15811 / 15811`.
- **Discord re-sync**: ainda por fazer pelo Rui — 319 entries em `status='new'` à espera. Re-sync vai re-criar as 4 placeholders Discord/SS em falta + atribuir matches SS↔HH com pipeline corrigido.

### Ainda em aberto pt16

- Re-sync Discord pelo Rui (operacional, fora de tech debt).
- Validação visual end-to-end na app (Estudo, Discord, Dashboard, modal de mão).

---

## Estado actual (7 Maio 2026 fim pt15)

pt15 foi sessão exclusiva de iteração visual — UI/UX. Sem mudanças de backend, parsers, schema ou dados. Painel torneio (TournamentHeader + Hands.jsx Estudo), popup do replayer (ReplayerPage), e cartas de poker (9 callers) reformulados. Detalhes em `JOURNAL_2026-05-06-07-pt15.md`.

- **Sessão pt15 fechou**: zero tech debts numerados de backlog (sessão visual não atacou tech debts pendentes).
- **Sessão pt15 introduziu** 1 novo tech debt: 8 cópias inline de `PokerCard` + 1 shared (ver §pt15 abaixo).
- **Sessão pt14 fechou** (não documentado nesta inventário ainda): #P10. **Pendentes carry-over de pt14**: #P9, #P11, #P12.

### Tech Debts e pendências pt15

#### Tech Debt nova
| # | Descrição | Esforço |
|---|---|---|
| **#TD-pt15-1** | Unificar 8 cópias inline de `PokerCard` num componente único (`components/PokerCard.jsx` shared). Cópias actuais em: `HandRow.jsx`, `Dashboard.jsx`, `Discord.jsx`, `Hands.jsx`, `HM3.jsx`, `Tournaments.jsx`, `Replayer.jsx` (RCard), `ReplayerPage.jsx` (RCard), `HandDetailPage.jsx` (RCard). Divergências entre cópias (sizes, paletas) já harmonizadas em pt15 mas mantidas em código separado. | ~1h |

#### Pendências de iteração visual (média prioridade — opcional UX)
- **Tournaments e HM3**: aplicar mesma limpeza visual do Estudo (bareMode + watermark)? Adiada nesta sessão. Decisão Rui se aplicar a todas as páginas para consistência ou manter modo normal nessas duas.
- **Replayer head-up**: D + SB badges sobrepostas no mesmo player (BTN = SB em head-up). Cenário raro em MTT.
- **Replayer slot único topo (50,10)**: badge cobre o nome do player. Aceitável por agora, melhorar se aparecer queixa.

#### Housekeeping (baixa prioridade)
- **Assets em `frontend/public/logos/`** ficaram não-referenciados após pt15: `gg1.png`, `gg2.jpg`, `ya.webp`, `wina1.png`, `wina2.png`, `ps.png`. Apenas `gg_horizontal.png` e `ps_logo.png` em uso. Candidatos a remoção numa sessão futura de housekeeping.
- **`composeTournamentTitle` em `HM3.jsx`**: sem callers depois da iteração customTitle (substituída por extracção inline). Limpeza cosmética.
- **`components/Replayer.jsx`** (legacy, distinto de `pages/ReplayerPage.jsx`): possivelmente não-usado. Verificar e remover se confirmado.

#### Backlog operacional carry-over (NÃO atacado em pt15)
- **Discord/HM3 tag fragmentation** (carry-over de sessões anteriores) — afecta quase todas as study hands. URGENTE quando voltarmos ao backend.
- **2nd Discord entry para duplicate TMs** — pendente.
- **Discord pipeline para Winamax replayer URLs** (Vision não extrai TM dos URLs Winamax).
- **71 SS Discord sem match** (Replayer 57 + Imagem 14): listagem com link/data/origem, pendente investigação.
- **Estudo: torneios estudados rasurados** → desaparecem; toggle para mostrar ocultos.

---

## Estado actual (4 Maio 2026 fim pt13)

pt12 fechou #B33 (regressão da Onda 8 do refactor #B23 documentada em pt11 retrospectivo). Root cause: regex `r'TM(\d+)'` em `screenshot.py:307` exigia prefixo `TM` literal; Vision omitiu em 2/26 entries. Fix: word-boundary `r'\b(\d{8,12})\b'` (commit `e7d88b2`). Backfill retroactivo curou as 2 hands afectadas (id=2083, id=2297) — hand 2297 ganhou 2 villains via Regra C; hand 2083 ficou em canal `icm-pko` com `mm` populado mas 0 villains (correcto). BD final: 1172 hands, 24 enriched, 47 villains, 7/7 nota com villains. **Onda 8 do refactor #B23 declarada COMPLETA.**

- **Sessões pt9 + pt10 fecharam:** #B12, #B14, #B15, #B16, #B17, #B18, #B19, #B19-ext, #B23, #B27, #B32 (11 tech debts).
- **Pendentes numerados pós-pt10:** #11, #B10, #B11, #B13, #B-edge, #B20, #B21, #B26, #B28, N1, N2, N3.
- **Pendentes não-numerados:** path bulk archive `mtt_hand_id` legacy (4 call sites em `mtt.py` — REGRAS §8).
- **Onda 8 e 9 do refactor #B23 ficaram em estado "parcial":** teste regressão (delete + re-import GG ZIP) e validação manual visual SS↔HH adiados para pt11.
- **Onda 9 (pt11)** — Rui validou visualmente 3/3 hands canal nota (1070, 261, 878). Algoritmo SS↔HH confirmado correcto em prod. **ONDA 9 FECHADA ✓**
- **Onda 8 (pt11+pt12)** — re-import GG ZIP correu 3-Mai 14:11 UTC. Estado pt11 inicial: 22 enriched, 45 villains, 6/7 nota com villains (regressão #B33). Pt12 fix + backfill retroactivo: **24 enriched, 47 villains, 7/7 nota com villains. ONDA 8 FECHADA ✓**

### Tech Debts fechados pt13

| # | Hash | Descrição |
|---|---|---|
| **#B-NOVO-2** ✅ | `554cafb` | Resolvido por #B32 (pt10) + assert defensivo extra. Verificação prod confirmou `degenerate_count=0`. Sem evidência de re-aparecimento. Assert em `screenshot.py:_enrich_hand_from_orphan_entry` antes da chamada a `_build_anon_to_real_map`: levanta `ValueError` explícito se apa só tem `_meta` (placeholder-only) — torna a falha visível em vez de silent skip. |
| **#B29** ✅ | `d478b68` | hands_seen double-count em refix. Investigação: prod limpo (inflação=0), mas código tinha 2 sítios desprotegidos (`mtt.py:_create_villains_for_hand` e `mtt.py:re_enrich_all`). Opção α: removidos os 2 blocos UPSERT redundantes + dead code associado (-32 linhas net). Comentários explicativos no código. `apply_villain_rules` continua single source of truth com Q6 guard. |
| **#B31** ✅ | `b455ff5` | MAPA_ACOPLAMENTO actualizar para refactor #B23 + #B29 + vilão principal. §7.4 substituída (doc canónica de `apply_villain_rules`), §7.5 nova (call sites). §6.3 distingue UI filter (A∨B∨C, branch B dead pós-#B8) vs classification logic (A∨C∨D). 7 cross-refs actualizadas em §2.1, §2.8, §5.2, §5.4, §7.3, §8.1. Opção α adoptada para `VILLAIN_ELIGIBILITY_CONDITION` — branch B mantido no SQL como dead code documentado em vez de remover. |
| **#B22** ✅ | `875be7a` | Dashboard reordenar painéis (SS subiu para nível 2) — fechado como parte do refactor Dashboard expandido |
| **Refactor study_state** ✅ | `c3c14c4` | 4 estados → 3 (remove review+studying nunca usados). Apaga Inbox.jsx (-1034 linhas). UI mostra "Nova"/"Revista". |
| **Dashboard expandido** ✅ | `875be7a` | Painel Mãos por estudar com top 3 tags + 4 salas. Total de mãos com X revistas. SS sobe para nível 2. OrphanList paginação 10+10. |

### Tech Debts fechados pt12

| # | Hash | Descrição |
|---|---|---|
| **#B33** ✅ | `e7d88b2` | Regex TM em parser Vision tolerante a omissão do prefixo (`r'TM(\d+)'` → `r'\b(\d{8,12})\b'` em `screenshot.py:307`). Cura retroactiva: 2 entries afectadas (id=30, id=36) → hands 2297 e 2083 enriched + villains criados onde aplicável (hand 2297: 2 villains via Regra C; hand 2083: 0 villains, canal `icm-pko` não-nota). |
| **Vilão Principal** ✅ | `0ebacfd` | `apply_villain_rules` filtra candidates a quem chegou mais longe na mão. Spec definida + implementada + backfill retroactivo (47→34 `hand_villains`, 7/7 nota preservadas). Sem migration. Validado visualmente em prod pelo Rui. |
| **GTO 404** ✅ | `304eecf` | Router `gto.py` não estava wired em `main.py:include_router` (fix 2 linhas, smoke test HTTP 401). |
| **#13c** ✅ | `d959ad8` | SITE_COLORS aliases legacy removidos; callers (Dashboard.jsx, HandRow.jsx) consolidados a `SITE_COLORS` directo. 3 ficheiros tocados. |
| **#B25** ✅ | `ba2792b` | Agrupar torneios por `tournament_id`. Fix bugs cross-midnight (chave `${day}__${name}` dividia 1 torneio em 2) e nomes duplicados (chave `${name}` fundia torneios distintos). Ambos os modos passam a usar `tm:${tournament_number}` como chave. |
| **Stack Inicial GG** ✅ | `68a9e8a` + `799864e` + `457048f` + `a2158c3` | Tabela canónica `tournaments_meta` (PK `tournament_number+site`, restrito a GG). Hook em `_run_zip_import`, endpoint `GET /api/tournaments/meta?tms=...`, frontend lookup com fallback graceful. Backfill 26 TMs → 20 rows GG. |
| **#B34** ✅ | `43c0041` | ID hand visível em todas as vistas (Estudo Por Tags / Por Torneio / Tabela / Cards, Dashboard "Últimas mãos", HandDetailPage Normal+Placeholder, Tournaments drill-down). 4 ficheiros tocados. |
| **#B30** ✅ | `580be1c` | 142 scripts ad-hoc removidos da raiz + 28 patterns adicionados ao `.gitignore`. 3 backfills úteis preservados como tracked. |

### Tech Debts fechados pt9 (carry-over de pt8)

| # | Hash(es) | Descrição |
|---|---|---|
| **#B12** ✅ | (pt9) | Helper centralizado `append_discord_channel_to_hand` propaga `discord_tags` mesmo em hands GG sem match. |
| **#B14** ✅ | (pt9) | Estudo aceitava mãos sem `tournament_name`/`buy_in`/`site` — resolvido na sequência de #B17 (filtros `STUDY_VIEW_*` consolidados). |
| **#B15** ✅ | `1cca3a6` | Estudo passa a excluir mãos só com tag `nota` (HM3 ou Discord). Caso 2 e 5 dos canónicos. |
| **#B16** ✅ | (pt9) | `_apply_channel_tags` cross-post HH text — coberto pelo helper centralizado #B12. |
| **#B17** ✅ | `7806d33` | Estudo unifica tags HM3 + Discord (1 chip por nome normalizado), `OriginBadge` por mão, remove secções por origem. |
| **#B18** ✅ | (pt9) | Drill-down torneio passa a mostrar `OriginBadge` por mão (consistência com Estudo pós-#B17). |
| **#B19** ✅ | `ca9fbc3` + `f0b778d` + `ab8e033` | Vilões aceita non-hero postflop quando `hm3_tags ~ 'nota%'`; bypass da pré-condição `has_cards∨has_vpip`. (estendida em pt10 — ver #B19-ext) |

### Tech Debts fechados pt10

| # | Hash(es) | Descrição |
|---|---|---|
| **#B10** ✅ (mínimo) | `66db5cc` | Persistir `tournament_name` extraído por Vision em `entries.raw_json` (1 linha em `_run_vision_for_entry`). SS uploaded a partir deste commit. Backfill diferido. |
| **#B23** ✅ | `abb6d59` → `8476e87` (8 commits) | Refactor completo: 4 funções de criação de villains → 1 canónica `apply_villain_rules` em `services/villain_rules.py`. 18 call sites unificados (12 migrados, 5 skips legacy `mtt_hand_id` + 1 interno). ~470 linhas líquidas removidas. Resolveu Regra C não-disparada no caminho Discord+ZIP. |
| **#B27** ✅ | `8476e87` | Apagados blocos "Extract villains for nota++ hands" em `hm3.py` + função `_detect_vpip_hm3` redundante. Incluído na Onda 6 do refactor #B23. |
| **#B32** ✅ | `5fe2201` | Enrich SS↔HH não grava mais `match_method='anchors_stack_v2'` com `anon_map` vazio. Guard idempotência verifica também `existing_anon_map` populado. Defesa em camadas: previne novas + cura estado existente quando auto-rematch revisita. |
| **#B19-ext** ✅ | `677a1fb` | Excepção #B19 estendida a `'nota' ∈ discord_tags` (paridade semântica com tag HM3 `nota%`). Variável renomeada `has_nota_hm3` → `has_nota_intent`. Hand 261 passou a ter villains. |

### Tech Debts abertos pós-pt10 (carry-over + novos)

| ID | Título | Severidade | Origem | Esforço |
|---|---|---|---|---|
| **#11** | Botão eliminar villain manual. Decisão pt13: blacklist persistida escolhida; implementação adiada. Historicamente ligado a #12 (re-arquitectura modal). | 🟡 Funcional | pt7 | ~2-3h |
| **#B10** (full) | Vision galeria — extrair `tournament_name` para filtragem (fix mínimo já aplicado) | 🟢 UX | pt7 | ~2-3h |
| **#B11** | Auto-tag mãos via LLM (ideia exploratória) | 🟢 Feature | pt7 | ~3-4h |
| **#B13** | Contadores `last_sync` (N/M/K) medem entries criadas em vez de trabalho útil. Decisão pt13: manter como está, não tocar. Vive na página Discord, não migra para Dashboard. | 🟢 UX | pt8 | ~1h |
| **#B-edge** | Hero detection seat não-central (1/23 ≈ 4.3% taxa) | 🟢 Edge case | pt7 | ~30 min |
| **#B20** | Filtros HM3 por tag (não por nick) | 🟢 UX | pt10 | a estimar |
| **#B21** | Dashboard "por estudar" filtrar por elegibilidade | 🟢 UX | pt10 | a estimar |
| **#B26** ✅ FECHADO pt16 | Investigar cor das TAGS na secção Estudo. Verificado em prod (2026-05-07): chips Discord + `OriginBadge` já existiam (#B17 pt9). Backlog desactualizado, sem código novo. Detalhes em "Estado actual fim pt16" no topo. | 🟢 UX | pt10 | 0 (verificação) |
| **#B28** ✅ FECHADO pt14 | Counter `villains_created` no response do `POST /api/hm3/import` (e por extensão output do `.bat`) ficou silenciosamente em 0 desde refactor #B23 (pt10): a função canónica `apply_villain_rules` passou a devolver `dict` com `n_villains_created` em vez do `int` da predecessora, e os 2 call sites em `hm3.py:930` e `hm3.py:1034` passaram a ignorar o return. Fix: captar return em ambos os call sites e somar `n_villains_created` ao counter. Cosmético — sem efeito em dados, regras de elegibilidade ou pipelines downstream. | 🟡 Funcional | pt10 | ~30 min (consumido) |
| **N1** | MAPA_ACOPLAMENTO.md desactualizado: cabeçalho diz "Última actualização 2026-04-26" + drift pt10/pt12/pt13 (refactor #B23, vilão principal, study_state, tournaments_meta) | 🟢 Docs | pt14 | a estimar |
| **N2** | VISAO_PRODUTO.md tem refs de linha exactas (ex: `hands.py:567-574`, `hands.py:565-566`) que mexem com refactors. Substituir por refs simbólicas (constantes nomeadas) ou re-âncorar | 🟢 Docs | pt14 | ~30 min |
| **N3** | Promover regra "imagens directas Discord NUNCA criam mãos" (anexos `.png/.jpg/.webp` + Gyazo) de CLAUDE.md "Imagens de contexto Discord" para REGRAS_NEGOCIO.md §6 como regra dura | 🟢 Docs | pt14 | ~15 min |
| **#P9** ✅ FECHADO pt14 | Parser `buy_in` em `tournaments_meta` falha em vírgula de milhar — torneio com nome `'$1,050 GGMasters HR'` ficou com `buy_in=1.00`. Causa: regex `\d+(?:\.\d+)?` não suportava `,`. Fix: `_NUM_PATTERN = \d{1,3}(?:,\d{3})*(?:\.\d+)?` + helper `_to_float` em `gg_hands.py:114-148`. Backfill: 245 hands + 1 tournaments_meta. Mini-test 5/5. Commit a registar abaixo. | 🟡 Funcional | pt14 | ~30 min (consumido) |
| **#P10b** ✅ FECHADO pt14 | Queries X1.1 e X1.3 do `VERIFICACAO_PIPELINES.md` overly broad. X1.1 refinada com `STUDY_VIEW_REQUIRES_HH + STUDY_VIEW_HAS_STUDY_TAG` (2970→0). X1.3 refinada como sentinela do filtro UI (combinação contraditória: `STUDY_VIEW_HAS_STUDY_TAG` + "todas as tags = nota" = sempre 0; > 0 indica regressão no filtro UI). Validação BD: 2970→0, 3014→0. | 🟢 Docs | pt14 | ~30 min (consumido) |
| **#P10c** ✅ FECHADO pt14 | Query Q3.6 do `VERIFICACAO_PIPELINES.md` filtro hardcoded substituído por `cardinality(COALESCE(discord_tags, '{}'::text[])) > 0`. Validação BD: 40→57 hands apanhadas (canais como `pos-nko` que estavam invisíveis). | 🟢 Docs | pt14 | ~10 min (consumido) |
| **#P11** | Parser `_extract_buyin_numeric` apanha **primeiro `$X,YYY`** do nome do torneio sem distinguir buy-in vs prize pool. Caso real Fase B: `Daily $100,000 #ThanksGG Flipout` ficou com `buy_in=100000.00` (era GTD/prize pool, não buy-in). Magnitude: 1/236 torneios em pt14 Fase B (0.4%). Resolvido caso pontual com DELETE; fix conceptual aberto: parser semântico que reconheça padrões `$X GTD` / `$XM GTD` como prize pool. | 🟢 UX/Cosmético | pt14 | ~45 min |
| **#P12** | Parser não tolera símbolos monetários não-Latin1 (yuan ¥, won ₩, yen ¥). Torneios em moedas asiáticas vêm com `�` (replacement char U+FFFD) onde devia estar o símbolo monetário. Caso real Fase B: `Zodiac Late Night 6-Max �220` ficou com `buy_in=NULL`. Magnitude: 1/236 torneios em pt14 Fase B (0.4%). Causa: encoding Latin-1/Win-1252 do ficheiro GG antes do parser. Fix futuro: ler ficheiros com encoding UTF-8 ou parser tolerante a símbolos não-`$`. | 🟢 UX/Cosmético | pt14 | ~30 min |
| **#P13** ✅ FECHADO pt14 | Endpoint `process-replayer-links` com `limit` hardcoded 200 em `sync-and-process` + `ORDER BY id DESC` cortava entries silenciosamente quando volume >200. IDs mais baixos (canais sincronizados primeiro pelo bot) ficavam sempre fora do batch. Detectado pt14 Fase B: 83/283 entries (29%) cortadas, **100% das 67 mensagens do canal `nota` afectadas**. Adicional: filtro `img_b64 IS NULL` não cobria estado intermediário (img extraído mas Vision pendente). Fix em commit 2f15445: paginação interna até esgotar candidatos + cap defensivo 50 iter + `ORDER BY id ASC` (cronológico) + secção 4b inline em `sync-and-process` para apanhar estado intermediário + counter `new_entries` expandido. Validado em prod: 83 entries recuperadas, 72 hands canal `nota` enriched, 88 villains via Regra C criados (80 nicks únicos), princípio invariante GG anon mantido. | 🔴 Funcional | pt14 | ~2h (consumido) |
| **`mtt_hand_id` legacy** | 4 call sites em `mtt.py` (linhas 1264, 1882, 2202, 2297) ainda passam `mtt_hand_id` em vez de `hand_db_id`. REGRAS §8. | 🟢 Refactor | pt10 | a estimar |

### Pendente operacional pt11

- **Onda 8** — teste regressão (delete + re-import GG ZIP) confirma que pipeline produz mesmo resultado em re-execução.
- **Onda 9** — validação manual visual SS↔HH (Rui escolhe 3-4 hands ao calhas, valida visualmente que nicks atribuídos batem com imagem do SS).

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

<!-- TODO futura: §2 tem entries ✅ RESOLVIDO misturadas com bugs ainda abertos. Limpar separadamente. -->

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

### #B14 — Estudo aceita mãos sem tournament_name/buy_in/site

- **File:** `backend/app/routers/hands.py:359-363` (`STUDY_VIEW_GG_MATCH_FILTER`).
- **Origem:** Visão de produto pt9 (regra de negócio do Rui consolidada em `docs/VISAO_PRODUTO.md`).
- **Sintoma:** Mãos podem entrar em Estudo sem campos obrigatórios de identificação do torneio. Filtro actual só exige `match_method` populado; permite hands sem `tournament_name`, `buy_in` ou `site`.
- **Severidade:** 🟡 Funcional. Mostra mãos incompletas em Estudo, contraria regra de negócio.
- **Fix:** adicionar `AND h.tournament_name IS NOT NULL AND h.buy_in IS NOT NULL AND h.site IS NOT NULL` ao `STUDY_VIEW_GG_MATCH_FILTER` (e à variante `..._WITH_DISCORD_PLACEHOLDERS` quando aplicável).
- **Esforço:** ~30 min + validação contra BD prod.

### #B15 — Estudo aceita mãos só com tag "nota"

- **File:** `backend/app/routers/hands.py:359-363` (`STUDY_VIEW_GG_MATCH_FILTER`); ver também `..._WITH_DISCORD_PLACEHOLDERS` linhas 371-389.
- **Origem:** Visão de produto pt9 (regra de negócio do Rui consolidada em `docs/VISAO_PRODUTO.md`).
- **Sintoma:** Regra de negócio: mão só com tag `nota` (HM3 ou Discord) → só Vilões, não Estudo. Implementação actual cobre **parcialmente** o caso `discord_tags=['nota']` em placeholders Discord (`include_discord_placeholders=true`), mas falha:
  - (a) hands HM3 com `hm3_tags ⊆ {nota, notas, nota+, nota++}` exclusivamente.
  - (b) hands GG match-real com `discord_tags=['nota']` exclusivamente (não placeholders).
- **Severidade:** 🟡 Funcional. Polui Estudo com mãos destinadas a Vilões.
- **Fix:** estender o filtro principal para excluir hands cujo conjunto de tags de estudo (hm3_tags excluindo padrões `nota%` + discord_tags excluindo `nota`) seja vazio. Casos canónicos 2 e 5 (`docs/VISAO_PRODUTO.md`) servem de teste.
- **Esforço:** ~30-45 min + validação.

### #B16 — `_apply_channel_tags` filtra por entry_id (vector latente HH cross-post)

- **File:** `backend/app/discord_bot.py:244-257` (`_apply_channel_tags`).
- **Origem:** Identificado durante diagnóstico #B12 (pt9, 30-Abr).
- **Vector:** Quando uma HH text é cross-postada em 2 canais Discord, a 1ª entry processada cria as hands via `process_entry_to_hands` e `_apply_channel_tags` popula `discord_tags` com o canal A. A 2ª entry chega com a mesma HH; `process_entry_to_hands` faz `INSERT ... ON CONFLICT DO NOTHING` (não cria hands duplicadas); `_apply_channel_tags` filtra `WHERE entry_id = %s` (entry da 2ª) e não toca em nada — o canal B nunca é appendado.
- **Severidade:** 🟡 Funcional latente. Magnitude actual: 0 hands afectadas em prod (Rui não usa cross-post HH text — usa replayer_link, coberto por #B12 fix).
- **Fix proposto:** alterar `_apply_channel_tags` para também tocar hands cujo `hand_id` derive da mesma HH parseada da entry, mesmo quando `entry_id` ≠ entry actual. Em alternativa, chamar `append_discord_channel_to_hand` (helper #B12) para cada hand_id afectado.
- **Esforço:** ~45 min + validação contra cenário simulado.
- **Bloqueado por:** nada. Tem prioridade baixa enquanto magnitude=0.

### #B17 — Estudo separa tags por origem em vez de unificar (DIVERGÊNCIA 5)

- **File provável:** `frontend/src/pages/Hands.jsx` (vista "Por Tags") + `backend/app/routers/hands.py` (endpoint tag-groups).
- **Origem:** Visão de produto pt9 (DIVERGÊNCIA 5 documentada em `docs/REGRAS_NEGOCIO.md` §3.2.2).
- **Sintoma:** Estudo apresenta a mesma chip de tag em 3 secções separadas: PRINCIPAIS/SECUNDÁRIAS/SPOTS (HM3 only), CANAIS DISCORD (Discord with HH), DISCORD — SÓ SS (Discord without HH). Rui pediu há ~1 mês para unificar; não está implementado.
- **Severidade:** 🔴 Funcional alto. Viola pedido explícito antigo do Rui. Estudo torna-se redundante e confuso. Inclui caso especialmente grave: secção "DISCORD — SÓ SS" mostra 119 mãos sem HH, violando regra dura 3.2.1.
- **Fix proposto:**
  - Backend: query tag-groups deve agregar hm3_tags + discord_tags por NOME (ex: "ICM PKO" + "icm-pko" → mesma chave normalizada).
  - Frontend: remover secções "CANAIS DISCORD" e "DISCORD — SÓ SS (SEM HH)". Apresentar 1 chip por nome unificado. Cada mão mostra origem como rótulo discreto.
  - Aplicar regra dura: mãos sem HH NUNCA em Estudo.
- **Esforço:** ~3-4h (backend agregação + frontend redesign + validação).
- **Bloqueado por:** nada. Pode atacar em pt10 ou continuação pt9.

### #B18 — Lista de mãos em torneio (drill-down): falta badge de origem por mão

- **File provável:** `frontend/src/components/HandRow.jsx` ou caller no drill-down de torneio (`frontend/src/pages/Tournaments.jsx`, `frontend/src/pages/Hands.jsx::TournamentGroup`).
- **Origem:** Coerência com #B17 (pt9).
- **Sintoma:** No drill-down de torneio, lista de mãos mostra: nome do torneio, buy-in, data, número do torneio, stack inicial (quando disponível), número de mãos. Falta badge de origem por mão (HM3 / Discord / SS-only) — incoerente com a vista Estudo pós-#B17 que adicionou `OriginBadge` via prop `extraEnd`.
- **Severidade:** 🟢 UX.
- **Fix proposto:** passar `extraEnd={<OriginBadge ...>}` no `HandRow` dentro do `TournamentGroup` quando aplicável; ou tornar `HandRow` capaz de calcular o badge a partir das próprias `hand.hm3_tags` / `hand.discord_tags` quando uma prop `showOrigin=true` for passada.
- **Esforço:** ~30-45 min.
- **Bloqueado por:** nada.

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

<!--
Nota histórica (#B31 limpeza pt13): §5-§10 (plano sequencial pré-pt8,
dependências, esforços, riscos, decisões, notas para próxima sessão)
foram apagadas porque referiam tech debts já fechados (#22, #18, #15,
#B7, #12, #13c, #B12, etc.) e não eram mais accionáveis. Conteúdo
preservado em git history. Único item ainda válido (#11 blacklist
persistida vs re-criar) movido inline para a entry de #11 no backlog
"Tech Debts abertos pós-pt10" acima.
-->

