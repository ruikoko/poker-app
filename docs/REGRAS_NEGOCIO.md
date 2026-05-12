# Regras de Negócio — Poker Study App

Documento operacional. Detalha as regras que regem entrada, processamento, distribuição e análise de dados na app. Próximas sessões DEVEM ler este documento ANTES de tocar em código que afecte qualquer um destes vectores.

Complementa `docs/VISAO_PRODUTO.md` (visão alta) e `docs/MAPA_ACOPLAMENTO.md` (mapa técnico).

## Os 4 vectores da app

1. **ENTRADA** — recolha de dados (HM3 .bat, Discord bot, Upload manual).
2. **PROCESSAMENTO** — parse, match, enriquecimento.
3. **DISTRIBUIÇÃO** — envio de cada dado para a secção certa.
4. **ANÁLISE** — Rui trabalha sobre o resultado distribuído.

---

## 1. ENTRADA

### 1.1. HM3 (.bat local)

- **Trigger:** manual, corre quando Rui decide. Não há agendamento.
- **Período:** Rui escolhe (últimos 3 dias, 7 dias, etc).
- **Critério de importação:** importa SÓ mãos COM tags HM3 dentro do período. Mãos "rotina" sem tag NUNCA entram via HM3.
- **Salas cobertas:** Winamax, WPN, PokerStars.

### 1.2. Discord bot (manual via app)

- **Trigger:** botão "Sincronizar" na página Discord. `DISCORD_AUTO_SYNC=false` em produção (não corre sozinho).
- **Janelas pré-definidas:** 24h, 72h, 1 semana, 15 dias, 1 mês.
- **Janela custom:** Rui escolhe `De` e `Até` (calendário inline).
- **Cutoff absoluto:** 1 Jan 2026 Lisboa. Nenhuma mensagem anterior é varrida (regra de negócio Rui — é o início da era da app).
- **Cobertura de canais:** todos os canais do servidor monitorizado.
- **Conteúdo apanhado:** replayer-links GG + imagens (anexos directos + links Gyazo).

### 1.3. Upload manual (na app)

- SS GGPoker (`.png`, `.jpg`, `.webp`).
- HH em texto (qualquer sala) — upload de ficheiro `.txt`.
- ZIPs (HHs em massa) — caminho separado para o GG (não vem via HM3 .bat porque é anonimizada).
- Outras imagens (contexto).

---

## 2. PROCESSAMENTO

### 2.1. Parse

Lê o input cru e extrai info estruturada:
- Hand histories texto → mãos + acções + jogadores.
- Screenshots (Vision GPT-4o-mini) → seats + nicks + stacks; identifica o Hero (centro-baixo).
- Replayer-links Discord → screenshot embebida na URL.
- Imagens Discord/Gyazo → ficam como anexos (não viram mãos).

### 2.2. Match

Tenta unir peças que pertencem juntas:
- **SS ↔ HH (mesma mão GG):**
  - Match por `hand_id = GG-{TM_number}`.
  - Resolve hashes anonimizados → nicks reais por âncoras (Hero/SB/BB) + aritmética de stacks + eliminação para o resto.
- **Discord entry ↔ HH existente:**
  - Append discord_tags via helper centralizado `append_discord_channel_to_hand` (#B12 fix pt9).
- **Imagem ↔ mão (galeria):**
  - Manual. Rui escolhe via UI.

### 2.3. Enriquecimento

Adiciona informação derivada:
- Posições calculadas (BTN, SB, BB, UTG, etc).
- Tags auto-geradas (showdown, position, etc).
- `tournament_format` (KO/PKO/Mystery/Vanilla).
- `buy_in` numérico extraído do nome do torneio.
- `result` (lucro/perda em BB).

---

## 3. DISTRIBUIÇÃO

### 3.1. Secções de ORIGEM

Toda mão entra na sua secção de origem.

| Secção | Conteúdo |
|---|---|
| HM3 | Mãos do .bat HM3 (Winamax/WPN/PokerStars). |
| Discord | Mãos do bot Discord. |
| Torneios | Drill-down por torneio (toda mão GG). |
| Dashboard | SS e imagens uploadadas manualmente. |

### 3.2. Secções DERIVADAS — Estudo

#### 3.2.1. Regras de elegibilidade (TODAS obrigatórias)

Fonte de verdade: `backend/app/routers/hands.py:567-574` (3 filtros aplicados quando `study_view=true`, mais `study_state != 'mtt_archive'` por defeito em `hands.py:565-566`).

**Condições técnicas:**
- Nicks reais (não hashes). Para GG: requer `match_method` populado e diferente de `discord_placeholder_*` — `STUDY_VIEW_GG_MATCH_FILTER` (`hands.py:359-363`).
- Mão TEM HH (`raw` não vazio). Mãos só com SS, sem HH, NUNCA aparecem em Estudo — `STUDY_VIEW_REQUIRES_HH` (`hands.py:395`).
- Não estar em arquivo MTT (`study_state != 'mtt_archive'`) — default em `hands.py:565-566`.

**Condição de tag** — `STUDY_VIEW_HAS_STUDY_TAG` (`hands.py:402-409`):
- Pelo menos 1 tag de estudo:
  - Tag HM3 que NÃO bate `nota%` (case-insensitive).
  - OU canal Discord que NÃO seja `nota`.

**Excepção (aditiva):**
- Mão com tag `nota` + tag de estudo → entra em Estudo E Vilões.
- Mão SÓ com `nota` → vai apenas para Vilões.

**Não exigido pelo código** (apesar de docs antigas afirmarem): `tournament_name`, `buy_in`, `site`. Parsers PS deixam `tournament_name=None` deliberadamente (`hm3.py:335-336`); parsers WPN deixam `buy_in=None` deliberadamente (`hm3.py:211-212` em `_extract_buyin_hm3`). Exigir bloquearia mãos legítimas.

#### 3.2.2. Apresentação em Estudo

**Regra:** tags HM3 e canais Discord são o MESMO conceito. Rui nomeou os canais Discord para coincidirem com tags HM3 (ex: canal `icm-pko` ≡ tag `ICM PKO`).

**Apresentação (estado actual, pt13):**
- 1 chip por nome de tag/canal (unificação case-insensitive + hyphen→space; ver `normalizeTagKey` em `frontend/src/pages/Hands.jsx`).
- Dentro da chip: todas as mãos com essa tag, vindas de qualquer origem (HM3 ou Discord).
- Cada `HandRow` carrega um `OriginBadge` (`HM3`, `Discord`, ou `HM3+D` quando a tag normalizada existe nas duas origens da mesma mão).
- Mãos sem HH excluídas (regra 3.2.1: "Mão TEM HH").
- Mãos só com tag `nota` excluídas (vão apenas para Vilões).
- Cada `HandRow` mostra o ID da mão (monospace cinzento esbatido) — pt12 #B34.
- Torneios agrupam-se por `tournament_number` (chave `tm:${number}`), não por nome — pt12 #B25 resolveu cross-midnight + nomes duplicados.

**Pista de estudo simplificada (pt13):** `study_state` é um de 3 valores: `new` (ainda por estudar), `resolved` (revista) ou `mtt_archive` (arquivo de torneio, não aparece em Estudo). UI mostra "Nova" / "Revista". CHECK constraint no schema.

**Ponto de entrada (pt13):** o cartão Dashboard "Mãos por estudar" expandiu com top 3 tags normalizadas + 4 salas (GG/PS/WN/WPN sempre presentes); o cartão "Total de mãos" tem sub-linha condicional "X revistas". A Inbox foi eliminada — 7 secções no sidebar (Dashboard / HM3 / Discord / Torneios / Estudo / Vilões / GTO).

### 3.3. Secções DERIVADAS — Vilões

Critérios de elegibilidade (regras canónicas A∨C∨D — `_classify_villain_categories` em `backend/app/services/hand_service.py`):

- **Regra A** — `hm3_tags` contém tag a começar por `nota` (`nota`, `notas`, `nota+`, `nota++`, etc) → `category='nota'`.
- **Regra C** — canal Discord `nota` em `discord_tags` E `match_method` real (não `discord_placeholder_*`) → `category='nota'`.
- **Regra D** — `villain_nick` em `FRIEND_HEROES` (lista em `backend/app/hero_names.py` — Karluz, flightrisk) → `category='friend'`. Independente de tag; sempre dispara quando o nick aparece como non-hero. Permite ver mãos de amigos sem o Rui ter de marcá-las explicitamente.

**Pré-condição padrão** do classificador: villain tem `has_cards` (showdown) OU `has_vpip` (call/raise/bet preflop). Sem nenhuma das duas evidências, normalmente não é villain a registar.

**Excepção #B19** (pt9, estendida em pt10) — quando a mão tem tag HM3 `nota%` **OU** `'nota' ∈ discord_tags`, a pré-condição é ignorada: qualquer non-hero que **viu o flop** (acção em street ≠ `preflop` no `all_players_actions`) é elegível, mesmo sem VPIP nem cards. Justificação: a tag `nota` (HM3 ou canal Discord) é sinal de intenção explícita do Hero — quer estudar o adversário, mesmo sem showdown, mesmo se o non-hero só agiu postflop (ex: line/sizing notável seguido de fold sem chegar a SD).

**Implementação:** `backend/app/services/villain_rules.py` (`apply_villain_rules` — função canónica única após refactor #B23). Excepção aplicada em 2 sítios:
- `_classify_villain_categories` (`hand_service.py`): bypass da pré-condição `has_cards∨has_vpip` quando há `has_nota_intent` (variável agnóstica de origem; pt10 unificou `has_nota_hm3` + verificação Discord).
- `_build_candidates` (`villain_rules.py`): alarga candidates a postflop-only nesses casos.

### 3.4. Regra de Cross-post Discord

Toda mão que apareça num canal Discord deve ter o nome desse canal em `discord_tags`. Sem excepções por origem da mão.

Implementado via helper `append_discord_channel_to_hand` em `backend/app/services/hand_service.py` (#B12 fix pt9).

### 3.5. Casos canónicos (referência rápida)

| # | Origem da mão | Tags / canais | Estudo? | Vilões? | Aparece em |
|---|---|---|---|---|---|
| 1 | HM3 | `["ICM PKO"]` | ✓ | ✗ | HM3, Estudo |
| 2 | HM3 | `["nota"]` | ✗ | ✓ | HM3, Vilões |
| 3 | HM3 | `["nota", "ICM PKO"]` | ✓ | ✓ | HM3, Estudo, Vilões |
| 4 | Discord | canal `pos-pko` | ✓ | ✗ | Discord, Estudo |
| 5 | Discord | canal `nota` | ✗ | ✓ | Discord, Vilões |
| 6 | Discord | canais `["nota", "pos-pko"]` | ✓ | ✓ | Discord, Estudo, Vilões |
| 7 | GG anon (sem SS, sem match) | — | ✗ | ✗ | Torneios |
| 8 | HH bulk + SS match, sem tags | — | ✗ | ✗ | Torneios |

---

## 4. ANÁLISE

Rui trabalha mãos em Estudo + Vilões. Detalhes do fluxo de análise não documentados nesta versão (foco actual: vector ENTRADA + DISTRIBUIÇÃO).

---

## 5. Regras de identificação de TORNEIO (por sala)

Necessário para alimentar `tournament_name` e `tournament_format` (campos obrigatórios para Estudo).

### 5.1. PokerStars

**Nome construído:** `<número_torneio> + <buy_in_total> + <formato>`.
Exemplo: `3983883171 - €50.00 - Mystery KO`.

**Formato (regra dura):**
- buy_in com 1 parte (ex: `€10`) → **Vanilla**.
- buy_in com 3 partes (ex: `€22.50+€22.50+€5.00`) → tem bounty:
  - Se as stacks dos seats mostram bounty value → **PKO**.
  - Se NÃO mostram bounty value → **Mystery KO**.

**KO regular:** PokerStars não corre KO regular hoje. Ignorar essa categoria.

### 5.2. Winamax

**Igual ao PokerStars** (mesmo formato de buy_in, mesma regra de bounty nas stacks).

### 5.3. WPN

**Nome construído:** `<número_torneio> + <GTD garantido>`.
Exemplo: `Tournament 12345 — $30,000 GTD`.

**Formato:** indeterminado. WPN não define nada útil na HH. Aceitar e seguir.

### 5.4. GGPoker

**Nome:** já vem na HH (linha 1, ex: `WSOP-SC HR: $525 Bounty Hunters Circuit HR`).

**Formato (deduzido pelo nome):**
- "Mystery" no nome → **Mystery KO**.
- "Bounty" no nome (sem "Mystery") → **PKO**.
- Sem "Mystery" nem "Bounty" → **Vanilla**.

**Particularidade:** GG não mostra bounty value nas stacks (todas anonimizadas). Por isso a regra de stacks do PS/Wina não se aplica — só o nome conta.

### 5.5. GG Tournament Summaries — fonte autoritativa post-jogo

Adicionado em pt19 (FASE B). Tabela `tournament_summaries` (ver `docs/MAPA_ACOPLAMENTO.md` §2.12) é populada por upload manual via `Tournaments.jsx` de ficheiros `.txt`/`.zip` emitidos pelo cliente GG quando um torneio termina.

**Regra autoritativa:**

- Cada TS contém `Tournament #<numero>` literal no header → match determinístico do `tournament_number`.
- O resolver (`backend/app/services/tournament_resolver.py:resolve_tournament_number`) usa `tournament_summaries` como **TIER 0** (antes de `tournaments_meta` e `hands` fallback).
- TIER 0 corre **sem janela temporal**. Justificação: TS é post-jogo, não há risco de "torneio ainda nem começou"; tempo não acrescenta informação útil.
- Quando há múltiplas instâncias do mesmo nome (ex: `Daily Hyper $80` corre todos os dias), discriminam-se por **`prize_pool` e `total_players`** lidos pela Vision do header da lobby SS — filtros estritos opt-in (NULL = sem filtro).

**Quando TS não chega para resolver:**

- Vision falha a ler `prize_pool` e há 2+ torneios com mesmo nome → resolver devolve `(None, candidates)`. Caption manual `#<TM>` no post Discord faz bypass total.
- Torneio em curso (TS ainda não emitido) → cai para TIER 1 (`tournaments_meta`) ou TIER 2 (`hands` fallback) com janela apertada.

### 5.6. Parser de Tournament Summaries — campos extraídos

`backend/app/routers/tournament_summaries.py:parse_tournament_summary`. Total **26 campos**.

**14 originais (B1):** `tournament_number`, `tournament_name`, `buy_in_text`, `buy_in_total`, `buy_in_currency`, `total_players`, `prize_pool`, `start_time` (UTC), `hero_position`, `hero_payout`, `hero_re_entries`, `raw_text`, `source_filename`, `site` (hard-coded `'GGPoker'`).

**12 estendidos (B1.x):** divididos em 3 categorias:

- **Literais (do raw text):**
  - `game_type` (ex: "Hold'em No Limit")
  - `buy_in_entry`, `buy_in_rake`, `buy_in_bounty` (split do total: 2 tokens = entry+rake; 3 tokens = entry+rake+bounty/mystery)
  - `hero_total_received` (cross-check com `hero_payout`)
  - `hero_finish_phrase_position` (cross-check com `hero_position`)
  - `tournament_modifiers TEXT[]` (tokens em `[…]`)
  - `tournament_series` (prefixo antes de `:` no nome)

- **Heurísticas (keyword no nome):**
  - `tournament_speed` — `Hyper`/`Turbo`/`Deepstack`; `'speed racer'` branded → `Hyper`; default `Slow`.
  - `tournament_schedule` — `Daily`/`Sunday`/`Monday`/…/`Weekly`/`Monthly`; `None` se ausente.

- **Derivados (via `apply_ratio_lookup` reusada de `lobby_vision`):**
  - `tournament_format` — `PKO`/`KO`/`None`.
  - `tournament_pko_ratio NUMERIC(4,2)` — `0.50`/`0.75`/`0.40`/`0.33`; `None` se sem bounty.

Campos opcionais que faltam no TS resultam em `NULL`/`None`. Apenas `tournament_number` e `start_time` são obrigatórios — ausência levanta `ValueError` e a row é registada em `failed[]` no endpoint sem abortar o batch.

---

## 6. Regras DURAS — o que a app NUNCA pode fazer

- Mãos GG anonimizadas (sem `match_method`) NÃO podem aparecer em Estudo.
- Mãos só com tag `nota` NÃO podem aparecer em Estudo.
- Mãos sem HH NUNCA aparecem em Estudo (mesmo que tenham tags).
- Cross-post Discord NÃO pode perder canais.
- Mensagens Discord anteriores a 1 Jan 2026 Lisboa NÃO são varridas.
- HM3 .bat NÃO importa mãos sem tag.

---

## 7. Áreas futuras (NÃO implementar sem confirmação Rui)

- Análise post-estudo (evolução das mãos estudadas).
- Estudo de população (mãos GG sem tag — Caso 7/8).
- GTO Brain (documentado separadamente).
- Integração GTOWizard / HRC.

---

## 8. Limitações conhecidas

- **Path bulk archive (`mtt_hand_id` legacy) NÃO usa `apply_villain_rules`.** 4 call sites em `backend/app/routers/mtt.py` (linhas 1264, 1882, 2202, 2297) e 1 chamada interna em `_create_villains_for_hand` legacy continuam a passar `mtt_hand_id` em vez de `hand_db_id`. Esses caminhos correspondem ao path bulk archive de `mtt_hands` (table separada de `hands`) e não estão no fluxo principal pós-pt10. Merecem revisão futura — ou migrar para `hand_db_id` quando promovidos a `hands`, ou remover se `mtt_hands` for deprecado.

---

## 11. Terminologia

Adicionado em pt19. Pivot deliberado de vocabulário para reduzir ambiguidade com a linguagem do Rui.

### Tags HM3 / canais Discord

- **`GTw` descontinuada** (pt19, commit `a4a9595`). Tag canónica para "posição em torneios não-KO (vanilla, sem bounty)" é **`pos-nko`** (originalmente nome de canal Discord — `discord_tags`). Continua listada em `HM3_REAL_TAGS` com id sintético `9999` para que UI/admin a reconheçam; o importer `import_hm3` aplica `apply_hm3_tag_aliases()` (`backend/app/services/hm3_tag_aliases.py`) pré-INSERT a re-imports do `.bat` que ainda trazem `GTw`.

### TM vs tournament_number

Refactor categoria (a)(b)(c) em pt19 (commit `440b248`).

- **No vocabulário do Rui** (linguagem do replayer GG): **TM** = número da **mão** visível no canto do replayer (ex: `TM5672663145`). Faz parte do `hand_id` GG (`GG-{TM}`).
- **No vocabulário interno antigo da app**: **TM** era o número do **torneio** (`tournament_number`). Causava colisão.
- **A partir de pt19** o código usa `tournament_number` para o identificador do torneio. Serviços, símbolos, log prefixes, mensagens user-facing renomeados.

**Restos do vocabulário antigo** (categoria d, deferida pt20+): ~50 sítios em `screenshot.py`/`mtt.py`/`hm3.py`/`import_.py`/`discord.py`/`hands.py` ainda usam `tm_number` no pipeline `hand_id GG = GG-{tm_digits}`. Mexe em coluna `mtt_hands.tm_number`, índices, e lógica de string-replace — separado por envolver migração de dados.

### Caption manual `#<numero>`

No canal `#lobbys` o Rui pode bypassar o resolver escrevendo `#12345678` ou `TM12345678` no texto da mensagem com a SS. A regex aceita prefixos `#`, `TM`/`tm`, `TN`/`tn`, ou número sozinho (8-12 dígitos, lookarounds `(?<!\d)`/`(?!\d)`).

---

## 12. Pipelines de payouts (pt20+)

Adicionado em pt20 (Commit E + endpoint backoffice).

### 12.1. Três caminhos para `tournament_payouts`

| Caminho | Como entra | `source` na row |
|---|---|---|
| **Manual** (raro) | `POST /api/payouts` ou INSERT directo | `manual:<rotulo>` (ex: `manual:rui_backoffice_ss_pt20_correction`) |
| **Lobby Vision** (real-time + sync) | SS no `#lobbys` Discord → Vision → resolver TIER 0/1/2 | `discord_lobby_vision:<msg_id>` |
| **Backoffice import** (pt20) | Upload imagem do backoffice GG via `Tournaments.jsx` → Vision → resolver TIER 0 | `backoffice_vision:<filename>` |

### 12.2. Precedência (D11 pt20)

Quando uma row já existe em `tournament_payouts` para um `(site, tn)`:

- `manual:` **nunca** é sobrescrito automaticamente (intervenção humana explícita).
- `backoffice_vision:` **sobrescreve** `discord_lobby_vision:` (backoffice tem dados mais completos: distribuição de prizes por posição vs lobby SS que muitas vezes só mostra top-N visível).
- `skip_existing=true` no endpoint backoffice skipa apenas rows com source `backoffice_vision:` ou `manual:` (não skipa lobby).

**Limitação pt20:** o lobby pipeline (`process_lobby_message`) hoje não verifica a precedência ao fazer UPSERT — pode sobrescrever uma row `backoffice_vision:` com `discord_lobby_vision:` (regressão de qualidade). Tech debt `#SYNC-RECENT-RESPECT-MANUAL`.

### 12.3. Mystery KO actualmente unsupported no backoffice

O endpoint `/api/tournament-results/import` devolve `result='mystery_unsupported'` quando o TS resolvido tem `tournament_format='KO'`. Justificação:

- Sample real de blob HRC para Mystery não está disponível para confirmar o `bountyType` aceite pelo HRC Structure Manager (`"KO"` vs mapear para `"PKO"` com factor especial).
- Web/Rui escolheram em pt20 entregar o pipeline vanilla+PKO e deixar Mystery para commit subsequente (D13).

Para popular `tournament_payouts` de um torneio Mystery hoje: caminho manual (lobby SS no `#lobbys` se ainda decorrer, ou `POST /api/payouts` directo). Tech debt: **`#BACKOFFICE-MYSTERY`**.

### 12.4. Buraco TS→payouts (resolvido em pt20)

Importar um `.txt` TS popula `tournament_summaries` (metadata pós-jogo) mas **não** `tournament_payouts` (não há distribuição de prizes por posição no `.txt`). Regra (pt20): para o `/api/queue/hrc` poder incluir as mãos de um torneio no zip para o HRC watcher, é necessário **um dos 3 caminhos** acima popular `tournament_payouts` independentemente do TS.

Caso Rui peça automação no futuro (derivar payouts via ICM a partir de TS), tech debt `#TS-AUTO-PAYOUTS-ICM` está registado — não implementado por defeito (ICM é estimativa; backoffice é literal).
