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
| **P2** | **QUEM senta em que cadeira?** | Mapeia cada hash anónimo → nick real, na cadeira certa | âncora (posição/botão); stacks só p/ direcção | **RESOLVIDO**: gold=`position_v3` (§3.2.2); table-SS=âncora Hero+botão (§3.2.3, pt96) |

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

> **Gold image (pt75, 2026-06-18):** a "gold image" = a **descarga completa da mão** pelo
> botão do replayer GG (não um screenshot). A GG **NÃO desenha rótulo de posição por seat**;
> as siglas (UTG/MP/CO/BTN/SB/BB) vivem no **LOG DE ACÇÃO** (painel inferior, uma linha por
> acção). É daí que a Vision as lê (ver §3.2.2).
>
> **★ FIABILIDADE DO NOME DO FICHEIRO DA GOLD (corrigido pt97, provado, 6 exemplos):**
> ao contrário do que se dizia, na **Gold** (descarga do replayer) o nome é
> **FIÁVEL** para três coisas: (1) o **TM/hand-id** casa **1:1 EXATO** com a HH
> (a Gold carrega a identidade da mão); (2) a **hora** = hora de **jogo em UTC**
> (a HH está em Lisboa UTC+1) → **desvio FIXO −1h**, não é lixo; (3) as **blinds**
> = blinds reais **em milhares** (`0.35/0.70` no nome = 350/700). *(Isto é a
> GOLD; para o IT o número do nome NÃO é fiável — ver §2.2.)*

### 2.2 Table-SS ↔ mão GG

> **★ DECISÃO pt73 REVISTA em pt97 (2026-07-01): o hand-id do nome do ficheiro do IT
> NÃO é fiável — a proposta "casar por ele, autoritário" foi ABANDONADA.**
>
> A pt73 propunha casar o table-SS pelo hand-id embutido no nome. A análise por
> **fit de stacks** (Vision vs HH) em pt97 desmentiu a premissa: das **244**
> capturas IT com nº≠mão casada, só **~72 são trocas reais**; em **60** o match
> por tempo estava **certo** e o nome errado; **101** ambíguas. **Razão:** a
> captura do IT é tirada **segundos DEPOIS** do início da mão, e em multi-tabling
> o número do nome anda uma mão à frente/atrás (aponta a mão **vizinha**). Casar
> por ele partiria mais do que conserta.
>
> **Conclusão (pt97):** o **IT** mantém o match por **tempo + nome + fingerprint**
> (o que já existe). O sinal fiável de "captura trocada" é o **fit de stacks**, não
> o nome (a secção "Saúde GG" mostra o nº≠mão como **suspeita**, não veredicto).
>
> **A GOLD é diferente:** o TM do nome da Gold casa **1:1 EXATO** (§2.1) — é o
> único match por-número fiável. **Regra do Rui: "quando há Gold, casa-se por aí"**
> (já acontece nas **132** mãos com Gold + IT, 0 trocas). Onde o IT falhar, a via
> premium é **descarregar a Gold** dessa mão (ver §2.3).

**Estado HOJE no código (até a decisão ser implementada):** o table-SS casa por uma função
determinística `compute_table_ss_match` (`table_ss.py`, pt50), **por tempo** (janela ±5min),
com:
- **Site** lido do **nome do ficheiro** (`_site_from_filename`, pt56) — autoritativo sobre a Vision.
- **`tournament_number`** já extraído do filename no formato novo (`parse_table_ss_filename`, pt60).
- **Desambiguação multi-tn** por **nome fiel** da imagem (`name_tokens_subset`, pt54/pt58) e,
  no plano `PLAN_2026-06-02-table-ss-gg-match.md`, **fingerprint** (hero_stack_bb ±20% + big_blind).

**(pt97) O fingerprint/nome-directo do IT MANTÊM-SE** — a reversão da pt73 (acima)
significa que o table-SS continua a casar por tempo+nome+fingerprint; não há chave
por-número fiável para o IT (ver `#TABLE-SS-GG-MULTITABLING-MATCH`).

### 2.3 Gold vence IT — alcance e via premium (pt97)

Das **9263** mãos GG 2026: **332** têm Gold (`position_v3`), **382** têm só IT
(`table_ss`), **8549** sem imagem. Das 382 só-IT, **0** têm uma Gold à espera — o
IT é frágil precisamente porque **nunca lhe foi descarregada Gold**. Nas **132**
mãos com Gold **e** IT, a Gold **já ganha** (position_v3), 0 trocas. **Solução onde
o IT falha (captura trocada / nomes por verificar): descarregar a Gold** dessa mão
— casa 1:1 exato e substitui o IT frágil. É a via premium (decisão do Rui).

---

## 3. Pergunta 2 — QUEM senta onde (hash → nick → cadeira)

O hand_id resolve P1 mas **não traz nicks**. Para pôr cada nick real na cadeira certa é
preciso uma âncora própria. **Ambos os caminhos estão RESOLVIDOS e DEPLOYED:**
- **Gold images GG (replayer): `position_v3` por POSIÇÃO** (§3.2.2, pt75).
- **Table-SS: âncora Hero+botão** (§3.2.3, **pt96 2026-07-01**) — implementa o desenho
  §3.2.1 (Hero+botão+ordem circular, stacks só p/ direcção). **Substituiu o
  stack-elimination como primário** (este ficou fallback p/ dados antigos sem `is_button`).
  As 15 mãos com "vilão = nome do Hero" (§3.2) ficaram consertadas 15/15, bug a **0**.

A âncora por **stack** (§3.1) **deixou de ser primário** — é só fallback (entries/dados
sem sigla nem `is_button`). O §3.2.1 **já não é "pendente"** — está implementado em §3.2.3.

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

### 3.2.1 ★ Âncora P2 — desenho FECHADO (2026-06-16)

> Fecha o antigo "a especificar pelo Rui". **É desenho, não implementação** — a maquinaria
> por stack (§3.1) e o bug (§3.2) continuam no código até isto ser construído.

**Princípio (a HH é a fonte de verdade da estrutura).** A HH GG é exacta para
**posições (SB/BB/BTN/Hero), stacks, ações, ordem**. Tem **exactamente DOIS buracos**:
(1) os vilões vêm em hash (o Herói vem como `Hero`); (2) **não traz tags** (ICM/PKO/pos-pko/nota).
A **imagem é a única fonte de ambos** — a tag vem da imagem do IT (**a subpasta de captura = a
tag**) e os nicks reais vêm da imagem (IT e/ou replayer). Logo a imagem é a **OUTRA METADE** do
registo da mão e **TEM de ser persistida**: perdê-la = perder tags + nicks para sempre.
(O table-SS já guarda `img_b64`; a lane do replayer — ver `PENDENTES` — tem de garantir o mesmo.)

**P2 é ALINHAMENTO, não estrutura.** A HH já conhece todas as cadeiras e posições com certeza;
a imagem só dá os nicks. P2 = alinhar o layout da imagem ao da HH para cada nick aterrar na
cadeira (hashed) certa. **Uma troca é erro de alinhamento de NOMES, nunca de estrutura.**

**Âncora = TRÊS critérios corroborantes**, legíveis na imagem **E** na HH:

1. **SB + BB (âncora primária)** — campo próprio dos dois lados. Duas cadeiras fixas e adjacentes.
2. **Botão do dealer (confirmação)** — sempre na imagem (disco "D"); marcado na HH. Comparar
   Vision vs HH usando o **invariante**: BTN, SB, BB são **três cadeiras seguidas**
   (BTN → SB → BB; a SB entre o botão e a BB). O botão tem de cair na cadeira encostada à SB,
   do lado oposto à BB.
3. **Herói (referência fixa)** — centro-baixo + nick conhecido na imagem; `Hero` na HH. Já usado
   pela máquina actual.

**Resultado:** até **4 cadeiras conhecidas (SB, BB, BTN, Hero)** sobre-determinam a roda; o
**stack desce a cruzamento final** (deixa de ser a âncora primária — passa a desempate).

**Corroboração obrigatória:** os critérios **têm de concordar**. Algum não bate → **NÃO atribuir**
→ a cadeira fica **"por mapear"** (hash mantido). **Nome em falta é honesto; nome trocado é veneno.**
A HH fica **intacta** em qualquer caso.

**Borda:** heads-up (**BTN = SB**) → tratar à parte.

**Novo vs existente:** o **Herói** já é âncora; **SB/BB** existiam (pt7) mas o table-SS
**salta-as** (= raiz do bug §3.2) → **REPOR**; o **botão como confirmação pela invariante** é
**NOVO**.

### 3.2.2 ★ `position_v3` — desanon por POSIÇÃO (FEITO + DEPLOYED, pt75 2026-06-18)

Método **primário** para gold images GG. Sem aritmética de stack: a Vision lê a **sigla de
posição de cada jogador no LOG DE ACÇÃO** (§2.1); a HH dá seat→posição pelo botão; cada nick
vai para o seat da HH com a **mesma** posição (`_canon_position` reconcilia a grafia GG↔HH,
inclui LJ). `match_method='position_v3'`.

- **Verificação do Hero:** o seat `Hero` da HH só recebe o nick da Vision se for um **nick-Hero
  conhecido** (`hero_unverified` caso contrário) — nunca se escreve um nick de vilão no seat do
  Hero (bug apanhado no smoke).
- **Guard-rails de lacuna honesta:** sigla em falta, posição sem seat, colisão, ou não-participante
  → seat **por mapear** (hash mantido), nunca um nome trocado.
- **A ordem deixou de importar:** HH-primeiro (match directo, `screenshot._enrich_hand_from_orphan_entry`)
  **e** imagem-primeiro (órfã → re-link na promoção do placeholder, `hand_service._insert_hand`)
  dão **ambos `position_v3`**. Entries **sem** sigla caem no stack-elimination (§3.1), intacto.
- **Prova:** 41 gold images de Junho (âncoras SB/BB 81/81; consistência entre mãos 54/55, 0
  inconsistências) + smoke ao vivo nos dois sentidos (nomes certos por cadeira). → `JOURNAL pt75`.

### 3.2.3 ★ Âncora Hero+botão — desanon do TABLE-SS (FEITO + DEPLOYED, pt96 2026-07-01)

**Método PRIMÁRIO do table-SS** — substitui o **stack-elimination** (§3.1) como primário
(este fica só fallback para dados antigos sem `is_button`). É a **implementação do desenho
§3.2.1** adaptada ao table-SS (que, ao contrário da gold, **NÃO tem secção de blinds em
texto**): a âncora é o **HERO** (não SB/BB) + o **BOTÃO**.

**Princípio:** TEXTO (HH) manda na estrutura; imagem só dá NOMES; **stacks NÃO mapeiam**.

- **Vision estendido** (`table_ss_vision.py`): `is_hero` **POSICIONAL** (baixo-centro
  auto-center, **IGNORA cartas** — o Hero foldado não tem cartas mas está sempre lá; furo
  apanhado pelo Rui) + `is_button` (o 'D') + seats em **ordem CIRCULAR** (horário do Hero).
- **Alinhamento** (`build_anon_map_by_hero_button`):
  1. Roda da HH (`POSITION_MAPS`: SB,BB,…,BTN) rodada para o **Hero no índice 0**.
  2. **2 âncoras** fixam a roda: Hero (índice 0) + a **DIRECÇÃO** (a "horário" da Vision
     **NÃO é consistente** — ~50% invertida). A direcção vem do **BOTÃO**; se o 'D' se lê
     mal (~50% das SS), **fallback: STACKS** — comparam img-vs-HH nas 2 hipóteses; a de
     erro menor (margem ≥50%) dá a direcção. **Os stacks SÓ escolhem 1 de 2 sentidos —
     NUNCA mapeiam nomes** (inócuo; radicalmente + seguro que o stack-elimination, que
     usava stacks p/ escolher QUEM é cada um).
  3. **Cruzamento:** botão+stacks concordam → alta confiança; **discordam → ALARME**.
  4. **Regra dura:** Hero no índice 0 fixo → **NUNCA mapeado a um vilão** (a raiz do bug dos 15).
  5. **SALVAGUARDA:** contagens img≠HH (sitting-out/mesa incompleta) / direcção indecisa →
     **ALARME, NÃO escreve** (`status='review_alarm'`) — nunca sai com nomes trocados em silêncio.
- **Resultado:** as **15 mãos** com "vilão = nome do Hero" (o stack-elimination trocava em
  stacks próximos) **re-desanonimizadas 15/15**, bug sistémico a **0** (7 pelo botão, 7 pelo
  fallback de stacks, 1 [a 4321] por override manual de blinds). Ensaio de leitura: 8/8 na
  4321 ground-truth (Hero foldado sem cartas), 8/7/5/2-max. **19 testes**, commit `72eaedc`. **Só GG.**
- **Código:** `build_anon_map_by_hero_button` + `_num_stack` (`table_ss_deanon.py`);
  `deanonymize_hand_from_table_ss` prefere-o quando há `is_button`. Override manual:
  `POST /api/table-ss/set-anon-map` (por blinds/gold) + `/set-bounties`.

### 3.2.4 ⚠️ CASO A PROTEGER — jogador SENTADO-mas-SEM-CARTAS na Gold (N+1) → apa desliza

**Sintoma (caso real `GG-6083771298`, Speed Racer Bounty $108, 2026-06-16):** na mesa há
**6 sentados** mas a MÃO tem só **5** — um jogador (`Afonso Neto`) **acabara de se sentar
e NÃO jogou** (sem cartas, `position=null` no `players_list` da Vision). A Vision lê **N+1
nomes** (6) contra **N cadeiras** da HH (5). O `all_players_actions` ficou **corrompido**:
`Afonso Neto` injectado no seat do BB, os nomes **deslizados uma posição**, um seat
**colapsado** (5→4), o SB (`CORDEIRODEDEUS`) **perdido**.

**⚠️ Nuance importante — o `anon_map` estava CERTO; o apa é que estava STALE.** O
`position_v3` (§3.2.2) mapeia por **RÓTULO de posição** e por isso **descartou bem** o
`Afonso Neto` (sem rótulo → `no_label` → não mapeado): o `anon_map`
(`player_names`) ficou **correcto por posição**. A corrupção estava só no `all_players_actions`,
escrito por **outro caminho (order/stack)** e **nunca reconciliado** com o `anon_map`. Ou seja:
**dois escritores** (apa por um lado, `anon_map`/`match_method` por outro) **saíram
inconsistentes** e nada o detecta. Esta mão era exactamente a **"1 diverge"** que o fix
automático `#DESANON-GOLD-SCRAMBLE` (`reenrich-scrambled-gold`) **recusou escrever** — o seu
gate de fichas FINAIS (`_stack_gate_ok`, Gold-vs-HH-final) **divergiu** (stacks Gold em unidade
inconsistente / momento fim-vs-início — `#GOLD-STACK-CHIPS-UNIT-INCONSISTENT` +
`#GOLD-STACK-MOMENT-END-NOT-START`) → skip conservador → apa ficou stale.

**Porque é que a SALVAGUARDA img≠HH (§3.2.3) NÃO apanhou isto?** Porque essa salvaguarda
(`build_anon_map_by_hero_button`, contagens img≠HH → alarme) vive **SÓ no método ÂNCORA do
table-SS** (pt96). Esta mão foi desanonimizada pela **Gold `position_v3`**, um caminho
**diferente**, que **não tem count-abort** — degrada por rótulo (o extra sem rótulo é
silenciosamente largado). E a corrupção do apa veio de um **3º caminho (order/stack)** que
**também não tem** guarda img≠HH. **A protecção N+1 NÃO é universal** — mora só na âncora.
Cross-ref: `#DESANON-SITTING-OUT-NPLUS1-NO-UNIVERSAL-GUARD` (buraco registado).

**Remediação (2026-07-02):** correcção MANUAL via `POST /api/table-ss/set-anon-map`
(reparse do apa hash-keyed do RAW → aplica o `anon_map` de 5, **sem** `Afonso Neto` → 5 seats
certos por posição, Hero=Lauro Dermio no BTN, sem duplicados). O `/set-anon-map` **não tem** o
gate de fichas que travou o fix automático (confia no `anon_map` confirmado pelo Rui). **Efeito
colateral:** o `match_method` passa `position_v3` → `table_ss`/`manual_blinds_override` (badge
`deanon_status` **verified → unverified**) — dados certos, badge conservador.

**Regra a proteger:** Gold com **sentado-sem-cartas** (mesa > mão) é caso normal, não erro do
Rui — a Vision devolve N+1 e **qualquer mapeamento por ORDEM desliza**. O `position_v3` (por
rótulo) é imune ao deslize; o perigo é o **apa escrito por um caminho de ORDEM** ficar
inconsistente com o `anon_map` correcto. Ao tocar em qualquer caminho de desanon/enrich, tratar
**img≠HH como sinal duro** e **assertar apa↔anon_map** (contagem de seats == hashes da HH).

### 3.3 Mitigações já no sítio (reduzem, não resolvem)
- **Guarda anti-envenenamento** (`_filter_ambiguous_stackless`, pt71): ≥2 bancos não-herói
  **sem stack utilizável** (all-in/null) ficam **POR MAPEAR** (hash mantido) +
  `player_names.deanon_partial=true`. **Nome em falta é honesto; nome trocado é veneno.**
- **Votação cross-mão por torneio** (`vote_tournament_maps` / `reconcile_tournament_deanon`,
  pt71 E6), fundada no invariante:
  > **★ (corrigido/reforçado pt97) O hash GG SEGUE o jogador ATRAVÉS DE MESAS dentro do
  > torneio** — não é só "fixo dentro do torneio" em abstracto; o **mesmo hash = a mesma
  > pessoa mesmo quando muda de mesa e de posição**. **Prova (Rui à imagem):** Daily Hyper
  > $80 (tn `293321688`) — `95c4411e` = "Jailinrabei" e `2b3f299a` = "Daniel Fili" aparecem em
  > **mesas E posições diferentes** com o mesmo nick. (Forense Jun-2026: 0 violações
  > cross-torneio em 1059 hashes.)
  >
  > ⚠️ **Engano desmascarado:** no Daily Main (tn `293616024`) deram **0 cruzamentos** de hash
  > entre mãos e concluiu-se "a GG re-embaralha hashes entre mesas" — **FALSO**. Nesse torneio
  > **ninguém seguiu o Rui de mesa** (por isso 0 cruzamentos), não porque o hash mude. O hash
  > é estável; a ausência de cruzamentos foi de amostra, não da mecânica.
  A maioria por torneio corrige swaps do per-mão; cada captura nova acrescenta um voto e
  retro-corrige. Vigiada na Saúde do Import (`capture_deanon_agreement`).

  > **Alcance da propagação por hash (pt97, só mãos TAGADAS):** 75 torneios GG 2026 com ≥2
  > mãos tagadas · **484** tagadas · **1126** hashes distintos. **1 confirmação de nome
  > propaga a ~3 mãos tagadas** (média global 2,98) → corta a nomeação de **3352 → 1126
  > (−66%)**. Muito **enviesado pela fase**: mesa final (poucos jogadores, muitas mãos) 5–13;
  > início/multi-mesa 1,5–2. **Decisão do Rui: nomear TODOS os vilões.** O universo de estudo
  > são as **mãos TAGADAS** (507 GG tagadas; 377 das 382 "só IT" são tagadas), não as 9263.

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
