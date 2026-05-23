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

O produto existe para conciliar duas fontes de verdade, cada uma com metade da informação:

1. **Hand History (HH) da GGPoker** — matematicamente exacta (acções, stacks, pot) mas **anonimizada**: jogadores aparecem como hashes (`89ef4cba`).
2. **Screenshots** tirados durante o jogo — têm nicks reais e bounties mas sem dados de acção fiáveis.

A app cruza as duas para produzir `hands.all_players_actions` enriquecido. Ter isto em mente ao mexer em `screenshot.py`, `mtt.py`, ou no parser GG.

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

Última sessão fechada: **pt35** (22 Maio 2026 — GTO Brain Fase 1: watcher exporta Complete Export, smoke real `GG-5944816316` 44 MB, `GTO_BRAIN.md` v1). Detalhes em `docs/JOURNAL_2026-05-22-pt35.md`.

Próxima sessão: **smoke battery de robustez** (`#PIPELINE-ROBUSTNESS-SMOKE-BATTERY`) — validar o pipeline nas 4 combinações site × formato (GG NKO Vanilla, PokerStars PKO, Winamax PKO, PokerStars NKO Vanilla) como porta de entrada da **Fase 2** (auto-import `.zip` → `gto_trees`/`gto_nodes`). Em paralelo continua aberto `#HRC-BOUNTY-HARDCODED-50PCT`. Backlog completo em `docs/PENDENTES.md` e `docs/GTO_BRAIN.md §7`.
