# LIÇÕES — Problemas → Soluções → Êxitos

Registo **cumulativo, append-only**. Uma linha por lição: o **problema**, a **solução**,
e (quando aplicável) o **êxito**. Link ao journal da sessão. Acrescentar, nunca
substituir. Serve para não repetir erros e para reconhecer o que funcionou.

Formato: `- AAAA-MM-DD — **Problema:** … → **Solução:** … (→ journal)`

---

## 2026-06-10 (pt64–pt67) — → `docs/JOURNAL_2026-06-10-pt67.md` + `…-pt66.md`

- 2026-06-10 — **Problema:** run intermédia redundante no watcher (qualidade inconsistente). → **Solução:** removida — o Finish já lança a 1ª run → exatamente 2 runs.
- 2026-06-10 — **Problema:** watcher cego a runs curtas (`sleep(30)` engolia runs de ~4-5s). → **Solução:** vigília da janela de progresso **desde o Finish** por hwnd (sem heurísticas de tempo) → runs de 4s **VISTAS**.
- 2026-06-10 — **Problema:** CI escrito às cegas (e a salvaguarda lia o título, não o valor). → **Solução:** leitura do "Target CI" pelos **child controls** do dialog; watcher não escreve o CI.
- 2026-06-10 — **Problema:** Max Players contava participantes, não o span; e a re-smoke das 18:09 correu contra o backend **não deployado**. → **Solução:** lei do span âncora→BB (teto 6) **+ lição FLUXO §10** (fix de backend valida-se **deployado**, não com "push no fecho").
- 2026-06-10 — **Problema:** nó de navegação errado na 2ª run (off-by-one within-bucket). → **Solução:** convenção `offset_within_bucket` all-in-dependent (jam = nó ALLIN = último) + **desempate fotográfico** que **reescreveu a semântica** do Selected Subtree e **reativou a LEI B** (revelando que o veneno real é a **posição errada**, `#IMPLICIT-LINES`, não o within-bucket).
- 2026-06-10 — **Problema:** POST de resultado a dar 413 (zip 112 MB, medido pelo Rui). → **Solução:** diagnosticado como cap da **própria app** (50 MB), não edge (POST de 120 MB chega ao uvicorn) → cap a **200 MB** interino; `/hrc-sessions` como plano B.
- 2026-06-10 — **Problema:** `.bat` corrompido no Beelink (LF + acentos → cmd rebenta). → **Solução:** ASCII puro + CRLF + `.gitattributes` (`*.bat text eol=crlf`).
- 2026-06-10 — **Problema:** build Railway a falhar (mise sem binário pré-compilado p/ Python 3.13.14). → **Solução:** pin **Python 3.12** (`.python-version`) + `audioop-lts; python_version>="3.13"`.
- 2026-06-10 — **ÊXITO:** **1ª mão certificada ponta-a-ponta** (`#225`, `hrc_job 10`) — `app → adapter → watcher → 2 runs → resultado na BD`.
- 2026-06-10 — **ÊXITO:** deploy de binários por **GitHub Release de 1 clique** (SHA-check, 1 exe no Beelink) consolidado.
- 2026-06-10 — **ÊXITO:** **verificação visual do nó** promovida a **critério permanente** de toda a smoke de navegação (o que apanhou o off-by-one e desbloqueou a semântica).

## 2026-06-11 (pt68) — → `docs/JOURNAL_2026-06-11-pt68.md`

- 2026-06-11 — **Problema:** 502 "Application failed to respond" no `/api/import` parecia crash. → **Solução:** diagnosticar pela BD ANTES de re-tentar — as 4710 mãos estavam TODAS lá (import completo, **resposta perdida por timeout síncrono**, não memória/crash). Idempotente → re-try seguro mas desnecessário.
- 2026-06-11 — **Problema:** `Ctrl+W` para fechar a aba da mão no HRC. → **Solução (achado do Rui na fonte):** `Ctrl+W` é **chord de nova-mão** (Ctrl+W,E/M/H/S) — **NUNCA usar**; o fecho de aba é **`Ctrl+F4` + diálogo "Save Resource" → Don't Save** (Win32 BM_CLICK).
- 2026-06-11 — **Problema:** o watcher derailou de madrugada (avaria "súbita"?). → **Solução:** o padrão (setup-failed cold start → 3 OK → derail; ritmo 3→9 min) é **degradação PROGRESSIVA** por **acumulação de abas** (HRC não fecha a anterior — confirmado na fonte). Fix: fechar aba + reiniciar a cada N + health-check de cold start.
- 2026-06-11 — **Problema:** consola do watcher perdida → sem root-cause do incidente. → **Solução:** `#WATCHER-LOG-TO-FILE` subido a prioridade + entregue no exe pt68 (Tee → ficheiro com rotação). Esta noite provou o custo.
- 2026-06-11 — **Problema:** o Code andou a vasculhar o disco (Documents\Poker\GG…) à procura da GG. → **Solução (regra `FLUXO §11`):** só os paths listados; **a GG vem do BACKOFFICE do Rui** — pede-se, não se vasculha.
- 2026-06-11 — **Problema:** mtime das zips GG sugeria "sessão 04-05" (era 3-4 Jun). → **Solução:** espreitar o **conteúdo** (horas reais das mãos), não confiar no mtime.
- 2026-06-11 — **Problema:** `gh` ausente → "não consigo publicar a Release". → **Solução (correcção do Rui):** publicar pela **API REST do GitHub** com as mesmas credenciais do push (`git credential fill` → POST releases + upload assets). Validar: download anónimo 200 + SHA round-trip.
- 2026-06-11 — **Problema:** wipe irreversível. → **Solução:** backup logical **restore-verificado** ANTES (COPY → schema scratch → assert contagens) + cross-check de cobertura vs `information_schema` (zero gaps) + TRUNCATE atómico com assert-zero/rollback.
- 2026-06-11 — **ÊXITO:** **Saúde do Import v1** (`/import-health`) — instrumento de validação da própria Etapa 1.
- 2026-06-11 — **ÊXITO:** **Gate da fila v1** + **multi-select backend** (release forçado + states) — controlo de lotes do Rui sobre o robot.
- 2026-06-11 — **ÊXITO:** **exe watcher pt68** construído (swap_and_smoke ALL OK) + **Release publicada via API REST + validada** (SHA round-trip).
- 2026-06-12 — **PROBLEMA→SOLUÇÃO→ÊXITO:** deadlock "Activas" reincidente (mão 2 pós-fecho-de-aba) — o `open_wizard` OG assumia o wizard às cegas (`Wizard assumed`) quando o chord falhava → pipeline contra o vazio. Fix: wrapper `_open_wizard_confirmed` confirma via janela `Hand Setup` real + escada re-chord→restart→bail (cold start = único estado 100% fiável). Release `watcher-pt70` (`315CC2B5…`). → `JOURNAL_2026-06-11-pt69-pt70.md`.
- 2026-06-12 — **PROBLEMA→SOLUÇÃO→ÊXITO:** betting scripts com 3-bets fabricados sobre opens all-in (`2.3×shove`) + SB-shoves `8<eff≤25` sem size — destapados por auditoria visual + busca inversa (BD prod). Fix: LEI do Rui §18 (tabela open blinds, tabela 3-bet BB, B1 sobre all-in, ordem [size,ALLIN]). Validado contra as mãos reais + suite 935 verde. → `REGRAS_NEGOCIO §18`.
- 2026-06-12 — **LIÇÃO:** mudar `setup_hand` (open_wizard→wrapper) partiu 11 testes do watcher que só o **full-run** apanhou (o swap_and_smoke passou na mesma) — a confirmação autoritária nova exigia o mock no stub partilhado. Correr a suite completa antes de declarar verde, não só o harness.
- 2026-06-13 — **PROBLEMA→SOLUÇÃO (table_ss de-anon):** reutilizar a atribuição óptima do pt7 sobre bancos **sem stack** (≥2 ALL-IN/null) mapeia-os por **palpite** (diffs todos = stack vs 0 → permutação arbitrária) → nome trocado **envenena fichas de vilões** via tag 'nota'. → Afinação Web: dropar os bancos não-herói sem stack quando há ≥2 (`_filter_ambiguous_stackless`) → ficam **POR MAPEAR** (hash mantido) + `deanon_partial=true`. Teste documenta o **antes** (helper força) e o **depois** (filtrado deixa por mapear). **Nome em falta é honesto; nome trocado é veneno.** → `REGISTO_CONCEITO` 2026-06-13; `test_table_ss_deanon.py`.
- 2026-06-13 — **PROBLEMA→SOLUÇÃO→ÊXITO (swap inter-mão):** o dry-run das 64 destapou que o de-anon per-mão TROCA vilões de stacks próximos entre mãos do MESMO torneio (`881`: `4d2df37c` ora `hxnniUb` ora `justdoittttt`). → **Votação cross-mão por torneio** (maioria), fundada no **invariante hash-fixo-por-torneio** validado por forense ANTES de construir (gate do Rui: 0 violações cross-torneio em 1059 hashes). Corrigiu o `881` em prod. **Construir a votação SÓ depois de a forense provar o invariante** — não assumir. → `JOURNAL pt71 §C`.
- 2026-06-13 — **LIÇÃO (teste demasiado específico):** o 1º teste da votação assertou a grafia EXACTA do nick vencedor (`justdoittttt`), mas o desempate de contagem escolheu `justdoitttttt` (mais longa) — **ambas o mesmo jogador**. A votação **unifica** a grafia (sem fragmentação), por isso o teste deve validar o **cluster/identidade**, não a contagem de 't'. Assertar a propriedade que importa (não é hxnniUb / é justdoit*), não o cosmético.
- 2026-06-13 — **LIÇÃO (forense vs intuição):** o 1º teste de veneno ("mesmo hash <120s em mesas diferentes") deu 22 "violações" — mas **3 hashes movem-se juntos** m19→m7 = quebra de mesa, não reuso; e o 1 residual tinha **hand-ids a distar ~894k** (impossível em 62s) = artefacto de timestamp. **O teste decisivo foi a continuidade do stack na mudança** (≤1.6x = move). Quando um teste forense dispara, validar a ASSINATURA (movem-se juntos? stack transita? hand-id plausível?) antes de gritar violação. → `JOURNAL pt71 §C`.
- 2026-06-13 — **LIÇÃO (backfill prod = código deployado):** as 64 reprocessaram-se com um script LOCAL que importa o código já DEPLOYADO (`DATABASE_URL`=proxy → `app.db` escreve na prod) — não lógica re-escrita no script. Mantém a integridade do FLUXO §10 (valida-se o que está em produção) e é reversível (idempotente). Batch pequeno primeiro (3 do swap) + read-back antes do resto (61).
- 2026-06-23 — **PROBLEMA→SOLUÇÃO (cego de formato por sala):** a árvore navegável de verificação HRC (GRAVITY) não expandia o "SB call" — faltava o nó do BB. Causa-raiz: `derive_max_players._ACTION_RE` exigia `": "` (formato GG/PS), mas a **Winamax escreve sem dois-pontos** → 0 matches → âncora nunca detectada → fallback silencioso a `max=2` → **TODA** a WN exportada saiu colapsada a heads-up (`maxactive=2`, multiway cortado + ICM ao nº errado). → Fix `": "`→`:?\s+` (1 só sítio cego; os outros 7 regexes de acção já eram colon-opcionais). **LIÇÃO:** um regex de parse de HH com colon **obrigatório** é um cego por-sala — a Winamax/WPN não têm dois-pontos. Ao tocar/auditar parse de linhas de acção, varrer TODOS os sítios numa passagem e alinhar com os já-colon-opcionais (`hrc_verify_tree`, `hrc_script_gen`). E: um **fallback silencioso** (cair em 2 sem sinal) esconde o estrago — uma feature de **verificação à vista** (a árvore navegável) foi o que o destapou. Distinto do `#HRC-MAX-PLAYERS-SPAN-NOT-PARTICIPANTS` (pt67, span-vs-participantes). → `JOURNAL_2026-06-23-pt85-pt86.md`, `#DERIVE-MAX-PLAYERS-WINAMAX-COLON-BLIND`.

## 2026-06-25 (pt89) — → `docs/JOURNAL_2026-06-25-pt89.md`

- 2026-06-25 — **ÊXITO (smoke do gerador prova o fix sem HRC):** o `#GTO-OPEN-SIZE-NOT-PER-POSITION` validou-se gerando o `script.js` da mão alvo (`GG-6084129607`) com o gerador de produção e lendo as linhas `SIZES_OPEN_*` — `SIZES_OPEN_HJ=[2,ALLIN]` (opener curto 18bb), fundos `UTG/MP/CO=[2]` limpos. Contaminação confinada ao opener, **sem** soltar mão nem correr o HRC. **LIÇÃO:** para um fix de gerador (sizings/arrays), o smoke do GERADOR (read-only, ler o `.js` produzido) é prova suficiente e barata; o smoke da âncora no HRC é um passo separado, reservado para mão que flua naturalmente (não soltar mão de propósito). → `JOURNAL pt89`.
- 2026-06-25 — **PROBLEMA→SOLUÇÃO (doc stale após fix shipped):** o `#GTO-OPEN-SIZE-NOT-PER-POSITION` ficou corrigido em `90c07ad` mas `PENDENTES`/`GTO_BRAIN §9` continuaram a listá-lo como "FUTURO, sem fix", e não havia entrada de fecho em `TECH_DEBTS`. **LIÇÃO:** ao fechar um tech debt que estava registado como FUTURO/aberto, atualizar os 3 sítios na mesma sessão (PENDENTES + doc-âncora + TECH_DEBTS) — senão o doc mente ao próximo Claude (CLAUDE.md "Reconfirmar tech debts"). → `JOURNAL pt89`.

## 2026-06-25 (pt89) — → `docs/JOURNAL_2026-06-25-pt89.md`

- 2026-06-25 — **PROBLEMA→SOLUÇÃO (`#HRC-ADAPTER-STATE-DESYNC-SILENT`):** re-enviar uma mão pela app não a fazia correr, sem erro nenhum — o `/hrc/release` usava `ON CONFLICT DO NOTHING`, logo o `requeue_epoch` nunca subia num re-envio e o adapter saltava a mão em silêncio (dedup `served_epoch <= stored`, `hrc_adapter.py:262`). → **Fix server-only:** `ON CONFLICT DO UPDATE` com `requeue_epoch += 1` → o adapter re-puxa sozinho (mecanismo de epoch já existia da pt83). **LIÇÃO:** um `DO NOTHING` num UPSERT idempotente esconde a intenção de "re-fazer" — quando há um contador que destrava o consumidor a jusante (aqui o epoch do dedup do adapter), o re-envio TEM de o incrementar, senão o no-op vira skip silencioso. Antes do fix, confirmar o **consumidor único** do campo (grep) garante que o bump não tem efeitos colaterais. → `JOURNAL pt89`; `bf2da9a`.

## 2026-06-25 (pt90) — watcher OCR tree-size (#HRC-TREE-GIGANTE)

- 2026-06-25 — **LIÇÃO (sinal de confiança certo):** para abortar trees gigantes, o tempo de construção é um sinal MORTO (gigantes 2-3s, normais <1s — janela demasiado estreita; o 1º limiar proposto de 5s estava acima das próprias gigantes → nunca dispararia). O sinal fiável é a **dupla leitura do OCR**: erro de OCR é aleatório e não se repete igual, por isso duas leituras concordantes em >15GB são de confiança; discordância = instável = não abortar. **Generalizável:** quando uma medição é ruidosa, repetir-e-concordar bate um threshold sobre um proxy enviesado.
- 2026-06-25 — **LIÇÃO (build winsdk/winrt + PyInstaller):** o `.exe` empacota o próprio Python, por isso a versão do Beelink (3.14/winrt) não obriga o build — venv 3.12 + **winsdk** chega (dual-import `try winsdk / except ImportError → winrt` cobre ambos). Bundle exige `collect_all('winsdk')` (namespace packages) + **`--hidden-import tree_stats`/pathex** (lazy-import → o auto-analyzer não o vê) + **UPX OFF** (nativos do winsdk corrompem com UPX). **VERIFICAR o bundle por TOC** (tree_stats + winsdk OCR presentes) antes de declarar pronto — senão o `.exe` corre mas a guarda fica fail-open-morta. → `JOURNAL pt90`; Release `watcher-pt90`.
- 2026-06-25 — **LIÇÃO (gh release create):** `--target` rejeita SHA curto (`HTTP 422 target_commitish is invalid`); usar o **SHA completo** (ou o nome do branch). E o `gh` recém-instalado pode não estar no PATH da shell já aberta → chamar por caminho completo (`C:\Program Files\GitHub CLI\gh.exe`).

## 2026-07-02 — desanon: sentado-sem-cartas (N+1) + apa vs anon_map

- 2026-07-02 — **Problema:** `GG-6083771298` mostrava um jogador errado (`Afonso Neto`) numa cadeira e nomes deslizados — um jogador **sentou-se mas não jogou a mão** (sem cartas) → a Vision da Gold leu **N+1 nomes** (6) vs **N cadeiras** da HH (5). → **Solução:** correcção manual via `/set-anon-map` (5 seats por posição, ground-truth do Rui, `Afonso Neto` fora) + coroas do Rio UTG→BB. **Diagnóstico-chave:** o `anon_map` estava **CERTO** (o `position_v3` por rótulo descartou bem o sem-cartas); só o `all_players_actions` estava **stale/corrompido**, escrito por um caminho de ORDEM que deslizou e colapsou um seat (5→4). Ler o apa E o anon_map (`/deanon-debug` vs `/hand-seats`) destapou a inconsistência que uma única vista esconderia.
- 2026-07-02 — **LIÇÃO (guarda não-universal):** a salvaguarda "img≠HH → alarme" **só existe no método ÂNCORA do table-SS** (pt96); o `position_v3` e o caminho order/stack **não têm** guarda N+1. Um badge `deanon_status=verified` deriva do `match_method`, **não** da consistência real do apa → uma mão pode estar "verificada" com o apa silenciosamente errado. **Ao tocar em desanon/enrich: tratar img≠HH como sinal duro em TODOS os caminhos e assertar apa↔anon_map (seats == hashes da HH).** Registado `#DESANON-SITTING-OUT-NPLUS1-NO-UNIVERSAL-GUARD`; caso em `DESANON_ANATOMIA §3.2.4`.
- 2026-07-02 — **LIÇÃO (o fix automático deixou um resíduo honesto):** esta mão era a **"1 diverge"** que o `reenrich-scrambled-gold` (#DESANON-GOLD-SCRAMBLE) **recusou escrever** — o gate de fichas FINAIS divergiu (stacks Gold em unidade inconsistente / momento fim-vs-início). O gate conservador **acertou em não escrever às cegas**; o desbloqueio é o **override manual confirmado pelo Rui** (`/set-anon-map`, sem o gate). Um skip de gate não é "esquecido" — é dívida à espera de confirmação humana.

## 2026-07-09 — re-leitura de coroa agarrou a do vizinho num jogador ELIMINADO (verde-KO)

- 2026-07-09 — **Problema:** a re-leitura de coroas agarrava a coroa do seat **VIZINHO** e colava-a num
  jogador **ELIMINADO** (sem coroa própria) → bounty errado gravado **em silêncio** (GG-6140169166: o Hero
  levou o **$170.63** do KamikazzE97). Um "arranjo completo" anterior ficou só **DOCUMENTADO** (armadilha
  verde-KO no CLAUDE.md, caso arieloo/mirroring GG-6114944767 pt95), **nunca construído+verificado** →
  **recorreu semanas depois**. → **Solução:** mudar o **método** — a garantia de não-contaminação vive numa
  guarda **DETERMINÍSTICA pela HH** (nunca na Vision), num **chokepoint único** (`services/eliminated_bounty.py`);
  "completo" passa a exigir **teste de aceitação com mãos reais nomeadas + validação DEPLOYADA (§10)**, não
  "em buffer". O bónus (ler o verde) é secundário; as raras entram **à mão**. → êxito a confirmar no
  **reimporte** (eliminados-contaminados ~0).

## 2026-07-09 — cura verde-KO: lista provada + mãos reais + gate duro no ar (não "em buffer")

- 2026-07-09 — **Problema:** a re-leitura de coroas colava a coroa do seat **VIZINHO** num
  jogador **ELIMINADO** → bounty errado gravado **em silêncio** (GG-6140169166: Hero levou
  $170.63 do KamikazzE97). Um "arranjo completo" anterior ficou só **DOCUMENTADO** (armadilha
  verde-KO no CLAUDE.md) e **recorreu semanas depois**. → **Solução:** método com (a) lista de
  escritores **PROVADA-completa** — a varredura apanhou o **`reread_gold_crowns`**, o próprio
  culpado, que os 4 sítios nomeados deixavam de fora; (b) **teste em mãos reais nomeadas**
  (GG-6140169166/GG-6139653123); (c) **gate duro (contagem=0) DEPLOYADO**
  (`vision_origin_contamination`). → **ÊXITO:** contaminação das tagadas **29→0** em prod;
  a mão-troféu lê **$204.54**, nunca $170.63. **LIÇÃO:** "completo" só conta com **lista provada
  + prova em mãos reais + gate duro no ar** — não "em buffer" nem "documentado". (Reforça a lição
  de 2026-07-09 anterior — o arranjo só-documentado que recorreu.)

- 2026-07-09 (noite) — **Ausência num painel a jusante ≠ bug do painel.** O Rui notou "0 mãos
  Speed Racer no HRC". O gate do HRC estava **certo** (só aceita mãos com etiqueta de estudo); a
  causa real era **a montante** — a etiqueta `speed-racer` **nunca aterrou** (0 prints com pasta;
  todos soltos por web). **LIÇÃO:** quando algo falta num painel, seguir o **pipeline da condição**
  (aqui: a etiqueta), não só o filtro do painel. Confirmar na fonte + com dados reais (contámos as
  218 mãos, os 31 prints por source, os 0 folder_tag) antes de concluir.
- 2026-07-09 (noite) — **Coroa gravada sem perguntar "este torneio tem bounty?".** A raiz das coroas
  espúrias num vanilla foi um **writer sem gate** (`_seats_to_vision_data` copiava o `bounty_usd` da
  Vision para cada seat). **LIÇÃO:** o valor da Vision é palpite; a guarda vive no **funil único**
  (com o sinal autoritativo do TS), não espalhada por cada escritor — foi assim que a vivo-$0 e a
  vanilla entraram no mesmo chokepoint da verde-KO, e não em N sítios.
- 2026-07-09 (noite) — **Diagnóstico só-na-conversa mente ao próximo Claude.** O
  `#TABLE-SS-SPEEDRACER-NO-MATCH` estava registado como "HH em falta" (metade); a versão completa
  (dois bloqueios: no-match + etiqueta inexistente) vivia só no chat. **LIÇÃO:** ao evoluir um
  diagnóstico, reescrever a versão final nos **docs vivos** (PENDENTES) na mesma sessão.

- 2026-07-09 (noite) — **O nosso próprio processo fabricava a doença.** O move do appimport
  **achatava** o `done\it` (`it\<SUB>\x → done\it\x`), destruindo a subpasta — e a subpasta É a
  etiqueta. Um reimporte a partir do `done` nasceria TODO sem etiqueta (a mesma doença que
  investigávamos no Speed Racer). **Descoberto pelo Rui**, não pela suite. **LIÇÃO:** o `done`/arquivo
  não é lixo — é **matéria-prima do reimporte**; qualquer passo que MOVA dados tem de preservar o que
  os classifica (aqui, a subpasta). Ao curar, garantir o **round-trip** (guardar → reler dá o mesmo)
  com teste nos dois sentidos, e **não adivinhar** o que já se perdeu (prints sem tag na BD ficam na
  raiz — branco honesto).

- 2026-07-10 — **Dedup que descarta metadados = perda silenciosa.** O atalho de dedup do table-SS
  (mesmo file_hash → sai cedo) deitava fora a `folder_tag` de um re-envio → mãos ficavam sem etiqueta
  em silêncio (as 3 Speed Racer). **LIÇÃO:** um caminho de "já processado" tem de reconciliar os
  metadados NOVOS que o pedido traz (aqui a tag), não só devolver o antigo — sobretudo antes de um
  reimporte que gera duplicados em massa.
- 2026-07-10 — **Diagnóstico refuta hipótese: seguir o gate real, não o nome do campo.** A hipótese
  "IRE morto porque exige `bounty_pct` (que deixou de gravar)" caiu ao ler o gate: o IRE usa a COROA
  (ko_units), não a chama; a mão "sem IRE" estava só tagada 'nota' (fora do âmbito KO). **LIÇÃO:**
  medir (taxa pré/pós) + correr a função real sobre a mão concreta ANTES de aceitar a causa — a
  premissa plausível estava errada.

- 2026-07-10 (fecho do lote da auditoria) — quatro lições:
  - **(a) Um "duplicado" não é um no-op.** O dedup do table-SS saía cedo e engolia a `folder_tag` do
    reenvio → mãos sem etiqueta em silêncio. O que o reenvio traz de NOVO (a tag) tem de ser
    reconciliado, não deitado fora — sobretudo antes de um reimporte que gera duplicados em massa.
  - **(b) Um sinal que motivou uma decisão não a pode reacordar.** O print Info pré-existente
    reacordava a dispensa FT a cada refresh (zombie). Só sinal POSTERIOR à decisão conta.
  - **(c) Resolver por nome+dia sem HORA é palpite quando há edições múltiplas.** Os Daily têm 2+
    edições/dia (mesmo nome, `start_time` diferente). A janela REAL com prova (`start_time` do TS +
    janela de mãos) é o método; "hora mais próxima" seria adivinhar. Em falta → quarentena (honesto);
    colar às cegas → veneno (payout na edição errada).
  - **(d) Smoke com contagem COMPLETA de proveniência > amostragem.** Verificar os 5/5 solves +
    varrer TODOS os lobbys (114) + confirmar 0 solves nas edições mal-coladas dá certeza; olhar
    a 1-2 mãos não.

## 2026-07-11 — Raiz 2 (resolver de edições)

- **Prova > palpite, e o sinal certo estava no vision_json o tempo todo (`entrants`).** A
  desambiguação de edições parecia precisar de heurísticas de tempo frágeis; o disambiguador limpo
  era o `entrants` (total de inscritos) que TODOS os 85 lobbys GG já traziam: `entrants > campo final
  da edição` é **impossível** (H2) e apanhou 3 contaminações reais (BH$88) que o modelo temporal
  deixava colar. Antes de inventar heurísticas, ver que campos os dados já têm.
- **A régua da impossibilidade é UNIDIRECIONAL.** `entrants > campo` prova (exclui); `entrants <
  campo` NÃO prova nada (print antes de fechar inscrições). Um desempate "entrants mais próximo do
  campo" não pode colar sozinho → quarentena. (Ressalva do Rui, incorporada.)
- **Fuso é uma armadilha silenciosa.** O `posted_at` do lobby está em **UTC**; `start_time`/
  `played_at` estão em **Lisboa naive**. O resolver antigo tolerava o −1h porque as janelas eram de
  12h; uma prova apertada (±45–120min) obriga a converter a âncora UTC→Lisboa. Janela larga esconde
  bugs de fuso.
- **Divergência da prévia ≠ erro — reportar, não ajustar em silêncio.** O modelo forte deu 5
  corrigidos vs 2 da prévia; os +3 eram provados (entrants). Reportar a divergence com a prova e
  pedir a decisão (o Rui escolheu o modelo forte) > forçar os números da prévia.
- **O crivo prova-se a apanhar um real logo à 1ª.** `lobby-edition-scan` acusou 1 contaminação
  verdadeira (294738291) na 1ª corrida — o gate duro funciona; um crivo que nunca acusa nada não
  está a ser testado.

## 11 Jul 2026 — Vision, fuso e o olho de jogador (Raiz 2 + prompt + provas)

- 2026-07-11 — **Problema:** suspeita de que a Vision lia a POSIÇÃO do Hero como `entrants` nos
  lobbys → provas de edição (H2/igualdade) assentes em areia. **Solução:** carimbo VISUAL — as
  imagens não estão na BD, mas vivem em `Batmen\done\lobby`; casei-as por `sha256` (=
  `discord_message_id`) e **abri-as eu próprio** (Read renderiza imagem). 3 GG + 1 WN: o rótulo é
  **`Players Left: <left> / <entrants>`** (GG, corroborado por `Unique+Re-entry`) / `Players
  <left>/<entrants>` (WN); a posição/RANK do Hero é um campo SEPARADO que a Vision não lê. Suspeita
  **desmentida**; entrants está certo; a correção do 294738291 (305>219) aguenta.
  **→ Lição (a): um campo de IA sem semântica verificada contra o ecrã é uma bomba latente** —
  fechar o loop abrindo a imagem real, não só olhando o número gravado.
- 2026-07-11 — **Problema:** painel de edições com −1h (print SR$32 Level 1 às 20:10 mas edição
  candidata dizia start 19:10). **Solução:** `start_time` do TS em UTC vs tempos de print em Lisboa,
  comparados/exibidos sem normalizar (o fantasma GG conhecido). Normalizar tudo a Lisboa na
  exibição E nas comparações. **→ Lição (b): motor certo + montra torta = desconfiança evitável —
  a exibição converte SEMPRE fusos e declara-os.**
- 2026-07-11 — **Êxito:** o **olho de jogador do Rui** ("um hyper 10BB não está no Level 1 uma hora
  após o start") apanhou o bug de fuso que nenhuma suite tinha. **→ Lição (c): a intuição de
  domínio do Rui vale por uma suite — quando ele diz "isto é fisicamente impossível", é um teste.**
- 2026-07-11 — **Solução (provas novas, regressão-zero por construção):** H5 (igualdade dura:
  entrants == campo EXACTO de 1 edição, ≠ das outras, corroborado por ≥2 prints) + H6
  (impossibilidade temporal: eliminados implicados vs tempo desde o start) só actuam no ramo
  AMBÍGUO, DEPOIS do `hand_window_contained` — convertem quarentena→cola, nunca mudam uma cola
  existente. Prompt endurecido pelos rótulos reais + `reg_open` (a igualdade só é fiável com reg
  fechada; os 6 da quarentena eram capturas de late-reg com contagem parcial, não misreads).

## 11 Jul 2026 (tarde) — correlação ≠ causa (coroas)

- 2026-07-11 — **Problema:** ao explicar o flame-as-crown, propus uma causa VISUAL ("chama e
  coroa coladas em stacks curtos" / "chama saliente no avatar") a partir de uma correlação
  (97% das suspeitas em stacks curtos) — **sem ter aberto uma única imagem**. O Rui corrigiu:
  no layout GG os elementos da mesa **não** mudam de tamanho/posição com o stack; a explicação
  era especulação. **→ Solução/Lição: correlação NÃO é causa. Uma explicação visual plausível
  quase entrou nos docs (REGISTO_CONCEITO) sem ninguém ter olhado para um pixel.** Retirada dos
  registos. Regra: só escrever causa depois de confirmar na imagem/dados; separar SEMPRE o facto
  (correlação medida) da hipótese (porquê). A guarda protege independentemente da causa — a causa
  fica para quem olha as imagens.
- 2026-07-11 — **Êxito colateral:** ao ABRIR as imagens (da BD, não do disco OneDrive) o quadro
  mudou: as "46-60 suspeitas Gold" eram falsos positivos (coroa fresca base÷2 == VPIP) + omissão
  $0; o erro real é table-SS (55 seats, 15 mãos), Gold escreve 0 impossíveis. Olhar a imagem
  desfez uma conclusão errada tirada só dos números.
- 2026-07-11 — **Problema (o de fundo):** o prompt da Vision descrevia um **"gold crown badge"**
  colado ao avatar — elemento que **NÃO existe** na GG (o bounty vive na placa de $ acima do
  avatar; a única badge é a chama = VPIP). Este prompt errado **sobreviveu a DUAS curas** anteriores
  do flame-as-crown (pt95 + a guarda base÷2) porque cada cura mexeu na jusante (guardas, gates,
  rellink) e **ninguém pôs a descrição ao lado de uma imagem real**. Foi o **Rui a olhar o ecrã**
  que viu que a coroa descrita não existia. **→ Lição: um prompt de Vision é código que descreve um
  ecrã — valida-se comparando a LETRA com uma IMAGEM real, não relendo o texto. Duas curas trataram
  sintomas a jusante de um prompt que descrevia um elemento imaginário; a raiz só cai quando se
  confronta a descrição com o pixel.**
- 2026-07-11 — **Êxito:** a **grelha aritmética** (2º critério da guarda) parecia sólida no papel
  (coroas = base×k/2ⁿ) mas o **teste de aceitação ao vivo** apanhou-a a NULLar o **259.37 real** do
  Lucas — coroas progressivas/rake não são dyadic. **→ Lição: uma guarda "matematicamente elegante"
  só se aprova contra dados reais; o teste com a Vision real sobre a imagem real matou a grelha antes
  de ela corromper produção. Testar ao mais alto nível (Vision real, imagem real) > raciocinar sobre
  a forma dos valores.**
- 2026-07-11 — **Problema (âncora sem validação do ponto de partida):** 7 mãos com o nome do Rui
  ("Lauro Dermio") num hash-vilão. Raiz: a Vision do table-SS marcou um VILÃO como `is_hero`
  (baixo-centro) — 'R Sanchez' em 6 mãos (HR $525), 'buildthepot' na 7ª (Daily $88). A âncora
  (`build_anon_map_by_hero_button`) confia cegamente no `is_hero` e fixa `anon_map["Hero"]` a esse
  nick → **swap de 2 vias**: o Hero (Lauro) fica com o nome do vilão e o vilão com o nome do Hero.
  Pior: nas 6, **1 leitura má (a que trocou) venceu 5 boas** — a propagação de nomes por hash
  espalhou `2223abd8 = Lauro` do único capture mal lido para os outros 5 que tinham lido o Hero
  CERTO. **→ Lição: uma leitura má vence N boas se a âncora não valida o PONTO DE PARTIDA. Uma
  âncora só é âncora se se validar contra verdade CONHECIDA — aqui, o `is_hero` das capturas do Rui
  É SEMPRE uma conta HERO_NICKS; se não é, é misread, alarme, não escreve.** Guarda posta (tolerante
  a truncação da Vision). As outras salvaguardas (contagem, direção por botão/stacks, nicks
  distintos) passaram todas porque a ROTAÇÃO estava certa — só o ponto de âncora estava errado; nenhuma
  olhava para a verdade conhecida "o baixo-centro é o Rui".
- 2026-07-11 — **Êxito (consistência = prova):** a re-leitura devolveu 7 coroas "implausíveis"
  (10–21×base). Antes de alarmar, reparei que vinham em **pares idênticos** (mãos consecutivas do
  mesmo torneio: Puntti $5324 nas DUAS mãos do HR Main Event) — sinal de **leitura consistente, não
  ruído**. O Rui confirmou à vista: **7/7 reais**. **→ Lição: valores repetidos entre capturas
  independentes do mesmo estado são EVIDÊNCIA de leitura verdadeira, não de erro. Flaguei para o olho
  humano em vez de reverter — e estava certo. "Implausível pelo tamanho" ≠ "errado"; separar sempre
  o invulgar do inválido.** Corolário: a coroa alta não tem guarda automática (a base÷2 só apara
  baixos); fica **grupo de confirmação** (não suspeita) com carimbo manual antes do export.
- 2026-07-12 — **Retração própria: "recuperável" só se declara depois de VALIDAR A ÂNCORA, não só a
  presença de nomes.** Ao ver as 13 golds sem-nomes de 26/06, classifiquei 9 como "recuperáveis" só
  porque tinham uma table-SS ligada com nicks + o Rui presente. **Estava errado.** Ao correr o
  `/redeanon` de facto: **0/9 nomearam** — TODAS deram `review_alarm` (6 por `seat_count_mismatch`
  SS>HH, 3 por `button_stack_direction_disagree` com contagens iguais, 1 por `hero_not_rui_account`).
  Ter nomes + Rui é NECESSÁRIO mas não SUFICIENTE: a âncora ainda pode falhar por contagem, direção
  ou hero mal lido. **→ Lição: nunca prometer "recuperável" a partir de um pré-requisito parcial;
  ou corro a âncora e reporto o resultado real (nomeou vs alarme), ou digo "candidato a testar",
  nunca "recuperável".** É a mesma família da lição da âncora (11 Jul): uma condição só vale depois
  de validada contra a verdade, não por presença de sinais soltos. Corolário que salvou o caso: a
  raiz real não era a table-SS (que não alinha) mas a **Gold nunca lida** (`vision_done=false`) — a
  1ª leitura do gold no formato atual de-anonimiza pela via premium (`position_v3`), validado ao vivo
  na GG-6117480341 (5 nomes, Hero=Lauro).
- 2026-07-12 — **N conflitos podem ser 1 captura podre — agrupa por FONTE; os STACKS são o
  árbitro.** No tn 292179612, 6 dos 7 conflitos do painel "Nomes em conflito" vinham de UMA
  captura table-SS (GG-6100838605, ctx=782) cuja âncora **rodou a roda** (ponto/direção off →
  cada seat recebeu o nick do vizinho). A UI oferecia 6× "confirma o forte" — tedioso E
  perigoso: se o forte fosse o rotacionado, confirmar gravava o erro. **A prova objetiva são
  os STACKS:** os nomes+stacks da Vision estavam CERTOS; alinhados por stack davam 8/8 o mapa
  forte — foi só o mapeamento nome→hash que rodou. **→ Lições:** (1) quando ≥3 conflitos de um
  torneio partilham uma captura que discorda do mapa forte, é UMA captura podre, não N
  desacordos — agrupar por fonte e oferecer 1 ação (reverter a captura), não N confirmações;
  (2) os stacks são o árbitro objetivo — validar sempre o mapa nome→hash contra os stacks da
  HH (uma rotação mostra todos os stacks trocados); (3) "forte" (position_v3) não é imune —
  confirmar só depois do cross-check por stack. Curas: guarda de stacks no de-anon
  (`build_anon_map_by_hero_button`, alarme `stack_map_mismatch`), prune de quarentena stale
  (a captura revertida faz cair os N conflitos), detetor de rotação no painel
  (`/names/rotation-scan` → "reverter captura podre"). Ver `REGISTO_CONCEITO 2026-07-12`.
- 2026-07-13 — **Detetor novo SEM tolerância a truncação = falsos positivos em massa.** O
  detetor de rotação contava nome TRUNCADO da Vision ('Tobias Schwecht'→'Tobias Schw..') como
  troca de vizinho → **7 de 9 "capturas podres" eram truncação, não rotação** (7 capturas boas
  quase revertidas). O **"devo confiar?" do Rui salvou-as** (parou antes de reverter). **→ Lição:
  qualquer detetor que compare nomes tem de ser tolerante a truncação (prefixo, mín 4 chars —
  como a guarda da âncora) ANTES de acusar; uma rotação exige nomes DIFERENTES entre si (a,b→b,a),
  não encurtados.** Fix: `_same_name_trunc` no `/names/rotation-scan` (9→0). Ver `JOURNAL_2026-07-13`.
- 2026-07-13 — **Nunca oferecer "confirmar" quando TODAS as variantes estão truncadas.** No caso
  `Andre Figue..` as duas candidatas são cortes do mesmo nome; o "confirmar o forte" gravaria uma
  grafia arbitrária. **→ Lição: quando o conflito é só truncação (sem nome-cheio para arbitrar), a
  UI deve oferecer "nome manual / fundir variantes", não "confirmar".** Corolário do stack-árbitro:
  o stack confirma o LUGAR (mesmo seat) mas não escolhe a GRAFIA — isso é olho humano ou nome manual.
- 2026-07-13 — **`asyncio.create_task` em imports = padrão FRÁGIL; usar daemon thread.** Os
  reconciles (table-SS/lobbys) disparados por `asyncio.create_task` no `import_hm3`/`import_`
  **perdem-se** quando o import é síncrono-pesado ou o request expira — a leva WN de hoje ficou sem
  re-match até correr à mão. **→ Lição: triggers fire-and-forget pós-import que TÊM de correr usam
  DAEMON THREAD** (sobrevive ao ciclo do request, não bloqueia o event loop; padrão de
  `trigger_name_propagation`), não tasks do event loop. Cura: `trigger_import_reconciles`
  (`#HM3-IMPORT-NO-RECONCILE-REDISPATCH`). Ver `JOURNAL_2026-07-13`.

- 2026-07-16 — **Etiqueta ≠ conteúdo: verificar a lei pela TIMELINE de deploy, não pelo rótulo.**
  Os packs HRC carregam `sizing_rules_version` gravada **no release** (quando o Rui clica Enviar),
  mas o `script.js` (o conteúdo real) é gerado **no pull** do adapter. Um zip pode sair com etiqueta
  v3 e conteúdo v2 se o release foi pós-bump mas o deploy ainda não subira — ou o inverso (foi o que
  abortou o smoke de 15 Jul: cliques pré-deploy → zips `2026-07-11-3bet-v2`). **→ Lição: para
  afirmar "a mão saiu com a lei X" cruzar sempre a etiqueta com a timeline `commit/deploy < release
  < pull < solve` (o `completed_at` do job > hora do deploy prova o conteúdo), e/ou ler os sizings
  reais dos nós da tree.** No VALE de hoje: deploy 03:02/03:34 UTC < solves 05:50–13:29 UTC → v3
  confirmado por conteúdo, não só rótulo. Ver `JOURNAL_2026-07-16.md`.

- 2026-07-17 — **Audit que conta só LINHAS NOVAS acusa falsos desaparecimentos.** O audit da
  leva de 13 Jul reportou "golds 16/18" e "TS 0/1" como se 2 golds + 1 TS se tivessem perdido.
  Investigação read-only: os 2 golds eram **duplicados reais** (dedup por `file_hash`, HTTP 200
  `duplicate`, não cria linha — prova: 621 golds, 621 hashes únicos, 0 hashes com >1 entry); o TS
  era um **re-import** (UPSERT por PK `(site,tournament_number)` → conta como *updated*, não
  *inserted*). **Nenhuma perda de dados.** O import devolve 200 tanto para "inseriu" como para
  "dedup/upsert"; um audit que só soma linhas novas trata os 200-sem-linha como falha. **→ Lição:
  qualquer audit de leva tem de distinguir os 3 desfechos do import — `inserted` / `duplicate`
  (dedup benigno) / `updated` (upsert benigno) — antes de acusar "sem assentar". "N enviados vs M
  linhas novas" NÃO é um buraco de dados; é o comportamento correto do dedup/upsert. Confirmar
  sempre pela BD (unicidade de hash, `xmax=0` do RETURNING) antes de tratar como incidente.** Ver
  `JOURNAL_2026-07-16.md` (dívida "2 Golds + 1 TS sem assentar" fechada como falso alarme).

- 2026-07-17 — **O wipe de 8 Jul saldou as dívidas de PROMPT; a classe viva é o erro POR-IMAGEM,
  só medível por amostra.** Dois censos de coroas potencialmente erradas deram **0** pela MESMA
  razão estrutural: a BD foi limpa+reimportada a 8 Jul e as correções de prompt são anteriores
  (pt95/table-SS `824f23d` 1 Jul; anti-chama da Gold `13ef90d` 5 Jun) → **nenhuma leitura
  pré-correção-de-prompt sobrevive na BD viva** (nem table-SS, nem Gold, nem carry). Mas isto NÃO
  quer dizer "cano limpo": o caso `/hand/6570` (curado 15 Jul) é uma classe DIFERENTE — a Vision a
  errar **numa imagem específica APESAR do prompt correto** (erro por-imagem, não artefacto de
  versão). **→ Lição: distinguir sempre "erro de VERSÃO de prompt" (datável → um wipe/reimport
  sana-o em bloco, contável por censo de data/versão) de "erro POR-IMAGEM" (a IA falha aquela foto
  apesar do prompt bom → NÃO datável, NÃO contável por censo; a coroa in-band certa é
  indistinguível da errada só pelo valor). A segunda classe só se mede RE-LENDO uma amostra, nunca
  por censo de valor/versão.** Corolário: um "0" de censo por-versão é honesto mas não é
  certificado de limpeza — dizê-lo sempre junto. Ver `JOURNAL_2026-07-17` (censos 1+2), amostrador
  das 177 (sliver 9 Jul + in-band Gold).

- 2026-07-17 — **TODA operação em lote da app tem botão de CANCELAR — o Rui nunca fica refém de
  um background.** O amostrador de coroas (177 releituras Vision, minutos) arrancou sem forma de
  parar; o Rui quis interromper a meio e não havia como (uma thread no servidor não se mata à
  distância). **→ Regra permanente: qualquer job em lote (releituras, reconciles massivos, robot,
  reimports) nasce com cancelamento cooperativo — bandeira verificada no topo de cada iteração +
  endpoint `/cancel` + botão no painel; interrompe na próxima unidade, MANTÉM o parcial já apurado
  ("interrompido a N/M"), nunca perde o feito.** Fallback duro: um redeploy reinicia o processo e
  mata qualquer daemon + limpa cache in-process. Ver `crown_sample.py` (padrão de referência),
  memória `feedback_batch_ops_need_cancel`.

- 2026-07-17 — **Releitura de verificação sobre a cópia COMPRIMIDA tem teto: o "sumiu" (—) é
  fraco; só valor→valor pesa.** O amostrador re-lê a Gold a partir de `entries.raw_json.img_b64`,
  que é a cópia **comprimida 1280/JPEG85** (o original não é retido — dado à Vision só no upload e
  descartado). Logo uma coroa que **desaparece** na releitura pode ser **degradação da imagem, não
  prova** de erro no gravado. Já um par **valor→valor** com padrão sistemático (ex.: halving
  $40→$20, $105→$55 em várias mãos do mesmo torneio) **não é degradação** — a compressão não divide
  números por 2 de forma limpa; é assinatura real (aqui: gravado somou o verde-KO pré-refinamento
  GREEN_KO → releitura lê só o dourado = correto). **→ Lição: uma verificação por releitura sobre
  cópia degradada classifica CANDIDATOS, não veredictos; separar sempre "— (fraco)" de "valor→valor
  (forte)" e declarar a limitação na própria UI. Para veredicto sobre os "—" é preciso o original
  (aqui: re-descarregar a Gold), não a cópia guardada.** Ver banner do painel `/crown-sample`.

- 2026-07-17 — **Padrão "suspeito de uniforme" (149/155) verifica-se contra os OLHOS antes de
  virar narrativa.** A auditoria aritmética reportou `delta=1` (sentados−extraídos) em **149 de 155**
  mãos e eu chamei-lhe "sistemático, estrutural, não corrupção" — dei-lhe uma explicação bonita
  (o seat que falta é o eliminado). O Rui verificou **7 mãos à vista** e em TODAS os extraídos eram
  EXATAMENTE os jogadores da mão → 7/7 limpas com "149/155 em falta" tem probabilidade ~zero → a
  régua media OUTRA coisa (o "sentados" contava sit-outs/gente fora da mão). **→ Lição: uma
  distribuição quase-uniforme e alta (149/155, 90%+) é MAIS provável um bug de medida do que um
  facto do mundo; antes de lhe dar narrativa, cruzar com uma pequena amostra à vista — se a amostra
  contradiz a estatística, é a régua que está errada, não o mundo. Anular os números e re-medir,
  não racionalizar.** Ver `JOURNAL_2026-07-17` (auditoria das 155, régua corrigida).

- 2026-07-17 — **Teoria plausível declara-se como ESPECULAÇÃO até à prova; morre limpa com 0/N na
  forense.** A hipótese "verde-KO somado" (a coroa do eliminador = placa própria + verde do
  eliminado, inflada) explicava tão bem os pares halving ($105→$55) que eu a dei por confirmada na
  Q2 ("a releitura é a certa"). A forense sobre 7 espécimes nomeados deu **0/7** — os eliminadores
  mostram o instantâneo FRESCO exato (base/2), sem verde somado; o padrão real era outro (o
  ELIMINADO fica com coroa NULL). **→ Lição: uma teoria que "encaixa" não é prova; enquanto não
  houver forense nos dados, apresenta-se rotulada como hipótese/especulação, nunca como facto — e
  quando a forense a mata (0/N), corrige-se em voz alta a afirmação anterior, não se deixa a versão
  plausível a contaminar as decisões.** (Corolário do adversarial-verify: uma hipótese sobrevive só
  depois de tentarem refutá-la com dados.) Ver `JOURNAL_2026-07-17` (forense verde-KO).

- 2026-07-17 — **Nem o gravado nem a mecânica teórica ARBITRAM uma coroa — só a IMAGEM.** Na mão
  2480 (matador AVRELIY) errei o valor da coroa dele DUAS vezes por raciocínio: primeiro "$125 =
  frame pré-KO", depois "$187.5 = próprio + metade do eliminado". A imagem, à vista do Rui, mostrou
  **dourada $265.62 + verde $187.5** — o gravado ($125) era **misread puro**, e o eliminado
  (PhilVsSandw..) tinha bounty **$375** (não os $250 "base" que assumi: ele não estava fresco).
  Tanto o valor gravado como a fórmula teórica (base÷2, own+verde) são PALPITES; a coroa real do
  frame não obedece a nenhum. **→ Lição: uma coroa só se corrige/escreve DEPOIS de olhar a imagem
  do frame — nunca a partir do gravado (pode ser misread) nem da mecânica do PKO (a acumulação real
  é o que o frame mostrar). Qualquer fluxo que escreva um bounty TEM de mostrar a imagem primeiro e
  gravar o que o olho lê, não o que o modelo calcula.** A fórmula do Rui `bounty_eliminado = verde ×
  2` ganha-se ao LER o verde na imagem (aqui $187.5 × 2 = $375), não ao assumir a base. Desenho do
  fluxo (A)+(B): imagem SEMPRE antes da escrita. Ver `JOURNAL_2026-07-17`, `#CROWN-RECOVERY`.

- 2026-07-18 — **Nenhum caso de COROA se fecha sem a IMAGEM aberta — contas de stacks validam a
  MÃO, não o VALOR.** Na "queda" GG-6090481210 ($437.5→$421.87) construí três teses (mecânica GG
  desconhecida de −B/8; indexação errada; e o match de stacks 6/7 a "provar" que a imagem pertencia
  à ...1210) e dei o veredicto **"ambas as placas confirmadas, queda real, caso aberto"** — **sem
  ninguém ter olhado a placa**. Quando o Rui finalmente abriu a imagem (entry 1720), a coroa do
  Lauro dizia **$421.87**, não $437.5: o gravado era um **misread da Vision** e **não havia queda
  nenhuma** (421.87→421.87). As minhas contas de stacks estavam certas quanto à MÃO (a imagem é
  mesmo da ...1210) e completamente irrelevantes quanto ao VALOR (o que a placa mostra). **→ Lição:
  o valor de uma coroa é um facto ótico — só a imagem o arbitra. Match de stacks, dyadic-fits,
  mecânica teórica, "referência anterior" — tudo valida a IDENTIDADE da mão ou a plausibilidade,
  NUNCA o número na placa. Um caso de coroa só se fecha (real/misread/o que for) DEPOIS de a imagem
  estar aberta e lida a olho. E "placa confirmada" só se escreve quando alguém olhou mesmo a placa —
  nunca por inferência.** Corolário operacional: quando o Rui pede a imagem, ela é a prioridade
  absoluta e tem de vir num link que ABRA (o meu 1º link caiu no dashboard por estar no domínio do
  frontend, que não serve `/api` em produção — a imagem vive no backend). Ver `feedback_hand_refs_by_link`,
  `feedback_review_panel_no_prefill_guess`, e o fecho da GG-6090481210 (corrigida a $421.87 selado).
