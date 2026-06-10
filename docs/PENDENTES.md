# Pendentes — backlog vivo

**Última actualização:** 10 Junho 2026 (pt64 — ★ **smoke real Beelink PASSOU**, ciclo HRC ponta-a-ponta fechado [`GG-6028190109`]; housekeeping de docs + quarentenas). Antes: pt62/pt63 (lobby-IT por nome/filename); pt50–pt58 (RE-IMPORT end-to-end + fuso Lisboa-naive + Vision Claude-only + `tools/appimport`). Journal: `docs/JOURNAL_2026-06-10-pt64.md`.
**Propósito:** lista priorizada do que atacar a seguir. Distinta do
`TECH_DEBTS_INVENTARIO.md` (que é o registo histórico exaustivo, com
estado de cada debt) — aqui é só a **fila de trabalho**, ordenada.

> Manutenção: quando um item for feito, mover para o journal/tech debts e
> remover daqui. Quando aparecer um item novo, colocar na categoria certa.

---

## Alta prioridade (atacar a seguir)

> **★ pt66 — sessão dedicada do watcher (GATE da fila completa).** A smoke pt64
> PASSOU o ciclo HRC ponta-a-ponta (`GG-6028190109`), mas expôs ao vivo que o
> watcher ainda faz **3 runs** (a intermédia Full-Tree redundante dispara
> **enquanto a 1ª run corre** — o HRC enfileira-as). Numa só sessão (mesmo
> ficheiro, mesmo build): (a) remover a run intermédia redundante — ir DIRETO de
> fim-da-1ª-run para navigate + Selected Subtree + CI (o `meta.json` já tem
> `target_node_offset` + `aggressor_real_action`; spec `docs/WATCHER_FLUXO.md`);
> (b) endurecer o run-wait contra o **falso-trivial** (`#HRC-RUN-WAIT-FALSE-TRIVIAL`);
> (c) **CI via lista/read-back** (SysListView32, como o scope pt64) + limpar `CB_*`
> morto; (d) `.exe` novo + **GitHub Release** (regra 4 do FLUXO) + re-smoke.
> **⚠️ A fila completa (~49 mãos em `queue_hold`) SÓ se solta após a re-smoke pt66
> passar** — decisão do Rui pendente, mas o gate fica registado. Debts:
> `#HRC-REDUNDANT-SECOND-RUN-OLD-CONFIGS` (🔴 HIGH), `#HRC-RUN-WAIT-FALSE-TRIVIAL`,
> `#CI-TARGET-INITIAL-NOT-CALIBRATED`. Detalhe: `TECH_DEBTS_INVENTARIO.md` (pt62–pt64).

> **★ Quarentena de 2 resultados HRC (recalcular pós-pt66).** `GG-6028190109`
> (smoke pt64, corridas sobrepostas) e `GG-6027751209` (STALE, postado no arranque
> do adapter a 9 Jun). **Invalidar = re-POSTar pós-pt66** (o `upsert_hrc_job_result`
> sobrescreve por `hand_db_id`); não é preciso mexer na BD. Não estão visíveis em
> nenhuma UI hoje (`hrc_jobs` ≠ `/hrc-sessions`). Suspeito a investigar:
> `players_left = 3179` numa mesa GG (escala ICM). Detalhe: `TECH_DEBTS_INVENTARIO.md`
> (pt62–pt64).

> **★ Bounty Mode — VERIFICADO pt65 (decompile): confirma-se como bug; pt66 GANHA o
> bounty-fix.** Veredicto: `import_prizes` **só carrega** a `payouts.json`; é o HRC que
> põe o modo no sítio ao ler a estrutura (o que o Rui observou). Mas `select_bounty_mode`
> corre **a seguir** e, **só em KO** (gate `is_ko_tournament`), **esmaga** o modo da
> estrutura para um **PKO 50% cego**. Não-KO ✅; PKO 50% redundante; **PKO 25% / KO ≠50%
> = errado**. **Fix (no mesmo `.exe`/rebuild do pt66):** remover a chamada
> `select_bounty_mode` + o gate (o modo da estrutura prevalece em todos os formatos);
> validar 1 caso KO ≠50% na re-smoke (+ KO-T$/KO-P$ ≠0 numa PKO real). Detalhe em
> `TECH_DEBTS_INVENTARIO.md` (pt62–pt64, `#HRC-BOUNTY-HARDCODED-50PCT`).

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

2. **`#HRC-BOUNTY-HARDCODED-50PCT`.** O robot mete sempre `Bounty Mode PKO
   50%` (via `select_bounty_mode` legacy). Fazer ler o `progressiveFactor`
   do `payouts.json` (já é data-driven: 0.5/0.33/0.25/0.0) ou o
   `tournament_format`, e seleccionar a opção correspondente no dropdown
   do HRC. Suporta PKO 25% e Mystery KO correctamente. Ver
   `TECH_DEBTS_INVENTARIO.md` e `WORKFLOW_OPERACIONAL.md` §4.2.

3. **`#HRC-REDUNDANT-SECOND-RUN-OLD-CONFIGS` (🔴 HIGH, registado pt61).** A 2ª
   fase do watcher **diverge** do spec `docs/WATCHER_FLUXO.md`: a seguir à 1ª run
   faz um **Prune (errado)** + uma **run intermédia com configs antigas
   (redundante)** antes da run boa. Devia ir DIRETO a: seleccionar o nó da **1ª
   ação não-fold** → Selected Subtree → CI=10 → OK → esperar → exportar (sem prune,
   exatamente 2 runs). **Fix = `tools/watcher_src` + reconstruir `.exe`, sessão
   dedicada.** Spec canónico: `docs/WATCHER_FLUXO.md`.

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

10. **`#CI-TARGET-INITIAL-NOT-CALIBRATED` (pt25e Bloco 2).** Calibrar a coord
   do campo CI Target inicial da 1ª run no main UI. Actualmente
   `CI_TARGET_FIELD_X/Y = 0` → `_set_ci_target_common` degrada para Enter
   (funciona, mas é menos limpo). Smoke devagar com o Rui para medir a
   coord.

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
