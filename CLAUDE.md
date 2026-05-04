# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⚠️ LEITURA OBRIGATÓRIA ANTES DE TUDO

Qualquer sessão Claude Code que toque neste repositório DEVE ler primeiro estes 4 documentos, por esta ordem:

1. **`docs/VISAO_PRODUTO.md`** — visão alta da app (propósito, vectores, secções).
2. **`docs/REGRAS_NEGOCIO.md`** — regras operacionais (entrada, processamento, distribuição, casos canónicos, regras duras).
3. **`docs/MAPA_ACOPLAMENTO.md`** — mapa técnico de conceitos (`match_method`, `study_state`, `origin`, etc).
4. **`docs/TECH_DEBTS_INVENTARIO.md`** — backlog actualizado de tech debts.

Sem ler estes 4 documentos, NÃO tocar em código. Atalhos aqui produzem regressões (já aconteceu).

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

Última sessão fechada: pt12 (4 Maio 2026, #B33 fechado, pipeline ZIP+Discord robusto e idempotente, commits `c979181` + `e7d88b2`).
