# DESANON_ANATOMIA — anatomia consolidada da desanonimização GG

**Sítio canónico** da desanonimização das mãos GGPoker (anónimas → nicks reais).
Consolida o que estava disperso por `JOURNAL_2026-06-13-pt71.md`, `JOURNAL_2026-06-14-pt72.md`,
`REGISTO_CONCEITO.md` (entradas 2026-06-13/14) e o código (`services/table_ss_deanon.py`,
`services/table_ss_vision.py`, `routers/screenshot.py`, `routers/table_ss.py`).

**Leitura obrigatória antes de mexer no match/desanon GG** (cross-ref `CLAUDE.md`).

---

## 0. As DUAS perguntas — manter SEMPRE separadas

A desanon parte-se em duas perguntas independentes. Confundi-las cria a ilusão de que
resolver uma resolve a outra — **não resolve**.

| | Pergunta | O que responde | Sinal usado | Estado |
|---|---|---|---|---|
| **P1** | **QUAL é a mão?** | Liga a captura (SS) à mão GG certa na BD | hand_id / tempo / nome | ver §2 |
| **P2** | **QUEM senta em que cadeira?** | Mapeia cada hash anónimo → nick real, na cadeira certa | âncora + stacks | ver §3 — **NÃO fechada** |

> **Por que importa a separação:** o hand_id do filename (decisão pt73, §2) resolve **só P1**
> — diz qual é a mão, **não** quem são os jogadores. P2 continua a precisar de uma âncora
> própria e é a origem do **bug dos vilões em cadeiras trocadas**. Acertar P1 não corrige P2.

---

## 1. Fontes de nomes reais para a GG anónima

A HH GG é matematicamente exacta mas **anónima** (jogadores = hashes tipo `89ef4cba`).
Os nomes reais vêm de uma de duas capturas:

1. **Replayer-SS (Discord)** — `og:image` da página partilhada da pokercraft, lida por Vision.
   **DESCONTINUADO (pt72):** a GG migrou a página para SPA Angular sem `og:image` → o
   fetch+regex (único mecanismo que sempre existiu) extrai 0 em todas as idades. A via
   screenshot/headless foi investigada e **descartada**. Ver `#REPLAYER-OGIMAGE-DEAD-SPA`.
2. **Table-SS (Intuitive Tables)** — captura do feltro da própria mesa, com os nicks reais
   por banco. **É AGORA a única fonte de desanon GG** (pt72). Vision lê
   `seats[{nick, stack_bb, bounty, is_hero}]` por banco (`table_ss_vision.py`, pt71 E1).

---

## 2. Pergunta 1 — QUAL é a mão (match captura ↔ mão GG)

### 2.1 Replayer-SS ↔ HH (por TM)
Match por `hand_id = GG-{TM_number}`, com o TM extraído do nome do ficheiro do SS
(`screenshot.py`). Determinístico. Não afectado pela decisão pt73 (já era por hand-id).

### 2.2 Table-SS ↔ mão GG

> **★ DECISÃO pt73 (DECIDIDO / POR IMPLEMENTAR — ainda NÃO no código).**
>
> **PRIMÁRIO:** **hand ID extraído do nome do ficheiro** — o número TM imediatamente antes
> do timestamp. Ex.: `...6081471864-20260615223557-127.png` → `GG-6081471864`.
> Determinístico, sem Vision, sem tempo, sem stack. Confirmado nas HH (`#TM6081471864`,
> `#TM6079987069` batem exactamente).
>
> **Substitui** o match actual por **tempo + nome + fingerprint**, que é frágil: a captura
> é tirada **segundos DEPOIS** do início da mão → em multi-tabling (média 3.2 torneios GG
> concorrentes na janela ±5min, até 8) a hora sozinha erra a mão por segundos (a mais
> próxima no tempo pode ser de OUTRA mesa).
>
> **FALLBACK:** torneio + mesa + tempo **SÓ** quando o ID falta no nome (formato antigo,
> ex.: `...Table 171_!)-20260605201233-19` sem TM — ver `img/89`).

**Estado HOJE no código (até a decisão ser implementada):** o table-SS casa por uma função
determinística `compute_table_ss_match` (`table_ss.py`, pt50), **por tempo** (janela ±5min),
com:
- **Site** lido do **nome do ficheiro** (`_site_from_filename`, pt56) — autoritativo sobre a Vision.
- **`tournament_number`** já extraído do filename no formato novo (`parse_table_ss_filename`, pt60).
- **Desambiguação multi-tn** por **nome fiel** da imagem (`name_tokens_subset`, pt54/pt58) e,
  no plano `PLAN_2026-06-02-table-ss-gg-match.md`, **fingerprint** (hero_stack_bb ±20% + big_blind).

A decisão pt73 torna o **fingerprint e o nome-directo obsoletos/reduzidos a fallback** para
o caso GG com TM no nome — passam a ser usados só quando o hand_id falta (ver
`#TABLE-SS-GG-MULTITABLING-MATCH`).

---

## 3. Pergunta 2 — QUEM senta onde (hash → nick → cadeira) — **NÃO fechada**

O hand_id resolve P1 mas **não traz nicks**. Para pôr cada nick real na cadeira certa é
preciso uma âncora própria. Hoje a âncora é por **stack**.

### 3.1 Maquinaria actual (por stack — herança do pt7)
`deanonymize_hand_from_table_ss()` (`table_ss_deanon.py`, pt71 E3) reutiliza
`_build_anon_to_real_map` + `_enrich_all_players_actions` do pt7 (`screenshot.py` intocado):
- Âncora **Hero** (centro-baixo) + **folds por stack** (`stack_ss ≈ stack_hh − ante`, tol. <2%)
  + **eliminação/permutação óptima** para os restantes.
- Marca `match_method='table_ss'` (no replayer-SS é `anchors_stack_elimination_v2`).

### 3.2 O BUG dos vilões em cadeiras trocadas (aberto)
A permutação por stack **troca dois jogadores de stacks próximos / all-in** entre cadeiras.
Nome trocado = **veneno** (envenena fichas de vilões via tag `nota`). **P2 NÃO está fechada.**

**Como se chegou ao número (pt73):** o bug foi **detectado visualmente pelo Rui** (`img/89`,
`GG-6042783089`); o Code correu então um **scan de fit** (stacks da Vision vs stacks da HH)
sobre a BD pt73 → **66/185 misfit**, **6 com wrong-hand flagrante**, **119 fiáveis**. O 36% é
**o resultado do scan**, não uma estimativa — a detecção foi do Rui, a quantificação foi o fit.

**Âncora futura (a especificar pelo Rui):** o **disco do dealer / botão** como âncora
posicional, em vez de (ou além de) o stack. Ainda por desenhar.

### 3.3 Mitigações já no sítio (reduzem, não resolvem)
- **Guarda anti-envenenamento** (`_filter_ambiguous_stackless`, pt71): ≥2 bancos não-herói
  **sem stack utilizável** (all-in/null) ficam **POR MAPEAR** (hash mantido) +
  `player_names.deanon_partial=true`. **Nome em falta é honesto; nome trocado é veneno.**
- **Votação cross-mão por torneio** (`vote_tournament_maps` / `reconcile_tournament_deanon`,
  pt71 E6), fundada no **invariante observado-e-vigiado: o hash GG é fixo por jogador
  DENTRO do torneio** (forense Jun-2026: 0 violações cross-torneio em 1059 hashes). A maioria
  por torneio corrige swaps do per-mão; cada captura nova acrescenta um voto e retro-corrige.
  Vigiada na Saúde do Import (`capture_deanon_agreement`).

> **⚠️ LIÇÃO — "0 swaps cross-torneio" NÃO é prova de correcção.** A votação prova
> **consistência** (o mesmo hash recebe o mesmo nome em todas as mãos do torneio), **não**
> que o nome esteja **certo**. Se a SS estiver mal-ajustada de forma **correlacionada** (ex.:
> o mesmo desalinhamento de cadeira repete-se nas várias capturas do torneio), a maioria fica
> **consistentemente errada** — e a votação consente nesse erro em vez de o apanhar. O teste
> que de facto valida a correcção é o **fit** (stacks Vision vs stacks HH, §3.2), não o
> agreement da votação. Consistência ≠ correcção.

---

## 4. Mapa de código

| Peça | Ficheiro |
|---|---|
| Vision do table-SS (seats por banco) | `backend/app/services/table_ss_vision.py` |
| Match table-SS ↔ mão (P1) | `backend/app/routers/table_ss.py` (`compute_table_ss_match`, `reconcile_table_ss`) |
| Parser do filename (site, tn; **TM = pt73**) | `parse_table_ss_filename` (`table_ss.py`) |
| Desanon hash→nick (P2) + votação | `backend/app/services/table_ss_deanon.py` |
| Maquinaria base pt7 (âncoras/stacks) | `backend/app/routers/screenshot.py` (`_build_anon_to_real_map`) |
| `match_method` (rótulo do cruzamento) | `MAPA_ACOPLAMENTO.md §2.1` |

## 5. Cross-refs
- `REGRAS_NEGOCIO.md §2.2` (Match) · `MAPA_ACOPLAMENTO.md §2.1/§2.2` · `REGISTO_CONCEITO.md` (2026-06-13/14/16)
- `JOURNAL_2026-06-13-pt71.md` (pipeline 6 estágios + votação) · `JOURNAL_2026-06-14-pt72.md` (replayer morto)
- Tech debts: `#TABLE-SS-GG-MULTITABLING-MATCH`, `#REPLAYER-OGIMAGE-DEAD-SPA`, `#TABLE-SS-DEANON-*`
- `PLAN_2026-06-02-table-ss-gg-match.md` (superseded em P1 pela decisão pt73)
