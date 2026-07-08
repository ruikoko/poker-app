# FT_BOUNDARY — anatomia da máquina de mesa final (propagação de FT)

> **Estado (8 Jul 2026):** frente construída por inteiro (F1–F5) e **LIVE** em produção
> (`main`→`874bd7e`). Irmão do `DESANON_ANATOMIA.md`. Documenta a máquina que detecta a
> **fronteira da mesa final (FT)** por torneio e converte as tags de estudo base (`icm`,
> `pos-pko`, …) na variante `-ft` nas mãos a partir dessa fronteira.
> Cross-ref: `JOURNAL_2026-07-08.md`, `JOURNAL_2026-07-07-*`, `REGISTO_CONCEITO` (entradas
> 2026-07-07 e 2026-07-08), `REGRAS_NEGOCIO §20`, `services/ft_boundary.py`,
> `routers/gg_health.py` (F3/F4/F5), `services/lobby_vision.py`, `services/lobby_sync.py`.
> **Obrigatório antes de tocar no motor FT.**

---

## 1. O conceito (humano)

O Rui estuda a **mesa final** (FT) com regras diferentes do resto do torneio (ICM mais
apertado, sizings próprios — as regras `-ft` do HRC, `IS_FT`). Por isso as mãos de FT levam
uma **tag própria**: a variante `-ft` da tag base (`icm`→`icm-ft`, `pos-pko`→`pos-pko-ft`).

A **fronteira da FT** é o instante (o `played_at` da 1ª mão de FT) a partir do qual, **nesse
torneio**, todas as mãos passam a ser FT. A máquina existe para **descobrir essa fronteira por
torneio** e **propagar** a variante `-ft` às mãos base a partir dela — sem o Rui ter de marcar
mão a mão.

**Princípio invariante:** a **escrita das tags `-ft` é SEMPRE por aprovação manual do Rui**
(botão + ensaio + confirmação). A máquina **calcula e propõe**; nunca escreve tags sozinha.
Ver §7–§8.

---

## 2. A cascata de fontes — `(0) → (a) → (b) → none`

A fronteira computa-se por uma cascata de fontes, da mais fiável para a salvaguarda
(`compute_ft_boundary` em `services/ft_boundary.py`):

| Fonte | O que é | Fiabilidade |
|---|---|---|
| **(0) tag `-ft` MANUAL** | 1ª mão (por `played_at`) com `folder_ft_source='manual'` — o Rui marcou a mesa final à mão (pasta `-ft` do IT na GG → `discord_tags`; tags HM3 nas outras salas). Definição **ESTRITA** (só `'manual'`, nunca `'auto'` — o `'auto'` é adivinhado pela Vision e seria circular). | **PRIMÁRIA** |
| **(a) lobby aba Info** | print de lobby com a aba **Info** aberta → `vision_json.open_tab='Info'` + `final_table_size` (o **N**). Ancora quando não há tag manual (histórico). | salvaguarda |
| **(b) capturas coerentes** | `_it_ft_boundary`: a 1ª captura IT que apanha **1 mesa** (`sentados==players_left`), com snap + coerência pós-pico. Ancora quando não há tag manual nem lobby Info. | salvaguarda |
| **(none)** | nenhuma das 3 dá sinal → o torneio **não precisa de fronteira** (sem FT do Rui, ou capturas nunca apanharam 1 mesa). `none` é **desfecho correcto, não falha**. | — |

**Porquê esta ordem (decisão do Rui, 7 Jul):** as **tags mandam** — o Rui marca sempre as mãos
de FT, logo a tag manual é o sinal mais fiável do arranque; os **lobbys/capturas são
salvaguarda** para o histórico sem tags. A fonte (0) VAZIA **não mata** o torneio — cai na
salvaguarda (a cascata continua). Ver `REGISTO_CONCEITO 2026-07-07` ("a TAG -ft MANUAL é a
fonte PRIMÁRIA").

---

## 3. Snap-to-N — e a razão física

A fronteira computada por (a)/(b) cai **~1 mão TARDE**: o sinal (print/captura) chega
**38–51 s DEPOIS** de a FT arrancar (gaps reais medidos). O **snap-to-N** (`_snap_to_n`) recua
até **3 min** (`SNAP_WINDOW_MIN`) e passa a fronteira para a **1ª mão REAL da FT**: a mais cedo
com `sentados == N` que **INICIA a drenagem** (==N seguida de mãos ≤N — `_starts_drainage`).

Distingue-se da **mesa pré-FT do Hero** (que volta a SUBIR, ex. …3→7) pela regra do "início da
drenagem" (não-crescente daí em diante). Sem mão ==N na janela → **fallback** à fronteira
computada (segue para o cross-check; mismatch → quarentena, **nunca promove às cegas**).

Efeito validado: o torneio de 2 Jul passou de cross-check **7 vs 6 ✗** para **7 vs 7 ✓**
(fronteira 19:19:27 → 19:18:36).

---

## 4. Guarda pós-pico (late-reg)

A coerência da via-b avalia-se **só na cauda DESCENDENTE PÓS-PICO** (`_post_peak_tail`). O
**pico** da sequência de `players_left` = **fecho do late-reg** (com re-entradas, o pico
final). A **subida ANTES do pico é vida normal do torneio, NÃO incoerência** — o guarda antigo
rejeitava o torneio inteiro (`incoherent_signal`) por causa dela (ex. `35→37→40→52…`). Agora
avalia só do último pico em diante; dentro da cauda mantém-se o rigor (descarte de 1 outlier;
`incoherent_signal` só com 2+ saltos). Só `incoherent_signal` (2+ saltos na cauda) é sinal de
"investigar"; `none` não é.

---

## 5. Salvaguarda do cross-check HH (só GG)

Depois de computada a fronteira, faz-se **cross-check**: o **N** (da fonte 0 via lobby, ou da
via-b) vs os **sentados da 1ª mão ≥ fronteira** na HH (`_cross_check` + `_first_hand_seats_after`).
- **Concordância** (N == sentados) → **"Pronta a aprovar"** (match limpo).
- **Discordância** → **quarentena** ("Precisam de ti"): nunca promove às cegas, nunca descarta
  o torneio.

É **só GG** (a HH GG tem os sentados por mão fiáveis) e dá **cobertura total** ao universo
tagado (toda a mão tem HH). **Limitação conhecida da via-b:** o N da via-b pode ser **menor**
que o tamanho real da FT se a única captura de 1-mesa apanhar a FT já drenada (`#FT-N-FROM-NONGG-LOBBY`
regista o inverso: N de lobby não-GG). A via-a (print Info, N real) é superior.

---

## 6. Convenção do print de lobby POR ABA (Info = marco, nunca payouts)

**Regra de produto (Rui, 7 Jul) — o print de lobby que marca o ARRANQUE da FT é APENAS o que
tem a aba "Info" ABERTA** (lê-se "N players at the final table" no "Table Type"). Prints do
mesmo torneio com outras abas (Players, Prize Pool) são de fora da FT ou já a decorrer e
**NUNCA ancoram a fronteira**.

**Consequência crítica (`#LOBBY-INFO-NO-PAYOUT`):** o print da aba Info **NUNCA escreve
`tournament_payouts`** — na aba Info os prémios não são fiáveis (`#LOBBY-VISION-CHIPS-AS-PRIZES`:
lê fichas como prémios). Continua a resolver o `tn` e a gravar `vision_json`/`players_left` (é
o que o motor FT lê). Os prints das **outras abas** mantêm o comportamento de payouts (D11). O
gate (`_is_info_tab` em `services/lobby_sync.py`) resolve por desenho um bug latente: o print
do Info é sempre o ÚLTIMO do torneio → sem o gate, esmagaria os payouts bons das abas de
prémios (last-write-wins). Ver `REGRAS_NEGOCIO §21` e a **guarda de coerência dos payouts**
(`#PAYOUT-COHERENCE`, `REGRAS_NEGOCIO §22`), que é uma 2ª defesa independente contra Vision
alucinada em QUALQUER aba.

---

## 7. O painel (Saúde GG) — secções e semântica das decisões

A revisão vive na **Saúde GG** (`routers/gg_health.py` F3/F4, `frontend/.../GGHealth.jsx`),
apoiada na tabela **`ft_boundary_review`** (tn PK; status match/mismatch/n_unavailable/
incoherent/none; decision pending/confirmed/corrected/promoted/dismissed; override_boundary/
override_n; decided_by/decided_at). Gate de candidatos apertado: `players_left <= FT_CAP` (=9)
no ramo IT (senão o painel enchia com qualquer captura a meio do torneio — foi o **99→6**).

Secções:
- **"Precisam de ti"** — só o que exige decisão (`none`-com-sinal, mismatch, discordância,
  `n_unavailable`, `incoherent`). É o que o `/summary` conta como `ft_quarantine`.
- **"Prontas a aprovar"** — match limpo (cross-check ✓); ensaio dry-run → aprovar. A cobertura
  parcial (N conservador da via-b) fica **visível** na linha.
- **"Concluídas"** — já promovidas (tags `-ft` escritas).
- **"Dispensados"** — o Rui marcou "sem FT" (Dispensar).

Semântica das decisões (**fixar a fronteira ≠ promover** — 2 passos):
- **Confirmar / Corrigir** — FIXA a fronteira (aceita ou corrige o boundary/N via override) mas
  **NÃO** escreve tags. `decision=confirmed|corrected`.
- **Promover** — o 2º passo explícito: ensaio dry-run → **Escrever** → `decision=promoted`
  (escreve as tags `-ft`). Só aqui há escrita.
- **Dispensar** — escreve **SÓ na `ft_boundary_review`** (`decision=dismissed`). **NÃO** toca
  nas mãos, tags, `study_state` nem vilões. Reversível com sinal novo forte.

---

## 8. Gatilhos automáticos vs escrita só-por-aprovação

- **Cálculo automático (nunca escreve tags):** `refresh_ft_boundaries` corre **fire-and-forget**
  após cada import (`import_`, `import_hm3`, `tournament_summaries`) e reconcile — recomputa a
  fronteira e sincroniza a review **respeitando decisões**: `promoted` não recalcula;
  `confirmed`/`corrected` ficam fixados; `dismissed` só renasce com **sinal novo forte**
  (`has_new_ft_signal` = tag manual OU print Info); `pending` → snapshot. Idempotente; o gate
  apertado (≤ FT_CAP) evita peso nos imports.
- **Escrita (tags `-ft`):** **SÓ** pelo fluxo **Aprovar → dry-run → Escrever** (§7). Nenhum
  gatilho automático escreve tags. `refresh_ft_boundaries` foi validado read-only (8 Jul): não
  ressuscita dispensados sem sinal, não mexe em promovidos.

---

## 9. F6 — re-solve das HRC stale (DORMENTE)

Quando uma mão passa a `-ft`, o seu solve HRC anterior (feito com as regras base) fica **stale**
e devia ser re-solvido com as regras FT. **F6 dorme** (8 Jul: 0 solves afectados — as mãos de FT
na lab data estão sem tag base ou já `-ft`). Acende quando aparecer a 1ª mão FT com solve HRC.

---

## 10. Mapa de código

| Peça | Ficheiro |
|---|---|
| Motor da cascata + snap + pós-pico + cross-check + review | `backend/app/services/ft_boundary.py` |
| Vision `open_tab`/`final_table_size` (aba Info) | `backend/app/services/lobby_vision.py` |
| Gate do Info (não escreve payouts) | `backend/app/services/lobby_sync.py` (`_is_info_tab`, `process_lobby_message`, `reconcile_lobby_logs`) |
| Guarda de coerência dos payouts | `backend/app/services/payout_coherence.py` |
| F3/F4/F5 endpoints + painel | `backend/app/routers/gg_health.py`; `frontend/src/pages/GGHealth.jsx` |
| Gatilhos F&F | `routers/import_.py`, `routers/hm3.py`, `routers/tournament_summaries.py`, `routers/lobbys.py` |

**Antes de mexer no motor:** ler `services/ft_boundary.py` + `REGISTO_CONCEITO 2026-07-07/07-08`.
Escrita das tags `-ft` **só por aprovação manual**. O **wipe+reimport** é o teste de aceitação
de toda a frente (as `-ft` entram a sério quando as mãos de FT chegarem com tags base).

> **Irmã da FT:** a **quarentena de nomes** da propagação por hash (`name_quarantine_review`,
> `NamePropagationPanel`, APA §B.6 Fase 3) segue o MESMO padrão desta frente — secção na Saúde GG,
> decisões persistidas e respeitadas por re-runs, escrita manual nos casos de conflito. Motor em
> `services/name_propagation.py`; ver `DESANON_ANATOMIA §3.4`.
