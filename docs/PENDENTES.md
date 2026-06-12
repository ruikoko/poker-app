# Pendentes — backlog vivo

## ★ Fila de arranque da pt71 (fecho pt70)

**Fechado em pt70 (não repetir):** LEI §18 deployada LIVE (`7e7a68e`, SUCCESS) + `WN-…663`
→ `SIZES_OPEN_SB=[2.5, ALLIN]` confirmado a olho; `watcher-pt70` (exe `315CC2B5…D50C`)
**instalado no Beelink + smoke dirigida PASSOU** (escada validada no rung 2 na
`GG-6041753261`, transições limpas no rung 0, zero deadlock).

Genuinamente para a pt71:
1. **1º lote real disparado no gate** (`POST /trigger?count=N`) com o exe pt70 a correr.
2. **`#HRC-NODE-OFFSET-IMPLICIT-LINES`** — modelar o ALLIN implícito (regra 25 BB confirmada).
3. **Política CI/tempo da 2ª run** (`#HRC-2ND-RUN-CI-TIME-DISCREPANCY`).
4. **Mistério do chord SWT** (observação) — porque é que o chord `Ctrl+W,M` falha pós-fecho
   de aba mas nunca em cold start (o pt70 contorna com a escada; a causa-raiz fica por
   caracterizar — binding contextual SWT?).
5. **`#SECOND-RUN-NOOP-SILENT-DONE`** — 2ª run que degrada para no-op sem sinalizar.
6. **Max=2 da WN por auditar.**
7. **Etapa 2 do re-teste** (sessões dos dias 5 + 8 + 9).
8. **★ Futura encomenda — "Mestre único" de import (sem código nesta fase):** um
   duplo-clique = HM3 + appimport ao-vivo (com confirmação) + Discord sync + rematch +
   abrir a Saúde do Import. O **Intuitive Tables passa a gravar direto em `Batmen\it`** por
   definição própria (config da app, sem código). Ver `REGISTO_CONCEITO` (linha pt70).

Backlog: 413 definitivo (interino 200 MB), `#MYSTERY-KO-DUAL-SUPPORT`.

---

**Última actualização:** 11 Junho 2026 (**pt68 FECHADO**). Wipe total + Etapa 1 (sessão dia 4, 6 canos validados, ~5044 mãos, 123/127 órfãos); 502 do `/api/import` = timeout síncrono com import COMPLETO (4710 mãos 4-9 Jun verificadas); incidente do watcher (degradação progressiva por acumulação de abas, confirmada na fonte; 3 done VERDES na mini-auditoria); **★ Saúde do Import v1** (`/import-health`); **★ Gate da fila v1** (fila fechada + disparo manual/lote); **★ exe watcher pt68** (3 fixes: fechar aba Ctrl+F4+Don't Save, reiniciar/5+health-check, log-em-ficheiro) — **Release publicada+validada, instalação no Beelink PENDENTE**; **★ multi-select "Enviar ao HRC" backend LIVE** (frontend = 1º da próxima). Journal: `docs/JOURNAL_2026-06-11-pt68.md`. Antes: pt67 (pipeline certificado).
**Propósito:** lista priorizada do que atacar a seguir. Distinta do
`TECH_DEBTS_INVENTARIO.md` (que é o registo histórico exaustivo, com
estado de cada debt) — aqui é só a **fila de trabalho**, ordenada.

> Manutenção: quando um item for feito, mover para o journal/tech debts e
> remover daqui. Quando aparecer um item novo, colocar na categoria certa.

---

## ★ Fila de arranque da pt69 (ordem do Rui no fecho pt68)

1. **Frontend do multi-select "Enviar ao HRC"** (1º item) — backend **LIVE** à espera
   (`POST /api/queue/hrc/release` + `/states`). Estudo (`Hands.jsx` 2001 linhas + `HandRow`):
   checkboxes + "selecionar todas do torneio/grupo" + barra "Enviar N" + badges de estado +
   checkbox desabilitado nas não-exportáveis (com motivo).
2. **Instalar o exe pt68 no Beelink** (`irm` do `instala_pt68.bat`, Release `watcher-pt68`,
   SHA `222fc48d…3f57`) + **smoke do reinício-a-cada-5 e do fecho de abas** (Ctrl+F4 +
   Don't Save) + confirmar o log em `C:\hrc\watcher_logs\`.
3. **Etapa 2** = importar **dias 5 + 8 + 9** (re-teste com volume, à luz da Etapa 1).
4. **Fix `#HRC-NODE-OFFSET-IMPLICIT-LINES`** (gate da fila grande; regra 25 BB confirmada).
5. **Política CI/tempo da 2ª run** (`#HRC-2ND-RUN-CI-TIME-DISCREPANCY`) — **decisão de
   produto** do Rui (reiniciar a cada N? alvo de CI? tempo-limite?).
6. **4 órfãos Discord** (dias 5/8/9) sem match — investigar.
7. **2 lobbys com Vision de site trocado** — corrigir.
8. **Limpeza física do Beelink** (`C:\hrc\queue_hold\`, `stale_done`, Desktop riand) — as
   linhas dry-run + apagar já foram desenhadas no chat; correr quando o Rui puder.
9. **Mão do derail** (a seguir à `GG-6041861838`) — **forense opcional** (precisa do
   `state.json`/ordem de pick do Beelink).
10. **Gate por botão** (`#QUEUE-NO-SERVER-SIDE-GATE`) — ✅ **ENTREGUE pt68** (riscado).

---

## Alta prioridade (atacar a seguir)

> **★ FEATURE FUTURA (registar; desenho quando chegar a vez) — AVALIAÇÃO AUTOMÁTICA
> HERÓI vs HRC.** Ao receber o zip de estratégias, avaliar a decisão do herói: localizar
> na árvore o(s) nó(s) da linha real, ler a estratégia do solver para o **combo exacto**
> do herói (freq + EVs por ação) e comparar com a ação tomada → **veredicto** (em linha /
> mix / desvio) + **custo em EV** (ação tomada vs melhor). Output no Estudo + badge/filtro
> **"mãos onde desviei"**. **Questões para o desenho:** (1) mapear a acção real aos sizings
> da árvore (ex.: raise 2.2bb real vs linha 2.0 do solver); (2) herói com **múltiplos nós**
> de decisão na linha; (3) **onde guardar** o veredicto (coluna na mão? tabela própria?);
> (4) badge/filtro no Estudo. Constrói sobre a infra do **GTO Brain** (matching + navegação
> a nó). Reusa o zip que já entra em `hrc_jobs`/`hrc_sessions`.
>
> **★ ✅ ENTREGUE (pt68, `c10e303`) — GATE SERVER-SIDE DA FILA HRC COM DISPARO MANUAL**
> (`#QUEUE-NO-SERVER-SIDE-GATE`). Construído: tabela `hrc_queue_release` + filtro no GET +
> `POST /trigger?count=N` + `GET /gate` + página HRC Queue. ~~Desenho:~~ feito.
> A fila nasce FECHADA no servidor
> (`GET /api/queue/hrc` devolve vazio); só serve mãos após o Rui carregar em **"Disparar"**
> na página HRC Queue. **Modelo proposto:** tabela `hrc_queue_release` + filtro no GET (só
> mãos libertadas e não-done) + `POST /api/queue/hrc/trigger?count=N` + `GET …/gate` (estado:
> fechada/aberta/N em curso). **Auto-fecho** quando o lote é consumido. **Disparo:** "tudo"
> (v1) ou "lote de N" (v2). **Per-mão `…/hand/{id}` NÃO gated** (pedido explícito do Rui).
> **Zero alterações no adapter/Beelink** (o adapter já idle em vazio). **Esforço:** v1 ~1 dia
> (tabela+filtro+trigger+gate+botão "Disparar tudo"); v2 lote-de-N + histórico. Entra em
> vigor quando construído; a corrida de 11 Jun à noite mantém-se. Detalhe: `REGISTO_CONCEITO`.
>
> **★ pt67 IMPLEMENTADO (em buffer + Release `watcher-pt67`); falta a RE-SMOKE real
> (gate da fila).** 3 fixes em código (**916 PASSED** + 102 watcher + in-process smoke
> ALL OK; diffs validados pelo Web): **#HRC-MAX-PLAYERS-SPAN-NOT-PARTICIPANTS** (backend
> — span âncora→BB, **teto 6** [LEI `REGRAS_NEGOCIO §15`]; GG-6029013400 agora 5),
> **#HRC-RUN-WINDOW-DETECTION-BLIND** (watcher — vigia desde o Finish por hwnd, sem sleep
> cego), **#HRC-CI-SAFEGUARD-CHILD-CONTROLS** (watcher — "Target CI" nos child controls).
> + In-hand `\S+`→`.+?`. `.exe` **`a9554427`**.
>
> **Re-smoke pt67 = as MESMAS 2 mãos.** **DELETE dos 2 hrc_jobs (job 6,7) FEITO** → ambas
> voltaram a elegíveis (recalc da quarentena dessas 2). Beelink: instala_pt67 →
> `requeue_pt67.bat` (asset da Release, self-fetch do `requeue_state.py`) → adapter →
> watcher → packs novos (Max=5). **Critérios:** GG-6029013400 com **Max=5** + 1ª run
> DETECTADA (sem WARN "NUNCA vista"); GG-6039094225 regressão.
>
> **⚠️ FILA (~49) TRAVADA** até a re-smoke pt67 passar; depois lote(s) ao ritmo do Rui.
> **Quarentenas restantes:** `GG-6028190109` + `GG-6027751209` (recalc no 1º lote).
> Detalhe: `JOURNAL_2026-06-10-pt67.md` + `TECH_DEBTS_INVENTARIO.md` (pt67).

> **★ Quarentena de 2 resultados HRC (recalcular pós-pt66).** `GG-6028190109`
> (smoke pt64, corridas sobrepostas) e `GG-6027751209` (STALE, postado no arranque
> do adapter a 9 Jun). **Invalidar = re-POSTar pós-pt66** (o `upsert_hrc_job_result`
> sobrescreve por `hand_db_id`); não é preciso mexer na BD. Não estão visíveis em
> nenhuma UI hoje (`hrc_jobs` ≠ `/hrc-sessions`). Suspeito a investigar:
> `players_left = 3179` numa mesa GG (escala ICM). Detalhe: `TECH_DEBTS_INVENTARIO.md`
> (pt62–pt64).

> **★ pt58 — RE-IMPORT de scope ABRIL é o PRÓXIMO GRANDE PASSO operacional.**
> O re-import end-to-end **já foi feito** (pt50, Fases 1+2) mas só com a **janela
> de 3 dias** das HH (HH3dias.zip + TS3dias.zip). Falta o **scope de Abril**:
> 1. Importar as HH GG de Abril para **fechar os placeholders Discord/lobby de
>    Abril** (a Fase 3 confirmou que os replayer de Abril ficam placeholders por
>    não terem mão importada — esperado, mas resolúvel) e os `no_match` do
>    table-SS que caem **fora da janela 30/Mai+** (28 rows = gaps reais de import,
>    não bug de site/nome).
> 2. **Convenção de fuso já é Lisboa-naive** (pt51) — GG/PS gravam verbatim, sem
>    matemática DST. **A "validação de Inverno" da rota UTC dissolveu-se** (já não
>    convertemos GG/PS). Nada a validar do lado do fuso no re-import de Abril.
> 3. **Reavaliar o table-SS** com Abril importado: `#TABLE-SS-VISION-SITE-MISCLASS`
>    ✅ (pt49), site agora **determinístico pelo filename** (pt56). Suspeitos reais
>    que sobram: **WPN/PS time-only** (`#WPN-PS-TABLE-SS-TIME-ONLY-MATCH`),
>    **multi-tabling GG** (`#TABLE-SS-GG-MULTITABLING-MATCH` MED).

> **CoinPoker — adiado (o Rui joga, adição diferida).** Quando se fizer = **pacote
> completo**: `_FILENAME_SITE_MAP` (token do filename), nicks de hero, fonte de
> import das mãos, e pool de matching. Hoje cai no fallback + log (`_site_from_filename`
> devolve `None` para o token `CoinPoker`).

> **Sessão 2026-06-02 — planeado, NÃO aplicado (ver `docs/PLAN_2026-06-02-table-ss-gg-match.md`):**
> Match SS de mesa ↔ mão GG em multi-tabling. Investigação read-only completa.
> Achados: GG falha sobretudo por **import em falta** (68/99 SS sem mão na janela) + ~9 que o
> matcher devia apanhar (usa o resolver de nomes frágil em vez de nome-directo+fingerprint);
> nomes GG **fiéis** (prefixos de série a manter), `#NNN` é só da Winamax (já aparado, garantido
> preservado); TZ OK; 2 SS Winamax mal classificados como GG pelo Vision.
> **Próxima sessão (por ordem):** 1) fix `_resolve_match` (nome-directo por-site + impressão
> digital stack/blinds; GG sem limpeza; chokepoint que serve upload+relink) + testes; 2) importar
> as HH GG em falta (depois do fix, p/ o relink ligar); 3) abrir `#TABLE-SS-VISION-SITE-MISCLASS`.
> Constantes fixadas: `_FINGERPRINT_STACK_TOL=0.20`, blinds exacto, NÃO usar hero_position.
> **⚠️ Actualização pt49:** `#TABLE-SS-VISION-SITE-MISCLASS` já **FEITO** (`ef82a0d`/`41d83d3`);
> e o "TZ OK" acima estava **errado** — o GG tinha o bug de fuso `#GG-PLAYED-AT-LOCAL-NOT-UTC`
> (✅ pt49) a falsear a janela ±5min. Re-medir tudo **pós-reimport** (ver bloco ★ pt49 no topo).

> **Foco pt42e (por ordem):**
> 1. **Smoke real Beelink pt42d** (CRITICAL pré-commit). Sequência:
>    - Rui corre backend DEV LOCAL (`uvicorn` em `:8000`).
>    - Descarrega zip WN PKO pós-pt42d local.
>    - Valida `payouts.json` no zip: APENAS `{name, folders, structures}`;
>      `structures[0].name == "<Name>  #<tn>"`; `bountyType="PKO"`;
>      `progressiveFactor=0.5`.
>    - Copia para o Beelink: `.exe` novo (SHA cdfc7247...3262) +
>      `payouts_helpers.py`.
>    - Importa no HRC → confirma Instant=50% (não ICM puro).
>    - Corre robot Beelink (1ª + 2ª run) com hints em meta.json.
> 2. **Commit + push pt42d** (após smoke OK).
> 3. **`#LOBBY-SYNC-PAGINATION-LIMIT` (🟡 MED)** — paginação Discord.
> 4. **`#MYSTERY-KO-DUAL-SUPPORT` (🟡 MED)** — pré/pós-ITM.
> 5. **`#SMOKE-HARNESS-WAIT-FOR-FINISH-MOCK-MISSING` (🟢 LOW, novo pt42d)**.
> 6. **`#OPEN-COUNT-DRIFT-HRC-NODE-OFFSET-LATENT` (🟢 LOW)**.
> 7. **`#POSITION-LABELS-PYTHON-JS-DRIFT` (🟢 LOW, pt42b)**.
> 8. **`#META-START-TIME-IS-FIRST-HAND-NOT-SCHEDULED-START` (🟡 MED)**.
>
> ✅ **Guarda mantida:** `DISCORD_LOBBY_AUTO=true`.
> **Fechados pt42d:** `#WN-BOUNTY-NULL-IN-HRC-PIPELINE` v2 ✅ (pt42c v1
> revertido em T2; pipeline v2 final com payouts HRC-native + meta hints).
> Suite 730→734 PASSED. .exe recompilado.
> **Pendente:** smoke real Beelink + commit/push.
> **Fechados pt42c:** `#WN-BOUNTY-NULL-IN-HRC-PIPELINE` v1 (parcial — Seat
> lines conversion subsequentemente revertida em pt42d).
> **Fechados pt42b:** `#HRC-BETTING-SCRIPT-IMPROVEMENTS` ✅ (3-bet IP por
> posição).
> **Fechados pt42:** `#HRC-BETTING-SCRIPT-IMPROVEMENTS` ✅ (1ª parte).
> **Fechados pt41:** `#HERO-BOUNTY-FROM-TS-DERIVATION` ✅ (`a942ac7`);
> `#LOBBY-ANCHOR-PRESTART-REGRESSION` ✅ + `#RESOLVER-TIER12-WINDOW-NO-START` ✅ (`6409b19`).
> **Fechados antes:** `#HRC-PER-HAND-DOWNLOAD` ✅ (`dfc13a5`, pt40);
> `#RESOLVER-TIER0-STRICT-EQUALITY` ✅ + `#TABLE-SS-RESOLVER-COLLISION` ✅ (pt39).

1. **`#PIPELINE-ROBUSTNESS-SMOKE-BATTERY` — porta de entrada da Fase 2 do
   GTO Brain.** Validar o pipeline ponta-a-ponta nas **4 combinações site ×
   formato**: (1) GG NKO Vanilla, (2) PokerStars PKO, (3) Winamax PKO,
   (4) PokerStars NKO Vanilla. Cada smoke = mão marcada na app → adapter
   pull → watcher → adapter push → `.zip` em `hrc_jobs` com dezenas de MB /
   milhares de nós. Ponto de partida validado: pt35 GG PKO 50%
   (`GG-5944816316`, Complete Export 44 MB). Só depois das 4 baterem se
   arranca a Fase 2 (auto-import `.zip` → `gto_trees`/`gto_nodes`). Ver
   `docs/GTO_BRAIN.md §7` e `docs/TECH_DEBTS_INVENTARIO.md`.

   > **SUPERSEDED (pt35):** o antigo item "validar o `.zip` pt34 v1
   > (~23 000 nós) vs Save As manual" foi tornado obsoleto pelo smoke real
   > pt35. O mecanismo de export mudou de Selected-Subtree/Save-As para
   > **Complete Export** (44 MB, ciclo funcional ponta-a-ponta), pelo que a
   > comparação célula-a-célula contra o Save As manual deixou de fazer
   > sentido.
   >
   > **pt36 — blocker removido:** `#HRC-RUN-2-ALWAYS-DISPATCH` ✅ resolvido
   > (backend). Toda mão que entra no zip tem agora `aggressor_real_action`
   > não-None → o gate da 2ª run no watcher passa sempre. A smoke battery
   > deixa de ter o risco de mãos exportadas com 1 run só; mãos limp/walk
   > passam a refinar a raiz da Strategy Table na 2ª run. (Detalhe +
   > `#PARSER-SEATS-FAILURES` em `docs/TECH_DEBTS_INVENTARIO.md` pt36.)

2. **`#HRC-BOUNTY-HARDCODED-50PCT` — RESOLVIDO em pt66 (em buffer; pendente
   build + re-smoke).** O robot metia sempre `Bounty Mode PKO 50%` (via
   `select_bounty_mode` legacy, que corria **depois** do import da estrutura e a
   **esmagava**, só em KO). **Fix pt66:** remover `select_bounty_mode` + o gate
   `is_ko_tournament` → é o **HRC** que põe o modo a partir da estrutura
   importada (`payouts.json`); **não** se constrói mapa→dropdown.
   **⚠️ Correcção factual (3ª vez — a cópia stale aqui voltou a infetar):
   NÃO existe `progressiveFactor=0.25` no pipeline HRC.** Os factores vêm do
   **`LOBBY_RATIO_LOOKUP`** (`backend/app/services/lobby_vision.py`, por nome do
   torneio) — **fonte única**: `0.75` monster, `0.50` bounty
   hunters/builder/knockout/[bounty], `0.40` super ko, `0.33` mystery (`KO`),
   `0.0` resto. (Os `0.25`/`0.33` doutras notas são constantes do `ire.py` —
   coisa **diferente**.) Já corrigido no TECH_DEBTS em `135be97` (22 Mai); esta
   era a cópia stale que sobreviveu. Ver `TECH_DEBTS_INVENTARIO.md` (pt66).

3. **`#HRC-REDUNDANT-SECOND-RUN-OLD-CONFIGS` ✅ RESOLVIDO em pt66** (código +
   exe `9ea51ce4` na Release `watcher-pt66`; pendente re-smoke real). Removido o
   `start_calculation` do `setup_hand` → a 1ª run é lançada pelo Finish e vai-se
   direto a navigate → Selected Subtree (exatamente 2 runs, sem prune). Ver o
   bloco ★ pt66 acima + `TECH_DEBTS_INVENTARIO.md` (pt66).

4. **Uniformização de tags Discord ↔ HM3.** Urgente — fragmentação visual
   no Estudo (o mesmo conceito aparece com nomes diferentes consoante a
   fonte). 3 opções já levantadas: renomear canais, dict de aliases
   hardcoded, ou UI admin central de tags. Decisão de produto pendente.

7. **`#META-START-TIME-IS-FIRST-HAND-NOT-SCHEDULED-START` (🔴 HIGH, aberto pt37
   como `#START-TIME-TIMEZONE-INCONSISTENCY`, re-rotulado pt39).** **NÃO é bug de
   TZ** (re-diagnose pt39, read-only). `tournament_summaries.start_time` =
   arranque agendado; `tournaments_meta.start_time` = `MIN(played_at)` = 1ª mão
   importada (horas adiantada quando há late-reg / import parcial). O diff é 0
   quando a 1ª hand é Level1 e cresce com níveis tardios — semântica, não
   relógio. **Já não bloqueia os outros** (não há TZ a corrigir); mas continua a
   contaminar qualquer janela ancorada em `meta.start_time`. Ver
   `TECH_DEBTS_INVENTARIO.md` (secção pt39).

9. **`#HRC-MTT-STACKS-PAGE-SKIPPED-ON-NULL-PLAYERS-LEFT` (🔴 HIGH, aberto pt38; pipeline construído pt38).**
   **Endereçado** pelo **pipeline SS de mesa** construído em pt38 (Fases A+B +
   trigger re-link + fix mapeamento Vision): captura via Intuitive Tables →
   Vision lê `players_left` **por mão** → `_resolve_players_left` usa-o
   (prioridade granular, antes do fallback lobby). **Residual a fechar:**
   - **Fase C** (cliente automático `.bat-like`) **pendente** → até lá o upload
     é **manual** em `/table-ss`.
   - **Captura:** a SS tem de incluir o painel "Rank:"
     (`#TABLE-SS-VISION-CAPTURE-GAP`), senão `players_left` vem null —
     Rui configurar o Intuitive Tables.
   - **Fiabilidade do linking depende do resolver**
     (`#TABLE-SS-PIPELINE-DEPENDENCIES`, `#TABLE-SS-RESOLVER-COLLISION`):
     multi-tabling não é 100% fiável enquanto o resolver não estabilizar (TIER0
     ✅ pt39, TIER12 ✅ pt41; resta `#META-START-TIME-IS-FIRST-HAND-NOT-SCHEDULED-START`,
     item 7). Ver `docs/JOURNAL_2026-05-24-pt38.md` e `TECH_DEBTS_INVENTARIO.md` (pt38).

---

## GTO Brain — roadmap (depois da smoke battery)

Plano completo em `docs/GTO_BRAIN.md §7`. Resumo da fila:

- **Fase 1 — ✅ fechada (pt35).** Watcher exporta Complete Export; ciclo
  `app → adapter → watcher → adapter → app` validado (`GG-5944816316`, 44 MB).
- **Fase 2 — auto-import `.zip` → `gto_trees`/`gto_nodes`.** Estender
  `POST /api/queue/hrc/results` para, depois de gravar em `hrc_jobs`, chamar
  `parse_hrc_zip()` + insert em `gto_trees`/`gto_nodes`, derivando metadados
  automaticamente (format, num_players, hero_position, stack, phase) — sem
  form manual. **Gated por `#PIPELINE-ROBUSTNESS-SMOKE-BATTERY`** (ver Alta
  prioridade). Tech debts: `#GTO-IMPORT-AUTOMATICO-AUSENTE` (HIGH),
  `#GTO-METADADOS-DERIVACAO-AUSENTE` (LOW).
- **Fase 3 — UI rica + tab FIELD.** Navegação interactiva multi-spot (não só
  o nó do Hero), grelha 13×13 com pesos/EVs, e construção do lado FIELD
  (schema `field_stats_preflop` + worker de agregação + `/api/field/match` +
  tab FIELD no replayer). Tech debts: `#GTO-NAVIGATE-SO-HERO-NODE` (MED),
  `#FIELD-PIPELINE-AUSENTE` (MED), `#GTO-RANGE-VISUAL-VALIDACAO` (LOW).

---

## Médio prazo

10. **`#CI-TARGET-INITIAL-NOT-CALIBRATED` ✅ DISSOLVIDO em pt66.** Já não há set
   do CI no main UI: o watcher deixou de escrever o CI (default do popup = 10.0);
   `set_ci_target_initial/refine` + `_set_ci_target_common` + `CI_TARGET_FIELD_*`
   removidos. Salvaguarda só-leitura `_ci_target_readback_warn`. Ver bloco ★ pt66.

11. **`#WIZARD-FINISH-FALSE-POSITIVE-STATE-CHECK`.** `verify_wizard_finished`
   (state check WARN-only pós-Finish, pt29-v1) verifica **cedo demais** — o
   wizard ainda está visível no instante da verificação, gera WARN espúrio,
   mas a 1ª run efectivamente arranca. Adicionar um pequeno settle/poll
   antes de verificar, ou retirar o WARN. Não-bloqueante.

12. **`#CURSOR-ANOMALY-POST-SAVE-AS`.** Após o Save As, o cursor da Strategy
   Table cai na 2ª linha (EP). **Refinado pt64: é DETERMINÍSTICO** — o Rui
   confirma "sempre o 2º nó" na fase de guardar estratégias (já não é anomalia
   de origem desconhecida; há padrão reproduzível). Não bloqueia o flow, mas
   investigar (pode afectar uma futura 3ª run ou navegação encadeada).

13. **`#PARSER-SEATS-FAILURES` (🟡 MED, aberto pt36).** `build_queue_zip`
   passou a skipar mãos cujo `derive_seats_in_preflop_order` devolve `[]`
   (sem button / <2 seats) com `reason="no_seats_at_table"`. Desde
   `#HRC-RUN-2-ALWAYS-DISPATCH`, uma falha do parser de seats custa a **mão
   inteira** à biblioteca (antes só a 2ª run). Robustecer
   `derive_seats_in_preflop_order` contra edge cases cross-site (PS/GG/WN/WPN;
   ex.: nicks com espaços, `#DERIVE-MAX-PLAYERS-HERO-REGEX-GG`). Detalhe em
   `docs/TECH_DEBTS_INVENTARIO.md` (secção pt36).

14. **`#LOBBYS-RETRIGGER-NOT-DISCOVERABLE` (🟡 MED UX, aberto pt37).** O botão
   "Sincronizar Lobbys" + Avançado/`tm_not_found` vive só na página Discord,
   fácil de não notar; não há aviso em Dashboard/Torneios quando há candidatos
   `tm_not_found` pendentes. O utilizador importa TS+HH e não sabe que precisa
   de re-disparar os lobbys para fechar o ciclo. Fix: badge/link na
   Dashboard/Torneios, ou auto-retrigger pós-import. Ver
   `TECH_DEBTS_INVENTARIO.md` (pt37).

14b. **`#WPN-PS-TABLE-SS-TIME-ONLY-MATCH` (🟡 MED, aberto pt50).** WPN/PS não estão
   em `_NAME_RELIABLE_SITES` → o table-SS casa-os **só por tempo** (nomes WPN =
   garantia, PS = NULL, não validáveis). Superfície de falso-match em multi-tabling
   WPN/PS na janela. Mitigado pelo site determinístico (filename, pt56). Reavaliar
   se aparecerem falsos matches reais. Ver `TECH_DEBTS_INVENTARIO.md` (pt50–pt58).

15. **`#BUBBLE-FACTOR-PER-PLAYER` (FEATURE FUTURA — estudo de viabilidade feito,
   NÃO implementar sem OK).** Mostrar um **bubble factor por jogador, ajustado a
   bounty**, ao lado de cada jogador na vista da mão.
   - **Âmbito:** **só as mãos que vão ao HRC**, onde o `players_left` **já é exacto**
     via o mecanismo que alimenta o watcher (`_resolve_players_left` / a SS de
     `players_left` associada à mão). **NÃO estimar `players_left`** — usar o exacto
     dessas SS. *(Corrige a conclusão do estudo: o "furo de players_left" NÃO se
     aplica a estas mãos — só apareceria se quiséssemos BF em qualquer mão.)*
   - **Motor:** **próprio**, ICM **Malmuth-Harville** (mesa ≤9 exacta + resto do
     campo colapsado em stacks médios; ~ms/mão, on-demand). O **HRC NÃO serve como
     fonte primária** — só dá BF **pós-processamento** e cobre ~0 mãos (`hrc_jobs`
     vazio); fica como **cruzamento v2**: parsear `bubbleFactors` (matriz NxN) +
     `preHandEquity` do `equity.json` do HRC quando a mão já passou pelo robot
     (formato confirmado em `services/hrc_import.py`; hoje só se extrai o `meta.json`).
   - **Bounty (PKO):** reutilizar a matemática do **`ire.py`** (`ko_units`,
     `constant = KOP_fraction × instant_fraction`, coroas `bounty_value_usd`) para o
     **termo de bounty**; combina (multiplicativo no risk premium) com o termo
     **ICM-regular** do motor próprio. Já temos metade (o lado bounty).
   - **Dados já presentes por mão:** stacks (apa), coroas (`bounty_value_usd`),
     escada de prémios completa (`tournament_payouts.payouts_json.structures[0].prizes`,
     ex.: 912 ranks), field size (`tournament_summaries.total_players`), split
     `buy_in_entry`/`buy_in_bounty`, `starting_stack`. (Não falta nada para as mãos
     do âmbito.)
   - **Esforço (do estudo):** motor ICM **~2-3 dias** + termo bounty **+1-2** +
     híbrido HRC (parse `equity.json` no ingest do robot) **+1-2**.

16. **`#CONTEXT-IMAGE-MKO-BOUNTY-AVG` (FEATURE FUTURA — NÃO implementar sem OK).**
   Aproveitar **imagens de contexto não-reconhecidas** (lobbys + Intuitive Tables)
   que hoje caem em `no_match_to_hand`/`vision_failed`/ignoradas e **perdem-se** —
   tratar as que são contexto útil.
   - **Caso-bandeira: Mystery KO.** Foto dos **KOs restantes** numa mão → obter o
     **valor MÉDIO do bounty restante** → alimentar o **HRC em KO mode** para essa
     mão (o MKO é não-progressivo, `instant_fraction=1.0`; a média é o input que
     falta para modelar o bounty).
   - **Extracção POR SALA** (a média pode ou não vir já calculada — mesmo padrão
     por-sala que o `ire.py` tem para GG vs Winamax):
     - **PokerStars, Winamax:** já mostram a média → Vision lê o número directo.
     - **WPN, GG:** NÃO calculam → Vision extrai o **breakdown** dos bounties
       restantes (nº × valor por tier) e calcula a média (total restante ÷ nº de
       bounties).
   - **Modelo:** irmão do **table-SS** (`context → players_left`); aqui
     `context → média bounty MKO → HRC KO mode`. **Mesma família HRC** do bubble
     factor (`#BUBBLE-FACTOR-PER-PLAYER`) e do IRE.
   - **A confirmar ao implementar:** como a imagem se prende à mão (timestamp, à la
     table-SS); **nova categoria de imagem** na pipeline (hoje só lobby / table-SS /
     manual / replayer); **formato do breakdown** em WPN/GG. Nota: as imagens do
     table-SS não são guardadas (`#TABLE-SS-IMAGE-NOT-STORED`) — se este fluxo
     precisar de re-Vision retroactiva, ter isso em conta.

---

## Baixo prazo / qualidade

15b. **`#TABLE-SS-IMAGE-NOT-STORED` (🟢 LOW, aberto pt56).** Imagens do table-SS
   descartadas após a Vision (`table_ss_processing_log` sem coluna de imagem) →
   sem re-Vision sem re-fornecer o ficheiro. Bloqueou o V2 multi-site. Trade-off
   aceite (poupa storage); registar antes de qualquer plano que dependa de
   re-Vision retroactiva.


15. **Vision parser improvements** — tolerância ao prefixo TM, heurística do
   BB stack, prompt GTO mais forte.
17. **Filtros derivados no Estudo.**
18. **Dashboard — colunas adicionais.**
19. **Winamax replayer — URL da Vision.**
20. **`_upload_screenshot_to_storage`** — limpeza do stub.
21. **Discord entry status** — cosmético.
22. **Discord page — dual time filters.**
23. **Teste de regressão `/ss-without-match`** (pt48) — não há teste pytest para o
   endpoint; o dedupe por TM só está verificado por simulação ad-hoc. Adicionar: 2
   uploads manuais **sem TM** por casar → **ambos** aparecem (não colapsam por
   `NULL=NULL`); N replayers do **mesmo** TM → **1** linha. Cobre o `COALESCE(tm,
   'e'||entry_id)` do `56025af`.

---

## Cross-references

- `docs/TECH_DEBTS_INVENTARIO.md` — estado detalhado de cada `#TECH-DEBT`.
- `docs/GTO_BRAIN.md` — visão e roadmap do GTO Brain (3 fases).
- `docs/JOURNAL_2026-05-22-pt35.md` — sessão que fechou a Fase 1 do GTO Brain.
- `docs/JOURNAL_2026-05-22-pt30-pt34.md` — contexto da sessão que fechou a
  cadeia da 2ª run.
