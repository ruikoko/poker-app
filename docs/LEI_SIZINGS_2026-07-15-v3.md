# LEI DE SIZINGS DO SCRIPT HRC — v3

- **Versão:** `2026-07-15-sizings-v3`
- **Ditada e carimbada pelo Rui:** 15 Julho 2026 (linha a linha; carimbo integral).
- **Estado:** ✅ **VERIFICADA EM PRODUÇÃO — VALE DO RUI (16 Jul 2026).** Relatório tree-a-tree
  sobre 13 mãos resolvidas pelo robot: **187 nós MATCH, 0 violações**; todos os cenários provados
  em trees reais (KO 9.0 · 4-bet 10.3 · squeeze 9.0 · BB-vs-limp 3.0+ALLIN · call garantido no
  sobre-allin · cadeia SBvsBB · colapso). **Rege a partir de agora tudo o que o robot resolver.**
  Ver `JOURNAL_2026-07-16.md`. (Fases 1-4 backend implementadas + Portão 1 carimbado antes.)
  Trees já resolvidas com a lei antiga ficam como estão (sem re-solve). ⚠️ Limpeza
  Python dos helpers mortos (CASO A/B, `_compute_default_*`, `_array_for_*`, `_bucket_*`) fica
  como passagem dedicada — estão **inertes** (`build_sizings_overrides` devolve `{}`), não
  afetam runtime.

**Esta lei SUBSTITUI, onde conflituarem:** `REGRAS_NEGOCIO §17, §18, §18.1–§18.4, §19`
e as réguas de sizing das sessões pt42/pt42b/pt91. As secções antigas ficam com banner
"SUPERSEDED por v3" (não se reescrevem — convenção de imutabilidade dos snapshots).
`§14` (equity model) e `§16 FT` (regras de mesa final) ficam **fora** desta lei.

Cross-ref: `HRC_ANATOMIA_OPERACIONAL §3.4`, `hrc_scripts/mtt_advanced_canonical_2026.js`,
`hrc_script_gen.py`, `hrc_node_offset.py`, `queue_export.py`.

---

## 0 · PRINCÍPIOS (mandam sobre os escalões)

| Princípio | Definição |
|---|---|
| **Regra de Ouro** (primeira, manda sobre tudo) | o **size real da HH** substitui o default na posição respetiva (ex.: UTG abriu 2.5× → a tree nasce com UTG 2.5×); o resto constrói-se normal. |
| **Régua única da efetiva** (mata as 3 medidas antigas) | `eff = min(REMAINING de quem age, REMAINING do adversário do confronto)`. Adversário: **open** → o **maior** remaining vivo **por falar** · **3-bet / 4-bet** → o **agressor anterior** · **squeeze** → **O MAIOR** entre opener e callers. |
| **Bordas** | a fronteira pertence ao **escalão de baixo**: 60 ∈ `36-60`, 61 ∈ `61-90`; 100 ∈ `36-100`, 101 ∈ `101+`. |

**Convenções:**
- **IP** = agressor **não-blind** (age sempre depois → está IP). **OOP** = SB/BB.
  *Não há 3-bet/4-bet OOP fora das blinds* (quem 3-beta sem ser blind está sempre depois
  do opener). Logo os blocos IP / SB / BB / SBvsBB são **completos**.
- **`size`** nas tabelas = valor do escalão **ou** o size real da HH quando a posição
  jogou (a Regra de Ouro sobrepõe-se).
- Todos os multiplicadores são **× o raise anterior**: 3-bet × open · 4-bet × 3-bet ·
  squeeze × open.
- Efetiva sempre em **BB**.

---

## A · OPENS

**Base (todas as posições):** `eff > 9` → open **2 BB** · `eff ≤ 9` → **SÓ JAM** (colapso; fica).

**Linha de all-in no nó de open** (§19 **reformada** para a régua única — **morre o "individual"**):

| Caso | Acrescenta ALLIN até | Array resultante |
|---|---|---|
| **IP** (não-blind) | eff **≤ 25** | `≤25 → [2 BB, ALLIN]` · `26+ → [2 BB]` |
| **SB** | eff **≤ 30** | `≤30 → [size, ALLIN]` · `>30 → [size]` |
| **BB** (sobre limp da SB) | eff **≤ 25** | `≤25 → [size, ALLIN]` · `>25 → [size]` |

**Tabelas de size das blinds (× BB):**

| Sub-caso | `< 10` | Escalões |
|---|---|---|
| **SBvsBB** — fold até à SB, a **SB** abre | jam | `10-15 → 2.2` · `16-25 → 2.5` · `26-35 → 3` · `36-100 → 3.5` · `101+ → 4` |
| **BB vs LIMP da SB** — SB limpa, a **BB** sobe | jam | `10-14 → 2` · `15-20 → 2.5` · `21-30 → 3` · `31-100 → 3.5` · `101+ → 4` |

---

## B · 3-BET

**× OPEN · `[size, ALLIN]` em TODOS os escalões · abaixo da banda = SÓ JAM.**

| Bloco (quem 3-beta) | Escalões |
|---|---|
| **IP** (não-blind vs opener) | `17-25 → 2.25` · `26-35 → 2.5` · `36-60 → 3` · `61-90 → 3.5` · `91+ → 4` · *(10-16 jam)* |
| **SB** (vs opener não-blind) | `18-25 → 3` · `26-30 → 3.5` · `31-80 → 4` · `81+ → 5` · *(<18 jam)* |
| **BB** (vs opener não-blind) | `16-20 → 2.5` · `21-25 → 3` · `26-35 → 3.5` · `36-80 → 4` · `81+ → 5` · *(<16 jam)* |
| **SBvsBB** — o 3-bet é **do BB** sobre o open da SB | `16-25 → 2.2` · `26-35 → 2.5` · `36-100 → 3` · `101+ → 4` · *(<16 jam)* |

**Bónus KO:** torneio KO (`IS_PKO`) **E** o opener **cobre** o 3-bettor (tem ≥ fichas
totais) → **+0.5** ao multiplicador. **SÓ no 3-bet** (não se estende a 4-bet nem squeeze).

---

## C · 4-BET

**× 3-BET · all-in SEMPRE presente no nó · abaixo do 1º escalão com valor = SÓ ALL-IN**
(inclui qualquer eff abaixo do escalão jam listado — o 4-bet só existe depois de um 3-bet).

| Bloco (quem 4-beta) | Escalões |
|---|---|
| **IP** | `26-35 → 2` · `36-60 → 2.2` · `61-90 → 2.5` · `91+ → 2.7` · *(17-25 só allin)* |
| **SB** | `31-80 → 2.3` · `81+ → 2.5` · *(18-30 só allin)* |
| **BB** | `26-35 → 2.3` · `36-80 → 2.5` · `81+ → 3` · *(16-25 só allin)* |
| **SBvsBB** — o 4-bet é **da SB** | `36-100 → 2.2` · `101+ → 2.7` · *(16-35 só allin)* |

**A regra SPR≤7 MORRE — o all-in do 4-bet é incondicional.**

---

## D · 5-BET

**Mantém `0.4 / 0.5` pot** (inalterado) — **com o all-in no array** (comportamento atual).

---

## E · SQUEEZE

**× OPEN · `eff = min(squeezer, O MAIOR entre opener e callers)` · `[size, ALLIN]` em
todos os escalões · `< 20` SÓ JAM (IP e OOP).**

| Escalão | IP | OOP |
|---|---|---|
| `20-25` | 3 | 3.5 |
| `26-35` | 3.5 | 3.7 |
| `36-60` | 3.7 | 4 |
| `61-100` | 4 | 4.5 |
| `101+` | 4.5 | 5 |

**O `+1 BB` por caller MORRE.**

Exemplo do Rui (régua da efetiva no squeeze): UTG 20 abre, CO 100 call, BTN 100 squeeza
→ efetiva = `min(100, max(20, 100)) = 100`.

---

## F · SOBRE UM OPEN ALL-IN

3-bet comum (tabelas do **bloco B**) **+ linha de CALL sempre garantida no nó**.
**B1 / iso-raise enterra-se** (`_ISO_RAISE_OVER_ALLIN_MULT` morre).

---

## G · SOBREPOSIÇÕES QUE SOBREVIVEM (aditivas)

| Regra | Estado |
|---|---|
| **Bónus KO +0.5** (KO + opener cobre) | **MANTÉM — só no 3-bet.** |
| **Regra 3 — shortie PKO ≤ 4 BB** (ISO all-in aditivo em opens e 3-bets quando há adversário vivo ≤ 4 BB, ou o próprio opener ≤ 4 BB) | **MANTÉM.** |

---

## H · MANTÊM-SE (eram texto silencioso → passam a LEI ESCRITA)

- **Flats:** `ALLOWED_FLATS_PER_RAISE = {2:3, 3:2, 4:1, 5:0, 6:0}`.
- **Só a SB completa (limp)** em bets == 1.
- **Postflop cortado** depois do FLOP (turn/river só check) com a config atual:
  hint geométrico `0.75`, flop bet `0.20` pot, all-in postflop `SPR ≤ 5`, donk **off**.
- **Clamps** (`applyAllinThreshold`, `PREFLOP_ALLIN_THRESHOLD = 1`).
- **`preserveRealRaise`** (re-injeta a ação real no seu nó, com dedupe).
- **"Primeira ganha"** no bucket (2 ações no mesmo bucket → só a 1ª).

---

## I · MORREM (limpeza incluída na implementação)

- **R6** blind-open por eff (antigo §18.1, `_blind_open_size_by_eff`) — o SBvsBB /
  BB-vs-limp cobre.
- As **3 réguas velhas** de efetiva (D2): `effectiveStackBBAtOpen`,
  `effectiveStackBBVsRaiser`, `_compute_effective_at_action` divergentes → **1 régua**.
- **+1 BB do squeeze** (`SQUEEZE_INCREASE_PER_CALL`).
- **SPR≤7 do 4-bet** (`PREFLOP_ADD_ALLIN_SPR` no caminho do 4-bet).
- **B1** (`_ISO_RAISE_OVER_ALLIN_MULT`).
- **CASO A/B** do 3-bet IP (~300 L: `_apply_caso_a_3bet_ip`, `_apply_caso_b_3bet_overrides`,
  `_default_3bet_for_candidate`, `_bb_3bet_default_vs_open`, `_eff_spot_specific_bb`,
  `_eff_3bettor_vs_live_nonallin`, `_candidate_3bet_positions_ip`).
- **Helpers/arrays inertes:** `SIZES_3BET_IP/UTG1..BU`, `SIZES_3BET_SB_VS_*`,
  `SIZES_3BET_BB_VS_*`, mirrors Python `threebet_multiplier`/`threebet_sizings_bb`.
- **Tetos 40 IP / 45 OP** (pt91).
- **Buckets antigos** (2.0…4.5 do §18.4; 2.3/2.7/3.0 do pt42).

---

## J · IMPLEMENTAÇÃO (bloqueada até ordem explícita do Rui)

1. **Template + `count_lines_for_position`/offset em LOCKSTEP** + testes adaptados +
   **dedupe de all-in por construção** (fim do all-in triplo dos opens).
2. Lei **versionada e datada**: `SIZING_RULES_VERSION = "2026-07-15-sizings-v3"`.
   Trees existentes ficam da lei antiga — **sem re-solve** (anti-massivo).
3. **Verificação antes de valer:** smoke 5/5 + **trees de prova** (1 por cenário:
   colapso ≤9 · open IP 10-25 e 26+ · SB ≤30 · SBvsBB open+3bet+4bet · BB-vs-limp ·
   3-bet dos 4 blocos · 4-bet só-allin e com size · squeeze <20 e 36-60 ·
   sobre-open-allin com call) → relatório **tree-a-tree** ao Rui.
4. **Dúvida de interpretação = pergunta ao Rui, nunca decisão do Code.**
