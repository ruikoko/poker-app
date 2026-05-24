# Pendentes — backlog vivo

**Última actualização:** 24 Maio 2026 (pt40 em curso — 🛡️ guarda `DISCORD_LOBBY_AUTO=false` em prod; aberto `#LOBBY-ANCHOR-PRESTART-REGRESSION` HIGH; ver TECH_DEBTS secção pt40).
**Propósito:** lista priorizada do que atacar a seguir. Distinta do
`TECH_DEBTS_INVENTARIO.md` (que é o registo histórico exaustivo, com
estado de cada debt) — aqui é só a **fila de trabalho**, ordenada.

> Manutenção: quando um item for feito, mover para o journal/tech debts e
> remover daqui. Quando aparecer um item novo, colocar na categoria certa.

---

## Alta prioridade (atacar a seguir)

> **Foco pt40 (em curso):** 🛡️ **guarda activa** — `DISCORD_LOBBY_AUTO=false` em
> prod (deploy `ac26c261`); **não** correr sync de lobby nem re-disparar até o
> anchor fix. Dois tracks:
> - **Track A (prod-safety, prioritário): `#LOBBY-ANCHOR-PRESTART-REGRESSION`** —
>   o anchor `start ≤ posted` do TIER 0 (pt39) falha p/ lobby SS (tirada na
>   inscrição → torneio começa depois do post) → mis-resolve p/ o dia anterior.
>   É o que **desbloqueia o re-disparo seguro** dos ~24 `tm_not_found`.
> - **Track B (alívio operacional, paralelo): `#HRC-PER-HAND-DOWNLOAD`** — botão
>   "Download HRC pack" per-mão no `/hrc` (independente do resolver).
> **Depois do Track A:** `#RESOLVER-TIER12-WINDOW-NO-START` +
> `#META-START-TIME-IS-FIRST-HAND-NOT-SCHEDULED-START` (passos 5+6, agora MED) +
> re-disparo (`sync-recent` `dry_run`→real) + **reverter `DISCORD_LOBBY_AUTO=true`**.
> **Fechados em pt39:** `#RESOLVER-TIER0-STRICT-EQUALITY` ✅ (`35286c1`) e
> `#TABLE-SS-RESOLVER-COLLISION` ✅ (`36f7f7f`+`e2c6460`+cleanup BD).

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

3. **Discord — 2ª entry para Tournament Markers duplicados.** Bug aberto há
   sessões: quando um TM aparece em 2 canais, o 2º canal não é adicionado a
   `discord_tags`, e a regra C de villain não dispara. Alta prioridade
   pré-sessão.

4. **Uniformização de tags Discord ↔ HM3.** Urgente — fragmentação visual
   no Estudo (o mesmo conceito aparece com nomes diferentes consoante a
   fonte). 3 opções já levantadas: renomear canais, dict de aliases
   hardcoded, ou UI admin central de tags. Decisão de produto pendente.

5. **`#RESOLVER-TIER0-STRICT-EQUALITY` — ✅ FIXED pt39 (`35286c1`).** TIER 0 passa
   a `buy_in` (igualdade exacta `buy_in_total`+currency) + **janela `start_time`
   ancorada no `posted_at`** (instância em curso); `prize_pool`/`total_players`
   mantidos NULL-permissivos para o backoffice (`tournament_results.py`, 5º
   consumidor). Detalhe em `TECH_DEBTS_INVENTARIO.md` secção pt39.
   *(Pendente só: re-disparar os lobbys `tm_not_found` para validar em prod — ver foco.)*

6. **`#RESOLVER-TIER12-WINDOW-NO-START` (🔴 HIGH, aberto pt37).** Janela dos
   TIER 1/2 inutilizável quando a Vision não lê `start_time` (consistente): o
   fallback `[posted_at−12h, posted_at−30min]` exclui o candidato (o torneio
   começa depois do post). Fix: alargar fallback para `+12h`, ou Vision extrair
   `start_time`. **Relacionado: `#META-START-TIME-IS-FIRST-HAND-NOT-SCHEDULED-START`**
   (ex-`#START-TIME-TIMEZONE-INCONSISTENCY`); a dependência "TZ primeiro"
   dissolveu-se em pt39 (não é TZ — `meta.start_time` é a 1ª mão, não o arranque).
   Ver `TECH_DEBTS_INVENTARIO.md` (pt37 + pt39).

7. **`#META-START-TIME-IS-FIRST-HAND-NOT-SCHEDULED-START` (🔴 HIGH, aberto pt37
   como `#START-TIME-TIMEZONE-INCONSISTENCY`, re-rotulado pt39).** **NÃO é bug de
   TZ** (re-diagnose pt39, read-only). `tournament_summaries.start_time` =
   arranque agendado; `tournaments_meta.start_time` = `MIN(played_at)` = 1ª mão
   importada (horas adiantada quando há late-reg / import parcial). O diff é 0
   quando a 1ª hand é Level1 e cresce com níveis tardios — semântica, não
   relógio. **Já não bloqueia os outros** (não há TZ a corrigir); mas continua a
   contaminar qualquer janela ancorada em `meta.start_time`. Ver
   `TECH_DEBTS_INVENTARIO.md` (secção pt39).

8. **`#IMPORT-MODAL-MISROUTES-TS-RESULTS` (🟠 HIGH UX, aberto pt37).** O
   `ImportModal` manda qualquer `.zip` para `/api/import`; um TS cai no ramo P&L
   (degrada), Results dá 400/screenshot, e a UI mostra "Importado" escondendo o
   resultado real. Fix: detectar o tipo pelo conteúdo e encaminhar, ou avisar
   quando não é HH. Ver `TECH_DEBTS_INVENTARIO.md` (pt37).

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
     multi-tabling não é 100% fiável até os 3 HIGH do resolver (itens 5–7)
     fecharem. Ver `docs/JOURNAL_2026-05-24-pt38.md` e `TECH_DEBTS_INVENTARIO.md` (pt38).

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
   Table cai na 2ª linha (EP). Origem desconhecida. Não bloqueia o flow,
   mas investigar (pode afectar uma futura 3ª run ou navegação encadeada).

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

---

## Baixo prazo / qualidade

15. **Vision parser improvements** — tolerância ao prefixo TM, heurística do
   BB stack, prompt GTO mais forte.
16. **Gyazo pipeline** — tabela `hand_attachments` (anexos de imagem
   Discord ↔ mão; ver CLAUDE.md "Imagens de contexto Discord").
17. **Filtros derivados no Estudo.**
18. **Dashboard — colunas adicionais.**
19. **Winamax replayer — URL da Vision.**
20. **`_upload_screenshot_to_storage`** — limpeza do stub.
21. **Discord entry status** — cosmético.
22. **Discord page — dual time filters.**

---

## Cross-references

- `docs/TECH_DEBTS_INVENTARIO.md` — estado detalhado de cada `#TECH-DEBT`.
- `docs/GTO_BRAIN.md` — visão e roadmap do GTO Brain (3 fases).
- `docs/JOURNAL_2026-05-22-pt35.md` — sessão que fechou a Fase 1 do GTO Brain.
- `docs/JOURNAL_2026-05-22-pt30-pt34.md` — contexto da sessão que fechou a
  cadeia da 2ª run.
