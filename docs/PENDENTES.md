# Pendentes — backlog vivo

## ★ Propagação FT (`ft_boundary`) — em construção faseada (plano APROVADO, 7 Jul)

Plano de wiring aprovado (7 Jul) com emenda + decisões D1-D5. Ordem: **F1** corrigir 2
incompatibilidades → **F2** Adição 1 (cross-check HH) → **F3** tabela + endpoints ensaio/quarentena →
**F4** UI da quarentena → **F4b** validação empírica contra torneios reais → **F5** ligar gatilhos +
botão promover → **F6** re-solve das mãos HRC stale. Escrita **sempre manual** (dry-run → OK do Rui);
**CONFIRMAR/CORRIGIR na quarentena fixa a fronteira e devolve o ensaio** (2 passos: decidir a
fronteira ≠ aprovar a escrita). Decisões: D1 quarentena se N ilegível; D2 cross-check também no
fallback (players_left da fronteira = N); D3 `folder_ft_source='auto'`; D4 manter as 2 escritas do
`_ft_applies`; D5 construir ANTES do wipe (é cura do core).

- **F1 ✅ (7 Jul)** — `_persist_ft_correction` grava `folder_ft_source='auto'` (não a via
  `propagated_*`, que poluía o filtro "-ft auto") + `CASE` preserva `'manual'` (pasta -ft manda). +1 teste.
- **★ Endpoint `GET /api/gg-health/ft/raw-material` (SÓ LEITURA, `require_auth_or_api_key`)** — matéria-prima
  da F4b: torneios GG 2026 por dia com pista de FT (`min_players_left` + `latest_hand_seats` +
  `has_lobby` + `ft_candidate`). **REUTILIZADO pela Fase 3** (o preview/quarentena parte das mesmas
  leituras: fronteira + cross-check) e **RE-CORRÍVEL após o wipe+reimport** (recomputa de raiz, nada
  persistido) → serve de sanity-check pós-reimport. +3 testes.

- **CONVENÇÃO do print de arranque da FT (via 1) — 7 Jul, ver `REGISTO_CONCEITO 2026-07-07`.** A fonte
  (a) do motor só pode ancorar em lobbys com a **aba "Info" ABERTA** (`vision_json.open_tab=='Info'`),
  onde se lê "N players at the final table"; o N vem daí (`final_table_size`). Prints de outras abas
  (Players/Prize Pool) **nunca** ancoram. **A `lobby_vision` WIP já tem `open_tab` + `final_table_size`**
  (lado da Vision) → **commitar/deployar com a F2**; o `ft_boundary._lobby_ft_boundary` tem de passar a
  **gatear por `open_tab='Info'`** (hoje usa `players_left<=FT_CAP` de qualquer print — corrigir na F2
  ANTES de ligar a escrita).

- **★ Caso de teste da 4b — VIA 1 ponta-a-ponta (Daily Hyper $60, 2 Jul):** started 17:45, 172 entradas;
  **print do Info ~19:19 → "7 players at the final table", 7/172 restantes** (Hero **Lauro Dermio**, 5º,
  7 BB). Teste: fronteira **pelo print do Info** + **N=7** + cross-check com os sentados da 1ª mão
  pós-fronteira (deve dar 7). **Controlo NEGATIVO:** 2º print do mesmo nome nessa noite — **edição das
  21:27, 169 entradas, nível 13, 107 restantes, aba Prize Pool** → o motor **não** o pode usar como
  fronteira nem confundir a edição. ⚠️ **Dependências para correr:** (1) confirmar que a HH+TS do Daily
  Hyper entraram (tournament_number + nº de mãos — pendente `railway login`); (2) a via-1 só corre com a
  `lobby_vision` nova **deployada** e o print do Info **re-Visionado** (senão o `vision_json` não traz
  `open_tab`/`final_table_size`).

- **4 FTs de Jun (16-26) — testam a VIA 2 (fallback) + cross-check D2.** Não têm print do Info (o Rui só
  começou a tirá-los a 2 Jul) → fronteira por `players_left` coerente das capturas IT + cross-check com
  `players_left` da fronteira como N. A tabela do endpoint cruza-as (o Rui identifica-as por
  `min_players_left`/`latest_hand_seats`).

## ★★ MUDANÇA DE ESTRATÉGIA (3 Jul 2026) — LER ANTES DE TOCAR NO BACKLOG DE DADOS GG

A sessão de **3 Jul** virou a estratégia (registada em `docs/APA_INDEXACAO_E_COLAPSO.md`):
**os dados actuais da app vão ser APAGADOS e REIMPORTADOS.** Consequência directa no backlog:

- **(a) A cura de DADOS históricos foi ABANDONADA.** As "pontas" de bounties/desanon
  históricos (1 presa `GG-6102580840`, 2 por rever, 5 seats truncados, mãos consertadas à
  mão, lote das 44 partidas) **podem morrer com o wipe** → **NÃO as trabalhar sem o Rui
  confirmar** que ainda fazem sentido depois do reimport. O esforço mudou de "curar os dados"
  para **"curar o CORE"** (o código que produz o apa) para que os mesmos dados entrem
  direitos quando reimportados.
- **(b) `#HRC-REIMPORT-REDEANON-CASADAS` DEIXA de ser diferível — prioridade SUBIU.** Sem
  ele, o reimport de HH **parte a desanon das mãos com captura já casada** (repõe o apa cru +
  esvazia o `anon_map` sem re-disparar a desanon das SS **casadas**, só das órfãs). Passa de
  "melhoria futura, NÃO agora" (pt93) a **pré-requisito do wipe**. Ver secção própria abaixo.
- **(c) A decisão do CORE (apa indexado por HASH em vez de nome) está NÃO APROVADA.** É
  decisão do **Rui**, não backlog do Code — há uma desconfiança dele por resolver (`APA §B.4`:
  como convivem o nível-mão [hash] e o nível-jogador [nome dos Vilões]). **Não escrever código
  do core** até o Rui aprovar o desenho. O §C do doc (mapa de acoplamento do apa, ~15-18
  sítios) é o Passo 1 já feito.

## ★ pt97 (1 Jul 2026, Web) — pós crachá/guardião/tags/saúde GG

- **Fase 2 da "Saúde das mãos GG" (ações):** hoje a secção só MOSTRA (Fase 1, `a3deb74`). A Fase 2 traz as ações e **absorve a "Marcadas por captura"**: tag de **1-clique** (11 tags canónicas), **corrigir nomes** (via `/set-anon-map`), confirmar **unverified→verified**, e **propagação de nome por hash no torneio** (1 confirmação → ~3 mãos tagadas; o hash segue o jogador entre mesas — `DESANON_ANATOMIA §3.3`). Herdar: estado `capture_triage`, `folder_ft_source`, `apply_villain_rules`.
- **2 mãos de CAPTURA TROCADA por resolver** (a captura pertence a outra mão — não é erro de nomes): `GG-6104057685` (dona verdadeira `GG-6104057552`, hoje sem captura) · `GG-6105043278` (dona `GG-6105043116`). **Bloqueadas por 2 primitivas que NÃO existem:** (1) **"reverter uma mão a anónima"** (repor `player_names={}` + apa hash-keyed do raw + limpar villains + `context_table_ss_id=NULL`) — hoje tirar a captura NÃO reverte, a mão fica com o anon_map errado; (2) **guarda que protege `position_v3`** (`_REAL_MATCH_METHODS` só tem `anchors_stack_elimination_v2` → ligar uma captura IT a uma mão gold **clobbera** o position_v3). Só depois destas duas é seguro religar a Gold/IT certa.
- **2 mãos em CONFLITO DE TAGS (formato)** a resolver — a mesma mão (`GG-6117985931`) com `icm` (não-PKO) + `icm-pko` (PKO). Ver R1 em `TAGS_CANONICO.md`.
- **Enforcement das 2 regras de incompatibilidade de tags** (R1 formato, R2 fase) — definidas em `TAGS_CANONICO.md`, hoje só **sinalizadas** (Saúde GG), não impedidas na escrita.
- **Decisão Gold-vence-IT — via premium:** onde o IT falha (captura trocada / nomes por verificar), **descarregar a Gold** dessa mão (casa 1:1 exato). 0 Golds à espera nas 382 só-IT; é acção manual do Rui.
- **2 buracos novos destapados (2 Jul, editor Saúde GG):** (1) **excluir jogador que não jogou** — o `players_list` guarda o sentado-sem-cartas (ex. `Afonso Neto` em `GG-6083771298`, coroa 0.0) e a **guarda de suspeitas (`suspicious.py`) lê `players_list`** → falsa `bounty_below_half` (floor 25); falta primitiva "excluir do players_list" OU a guarda só contar seats mapeados (`anon_map.values()`). (2) **confirmar coroa <½-base como legítima** — `detect_bounty_below_half` é pura/live, SEM whitelist; falta flag persistido (`bounty_confirmed`) que a guarda respeite. Ambos entram no **editor por-mão do Saúde GG** (desenho 2 Jul, à espera de aprovação do Rui — não codificar antes).

## ★ 1 Jul 2026 — pendências pós-frentes (bounties + desanon por âncora)
- **Build do watcher (foco + guarda de TEMPO):** o foco (`#HRC-FOCUS-ROBUSTNESS`, `049cd4b` em `watcher-gate`, NÃO buildado) + a **guarda de tempo** (teto **5h/1ª run** decidido; falta o **print do painel do HRC com o tempo** + escrever o OCR do tempo em `tree_stats.py`) — **um build só** com `min_children=60`.
- **Pontas dos bounties (histórico):** **1 presa** (`GG-6102580840`, seat `G Sieemshchikov` — reread OCR l/i não casou) + **2 por rever** (`6101135610` parcial, `6104865113` sem imagem em Transferências) + **5 seats truncados**. Consertam re-lendo a coroa certa.
- **Desanon por âncora — VERIFICAÇÃO VISUAL do Rui** das 14 (fichas de verificação geradas: hand/torneio/hora + seat a seat + âncora que resolveu). + o `arieloo` (bounty a **verde** na coroa do `mirroring`, `GG-6114944767`).
- **Inventário Vision:** 4 pontos Claude Sonnet 4.6 (table-SS, replayer, lobby, backoffice) + 1 OCR winsdk (`tree_stats`, watcher). Rever qualidade/prompts de cada.
- **Guardião de validação automática** (pedido do Rui): detectar `bounty < base÷2` / vilão=nome do Hero / desanon `review_alarm` e **alertar** (não deixar passar em silêncio). **v1 construída** — secção **"Mãos suspeitas"** (endpoint `GET /api/suspicious-hands`, page + badge na sidebar) cobre os **2 venenos PUROS** (bounty<½ ≈91 · nome-do-Hero-num-vilão =6). Falta: **veneno 3 (`review_alarm`)** — não é persistido, precisa de coluna/log próprio para ser listável.
- **Reorganização da barra lateral (pedido do Rui):** o Rui quer **reavaliar a disposição/organização da sidebar mais tarde**, quando a app estiver ao gosto dele (ordem/agrupamento dos itens — ex. juntar as filas de revisão «Marcadas/captura» + «Mãos suspeitas»). Não mexer agora; só quando ele pedir.
- **8549 (`#STUDY-STATE-REGRESSION-HH-IMPORT`):** Opção A (deixar). Opção B só COMPLETA (3 peças) em sessão dedicada — ver TECH_DEBTS.

## ★ pt91 (26–27 Jun 2026) — FECHO DE DIA (import Junho + Vision + fix posições HRC + GTO Nível 2 mapa técnico)

> ⚠️ **Reconciliação com a nota ditada do Rui:** 2 itens da nota de fecho avançaram NESTA
> sessão e a redacção dela ficou stale — registado o estado **verificado** (confirmar):
> **(item 3)** o `GG-6101135610` foi **diagnosticado e Fase 1 corrigida** (`8c9ef66`) — é o
> `#POSITION-LABELS-PYTHON-JS-DRIFT`, **NÃO** money-vs-BB (descartado: stacks corretas em BB);
> **(item 7)** o import `--ao-vivo` 21–26 Jun **FOI corrido e concluído** nesta sessão.

### ✅ Feito/confirmado nesta sessão (verificado)
- **#POSITION-LABELS-PYTHON-JS-DRIFT Fase 1** (`8c9ef66`, deployed) — label do 1º a agir 6-max
  `MP→UTG` em `_POSITION_LABELS_BY_N[6]`. Corrige o `GG-6101135610` (UTG ~3,3 BB: dava
  `R 2.00 + R 3.16`, passa a só `ALLIN`). +7 testes migrados; prova local `SIZES_OPEN_UTG=['ALLIN']`.
  Ver entrada no `TECH_DEBTS`.
- **Import 21–26 Jun `--ao-vivo`** corrido e concluído (~1968 ficheiros em `done`: mesa 1145,
  lobby 457, gold 315, mãos/TS). Fora-da-janela (datas ≠ 21–26) saltadas, como esperado.
- **Vision destrancada** — a IA Anthropic estava **sem créditos** (todas as chamadas 400
  "credit balance too low"); após recarga do Rui, backfill `POST /api/screenshots/vision/backfill`
  processou as 244 pendentes → **SS sem match 145 → 0**; gold ligadas às mãos.
- **Lobbys**: 303/319 casaram (95%); os 16 pendentes são capturas inválidas/lixo (login,
  "late registration", WPN com data partida) — não casam por não terem torneio real. **ZENITH**
  (Winamax, lobby 15 Jun) fica `tm_not_found` porque **não há mãos ZENITH de 15 Jun** na app
  (só 16/21/22/23/25/26) — falta-lhe a edição desse dia, não é bug.
- **Nível 1 (badge HRC na Estudo)** — **JÁ EXISTE desde pt69**, funciona (provider envolve
  `Hands.jsx`; `HrcStateBadge` em `HandRow.jsx:241`; `/api/queue/hrc/states` devolve
  `concluída/na fila/falhou`; vocab bate). **Nada a fazer.** Estado prod: gate **ABERTO**,
  **71 mãos resolvidas (done)**, 36 por resolver, 17 falhou, 373 não enviadas.
- **#APPIMPORT-DATE-FILTER-IT-GOLD** (item 5) — FECHADO (`de2fa18` + `d3bdfa2`). [já registado abaixo]
- **#HRC-NODE-OFFSET-IMPLICIT-LINES** — confirmado **já FECHADO** (`8096f3c`, pt86b); a nota
  "fila travada por este bug" (pt67) está **stale**. A fila está aberta; ~0 solves era falso.

### EM ABERTO — para retomar amanhã
1. **GTO Nível 2 (mostrar estratégia HRC na mão + NAVEGAR a árvore)** — **decisão tomada** (Rui):
   o MEU spot + navegação multi-spot, com a **solve exata 1:1**. **Mapa técnico FEITO (leitura):**
   a navegação da tab GTO (`ReplayerPage.jsx`) **NÃO está presa ao match** — `POST /api/gto/navigate`
   e `getNode` só precisam de um `tree_id`; o `gtoApi.match` (l.287) é apenas a fonte do `tree_id`.
   **Desenho ideal:** parsear a solve 1:1 (`hrc_jobs.result_zip` → `parse_hrc_zip()` já existe) para
   uma árvore `gto_trees` **própria**, ligá-la à mão (coluna nova `source_hand_db_id`), endpoint
   `GET /api/hands/{id}/gto-tree` → `tree_id`, e no frontend usar **esse** `tree_id` em vez do
   `bestMatch.tree_id` (fallback ao match para mãos sem solve). Reaproveita `parse_hrc_zip`,
   `gto_trees/gto_nodes`, `/navigate`, `/node` e a tab GTO inteira. **3 DETALHES POR DECIDIR:**
   (a) **excluir** as árvores por-mão do `/match` difuso (`AND source_hand_db_id IS NULL`);
   (b) **storage** — descartar o zip bruto após parsear ou manter para auditoria;
   (c) **solves "stale"** pré-correções (offset pt86b + posições pt91) — re-gerar as antigas.
   **FALTA: a proposta de implementação faseada.** NÃO construído.
2. **(item 3 resto) Sizes em stack curto** — UTG **FIXO** (Fase 1). **Por verificar:** o caso
   **BTN <5BB** (nota Rui) também a dar 2 sizes — provavelmente **causa distinta** (o BTN já
   normalizava `BTN→BU`, a Fase 1 não o muda). **Fase 2** (n=7/8/9, drift estrutural + `EP/UTG1`)
   aberta. Ver `#POSITION-LABELS-PYTHON-JS-DRIFT`.
3. **(item 4) OCR pt90 não dispara** — *(fio do Code principal, branch `watcher-gate`)*. Diagnóstico
   Beelink: solves grandes/reais não registaram nodes/GB; **0 OCR em log nenhum de sempre**. Causa
   provável: call-site do OCR **não alcançado** no `.exe` (chamada ausente do fluxo OU try/except a
   engolir). Por achar no código-fonte do watcher. *(Não tocado nesta sessão.)*
4. **(item 7 resto) HM3 — 6 dias por importar** *(operacional do Rui)*. O appimport faz-se à mão
   (`python app_import.py --ao-vivo --desde 2026-06-21 --ate 2026-06-26`, salas fechadas), **NÃO** o
   RunAll/appmaster (força Discord). O **import de mãos GG/IT/gold** já foi nesta sessão; **falta o
   HM3** (mãos WN/PS/WPN dos 6 dias). *(Nota: o HM3 já foi corrido pelo Rui a meio da sessão p/
   destrancar os lobbys WN; confirmar cobertura dos 6 dias.)*
5. **(item 8) Fila partilhada — 5 pessoas do backer team a partilhar o Beelink** (recepção→HRC→envio).
   FUTURO, sem pressa. Em discussão: regra de fila (à vez vs pequena-primeiro) + realidade de
   1 máquina / 1 mão de cada vez. **Depende do OCR (tamanho da árvore) funcionar.** NÃO começado.

### ✅ Fechado hoje (confirmado, não reabrir)
- **(item 6) Reinício do HRC a cada 5 mãos** — confirmado a funcionar no pt90 (**falso alarme**).
- **(item 5) #APPIMPORT-DATE-FILTER-IT-GOLD** — `de2fa18` + `d3bdfa2`.

---

## ★ pt90 (25 Jun 2026) — watcher OCR tree-size: instalar `watcher-pt90` + smoke end-to-end

`#HRC-TREE-GIGANTE` **fix shipped** (`watcher-gate` `9609ab6`+`7384ed2`; Release `watcher-pt90`).
Source + harness + OCR (smoke #1 no Beelink) + bundle do `.exe` **verificados**. **`.exe`:**
SHA256 `69e741c2f8b80e3f1323aaa1fe6150adb046d3b83ef87debadf7613321cc673c` (32 988 546 B);
Release https://github.com/ruikoko/poker-app/releases/tag/watcher-pt90.

**Instalado no Beelink — REPORTADO pelo Rui (26 Jun):** o `.exe` `watcher-pt90` (SHA acima) foi
instalado; o **pt87 foi guardado em `C:\hrc\backup_watcher`** como rollback. ⚠️ Nota: um backup do
exe anterior no Beelink **fricciona com a regra «1 só watcher exe»** (o histórico devia viver no
PC+git) — registado aqui para não se perder; decidir se `C:\hrc\backup_watcher` fica ou se limpa
depois do smoke OK. *(Estado da instalação por confirmação de SHA round-trip no próprio Beelink.)*

**Smoke happy-path — 1ª tentativa (26 Jun), NÃO concluída.** A 1ª mão (`GG-6083866641`) caiu no
**ramo `tree=0`** → o OCR **não disparou** (ver `#WATCHER-OCR-NOT-READ-ON-TREE-ZERO-BRANCH` em
`TECH_DEBTS`). **Esclarecido: NÃO era gigante** — árvore **~2 GB** (os **8.6 GB** eram **RAM do
processo**, não a árvore); os **33 min** são **normais** para o perfil **MP/multiway** (confirmado
no histórico: solves longos são todos early/multiway HJ). **Sem falha de guarda, sem drama**; mão
em `C:\hrc\queue_hold`, **recuperável**. **FALTA:** correr o happy-path com uma mão de **árvore
média** que dispare **"tree estável" limpo** (e ver `nodes/gb` no `meta.json` + `ocr_ok:true`).

**Falta (operacional, Rui+Web no Beelink):**
1. ~~Descarregar da Release + confirmar o SHA256~~ / ~~Instalar no Beelink~~ — **reportado feito** (ver acima; SHA round-trip a confirmar no Beelink).
2. **Smoke end-to-end no `.exe`:** (a) mão normal corre; (b) tree gigante forçada → `.failed`
   com motivo "tree gigante: X GB > 15"; (c) OCR forçado a falhar → corre na mesma (`ocr_ok:false`).
3. Só depois de (2) OK: dar `#HRC-TREE-GIGANTE` por **fechado** e ponderar merge `watcher-gate`→`main`.

## ★ `#WATCHER-JANELA-DE-TRABALHO-ETA` (FUTURO, URGENTE) — janela de trabalho + travão por ETA/custo

**Ideia:** definir uma **janela de trabalho** (ex.: 8h) e o watcher **gerir a fila** para a encher
da forma mais produtiva, usando o **ETA da janela "Monte Carlo Sampling" do HRC** como **travão em
tempo real** (*Via C*). Liga-se ao pt90 (captura OCR) — **reutiliza a mesma infra** de OCR de
janela do HRC (`tools/watcher_src/tree_stats.py`, PrintWindow + `Windows.Media.Ocr`).

**Comportamento desenhado até agora:**
- O watcher **lê o ETA assim que aparece** (logo após o Finish, no início do solve).
- **Critério de corte: POR FECHAR** — decidir entre **teto fixo por mão + margem no fim da janela**
  (recomendado) vs. **só tempo-restante**.
- **Mão saltada** (ETA grande de mais) → **marcada para OUTRA janela** (mais longa), **NÃO se perde**.
- **Se o ETA crescer depois de começar:** comportamento **POR DECIDIR**.

**Obstáculos conhecidos (registar):**
1. O ETA **só aparece DEPOIS de o solve começar** (visível na barra ~13%), **não antes** → não dá
   para **ordenar à partida**, só **travar em tempo real**.
2. Percorrer N mãos só para **"espreitar" o ETA** de cada uma **CONSOME tempo real da janela** →
   viabilidade depende de **quanto custa ler o ETA por mão** (**medição pendente no Beelink**:
   setup→Finish, Finish→ETA estável, overhead de troca de mão).
3. Ler o ETA exige **OCR da janela "Monte Carlo Sampling"** — **ainda NÃO testado** se essa janela
   se lê (pode ser opaca, como o painel Tree Statistics era; talvez precise do **mesmo PrintWindow**).
   **Validação pendente.**

**SINAIS PRECOCES DE CUSTO (ideia Rui — alternativa/complemento ao ETA, que é caro):**
em vez de esperar o ETA estabilizar (obriga a **gastar solve** por mão), usar sinais que aparecem
**MAIS CEDO** como proxy do tamanho/tempo da tree:
1. **Tamanho da tree (nós/GB)** — **JÁ lido por OCR antes do Finish** (pt90). O **mais precoce**.
2. **NOVO (Rui):** o **tempo de espera até à 1ª run** / a **lentidão dos primeiros instantes** do
   Monte Carlo Sampling **correlaciona com o tamanho da tree** → dá pista do custo **antes** de o
   ETA estabilizar.
3. **ETA estabilizado** — o **mais tarde e caro**.

**Implicação:** a "janela de trabalho" **pode talvez dispensar a leitura cara do ETA** e gerir-se
pelos **sinais 1+2** (baratos, precoces). **A validar** quando se medir no Beelink
(setup→Finish, Finish→1ª run, evolução do ETA) — **cruzar os 3 sinais contra o tempo real de mãos
conhecidas** para ver qual prevê melhor.

**Alternativa a considerar — *Via A*:** **ordenar pelo TAMANHO da tree** (que já lemos por OCR
**ANTES** do Finish, sem gastar solve), como **proxy do tempo**. Pode ser melhor que a *Via C* se a
leitura do ETA for cara.

> Estado: **FUTURO/URGENTE — medição pendente no Beelink**. Não construir antes de medir os 3 sinais.
> Cross-ref: pt90 (`#HRC-TREE-GIGANTE`, infra OCR), `TECH_DEBTS_INVENTARIO.md` (secção homónima).

## ✅ FECHADO (`de2fa18`, 26 Jun) — `#APPIMPORT-DATE-FILTER-IT-GOLD`

**Construído e validado.** O `gold` era o **único gap** de cobertura de janela; depois do fix, as
**5 fontes de imagem** (`manual`, `it`, `lobby`-subpasta, `gold`, `LOBBY_DIR`) respeitam
`--desde/--ate`. `process_gold_dir` ganhou `window=` e filtra pela **data do NOME** (helper
`_gold_name_date`, regexes alinhadas com `screenshot._parse_filename`; **decisão pt91: data/hora de
download = de jogo** → a objecção download-vs-play dissolveu-se). Nome sem data/hora legível →
**incluído por defeito + aviso** ("na dúvida inclui"). Conta/reporta `fora da janela` no resumo.
Critério não-uniforme **por desenho**: data-do-nome onde existe (`it`, `gold`); `mtime` onde o nome
não tem data (`manual`, `lobby`). **Dry-run `--desde 2026-06-01`:** gold **325 dentro / 89 fora**
(Março), fronteira dia-de-jogo 15:00 correcta, **0 avisos**. **Tool-side, sem deploy** → `git pull`
na máquina do appimport. Detalhe em `TECH_DEBTS pt91`. Mantém-se o registo da investigação original abaixo.

Pedido do Rui: filtrar `--desde/--ate` também por **data do NOME** do ficheiro nas fontes de
imagem `it` e `gold`, para **não ter de mover ficheiros à mão por data**. **Investigação read-only
feita (26 Jun):**

- **`it` — JÁ FUNCIONA, nada a fazer.** O filtro `--desde/--ate` já se aplica aos `it` e já lê a
  data **do NOME** (`classify_it_file` extrai `YYYYMMDDHHMMSS` da cauda `-YYYYMMDDHHMMSS-NN`;
  `_img_date(path, captured)` em `process_it_mixed`). **Provado** correndo as funções sobre nomes
  reais: 22/06 e 25/06 saem **FORA**, 23/06 **DENTRO** com `--desde/--ate 2026-06-23`. (Formato
  novo `GGnet.exe-<Título>-<YYYYMMDDHHMMSS>-<NN>.png`; antigo `Shot<N>-<Site>-<YYYYMMDDHHMMSS>` →
  `_OLD_SHOT_RE`, também com data; nome sem data → SKIP, nem é enviado, ou fallback a `mtime`.)
- **`gold` — FALTA. É o único gap.** `process_gold_dir(session, live)` **não tem parâmetro
  `window`** e é chamada sem janela (de propósito: "SEM filtro de mês"). Os nomes gold/manual são
  `YYYY-MM-DD_ HH-MM_AM|PM_$SB_$BB_#TM.png` (data **no início**, hora **12h AM/PM**).
  **Mudança** (1 ficheiro, `tools/appimport/app_import.py`): helper `_gold_name_date(fname)`
  (regex `^(\d{4}-\d{2}-\d{2})_\s*(\d{2})-(\d{2})_(AM|PM)` → datetime 24h, **fallback a `mtime`**
  se não casar, para nunca descartar em silêncio) + `process_gold_dir(..., window=None)` + passar
  `window=img_window` no `main()` + contagem "fora da janela".
- ⚠️ **Decisão de produto POR FECHAR antes de construir:** a data do nome gold/manual é a do
  **DOWNLOAD**, **não** a hora de jogo (`#GG-DOWNLOAD-IMG-FILENAME-TIME-AND-BLINDS-UNRELIABLE`).
  Para "não enviar meses antigos" serve (≈ `mtime`, que o `manual`/`lobby` já usam); se o objetivo
  fosse filtrar pela **hora a que a mão foi jogada**, o nome do gold **não** ta dá. Confirmar o
  objetivo antes de desenhar.
- **Contexto (mudança de hoje):** o `GOLD_DIR` do `config_local.py` passou de `Documents` (raiz)
  para a **subpasta dedicada `Documents\Gold`** — `config_local.py` é gitignored, mas o
  `config_local.example.py` foi alinhado (a raiz era perigosa: o read é **não-recursivo** e
  enviaria **todas** as imagens da pasta). Ver `#GOLD-DIR-DEDICATED-SUBFOLDER`.

> Estado: ✅ **FECHADO** (`de2fa18`, 26 Jun) — ver topo desta secção. A decisão download-vs-play
> foi tomada (pt91: download = play na prática) e o fix shipped.

**Import de mãos — mapa levantado, por EXECUTAR (26 Jun).** As pipelines de entrada estão todas
mapeadas: **`RunAll.bat`** (appmaster → appimport + HM3 + Discord, um clique) · **`ImportAoVivo.bat`**
(só appimport: `gg_hh`/`gg_ts`/`manual`/`it`/`lobby`/`gold`) · **`Import.bat`** (dry-run de ensaio).
A **execução real** fica para amanhã (regra de sessão: **salas fechadas**). Ordem embutida no
appimport (HH→TS→imagens→lobby→gold) + reconciles automáticos no servidor; ver também a ordem
gold↔HH em "★ pt75 — operacional".

## ★ pt88 (24 Jun 2026) — 2 fixes em prod + reclassificação do study-state

- ✅ **`#POST-TABLE-SS-MOVE-EM-VISION-FAILED`** (commit `c5a2a29`, origin/main) — table-SS `vision_failed`
  deixa de ser movida com ✓ falso; passa a `retry` (fica, re-envia no próximo run), paridade com o
  lobby. Tool local appimport, sem deploy. (Detalhe em `TECH_DEBTS pt88`.)
- ✅ **`#include_no_payout-mismatch`** (commit `078072f`, deploy Railway SUCCESS) — `/hrc/release`
  alinhado a `include_no_payout=False`; mão sem payout **rejeitada com motivo claro**
  (`sem payout — não pode ir ao HRC (torneio sem estrutura de prémios)` no tooltip de "ignoradas")
  em vez de **released-fantasma** presa sem nunca correr.
- 🟢 **`#STUDY-STATE-REGRESSION-HH-IMPORT` reclassificado — NÃO é bug.** As não-GG (PS/WN/WPN) são
  mãos de estudo → `'new'`/Estudo é **correto e documentado** ("PS/WN/WPN HH sem SS → Estudo directo").
  A premissa "deviam arquivar" vinha da spec pt27 "Duas pistas", que era **só para GG anonimizada**.
  Só a **GG bulk** tem mislabel cosmético (`'new'` vs `'mtt_archive'`) **sem sintoma** (escondida do
  Estudo pelo gate `match_method`; visível em Torneios na mesma). Acionável = **só doc, sem backfill**;
  nota acrescentada à spec "Duas pistas" no `CLAUDE.md`. (Detalhe em `TECH_DEBTS pt88`.)

## ★ pt87 (24 Jun 2026) — verify-gate do save-as FEITO + VALIDADO EM PRODUÇÃO; 3 problemas novos do smoke

**`#HRC-WATCHER-SAVE-NOT-PERSISTED` ✅ FEITO + VALIDADO EM PRODUÇÃO (24 Jun).** Causa: o
`_close_hand_tab` (Ctrl+F4) corria contra o write assíncrono do Complete Export (40-70 MB) e
**cancelava o save** → 0/38 mãos persistiam, watcher preso 24h. Fix (watcher-gate `6522278`):
`_verify_export_zip` passa a **barreira** (existe + tamanho estável + `testzip`) que gateia o
close-tab; trata overwrite; 1 retry; em falha `.failed`+avança; `EXPORT_WAIT_TIMEOUT` 24h→30 min.
Harness 19/19. Exe `e1dced5a` (Release `watcher-pt87`) **instalado no Beelink e validado**: a WN
de 36 MB drenou ponta-a-ponta com `[SAVE-AS-CHECK] OK`; lote a drenar (33+). É o **1º exe a conter
de facto pt84 (watchdog) + pt85 + pt87** (a Release `watcher-pt84` enviara o exe pré-pt84 `5e1414`).

**Reconciliação — saem do backlog (✅ FEITO + validado no smoke pt87 24/06; código no `main` + no
exe que correu hoje):** `#HRC-WATCHER-TAB-ACCUMULATION`, `#WATCHER-LOG-TO-FILE`,
`#HRC-CLOSE-TAB-BREAKS-CHORD-FOCUS`, `#OPEN-WIZARD-CHORD-FALLBACK-BLIND`,
`#HRC-RUN-WINDOW-DETECTION-BLIND`, `#HRC-BOUNTY-HARDCODED-50PCT`,
`#HRC-REDUNDANT-SECOND-RUN-OLD-CONFIGS`, `#CI-TARGET-INITIAL-NOT-CALIBRATED` (8 itens watcher
pt66-70 que estavam listados "re-smoke pendente / fix em buffer").

**3 problemas NOVOS do smoke 24/06 (detalhe em `TECH_DEBTS pt87`):**
- 🔴 `#START-CALC-SELECTED-SUBTREE-NO-POPUP-OPEN` **REABERTO / REGRESSÃO** — a 2ª run não dispara
  o popup Nash (estava fechado em pt32-34; voltou). **Investigar porque o fix antigo deixou de pegar.**
- 🟠 `#HRC-EXPORT-DIALOG-32770-NO-OPEN` **NOVO** — o diálogo Export Strategies (`#32770`) não abre
  (≠ popup Nash, com que partilha a classe).
- 🟢 `#HRC-TREE-GIGANTE` **FIX SHIPPED em pt90** (Release `watcher-pt90`) — guarda preventiva
  construída (OCR do painel "Tree Statistics" + abort por dupla leitura, ANTES da 1ª run). Falta
  só o **smoke end-to-end no `.exe`** (ver "★ pt90" no topo).

**Continuam pendentes (não tocados pelo pt87):** `#HRC-ADAPTER-STATE-DESYNC-SILENT` (🔴, abaixo),
`#HRC-WATCHER-BETTING-SCRIPT-STALL` (🟠, abaixo), `#HRC-ANCHOR-NONBLIND-LIMP` (Passo 2, abaixo).

## ✅ FECHADO (pt89, `bf2da9a`, deployed) — `#HRC-ADAPTER-STATE-DESYNC-SILENT`

**Era 🔴 HIGH diferido.** Causa-raiz operacional resolvida do **lado do servidor**: o
re-envio (`POST /hrc/release`) usava `ON CONFLICT DO NOTHING` → re-enviar uma mão já
libertada era no-op, o `requeue_epoch` não subia, e o adapter saltava-a em silêncio
(`hrc_adapter.py:262`). **Fix:** `ON CONFLICT DO UPDATE` incrementa `requeue_epoch` (+1)
no re-envio → `served_epoch > stored` → o adapter re-puxa sozinho e loga `re-queue`
(mecanismo pt83, já existente). Release fresco = epoch 0 (adapter puxa na mesma). **Sem
mudanças no adapter, sem rebuild.** Consumidor único verificado (manifest → dedup do
adapter). +teste `test_release_rerelease_bumps_epoch`. Ver `JOURNAL_2026-06-25-pt89.md`,
`TECH_DEBTS pt89`.

As opções (a)/(b)/(c) abaixo (robustez do `state.json` no adapter) ficam **dispensáveis**
para o sintoma real (re-envio não corre); só voltam a interessar se aparecer um desync de
outra natureza. Registo histórico do plano:

**(diferido — robustez adicional do adapter, não necessária agora).** O adapter saltava em silêncio mãos que já constavam do
`state.json` local mesmo quando o servidor as volta a oferecer (dedup `hrc_adapter.py:262`);
fica em "entering main loop" a puxar 0 — opaco para o Rui. O "Disparar" da app não toca no
state local → desencontro garantido. **Já não há razão para o skip permanente:** desde o
pt43 o servidor já exclui as `done`, por isso o que ele serve **precisa mesmo** de correr.
**Plano (não implementar até o Rui aprovar):** **(a)** auto-reconciliação — confiar no
servidor e re-puxar, com guarda de in-flight + cooldown pós-done (custo BAIXO-MÉD, adapter
Python puro sem rebuild, exige smoke Beelink); **(b)** aviso claro em PT na consola quando
salta N mãos (custo muito baixo — pode entrar já); **(c)** ressincronizar sem mexer em
ficheiros (sentinela `RESYNC`, custo baixo; ou botão na app, custo méd-alto, dispensável com
(a)). **Recomendado: (a) + (b).** Objetivo: o Rui nunca mais tocar no `state.json` à mão.

## ★ pt86c — bug do robot: stall no betting script (`#HRC-WATCHER-BETTING-SCRIPT-STALL`)

**NOVO** (ver `TECH_DEBTS pt86c`, `JOURNAL_2026-06-23-pt86c.md` fecho 24 Jun). Na validação
visual do Passo 1 do anchor (**as 2 mãos CONFIRMADAS à vista ✓**, âncora no BTN), o robot
**encravou (STALL)** no passo de seleção do **betting script** na GG-6083363843 (3-max):
janela Open/Browse **aberta e pronta**, robot **parado sem avançar nem dar erro**, exigiu
**mão humana** (o Rui desencravou → a mão terminou). **Sem timeout nem recuperação.** Pista:
`setup_scripting` (`watcher_src/patched_funcs.py:912`) carrega o script às cegas + o
`_wait_for_finish_ready` (2480) sem saída se o Open dialog ficar aberto. **Investigar** esse
passo. **Distinto** do incidente do chord do wizard a falhar 2×→reinício (esse **recuperou
sozinho** — não fundir). Relacionado: arco **pt79 / hang-watchdog** atrás do gate (não
ativo). **Prioridade a definir pelo Rui.**

## ★ pt86c — Passo 2 do anchor: limp de não-blind (`#HRC-ANCHOR-NONBLIND-LIMP`) — ADIÁVEL

**Passo 1 do `#HRC-ANCHOR-FALLS-TO-ROOT-NOT-HERO` ✅ FEITO** em pt86c (commit, sem push;
ver `TECH_DEBTS pt86c` + `JOURNAL pt86c`). Regra do Rui aplicada: âncora = nó que governa
a 1ª decisão do Hero (open do próprio Hero / complete da SB; walk → skip). Cobre **6 das 7**
mãos sem-raise (5 Hero-open + 1 walk-skip; 0 Hero=BB-vs-SB-limp hoje). A moldura antiga
"decisão de produto Hero=BB / vs-limp" **dissolveu-se** (Hero=BB-vs-SB-limp ancora no
Complete da SB, que já existe).

**Falta só o Passo 2 — `#HRC-ANCHOR-NONBLIND-LIMP` (1 mão, mexe na árvore → exige smoke):**
o limp de **NÃO-blind** antes do Hero (#7 GG-6083363633, MP limpa, Hero=BTN folda atrás).
O template só modela limp da SB → não há nó. Fix em 3 peças:
- **template** `LIMP_POSITIONS` (default `[]`, override per-mão com o índice HRC do limper)
  + `canFlatCallPreflop` a aceitá-lo;
- **parser de limp** no gerador (`_parse_preflop_actions` hoje só emite raises);
- `count_lines_for_position` **limp-aware** (o bucket do limper ganha +1 linha Complete,
  desloca os offsets seguintes — hoje só a SB).

Confinado (`LIMP_POSITIONS=[]` nas outras = byte-idêntico), mas **toca a árvore → smoke
obrigatório**. Por **1 mão**; não bloqueia nada (fica fallback_root como hoje). **Não
construir até o Rui mandar.**

## ★ pt86 — RE-GERAR trees desalinhadas com a regra nova do ALLIN implícito (25/30)

`#HRC-NODE-OFFSET-IMPLICIT-LINES` ✅ corrigido e **pushed** (`8096f3c`): o template
(`mtt_advanced_canonical_2026.js`) passou de **30 BB geral** para **25 BB geral / 30 BB
só blind-vs-blind** no `shouldAddPreflopAllIn`, e o `count_lines_for_position`
(`hrc_node_offset.py`) passou a espelhar o template com a stack individual de cada
posição (limiar 25/30, colapso, Complete da SB) em vez de `len(array)`.

- **Consequência:** as trees **já geradas/resolvidas com o template 30-geral** (todas
  as do `hrc_jobs` até agora) ficam **desalinhadas** com a regra nova — o `script.js`
  que correu nelas usava 30-geral, logo a contagem de linhas / âncora da 2ª run
  podia divergir. **Re-geração futura no robot** (re-exportar com o template novo +
  re-correr) quando o Rui mandar e o robot estiver livre. **Não fazer agora.**
- Cruza com a re-corrida WN do `#DERIVE-MAX-PLAYERS-WINAMAX-COLON-BLIND` (PENDENTES
  abaixo) — quando se re-correr, é com **ambos** os fixes (max_players + template 25/30).
- GG/PS/WN/WPN todas afetadas (o template é cross-site). Não há corrupção de dados
  na app; é a qualidade da **tree/âncora** que melhora com a re-geração.

## ✅ FECHADO (pt89, `90c07ad`) — `#GTO-OPEN-SIZE-NOT-PER-POSITION`

**Era FUTURO; foi feito em pt89.** Os opens passaram a **per-posição** (cada não-blind
tem a sua var `SIZES_OPEN_UTG/UTG1/MP/HJ/CO`, como os 3-bets em pt42b); o gerador faz
override **só** ao bucket do opener real, as restantes ficam no default do template `[2]`.
Acabou a propagação pela var partilhada `SIZES_OPEN_OTHERS`.

- **Regra do Rui satisfeita:** só o **opener** usa o seu size real; posições **à frente**
  usam o standard **2 BB**; a **SB** usa o seu próprio size de blind; posições atrás
  (foldadas) indiferentes.
- **Smoke do gerador PROVADO (25 Jun, read-only, sem HRC)** — `GG-6084129607` (HJ abre
  2.0bb, eff 18.02bb): `SIZES_OPEN_HJ = [2, ALLIN]` (ALLIN confinado ao opener curto);
  `SIZES_OPEN_UTG/_MP/_CO = [2]` (fundos 36.9/32.5/49.5bb **limpos, sem allin**).
  **Contaminação confinada ao HJ.**
- **Falta só o smoke da ÂNCORA no HRC** (navegação real ao nó) — para mão que flua
  naturalmente; **não** soltar mão de propósito.
- **Não afetou o `#HRC-NODE-OFFSET-IMPLICIT-LINES`** (o valor do size não gateia o offset,
  só o comprimento/ALLIN do array).
- Detalhe: `JOURNAL_2026-06-25-pt89.md`, `GTO_BRAIN.md §9`, `TECH_DEBTS pt89`.

## ★ FUTURO (registar, sem fix agora) — `#BEELINK-DAEMONS-AUTOSTART`

Arranque automático dos daemons do robot no Beelink. **Estende/subsome o
`#HRC-ADAPTER-SCHEDULED-TASK`** (TECH_DEBTS, 🟢 LOW, que cobre **só o adapter**) — esta
visão é mais larga: **adapter + watcher + watchdog**.

- **O que já está feito:** o lado da **APP**. O Rui abre a queue na app e a app comanda o
  que o robot puxa (gate da fila pt68, multi-select, `GET /api/queue/hrc`). Esse fluxo
  funciona.
- **A dor (o que falta):** o arranque **no Beelink** é todo manual e frágil — arrancar o
  adapter à mão (`arranca_adapter.bat` / `venv\python hrc_adapter.py`), ligar o watcher à
  mão (`hrc_watcher.exe`), e o PATH/env que não persiste entre reinícios (visto nesta
  sessão: o Claude Code do Beelink e o `setx` na janela errada). E os daemons **morrem em
  silêncio** sem ninguém os levantar.
- **Visão:** adapter + watcher arrancam **sozinhos** (no boot/logon do Beelink, ou num
  único atalho/serviço), para o Rui **só ligar o Beelink e abrir a queue na app** — zero
  comandos à mão.
- **Candidato técnico (confirmado read-only, faz sentido):** **Scheduled Task do Windows
  "ao logon"** para os dois. **Caveat-chave:** o **watcher precisa de sessão interactiva
  com desktop** (conduz o GUI do HRC por rato/Win32) → tem de ser **task ao logon a correr
  como `riand`**, **NÃO um Windows Service** (sem desktop). O **adapter é headless** (HTTP +
  filesystem) e podia ser serviço, mas por simplicidade vai como task ao logon ao lado do
  watcher. Cadeia: Beelink liga → **auto-logon** `riand` → task(s) arrancam adapter +
  watcher → o `ensure_hrc` do watcher abre o HRC. O env (`HRC_WATCHER_API_KEY`) viaja na
  task (ou no `.bat`), matando a fragilidade do `setx`.
- **Watchdog (incluir):** relançar um daemon que **morra**. (a) "restart-on-failure" nativo
  da Scheduled Task apanha o fim do processo; (b) uma 2ª task em intervalo curto que
  **verifica liveness** (processo vivo?) e relança — apanha também o caso de morte
  silenciosa. ⚠️ **Distinto** do `pt84` hang-watchdog INTERNO do watcher (esse trata o HRC
  pendurado/OOM **dentro** do watcher; não relança o **processo** watcher se este morre).
- **Custo grosseiro:** **BAIXO-MÉD.** Config (schtasks/XML do Task Scheduler), **não código**
  nos daemons; + config de **auto-logon** (registo/netplwiz — nota de segurança: sem gate de
  password numa máquina dedicada, aceitável); + watchdog (pequeno script/2ª task). A maior
  parte é **operacional no Beelink** + 1 validação (reiniciar → ambos sobem → queue funciona).
- **NÃO implementar agora — só registado.** Instruções base do adapter já em
  `tools/hrc_adapter/README.md`; o `tools/appmaster/RunAll.bat` (bat-mestre) é ponto de
  partida para o "único atalho".

## ★ pt85–pt86 (22-23 Jun) — re-corrida das trees Winamax contaminadas

Contexto: `#DERIVE-MAX-PLAYERS-WINAMAX-COLON-BLIND` ✅ fechado (`b7c3b08`,
deployed) — ver `JOURNAL_2026-06-23-pt85-pt86.md` + `TECH_DEBTS_INVENTARIO.md`.
O fix corrige a **geração** (mãos WN novas já saem com `max_players` certo,
provado read-only sem robot). Falta **re-correr o que já está contaminado**.

1. **Re-correr as 7 trees Winamax contaminadas** (quando o Rui mandar, com o
   **robot livre**). Sequência: **apagar SÓ os `hrc_jobs` destas 7** (NUNCA a
   tabela `hands`) → re-exportar (já com `max_players` certo) → re-correr no
   Beelink. **Lista dos 7 `hand_id`:**
   `WN-4850168930850832386-8-1781543237` (GRAVITY, max 2→3),
   `WN-4850168930850832391-177-1781554111` (2→6),
   `WN-4778368858757005322-248-1781557719` (2→5),
   `WN-4778368858757005442-9-1781564008` (2→6),
   `WN-4778368858757005442-14-1781564568` (2→5),
   `WN-4853541992006680581-17-1781626609` (2→6),
   `WN-4853547261931552780-74-1781630020` (…780-74, 2→4).
   **EXCLUIR `WN-4853541992006680581-53-1781629653`** (já correta — SB-vs-BB
   genuíno, max=2 certo, **não contaminada**). As **GG (17 done) ficam como
   estão** (têm dois-pontos, nunca foram afetadas).

2. **Validação à vista da página de verificação HRC** (pendente anterior,
   continua) — só retoma **DEPOIS** de as 7 estarem re-corridas com max certo (a
   árvore navegável da GRAVITY só fica "boa" então: o flat-call do SB passa a ter
   o nó do BB). A **decisão do flat-call na UI** (deixar a opção CALL sem ▸ vs
   pôr uma nota tipo "→ vai a flop, multiway não modelado") fica para quando a
   árvore estiver boa.

## ★ pt80 (18 Jun) — equity model FT/MTT

- **Onde o Rui vê o alarme de validação do equity model** (`#EQUITY-MODEL-FT-VS-MTT-VALIDATION`).
  A validação `validate_equity_model_vs_table_ss` (a SS de mesa do IT valida o modelo
  que a tag decidiu) já corre e regista o conflito em **dois sítios**: `logger.warning`
  (`[equity-validation] ALARME …`) + `manifest.hands_included[*].equity_validation`
  (None ou `{kind, equity_model, players_left, seats_at_table, looks_ft}`). **Falta
  decidir ONDE o Rui o vê** — coluna/badge no painel `/hrc`, no Estudo, ou um painel
  próprio. **Pode mexer em schema/UX → desenhar COM o Rui** (não decidir sozinho).
  Tipos de alarme: `ft_tag_but_multi_table` (tag FT mas várias mesas),
  `mtt_tag_but_single_table` (tag MTT mas todos numa mesa). Hoje: 0 conflitos reais
  (scan 91 mãos com SS de mesa). Ver `JOURNAL_2026-06-18-pt80.md`.

## ★ pt78 (18 Jun) — HRC pacote vazio / payouts Winamax (lobby SS)

Contexto completo em `docs/JOURNAL_2026-06-18-pt78.md` (arco: pacote HRC vazio →
payouts Winamax → upload de lobby SS).

1. ✅ **RESOLVIDO (pt81) — `#WN-LOBBY-NO-AUTO-RETRY`.** As mãos WN entram pelo **.bat do
   HM3 (`import_hm3`)**, que — ao contrário do `import_.py` — **não** re-corria
   `reconcile_lobby_logs` → os lobbys ficavam `tm_not_found` mesmo depois de as mãos
   chegarem. **Fix:** `import_hm3` (hm3.py) passa a disparar o mesmo gatilho fire-and-forget
   `reconcile_lobby_logs()` (o relink de SS de mesa órfãs já lá estava) → caminho HM3 igual
   ao `import_`/`tournament_summaries`. Ver `JOURNAL_2026-06-18-pt81.md`.

2. **Avisar à entrada quando um torneio entra SEM payout (não-pronto p/ HRC).** Hoje
   descobre-se só por **pacote vazio**. Inclui resolver o **mismatch `include_no_payout`**:
   o `POST /hrc/release` valida com `include_no_payout=True` (`queue.py:186`) → liberta;
   o `GET /api/queue/hrc` puxa com `include_no_payout=False` (`queue.py:96→124`) → dropa
   em `missing_payouts`. Resultado: **libertada mas não puxável**. Decidir comportamento
   canónico (bloquear release sem payout, ou sinalizar "à espera de payout" no painel/gate).

3. ✅ **FEITO (pt81) — religação a sério do lote 16-Jun.** Reconcile **scoped** (novo param
   `message_ids` no `POST /api/lobbys/reconcile`) corrido a sério sobre os **14** lobbys WN
   tm_not_found do lote: **12 escritos** (7 torneios, source `reconcile_lobby_vision:`),
   **2 still** (LATE REGISTRATION misread + ZENITH 15-Jun sem mãos), precedência OK
   (0 manual/backoffice sobrescrito), 4 GG intactos. Ver `JOURNAL_2026-06-18-pt81.md`.

4. **`tm_not_found` por resolver.** Casos a triar: **2 GG Bounty Hunters**, **ZENITH 15-Jun**,
   **William Harding** (este possível **misread da Vision** no nome do torneio). Re-Vision
   ou desambiguação manual.

5. **`limpa_scratch.bat`: `arquivo\` access denied** (snag operacional, POR RESOLVER) — ao
   mover `arquivo\` para o backup. Provável permissão `riand`↔`Administrator` ou handles
   abertos. A tentar: correr como `Administrator` / fechar HRC+watcher antes / `robocopy
   /MOVE` com retry. → `tools/hrc_adapter/limpa_scratch.bat`.

## ★ pt75 (18 Jun) — operacional

- **Cobertura de HH (Março/Junho) do backoffice.** A desanon por `position_v3` está pronta e
  a lane gold (`GOLD_DIR`→`/api/screenshots`) também, mas as gold images da Documents só
  desanonimizam quando a **HH correspondente** existir na app. As HH de Março e de 16-Jun **não
  estão importadas** (vivem no backoffice do Rui). **Ordem recomendada:** importar a HH primeiro,
  depois correr a gold lane → `position_v3` no match directo (a ordem inversa também dá
  `position_v3` via re-link, mas precisa na mesma da HH). Operacional, não código.

## ★ Fila de arranque da pt73 (fecho pt72, 14 Jun)

**Contexto fechado em pt72 (não repetir):** o **replayer-image GG morreu** (SPA Angular
sem og:image, todas as idades — `#REPLAYER-OGIMAGE-DEAD-SPA`); screenshot/headless
**descartado** (pesado/frágil/ToS incerto). Desanon GG = **só table-SS do IT**. 3 features
shipped (`70a2919` botão Sincronizar histórico, `6b8d09c` janela de datas appimport,
`f539cef` Dashboard nome-clicável). Detalhe: `JOURNAL_2026-06-14-pt72.md`.

Para a pt73:
1. **★ Classificador de tags por PASTA do IT** — **AUTORIZADO** (Rui, pt72). Tabela:
   `ICM`→`icm`, `ICM PKO`→`icm-pko`, `PKO Pos`→`pos-pko`, `NPKO Pos`→**`pos-nko`**
   (canónica existente — o Rui propôs `pos-npko` mas órfão de 21 mãos `pos-nko`;
   recomendado `pos-nko`; aguarda 1 linha de confirmação da grafia). FT auto em todas
   as famílias (`len(seats)==players_left`; fail-safe sem `-ft` se incerto;
   `pos-pko-ft` unifica com `pos pko FT` existente — sem órfão). Construção:
   (a) appimport itera **subpastas** de `it\` + injecta tag; (b) `folder_tag` no
   `/api/table-ss/upload` → aplica a `discord_tags` da mão casada (como `capture_triage.tag`)
   + guarda no log p/ reconcile; (c) `ALLOWED_TRIAGE_TAGS` += `pos-nko` + variantes `-ft`;
   (d) FT `-ft` prudente. Diff ao Web antes do push. Ver `JOURNAL pt72 §E/§F`.
2. **Concluir o Discord de maio 15-31** (`#DISCORD-MAIO-15-31-PENDENTE`) — sync até 31-mai +
   processar o sem-replayer; GG-só-replayer ficam anónimas até haver table-SS.
3. **★ VALIDAR o `-ft` automático nas primeiras FT reais** (pedido do Web, pt72) — a regra
   `len(seats_ocupados)==players_left → +"-ft"` está LIVE mas **nunca foi vista numa mão FT
   real** (no lote das 64 GG, 0 eram FT). Quando aparecer a 1ª captura de mesa final
   (`it\…` com bancos==restantes), confirmar que a tag sai `…-ft` correcta (ex. `icm-pko-ft`)
   e que a contagem de bancos ignora vazios. Fail-safe activo (incerto → sem sufixo). Se a
   Vision contar bancos a mais/menos, rever o `_ft_applies`. → `table_ss.py:_ft_applies`.

### Ajuste pt73 ao classificador (14 Jun) — ✅ FEITO (diff ao Web; falta correr `--ao-vivo`)

- **Tabela alargada** (`IT_FOLDER_TAGS`): + `ICM PKO FT`→`icm-pko-ft`, `PKO Pos FT`→`pos-pko-ft`,
  `SpeedRacer`→`speed-racer`, `Nota`→`nota` (4 faltavam → 34 capturas entravam SEM tag).
  `ALLOWED_TRIAGE_TAGS` += `speed-racer`, `speed-racer-ft`.
- **FT dupla, prioridade MANUAL > AUTO**: pasta já com `-ft` = FT confirmado (não re-verifica,
  não duplica sufixo); pasta base = `-ft` AUTO via Vision. `_folder_tag_ft_source` devolve
  `'manual'`/`'auto'`/`None`.
- **✅ Distinguir `-ft` MANUAL vs AUTO na app** (aprovado pelo Rui, pt73): coluna nova
  `hands.folder_ft_source` (`manual`/`auto`/NULL; `ensure_capture_triage_column`); escrita no
  table-SS (`_apply_folder_tag_to_hand`) e na triagem manual (tag `-ft` clicada = manual). Badge
  **âmbar "auto"** ao lado da tag `-ft` no `HandRow`; filtro **"-ft auto"** na Estudo
  (`list_hands`/`tag-groups` param `folder_ft_source`) para o Rui rever as adivinhadas.
- **✅ `Nota` sem formato/pré-pós — RESOLVIDO** (decisão do Rui, pt73): a tag `nota` sozinha
  basta (→ Vilões, regra C). Sem família de formato nem fase. Questão fechada.

### ✅ RE-IMPORT do 14 Jun — RECUPERAÇÃO CONCLUÍDA (verificado 16 Jun, pt73)

No `--ao-vivo` de 14 Jun a **Vision falhou 100%** (166 capturas `vision_failed`, 39 lobbys
"transitório"). **Causa confirmada** (teste directo à API com a chave de prod): Anthropic
**`400 invalid_request_error: "Your credit balance is too low"`** — saldo a zero. **NÃO é o
deploy** `a894703` (ilibado: 8 capturas tiveram `success` antes do saldo acabar; serviço
saudável, migração `folder_ft_source` correu no boot; rollback não resolveria). O
classificador de pastas funcionou (tags certas em todas as subpastas).
- **Acção do Rui:** ✅ feito — créditos carregados na conta Anthropic.
- **Retrato (verificado read-only, 15 Jun):** **120 capturas de 14 Jun**, todas `vision_failed`,
  `attempt_count=1`, **com `folder_tag` (120/120) + `img_b64` (120/120) + `original_filename`**
  guardados no `table_ss_processing_log`. **0 mãos desanon** (Vision falhou → sem match → tag não
  propagou a `hands.discord_tags`). As 1495 HH GG de 14 Jun estão na BD. **Nada perdido.**
  ⚠️ **Correcção:** os ficheiros **FORAM movidos para `done\`** (não "ficaram nas pastas" — eu
  tinha dito mal); `attempt_count=1` ⟹ nunca reprocessados (o re-import pós-créditos não lhes
  tocou, já estavam em `done\`).
- **✅ Recuperação 14 Jun CONCLUÍDA (verificado 16 Jun):** **120/120** capturas em `success`,
  `img_b64` guardado. Preview `GET /api/table-ss/reprocess-failed` = **0 eligible** → **nada a
  reprocessar**. Créditos já carregados. A ferramenta de reprocesso server-side existe (re-corre a
  Vision sobre o `img_b64` guardado → match HH → `folder_tag` → desanon; idempotente, `file_hash`
  PK; sem re-feed de `done\`) mas **não foi preciso disparar** — as 120 já tinham passado a `success`.
- **Snapshot verificado (`table_ss_processing_log`, 16 Jun):** **262 linhas** — **261 success, 1
  no_match_to_hand (12 Jun), 0 vision_failed**. Por dia: 05/1, 08/15, 09/36, 11/36, 12/4 (+1
  no_match), 13/3, **14/120**, 15/46 — todas `success`.
- **Observabilidade (✅ pt73, commit a):** `extract_table_ss_json`/`extract_lobby_payout_json`
  propagam o erro REAL da Anthropic para `reason_detail` (ex. "credit balance too low") em vez
  do genérico "devolveu None" — o próximo caso é óbvio no `/import-health` sem ir à API.

### Discord ReadTimeout no mesmo import — `#SYNC-ENDPOINTS-SYNCHRONOUS-TIMEOUT` (pré-existente)

O Discord sync deu **ReadTimeout (300s)** no mesmo import. É **separado** da Vision e
**pré-existente** (pt68, `#SYNC-ENDPOINTS-SYNCHRONOUS-TIMEOUT`): endpoint síncrono a estoirar
o limite num lote grande. Não tem a ver com o crédito Anthropic nem com o deploy de hoje.
Backlog: tornar os endpoints de import assíncronos (job + polling) — fora do âmbito da pt73.

### 🟥→✅ 502 do servidor (15 Jun) — replayer GG morto a prender o event loop — FIX pt73

Após o re-import (com créditos), a app deu **502** (containers "Online", mas o worker único do
uvicorn **bloqueado**). Causa real (watchdog dumpou a stack do event loop 3×, fundo em
`httpcore/_sync/ssl.recv`): `process_replayer_links` é `async` mas chamava
`_extract_gg_replayer_image` **síncrono no event loop**, 1× por entry replayer GG pendente —
cada um um fetch a `gg.gl→pokercraft` que **falha sempre** (SPA morto, `#REPLAYER-OGIMAGE-DEAD-SPA`).
Em lote (14 Jun), centenas a fio congelaram o worker. **Não era OOM nem crash-loop; não era o
deploy.** Rui reiniciou → estável.
- **✅ FIX (pt73, commit b):** flag `REPLAYER_IMAGE_DISCOVERY` (env, **default OFF**) +
  short-circuit em `_extract_gg_replayer_image` (zero rede); a chamada em `process_replayer_links`
  passa a `asyncio.to_thread` (nunca no event loop) + early-return quando off; `preview` reporta
  `pending_extract=0` (botão "Sincronizar histórico" não entra em loop). Fecha o lado **replayer**
  do `#SYNC-ENDPOINTS-SYNCHRONOUS-TIMEOUT`; o refactor async geral dos endpoints de import fica
  backlog. Reversível por `REPLAYER_IMAGE_DISCOVERY=1` se a GG repuser og:image.

### 🟡 BUG appimport — `_post_table_ss` move para `done\` mesmo em `vision_failed` (registar, corrigir depois)

`tools/appimport/app_import.py:_post_table_ss` trata **qualquer HTTP 200 como sucesso** e o
appimport move o ficheiro para `done\` — mas o endpoint responde 200 mesmo em `vision_failed`.
Resultado: capturas que **não** foram desanon foram movidas (e o `done\it\` é **achatado**, perde
a subpasta = a tag). Foi isto que assustou o Rui no 14 Jun. **Correcção (não agora):** o MESA deve
imitar o LOBBY — em falha **não mover** (deixar nas pastas para retry), distinguindo `success` de
`vision_failed`/`json_invalid`/`no_match` na resposta. Ver `_post_lobby` (devolve `retry` e não move).

---

## ★ Feito em pt71 (13 Jun) — desanonimização por table-SS

**FECHADO (não repetir):** pipeline de desanonimização por SS de mesa em **6 estágios**
(deployed) + **votação cross-mão por torneio** (validada por forense: hash-fixo-por-torneio,
0 violações cross-torneio) + **64 mãos GG renascidas** com nomes reais (confirmação visual
do Rui) na fila `/marcadas-por-captura` + lightbox + guarda epistémica na Saúde do Import.
Commits `79677fe`…`9442729`. Detalhe: `JOURNAL_2026-06-13-pt71.md`.

Follow-ups LOW (não-bloqueantes): `#TABLE-SS-DEANON-VILLAIN-NOTES-STALE`,
`#TABLE-SS-DEANON-SINGLETON-UNVERIFIED`, `#PLAYED-AT-COARSE-GRANULARITY` (TECH_DEBTS pt71).

## ★ Fila de arranque da pt71 (fecho pt70) — HRC (não tocado nesta sessão)

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
     table-SS **são guardadas** (`img_b64`; `#TABLE-SS-IMAGE-NOT-STORED` ✅ resolvido
     16 Jun) → re-Vision retroactiva **é** possível para esse caminho.

---

## Baixo prazo / qualidade

15b. **`#TABLE-SS-IMAGE-NOT-STORED` — ✅ RESOLVIDO (16 Jun, pt73).** **Era falso já:**
   o `table_ss_processing_log` **guarda** a imagem em `img_b64` (coluna `table_ss.py:194`;
   escrita no upload). Validado ponta-a-ponta na recuperação 14 Jun: **120/120** com
   `img_b64` + re-Vision a partir do guardado a funcionar (`/reprocess-failed`). **A
   re-Vision retroactiva é possível** — sem re-fornecer o ficheiro. Âmbito: caminho
   **table-SS** (o screenshot/replayer guarda `img_b64` em `entries.raw_json`, separado).
   Reforça o princípio de hoje (a imagem é a outra metade — `REGISTO_CONCEITO 2026-06-16`),
   já satisfeito aqui. Detalhe: entrada `#TABLE-SS-IMAGE-NOT-STORED` no `TECH_DEBTS_INVENTARIO.md`.

15c. **🟢 BAIXA (tracking, pt73) — 1 captura `no_match_to_hand` (12 Jun).** site/tn
   casados mas **sem mão correspondente** na BD. Leitura provável (**não verificada**):
   HH ainda não reimportado (reimport por fases) ou órfão. **Revisitar quando a fase do
   HH chegar**; **não** é `vision_failed` (fora do âmbito da recuperação de Vision).


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

## ★ Lane — Importador automático de replayer GG (ressuscitar a desanon) — **FIX-PRIMEIRO**

Lane nova (registada pt73, 16 Jun). **Não ligar a torneira antes do fix** — ver ordem abaixo.

**O quê:** um **importador automático** (irmão do `bat` HM3 / `appimport` / `appmaster`) que
lê imagens do **replayer GG** de uma pasta e as mete pelo **caminho de screenshot-por-nome**
(`screenshot.py:_parse_filename` + `mtt._match_screenshot`) → **ressuscita a desanon GG** agora
que o `og:image` morreu (pt72, `#REPLAYER-OGIMAGE-DEAD-SPA`).

**Porquê vale a pena:** a imagem do replayer é a **MELHOR fonte de desanon** — traz **SB/BB +
botão do dealer + Herói**, ou seja os **três critérios da âncora P2** (`DESANON_ANATOMIA §3.2.1`).
Melhor que o table-SS para alinhamento.

- **Persistir a imagem** — é a **outra metade do registo da mão** (tags + nicks); perdê-la =
  perder ambos para sempre. O table-SS já guarda `img_b64`; esta lane tem de garantir o mesmo.
- **P1 (qual é a mão)** = por **hand-id do nome** (o número TM imediatamente antes do timestamp),
  determinístico — decisão pt73 (`DESANON_ANATOMIA §2`).
- **P2 (quem senta onde)** = âncora SB+BB + botão (invariante) + Herói — `DESANON_ANATOMIA §3.2.1`.

**⚠️ ORDEM OBRIGATÓRIA — fix-primeiro-depois-acordar.** Antes de alimentar **mãos reais** por
este caminho:
1. **Corrigir o debt do nome** `#GG-DOWNLOAD-IMG-FILENAME-TIME-AND-BLINDS-UNRELIABLE` — tirar a
   **hora-de-download** e as **blinds** do nome do `_match_screenshot` (desempate) **e** do
   **`played_at`-fallback** (`screenshot.py:1565`). O único sinal fiável do nome é o **TM**.
2. **Corrigir a doutrina** — para estas imagens, a **Vision é a fonte das blinds**; o nome só
   dá o TM (reconciliar `CLAUDE.md:174` / `MAPA_ACOPLAMENTO §file_meta` / `VERIFICACAO_PIPELINES:516`).
3. **Só depois ligar a torneira** (apontar o importador a mãos reais).

> Nota: o **scan pt73** mostrou **0 mãos contaminadas hoje** (a superfície de screenshot-por-nome
> está vazia post-wipe + replayer morto). O caminho está **latente**, não activo — é exactamente
> por isso que se corrige **antes** de o reactivar, e não depois. → `#GG-DOWNLOAD-IMG-FILENAME-TIME-AND-BLINDS-UNRELIABLE`.

---

## #HRC-REIMPORT-REDEANON-CASADAS — 🔴 PRÉ-REQUISITO DO WIPE (subiu de prioridade em 3 Jul)

> **⚠️ Re-priorizado (3 Jul 2026).** Deixou de ser "melhoria futura, NÃO agora" (pt93). Com a
> decisão de **apagar + reimportar** todos os dados (ver `APA_INDEXACAO_E_COLAPSO.md` e o banner
> ★★ no topo deste ficheiro), este passa a ser **bloqueador do reimport**: sem ele, o reimport
> **parte a desanon de TODAS as mãos GG com captura já casada** (não só de 1 mão pontual). O
> "acidente 1 vez" descrito abaixo torna-se a regra no dia do wipe. **Fix a fazer ANTES do
> reimport:** o `import_` (e o `import_hm3`) re-dispararem a desanon por table-SS para mãos com
> SS **casada** (não só as órfãs `no_match_to_hand`).

Um **re-import de HH** repõe `all_players_actions` cru + esvazia `player_names.anon_map`
**sem re-disparar a desanon por table-SS**, porque o re-link só re-corre a desanon de SS
**órfãs** (`no_match_to_hand`), não de SS **já casadas**. Resultado: uma mão GG que já estava
desanonimizada volta a ficar com hashes (display) e, se for **PKO**, com **bounty achatado no
solve HRC** (a injecção casa por nome → miss → todos no base). Aconteceu **1 vez** (GG-6113994321,
por causa dos wipes/re-imports pt68/pt92). **Fix futuro:** o `import_` re-disparar a desanon para
mãos com table-SS já casada (não só órfãs). Diferido por decisão do Rui (pt93) — não empilhar nas
3 frentes em curso (gravação/âncora/bounty). O acidente actual resolve-se com **re-run** da desanon
da própria mão. Cross-ref: `DESANON_ANATOMIA`, `#HRC-ANCHOR-RAISE-AFTER-HERO-FOLD`.

---

## Cross-references

- `docs/TECH_DEBTS_INVENTARIO.md` — estado detalhado de cada `#TECH-DEBT`.
- `docs/GTO_BRAIN.md` — visão e roadmap do GTO Brain (3 fases).
- `docs/JOURNAL_2026-05-22-pt35.md` — sessão que fechou a Fase 1 do GTO Brain.
- `docs/JOURNAL_2026-05-22-pt30-pt34.md` — contexto da sessão que fechou a
  cadeia da 2ª run.
