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
