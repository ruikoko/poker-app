# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⚠️ REGRA DE OURO — LER ANTES DE QUALQUER ACÇÃO

**O PC onde este projecto é desenvolvido é o mesmo onde o utilizador joga poker.** As salas (GGPoker, PokerStars, Winamax, WPN, iPoker, 888) têm anti-cheat agressivo que scanneia processos activos. Qualquer processo "suspeito" (editores, terminais, ferramentas de análise, scripts Python a correr) pode gerar falsos positivos e prejudicar a conta.

**Claude Code só deve correr quando:**
- Todas as salas de poker estão **fechadas** (não minimizadas — fechadas).
- HM3, SharkScope HUD e Intuitive Tables estão fechados.
- O utilizador não está em sessão nem vai estar dentro dos próximos ~30 minutos.

**Durante uma sessão de poker activa**, apenas browsers são aceitáveis (inclui a app web deste projecto, porque corre dentro do browser).

**Se o Claude for invocado durante uma sessão activa**, avisar imediatamente o utilizador e pedir confirmação explícita antes de prosseguir. Nunca arrancar processos de longa duração (dev server, bot Discord, watchers) sem essa confirmação.

## Stack

- **Backend**: FastAPI + `psycopg2` contra PostgreSQL. Entry point `backend/app/main.py`; routers em `backend/app/routers/`; lógica em `backend/app/services/` e `backend/app/hand_service.py` (top-level); parsers por sala em `backend/app/parsers/`.
- **Frontend**: React 18 + Vite + React Router. Todo o HTTP passa por `frontend/src/api/client.js` (cookie-based auth, path relativo `/api`, proxy Vite para `localhost:8000`).
- **Integrações**: OpenAI Vision (GPT-4o-mini / GPT-4.1-mini) para screenshots; `discord.py` para puxar mãos de canais de estudo.
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

- **Arquivo MTT**: imports em bulk (`.zip` HH) entram com `study_state = 'mtt_archive'`. Aparecem só na secção **MTT** (drill-down por torneio) — **nunca** na Inbox nem na página Mãos.
- **Estudo**: uma mão entra em `new` apenas quando chega um screenshot (ou marcação manual). Depois percorre `new → review → studying → resolved`. A Inbox mostra `new`; a página Mãos mostra o track de estudo.

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

## Auth

Cookie-based (`HttpOnly`, 7 dias, assinado com `SESSION_SECRET` via `itsdangerous`). `require_auth` é o dependency FastAPI para rotas protegidas. bcrypt para hashing de passwords. Não há CSRF para além de `SameSite` + CORS `ALLOWED_ORIGIN` — manter `ALLOWED_ORIGIN` apertado em produção.

## Ficheiros delicados — alto risco, ler o código inteiro antes de mexer

- **`backend/app/routers/screenshot.py`** — pipeline SS→HH com âncoras + aritmética de stacks + eliminação. Bugs aqui afectam **1000+ mãos** já em BD. Nunca alterar a ordem das fases nem a tolerância de stack sem correr um backfill de validação a seguir.
- **`backend/app/routers/mtt.py`** — especialmente `_promote_to_study`, `_create_villains_for_hand`, `import_mtt`. Toca arquivo, track de estudo e criação de villains em simultâneo; um erro pode contaminar as duas pistas.
- **`backend/app/services/hand_service.py:_insert_hand`** — detecta placeholders GGDiscord e apaga-os antes de inserir a HH real. Bug aqui **bloqueia imports inteiros**.

## Trabalho em curso (20 Abril 2026)

- Feature `has_showdown` adicionada à tabela `hands` (commit `d91a186`).
- `_create_villains_for_hand` agora tem modo showdown: só cria villains para jogadores com `cards != None`.
- Backfill SQL processou 5269 mãos e criou 266 villains.
- **Por validar**:
  - Deploy no Railway está activo com estas alterações?
  - Mãos novas (inseridas após o merge) estão a popular `has_showdown` correctamente?
  - Distribuição dos 266 villains faz sentido (sem duplicados, nicks razoáveis)?

## MODELO DE DADOS E FLUXO (v2, 21-Abr-2026)

Consolidação após sessão de 21-Abr. Substitui o modelo antigo onde aplicável — nos pontos em conflito, **esta secção ganha**.

### 1. Quatro fontes de input

Cada input deixa uma marca diferente na mão:

| Fonte | Como entra | Marca em `hands` |
|---|---|---|
| **HM3 (.bat)** | Script `.bat` lê BD do HoldemManager3 e faz POST | `hm3_tags` = tags reais do HM3 (lista em `HM3_REAL_TAGS`) |
| **Discord** | Bot puxa mensagens de canais monitorizados | `discord_tags` = nome literal do canal (ex: `'nota'`, `'icm'`) |
| **Upload manual SS** | Drag-and-drop de screenshot na UI | `origin = 'ss_upload'` *(coluna ainda por criar)* |
| **Import ZIP/TXT HH** | Upload de ficheiro HH bruto (GG/PS/Winamax/WPN) | `origin = 'hh_import'` *(coluna ainda por criar)* |

**Nota técnica:** coluna `hands.origin TEXT` ainda não existe — será adicionada numa fase seguinte (mesmo padrão `ensure_origin_column`). Até lá, origem para SS/HH deriva-se indirectamente via `entries.source` + `entries.entry_type`.

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
5. **Discord** — centro de operações SS↔HH: logs detalhados, associação de gyazos (±10 min → mão adjacente). **Sem** listas de SSs/mãos (vivem no Dashboard / Estudo / Vilões).
6. **HM3** — centro de operações do script `.bat`: logs, listagem de mãos filtrável (tag / data / PKO-NPKO / pré-flop vs pós-flop), edição manual de tags com re-avaliação automática de destinos.
7. **GTO** — inalterada.

### 3. Transições entre secções

Regras determinísticas; cada mão pode cair em múltiplos sítios:

| Condição na mão | Vai para |
|---|---|
| `hm3_tags` contém tag `~ 'nota%'` | Vilões |
| `hm3_tags` contém outras tags | Estudo |
| `hm3_tags` mistas (ex: `['ICM','nota']`) | **Ambas** — cada secção filtra só as tags da sua semântica |
| `discord_tags` contém `'nota'` + tem match | Vilões |
| `discord_tags` outros canais + tem match | Estudo |
| SS sem HH (match falhou) | Dashboard (painel "À espera de HH") |
| HH GGPoker sem SS | Torneios > GG > Sem SS |
| HH PokerStars/Winamax/WPN sem SS | Estudo directo (já têm nicks reais) |
| Match SS↔HH | Bidireccional: qualquer lado pode chegar primeiro |

### 4. Regra de elegibilidade para `hand_villains`

Uma mão gera entry em `hand_villains` sse **(A OR B OR C)**:

- **(A)** `hm3_tags ~ 'nota%'` (tag HM3 começa por "nota")
- **(B)** `player_names ->> 'match_method' IS NOT NULL` **AND** `has_showdown = TRUE` (match SS↔HH válido **e** houve showdown)
- **(C)** `'nota' = ANY(discord_tags)` **AND** `player_names ->> 'match_method' IS NOT NULL` (partilhada no canal Discord #nota, ID `1410311700023869522`, e com match SS↔HH)

O modal do vilão mostra **só** mãos presentes em `hand_villains` — não mais o VPIP global antigo, que puxava toda a mão onde o vilão aparecia.

**Princípio invariante:** NUNCA criar villain numa mão GG anonimizada (sem `match_method`). Aplica-se às 3 regras — B e C já o exigem explicitamente; A aplica-se a tags HM3 que em GG também implicam match na prática.

### 5. Filtro permanente: só mãos de 2026

Rui só estuda mãos de 2026. **Qualquer query ad-hoc ou script contra `hands` deve incluir `played_at >= '2026-01-01'`**. Em produção a UI já filtra; em scripts `query_*.py` / `backfill_*.py` é obrigatório. Histórico anterior existe na BD mas é ruído para qualquer análise actual.

## ESTADO FIM SESSÃO 21-22 ABR 2026

### Concluído hoje
- Coluna hands.origin criada + backfill 5271 mãos
- Regra villain A∨B∨C aplicada em /villains/search/hands e /recalculate-hands (VPIP antigo removido)
- Filtros showdown (Com/Sem) na página Estudo
- Torneios: aba "GG sem SS", header enriquecido (TM · nome · $buy_in · blinds · horas · N mãos/SS/V), chip buy_in
- Placeholders Discord excluídos de Torneios
- Secção HM3 adicionada ao sidebar (/hm3)
- Coluna hands.tournament_format criada + parser por sala (nome primeiro; fallback: Winamax bounty pattern, PS 3-componentes buyIn, GG bounty_pct) + backfill
- Badge KO/NKO no HandRow unificado (Estudo, HM3, Torneios)
- Componente HandRow partilhado em components/HandRow.jsx substituindo 3 HandRows locais
- Endpoint HM3 .bat agora popula origin='hm3'
- Fix button seat não presente em seats (Winamax raw bug) — 3 mãos que falhavam agora entram com position=NULL
- Fallback site detection via hero aliases (HERO_NICKS_BY_SITE por sala) quando SITE_MAP HM3 falha

### Bugs detectados, por resolver
1. CRÍTICO: _detect_vpip_hm3 em hm3.py só olha VPIP preflop; mãos com tag nota* + showdown não criam entries em hand_villains. Ex: id=182259 (WN-...-157) nota++ sd=True villains=[]. Código escreve em villain_notes mas NUNCA em hand_villains — regra A∨B∨C fica sem rows. Fix: (a) iterar all_players e extrair não-hero com cards preenchidos (showdown-based); fallback VPIP preflop quando sd=False; (b) INSERT em hand_villains além de villain_notes. Modelo equivalente existe em mtt.py _create_villains_for_hand.
2. Parser WPN incompleto (baixa prioridade — Rui joga pouco em WPN)

### Simulação end-to-end
- Passo 1 HM3 .bat: VALIDADO (3 mãos button-bug resolvidas, 0 erros)
- Passo 2 Discord sync: PENDENTE
- Passo 3 validação UI: PENDENTE

### Contexto útil próxima sessão
- hero_names.py tem HERO_NICKS_BY_SITE e FRIEND_NICKS_BY_SITE novos. FRIEND_NICKS_BY_SITE["GGPoker"] = ["karluz","flightrisk"] — extensível à medida que Rui pede mãos de amigos.
- Commits session: c499c6f→d6d0505→5ea3db6→9bd40aa→8fdb0a7→42bca81→3305c60→0737d61→b864773→5c7c33b→dd2e960→dee479f→17f5cf1→e3ab933→7ab5ac1→828d736→3aedae5→76b67bc→3493b56
