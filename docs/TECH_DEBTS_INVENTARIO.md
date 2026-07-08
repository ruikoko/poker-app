# Inventário Tech Debts — 4-Mai 2026 pt13 (fechada)

Compilação read-only baseada em journals (23-24 Abr → 29-Abr pt6), VALIDACAO_END_TO_END §6/§7/§11, MAPA_ACOPLAMENTO, git log, e leitura directa do código.

Substitui os fragmentos espalhados pelos vários docs como **single source of truth** sobre tech debts pendentes. Para descrição detalhada de cada fix fechado, consultar journal/commit correspondente.

---

## 7–8 Jul 2026 — frente FT (F1–F5) + core aprovado (apa-por-hash) + Fase 1 leitores

Sessão longa. Frente FT construída por inteiro e LIVE; decisão do core APROVADA + Fase 1
(leitores). Detalhe: `JOURNAL_2026-07-08.md`, `FT_BOUNDARY_ANATOMIA.md`, `APA_INDEXACAO_E_COLAPSO §B.6`.

**Fechados:**
- ✅ **CORE apa-por-hash CURADO (Fases 1-3 LIVE)** — `d9c504f` leitores → `dc20ad1` writer →
  `2c8fe8a` propagação + quarentena de nomes. Fecha a fusão de seats (MaLong07/4321) e a queda de
  lugares por desenho; propaga nomes fortes pelos brancos das tagadas. Teste de aceitação = wipe+reimport.
  Scope futuro (LOW, registado): `#APA-WEAK-TO-STRONG-UPGRADE` (propagação preenche só brancos, não
  faz upgrade de nome fraco→forte) + `#APA-GOLD-ONLY-TRIGGER` (upload Gold-só usa o botão "Aplicar
  propagação"; hooks de import cobrem o normal). `#OCR-MERGE-GOLD-CROWN-UNSAFE` resolvido com
  `_ocr_variant` endurecido (distância de edição, rejeita colisão de 1º nome).
- ✅ **`#FT-ENSAIO-VIA-F3-ENDPOINT`** — os ensaios da FT correm por `GET /api/gg-health/ft/preview`
  (mesmo caminho da app), não por script local/proxy. (F3, 8 Jul.)
- ✅ **`#RAILWAY-TOKEN-SHORT-LIVED`** (mitigado) — DB reads passam por `~/.pokerapp_db_ro.env`
  (URL público, só-leitura, fora do repo); deploys por OpenAPI/liveness. Railway CLI dispensado
  do fluxo. Causa provável: access token TTL 1h + refresh partido server-side (CLI inalterado).
- ✅ **Gate de candidatos FT 99→6** — o ramo IT do `_candidate_tns` passou de `players_left IS NOT
  NULL` (qualquer captura) para `<= FT_CAP`; corrige a lista impossível e a lentidão do painel.

**Abertos / registados:**
- 🟡 **`#LOBBY-VISION-CHIPS-AS-PRIZES`** — a Vision do lobby na aba **Info** lê fichas como prémios
  (caso Daily Hyper $60, print `-101`). Motiva o gate `#LOBBY-INFO-NO-PAYOUT` (§21). Não escreve
  payouts do Info → sem sintoma; fica registado p/ quando/se se quiser payouts multi-aba robustos.
- 🟡 **`#NORAISE-ANCHOR-POSITION-MISLABEL`** (pré-existente, `queue_export`) — `test_noraise_anchor`
  falha (`'UTG' == 'MP'`): âncora de mão sem raise etiqueta a posição errada. Baseline registada
  na secção abaixo (7 Jul). Não é da FT nem do apa.
- 🟢 **`#FT-GUARD-BY-LOBBY-STATUS`** (futuro) — reforçar o guarda pós-pico com `tournament_status`
  (Late Reg./Running) do lobby. Ver `PENDENTES` (melhorias futuras FT).
- 🟢 **`#FT-N-FROM-NONGG-LOBBY`** (futuro) — N direto do lobby nas salas não-GG (âmbito atual: só-GG).
- 🟢 **OCR-merge da Fase 3 do core** — os conflitos "mesmo-hash→nomes-dif" do dry-run (9 casos) são
  variantes OCR/truncação do mesmo nome → resolvem-se na **Fase 3** com matching tolerante
  (família do `#GOLD-CROWN-CARRY-NAME-TRUNCATION`): auto-merge se inequívoco, 1-clique senão. Os
  "nome→2-hashes" (8) ficam quarentena pura. Ver `APA_INDEXACAO_E_COLAPSO §B.6.6`.

## 7 Jul 2026 — baseline de testes: âncora sem-raise erra a posição (pré-existente)

| Tech debt | Estado | Resumo |
|---|---|---|
| **#NORAISE-ANCHOR-POSITION-MISLABEL** | 🔴 aberto · **pré-existente** (não no baseline conhecido) · investigação diferida p/ depois da frente FT | **Sintoma:** `test_noraise_anchor.py::test_nonblind_limp_before_hero_returns_none` (linha 101) falha — `_resolve_position_for_nick(hh, "P1")` devolve **`'UTG'`** onde o teste espera **`'MP'`** (`assert 'UTG' == 'MP'`). Layout: 6-max, **Hero=BTN**, P1 limpa (call não-blind) antes do Hero. A resolução de posição da **âncora sem-raise** (`derive_noraise_anchor`/`_resolve_position_for_nick` em `services/queue_export.py`, feature **pt86c**) **rotula mal a cadeira**. Neste caso concreto o `derive_noraise_anchor` ainda devolve `None` (limp de não-blind → nó não modelado), mas o helper de posição está **factualmente errado** e a posição alimenta as **leis de âncora/offset do HRC** — **âncora em posição errada é o veneno real** (`REGRAS_NEGOCIO §16`; cai fora do ponto de decisão certo → âmbito errado = lixo, tal como `#HRC-NODE-OFFSET-IMPLICIT-LINES`). **Provado PRÉ-EXISTENTE (não introduzido pela F2):** `git stash` das mudanças F2 + correr o teste no HEAD limpo (`8a3d75c`) → **falha idêntica** (`assert 'UTG' == 'MP'`, `+ UTG`). **Não estava no baseline conhecido**, que os journals descreviam como **só Postgres-local** (5 falhas de `OperationalError` sem BD local) — esta 6ª é **lógica pura**, não de ambiente, e passou despercebida. **Âmbito:** só o caminho da âncora sem-raise; não toca a frente FT. **Próximo:** investigar a derivação de posição em `queue_export` (contagem de cadeiras a partir do BTN vs blinds em 6-max) **depois** da frente FT. Descoberto na suite da F2 (7 Jul). |
| **#LOBBY-VISION-CHIPS-AS-PRIZES** | 🟡 aberto · **NÃO bloqueia a FT** | **Sintoma (caso real, Daily Hyper $60 2 Jul, print `-101` das 19:19:27):** a Vision do lobby (`lobby_vision`, Claude) leu as **FICHAS dos jogadores da lista** (`269061, 242139, …`) para o campo `prizes` **1-7** (deviam ser os prémios em €/$ por posição), e o `start_time_iso` saiu **2024** (ano errado). O print irmão `-100` (19:19:25) leu os prémios **bem** → é intermitência da Vision naquele layout, não bug determinístico. **Impacto:** (a) prémios errados no `vision_json` desse print → se resolvesse torneio, escreveria `tournament_payouts` com prémios das fichas; (b) `start_time` 2024 fura a janela do resolver → tende a `tm_not_found`. **NÃO afecta a frente FT:** o motor só lê `open_tab`/`final_table_size` do print do Info; o refresh-only (`#LOBBY-FORCE-REVISION`) **não escreve payouts**. **Próximo (à parte):** endurecer o prompt para distinguir **fichas do lobby** (números grandes na coluna de jogadores) de **prémios** (moeda por posição) + validar `start_time` (ano ≥ 2026). Registado hoje (7 Jul), diferido. |

## 2 Jul 2026 — desanon: sentado-sem-cartas (N+1) sem guarda universal

| Tech debt | Estado | Resumo |
|---|---|---|
| **#DESANON-SITTING-OUT-NPLUS1-NO-UNIVERSAL-GUARD** | 🟡 aberto (buraco) · 1 mão consertada à mão | **Sintoma (caso `GG-6083771298`):** um jogador **sentado-mas-sem-cartas** na Gold (`Afonso Neto`, acabou de sentar, `position=null`) faz a Vision ler **N+1 nomes** (6) vs **N cadeiras** da HH (5). O `position_v3` (por RÓTULO) **descartou-o bem** → `anon_map` **correcto**; mas o `all_players_actions` ficou **corrompido** por **outro caminho (order/stack)** que **deslizou** os nomes uma posição e **colapsou** um seat (5→4, `Afonso Neto` injectado no BB, SB perdido). **Porque a salvaguarda img≠HH não apanhou:** essa guarda (contagens img≠HH → alarme) vive **SÓ no método ÂNCORA do table-SS** (`build_anon_map_by_hero_button`, pt96); o **`position_v3`** e o **caminho order/stack** que escreveu o apa **não têm** guarda N+1 nenhuma. **Dois buracos:** (1) a protecção N+1/img≠HH **não é universal**; (2) **não há invariante apa↔anon_map** — uma mão pode ficar `deanon_status=verified` (via `match_method`) com o apa **silenciosamente inconsistente** com o `anon_map` (correcto). O `/set-anon-map` **tem** o check anti-fusão (enriched==hashes) mas o caminho normal de enrich/relink **não o impõe**. Era a **"1 diverge"** residual do `#DESANON-GOLD-SCRAMBLE` (o gate `_stack_gate_ok` divergiu — `#GOLD-STACK-CHIPS-UNIT-INCONSISTENT`/`#GOLD-STACK-MOMENT-END-NOT-START`). **Consertada à mão (2 Jul)** via `/set-anon-map` (5 seats certos + coroas do Rui UTG→BB 109.37/50/81.25/50/68.75); efeito colateral: `match_method` `position_v3`→`table_ss`/`manual_blinds_override` (badge verified→unverified). **Fix próprio (futuro):** N+1/img≠HH como sinal duro em TODOS os caminhos de desanon + assert apa↔anon_map (seats == hashes da HH) pós-enrich/relink; e ponderar preservar `position_v3` (ou aceitar override manual como "verified") no `/set-anon-map`. Detalhe: `DESANON_ANATOMIA §3.2.4`. |

## 1 Jul 2026 — 2 frentes de QUALIDADE DE DADOS GG (bounties + desanon por âncora)

| Tech debt | Estado | Resumo |
|---|---|---|
| **#TABLE-SS-BOUNTY-UNDERREAD** | ✅ FIXED (`824f23d`) + histórico 10/13 | A Vision do table-SS lia a **CHAMA (VPIP %)** para o `bounty_usd` (coroa $) — o prompt nem mencionava a chama → **77/278 PKO table-SS GG (28%)** com ≥1 bounty mal lido. Regra: coroa = KO instantâneo = **metade → nunca < base÷2** (GG/PS). Fix: prompt afinado (coroa$ vs chama%, **sem campo VPIP gravado**) + **guarda dura** `bounty_below_half_base` em `queue_export.build_queue_zip`. **Verde de KO** documentado (CLAUDE.md armadilha — eliminado → bounty a verde na coroa de quem o elimina, total=verde×2). A Vision lê a **original** no upload (compressão só p/ guardar). Histórico: **10 consertadas** (SS original full-quality de Transferências) fora da quarentena; **1 presa** (`6102580840`, seat `G Sieemshchikov`); **2 por rever** (`6101135610`, `6104865113`); 5 seats truncados por-rever. |
| **#DESANON-HERO-BUTTON-ANCHOR** | ✅ FIXED (`72eaedc`) — **15/15, bug a 0** | Substitui o **stack-elimination** (trocava nicks em stacks próximos → 15 mãos com vilão=nome do Hero) pela **âncora Hero+botão + ordem circular**. Detalhe: `DESANON_ANATOMIA §3.2.3`. Vision estendido (`is_hero` POSICIONAL sem cartas + `is_button` + ordem circular); **stacks SÓ p/ a direcção** (nunca mapeiam nomes); Hero nunca a vilão; **salvaguarda** (img≠HH/direcção indecisa → alarme, não escreve). 19 testes. **Só GG.** |
| **#STUDY-STATE-REGRESSION-HH-IMPORT** (8549) | **Decisão: Opção A (DEIXAR)** | As 8549 GG-sem-SS em `new` são **inócuas** (escondidas do Estudo pelo gate `match_method`+tag; 851 visíveis = 440 GG+SS + 395 WN + 14 WPN + 2 PS). **Mover→`mtt_archive` PRENDIA-AS** — as queries do table-SS têm `!= mtt_archive` (`table_ss.py:376/397/1396`) → o SS não as apanharia. **Opção B só COMPLETA (3 peças: migração + fix da entrada `import_.py:343/367` + tirar `!= mtt_archive` + promover archive→new na desanon)** em sessão dedicada — **NUNCA parcial**. |
| **#HRC-FOCUS-ROBUSTNESS** | ⏸ código em `watcher-gate` (`049cd4b`), **NÃO buildado** | Foreground garantido antes de cliques críticos (Play/export) + retry. As 6 falhas foco/timing da corrida pt94. **Junta ao próximo build do watcher** (com a guarda de tempo). |
| **#GOLD-STACK-CHIPS-UNIT-INCONSISTENT** | 🟡 aberto · **decisão: unidade canónica = FICHAS** | O campo `players_list[i].stack_chips` da entry Gold (replayer) **não tem unidade consistente**: nalgumas mãos guarda **BB** (`GG-…670` → 7), noutras **fichas** (`GG-6108178648` → 136084), noutras **vazio/None**. A Vision lê o número do avatar sem saber se é stack em fichas ou já em BB. **Decisão (Rui, 2 Jul): a app usa FICHAS internamente** (é o que o parser já guarda em `all_players_actions[*].stack`; `stack_bb` é derivado). Gate do re-enrich compara **em fichas** (Gold vs HH-final), com fallback unit-agnóstico (`≈ HH_fichas` OU `≈ HH_bb`) **só** como defesa dos dados Gold legados mistos. Fix próprio (futuro) = normalizar na Vision à leitura (distinguir fichas vs BB) e gravar sempre fichas. Não corrompe dados (campo de leitura auxiliar). **⚠️ ver `#GOLD-STACK-MOMENT-END-NOT-START`.** |
| **#DESANON-GOLD-SCRAMBLE** | ✅ FIXED (`d8a3fb5`) — 34 escritas, 2 resíduo Karluz | Mãos Gold (position_v3) com `all_players_actions` STALE (nomes trocados de cadeira / vilões largados como hash). **anon_map guardado está certo** → reconstrói o apa do RAW (`parse_hands`, recupera vilões largados) + re-enrich por anon_map+seat + re-carga das coroas (guarda ½-base), só as que passam o **gate de fichas FINAIS**. Endpoint `POST /api/screenshots/reenrich-scrambled-gold` (dual-auth, dry_run). **Realmente partidas = 37** (não 114 — o resto era truncagem/OCR do mesmo nome, `_same_player`). **Escritas 34** (11 vilões recuperados, 128 coroas); **332→327 limpas**. **Resíduo (2, caso-a-caso): `GG-6113127853`/`GG-6113686726`** — o anon_map mapeia **`"Karluz"` a DOIS seats** (`"Hero"→"Karluz"` + um hash→"Karluz"); como o apa é indexado por nome, os dois colidem e um seat é esmagado (fica 4 em vez de 5). É **nome duplicado no anon_map** (Vision leu um vilão como "Karluz"), não falha do re-enrich. **3 não escritas** (1 sem-stack `GG-6083437454` → **fechada** — hoje 4/4 seats mapeados + apa limpo, o "sem-stack" já não se aplica, 1 diverge `GG-6083771298` → **RESOLVIDA à mão em 2 Jul via `/set-anon-map`** — ver `#DESANON-SITTING-OUT-NPLUS1-NO-UNIVERSAL-GUARD`; **⚠️ resíduo: o `players_list` mantém `Afonso Neto` (coroa 0.0, sentado-sem-cartas) → a guarda de suspeitas lê `players_list` e marca-a falsamente `bounty_below_half` (floor 25). Falta primitiva "excluir jogador do players_list" / a guarda só devia contar seats mapeados**, 1 anon_map incompleto `GG-6116735459` → **RESOLVIDA à mão em 2 Jul via `/set-anon-map`** — `885023a9`=`Haarlem 91` confirmado por eliminação de posição + fingerprint de stack único 17.4≈17.3 bb; apa reconstruído 5→6 seats). |
| **#DESANON-HERO-FRIEND-NICK-ACCEPTED** | ✅ FIXED (`95a71ee`) + 2 mãos corrigidas | O campo `hero` da Vision às vezes lê o nick de um **vilão-amigo** (Karluz/flightrisk) como sendo o Hero (`raw_vision` literal **"HERO: Karluz"** em `GG-6113127853`/`GG-6113686726`). Como os FRIEND_HEROES estavam em `_KNOWN_HERO_NICKS` (via `HERO_NAMES_ALL`), o guarda **aceitava** → `anon_map["Hero"]="Karluz"`, colidindo com o vilão real (o apa, indexado por nome, **fundia** os 2 seats "Karluz" num só). **Causa: Vision (campo hero) + whitelist**, não o `players_list` (que lia `Karluz@BB` e `Lauro Dermio@null` **certos**). Fix: **friend-heroes fora de `_KNOWN_HERO_NICKS`** → o guarda rejeita e deixa lacuna honesta. **Raio medido: 0 Gold legítimas** com Hero=friend (as 2 eram o bug). As 2 mãos **corrigidas via `/set-anon-map`** (Hero→Lauro Dermio): 5 nicks distintos, Karluz vira vilão no BB com o SEU stack/coroa, sem fichas falsas (Karluz foldou o BB → Regra D não dispara, correto). **Cue fiável por explorar: o texto do Hero na gold é AMARELO** (upgrade do prompt da Vision, precisa re-Vision). |
| **#GOLD-CROWN-CARRY-NAME-TRUNCATION** | ✅ FIXED (`ce4ff1a`) — 124 recuperadas | A carga de coroas por NOME casava apa↔Gold por **igualdade exacta**; apa completo (`vunzigeviktor`) vs Gold truncado (`vunzigevikt..`) não batia → coroa perdida (fallback por posição não salva — a Gold não traz `players_by_position`). Fix: `backfill_gold_bounties` casa por `_same_player` **quando o nome exacto está AUSENTE** (protege Hero-0 presente-com-0 + já-preenchidas), **match único obrigatório** (ambíguo → não escreve), guarda ½-base mantida. Corrida real: **124 recuperadas / 63 mãos, todas via truncagem, 0 ambíguas, 0 já-preenchidas alteradas**; VAZIAS 124→0. Agrupamento de vilões não afetado (0 pares fragmentados — propagação por hash é segura). |
| **#GOLD-STACK-MOMENT-END-NOT-START** | 🟡 aberto (corrigido no gate) | As fichas que a Gold mostra por jogador são as do **FIM da mão** (todos já sem o ante; quem ganhou o pote já com ele somado). A HH (linhas `Seat N:`) dá as fichas do **INÍCIO**. Comparar Gold(fim) com HH(início) dá falsas divergências — sobretudo em folders short-stack tarde (ante é % grande do stack). **Gate corrigido:** deriva as fichas **FINAIS** da HH por jogador — `final = inicial − ante − apostas(comprometido por street) + uncalled + ganho(collected)` — e compara a Gold contra essas. Informação do Rui (2 Jul). |

## pt92 (29-30 Jun 2026 — índice de navegação, fila manual, painel rápido, ICM, FT)

**Tudo LIVE em produção.** Sessão grande: fix do índice de navegação do HRC (`#OFFSET-WITHIN-BUCKET-JAM`) + re-process das mãos contaminadas, fila HRC 100% manual, painel `/hrc` rápido, ICM via TS, regras de sizing pt91, regras de FT seladas (a implementar).

### Índice de navegação do HRC (2ª run / Selected Subtree)

| ID | Sev | Resumo |
|---|---|---|
| `#OFFSET-WITHIN-BUCKET-JAM` | ✅ **FIXED (commit `db16888`)** | **Descoberto por verificação VISUAL do Rui** (o realce caía no **BTN** em vez do **CO**). **Problema:** o `offset_within_bucket` (`hrc_node_offset.py`) assumia layout **FIXO** no bucket do abridor (jam non-SB→1, SB jam→2). Quando o abridor abre em **ALL-IN/jam curto** e o bucket **COLAPSA para 1 linha** (Regra 1, eff≤9; ou o size **É** o all-in → array `[ALLIN]`), o código contava **+1 linha** → o realce caía **SEMPRE uma posição À FRENTE** do abridor (ou no **clamp** da última linha, escondendo o erro na SB). **Padrão:** erra **só** quando o abridor abre em jam; acerta sempre em min-raise deep. **Fix:** o `offset_within_bucket` passa a **DERIVAR** o nº real de linhas chamando `count_lines_for_position` (a **mesma** lógica de colapso da Regra 1 que já conta as posições anteriores). `within = count_lines(abridor)-1` (jam) / `0` (Complete/small non-SB) / `1` (SB small). Os **três** sítios — template `shouldAddPreflopAllIn`, `count_lines_for_position`, `offset_within_bucket` — partilham **UMA** lógica de contagem → não podem divergir. **Variante uniforme** (SB jam 14→13; cosmético — a SB é a última linha, **mesmo landing**; alinha com a árvore real). **+4 testes regressão; suite 1144 passed; validado tree-a-tree em 5 mãos** (as 2 que erravam — `WN-…-13`, `GG-6114196293` — caem agora no **CO**). **Importância:** prepara o FT — como o offset deriva da contagem, quando o FT mudar a contagem (template+count_lines juntos), o offset segue automaticamente. |
| Re-process das contaminadas | ✅ **FEITO (commit `b15129e`)** | **Scan:** das **110** done, **46** tinham abridor em all-in (**34** caíram na posição errada — resultados maus — + **12** SB-última, clamp provavelmente salvou, re-processadas por garantia); as outras **64** (min-raise deep) estavam certas, intocadas. **Mecanismo:** `POST /api/queue/hrc/reset-done` (aceita **SÓ** a lista de IDs confirmados — **NUNCA** reset geral) + coluna `hands.reprocess_reason` + separador **"↻ Re-processar (offset corrigido)"** no painel `/hrc` com "selecionar todas". **As 46 repostas** (reset 46, skipped 0; 46 re-elegíveis, 64 done restantes). Rui seleccionou e enviou as 46 ao HRC — a processar na noite de 30/06. **PENDENTE: confirmar que ficaram boas.** |
| `#HRC-EXPORT-DIALOG` | 🟡 **NOVO — registado, não prioritário** | `WN-4872606583034478607-2` (ZENITH nível 23) falhou no export (**"Save-As não persistiu em 180s"**). Bug de **UI do export do HRC**, **NÃO** índice nem RAM. `job=failed`, sem zip. |

### Fila HRC + painel `/hrc`

| ID | Sev | Resumo |
|---|---|---|
| Fila HRC 100% MANUAL | ✅ **FEITO (commit `84bd63b`)** | **"Disparar tudo" REMOVIDO** (botão + `POST /trigger`); gate → **contadores**; novo `POST /hrc/clear-released` ("Limpar fila"); `select_andar1_rows` **exclui mãos set-aside** (`hrc_jobs.meta_json.set_aside='true'`). Reset operacional: 124→0. ⚠️ **ABERTO:** falta **gatilho UI para "pôr de lado"** (exclusão armada, sem botão). |
| `#HRC-QUEUE-SLOW-OPEN` | ✅ **FIXED (commits `2f463d7` ① + `f2be50e` ②)** | Abertura do painel `/hrc` **~14s** porque o `GET /hrc/verify` puxava **~809 MB** de result_zips (106 done) + parse a **CADA** abertura, a crescer com cada mão feita. **①** verify **FORA** da abertura → botão "Verificar resolvidas" (abertura **~14s→~0,4s**). **②** cache `hrc_jobs.verify_json` (eager no `POST /results` + lazy backfill) → `/verify` **16s→0,4s** (provado). **+3 testes.** |

### ICM + sizing pt91

| ID | Sev | Resumo |
|---|---|---|
| `#ICM-CHIPS-USE-TS-FINAL-FIELD-GG` | ✅ **FIXED (commit `842d64f`, merge `3d24df0`)** *(reclassifica o "SÓ REGISTADO" da secção 29 Jun abaixo)* | O `chips` do `payouts.json` (total de fichas p/ ICM) vinha da estimativa do lobby (subconta em registo tardio); passa a **`total_players` (do TS) × stack inicial** (1ª mão **fresca**: Nível 1, stacks iguais e redondos), **GG+TS only**, override em `build_queue_zip` + auditoria no manifest (`icm_chips_source`). WN/PS/WPN e GG-sem-TS inalterados. **Validado:** tn 292447656 → 1 409 980 → **1 510 000**. **+18 testes.** |
| `#SQUEEZE-LIVE-CALLER-PT91` | ✅ **FIXED (commits `d64f47e`/`df93989`/`08757c9`, merge `1c958a5`)** | Regras de sizing pt91: 3 regras do Rui + **preservação da ação real** + mirror do offset + **fix do squeeze** — um shortie all-in atrás (side-pot) deixa de disparar o squeeze fixo; cai no 3bet normal (helper `hasLiveNonAllInCaller`). |

### Pendentes (definidos, NÃO em produção)

| ID | Sev | Resumo |
|---|---|---|
| Regras de FT (open) | 🔵 **DEFINIDAS e SELADAS — a implementar** | Em `project_ft_open_sizing_rules_pending.md`. **Implementar SÓ depois** das 46 re-processadas confirmadas. **FT-1 (limiar):** tag `-ft` → `IS_FT` → open-all-in sobe 25→**35bb efetivas** (`<9` só all-in · `9-35` min+all-in · `>35` só min; BvB→35; 3bets intocados). **FT-2 (fake all-in):** `IS_FT`+eff≤9 → além do all-in, **raise para 85% do stack NOMINAL** (raise-to 0.85×nominal; arredondamento fichas→BB; a app calcula, o gerador injeta via `ctx.sizingBigBlinds`). **Acoplamento obrigatório (#IMPLICIT-LINES):** as 2 mudam template (`shouldAddPreflopAllIn`) **E** `count_lines_for_position` **EM CONJUNTO** (a FT-2 cria linha nova); exige smoke visual dedicado. **Descoberta:** o override `stage 'FT'→'MTT'` (por `players_left`) é **INOFENSIVO** para o sizing — só afeta o equity model (ICM, que sai certo); os limiares de all-in não têm hoje noção de FT (fixos 25/30bb, decididos por stack efetivo + `IS_PKO`). |
| Secção **Marcadas/captura** — pedidos do Rui | 🟡 **EM ABERTO (por definir)** | (a) **Expor as 11 tags na UI** (hoje só 5 botões; faltam `-ft`, `pos-nko`, `speed-racer` — todas em `ALLOWED_TRIAGE_TAGS`). (b) **Editar nomes à mão** → confirmar a atribuição (mãos vêm do IT, desanon por stack, "por verificar") → passar **unverified→verified** (novo `match_method='manual_confirmed'` em `VERIFIED_MATCH_METHODS`). (c) **Propagar nome por HASH GG** dentro do torneio (mesmo jogador = mesmo hash; confirmar um nome propaga aos outros) — **a confirmar:** as mãos do IT carregam o hash GG? (d) **Investigar** porque a fila só mostra **~5** mãos quando há **382** `table_ss` "por verificar" (predicado exige sem tag + sem discord + não-triada → onde estão as ~377?). |

---

## 29 Jun 2026 — fidelidade do total de fichas ICM (lobby parcial vs campo final)

| ID | Sev | Resumo |
|---|---|---|
| `#ICM-CHIPS-USE-TS-FINAL-FIELD-GG` | 🟢 **LOW-MED — SÓ REGISTADO (decisão do Rui: registar, atacar depois)** | **Problema:** o `chips` do `payouts.json` (= **total de fichas do torneio**, que o HRC usa para o **ICM**) é a **estimativa do lobby** — `average_stack × players_left` (`services/lobby_vision.py:285-296`), lida no **momento da SS**. Quando a SS é tirada durante o **registo tardio**, o campo ainda está incompleto → o `chips` **subconta**. **Caso real (tn 292447656, Speed Racer Bounty Europe $108, mão GG-6102826859):** lobby deu **1 409 980** (≈ **141** entradas a 10 000); o **TS** diz **151 Players** → total verdadeiro **151 × 10 000 = 1 510 000**. Faltam **10 entradas (~100 000 fichas)** que se inscreveram **depois** da foto (TS: torneio começou 17:10:00; a mão foi 17:16, ainda Nível 1, late-reg aberto). Fichas não somem — é *timing* da SS. **Impacto:** ICM ligeiramente sobrevaloriza as fichas (~7% de campo a menos); ao Nível 1 / longe do dinheiro é pequeno, mas perto da bolha pode pesar. Os **prémios** no `payouts.json` já são os finais e corretos. **Fix proposto (GG-only):** quando **GG + TS existe**, sobrescrever `chips = TS.total_players × stack_inicial`, com `stack_inicial` = **stack do Hero na mão MAIS ANTIGA do `tournament_number`** (regra do Rui: a 1ª mão = entrada = stack inicial; validado — a 1ª mão TM6102826764 tinha **os 6 seats a 10 000 redondos**). Robustez: validar que a mão é "fresca" (1ª por `played_at`, stack redonda / Nível 1) para não apanhar uma stack a meio. **Fora de scope (inalterado):** **WN / PS / WPN** (o parser de TS é **GG-only** desde pt38) e **GG sem TS** → continuam na estimativa do lobby. **Onde mexer:** override no caminho que monta o `chips` (pós-`lobby_vision` / resolver / `queue_export`), gated por site GG + existência de TS. **Cross-ref:** `#RESOLVER-TIER0-STRICT-EQUALITY` (mesma tensão lobby-tempo-real vs TS-final), `lobby_vision.py:285-296`, `tournament_summaries`. **Investigação read-only feita (29 Jun):** 1ª mão tirada de `Batmen/gg_hh` (stack 10 000) + TS colado pelo Rui (151); zero acesso a prod. **Só registado — não implementado.** |

---

## pt91 (26 Jun 2026 — filtro de data do gold por NOME)

| ID | Sev | Resumo |
|---|---|---|
| `#APPIMPORT-DATE-FILTER-IT-GOLD` | ✅ **FECHADO (commit `de2fa18`, tool-side, sem deploy)** | O `gold` era o **único gap** de cobertura de janela no appimport: `process_gold_dir` corria **sempre sem janela** ("SEM filtro de mês"). **Fix (1 ficheiro, `tools/appimport/app_import.py`):** `process_gold_dir(session, live, window=None)` filtra pela **DATA-DE-JOGO lida do NOME** — novo helper `_gold_name_date(fname)` (regexes `(\d{4}-\d{2}-\d{2})` + `(\d{1,2})[-_](\d{2})[-_](AM\|PM)`, **alinhadas com `backend/app/routers/screenshot.py:_parse_filename`** para não divergirem). **Decisão de produto (pt91):** a data/hora do nome gold é a do DOWNLOAD, mas o Rui **descarrega a mão no momento em que a joga** → download = play na prática; a objecção `#GG-DOWNLOAD-IMG-FILENAME-TIME-AND-BLINDS-UNRELIABLE` **não se aplica** ao filtro de meses. **"Na dúvida inclui":** nome sem data/hora legível → **incluído por defeito + aviso** (`[aviso]`), nunca descartado em silêncio. Conta/reporta `fora da janela` no resumo, como as outras fontes; `main()` passa `window=img_window`. **Resultado:** as **5 fontes de imagem** (`manual`, `it`, `lobby`-subpasta, `gold`, `LOBBY_DIR`) respeitam agora `--desde/--ate`. **Critério não-uniforme por desenho** (auditoria fonte-a-fonte): data-do-nome onde o nome a tem (`it`, `gold`); `mtime` onde não (`manual`, `lobby` — nomes sem timestamp). **Validação:** dry-run `--desde 2026-06-01` → gold **325 dentro / 89 fora** (os de Março), fronteira dia-de-jogo 15:00 correcta, **0 avisos** (414 ficheiros gold reais todos com data+hora legíveis). **Tool-side → `git pull` na máquina do appimport** (não há deploy). Ver `PENDENTES` (secção homónima, com a investigação original) + `#GOLD-DIR-DEDICATED-SUBFOLDER`. |

---

## pt90 (25 Jun 2026 — captura OCR do tamanho da tree + abort preventivo; Release watcher-pt90)

**★ Guarda preventiva de trees gigantes shipped no `watcher-gate` + Release `watcher-pt90`.**
O watcher lê as estatísticas da tree (OCR read-only do painel "Tree Statistics") logo após a
Fase 2 do finish-wait (tree size já computado, **ANTES da 1ª run**) e aborta as gigantes pelo
mecanismo `.failed` existente. **End-to-end no `.exe` por validar no Beelink (smoke).**

| ID | Sev | Resumo |
|---|---|---|
| `#HRC-TREE-GIGANTE` | 🟢 **FIX SHIPPED (watcher-gate `9609ab6`+`7384ed2`, Release `watcher-pt90`); end-to-end `.exe` PENDENTE** | `tools/watcher_src/tree_stats.py` (novo) lê `{nodes, gb, hrc_available_gb}` por OCR (PrintWindow `PW_RENDERFULLCONTENT` + `Windows.Media.Ocr`; **dual-import winsdk (Py≤3.13) / winrt (Py3.14+)**; nunca lança). Hook em `_wait_for_finish_ready` (Fase 2): regista stats no `meta.json` (`tree_nodes`/`tree_size_gb`/`hrc_available_gb`/`build_seconds`/`solve_seconds`/`ocr_ok`) + **abort por DUPLA LEITURA** — aborta (raise → `.failed`, como a Fase 2 timeout) SÓ se ambas as leituras `ok` E concordarem que `gb > TREE_GB_ABORT_LIMIT`(15) **OU** `> hrc_available`; OCR falhado / leituras a discordar → **NUNCA aborta (fail-open)**. Cross-check do tempo-de-build **descartado** (gigantes 2-3s / normais <1s — janela cega). **Validação:** OCR provado em Python real no Beelink (smoke #1: `nodes=507581, tree=3.8GB, hrc=19.9GB` certos contra o painel); harness `swap_and_smoke` **ALL OK**; bundle do `.exe` verificado por TOC (`tree_stats` + winsdk OCR `media.ocr`/`graphics.imaging`/`storage.streams`/`globalization` + `_winrt.pyd` presentes → guarda viva, não fail-open-morta). **`.exe`: SHA256 `69e741c2f8b80e3f1323aaa1fe6150adb046d3b83ef87debadf7613321cc673c`, 32 988 546 B, Release https://github.com/ruikoko/poker-app/releases/tag/watcher-pt90.** **Instalado no Beelink — reportado pelo Rui (26 Jun; pt87 guardado em `C:\hrc\backup_watcher` como rollback — fricciona com «1 só exe», ver `PENDENTES` pt90).** **Falta:** confirmar SHA round-trip no Beelink + **smoke end-to-end** no `.exe` (mão normal corre; gigante forçada → `.failed`; OCR forçado a falhar → corre). |

---

## pt90-bug (26 Jun 2026 — regressão do log + lacuna de registo OCR no ramo tree=0)

| ID | Sev | Resumo |
|---|---|---|
| `#WATCHER-LOG-FILE-REGRESSION-PT90` | 🟡 **NOVO — A INVESTIGAR (reportado pelo Rui, 26 Jun)** | **Sintoma:** o `.exe` `watcher-pt90` **deixou de escrever o ficheiro de log** (só `stdout`); o `#WATCHER-LOG-TO-FILE` (entregue no pt68) gravava em `C:\hrc\watcher_logs\hrc_watcher_<ts>.log`. **Bug, não intencional:** a fonte **continua a ter** `_ensure_file_logging` (`tools/watcher_src/patched_funcs.py:1954`, Tee de stdout/stderr → ficheiro + rotação 14) e **continua a chamá-la** como **1ª linha do `setup_hand`** (`:2299`), em `main` E em `watcher-gate` → a perda do ficheiro **não** vem de remoção no código-fonte. **Pistas a investigar (no Beelink):** (1) o **bundle/trampoline do pt90** (`_local_only/…/swap_and_smoke.py`/`wrapper.py`, gitignored) pode não fiar a chamada, ou o SWAP de `setup_hand` no bundle pode ter trazido uma versão sem ela; (2) **build PyInstaller windowed / sem consola** → `sys.__stdout__` None pode partir o `_Tee` (cai no `except` → "[WARN] … só consola"); (3) `_ensure_file_logging` só corre quando o **1º `setup_hand`** dispara — com a fila vazia, nunca há log (pré-existente, não-pt90). **Verificação concreta:** processar 1 mão com o pt90 e confirmar se `C:\hrc\watcher_logs\hrc_watcher_*.log` é criado; se não, capturar o stdout para ver a linha `[log] a gravar em …` vs `[WARN] _ensure_file_logging falhou`. Cross-ref `#WATCHER-LOG-TO-FILE` (a feature original, pt68). **Só registado — investigar antes de fix.** |
| `#WATCHER-OCR-NOT-READ-ON-TREE-ZERO-BRANCH` | 🟢 **LOW — NOVO (lacuna de DADOS, não de guarda; para pt91)** | **Descoberto no smoke happy-path pt90** (1ª mão `GG-6083866641`): a mão caiu no **ramo `tree=0`** e o **OCR não disparou** → o `meta.json` dessa mão **não regista `tree_nodes`/`tree_size_gb`** (`ocr_ok` em falso/ausente). **NÃO é abort falhado** — não há gigantes a escapar à guarda (a `GG-6083866641` era ~2 GB, normal; os 8.6 GB eram **RAM do processo**, não árvore); é só **registo de dados incompleto** para as mãos que entram nesse ramo. **Fix (pt91, sem urgência):** fazer o OCR ler o painel "Tree Statistics" **também** no ramo `tree=0`, para preencher `nodes/gb` no `meta.json` (telemetria completa) — reutiliza a mesma infra `tree_stats.py`. **Não bloqueia** o fecho do `#HRC-TREE-GIGANTE` (a guarda está viva onde importa). Cross-ref `#HRC-TREE-GIGANTE`, `#WATCHER-JANELA-DE-TRABALHO-ETA` (os sinais precoces dependem de ter `nodes/gb` sempre registados). **Só registado.** |

---

## `#WATCHER-JANELA-DE-TRABALHO-ETA` (FUTURO, URGENTE — janela de trabalho + travão por ETA/custo)

| ID | Sev | Resumo |
|---|---|---|
| `#WATCHER-JANELA-DE-TRABALHO-ETA` | 🟡 **FUTURO/URGENTE — medição pendente no Beelink (não construído)** | **Ideia:** definir uma **janela de trabalho** (ex.: 8h) e o watcher **gere a fila** para a encher de forma mais produtiva, usando o **ETA da janela "Monte Carlo Sampling" do HRC** como **travão em tempo real** (*Via C*). **Liga ao pt90** (`#HRC-TREE-GIGANTE`) — **reutiliza a infra de OCR** (`tools/watcher_src/tree_stats.py`, PrintWindow + `Windows.Media.Ocr`). **Comportamento desenhado:** watcher **lê o ETA assim que aparece** (logo após o Finish, início do solve); **mão saltada** (ETA grande de mais) → **marcada para OUTRA janela** (mais longa), **não se perde**. **POR FECHAR:** critério de corte (**teto fixo por mão + margem no fim da janela** *(recomendado)* vs. só tempo-restante); **POR DECIDIR:** comportamento se o ETA **crescer depois de começar**. **Obstáculos conhecidos:** (1) o ETA **só aparece DEPOIS de o solve começar** (~13% da barra), **não antes** → só dá para **travar em tempo real**, não **ordenar à partida**; (2) **espreitar** o ETA de N mãos **consome tempo real da janela** → viabilidade depende do **custo de ler o ETA por mão** (medição pendente: setup→Finish, Finish→ETA estável, overhead de troca de mão); (3) ler o ETA exige **OCR da janela "Monte Carlo Sampling"** — **não testado** se essa janela se lê (pode ser opaca como o Tree Statistics era; talvez precise do mesmo **PrintWindow**). **SINAIS PRECOCES DE CUSTO (ideia Rui — alternativa/complemento ao ETA caro):** em vez de esperar o ETA estabilizar (gasta solve por mão), usar sinais mais cedo como proxy do tamanho/tempo: **(1)** tamanho da tree (nós/GB), **JÁ lido por OCR antes do Finish** (pt90) — o mais precoce; **(2) NOVO (Rui):** o **tempo de espera até à 1ª run** / a **lentidão dos primeiros instantes** do Monte Carlo Sampling **correlaciona com o tamanho da tree** → pista do custo **antes** do ETA estabilizar; **(3)** ETA estabilizado — o mais tarde e caro. **Implicação:** a janela de trabalho **pode dispensar a leitura cara do ETA** e gerir-se pelos **sinais 1+2** (baratos, precoces) — **a validar** cruzando os 3 sinais contra o tempo real de mãos conhecidas. **Alternativa — *Via A*:** **ordenar pelo TAMANHO da tree** (lido por OCR **ANTES** do Finish, sem gastar solve) como proxy do tempo; pode ganhar à *Via C* se o ETA for caro de ler. **Não implementar agora — só registado.** Detalhe em `PENDENTES.md` (secção homónima). |

---

## pt89 (25 Jun 2026 — open per-posição FECHADO + filtros /hrc + registo geral)

| ID | Sev | Resumo |
|---|---|---|
| `#GTO-OPEN-SIZE-NOT-PER-POSITION` | ✅ **FECHADO (commit `90c07ad`, deployed)** | Era 🟢 FUTURO (`PENDENTES`/`GTO_BRAIN §9`). **Fix:** opens passam a **per-posição** — cada não-blind tem a sua var `SIZES_OPEN_UTG/UTG1/MP/HJ/CO` (como os 3-bets em pt42b), acabou a partilhada `SIZES_OPEN_OTHERS` como canal de propagação. O gerador faz override **só** ao bucket do **opener real**; as restantes posições ficam no **default do template `[2]`**. Regra do Rui satisfeita: opener usa o seu size real; posições à frente usam o standard 2 BB; SB usa o size de blind. **Ficheiros:** `hrc_node_offset.py`, `hrc_script_gen.py`, `mtt_advanced_canonical_2026.js` (+ `test_hrc_node_offset.py`/`test_queue_export.py`). **★ Smoke do GERADOR PROVADO (25 Jun, read-only, sem HRC)** — `GG-6084129607` (8-max; HJ abre 2.0bb, eff 18.02bb ≤25): gerador de produção produziu `SIZES_OPEN_HJ = [2, ALLIN]` (ALLIN **confinado** ao opener curto) e `SIZES_OPEN_UTG/_UTG1/_MP/_CO = [2]` (fundos UTG 36.9bb · MP 32.5bb · CO 49.5bb **limpos, SEM allin**); overrides aplicados = só `SIZES_OPEN_HJ`. **Contaminação confinada ao HJ → bug desapareceu. Falta só o smoke da ÂNCORA no HRC** (mão que flua naturalmente; não soltar mão de propósito). Ver `JOURNAL_2026-06-25-pt89.md`, `GTO_BRAIN §9`. |
| `#HRC-QUEUE-PANEL-FILTERS` | ✅ **FEITO + UX VALIDADO À VISTA (commit `6e2c2d7`)** | Painel `/hrc`: **8 filtros** + **seleção mão-a-mão (multi-select)** + **normalização de posições**. Backend `hrc_queue.py`/`queue_export.py` (+ `test_queue_export.py`); frontend `HRCQueue.jsx`. UX já validado visualmente pelo Rui. |
| `#HRC-ADAPTER-STATE-DESYNC-SILENT` | ✅ **FECHADO (commit `bf2da9a`, deployed)** | Era 🔴 HIGH diferido (registado pt86c). O re-envio (`POST /hrc/release`) usava `ON CONFLICT DO NOTHING` → re-enviar mão já libertada = no-op → `requeue_epoch` não subia → adapter saltava em silêncio (`hrc_adapter.py:262`, `served_epoch <= stored`). **Fix server-only:** `ON CONFLICT DO UPDATE` faz `requeue_epoch += 1` + actualiza `released_at`/`batch_id` no re-envio → `served > stored` → adapter re-puxa sozinho e loga `re-queue`. Release fresco = INSERT epoch 0 (adapter puxa na mesma). Sem mudanças no adapter, sem rebuild; consumidor único verificado (manifest → dedup adapter). +teste `test_release_rerelease_bumps_epoch`; suite 1110 passed (3 falhas pré-existentes Postgres-local). Mãos presas (poison) intactas. Detalhe completo na secção **pt86c** acima + `JOURNAL_2026-06-25-pt89.md`. |

---

## pt89-bug (25 Jun 2026 — fallback_root com meta incoerente; tema do gerador)

| ID | Sev | Resumo |
|---|---|---|
| `#HRC-FALLBACK-ROOT-INCOHERENT-META` | 🟠 **NOVO (gerador; NÃO é o `#GTO-OPEN-SIZE-NOT-PER-POSITION`)** | **Sintoma (GG-6083771323, Speed Racer ~1.75 BB, 5 jogadores):** o gerador não acha agressor real → `fallback_root`, mas emite metadados **INCOERENTES** — `max_players=2` (a mão real tinha 5) + âncora etiquetada **"HJ"** com `aggressor_position=null`. "HJ" não existe numa árvore de 2 → 1ª run em ~2 s, **árvore vazia, mão inútil**. **2 facetas a corrigir (quando atacarmos):** **(1) Coerência** — no `fallback_root`, não deixar etiqueta de posição incompatível com o `max_players` que o próprio gerador calcula; se `aggressor_position=null`, a âncora não devia carregar um "HJ" placeholder. **(2) Raiz** — spots de stack ultra-curta (~1-2 BB) são all-in/fold: o gerador devia reconhecê-los e ou tratá-los como tal, ou marcá-los **não-solvíveis** e **não os mandar ao HRC** (poupa uma run inútil). **EXIGÊNCIA DE PRODUTO (Rui):** no fallback o gerador **não deve desistir de tudo** — tem de encontrar **PELO MENOS o Hero** (está sempre na mão; aliases GG `lauro dermio`/`koumpounophobia`; posição sempre determinável): (1) identificar sempre o Hero + posição; (2) sem agressor → ancorar na **DECISÃO DO HERO**, não num "HJ" incoerente; (3) `max_players` refletir a mão real (5), não 2. **INVESTIGAÇÃO read-only (25 Jun) — mecanismo + a pergunta "falta lógica ou dado?":** **(a) o meta incoerente** vem de DUAS derivações que não falam: `build_queue_zip` (`queue_export.py:1740-1745`) no ramo fallback põe `position = positions[0]` = `strategy_table_positions(seats REAIS)` (a tal "HJ"/placeholder das 5 cadeiras), enquanto `derive_max_players` (`derive_max_players.py:107-110`) devolve **2** "por convenção heads-up" quando **não há ação voluntária** — usando uma âncora **separada** que **ignora** a âncora-Hero. → label-da-tabela-de-5 + `max_players=2` = incoerência. **(b) Porque não usa o Hero:** **NÃO é "nunca tenta o Hero"** — o `derive_noraise_anchor` (pt86c, `[[#HRC-ANCHOR-FALLS-TO-ROOT-NOT-HERO]]`) **já ancora no Hero** quando há decisão (Hero abre / SB completa). **NÃO é dado em falta** — o Hero (BB) é identificável. **É que ESTA mão é um WALK:** o pt86c já a classificou em prod (ver secção pt86c, "#3 GG-6083771323 **BB → walk → skip ✓**") — Hero na BB, todos foldam, **ganha as blinds sem agir**; `derive_noraise_anchor` devolve `None` corretamente (`queue_export.py:719-720` "walk — o Hero nunca teve decisão"). → cai no `fallback_root` com o placeholder. **⚠️ TENSÃO a resolver com o Rui antes do fix:** a exigência "ancorar sempre na decisão do Hero" **não se aplica a um walk** — num walk **não há decisão do Hero** para ancorar (o Hero/BB ganha sem agir). Para ESTA mão o fix certo é a **faceta 2** (reconhecer walk/ultra-curto não-solvível → não mandar ao HRC) + **faceta 1** (meta coerente: nunca emitir posição incompatível com `max_players`), **não** forçar uma âncora-Hero inexistente. **SE** a mão tiver ação ultra-curta escondida (um shove que `derive_aggressor_real_action` perde) e **não** for walk, então o bug desloca-se para a **deteção do agressor** (e aí o Hero/agressor seria encontrado) — **distinguir os dois exige a HH de GG-6083771323**, que não consegui buscar nesta sessão (endpoint Bearer deu 401; a memória barra script local contra a BD de prod). **CONCLUSÃO (25 Jun, Rui):** a HH crua foi **apagada** (o adapter faz `rmtree` da pasta na falha — ver `#ADAPTER-KEEP-FAILED-FOLDERS`), mas a evidência dos metadados é forte (**`fallback_root` puro, zero agressor**) → **quase de certeza um WALK**, não um shove perdido; decisão de fix tomada sem certeza absoluta. **FIX-ALVO (quando atacarmos):** **(1)** o gerador **DETETA** mãos sem agressor voluntário (walk / pote sem raise) e **NÃO as manda à fila do HRC** — não há decisão a estudar, dá árvore vazia; **descartar a montante** com motivo claro (*"sem ação voluntária — nada a solver"*). **(2)** garantir **meta coerente** no fallback (nunca emitir posição incompatível com `max_players`) — para os fallbacks que **não** sejam walk. **(3)** a **âncora-Hero** (exigência do Rui) aplica-se aos fallbacks **COM** decisão do Hero, **NÃO** aos walks (onde não há decisão). **Não implementar agora — só registado.** |
| `#ADAPTER-KEEP-FAILED-FOLDERS` | 🟢 **NOVO (futuro; adapter/observabilidade)** | O adapter HRC **apaga a pasta da mão** (`rmtree`) quando a mão **falha** → **impede investigar mãos `.failed` a posteriori** (foi o que perdeu a HH crua de GG-6083771323, bloqueando a confirmação definitiva walk-vs-shove de `#HRC-FALLBACK-ROOT-INCOHERENT-META`). **Melhoria:** avaliar **preservar** as pastas das mãos `.failed` em vez de `rmtree` — ex.: mover para `C:\hrc\failed\<hand>\` (com cap de retenção/limpeza) ou marcar-e-não-apagar — para diagnóstico post-mortem. Adapter é **Python puro** (sem rebuild de exe). **Não implementar agora — só registar.** |

---

## pt88 (24 Jun 2026 — backlog: 2 fixes em prod + study-state reclassificado)

| ID | Sev | Resumo |
|---|---|---|
| `#POST-TABLE-SS-MOVE-EM-VISION-FAILED` | ✅ **FEITO (commit `c5a2a29`, origin/main)** | O `_post_table_ss` (`tools/appimport/app_import.py`) tratava **qualquer HTTP 200 como sucesso** → uma captura table-SS com `result:"vision_failed"` (200 + Vision falhou, ex. soluço/créditos) era **movida para `done\it` com ✓ falso**, sem retry. O lobby (`_post_lobby`) já distinguia o `vision_failed`. **Fix:** `_post_table_ss` passa a ler o JSON e devolve tri-estado `table`/`retry`/`fail`; `vision_failed` → **`retry`** (não move, fica para re-envio no próximo run — retry infinito, paridade com o lobby), com `⟳ … não movido` em vez do ✓. Âmbito SÓ `vision_failed` (`json_invalid`/`site_undetected` seguem `table`/move; não-2xx/exceção continuam `fail`). Backend intacto (`img_b64`+`folder_tag` guardados; `POST /api/table-ss/reprocess-failed` para os não-transitórios). Tool local, **sem deploy**. |
| `#include_no_payout-mismatch` | ✅ **FEITO + EM PRODUÇÃO (commit `078072f`, deploy Railway SUCCESS)** | `POST /hrc/release` (`queue.py:198`) testava a exportabilidade com `include_no_payout=True`, mas `GET /hrc` serve com `False` → mão sem `tournament_payouts` passava o release (libertada em `hrc_queue_release`) mas o adapter **nunca a servia** → **released-fantasma** presa, sem tree, sem feedback. **Fix:** o guard do release passa a `False` (paridade com o serve); a sem-payout cai em `manifest.missing_payouts` e é **rejeitada com motivo claro** — no multi-select da Estudo aparece `N× sem payout — não pode ir ao HRC (torneio sem estrutura de prémios)` (tooltip de "ignoradas"). Sem backfill, sem schema. |
| `#STUDY-STATE-REGRESSION-HH-IMPORT` | 🟢 **RECLASSIFICADO — NÃO é bug** (era 🟡 "regressão a corrigir + backfill") | **Premissa furada.** O `import_.py` mete bulk HH em `study_state='new'` (site-agnóstico, `:343/:367`). Isso é **correto** para as não-GG (PS/WN/WPN): são mãos de **estudo**, com nicks reais, e a doc de routing manda-as para Estudo (*"PS/WN/WPN HH sem SS → Estudo directo"*). A suposição "deviam arquivar" vinha da spec pt27 **"Duas pistas"**, que era **só para GG anonimizada** — generalizada por engano a todo o bulk. **GG bulk** em `'new'` (em vez de `'mtt_archive'`) é só **mislabel cosmético SEM sintoma**: escondida do Estudo pelo gate `match_method` (`hands.py` `STUDY_VIEW_GG_MATCH_FILTER`, aplicado quando `study_view` ligado — `:687-689`), e visível na mesma em **Torneios** (a listagem filtra por site/SS/match, **não** por `study_state` — `mtt.py:1216-1241`, `:82`). Verificado de passagem: `hands.py:683-684` exclui `mtt_archive` por defeito, mas a Estudo (com `study_view`) aplica o gate GG → só uma chamada crua (study_view off, sem tag) mostraria a GG-anon-`'new'`, e não é superfície de uso. **Acionável = doc, não código** (sem backfill). Substitui a redacção antiga (pt27/`JOURNAL_2026-05-19-pt27.md`); nota acrescentada à spec "Duas pistas" no `CLAUDE.md`. |

---

## pt87 (24 Jun 2026 — verify-gate do save-as + smoke real Beelink + reconciliação de estado do watcher)

**★ Smoke real ponta-a-ponta no Beelink (24 Jun), exe pt87 `e1dced5a` instalado e VALIDADO EM PRODUÇÃO.** A WN de 36 MB drenou ponta-a-ponta com `[SAVE-AS-CHECK] OK`; os 3 comportamentos (verify-gate, falha-limpa, watchdog) confirmados; o lote está a drenar (33+ mãos feitas). O exe pt87 é o **primeiro** a conter de facto pt84 (watchdog) + pt85 + pt87 — a Release `watcher-pt84` tinha enviado o exe **pré-pt84** (`5e1414`), por isso pt84/pt85 nunca tinham chegado a um exe instalado até agora.

| ID | Sev | Resumo |
|---|---|---|
| `#HRC-WATCHER-SAVE-NOT-PERSISTED` | ✅ **FEITO + VALIDADO EM PRODUÇÃO (24 Jun)** | O "Complete Export" escreve a árvore (40-70 MB) de forma **assíncrona**; o `_close_hand_tab` (pt68, Ctrl+F4) corria contra o write e **cancelava o save** → 0/38 mãos persistiam (`done\Exports\` vazio, watcher preso 24h). **Fix (watcher-gate `6522278`):** `_verify_export_zip` (pt85, antes só observabilidade) passa a **BARREIRA** — devolve bool (existe + tamanho estável + `testzip`), gateia o close-tab; trata `Confirm Save As` (overwrite); 1 retry; em falha marca `.failed` e o watcher **AVANÇA**; `EXPORT_WAIT_TIMEOUT` 24h→30 min. Harness `swap_and_smoke` **19/19**. Exe `e1dced5a`, Release `watcher-pt87`. **Smoke real 24 Jun: WN 36 MB drenou com `[SAVE-AS-CHECK] OK`; lote a drenar (33+).** |
| `#START-CALC-SELECTED-SUBTREE-NO-POPUP-OPEN` | 🔴 **REABERTO / REGRESSÃO (smoke 24 Jun)** | A 2ª run **volta a não disparar o popup Nash** — bug que fora **fechado em pt32-34** (`c9c8818`/`867460c`/`e58c517`: origem do click `wpos`→`find_hrc()`, OK por BM_CLICK, ciclo ponta-a-ponta). Voltou no smoke pt87. **Investigar porque o fix antigo deixou de pegar** (coord/timing/estado do HRC pós-pt66-70? interação com watchdog/close-tab?). |
| `#HRC-EXPORT-DIALOG-32770-NO-OPEN` | 🟠 **NOVO (smoke 24 Jun)** | O **diálogo Export Strategies** (`_find_export_dialog`, classe `#32770`, título vazio) **não abre** em alguns casos. **Distinto** das refs `#32770` históricas, que eram do **popup Nash**. Sem o diálogo, `export_strategies` aborta. Investigar o passo Hand→Export Strategies (menu/timing/foco). |
| `#HRC-TREE-GIGANTE` | 🟢→ **FIX SHIPPED em pt90** (Release `watcher-pt90`; end-to-end `.exe` pendente — ver secção pt90 no topo) | *(diagnóstico à data)* Uma mão gerou uma árvore **~20 GB** e **sobrecarregou a máquina**; o Rui teve de **cancelar à mão**. Falta **guarda preventiva: medir o tamanho/ETA da tree ANTES da 1ª run** e abortar/marcar `.failed` acima de um limite, em vez de deixar o HRC explodir. Relacionado (stale): `#HRC-WATCHER-JS-HARDCODED` (pt22, superado pelo gerador per-hand). |

**Reconciliação — 8 tech debts do watcher pt66-70 ✅ FEITO + VALIDADOS (smoke pt87 24 Jun).** Estavam listados "aberto / Release ptXX / re-smoke pendente / fix em buffer", mas o código está no `main` **E** no exe que correu hoje no Beelink (confirmados a correr, não só committed):

| ID | Fix | Geração |
|---|---|---|
| `#HRC-WATCHER-TAB-ACCUMULATION` | `_close_hand_tab` | pt68 |
| `#WATCHER-LOG-TO-FILE` | `_ensure_file_logging` | pt68 |
| `#HRC-CLOSE-TAB-BREAKS-CHORD-FOCUS` | `_restore_hrc_main_focus` | pt69 |
| `#OPEN-WIZARD-CHORD-FALLBACK-BLIND` | `_open_wizard_confirmed` | pt70 |
| `#HRC-RUN-WINDOW-DETECTION-BLIND` | `_find_progress_window_hwnd` | pt67 |
| `#HRC-BOUNTY-HARDCODED-50PCT` | `select_bounty_mode` removido | pt66 |
| `#HRC-REDUNDANT-SECOND-RUN-OLD-CONFIGS` | run intermédia removida de `setup_hand` | pt66 |
| `#CI-TARGET-INITIAL-NOT-CALIBRATED` | dissolvido; `_ci_target_readback_warn` | pt66 |

(pt79/pt84/pt85/pt87 vivem no `watcher-gate`; pt84+pt85+pt87 agora **deployed** via exe `e1dced5a`. Push/merge do `watcher-gate`→`main` = decisão à parte.)

---

## pt86c (23 Jun 2026 — âncora no-raise Passo 1)

| ID | Sev | Resumo |
|---|---|---|
| `#HRC-ANCHOR-FALLS-TO-ROOT-NOT-HERO` | ✅ **Passo 1 FECHADO (commit pt86c, backend-only)** | Regra do Rui (operativa): a âncora é o **nó que governa a 1ª DECISÃO do Hero** — limp/raise **antes** do turno do Hero → ancora aí (Hero responde no subtree, LEI B); **pote por abrir** no turno do Hero → **open do próprio Hero**; Hero **nunca decide** (walk) → skip. **Passo 1** (sem tocar a árvore/watcher/template/`count_lines`): nova `derive_noraise_anchor` em `queue_export.py` (chamada só quando `derive_aggressor_real_action`→`None`), mesmo contrato `{type,size_bb,position,source}`; `build_queue_zip` ganha o ramo `noraise_hero` (computa offset como o "real"; o caminho "1º raiser" das mãos com raise fica **byte-idêntico**, gated em `!= "real"`). `compute_target_node_offset` **não tocado** (o short-circuit `None` é contornado por lhe passarmos sempre um dict). **Breakdown REAL (read-only prod, 70 elegíveis 2026, 7 sem-raise):** 5 Hero-open (#1 GG-6083363766 BTN, #2 GG-6083048023 BTN, #4 GG-6083363843 BTN, #5 GG-6083680638 SB, #6 WN-…8 BTN) → **âncora cai na linha do Hero ✓**; 1 walk (#3 GG-6083771323 BB) → skip ✓; 1 limp de **não-blind** (#7 GG-6083363633 MP) → skip (Passo 2). **0 mãos** Hero=BB-vs-SB-limp hoje (ramo `noraise_sb_complete` future-proof, nó já existe na tabela). **A moldura antiga "(b) Hero=BB sem nó / (c) vs-limp" estava errada:** Hero=BB-vs-SB-limp ancora no Complete da SB (existe); o único caso difícil é o limp de não-blind → `#HRC-ANCHOR-NONBLIND-LIMP`. **Testes:** `test_noraise_anchor.py` novo (8) + `test_queue_export` ajustado; focados 317 passed, suite 1104 passed / 3 falhas pré-existentes Postgres-local. **Pendente: validação visual no robot (âncora pousa na linha do Hero) + push.** Ver `JOURNAL_2026-06-23-pt86c.md`. |
| `#HRC-WATCHER-BETTING-SCRIPT-STALL` | 🟠 **NOVO (robot; prioridade a definir pelo Rui)** | Observado na validação visual de 24 Jun (é do **robot a operar o HRC**, NÃO da âncora do backend). **Sintoma — STALL (não é clique-fora-do-alvo):** ao chegar ao **passo de seleção do betting script** (a janela Open/Browse do script `.js` **aberta e pronta para seleção**), o robot **fica PARADO — não avança nem dá erro** — e exigiu **intervenção MANUAL do Rui** para prosseguir. Sem **timeout** nem recuperação automática. **Contexto:** GG-6083363843 (3-max); a GG-6083363766 (6-max) correu bem logo antes; o Rui desencravou à mão e a mão terminou (âncora BTN confirmada). **Pista no código (`tools/watcher_src/patched_funcs.py`):** `setup_scripting` (linha 912) carrega o script às cegas — `click SCRIPTING_TAB → sleep → click SCRIPT_FOLDER → sleep 1.5 → paste_path` — **sem confirmar que o Open/Browse fechou** e sem retry; se o diálogo fica aberto, o passo seguinte `_wait_for_finish_ready` (linha 2480) espera o Finish ficar pronto e **não tem saída para este estado** → robot preso (o próprio comentário em 2486 reconhece que "setup_scripting fecha um Open dialog"). **Pedido:** investigar este passo — porque fica preso (paste falha? diálogo lento? foco?) e adicionar timeout + recuperação (fechar/repetir o Open, ou marcar `.failed`). **Distinto** do incidente do **chord do wizard a falhar 2×→reinício do HRC**, que **recuperou sozinho** (não fundir os dois). Relacionado com o arco **pt79 / hang-watchdog**, que continua **atrás do gate (não ativo)**. **Impacto:** bloqueia a validação visual autónoma de mãos no robot. Ver `JOURNAL_2026-06-23-pt86c.md` (fecho 24 Jun). |
| `#HRC-ADAPTER-STATE-DESYNC-SILENT` | ✅ **FECHADO (pt89, `bf2da9a`, deployed)** | **FECHADO em pt89** — causa-raiz operacional resolvida server-side: o re-envio (`/hrc/release`) passava a no-op (`ON CONFLICT DO NOTHING`) → `requeue_epoch` não subia → adapter saltava em silêncio. Fix: `ON CONFLICT DO UPDATE` faz `requeue_epoch += 1` no re-envio → adapter re-puxa sozinho (mecanismo pt83). Sem tocar no adapter. Ver secção **pt89** + `JOURNAL_2026-06-25-pt89.md`. As opções (a)/(b)/(c) de robustez do `state.json` ficam dispensáveis para o sintoma real. *Diagnóstico original à data:* **Problema:** quando o `state.json` local do adapter está dessincronizado do servidor (mãos marcadas `pulled`/`done` localmente que o servidor **voltou a oferecer**), o adapter **ignora-as em SILÊNCIO** e fica em "entering main loop" sem puxar nada — o operador não-programador não tem como perceber porquê (parece avariado). **Causa:** dedup `served_epoch <= state[hand_id].requeue_epoch` (`tools/hrc_adapter/hrc_adapter.py:262`) → salta qualquer `hand_id` que já conste do state, a menos que o backend sirva um epoch maior. O **"Disparar" da app mexe na fila do servidor mas NÃO toca no state.json local** → desencontro garantido (app diz "43 elegíveis", adapter puxa 0). **Achado-chave:** desde o **pt43 (`#SERVER-FILTER-HRC-STATUS`) o servidor JÁ exclui as `done`** do `GET /api/queue/hrc` → o skip-permanente-por-state local é **redundante E nocivo** (o seu único papel legítimo é evitar re-puxar uma mão **em curso** na pasta). **Bateu em 24 Jun** (após "Disparar" das 43). Workaround atual (frágil, manual): `Ctrl+C` → renomear `state.json` → re-arrancar. **Opções de fix:** **(a) auto-reconciliação [RECOMENDADA, raiz]** — confiar no servidor: se o servidor serve a mão, puxa-a (o servidor só serve não-`done`); o state local degrada-se de "skip permanente" para **guarda de in-flight** (pasta presente sem `.done`/`.failed`) **+ cooldown curto pós-POST-done** (evita re-puxar na janela POST→ack). Custo **BAIXO-MÉD** (~15-30 linhas no loop de pull + timestamp de cooldown no state; **adapter é Python puro, sem rebuild do `.exe`** → editar + copiar p/ Beelink; **exige smoke** Beelink: re-puxa servidas, NÃO pisa pasta em curso, NÃO entra em loop numa mão acabada de fazer). **(b) aviso claro em PT na consola [rede de segurança barata]** — após o loop, se N>0 servidas foram saltadas-por-state e 0 puxadas, imprimir "⚠ O servidor tem N mão(s) que ignorei porque já constam do registo local; para reprocessar: …". Custo **MUITO BAIXO** (~6-10 linhas, sem mudança de comportamento → quase sem risco; remove já a OPACIDADE). **(c) ressincronizar sem mexer em ficheiros** — c1 ficheiro-sentinela (`C:\hrc\adapter\RESYNC` vazio → adapter limpa o state e apaga o sentinela; não-programador cria o ficheiro), custo **BAIXO**; c3 botão na app→adapter (endpoint backend + leitura no adapter + botão no painel), custo **MÉD-ALTO** (desnecessário se (a) entrar). **Recomendação: (a) + (b) juntos** — (a) mata a raiz (o Rui nunca mais toca no `state.json`), (b) é quase grátis e dá observabilidade de defesa-em-profundidade; (b) pode entrar **primeiro/imediato**. (c) fica dispensável com (a); se quiserem escape-hatch manual, (c1) é o barato. **Prioridade sugerida: 🔴 HIGH** (pára o pipeline INTEIRO de forma opaca, recorrente, não-diagnosticável pelo operador; mitiga: sem corrupção de dados, servidor protege as `done`, há workaround). **Não implementar até aprovação do Rui.** Ver `JOURNAL_2026-06-23-pt86c.md`, `PENDENTES`. |
| `#HRC-ANCHOR-NONBLIND-LIMP` | 🟢 **NOVO (adiável — Passo 2, mexe na árvore)** | O **único** sub-caso do anchor que falta: limp de **NÃO-blind** antes do Hero (ex. #7 GG-6083363633, MP limpa, Hero=BTN folda atrás). O template só modela limp da **SB** (`canFlatCallPreflop` bets==1 → só SB) → não há nó para ancorar. **1 mão** em todo o 2026. **Fix (3 peças):** (1) template `LIMP_POSITIONS` (default `[]`, override per-mão com o índice HRC do limper) + `canFlatCallPreflop` a aceitá-lo; (2) **parser de limp** no gerador (`_parse_preflop_actions` hoje só emite raises) → emitir o índice; (3) `count_lines_for_position` **limp-aware** (o bucket do limper ganha +1 linha Complete, deslocando os offsets das posições seguintes — hoje só a SB leva esse +1). **Mexe na árvore (confinado: `LIMP_POSITIONS=[]` nas outras = byte-idêntico) → exige smoke** (tamanho + nó). Por 1 mão; não bloqueia nada (fica fallback_root como hoje). Ver `PENDENTES`, `JOURNAL_2026-06-23-pt86c.md`. |

## pt85–pt86 (22-23 Jun 2026 — vista de verificação HRC + cego Winamax)

| ID | Sev | Resumo |
|---|---|---|
| `#HRC-NODE-OFFSET-IMPLICIT-LINES` | ✅ **FECHADO (`8096f3c`)** | **Causa:** `count_lines_for_position` contava `len(array)` em vez das linhas reais que o HRC desenha → âncora da 2ª run na **posição errada**. O nº de linhas é **determinístico** a partir da stack individual + da regra do template (ALLIN implícito **25 BB geral / 30 BB blind-vs-blind**, `REGRAS_NEGOCIO §19`). **Fix:** template `mtt_advanced_canonical_2026.js` (`shouldAddPreflopAllIn` → `isBlindVsBlind ? 30 : 25`); `count_lines_for_position` espelha o template (sizings não-ALLIN abaixo da stack + 1 ALLIN se [explícito ∨ stack≤limiar ∨ size≥stack colapso] + Complete-SB), com a stack individual via `derive_position_stacks_bb` passada por `compute_target_node_offset`. `stack_bb=None` mantém o legacy. **Mão de teste `GG-6084189514`** (8-max, agg CO): offset **4 (MP, errado) → 6 (CO, agressor)**. **Escopo real:** das 45 elegíveis, **12 mudam offset, 10 movem a âncora — bidirecional** (undercount+overcount). O **"521" anterior era da premissa errada** (ALLIN implícito sempre), descartado. **+12 testes (48 no ficheiro).** Backend-only (NÃO toca `tools/watcher_src/`). **Pendente: re-gerar as trees já resolvidas com o template 30-geral (`PENDENTES`).** Ver `JOURNAL_2026-06-23-pt86b.md`, `REGRAS_NEGOCIO §19`. |
| `#HRC-ANCHOR-FALLS-TO-ROOT-NOT-HERO` | 🟠→ **Passo 1 ✅ FECHADO em pt86c** (resto = `#HRC-ANCHOR-NONBLIND-LIMP`) | *(diagnóstico à data; estado actual na secção pt86c acima)* Sem raise preflop (walk/limp-pot), a âncora do offset cai na **RAIZ** (`positions[0]`, 1ª a agir), **não no Hero**: `derive_aggressor_real_action`→`None` → `classify_aggressor_source='fallback_root'` → `target_node_offset=0` (`queue_export.py`). A regra "Hero-foldou-unopened → âncora=Hero" existe no `derive_max_players.py:100` (para o max_players) mas **não** no caminho do offset. **Exposição: ~7 mãos / ~10%** das elegíveis. **3 sub-casos:** (a) Hero=BTN → fácil (tem nó de open; transplanta limpo); (b) **Hero=BB → sem nó de open** na tabela; (c) **pote limpado → "vs limp" não existe** como nó de open. **Decisão de produto pendente** para (b) e (c) — o que fazer quando o Hero não tem nó de open. Ver `REGISTO_CONCEITO 2026-06-23`, `PENDENTES`. |
| `#DERIVE-MAX-PLAYERS-WINAMAX-COLON-BLIND` | ✅ **FECHADO (mesma sessão, `b7c3b08`)** | **Sintoma:** na árvore navegável de verificação HRC (GRAVITY), a opção **"SB call" não expandia** — faltava o nó do BB a fechar a acção (à vista, na página de verificação). **Causa:** `derive_max_players._ACTION_RE` exigia `": "` (formato GG/PS, `"Hero: folds"`); a **Winamax escreve sem dois-pontos** (`"thinvalium folds"`) → **0 matches** → âncora nunca detectada → **fallback silencioso a `max=2`**. **TODA** a Winamax exportada para o HRC saiu colapsada a heads-up (`settings.engine.maxactive=2` → multiway cortado + redução ICM/equity ao nº de jogadores errado). **Distinto** do `#HRC-MAX-PLAYERS-SPAN-NOT-PARTICIPANTS` (fechado pt67, span-vs-participantes) — **este é formato de HH Winamax**. **Alcance (varrido o `app/` inteiro):** 1 só sítio cego; os outros 7 regexes de acção já eram colon-opcionais. **`derive_aggressor_real_action` e `target_node_offset` NÃO afetados** (caminho `_PREFLOP_OPEN_RE` colon-opcional) → âncora e 2ª-run foram ao **nó certo**; só o `max_players` saiu errado. **Fix:** `": "` → `:?\s+` (colon opcional, alinhado com `hrc_verify_tree`/`hrc_script_gen`). +2 testes WN sem colon. **32 passed**, backend-only, deployed. **Prova read-only** (packs gerados em memória, sem robot): `max_players` correto — GRAVITY 3, multiway 5/6, SB-vs-BB 2 pela razão certa; **7 de 8 mãos WN mudaram**; nenhum outro campo do pack preso ao max antigo (`payouts.json` só prémios; `maxactive` no `script.js` = var local de chips activos, não derivada). Ver `JOURNAL_2026-06-23-pt85-pt86.md`. **Pendente associado: re-correr as 7 trees contaminadas (ver `PENDENTES.md`).** |

## pt77 (18 Jun 2026 — YaPoker → WPN)

| ID | Sev | Resumo |
|---|---|---|
| `#LOBBY-NAME-HINT-YAPOKER-JUNK` | 🟢 LOW (parqueado) | `lobby_name_hint()` (`tools/appimport/app_import.py`) extrai do nome dos ficheiros YaPoker o título `"YaPoker Lobby Logged in as cringemeariver"` — que **não é nome de torneio** — e sobrepõe-no ao nome lido pela Vision no lobby. Efeito: o lobby YaPoker fica **reconhecido como WPN** (pt77, FEITO) mas o resolver tende a falhar → `tm_not_found` em vez de `success`. **Não bloqueante** (mãos WPN já têm nomes pelo HM3) e mexe em lógica **partilhada** de extração de nomes (GG depende dela) → adiado por decisão do Rui. Fix futuro: suprimir o título quando é o chrome da janela do IT (ex.: contém "Logged in as"), deixando a Vision mandar no nome. Ver `JOURNAL_2026-06-18-pt77.md`. |

## pt75 (18 Jun 2026 — desanon por posição shipped: notas/dívidas)

| ID | Sev | Resumo |
|---|---|---|
| `#POSITION-V3-TWO-RELINK-PATHS` | 🟢 LOW (manutenção) | A branch `position_v3` (posições→`_build_anon_to_real_map_by_position`; senão stack) vive em **DOIS** sítios que têm de ficar em sync: `screenshot._enrich_hand_from_orphan_entry` (match directo + um caminho de rematch) e `hand_service._insert_hand` (promoção de placeholder = re-link imagem-primeiro). Um 3º caminho que desanonimize tem de replicar a mesma branch. |
| `#CANON-POSITION-LJ-NO-HH-SEAT` | 🟢 LOW (latente) | `_canon_position` reconhece `LJ` mas a `POSITION_MAPS` da HH não tem `LJ` (usa HJ/MP no full-ring). Se a GG escrever `LJ` para um seat, não casa → **lacuna honesta** (seat por mapear, nunca nome errado). Não apareceu nas 41; só morde em full-ring 9-handed. |
| `#STACK-LEGACY-TABLE-SS-AND-PANEL` | 🟡 MED (dívida do stack) | O stack-elimination continua nas **185 table-SS** (sem sigla de posição) e ancora no **painel SB/BB** — que o smoke mostrou ser **mal lido ~10/19** quando o Hero é o blind (o crachá do log é mais fiável). Argumento para migrar o table-SS para a âncora SB/BB+botão (`DESANON_ANATOMIA §3.2.1`) ou posição quando houver sinal. |

---

## pt73 (16 Jun 2026 — nome das imagens GG-download: hora E blinds não-fiáveis)

| ID | Sev | Resumo |
|---|---|---|
| `#GG-DOWNLOAD-IMG-FILENAME-TIME-AND-BLINDS-UNRELIABLE` (renomeado de `#GG-DOWNLOAD-IMG-FILENAME-TIME-IS-DOWNLOAD-NOT-PLAY`, que nunca chegou a ser registado em commit) | 🟡 MED — **confirmado LATENTE (0 mãos contaminadas, 16 Jun)**, não activo | **Aberto — latente.** **FACTO (Rui, 16 Jun, com print, ex. `2026-06-16__08-42_PM__0_35__0_70__6083717338.png`):** no nome destas imagens GG-download / replayer-share, **nem a hora nem as blinds** correspondem à mão — a **HORA é a do DOWNLOAD** (não a do jogo) e as **BLINDS no nome (`0_35`/`0_70`) estão ERRADAS** (as reais são extraídas **depois**, pela Vision, sobre a imagem). **Único sinal fiável no nome = TM/hand-id** (`6083717338` → `GG-6083717338`). **Exposição no código (read-only, confirmada):** (1) `screenshot.py:88` `_parse_filename` extrai date/time/blinds/tm e a doutrina chama-lhes "fonte primária"; (2) `screenshot.py:1565-1574` escreve `played_at = date+time` do nome quando a mão ainda não tem `played_at` → grava **DOWNLOAD-time como hora-de-jogo**; (3) `mtt.py:445` `ss_blinds = file_meta.get("blinds")` + `mtt.py:1042` `_match_screenshot(tm, played_at, blinds)` → blinds **e** hora do nome entram como **sinal de match** imagem↔mão (ambos do download, não da mão). **Contradição com a doutrina (a reconciliar, NÃO mexer sem decisão do Rui):** `CLAUDE.md:174` ("Parse determinístico do nome — fonte de verdade para data, hora, blinds e TM number; nunca confiar no Vision p/ blinds"), `MAPA_ACOPLAMENTO §file_meta`, `VERIFICACAO_PIPELINES:516`, `archive/ONBOARDING_OPERADOR_pre_pt9.md:37` afirmam o contrário do que o Rui afirma para estas imagens (blinds via Vision). Decisão de **doutrina/dados → Rui**. **Cross-ref:** `DESANON_ANATOMIA §2` (nome do replayer-SS GG: só o TM é fiável; hora/blinds do nome não são da mão) — reforça a **DECISÃO pt73** (match por hand-id). **A DECIDIR ANTES DE FIX (Rui):** (a) flip da doutrina p/ estas imagens (Vision = fonte de blinds; nome só dá o TM); (b) tirar hora+blinds do nome do `_match_screenshot` e do `played_at`-fallback; (c) scan read-only à prod p/ contar quantas mãos já têm `played_at`/blinds vindos do nome. **Scan pt73 (16 Jun, read-only): 0 mãos contaminadas.** Causa: caminho **latente** (0 `entry_type='screenshot'`; `played_at` sempre = HH; 0 desempate por blinds). **Debt confirmado LATENTE, não activo** — só morde se a lane de screenshot-por-nome for reactivada (ver lane nova em `PENDENTES` + ordem fix-primeiro). **✅ FIX-PRIMEIRO APLICADO (17 Jun 2026):** **(b) feito** — `_match_screenshot` (`mtt.py`) passa a casar **só por TM/hand-id** (assinatura reduzida a `(tm_number)`; removidos ambos os desempates do nome — por blinds e por hora; múltiplos SS do mesmo TM = mesma mão → menor `id` determinístico) e a chamada em `import_mtt` (`mtt.py:~1042`) deixou de passar hora/blinds; o `played_at`-fallback do nome **removido** no enrich de órfãs (`screenshot.py:~1565`) → sem HH, `played_at` fica **NULL**, não se inventa do download. **Bug bónus fechado:** o guard do fallback (`not matched_hand.get('played_at')`) era **inócuo** — o `SELECT` da função nem trazia a coluna `played_at` → o fallback disparava **sempre** que o nome tinha data, gravando DOWNLOAD-time como hora-de-jogo. **(c) re-verificado read-only na prod (17 Jun):** **0 contaminação** — **36 084/36 084** GG com `played_at` == hora da HH (ao minuto), **0** `anchors_stack_elimination_v2`, **0** `file_meta` em `player_names` → fix **PREVENTIVO, sem dados a sarar**. Testes novos: `backend/tests/test_gg_filename_not_in_match.py` (7 casos, verdes). **(a) doutrina/dados (flip "Vision = fonte de blinds; nome só dá o TM") continua a decidir o Rui** — não tocada. **Estado: caminho continua DORMENTE**; o fix protege-o para quando a lane de screenshot/órfãs reactivar. |

---

## pt72 (14 Jun 2026 — replayer GG morto + Discord maio por concluir)

| ID | Sev | Resumo |
|---|---|---|
| `#REPLAYER-OGIMAGE-DEAD-SPA` | 🟠 (estrutural, externo) | **Aberto / não-corrigível do nosso lado.** A GG migrou `my.pokercraft.com/embedded/shared/client/…` de página server-rendered (com `<meta og:image>`) para **SPA Angular sem og:image** → `_extract_gg_replayer_image` (fetch+regex, httpx + urllib fallback) extrai **0/627** em TODAS as idades (fetch real maio-08→junho-13: HTTP 200, ~85 KB, zero `og:*`; só assets CSS `.png`; confirmado pelo Rui no HTML). Sem fallback guardado (`img_b64`=0, `screenshot_url`=0 nos entries + 0 nas 34 320 mãos GG). **Via screenshot/headless investigada e DESCARTADA** (Chromium na Railway: pesado ~300-500 MB + RAM/página, ~5-15 s/link, render assíncrono/bot-protection por validar, ToS pokercraft **não-verificado**). **Decisão:** replayer-image **descontinuado**; desanon GG só por table-SS do IT. Não há fix — é mudança da GG. **Impacto:** a Fase 2 do botão "Sincronizar histórico" (`70a2919`) extrai 0; o valor do botão fica na Fase 1 (RETOMAR sync) + Fase 3 (placeholders). → `JOURNAL pt72 §A/§B`; `discord_bot.py:_extract_gg_replayer_image`. |
| `#DISCORD-MAIO-15-31-PENDENTE` | 🟡 MED | **Aberto — ficou por concluir nesta sessão.** O Discord de maio (15-31) está **cru/parcial**: as mensagens apanham-se (Fase 1 / `/sync`), mas as mãos GG referidas por replayer-link **ficam anónimas** (Fase 2 morta — ver `#REPLAYER-OGIMAGE-DEAD-SPA`). **Próximo:** (1) confirmar que o `/sync` apanhou tudo até 31-mai (cursor por canal); (2) processar o processável **sem** replayer (HH-text directo, placeholders GGDiscord); (3) aceitar que as GG-só-replayer de maio ficam por desanonimizar até haver table-SS do IT (se houver captura). → `JOURNAL pt72 §D`. |

## pt70 (11 Jun 2026 — fix #OPEN-WIZARD-CHORD-FALLBACK-BLIND + Release watcher-pt70)

| ID | Sev | Resumo |
|---|---|---|
| `#OPEN-WIZARD-CHORD-FALLBACK-BLIND` | 🔴 HIGH | ✅ **FIX em buffer** (validado Web; exe `315CC2B5…D50C` na Release `watcher-pt70`; smoke real Beelink pendente). O `open_wizard()` OG (`_local_only/.../hrc_watcher.py:128-163`), ao fim de **2 chords `Ctrl+W,M` falhados**, DESISTE e devolve um `WizardPos` **fabricado** (`Wizard assumed at ...`) **sem confirmar** que o wizard abriu → o pipeline opera contra a janela principal `HRC Pro` (cola/navega no vazio, export cancela, zip nunca nasce) → **deadlock `Activas`**. Provado na smoke pt69 (log `hrc_watcher_20260611_164520`): mão 1 OK; mão 2 (logo após o fecho de aba) `Wizard assumed`, foreground `HRC Pro` a mão toda, `hwnd_wizard=None`, Nash popup nunca visto. O comando do chord **não disparou** (janela `Hand Setup` nunca enumerada em 2 retries × 4s — **refuta** "wizard atrás" e "timing de detecção"). O `_restore_hrc_main_focus` (pt69) repôs o foreground mas **não** o contexto do chord multi-stroke SWT pós-fecho-de-aba — **necessário, não suficiente**. **Fix:** wrapper `_open_wizard_confirmed(hh_text)` (APPEND) — confirma via janela `Hand Setup` **real** (`_scan_handsetup_window`), descarta sempre o `WizardPos` fabricado, e escada `rung 0 confirma → rung 1 Esc+repor-foco+re-chord → rung 2 _restart_hrc+_wait_hrc_responsive+re-armar clipboard(HH)+zerar contador → rung 3 None (bail limpo)`. Cold start = único estado 100% fiável (prova: mão 1). `setup_hand` chama o wrapper; `open_wizard` OG intocado (sem novo SWAP). swap_and_smoke ALL OK (51 funcs). Mitiga (mas **não** fecha) o `#OG-MAIN-LOOP-NO-WATCHDOG` (pt69) — pior caso vira atraso ~30s em vez de deadlock. |
| `#QUEUE-BETTING-SCRIPT-BUG` | 🟡 MED | **Aberto** (registado pt70; fix mais tarde — **não bloqueia o smoke pt70**). O `script.js` gerado para a mão **`GG-6041006979`** (auditoria visual do Rui) tem um bug no betting script. **A inspecionar quando chegar a vez:** o pack da mão (`queue`/`done` do Beelink) + o builder no backend (`backend/app/services/hrc_script_gen.py` + template `backend/app/services/hrc_scripts/mtt_advanced_canonical_2026.js`). O Rui descreve o **sintoma concreto** na altura do fix. |

## pt69 (11 Jun 2026 — frontend multi-select HRC + diagnóstico da deadlock "Activas")

| ID | Sev | Resumo |
|---|---|---|
| `#HRC-CLOSE-TAB-BREAKS-CHORD-FOCUS` | 🔴 HIGH | ✅ **FIX em buffer** (pendente validação Web + build do exe). O `_close_hand_tab` (pt68) dispensa o "Save Resource" via `BM_CLICK` (mensagem, não foca) e retornava **sem repor o foreground/foco** na janela principal. O `open_wizard()` OG (`_local_only/.../hrc_watcher.py:128-163`) abre o wizard via **chord `Ctrl+W,M`** e **assume a janela principal focada** (center-click linha 134, antes do chord). Resultado: ao fim da mão 1 (1ª execução do `_close_hand_tab`) o estado de foco fica errado → o chord da mão 2 falha → `open_wizard` devolve `None` → `setup_hand` `return False` (`hwnd_wizard=None`). O `main()` OG (`active=[]`) fica preso → **deadlock "Activas"** (HRC vivo idle). A mão 1 (cold start) passa por estado limpo. **Fix:** `_restore_hrc_main_focus()` no fim do `_close_hand_tab` — espera o modal sumir (WARN se ficar) + `activate()`+center-click+settle (espelho da pré-condição do `open_wizard`). Provenance: o exe a correr no Beelink é `222FC48D…3F57` (pt68 — causa certa). swap_and_smoke ALL OK (49 funcs). |
| `#OG-MAIN-LOOP-NO-WATCHDOG` | 🟠 MED | **Aberto** (registado pt69, fix futuro). O loop principal do bundle OG (`hrc_watcher.py:main()`, `active=[]`) espera o fim das mãos em curso **sem timeout/watchdog** → a deadlock "Activas" repete-se com **qualquer** causa futura de "zip-que-não-nasce" (não só o foco do `#HRC-CLOSE-TAB-BREAKS-CHORD-FOCUS`, que o pt69 remove). O bundle OG está em `_local_only/` (decompilado) — o watchdog exige editar o launcher OG. Adiar para um pt dedicado. |

---

## pt68 (11 Jun 2026 — wipe total + re-teste faseado + Saúde do Import)

| ID | Sev | Resumo |
|---|---|---|
| **#SYNC-ENDPOINTS-SYNCHRONOUS-TIMEOUT** (ex-`#DISCORD-SYNC-…`) | 🟡 MED (aberto) | Endpoints **síncronos e pesados** estoiram o timeout do cliente/edge mas **completam server-side**. **2 instâncias provadas pt68:** (1) `POST /api/discord/sync-and-process` — ReadTimeout 300s no cliente, mas 127 replayer + GGDiscord inseridos. (2) `POST /api/import` — **502 "Application failed to respond"** num zip GG de **4710 mãos** (7,6 MB — **não** é memória), mas as **4710 mãos ficaram TODAS na BD** (0 em falta; distinct `hand_id` GG = 4710). **Ambos idempotentes** → re-correr é seguro (HH: `_insert_hand` salta `hand_id` já existente, `hand_service.py:304`; Discord: cursor + PK). **Fix:** job em **background** + resposta-cedo com handle de progresso. **Quick-win adjacente:** escrever o `import_log` **no INÍCIO** (antes de processar) — hoje o timeout deixa `import_logs` **vazio** apesar do sucesso → a Saúde do Import não mostra o run (só o vê em "Mãos importadas" por `played_at`). |
| **#IMPORT-HEALTH-LOGGING-HOLES** | 🟢 LOW (aberto) | A Saúde do Import v1 (`/import-health`) só cobre o que já é queryable (table_ss/lobby/import_logs/entries). **Falhas sem rasto na BD** (a tapar em v2): (1) **HM3** (.bat) não persiste log — só o resumo na resposta; (2) **Vision do replayer GG** falha em log de **consola**, não em tabela; (3) ficheiros **rejeitados/SKIP no appimport** (client-side); (4) **parse de HH por mão** — erros agregados em `import_logs.log`, sem detalhe por mão. |

### pt68 — incidente do watcher (madrugada 11 Jun) + gate

| ID | Sev | Resumo |
|---|---|---|
| **#HRC-WATCHER-TAB-ACCUMULATION** | 🔴 HIGH | **Degradação progressiva** do HRC ao longo da fornada (setup-failed 02:14 → 3 OK → derail ~02:35; ritmo a subir 3→9 min/mão). Hipótese forte: o watcher **abre wizard/tab por mão mas NÃO fecha o anterior** → tabs **acumulam** (Rui viu 3 tabs = 3 sucessos) → fuga de memória/handles/UI → setup falha cada vez mais. **Sem lógica de fecho de tab na fonte** (`patched_funcs.py`). **Mitigação:** (a) fechar a tab anterior após export; (b) **reiniciar o HRC a cada N mãos** (o gate de lotes ajuda já); (c) health-check pré-setup. |
| **#WATCHER-LOG-TO-FILE** | 🔴 HIGH (subido) | O watcher escreve para **consola**; a consola perdeu-se na noite → **sem root-cause** do setup-failed/derail. Tem de gravar para **ficheiro** (como o adapter, `TimedRotatingFileHandler`). Esta noite provou o custo. |
| **#WATCHER-SETUP-FAILED-OPAQUE** | 🟡 MED | O `.failed` que o watcher marca chega à BD como `error="setup failed"` **sem sub-razão** (clipboard rejeitado? wizard frio? foco?). `GG-6041693835` (1ª mão, cold start) — provável race de arranque a frio. Marcar o `.failed` com a **razão concreta** + o log-to-file fecham isto. |
| **#QUEUE-NO-SERVER-SIDE-GATE** | ✅ FIXED v1 (`c10e303`) | Gate server-side + disparo manual (tabela `hrc_queue_release` + filtro no GET + `POST /trigger?count=N` + `GET /gate`; auto-fecho; per-mão não-gated; zero Beelink). Página HRC Queue com "Disparar tudo / lote de N". Fila arranca FECHADA. |

**★ Saúde do Import v1 (`/import-health`)** — página nova (nav "Saúde Import") + `GET /api/import-health?day=YYYY-MM-DD` (janela dia-de-jogo 15:00→15:00). Por pipeline (hands/mesa/lobby/hh_ts/inbox): contagens + lista de falhas/sem-match (motivo + timestamp). Instrumento de validação da Etapa 1. Read-only sobre os logs existentes; buracos acima.

---

## pt67 (IMPLEMENTADO — em buffer + Release `watcher-pt67`; re-smoke real pendente)

3 debts FIXADOS (backend 916 PASSED + 102 watcher pytest + in-process smoke ALL OK;
diffs validados pelo Web antes do build). `.exe` `a9554427…b3bc931` + Release
`watcher-pt67`. **DELETE dos 2 hrc_jobs (job 6,7) feito** → as 2 mãos voltaram a
elegíveis (= recalc da quarentena). Re-smoke real das 2 mãos pendente (Beelink).
Journal: `JOURNAL_2026-06-10-pt67.md`.

### Fixados (em buffer/Release; re-smoke real pendente)

| ID | Sev | Resumo |
|---|---|---|
| **#HRC-RUN-WINDOW-DETECTION-BLIND** | 🔴 HIGH | O **sleep cego de 30s pós-Finish engole runs curtas** (~5s a 10M iter @ ~1.9M/s). A janela da 1ª run é **"Hand Setup" do início ao fim** (o popup pós-Finish MORFA na run sem fechar/retitular). Fix pt67 (watcher): eliminar o sleep cego; vigiar desde o Finish (poll ~0.5s, tracking por **hwnd**); nunca-vista + N s de ecrã limpo → acabou rápida OU não arrancou (a navegação denuncia). **Sem heurísticas de tempo/memória.** Invariante: corrida ⇔ janela no ecrã → **NUNCA "Always run in background"** (runbook §2.7). |
| **#HRC-CI-SAFEGUARD-CHILD-CONTROLS** | 🟡 MED | A salvaguarda só-leitura do CI (pt66) lê o **título** da janela, mas o "MC-CFR [Target CI < 10.00]" vive num **label INTERIOR** do dialog → nunca pega (cai no fail-safe). Fix pt67 (watcher): ler **child controls** (WM_GETTEXT/UIA); plano B: barra de estado do HRC. |
| **#HRC-MAX-PLAYERS-SPAN-NOT-PARTICIPANTS** | 🔴 HIGH | `derive_max_players` (**backend** `derive_max_players.py`) conta **participantes** (`voluntary_before + hero + still_to_act`), **não** o **span posicional âncora→BB** que a regra do Rui exige (LEI — `REGRAS_NEGOCIO §15`, `WATCHER_FLUXO`). Descarta os **folders entre a âncora e o herói** → **subconta** com herói tardio (BB). Cross-check: GG-6028190109 (6-max, BU, âncora HJ)=5 ✓; GG-6039094225 (8-max, BB, âncora SB)=2 ✓; **GG-6029013400 (8-max, BB, âncora HJ)=2 ✗ (devia 5)**. Fix pt67 (**backend**): reescrever como span âncora→BB inclusive (usar `derive_seats_in_preflop_order`); cobrir regra 1 (herói foldou unopened → âncora=herói) **e** regra 2; testes. **Regra 1 nunca exercitada** nas 3 mãos (coincide hoje por sorte). |
| **#WATCHER-PLAYER-COUNT-SPACE-NICKS** | 🟢 LOW | `get_player_count_from_hh` (`patched_funcs.py:811`, o diagnóstico "In hand: X") usa `\S+` p/ o nick → **salta nicks com espaços** (nomes reais GG): GG-6039094225 (8 entrantes) → "In hand: 4". **Cosmético** (não é o Max enviado ao HRC — esse vem do hint backend). Alinhar a `.+?` (como `derive_max_players` em pt27). |

### Quarentenas (recalcular pós-pt67 — re-POST sobrescreve)

`GG-6028190109` + `GG-6027751209` (anteriores) + **`GG-6029013400`** (nova: calculada
com **Max=2** quando a regra manda **5**).

### Fila ~49 — TRAVADA até pt67 + fix Max Players (decisão do Rui)

Re-smoke pt67 = **as mesmas 2 mãos**: `GG-6029013400` tem de sair com **Max=5** (+ recalc
da quarentena); `GG-6039094225` = regressão (Max=2). Só depois: lote(s) ao ritmo do Rui.

### pt67b — off-by-one do nó (3ª volta) + label + lei da âncora

A 3ª volta validou **Max=5** mas expôs **nó de navegação errado** (off-by-one). Fixes:

| ID | Sev | Resumo |
|---|---|---|
| **#HRC-NODE-OFFSET-OFFBY1-REVERT-PT61** | 🔴 HIGH → ✅ FIXED (`9b772ce`); ⚠️ re-classificado **inofensivo** | `offset_within_bucket` (`hrc_node_offset.py`): o **pt61** (`940bf36`, "EM BUFFER" nunca smoke) colapsara o within-bucket p/ "1º nó" (0/1); a 1ª smoke real mostrou o **jam** no nó **ALLIN = último**. Revertido p/ all-in-dependent (non-SB small=0/jam=1; SB Complete=0/small=1/jam=2). Cross-check (visual + `build_queue_zip`): GG-6029013400→**7**, GG-6039094225→**14**, GG-6028190109→**2**. Suite **919 PASSED**; deployado+verificado (offset 7/14 no GET; poker-app SUCCESS `6fd6b30`). **⚠️ 4ª volta:** com a LEI B confirmada (`#HRC-2ND-RUN-ANCHOR-LAW`), o within-bucket é **inofensivo** (jam e small-raise = mesma posição = mesmo âmbito) — o fix **não era a causa de lixo**; fica por ser mais limpo (aterra na acção real). |
| **#HRC-NODE-OFFSET-IMPLICIT-LINES** | 🔴 HIGH (o **veneno real** — pós-4ª volta) — contagem errada de linhas salta para a **POSIÇÃO ERRADA** → âmbito errado = lixo genuíno (≠ within-bucket, que é inofensivo sob a LEI B). | **Escavação pt67 (a pedido do Rui):** a regra do limiar de stack é `_OPEN_ALLIN_THRESHOLD_BB = 25` (`hrc_script_gen.py:51`) + `_array_for_raise` (816-842): raise non-all-in com **`eff ≤ 25 → [size,"ALLIN"]`** (2 sizings) / **`eff > 25 → [size]`** (1 sizing). Os defaults do template (`mtt_advanced_canonical_2026.js:26-29`) são **1 sizing** (`[2]/[2]/[3.5]/[4]`), mas a prova visual da #225 (offset 14 = 6×2) mostra que o **HRC acrescenta uma linha ALLIN IMPLÍCITA** → o nº de linhas = `sizings não-allin + 1`, **não** `len(array)`. `count_lines_for_position` lê `len(override)` → acerta no default (→2) e no `[size,ALLIN]` (→2), mas **devolve 1 (errado, devia 2) para um override `[size]` de `eff>25`**. **Exposição: 17 de 70 mãos elegíveis** têm um `[size]` numa posição ANTERIOR ao agressor → offset sub-conta ≥1 (assumindo que o HRC trata override `[size]` como default `[size]` — estruturalmente idêntico, **não** confirmado visualmente). **#400/#225 NÃO afectadas.** Fix (depois da confirmação): `count_lines` = nº de sizings não-allin **+ 1** implícito, OU ler o script.js renderizado. **Confirmação visual obrigatória.** |
| **#HRC-NAV-LABEL-MISLEADING** | 🟢 LOW → ✅ FIXED (watcher source; Release `watcher-pt67b`) | O label `navigate_to_target_node: …(esperado: HJ raise 9.01bb)` mostrava a **acção do agressor**, não o **alvo da navegação** → mascarou o offset e deixou o off-by-one passar. Corrigido p/ `[ALVO nav: linha N (offset K) \| accao real: …]`. Exige recompilação do `.exe`. |
| **#HRC-2ND-RUN-ANCHOR-LAW** | ✅ RESOLVIDO (4ª volta pt67, 3 fotos) | Veredicto visual: um Selected Subtree numa linha **recalcula o ponto de decisão INTEIRO da posição-âncora + jusante; montante congelado** (`HJ 2.00: 5.3→1.2%`, jam `17→20.6%`; CO/BU/SB mudam; UTG/EP/MP idênticos). Logo **âncora = a POSIÇÃO certa; a linha é indiferente** = **LEI B do Rui confirmada** (`REGRAS_NEGOCIO §16`, `HRC_ANATOMIA §14.2/§14.3`). Consequência: o off-by-one within-bucket é **inofensivo**; o lixo real é **posição errada** (→ `#HRC-NODE-OFFSET-IMPLICIT-LINES`). Reavaliar apagados/quarentenados (3ª volta #400 + #225 job 9 **não** eram lixo). |
| **#HRC-2ND-RUN-CI-TIME-DISCREPANCY** | 🟢 LOW (aberto, anatomia) | 4ª volta: 2ª run em **CI 121.87 aos 78,5 min** (alvo <10) vs 3ª volta **29,5 min** com âmbito equivalente. A explicar: semântica do CI? variância MC? estado inicial (convergência da 1ª run)? Não bloqueia. `HRC_ANATOMIA §14.4`. |

### pt67b — descobertos via os logs de runtime (Beelink live; NÃO resolver agora)

| ID | Sev | Resumo |
|---|---|---|
| **#HRC-RESULT-ZIP-413** | 🔴 HIGH (aberto) | O `POST /api/queue/hrc/results` da `GG-6029013400` devolve **413 Content Too Large** — o zip do Complete Export de uma árvore **Max=5** excede o limite de upload. O adapter fica em **retry-loop** (de 60 em 60s; não corrompe nada — 413 = sem escrita na BD). **Blocker REAL da fila:** muitas das ~72 mãos são span 5 → árvores grandes → 413 → não entram. **Investigar:** onde é o limite (proxy Railway? body-size do FastAPI/Starlette? cap 50 MB do endpoint pt21?); **fix:** subir limite / upload por chunks / compressão extra. **+ desenhar backoff/desistência** no adapter (não loop infinito). Sem isto, a fila **não solta**. Contraste: pt35 entregou 44 MB OK → o limite está algalgures entre 44 MB e o tamanho desta árvore. |
| **#QUEUE-NO-SERVER-SIDE-GATE** | 🟡 MED (aberto) | A "fila travada" era **só procedimental** (estado do `state.json` do adapter + disciplina do Rui de não arrancar). O servidor serve **72 mãos** a quem pedir (`GET /api/queue/hrc`). Em pt67 o adapter ficou ligado e a fila não estava travada de facto. **Propor gate server-side** (flag de pausa da fila — env var ou tabela — que faz o GET devolver vazio/403). Prioridade a definir pelo Rui. |

---

## pt66 (10 Junho 2026 — cirurgia ao watcher: 4 fixes, exe `9ea51ce4`, gate da fila)

Sessão dedicada ao watcher (âmbito fechado pelo Rui, diffs aprovados pelo Web).
**Backend 911 PASSED + in-process smoke ALL OK (a–m)**; `.exe` recompilado
(`9ea51ce4…c103bd4`, 12,89 MB) e publicado na **Release `watcher-pt66`** (SHA
round-trip validado). **Push da fonte pendente do OK do Rui; re-smoke real
pendente (2 mãos).** Journal: `docs/JOURNAL_2026-06-10-pt66.md` (inclui o **guia de
re-smoke** com as linhas literais da consola).

### Fechados (em código; pendente re-smoke real)

| ID | Como fechou |
|---|---|
| **#HRC-REDUNDANT-SECOND-RUN-OLD-CONFIGS** ✅ | Removido `start_calculation` do `setup_hand` — a 1ª run é lançada pelo Finish; vai-se DIRETO a navigate → Selected Subtree (**exatamente 2 runs, sem prune**). Smoke (m): ordem `nav→start_ss→finalize`, **sem `start_1st`**. |
| **#HRC-RUN-WAIT-FALSE-TRIVIAL** ✅ | `_wait_for_run_completion`: `timeout_appear` 30→180s; WARN sem "trivial"; `_find_progress_window_title` aceita **tuple** de candidatos (1ª run casa "Hand Setup" OU "Monte Carlo Sampling"). |
| **#HRC-BOUNTY-HARDCODED-50PCT** ✅ | Removido `select_bounty_mode` + gate `is_ko_tournament`; o **HRC** põe o Bounty Mode a partir da **estrutura importada** (`import_prizes`). |
| **#CI-TARGET-INITIAL-NOT-CALIBRATED** ✅ (dissolvido) | O CI deixou de ser **escrito** (default do popup = **10.0** sempre). Removidos `_fill_ci_target_in_popup`/`_find_single_edit`/`_read_edit_text` + consts CB_*/WM_* mortos + `set_ci_target_initial/refine`. Salvaguarda nova **só-leitura** `_ci_target_readback_warn`. |

### Notas / abertos

- **Correcção factual (3ª vez):** os fatores de bounty vêm do **`LOBBY_RATIO_LOOKUP`**
  (`backend/app/services/lobby_vision.py`) — **fonte única**: `0.75`/`0.50`/`0.40`/`0.33`/`0.0`.
  **Não existe `0.25`** no pipeline HRC (já corrigido em `135be97`; a cópia stale do
  `PENDENTES.md` foi corrigida aqui). Os `0.25`/`0.33` doutras notas são do `ire.py`.
- ⚠️ **Cobertura do fix (d) na re-smoke = PARCIAL.** A fila pt66 (48 elegíveis) não
  tem mãos PKO **≠0.5** (todas as KO são 0.5: 14 GG structure-driven + 25 WN forçadas
  a 0.5 no export) nem Mystery. Numa mão 0.5 o antigo e o novo são indistinguíveis →
  a re-smoke (`GG-6029013400` KO + `GG-6039094225` não-KO) valida (a)(b)(c') + o modo
  PKO 50%-via-estrutura, mas a **prova do ≠50% fica DEFERIDA** até entrar uma monster
  (0.75) / super ko (0.40). **Flag:** confirm one-off quando aparecer.
- 🟢 **#HRC-NAV-TABLE-READBACK-PENDING** (LOW) continua aberto — read-back visual do nó é manual.
- 🟢 **Salvaguarda do CI** — o formato do título "Target CI < X" (foto pt64) **não está
  verificado em código** → fail-safe **sem alarme** se diferir; re-confirmar na re-smoke e
  ajustar `_CI_TARGET_RE` se preciso.
- **Quarentenas** `GG-6028190109` + `GG-6027751209`: recalcular pós-re-smoke (re-POST sobrescreve).

---

## pt62–pt64 (9–10 Junho 2026 — lobby-IT por nome/filename; ★ smoke pt64 PASSOU [ciclo HRC ponta-a-ponta])

**pt62** (`edb47cc`) e **pt63** (`cf1401f`) — entrada do lobby pelo Intuitive Tables (pasta única, classificação determinística por **nome**; o **filename tem precedência sobre a Vision**, alinhado com o table-ss). Sessões de feature, **sem tech debts novos**. Detalhe nos journals `JOURNAL_2026-06-09-pt62.md` / `-pt63.md`.

**pt64** — **smoke real no Beelink (10 Jun, `GG-6028190109`, Hyper) PASSOU** no objetivo central: a cadeia HRC fechou ponta-a-ponta. Sinais: scope da 2ª run via **SysListView32** do dropdown (CCombo SWT) com read-back LVM (idx=1) **sem [ABORT]**; navigate foco-raiz + 2 setas → nó **HJ raise 2.0bb** (confirmado visualmente + painel Range), a bater com o `meta.json`; **Complete Export 6.78 MB / 2646 ficheiros / 2644 nós** (nó 0 = árvore completa, settings/equity coerentes — **não** é export de 1 nó); adapter `post done OK action=inserted`, move → `done\Exports\replied`; mão saiu de "Activas" (advance-hang **não** reapareceu). Commits do watcher pt64 já em main (`7f7d7ff` scope via SysListView32 + diag `77db441`/`6ba34e9`). Journal: `docs/JOURNAL_2026-06-10-pt64.md`.

### Validados AO VIVO no smoke pt64 (fixes em buffer pt61 → confirmados)

- **#HRC-2ND-RUN-BLIND-CLICKS** ✅ — scope da 2ª run lido/escrito pela lista nativa do dropdown (SysListView32 do CCombo SWT, fix pt64 `7f7d7ff`), read-back idx=1, **sem [ABORT]**; navigate parou no nó certo.
- **#HRC-EXPORT-WRITES-BUT-FINALIZE-HANGS** ✅ — adapter move `done\Exports\<hand>.zip` → `done\Exports\replied`; mão saiu de "Activas", `Total processados: 1`. O advance-hang **não** reapareceu.

### Novos abertos / refinados (smoke pt64)

| ID | Severidade | Resumo |
|---|---|---|
| **#HRC-REDUNDANT-SECOND-RUN-OLD-CONFIGS** | 🔴 HIGH (refinado pt64 — **GATE da fila completa**) | Confirmado **ao vivo** no build pt64, com **correção à descrição**: a run intermédia (Full Tree, configs antigas, **sem** navegar ao nó) é disparada **ENQUANTO a 1ª run ainda corre** (não "a seguir"). O HRC **enfileira-as** (2 janelas Monte Carlo: 1 *running* + 1 *Waiting*, fotos do Rui). Cadeia observada: Finish → 1ª run arranca → watcher abre popup e dispara intermédia → watcher navega e dispara a boa (Selected Subtree) = **3 runs no total**. Devia ser exatamente **2** (1ª do Finish; 2ª Selected Subtree após navigate). Fix = `tools/watcher_src` + rebuild `.exe` (**pt66**, ir DIRETO de fim-da-1ª-run para navigate+Selected Subtree+CI; o `meta.json` já tem `target_node_offset`+`aggressor_real_action`). Spec: `docs/WATCHER_FLUXO.md`. **A fila completa (~49 mãos em `queue_hold`) só se solta após a re-smoke pt66 passar** (decisão do Rui pendente). |
| **#HRC-RUN-WAIT-FALSE-TRIVIAL** | 🟡 MED (novo pt64, sub-item de #HRC-REDUNDANT-…) | `[WARN] [run-wait] "1ª run: janela de progresso nao apareceu em 30s — run trivial"` é um **FALSO TRIVIAL**: a janela não apareceu porque a run estava **lenta a arrancar / enfileirada**, não porque acabou. O wait posterior (2ª run, **778s**) provavelmente **cobriu todas as runs enfileiradas** (mesmo título de janela) — foi o que salvou o export. Endurecer a heurística run-wait contra runs enfileiradas com título idêntico. Fix junto com #HRC-REDUNDANT-… em pt66. |
| **#CURSOR-ANOMALY-POST-SAVE-AS** | 🟡 MED (refinado pt64 — agora **DETERMINÍSTICO**) | Era "origem desconhecida" (PENDENTES item 12). O Rui confirma padrão **reproduzível**: **"sempre o 2º nó"** na fase de guardar estratégias. Já não é anomalia aleatória — há padrão a investigar/corrigir. |
| **#CI-TARGET-INITIAL-NOT-CALIBRATED** | 🟡 MED (refinado pt64 — "pt65 CI") | pt65 exercitou o CI: `[ci]` fallback `pyautogui` **NÃO confirmado**, `ci_ok=False`; seguiu com o **default do HRC** (que era 10.0 no popup — **inócuo hoje, não garantido**). Confirma a necessidade do tratamento **SysListView32 / read-back** para o campo CI (mesma técnica do scope pt64) + limpar `CB_*` morto. Fix em pt66. |
| **#HRC-BOUNTY-HARDCODED-50PCT** | 🟡 MED — **VERIFICADO pt65 (decompile); CONFIRMA-SE como bug; entra no pt66** | **Veredicto (bytecode `_local_only/main_inspect.txt` + `ANALYSIS.md`; o decompile `.py` falhou nestas 2 funções, recuperadas via disassembly).** A sequência em `setup_hand` é: (1) **`import_prizes`** = `click_rel(PRIZE_FOLDER)` + `paste_path(prize_path)` — **só carrega o ficheiro** `payouts.json`; **não toca no dropdown**. É o HRC que, ao ler a estrutura (bountyType/progressiveFactor pt42d + `@flags`/`@prizeBountyComponent`), **põe o Bounty Mode no sítio** (= o que o Rui observou). (2) **`if is_ko_tournament(prize_path): select_bounty_mode(wpos)`** (`patched_funcs.py:2097-2099`) corre **A SEGUIR**. `is_ko_tournament` devolve True se `@flags` tem `'B'` OU há `@prizeBountyComponent` OU o raw lowercase contém `"bounty"`/`"pko"` (a estrutura PKO bate **sempre** — `"bountyType":"PKO"` contém `pko`). `select_bounty_mode` é **cego/hardcoded**: clica `(635,451)` + `down,down,enter` → **PKO 50%**, sem ler nada. **Quem corre por último ganha → `select_bounty_mode` CLOBBER a estrutura**, mas **só em KO** (gate). Efeito: **não-KO** ✅ (gate salta, fica o modo da estrutura); **PKO 50%** = redundante/inócuo; **PKO 25% / Super KO / KO ≠50% / progressive** = a estrutura põe o modo CERTO e o hardcode esmaga-o para 50% → **ERRADO** (Mystery KO não chega ao watcher hoje — gated a montante). **Fix (pt66, mesmo `.exe`/rebuild):** **remover** a chamada `select_bounty_mode` + o gate `is_ko_tournament` (fica dead) → o modo da estrutura (HRC no import) prevalece em TODOS os formatos; **não** é preciso mapa `payouts.json`→dropdown + read-back (o HRC já faz o mapeamento da estrutura). **Validação na re-smoke pt66 (1 caso KO ≠50%):** confirmar que, sem o hardcode, o HRC mostra o Instant% certo da estrutura — único ponto não-observado hoje (o clobber esconde o que o HRC poria num KO). Colunas **KO-T$/KO-P$ = 0.0 numa mão NÃO-KO é esperado**; confirmar **≠0** numa PKO real na re-smoke. |

### Quarentena de resultados HRC (integridade de dados — registo consultável)

Dois `hrc_jobs` ficam **QUARENTENADOS** — **não confiar no zip**, recalcular após o fix pt66:

| hand_id | Estado em `hrc_jobs` | Porquê |
|---|---|---|
| **GG-6028190109** | `inserted` 10 Jun 12:18 (smoke pt64) | Resultado de **corridas sobrepostas** (3 runs enfileiradas, #HRC-REDUNDANT-…); o export pode não refletir a 2ª run boa **isolada**. |
| **GG-6027751209** | `done`, postado no **arranque** do adaptador (9 Jun) | **STALE** — postado antes da lousa limpa; pode já não bater com o pipeline atual. |

**Mecânica de invalidação (descoberta pt64 — sem DELETE necessário):** re-POSTar a mão pós-pt66 **sobrescreve** — `upsert_hrc_job_result` faz `ON CONFLICT (hand_db_id) DO UPDATE` (`backend/app/services/hrc_jobs.py:124`), preservando `submitted_at`. Basta a mão voltar ao robot e o adapter re-POSTar; **não é preciso mexer na BD à mão**. (Apagar de vez, se se quiser: `DELETE FROM hrc_jobs WHERE hand_db_id = (SELECT id FROM hands WHERE hand_id = '<…>')`.) **Nota:** estes jobs **não estão visíveis em nenhuma UI hoje** (`hrc_jobs` ≠ `/hrc-sessions`; ver runbook §4.3 corrigido em pt64) → a quarentena é só de dados, sem limpeza de ecrã. O zip de `GG-6028190109` está **preservado na app** (`hrc_jobs.result_zip` BYTEA) independentemente do prune do disco do Beelink.

### Suspeito a investigar (read-only, sem ação)

- **`players_left = 3179` numa mesa GG** (smoke pt64) — valor suspeito (demasiado alto para "players left" duma mesa). Investigar a origem (`_resolve_players_left` / table-ss / lobby) antes de confiar no ICM dessa mão. Pode distorcer a escala ICM (cross-ref **#HRC-TOTAL-CHIPS-NULL**, pt61).

---

## pt61 (6 Junho 2026 — adaptador HRC instalado no Beelink; spec do watcher)

Sessão operacional (Beelink). Sem código no repo excepto docs. Journal: `docs/JOURNAL_2026-06-06-pt61.md`.

### Novos abertos

| ID | Severidade | Resumo |
|---|---|---|
| **#HRC-REDUNDANT-SECOND-RUN-OLD-CONFIGS** | 🔴 HIGH | A **2ª fase do watcher diverge** de `docs/WATCHER_FLUXO.md` (spec canónico do comportamento desejado). No build atual (`.exe` `cdfc7247`/pt42d), a parte "configurar → Finish → 1ª run" está **correta**, mas a seguir à 1ª run o watcher faz um **Prune (errado)** + uma **run intermédia com configurações antigas (redundante)** antes da run boa. **Devia** ir DIRETO a: seleccionar o nó da **1ª ação não-fold** (1ª ação voluntária da mão) → Scope = **Selected Subtree** → **CI=10** → OK → esperar → exportar. **Sem prune. Exatamente DUAS runs** (1ª lançada pelo Finish; 2ª Selected Subtree). **Fix = código do watcher (`tools/watcher_src`) + reconstruir o `.exe`, sessão dedicada.** Spec: `docs/WATCHER_FLUXO.md`. *(Registado em pt61; o tag tinha sido mencionado em sessão anterior mas nunca chegou ao repo.)* |
| **#HRC-EXPORT-WRITES-BUT-FINALIZE-HANGS** | 🔴 HIGH | O export **grava o zip** em `done\Exports\<hand_id>.zip` (confirmado: gravado às 9:31), mas o passo de **finalização** ("Bloco 1 → finalize Bloco 2") **não completa** → a mão fica em **"Activas" indefinidamente** → o watcher (**serial**) **não arquiva nem passa à mão seguinte**, **bloqueando a fila toda**. **Observado em pt61:** zip de `GG-6027751209` gravado **9:31**, mão ainda **"Activas" às 9:58** (27 min depois). Relacionado com o **"Bloco 2" incompleto** do build `cdfc7247`/pt42d. **Fix na sessão de código do watcher** (`tools/watcher_src` + reconstruir `.exe`). Spec: `docs/WATCHER_FLUXO.md`. |
| **#HRC-TOTAL-CHIPS-NULL** (escala do ICM) | 🟡 MED (a investigar) | No `meta.json` de `GG-6027751209` (pt61), **`total_chips = null`**. No export, os **stacks da mesa** estão em **milhões** (~3M cada) mas a **estrutura ICM** (`structure.chips ≈ 1.56M`) e os **`otherstacks`** (~275k → 2k) estão **noutra escala**. **Possível desajuste de escala a distorcer o ICM**, ou normalização interna do HRC. **A verificar:** (1) de onde vem `total_chips` (porque é null); (2) se a escala dos `otherstacks`/total **bate** com os stacks da mesa. Refs: pipeline de hints (`meta.json`), `backend/app/services/queue_export.py`. |

**Pista de implementação — `#HRC-REDUNDANT-SECOND-RUN-OLD-CONFIGS`:** o `meta.json` de cada mão **JÁ fornece** o que a 2ª run precisa — **`target_node_offset`** (o nó a seleccionar) + **`aggressor_real_action`** (`type`/`size_bb`/`position` da 1ª ação não-fold). **Confirmado em `GG-6027751209` (pt61):** `aggressor_real_action = SB raise 4.5bb`, `target_node_offset = 8`. Ou seja, o watcher só tem de **USAR o `target_node_offset`** para seleccionar o nó (Selected Subtree → CI=10), em vez de fazer prune + run redundante. **A informação já existe no pipeline; falta o watcher consumi-la.**

### ★ Re-smoke pt61 (restart LIMPO do `cdfc7247`) — CONCLUSÃO que SUPERSEDE o enquadramento acima

Re-smoke com restart limpo do exe **`cdfc7247`** (SHA do exe ATIVO no Beelink, HRCWatch, **confirmado**) + leitura do log da 1ª mão. Reenquadra os dois HIGH:

1. **O swap ESTÁ no `cdfc7247`** — o log mostra `navigate_to_target_node` (8 downs), 2ª run Selected Subtree disparada, scope set, CI 10, export. **NÃO é stale-exe / no-swap.** As coords do log **batem com a fonte atual** (`SCOPE_OPTION_SELECTED_SUBTREE_REL=(274,108)`, `SCOPE_DROPDOWN_REL=(278,67)`, `CI_TARGET_POPUP_REL=(270,109)`, `CALCULATE_BUTTON=(204,64)`). **⇒ Recompilar da fonte atual NÃO resolve** (produz coords idênticas).

2. **`#HRC-REDUNDANT-SECOND-RUN-OLD-CONFIGS` — nome ENGANADOR (não há prune nem run redundante no `cdfc7247`).** O defeito real: a 2ª run **clica ÀS CEGAS e falha o alvo** — no ecrã o nó certo não fica seleccionado nem o Scope vira "Selected Subtree". O código **loga "sucesso" porque regista o ENVIO do clique, não o efeito**. Causas: (a) **geometria do popup mudou** — popup Nash agora **436×230**, mas a calibração de 18 Mai foi contra **416×214** → os pixels-rel já não aterram nos widgets; (b) `CI_TARGET_FIELD_X/Y=0` (placeholder) → `[WARN] CI Target initial: coords não calibrados`; (c) `navigate_to_target_node` faz só N down-presses **sem verificar foco / nó-inicial**; (d) sintomas: 1ª run `tree=0`, 2ª run "terminou em 20s" (runs triviais). **Os cliques verificados via Win32 (detecção do popup por título + OK por `BM_CLICK`) funcionam; os cliques `pyautogui` por pixel-rel (dropdown Scope, opção, campo CI) e o navigate são CEGOS e falham.** **Fix REAL:** (i) **recalibração INTERACTIVA** das coords (Rui ao Beelink, smoke devagar como 18 Mai) contra a geometria actual **436×230**; (ii) **read-back de verificação** (ler o texto do combo Scope / o nó seleccionado antes de prosseguir) em vez de clicar e assumir; depois build novo (regra 1-exe). **Recompilar SEM recalibrar+read-back não muda nada.** Helper de captura: `_local_only/get_calibrate_coords.py` (Beelink).

3. **`#HRC-EXPORT-WRITES-BUT-FINALIZE-HANGS` — causa-raiz ENCONTRADA (não é finalize do `setup_hand`).** O `setup_hand` **retorna** e imprime `[QUEUED]`; o hang é no **main loop do `.pyc` (Baltazar `main()`, NÃO em `patched_funcs.py`)**. O loop só faz `archive_hand` + avança quando `zip_is_ready(export_zip)` é True — e `zip_is_ready` **exige o zip em `done/replied/<hand>.zip`** (mtime ≥ `batch_start`), com `EXPORT_WAIT_TIMEOUT = 86400` (**24h**). **Mas o adaptador** (`reconcile_done`), após POST OK, faz **`_safe_unlink`** (apaga o zip de `done/Exports`) e **nunca popula `replied/`** — o próprio adaptador declara `replied/` "morto" (`#WATCHER-META-INJECTION-BYPASSED`). **Mismatch estrutural:** o main loop espera um handshake (`replied/`) que **nenhum componente satisfaz** → cada mão fica "Activas" até ~24h → fila serial bloqueada. **Fix candidato (sem recompilar):** o adaptador **mover** `done/Exports/<hand>.zip` → `done/replied/<hand>.zip` após POST OK (em vez de `unlink`) → `zip_is_ready` True → arquiva → avança. **Alternativa (recompilar):** swap/patch do `zip_is_ready`/`main` para não exigir `replied/`. A validar na re-smoke com adaptador a correr em paralelo.

**Fix do advance-hang — APROVADO (pt61, lado ADAPTADOR, sem recompilar):** `reconcile_done` (`tools/hrc_adapter/hrc_adapter.py`), após `post_done` OK, **move** `done/Exports/<hand>.zip` → `done/replied/<hand>.zip` (em vez de `_safe_unlink`) → o `zip_is_ready` do main loop Baltazar passa a True → arquiva + avança. **Guardrails (Rui):** (i) **sem loop** — o adaptador **não re-scaneia nem re-POSTa** a partir de `replied/` (`detect_done_zips` só varre `done/*.zip`+`done/Exports/*.zip`, e `replied` ∈ `RESERVED_NAMES`; mover para lá tira o zip do radar → 0 re-POST); (ii) **`replied/` não acumula** — `prune_replied(max_age)` por idade em cada tick (unlink puro, **nunca** POST; idade generosa, ex. ≥1h, bem depois de o watcher ter consumido o zip). *(Rui alérgico a pilhas de zips.)* Implementação bundled no passo de build (D abaixo), não em commit avulso.

**Plano (sessão de build, NÃO recompilar antes da recalibração):** (a) Rui corre `get_calibrate_coords.py` no Beelink com o popup Nash aberto (436×230) e aponta os elementos reais → captura rel offsets de: dropdown Scope, opção Selected Subtree, campo CI no popup, nó-alvo na Strategy Table, botão Calculate; (b) meto offsets na fonte + **read-back** (ler o texto do combo Scope **e** o nó seleccionado antes de avançar); (c) fix do adaptador (move-to-`replied/` + `prune_replied`); (d) escrevo `instala_ptXX.bat` (**parar o processo do watcher** antes de trocar + **apagar todos** os exes + instalar **só o novo**, regra 1-exe) + build + deploy; (e) re-smoke com **watcher E adaptador a correr** → esperar 2ª run a aterrar + avanço da fila.

### Fixes pt61 — EM BUFFER (escritos, suite verde; NÃO built/pushed)

A re-smoke (acima) re-diagnosticou; estes fixes implementam o plano. **Diffs em buffer**, suite **897 PASSED**; `.exe` **NÃO** recompilado (pós-recalibração de coords no Beelink).

| ID | Estado | Resumo |
|---|---|---|
| **#HRC-NODE-OFFSET-SB-JAM-OFFBY1** | ✅ FIXED (buffer) | `offset_within_bucket` (`backend/app/services/hrc_node_offset.py`) deixou de depender de all-in: o nó-alvo é a acção ORIGINAL = **1ª opção** do array (`_array_for_raise`) → 1º nó de raise da posição (non-SB=0; SB=1 após Complete). A convenção 0/1/2 antiga fazia +1 em jams (SB jam 2→1; non-SB jam 1→0). Regressão `GG-6027751209` (SB-vs-BB jam ~4.5bb): offset **8→7**. +1 teste, 4 corrigidos. |
| **#HRC-2ND-RUN-BLIND-CLICKS** | ✅ FIXED (buffer) | A 2ª run clicava Scope/opção/CI ÀS CEGAS (pyautogui) no popup SWT e logava sucesso pelo ENVIO, não pelo efeito → Full-Tree disfarçado de Selected Subtree. Fix (`tools/watcher_src/patched_funcs.py`): **Scope via Win32** (`CB_SETCURSEL`+`CBN_SELCHANGE`+`CB_GETCURSEL` read-back; combo achado pelo item "Selected Subtree"; reusa padrão `export_strategies` pt35), **CI via Win32** (`WM_SETTEXT`+`WM_GETTEXT`, Edit único). **Scope não confirmado → ABORTA** a mão (`_cancel_nash_popup`, sem OK/export; `setup_hand` devolve None → `.failed` + avança, sem loop). CI não confirmado → WARN-e-segue (não muda Full-vs-Subtree). Baseline coords (fallback) recalibrados 436×230. Falha SINALIZADA, nunca fingida. +Win32 helpers; testes Win32+fallback+abort (watcher 45). |
| **#HRC-EXPORT-WRITES-BUT-FINALIZE-HANGS** | ✅ FIXED (buffer) | Adaptador (`tools/hrc_adapter/hrc_adapter.py`): `reconcile_done` após POST OK **move** o zip `done/Exports/<hand>.zip` → `<parent>/replied/` (= `dirname(export)/replied/` que o `zip_is_ready` Baltazar observa) em vez de `_safe_unlink` → desbloqueia arquivar+avançar. Guardrails: (i) sem loop (`detect_done_zips` não varre `replied/`; `RESERVED_NAMES`); (ii) `prune_replied(≥1h)` por idade no main loop (unlink puro, nunca POST). +4 testes. |
| **#HRC-NAV-TABLE-READBACK-PENDING** | 🟢 LOW (aberto) | O `navigate_to_target_node` loga o nó ESPERADO (de `aggressor_real_action`, dinâmico) mas **não lê o conteúdo** da Strategy Table (widget SWT) para confirmar a aterragem — falta um **snapshot do controlo no Beelink** (à imagem dos child-windows do popup em pt33). Até lá: **verificação visual** na re-smoke. Decisão Rui aceite. |
| **#OPEN-COUNT-DRIFT-HRC-NODE-OFFSET-LATENT** | 🟢 LOW (aberto, **realçado pt61**) | `count_lines_for_position` (posições ANTES do agressor) ainda usa constantes (`_TEMPLATE_DEFAULT_OPEN_COUNT`), não as arrays geradas. Não morde a mão pt61 (preceding=6 correcto). **Se OUTRA mão aterrar no nó errado na re-smoke, é a suspeita nº1** (não o `within_bucket`, já corrigido). |

**Navigate (pt61):** foco-click no nó-raiz `(221,131)` MAIN rel + setas×offset (primário, independente de geometria); **direct-click** `(222, 131+offset×18.71)` como reserva (`_NAV_USE_DIRECT_CLICK`, Rui alterna ao vivo). `instala_pt61.bat` em `_local_only/` (regra 1-exe). **Pendente:** recalibração interactiva das coords + build + smoke.

---

## pt50–pt58 (3–4 Junho 2026 — re-import end-to-end + fuso Lisboa + Vision Claude + import por pasta)

Arco contínuo. Suite **840 → 876 PASSED**. Journal: `docs/JOURNAL_2026-06-04-pt50-pt58.md`.

### Fechados (✅)

| ID | Estado | Resumo |
|---|---|---|
| **#FIX-A** (HM3 clobber) | ✅ FECHADO (`81255b2`) | O UPDATE do PATH A do HM3 (`hm3.py`) podia pisar `all_players_actions` já enriquecido (cruzamento SS↔HH) se a HH HM3 chegasse depois. Guard `CASE`: só escreve se o existente estiver vazio. Convergência independente da ordem. |
| **#FIX-B1** (relink ambíguos) | ✅ FECHADO (`81255b2`) | O relink órfão do table-SS passou a reconsiderar também `tm_ambiguous`, não só `no_match_to_hand`. |
| **#FIX-B2** (name-estrito) | ✅ FECHADO (`81255b2`) | Validação de nome só nos sites de nome fiável (`_NAME_RELIABLE_SITES = {GGPoker, Winamax}`). |
| **#FIX-B3** (match desacoplado) | ✅ FECHADO (`6578f63`) | Match do table-SS desacoplado do upload numa função determinística **R** (`compute_table_ss_match` pura + `_apply_hand_link` + `reconcile_table_ss` que re-avalia TODAS as rows + `_persist_table_ss_match`). Idempotente, convergente, independente da ordem. `POST /api/table-ss/reconcile`. |
| **#GG-PLAYED-AT-LOCAL-NOT-UTC** | ✅ FIXED (pt49) → **SUPERSEDED** (pt51 `4645960`) | A rota UTC da pt49 (GG+PS → UTC DST-aware) foi **substituída pela convenção Lisboa-naive** (ver abaixo). Toda a hora-de-evento passa a Lisboa wall-clock `timestamp` naive; **GG/PS gravam verbatim** (zero matemática DST). A "validação de Inverno" (provar DST-aware da 1ª timestamp PS) **dissolve-se** — já não convertemos GG/PS. *Porquê: o Rui joga sempre de Portugal; guardar Lisboa-naive mata a ambiguidade DST na origem.* |
| **Vision OpenAI→Claude** | ✅ FECHADO (`af44a75`/`659830e`/`8eb5ec2`/`343e30f`) | Causa do "Failed to fetch" no Discord sync = **quota OpenAI esgotada** (429), não timeout. Migrado todo o Vision para `claude-sonnet-4-6`; função OpenAI removida, dep `openai` fora, `OPENAI_API_KEY` removida do Railway. Fix do "engole erro" (Vision falhada não marca `vision_done`) + endpoint `POST /api/discord/revision-replayers`. |
| **#TABLE-SS-SITE-FROM-FILENAME** | ✅ FECHADO (`45aa12a`) | Site do table-SS lido do **nome do ficheiro** (`Shot<N>-<Site>-<ts>`, `_FILENAME_SITE_MAP`), autoritativo sobre a Vision; removido `_correct_site` do compute para o filename não ser pisado. **V2 (prompt Vision multi-site) descartado** — o feltro muda por torneio/fase (não por sala) e as imagens não são guardadas. |
| **#WN-NAME-CANONICAL** | ✅ FECHADO (`defd715`) | `clean_winamax_tournament_name` apara `#NNN`+`(ID)`, preserva `150K`/`80K`. |
| **#TABLE-SS-NAME-DIRECT-DISAMBIG** | ✅ FECHADO (`901e965`+`eddca4d`) | multi_tn desambigua directo pelo nome (exactamente-1 candidato); `name_tokens_subset` tolera título GG truncado (prefix-match do último token). |

### Novos abertos (do arco)

| ID | Severidade | Resumo |
|---|---|---|
| **#WPN-PS-TABLE-SS-TIME-ONLY-MATCH** | 🟡 MED | WPN/PS não estão em `_NAME_RELIABLE_SITES` → o table-SS casa-os **só por tempo** (sem validar nome), porque os nomes WPN (string de garantia) e PS (NULL) não servem. **Superfície de falso-match.** Mitigado agora que o site é determinístico (filename) — reduz candidatos ao site certo — mas o risco mantém-se em multi-tabling WPN/PS na janela. Sem fix desenhado; reavaliar se aparecerem falsos matches reais. |
| **#TABLE-SS-IMAGE-NOT-STORED** | 🟢 ✅ **RESOLVIDO (16 Jun, pt73)** | **Já não é verdade.** O `table_ss_processing_log` **passou a guardar a imagem** em `img_b64 TEXT` (coluna via ensure-migration `table_ss.py:194`; escrita no upload `table_ss.py:919/930/…/988`). **Prova ponta-a-ponta (recuperação 14 Jun):** **120/120** capturas com `img_b64` guardado + **re-Vision a partir do guardado** validada (`_reprocess_failed_row` decodifica `row["img_b64"]`, `table_ss.py:1051`; endpoint `/reprocess-failed`). A re-Vision retroactiva que o debt dizia impossível **funciona** — sem re-fornecer o ficheiro. **Âmbito:** verificado **para o caminho TABLE-SS** (`table_ss_processing_log.img_b64`). O caminho **screenshot/replayer** é separado (guarda `img_b64` em `entries.raw_json` — ver `MAPA §3.4`) e **fora do âmbito deste debt**. Origem da persistência: pt71 E2 (imagem do table-SS) + reprocesso pt73. **Reforça** o princípio de hoje "a imagem é a outra metade e tem de ser persistida" (`REGISTO_CONCEITO 2026-06-16`; `DESANON_ANATOMIA §3.2.1`) — já satisfeito no caminho table-SS. |

### appimport (ferramenta nova, `tools/appimport`)

Import por pasta local (`3127ea0`/`11c496d`/`fc2ac7d`) — GG HH/TS + IT + SS manual + lobby por pasta. `config_local.py` gitignored (setup manual no PC do Rui). Não é tech debt; registado para descoberta.

---

## pt48 (2 Junho 2026 — reenquadramento docs + editor de tags + IRE-WN por preço)

Sequência da pt47. Suite **818 PASSED**. Journal: `docs/JOURNAL_2026-06-02-pt48.md`.

| ID | Estado | Resumo |
|---|---|---|
| **#IRE-WN-BY-PRICE** | ✅ FECHADO (`87f3c67`) | Evolução do **#IRE-WN** (pt46). O gate WN deixou de ser "nome na tabela curada" → passou a **`buy_in` no mapa de preços** `{50,100,125,250}` (stack 20000). Resolve a limitação da pt46 (335 mãos WN PKO 2026 fora da tabela → IRE None): `hands.buy_in` é 100% fiável na WN (0 NULL em 219). Todos os WN PKO 2026 acendem o IRE, retroactivo, sem manutenção de nomes. `winamax_ire_tournaments.py` (mapa por preço) + `ire.py:_compute_ire_winamax`. |
| **#TAGEDITOR-PORTAL** | ✅ FECHADO (`32d6746`) | Frontend. O popover de sugestões do editor de tags ficava cortado pelo `overflow:hidden` dos cartões de grupo na Estudo (`Hands.jsx` 950/1065). Render via React portal no `<body>` (`position:fixed` por `getBoundingClientRect`). Capacidades + os 3 outros usos intactos. |
| **#DEFAULT-TAGS-STALE-TESTS** | ✅ FECHADO (`dec944f`) | `test_queue_default_tags` assumia 6 keys; o basket Speed Racer da pt47 (`eb839e0`) levou-o a 8. Fix stale-only (assert 8 + as 2 keys speed-racer). Não-bug. |
| **#DOCS-PROPOSITO-REENQUADRAMENTO** | ✅ FECHADO (`ebd8e5e`) | `## Propósito` (VISAO_PRODUTO) + `## Modelo de domínio` (CLAUDE) reposicionados: propósito = centralizar o estudo; o cruzamento SS↔HH GG é mecanismo (da GG), não a razão de ser. |

**Override por nome no IRE-WN** — **não implementado**, registado para a 1ª excepção real
(ex.: deepstack com stack ≠ 20000 ao mesmo preço): dict por nome a sobrepor-se ao preço.

---

## pt47 (2 Junho 2026 — reset BD + reimport + 3 fixes)

Reset total da BD + reimport + investigação read-only. Suite **não corrida** (validação
read-only contra prod). Journal: `docs/JOURNAL_2026-06-02-pt47.md`.

| ID | Estado | Resumo |
|---|---|---|
| **#HRC-BASKET-SPEED-RACER** | ✅ FECHADO (`eb839e0`) | `DEFAULT_TAGS` (`hrc_queue.py`) ganha `speed-racer`+`speed-racer-ft`. Match exacto normalizado (`NORM(t)=ANY`) exige as 2 formas (diferem em nº de tokens), ≠ IRE que usa substring. +10 mãos elegíveis no Andar 1 (validado contra prod). Partiu 2 testes stale → fechados na pt48 (`dec944f`). |
| **#DUP-REPLAYER-COUNT** | ✅ FECHADO (`10d7229` contador + `56025af` lista) | "Discord sem match" / `/ss-without-match` contavam por entry (LEFT JOIN `entry_id`), inflando com replayer duplicados (mão liga a UMA entry; irmãs ficavam `hand_db_id NULL` apesar de a mão existir). Fix: `is_matched` por `entry_id` **ou** `hand_id=GG-{tm}` + dedupe por TM na lista (`COALESCE(tm,'e'||entry_id)` — sem-TM não colapsam). 17→0. |
| **#VILLAIN-MISSED-ON-ENRICH-GUARD** | ✅ FECHADO (`42dc4e8`) | O guard de idempotência de `_enrich_hand_from_orphan_entry` (`screenshot.py`) fazia `return` cedo, saltando o append da `discord_tag` do canal **e** `apply_villain_rules`. Como o auto-rematch chama o enrich por cada entry com TM, a 2ª/3ª entry de uma mão partilhada perdia a tag do 2º canal **e** a Regra C não re-corria → vilão perdido (7 mãos GG `nota` do 30/05). Fix: o guard passa a apensar a tag + correr a Regra (idempotente) antes do `return` → self-healing nos re-imports. |

---

## Estado actual (2 Junho 2026 — investigação read-only: match SS de mesa ↔ mão GG)

Sessão read-only (zero código). Diagnóstico completo de porque é que a importação em massa dos
SS do Intuitive Tables ligou pouco às mãos GG. Plano detalhado em
**`docs/PLAN_2026-06-02-table-ss-gg-match.md`**.

### Tech debts novos abertos (3)

| ID | Severidade | Resumo |
|---|---|---|
| **#GG-PLAYED-AT-LOCAL-NOT-UTC** | ✅ FIXED (pt49) → **SUPERSEDED (pt51, ver secção pt50–pt58)** | **⚠️ A rota UTC abaixo foi substituída pela convenção Lisboa-naive (pt51 `4645960`): GG/PS gravam verbatim em Lisboa, sem conversão para UTC; a "validação de Inverno" no fim deste verbete dissolveu-se.** Registo histórico da rota pt49: o parser GG gravava `hands.played_at` **verbatim** da string de hora da HH (que está em **hora local de Lisboa**), **sem normalizar para UTC**; a HH GG **não traz marcador de fuso**. No Verão (WEST/UTC+1) o stored fica **+1h adiantado** face ao UTC; no Inverno (WET/UTC) o offset é 0. Só o **table-SS** (pt38, casa por **tempo**) está exposto — o pipeline principal GG casa por **TM number** (`hand_id=GG-{tm}`), imune. **Sintomas** (Verão): SS de mesa GG ou **não liga** (torneio curto — a mão verdadeira cai 1h fora da janela ±5min, ex. id=13 tn287210981) **OU faz MATCH FALSO ~1h antes** (torneio longo — id=14 Daily Special $88: SS leu blinds **350/700** Level12, mas ligou a mão de Level7 **175/350** stored 18:13; a verdadeira 350/700 está stored 19:14 = 18:14 UTC = SS), com **`players_left` errado a alimentar o HRC**. Contradiz o "TZ OK (offset ~±1min)" do `#TABLE-SS-GG-MULTITABLING-MATCH` (esse era só dos WN, que ligam bem). **Validação read-only pt49 (fuso real):** ligando `replayer_link` (Discord `posted_at`, UTC absoluto) à mão via `raw_json.tm`, `máx(played_local − posted_utc) = offset` → **+1h consistente** em **Abril (Portugal)** (13–28/04, n=187) **e em Maio (Portugal)** (n=351). **✅ FIX (decisão Rui, sem backfill — a BD foi limpa e re-importada com os dados já certos):** **(1) parser GG** (`gg_hands.py`) via helper partilhado `lisbon_local_to_utc` (`app/utils/timezones.py`) — interpreta a hora da HH como local de Lisboa e converte para UTC **DST-aware pela data da própria mão** (nunca offset fixo, nunca a data de "agora"); `played_at` passa a UTC. **(2) PokerStars tinha o bug IDÊNTICO** — a HH PS traz a 1ª timestamp em **WET/Lisboa** (`… 18:20:32 WET [13:20:32 ET]`; o bracket é **ET**, não UTC) e o parser gravava-a verbatim → corrigido na **mesma mudança** (`hm3._parse_hand`, ramo `PokerStars`/`GGPoker`). **Winamax e WPN** gravam **UTC explícito** (`… UTC`) → **sem alteração** (guard em teste). **(3) UI display=Lisboa** (`frontend/src/utils/datetime.js`: `isoDateLisbon`/`dateTimeLisbon`) — storage=UTC, display=Lisboa: datas que slicavam a string crua (passariam a mostrar UTC) e horas reconvertidas para `Europe/Lisbon`. +11 testes (`test_played_at_tz.py`: Verão −1h / Inverno 0h / DST-aware / PS / guard WN). **Incerto (não bloqueia):** DST-aware (Lisboa, Inverno **0h**) vs constante +1h — indistinguível em Verão e sem âncora de Inverno na altura; `ZoneInfo("Europe/Lisbon")` assume Lisboa (aposta mais sólida). **Passo de validação no recomeço end-to-end:** nas mãos **PS** cruzar **WET→UTC** vs **ET→UTC** (a HH PS traz as duas); se baterem no Verão **E** no Inverno, fica **PROVADO** que a 1ª timestamp é DST-aware (Lisboa real) — e por analogia reforça que o GG também é. |
| **#TABLE-SS-GG-MULTITABLING-MATCH** | 🟡 MED — **REENQUADRADO pt73** | **★ DECISÃO pt73 (DECIDIDO / POR IMPLEMENTAR, ainda NÃO no código):** o match table-SS↔mão GG (Pergunta 1) passa a ser PRIMARIAMENTE por **hand-id extraído do nome do ficheiro** (TM antes do timestamp → `GG-{TM}`; ex. `...6081471864-...` → `GG-6081471864`; confirmado nas HH). Determinístico → **mata o multi-tabling de raiz**. Isto torna o **fingerprint (hero_stack ±20% + big_blind) e o nome-directo OBSOLETOS/REDUZIDOS a FALLBACK** — usados só quando o ID falta no nome (formato antigo). O fix desenhado abaixo (chokepoint `_resolve_match` por nome/fingerprint) passa a ser **plano B**, não a forma primária. **NOTA P1 vs P2:** isto resolve **só "qual é a mão"**; **não** resolve "quem senta onde" (o bug dos vilões em cadeiras trocadas — P2, âncora por stack; detectado pelo Rui em `img/89`/`GG-6042783089`, quantificado por scan de fit = 66/185 misfit; ver `DESANON_ANATOMIA.md §3`). Detalhe: `DESANON_ANATOMIA.md §2.2`; `REGISTO_CONCEITO` 2026-06-16. — *Diagnóstico original (mantido):* Em multi-tabling GG (média 3.2 torneios concorrentes na janela ±5min, até 8), o `_resolve_match` (`table_ss.py`) desambigua via `resolve_tournament_number` (resolver de nomes frágil) em vez de comparar o **nome fiel da imagem** directamente com os candidatos + **impressão digital (hero_stack_bb ±20% + big_blind exacto)**. Resultado: GG liga só 33% (vs WN 73%). Dos 99 SS GG falhados: 68 sem mão na janela, ~9 que o matcher devia apanhar, 2 Winamax mal classificados. **⚠️ Reavaliar pós-reimport (pt49):** a leitura "TZ OK ~±1min" era só dos **WN** — o **GG tinha o bug de fuso `#GG-PLAYED-AT-LOCAL-NOT-UTC`** (`played_at` +1h no Verão) a **esconder a mão certa 1h fora da janela ±5min**, logo parte dos "sem mão na janela" e dos "ambíguos" era **artefacto do fuso**, não import em falta nem multi-tabling. Com o fuso já corrigido + a BD re-importada, **recontar**; suspeitos reais que sobram: **nomes genéricos do WPN** (string de garantia, não nome real), **multi-tabling** GG, e **gaps reais de import**. Nomes GG são **fiéis** (prefixos de série `250-H:` a MANTER — NÃO limpar). Fix desenhado (chokepoint `_resolve_match`, serve upload+relink; single_tn/WN intactos; 0 falsos positivos validados em 31). Alvo final: alimentar `#HRC-MTT-STACKS-PAGE-SKIPPED-ON-NULL-PLAYERS-LEFT`. |
| **#TABLE-SS-VISION-SITE-MISCLASS** | ✅ FIXED (pt49) | O Vision do SS de mesa classificava esporadicamente o site errado (2 SS Winamax — `EXPLORER 150K #032`, `GALACTI` — marcados `GGPoker`), fazendo o match procurar candidatos no site errado. **Fix:** `_correct_site(name, read_site)` em `table_ss_vision.py`, aplicado pós-parse no upload (`routers/table_ss.py`, antes de gravar a site no log e filtrar candidatos). **Regra A** (string pura, 0 falsos positivos): nome com `#NNN` trailing (nº de mesa Winamax) + site≠Winamax → Winamax. **Regra B** (cross-check BD, conservadora): se a sala lida não tem torneio com o nome e existe exactamente 1 outra que tem → essa. Senão mantém. Loga INFO em cada correcção (auditoria); fail-safe a erro de BD. Validado read-only sobre as 258 SS do backup: A apanha `EXPLORER 150K #032` (0 nomes não-WN têm `#NNN` trailing na BD), B apanha `GALACTI`→`GALACTICA`; A∪B = exactamente as 2, 0 falsos positivos. **Self-healing no `relink_orphan_table_ss`** (pt49 follow-up): aplica `_correct_site` às rows já gravadas em `no_match_to_hand` **antes** do match, persiste a site corrigida no log (`_persist_corrected_site_table_ss`, guard `result='no_match_to_hand'` = idempotência/escopo) e re-corre o match no site certo — corrige retroactivamente sem re-upload (espelha o padrão do `#VILLAIN-MISSED-ON-ENRICH-GUARD`). Escopo só `no_match_to_hand`; confirmado read-only que a única mal-classificada em prod (`EXPLORER 150K #032`) está nesse estado (nenhuma presa em `success`/`tm_ambiguous`). +11 testes (`test_table_ss_vision.py` 8, `test_table_ss.py` 3). |

---

## Estado actual (31 Maio 2026 — pt46, UX do ImportModal + comentários stale WN + imagem replayer GG)

Diagnóstico read-only (sessão de ingestão pós-pt45). Sem código alterado.
Tech debt novo aberto **#IMPORT-MODAL-UX** (🟢 LOW, sem pressa) + bónus de
correcção de comentários stale. Contexto: imports de HH GG correram bem
(`hh_import` 29 788 → 58 214, +28 426 mãos reais; backend `/health` 200), mas
o modal mostrou feedback enganador ("✗ + N screenshots matched") em re-imports
dedupados. Não é bug funcional — é display.

### Tech debt novo aberto em pt46 (1)

| ID | Severidade | Resumo |
|---|---|---|
| **#IMPORT-MODAL-UX** | 🟢 LOW | UX do feedback de import de HH no ImportModal. **Três faces do mesmo problema** + 1 bónus. Não-bloqueante; os imports gravam correctamente, só o display engana. |

**Detalhe #IMPORT-MODAL-UX (3 pontos):**

1. **`status:"error"` em re-import dedupado.** O ramo HH de `/api/import`
   devolve `"status": "ok" if total_inserted > 0 else "error"`
   (`backend/app/routers/import_.py:507`). Num re-import do mesmo ZIP, o dedup
   por `hand_id` faz `total_inserted=0` (comportamento **correcto**), mas o
   backend devolve `status:"error"` e o modal (`ImportModal.jsx:181`, regra
   `result.status === 'error'`) pinta **✗ vermelho**. Resultado: re-importar o
   mesmo ZIP garante ✗ na 2ª vez, sem haver erro nenhum. **Fix:** distinguir
   "0 novas por dedup" (sucesso benigno) de erro real — ex. novo status
   `"noop"`/`"duplicate"`, ou o frontend tratar `hands_inserted===0 &&
   errors===0` como sucesso.

2. **Com 0 inseridas, o modal esconde as mãos e só mostra `rematched.length`.**
   `formatResult` (`ImportModal.jsx:104-110`, caso `hh`/`hh_zip`) só lista
   `hands_inserted` se `> 0`; com 0 inseridas a única parte truthy que resta é
   `rematched.length` → "N screenshots matched". Combinado com o ✗ do ponto 1,
   dá **"✗ + N screenshots matched"** sem contexto de quantas mãos havia /
   foram ignoradas. **Fix:** mostrar sempre "0 novas · X duplicadas" mesmo
   quando inserted=0.

3. **"N screenshots matched" é total global, não delta.** O `rematched`
   (`import_.py:514`, `len(rematched)`) vem de um **auto-rematch global** que,
   no fim de *qualquer* import HH, varre **todos** os entries órfãos
   (replayer/image/screenshot com Vision feito + TM) e re-enriquece a mão
   GG-`<tm>` correspondente — **independente do conteúdo do ZIP**. Por isso 3
   ZIP diferentes deram exactamente o mesmo número (ex. "176"): é o mesmo pool
   global recomputado igual. **Fix:** rotular como global ("N órfãos
   re-associados (total)") ou calcular/mostrar o delta atribuível a este import.

**Bónus — comentários stale no `import_.py` (corrigir quando se mexer):**
~linhas **534** e **577** dizem "hoje só GG / WN é só P&L / `ts_applicable=False`
p/ Winamax", mas o código já tem `OPERATIONAL_TS_SITES = {"ggpoker", "winamax"}`
(desde `7ecf092`, pt44) — **WN popula o operacional, não só o P&L**. O comentário
contradiz o código e foi o que induziu uma descrição errada em sessão anterior.
Corrigir o texto dos comentários (não há mudança de comportamento).

**Refs:** `backend/app/routers/import_.py:507,514,534,577`,
`frontend/src/components/ImportModal.jsx:104-110,181`.

### #REPLAYER-IMG-HH-FIRST ✅ FECHADO (pt46, commit `4eef6b5`)

Mãos GG em Estudo deixaram de mostrar a imagem captada do replayer. **Causa:**
no caminho **HH-primeiro** (HH importada antes do replayer Discord sincronizar —
a ordem actual), o enrich (`_run_vision_for_entry` → match em `hands` →
`_enrich_hand_from_orphan_entry`) liga o entry replayer à mão e mete os nomes,
mas **não propaga a imagem**: `hands.screenshot_url` fica NULL (o dict passado e
o `raw_json` do entry não têm chave `screenshot_url` — só `img_b64` +
`file_meta.og_image_url`), e o entry é `replayer_link`, que o flag
`has_screenshot_image` (só `'screenshot'`) não aceitava. As duas vias de imagem
do frontend (`Hands.jsx:1272`) falhavam apesar dos ~242 KB de `img_b64` estarem
no entry ligado. **Evidência prod:** G-6019169471 (entry 2357, `replayer_link`,
`img_b64` presente, `screenshot_url`=NULL, `hand_created` < `entry_created` →
HH-primeiro). **313 mãos** afectadas (todas com `img_b64`).

**Fix (Opção B, read-path, sem backfill):** `has_screenshot_image` (lista
`hands.py:715` + detalhe `:1331`) passa a aceitar `replayer_link` COM `img_b64`;
`GET /api/screenshots/image/{id}` (`screenshot.py:1664`) serve `entry_type IN
('screenshot','replayer_link')`. Como é computado em query-time, as 313 ficam
repostas no deploy sem UPDATE. Suite 797 → 801 PASSED.

### Tech debt latente novo aberto em pt46 (1)

| ID | Severidade | Resumo |
|---|---|---|
| **#CDN-URL-EXPIRY-OLD-REPLAYER-SS** | 🟢 LOW | ~147 mãos GG antigas (replayer-primeiro) têm `hands.screenshot_url` a apontar para a URL CDN GG (`user.gg-global-cdn.com/...png`), externa e potencialmente expirável. O `img_b64` está no entry replayer ligado → recuperáveis pelo mesmo read-path do `#REPLAYER-IMG-HH-FIRST` (frontend cair no fallback do entry quando a URL falha, ou migrar `screenshot_url`→endpoint interno). Não bloqueia; só se imagens antigas começarem a falhar. |

**Refs:** `backend/app/routers/hands.py:715,1331`,
`backend/app/routers/screenshot.py:1664`, `frontend/src/pages/Hands.jsx:1272`.

---

## Estado actual (28 Maio 2026 — pt42d, payouts.json HRC-native + hints em meta.json)

Re-abertura pt42c após smoke real expor `Instant=0%` no HRC apesar do
`bountyType="PKO"`/`progressiveFactor=0.5` aplicado em pt42c. Investigação
profunda da biblioteca HRC persistente (`%USERPROFILE%\HoldemResources\
.metadata\.plugins\net.holdemresources.calculator\structuredata\custom.json`)
revelou que o HRC rejeita campos extra no `payouts.json` (cai em ICM puro)
e que o `name` da structure precisa de sufixo `"  #<tournament_number>"`
(2 espaços + `#tn`) para evitar colisão na biblioteca.

**Causa raiz definitiva (3 elementos):**

1. **4 hints top-level no payouts.json** (`equity_model`, `max_players`,
   `script_path`, `aggressor_real_action`) injectados em pt23+ via
   `_build_watcher_hints` faziam o HRC rejeitar a structure inteira.
2. **`structures[i].name` sem sufixo `#<tn>`** — colidia na biblioteca
   persistente HRC com entries de outros torneios com o mesmo nome
   ("GRAVITY", "INTERSTELLAR", etc.).
3. **Pipeline pt42c v1 (Seat lines conversion WN→PS)** era desnecessário —
   HRC lê formato WN nativo `(<chips>, <X>€ bounty)` directamente. Reverter.

**Path B (Web/Rui):** backend + watcher source recompilado + adapter na
mesma sessão. Manual flow (Rui descarrega → importa no HRC) é o caso de
uso principal; smoke real Beelink usa uvicorn local antes do push para
prod.

Suite **730 → 734 PASSED** (+15 testes pt42d − 14 modificações: T1 +5
novos, T2 −4 removidos T2 pt42c +1 update, T3 +2 novos, T4+T5 9 updates +
1 e2e + 1 novo). 0 regressões.

**Watcher recompilado:** `.exe` SHA `cdfc7247...3262` (pt35 era
`33eae43a...c53c4f`); ~13 MB; build sucesso. Smoke harness in-process
parte num sub-test pre-existente (mock `_wait_for_finish_ready` ausente);
issue ortogonal documentado em debt novo.

**Adapter recompilado** (Python puro): `rewrite_script_path_in_meta`
substitui `rewrite_script_path_in_payouts`; target file = `meta.json`.

### Fixes shipped em pt42d (1 ✅)

| Debt | Estado | Detalhe |
|---|---|---|
| **#WN-BOUNTY-NULL-IN-HRC-PIPELINE** v2 | ✅ FIXED RESOLVIDO (pt42c v1 revertido em T2; pipeline v2 final em T1+T3+T4+T5+T6+T8+T9+T10) | (a) Helper `_format_winamax_structure_name(name, tn) → "<Name>  #<tn>"`. (b) `_patch_winamax_payouts_bountytype` aceita `tournament_number` kwarg + aplica formato HRC-aceite. (c) `convert_gg_hh_to_pokerstars_compatible`: branch WN PKO removido → passthrough total para PS/WN/WPN (HRC lê formato WN nativo). (d) `build_queue_zip`: `payouts.json` no zip = APENAS `{name, folders, structures}` (sem merge com hints top-level — HRC rejeitava). (e) `_build_hand_meta` ganha 4 hints (`equity_model`/`max_players`/`script_path`/`aggressor_real_action`) — movidos do payouts para meta. (f) `tools/watcher_src/patched_funcs.py`: 4× `_payouts.get(...) → hand_meta.get(...)`; load `_payouts` órfão removido. **`.exe` recompilado, SHA `cdfc7247...3262`.** (g) `tools/hrc_adapter/payouts_helpers.py`: `rewrite_script_path_in_payouts → rewrite_script_path_in_meta` (target = meta.json). (h) `hrc_queue.py`: comentário Andar 1 actualizado. Suite **734 PASSED**. Refs: `backend/app/services/{queue_export,hrc_queue}.py`, `backend/tests/test_queue_export.py`, `tools/watcher_src/patched_funcs.py`, `tools/hrc_adapter/{payouts_helpers,hrc_adapter}.py`. |

### Tech debt novo aberto em pt42d (1)

| ID | Severidade | Resumo |
|---|---|---|
| **#SMOKE-HARNESS-WAIT-FOR-FINISH-MOCK-MISSING** | 🟢 LOW | `_local_only/watcher_decompile/swap_and_smoke.py` smoke harness in-process bate em `RuntimeError: WIZARD_FINISH_NEVER_RE_ENABLED` quando exercita `setup_hand`. Causa: `_wait_for_finish_ready` (função APPEND adicionada pt30) faz polling Win32 do botão Finish (disabled→enabled), mas o harness usa `CallRec` mocks que retornam None → polling timeout 60s. **Não-bloqueante:** o `.pyc` swapped é gravado em `repacked/` ANTES do smoke; PyInstaller consome-o sem problema. Fix: adicionar mock dedicado de `_wait_for_finish_ready` (returns True) no `install_module_mocks` ou pré-bind no `g["_wait_for_finish_ready"]`. Pre-existente desde pt30; só agora foi exercitado (sessões pt30-pt42c não correram swap_and_smoke.py com este path). Não bloqueia builds futuros (.pyc continua a gerar OK). |

### Decisões internas pt42d (refinamentos defensivos)

- **Path B (vs Path A passthrough degrada watcher temporariamente)** —
  Rui prefere recompilar watcher na mesma sessão para evitar regressão
  na 2ª run do robot. Custo: +T8+T9+T10. Benefício: smoke real Beelink
  pós-T12 é completo (manual + robot ambos).
- **`_payouts` removido por completo do watcher** (Opção B "limpeza" em T8)
  em vez de manter dead code (Opção A). −15 / +9 linhas. Sem risco
  porque o load era only consumed nas 4 substituições.
- **Ficheiro `payouts_helpers.py` mantém o nome** (sem renomear para
  `meta_helpers.py`) — só a função interior muda. Reduz reinstalação
  no Beelink (cópia de 1 ficheiro inalterada).
- **`compute_hero_bounty_from_hh` + `_extract_winamax_seat_bounties`
  mantidos** para audit no manifest (informativo, não muda HRC). Sem
  alteração face a pt42c.
- **Tournament_number defensivo como kwarg-only com default None** em
  `_patch_winamax_payouts_bountytype`. Permite backward-compat dos 4 tests
  existentes pt42c (passam tn=None implícito) — 0 tests partidos por kwarg.
- **payouts.json escrito SEMPRE no zip** mesmo sem blob (defensivo: `{name:
  "/", folders: [], structures: []}`). Pré-pt42d era hints-only-fallback;
  agora é structures-only-fallback.

---

## Estado anterior (27 Maio 2026 — pt42c, WN bounty via HH crua)

Re-abertura `#WN-BOUNTY-NULL-IN-HRC-PIPELINE` (🔴 HIGH, novo) na mesma
sessão pt42b após smoke da mão 4 expor bounty null em WN PKO. **1232
mãos PKO 2026 Winamax** (em 179 torneios distintos) tinham
`payouts_json.bountyType="None"` (lobby vision não classifica nomes WN
como bounty) e `convert_gg_hh_to_pokerstars_compatible` em passthrough
total para non-GG.

**Opção C escolhida pelo Web/Rui:** estender gerador para converter HH
WN → PS-compat com bounty inline (sem dependency de TS Winamax). HH
Winamax já tem `(<X>€ bounty)` literal por Seat.

**Pipeline pt42c:**
1. `_extract_winamax_seat_bounties(hh)` parsea `{nick: bounty_eur}`.
2. `_inject_bounties_winamax_to_ps_format(text, ...)` reescreve Seat
   lines (`(<chips>, <X>€ bounty)` → `(<chips> in chips, €<X> bounty)`).
3. `compute_hero_bounty_from_hh` para audit Hero (source `"hh"` novo;
   Vision ganha se > HH — regra pt41 mantida).
4. `_patch_winamax_payouts_bountytype` sobrescreve `bountyType="PKO"` +
   `progressiveFactor=0.5` no zip (BD não tocada).
5. `build_queue_zip` orquestra; `converted_format="pokerstars_compat"`
   no manifest para WN PKO.

Suite **725 → 730 PASSED** (+15 testes pt42c líquidos; 0 removidos).
Backend-only — `.exe` do watcher não tocado.

**Smoke real Beelink pendente** — re-descarregar mão WN PKO + correr no
HRC para validar formato WN-converted. Se HRC rejeitar (header / markers
WN diferem de PS), escalar para conversão completa em pt42d.

### Fixes shipped em pt42c (1 ✅)

| Debt | Estado | Detalhe |
|---|---|---|
| **#WN-BOUNTY-NULL-IN-HRC-PIPELINE** (novo) | ✅ FIXED (diffs aplicados; smoke real Beelink pendente) | (a) Helpers `_extract_winamax_seat_bounties`, `_patch_winamax_payouts_bountytype`, `_inject_bounties_winamax_to_ps_format`, `compute_hero_bounty_from_hh`. (b) Constante `WINAMAX_BOUNTY_FORMATS = ("pko", "super ko", "ko")`. (c) Branch WN PKO em `convert_gg_hh_to_pokerstars_compatible`. (d) `build_queue_zip` aplica patch ao `payouts.json` no zip + audit Hero bounty WN com source `"hh"`. (e) `hrc_queue.py` actualiza comentário do gate Andar 1 (sem mudar SQL — WN já passava). Mystery KO WN continua excluído (gated em `MYSTERY_FORMATS` desde pt41). Suite **730 PASSED**. Refs: `backend/app/services/queue_export.py`, `backend/app/services/hrc_queue.py`, `backend/tests/test_queue_export.py`. |

### Decisões internas pt42c (refinamentos defensivos)

- **HH crua como source no audit** (`h.get("raw")`, não `hh_text`
  convertido). Razão: pós-converter, o formato Seat já está em PS-compat
  e o regex WN não matcha. Audit corre **antes** do output ser escrito.
- **Patch do `payouts.json` antes do merge com hints**. Preserva semântica
  do merge (hints ganham se houver chave em conflito).
- **`compute_hero_bounty_from_hh` separado de `compute_hero_bounty`** pt41
  (em vez de estender o helper GG). Source enum claro: `"hh"` (WN) vs
  `"ts"` (GG). Sem refactor da função pt41.
- **`anon_map["Hero"] → nick_real` para identificar Hero em WN** (WN não
  anonimiza; nick real aparece literal nos Seats). Distinto do GG (onde
  `nick == "Hero"` literal funciona após `_replace_hashes`).
- **Pipeline degrada gracefully** quando HH sem bounty token (`hh_bounties`
  vazio → devolve text inalterado). Defensivo para formatos não-PKO ou
  variantes inesperadas.
- **`progressive_factor` parâmetro com default 0.5** (Rui confirma WN
  PKO 50% universal). Override possível por keyword se variantes
  aparecerem no futuro.
- **`_patch_winamax_payouts_bountytype` força PKO mesmo quando bountyType
  era "Other"** (não só "None"). Decisão defensiva: gerador para WN PKO
  sabe melhor que o lobby vision (override total).

---

## Estado anterior (27 Maio 2026 — pt42b, 3-bet IP por posição)

Re-abertura `#HRC-BETTING-SCRIPT-IMPROVEMENTS` para refinar o **3-bet
clássico IP**: a regra pt42 aplicava-se a 1 array partilhado
(`SIZES_3BET_IP`); pt42b separa em **5 variáveis por posição**
(`SIZES_3BET_EP/MP/HJ/CO/BU`), cada uma com sizing calibrado pela eff
spot-específica entre essa posição e o opener.

**CASO B** (todos os candidatos) → **CASO A** (sobrescreve a posição que
efectivamente 3-betou). Decisão Web #3: CASO B gera mesmo sem 3-bet real,
para o HRC simular vilões com sizings calibrados em vez do default
genérico.

Suite **705 → 713 PASSED** (+20 helpers unit, +6 e2e, +2 apply_overrides;
0 removidos). Backend-only — `.exe` do watcher não tocado.

### Fixes shipped em pt42b (1 ✅)

| Debt | Estado | Detalhe |
|---|---|---|
| **#HRC-BETTING-SCRIPT-IMPROVEMENTS** (re-aberto) | ✅ FIXED (diffs aplicados; commit/push pt42c) | (a) 4 helpers novos no gerador: `_canonical_3bet_position`, `_candidate_3bet_positions_ip`, `_eff_spot_specific_bb`, `_default_3bet_for_candidate`. (b) `_bucket_3bet` devolve `SIZES_3BET_<POSITION>` para clássico IP. (c) `build_sizings_overrides` chama `_apply_caso_b_3bet_overrides` antes do loop + `_apply_caso_a_3bet_ip` no branch bc=2 IP por posição. (d) Template JS: 5 variáveis novas + `POSITION_LABELS_BY_N` const + `positionLabelForIdx` + `getSizings3BetByPositionIP` switch. Squeeze + SB/BB + opens intocados. Suite **713 PASSED**. Refs: `backend/app/services/hrc_script_gen.py`, `backend/app/services/hrc_scripts/mtt_advanced_canonical_2026.js`, `backend/tests/test_queue_export.py`. |

### Tech debt novo aberto em pt42b (1)

| ID | Severidade | Resumo |
|---|---|---|
| **#POSITION-LABELS-PYTHON-JS-DRIFT** | 🟠 **Fase 1 ✅ FEITA+DEPLOYED** (`8c9ef66`, pt91) — Fase 2 + caso BTN por verificar (era 🔴 HIGH) | `POSITION_LABELS_BY_N` duplicado em Python (`queue_export.py:167`) e JS (`mtt_advanced_canonical_2026.js`). **As duas DIVERGIRAM** e o `90c07ad` (pt89, opens per-posição) expôs o sintoma: o override `SIZES_OPEN_<pos>` é gravado pela tabela Python (n=6 índice 0 = **"MP"**) mas o script lê pela tabela JS (índice 0 = **"UTG"**) → o override **falha o assento** → o 1º a agir mostra o open default em vez do real. **Caso reportado:** `H-6101135610` (GG-6101135610), UTG ~3,3 BB dá open-shove all-in; a árvore dá ao UTG `R 2.00 + R 3.16` em vez de só ALLIN (o ALLIN foi para `SIZES_OPEN_MP`, que o HRC nunca pergunta para aquele assento). **Convenção correcta = JS (HRC: UTG no topo, BU)** — provado por 5 fontes (display do HRC; docs de navegação `hrc_node_offset.py` l.4/11/323; comentário "BU no HRC"; pt25d `hrc_docs_v1`; tabela JS que corre dentro do HRC). **Fase 1 (fix do bug, 6-max):** `_POSITION_LABELS_BY_N[6]` índice 0 `"MP"→"UTG"` (uma troca; **manter `BTN`** — é traduzido a `BU` por `_canonical_3bet_position`; trocá-lo regrediria o botão como candidato a 3-bet). Navegação é index-based → sem regressão. **✅ Fase 1 FEITA (`8c9ef66`, deployed; +7 testes migrados MP→UTG; prova local na HH real `GG-6101135610`: `SIZES_OPEN_UTG=['ALLIN']`, `SIZES_OPEN_MP` desaparece).** ⚠️ **POR VERIFICAR (nota Rui pt91): caso BTN <5BB** também a dar 2 sizes em vez de só all-in — confirmar se é o mesmo drift. **Provavelmente NÃO:** o BTN já normalizava `BTN→BU` de forma consistente (Fase 1 não o muda), logo um BTN-short a falhar seria **causa distinta** (re-investigar — possível deteção de all-in do agressor / default per-posição do BU). **Fase 2 (separada):** n=7/8/9 divergem estruturalmente + labels `EP/UTG1` exigem lockstep de 3 ficheiros. |

### Decisões internas pt42b (refinamentos defensivos)

- **`_eff_spot_specific_bb` recebe `remaining_chips`** (não nicks + dicts).
  API mais clean; T3 calcula remaining no caller via
  `_init_pot_from_blinds_antes` + opener override.
- **`_canonical_3bet_position` rejeita SB/BB/UTG** (devolve None). Caller
  filtra. BTN aceito como alias de BU (defensivo, alguns sites usam BTN
  no `position`).
- **Dedup EP1/EP2 no helper** (`_candidate_3bet_positions_ip` devolve
  `[EP, MP, ...]`, não `[EP, EP, MP, ...]`). 9-handed raríssimo mas
  contemplado.
- **CASO A reusa `_array_for_raise`** via shallow copy do action com
  `effective_stack_at_action_bb` substituído pela eff spot. Sem
  duplicação de lógica.
- **2 parses HH por mão** (1 no CASO B helper, 1 no CASO A helper se
  3-bet IP real). Aceitável (HH pequena, ~2ms por parse).
- **Open-jam edge case validado**: `opener_to_bb` é o jam-to-bb (ex.: 15
  BB se UTG jam de 1500 chips em level 100), não 2 BB. Bucket low gera
  `2.3 × 15 = 34.5 BB` no CASO B. Testes asseram isso explicitamente.

---

## Estado anterior (26 Maio 2026 — pt42, regra universal de sizings + cortar turn/river)

Sessão de **gerador `script.js`**: fecha `#HRC-BETTING-SCRIPT-IMPROVEMENTS` (HIGH) com 2 mudanças
combinadas (Pedidos 1 + 2): (1) variante "pré-flop + flop only" no template canónico (turn/river
sem betting); (2) regra universal de sizings — 1ª opção = sizing original da HH (ou ALLIN se a
acção foi all-in), 2ª opção = ALLIN (se eff ≤ 25) ou non-all-in default por tipo de aposta (se
original foi ALLIN). Efectiva passa a ser **dinâmica por raise** (`min(raiser_remaining,
max(active_opponents_remaining)) / BB`), substituindo a `compute_effective_stack_bb` global.
Tabela pt25f de multiplicadores 3-bet (`_classic_3bet_band`, `_compute_classic_3bet_overrides`)
**abandonada**.

Suite **666 → 685 PASSED** (-16 testes obsoletos pt25f, +35 novos pt42). Modo investigação +
implementação read-only; sem commits/push/smoke real Beelink ainda — diffs em buffer para
validação Web. **`.exe` do watcher não tocado.**

### Fixes shipped em pt42 (1 ✅)

| Debt | Estado | Detalhe |
|---|---|---|
| **#HRC-BETTING-SCRIPT-IMPROVEMENTS** | ✅ FIXED (diffs em buffer) | (a) Template canónico `mtt_advanced_canonical_2026.js`: `POSTFLOP_FORCE_CHECKDOWN_AFTER` força checkdown após FLOP para **todos** os live counts (2..9) — turn/river ficam sem betting modelado, só check. Reduz árvore. (b) Gerador `hrc_script_gen.py`: regra universal por acção — 1ª opção sempre original (ou ALLIN se a acção foi jam); 2ª opção: ALLIN se `effective_stack_at_action_bb <= 25` e original NÃO ALLIN, OU non-all-in default por tipo (open 2 BB se eff>8 e não-blind; 3-bet clássico 2.3/2.7/3.0×opener_to_bb conforme bucket; squeeze 3.0×opener; 4-bet 2.3×3-bet anterior; 5-bet 2.2×4-bet anterior). 4-bet/5-bet ficam em pot-fraction (compatibilidade com `getSizings4Bets`/`5Bets`); conversão BB→fraction em `_array_for_4bet5bet_in_pot_fraction`. Parser ganha 4 campos novos por acção: `previous_raise_to_bb`, `opener_to_bb`, `is_all_in` (95% threshold de `_ALL_IN_EFFECTIVE_THRESHOLD` partilhado com `hrc_node_offset`), `effective_stack_at_action_bb`. Removidos: `_CLASSIC_3BET_DEFAULTS`, `_classic_3bet_band`, `_compute_classic_3bet_overrides`. Suite **685 PASSED**. Refs: `backend/app/services/hrc_script_gen.py`, `backend/app/services/hrc_scripts/mtt_advanced_canonical_2026.js`. |

### Tech debt novo aberto em pt42 (1)

| ID | Severidade | Resumo |
|---|---|---|
| **#OPEN-COUNT-DRIFT-HRC-NODE-OFFSET-LATENT** | 🟢 LOW | `count_lines_for_position` em `services/hrc_node_offset.py:88-105` usa `_TEMPLATE_DEFAULT_OPEN_COUNT = 2`, mas o template default actual (pt29 tree-size control) é `[2]` com 1 entrada. Quando uma posição **não** está em `script_overrides` (não fez raise voluntária na HH), o offset é calculado com 2 linhas por posição em vez de 1 → `target_node_offset` pode estar **+1 por posição precedente**. **Não é regressão pt42** (vive desde pt29). Cross-ref com `#TEMPLATE-DEFAULT-OPEN-COUNT-MISMATCH` se quisermos abrir um par. Fix: alinhar `_TEMPLATE_DEFAULT_OPEN_COUNT` com `len(template_default)` (1, ou ler dinamicamente do template). Impacto real: navegação 2ª run aterra 1+ linhas a mais quando o raiser real está depois de uma posição sem override. **Validar empiricamente em smoke real** pt42 antes de elevar severidade. |

### Investigação Q1-Q8 pt42 (read-only, antes da implementação)

A investigação ficou no journal pt42 e cobre: (Q1) localização do código a tocar; (Q2) 3
opções de cortar turn/river com trade-offs (Opção A escolhida — `POSTFLOP_FORCE_CHECKDOWN_AFTER`);
(Q3) detecção de tipos de raise (já existia no parser, faltava expor previous/opener);
(Q4) detecção de all-in via 95% threshold (reutilizado de `hrc_node_offset`);
(Q5) efectiva dinâmica por acção como min(raiser_remaining, max_opp_remaining);
(Q6) 11 edge cases E1-E11 com tratamento; (Q7) testes a remover/reescrever/adicionar;
(Q8) 4 cenários smoke (1 por site) para próxima fase.

### Decisões internas pt42 (refinamentos defensivos)

- **Threshold ALLIN partilhado.** `_is_all_in_for_actor` reusa `_ALL_IN_EFFECTIVE_THRESHOLD =
  0.95` de `hrc_node_offset.py` em vez de duplicar (single source of truth para a heurística
  "raiser commits ~all"). Threshold INCLUSIVO: 950/1000 → True, 949/1000 → False.
- **4-bet/5-bet ficam em pot-fraction.** Considerada Opção II (renomear `SIZES_POT_*BET_*` →
  `SIZES_*BET_*` em BB, mudar JS function para `sizingBigBlinds`) mas rejeitada — mudança
  estrutural maior do template. Optou-se por conversão BB→fraction *dentro do gerador*
  (`_array_for_4bet5bet_in_pot_fraction`), preservando a forma do template.
- **Boundary do gate "eff > 8 BB" inclusiva no <=.** `_compute_default_for_open` devolve None
  para `eff <= 8` (não `eff < 8`). Validado por teste dedicado.
- **`opener_to_bb` é None para o open (auto-referência).** Para `bet_count > 1` aponta ao open.
- **`effective_stack_bb` parâmetro de `build_sizings_overrides` mantido para retro-compatibilidade
  da assinatura**, mas **não é usado** (a efectiva é por acção). Caller pode passar None.

---

## Estado anterior (25-26 Maio 2026 — pt41, 2 fixes HIGH: bounty via TS + anchor lobby)

Sessão com **2 fixes HIGH shipped** + re-disparo lobby validado + reversão da guarda.
Suite **651 → 661 → 666 PASSED**. SHAs: `a942ac7` (bounty) → `0707978` (docs betting) →
`6409b19` (anchor) → redeploy reversão guarda (mesmo commit, env-var only). Cronologia em
`docs/JOURNAL_2026-05-25-pt41.md`.

### Fixes shipped em pt41 (3 ✅)

| Debt | Estado | Detalhe |
|---|---|---|
| **#HERO-BOUNTY-FROM-TS-DERIVATION** | ✅ FIXED (`a942ac7`) | Bounty base por torneio vem de `tournament_summaries.buy_in_bounty` (Hero `max(Vision, base)`, vilões `base`, `€` mantido); hardcode `_HERO_BOUNTY_DEFAULT_USD=250` **removido**. Gate Andar 1 GG-only: PKO/SuperKO/KO exigem TS com bounty; **Mystery KO excluído**; vanilla sem token (Opção A); Winamax/PS passthrough. `lookup_bounties` + `bounty_by_key` em `build_queue_zip`; defensiva 422 `pko_without_ts_bounty`; manifest audit. `GET /api/hrc/pending-ts` + banner D1 no `/hrc`. Smoke real do Rui: Hyper Special $108 importou com **bounty €50 correcto**. |
| **#LOBBY-ANCHOR-PRESTART-REGRESSION** | ✅ FIXED (`6409b19`) | Resolver **source-aware** (`anchor_mode='during_play'`\|`'prestart'`; lobby passa `prestart`). **TIER 0** (`_query_summaries`): selecção **closest** (`ORDER BY abs`) + janela por modo (prestart `[anchor−12h, anchor+2h]`; during_play `[anchor−24h, anchor]` inalterado). 🟢 **Validação empírica:** msg 05-09 13:38 — código antigo teria mis-resolvido para o TS de 05-08 (dia anterior); o novo **rejeita** e devolve `tm_not_found` honesto. Mis-resolve silencioso → erro honesto. |
| **#RESOLVER-TIER12-WINDOW-NO-START** | ✅ FIXED (`6409b19`) | Mesmo commit do anchor: `_decide_window` source-aware — **ramo-2** (sem `start_time_iso`) prestart `[posted−12h, posted+2h]` (forward-aware, em vez de `[posted−12h, posted−30min]` que excluía o torneio que arranca após o post); **ramo-1** forward 2h→4h (1ª hand importada entra ~1-2h depois do start). **Re-frame pt41:** o impacto real-world era modesto — as Winamax (caso TIER 1/2) têm `start_time_iso` → ramo-1, e desbloqueiam-se com **re-run** (hands já importadas), não com o anchor; o valor concreto do TIER 1/2 foi o **forward +4h do ramo-1**. Mecanismo da janela corrigido em ambos os ramos. |

### Tech debt novo aberto em pt41 (1)

| ID | Severidade | Resumo |
|---|---|---|
| **#MYSTERY-KO-DUAL-SUPPORT** | 🟡 MED | Mystery KO **excluído do /hrc na pt41** (gate site-agnóstico em `select_andar1_rows`). O HRC não modela Mystery KO de forma fiável: o bounty é **oculto/aleatório** e a equity muda radicalmente **pré- vs pós-ITM** (antes do ITM o bounty é desconhecido → a mão joga-se como **vanilla**; depois do ITM os bounties revelados viram **KO fixos**). **Suporte futuro:** (1) pré-ITM tratar como vanilla (sem token); (2) pós-ITM como KO fixo com o bounty revelado; (3) `players_left` vs `places_paid` como gate ITM (depende do pipeline SS de mesa fidedigno); (4) importar os TS Mystery (**~1.353 mãos GG 2026** à espera, ex. `tn 281143347` Sunday Showdown). **Bloqueado por:** estado ITM por mão + decisão de produto sobre o valor de bounty pós-revelação. Refs: `queue_export.py:MYSTERY_FORMATS`; `hrc_queue.py:select_andar1_rows`/`pending_ts_hands`. 📎 **Estrutura real observada:** ver «Estruturas observadas — Mystery Bounty PokerStars (2026-05-28)» na secção IRE (split 33/67, mecânica de desbloqueio, coluna Bounty = acumulado). |

### Tech debt novo aberto em pt41 (2 — foco pt42)

**`#HRC-BETTING-SCRIPT-IMPROVEMENTS`** — 🔴 **HIGH 🚨 URGENTE (foco pt42, junto com Track A)**

**Contexto.** O pipeline HRC gera, por mão, `<hand_id>/script.js` que tenta replicar a *betting structure* da HH (o gerador de scripts; ver investigação dependente para localização exacta). Descoberto pelo Rui **após o shipping do Track B** (`dfc13a5`): o script actual **limita a análise estratégica** em dois aspectos.

**1. Cobertura de streets — variante "pré-flop + flop only".**
Hoje o script gera bets em **pré-flop + flop + turn + river**. Em muitos estudos só interessam **pré-flop + flop**; turn/river expandem a árvore desnecessariamente (mais nós, mais tempo de cálculo, ruído). **Pedido:** variante com bets **só em pré-flop + flop**; turn e river ficam **sem betting** (só check).

**2. Alternativas estratégicas para o Hero.**
O script replica apenas as acções **tomadas** na HH. O Hero fica com uma única acção (ex.: all-in 14.6 BB no BU), **sem alternativas a comparar** (ex.: mini-raise 2 BB). Permite validar o resultado da linha jogada, mas **não comparar opções**. **Regra-base proposta pelo Rui** (única a fixar agora):
- Stack effective do Hero **> 8 BB** num **spot de open** → o script **inclui SEMPRE mini-raise 2 BB**, independentemente da acção tomada na HH.
- Mantém as acções **reais** da HH (replica) **+** adiciona o 2 BB se ainda não estiver lá.
- **Outros sizes** (3.5 BB, 4 BB, etc.) e **outros spots** (3-bet, BB defense, cold-call) → regras a definir em **sessão futura**; **NÃO fixar agora**.

**Investigação dependente (sessão futura, antes de codificar):**
- Localização do gerador de scripts no código (provável `backend/app/services/` — `hrc_script_gen.py`/`queue_export.py`).
- Parâmetros que controlam bets **por street** e **por seat**.
- Como expor as variantes: múltiplos scripts no zip? botão alternativo no `/hrc`? toggle? parâmetro de endpoint?
- Como **detectar "spot de open do Hero"**: posição + stack effective + acções anteriores (ninguém abriu antes).
- Smoke test: gerar zip com scripts expandidos e validar que o **HRC processa** as alternativas.
- Eventual **interacção entre os 2 aspectos** (variantes de streets × alternativas do Hero → combinatória de scripts).

**Severidade HIGH 🚨:** afecta a utilidade analítica de **cada mão estudada** no HRC (o produto nº1 é o estudo). Refs (a confirmar na investigação): gerador de `script.js`; pipeline `build_queue_zip` (`queue_export.py`); painel `/hrc`.

### Tech debt novo aberto em pt41 (3)

| ID | Severidade | Resumo |
|---|---|---|
| **#LOBBY-SYNC-PAGINATION-LIMIT** | 🟡 MED | `gather_candidates` (`lobby_sync.py`) usa `channel.history()` **sem paginação explícita** → o discord.py assume **`limit=100`** por defeito. Em janelas largas (30d+) com canal activo, as mensagens **mais antigas** registadas no log **não são puxadas** pela history → não entram como candidatas do `sync-recent`. **Sintoma pt41:** probe encontrou **34** `tm_not_found` (12-24 Mai); `sync-recent` com 30d apanhou só **12** (as mais recentes). O Rui **confirmou que NÃO apaga mensagens** no `#lobbys` → não é apagamento, é limitação de paginação. **Solução futura:** paginação explícita (loop até esgotar a janela) ou `limit` maior. Não-bloqueante. Refs: `lobby_sync.py:gather_candidates`. |

---

## Estado actual (24 Maio 2026 — pt40, guarda lobby + regressão do anchor)

Sessão fechada. Investigação read-only dos 2 HIGH temporais (passos 5+6 do plano
pt39) destapou uma **regressão do anchor do TIER 0** (pt39) + motivou uma **guarda
de produção**; entregou o **Track B** (`#HRC-PER-HAND-DOWNLOAD` ✅, `dfc13a5`) e o
teste do Track B expôs um **2º achado crítico** — **bounties hardcoded errados** no
converter GG→PS. Cronologia em `docs/JOURNAL_2026-05-24-pt40.md`.

### 🛡️ Guarda activa (prod) — NÃO reverter sem fix

- **`DISCORD_LOBBY_AUTO` mudada para `false`** em prod (env var Railway, serviço
  `poker-app`, redeploy `ac26c261` SUCCESS). Desliga o handler real-time do
  `#lobbys`. **Motivo:** o anchor bugado (debt abaixo) escreveria
  `tournament_payouts` errado no próximo SS de lobby.
- **Não ligar de volta** (nem correr sync manual de lobby, nem re-disparar os
  **~24 `tm_not_found`** acumulados) **até `#LOBBY-ANCHOR-PRESTART-REGRESSION`
  estar resolvido.** Após o fix: reverter `DISCORD_LOBBY_AUTO=true` + re-disparar
  via `sync-recent` `dry_run`→real.

### Tech debt novo aberto em pt40 (1)

| ID | Severidade | Resumo |
|---|---|---|
| **#LOBBY-ANCHOR-PRESTART-REGRESSION** | 🔴 HIGH (latente) | O anchor `start_time ≤ posted_at` do TIER 0 (introduzido em pt39 `35286c1`, ramo *anchored* de `_query_summaries`) assume **SS tirada durante o jogo** (verdade p/ **table-ss**), mas falha p/ **lobby SS** — tirada na **fase de inscrição**, com o torneio a começar **~30min DEPOIS** do post. **Simulação pt40** dos 3 lobby `tm_not_found` do pt37: **1 resolve certo** (Deepstack $125, post 1h após start), **1 fica `tm_not_found`** (Daily Hyper $80 18-Mai — instance certo ainda não começou + anterior >24h), **1 mis-resolve para o DIA ANTERIOR** (Daily Hyper $80 19-Mai → tn de 18-Mai; `ORDER BY start DESC LIMIT 1` agarra o instance que já começou). **Latente** (M1=0: nenhum lobby `success` processado pós-deploy) mas **dispara na próxima actividade de lobby** — daí a guarda. **Fix candidato:** janela ~simétrica em torno do `posted_at` + selecção *"start mais PRÓXIMO do posted"* (não "último ≤ posted"), distinguindo lobby de table-ss. **Blast radius:** ~24 `tm_not_found` acumulados (17 de 23-Mai + 7 de 19-Mai). Refs: `tournament_resolver.py:_query_summaries` (ramo anchored); call-site `lobby_sync.py`. **Cross-ref:** distinto de `#RESOLVER-TIER12-WINDOW-NO-START` (janela dos TIER 1/2 ancorada em `meta.start_time`); raiz comum "anchor temporal assume SS-durante-o-jogo". |

### Feature-request implementado em pt40 (1 — Track B)

| ID | Severidade | Estado |
|---|---|---|
| **#HRC-PER-HAND-DOWNLOAD** | 🟡 MED | ✅ **IMPLEMENTED (pt40).** Botão "Download HRC pack" per-mão no painel `/hrc` → `GET /api/queue/hrc/hand/{hand_id}` (reusa `lookup_payouts` + `build_queue_zip([h])`): zip `<hand_id>/hh.txt` + `payouts.json` (+ meta/script/manifest). **404** (mão inexistente) / **409** (sem `tournament_payouts`) / **422** (raw/seats não exportáveis, com `reason` do manifest). `eligible_hands` ganha `has_payout` → o botão só aparece quando há payout. Elimina o "criar estrutura à mão" do workflow manual do Rui para as ~111 mãos payout-ready (cobertura ampla baixa — ver pt40). Refs: `routers/queue.py:export_queue_single_hand`; `services/hrc_queue.py:eligible_hands`; `frontend/src/pages/HRCQueue.jsx` + `client.js:queue.hrcHandDownload`. |

### 🚨 Tech debt agravado em pt40 (1 — URGENTE pt41)

| ID | Severidade | Resumo |
|---|---|---|
| **#HERO-BOUNTY-FROM-TS-DERIVATION** | 🔴 HIGH 🚨 | **Hero bounty hardcoded errado no converter GG→PS** (`services/queue_export.py`). `_HERO_BOUNTY_DEFAULT_USD = 250.0` (linha 488, = bounty base do **$525** Big Game) aplicado a **todos** os torneios: cada Seat GG leva `, €<max(Vision,250)> bounty)` (`_inject_bounties_ps_format`, ~521-563). **Sintoma (Rui, pt40):** Big Game **$215** (bounty real **$100 USD** no TS) → Hero `€250` no HH — **moeda E magnitude erradas**. **Achados pt40 (pior que documentado):** (a) **sem gate de formato** → vanilla GG (`Daily Hyper $80`, sem bounty) também recebe **€250 fantasma**; (b) **vilões sempre a €0** (Vision não lê HHs GG anonimizados); (c) afecta **batch (`/api/queue/hrc`, watcher) E per-mão (`dfc13a5`)** — **NÃO é regressão pt40**, vive desde FASE-1/pt28; o endpoint per-mão herdou; (d) **fix desbloqueado** — o TS já tem `buy_in_bounty` por `tournament_number` (ex.: $215→100, $108→50, $44→20). **Moeda `€` é intencional** (workaround do parser HRC, validado pelo Rui — rejeita `$`). **Impacto:** equity PKO do HRC off (Hero inflado), pior quanto menor o buy-in; bounty fantasma em vanilla. **Fix (A) mínimo:** Hero/vilões ← `tournament_summaries.buy_in_bounty` por tn; gate por `tournament_format` (vanilla → sem bounty/0); manter `€`. Refs: `queue_export.py:488,521-563`. **🚨 Foco pt41** — afecta cada mão estudada hoje (batch + per-mão). |

---

## Estado actual (24 Maio 2026 — pt39, re-diagnose read-only do resolver)

Sessão de investigação read-only (queries directas à BD de produção) **+ 4 fixes
shipped + cleanup BD**, sobre os 4 debts HIGH do resolver/pipelines (3 de pt37 +
`#TABLE-SS-RESOLVER-COLLISION` de pt38). Resultado-chave: um dos debts estava
**mal diagnosticado** (re-rotulado abaixo); **2 ficaram ✅ FIXED** e 2 mantêm-se
abertos (foco pt40). Cronologia completa em `docs/JOURNAL_2026-05-24-pt39.md`.

### Tech debt re-rotulado em pt39 (1)

| ID antigo | ID novo | Nota |
|---|---|---|
| **#START-TIME-TIMEZONE-INCONSISTENCY** | **#META-START-TIME-IS-FIRST-HAND-NOT-SCHEDULED-START** | **NÃO é bug de timezone.** A investigação pt39 (query a 20 torneios GG em prod) prova que o diff `tournament_summaries.start_time` vs `tournaments_meta.start_time` é **0.00h quando a 1ª hand em BD é Level1** (≈ arranque) e **cresce quando a 1ª hand é nível tardio** (entry em meio-torneio) — um bug de TZ daria offset **constante**, não variável. Causa real = **semântica diferente das 2 colunas** (detalhe na entrada renomeada, secção pt37). Severidade: 🔴 HIGH em pt39, **baixada para 🟡 MED em pt40** (não-bloqueante). Entrada original preservada e actualizada in-loco na secção pt37. |

### Confirmações factuais pt39 (read-only, BD prod) dos outros 3 HIGH

- **#RESOLVER-TIER0-STRICT-EQUALITY** ✓ confirmado. Ex.: lobby "Daily Deepstack
  Special $125" Vision pool=12500/entrants=57 vs TS `tn 284491487`
  pool=18515/players=161 — **`buy_in`=125 bate nos dois** (campo estável, hoje
  não usado no TIER 0). Idem 2× "Daily Hyper $80" (Vision 5000/46 e 5000/59 vs TS
  `tn 284939855` 7580.80/103 e `tn 284939948` 7728/105; buy_in=80 bate sempre).
- **#RESOLVER-TIER12-WINDOW-NO-START** ✓ confirmado. Os 3 lobby `tm_not_found`
  têm `start_time_iso=None`; `reason_detail='start=None'` é só rótulo do último
  tier (**engana** — o bloqueio primário é o TIER 0, que nem usa start_time).
- **#TABLE-SS-RESOLVER-COLLISION** ✓ confirmado + **refinado**: a colisão
  (INTERSTELLAR/EXPLORER → mesma mão) deu-se via `reason_detail='single_tn'` —
  **o resolver-por-nome nem foi chamado**. O fast-path `single_tn` de
  `_resolve_match` (`table_ss.py:238-241`) aceita a mão mais próxima por
  proximidade temporal **sem validar o nome** quando há 1 só `tournament_number`
  na janela; a SS de EXPLORER não tinha nenhuma hand sua na janela ±5min, só de
  INTERSTELLAR. Os 2 `tm_ambiguous` (ZENITH/GALACTICA) falham por motivo
  **diferente**: o sufixo `#NNN` da SS (nº de mesa Winamax) vira token e mata o
  `ILIKE ALL` (nomes em `hands` são bare) **+** Winamax não tem TS/meta (GG-only),
  logo só TIER 2 está disponível e é derrotado pelo sufixo.

### Fixes shipped em pt39 (2 ✅ FIXED, 2 mantêm-se abertos)

| Debt | Estado | Detalhe |
|---|---|---|
| **#RESOLVER-TIER0-STRICT-EQUALITY** | ✅ FIXED (`35286c1`) | TIER 0 ganha `buy_in` (igualdade exacta em `buy_in_total` + currency) **+ janela `start_time` ancorada no `posted_at`/`captured_at`** (instância em curso, `ORDER BY start_time DESC LIMIT 1`). **Reversão parcial da decisão #4:** `prize_pool`/`total_players` **mantidos** NULL-permissivos porque o **5º consumidor do resolver — `routers/tournament_results.py` (backoffice GG, descoberto a meio do trabalho)** — é pós-jogo e precisa deles (valores finais, exactos; é o único discriminador entre instâncias em dias diferentes sem âncora). Achado **W4**: **18/101 TS GG são 2×/dia** (mesmo nome+buy_in) → só a hora desempata, daí janela+`LIMIT 1`. Helper `_parse_buy_in_str` em `table_ss.py` (buy_in da SS de mesa vem string "€50"). |
| **#TABLE-SS-RESOLVER-COLLISION** | ✅ FIXED (`36f7f7f`+`e2c6460`+cleanup BD) | parte 1/2 `36f7f7f` — `clean_tournament_name` **trailing-only** (achado: W SERIES `#220 - …` é prefixo **legítimo**; drop global parti-lo-ia). parte 2/2 `e2c6460` — `name_tokens_subset` valida o nome no fast-path `single_tn` antes de aceitar. Cleanup BD data-only (`_local_only/pt39_cleanup.py`, 4 UPDATEs atómicos). Achado: **2 colisões** em prod, não 1 — `ODYSSEY→ZENITH` (**não estava flagged**) além de `EXPLORER→INTERSTELLAR`. |
| **#META-START-TIME-IS-FIRST-HAND-NOT-SCHEDULED-START** | ✅ FIXED (8 Jul, item 9 casa-limpa — re-escopado GG-only) | **Fix GG-scoped no intervalo SEM TS.** Enquadramento do Rui: TS-primeiro onde existir (já era — TIER 0); o defeito só morde a GG no intervalo em que o lobby chega ANTES do summary (sem TS → cai p/ TIER 1/2, cuja coluna `start_time`/`MIN(played_at)` = 1ª mão, não arranque). Fix: `_decide_window` ganha `site`; para **GG prestart** o forward passa de +2h → **+6h** (`_GG_PRESTART_FWD_HOURS`, tolerância late-reg) — a 1ª mão entra depois do post por (agendado−post)+late-reg. **Só toca o `window` dos TIER 1/2** (TIER 0/TS usa `anchor` próprio, intocado); **non-GG intocado** (+2h — o lobby WN/PS traz `start_time_iso` da Vision → ramo-1, ancora no arranque real, não sofre). **Confirmação (ponto 1 do Rui):** não há `tournaments.started_at` literal (a tabela `tournaments` = livro P&L HM3, só `date`, nada casa por tempo); o campo real `tournaments_meta.start_time` **É lido pelo resolver para não-GG também** (SQL site-agnóstico em `_query_meta`/`_query_hands`), mas o **dano é GG-only** (as não-GG têm o anchor da Vision). Âmbito **não alargou**; o fix não muda comportamento não-GG. `services/tournament_resolver.py:_decide_window`. +3 testes. |
| **#RESOLVER-TIER12-WINDOW-NO-START** | ✅ FIXED (`6409b19`, pt41) | resolvido pelo `_decide_window` source-aware (ramo-2 prestart forward + ramo-1 +4h). Ver secção pt41. |

Commits pt39 (cronológico): `b76cea7` (docs re-rotular) → `35286c1` (TIER 0) → `36f7f7f` (collision p1) → `e2c6460` (collision p2) + cleanup BD data-only. Suite **621 → 627 → 637 → 646 PASSED**. Detalhe em `docs/JOURNAL_2026-05-24-pt39.md`.

---

## Estado actual (24 Maio 2026 — pt38, descoberta empírica MTT-Stacks)

Descoberta empírica do Rui sobre a página **MTT-Stacks** do HRC, via 2 SS do
HRC (antes/depois de clicar **OK** no sub-popup "Generate MTT Stacks"):

- **Antes do OK:** Other Tables Players = 0.
- **Depois do OK com Remaining Players = 313:** Other Tables Players = **305**
  (313 − 8 = 305), Other Tables Chips = **54 762 354** (Total − Active).

Conclusão: **o HRC auto-calcula a coluna "Other Tables"** a partir de Remaining
Players quando se carrega OK no sub-popup. O watcher **não** precisa de
preencher "Other Tables" directamente — basta preencher Remaining Players (que
já preenche em `handle_mtt_stacks_page`) e dar OK. Isto invalida o workaround
`#HRC-MTT-OTHER-TABLES-INFO` (que assumia ser preciso escrever o campo) e
re-foca o problema real: quando `players_left=None`, a página MTT-Stacks é
saltada e a tabela fica em defaults.

### Tech debt re-classificado em pt38 (1)

| ID | Estado | Nota |
|---|---|---|
| **#HRC-MTT-OTHER-TABLES-INFO** | ✅ **FALSO POSITIVO** | Verificado empiricamente em pt38 (SS do HRC com Remaining Players=313 → Other Tables Players=305 auto-calculado). O HRC auto-calcula Other Tables baseado em Remaining Players, não é necessário typewrite separado no watcher. A formulação original (cadeia pt26: `#VISION-LOBBY-API-FAILURE` → `#HRC-CONTEXT-MISMATCH-PLAYERS-LEFT` → `#HRC-MTT-OTHER-TABLES-INFO`) estava incorrecta a partir do 3º elo. Entrada histórica original preservada na secção pt23 (não eliminada). |

### Tech debt novo aberto em pt38 (1)

| ID | Severidade | Resumo |
|---|---|---|
| **#HRC-MTT-STACKS-PAGE-SKIPPED-ON-NULL-PLAYERS-LEFT** | 🔴 HIGH | Quando `players_left=None` no `meta.json` (mão sem lobby SS no `#lobbys`), o watcher salta a página MTT-Stacks com Next directo (`tools/watcher_src/patched_funcs.py:1861-1871`). A tabela MTT-Stacks fica em defaults (Other Tables Players=0, Active Table Players=N, Total=N). O HRC trata como se só existisse a mesa actual → Multi-Table ICM colapsa a FT ICM dos sentados. **CAUSA RAIZ:** falta de `players_left` fidedigno por mão; a fonte actual (lobby SS no `#lobbys`) cobre poucos torneios. (Nota pt43: o "~34% de falha Vision" outrora atribuído ao `#VISION-LOBBY-API-FAILURE` está desmentido empiricamente — 0 `vision_failed` em 131 tentativas; ver entrada reclassificada. A cobertura limitada vem de `tm_not_found`/falta de TS, não de falha de Vision.) **SOLUÇÃO PROPOSTA:** capturar SS de mesa via Intuitive Tables (1-clique por mão) → Vision extrai `players_left` → `meta.json` populado → wizard preenche Remaining Players → HRC auto-calcula Other Tables. Substitui operacionalmente o ex-`#HRC-MTT-OTHER-TABLES-INFO`. |

### Tech debts do pipeline SS de mesa em pt38 (3 novos + 1 fechado)

Contexto: pipeline SS de mesa construído ponta-a-ponta (Fases A+B + trigger
re-link + fix mapeamento Vision). Ver `docs/JOURNAL_2026-05-24-pt38.md`.

| ID | Severidade | Resumo |
|---|---|---|
| **#TABLE-SS-PROMPT-VISION-V1-OUTDATED** | ✅ FIXED (`0d0ec30`) | Prompt v1 de `services/table_ss_vision.py` ensinava a barra do painel como *left/entrants* e não tinha `hero_rank` → a Vision guardava `players_left` **errado em 3 de 4 SSs success** (ODYSSEY 71=rank, GALACTICA 7=itm/parênteses, GG 813=rank; HIGHROLLER OK por coincidência). **Bloqueava o HRC** (`_resolve_players_left` recebia valor errado). **Fix:** campo `hero_rank` + mapeamento explícito por site (Winamax `Rank: <hero_rank> / <players_left> (<itm_places>)`; GG `My Rank: <hero_rank> / <players_left>`), `players_left` = sempre depois da barra, `total_entries` só se contador separado/explícito, exemplo enganador `Players: 71/124` removido. `hero_rank` só no `vision_json` (sem coluna). Reset BD (7 rows + 3 hands NULLed). Smoke pós-fix OK (ODYSSEY `players_left=124`, HIGHROLLER `players_left=8`). |
| **#TABLE-SS-RESOLVER-COLLISION** | ✅ FIXED (`36f7f7f`+`e2c6460`+cleanup, pt39 — ver secção pt39) | INTERSTELLAR #005 (Shot4) + EXPLORER #010 (Shot5) ligaram à **mesma** mão (`WN-4725259290334461958-39-…`): o resolver devolveu o **mesmo** `tournament_number` (`1100185162`) para **2 nomes de torneio diferentes** na janela ±5 min. Causa = a desambiguação por nome de `_resolve_match` herda os bugs do resolver (TIER 1/2 sobre `hands`/`tournaments_meta` com nome ILIKE + janela frouxa). **Cross-ref** com os 3 HIGH do resolver (pt37): `#RESOLVER-TIER0-STRICT-EQUALITY`, `#RESOLVER-TIER12-WINDOW-NO-START`, `#META-START-TIME-IS-FIRST-HAND-NOT-SCHEDULED-START` (re-rotulado pt39, ex-`#START-TIME-TIMEZONE-INCONSISTENCY`) — fix conjunto na sessão dedicada ao resolver. Refs: `backend/app/routers/table_ss.py:_resolve_match`; `services/tournament_resolver.py`. |
| **#TABLE-SS-VISION-CAPTURE-GAP** | 🟡 MED | Algumas SSs Winamax (ZENITH #005, INTERSTELLAR, EXPLORER) vieram com `players_left=null` porque a SS **não tinha o painel "Rank:" visível** (a Vision leu todo o resto correctamente — não é falha do modelo). Sem o painel na imagem, nenhum prompt recupera o número. **Workaround:** Rui configurar o Intuitive Tables para garantir o painel de torneio sempre visível na captura. Sem fix de código possível. Refs: `docs/JOURNAL_2026-05-24-pt38.md §8`. |
| **#TABLE-SS-PIPELINE-DEPENDENCIES** | 🟡 MED | O pipeline SS de mesa **depende do resolver** para o linking fiável: em multi-tabling (>1 torneio na janela ±5 min) `_resolve_match` chama `resolve_tournament_number` para desambiguar → qualquer bug do resolver propaga-se ao matching SS↔mão. Enquanto os 3 HIGH do resolver (pt37) não fecharem, o linking multi-tabling não é totalmente fiável. Não-bloqueante para single-table (a maioria). |

---

## Estado actual (23 Maio 2026 — pt37, setup da smoke battery 1: investigação read-only lobby→resolver)

Sessão de **investigação read-only** (zero mudanças de código) como setup da
smoke battery (`#PIPELINE-ROBUSTNESS-SMOKE-BATTERY`). Análise caso-a-caso de 3
SSs de lobby presas em `tm_not_found`, validada com **queries directas à BD de
produção** (message_ids `1505967173032607784`, `1506327372629282879`,
`1506329968781557890`, todos GGPoker). Confirmou-se que os torneios **existem**
em `tournament_summaries`/`tournaments_meta`/`hands` — o resolver é que não bate.
A investigação paralela do `/import` vs endpoints dedicados (TS/Results) e do
re-trigger de lobbys completou o quadro. **6 tech debts novos.**

### Tech debts novos abertos em pt37 (6)

| ID | Severidade | Resumo |
|---|---|---|
| **#RESOLVER-TIER0-STRICT-EQUALITY** | ✅ FIXED (`35286c1`, pt39 — ver secção pt39) | TIER 0 do resolver compara `prize_pool`/`total_players` por **igualdade estrita (`=`)**, mas a Vision lê do lobby **em tempo real**: `prize_pool` = garantia anunciada (redonda) vs pool real pós-jogo; `entrants` = inscritos a meio da late-reg vs total final. Igualdade nunca bate → torneios que existem em `tournament_summaries` ficam `tm_not_found`. **Evidência BD prod (23-Mai):** `1505967173032607784` "Daily Hyper $80" — Vision pool=5000/players=46 vs TS mesmo-dia `tn 284939855` pool=7580.80/players=103; `1506327372629282879` "Daily Deepstack Special $125" — Vision pool=12500/players=57 vs TS mesmo-dia `tn 284491487` pool=18515/players=161; `1506329968781557890` "Daily Hyper $80" — Vision pool=5000/players=59 vs TS mesmo-dia `tn 284939948` pool=7728/players=105. Em todos, TIER 0 só-nome devolve ≥2 rows (torneio presente). Fix candidato: matching por **nome + data de calendário**, OU igualdade em `buy_in` (campo estável) em vez de pool/players. Refs: `backend/app/services/tournament_resolver.py:_query_summaries:96-115`. |
| **#RESOLVER-TIER12-WINDOW-NO-START** | ✅ FIXED (`6409b19`, pt41 — ver secção pt41) | TIER 1/2 dependem do `start_time_iso` da Vision para a janela `[start−2h, start+2h]`. Quando a Vision **não lê** `start_time` (acontece consistentemente — `start_time_iso=None` nos 3 casos), o fallback usa `[posted_at−12h, posted_at−30min]`, que **exclui o candidato real** (o torneio começa *depois* do post, porque o user posta a SS durante o jogo). **Evidência:** start dos candidatos = 16:45–17:16; fim da janela de fallback = 15:37–15:47 (`posted_at−30min`) → TIER 1/2 windowed = 0 rows. Fix candidato: alargar fallback para `[posted_at−12h, posted_at+12h]`, OU prompt Vision mais agressivo para extrair `start_time`. **Relacionado: `#META-START-TIME-IS-FIRST-HAND-NOT-SCHEDULED-START`** (ex-`#START-TIME-TIMEZONE-INCONSISTENCY`) — a re-diagnose pt39 dissolve a antiga dependência "investigar TZ primeiro" (não há TZ); o que resta é que `meta.start_time` = `MIN(played_at)` **não é o arranque**, logo a janela do TIER 1 ancorada nele é não-fiável. Refs: `backend/app/services/tournament_resolver.py:_decide_window:67-93`; `backend/app/services/lobby_vision.py`. |
| **#META-START-TIME-IS-FIRST-HAND-NOT-SCHEDULED-START** (ex-`#START-TIME-TIMEZONE-INCONSISTENCY`, re-rotulado pt39) | 🟡 MED (baixada pt40) | **NÃO é bug de timezone** (re-diagnose pt39, read-only, BD prod). `tournament_summaries.start_time` e `tournaments_meta.start_time` para o mesmo `tournament_number` medem **coisas diferentes**: o TS guarda o **arranque agendado** do torneio (`backend/app/routers/tournament_summaries.py:_parse_start_time_utc:212-223`, header GG forçado a UTC); a `tournaments_meta` guarda **`MIN(played_at)` das hands** (`backend/app/services/tournament_meta.py:upsert_tournament_meta:99-114`), ou seja a **primeira mão importada na BD** — que **não é o arranque** quando o Hero entra tarde (late-reg) ou só se importam mãos de meio-torneio. **Prova (pt39, 20 torneios GG):** o diff é **0.00h quando a 1ª hand é Level1** (ex.: `tn 284528691` TS 18:30:00 / meta 18:30:02) e **cresce quando a 1ª hand é nível tardio** (ex.: `tn 284491487` TS 15:05 / meta 17:03:51, 1ª hand **Level9**; `tn 284939948` TS 16:45 / meta 17:16, **Level9**). Um bug de TZ daria offset **constante**; aqui é variável e correlaciona com o nível da 1ª hand → semântica, não relógio. (Ambos os literais GG são UTC e batem ao segundo no mesmo instante.) **Implicação:** qualquer fix de janela (`#RESOLVER-TIER12-WINDOW-NO-START`) que assuma `meta.start_time ≈ arranque` está **errado**; e a "dependência" antes declarada ("investigar TZ primeiro") **dissolve-se** — não há TZ para corrigir. **Baixada para 🟡 MED em pt40** (não-bloqueante: o TIER 0 usa o arranque do TS, não `meta.start_time`; valor sobretudo analítico/futuro). Continua a poder contaminar janelas ancoradas em `meta.start_time` (TIER 1). Ver re-diagnose na secção pt39. |
| **#IMPORT-MODAL-MISROUTES-TS-RESULTS** | ✅ FECHADO (`ced7531`, pt43) | O `ImportModal` classifica **qualquer `.zip`** como `hh_zip` → `/api/import`; um TS cai no ramo P&L (`tournaments`, degrada com `tournament_number=""`), Tournament Results dá 400 ou path de screenshot. A UI mostra **"Importado"** via `formatResult('hh_zip')`, que **esconde o resultado real**. Os botões dedicados existem em `/tournaments`, mas o utilizador não-iniciado não sabe que tem de os usar — pode pensar que importou TS quando não importou (**aconteceu nesta sessão** — ZIP 20KB). Fix candidato: `ImportModal` detecta TS/Results pelo conteúdo do `.zip` e encaminha para o endpoint certo, OU mostra erro/aviso explícito quando o tipo não é HH. Refs: `frontend/src/components/ImportModal.jsx:13-18,49-51,83-92`; `backend/app/routers/import_.py:142-150,486-493`. |
| **#LOBBYS-RETRIGGER-NOT-DISCOVERABLE** | 🟡 MED (UX) | O botão "Sincronizar Lobbys" + Avançado/`tm_not_found` vive **só** na página Discord, fácil de não notar. Não há aviso em Dashboard ou Torneios quando há candidatos `tm_not_found` pendentes. O utilizador importa TS+HH e fica sem saber que precisa de **re-disparar** os lobbys para fechar o ciclo. Fix candidato: badge/link na Dashboard ou Torneios quando há lobbys pendentes, OU automatizar o re-trigger após import TS/HH. Refs: `frontend/src/pages/Discord.jsx:655-682`. |
| **#DISCORD-VISION-NO-RECOVERY** | 🟢 LOW | Entries `replayer_link` em `has_image_no_vision` (`img_b64` presente, `vision_done=false`) **não são recuperadas** por novo sync — `process_replayer_links` só selecciona `WHERE (raw_json->>'img_b64') IS NULL`. Ficam em limbo. Fix candidato: endpoint `/retry-vision`, OU alargar o WHERE para incluir `vision_done=false`. Refs: `backend/app/routers/discord.py:565,688`. |

---

## Estado actual (23 Maio 2026 — pt36, HRC Run-2 always-dispatch)

Backend-only. Garante que **toda mão exportada para o robot tem 2 runs**
(Opção D1). `build_queue_zip` passa a aplicar uma sentinela ao
`aggressor_real_action` quando o derive devolve `None` ou uma position
inutilizável, de modo que o gate da 2ª run no watcher
(`tools/watcher_src/patched_funcs.py:1987`, `if aggressor_real_action is not
None`) passa sempre. `.exe` **não tocado** — fix puramente backend no payload.
Suite **573 PASSED**; smoke local validado em 4 cenários (real / fallback_root
/ fallback_unusable_position / no_seats).

### Tech debt resolvido em pt36 (1)

| ID | Como fechou |
|---|---|
| **#HRC-RUN-2-ALWAYS-DISPATCH** | ✅ **Resolvido pt36.** `build_queue_zip` (`backend/app/services/queue_export.py`) aplica fallback unificado ao `aggressor_real_action`: (a) **`real`** quando o derive devolve dict com `position ∈ strategy_table_positions(seats_at_table)`; (b) **`fallback_root`** quando devolve `None` (limp/walk, sem blinds); (c) **`fallback_unusable_position`** quando devolve dict mas position é `None`/`"BB"`/fora da Strategy Table. Nos casos (b)/(c) a sentinela é `{"type":"fallback_root","position":positions[0],"size_bb":None,"source":<b\|c>}` → `target_node_offset=0` (raiz). `manifest.hands_included[*]` ganha o campo `aggressor_source` (`real`/`fallback_root`/`fallback_unusable_position`) para auditoria. O caso `real` preserva a estrutura legacy do derive (sem chave `source`). Tests: 4 novos + 1 renomeado/actualizado (`..._None_for_limp_pot` → `..._fallback_root_for_limp_pot`) + assert reforçado num test existente. |

### Tech debt novo aberto em pt36 (1)

| ID | Severidade | Resumo |
|---|---|---|
| **#PARSER-SEATS-FAILURES** | 🟡 MED | `build_queue_zip` passou a **skipar** mãos cujo `derive_seats_in_preflop_order` devolve `[]` (sem `Seat #N is the button` ou <2 seats) com `reason="no_seats_at_table"` — HH malformada não vai ao robot. **Consequência:** uma falha do parser de seats agora **custa a mão inteira à biblioteca** (antes só perdia a 2ª run). O parser regex já teve bugs em HHs válidas (ex.: `#DERIVE-MAX-PLAYERS-HERO-REGEX-GG`, nicks com espaços). Robustecer `derive_seats_in_preflop_order` (`backend/app/services/queue_export.py:140`) contra edge cases conhecidos cross-site (PS/GG/WN/WPN) é prioridade — cada falha é agora uma mão perdida em silêncio (só rasto em `manifest.skipped`). |

---

## Estado actual (22 Maio 2026 — pt35, GTO Brain Fase 1)

**Fase 1 do GTO Brain fechada.** O watcher passa a exportar em **Complete
Export** (antes "Manual Selection" = 1 nó por árvore). Smoke real ponta-a-ponta
validado no Beelink (`GG-5944816316`, 2 runs, `.zip` final **44 MB** — dentro da
faixa empírica 40-70 MB). `.exe` recompilado e instalado, SHA256
`33eae43aa0e4ab0f331b880ee217efe6d52369b4190cc07fb3be7fb647c53c4f`.

Mudança: SWAP de `export_strategies` em `tools/watcher_src/patched_funcs.py`
(Win32 `CB_SETCURSEL` idx 0→1 + `CBN_SELCHANGE` + read-back; OK por `BM_CLICK`)
e port self-contained do `_save_as_set_and_click` (Save As via clipboard +
`BM_CLICK` no Save). Boot via `wrapper.py` **sem** `make_patched_export`.

### Tech debt novo registado em pt35 (1)

| ID | Severidade | Estado |
|---|---|---|
| **#DOC-MAKE-PATCHED-EXPORT-OVERRIDES-SWAP** | 🟢 LOW (resolvido pt35) | **Ponto cego documentado para não se repetir.** O launcher Baltazar (`hrc_watcher_apr19_launcher.pyc`), no seu `main()`, corre `g['export_strategies'] = make_patched_export(g)` **depois** do `exec` do trampoline (offsets `main()`: 154 exec → 232-256 override → 260 `g['main']()`). Ou seja, **sobrescreve qualquer `export_strategies` definida via SWAP em `patched_funcs.py`** com a versão do launcher → um SWAP dessa função tem efeito **zero** em produção. Descoberto em pt35 por disassembly do launcher (a 1ª recompilação teria passado o smoke do trampoline mas o `.exe` ignoraria a mudança). **Resolvido em pt35:** o `wrapper.py` passa a bootar o trampoline directamente (`exec` → `MAX_CONCURRENT=1` → `g['main']()`) **sem** chamar `make_patched_export`, tornando canónica a nossa `export_strategies`. **Lição:** antes de assumir que um SWAP aterra, confirmar que o launcher não monkey-patcha a função pós-`exec`. Ver `HRC_ANATOMIA_OPERACIONAL.md §8`. |

### Tech debt do GTO Brain fechado em pt35 (1)

| ID | Como fechou |
|---|---|
| **#GTO-WATCHER-EXPORT-DEFAULT-DEPTH-2** (🔴 HIGH, era Fase 1; vive em `docs/GTO_BRAIN.md §9`) | `export_strategies` (SWAP) muda o combo do diálogo Export Strategies de "Manual Selection" → "Complete Export" via `CB_SETCURSEL` (idx 0→1, read-back) + `CBN_SELCHANGE`; OK por `BM_CLICK`; Save As robusto via `_save_as_set_and_click` portado. Smoke real `GG-5944816316` = 44 MB (era 1 nó / ~6 KB). |

### Tech debt aberto em pt35 — pré-requisito da Fase 2 (1)

| ID | Severidade | Estado |
|---|---|---|
| **#PIPELINE-ROBUSTNESS-SMOKE-BATTERY** | 🟡 MED | **Aberto, ainda não fechado.** Validar o pipeline ponta-a-ponta nas **4 combinações site × formato** listadas em `docs/GTO_BRAIN.md §7` ("Fase 1 — smoke battery de robustez pré-Fase 2"): (1) GG NKO Vanilla, (2) PokerStars PKO, (3) Winamax PKO, (4) PokerStars NKO Vanilla. Cada smoke = mão marcada na app → adapter pull → watcher → adapter push → `.zip` em `hrc_jobs` com dezenas de MB / milhares de nós. Ponto de partida validado: pt35 GG PKO 50% (`GG-5944816316`, 44 MB). **Pré-requisito para arrancar a Fase 2** (auto-import `.zip` → `gto_trees`/`gto_nodes`). |

---

## Estado actual (22 Maio 2026 — pt30-pt34)

Sessão pt30-pt34 (madrugada). **Fecho de toda a cadeia da 2ª run do HRC**
(Selected Subtree), ponta-a-ponta no Beelink, com `.zip` final de ~23 000
nós (equivalente ao Save As manual). 6 commits feature em main, todos no
robot watcher (`tools/watcher_src/patched_funcs.py` + 2 ficheiros de teste);
`.exe` **não recompilado** (passo separado). Suite **550 → 569 PASSED**.
Detalhe em `docs/JOURNAL_2026-05-22-pt30-pt34.md` e
`docs/HRC_ANATOMIA_OPERACIONAL.md` v5.

Discovery transversal: **o HRC usa SWT, não Swing** — widgets expostos como
child windows nativas ao Win32 (`BM_CLICK`, `IsWindowEnabled`,
`GetWindowText`). Toda a sessão assenta nisto.

### Tech debts fechados em pt30-pt34 (6)

| ID | Como fechou |
|---|---|
| **#START-CALC-SELECTED-SUBTREE-NO-POPUP-OPEN** (CRIT, aberto pt26) | **pt32 v1 + v2** (`61dfa5f`/`c9c8818`). Causa raiz isolada por smoke + logging `[calc-diag pre-click]`: `_click_calculate_button` usava a `wpos` do wizard "Hand Setup" — **já fechado** no Finish da 1ª run — como origem do click do Play. Log: `coord=(1174,64)` com `wpos=(970,0,...)` → 1174=970+204, click em zona vazia. Fix: (a) coord Y 59→64 (a 1ª run usa 64 e funciona); (b) origem `wpos` → `find_hrc()`, igual à 1ª run do Baltazar OG (`hrc.left+204, hrc.top+64`). `find_hrc()` None → WARN + raise. Resultado: **popup Nash abre.** |
| **#START-CALC-SELECTED-SUBTREE-OK-CLICK-FAILS** (aberto+fechado pt33) | **pt33 v1** (`867460c`). Smoke pt32 v2 mostrou que o popup abre e os cliques intra-popup (scope, Selected Subtree, CI) funcionam, mas o OK por `Enter` não era registado → popup ficava aberto e parado, 2ª run não disparava. Snapshot Win32 (`check_nash_popup_children`) mostrou o popup como dialog `#32770` com Button OK **exposto** (`class='Button' text='OK'`). Fix: substituir Enter por `EnumChildWindows` + `BM_CLICK` no hwnd (`_find_nash_popup_hwnd` + `_find_ok_button` + `_click_ok_in_popup`), sem fallback Enter. Resultado: **popup fecha, 2ª run dispara.** |
| **#WAIT-FOR-RUN-COMPLETION-2A-RUN-FALSE-NEGATIVE** (aberto+fechado pt34) | **pt34 v1** (`e58c517`). A 2ª run disparava mas `_wait_for_run_completion` dava timeout 30s a "esperar a janela aparecer", porque procurava título exacto "Hand Setup" e a janela de progresso da 2ª run chama-se **"H-\<hand_id\>: Monte Carlo Sampling"**. Fix: param `match_substring` + helper `_find_progress_window_title` (None → FindWindowW exacto; preenchido → EnumWindows substring case-insensitive). 1ª run inalterada. Resultado: 2ª run esperada até ao fim real (~14 min). |
| **#WAIT-FOR-CALCULATION-FALSE-POSITIVE-MEMORY-HEURISTIC** (aberto+fechado pt31) | **pt31** (`0f159bc`). A heurística de memória do `wait_for_calculation` (Baltazar OG, instalada pt29-v3) deu falso positivo no smoke pt30 (declarou fim da 1ª run aos 48s = 15s+3×10s, com a run ainda a correr). Substituída por `_wait_for_run_completion`, que polla a janela de progresso top-level (sinal **binário**). `wait_for_calculation` fica no namespace mas já não chamada. |
| **#WIZARD-FINISH-DISABLED-DURING-TREE-CALC** (aberto+fechado pt30) | **pt30** (`52aef9c`). Diagnóstico SWT (`check_wizard_children_polling`) provou que ao carregar o script o HRC desabilita o Finish enquanto calcula o tree size (~1.7s); o slow-click pt29-v2 caía num botão **disabled** (causa do smoke pt29-v3 falhar). Fix: `_wait_for_finish_ready` espera a transição enabled→disabled→enabled via Win32 (`IsWindowEnabled`) antes do slow-click. Instância isolada `_pt30_user32` para não colidir argtypes com o launcher Baltazar. |
| **#FINALIZE-NEVER-FIRES-ON-NO-OP** (MED, aberto pt26) | Coberto pelo wiring do `second_run_dispatched` em `setup_hand`: `start_calculation_selected_subtree` devolve bool; `False` (popup não abriu) → WARN explícito antes do finalize; `True` → espera a 2ª run terminar antes do export. Com a cadeia pt32-pt34 a funcionar, o caminho `True` é o normal. |

### Tech debts novos abertos em pt30-pt34 (2)

| ID | Severidade | Resumo |
|---|---|---|
| **#CURSOR-ANOMALY-POST-SAVE-AS** | 🟢 LOW | Observação visual do Rui no smoke pt34: após o Save As, o cursor da Strategy Table fica na **2ª linha (EP)**. Origem desconhecida. Não bloqueia o flow actual (export já aconteceu), mas pode afectar uma futura 3ª run ou navegação encadeada. Investigar origem (efeito secundário do Save As? do export patch?). |
| **#WIZARD-FINISH-FALSE-POSITIVE-STATE-CHECK** | 🟢 LOW | `verify_wizard_finished` (state-check WARN-only pós-Finish, pt29-v1) verifica **cedo demais** — a janela "Hand Setup" ainda está presente no instante da verificação, gera WARN espúrio (`janela "Hand Setup" ainda presente apos click + activate`), mas a 1ª run efectivamente arranca. Fix: pequeno settle/poll antes de verificar, ou retirar o WARN. Não-bloqueante. |

### Tech debts confirmados abertos (3)

| ID | Severidade | Estado |
|---|---|---|
| **#HRC-BOUNTY-HARDCODED-50PCT** | 🟡 MED | **Aberto — validação parcial (só PKO 50%).** (a) O dropdown "Bounty Mode" do wizard está hardcoded a "PKO 50%" (`select_bounty_mode` legacy no bytecode Baltazar OG, `tools/watcher_src/patched_funcs.py:1519-1521` — `if is_ko_tournament(prize_path): select_bounty_mode(wpos)`). (b) Mas o `progressiveFactor` real **chega** ao HRC via `payouts.json` data-driven (`apply_ratio_lookup`/`LOBBY_RATIO_LOOKUP` em `backend/app/services/lobby_vision.py:36-46` → PKO 0.75/0.50/0.40, KO 0.33, None 0.0 — **não há 0.25**). (c) Validação empírica pt34 v1 (`GG-5944816316`, "Bounty Hunters Daily"): `apply_ratio_lookup` devolve `("PKO", 0.50)` e o settings.json exportado pelo HRC mostra `progressiveFactor: 0.5` — **mas é o caso degenerado onde hardcode = ratio real**, não prova nem refuta nada. (d) **Falta** validação empírica em PKO≠50% (Super KO 0.40, Monster 0.75, Mystery KO 0.33) para decidir se o dropdown é **cosmético** (HRC usa o JSON → debt fecha-se) ou **activo** (HRC faz override do JSON → bug real). (e) Estado: **aguarda dados empíricos**, não "implementar". Prioridade mantém-se MED. Nota arquitetural (independente da validação): `_build_watcher_hints` em `backend/app/services/queue_export.py:762` não passa `bountyType`/`progressiveFactor` ao watcher; fechar esse gap (passar hints) é change funcional que **não** bloqueia o debt — só faz sentido depois de saber se o dropdown afecta o cálculo. |
| **#HRC-TOTAL-CHIPS-MISSING** | 🟡 MED | **Continua aberto.** `chips: null` no `payouts.json` (ainda visível no log: `Total chips: None`). É o total de fichas em jogo; o HRC precisa dele para o chip average / ICM. Fonte: `Average Stack × Players Left` do lobby. Ver `HRC_ANATOMIA_OPERACIONAL.md` §12.8. |
| **#CI-TARGET-INITIAL-NOT-CALIBRATED** (= antigo Bug F, pt25e Bloco 2) | 🟢 LOW | **Continua aberto.** Coords do CI Target inicial da 1ª run no main UI nunca calibradas (`CI_TARGET_FIELD_X/Y = 0`) → `_set_ci_target_common` degrada para Enter (funciona). Log: `[WARN] CI Target initial: coords não calibrados`. Calibrar em smoke devagar; não-bloqueante. |

### Estado da Fase 3 HRC pós-pt34

- Cadeia da 2ª run (Selected Subtree) **funcional ponta-a-ponta** ✓
- Smoke real **mecânico** ✓ + **funcional** ✓ (`.zip` ~23 000 nós)
- Pendente: **validação formal** dos nós vs Save As manual (alta prioridade,
  `docs/PENDENTES.md`) + `#HRC-BOUNTY-HARDCODED-50PCT`.

---

## Estado actual (21 Maio 2026 — pt29)

Sessão pt29 (cascata de fixes do robot HRC, smoke real com `GG-5944816316`).
Detalhe completo em `docs/JOURNAL_2026-05-21-pt29.md` e
`docs/HRC_ANATOMIA_OPERACIONAL.md` v4. Watcher recompilado pt29-v1/v2/v3.

### Tech debt novo aberto em pt29 (1)

| ID | Severidade | Resumo |
|---|---|---|
| **#HRC-BOUNTY-HARDCODED-50PCT** | 🟡 MED | O robot Baltazar OG tem o Bounty Mode hardcoded em PKO 50% na heurística "KO detetado → selecionar Bounty Mode PKO 50%". Para suportar PKO 25% e Mystery KO temos de ler o valor real do `tournament_format` parsed do TS e selecionar a opção correspondente no dropdown do HRC. Impacto: cálculos para torneios não-PKO-50% têm Bounty Mode errado. |

### Bugs do robot resolvidos em pt29 (nunca foram tech debts formais)

Descobertos e fechados na mesma sessão pt29 via smoke real — registados
aqui para histórico (não tinham entry própria no inventário):

| Bug | Como fechou |
|---|---|
| Finish click silenciosamente ignorado (HRC Java perde click instantâneo) | **pt29-v2** (`cb4c520`): slow-click `mouseDown → sleep(0.15) → mouseUp` + activate pré-click + state check pós-click via título "Hand Setup". |
| 2ª run começava antes da 1ª terminar (e Save As antes da 2ª) | **pt29-v3** (`3b9d72c`): `wait_for_calculation()` (Baltazar OG, já existia inutilizada) chamada após 1ª run e após 2ª run (esta condicionada a `second_run_dispatched is True`). Heurística: memória HRC estável >100 MB / variação <20 MB por 3 ciclos de 10s. |
| "Save As dialog não aparece em 20s" | Provavelmente resolvido em cascata pelo wait da 2ª run (pt29-v3) — **a confirmar com o resultado do smoke pt29-v3** (por arrancar à hora deste closeout). |

---

## Estado actual (19-20 Maio 2026 pós-pt27 closeout)

Sessão pt27 fechada com **1 commit feature em main** (`7de8df6`, 3 fixes
backend HRC) + commit docs (este). Bloco A (read-only) descobriu 1
regressão antiga não-fixada (`study_state` desde 18 Abr). Bloco B (etapa
2) entregou 3 fixes ao pipeline `/api/queue/hrc`. Bloco C (fix funcional
do `.exe`) **não atacado** — fica para pt28. Suite **449 → 455 PASSED
(+6 líquidos)**.

Re-classificação operacional: smoke A (rollback `.exe` pt25d) confirmou
fragilidade da baseline anterior (40 de 41 mãos pulled em 14 Maio nunca
chegaram a `done`). O caminho não é restaurar pt25d — é fixar
`#START-CALC-SELECTED-SUBTREE-NO-POPUP-OPEN` em pt28.

### Tech debts fechados em pt27 (3)

| ID | Como fechou |
|---|---|
| **#CI-DEFAULT-MISMATCH** | Backend `_DEFAULT_CI_TARGET_FIRST_RUN = 5.0` → `_DEFAULT_CI_TARGET = 10.0` em `services/queue_export.py` (`7de8df6`). Watcher já hardcode-passa 10.0 na 2ª run → 1ª e 2ª agora alinhadas. Decisão product Rui: opção (ii) "alinhar ambos em 10". |
| **#DERIVE-MAX-PLAYERS-HERO-REGEX-GG** | Aberto + fechado em pt27. 3 sub-bugs em `services/derive_max_players.py`: (a) `_HERO_RE = ^Dealt to (\S+)` apanhava 1º "Dealt to" (em GG pós-`_replace_hashes` todos os 8 seats têm essa linha); (b) `_SEAT_RE`/`_ACTION_RE` com `\S+` truncavam nicks com espaços tipo "Andrii Novak"; (c) `_SEAT_RE` matchava SUMMARY `Seat 6: Hero collected (X)` sobrescrevendo seats[6]. Fix: `_HERO_RE` exige ` \[`; `\S+` → `.+?`; parsing restrito ao header pré-`*** HOLE CARDS ***`. Mão real `GG-5944816316`: `max_players` 4 → 6. +1 test. Commit `7de8df6`. |
| **#COMPUTE-TARGET-NODE-OFFSET-USES-WRONG-PLAYER-COUNT** | Aberto + fechado em pt27. `compute_target_node_offset` usava `max_players` (redução ICM) como input para `strategy_table_positions`. Errado — Strategy Table HRC tem 1 linha-base por jogador real sentado. Para `GG-5944816316`: `max_players=6` fazia `MP` cair fora de `strategy_table_positions(6)=[UTG,HJ,CO,BU,SB]` → offset=None. Fix: param renomeado para `seats_at_table`; caller passa `len(derive_seats_in_preflop_order(hh_text))` em vez de `hints.get("max_players")`. Mão real: offset null → 4. Tests renomeados + 1 test novo. Commit `7de8df6`. |

### Tech debts novos abertos em pt27 (4)

| ID | Severidade | Resumo |
|---|---|---|
| **#STUDY-STATE-REGRESSION-HH-IMPORT** | 🟡 MED | Regressão silenciosa desde commit `15cb9b3` (2026-04-18, "feat: consolidate update v8.5"). Antes, `_insert_hand` tinha default `study_state='mtt_archive'` e `import_.py` não passava o arg → bulk HH imports iam para `mtt_archive` (conforme spec CLAUDE.md §"MODELO DE DADOS E FLUXO v2"). Pós-`15cb9b3`, `import_.py:311` e `:335` passam explicitamente `study_state='new'`, anulando o default. Pt13 (5 Maio) notou "1172 hands all in new" no journal mas adoptou-o como facto consumado em vez de fixar. Auditoria pt27 confirmou: 4258/4258 hh_import 7d em `new`, 0 em `mtt_archive`. UI sobreviveu por filtrar por tags em vez de `study_state`. Dashboard counter "mãos por estudar" inflacionado. **Fix conceptual:** remover `, study_state='new'` das 2 linhas em `import_.py:311/335` (default `mtt_archive` toma conta) + migration one-shot `UPDATE hands SET study_state='mtt_archive' WHERE origin='hh_import' AND study_state='new' AND entry_id IS NULL AND screenshot_url IS NULL`. Volume estimado ~25k mãos. **Decisão product pendente** antes de fix: Rui ainda quer a spec original "bulk imports invisíveis na página Mãos"? Se mudou de ideia (querer ver tudo na página Mãos), regressão vira feature pelo silêncio e a tech debt fecha por declaração. |
| **#WINAMAX-TOURNAMENT-SUMMARIES-PIPELINE** | 🟡 MED | Pipeline `tournament_summaries` é **GG-only**. Parser em `routers/tournament_summaries.py` reconhece header GG `Tournament #<tn>`; endpoint `/api/tournament-summaries/import` aceita `.txt`/`.zip`; UI em `Tournaments.jsx` faz upload. Para Winamax, workflow normal de Rui é upload manual de SS lobby (sem TS). Confirmado por Rui em pt27. **Impacto:** `tournament_resolver` TIER 0 (autoritativo, sem janela) só dispara para mãos GG. Mãos Winamax dependem 100% de TIER 1 (`tournaments_meta`) ou TIER 2 (`hands` fallback) — janela temporal apertada. Auditoria pt27 mostrou que 4/10 lobby failures 7d eram Winamax com `start_time` fora da janela `[posted_at-12h, posted_at-30min]`. **Fix conceptual:** espelhar pipeline GG para Winamax — parser dedicado para formato Winamax Summary (header `Winamax Poker Tournament Summary :`), reutilizar endpoint + UI com discriminação por `site`. Resolve parte do gap G1 (Winamax sempre falha no resolver). **Decisão pendente:** vale o esforço dado o volume Winamax (~5% das mãos 7d)? |
| **#AUTH-SCHEME-MIGRATION-UNDOCUMENTED** | ✅ RESOLVIDO (pt43) | Tentativa pt27 de pull `/api/queue/hrc` com header `X-API-Key:` devolveu 401. Diagnóstico revelou que o auth-handler é `require_auth_or_api_key` (G4 pt21) que aceita `Authorization: Bearer <HRC_WATCHER_API_KEY>` mas não `X-API-Key`. Documentação `JOURNAL_2026-05-12-pt21.md` confere — sempre foi Bearer; nunca houve X-API-Key. **✅ Fechado (pt43, 2026-05-29):** grep literal `X-API-Key`/`X_API_KEY`/`X-Api-Key` em todo o repo → **zero** ocorrências em código (`backend/`, `tools/`) e em docs operacionais (README/ONBOARDING/MAPA). As únicas refs são em `JOURNAL_2026-05-19-pt27.md` e `PLANO_2026-05-20-pt28.md` — que *descrevem* esta própria dívida, não instruções activas. Nada a corrigir; código e docs já consistentes com Bearer. |
| **#PT25D-WATCHER-FRAGILE-CLIPBOARD-OR-RESTORE** | 🟢 LOW | Smoke A pt27 (rollback `.exe` pt25d para validar baseline antes de atacar fix popup) revelou: watcher arrancou mas não conseguiu processar `GG-5944816316`. Causa exacta não isolada — 3 hipóteses: (a) auto-restore HRC da última "Hand 1" persistida cria race condition com paste do watcher; (b) clipboard interference (Windows clipboard history ou script paralelo); (c) state.json pt25d mostra **40 de 41 mãos pulled em 14 Maio nunca chegaram a `done`** — fragilidade conhecida da baseline, não regressão nova. **Decisão pt27:** não investigar mais — o caminho é fixar `#START-CALC-SELECTED-SUBTREE-NO-POPUP-OPEN` em pt28, não restaurar pt25d. Tech debt mantém-se como recordatório histórico se algum dia for necessário voltar ao pt25d como fallback. |

## Estado actual (19 Maio 2026 pós-pt26 closeout)

Sessão pt26 fechada com **1 commit feature em main** (`a735053`, pt26 smoke
calibração) + commit docs. Trabalho substancial em `_local_only/`
(gitignored): trampoline strategy do `swap_and_smoke.py` (4 SWAP + 13
APPEND + 15 consts), PyInstaller bundle do `.exe` pt26 (12.86 MB, sha256
`2213aa19...a4a7`). Suite **449 → 453 PASSED** (+4 líquidos para tests
de pixels-rel + Nash hint + Calculate calibration).

Re-classificação do problema reportado pelo Rui no smoke real: o sintoma
de "equity_model errado" **não é regressão FT/MTT** (design tag-based é
canónico desde pt23, confirmado nesta sessão) — é cadeia
`#VISION-LOBBY-API-FAILURE → #HRC-CONTEXT-MISMATCH-PLAYERS-LEFT`
mascarada pelo workaround `#HRC-MTT-OTHER-TABLES-INFO` aceite em pt23.
Erro do Web auto-registado no journal pt26: interpretação literal antes
de pattern-matching.

**Estado do gatekeeper `#HRC-PRUNE-IN-GAP-DOWNSTREAM`:** continua
**substituído** pelo flow Bloco 2; recompilação validada mecanicamente
no smoke harness do `swap_and_smoke.py` (14/14 PASS), mas
**funcionalmente bloqueada** por `#START-CALC-SELECTED-SUBTREE-NO-POPUP-OPEN`
(CRIT novo, descoberto no smoke real 19 Maio).

### Tech debts fechados em pt26 (1)

| ID | Como fechou |
|---|---|
| **#CALCULATE-BUTTON-COORD-PENDING** | `a735053` aplicou `CALCULATE_BUTTON_X=204`, `CALCULATE_BUTTON_Y=59` (pixels-rel à wpos, convenção alinhada com `EQUITY_MODEL_X/Y` e `STRATEGY_TABLE_FOCUS_X/Y`). Título Nash refinado para `("Nash Calculation",)` (drop hint permissivo `"Calculate"`). Migração das fracções do popup para pixels-rel (`SCOPE_DROPDOWN_REL = (278, 67)`, etc.) — robustez contra variação de tamanho do popup observada entre smokes 18 e 19 Maio (416×214 → 436×230). Tests 27→31 em `test_watcher_set_scope.py`. Detalhe completo em `docs/JOURNAL_2026-05-19-pt26.md`. |

### Tech debts abertos e fechados em pt27 Bloco B (4)

Diagnosticados na simulação Bloco B da mão `GG-5944816316` (8-handed, MP open 2bb, Hero HJ 3-bet jam, eff 6.64BB). Fechos backend-only — sem mudança no watcher.

| ID | Como fechou |
|---|---|
| **#CI-DEFAULT-MISMATCH** | Backend default `_DEFAULT_CI_TARGET_FIRST_RUN = 5.0` renomeado para `_DEFAULT_CI_TARGET = 10.0` em `services/queue_export.py`. Watcher já hardcode-passa 10.0 a `start_calculation_selected_subtree` (1ª e 2ª run alinhadas). Decisão product do Rui em pt27 Bloco B: opção (ii) "alinhar ambos em 10". |
| **#DERIVE-MAX-PLAYERS-HERO-REGEX-GG** | Aberto + fechado em pt27 Bloco B. Sintoma: `derive_max_players` em `services/derive_max_players.py` devolvia 5 (ou 3 com nicks-com-espaço) em vez de 6 para mão GG-5944816316 8-handed. Cadeia causal: (a) `_HERO_RE = ^Dealt to (\S+)` apanhava o 1º `Dealt to` (em GG pós-`_replace_hashes` todos os 8 seats têm essa linha, não só Hero); (b) `_SEAT_RE`/`_ACTION_RE` usavam `\S+` que truncava nicks com espaços tipo "Andrii Novak" → seat 7 e action filtradas para fora; (c) `_SEAT_RE` matchava também na linha SUMMARY `Seat 6: Hero collected (X)` sobrescrevendo `seats[6]="Hero collected"` e fazendo `Hero` deixar de bater nicks. Fix: (i) `_HERO_RE` exige ` \[` (só Hero tem hole cards visíveis); (ii) `_SEAT_RE` + `_ACTION_RE` mudam `\S+` para lazy `.+?` (tolera espaços); (iii) parsing de seats restrito ao header pré `*** HOLE CARDS ***` para evitar match SUMMARY. +1 test reproduz a mão real. |
| **#COMPUTE-TARGET-NODE-OFFSET-USES-WRONG-PLAYER-COUNT** | Aberto + fechado em pt27 Bloco B. `compute_target_node_offset` em `services/hrc_node_offset.py` usava `max_players` (redução ICM via `derive_max_players`) como input para `strategy_table_positions`. Errado conceptualmente — Strategy Table HRC renderiza uma linha-base por jogador real sentado, não pela redução ICM. Em GG-5944816316 isto fazia `position='MP'` falhar lookup em `strategy_table_positions(6)=[UTG,HJ,CO,BU,SB]` → `target_node_offset=None`. Fix: renomear param para `seats_at_table`; caller `build_queue_zip` passa `len(derive_seats_in_preflop_order(hh_text))` em vez de `hints.get("max_players")`. Tests existentes renomeados semanticamente; +1 test reproduz mão real (offset esperado 4 = 2 posições × 2 linhas + 0 within bucket). |
| **#START-CALC-SELECTED-SUBTREE-NO-POPUP-OPEN** (parcial) | Continua **aberto** para a parte do popup. Dependência backend resolvida: `target_node_offset` agora computa correctamente em mãos cujo agressor está em posição que estava fora da redução ICM. O watcher pode usar este valor para `navigate_to_target_node` antes do click Calculate — mesmo que o popup falhe a abrir, a arrow-nav fica correcta. Diagnóstico do popup propriamente dito (timing/coord/state) continua bloqueador para smoke real funcional. |

### Tech debts novos abertos em pt26 (5)

| ID | Severidade | Resumo |
|---|---|---|
| **#VISION-LOBBY-API-FAILURE** | ✅ FECHADO — RECLASSIFICADO (pt43) | Vision API do lobby falhou em processar o SS do torneio para mão `WN-4690815078549684227-208-1778279040`. Investigação original (pt26): (a) SS associado à mão? (b) `lobby_processing_log` tem entrada? (c) Vision call site em `lobby_vision.py` só faz `logger.error/warning` + `return None`; (d) quotas Anthropic. Fix conceptual pedido: tornar a falha observável + popular `lobby_processing_log`. **✅ Fechado por reclassificação empírica (pt43, 2026-05-29):** a premissa "~34% silent failures" está **stale**. (1) A falha **já é observável** — `process_lobby_message` regista `result='vision_failed'` em `lobby_processing_log` quando a API devolve None (o fix conceptual pedido já existe). (2) Evidência da BD (`lobby_processing_log`, **131 tentativas**, 11-28 Mai): **0 `vision_failed`**, 0 `upsert_error`; falhas reais = `tm_not_found` **66 (50%)** = fase **resolver** (não Vision), `site_undetected` 5 + `json_invalid` 3 ≈ **6%** de qualidade de Vision (output inutilizável, não falha de API). (3) O sintoma original (`players_left` em falta naquela mão) foi re-diagnosticado em pt38 e é rastreado por `#HRC-MTT-STACKS-PAGE-SKIPPED-ON-NULL-PLAYERS-LEFT`; a cadeia pt26 `→ #HRC-CONTEXT-MISMATCH-PLAYERS-LEFT → #HRC-MTT-OTHER-TABLES-INFO` estava errada do 3º elo (falso-positivo confirmado pt38). **Nada a corrigir do lado Vision.** O `tm_not_found` (50%) pertence ao tema resolver (`#RESOLVER-*` pt39-41, maioritariamente fechados) e é em grande parte "falta de TS importado" (operacional, não defeito) — ver closeout pt41; não justifica debt próprio. |
| **#HRC-CONTEXT-MISMATCH-PLAYERS-LEFT** | 🔴 CRIT (sintoma do `#VISION-LOBBY-API-FAILURE`) | HRC calcula como N-handed quando torneio tem K-left (N << K). Para `WN-4690815078549684227-208-1778279040`: 13-left em 6-max, HRC viu 4 jogadores no torneio totais → ICM strategies não confiáveis. Vinculado a `#VISION-LOBBY-API-FAILURE` (causa upstream) e `#HRC-MTT-OTHER-TABLES-INFO` (workaround aceite em pt23 Bloco 7 que mascara este sintoma). Fix em 2 frentes paralelas: (1) garantir `players_left` no meta.json (depende de `#VISION-LOBBY-API-FAILURE`); (2) watcher escreve Other Tables = `ceil((players_left - max_players) / max_players)` quando `players_left` está populado — source-side em `handle_mtt_stacks_page` ou função paralela. Coords + Generate button + sequência de teclas pendentes de calibração smoke. **[Actualização pt38: a frente (2) é desnecessária — o HRC auto-calcula Other Tables ao dar OK no sub-popup com Remaining Players preenchido (`#HRC-MTT-OTHER-TABLES-INFO` = falso positivo). Resta a frente (1): garantir `players_left` por mão — agora rastreada em `#HRC-MTT-STACKS-PAGE-SKIPPED-ON-NULL-PLAYERS-LEFT`.]** |
| **#START-CALC-SELECTED-SUBTREE-NO-POPUP-OPEN** | 🔴 CRIT | Smoke real 19 Maio com `.exe` pt26 mostrou que `start_calculation_selected_subtree` não dispara o popup Nash. `_wait_for_nash_popup` devolve `None` por timeout (5s). Cadeia cai no early-return defensivo de `_set_scope_in_popup`. Hipóteses: (a) `_click_calculate_button` clicou mas popup não abriu por algum estado do HRC; (b) timing — popup demora >5s, `_NASH_POPUP_WAIT_TIMEOUT_S=5.0` curto demais; (c) Calculate button coord `(204, 59)` errado para estado pós-1ª-run; (d) `start_calculation` legacy (não-patched) já abre e fecha popup Nash da 1ª run, o segundo Calculate vai a outro lado. Diagnóstico exige smoke devagar dedicada. **Bloqueia smoke real funcional do `.exe` pt26.** |
| **#FINALIZE-NEVER-FIRES-ON-NO-OP** | 🟡 MED | Quando `start_calculation_selected_subtree` faz early-return por popup não detectado (`#START-CALC-SELECTED-SUBTREE-NO-POPUP-OPEN`), `finalize_after_second_run` é chamado na mesma mas a 2ª run não correu. Zip exportado pode conter só a 1ª run (Full Tree) ou estar vazio/parcial. Fix: `start_calculation_selected_subtree` devolve bool de sucesso; `setup_hand` só chama `finalize` se Selected Subtree completou. Senão `finalize` da 1ª run com warning explícito. |
| **#CI-DEFAULT-MISMATCH** | 🟢 FECHADO em pt27 Bloco B (ver "Tech debts abertos e fechados em pt27 Bloco B" no topo). Texto preservado por contexto histórico. | Smoke real 19 Maio expôs inconsistência: `meta.json.ci` defaulta `5.0` em `_build_hand_meta` ([`queue_export.py:570`](backend/app/services/queue_export.py)); `start_calculation_selected_subtree` chamado em `setup_hand` com hardcoded `10.0`; docstrings DEPRECATED de `set_ci_target_initial/refine` falam de 5.0/10.0. Risk: tree explora em CI=5 na 1ª run mas user pode esperar CI=10 coerente em ambas. Decisão product pendente: (i) split 5/10 explícito; (ii) alinhar ambos em 10; (iii) parametrizar via meta.json. |

## Estado actual (15-18 Maio 2026 pós-pt25f closeout estendido)

Sessão pt25f fechada com **10 commits feature em main** + 2 commits docs.
Núcleo 15-16 Maio: `76e2ea7` / `0444cf2` / `11c2dea` / `e18c8ff` / `cde29f4` /
`9b6e839`. Extensão 18 Maio (não-prevista no scope original): `7e38d89` /
`f99e994` / `fa4f21a` / `92778bd`. Suite **340 → 449 PASSED (+109 líquidos)**.

Focos:
- Núcleo: limpezas cross-case + deprecation fix + versionamento bridge HM3 +
  rotação operacional de password + Trabalho A (refactor gerador `.js` HRC
  com sizings da HH real e prune via JS removido).
- Extensão: regra de multiplicador de efetiva nos 3-bet clássicos (5 buckets)
  + **Bloco 2 do watcher completo source-side** (peça 1 calibrada via
  smoke 2026-05-18 + peça 2 end-to-end com meta.json automático +
  `target_node_offset` + navegação por setas).

**Estado do gatekeeper `#HRC-PRUNE-IN-GAP-DOWNSTREAM`:** **substituído**
em pt25f. Mecanismo original (REAL_AGGRESSOR_POS + DOWNSTREAM_POSITIONS +
guard JS) removido em `9b6e839`. Caminho novo: (a) sizings literais
substituídos no `.js` pela acção real da HH + regra multiplicador para
classic 3-bet (`9b6e839` + `7e38d89`) + (b) Bloco 2 do watcher
(Scope=Selected Subtree + navegação até nó do raiser + 2ª run em subtree —
source-side completo em `92778bd`, recompilação `.exe` pendente pt26).
Gatekeeper continua aberto **apenas** até smoke real end-to-end no Beelink
pós-recompilação. Backend está 100% pronto.

**Falha de governance herdada de pt25:** o prune via JS foi implementado sem
aprovação product explícita do Rui em pt25/b/c/d (decisão user-facing tratada
como optimização técnica). Remediada em pt25f via Trabalho A. Próxima
instância: interpretar a rule de aprovação prévia em
`PAPEIS_E_RESPONSABILIDADES.md` de forma rigorosa para mudanças que afectam o
que o Rui vê quando usa a app/HRC.

### Tech debts fechados em pt25f (8)

| ID | Como fechou |
|---|---|
| **#HRC-PRUNE-IN-GAP-DOWNSTREAM (mecanismo)** | Removido em `9b6e839`. Active code já não tem referências a `REAL_AGGRESSOR_POS` / `DOWNSTREAM_POSITIONS` / `derive_prune_downstream`. Pasta `hrc_scripts/archive/` retém os ficheiros legacy para histórico. O gatekeeper continua aberto na sua intenção (redução de tree explosion), mas o caminho é agora via sizings literais + Bloco 2 do watcher (source-side completo em `92778bd`). |
| **#TEMPLATE-DYNAMIC-SIZINGS-PER-HAND** | Implementado em `9b6e839` exactamente como a tech debt descrevia (per-hand `SIZES_*` substituídos pela acção real da HH via regex sub) — só com semântica de prune via JS removida (não é defense-in-depth como a tech debt sugeria; é substituto). Módulo novo `backend/app/services/hrc_script_gen.py`. Estendido em `7e38d89` com regra de multiplicador para os 5 buckets de 3-bet clássico (sizing real da HH ignorado nesses; opens/squeezes/4-bets/5-bets mantêm sizing real). |
| **#APPHM3-NOT-VERSIONED** (descoberto pt25f) | Migrado para `tools/apphm3/` em `cde29f4`. `config_local.py` gitignored, template `.example` versionado, README PT-PT, fix `datetime.utcnow` aplicado, `.bat`s usam `%~dp0`. Rui migrou localmente. |
| **#DATETIME-UTCNOW-DEPRECATED** (descoberto pt25f) | Substituído em 3 sítios (`routers/hands.py:1326`, `routers/hands.py:1371`, `routers/hm3.py:756`) por `datetime.now(timezone.utc).replace(tzinfo=None)` em `e18c8ff`. Bit-for-bit preservado. Same fix aplicado em `tools/apphm3/hm3_export.py` no commit `cde29f4`. |
| **#WATCHER-BUG-G-SCOPE-SELECTED-SUBTREE** | Source-side completo em `f99e994` (função paralela `start_calculation_selected_subtree` + `_set_scope_in_popup` + defensive returns; opção (b) escolhida vs decompor `start_calculation` legacy — justificação no journal). Coords reais calibradas em `fa4f21a` (smoke 2026-05-18, fracções `SCOPE_DROPDOWN_FRAC = (0.668, 0.313)` + `SCOPE_OPTION_SELECTED_SUBTREE_FRAC = (0.659, 0.505)`; convenção de fracções alinhada com pt25d CI Target). Wiring end-to-end em `92778bd` (passos 1/2/4 do popup flow: `_wait_for_nash_popup` + `_fill_ci_target_in_popup` + `_click_ok_in_popup` via Enter). |
| **#WATCHER-BUG-H-FLOW-ORDER-SAVE-LAST** | Wiring resolvido em `92778bd`. `setup_hand` block "STUBS Bloco 2" descomentado e refeito: `navigate_to_target_node` + `start_calculation_selected_subtree` + `finalize_after_second_run` na ordem correcta após a 1ª run. `export_strategies` continua dentro de `finalize_after_second_run` (stub source-side de pt25e Bloco 1), agora chamado no fim — não no meio. |
| **#WATCHER-BUG-F-CI-TARGET-2ND-RUN** | Confirmado **DEPRECATED**. Popup Nash gere o CI internamente — não é necessário set no main UI antes de Calculate. Stubs `set_ci_target_initial` / `set_ci_target_refine` mantidos no source (`patched_funcs.py`) com docstrings DEPRECATED. Razão para manter: o marshal swap do bundle .pyc pareia cada função patched com slot específica; remover desalinha o slot map já documentado em pt25e Bloco 1. Eliminação fica acoplada ao smoke real pós-recompilação (quando confirmamos que o `_fill_ci_target_in_popup` dentro de `start_calculation_selected_subtree` cobre todos os casos). |
| **#META-AGGRESSOR-REAL-ACTION** (re-confirmado) | Já estava fechado em pt25e Bloco 2 fix urgente; em pt25f passou a alimentar `compute_target_node_offset` no backend (`92778bd`). O campo `position` (BTN→BU follow-up) é input directo do cálculo de offset. |

### Tech debts novos abertos em pt25f (2)

| ID | Severidade | Resumo |
|---|---|---|
| **#CHANGE-PASSWORD-FEATURE** | 🟡 MED | App não tem endpoint nem UI para change-password. Rotação de password do user `rui@pokerapp.com` em pt25f (15 Maio, post-exposure da `MudaEsta123!` em scripts/zips/briefings) foi single-shot via `UPDATE users SET password_hash = ...` na DB Railway com Code com acesso. Próxima rotação volta a depender de DB direct. Fix: implementar `POST /api/auth/change-password` (validar old + bcrypt-hash new + invalidate session opcional) + UI em SettingsPage / Profile dropdown. Pré-requisitos: nenhum. Esforço: ~2h (1 endpoint + 1 form). |
| **#CALCULATE-BUTTON-COORD-PENDING** | 🟢 FECHADO em pt26 (`a735053`) — ver §"Tech debts fechados em pt26" no topo. Texto pt25f preservado abaixo por contexto histórico. | `CALCULATE_BUTTON_X/Y` em `tools/watcher_src/patched_funcs.py:317` ainda a 0 (placeholder) + early-return defensivo no `_click_calculate_button`. Botão verde Calculate no main UI HRC, à direita do painel da Strategy Table — visualmente o único botão "go" verde grande no estado pós-1ª-run. Não documentado no source legacy do Baltazar; `start_calculation` legacy clica-o internamente sem expor coords. Calibração: smoke pequeno comigo no Beelink (Rui usa `pyautogui.position()`, 1 click) — `_local_only/get_calibrate_coords.py` se ainda existir, ou substituto inline. **Bloqueia recompilação do `.exe`**: sem este coord, o `start_calculation_selected_subtree` recompilado faz early-return defensivo do passo 1 e o flow Selected Subtree não dispara. Ao mesmo tempo confirmar o título exacto da janela do popup Nash (hints provisórios `("Nash", "Calculate")` em `_NASH_POPUP_TITLE_HINTS`) — Rui copia o título visível na barra do popup. |

## Estado actual (15 Maio 2026 pós-pt25e Bloco 1 + smoke devagar manual em curso)

Sessão pt25e Bloco 1 fechada (commits `8eb9d87` / `f7c8833` / `bad2c51`). Source watcher (`tools/watcher_src/patched_funcs.py`) ganhou stubs para Bugs F/G/H/J, todos atrás de defensive flags (coords não calibrados → early-return WARN; finalize ainda não wired no Bloco 1). `.exe` em produção (Beelink) continua pt25d intacto — Bloco 1 valida arquitectura, não muda comportamento operacional. Suite **266→282 PASSED** após Bloco 1.

Sessão pt25e Bloco 2 começa com smoke devagar manual. Rui corre o `.exe` pt25d **directamente** no Beelink com a mão GALACTICA (`WN-4706316461629505541-158-1778795596`, Winamax, 6-handed, UTG abre 2.5bb, SB 3-bet all-in, BB Hero call all-in). Pasta preparada à mão sem passar pelo backend: `hh.txt` + `payouts.json` (94 lugares reais do lobby + bountyType PKO + progressiveFactor 0.5 como aproximação ao Space KO Winamax) + `script.js` (template Charles "open 2x" com `SIZES_OPEN_OTHERS=[2.5, ALLIN]` + `SIZES_3BET_SB_VS_OTHER=[7.5, ALLIN]`, sem prune block) + `meta.json` (`stage=MTT`, `players_left=88`, `total_chips=14940000`, `ci=10.0`). 2ª run ainda a correr ao fechar deste briefing; Rui devolve screenshots + export + observações amanhã.

**Status do gatekeeper `#HRC-PRUNE-IN-GAP-DOWNSTREAM`:** **ainda OPEN.** Backend está 100% pt25/b/c/d/e; bloqueio é exclusivamente downstream — fluxo do watcher + dependência position-do-aggressor (este commit pt25e Bloco 2 fix urgente fecha essa dependência).

### Achados do smoke devagar pt25e Bloco 2 (15 Maio, em curso)

1. **MTT Stacks panel workaround por config:** sem `stage: "MTT"` explícito no `meta.json`, o caller cai no branch `elif equity_model == 'multi_table_icm'` (pt23 Bug E fix) e salta o painel com `BTN_NEXT` directo, deixando Other Tables em 0. Para mãos MTT correctas o Rui quer "++" + OK (live em `handle_mtt_stacks_page`, branch `if stage == 'MTT' and (players_left or players_in_hand)`). Fix imediato é config (meta.json com `stage=MTT` explícito + `players_left`); fix longo prazo é reavaliar heurística do branch — provavelmente manter como está e enriquecer meta.json no pipeline upstream.
2. **CI=10 confirmado empiricamente:** com CI=10 a 2ª run baixa de ~7.2h (CI=5) para ~76min. Confirma regra semântica correcta (CI baixo = mais refinado = mais lento) — alinha com a docstring de `_set_ci_target_common`.
3. **Save mid-flow continua a aparecer:** caixa "Save As" abre entre fim da 1ª run e início da 2ª, fica em wait até estratégias estabilizarem. Bug H stub (`finalize_after_second_run`) ainda não está wired. Sem prejuízo para o Bloco 1; reordering completo só depois de G+J calibrados.
4. **Bug I (Basic Hand Data, 1º painel pós-paste da HH)** ainda por isolar. Rui captura amanhã step-by-step.
5. **Re-priorização pelo Rui:** **Bug G > Bug J.** Argumento: Selected Subtree corta a 2ª run para uma fracção do tempo (centrado no spot real da mão) e Prune Action é optimização adicional menos crítica. Bug G passa para HIGHEST entre os 5 bugs do watcher; Bug J reposicionado abaixo.
6. **Solução desenhada para Bloco 2 wiring (depende deste commit fix urgente):** watcher faz OCR confinado à coluna Player da Strategy Table HRC e clica a primeira linha onde `Player == aggressor_real_action.position`; depois click no botão play (já calibrado pt25d); no popup Nash que abre — dropdown Scope → "Selected Subtree" → CI=10 (vem do meta.json) → OK. Reduz drasticamente o custo de OCR (vocabulário fechado de ~6 strings curtos vs OCR genérico sobre toda a tabela). Coords das 3 entradas novas (column Player, dropdown Scope no popup, opção "Selected Subtree") a calibrar em smoke devagar pt25e Bloco 2 final.

### Tech debts pt25e abertos — `#WATCHER-COMPLETE-FLOW` (HIGH gatekeeper) (6)

Ordem actualizada pelo Rui em 15 Maio: Bug G antes de Bug J.

| ID | Severidade | Resumo |
|---|---|---|
| **#WATCHER-BUG-G-SCOPE-SELECTED-SUBTREE** | 🟢 FECHADO em pt25f (`f99e994` + `fa4f21a` + `92778bd`) — ver "Tech debts fechados em pt25f" no topo. Recompilação `.exe` pendente pt26. | A 2ª run tem de correr em Scope=`Selected Subtree`, não em `Full Tree` (default da 1ª). Spec final pt25e Bloco 2 (15 Maio, simplificada): (1) OCR confinado à **coluna Player** da Strategy Table HRC (vocabulário fechado: UTG/HJ/CO/BU/SB/BB/EP/MP/EP1/EP2/`BU/SB`), (2) clicar a primeira linha onde `Player == aggressor_real_action.position` (vinda do payouts.json — este commit fecha a dependência), (3) clicar botão play (coords pt25d já calibrados), (4) no popup Nash que abre: dropdown Scope → seleccionar "Selected Subtree", (5) CI=10 (lido do meta.json), (6) OK. Coords pendentes calibração: column Player, dropdown Scope no popup, opção "Selected Subtree" no dropdown. Re-priorização pelo Rui em 15 Maio: corta 2ª run para fracção do tempo; mais crítico que Bug J. |
| **#WATCHER-BUG-H-FLOW-ORDER-SAVE-LAST** | 🟢 FECHADO em pt25f (`92778bd`) — `setup_hand` STUBS block descomentado, ordem correcta `navigate_to_target_node` → `start_calculation_selected_subtree` → `finalize_after_second_run` no fim. Recompilação `.exe` pendente pt26. | Fluxo actual: Setup → 1ª run → **save_strategies imediato** → done. O save_strategies deve ser **último**, após a 2ª run. Ordem correcta: Setup → 1ª run → (G: Selected Subtree + CI=10) → 2ª run → **save_strategies**. Mover o passo save_strategies da `setup_hand` para função `finalize_after_second_run`. Stub source-side já existe (pt25e Bloco 1, `tools/watcher_src/patched_funcs.py:finalize_after_second_run`); wiring + recompile do `.exe` é trabalho do Bloco 2 após G+J calibrados. |
| **#WATCHER-BUG-J-PRUNE-ACTION-PER-LINE** | 🔴 HIGH | Após 1ª run, o watcher faz Prune Action **linha a linha** para cada player em `DOWNSTREAM_POSITIONS`, percorrendo a tree visual. **CUIDADO armadilha UX HRC:** o context menu tem **2 entradas com "Prune"** — uma é **"Prune Action"** (queremos esta, prune da sizing específica clicada), outra é um Prune global mais agressivo (NÃO esta). Watcher tem de seleccionar o texto exacto **"Prune Action"**. Coords + ordem das entradas no menu a confirmar em smoke devagar pt25e Bloco 2. **Não confundir com o guard `getSizingsOpening` injectado pelo script.js** — esse é prune **scripted** (afecta árvore inicial pre-1ª run); este é prune **manual** sobre nós da subtree pré-2ª run. Os dois complementam-se. Re-priorização 15 Maio: abaixo de Bug G (optimização adicional, menos crítica). **Caminho preferido descoberto 15 Maio (manhã):** atalho de teclado **`Ctrl+D` = Prune Action** na Strategy Table HRC. Permite ao watcher fazer prune via keystroke após seleccionar a linha — sem coords de context menu, sem risco da armadilha das 2 entradas "Prune". Outros atalhos relevantes descobertos na mesma corrida: `Ctrl+Shift+D` (Prune Children — NÃO usar), `Ctrl+Shift+A` (Add Action), `Alt+L` (Lock/Unlock Range), `Ctrl+C` / `Ctrl+Shift+C` (Copy Range / Strategy), `Ctrl+V` / `Ctrl+Shift+V` (Paste Range / Strategy). Wiring de Bloco 2 deve seguir o caminho `Ctrl+D` via `pyautogui.hotkey('ctrl','d')` (ou equivalente), com fallback context menu apenas se `Ctrl+D` falhar em smoke. |
| **#WATCHER-BUG-I-FIRST-PANEL-WRONG-BUTTON** | 🟡 MED | Smoke devagar 14 Maio: Rui detectou que **o watcher clica num botão errado no 1º painel pós-extract** (Basic Hand Data). Repro confirmado visualmente mas sem screenshot/log estruturado ainda. Possíveis causas: deslocamento de coords pós-refresh HRC UI (5.0.X), race condition (botão clicked antes de habilitar), ou rotina chama wrong helper entre `select_bounty_mode` e `setup_scripting`. Identificar exactamente qual botão em smoke devagar dedicado pt25e Bloco 2 (Rui executa step-by-step e regista, planeado para 15-16 Maio). |
| **#WATCHER-BUG-F-CI-TARGET-2ND-RUN** | 🟢 FECHADO em pt25f (DEPRECATED confirmado em `f99e994` docstrings; CI passa a viver dentro do popup via `_fill_ci_target_in_popup` em `92778bd`). Stubs mantidos no source por razão de slot map do marshal swap. | Hipótese inicial pt25e: set CI Target no main UI HRC antes do Calculate, com initial=5.0 + refine=10.0. Smoke devagar 15 Maio revelou que CI value é controlado via `meta.json` campo `ci` que `start_calculation(ci_target)` lê, e o popup Nash que aparece pós-Calculate já tem o campo CI calibrado pt25d (`rect.left + int(w * 0.65)`, `rect.top + int(h * 0.51)`). Set CI no main UI antes do Calculate revela-se **desnecessário**. Helpers `set_ci_target_initial` / `set_ci_target_refine` continuam no source (`patched_funcs.py`) mas **não wired** em `setup_hand` e o early-return defensivo evita clicks falsos. Resolução: manter source-side para histórico mas remover stubs comentados em `setup_hand` quando Bloco 2 fechar; alternativa de fechar formal — limpar em pt25f. |
| **#META-AGGRESSOR-REAL-ACTION** | 🔴 HIGH | Dependência backend: `meta.json` (ou `payouts.json`) tem de ganhar campo novo `aggressor_real_action` com forma `{type: "raise"\|"bet", size_bb: float, position: str\|None}` extraído da HH parseada. Permite ao watcher (Bug G passo 3, simplificado em 15 Maio) clicar a linha exacta na coluna Player da Strategy Table HRC via OCR + position match. Implementação: helper `derive_aggressor_real_action(hh_text, level_sb, level_bb) -> dict\|None` em `services/queue_export.py` — parseia primeira raise/bet preflop, converte chips → bb units relativos ao level da mão, resolve position via `derive_seats_in_preflop_order`, devolve dict. Injecção no manifest entry + payouts.json em `build_queue_zip`. Status: campo `type/size_bb` deployed em pt25e Bloco 1 (commit `8eb9d87`); campo `position` deployed neste commit pt25e Bloco 2 fix urgente (ver `#META-AGGRESSOR-POSITION` abaixo). |
| **#META-AGGRESSOR-POSITION** | 🟢 FECHADO (pt25e Bloco 2 fix urgente, 15 Maio + follow-up BTN→BU mesmo dia) | Extensão de `derive_aggressor_real_action` com campo `position` (string maiúsculas — labels canónicos de `_POSITION_LABELS_BY_N`: UTG/HJ/CO/BU/SB/BB/EP/MP/EP1/EP2 + `BU/SB` para HU). Mapping nick → position via `derive_seats_in_preflop_order` (única fonte de verdade do preflop order pt25d). Schema final: `{type, size_bb, position}`. Schema injection: manifest entry + payouts.json (sítios onde `type/size_bb` já viviam). Tests pytest: 4 samples reais cross-site (PS Votsarrr=BU, GG 221ebf0d=HJ, WN INTERSTELLAR blueballs67=UTG, WPN DAVIDSBAGOFICE=HJ) + sintéticos N=5/N=4/HU cobrindo UTG/HJ/CO/BU/SB/BB/`BU/SB`. Justificação da urgência: destranca Bloco 2 do watcher — OCR confinado à coluna Player com vocabulário fechado de ~6 strings (vs OCR genérico sobre toda a tabela). Follow-up BTN→BU: confirmação empírica do Rui que Strategy Table HRC mostra "BU" não "BTN"; `_POSITION_LABELS_BY_N` realinhado nos índices 3-9 (HU mantém "BU/SB"). |

### Tech debts operacionais descobertos (sessão backfill HM3 pt25e, 15 Maio)

| ID | Severidade | Resumo |
|---|---|---|
| **#RAILWAY-POSTGRES-PASSWORD-DRIFT** | 🟡 MED | Divergência entre `POSTGRES_PASSWORD` da service `Postgres` e o password embutido no `DATABASE_URL` da service `poker-app` (Railway, projecto `trustworthy-dedication`). Diagnóstico empírico durante backfill HM3 pt25e: psql contra `ballast.proxy.rlwy.net:37559` (proxy TCP público) com credenciais da service Postgres dá `FATAL: password authentication failed for user "postgres"`. Credenciais embutidas no `DATABASE_URL` da poker-app autenticam OK. Detalhe: `POSTGRES_PASSWORD` tem 32 chars, password embutido no URL da poker-app tem 31 chars (após URL-decode) — desalinhamento de 1 caractere indicia rotação manual antiga apenas em UM dos sítios (provavelmente a poker-app foi reapontada com `?-password` actualizado mas a service Postgres ficou com o original; ou vice-versa). **Impacto runtime: zero** — a app em produção liga ao DB pelo hostname interno (`postgres.railway.internal:5432`) com o password que de facto autentica. **Impacto operacional: alto-para-ferramentas-locais** — qualquer script `railway run` que linke à service Postgres e use `DATABASE_PUBLIC_URL` falha em auth; o workaround usado em pt25e foi reescrever o URL da poker-app substituindo apenas o host/porto pelo proxy público (`sed -E "s\|@[^/]+/\|@${PG_TCP_DOMAIN}:${PG_TCP_PORT}/\|"`). Fix sugerido: rotar password explicitamente via Railway dashboard (Database service → Connect → Rotate password) e confirmar que `POSTGRES_PASSWORD` + `DATABASE_URL` (Postgres) + `DATABASE_URL` (poker-app) ficam todos sincronizados; ou aceitar a divergência e documentar o workaround do URL-swap no MAPA. **Só documentar nesta sessão**, sem fix. |

### Tech debts pt25f abertos — re-arquitectura template script.js (1)

| ID | Severidade | Resumo |
|---|---|---|
| **#TEMPLATE-DYNAMIC-SIZINGS-PER-HAND** | 🟢 FECHADO em pt25f (`9b6e839`) — ver "Tech debts fechados em pt25f" no topo do ficheiro. Restante texto abaixo preservado por contexto histórico. | Bug K — Re-arquitectura. Template `mtt_advanced_20211029...bvb.js` actualmente declara sizings fixos top-of-file: `SIZES_OPEN_OTHERS = [2, ALLIN]`, `SIZES_3BET_IP = [7.5, 12, ALLIN]`, `SIZES_3BET_BB_VS_SB = [7, ALLIN]`, etc. Estes sizings genéricos inflam a árvore HRC porque o solver explora cada um (e.g., 1ª open: 2bb + ALLIN; 3-bet IP: 7.5bb + 12bb + ALLIN). Para que a árvore contenha apenas o sizing **real** da mão, o backend tem de **injectar dinamicamente** `SIZES_*` per-hand baseados na action sequence parseada da HH. Cada raise/bet preflop é extraído e injectado no slot correspondente (e.g., UTG raise 2.1bb da HH → injectar `SIZES_OPEN_OTHERS = [2.1, ALLIN]`; HJ 3-bet 8bb IP → `SIZES_3BET_IP = [8, ALLIN]`). Reduz a tree drasticamente by design — pode tornar o prune via `getSizingsOpening` (pt25) redundante na prática, mas mantemos como defense-in-depth. Implementação: generalizar `generate_hrc_script` para 2 substituições — (a) bloco prune existente (REAL_AGGRESSOR_POS + DOWNSTREAM_POSITIONS), (b) cada SIZES_* var top-of-file via regex. Helper novo `derive_preflop_sizings(hh_text, level_sb, level_bb) -> dict[str, list[float]]` em `services/queue_export.py` faz parsing completo (5+ raises sequenciais) e mapeia bet_count + position → SIZES_* key. Trabalhoso; depende implicitamente de **#META-AGGRESSOR-REAL-ACTION** (parsing comum). |

### Smoke real pt25d — observações operacionais (14 Maio)

- ✅ Zip `/api/queue/hrc` chega ao Beelink com `script.js` per-hand correcto.
- ✅ `REAL_AGGRESSOR_POS=0` + `DOWNSTREAM_POSITIONS=[1,2,3]` em convenção docs UTG=0 — validado por Rui visual no `.js` desempacotado para INTERSTELLAR (`WN-4699459877053923331-277-1778535900`).
- ✅ Manifest entry com `prune_index_convention="hrc_docs_v1"` (traceability pt25d).
- ❌ Watcher salta 2ª run e exporta directo → tree guardada é a da 1ª run sem prune avaliado em subtree.
- ❌ Bug I (botão errado no 1º painel) detectado mas sem screenshot — pendente repro pt25e.
- **Conclusão:** pipeline backend → adapter → HRC engine está OK; o gap está no fluxo do watcher pós-extract.

### Commits pt25b/c/d/e em main (cronológico)

```
f32ed28  pt25b: robustez backend cross-site (markers WN/WPN + duplicate let fix + table_format detection + seats vazios) + 22 tests
77ff496  pt25c: mover hrc_scripts/ para backend/ (fix Railway deploy) + escalar silent OSError para logger.error + manifest field prune_script_error
3347fcf  pt25d: fix convention indices HRC scripting (UTG=0 docs canonical)
8eb9d87  pt25e bloco 1 #META-AGGRESSOR-REAL-ACTION: helper + injection manifest/payouts
f7c8833  pt25e bloco 1 Bug F: split set_ci_target em initial/refine (watcher source)
bad2c51  pt25e bloco 1 Bug H: re-order setup_hand + stubs Bloco 2 (watcher source)
```

---

## Estado actual (14 Maio 2026 — pt25d fix convenção indices HRC)

Sessão pt25d. Web descobriu via investigação dos docs oficiais HRC scripting que a convenção de índices oficial é **UTG=0 (first-to-act preflop), SB=N-2, BB=N-1** — não a convenção `SB=0, BB=1, UTG=2, ..., BTN=N-1` que `derive_seats_in_preflop_order` usava desde pt25. Bug silencioso: `script.js` injectado correctamente, template tinha o guard `DOWNSTREAM_POSITIONS.indexOf(player) !== -1`, mas `ctx.getActivePlayer()` retorna índices na convenção docs e o nosso array vivia na convenção SB=0 — `indexOf` nunca match → prune nunca disparava → tree continuava a explodir mesmo com pt25/pt25b deployed. **Não detectado em pt25b smoke** porque o smoke real bloqueou no fix script.js missing (pt25c). Confirmação por Web pediu cat do template original + output `generate_hrc_script` para INTERSTELLAR; comparação revelou que `getSizingsOpening` compara `player == ctx.getPlayerIndexButton/SmallBlind/BigBlind()` (API-vs-API, agnóstica) mas o nosso `indexOf` é API-vs-Python-emitted (precisa da mesma convenção).

Fix backend-only — template e JS patch são convenção-agnósticos. Refactor de 3 helpers (`derive_seats_in_preflop_order`, `derive_real_aggressor_position`, `derive_prune_downstream`) + drop de 2 params (`seated_hrc_indices`, `table_format` em `derive_prune_downstream`) + reescrita de `_POSITION_LABELS_BY_N` (8 entries, agora começa em UTG/BTN/BU consoante N e termina em BB). 28 tests reescritos + 18 sintéticos novos (`5h/6max/8max` series cobrindo todas as posições + HU + degenerate cases). Manifest field novo `prune_index_convention="hrc_docs_v1"` para distinguir zips pré-pt25d (buggy) vs pós-pt25d. Suite **264 PASSED** (era 264). Dry-run INTERSTELLAR confirma: `REAL_AGGRESSOR_POS=0, DOWNSTREAM=[1,2,3]` (UTG=0, downstream HJ/BTN/SB; BB=4 excluído). Smoke real pendente: Rui faz cleanup + re-pull Beelink + reporta tree size.

### Tech debts fechados pt25d (1)

| ID | Como fechou |
|---|---|
| **#HRC-INDEX-CONVENTION-MISMATCH** (descoberto pt25d) | `derive_seats_in_preflop_order` mudou a fórmula: `first_to_act_offset = 0 if n == 2 else 3` (HU age primeiro pelo botão; N≥3 age via `button + 3`, wraps mod N). Indices contíguos `0..N-1` por construção, daí drop do param `seated_hrc_indices` em `derive_prune_downstream`. SB-aberto early-return removido em `derive_real_aggressor_position` (era artefacto da convenção velha; com SB=N-2, `derive_prune_downstream` devolve [] naturalmente para esse caso). Commit pt25d ETAPA 3. |

### #HRC-PRUNE-IN-GAP-DOWNSTREAM (gatekeeper)

**Nota pt25f (16 Maio):** o mecanismo descrito abaixo (REAL_AGGRESSOR_POS +
DOWNSTREAM_POSITIONS + guard JS) foi **removido em `9b6e839`**. A redução de
tree passa agora pelo Trabalho A (sizings literais substituídos no `.js`) +
Bloco 2 do watcher. Ver "Estado actual (15-16 Maio 2026 pós-pt25f closeout)"
no topo do ficheiro. O texto abaixo é histórico (pt25 → pt25d).

Continua aberto até smoke real validar tree size pós-pt25d. Pipeline técnico completo:
- pt25 — helpers + JS template guard + adapter integration + lobby_vision `players_left`
- pt25b — robustez cross-site (PS/GG/WN/WPN markers, action format, table layout)
- pt25c — script.js no zip (Railway deploy fix) + manifest `prune_script_error`
- pt25d — fix convention indices (UTG=0 docs canónica)

Sem confirmação real de redução de tree size, o gatekeeper continua HIGH. Smoke real pt25d: Rui apaga state Beelink, re-pull `/api/queue/hrc`, abre INTERSTELLAR no HRC pos-extract, observa tree size na barra inferior — esperamos drop de ~17h ETA / >20GB para minutos / sub-GB se a optimização disparar como pretendido.

---

## Estado actual (13 Maio 2026 — pt25b validado, prune-in-gap robusto cross-site)

Sessão pt25 → pt25b. Foco em `#HRC-PRUNE-IN-GAP-DOWNSTREAM` (HIGH gatekeeper, herdado de pt24). **pt25** implementou 4 frentes core: helpers backend (`derive_real_aggressor_position` + `derive_prune_downstream` + `generate_hrc_script`), JS template guard, `build_queue_zip` escreve `script.js` no zip + override `script_path`, adapter reescreve para path absoluto pós-unzip. Plus `lobby_vision` extrai `players_left` mid-tournament + `lobby_processing_log` ganha coluna dedicada + `_resolve_players_left` lookup SQL. **pt25b** adicionou robustez cross-site (GG/PS/Winamax/WPN): helper novo `find_preflop_marker` (aceita `*** HOLE CARDS ***` e `*** PRE-FLOP ***`); `_PREFLOP_OPEN_RE` ganha colon opcional para action lines WN/WPN; `generate_hrc_script` faz substitution idempotente no placeholder em vez de inserir (evita duplicate `let`); helper canónico `derive_seats_in_preflop_order` com labels por N-handed (suporta 5-sentados-6-max INTERSTELLAR); `derive_prune_downstream` aceita `seated_hrc_indices` para downstream baseado nos sentados. Smoke real (PASSO B5) aguarda transferência adapter ao Beelink.

### Tech debts fechados em pt25b (4)

| ID | Como fechou |
|---|---|
| **#TABLE-FORMAT-DETECTION** | Novo helper `derive_table_format(hh_text)` parsa `\\b(\\d+)-max\\b` (universal nos 4 sites: PS, GG, Winamax, WPN — confirmado em ETAPA 1). `derive_prune_downstream` aceita `seated_hrc_indices` (canónico via `derive_seats_in_preflop_order`); fallback `table_format=8` mantido para tests sintéticos legacy. Commit pt25b ETAPA 3. |
| **#SEATS-EMPTY-TABLE-LAYOUT** | `derive_seats_in_preflop_order` walks apenas pelos seats sentados, mapping contínuo hrc_idx 0..N-1 (N = sentados, não table_format regular). 5-sentados-6-max (INTERSTELLAR Winamax) → `[SB, BB, UTG, HJ, BU]` com hrc_idx [0..4]; CO desaparece em 5-handed labels. Commit pt25b ETAPA 3. (Pt25e follow-up: label "BU" alinhado com Strategy Table HRC; era "BTN" pré-Bloco 2.) |
| **#HH-FORMAT-WINAMAX-MARKERS** | Novo helper `find_preflop_marker(hh_text)` tenta `*** HOLE CARDS ***` (PS/GG/WPN) e `*** PRE-FLOP ***` (Winamax) — devolve a posição mais cedo. `_build_nick_to_hrc_index` + `derive_real_aggressor_position` passam a usar o helper. `_PREFLOP_OPEN_RE` regex ganha colon opcional (`(?::)?`) para action lines sem colon (WN/WPN: `nick raises X to Y`; PS/GG: `nick: raises X to Y`). Commit pt25b ETAPA 1. |
| **#GENERATE-HRC-SCRIPT-DUPLICATE-LET** | `generate_hrc_script` revisto: regex `_PRUNE_PLACEHOLDER_RE` faz `subn` que substitui o bloco placeholder existente do template B2 em vez de inserir um segundo bloco antes de `let ALLIN`. Idempotente (rodar 2× com mesmos args produz output byte-igual). Fallback legacy mantido para templates sem placeholder. Commit pt25b ETAPA 2. |

### Tech debts pt25 ainda open (3)

| ID | Severidade | Resumo |
|---|---|---|
| **#FT-PLAYERS-DIFFERENT-FROM-REGULAR** | 🟡 MED (pt26+) | FT pode ter mais jogadores que a mesa regular (e.g., INTERSTELLAR Winamax é 6-max regular mas FT são 7 jogadores). O threshold `players_left > 3 × max_players` torna-se ambíguo: `3 × regular_max` (=18 para 6-max regular) vs `3 × FT_max` (=21 para 7-max FT). Resolver detectando FT layout do tournament metadata e ajustando `max_players` parameter accordingly. |
| **#BUY-IN-PKO-RATIO-EXTRACTION** | 🟡 MED (pt26+) | Buy-in revela ratio prize:KO real (e.g., INTERSTELLAR €40 prize + €50 KO = 44%:56%, não o 50:50 standard assumido pelo `apply_ratio_lookup` em `services/lobby_vision.py`). Esclarecimento Rui: o average buy-in está **registado na própria HH** da mão — backend pode extrair directamente sem precisar de `tournaments_meta` externo. Útil para enriquecer bounty injection (Bug D futuro) com valores accurate em vez do PKO standard. |
| **#BACKFILL-LOBBY-PLAYERS-LEFT-DISCORD-REFETCH** | 🟢 LOW | Cobertura retroactiva dos 18 lobby snapshots históricos via Discord API re-fetch. Script `scripts/backfill_lobby_players_left.py` está em **shell com `NotImplementedError`** no fetch step (lobby_processing_log NÃO persiste `img_b64`; imagens lobby passam in-memory por `process_lobby_message`). Implementação real exige bot token + lifecycle + rate-limit handling (custo ~$0.18-$0.36 Vision + 30-60min). Sem urgência: Rui posta SS fresca para qualquer torneio recente e o pipeline real-time captura, OU UPDATE manual via Rui visual (pt25 smoke usou esta via: `UPDATE lobby_processing_log SET players_left=36 WHERE discord_message_id='1503540439884501043'` para INTERSTELLAR Winamax tn=1094178268). |

---

## Estado actual (13 Maio 2026 — pt24 em curso, Vision bounty_value_usd validado)

Sessão pt24 em curso. Foco em `#HRC-GG-KOS-EXTRACTION` (HIGH gatekeeper pt24): Vision extrai `bounty_value_usd` (coroa dourada) por player no `players_list`. Prompt + parser de `backend/app/routers/screenshot.py:_extract_hand_data_from_image` actualizado para 5-field format (`name|stack|vpip_pct|bounty_value_usd|country`) com backward-compat 4-field. Smoke pt24 valida 8/8 contra ground truth do Rui em GG-5914506215 (bounty e vpip ambos correctos). **Sem commits ainda**.

### Tech debts novos levantados pt24 (em curso) (4)

| ID | Severidade | Resumo |
|---|---|---|
| **#VISION-BACKFILL-BOUNTY-VALUE-USD** | 🟡 MED (pt25+) | Re-correr Vision (já deployed em commit `59704da` — prompt pt24 com `bounty_value_usd`) sobre `entries.raw_json['img_b64']` de entries antigas com mãos GG já matched, para popular `player_names.players_list[].bounty_value_usd` retroactivamente. Sem este backfill, o bounty injection em `queue_export` (commit pt24 PASSO C) funciona apenas para mãos **novas** daqui em diante (ingestion pós-`59704da`). Implementação: script `backend/app/scripts/backfill_bounty_value_usd.py` que loopa entries com `entry_type='replayer_link'` + `raw_json->'img_b64'` não-null + hands GG matched, chama `_extract_hand_data_from_image` + `_parse_vision_response`, faz UPDATE `hands.player_names` com `players_list` re-extraído. Custo OpenAI: ~$0.01-0.02 por mão × ~N GG hands em prod. |
| **#VISION-STACK-UNIT-DETECTION** | 🟡 MED | Vision às vezes devolve stack em BB sem preservar o sufixo `BB` no output (ex: `28.1` quando devia ser `28.1 BB`). Parser `_parse_vision_response` (`screenshot.py:361`) detecta unit via regex `\\d+\\s*BB`; sem "BB" cai em `stack_unit='chips'` e o valor fica errado (28.1 chips em vez de 28.1 BB ≈ 196 700 fichas a BB=7000). Reproduzido em smoke pt24 (GG-5914506215): 8/8 stacks parseados como chips com valores ridiculos. Solução: cross-ref com a HH (que tem chips canónicos em "(N in chips)") via `_normalize_vision_stacks` (já existe parcialmente). Tunar prompt para reforçar "preserve BB suffix" não é definitivo (Vision pode escapar). Fix robusto: aceitar Vision como advisory, autoritativo = HH parser. |
| **#FIELD-BOUNTY-PCT-MISNAMED** | 🟢 LOW | Historicamente o field `players_list[].bounty_pct` armazena **VPIP %** (orange flame badge), não bounty. Mantido por backward-compat com 4 consumidores backend (`villain_rules.py`, `mtt.py`, `ire.py`, `screenshot.py:_replace_hashes_in_actions`) + 1 coluna BD (`hand_villains.bounty_pct TEXT`). Em pt24 o **prompt** novo de Vision foi clarificado: `vpip_pct` na output line; field key dict `bounty_pct` continua a existir com mesma semântica. Rename completo (key + coluna + 4 consumidores + frontend) fica para refactor futuro. |
| **#FIELD-STACK-CHIPS-AMBIGUOUS** | 🟢 LOW | `players_list[].stack_chips` está em "chips" para stacks que Vision lê numericamente (sem unit declarado) mas pode ser BB-derivado (×bb_size em `_normalize_vision_stacks`) ou valores fictícios (Vision a esquecer-se de preservar BB suffix — ver `#VISION-STACK-UNIT-DETECTION`). Frontend (`HandDetailPage.jsx:233`, `Hands.jsx:1259`) e backend IRE (`ire.py:186-269`) consomem como se fosse autoritativo. Unificar unidade para "chips canónicos" (sempre, com fallback a HH `(N in chips)`) eventualmente. |

### Edit pt24 ainda uncommitted

- `backend/app/routers/screenshot.py` — prompt + parser ganha campo `bounty_value_usd` (smoke 8/8 PASS).

---

## Estado actual (13 Maio 2026 — pt23 em curso, marshal swap + recompile validados)

Sessão pt23 em curso. Descompilação `hrc_watcher.exe` via `pycdc` (build local com VS 2022 Build Tools + CMake) + `dis` manual concluída. Marshal swap das 4 funções alteradas (`set_equity_model`, `get_player_count_from_hh`, `setup_scripting`, `setup_hand`) validado em smoke local (8/8 sub-tests PASS). Re-bundle PyInstaller `--onefile` valida arranque end-to-end no PC principal: launcher carrega `.pyc` swapped, `exec` do main inicia, bate como esperado em `os.makedirs('C:\\Users\\Administrator\\...')` (path do Beelink, não escrevível no PC principal). Pronto para smoke real no Beelink. **Sem commits ainda**.

### Tech debts novos levantados pt23 (em curso) (5)

| ID | Severidade | Resumo |
|---|---|---|
| **#HRC-PRUNE-IN-GAP-DOWNSTREAM** | 🔴 HIGH (pt24+) | **Gatekeeper de produção.** Reduzir tree HRC eliminando opens in gap das posições **downstream** do agressor inicial (pathways paralelos puros — só ocorreriam se agressor foldasse, o que não aconteceu na mão real → impacto zero no EV do spot focal). **Trigger:** `players_left > 3 × max_players` (pré-3 final tables, fase Multi Table ICM). **Excepção:** agressor SB → não trigger (BB nunca open). Por agressor inicial, eliminar opens in gap de: UTG → `{EP,MP,HJ,CO,BU,SB}`; EP → `{MP,HJ,CO,BU,SB}`; MP → `{HJ,CO,BU,SB}`; HJ → `{CO,BU,SB}`; CO → `{BU,SB}`; BU → `{SB}`. **Importante:** NÃO eliminar upstream (já foldaram mas range de fold real importa para card removal no nó focal). **Implementação pt24:** helper `derive_prune_downstream(hh_text, max_players, players_left) -> list[str] \| None` em `services/queue_export.py` → novo campo `prune_in_gap_downstream` em `payouts.json` → script HRC (variante `bvb.js`) lê hint e faz prune action por posição. **Razão da prioridade:** smoke real pt23 confirmou trees com ETA ~17h sem esta optimização, inviabilizando uso em volume real. |
| **#HRC-GG-KOS-EXTRACTION** | 🔴 HIGH (pt24) | GGPoker HHs exportadas sem bounties (KOs) → HRC roda PKO em vazio. Solução planeada: pipeline Vision (Claude Sonnet similar a `services/lobby_vision.py`) extrai `{nick: bounty}` da SS anexada à mão via `hand_attachments`, backend `services/queue_export.py` enriquece HH PS-compat inserindo bounties em cada linha `Seat` antes de enviar para o adapter. |
| **#HRC-MTT-OTHER-TABLES-INFO** | ✅ FALSO POSITIVO (re-classificado pt38) | **[Re-classificado pt38 — ver secção pt38 no topo. O HRC auto-calcula Other Tables a partir de Remaining Players ao dar OK no sub-popup "Generate MTT Stacks"; o workaround não era necessário.]** _Texto histórico:_ Multi Table ICM com Other Tables = 0 (default actual) reduz-se semanticamente à Final Table ICM — perde a contribuição informativa das outras mesas. Para precisão real, watcher precisa de info das outras mesas (player counts, stack averages). Backend pode derivar via `tournaments_meta` ou Lobbarize. Por agora aceitamos `Other Tables=0` (pipeline funcional, precisão sub-óptima). Descoberto no smoke real pt23 — fix cirúrgico Bug E em `setup_hand` clica Next sobre a página MTT Stacks sem preencher, em vez de pendurar o wizard. |
| **#WATCHER-META-INJECTION-BYPASSED** | 🟢 LOW (pt24+ refactor) | Watcher Baltazar Apr19 tinha `inject_meta_into_zip(hand_path, export_zip)` + `zip_is_ready` (verifica `done/replied/<hand>.zip`) que assumiam um "bot externo" que movia o zip de `Exports/` → `replied/` e adicionava `meta.json` com `{rank, players_left, stage, ci}`. Esse bot **não existe na pipeline poker-app→adapter→watcher** (pt22+). Adapter agora injecta meta minimal (`{hand_id, exported_at, source, watcher_built_meta=False}`) em `_ensure_meta_in_zip` antes do POST. Implicação: `inject_meta_into_zip` + ramo `replied/` no watcher são dead code. Quando refactorizarmos o watcher (pt24+) remover. Adapter perde acesso a `rank/players_left/ci` (esses valores existem em settings.json interno do HRC mas exigem parser do formato HRC — adiar para quando for útil). |
| **#PYINSTALLER-BUNDLE-SIZE** | 🟢 LOW (sem prazo) | Bundle re-empacotado em pt23 tem 13.4 MB vs 30.5 MB original do Baltazar. PIL/Pillow não auto-detectado pela análise estática do PyInstaller a partir do `wrapper.py`; provavelmente outras libs do bundle Apr19 que não são essenciais para runtime. Tunar `_local_only/watcher_decompile/build_pyi/hrc_watcher.spec` quando for relevante (ex: se faltar dep em runtime real no Beelink). |

---

## Estado actual (13 Maio 2026 — pós-pt22, Adapter G1 deployed, 3 bugs watcher tracked)

Sessão pt22 fechada. **2 commits feature em main:** `cc93698` (G1 adapter Python Beelink), `67761a0` (fix regex hand_id Winamax). + commit docs de fecho. Pipeline mecânico Beelink ↔ poker-app **validado ponta-a-ponta**; smoke funcional bloqueado por **3 bugs do watcher Baltazar** que exigem descompilação do exe. Suite **172 PASSED** inalterada (adapter é cliente externo). Detalhe completo em `docs/JOURNAL_2026-05-13-pt22.md`.

### Commits da pt22 em main (cronológico)

```
cc93698  feat(hrc-adapter): G1 adapter Python Beelink ↔ poker-app API
67761a0  fix(hrc-adapter): regex hand_id aceita formato Winamax multi-segmento
```

### Tech debts fechados pt22

| ID | Hash | Resumo |
|---|---|---|
| **G1 adapter (queue/results bridge)** ✅ | `cc93698` | 4 ficheiros novos em `tools/hrc_adapter/`. Loop Python 3.14 a correr no Beelink: GET zip → unzip → watcher → POST results. state.json local atomic. Logging diário rotativo 14d. Fecha G1 do plano Fase 3. |
| **Adapter regex multi-segmento** ✅ | `67761a0` | `HAND_ID_RE` agora `^[A-Z]+-\d+(-\d+)*$` — cobre GG (1 segmento) + Winamax (3 segmentos). 40 mãos WN saltadas no 1º tick smoke deixam de ser skipped. |

### Tech debts novos levantados pt22 (9)

| ID | Severidade | Resumo |
|---|---|---|
| **#HRC-WATCHER-EQUITY-MODEL-FIXO** | 🔴 HIGH | Bug A — watcher fixo em `Malmuth-Harville ICM`, sem branch para `Multi-Table FGS`. Mãos mid-MTT ficam com equity FT-style → solver dá EVs científicamente questionáveis. Solução proposta pelo Rui: tag-based design via canais Discord `#icm-ft`/`#icm-pko-ft` + HM3 tags → hint `equity_model` no payouts.json → watcher (recompilado) lê hint. Especificação em `REGRAS_NEGOCIO.md §14`. **Bloqueia G5/G6 funcionais**. Requer recompilação do watcher (pt23). |
| **#HRC-WATCHER-MAX-PLAYERS-ESTATICO** | 🔴 HIGH | Bug B — `get_player_count_from_hh()` regex de seats sentados na HH (ex: 8-9) em vez de jogadores relevantes à decisão (ex: 3 para `UTG raise / MP+CO+SB fold / BTN call / BB→hero`). Árvore do solver explode com combos irrelevantes → tempo de cálculo + EV diluído. Solução: parsing HH no watcher (`last_raiser_position → hero_position` + `players_after_hero_still_active`). Requer recompilação. |
| **#HRC-WATCHER-JS-HARDCODED** | 🔴 HIGH | Bug C — script `mtt_advanced_20211029 - 2 flats + bb close action size open 2x - 3x bvb.js` carregado por nome literal. Ranges muito largos → tree >20GB → OOM crash HRC. Mitigação imediata (sem recompilar): substituir o ficheiro do mesmo nome por versão tight. Final: config externa no watcher (env var `HRC_SCRIPT_PATH` ou metadata por mão). Requer recompilação. |
| **#HRC-WATCHER-DECOMPILE-REQUIRED** | 🔴 HIGH | Baltazar (autor do `hrc_watcher.exe`) emigrou, sem contacto. Sem fonte Python original. Material já no repo: `_local_only/hrc_watcher.exe` (30.5 MB), `_local_only/extracted/` (bytecode raw via pyinstxtractor), `_local_only/ANALYSIS.md` (~80% mapeado por análise estática). Próximo: `pycdc` ou `decompyle3` para gerar `.py` legível. Bloqueia A/B/C. Sessão pt23. |
| **#HRC-WATCHER-PATH-BETA-LEGACY** | 🟡 MED | Watcher hardcoded a 3 paths sob `C:\Users\Administrator\...` incluindo `AppData\Local\HoldemResources\HRC Beta\hrc.exe`. Hoje funcional via perfil legacy preservado pelo reset Windows; instalação HRC moderna do `riand` é em `Local\Programs\HoldemResources\HRC\` (sem "Beta"). Reconsiderar pós-recompilação — tornar paths configuráveis (env var ou config file). |
| **#HRC-ADAPTER-SCHEDULED-TASK** | 🟢 LOW | Adapter actualmente em interactive console (`python hrc_adapter.py`). Migrar para Windows Scheduled Task com restart-on-fail (instruções em `tools/hrc_adapter/README.md`). Não bloqueia nada — Rui pode parar com Ctrl+C; útil quando o adapter for 24/7. |
| **#SERVER-FILTER-HRC-STATUS** | 🟢 LOW | `GET /api/queue/hrc` (`routers/queue.py:export_queue`) **não** filtra mãos que já têm `hrc_jobs.status='done'`. Devolve sempre o mesmo conjunto baseado em tags/study_state. Adapter usa `state.json` local para dedup (D10 aprovado em pt22). Servidor podia filtrar para reduzir bandwidth — adicionar `WHERE NOT EXISTS (SELECT 1 FROM hrc_jobs WHERE hrc_jobs.hand_db_id = hands.id AND hrc_jobs.status = 'done')`. |
| **#HRC-RESET-PRESERVATION** | 🟡 MED | Perfil `Administrator` legacy intacto pós-reset Windows é **frágil** — qualquer reset/reinstall futuro pode levar tudo (script Charles, pasta `Teste completo\`, subpastas `done/arquivo/replied`). Mitigação: clonar pasta `Teste completo\` para `C:\Users\riand\Documents\Teste completo\` e reconsiderar paths hardcoded. Depende de `#HRC-WATCHER-PATH-BETA-LEGACY`. |
| **#TOKEN-ROTATION-DEFENSIVE-PT23** | 🟡 MED | `HRC_WATCHER_API_KEY` actual (mask `Z10Soz9...37zSZ`) foi visto numa screenshot Railway que Rui partilhou ao Web durante debug pt22. Rotação defensiva pré-pt23: gerar novo via `python -c "import secrets; print(secrets.token_urlsafe(48))"`, meter no Railway dashboard (save + redeploy), atualizar `.bat` no Desktop, executar no Beelink. Code valida via CLI que mask mudou. |

### Decisões fechadas pt22

**Adapter G1 (D1-D10 + A1-A5):** D1 Python 3.14.5 / D2 source em `tools/hrc_adapter/` + copy manual / D3 interactive→Scheduled Task faseado / D4 `TimedRotatingFileHandler` 14d / D5 60s poll / D6 2 patterns (done/*.zip + <hand>/.failed) / D7 state.json atomic / D8 setx HKCU / D9 Retry urllib3 nativo 3x backoff 5/10/20s / D10 state.json local source of truth / A1 startup_scan / A2 estrutura repo / A3 logging com hand_id / A4 except amplo / A5 validação regex+RESERVED_NAMES.

**Watcher fix (decisão Web+Rui):** Opção 2 — descompilar `hrc_watcher.exe` em pt23. ANALYSIS.md cobre ~80%; resto via `pycdc`. Fixes cirúrgicos A/B/C + recompilar PyInstaller.

### Smokes validados em prod (pt22)

- **GET /api/queue/hrc** com Bearer válido → 200 OK + zip `queue_<ts>.zip` (size ~280 KB).
- **POST /api/queue/hrc/results** (status=done) → 200 OK, `hrc_jobs.status='done'`, `result_zip` populado em BD prod.
- **Pipeline mecânico ponta-a-ponta** — pull → unzip → watcher abre HRC → wizard completo executou → zip exportado para `done/<hand_id>.zip` → adapter POST → BD actualizada.

### Tech debts URGENT carry-over (pt19+, **nenhum atacado em pt22**)

- **Mãos órfãs em massa** (HIGHROLLER €250 WINAMAX, 27 mãos `#icm-pko` sem villains).

### Tech debts pt21 carry-over abertos (3)

- `#HRC-JOBS-HISTORY-SUBSEQUENT` 🟢 FUTURE / `#HRC-RESULT-STORAGE-MIGRATION` 🟢 FUTURE / `#HRC-AUTH-MULTI-KEY` 🟢 LOW.

### Tech debts pt20 carry-over abertos (5)

- `#BACKOFFICE-MYSTERY` 🟡 / `#TS-RATIO-MYSTERY-CONFIRM` 🟢 / `#TS-AUTO-PAYOUTS-ICM` 🟢 / `#SYNC-RECENT-RESPECT-MANUAL` 🟡 / `#PYDANTIC-V1-VALIDATOR-DEPRECATION` 🟢.

---

## Estado actual (12 Maio 2026 — pós-pt21, backend Fase 3 HRC G3+G4+G2 deployed)

Sessão pt21 fechada. **3 commits feature em main:** `5b9c10a` (G3 hrc_jobs schema), `764b53e` (G4 auth dual-path), `2fa1f60` (G2 POST /results). HRC_WATCHER_API_KEY setada em Railway env vars pelo Rui. Smokes G4+G2 validados em prod. Suite **154 → 172 PASSED** (7+11 tests novos, G3 sem tests dedicados — opção B). HEAD `2fa1f60` + commit docs. Detalhe completo em `docs/JOURNAL_2026-05-12-pt21.md`.

### Commits da pt21 em main (cronológico)

```
5b9c10a  G3 — tabela hrc_jobs schema
764b53e  G4 — auth dual-path cookie + Bearer
2fa1f60  G2 — POST /api/queue/hrc/results
```

### Tech debts fechados pt21

| ID | Hash | Resumo |
|---|---|---|
| **Schema persistência HRC** ✅ | `5b9c10a` | Tabela `hrc_jobs` criada com PK BIGSERIAL, FK ON DELETE CASCADE para `hands(id)`, UNIQUE (hand_db_id), status CHECK 5 valores, result_zip BYTEA. Fecha G3 do plano Fase 3. |
| **Auth long-lived para watcher** ✅ | `764b53e` | `require_auth_or_api_key` aceita cookie OU `Authorization: Bearer` constant-time. Aplicado em `/api/queue/hrc` + `/api/queue/hrc/results`. Fecha G4 do plano. |
| **Endpoint feedback do watcher** ✅ | `2fa1f60` | `POST /api/queue/hrc/results` multipart com lookup hand_id, validação zip, extract meta, UPSERT idempotente. Fecha G2 do plano. |

### Tech debts novos levantados pt21

| ID | Severidade | Resumo |
|---|---|---|
| **#HRC-JOBS-HISTORY-SUBSEQUENT** | 🟢 FUTURE | `UNIQUE (hand_db_id)` significa 1 job por mão. Re-upload overwrite. Se a regra de produto exigir histórico de re-attempts (2º solve com depth maior, comparação A/B), criar tabela auxiliar `hrc_job_attempts (id BIGSERIAL, hrc_job_id BIGINT FK, attempted_at, result_zip, meta_json)`. Migração não-destrutiva — adiciona, não muda. |
| **#HRC-RESULT-STORAGE-MIGRATION** | 🟢 FUTURE | `result_zip BYTEA` em BD. Volume actual estimado: Rui ~10-50 mãos/dia × ~273 KB de zip (GET) + zip results de ordem similar ≈ ~30 MB/dia. Aceitável durante meses. Migrar para storage externo (S3/R2/Railway storage quando existir) se chegar a GBs. Schema fica igual; coluna passa a TEXT (URL) + helper de read async. |
| **#HRC-AUTH-MULTI-KEY** | 🟢 LOW | `HRC_WATCHER_API_KEY` env var única cobre 1 watcher. Para 2+ máquinas (Beelink 2, watcher cloud, local test), migrar para tabela `hrc_api_keys (id, name, key_hash, created_at, last_used_at, revoked_at)`. Revogação granular sem redeploy, auditoria por key. Endpoint admin `POST/DELETE /api/admin/hrc-keys` protegido por cookie. |

### Decisões fechadas pt21

**G3 (schema hrc_jobs):** S1 FK INTEGER ON DELETE CASCADE / S2 BYTEA + size / S3 TEXT CHECK 5 valores / S4 JSONB / S5 BIGSERIAL PK + UNIQUE hand_db_id / S6 índice (status, submitted_at) / S7 services/hrc_jobs.py novo.

**G4 (auth dual-path):** D-G4-1 env var (opção A) / D-G4-2 `Authorization: Bearer` / D-G4-3 `HRC_WATCHER_API_KEY` / D-G4-4 48 bytes URL-safe / D-G4-5 `{id: None, email: None, auth_type: 'api_key'}` / D-G4-6 só endpoints HRC / D-G4-7 MAPA deferido / D-G4-8 log INFO em uso / D-G4-9 Bearer inválido não fallback / D-G4-10 key setada na sessão / D-G4-11 Rui gera local.

**G2 (POST /results):** D-G2-1 `/api/queue/hrc/results` / D-G2-2 multipart / D-G2-3 hand_id query / D-G2-4 50 MB cap / D-G2-5 validação minimal / D-G2-6 meta server-side / D-G2-7 augmentar meta / D-G2-8 UPSERT overwrite / D-G2-9 404 ausente / D-G2-10 só done+failed / D-G2-11 failed→error obrigatório / D-G2-12 1 por request / D-G2-13 MAPA fecho / D-G2-14 zip sintético / D-EXTRA-1 11 tests / D-EXTRA-2 submitted_at preservado / D-EXTRA-3 server-side wins / D-EXTRA-4 WARNING no failed com file.

### Smokes validados em prod (pt21)

- **G4 GET com Bearer**: `GET /api/queue/hrc?include_no_payout=true` → HTTP 200, size=279910 bytes (zip elegível). Via `railway run python` (env var injectada no subprocess, key nunca printed).
- **G2 POST sem auth**: HTTP 401 `"Não autenticado"` (rota registada).
- **G2 POST com Bearer + hand_id inexistente**: HTTP 404 `"hand_id 'GG-NONEXISTENT-99999' não encontrado"` (pipeline completo end-to-end).

### Achados operacionais (verificação BD pós-G3)

- `DATABASE_PUBLIC_URL` no serviço Postgres tem password stale (32 chars vs 31 chars real do `poker-app`). App usa internal URL, prod não bloqueada. Para queries externas: usar password do `poker-app` + proxy público do `Postgres`. Não formalizado como tech debt (workaround conhecido).
- `backend/.env` local com encoding não-UTF8 (byte `0xe3` em position 82). Causa `UnicodeDecodeError` em scripts ad-hoc que importam `app.db`. Workaround: ler vars via `subprocess(railway variables --kv)`. Não formalizado como tech debt (workaround conhecido).

### Operacional paralelo — Beelink GTR5 (Rui)

Reset PC nuclear (Windows reinstall local), conta `riand` criada, updates terminados, Python 3.12 instalado, HRC reinstalado, `hrc_watcher.exe` (30.5 MB PyInstaller) copiado do PC principal. **Pendente pt22:** `C:\hrc\queue\` + `C:\hrc\done\`; `hrc_watcher.exe --help` captura output.

### Tech debts URGENT carry-over (pt19+, **nenhum atacado pt21**)

- **Mãos órfãs em massa** (HIGHROLLER €250 WINAMAX, 27 mãos `#icm-pko` sem villains).

### Tech debts FASE 3 carry-over

- **#FASE-3-MINIPC** — substancialmente avançado em pt21 (reset+setup base); falta G1 adapter + smoke real (pt22).

### Tech debts pt20 carry-over abertos (5)

- `#BACKOFFICE-MYSTERY` 🟡 / `#TS-RATIO-MYSTERY-CONFIRM` 🟢 / `#TS-AUTO-PAYOUTS-ICM` 🟢 / `#SYNC-RECENT-RESPECT-MANUAL` 🟡 / `#PYDANTIC-V1-VALIDATOR-DEPRECATION` 🟢.

---

## Estado actual (12 Maio 2026 — pós-pt20, sync-recent + backoffice import deployed)

Sessão pt20 fechada. **2 commits feature em main:** `5465b32` (Commit E sync-recent + `lobby_processing_log`) e `af7e3c8` (endpoint backoffice `/api/tournament-results/import`). Ambos validados em campo. 5 tech debts novos registados, 2 fechados implicitamente. Suite **122 → 154 PASSED** (16+16 tests novos). HEAD `af7e3c8`. Detalhe completo em `docs/JOURNAL_2026-05-11-pt20.md`.

### Commits da pt20 em main (cronológico)

```
5465b32  Commit E — sync-recent de lobbys + lobby_processing_log
af7e3c8  Backoffice import — /tournament-results/import (vanilla+PKO)
```

### Tech debts fechados pt20

| ID | Hash | Resumo |
|---|---|---|
| **Persistência falhas #lobbys** ✅ | `5465b32` | Tabela `lobby_processing_log` UPSERT por `discord_message_id`. Handler real-time + sync-recent registam cada tentativa com `attempt_count`, `reason_detail`, `vision_json`. Logs Railway deixaram de ser source-of-truth para falhas. |
| **Buraco TS → tournament_payouts** ✅ | `af7e3c8` | Endpoint `POST /api/tournament-results/import` faz upload de SSs do backoffice GG, cruza com `tournament_summaries` via TIER 0 resolver, popula `tournament_payouts` com blob HRC completo (distribuição de prizes por posição). Vanilla + PKO; Mystery em tech debt separado. |

### Tech debts novos levantados pt20

| ID | Severidade | Resumo |
|---|---|---|
| **#BACKOFFICE-MYSTERY** | 🟡 MEDIUM | Suportar Mystery KO no backoffice import. Hoje devolve `mystery_unsupported` (fail-fast em `tournament_results._process_one` quando `ts_tournament_format == 'KO'`). Precisa de sample SS Mystery real + confirmação do `bountyType` aceite pelo HRC Structure Manager (`"KO"` ou mapear para `"PKO"` com factor especial). 📎 **Estrutura real observada (PS Mystery, split 33/67, KOP > PP, valores random):** ver «Estruturas observadas — Mystery Bounty PokerStars (2026-05-28)» na secção IRE. |
| **#TS-RATIO-MYSTERY-CONFIRM** | ⏸️ ADIADO (pt43) | Confirmar `apply_ratio_lookup` em `services/lobby_vision.py:35-45` para Mystery KO `("KO", 0.33)`. Web mencionou em pt20 que regra GG real é 25/75 — clarificar antes de fechar #BACKOFFICE-MYSTERY (impacta validação de drift). 📎 **Corroboração empírica (PS Mystery 2026-05-28):** split observado **PP ≈ 33%** / KOP ≈ 67% bate com `0.33` **enquanto fracção de PP** — atenção à ambiguidade PP-fraction (0,33) vs KOP-fraction (0,667). Ver «Estruturas observadas — Mystery Bounty PokerStars (2026-05-28)» na secção IRE. **⏸️ Adiado (pt43, 2026-05-29):** bloqueado por `#MYSTERY-KO-DUAL-SUPPORT`. Não há decisão técnica isolada a tomar aqui — a semântica do ratio (0,33 PP-fraction vs 25/75) só tem impacto quando o pipeline Mystery for implementado a sério; resolve-se dentro desse tech debt. A corroboração empírica fica registada para esse momento. |
| **#TS-AUTO-PAYOUTS-ICM** | 🟢 FUTURE | Derivar `tournament_payouts` automaticamente a partir do TS via algoritmo ICM (TS tem pool+players+ratio; falta distribuição). Decisão de produto: ICM é estimativa, backoffice é literal. Manter pipelines distintos a não ser que Rui peça automação. |
| **#SYNC-RECENT-RESPECT-MANUAL** | 🟡 MEDIUM | `sync-recent` actualmente re-tenta SSs onde já há `tournament_payouts.source` `manual:` ou `backoffice_vision:` — overwrite com `discord_lobby_vision:` (dados parciais) seria regressão de qualidade. Adicionar guard: `process_lobby_message` skipa UPSERT se source actual ≠ `discord_lobby_vision:`. Hoje a precedência D11 está documentada mas não enforced no lobby pipeline (só no backoffice). |
| **#PYDANTIC-V1-VALIDATOR-DEPRECATION** | 🟢 LOW | `routers/lobbys.py:34` usa `@validator` Pydantic V1 (1 warning durante pytest). Migrar para `@field_validator` V2. Sem impacto funcional; cosmético. |

### Decisões fechadas pt20

**Commit E (sync-recent lobbys):**

| # | Decisão |
|---|---|
| D1 | Síncrono (4-10 min worst-case; sem job queue) |
| D2 | Throttle Anthropic default 1.2s; override no body |
| D3 | `max_messages` default 200, hard cap 500 |
| D4 | UI sub-painel em `Discord.jsx` |
| D5 | Extracção α — core para `services/lobby_sync.py` |
| D6 | Tabela `lobby_processing_log` (β) criada |
| D7 | Reusar `tournament_resolver.resolve_tournament_number` |
| D8 | Sem log da Vision para casos sem `#lobbys` |

**Backoffice import:**

| # | Decisão |
|---|---|
| D1 | Naming `/api/tournament-results/import` |
| D2 | Hardcoded `GGPoker` (param ignorado) |
| D3 | Tolerância 0.05 vanilla / 2% PKO relativa |
| D4 | Cap 20 imagens / 50 em zip |
| D5 | UI inline (não modal) |
| D6 | Source `backoffice_vision:<filename>` |
| D7 | Reusar resolver TIER 0 |
| D8 | NÃO registar em `lobby_processing_log` |
| D9 | Refactor `detect_image_mime` → `services/image_utils.py` |
| D10 | Scope vanilla + PKO; Mystery fora |
| D11 | Precedência `manual > backoffice > lobby` |
| D12 | Mystery ratio mantém `0.33` (tech debt para confirmar) |
| D13 | Mystery → fail-fast `mystery_unsupported` |

### Smokes validados em campo (pt20)

- **sync-recent** (Commit E): 6 candidatos, 4 successes, 2 falhas (Daily Hyper $80 GG, Vision `json_invalid`). Persistência em `lobby_processing_log` confirmada.
- **backoffice vanilla** (`af7e3c8`): Daily Hyper $80 tn=283542054, 18 prizes, 7.4s.
- **backoffice PKO** (`af7e3c8`): Bounty Hunters Deepstack Turbo $88 tn=282721937, 51 prizes, 13.1s.

### Operações ad-hoc pt20

- INSERT manual tn=283542120 (errado, detectado por Web), revertido via `DELETE`+`INSERT` para tn=283542054 (correcto, pool 9420.80, 18 prizes). Soma das prizes bateu **exactamente** ao `prize_pool` do TS. Source: `manual:rui_backoffice_ss_pt20_correction`.

### Tech debts URGENT carry-over (pt19+)

- **Mãos órfãs em massa** (reproducer: HIGHROLLER €250 WINAMAX, 27 mãos `#icm-pko` sem villains em `hand_villains`). Não atacado em pt20. Hipótese: pre-condição `has_cards ∨ has_vpip` muito restritiva para Hyper.

### Tech debts FASE 3 carry-over

- **#FASE-3-MINIPC** (Beelink GTR5 watcher HRC 24/7). Dependência: setup hardware operacional pelo Rui.

---

## Estado actual (11 Maio 2026 — pós-pt19, FASE A + FASE B fechadas)

Sessão pt19 fechada. **FASE A pipeline lobbys fechada em prod** (3 commits A/B/C resolvem G1/G2/G3 de pt18 + refactor terminológico). **FASE B Tournament Summaries fechada em prod** (B1 import + B1.x parser extendido + B2 TIER 0 + B2.1 sem janela com discriminantes Vision). **Backfill GTw → pos-nko** aplicado a 25 mãos em prod (0 GG, 0 overlap). 11 commits totais, HEAD `a4a9595`. Detalhe completo em `docs/JOURNAL_2026-05-11-pt19.md`.

### Commits da pt19 em main (cronológico)

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

### Tech Debts fechados pt19

| ID | Hash | Resumo |
|---|---|---|
| **FASE A — A** ✅ | `d6dedda` | Token-set match em `tournament_resolver` (cobre G2). |
| **FASE A — B** ✅ | `c6088ee` | Fallback `hands` source + `posted_at_hint` window (cobre G1 Winamax/PS, mitiga G3). |
| **FASE A — C** ✅ | `f87be3a` | Caption manual `#TM<num>` no post Discord (bypass do resolver; cobre G3 final). |
| **Refactor TM** ✅ | `440b248` | TM → tournament_number (categoria a/b/c — serviços, símbolos, regex, mensagens). Categoria (d) deferida pt20+. |
| **FASE B B1** ✅ | `9ad1ceb` + `e6bef2d` + `0b0a087` | Import GG TS — tabela, parser 14 campos, endpoint, UI. Fix RealDictCursor row key. |
| **FASE B B1.x** ✅ | `417c071` | Parser TS extendido — 12 campos novos (literais + heurísticas + derivados). Bug regex `_RE_HERO_TOTAL_RECEIVED` apanhado pelos tests defensivos cross-check. |
| **FASE B B2** ✅ | `cdbbc59` | TIER 0 `tournament_summaries` no resolver. 3 helpers privados por tier. |
| **FASE B B2.1** ✅ | `c0ddef5` | TIER 0 sem janela (TS é autoritativo post-jogo). Discriminantes Vision `prize_pool` + `total_players`. |
| **GTw → pos-nko** ✅ | `a4a9595` | Backfill 25 mãos PS/WN/WPN + helper `apply_hm3_tag_aliases` no importer + `(9999, "pos-nko")` em `HM3_REAL_TAGS` + frontend (dropdown + cor). |

### Tech Debts URGENT pendentes pós-pt19

#### Mãos órfãs em massa (🔴 URGENT — reproducer concreto)

- **Reproducer:** Rui partilhou em pt19 screenshot do torneio HIGHROLLER €250 WINAMAX 08/05 com **27 mãos todas órfãs** em `#icm-pko`.
- **Hipótese inicial:** mão sem villain associado em `hand_villains` — regras A/B/C de `_classify_villain_categories` não dispararam. Causa-raiz possível: pre-condição padrão `has_cards ∨ has_vpip` muito restritiva para o tipo de mão deste torneio (Hyper, swings rápidos, pouca acção postflop), e nenhuma das tags HM3/Discord disparou a excepção `nota%`/`nota`.
- **Investigação adiada para pt20+.**

### Tech Debts pendentes (medium / future)

| ID | Severidade | Resumo |
|---|---|---|
| **TS-backfill** | 🟡 MEDIUM | Backfill histórico de Tournament Summaries GG para popular TIER 0 retroactivamente. Sem isto, casos antigos continuam a cair em TIER 1/2. Endpoint `/api/tournament-summaries/import` existe + UI em `Tournaments.jsx`; só falta correr os uploads. |
| **B2.1 Wina/PS** | 🟡 MEDIUM | Validação em campo da B2.1 com Winamax/PS. TIER 0 é GG-only (parser TS é GG-only). Winamax/PS dependem de TIER 2 fallback; field-testing necessário. |
| **Estudo TAGS column** | 🟡 MEDIUM | Vista "TAGS" na secção Estudo só mostra `hm3_tags`; `discord_tags` omitidos. Cosmético mas confunde Rui. |
| **2º Discord entry texto bruto** | 🟢 BAIXA | Marcado como "provavelmente resolvido pelo fix pt9; não-reproduzível em pt19". Reabrir só se Rui voltar a ver. |
| **Refactor TM cat. (d)** | 🟢 FUTURE | ~50 sítios no pipeline `hand_id GG` (screenshot.py, mtt.py, hm3.py, import_.py, discord.py, hands.py). Envolve coluna `mtt_hands.tm_number`, índices, lógica string-replace. Migração de dados necessária. |
| **Vilões vs Estudo arquitectura** | 🟢 FUTURE | Rui levantou em pt19 nuance entre as duas pistas. Discussão de produto antes de mexer. |
| **D — Gyazo URLs em #lobbys** | 🟢 BAIXA | Suporte a links Gyazo em `_handle_lobby_message` (hoje só Discord attachments). ~1h. |
| **E — Sync-recent UI** | 🟡 MEDIUM | `POST /api/lobbys/sync-recent` + botão UI. Permite backfill retroactivo do canal `#lobbys` sem depender de `LOBBY_AUTO=true`. ~2-3h. |
| **F — Cleanup instrumentation** | 🟢 BAIXA | Remover `[debug-msg-lobby]` + lobby channel list log no `on_ready` agora que pipeline está estável. ~10 min. |

### NEW — FASE 3 HRC (Watcher local Beelink GTR5)

- **🔴 ALTA, agendada pt20+.**
- Briefing `HRC_WATCHER_BRIEFING.md` recebido do Rui durante pt19. Cobre as 4 fases do plano de automação HRC; Fase A (FASE A deste repo, pipeline lobbys para popular `tournament_payouts`) **fechada** com este journal.
- **Hardware:** Beelink GTR5 em casa, ainda não ligado. Limpeza prévia necessária.
- **Licença HRC:** OK.
- **Plano:** porting do `hrc_watcher.exe` do Baltazar (`_local_only/ANALYSIS.md`) como referência, mas evitar fragilidades conhecidas — PKO ratio dinâmico do buy-in (não hardcoded), retries em GUI driving Win32 ctypes, error handling robusto.
- **Dependência:** limpeza/setup Beelink (operacional pelo Rui).

### Tech Debts IRE (carry-over de pt16, sem trabalho em pt18/pt19)

Mantêm-se em backlog: **#IRE-MB**, **#IRE-CL**, **#IRE-VB**, **#IRE-SK** (ver secção "Estado actual (8 Maio 2026 — pós-pt16, investigação IRE prod)" abaixo).

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

## Estado actual (9 Maio 2026 — pós-pt18, FASE A pipeline lobbys validado parcialmente)

Sessão pt18 fechada. **FASE 1 HRC export queue validated end-to-end em prod** (smoke real BBG $215). **FASE A C1-C3 deployed** com 9 commits totais (5 feature + 4 fixes/instrumentation). Pipeline lobbys responde no `#lobbys`, Vision API verde, mas TM resolver tem 3 gaps que bloqueiam upserts reais. Backlog ordenado A→B→C→E para pt19. Detalhe completo em `docs/JOURNAL_2026-05-09-pt18.md`.

### Commits FASE 1 + FASE A em main (cronológico)

```
2078eef  FASE 1 C1 — tabela tournament_payouts + endpoints upload
a3dc193  FASE 1 C2 — conversor HH GG → PokerStars-compativel
d16f291  FASE 1 C3 — endpoint GET /api/queue/hrc + build_queue_zip
93b9abc  FASE A C1 — payouts_service refactor
da36f56  FASE A C2 — Anthropic Claude Sonnet 4.6 + lobby_vision + tm_resolver
1ed640c  C2.5    — _DEFAULT_TAGS update (icm-pko/PKO SS/sqz-pko/ICM)
7e302e4  docs    — #FASE-3-MINIPC entry
68f40f9  FASE A C3 — Discord bot dispatch + lobby handler
1d15ac8  C3 patch — instrumentacao temporaria [debug-msg-lobby]
4dd3017  C3 fix   — filtro images Discord CDN URLs (content_type)
cd02d89  C3 fix   — remover assistant pre-fill (Sonnet 4.6 nao suporta)
0a1241b  C3 fix   — MIME magic-number + verbose [lobby] FAIL logs
```

### Gaps identificados na validação real (5 SSs no #lobbys)

| Gap | Casos (5 SSs) | Causa | Fix planeado |
|---|---|---|---|
| **G1** — `tournaments_meta` non-GG vazio | 2/5 (Winamax `GRAVITY`, `HIGHROLLER`) | `services/tournament_meta.py:upsert_tournament_meta` faz skip explícito para Winamax/PS/WPN | **Commit B** |
| **G2** — fuzzy matching insuficiente | 1/5 (`Bounty Hunters Hyper Special $108` → BD tem `Bounty Hunters Sunday Hyper Special $108`) | Vision pode omitir partes do nome; substring `%name%` falha quando nome lido < BD | **Commit A** |
| **G3** — `start_time_iso` ausente / nome muito comum | 2/5 (`Daily Hyper $80` × 2) | Vision não leu timestamp → fallback `LIMIT 5` sem janela; nome corre todos os dias | **Commit C** (caption TM) |

### Tech Debts pendentes pt19 (ordem de prioridade)

| ID | Título | Severidade | Esforço |
|---|---|---|---|
| **A** | Fuzzy / token-set match em `tm_resolver.resolve_tournament_number`. Cada token do nome lido por Vision tem que estar no nome do BD (sem ordem importar). Cobre G2 e elimina sensibilidade a "Sunday/Daily/etc" omitidos. | 🔴 ALTA | ~1-2h |
| **B** | Estender `tm_resolver` em 2 frentes: (i) fallback consulta `hands` directamente quando `tournaments_meta` retorna 0 rows — group by `(tournament_number, tournament_name, MIN(played_at))` com janela `±2h`. (ii) Aceitar `posted_at_hint: Optional[datetime]` (passar `message.created_at` do handler Discord); precedência `start_time_iso ±2h` → `posted_at_hint [-12h, -30min]` → fallback `LIMIT 5`. SS é tirada durante o torneio, logo torneio começou antes de posted_at. Cobre G1 (Winamax/PS) + mitiga G3 parcialmente. | 🔴 ALTA | ~1.5h |
| **C** | Suportar caption manual com TM no `message.content`: regex `\b(?:#|TM)?\s*(\d{8,12})\b`. Quando presente, override do Vision-resolved TM e bypass do resolver. Cobre G3 e qualquer caso ambíguo futuro. | 🟡 MÉDIA | ~30 min |
| **E** | Refactor manual sync de lobbys: endpoint `POST /api/lobbys/sync-recent` + botão UI. Permite backfill retroactivo do canal `#lobbys` sem depender de `LOBBY_AUTO=true` global. Útil quando Rui posta SS em batch. | 🟡 MÉDIA | ~2-3h |
| **D** | Suporte Gyazo URLs em `_handle_lobby_message` — extrair imagem do `message.content` quando contém `gyazo.com` link. | 🟢 BAIXA | ~1h |
| **F** | Cleanup `[debug-msg-lobby]` instrumentation + lobby channel list log no `on_ready` após pipeline estável (commit "remove temporary instrumentation"). | 🟢 BAIXA | ~10 min |

### Tech Debts IRE (carry-over de pt16, sem trabalho em pt18)

Mantêm-se em backlog: **#IRE-MB**, **#IRE-CL**, **#IRE-VB**, **#IRE-SK** (ver secção "Estado actual (8 Maio 2026 — pós-pt16, investigação IRE prod)" abaixo). Não atacados em pt18 por foco em FASE 1 + FASE A.

### Tech Debts FASE 3 (carry-over de pt18)

**#FASE-3-MINIPC** (Beelink GTR5) mantém-se 🔴 ALTA mas **adiada até FASE A pipeline lobbys completo** (= commits A+B+C+E fechados e pipeline a fazer upserts reais consistentemente).

---

## Estado actual (8 Maio 2026 — pós-pt16, investigação IRE prod)

Sessão de investigação read-only sobre o IRE v2 em prod (deployed pt16). 3 tech debts identificados, todos do lado IRE; nenhum requer mudança no `compute_ire` core nem no W3cray lookup.

### #IRE-MB — Monster Bounties tratado como PKO 25% (bug crítico)

- **File:** `backend/app/services/ire.py` (`compute_ire`, gates de filtragem) + `backend/app/services/tournament_meta.py` (schema `tournaments_meta`).
- **Origem:** Investigação prod 2026-05-08 sobre 6 mãos. Hand id=29675 é do torneio "$215 Sunday Bounty Overload [Monster Bounties]" — Monster Bounties = ratio bounty 75%, não 25%.
- **Vector:** A tabela W3cray hardcoded em `ire.py:54-76` (`W3CRAY_TABLE_25PCT`) é exclusivamente para ratio 25% (PKO standard). O único guard contra ratios diferentes é a deny-list textual `SUPER_KO_NEEDLE = "super ko"` que esconde Super KO 40%. Monster Bounties 75% **não** está na deny-list → IRE é calculado mas o valor está errado contra a tabela errada. UI mostra um número aparentemente válido que não corresponde à realidade do torneio.
- **Severidade:** 🔴 Funcional crítico. Dados errados apresentados como certos — pior que esconder.
- **Status:** **pronto para implementar (Onda 1, próxima sessão)** — bloqueador empírico (`instant_fraction` dos Big Bounty) RESOLVIDO em 2026-05-29; ver análise abaixo, ponto 6.
- **Solução temporária (~1h):** alargar a deny-list para apanhar todos os formatos não-25%. Adicionar needles tipo `"monster bounties"`, `"mystery bounties"` (case-insens). IRE fica escondido em vez de errado.
- **Solução robusta (~4h):** adicionar coluna `pko_ratio NUMERIC(4,2)` em `tournaments_meta` (ex: 0.25, 0.40, 0.75) com derivação automática via parser de nome do torneio + override manual. `compute_ire` selecciona a tabela W3cray correcta (ou fórmula fallback) consoante `pko_ratio`. Permite suportar todos os formatos sem deny-list crescente.
- **Esforço:** 1h (deny-list temporária) ou 4h (coluna `pko_ratio`).

#### Análise 2026-05-28 (Web + Rui) — **PRONTO PARA IMPLEMENTAR — bloqueador empírico RESOLVIDO (2026-05-29, ponto 6)**

Sessão de investigação sobre como resolver o `#IRE-MB` correctamente (não só esconder).
Conclusão: o caminho certo **não** é tabelas W3cray paralelas por formato — é decompor a
constante `0.25` em 2 parâmetros lidos por torneio. **Ainda nada implementado**, mas o bloqueador
do ponto 4 ficou **resolvido** com a confirmação empírica do ponto 6 (2026-05-29) → fix pronto
para Onda 1 na próxima sessão.

**1. Mecanismo entendido.** A constante `0.25` do W3cray (`bounty_si = ko_units × 0.25`,
`ire.py:_formula_fallback` + a tabela `W3CRAY_TABLE_25PCT`) decompõe-se em:

> `constante = KOP_fraction × instant_fraction`

- **`KOP_fraction`** = fracção do buy-in que vai para o **bounty pool** (a distribuição): 50% no
  PKO standard, 75% no Big Bounty.
- **`instant_fraction`** = parte do bounty que se ganha **em cash imediatamente** ao eliminar
  alguém. No PKO standard é metade (`0.5`); a outra metade vai para o head do vencedor.

PKO standard 50/50 com instant 0.5 → `0.50 × 0.50 = 0.25`. **Confere** com a tabela e a fórmula
actuais.

**2. Validação.** Derivação independente por pot odds (Rui): bounty inicial = 25% das fichas
iniciais (= metade do KO inicial de 50%); a redução de equity num spot 1-stack / 1-KO =
**5,556%**, que é exactamente `IRE = bounty_si / (4·stack_si + 2·bounty_si)` com `bounty_si=0.25`,
`stack_si=1`. O GTO Wizard descreve o mesmo split do PKO standard: 50% prize / 25% capturável
instant / 25% para o head.

**3. Caminho do fix (proposto, a confirmar).** Em vez de tabelas paralelas por formato, ler 2
parâmetros por torneio e calcular a constante dinamicamente:

- **`KOP_fraction`**: do split do buy-in (disponível no TS / lobby aba Info, ex.
  `"$14.44 + $15 + $2.56"`).
- **`instant_fraction`**: do mecanismo do torneio (lobby diz "instant $X por KO").
- `constante = KOP_fraction × instant_fraction`; aplicar na **fórmula geral**, que é independente
  do formato.
- 50/50 → `0.25` (inalterado); Big Bounty 25/75 com instant 0.5 → `0.375`.

**4. Bloqueador (resolvido no ponto 6).** Confirmar **empiricamente** a `instant_fraction` dos
Big Bounty / Monster. A busca online confirmou progressive 0.5 no PKO standard, mas foi
**inconclusiva** para os Big Bounty (fontes de salas pequenas, sem especificar o
mecanismo). **Rui trouxe um TS+HH de um Big Bounty real** para ler o instant por KO → ✅ **RESOLVIDO
(ponto 6): `instant_fraction = 0,5` confirmado também nos Big Bounty HR do GG.**
⚠️ **Não confundir `instant_fraction` com o `progressiveFactor` do HRC / `lobby_vision.py`** — são
convenções potencialmente distintas (no `lobby_vision` o PKO standard tem `progressiveFactor=0.50`,
mas o IRE trata o bounty standard como 25% do SI). Confirmar a convenção de cada um **antes** de
mexer. Cross-ref: `#TS-RATIO-MYSTERY-CONFIRM`.

**5. Interino.** Enquanto não resolvido, a app continua a mostrar **IRE errado** em Big Bounty.
Opção interina a decidir com o Rui: **deny-list** (não mostrar IRE em Big Bounty — needle no gate
`ire.py:229`, à imagem do `SUPER_KO_NEEDLE`) até o cálculo correcto estar validado.

**6. Confirmação empírica (Big Bounty HR) — 2026-05-29.** ✅ **Fecha o bloqueador do ponto 4.**
- TS analisado: **GG Tournament #278862118**, **$525 Bounty Hunters HR [Big Bounties]**, 554 players.
  Split do buy-in **$150 (PP) + $25 (rake) + $350 (KOP)** → `KOP_fraction` líquida = `350 / 500` =
  **0,70**.
- HH do mesmo torneio: **bounty total na cabeça do eliminado = $262,50**; **instant recebido pelo
  vencedor = $131,25** → `instant_fraction = 131,25 / 262,50 =` **0,5 exacto**.
- Conclusão: a família **Bounty Hunters do GG mantém progressive 0,5** mesmo na variante
  **[Big Bounties]**.
- Constante calculada para este torneio: `0,70 × 0,5 =` **0,35**.
- A fórmula geral `constante = KOP_fraction × instant_fraction` está agora validada com **2 pontos
  empíricos** (50/50 → `0,25`; 30/70 → `0,35`). **Status do bloqueador: RESOLVIDO.**

**7. Nota de implementação pendente.** A tabela W3cray (`ire.py:54-76`) é calibrada
empiricamente para a constante `0,25` e dá valores ligeiramente diferentes da fórmula pura (ex.:
célula `[1,1] = 5,1%` vs fórmula `5,56%`). Para constantes ≠ `0,25` há que decidir: **(a)** usar só
a fórmula nesses casos, mantendo a tabela como caminho rápido para `0,25`; **(b)** recalibrar
tabelas para outras constantes; **(c)** abandonar a tabela e usar sempre a fórmula. Decisão a tomar
quando o fix for implementado.

**8. Cobertura por site (resolvido).** Fonte do `KOP_fraction` por site:
- **GG:** via **TS parser** (já existe).
- **Winamax / WPN:** ~~constante fixa `0,25`~~ — **DESMENTIDO empiricamente (2026-05-29, ZENITH WN
  `1102500091`):** o TS Winamax real tem split **40€/50€/10€** (ordem WN `[entry, bounty, rake]`) →
  `KOP_fraction = 50/90 ≈ 0,556`, **não** 50/50. A assunção "Winamax = sempre PKO 50/50 → constante
  0,25 fixa" está errada. Hoje **sem impacto** (o IRE é GG-only via gate de site em `compute_ire`; e o
  HRC-WN usa os bounties da **HH**, não do TS — pt42c/d). Mas se o gate de site do IRE for relaxado para
  WN, a constante WN tem de ser **derivada do split** (`buy_in_bounty/(buy_in_entry+buy_in_bounty)`),
  nunca assumida `0,25`. O split WN passou a estar disponível em `tournament_summaries` desde o
  `#WINAMAX-TOURNAMENT-SUMMARIES-PIPELINE`.
- **PS:** via **HH header**. Investigação read-only confirmou: buy-in decomposto em **3 componentes**
  (`€A+€B+€C = PP + KOP + rake`; ex. `€22.50+€22.50+€5.00` → 50/50), e **bounty na cabeça por jogador
  inline na linha Seat** (ex. `Seat 1: Berkowitza33 (111680 in chips, €22.50 bounty)`).
  `detect_tournament_format` (`tournament_format.py:97-110`) já faz a detecção estrutural. **Não
  depende do nome do torneio** (o HH PS não o inclui).
  - ⚠️ **Caveat (sub-item):** **Mystery PS** — o que o Seat bounty mostra num HH Mystery PS
    (random/desconhecido) precisa de **confirmação empírica futura**.

**Conclusão:** cobertura completa dos **4 sites** possível na **1ª iteração**, sem novos parsers TS.

📎 **Dado empírico relacionado:** ver «Estruturas observadas — Mystery Bounty PokerStars
(2026-05-28)» logo abaixo. Não é o caso directo (esse lobby é **Mystery**, não Big Bounty
progressive), mas valida o ponto estrutural do ponto 4c: as distribuições reais são variadas
(50/50, 25/75, 33/67…) → o fix tem de **ler `KOP_fraction` do TS por torneio**, não hardcodar
por formato.

### Estruturas observadas — Mystery Bounty PokerStars (2026-05-28)

Registo read-only de uma estrutura real partilhada pelo Rui, para guiar `#MYSTERY-KO-DUAL-SUPPORT`,
`#BACKOFFICE-MYSTERY`, `#TS-RATIO-MYSTERY-CONFIRM` e `#IRE-MB`. **Nada implementado** — só dado de
referência validado aritmeticamente. Estas 4 entradas linkam para aqui.

**1. Identificação.**
- Site: **PokerStars**.
- Torneio: **Mystery Bounty Series-36**, **€50 Mega Mystery Bounty [6-Max]**, €25.000 GTD.
- Field: **690 entradas** (508 únicas + 182 re-entries). 4 re-entries permitidas durante late reg.

**2. Split do buy-in (€50)** — confirmado pelos totais do lobby:
| Componente | Por entrada | Total (×690) | Validação |
|---|---|---|---|
| **KOP** (bounty pool) | €30 | €20.700 | 690 × 30 ✓ |
| **PP** (prize pool) | €15 | €10.350 | 690 × 15 ✓ |
| **Rake** | €5 | €3.450 | — |

→ **Distribuição líquida (sem rake): 33,3% PP / 66,7% KOP.** Ou seja `KOP_fraction ≈ 0,667` do
líquido (`30 / 45`).

**3. Mecanismo (Mystery).**
- Bounties só **desbloqueiam após o fecho do late registration** ("bounties… can be won as soon as
  the late [reg closes]").
- Valor de **cada** Mystery Bounty é **aleatório/desconhecido** até ao KO (mecânica padrão Mystery).
- A coluna **"Bounty"** no lobby por jogador = **acumulado ganho por esse jogador até ao momento**,
  **NÃO** o valor na cabeça dele (confirmado pelo Rui). Implicação técnica: o valor por jogador
  **não é simétrico** (uns a 0, outros centenas/milhares de €), reflectindo o histórico de KOs.

**4. Implicações para a backlog.**
- **`#MYSTERY-KO-DUAL-SUPPORT`** — exemplo concreto de estrutura Mystery do PS com split 33/67. Dado
  real para o suporte na app (estado ITM por mão, threshold de desbloqueio por fecho de late reg).
- **`#BACKOFFICE-MYSTERY`** — a importação TS terá de lidar com este formato (**KOP > PP**, valores
  random).
- **`#TS-RATIO-MYSTERY-CONFIRM`** — o split observado (**PP ≈ 33%**) corrobora empiricamente o
  `("KO", 0.33)` do `apply_ratio_lookup` **enquanto fracção de PP**; atenção à ambiguidade
  PP-fraction (0,33) vs KOP-fraction (0,667) ao fechar o debt.
- **`#IRE-MB`** — **não** é o caso directo (Mystery ≠ Big Bounty progressive), mas reforça que o
  caminho do fix é ler `KOP_fraction` do TS por torneio, não hardcodar por formato.

**5. Nota técnica — IRE em Mystery.** A fórmula `IRE = bounty_si / (4·stack_si + 2·bounty_si)` foi
derivada para bounty **fixo e conhecido**. No Mystery o valor é aleatório/desconhecido até ao KO →
para aplicar a fórmula seria preciso usar o **EV/média do pool de bounties restantes** (que decresce
à medida que os top mystery bounties vão sendo revelados). **Tema distinto do `#IRE-MB`** — pertence
a `#MYSTERY-KO-DUAL-SUPPORT`.

### #IRE-CL — Clamp duro em off-table (sem fallback fórmula)

- **File:** `backend/app/services/ire.py:149-181` (`_nearest_idx`, `lookup_ire_pct`, `_formula_fallback`).
- **Origem:** Investigação prod 2026-05-08.
- **Vector:** A tabela W3cray é 17 linhas (stack_si 0.25–7.0) × 9 colunas (ko_units 1–5). Quando `(stack_si, ko_units)` cai fora destes limites, `_nearest_idx` faz **clamp para nearest-neighbour** (`if value <= axis[0]: return 0; if value >= axis[-1]: return len(axis)-1`). O `_formula_fallback` só é invocado quando a célula da tabela é `None` — não quando estamos genuinamente off-table. Resultado: stacks deep (>7×SI) ou bounties acumulados (>5 KO_iniciais) recebem o valor da última célula da tabela, que pode estar muito longe do correcto.
- **Severidade:** 🟡 Funcional. Valores aproximados grosseiros em casos extremos (late-stage MTT com stacks muito deep ou bounties acumulados).
- **Status:** **por iterar**.
- **Fix proposto:** detectar off-table antes do clamp (`if stack_si > rows[-1] or ko_units > cols[-1]: return _formula_fallback(...)`). Mantém clamp apenas para casos *interpolados* dentro do envelope da tabela.
- **Esforço:** ~2h (lógica + testes contra Mathematics.xlsx em ≥3 pontos off-table).

### #IRE-VB — Cobertura silenciosa zero quando Vision falha bounty_pct

- **File:** `backend/app/routers/screenshot.py` (Vision pipeline) + `backend/app/services/ire.py:282-284` (gate `any(op["ko_pct"] > 0)`).
- **Origem:** Investigação prod 2026-05-08 — 3 mãos sem badge IRE (18726, 19798, 20886) revelaram causa.
- **Vector:** Vision (GPT-4o-mini) falha por vezes em extrair `bounty_pct` da SS (% pouco legível, cortado, ou prompt não converge). Quando isso acontece, **todos** os jogadores no `players_list` ficam com `bounty_pct=0` e o mesmo se propaga para `all_players_actions`. O `compute_ire` deteca isto no GATE 9 (`not any(op["ko_pct"] > 0)`) e devolve `None` silenciosamente — UI esconde o badge sem qualquer aviso. Confirmado: 3/3 mãos afectadas têm config válida (GG PKO, `match_method='anchors_stack_elimination_v2'`, `starting_stack` válido, tag `icm-pko`); diferença é exclusivamente Vision-OCR. Nota: 20886 é mesmo torneio-tipo que 20879/20827 (Deepstack Turbo $88, SI 20k) — mesma config, resultados Vision diferentes em SSs distintas.
- **Severidade:** 🟡 Funcional. Sem corrupção de dados, mas o utilizador perde silenciosamente o IRE em mãos onde devia aparecer; sem sinal nenhum de que a Vision falhou esse campo específico.
- **Status:** **por iterar**.
- **Possíveis abordagens:**
  - **(a) Re-correr Vision com prompt melhorado** focado no campo bounty (~3h): ajustar prompt + re-processar entries afectadas + medir hit rate. Custo OpenAI moderado.
  - **(b) Parser de bounty do HH GG** (~5h): GG escreve `Total Bounty Awarded:` ou similar nas linhas de showdown. Parsear estas linhas dá ground-truth sem depender de Vision. Funciona retroactivamente sobre todas as HHs em BD, mas só apanha bounties de jogadores que efectivamente bustaram alguém na mão (não captura `bounty_pct` actual de jogadores que ainda não bustaram ninguém).
  - **(c) Aviso na UI quando bounty missing em PKO** (~1h): se mão é PKO/Mystery KO + match real + zero bounties detectados, mostrar badge cinza tipo "IRE indisponível (bounty não lido)" em vez de esconder silenciosamente. Não corrige a causa, mas torna a falha visível.
- **Esforço:** 3-5h (consoante abordagem).
- **Detectado em:** mãos id=18726, 19798, 20886 (todas GG PKO 2026, todas com SS matched, todas com `bounty_pct=0` em todos os jogadores).

### #IRE-SK — Super KO 40% (e outros ratios não-standard) escondido

- **File:** `backend/app/services/ire.py:42` (`SUPER_KO_NEEDLE`) + `ire.py:54-76` (`W3CRAY_TABLE_25PCT`) + `ire.py:228-230` (gate de filtragem por nome do torneio).
- **Origem:** Decisão de design v2 (pt16): expor IRE só para PKO standard 25%; esconder activamente Super KO 40% via deny-list. Outros ratios (Mystery KO 33%, Monster Bounties 75%) não estão na deny-list e caem em #IRE-MB.
- **Vector:** O lookup `lookup_ire_pct` consulta `W3CRAY_TABLE_25PCT` — tabela hardcoded para ratio 25%. Não há suporte para ratios diferentes; a única defesa contra falsa apresentação é a deny-list textual de nomes (`"super ko"` em `SUPER_KO_NEEDLE`). Resultado:
  - Super KO 40% → IRE escondido (gate `SUPER_KO_NEEDLE in tname`).
  - Mystery KO 33% → não-coberto (nem escondido, nem suportado correctamente — ver #IRE-MB).
  - Monster Bounties 75% → idem (#IRE-MB).
- **Severidade:** 🟡 Funcional. Não corrompe dados; só limita cobertura do produto. Rui perde análise IRE em formatos que joga (Super KO regularmente).
- **Status:** **por implementar**.
- **Solução A — tabelas W3cray paralelas por ratio (~3-4h):** uma tabela hardcoded `W3CRAY_TABLE_<ratio>PCT` para cada ratio suportado (25, 33, 40, 75). Validação de cada tabela contra Mathematics.xlsx sheet IRE para o ratio respectivo. `lookup_ire_pct` recebe `ratio` como param e selecciona a tabela. Vantagem: replica exactamente o que a Excel devolve (acceptance criterion). Desvantagem: requer Mathematics.xlsx ter sheets para todos os ratios pretendidos.
- **Solução B — fórmula matemática genérica (~2-3h):** generalizar `_formula_fallback` para aceitar qualquer ratio (`bounty_si = ko_units * ratio`) e usá-la como fonte primária quando ratio ≠ 25%. Vantagem: funciona para qualquer ratio sem tabela. Desvantagem: a fórmula é aproximação; pode divergir da W3cray real (que tem ajustes de modelo não-fórmula).
- **Híbrido recomendado:** tabela paralela para ratios comuns (25, 33, 40, 75) + fórmula fallback para ratios raros. Mantém precisão onde importa, cobertura onde for preciso.
- **Dependência:** **idealmente resolver #IRE-MB primeiro** — coluna `pko_ratio` em `tournaments_meta` permite detectar o ratio sem pattern matching frágil sobre nomes. Sem isso, a deny-list/needle-list cresce indefinidamente.
- **Esforço:** 3-4h (consoante solução A vs híbrido; ambos assumem `pko_ratio` resolvido por #IRE-MB).

---

## Estado actual (9 Maio 2026 — planeamento FASE 3)

Sessão de planeamento da FASE 3. FASE A (pipeline lobbys via Discord) em curso paralelamente — sem overlap directo. Esta entry regista a infra-estrutura nova (mini PC dedicado) que vai correr o watcher HRC 24/7 quando FASE A C3 estabilizar.

### #FASE-3-MINIPC — Mini PC dedicado para watcher HRC

- **Prioridade:** 🔴 ALTA (futura — apenas após FASE A C3 estabilizar).
- **Origem:** decisão Rui 9-Mai-2026.
- **Contexto:** Rui tem mini PC parado disponível. Decisão de o dedicar a watcher HRC 24/7, libertando o PC principal para jogar poker (sem o conflict ToS das salas a verem processos análise activos durante sessão).
- **Hardware (validado):**
  - Beelink GTR5
  - CPU: AMD Ryzen 9 5900HX (8C/16T, 3.3-4.6 GHz, Zen 3)
  - RAM: 32 GB DDR4 3200 MHz
  - Storage: 500 GB NVMe SSD
  - iGPU: AMD Radeon Vega 8
  - Network: Dual 2.5GbE + WiFi 6E
  - OS: Windows 11 Pro pré-instalado
- **Setup confirmado:** monitor + teclado + rato disponíveis (setup local). Mesma divisão do PC principal. WiFi por default; Ethernet opcional. Licença HRC já existente.
- **Limitação:** iGPU sem CUDA — **NÃO** permite OCR/Vision local (PaddleOCR-VL ou similar). Irrelevante para watcher HRC (que só consome cálculo CPU + filesystem queue), mas elimina cenário "all-in-one" (watcher + Vision local).
- **Plano (3 sub-steps):**
  1. **Setup ambiente:** HRC + Python 3.12 + watcher script (porting/adaptação do `hrc_watcher.exe` do amigo Baltazar — análise estática completa em `_local_only/ANALYSIS.md`).
  2. **Sync loop:** poll `GET /api/queue/hrc` → import zip → run analysis no HRC → POST `/api/queue/hrc/results` (endpoint a criar em FASE 4).
  3. **Operação 24/7:** auto-restart, logging estruturado, monitorização (uptime + queue depth).
- **Dependências:**
  - FASE 1 ✅ (queue endpoint deployed em prod, `da36f56`).
  - FASE A em curso (popular `tournament_payouts` via Discord lobby Vision).
  - Watcher Python script (a adaptar/escrever — base no exe do Baltazar).
  - Endpoint upload resultado `POST /api/queue/hrc/results` (FASE 4).
- **Estimativa:** 6-10h Code + algumas horas Rui setup HW.

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
- **`#TAGS-DISCORD-HM3-FRAGMENTATION`** — ✅ **FECHADO — RECLASSIFICADO (pt43).** Era marcado URGENTE. Reclassificado após auditoria empírica: (1) `normalize_tag_key` (#B17) já alinha os 6 conceitos comuns (icm, icm-pko, nota, pos-nko, pos-pko, mw-pko) no consumo (filtro `unified_tag` + tag-grouping do Estudo); (2) canais Discord novos são aceites automaticamente (accept-all-text, sem allowlist) e o nome literal vira `discord_tags`; (3) os near-misses Discord↔HM3 (`mw` vs `mw-op`, `icm-ft` vs `icm-pko-ft`) são **distinções correctas** confirmadas pelo Rui, não erros; (4) dos 22 canais reais (`discord_sync_state`), vários ainda sem tráfego (`timetell`, `icm-pko-ft`, …) alinham automaticamente quando virem mãos; (5) **única fusão real aplicada:** `nota++` → `nota` (alias `apply_hm3_tag_aliases` + backfill 273 mãos) + agrupamento visual `nota`/`nota ex` no Estudo (`tag_family_key`, grouping-only). `nota ex` preservado literal (nota exemplar p/ ML futuro). A tabela canónica (`#TAGS-CANONICAL`) foi considerada **desproporcional** — radiografia pt43 mostra que o ganho incremental sobre `normalize_tag_key` é só concept-merge + admin, não justificado para ~30 literais com 6 já unificados.
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

### #B12 — Hands GG anonimizadas com cross-post Discord não recebem `discord_tags` populado ✅ FECHADO (pt47)

- **Fechado (pt47):** `f8a8238` (2ª entry para o mesmo TM linka canal+resolve em vez de bail) + `5b7e74e` (#B23 onda 1 → `apply_villain_rules` nos call sites de `screenshot.py`) + **`42dc4e8`** (#VILLAIN-MISSED-ON-ENRICH-GUARD — o guard de idempotência do enrich passa a apensar a `discord_tag` do 2º canal **e** correr a Regra de vilões antes do `return`; self-healing nos re-imports do auto-rematch). Detalhe em `docs/JOURNAL_2026-06-02-pt47.md`.
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

## pt71 (13 Jun 2026) — desanonimização por table-SS

- 🟢 **`#TABLE-SS-DEANON-VILLAIN-NOTES-STALE` (LOW)** — quando a votação cross-mão
  corrige um nick, `reconcile_tournament_deanon` limpa os `hand_villains` da mão e
  re-aplica as regras com o nick votado, MAS os `villain_notes` (globais por nick,
  cross-mão) criados sob o nick **antigo** ficam órfãos. Impacto mínimo (o modal do
  vilão usa `hand_villains`, que é limpo); ruído nas notas. Follow-up: varrer
  `villain_notes` sem `hand_villains` correspondente. → `services/table_ss_deanon.py`.
- 🟢 **`#TABLE-SS-DEANON-SINGLETON-UNVERIFIED` (LOW)** — hashes em **1 só** mão
  table_ss do torneio (128 nas 64) não têm cross-check de votação → mantêm o
  mapeamento per-mão, que pode estar trocado se os stacks forem próximos.
  **Mitigação já activa:** a votação é contínua (cada captura nova do torneio
  acrescenta voto e retro-corrige). Não-bloqueante.
- 🟢 **`#PLAYED-AT-COARSE-GRANULARITY` (LOW, latente)** — a forense de veneno apanhou
  1 par com `played_at` a 62s mas hand-ids a distar ~894k (impossível) → o `played_at`
  de algumas mãos GG tem granularidade grosseira / artefacto. Não afecta a votação
  (usa hashes, não tempo) nem o pipeline HRC (TM number). Só relevante se um match
  temporal vier a depender de precisão sub-minuto. → `JOURNAL pt71 §C`.

