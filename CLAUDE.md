# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⚠️ LEITURA OBRIGATÓRIA ANTES DE TUDO

Qualquer sessão Claude Code que toque neste repositório DEVE ler primeiro estes 5 documentos, por esta ordem:

1. **`docs/PAPEIS_E_RESPONSABILIDADES.md`** — explica o papel do Rui, do Claude Web e do Claude Code neste projecto. Leitura obrigatória para Claude novo.
2. **`docs/VISAO_PRODUTO.md`** — visão alta da app (propósito, vectores, secções).
3. **`docs/REGRAS_NEGOCIO.md`** — regras operacionais (entrada, processamento, distribuição, casos canónicos, regras duras).
4. **`docs/MAPA_ACOPLAMENTO.md`** — mapa técnico de conceitos (`match_method`, `study_state`, `origin`, etc).
5. **`docs/TECH_DEBTS_INVENTARIO.md`** — backlog actualizado de tech debts.
6. **`docs/HRC_ANATOMIA_OPERACIONAL.md`** — anatomia do HRC consolidada (wizard, Strategy Table, popup Nash, clipboard, coords, formato HH aceite). **Obrigatório se o trabalho toca o robot ou a pipeline HRC.** Lê antes de propor mudanças em `tools/watcher_src/` ou `backend/app/services/queue_export.py`.
7. **`docs/GTO_BRAIN.md`** — visão consolidada do GTO Brain (origem, filosofia, arquitectura `gto_trees`/`gto_nodes` + matching engine, plano em 3 fases). **Obrigatório se o trabalho toca o GTO Brain** (watcher export, `backend/app/routers/gto.py`, tab GTO do replayer, ou o futuro pipeline `.zip` → `gto_trees`).

Sem ler estes 5 documentos (6 se tocares no robot/pipeline HRC, 7 se tocares no GTO Brain), NÃO tocar em código. Atalhos aqui produzem regressões (já aconteceu).

## ⚠️ ARMADILHA RECORRENTE — chama laranja ≠ bounty

**Nas screenshots/replayer da GGPoker há DOIS badges por jogador. NÃO os confundas (já se confundiu várias vezes):**

- **🔥 Chama LARANJA = VPIP do jogador (uma %).** NÃO é bounty, NÃO é "percentagem de bounty". É a frequência com que o jogador entra em pote.
- **👑 Coroa DOURADA = bounty, valor em $.** É ISTO o bounty (PKO/KO).

**No código o campo `bounty_pct` guarda a CHAMA LARANJA = o VPIP — o NOME É ENGANADOR.** O bounty real (coroa) está em **`bounty_value_usd`**. Qualquer cálculo de bounty (IRE, ko_units, etc.) usa `bounty_value_usd`, **nunca** `bounty_pct`. Rename do campo deferido por backward-compat — ver `#FIELD-BOUNTY-PCT-MISNAMED` (`screenshot.py`). Se vês `bounty_pct` e pensas "bounty", pára: é VPIP.

## ⚠️ REGRA DE OURO — LER ANTES DE QUALQUER ACÇÃO

**O PC onde este projecto é desenvolvido é o mesmo onde o utilizador joga poker.** As salas (GGPoker, PokerStars, Winamax, WPN, iPoker, 888) têm anti-cheat agressivo que scanneia processos activos. Qualquer processo "suspeito" (editores, terminais, ferramentas de análise, scripts Python a correr) pode gerar falsos positivos e prejudicar a conta.

**Claude Code só deve correr quando:**
- Todas as salas de poker estão **fechadas** (não minimizadas — fechadas).
- HM3, SharkScope HUD e Intuitive Tables estão fechados.
- O utilizador não está em sessão nem vai estar dentro dos próximos ~30 minutos.

**Durante uma sessão de poker activa**, apenas browsers são aceitáveis (inclui a app web deste projecto, porque corre dentro do browser).

**Se o Claude for invocado durante uma sessão activa**, avisar imediatamente o utilizador e pedir confirmação explícita antes de prosseguir. Nunca arrancar processos de longa duração (dev server, bot Discord, watchers) sem essa confirmação.

## Mapa de acoplamento da app

Antes de tocar em qualquer conceito da app (`match_method`, `origin`,
`hm3_tags`, `discord_tags`, `tags`, `study_state`, `entry_type`,
`source`, `raw_json`, etc.), lê **`docs/MAPA_ACOPLAMENTO.md`**.

Esse documento mapeia, para cada conceito-chave (33 entradas):
- Onde é produzido (ficheiro:linha + função)
- Onde é consumido (filtros, queries, painéis)
- Valores possíveis e significado de cada
- Comportamento quando muda (ripple effects)
- Armadilhas conhecidas (bugs já apanhados)
- FAQ adaptada ao conceito

Mexer sem ler causa regressões — vimos isto a acontecer em sessões
passadas.

**Manutenção obrigatória:** mudaste algo que produz/consome um
conceito mapeado? Actualiza o MAPA na mesma sessão. Senão fica
desactualizado e mente ao próximo Claude (pior do que não existir).

## ⚠️ Reconfirmar tech debts no repo antes de atacar

Antes de atacar qualquer tech debt, **reconfirma o estado actual lendo o
código/docs do repo** — não confies em listas de estado mantidas na conversa
(podem estar desactualizadas, ou o item pode ter sido silenciosamente resolvido
noutra sessão). Em pt43 isto apanhou: o `#DISCORD-VISION-NO-RECOVERY` já tinha
um step 4b de recuperação parcial (a redacção do debt estava stale), e o
`#SERVER-FILTER-HRC-STATUS`/`#SYNC-RECENT-RESPECT-MANUAL` tinham docs (MAPA,
REGRAS_NEGOCIO) a afirmar "não implementado" depois de implementados. Para cada
debt: confirma se ainda existe, onde vive (ficheiro:linha), e quantifica o
impacto real (ex.: query read-only) antes de estimar esforço.

## ⚠️ Descrever o problema em PT-PT simples antes de pedir decisão ao Rui

Antes de qualquer **decisão de produto**, o problema **todo** tem de estar descrito
em **linguagem normal** (PT-PT), em prosa, **sem jargão técnico** e **sem omitir o que
importa**. O Rui decide sobre o problema real, não sobre uma versão filtrada por termos
de engenharia. Se a explicação precisa de `match_method`, `NOT EXISTS`, `instant_fraction`
para se perceber, ainda não está pronta — traduz primeiro. A decisão técnica (como
implementar) vem **depois** da decisão de produto (o quê e porquê), e essa exige o
problema em claro.

## Stack

- **Backend**: FastAPI + `psycopg2` contra PostgreSQL. Entry point `backend/app/main.py`; routers em `backend/app/routers/`; lógica em `backend/app/services/` e `backend/app/hand_service.py` (top-level); parsers por sala em `backend/app/parsers/`.
- **Frontend**: React 18 + Vite + React Router. Todo o HTTP passa por `frontend/src/api/client.js` (cookie-based auth, path relativo `/api`, proxy Vite para `localhost:8000`).
- **Integrações**:
  - **OpenAI Vision** (GPT-4.1-mini) — screenshots de mesas/replayers GG. `screenshot.py`. Env: `OPENAI_API_KEY`.
  - **Anthropic Claude Sonnet 4.6** (model id `claude-sonnet-4-6`) — screenshots de lobbys (FASE A, pipeline `tournament_payouts`). `services/lobby_vision.py`. Env: `ANTHROPIC_API_KEY`. Adicionada em pt18 (9 Maio 2026).
  - `discord.py` para puxar mãos de canais de estudo + handler dedicado para canal `#lobbys` (pt18).
- **Deploy real**: Railway.
  - Backend: `poker-app-production-34a7.up.railway.app`
  - Frontend: `comfortable-hope-production-a87a.up.railway.app`
  - Configuração em `backend/nixpacks.toml` e `frontend/nixpacks.toml`.
- **Deploy alternativo (não usado)**: `deploy/` tem scripts para Ubuntu VPS (systemd + nginx + certbot + backups cron). Existe mas não é a infra actual — não assumir que está activa.

## Correr localmente (dev)

```bash
# Backend
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # preencher DB_PASSWORD, SESSION_SECRET, ALLOWED_ORIGIN
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Frontend (faz proxy de /api → :8000)
cd frontend
npm install
npm run dev       # servidor de desenvolvimento
npm run build     # build de produção → dist/
```

Schema aplica-se de duas formas: `python backend/bootstrap.py` corre o `backend/schema.sql` completo uma vez, e as funções `ensure_*_schema()` no lifespan do FastAPI (`main.py`) aplicam migrações idempotentes `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` no arranque. **Colunas/tabelas novas vão numa função `ensure_*` do router relevante** — não chega editar `schema.sql`, porque BDs já em produção só recebem o `ensure_*` no boot.

Não há suite de testes nem linter configurados.

## Modelo de domínio

O produto existe para **centralizar o estudo do Rui** — juntar num sítio único, organizado e trabalhável, as mãos de dúvida que hoje estão espalhadas por várias salas, vários sítios e vários formatos (tags HM3, canais Discord, screenshots, HHs em texto). Tudo o resto é canalização ao serviço disto.

Uma dessas salas — a **GGPoker** — vem **anonimizada**, e por isso exige um mecanismo extra para entrar no sítio único com nicks reais como as outras. Esse mecanismo cruza **duas fontes de verdade**, cada uma com metade da informação:

1. **Hand History (HH) da GGPoker** — matematicamente exacta (acções, stacks, pot) mas **anonimizada**: jogadores aparecem como hashes (`89ef4cba`).
2. **Screenshots** tirados durante o jogo — têm nicks reais e bounties mas sem dados de acção fiáveis.

A app cruza as duas para produzir `hands.all_players_actions` enriquecido. **Este cruzamento é um mecanismo (específico da GG), não o propósito da app.** Ter isto em mente ao mexer em `screenshot.py`, `mtt.py`, ou no parser GG.

### Duas pistas de ciclo de vida

Cada linha em `hands` tem `study_state`. As duas pistas não se devem contaminar:

- **Arquivo de torneio**: imports em bulk (`.zip` HH) entram com `study_state = 'mtt_archive'`. Aparecem só na secção **Torneios** (drill-down por torneio) — **nunca** na página Mãos.
- **Estudo**: uma mão entra em `new` apenas quando chega um screenshot (ou marcação manual). Depois percorre `new → review → studying → resolved`. A página Mãos mostra o track de estudo.

Ao listar mãos, **filtrar sempre por `study_state` explicitamente**. "Todas as mãos" quase nunca é o que a UI quer.

### Pipeline screenshot ↔ HH

1. Parse determinístico do nome do ficheiro — fonte de verdade para data, hora, blinds e TM number (ex: `2026-03-06_06_02_PM_2,000_4,000(500)_#TM5672663145.png`). **Nunca confiar no Vision para blinds/ante** — alucina; extrair do filename.
2. Vision extrai `(nome, stack)` por seat + identifica o Hero (centro-baixo).
3. Match por `hand_id = GG-{TM_number}`.
4. Constrói `hash → nome_real` por âncoras (Hero/SB/BB) + aritmética de stacks (folded: `stack_ss ≈ stack_hh - ante`, tolerância <2%) + eliminação para os restantes.
5. Escreve em `hands.all_players_actions`, `screenshot_url`, `player_names`.

Posições na wire: o parser emite `UTG1`, `MP1` (sem `+`). Vision devolve `UTG+1`; normalizar antes de persistir.

Hero nicks em `backend/app/hero_names.py` e espelho em `frontend/src/heroNames.js`. Actualizar ambos ao adicionar um alias.

### `entries` vs `hands`

`entries` é a inbox de inputs crus: cada mensagem Discord, screenshot, HH file, ou report HM3 aterra aí primeiro com `source` + `entry_type`. `hand_service.process_entry_to_hands()` promove uma entry `hand_history` a linhas em `hands`. Screenshots ficam como entries até fazerem match com uma HH (órfãos expostos em `/api/mtt/orphan-screenshots`).

### `hm3_tags` vs `tags`

`tags` (auto-geradas: showdown, nicks, etc.) e `hm3_tags` (tags reais de estudo importadas do HoldemManager3) são colunas **separadas**. Lista canónica em `HM3_REAL_TAGS` em `backend/app/routers/hands.py`.

### Placeholders Discord

Quando uma mensagem Discord referencia uma mão antes da HH ter sido importada, é criada uma linha placeholder em `hands` com `raw` vazio e `hm3_tags=['GGDiscord']`. Crucialmente, **o placeholder e a HH real partilham o mesmo `hand_id`** (formato `GG-<tm_number>`, derivado do TM number tanto no Discord como no parser da HH). É por isso que `_insert_hand` em `services/hand_service.py` detecta a colisão na inserção: faz `SELECT ... WHERE hand_id = %s`, confirma que o match é um placeholder (raw vazio + tag `GGDiscord`) e **apaga** a linha antes de inserir a HH real. Sem isto, essas mãos ficavam presas como placeholders para sempre. Preservar este comportamento.

## Bot Discord — modo manual

`DISCORD_AUTO_SYNC=false` por defeito no Railway. O bot liga-se mas **não** extrai mensagens sozinho. Só corre quando o utilizador carrega em "Sincronizar Agora" em `/discord` (→ `POST /api/discord/sync` ou `/sync-and-process`). Isto reduz risco face ao ToS das salas de poker, que olham mal para scraping contínuo de canais de estudo. **Não mudar para auto-sync sem pedir autorização explícita.**

## Imagens de contexto Discord — comportamento de produto

Imagens directas Discord (anexos `.png`/`.jpg`/`.webp` ou links Gyazo) são **contexto de mãos, não mãos por si**. O Rui usa-as para anexar prints de HM3, gráficos, diagramas, qualquer screenshot que ajude a entender uma mão já partilhada — nunca como hand source primária.

Padrão real:

1. O Rui partilha uma mão num canal temático (`pos-pko`, `icm-pko`, `icm`, `nota`, etc.) via replayer GG ou HH text.
2. Para anexar contexto, posta uma **imagem no mesmo canal**, com no máximo **90 segundos** de distância da mão.
3. **Caso especial:** a mão pode ter chegado via HM3 (.bat, fluxo separado), não via Discord. Mesmo assim o Rui pode partilhar contexto via Discord — o sistema tem que conseguir cruzar imagem Discord ↔ mão HM3 quando os timestamps caem dentro da janela.

Regra operacional do match imagem ↔ mão:

- **Janela temporal: ±90 segundos.** Não 10 minutos. Não 5 minutos. **90s.** Janelas mais largas trazem ruído inaceitável (cross-talk entre mãos consecutivas).
- **Match primário:** mesmo canal Discord + janela temporal.
- **Match fallback** (mão veio via HM3 sem entry Discord da mão): janela ±90s sozinha, em qualquer canal Discord do mesmo torneio.

**Comportamento esperado da app** quando o Rui estuda uma mão: ver a imagem de contexto **inline** ao lado da mão (não num separador, não num click extra). A imagem **acompanha visualmente** a mão durante o estudo. Sem isto, o anexo perde o propósito.

**Implicação para o pipeline:** imagens directas Discord **NÃO devem** ser tratadas como mãos (nem virar entries que disparam Vision para extrair TM, nem virar placeholders em `hands`). Devem ser anexos a mãos existentes em BD, ligadas via tabela `hand_attachments`. Qualquer fluxo que crie hands a partir de `entry_type='image'` está a violar esta regra.

**Implementação (Bucket 1, Abr 2026):** tabela `hand_attachments` + worker `POST /api/attachments/match` (com `GET /preview` dry-run) + triggers fire-and-forget em `sync_and_process` e `import_hm3` que reanexam imagens órfãs após cada operação. Detalhes técnicos completos no MAPA §2.11; spec original em `docs/SPEC_BUCKET_1_anexos_imagem.md`.

## Auth

Cookie-based (`HttpOnly`, 7 dias, assinado com `SESSION_SECRET` via `itsdangerous`). `require_auth` é o dependency FastAPI para rotas protegidas. bcrypt para hashing de passwords. Não há CSRF para além de `SameSite` + CORS `ALLOWED_ORIGIN` — manter `ALLOWED_ORIGIN` apertado em produção.

## Ficheiros delicados — alto risco, ler o código inteiro antes de mexer

- **`backend/app/routers/screenshot.py`** — pipeline SS→HH com âncoras + aritmética de stacks + eliminação. Bugs aqui afectam **1000+ mãos** já em BD. Nunca alterar a ordem das fases nem a tolerância de stack sem correr um backfill de validação a seguir.
- **`backend/app/routers/mtt.py`** — especialmente `_promote_to_study`, `_create_villains_for_hand`, `import_mtt`. Toca arquivo, track de estudo e criação de villains em simultâneo; um erro pode contaminar as duas pistas.
- **`backend/app/services/hand_service.py:_insert_hand`** — detecta placeholders GGDiscord e apaga-os antes de inserir a HH real. Bug aqui **bloqueia imports inteiros**.

## MODELO DE DADOS E FLUXO (v2, 21-Abr-2026)

Consolidação após sessão de 21-Abr. Substitui o modelo antigo onde aplicável — nos pontos em conflito, **esta secção ganha**.

### 1. Quatro fontes de input

Cada input deixa uma marca diferente na mão:

| Fonte | Como entra | Marca em `hands` |
|---|---|---|
| **HM3 (.bat)** | Script `.bat` lê BD do HoldemManager3 e faz POST | `hm3_tags` = tags reais do HM3 (lista em `HM3_REAL_TAGS`) |
| **Discord** | Bot puxa mensagens de canais monitorizados | `discord_tags` = nome literal do canal (ex: `'nota'`, `'icm'`) |
| **Upload manual SS** | Drag-and-drop de screenshot na UI | `origin = 'ss_upload'` |
| **Import ZIP/TXT HH** | Upload de ficheiro HH bruto (GG/PS/Winamax/WPN) | `origin = 'hh_import'` |

### 2. Sete secções do sidebar

Depois da consolidação a **Inbox foi eliminada** (redundante com Dashboard + botão "Importar" lateral).

1. **Dashboard** — hub; painel "SSs à espera de HH" mostra origem + tempo em espera.
2. **Estudo** — razão nº1 da app. Só mãos em dúvida **com nomes reais**. Entra:
   - Discord de canal `!= 'nota'` **com match**
   - HM3 com tags `!= 'nota*'`
   - Uploads manuais com match SS↔HH
   - HH de PokerStars/Winamax/WPN (já têm nicks reais directamente)
   - **Não entra**: HH GGPoker sem match (anonimizada).
3. **Vilões** — lista de nicks. Modal mostra apenas mãos em `hand_villains` desse nick (não mais VPIP global).
4. **Torneios** — aba GGPoker (Com SS / Sem SS); aba HM3 com Tag.
5. **Discord** — centro de operações SS↔HH: logs detalhados, associação de gyazos (±90s → mão adjacente). **Sem** listas de SSs/mãos (vivem no Dashboard / Estudo / Vilões).
6. **HM3** — centro de operações do script `.bat`: logs, listagem de mãos filtrável (tag / data / PKO-NPKO / pré-flop vs pós-flop), edição manual de tags com re-avaliação automática de destinos.
7. **GTO** — biblioteca de árvores HRC + GTO Brain. A página `/gto` é só gestão da biblioteca; o consumo real é a tab GTO **dentro do replayer** (match automático da árvore + navegação até ao nó do Hero). Fase 1 fechada em pt35 (watcher exporta Complete Export). Detalhe completo em `docs/GTO_BRAIN.md`.

### 3. Transições entre secções

Regras determinísticas; cada mão pode cair em múltiplos sítios:

| Condição na mão | Vai para |
|---|---|
| `hm3_tags` contém tag `~ 'nota%'` | Vilões |
| `hm3_tags` contém outras tags | Estudo |
| `hm3_tags` mistas (ex: `['ICM','nota']`) | **Ambas** — cada secção filtra só as tags da sua semântica |
| `discord_tags` contém `'nota'` + tem match | Vilões |
| `discord_tags` outros canais + tem match | Estudo |
| non-hero é nick em `FRIEND_HEROES` (Karluz, flightrisk) | Vilões (Regra D, sem tag necessária) |
| SS sem HH (match falhou) | Dashboard (painel "À espera de HH") |
| HH GGPoker sem SS | Torneios > GG > Sem SS |
| HH PokerStars/Winamax/WPN sem SS | Estudo directo (já têm nicks reais) |
| Match SS↔HH | Bidireccional: qualquer lado pode chegar primeiro |

### 4. Regra de elegibilidade para `hand_villains`

Uma mão gera entry em `hand_villains` sse **(A ∨ C ∨ D)** — regras canónicas em `_classify_villain_categories` (`backend/app/services/hand_service.py`):

- **(A)** `hm3_tags` contém tag a começar por `nota` → `category='nota'`.
- **(C)** `'nota' = ANY(discord_tags)` **AND** `player_names ->> 'match_method' IS NOT NULL` (não `discord_placeholder_*`) → `category='nota'`.
- **(D)** `villain_nick` em `FRIEND_HEROES` (`backend/app/hero_names.py` — actualmente Karluz, flightrisk) → `category='friend'`. Independente de tag; dispara sempre que o nick aparece como non-hero numa mão com nicks reais.

**Pré-condição padrão** do classificador: villain tem `has_cards` (showdown) OU `has_vpip` (call/raise/bet preflop). **Excepção #B19** (pt9): tag HM3 `nota%` ignora a pré-condição — qualquer non-hero que viu o flop é elegível. Detalhe completo em `docs/REGRAS_NEGOCIO.md` §3.3.

O modal do vilão mostra **só** mãos presentes em `hand_villains` — não mais o VPIP global antigo, que puxava toda a mão onde o vilão aparecia.

**Princípio invariante:** NUNCA criar villain numa mão GG anonimizada (sem `match_method`). Aplica-se às 3 regras — C exige `match_method` explicitamente; A aplica-se a tags HM3 que em GG implicam match na prática; D não dispara em GG anon porque `FRIEND_HEROES` exige nick real, não hash.

### 5. Filtro permanente: só mãos de 2026

Rui só estuda mãos de 2026. **Qualquer query ad-hoc ou script contra `hands` deve incluir `played_at >= '2026-01-01'`**. Em produção a UI já filtra; em scripts `query_*.py` / `backfill_*.py` é obrigatório. Histórico anterior existe na BD mas é ruído para qualquer análise actual.

---

Última sessão fechada: pt13 (4 Maio 2026, 5 features fechadas: #B-NOVO-2, #B29, #B31, refactor study_state, dashboard expandido. Limpeza HANDOFF + TECH_DEBTS §5-§10. ~15 commits c979181 → final).

## FASE 1 — HRC Export Queue (deployed 8 Maio 2026)

Pipeline completo `tournament_payouts` → endpoint `GET /api/queue/hrc` → zip com `<hand_id>/hh.txt` + `<hand_id>/payouts.json` + `manifest.json`. Validado end-to-end em prod com smoke real BBG $215.

- `routers/payouts.py` — `POST /api/payouts` upsert opaco do blob HRC Structure Manager.
- `services/queue_export.py` — conversor HH GG → PokerStars-compativel + `build_queue_zip()`.
- `routers/queue.py` — `GET /api/queue/hrc` com filtros tags/study_state/played_after/played_before/include_no_payout.

Smoke test em prod: 1 row em `tournament_payouts` (TM 281416137 BBG $215), zip download OK com 4 mãos.

## FASE A — Pipeline lobbys via Discord (✅ DEPLOYED, fechada em pt19)

Pipeline real-time `SS no #lobbys → Vision Anthropic Sonnet 4.6 → tournament_resolver → upsert tournament_payouts`. Gaps G1/G2/G3 identificados em pt18 fechados em pt19:

- **A** (`d6dedda`) — token-set match em `tournament_resolver` (cobre G2 — nome com palavras omitidas).
- **B** (`c6088ee`) — fallback `hands` source + `posted_at_hint` window (cobre G1 Winamax/PS e mitiga G3).
- **C** (`f87be3a`) — caption manual `#TM<numero>` no post Discord (bypass total do resolver; cobre G3 final).
- **refactor** (`440b248`) — terminologia TM → `tournament_number`. Serviço renomeado `tm_resolver.py → tournament_resolver.py`. Categoria (a)(b)(c) fechada; categoria (d) (~50 sítios no pipeline `hand_id GG`) deferida para pt20+.

Pendente apenas: **D** Gyazo URLs, **E** sync-recent UI, **F** cleanup instrumentation `[debug-msg-lobby]`.

## FASE B — Tournament Summaries GG (✅ DEPLOYED em pt19)

GG emite ficheiros TS quando torneios terminam, com `tournament_number` literal no header. Fonte autoritativa post-jogo. Integrada como TIER 0 do resolver.

- **B1** (`9ad1ceb`) — tabela `tournament_summaries (site, tournament_number)` PK composto. Parser GG-only com 14 campos: `tournament_name`, `buy_in_text/total/currency`, `total_players`, `prize_pool`, `start_time`, `hero_position/payout/re_entries`, `raw_text`, `source_filename`. Endpoint `POST /api/tournament-summaries/import` (`.txt` ou `.zip`). UI: botão em `Tournaments.jsx`.
- **B1.x** (`417c071`) — parser estendido com 12 campos novos. **Literais**: `game_type`, `buy_in_entry/rake/bounty`, `hero_total_received`, `hero_finish_phrase_position`, `tournament_modifiers`, `tournament_series`. **Heurísticas**: `tournament_speed`, `tournament_schedule`. **Derivados** (via `apply_ratio_lookup`): `tournament_format`, `tournament_pko_ratio`. Total: **26 campos**.
- **B2** (`cdbbc59`) — TIER 0 `tournament_summaries` antes de TIER 1 `tournaments_meta` e TIER 2 `hands` fallback. 3 helpers privados `_query_summaries/_query_meta/_query_hands` isolam SQL por tier.
- **B2.1** (`c0ddef5`) — TIER 0 **sem janela temporal** (TS é autoritativo post-jogo). Discriminação por `prize_pool` + `total_players` da Vision (estritos, opt-in). Tiers 1+2 inalterados — torneios em curso (sem TS ainda) continuam com janela apertada.

## Cinco fontes de input

Após FASE B a app tem 5 fontes de input distintas (era 4 em pt13):

| Fonte | Como entra | Marca/destino |
|---|---|---|
| **HM3 (.bat)** | Script .bat lê BD do HoldemManager3 e faz POST | `hm3_tags` |
| **Discord** | Bot puxa mensagens de canais monitorizados | `discord_tags` |
| **Upload manual SS** | Drag-and-drop de screenshot na UI | `origin = 'ss_upload'` |
| **Import ZIP/TXT HH** | Upload de ficheiro HH bruto | `origin = 'hh_import'` |
| **Tournament Summaries GG** | Upload `.txt`/`.zip` em `Tournaments.jsx` | `tournament_summaries` (não toca `hands`) |

Detalhe completo em `docs/JOURNAL_2026-05-11-pt19.md` e `docs/TECH_DEBTS_INVENTARIO.md` "Estado actual (11 Maio 2026)".

## 11 commits da pt19 em main

```
d6dedda  FASE A commit A — token-set match em tm_resolver
c6088ee  FASE A commit B — fallback hands + posted_at_hint
f87be3a  FASE A commit C — caption manual TM em #lobbys
440b248  refactor — TM → tournament_number (categoria a/b/c)
9ad1ceb  FASE B B1 — import de Tournament Summaries GG
e6bef2d  diag — logger.exception + repr no except do TS import
0b0a087  fix B1 — usar RealDictCursor key no RETURNING
cdbbc59  FASE B B2 — tier 0 tournament_summaries no resolver
417c071  FASE B B1.x — parser TS extendido (12 campos novos)
c0ddef5  FASE B B2.1 — TIER 0 sem janela + prize_pool/players
a4a9595  GTw → pos-nko backfill + alias no importer
```

## Backfill operacional pt19 — GTw → pos-nko

Rui descontinuou tag HM3 `GTw`. 25 mãos PS/Winamax/WPN migradas em prod (0 GG, 0 overlap). Tag canónica nova: `pos-nko` em `HM3_REAL_TAGS` com id sintético `9999` (não vem do HM3 — é nome de canal Discord). Helper `apply_hm3_tag_aliases()` em `backend/app/services/hm3_tag_aliases.py` aplica o rename pre-INSERT no `import_hm3`, garantindo idempotência face a re-imports do `.bat`.

### Variáveis de ambiente FASE A (Railway service `poker-app`)

| Var | Default | Descrição |
|---|---|---|
| `ANTHROPIC_API_KEY` | (obrigatório) | API key Anthropic. Adicionada em pt18. Usado por `services/lobby_vision.py`. |
| `OPENAI_API_KEY` | (obrigatório) | Já existia. Continua para Vision GG screenshots em `routers/screenshot.py`. **Rotada em pt18.** |
| `DISCORD_LOBBY_CHANNEL` | `lobbys` | Nome do canal Discord dedicado a screenshots de lobbys. Lowercase. |
| `DISCORD_LOBBY_AUTO` | `false` | Real-time processing do canal lobby. **Independente** de `DISCORD_AUTO_SYNC` global. Activado em prod em pt18. |

**Importante:** mudanças em `DISCORD_LOBBY_*` precisam de redeploy (`railway redeploy -s poker-app` ou push trivial) — env vars são lidas no module load, não em runtime.

## pt20 — sync-recent + backoffice import (12 Maio 2026)

2 commits feature em main:

- **Commit E** (`5465b32`) — `POST /api/lobbys/sync-recent` + tabela nova `lobby_processing_log` (PK `discord_message_id`, regista cada tentativa do handler real-time + sync). Refactor: lógica core de `_handle_lobby_message` extraída para `services/lobby_sync.py:process_lobby_message`. Sub-painel UI em `Discord.jsx`. Suite 122→138.
- **Backoffice import** (`af7e3c8`) — `POST /api/tournament-results/import` para upload de SSs do backoffice GG (página de resultados pós-jogo). Vanilla + PKO; Mystery KO → `mystery_unsupported` fail-fast. Cruza com `tournament_summaries` via TIER 0 resolver (prize_pool+total_players). Refactor: `detect_image_mime` extraído para `services/image_utils.py`. Suite 138→154.

**6 fontes de input** (era 5 pós-pt19, +1 com backoffice import):

| Fonte | Como entra | Marca/destino |
|---|---|---|
| **HM3 (.bat)** | Script .bat lê BD do HoldemManager3 e faz POST | `hm3_tags` |
| **Discord (canais estudo)** | Bot puxa mensagens de canais monitorizados | `discord_tags` |
| **Discord (#lobbys)** | Real-time + sync-recent batch | `tournament_payouts` + `lobby_processing_log` |
| **Upload manual SS** | Drag-and-drop de screenshot na UI | `origin = 'ss_upload'` |
| **Import ZIP/TXT HH** | Upload de ficheiro HH bruto | `origin = 'hh_import'` |
| **Tournament Summaries GG** | Upload `.txt`/`.zip` em `Tournaments.jsx` | `tournament_summaries` |
| **Tournament Results backoffice GG** | Upload `.png/.jpg/.zip` em `Tournaments.jsx` | `tournament_payouts` (cruza com TS por pool+players) |

**Precedência `tournament_payouts.source`:** `manual:` > `backoffice_vision:` > `discord_lobby_vision:`. UPSERT sempre permitido em real-time; `skip_existing` opt-in skipa apenas backoffice/manual prévios.

## pt21 — Backend Fase 3 HRC (12 Maio 2026)

3 commits feature em main fecham backend Fase B do plano HRC:

- **G3** (`5b9c10a`) — tabela `hrc_jobs` (schema). `ensure_hrc_jobs_schema()` no lifespan startup. PK `id BIGSERIAL`, FK `hand_db_id INTEGER REFERENCES hands(id) ON DELETE CASCADE`, `UNIQUE (hand_db_id)`, status CHECK constraint (5 valores: `submitted/running/done/failed/expired`), `result_zip BYTEA` + `result_zip_size INTEGER`, `meta_json JSONB`, índice `(status, submitted_at)`. Sem tests dedicados (opção B — cobertura indirecta via G2). Suite 154→154.
- **G4** (`764b53e`) — auth dual-path `require_auth_or_api_key` em `app/auth.py`. Aceita cookie OU `Authorization: Bearer <token>` comparado em constant-time com env var `HRC_WATCHER_API_KEY`. Aplicado em `GET /api/queue/hrc` (futuro `POST /results` em G2). Bearer inválido NÃO faz fallback para cookie. `require_auth` legado mantido para cookie-only nos outros 21 routers. Suite 154→161 (+7 cases).
- **G2** (`2fa1f60`) — `POST /api/queue/hrc/results` multipart. Pipeline: lookup `hand_id` (404 ausente), validar zip (50 MB cap, parseable, contém `meta.json`), extrair meta server-side, augmentar com `hand_id/received_at/received_from`, UPSERT em `hrc_jobs` por `hand_db_id`. `submitted_at` preservado em UPDATE (semântica "1ª submissão"). Helpers novos em `services/hrc_jobs.py`. Suite 161→172 (+11 cases, todos <0.01s).

**`HRC_WATCHER_API_KEY`** setada em Railway → service `poker-app` → environment `production` pelo Rui (gerada via `python -c "import secrets; print(secrets.token_urlsafe(48))"`, colada directamente, sem passar por Code/Web). Smoke validado: GET com Bearer → 200, size=279910 bytes (zip elegível). POST sem auth → 401 (rota activa); POST com Bearer + hand_id inexistente → 404 (pipeline completo).

### Variáveis de ambiente FASE 3 (Railway service `poker-app`)

| Var | Default | Descrição |
|---|---|---|
| `HRC_WATCHER_API_KEY` | (obrigatório para watcher) | Token URL-safe 48 bytes. Aceite em paralelo ao cookie em `require_auth_or_api_key`. Adicionada em pt21. Usada por endpoints `/api/queue/hrc` (GET) e `/api/queue/hrc/results` (POST). Rotação = mudar env var + redeploy. |

### Fontes de input (era 6 pós-pt20; +1 com results do watcher = 7 entradas + 1 saída-com-retorno)

A 8ª linha abaixo é o **único caminho** que **devolve dados ao backend** (em vez de só entrar):

| Fonte | Como entra | Marca/destino |
|---|---|---|
| **HM3 (.bat)** | Script .bat lê BD do HoldemManager3 e faz POST | `hm3_tags` |
| **Discord (canais estudo)** | Bot puxa mensagens de canais monitorizados | `discord_tags` |
| **Discord (#lobbys)** | Real-time + sync-recent batch | `tournament_payouts` + `lobby_processing_log` |
| **Upload manual SS** | Drag-and-drop de screenshot na UI | `origin = 'ss_upload'` |
| **Import ZIP/TXT HH** | Upload de ficheiro HH bruto | `origin = 'hh_import'` |
| **Tournament Summaries GG** | Upload `.txt`/`.zip` em `Tournaments.jsx` | `tournament_summaries` |
| **Tournament Results backoffice GG** | Upload `.png/.jpg/.zip` em `Tournaments.jsx` | `tournament_payouts` |
| **Watcher HRC (Beelink)** *(pt21)* | `POST /api/queue/hrc/results` com zip Complete Export | `hrc_jobs` |

## pt22 — Adapter Beelink G1 + smoke real (13 Maio 2026)

2 commits feature em main:

- **G1 adapter** (`cc93698`) — `tools/hrc_adapter/` (4 ficheiros novos, 705 insertions): `hrc_adapter.py` (410 linhas), `requirements.txt`, `.gitignore`, `README.md`. Loop Python 3.14 corre no Beelink (perfil `riand` elevated UAC) e cose `GET /api/queue/hrc` ↔ filesystem watcher ↔ `POST /api/queue/hrc/results`. Decisões D1-D10 + A1-A5 aprovadas. `state.json` local com atomic write é dedup (D10). Logging `TimedRotatingFileHandler` retenção 14 dias.
- **Fix regex Winamax** (`67761a0`) — `HAND_ID_RE` passa de `^[A-Z]+-\d+$` para `^[A-Z]+-\d+(-\d+)*$`. 40 mãos `WN-XXXX-YY-ZZ` saltadas no 1º tick smoke real.

**Setup Beelink (Rui):** Python 3.14.5 instalado, HRC reinstalado em `C:\Users\riand\AppData\Local\Programs\HoldemResources\HRC\` (path moderno sem "Beta"). Perfil `Administrator` legacy **preservado pelo reset Windows nuclear** — pasta `C:\Users\Administrator\Documents\Teste completo\` com `queue/done/arquivo/replied` + script Charles literal `mtt_advanced_20211029 - 2 flats + bb close action size open 2x - 3x bvb.js` ficou intacta post-reset. Watcher corre directo sob `Administrator` legacy, sem junctions externas.

**Pipeline mecânico validado ponta-a-ponta:** GG-5914506215 + GG-5915052810 entraram em queue, watcher abriu HRC, executou wizard completo (paste HH → max players → equity model → scripting → calculate). Smoke real funcional bloqueado por 3 bugs do watcher (ver `#HRC-WATCHER-*` em TECH_DEBTS).

### 3 bugs watcher descobertos via smoke real

| Bug | Sintoma | Solução |
|---|---|---|
| **A — equity model fixo** | Watcher escolhe sempre `Malmuth-Harville ICM`, sem branch para `Multi-Table FGS`. Mãos mid-MTT têm equity FT-style. | Tag-based hint via `payouts.json` (Discord canais `#icm-ft`/`#icm-pko-ft` + HM3 tags). Ver `REGRAS_NEGOCIO.md §14`. |
| **B — max players estático** | `get_player_count_from_hh()` usa regex de seats sentados em vez de jogadores relevantes à decisão. Árvore explode com seats vazios. | Parsing HH no watcher: `last_raiser→hero` + `hero→action_close`. |
| **C — JS hardcoded → OOM** | Nome literal `mtt_advanced_..._bvb.js` carregado fixo; ranges largos provocam tree >20GB → crash HRC. | Imediato: substituir o ficheiro com mesmo nome por versão tight. Final: config externa por tag/profundidade. |

Todos os 3 exigem fonte Python do watcher. Baltazar emigrou, sem contacto. **Decisão pt22**: descompilar `hrc_watcher.exe` em pt23 via `pyinstxtractor` (já corrido — bytecode em `_local_only/extracted/`) + `pycdc`, fix cirúrgico, recompilar com PyInstaller. Plano em `docs/PLAN_PT23.md`.

### Auth debug pt22 (resumo)

3 rotações no Railway dashboard + copy-paste contaminado + sessões PowerShell sem refresh do `setx` causaram 401s repetidos. Diagnóstico CLI confirmou Railway estável; desalinhamento estava sempre do lado Beelink. **Solução final**: `.bat` no Desktop do PC principal extrai token live via `railway variables --kv` (token nunca exposto ao chat) e faz `setx` automático no Beelink quando Rui dá duplo-clique. Token `Z10Soz9...37zSZ` exposto numa screenshot Railway durante debug → tech debt `#TOKEN-ROTATION-DEFENSIVE-PT23`.

### Estado Fase 3 HRC pós-pt22

- **G1 adapter** ✓ deployed (`cc93698`)
- **G2 POST /results** ✓ pt21 (`2fa1f60`)
- **G3 schema hrc_jobs** ✓ pt21 (`5b9c10a`)
- **G4 auth dual-path** ✓ pt21 (`764b53e`)
- **Smoke real mecânico** ✓ ponta-a-ponta validado
- **Smoke real funcional** ✗ bloqueado por bugs A/B/C
- **G5 UI botão exportar** ⏸ pendente (depende de smoke funcional)
- **G6 UI badge HRC** ⏸ pendente

### Pasta nova `tools/hrc_adapter/`

Repo passa a ter `tools/` para utilities locais não-backend não-frontend. Fica fora do dev server / build. Conteúdo source-controlled (audit + review via PR); cópia manual para o Beelink.

## pt23 — Descompilar watcher + fixes A/B/C/E (13 Maio 2026)

Descompilação do `hrc_watcher.exe` (PyInstaller 6.x, Python 3.12) via build local de `pycdc` (Visual Studio 2022 Build Tools + CMake 4.3 instalados from-scratch). Recuperação ~72% das funções limpas; restantes 28% via disassembly manual `dis` no host 3.12. Material persistido em `_local_only/watcher_decompile/decompiled/`.

**Marshal swap surgical** — `tools/watcher_src/patched_funcs.py` (~212 linhas) com 4 funções compiladas no host 3.12 e swapped no `co_consts` do module code original. Re-bundle via trampoline `wrapper.py` minimal (gitignored em `_local_only/`). Fecha Bugs A/B/C/E.

**Backend hints** — `derive_max_players(hh_text)` + `_derive_equity_model` baseado em tags `ICM FT`/`ICM PKO FT` (HM3) ou `icm-ft`/`icm-pko-ft` (Discord). Hints injectados no `payouts.json` de cada mão. Suite 172 → 184 PASSED.

**Adapter fixes** — `detect_done_zips` apanha `done/Exports/<hand>.zip` (layout Baltazar) além do directo; `_ensure_meta_in_zip` injecta meta minimal quando o zip HRC nativo não traz `meta.json`.

**Ciclo mecânico ponta-a-ponta validado em prod** com mão real `GG-5914506215` (`hrc_jobs.id=1, status=done, result_zip_size=3586`).

5 tech debts pt23 abertos, incluindo o **gatekeeper de produção** `#HRC-PRUNE-IN-GAP-DOWNSTREAM` (HIGH) — sem prune, smoke real produz trees com ETA ~17h.

2 commits feature em main: `c3cc66b` backend hints + `b3968ee` watcher/adapter consolidados.

## pt25b/c/d — Robustez backend + fix Railway + indices canónicos (14 Maio 2026)

Três pontas sobre o gatekeeper `#HRC-PRUNE-IN-GAP-DOWNSTREAM`. Backend acabou completo.

| pt | Foco | Commit | Suite |
|---|---|---|---|
| **pt25b** | Robustez cross-site (PS/GG/WN/WPN) — Winamax markers, duplicate `let` fix, table format detection | `f32ed28` | 264 PASSED |
| **pt25c** | `hrc_scripts/` move de `tools/` para `backend/app/services/` (Railway nixpacks só ship `backend/`) + manifest `prune_script_error` defensivo | `77ff496` | 264 PASSED |
| **pt25d** | Convention indices fix — `UTG=0` (docs canónica HRC) substitui rotativa `SB=0`. Manifest field `prune_index_convention='hrc_docs_v1'` distingue zips pré/pós | `3347fcf` | 266 PASSED |

Smoke real pós-pt25d: indices certos chegam ao Beelink no `script.js` (validado visual). Watcher só faz 1ª run + save directo — sem 2ª run em Selected Subtree.

**5 bugs novos do watcher** (F-J) + 1 feature de re-arquitectura (K) abertos para pt25e/pt25f.

## pt25e — Bloco 1 fechado + ★ Pipeline HRC → app v1 (14-15 Maio 2026)

**Bloco 1** (14 Mai, 3 commits `8eb9d87`/`f7c8833`/`bad2c51`): helper backend `derive_aggressor_real_action` + stubs defensivos no source watcher para Bugs F/G/H/J. `setup_hand` ganha encapsulamento `finalize_after_second_run` separado do export. `.exe` em produção intacto pt25d — Bloco 1 valida arquitectura, não muda comportamento operacional.

**Bloco 2 manhã 15 Mai**: smoke devagar manual com mão GALACTICA (`WN-4706316461629505541-158-1778795596`, Winamax). Fix urgente `#META-AGGRESSOR-POSITION` (`c6d6c40`) + follow-up BU canónico (`BTN → BU` em `_POSITION_LABELS_BY_N`).

**★ HRC Import Pipeline v1** (`4fa09be`) — primeiro ciclo fechado `mão → HRC → resultado importado na app`. Schema novo + 4 endpoints + UI `/hrc-sessions`. DELETE endpoint (`e45e507`). Marco simbólico.

**`#ORFA-HM3-SYNTHETIC-ENTRIES`** — 1117 mãos retroactivamente linkadas via backfill em 6+1 commits sequenciais. Suite 282 → 340.

## pt25f — Trabalho A + Bloco 2 watcher peças 1+2 (15-18 Maio 2026)

Sessão longa. Cobre dois sub-arcos:

**15-16 Mai (núcleo):** 3 fixes case-sensitivity (`76e2ea7`/`0444cf2`/`11c2dea`) via `normalize_tag_key`. Deprecation fix `datetime.utcnow()` → `datetime.now(timezone.utc)`. Versionamento `tools/apphm3/` + config externo. Rotação password Postgres. **★ Trabalho A** (`9b6e839`) — refactor do gerador `.js` HRC: sizings per-hand a partir do action log preflop real, drop prune via JS (gerador trabalha em arrays numéricos overridable).

**18 Mai (extensão):** multiplicador 3-bet clássico em 5 buckets (`7e38d89`). Bloco 2 watcher peças 1+2 (`f99e994`/`fa4f21a`/`92778bd`) — `_set_scope_in_popup` + `start_calculation_selected_subtree` paralela ao legacy + smoke calibração + flow Selected Subtree end-to-end + meta.json automático + navegação por setas.

Suite 340 → 449 PASSED (+109 líquidos). 10 commits em main.

## pt26 — Recompilação `.exe` + re-classificação do sintoma (19 Maio 2026)

Recompilação do `.exe` watcher pós-pt25f source-side completo. 1 commit feature em main (`a735053` pt26 smoke calibração); trabalho substancial em `_local_only/` (gitignored): trampoline `swap_and_smoke.py` (4 SWAP + 13 APPEND + 15 consts), bundle PyInstaller (sha256 `2213aa19...a4a7`, 12.86 MB), smoke harness 14/14 PASS.

**Coord Calculate validada** `(487, 124)` absoluta / `(204, 59)` rel à wpos. Título popup refinado para `"Nash Calculation"` exacto. Migração das fracções do popup para pixels-rel (rect do popup varia ~5-7% entre sessões).

**Re-classificação do sintoma do equity_model.** O que se via como FT/MTT mismatch é cadeia `#VISION-LOBBY-API-FAILURE` → `#HRC-CONTEXT-MISMATCH-PLAYERS-LEFT` mascarada pelo workaround `#HRC-MTT-OTHER-TABLES-INFO` aceite em pt23. Design tag-based é canónico desde pt23 — não é regressão.

5 tech debts novos incluindo o CRIT `#START-CALC-SELECTED-SUBTREE-NO-POPUP-OPEN` (peça 1 do Bloco 2 falha em runtime — popup Nash não abre na 2ª run).

## pt27 — 3 fixes backend HRC + auditoria 7 dias (19-20 Maio 2026)

Bloco A (auditoria 7 dias, read-only): 4602 mãos, 4 categorias diagnosticadas, regressão antiga `study_state` descoberta (`#STUDY-STATE-REGRESSION-HH-IMPORT`, desde 18 Abr — decisão product pendente sobre fix vs aceitar). Vision API failure ~34% (10/29).

Bloco B (3 fixes backend num só commit `7de8df6`):

| Tech debt | Como fechou |
|---|---|
| `#CI-DEFAULT-MISMATCH` | Backend `_DEFAULT_CI_TARGET_FIRST_RUN = 5.0` → `_DEFAULT_CI_TARGET = 10.0`. Alinha 1ª e 2ª runs em 10. |
| `#DERIVE-MAX-PLAYERS-HERO-REGEX-GG` | 3 sub-bugs em `derive_max_players.py`: `_HERO_RE` apanhava 1º "Dealt to" (em GG pós-`_replace_hashes` todos os seats têm essa linha); `\S+` truncava nicks com espaços; `_SEAT_RE` matchava SUMMARY. Mão real `GG-5944816316`: `max_players` 4 → 6. |
| `#COMPUTE-TARGET-NODE-OFFSET-USES-WRONG-PLAYER-COUNT` | Param renomeado `max_players` → `seats_at_table`. Strategy Table HRC tem 1 linha-base por jogador real sentado, não pela redução ICM. Mão real: offset null → 4. |

Bloco C (fix funcional `.exe` watcher) fica para pt28. Suite 449 → 455 PASSED (+6 líquidos).

## pt28 — Clipboard race + descoberta do formato HH PokerStars (20 Maio 2026)

Sessão sem journal separado (absorvido no pt29 quando o chat encheu). Trabalho coberto pelo `HRC_ANATOMIA_OPERACIONAL.md` v1→v3 e por tech debts.

**pt28-v2/v3 clipboard race fix.** Causa raiz: bug do `pyperclip 1.11.0` em `CheckedCall.__call__` que esconde falhas Win32 silenciosas (errno do CRT não actualizado por chamadas user32). Combinado com várias apps a competir pelo clipboard ownership no Beelink (HM3, Win+V cloud sync, RDP) levou a 40 de 41 mãos perdidas em 14 Maio. Fix: `clipboard_safe_paste` faz set + read-back verify + retry com pausa antes de mandar Ctrl+V.

**Descoberta crítica do formato HH aceite pelo HRC.** O parser GG do HRC **rejeita** qualquer tentativa de embutir bounty na linha Seat. Para o HRC processar a info de bounty é obrigatório converter a HH GG inteira para formato PokerStars (11 transformações: prefixo header, level format, chips sem vírgulas, bounty na seat com símbolo da moeda, `Dealt to` filtrado a Hero, SHOWDOWN só se houver showdown real, etc.). Implementado em `convert_gg_hh_to_pokerstars_compatible` em `backend/app/services/queue_export.py`.

Documento `HRC_ANATOMIA_OPERACIONAL.md` criado e iterado nesta sessão (v1 manhã → v2 tarde → v3 fim do dia).

## pt29 — Cascata de 3 fixes ao robot HRC (20-21 Maio 2026)

Cascata de 3 fixes ao robot watcher, smoke real com mão `GG-5944816316`:

| Versão | Commit | Fix |
|---|---|---|
| pt29-v1 | `1b5b388` | State check pós-Finish via título "Hand Setup" + activate pré-click + logging defensivo. WARN-only no state check. Resultado: hipótese de foco descartada. |
| pt29-v2 | `cb4c520` | **Slow-click no Finish** (`mouseDown → sleep(0.15) → mouseUp`). Causa raiz: HRC Java perde eventos de click instantâneo. **Validado** — wizard fecha. |
| pt29-v3 | `3b9d72c` | `wait_for_calculation()` (Baltazar OG, já no namespace mas inutilizada) em 2 pontos: após 1ª run incondicional; após 2ª run condicionado a `second_run_dispatched is True`. Heurística: memória estável >100 MB e variação <20 MB durante 3 ciclos de 10s. **Instalado no Beelink, smoke por arrancar à hora do fecho.** |

Documento `HRC_ANATOMIA_OPERACIONAL.md` atualizado para v4 com 3 factos novos descobertos: slow-click obrigatório no Finish, ausência de sinal explícito de "calculation done" (única inferência via memória), Hand Mode Max 6 para mesas 8-handed deep PKO.

1 tech debt novo: `#HRC-BOUNTY-HARDCODED-50PCT` (robot tem PKO 50% hardcoded; precisa de ler do `tournament_format` parsed do TS para suportar PKO 25% e Mystery KO).

**Mecânica de entrega de exes ao Rui:** Code constrói exe em `_local_only/watcher_decompile/build_pyi/dist/hrc_watcher.exe` no PC principal; Rui transfere para Beelink por qualquer canal; Web fornece `instala_ptXX.bat` via outputs; duplo-clique no .bat faz SHA-check + backup do exe antigo + instalação automática.

## pt30-pt34 — Fecho da cadeia da 2ª run do HRC (22 Maio 2026)

Madrugada. **Toda a cadeia da 2ª run (Selected Subtree) ficou funcional ponta-a-ponta** no Beelink, com `.zip` final de ~23 000 nós (equivalente ao Save As manual). 6 commits feature em main, todos no robot watcher (`tools/watcher_src/patched_funcs.py` + 2 ficheiros de teste); `.exe` **não recompilado** (passo separado). Suite **550 → 569 PASSED**.

| Etapa | Commit | Fix |
|---|---|---|
| pt30 | `52aef9c` | Polling Win32 do estado do botão Finish (enabled→disabled→enabled) antes do slow-click. **Discovery: o HRC usa SWT, não Swing** — widgets expostos como child windows nativas ao Win32. |
| pt31 | `0f159bc` | `_wait_for_run_completion` via janela de progresso "Hand Setup" (sinal binário) substitui a heurística de memória do `wait_for_calculation` (que dava falso positivo). |
| pt32 v1 | `61dfa5f` | Coord Y do Play da 2ª run 59→64 + logging `[calc-diag pre-click]`. Falhou no smoke, mas o logging desbloqueou o diagnóstico. |
| pt32 v2 | `c9c8818` | Origem do click do Play: `wpos` (do wizard já fechado) → `find_hrc()`. **Popup Nash abre.** |
| pt33 v1 | `867460c` | OK do popup Nash via `BM_CLICK` Win32 (o Enter não funciona no popup). Popup `#32770` com Button OK exposto. **2ª run dispara.** |
| pt34 v1 | `e58c517` | `_wait_for_run_completion` da 2ª run procura substring "Monte Carlo Sampling" (a janela de progresso da 2ª run não é "Hand Setup"). **Ciclo ponta-a-ponta.** |

Docs desta sessão: `HRC_ANATOMIA_OPERACIONAL.md` v5; `JOURNAL_2026-05-22-pt30-pt34.md` (novo); `RUNBOOK_SMOKE_BEELINK.md` v2; `WORKFLOW_OPERACIONAL.md` (novo); `PENDENTES.md` (novo). 6 tech debts fechados, 2 abertos (`#CURSOR-ANOMALY-POST-SAVE-AS`, `#WIZARD-FINISH-FALSE-POSITIVE-STATE-CHECK`).

## pt35 — GTO Brain Fase 1 (22 Maio 2026)

**Fase 1 do GTO Brain fechada.** O watcher passa a exportar em **Complete Export** — antes corria "Manual Selection" sem selecção = **1 nó por árvore** (inútil). Smoke real ponta-a-ponta **funcional** validado no Beelink (`GG-5944816316`, Bounty Hunters Daily, 2 runs), `.zip` final **44 MB** (faixa empírica 40-70 MB) contra 1 nó / ~6 KB antes. `.exe` recompilado e instalado, SHA256 `33eae43a…c53c4f`. É o primeiro ciclo `app → adapter → watcher → adapter → app` validado de verdade (até pt23 só mecânico).

3 commits em main:

| Commit | O quê |
|---|---|
| `7eca782` | docs — novo `GTO_BRAIN.md` (v1): visão consolidada do GTO Brain (origem, filosofia, arquitectura `gto_trees`/`gto_nodes` + matching engine v3, plano em 3 fases). |
| `94a83b1` | watcher — `export_strategies` (SWAP em `tools/watcher_src/patched_funcs.py`) muda o combo do diálogo Export Strategies de "Manual Selection" → **"Complete Export"** via Win32 `CB_SETCURSEL` (idx 0→1, read-back) + `CBN_SELCHANGE`; OK por `BM_CLICK`; Save As via `_save_as_set_and_click` portado. `wrapper.py` boota o trampoline **sem** `make_patched_export`. |
| `c22a617` | docs — `GTO_BRAIN.md` regista a smoke battery de robustez (`#PIPELINE-ROBUSTNESS-SMOKE-BATTERY`) como pré-requisito da Fase 2. |

(+ `135be97` docs — clarificação do `#HRC-BOUNTY-HARDCODED-50PCT`: flow data-driven vs hardcoded, validação parcial só PKO 50%.)

Tech debts: ✅ fechado `#GTO-WATCHER-EXPORT-DEFAULT-DEPTH-2`; 🟢 novo/resolvido `#DOC-MAKE-PATCHED-EXPORT-OVERRIDES-SWAP` (o launcher Baltazar sobrescrevia o SWAP de `export_strategies` pós-`exec` via `make_patched_export`; resolvido bootando o trampoline directamente no `wrapper.py`); 🟡 novo **aberto** `#PIPELINE-ROBUSTNESS-SMOKE-BATTERY` (validar 4 combinações site × formato antes da Fase 2). Detalhe em `docs/HRC_ANATOMIA_OPERACIONAL.md §8`, `docs/GTO_BRAIN.md` e `docs/TECH_DEBTS_INVENTARIO.md`.

Docs desta sessão: `GTO_BRAIN.md` (novo, v1); `HRC_ANATOMIA_OPERACIONAL.md` §8 (v6); `TECH_DEBTS_INVENTARIO.md` (secção pt35); `PENDENTES.md`; `RUNBOOK_SMOKE_BEELINK.md`; `WORKFLOW_OPERACIONAL.md`; `JOURNAL_2026-05-22-pt35.md` (novo).

## pt36 — HRC Run-2 always-dispatch (23 Maio 2026)

**Backend-only; `.exe` do watcher não tocado.** Garante que **toda mão exportada para o robot tem 2 runs** (Opção D1). Fecha `#HRC-RUN-2-ALWAYS-DISPATCH`, removendo o blocker que fazia algumas mãos exportarem só 1 run (qualidade inconsistente da biblioteca GTO).

**Origem:** investigação read-only do pipeline HRC ponta-a-ponta (sync Discord → fim da 2ª run, secções A-K). Achado disparador: a 2ª run no watcher só dispara se `aggressor_real_action != None` (`tools/watcher_src/patched_funcs.py:1987`); mãos sem raiser (limp/walk) ou com aggressor inutilizável davam `None` → 1 run só. Correcção factual registada na investigação: a Vision do **replayer GG no Discord é OpenAI `gpt-4.1-mini`** (`routers/screenshot.py`), **não** Claude Sonnet (essa é a do #lobbys/backoffice).

Fix em `backend/app/services/queue_export.py:build_queue_zip` (1 commit `33feaad`):
- `aggressor_real_action` com **fallback unificado**: `real` (dict com position válida) / `fallback_root` (derive devolve `None`) / `fallback_unusable_position` (position `None`/`"BB"`/fora da Strategy Table). Nos 2 fallbacks → sentinela na raiz (`positions[0]`, `target_node_offset=0`); o caso `real` preserva a estrutura legacy (sem chave `source`).
- `target_node_offset` computado **sempre**; campo novo `aggressor_source` no `manifest.hands_included[*]` para auditoria.
- Skip novo `no_seats_at_table` (HH sem button / <2 seats = malformada → não vai ao robot).

Suite **573 PASSED**; smoke local validado em 4 cenários (real / fallback_root / fallback_unusable_position / no_seats). Tech debt novo: `#PARSER-SEATS-FAILURES` (🟡 MED) — cada falha do parser de seats passa a custar a **mão inteira** à biblioteca (antes só a 2ª run); robustecer `derive_seats_in_preflop_order`.

Docs desta sessão: `JOURNAL_2026-05-23-pt36.md` (novo); `TECH_DEBTS_INVENTARIO.md` (secção pt36); `PENDENTES.md`.

## pt37 — Tech debts do resolver/UX + painel HRC MVP (23 Maio 2026)

Sessão de simulação de fim-de-sessão (Discord sync + lobby sync + import HH GG + `.bat` HM3) como setup da smoke battery 1, que destapou **6 tech debts** e produziu o **painel HRC MVP**. Smoke 1 **não arrancada** (fica para pt38). 2 commits em main.

**Investigação read-only (BD produção):** 3 SSs de lobby `tm_not_found` (GG Vanilla) analisadas caso-a-caso. Causa raiz dupla do resolver — (1) **TIER 0** compara `prize_pool`/`total_players` por igualdade estrita, mas a Vision lê o lobby em tempo real (garantia anunciada + inscritos parciais) vs `tournament_summaries` pós-jogo (pool real + total final): nunca bate; (2) **TIER 1/2** janela inutilizável quando a Vision não lê `start_time` (consistente) → fallback `[posted_at−12h, posted_at−30min]` exclui o candidato (torneio começa *depois* do post). Achado extra: `tournament_summaries.start_time` vs `tournaments_meta.start_time` diferem ~2h p/ o mesmo TM (bug de timezone). Confirmou-se ainda que o `ImportModal` encaminha qualquer `.zip` para `/api/import` (TS cai no ramo P&L; UI mostra "Importado" enganador).

6 tech debts novos (`docs/TECH_DEBTS_INVENTARIO.md` secção pt37): 🔴 `#RESOLVER-TIER0-STRICT-EQUALITY`, `#RESOLVER-TIER12-WINDOW-NO-START`, `#START-TIME-TIMEZONE-INCONSISTENCY`; 🟠 `#IMPORT-MODAL-MISROUTES-TS-RESULTS` (UX); 🟡 `#LOBBYS-RETRIGGER-NOT-DISCOVERABLE` (UX); 🟢 `#DISCORD-VISION-NO-RECOVERY`. Commit docs `175f502`.

**★ Painel HRC MVP** (`e67f065`) — página `/hrc` lista as mãos **actualmente elegíveis** para a queue HRC, espelhando exactamente os gates de `GET /api/queue/hrc` (Andar 1 SQL + Andar 2 payout/raw/seats). Motivação: descobriu-se que ligar o adapter agora puxaria **~110 mãos** (não 1) — Winamax/GG PKO já marcadas — e não há forma de ver isto sem SQL. Anti-drift: selecção extraída para `backend/app/services/hrc_queue.py` (**fonte única**), consumida por `export_queue` e pelo novo `GET /api/hrc/eligible`; `classify_aggressor_source` extraído em `queue_export.py` (partilhado). Nav: **"HRC" → `/hrc`** (painel, dia-a-dia); **"HRC Sessões" → `/hrc-sessions`** (import, renomeado). 9 ficheiros (+526/−104), **193 testes verdes** + `vite build` OK.

**Acesso BD produção (validado pt37):** após `railway login` interactivo do Rui (shell separado), os comandos `railway` não-interactivos passam a funcionar; query via psycopg2 + proxy público `ballast.proxy.rlwy.net` com a password do `DATABASE_URL` do serviço `poker-app` (as vars do serviço Postgres estão **stale**). Detalhe na memória `reference_railway_cli_auth`.

Docs desta sessão: `JOURNAL_2026-05-23-pt37.md` (novo); `TECH_DEBTS_INVENTARIO.md` (secção pt37); `PENDENTES.md`.

## pt38 — Pipeline SS de mesa (24 Maio 2026)

Sessão grande. **Construído o pipeline de SS de mesa ponta-a-ponta** para dar ao HRC um `players_left` fidedigno **por mão** (alvo `#HRC-MTT-STACKS-PAGE-SKIPPED-ON-NULL-PLAYERS-LEFT`). 5 commits em main; suite **573 → 621 PASSED**.

**Descoberta empírica (`6d7a2e0`):** o HRC **auto-calcula** "Other Tables" a partir de Remaining Players ao dar OK no sub-popup MTT-Stacks (SS Rui: Remaining=313 → Other Tables Players=305). Logo `#HRC-MTT-OTHER-TABLES-INFO` é **falso positivo** (cadeia pt26 errada no 3º elo); o problema real é `players_left=None` (página saltada → Multi-Table ICM colapsa a FT dos sentados). Novo debt HIGH `#HRC-MTT-STACKS-PAGE-SKIPPED-ON-NULL-PLAYERS-LEFT`.

**Pipeline SS de mesa** (captura via Intuitive Tables → Vision → `players_left` por mão):
- **Fase A** (`61fe349`) — tabela `table_ss_processing_log` (PK `file_hash`) + coluna `hands.context_table_ss_id` (soft-FK) + `services/table_ss_vision.py` (Vision `claude-sonnet-4-6` + `derive_captured_at` TZ Europe/Lisbon→UTC) + `routers/table_ss.py` (`POST /api/table-ss/upload`, `GET /recent`, match **temporal mão→resolver-desambigua**, janela ±5 min) + integração em `_resolve_players_left` (prioridade granular antes do fallback lobby) + `hrc_queue` SELECT `context_table_ss_id`. `requirements.txt` += `tzdata`.
- **Fase B** (`859134a`) — UI `/table-ss` (nav "SS Mesa", junto a Discord/HM3): drag-and-drop multi-file + estados por ficheiro + tabela "Últimas processadas". `client.tableSs`.
- **Trigger re-link** (`b59047f`) — `relink_orphan_table_ss()` fire-and-forget no fim de `import_hm3` e `import_` (GG zip): SSs em `no_match_to_hand` ligam-se a mãos recém-importadas (peça que faltava na Fase A; espelho do padrão `hand_attachments`).
- **Fix mapeamento Vision + reset BD** (`0d0ec30`) — diagnóstico: **bug de prompt** (não de mapping). Painéis reais: Winamax `Rank: <hero_rank> / <players_left> (<itm_places>)`; GG `My Rank: <hero_rank> / <players_left>` (sem ITM). O prompt v1 ensinava a barra como *left/entrants* e não tinha `hero_rank` → `players_left` guardado **errado em 3/4 success** (ODYSSEY 71=rank, GALACTICA 7=itm, GG 813=rank; HIGHROLLER OK por coincidência). Fix: campo `hero_rank` + mapeamento explícito por site, `players_left`=sempre depois da barra, `total_entries` só se contador separado. **Reset BD** (UPDATE hands context=NULL [3] + DELETE table_ss [7] → 0+0). Smoke pós-fix: ODYSSEY `players_left=124`, HIGHROLLER `players_left=8`.

**Acesso BD prod (pt38):** `railway login` interactivo do Rui + query via psycopg2; host/porto público do serviço **Postgres** (`ballast.proxy.rlwy.net`) + password viva do `DATABASE_URL` do `poker-app`. Deploy confirmável via `railway status --json` (`latestDeployment.commitHash`/`status`).

**Notas factuais:** o **parser TS da app é GG-only**, mas o **TS Winamax existe** (ex. `BATTLE ROYALE_1098231707`, comparado campo-a-campo em pt38): TS Winamax tem blinds completos + `bountyType` explícito + total entries/prize pool/start_time, mas **sem** estrutura de prémios por posição nem `hero_prize`; TS GG tem `hero_prize_amount` mas sem blinds completos nem `bountyType`. **Nenhum substitui o lobby SS** para `tournament_payouts` (estrutura de prémios), mas ambos serviriam para identificação + dados macro (parse TS Winamax = follow-up). O pipeline SS de mesa alimenta só `players_left` (≠ `tournament_payouts`). Tech debts novos: `#TABLE-SS-RESOLVER-COLLISION` (🔴 HIGH — 2 nomes → mesmo `tournament_number`), `#TABLE-SS-VISION-CAPTURE-GAP` (🟡 MED — SS sem painel "Rank:"), `#TABLE-SS-PIPELINE-DEPENDENCIES` (🟡 MED — depende do resolver); `#TABLE-SS-PROMPT-VISION-V1-OUTDATED` ✅ FIXED (`0d0ec30`).

Docs desta sessão: `JOURNAL_2026-05-24-pt38.md` (novo); `TECH_DEBTS_INVENTARIO.md` (secção pt38); `PENDENTES.md`; `VISAO_PRODUTO.md`.

## pt39 — Bugs HIGH do resolver: 4 fixes + cleanup BD (24 Maio 2026)

Investigação read-only dos 4 debts HIGH do resolver/pipelines (queries directas à BD prod via `_local_only/pt39_probe.py`) seguida de 4 fixes shipped + 1 cleanup de dados. Suite **621 → 646 PASSED**.

**Re-rotulação (`b76cea7`):** `#START-TIME-TIMEZONE-INCONSISTENCY` → **`#META-START-TIME-IS-FIRST-HAND-NOT-SCHEDULED-START`**. **Não é bug de TZ:** o diff `tournament_summaries.start_time` (arranque agendado) vs `tournaments_meta.start_time` (`MIN(played_at)` = 1ª mão importada) é **0 quando a 1ª hand é Level1** e **cresce com níveis tardios** (late-reg / import parcial) — semântica, não relógio (um bug de TZ daria offset constante). Mantém-se HIGH, aberto.

**`#RESOLVER-TIER0-STRICT-EQUALITY` ✅ FIXED (`35286c1`):** TIER 0 passa de `prize_pool`/`total_players` estritos (Vision live vs TS final → nunca batiam) para **`buy_in` (igualdade exacta em `buy_in_total` + currency) + janela `start_time` ancorada no `posted_at`/`captured_at`** (instância em curso, `ORDER BY start_time DESC LIMIT 1`). **Reversão parcial da decisão #4:** `prize_pool`/`total_players` ficam NULL-permissivos porque o **5º consumidor do resolver — `routers/tournament_results.py` (backoffice GG, descoberto a meio)** — é pós-jogo e precisa deles. Achado **W4**: **18/101 TS GG são 2×/dia** (mesmo nome+buy_in) → só a hora desempata. Helper `_parse_buy_in_str` em `table_ss.py`; comentário órfão em `table_ss_vision.py:221` corrigido no mesmo commit.

**`#TABLE-SS-RESOLVER-COLLISION` ✅ FIXED (`36f7f7f` + `e2c6460` + cleanup BD):**
- parte 1/2 (`36f7f7f`) — `clean_tournament_name` apara o sufixo `#NNN` (nº de mesa Winamax) **só no trailing** antes de tokenizar. Achado: W SERIES `#220 - …` é prefixo **legítimo** (discriminador do evento), drop global parti-lo-ia.
- parte 2/2 (`e2c6460`) — `name_tokens_subset` valida o nome no fast-path `single_tn` de `_resolve_match` antes de aceitar. Achado: **2 colisões** em prod (não 1) — `ODYSSEY→ZENITH` (não estava flagged) além de `EXPLORER→INTERSTELLAR`.
- cleanup BD data-only (`_local_only/pt39_cleanup.py`) — script atómico auto-guardado (BEGIN → 4 UPDATEs + rowcount checks → asserts pré-COMMIT → COMMIT): `hands` 42874→SS 12 (INTERSTELLAR, players_left=129) e 42911→NULL (ZENITH); `table_ss_processing_log` id 9/13 → `no_match_to_hand` + tn NULL (re-link futuro). Sem DELETE (total mantém-se 7).

**Continuam abertos (foco pt40):** `#RESOLVER-TIER12-WINDOW-NO-START` + `#META-START-TIME-IS-FIRST-HAND-NOT-SCHEDULED-START` (cruzam-se: ambos sobre fiabilidade temporal; a re-diagnose dissolveu a antiga dependência "investigar TZ primeiro").

Docs desta sessão: `JOURNAL_2026-05-24-pt39.md` (novo); `TECH_DEBTS_INVENTARIO.md` (secção pt39); `PENDENTES.md`.

## pt40 — Track B (HRC per-mão) + guarda lobby + 2 achados críticos (24 Maio 2026)

Investigação read-only dos 2 HIGH temporais (passos 5+6 pt39) + entrega do **Track B** + 2 achados críticos. Suite **646 → 651 PASSED**. Commits: `1915571` (doc/guarda) → `dfc13a5` (Track B) + redeploy `ac26c261` (guarda).

**Re-prioridade aceite:** passo 5 (anchor/janela) **antes** do passo 6; `#META-START-TIME-IS-FIRST-HAND-NOT-SCHEDULED-START` baixado **HIGH → MED** (não-bloqueante: o TIER 0 usa o arranque do TS, não `meta.start_time`).

**🚨 Achado crítico 1 — regressão do anchor (latente):** o anchor `start_time ≤ posted_at` do TIER 0 (introduzido em pt39 `35286c1`) assume **SS durante o jogo** (verdade p/ table-ss), mas os **lobby SS são tirados na inscrição** (torneio começa ~30min **depois** do post). Simulação dos 3 lobby `tm_not_found` pt37: 1 resolve certo, 1 fica `tm_not_found`, **1 mis-resolve para o dia anterior** (escreveria `tournament_payouts` errado). `M1=0` (latente, sem corrupção ainda) mas **blast radius ~24** `tm_not_found` acumulados disparam na próxima actividade de lobby. Novo debt `#LOBBY-ANCHOR-PRESTART-REGRESSION` (🔴 HIGH, `1915571`).

**🛡️ Guarda activa:** `DISCORD_LOBBY_AUTO` estava **`true`** em prod → mudado para **`false`** + redeploy `ac26c261` SUCCESS (handler real-time do `#lobbys` desligado). **Não reverter** (nem correr sync de lobby, nem re-disparar) até o Track A. Reverter para `true` só após Track A + re-disparo OK.

**Track B ✅ `#HRC-PER-HAND-DOWNLOAD` (`dfc13a5`):** botão "⬇ HRC" no painel `/hrc` → `GET /api/queue/hrc/hand/{hand_id}` gera zip per-mão (`hh.txt` + `payouts.json` + manifest) com guards 404/409/422; `has_payout` no `/eligible` controla a visibilidade. Alívio operacional real (Rui usa daqui em diante para o workflow manual).

**🚨 Achado crítico 2 — bounties errados no converter GG→PS** (descoberto pelo Rui ao testar o Track B): `_HERO_BOUNTY_DEFAULT_USD = 250.0` (`queue_export.py:488`, = bounty do **$525** Big Game) aplicado a **todos** os torneios → Hero `€max(Vision,250)`; ex.: Big Game **$215** (bounty real $100) → `€250` (moeda E magnitude erradas). Pior que documentado: **vanilla GG também** (sem gate de formato), **vilões sempre a €0**, afecta **batch + per-mão**. **NÃO é regressão pt40** (vive desde FASE-1/pt28). Moeda `€` é intencional (HRC rejeita `$`). Debt `#HERO-BOUNTY-FROM-TS-DERIVATION` subido a **🔴 HIGH 🚨** — fix desbloqueado (TS tem `buy_in_bounty` por tn). **Foco pt41.**

Docs desta sessão: `JOURNAL_2026-05-24-pt40.md` (novo); `TECH_DEBTS_INVENTARIO.md` (secção pt40); `PENDENTES.md`.

## pt41 — 2 fixes HIGH: bounty base via TS + anchor lobby pré-start (25-26 Maio 2026)

2 fixes HIGH shipped + re-disparo lobby validado + reversão da guarda. Suite **651 → 661 → 666 PASSED**. SHAs: `a942ac7` (bounty) → `0707978` (docs betting) → `6409b19` (anchor) → redeploy reversão guarda (mesmo commit, env-var only).

**✅ `#HERO-BOUNTY-FROM-TS-DERIVATION` (`a942ac7`):** bounty base vem de `tournament_summaries.buy_in_bounty` (Hero `max(Vision, base)`, vilões `base`, `€` mantido — o Rui revalidou hoje que o HRC aceita `€` em GG). Hardcode `_HERO_BOUNTY_DEFAULT_USD=250` **removido**. Gate Andar 1 **GG-only**: PKO/SuperKO/KO exigem TS com bounty; **Mystery KO excluído** do /hrc; vanilla sem token (Opção A); Winamax/PS passthrough. `lookup_bounties` + `bounty_by_key` em `build_queue_zip`; defensiva 422 `pko_without_ts_bounty`; manifest audit; `GET /api/hrc/pending-ts` + banner D1. Smoke real do Rui: Hyper Special $108 → bounty €50 correcto + árvore ~23k nós.

**✅ `#LOBBY-ANCHOR-PRESTART-REGRESSION` + `#RESOLVER-TIER12-WINDOW-NO-START` (`6409b19`):** resolver **source-aware** (`anchor_mode='during_play'`|`'prestart'`; `lobby_sync` passa `prestart`, `table_ss`/`tournament_results` no default). TIER 0 (`_query_summaries`): selecção **closest** (`ORDER BY abs`) + janela por modo (prestart `[anchor−12h, anchor+2h]`; during_play `[anchor−24h, anchor]` inalterado). TIER 1/2 (`_decide_window`): ramo-1 forward **2h→4h**, ramo-2 source-aware (prestart forward). 🟢 **Validação empírica:** msg 05-09 13:38 — o código antigo teria **mis-resolvido para o TS do dia anterior (05-08)**; o novo rejeita → `tm_not_found` honesto. Mis-resolve silencioso → erro honesto. **Re-frame:** o anchor pré-start no TIER 1/2 tinha impacto ~nulo (as Winamax têm `start_time_iso` → ramo-1, desbloqueiam-se com **re-run**, não com o anchor); o valor real do TIER 1/2 foi o **forward +4h do ramo-1**.

**Re-disparo lobby** (real run, painel `/discord`, janela 30d): 12 candidatos, **7 resolveram, 5 falharam** — todas (a) **falta de TS** (`Daily Hyper $80` 05-09 sem TS importado). **Guarda reposta:** `DISCORD_LOBBY_AUTO=true` (redeploy SUCCESS) — real-time do `#lobbys` activo com o anchor `prestart`.

**Tech debts abertos pt41:** 🔴 `#HRC-BETTING-SCRIPT-IMPROVEMENTS` (`0707978`, foco pt42 — variante pré-flop+flop only + alternativas do Hero, regra-base stack eff > 8BB no open → sempre mini-raise 2BB); 🟡 `#MYSTERY-KO-DUAL-SUPPORT` (`a942ac7`); 🟡 `#LOBBY-SYNC-PAGINATION-LIMIT` (`gather_candidates` sem paginação; discord.py `limit=100` corta janelas largas — o Rui confirmou que NÃO apaga mensagens, é limitação técnica).

Docs desta sessão: `JOURNAL_2026-05-25-pt41.md` (novo); `TECH_DEBTS_INVENTARIO.md` (secção pt41); `PENDENTES.md`.

## pt42 — `#HRC-BETTING-SCRIPT-IMPROVEMENTS` ✅ (26 Maio 2026, diffs em buffer)

**Backend-only; `.exe` do watcher não tocado.** Fecha `#HRC-BETTING-SCRIPT-IMPROVEMENTS`
(🔴 HIGH) combinando 2 pedidos product no mesmo trabalho. Suite **666 → 685 PASSED**
(-16 testes pt25f obsoletos, +35 novos pt42). Diffs em buffer (sem commit/push/smoke real
Beelink ainda — pendente validação Web + smoke pt43).

### Pedido 1 — variante "pré-flop + flop only" no template

`backend/app/services/hrc_scripts/mtt_advanced_canonical_2026.js` —
`POSTFLOP_FORCE_CHECKDOWN_AFTER` passa de `{2:RIVER, 3:RIVER, 4:TURN, 5:FLOP}` para
`{2:FLOP, 3:FLOP, ..., 9:FLOP}`. Turn/river ficam sem betting modelado (só check) para
todos os live counts → árvore HRC corta turn/river. `hasNextStreetBetting` (callback que
o HRC consome) devolve agora `false` em qualquer street pós-flop.

### Pedido 2 — regra universal de sizings + efectiva dinâmica

`backend/app/services/hrc_script_gen.py` reescrito. Cada raise preflop (open / 3-bet
clássico / squeeze / 4-bet / 5-bet) recebe um array com a forma:

- **1ª opção** = `to_amount_bb` da HH (ou `"ALLIN"` se a acção foi all-in, detectada via
  heurística 95% reusada de `hrc_node_offset._ALL_IN_EFFECTIVE_THRESHOLD`).
- **2ª opção** depende:
  - Original NÃO ALLIN + `effective_stack_at_action_bb <= 25` → `"ALLIN"`.
  - Original NÃO ALLIN + eff > 25 (ou None) → sem 2ª opção.
  - Original ALLIN + non-all-in default existe → o default por tipo.
  - Original ALLIN + default None → sem 2ª opção (`["ALLIN"]` só).

**Non-all-in defaults (só quando original=ALLIN):** Open 2 BB (se `eff > 8` e pos ≠ SB/BB;
HU "BU/SB" passa); 3-bet clássico 2.3/2.7/3.0 × `opener_to_bb` por bucket `<26`/`[26,35)`/`>=35`;
squeeze 3.0 × opener; 4-bet 2.3 × `previous_raise_to_bb`; 5-bet 2.2 × `previous_raise_to_bb`.

**Efectiva dinâmica por raise** (substitui `compute_effective_stack_bb` global como
referência para regras product): `min(raiser_remaining, max(active_opponents_remaining)) / BB`,
recalculada por acção. Activeness é set actualizado nos `folds`. Para 4-bet/5-bet o template
continua a usar `SIZES_POT_*BET_*` em pot-fraction; a conversão BB→fração vive no gerador
(`_array_for_4bet5bet_in_pot_fraction`).

### Implicação: pt25f abandonada

Os helpers `_classic_3bet_band`, `_compute_classic_3bet_overrides` e `_CLASSIC_3BET_DEFAULTS`
(extensão pt25f, 5 buckets de multiplicador que **ignoravam** o sizing real da HH) foram
**removidos**. A regra nova traz o sizing real de volta como 1ª opção em todas as raises.

### Parser ganha 4 campos novos por acção

`_parse_preflop_actions` em `hrc_script_gen.py` passa a expor:
- `previous_raise_to_bb` (BB do raise imediatamente anterior; None para opens)
- `opener_to_bb` (BB do open original; None para opens — auto-ref)
- `is_all_in` (bool, threshold 95% inclusivo)
- `effective_stack_at_action_bb` (efectiva dinâmica)

### Tech debt latente novo (descoberto pt42, não-regressão)

🟢 `#OPEN-COUNT-DRIFT-HRC-NODE-OFFSET-LATENT` (LOW) — `_TEMPLATE_DEFAULT_OPEN_COUNT = 2`
em `services/hrc_node_offset.py:52` desalinha do template default actual `[2]` (1 entrada,
pt29). Quando o gerador não overrida uma posição (não fez raise voluntário na HH), o
`target_node_offset` pode ficar +1 por posição precedente. Vive desde pt29; só elevar se o
smoke real pt43 mostrar navegação errada.

Detalhe completo em `docs/JOURNAL_2026-05-26-pt42.md`, `docs/TECH_DEBTS_INVENTARIO.md`
(secção pt42), `docs/HRC_ANATOMIA_OPERACIONAL.md` §3.4.

## pt42b — Re-abertura `#HRC-BETTING-SCRIPT-IMPROVEMENTS` (27 Maio 2026)

**Backend-only; `.exe` do watcher não tocado.** Re-abertura do mesmo tech
debt fechado em pt42, com pedido novo do Rui: cada posição candidata a
3-bet deve ter o seu próprio sizing baseado na efectiva spot-específica
entre essa posição e o opener (em vez do array único `SIZES_3BET_IP`).
Suite **705 → 713 PASSED** (+28 testes pt42b líquidos; 0 removidos).

**Regra:** para 3-bet clássico IP (exclui SB/BB/squeeze):

- **CASO A** (posição fez 3-bet na HH): 1ª = sizing original; 2ª = ALLIN
  se eff spot ≤ 25.
- **CASO B** (posição NÃO fez 3-bet — gera sempre): bucket por eff spot
  (2.3 / 2.7 / 3.0 × opener_to_bb consoante eff <26 / [26,35) / ≥35);
  + ALLIN se eff ≤ 25.

**Eff spot-específica** = `min(opener_remaining, candidate_remaining) / BB`
no snapshot pós-open (calculada no Python). Cada candidato (EP/MP/HJ/CO/BU
em IP) tem o seu array. CASO B gera primeiro; CASO A sobrescreve a entrada
do 3-bettor real.

**Template canónico** ganha 5 variáveis (`SIZES_3BET_EP/MP/HJ/CO/BU`) +
const `POSITION_LABELS_BY_N` (mirror Python) + helpers
`positionLabelForIdx` + `getSizings3BetByPositionIP`. SB/BB/Squeeze/Opens
intocados.

**Implementação T1-T6:** helpers no gerador + refactor `_bucket_3bet` +
refactor `build_sizings_overrides` (CASO B antes do loop, CASO A no loop) +
template JS dispatch por posição + 8 testes novos + 28 modificações em
testes existentes. Edge case validado: open-jam → `opener_to_bb` é o
jam-to-bb (não 2 BB), bucket low devolve `2.3 × jam_bb`.

**Tech debt novo (LOW):** `#POSITION-LABELS-PYTHON-JS-DRIFT` — tabela de
posições duplicada Python/JS sem single-source-of-truth cross-language.
Doc no comment do template alerta para manter em sync.

Detalhe completo em `docs/JOURNAL_2026-05-27-pt42b.md`,
`docs/TECH_DEBTS_INVENTARIO.md` (secção pt42b),
`docs/HRC_ANATOMIA_OPERACIONAL.md` §3.4.2.1.

## pt42c — `#WN-BOUNTY-NULL-IN-HRC-PIPELINE` (27 Maio 2026)

**Backend-only; `.exe` do watcher não tocado.** Tech debt novo aberto
e fechado na mesma sessão após smoke pt42b expor bounty null em mão WN
PKO. **1232 mãos PKO 2026 Winamax** (em 179 torneios) tinham bounty null
no pipeline HRC.

**Causa raiz (3 falhas):** (1) lobby vision não classifica nomes WN
como bounty (`apply_ratio_lookup` só reconhece nomes branded GG/PS);
(2) TS pipeline é GG-only; (3) `convert_gg_hh_to_pokerstars_compatible`
fazia passthrough total para non-GG.

**Opção C escolhida pelo Web/Rui:** estender gerador para converter HH
WN → PS-compat com bounty inline (sem dependency de TS Winamax). HH
Winamax já tem `(<X>€ bounty)` literal por Seat.

**Pipeline novo (`queue_export.py`):**

1. `_extract_winamax_seat_bounties(hh)` parsea `{nick: bounty_eur}`.
2. `_inject_bounties_winamax_to_ps_format(text, players_list, anon_map)`
   reescreve Seat lines: `(<chips>, <X>€ bounty)` → `(<chips> in chips,
   €<X> bounty)`.
3. `compute_hero_bounty_from_hh` espelho do `compute_hero_bounty` pt41
   GG; source enum `"hh"` (Vision ganha se > HH, regra pt41 mantida).
4. `_patch_winamax_payouts_bountytype` sobrescreve `bountyType="PKO"` +
   `progressiveFactor=0.5` no zip (BD não tocada — audit trail).
5. `build_queue_zip` orquestra; `converted_format="pokerstars_compat"`
   no manifest.

**Branch novo em `convert_gg_hh_to_pokerstars_compatible`** (nome
mantido por decisão Web): se `site == "Winamax"` AND `fmt in
WINAMAX_BOUNTY_FORMATS` (`pko`, `super ko`, `ko`), aplica pipeline pt42c.
Outros sites/formatos: passthrough actual.

Suite **725 → 730 PASSED** (+15 testes pt42c líquidos; 0 removidos).
Smoke real Beelink fica para pt42d.

**Tech debt novo (HIGH 🚨 → ✅ FIXED na mesma sessão):**
`#WN-BOUNTY-NULL-IN-HRC-PIPELINE`. Mystery KO WN continua excluído
(gated em `MYSTERY_FORMATS` desde pt41).

**Decisões product:** Hero bounty Vision ainda tem prioridade (Vision
de WN é raríssima — replayer Discord é GG-only); vilões usam HH literal
(pós-KO accumulator real); progressive factor 0.5 hardcoded (Rui
confirma WN PKO 50% universal); patch só no zip, BD intacta.

Detalhe completo em `docs/JOURNAL_2026-05-27-pt42c.md`,
`docs/TECH_DEBTS_INVENTARIO.md` (secção pt42c),
`docs/HRC_ANATOMIA_OPERACIONAL.md` §12.10.

## pt42d — `#WN-BOUNTY-NULL-IN-HRC-PIPELINE` v2 (28 Maio 2026)

**Backend + watcher recompilado + adapter.** Re-abertura pt42c após smoke
real expor que o HRC continuava em ICM puro (Instant=0%) apesar do
`bountyType="PKO"` correcto no payouts.json. Investigação profunda da
biblioteca persistente HRC revelou causa raiz dupla.

**Causa raiz definitiva:**

1. **4 hints top-level no `payouts.json`** (`equity_model`, `max_players`,
   `script_path`, `aggressor_real_action`) — HRC rejeita campos extra e
   guarda a structure na biblioteca `custom.json` sem `bountyType`. Em
   re-imports, fica órfã → ICM puro.
2. **`structures[i].name` sem sufixo `#<tournament_number>`** — colisão
   na biblioteca HRC com structures de outros torneios com o mesmo nome
   ("GRAVITY", "INTERSTELLAR").
3. **Seat lines conversion WN→PS de pt42c v1** era desnecessária — HRC
   lê formato WN nativo.

**Arquitectura final (3 elementos):**

1. **HH WN passthrough** — `convert_gg_hh_to_pokerstars_compatible`
   simplificado (branch WN PKO removido).
2. **`payouts.json` no zip = APENAS `{name, folders, structures}`** — sem
   hints top-level. Patch via `_patch_winamax_payouts_bountytype` com
   `tournament_number=tnum` → name = `"<Name>  #<tn>"` (2 espaços + #ID).
3. **Hints em `meta.json`** — 4 campos migrados do payouts.json:
   `equity_model`, `max_players`, `script_path`, `aggressor_real_action`.
   Watcher (`patched_funcs.py:setup_hand`) lê de `hand_meta.get(...)`.

**Path B (Web/Rui)** — backend + watcher source + adapter recompilados
na mesma sessão para evitar degradação do robot.

**Suite 730 → 734 PASSED.** 15 alterações líquidas (T1 +5, T2 −3, T3 +2,
T4+T5 9 modificados + 1 novo, T2 1 renomeado/invertido).

**Watcher recompilado:** `.exe` SHA `cdfc7247...3262` (pt35 era
`33eae43a...c53c4f`). Adapter Python puro: `rewrite_script_path_in_meta`
substitui `rewrite_script_path_in_payouts`.

**Tech debt novo:** `#SMOKE-HARNESS-WAIT-FOR-FINISH-MOCK-MISSING` (LOW) —
swap_and_smoke.py harness in-process bate em sub-test pre-existente
(mock Win32 ausente desde pt30); não-bloqueante.

**Decisões product:** prizes/chips passam como vêm do parsing (HRC aceita
números brutos; sem helpers de formato); `_extract_winamax_seat_bounties`
+ `compute_hero_bounty_from_hh` mantidos para audit no manifest;
patch só no zip, BD intacta.

Detalhe completo em `docs/JOURNAL_2026-05-28-pt42d.md`,
`docs/TECH_DEBTS_INVENTARIO.md` (secção pt42d),
`docs/HRC_ANATOMIA_OPERACIONAL.md` §12.10 (reescrita).

## pt43 — Onda 1 de tech debts: 8 fechados + 1 adiado (29 Maio 2026)

6 commits atómicos em main; suite **734 → 774 PASSED** (+40; `ire.py` ganhou
cobertura directa 0 → 30). Protocolo apertado (diff-em-buffer → validação Web →
aplicar → suite) por cada mudança.

| Commit | Tech debts |
|---|---|
| `942ec08` | **#IRE-MB** — constante do bounty derivada por torneio (`KOP_fraction × instant_fraction`), já não fixa em 0.25. `ire.py` parametrizado + `derive_kop_fraction`/`derive_constant`; `hands.py` faz LEFT JOIN a `tournament_summaries` (`buy_in_entry`/`buy_in_bounty`). Banda ±0.01 mantém PKO standard na tabela W3cray; Big Bounty (0.35) usa fórmula. Guarda PKO-only (Mystery 0.25 legacy). Super KO escondido. Ramo PS construído mas dormante (gate GG). |
| `6a1aa14` | **#AUTH-SCHEME** (docs, zero refs X-API-Key), **#PYDANTIC-V1** (`@validator`→`@field_validator` em `lobbys.py`), **F-cleanup** (remove instrumentação `[debug-msg-lobby]` em `discord_bot.py`). |
| `008342e` | **#DISCORD-VISION-NO-RECOVERY** — step 4b de `sync_and_process` alargado de `vision_done IS NULL` para `IS DISTINCT FROM 'true'` (SQL em constante `_RECOVERY_REPLAYER_SQL`). Defensivo: zero entries presas hoje (quantificado). |
| `16faa1e` | **#5 SERVER-FILTER-HRC-STATUS** (`select_andar1_rows` exclui `hrc_jobs.status='done'` via NOT EXISTS — afecta adapter GET e painel /hrc), **#7 SYNC-RECENT-RESPECT-MANUAL** (precedência D11 enforced em `lobby_sync.process_lobby_message`), **#2 TS-RATIO-MYSTERY-CONFIRM** (adiado → #MYSTERY-KO-DUAL-SUPPORT). |
| `d074634` | **#VISION-LOBBY-API-FAILURE** — fechado por reclassificação empírica. Premissa "~34% silent failures" stale: `lobby_processing_log` (131 tentativas) tem **0 vision_failed**; 50% `tm_not_found` é fase resolver (não Vision). Observabilidade pedida já existia. |
| `2794aab` | **#TAGS-DISCORD-HM3-FRAGMENTATION** — fix proporcional: alias `nota++`→`nota` + backfill 273 mãos + `tag_family_key` (`nota`/`nota ex` no grouping do Estudo) + reclassificação. Tabela canónica `#TAGS-CANONICAL` **decidida contra** (ROI desproporcional p/ ~30 literais com 6 já unificados por `normalize_tag_key`). |

**Info técnica Mystery KO (Rui):** não-progressivo, `instant_fraction=1.0`, bounties
ligam só no ITM (raramente no fecho do late reg), valor por sorteio. Reforça que o
suporte Mystery (incl. IRE Mystery via EV do pool) pertence a #MYSTERY-KO-DUAL-SUPPORT,
não ao #IRE-MB (daí a guarda PKO-only).

## pt46 — KO crown fix + imagem replayer + IRE Winamax (1 Junho 2026)

3 fixes shipped em commits isolados; suite **774 → 809 PASSED**. BD de produção
queryada read-only via proxy público (`ballast.proxy.rlwy.net`, padrão pt37+).

| Commit | O quê |
|---|---|
| `24e1898` | **#KO-CROWN-INSTANT-FIX** — a coroa lida pela Vision (`bounty_value_usd`) é a parte INSTANTÂNEA do bounty (metade no PKO 50/50), não o total. Era usada como total em 2 sítios → tudo a metade (HRC KO-T$ e IRE ko_units). Fix: recuperar total = coroa ÷ instant_fraction (×2), gated a PKO 50/50. HRC (`queue_export._crown_to_total_factor` + `crown_factor` threaded por `_vision_bounties_by_name`/`compute_hero_bounty`/`_inject_bounties_ps_format`) e IRE (`ko_units = bounty/(bib×ko_units_instant)`, instant=0.5 PKO). Super KO/KO/Mystery/Winamax intocados; Hero fresco fica $20; fallback `starting_bounty` não escala. |
| `4eef6b5` | **#REPLAYER-IMG-HH-FIRST** — mãos GG em Estudo deixaram de mostrar a imagem captada no caminho **HH-primeiro** (HH importada antes do replayer Discord sincronizar): o enrich (`_enrich_hand_from_orphan_entry`) liga o entry replayer e mete nomes mas não propaga a imagem (`screenshot_url` NULL; `entry_type='replayer_link'` que `has_screenshot_image` — só `'screenshot'` — rejeitava). Fix read-path (Opção B, **sem backfill**): `has_screenshot_image` (`hands.py:715,1331`) aceita `replayer_link` com `img_b64`; `GET /api/screenshots/image/{id}` serve `IN ('screenshot','replayer_link')`. 313 mãos repostas no deploy. |
| `e71e22a` | docs — secção pt46 do `TECH_DEBTS_INVENTARIO.md` (**#IMPORT-MODAL-UX** investigação + **#REPLAYER-IMG-HH-FIRST** + latente **#CDN-URL-EXPIRY-OLD-REPLAYER-SS**). |
| `64958f9` | **#IRE-WN** — estende o IRE à Winamax (ver abaixo). |

### #IRE-WN — IRE Winamax (`64958f9`)

O IRE era GG-only. Estende-se à WN mantendo a **GG 100% inalterada nos gates**
(núcleo partilhado novo `_assemble_ire` em `ire.py`; dispatch por site em
`compute_ire`). Mecânica WN: gate = site WN + `tournament_format` PKO +
`tournament_name` na tabela curada `app/services/winamax_ire_tournaments.py`
(10 torneios; interna, sem UI, à la `hero_names.py`); **sem** `match_method`
nem tag (WN tem nicks reais); `starting_stack/entry/bounty` da tabela; bounty
por jogador = literal da HH (`_extract_winamax_seat_bounties`, reuso read-only
do `queue_export`), que é o **TOTAL na cabeça** → `ko_units = bounty/bib`
(`ko_units_instant=1.0`, **sem** o ×2 da coroa GG); `constant =
(bounty/(entry+bounty))×0.5` (~0.278 nos 50/100, ~0.269 nos 250). A lista
(`hands.py`) injecta `h.raw` só p/ mãos WN da página; detalhe (`SELECT h.*`) e
frontend (badge site-agnóstico) intocados. Scope prod 2026: **~1116 mãos** WN PKO
em 9 torneios curados acendem o IRE. +9 testes WN.

**⚠️ Nota 1 — cobertura limitada à tabela:** **335 mãos WN PKO 2026 ficam fora
da tabela curada** (torneios não listados) → **IRE None** (escondido, não
errado). Extensível: acrescentar o torneio a `WINAMAX_IRE_TOURNAMENTS` com
`{starting_stack, buy_in_entry, buy_in_bounty}`.

**⚠️ Nota 2 — escala WN não comparável à GG:** o IRE-WN usa **sempre o
`_formula_fallback`** (constant ~0.278/0.269 cai fora da banda 0.25 da W3cray),
**não** a tabela W3cray calibrada. Por isso a escala WN sai um pouco **mais
alta** e **não é directamente comparável** ao IRE GG (que no PKO standard usa a
tabela). É intencional — não alinhar os dois sem recalibração empírica.

## pt47 — Reset total da BD + reimport + 3 fixes (2 Junho 2026)

Reset total dos dados (backup restore-verificado em `_local_only/reset_pt47/`,
`TRUNCATE … RESTART IDENTITY CASCADE`; preservados `users`/`stat_ideals`/`monthly_stats`;
DB 474 MB → 10 MB) + reimport por cima + investigação read-only da re-ingestão (ordem,
Discord sem-match, HM3 295→265, 30/05 fora da janela, gap de vilões). 4 commits em main:

| Hash | O quê |
|---|---|
| `eb839e0` | #HRC-BASKET-SPEED-RACER — Speed Racer no basket de elegibilidade HRC (`DEFAULT_TAGS` ganha `speed-racer`+`speed-racer-ft`; match exacto normalizado exige as 2 formas). |
| `10d7229` | #DUP-REPLAYER-COUNT (contador) — "Discord sem match" conta por mão (`is_matched` via `entry_id` **ou** `hand_id=GG-{tm}`), não por entry; 17→0. |
| `42dc4e8` | #VILLAIN-MISSED-ON-ENRICH-GUARD — o guard de idempotência do enrich (`screenshot.py`) saltava o append da tag do canal **e** `apply_villain_rules`; passa a fazer ambos antes do `return` → self-healing nos re-imports. |
| `56025af` | #DUP-REPLAYER-COUNT (lista) — `/ss-without-match` alinhada com o contador + dedupe por TM (`DISTINCT ON (COALESCE(tm,'e'||entry_id))`; sem-TM não colapsam). |

Suite **não corrida** nesta sessão (fixes validados read-only contra prod); o `eb839e0`
partiu 2 testes stale, fechados na pt48. Recuperação manual de dados (sem commit): 5 tags
de 2º canal + 3 TMs (Vision falhara) + 7 vilões do 30/05. Detalhe em `docs/JOURNAL_2026-06-02-pt47.md`.

## pt48 — Reenquadramento docs + editor de tags via portal + IRE-WN por preço (2 Junho 2026)

Sequência da pt47 (mesmo dia). 4 commits em main; suite `test_ire` 53 / completa **818 PASSED** (verde):

| Hash | O quê |
|---|---|
| `ebd8e5e` | docs — `## Propósito` (VISAO_PRODUTO) + `## Modelo de domínio` (CLAUDE) reposicionados à volta da **centralização do estudo**; o cruzamento SS↔HH GG passa a ser mecanismo (específico da GG), não a razão de ser. |
| `32d6746` | #TAGEDITOR-PORTAL (frontend) — popover de tags via React portal no `<body>` (`position:fixed` por `getBoundingClientRect`) → deixa de ser cortado pelo `overflow:hidden` dos cartões de grupo na Estudo. Capacidades e os 3 outros usos intactos. |
| `87f3c67` | #IRE-WN-BY-PRICE — IRE Winamax casa por **preço (`buy_in`)**, não por nome. `winamax_ire_tournaments.py` vira mapa por preço `{50,100,125,250}`→split (stack 20000); `_compute_ire_winamax` faz lookup por `hand.buy_in`. `buy_in` 100% fiável na WN (219 mãos 2026, 0 NULL). Efeito: todos os WN PKO 2026 acendem o IRE, retroactivo, sem manutenção de nomes. Override por nome não implementado (registado p/ 1ª excepção). |
| `dec944f` | test — `test_queue_default_tags` 6→8 keys (stale do basket Speed Racer da pt47, não do IRE-WN). |

Confirmado read-only: `56025af` em `origin/main`; dedupe `/ss-without-match` não colapsa
entries sem TM (`COALESCE`, provado por simulação). Achado: proveniência de
`hands.tournament_name` por sala — GG nome real da HH · WN nome entre aspas · WPN string
de garantia (sem nome real) · PS NULL de propósito. Detalhe em `docs/JOURNAL_2026-06-02-pt48.md`.

## pt49 — table-SS site-misclass + descoberta e fix do bug de fuso GG/PS (2–3 Junho 2026)

> ⚠️ **A rota de fuso desta secção (`#GG-PLAYED-AT-LOCAL-NOT-UTC`, GG+PS → UTC) está SUPERSEDED pela convenção Lisboa-naive (pt51) — ver secção pt50–pt58. A "validação de Inverno" dissolveu-se (já não convertemos GG/PS; gravam verbatim em Lisboa).** O resto da secção fica como registo histórico.

Sessão longa (seguiu de pt47/pt48 no mesmo dia). 5 commits em main; suite
**818 → 840 PASSED**. Journal completo: `docs/JOURNAL_2026-06-02-pt49.md`.

| Hash | O quê |
|---|---|
| `feefacd` | docs — reconciliação de backlog contra o repo real: fechados (já-feitos) `#B12` (pt47), `#RESOLVER-TIER0-STRICT-EQUALITY` (pt39), `#RESOLVER-TIER12-WINDOW-NO-START` (pt41), `#IMPORT-MODAL-MISROUTES-TS-RESULTS` (pt43), `#B9` (Bucket 1). Abertos genuínos: itens 2/20/23 + `#META-START-TIME-IS-FIRST-HAND-NOT-SCHEDULED-START`. |
| `ef82a0d` | **#TABLE-SS-VISION-SITE-MISCLASS** ✅ — `_correct_site(name, read_site)` pós-parse no upload (`table_ss_vision.py` + `routers/table_ss.py`): Regra A (`#NNN` trailing → Winamax, 0 falsos positivos) + Regra B (cross-check BD, exactamente-1). +8 testes. |
| `41d83d3` | #TABLE-SS-VISION-SITE-MISCLASS — **relink self-healing**: `relink_orphan_table_ss` re-aplica `_correct_site` às rows `no_match_to_hand` e persiste a site corrigida (`_persist_corrected_site_table_ss`, guard). +3 testes. |
| `eb6b447` | **#GG-PLAYED-AT-LOCAL-NOT-UTC** aberto + validação read-only do fuso. |
| `e902d52` | **#GG-PLAYED-AT-LOCAL-NOT-UTC** ✅ — `played_at` GG **e PokerStars** normalizado para UTC **DST-aware** (helper `lisbon_local_to_utc` em `app/utils/timezones.py`); UI mostra Lisboa (`frontend/src/utils/datetime.js`). Winamax/WPN gravam **UTC nativo** → intocados. +11 testes. **Sem backfill.** |

**★ Descoberta central:** o `played_at` da GG (e da PS) era gravado em **hora local de Lisboa, sem normalizar para UTC** (HH GG sem marcador de fuso; PS com a 1ª timestamp em WET/Lisboa, bracket em ET). No Verão fica +1h → só o **table-SS** (casa por tempo) estava exposto: no-match (torneio curto) ou **match FALSO ~1h antes** (torneio longo, provado por blinds na mão `id=14`). O offset **+1h** foi validado **independente da localização** (o Rui joga sempre de Portugal / hora de Lisboa). O pipeline principal GG (casa por **TM number**) é imune. Verificação à parte: Winamax/WPN gravam **UTC explícito** (sem bug); PokerStars tinha o **bug idêntico**, corrigido na mesma mudança.

**⚠️ Pendente de validação (não bloqueia):** confirmar o **Inverno** (DST-aware vs constante +1h) — cruzar nas mãos **PS** a hora **Lisboa↔ET** (a HH PS traz as duas) no re-import. **Próximo grande passo operacional: RE-IMPORT end-to-end** com os dados já certos (GG+PS em UTC).

## pt50–pt58 — re-import end-to-end + fuso Lisboa + Vision Claude + import por pasta (3–4 Junho 2026)

Arco longo e contínuo (14 commits `81255b2`…`eddca4d`, todos em main e deployed). Suite **840 → 876 PASSED**. Journal completo: `docs/JOURNAL_2026-06-04-pt50-pt58.md`. As operações em produção (backup, TRUNCATE, re-imports, backfills, `OPENAI_API_KEY` removida) **não deixam commit** — ver §B do journal.

**3 factos de estado que substituem comportamento antigo (LER):**

1. **Fuso = LISBOA naive (pt51, `4645960`) — substitui a rota UTC da pt49.** Toda a hora-de-evento (`played_at`, `discord_posted_at`, `start_time`, `captured_at`) passa a **hora de Lisboa wall-clock**, guardada `timestamp` **naive** (sem tz). **GG/PS gravam verbatim** (a string da HH já é Lisboa — zero matemática DST); **Winamax/WPN/Discord convertem UTC→Lisboa uma vez** (`utc_to_lisbon_naive`). Helpers em `backend/app/utils/timezones.py` (`lisbon_naive_verbatim`, `utc_to_lisbon_naive`). Frontend `datetime.js`: ISO sem offset = Lisboa naive (mostra directo); ISO com offset (`created_at` UTC) = converte. **A "validação de Inverno" da rota UTC dissolveu-se** — já não convertemos GG/PS, gravamos a wall-clock tal-e-qual. *Porquê: o Rui joga sempre de Portugal; guardar Lisboa-naive mata a ambiguidade DST na origem.*

2. **Vision = Claude-only (pt53, `343e30f`).** Todo o pipeline Vision corre `claude-sonnet-4-6`. A Vision do replayer GG era OpenAI `gpt-4.1-mini` → migrada para Claude. Função OpenAI removida, dep `openai` fora do `requirements.txt`, `OPENAI_API_KEY` removida do Railway. Endpoint novo `POST /api/discord/revision-replayers` re-corre a Vision sobre replayer entries com `img_b64` e `vision_done != 'true'` (o worker normal só apanha `img_b64 IS NULL`).

3. **Site do table-SS = nome do ficheiro (pt56, `45aa12a`), NÃO a Vision.** `_site_from_filename` lê o token `<Site>` de `Shot<N>-<Site>-<YYYYMMDDHHMMSS>` (`_FILENAME_SITE_MAP`), **autoritativo sobre a Vision**. ⚠️ **Não voltar ao caminho Vision para site:** o Rui **muda o feltro por torneio/fase, não por sala** → o feltro não é sinal de site; e as imagens do table-SS **não são guardadas** (descartadas após a Vision), logo um prompt Vision multi-site (V2) não é validável sem re-fornecer o ficheiro. V2 **descartado** por isso.

**Outras peças do arco:** match do table-SS desacoplado do upload numa função R determinística (`compute_table_ss_match`/`reconcile_table_ss`/`POST /api/table-ss/reconcile`, pt50 `6578f63`); nome canónico Winamax (`clean_winamax_tournament_name`, pt54); desambiguação directa do table-SS pelo nome (pt54 `901e965`); tolerância a truncação do título GG (`name_tokens_subset`, pt58); **`tools/appimport`** — import por pasta local GG HH/TS + IT + SS manual (pt55) + **2ª via de lobby pela pasta de Capturas** (`POST /api/lobbys/upload`, pt57) com `LOBBY_SINCE` + retry de falha transitória (pt57b). Fase 3 (Discord 30/Mai+) verificada read-only: enriquecimento **limpo** (76/76 match_method real, discord_tags propagadas, 24 vilões Regra C, posted_at Lisboa naive).

## pt59 — Lobbys (página + reconcile + fallback de sala), appmaster, coroa GG, balanços (4–5 Junho 2026)

13 commits em main (`554f7b3`…`16a435b`), todos deployed. Suite **876 → 886 PASSED**. Journal: `docs/JOURNAL_2026-06-05-pt59.md`. As operações em produção (2 wipes backup-verificados, crown backfill, reconcile) **não deixam commit** — ver §PROCESSO do journal.

**Mudanças de fluxo/pipeline (LER):**

1. **Contador do banner Discord = recompute no refresh (`554f7b3`).** O "K match HH" era uma foto tirada antes da Vision em background acabar (mostrava 3 quando o real era 22). Agora a UI chama `GET /api/discord/sync-counters?since=<sync_started_at>` no refresh; predicado canónico `match_method` (não mais `raw`). Helper partilhado `_compute_sync_counters`.

2. **Auto-reconcile de lobbys (`ad27c80`).** `reconcile_lobby_logs` (sem Vision) re-resolve lobbys `tm_not_found`/`tm_ambiguous` usando o `vision_json` guardado, **disparado fire-and-forget após import de HH (`import_`) e de TS (`tournament_summaries`)** + on-demand `POST /api/lobbys/reconcile?dry_run=`. Escreve payout (precedência D11 respeitada), source `reconcile_lobby_vision:`.

3. **Resolver de lobbys — fallback ancorado no Hero (`16a435b`).** Quando o primário (site+nome+tempo) dá `tm_not_found`, dispara `_resolve_via_hero_anchor`: usa as mãos do **Hero** à volta do `captured_at` (±45 min) para achar o torneio real e **corrigir a sala**. Guard rails: buy_in-igual-pelo-total **obrigatório** + (nome ⊆ OU prize_pool ±2%) + **unicidade** (senão None, não adivinha). Em `process_lobby_message` E no reconcile. *Causa-raiz HIGHROLLER: o lobby confiava na Vision para a sala (≠ table-SS, que usa o token do filename desde pt56) — Winamax lido como GG.*

4. **Vision do replayer GG lê a coroa ($ bounty) (`13ef90d`).** Prompt reescrito: o bounty é o **valor em $ no banner dourado no topo do avatar** (não "ícone de coroa"). Flag **`force=true`** no `revision-replayers` re-corre a Vision mesmo em `vision_done='true'` e **refresca `player_names` sem re-derivar o anon_map**. Backfill das 23 replayer entries → IRE volta a aparecer no GG-via-replayer. ⚠️ Armadilha registada (`cc0bf7c`): **chama laranja = VPIP** (campo `bounty_pct`, nome enganador), **coroa dourada = bounty** (`bounty_value_usd`) — ver topo do CLAUDE.md.

**Outras peças:** **Página Lobbys** in-app (upload + detalhe extração/import + data do lobby) (`38a62e4`/`9c91bd9`/`27fdb73`); subpasta **`lobby`** no appimport (`422d1ee`); **`tools/appmaster`** — bat-mestre que orquestra appimport+apphm3+Discord num clique com menu de janelas (`34d886e`); etiqueta de vilões honesta `villains_unique` (`eede8d6`). 2 features futuras em `docs/PENDENTES.md`: `#BUBBLE-FACTOR-PER-PLAYER` (`8229a45`), `#CONTEXT-IMAGE-MKO-BOUNTY-AVG` (`5980f09`).

Última sessão fechada: **pt59** (4–5 Junho 2026 — página Lobbys + auto-reconcile + fallback de sala ancorado no Hero + appmaster + coroa GG; suite **886 PASSED**; HEAD `16a435b`). Journal: `docs/JOURNAL_2026-06-05-pt59.md`. Antecedida por pt58 (`docs/JOURNAL_2026-06-04-pt50-pt58.md`).

⚠️ **Pendente herdado:** **Smoke real Beelink pt42d** (`#WN-BOUNTY-NULL-IN-HRC-PIPELINE` v2) — uvicorn local + cópia `.exe` SHA cdfc7247...3262 + `payouts_helpers.py` para o Beelink; validar HRC Instant=50%. Continua por fazer.

Próxima sessão, por ordem sugerida: 1) **Re-import de scope ABRIL** (fechar placeholders Discord/lobby de Abril + `no_match` fora da janela 30/Mai+); 2) **Smoke real Beelink pt42d** (herdado); 3) **`#MYSTERY-KO-DUAL-SUPPORT`** (🟡 MED); 4) **`#LOBBY-SYNC-PAGINATION-LIMIT`** (🟡 MED); 5) **CoinPoker** (adiado — pacote completo). Backlog em `docs/PENDENTES.md`.
