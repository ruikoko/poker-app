# Workflow operacional — como trabalhar diferentes tipos de mão

**Estado:** v1, 22 Maio 2026 (pt34).
**Audiência:** Web + Code (Rui lê em bónus).
**Propósito:** descrever, de fonte a destino, como cada **tipo de mão** e
cada **formato de torneio** é tratado pela app — sala, anonimização,
bounty, IRE, e o caminho até ao HRC. Complementa:
- `docs/HRC_ANATOMIA_OPERACIONAL.md` — anatomia do HRC (formato de HH que
  o HRC engole, coords, popup).
- `docs/REGRAS_NEGOCIO.md` — regras de negócio (entrada → processamento →
  distribuição).
- `docs/MAPA_ACOPLAMENTO.md` — onde cada conceito é produzido/consumido.

> **Regra de leitura:** quando este doc e o código discordarem, o **código
> ganha** e este doc está desactualizado — corrige-o. Cada afirmação aqui
> aponta para o ficheiro:função que a sustenta.

---

## 1. Formatos de HH suportados e como o site é identificado

A app aceita hand histories (HH) de **4 salas**. Cada uma tem o seu parser
em `backend/app/parsers/`.

| Sala | Como entra | Nicks | Notas |
|---|---|---|---|
| **GGPoker** | `.txt` / `.zip` HH | **Anonimizados** (hash `89ef4cba`) | Parser `parsers/gg_hands.py`. Precisa de cruzamento com SS para ter nicks reais. |
| **PokerStars** | `.txt` HH | **Reais** | Já trazem nicks reais — vão directos para Estudo. |
| **Winamax** | `.txt` HH | **Reais** | Line endings `\r\r\n` corrigidos em pt22. Bounty na linha Seat com símbolo **depois** do valor (`107€`). |
| **WPN** | fluxo `.bat` (HM3) / HH | **Reais** | Sem sinal estrutural fiável de bounty (ver §4). |

### 1.1 Duas formas distintas de "identificar o site" — não confundir

Há **duas** identificações de site no projecto, com propósitos diferentes:

**(a) `detect_site_from_hh(raw_hh)`** em `backend/app/hero_names.py` —
identifica a sala **por matching de nicks conhecidos**, não por prefixo de
header. Varre as linhas `Seat N: <nick>` e conta quantos batem com os
nicks de cada sala em `ALL_NICKS_BY_SITE` (= `HERO_NICKS_BY_SITE` +
`FRIEND_NICKS_BY_SITE`). Devolve a sala com mais matches; **empate → None**
(não adivinha); zero matches → None. É **case-insensitive**.
- *Uso:* fallback do parser HM3 quando o `site_id` vem errado na BD do HM3.

**(b) O parser interno do HRC** identifica o formato por **prefixo da
primeira linha** do header (`PokerStars Hand #`, `Winamax Poker - `,
`Poker Hand #TM` para GG). Isto é **do HRC, não nosso** — documentado em
`HRC_ANATOMIA_OPERACIONAL.md` §12.1. Relevante porque o HRC **rejeita**
bounty na linha Seat em formato GG; ver §4.3 abaixo.

> Não misturar (a) com (b). (a) é nosso e baseia-se em nicks; (b) é do HRC
> e baseia-se no prefixo do header. São coisas diferentes que ambas
> "detectam o site".

---

## 2. Workflow GGPoker (anonimizado)

O caso mais delicado, porque a HH GG vem **anonimizada**.

- **Hashes são fixos dentro do mesmo torneio**, mas variam entre torneios.
  Dentro de um torneio, o hash `89ef4cba` é sempre o mesmo jogador; noutro
  torneio o mesmo jogador tem outro hash.
- **Hero aliases GG** (`HERO_NICKS_BY_SITE['GGPoker']`):
  `lauro dermio`, `koumpounophobia`.
- **Friend aliases GG** (`FRIEND_NICKS_BY_SITE['GGPoker']`):
  `karluz`, `flightrisk`.
  - (A lista global de heroes/amigos vive em `HERO_NAMES`, `FRIEND_HEROES`,
    `FRIEND_NICKS` no mesmo `hero_names.py`; a versão "por sala" é a usada
    no `detect_site_from_hh`.)
- **Match SS ↔ HH:** o cruzamento screenshot↔HH (pipeline em
  `routers/screenshot.py`) resolve `hash → nome_real` por âncoras
  (Hero/SB/BB) + aritmética de stacks + eliminação. Os nicks dos SS podem
  vir **truncados** pela Vision; o match tolera truncatura (ver
  `is_friend_prefix` em `hero_names.py`, que faz starts-with para nicks ≥4
  chars).

**Regra dura:** uma mão **GG anonimizada sem match** SS↔HH **NÃO vai para
Estudo** (CLAUDE.md §"Duas pistas de ciclo de vida" + §3 da tabela de
transições). Sem nicks reais, não há o que estudar. Vai, no máximo, para
Torneios > GG > Sem SS. **NUNCA** se cria villain numa mão GG anonimizada
(invariante das regras A/C/D em `services/hand_service.py`).

---

## 3. Formatos de torneio e detecção

O classificador é `detect_tournament_format(name, *, site, raw_hh,
has_player_bounty)` em `backend/app/utils/tournament_format.py`. Devolve
sempre um de **4 valores canónicos**: `'Super KO'`, `'PKO'`, `'Mystery KO'`,
`'Vanilla'` (nunca `None`).

Hierarquia de decisão:

1. **NOME ganha sempre** (`_classify_by_name`):
   - `mystery` → `Mystery KO` (vence sempre — Mystery é KO-based mas tem de
     ser distinguido de PKO).
   - `bounty` / `pko` / `knockout` → `PKO`.
   - ` ko ` / ` ko$` isolado → `PKO` (default conservador: nome ambíguo
     como "KO Daily" assume bounty).
2. **Sinal estrutural por sala** (só quando o nome não decide):
   - **PokerStars** (3 componentes `$A+$B+$C` no header):
     `B > A` → `Super KO`; `B == A` com `$X bounty` no raw → `PKO`;
     `B == A` sem bounty no raw → `Mystery KO`.
   - **Winamax** (`<N>€ bounty)` na linha Seat) → `PKO`.
   - **GGPoker** (`has_player_bounty=True`) → `PKO`.
   - **WPN** — sem sinal estrutural fiável → `Vanilla`.
3. **Sem sinais** → `Vanilla`.

> Legacy em BD (`'PKO' | 'KO' | 'mystery' | 'vanilla'`) mantém-se sem
> backfill; o detector nunca devolve `'KO'` puro à saída — esse valor só
> existe para mãos legacy. Callers que comparam valores fazem dual-accept.

### 3.1 Super KO — ratio "escondido"

`Super KO` corresponde a um ratio de bounty de **40%** (vs 25% do PKO
clássico). Foi explicitamente **excluído do IRE** (ver §5): `compute_ire`
faz `return None` se o nome do torneio contém "Super KO". Razão histórica:
a tabela W3CRAY é válida só para ratio 25%.

---

## 4. Workflow por formato

### 4.1 Vanilla (sem bounty)

- Bounty Mode no HRC = **OFF**.
- Não dispara IRE.
- Caso mais simples — é só ICM puro.

### 4.2 PKO (Progressive Knockout)

- Bounty Mode no HRC = **PKO N%** (o HRC pede N entre 25 e 50).
- **Estado actual do robot:** o watcher tem o Bounty Mode **hardcoded em
  50%** — em `setup_hand`, quando `is_ko_tournament(prize_path)` é true,
  imprime `"KO detetado — a selecionar Bounty Mode PKO 50%"` e chama o
  `select_bounty_mode` legacy do Baltazar (que assume 50%).
  - **Nuance importante:** o `progressiveFactor` no `payouts.json` **É**
    data-driven (vem do lobby vision: 0.5 "Bounty Hunters", 0.33 "KO",
    0.25 PKO 25%, 0.0 vanilla). O que está hardcoded é o **dropdown
    Bounty Mode do watcher**, que ignora esse valor e mete sempre 50%.
  - Tech debt aberto: **`#HRC-BOUNTY-HARDCODED-50PCT`** — fazer o watcher
    ler o `progressiveFactor` / `tournament_format` e seleccionar a opção
    correspondente. Ver `docs/TECH_DEBTS_INVENTARIO.md`.
- **Detecção do ratio pelo nome:** "Super KO" → 40% (escondido do IRE);
  "PKO" / "Mystery KO" / "Vanilla" como em §3.

### 4.3 Bounty na HH e o HRC

O HRC **rejeita** bounty na linha Seat em formato GG. Para passar info de
bounty ao HRC é obrigatório converter a HH GG inteira para formato
PokerStars-compatível (11 transformações em
`convert_gg_hh_to_pokerstars_compatible`, `services/queue_export.py`).
Detalhe completo em `HRC_ANATOMIA_OPERACIONAL.md` §12.

### 4.4 Mystery KO

- Tratamento semelhante a PKO, mas com bounties **variáveis**.
- Distribuição mistério: o bounty real só é conhecido no momento do KO.
- No IRE, `Mystery KO` **é** um formato permitido (`ALLOWED_FORMATS =
  {"PKO", "Mystery KO"}`).

### 4.5 Export do resultado — Complete Export (pt35)

Desde pt35, o robot exporta o resultado via **Complete Export** (no diálogo
"Hand > Export Strategies" do HRC, o combo passa de "Manual Selection" para
"Complete Export"). Antes corria "Manual Selection" sem selecção, o que dava
**1 nó** por árvore = resultado inútil. Output: `.zip` de ~40-70 MB (smoke
real `GG-5944816316` = 44 MB) — é este `.zip` que o GTO Brain consome. O
campo Depth é ignorado pelo Complete Export. Mecânica completa em
`HRC_ANATOMIA_OPERACIONAL.md §8`; visão do GTO Brain em `GTO_BRAIN.md`.

---

## 5. IRE (Índice de Redução de Equity / Bounty Power)

`compute_ire(hand, tournament_meta)` em `backend/app/services/ire.py`.
Calcula, por oponente, quanto a equity é reduzida pela presença de bounties
("bounty power"). **GG-only, ratio 25%.**

- **Tabela W3CRAY** `17×9` (`W3CRAY_TABLE_25PCT`): linhas = stack do
  oponente em SI (starting stacks), colunas = KO do oponente em unidades de
  KO inicial. Valores em %. Células `None` → fallback por fórmula
  (`_formula_fallback`). Validada via `Mathematics.xlsx` sheet "IRE".
- **Válida só para ratio 25%** (initial bounty = 25% do starting stack).

**Condições de activação** (qualquer falha → `return None`, IRE escondido):

1. `hand.site == 'GGPoker'`.
2. `match_method` real (não `discord_placeholder_*`).
3. tag `ko` em `hm3_tags` **ou** `discord_tags` (case-insensitive).
4. `tournament_format ∈ {'PKO', 'Mystery KO'}`.
5. `tournaments_meta` com `starting_stack > 0`.
6. nome do torneio **não** contém "Super KO" (= ratio 40%).
7. ≥ 1 oponente (non-hero) com `bounty_pct > 0`.

O vilão principal é escolhido pela **regra D** (`_pick_main_villain`):
entre activos com bounty, prefere o que o Hero **cobre** (stack ≤ hero);
desempate pelo maior stack coberto, senão o maior stack activo.

---

## 6. Fluxo de input — as fontes até à BD

(Resumo; tabela canónica completa em CLAUDE.md "Fontes de input" e em
`docs/MAPA_ACOPLAMENTO.md`.)

As 4 fontes **clássicas** de mãos deixam marcas diferentes:

| Fonte | Como entra | Marca em `hands` |
|---|---|---|
| **HM3 (.bat)** | Script `.bat` lê BD do HoldemManager3 → POST | `hm3_tags` (tags reais do HM3) |
| **Discord (canais estudo)** | Bot puxa mensagens dos canais monitorizados | `discord_tags` (nome literal do canal) |
| **Upload manual SS** | Drag-and-drop de screenshot na UI | `origin = 'ss_upload'` |
| **Import ZIP/TXT HH** | Upload de ficheiro HH bruto | `origin = 'hh_import'` |

(Há mais fontes que **não** tocam directamente em `hands`: Tournament
Summaries GG, Tournament Results backoffice, #lobbys → `tournament_payouts`;
e o **watcher HRC** que **devolve** dados via `POST /api/queue/hrc/results`
→ `hrc_jobs`. Ver CLAUDE.md.)

---

## 7. Resolver cascade — cruzar SS de lobby com o torneio

`tournament_resolver` (antigo `tm_resolver`) resolve qual o
`tournament_number` de um SS de lobby, em **tiers**:

- **TIER 0 — `tournament_summaries`** (autoritativo post-jogo, **sem janela
  temporal**). Discrimina por `prize_pool` + `total_players` da Vision.
  GG-only (parser GG do TS).
- **TIER 1 — `tournaments_meta`** (janela temporal apertada).
- **TIER 2 — `hands` fallback** (janela temporal + `posted_at_hint`).

### 7.1 Workflow "deferido" do Rui (importante)

O Rui **acumula SSs durante a sessão** e, no fim, importa as HHs + os
Tournament Summaries de uma vez. O bot faz o match em **bulk** depois.
Isto significa que, durante a sessão, muitos SSs ficam órfãos à espera de
HH — e isso é **esperado**, não erro. O painel "SSs à espera de HH" no
Dashboard mostra-os. O TIER 0 (sem janela temporal) existe precisamente
para que este fluxo deferido funcione: quando o TS chega no fim, resolve
SSs de horas antes sem depender de proximidade temporal.

---

## Cross-references

- `backend/app/hero_names.py` — `detect_site_from_hh`, `HERO_NICKS_BY_SITE`,
  `FRIEND_NICKS_BY_SITE`, `is_hero`/`is_friend`/`is_friend_prefix`.
- `backend/app/utils/tournament_format.py` — `detect_tournament_format`.
- `backend/app/services/ire.py` — `compute_ire`, `W3CRAY_TABLE_25PCT`.
- `backend/app/services/queue_export.py` — conversão GG → PokerStars.
- `docs/HRC_ANATOMIA_OPERACIONAL.md` §12 — formato de HH aceite pelo HRC.
- `docs/REGRAS_NEGOCIO.md` — regras de elegibilidade de villain, IRE.
