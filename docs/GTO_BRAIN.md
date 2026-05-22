# GTO Brain — Documento de Referência

**Estado:** v1, 22 Maio 2026 (sessão pt35).
**Origem:** consolidação a partir de conversas com Rui (sessão pt35) + leitura do código existente (`backend/app/routers/gto.py`, `frontend/src/pages/GTOBrain.jsx`, `frontend/src/pages/ReplayerPage.jsx`).
**Audiência:** qualquer pessoa ou agente AI que entre no projecto pela primeira vez. Depois de ler este documento, deve perceber **o que é o GTO Brain, porque existe, como funciona, e para onde vai** sem precisar de mais contexto.
**Manutenção:** quem adicionar funcionalidade nova ao GTO Brain edita aqui antes de fechar o trabalho. Sem isto, o conhecimento perde-se.

---

## 1. O que é o GTO Brain — resposta de um parágrafo

O GTO Brain é uma camada de análise dentro da app de poker. Quando o Rui está a rever uma mão de dúvida pós-sessão, o GTO Brain apresenta duas vistas comparativas sobre o spot exacto onde a dúvida ocorreu:

1. **GTO** — o que o solver faz naquela situação. Vem de árvores HRC (Holdem Resources Calculator) acumuladas e matched automaticamente à mão real.
2. **FIELD** — o que o field do GGPoker faz mesmo. Vem da agregação estatística das hand histories importadas dia a dia.

Sem o GTO Brain, o Rui só tem a sua intuição quando revê uma mão. Com o GTO Brain, tem confronto duplo: o ideal teórico (solver) versus a realidade observada (field).

---

## 2. Origem e propósito

A app de poker do Rui existe para um objectivo central: estudar mãos de dúvida que aparecem durante o jogo de torneios MTT (multi-table tournament). O fluxo típico:

1. Rui joga vários torneios em simultâneo (até 9 mesas).
2. Durante a sessão, marca mãos onde teve dúvida (via tags no HoldemManager3, mensagens em canais Discord de estudo, ou screenshots tirados na hora).
3. No dia seguinte, na app, revê essas mãos no replayer (visualizador interactivo da mão).
4. Sobre cada mão, pensa na decisão que tomou e na decisão correcta.

Sem GTO Brain, a app é um repositório organizado de mãos. O Rui revê em vazio: olha para a mão e pensa "será que joguei bem?". Para ter resposta, sai da app, abre o HRC, calcula manualmente, compara — fluxo lento e que ele faz pouco na prática.

**O GTO Brain transforma isto num sistema de estudo activo:** no momento da revisão, o Rui tem dentro da app, ao lado da mão, informação contextualizada sobre como o solver e o field tratam aquele tipo de spot. A pergunta deixa de ser "será que joguei bem?" e passa a ser "como é que isto se compara com a referência?".

A ideia surgiu como evolução natural do produto: a app já cataloga mãos com nicks reais e contexto completo, e o Rui já paga assinatura de HRC. Falta cozer as duas pontas e tornar a análise GTO accionável directamente sobre as mãos guardadas.

---

## 3. Filosofia

Princípios não-negociáveis. Qualquer construção sobre o GTO Brain deve respeitá-los.

### 3.1 Pós-sessão, nunca live

O Rui **não quer** consultar o GTO Brain durante o jogo. Três razões:

- **RTA (real-time assistance)** — usar solver durante o jogo é violação dos ToS de qualquer sala de poker. Risco de banimento e perda dos fundos.
- **Anti-cheat** — as salas (GGPoker, PokerStars, Winamax, WPN) scanneiam processos activos. Ter a app aberta com painel GTO no ecrã durante uma sessão é red flag.
- **Fluxo de jogo** — pensar em GTO no momento atrasa decisões e estraga o jogo intuitivo. Estudo é em separado.

Implicação prática: o GTO Brain só é consultado **depois** de a sessão acabar, sobre mãos já guardadas. Não há live alerts, não há sugestões em tempo real.

### 3.2 Confronto duplo, não monólogo

Mostrar **só** a estratégia GTO é meio-passo. Mostrar **só** o field é meio-passo. O valor está em ver os dois **lado a lado** e ler a diferença.

Exemplo: no spot em estudo, o solver 3-betta o BTN 12% da mão; o field GG real 3-betta 6%. Esta diferença diz muito mais ao Rui sobre como adaptar do que qualquer dos números isolado.

### 3.3 Matching automático, não escolha manual

O Rui não quer ter de escolher manualmente qual árvore consultar para cada mão. Eventualmente vai ter dezenas ou centenas de árvores resolvidas. A app procura sozinha a melhor match e apresenta-a. Pode haver fallback manual (escolher entre top 5), mas o caminho principal é automático.

Matching é **aproximado, não exacto**: a app procura a árvore mais próxima do spot real entre as disponíveis e mostra essa, com indicação visual do grau de confiança. Não exige árvore com características 100% iguais à mão.

### 3.4 Pré-flop primeiro, pós-flop depois

O scope inicial é **pré-flop**: open, 3-bet, 4-bet, 5-bet, jam, call vs jam. Pós-flop (c-bet, raise vs c-bet, decisões turn/river) é evolução futura, **não bloqueador**. Toda a primeira versão do GTO Brain deve ser útil mesmo sem ler um único postflop.

### 3.5 Acumular trees, não calcular sempre

O HRC corre offline numa máquina dedicada (Beelink GTR5 mini PC). Cada árvore demora dezenas de minutos a calcular. Não vale a pena recalcular para cada mão. O resultado é guardado em BD e reutilizado em mãos parecidas (via matching engine).

A app é **cliente** de uma biblioteca crescente de árvores resolvidas, não solver em si.

### 3.6 Integração na vista da mão

A informação aparece **dentro do replayer**, ao lado da mão a rever. Tab GTO + tab FIELD junto à mão, no fluxo natural de revisão.

A página `/gto` que existe hoje é só para **gestão da biblioteca** (listar, editar metadados, apagar árvores). Não é a vista principal de consumo.

### 3.7 Cobertura conta sempre; em PKO é dominante

A relação de cobertura entre jogadores influencia o jogo correcto em **qualquer formato de torneio**. Magnitude varia:

- Em **Vanilla MTT** (sem bounty), a cobertura afecta a decisão via **bubble factor** do modelo ICM: quem é coberto paga mais caro por dobrar (eliminação custa $ICM em torneios pagos). O cálculo do solver muda quando a relação de cobertura muda, mesmo que os stacks absolutos não.
- Em **PKO**, o efeito acima continua e soma-se o bounty (quem cobre fica com direito a parte do bounty do eliminado). A relação de cobertura passa a ser o factor dominante.

Em ambos os formatos, o matching engine não deve penalizar fortemente diferenças de stack absoluto que **não alterem a relação de cobertura** entre os jogadores envolvidos no spot.

---

## 4. Caso de uso canónico

Para fixar a ideia, mão real (TM5944382201, 12 Maio 2026, *Bounty Hunters Daily Main*, formato PKO, mesa 8-max):

- **Hero** (Lauro Dermio, alias do Rui em GGPoker) — MP, 96.4 BB, QQ.
- Hero abre 2 BB. Folds dos jogadores entre MP e BTN.
- **BTN** (Y Capocetti) — 47.5 BB, 3-bet a 8 BB.
- SB e BB foldam.
- Volta a decisão a Hero.

Pergunta natural do Rui ao rever: *"Como devo jogar QQ aqui contra este 3-bet?"*

Pergunta mais profunda que o GTO Brain deve responder: *"O que esperava do BTN num spot destes, e o que o field real faz?"*

*Nota sobre os números abaixo: o matching é por aproximação. Os valores entre parêntesis (8-max, ITM, nível 7, stacks específicos) descrevem a mão real; o GTO Brain procura a árvore disponível **mais próxima** desse perfil entre as que tem em biblioteca, não uma idêntica (ver §3.3 e §3.7).*

### 4.1 Painel GTO — o que o solver mostra

1. **Range do BTN** — o que o solver 3-betta num spot **próximo** deste. O GTO Brain não precisa de uma árvore com aqueles 7 stacks exactos — usa a árvore disponível com **score de match mais alto** (combinação de fase, posições e stacks, conforme §5.3). Range visual em grelha 13×13 com pesos (frequência) e EVs (expected value). A UI mostra também o score da match para o Rui saber a confiança.
2. **Range do Hero vs 3-bet** — fold / call / 4-bet, com sizings recomendados, em grelha 13×13.
3. **Resposta do BTN vs 4-bet do Hero** — call / jam / fold.
4. **Navegação interactiva** — poder clicar num ramo da árvore e descer para o ver com detalhe.

### 4.2 Painel FIELD — o que o field GG faz mesmo

Em mãos com perfil próximo deste — formato PKO, fase ITM, mesa 8-max, **BTN com stack semelhante** (bucket ≈ 40–55 BB), a enfrentar open de jogador que o **cobre** (regra-chave; ver §3.7). O valor absoluto do stack do opener é secundário desde que a relação de cobertura se mantenha. Outros jogadores remaining que também cubram o 3-bettor pesam no perfil de risco da decisão e contam no matching aproximado.

1. **Quanto o BTN 3-betta** — frequência observada (% das mãos).
2. **Com que mãos** — range observado dos showdowns disponíveis.
3. **Com que sizings** — distribuição (2.5x, 3x, 4x, jam).
4. **Vs 4-bet non-allin** — call %, jam %, fold %.
5. **Vs 4-bet all-in** — call %, fold %.
6. *(futuro)* C-bet do flop, resposta vs c-bet, etc.

### 4.3 Leitura cruzada

A confrontação dos dois painéis dá ao Rui a leitura essencial:

- Se o BTN GTO 3-betta 12% e o field 3-betta 6%, o field é **tight** vs GTO → 4-bet do Hero deve ser **mais polarizado** (só com mãos top, sem bluff).
- Se o BTN GTO 3-betta 12% e o field 3-betta 18%, o field é **wide** vs GTO → Hero pode **call mais largo** com mãos especulativas que floppam bem (small pairs, suited connectors).

Sem GTO Brain, o Rui chega a esta leitura via intuição e memória. Com o GTO Brain, chega via dados.

---

## 5. Arquitectura técnica

### 5.1 Lado GTO — produção de árvores

```
[Rui marca mão para estudo] (HM3 tag, Discord canal, ou manual)
        ↓
[Backend Railway: GET /api/queue/hrc] (zip com hh.txt + payouts.json + script.js + meta.json)
        ↓
[Adapter Beelink: tools/hrc_adapter/] (Python loop 60s)
        ↓
[Filesystem do Beelink: queue/<hand_id>/]
        ↓
[Watcher: hrc_watcher.exe] (bytecode Baltazar OG + nossos patches em tools/watcher_src/patched_funcs.py)
        ↓
[HRC GUI operado via pyautogui: paste HH → wizard → 2 runs → Export Strategies]
        ↓
[done/Exports/<hand_id>.zip] (settings.json + equity.json + nodes/*.json)
        ↓
[Adapter detecta zip: POST /api/queue/hrc/results]
        ↓
[Backend Railway: hrc_jobs table] (estado actual: apenas BLOB do zip)
```

**Gap actual entre Watcher e BD GTO:** o zip recebido vai para `hrc_jobs` mas **não** é parseado para `gto_trees`+`gto_nodes`. Hoje, popular o GTO Brain exige import manual via UI (`POST /api/gto/import`). Ver §7 Fase 2.

### 5.2 Lado GTO — persistência

Schema (ver `backend/app/routers/gto.py:14-28`):

- **`gto_trees`** — 1 linha por árvore.
  - Metadados: `name`, `format` (PKO/Vanilla/etc.), `num_players`, `tournament_phase`, `hero_position`, `hero_stack_bb_min/max`, `villain_stack_bb`, `hero_covers`, `tags`, `uploaded_by`, `source_file`, `node_count`.
  - Dados crus: `settings_json` (JSONB com config do cálculo HRC), `equity_json` (JSONB com equity inicial).
- **`gto_nodes`** — N linhas por árvore (1 por nó da árvore).
  - `tree_id` (FK), `node_index`, `player` (quem decide), `street` (0=preflop), `sequence` (acções até aqui), `actions` (acções possíveis daqui), `hands` (array de 169 entries com `[weight, played, evs]` na ordem canónica `HAND_ORDER`).
  - Flags: `is_terminal`, `has_mixed`.

Storage fragmentado (1 nó por linha BD, não BLOB) permite consultas pontuais: pedir 1 nó específico sem carregar a árvore inteira para memória.

### 5.3 Lado GTO — motor de matching

`GET /api/gto/match` (`backend/app/routers/gto.py:466-503`).

**Input:** situação real:
- `format`, `num_players`, `hero_position`, `hero_stack_bb`
- `level` + `site` → fase do torneio derivada (helper `_phase_from_level`, linha 138)
- `active_positions` + `active_stacks_bb` — jogadores que **estão** na mão a decidir
- `remaining_positions` + `remaining_stacks_bb` — jogadores que **ainda actuam** depois do Hero

**Algoritmo (`calc_score`, linha 161):**

Para cada árvore na BD onde `format` bate, calcula 7 sub-scores e combina com pesos calibrados (com Rui, em conversas anteriores):

| Peso | Critério | Detalhe |
|---|---|---|
| 20% | Fase | early / middle / bubble / itm / final_table — diferença de 0 nível = 100, 1 nível = 60, 2 = 25, 3+ = 5 |
| 20% | Posição do Hero | match exacto = 100, mesmo grupo (steal/mid/early/blinds) = 66, grupo adjacente = 33 |
| 20% | Stack do Hero | <=5% diferença = 100, 15% = 80, 25% = 50, 40% = 25 |
| 15% | Posições dos jogadores activos | greedy match position → tree position |
| 15% | Stacks dos jogadores activos | depois do match de posições |
| 5% | Número de jogadores remaining | diferença 0 = 100, 1 = 60, 2 = 20 |
| 5% | Stacks dos jogadores remaining | depois do match de posições |

**Output:** top 5 árvores ordenadas por score, com breakdown por critério para auditoria visual.

### 5.4 Lado GTO — navegação

`POST /api/gto/navigate` (`backend/app/routers/gto.py:377-464`).

**Input:** `tree_id` + sequência de acções reais (`[{type: 'F'|'C'|'R', amount_bb}, ...]`).

**Algoritmo:** começa no nó raíz (node_index=0). Para cada acção da sequência:
- Encontra a próxima acção na árvore que bate o tipo (F/C/R).
- Para raises, faz fuzzy match no `amount` (chips, convertidos do `amount_bb` via blinds do `settings.json`) — escolhe a acção da árvore com `amount` mais próximo do real.
- Desce para o nó filho.

**Output:** nó final + `path` (lista de node_indexes percorridos).

### 5.5 Lado GTO — UI no replayer

`frontend/src/pages/ReplayerPage.jsx:239-360,627-815`.

Quando uma mão carrega no replayer:

1. Extrai metadados da mão (`hand.all_players_actions._meta`): jogadores, posições, stacks, level, site.
2. Identifica o Hero, calcula a sua stack em BB.
3. Constrói o input para `/api/gto/match`: format (PKO vs Vanilla, por regex no raw), posições e stacks de todos os jogadores (separados em active vs remaining em relação à posição do Hero).
4. Chama `/api/gto/match`. Guarda o top match.
5. Parseia as acções pré-flop da HH bruta (regex no `raw`).
6. Identifica a acção do Hero na sequência.
7. Chama `/api/gto/navigate` com as acções **anteriores** ao Hero → navega até ao nó onde o Hero está prestes a decidir.
8. Mostra na tab GTO: o range que o Hero deve jogar naquele spot.

### 5.6 Lado FIELD — não existe ainda

Construção planeada na Fase 3. Componentes:

- **Schema** BD para stats agregadas: tabela tipo `field_stats_preflop` com chave composta `(format, num_players, position, stack_bucket, phase)` e valores agregados (frequências, sample sizes).
- **Worker de agregação** que percorre HHs importadas (`hands.raw` na BD) em batches e popula a tabela. Pode correr nightly cron.
- **Buckets de stack** (a definir empiricamente; sugestão inicial: 0–10 / 10–15 / 15–20 / 20–30 / 30–50 / 50–80 / 80+ BB).
- **Endpoint** `/api/field/match` análogo ao `/api/gto/match`.
- **Tab FIELD** no replayer ao lado de GTO.

---

## 6. Estado actual (Maio 2026)

| Peça | Estado | Detalhe |
|---|---|---|
| Schema `gto_trees`+`gto_nodes` | ✓ deployed | `gto.py:14-28` |
| Matching engine v3 | ✓ deployed | `/api/gto/match`, pesos calibrados |
| Navegação | ✓ deployed | `/api/gto/navigate` |
| Import manual | ✓ deployed | `/api/gto/import`, requer upload de zip + form |
| Página `/gto` (gestão da biblioteca) | ✓ deployed | `GTOBrain.jsx` |
| Tab GTO no replayer | ✓ deployed | `ReplayerPage.jsx` |
| Match automático ao carregar mão | ✓ deployed | dispara `/api/gto/match` no `useEffect` |
| Navegação até ao nó do Hero | ✓ deployed | usa `/api/gto/navigate` |
| Pipeline Watcher HRC → app | ✓ ciclo completo validado (pt35) | Validado ponta-a-ponta no Beelink em pt35 (smoke real `GG-5944816316`): app → adapter → watcher → adapter → app, `.zip` final 44 MB. Antes só mecânico (pt23). |
| Watcher exporta Complete Export + Depth útil | ✓ deployed (pt35) | `export_strategies` (SWAP em `patched_funcs.py`) muda o combo do diálogo Export Strategies de "Manual Selection" → **"Complete Export"** via Win32 `CB_SETCURSEL` (idx **0→1**, confirmado por read-back) + `CBN_SELCHANGE`; OK por `BM_CLICK`; Save As via `_save_as_set_and_click` portado (clipboard + `BM_CLICK` no Save). Complete Export **ignora o Depth** (smoke do Rui), por isso não se escreve no campo. `.exe` SHA256 `33eae43a…c53c4f`. |
| Trees importadas em produção | ✗ ~0 | Rui não importou manualmente; pipeline automático ausente |
| Import automático Watcher → `gto_trees` | ✗ AUSENTE | Zip recebido em `/api/queue/hrc/results` vai só para `hrc_jobs`, não para `gto_trees`+`gto_nodes` |
| Navegação a nós que não o Hero | ✗ AUSENTE | UI hoje navega só até ao nó do Hero |
| Display visual do range (grelha 13×13 com pesos/EVs) | ◐ parcial | Código presente, validação visual pendente |
| Tab FIELD no replayer | ✗ AUSENTE | |
| Pipeline agregador do field | ✗ AUSENTE | |

---

## 7. Plano de evolução (3 fases)

### Fase 1 — Robot exporta trees úteis e ciclo fechado

**Objectivo:** garantir que cada mão calculada pelo watcher chega ao GTO Brain com profundidade que serve o caso de uso pré-flop.

**Trabalho:**
1. Decisão empírica de Depth: smoke manual no HRC com Complete Export Depth 5/6/7 sobre uma mão já calculada → comparar tamanhos do `.zip`, escolher o melhor compromisso entre cobertura pré-flop e tamanho. Foco apenas pré-flop ⇒ Depth ≈ 5 deve chegar.
2. Patch em `tools/watcher_src/patched_funcs.py` (função de export): mudar dropdown do diálogo "Export Strategies" para **"Complete Export"**, escrever Depth alvo no campo, OK. Hoje o patch só abre o diálogo e clica OK sem mexer nos defaults.
3. Recompilar o `.exe` do watcher e instalar no Beelink.
4. Smoke real ponta-a-ponta: marcar mão na app → adapter pull → watcher processa → adapter push → confirmar `hrc_jobs.result_zip_size` razoável e zip parseável.

**Estado de saída:** cada mão marcada para HRC produz uma árvore consumível pelo GTO Brain.

#### Fase 1 — smoke battery de robustez pré-Fase 2

Antes de avançar para a Fase 2 (auto-import `.zip` → `gto_trees`), validar o
pipeline ponta-a-ponta em **4 combinações de site × formato**. Cada smoke segue
o mesmo padrão da pt35 (marcar mão na app → adapter pull → watcher → adapter
push → `.zip` em `hrc_jobs` com dezenas de MB e milhares de nós).

Combinações alvo:

1. **GG NKO Vanilla** — formato sem KO (MTT regular ICM puro, sem bounty).
   Mystery KO **NÃO** conta como NKO (é PKO com bounty hidden mas progressive).
   Valida o pipeline em estrutura não-bounty: `lobby_vision.LOBBY_RATIO_LOOKUP`
   devolve `None`/`0.0`; `hrc_script_gen` sem bounty config; cálculo HRC
   vanilla ICM.
2. **PokerStars PKO** — primeiro site não-GG. Valida hero_aliases
   (`kokonakueka` / `misterpoker1973`) + parser HH PokerStars.
3. **Winamax PKO** — valida alias `thinvalium` + parser HH Winamax.
4. **PokerStars NKO Vanilla** — combinação extra; potencial revelar edge cases
   na intersecção de site não-GG com formato vanilla.

**Ponto de partida (validado):** smoke pt35 = GG PKO 50% (`GG-5944816316`,
Bounty Hunters Daily, 44 MB / milhares de nós).

Tracking: `#PIPELINE-ROBUSTNESS-SMOKE-BATTERY` em `docs/TECH_DEBTS_INVENTARIO.md`.

### Fase 2 — Acumular trees automaticamente no GTO Brain

**Objectivo:** transformar cada `.zip` recebido pelo adapter em entries em `gto_trees`+`gto_nodes` sem intervenção do Rui.

**Trabalho:**
1. Estender `POST /api/queue/hrc/results` (em `backend/app/routers/queue.py`): após gravar em `hrc_jobs`, chamar também `parse_hrc_zip()` (já existe em `gto.py:70`) e fazer insert em `gto_trees`+`gto_nodes`.
2. Derivar metadados automaticamente (eliminar form manual):
   - `format` — do `tournament_summaries.tournament_format` ou `tournament_payouts.payouts_json.structures[0].bountyType`.
   - `num_players` — do parser HH (existe `derive_max_players`).
   - `hero_position` — do match SS↔HH (existe `player_names`).
   - `hero_stack_bb_min`/`max` — do parsing pré-flop da HH (stack do Hero no momento da decisão).
   - `tournament_phase` — derivada do `level` + `site` (helper `_phase_from_level` já existe em `gto.py:138`).
3. Decisão pendente: **descartar zips brutos em `hrc_jobs`** após import bem-sucedido (libera espaço, evita duplicação de storage) **ou manter para auditoria** (debugging futuro). Recomendação preliminar: manter por agora, decidir a sério após Fase 2 estabilizar.

**Estado de saída:** biblioteca cresce sozinha conforme o Rui marca mãos para HRC.

### Fase 3 — UI rica + tab FIELD

**Objectivo:** transformar a tab GTO actual num painel completo + construir o lado field.

**GTO — extensões:**
1. **Navegação interactiva** — clicar em qualquer ramo da árvore para descer ao nó correspondente. Hoje a UI só pousa no nó do Hero; precisa de permitir cliques que descem a árvore.
2. **Display visual do range** em grelha 13×13 com pesos (frequência de jogar cada acção) e EVs.
3. **Múltiplos pontos de decisão** — não só o do Hero. Para o caso canónico (§4), preciso de ver o que o BTN faz vs open do MP, o que o Hero faz vs 3-bet do BTN, e o que o BTN faz vs 4-bet do Hero. Três pontos de navegação, não um.

**FIELD — construção nova:**
1. **Schema BD** para stats agregadas (tabela `field_stats_preflop` ou equivalente).
2. **Worker de agregação** que processa HHs importadas em batches e popula a tabela. Pode correr nightly cron.
3. **Buckets de stack** — definir empiricamente. Sugestão inicial: 0–10 / 10–15 / 15–20 / 20–30 / 30–50 / 50–80 / 80+ BB.
4. **Endpoint** `/api/field/match` análogo ao `/api/gto/match`.
5. **Tab FIELD** no replayer ao lado de GTO.

**Estado de saída:** Rui revê uma mão e vê GTO + FIELD ao lado, com navegação interactiva em ambos.

---

## 8. Decisões importantes (com justificação)

### 8.1 Pré-flop primeiro, pós-flop depois

Razões:
- Cobre a maioria dos spots de dúvida que o Rui marca durante o jogo.
- Reduz drasticamente a profundidade da árvore necessária ⇒ trees pequenas (poucos MB) ⇒ acumulação viável.
- Permite iterar a UI e o matching engine sobre dados reais antes de complicar com pós-flop.

Pós-flop só depois de pré-flop estar sólido em produção.

### 8.2 Depth ≈ 5 para o export, não Depth 10+

O export do HRC ("Hand > Export Strategies") tem um campo Depth que controla quantos níveis de decisão a árvore exportada captura. Depth alto ⇒ ficheiros gigantes (centenas de MB), inviável para acumular.

Para pré-flop only, Depth ≈ 5 cobre:
- Nível 1: open
- Nível 2: respostas (fold/call/3-bet) de cada jogador a seguir
- Nível 3: 4-bet do opener vs 3-bet
- Nível 4: 5-bet/jam vs 4-bet
- Nível 5: call vs 5-bet

Decisão final empírica, a confirmar com smoke (§7 Fase 1).

### 8.3 Storage fragmentado (`gto_nodes` 1-linha-por-nó), não BLOB

Permite queries pontuais (1 nó específico) sem carregar a árvore inteira. Trade-off: import demora um pouco mais, mas leitura é muito mais rápida — e o use case é leitura intensiva (matching + navegação) com import esporádico (uma árvore por mão marcada).

### 8.4 Matching engine na BD, trees pequenas, sem trees gigantes em disco

Existe a hipótese alternativa de manter trees gigantes em disco e indexar só metadados na BD. Após confirmação de que pré-flop só precisa de Depth ≈ 5 (⇒ trees de poucos MB), a opção "tudo na BD" volta a ser viável e simplifica a arquitectura. Mantém-se assim por agora.

**Nota importante de terminologia:** o "Save As" do HRC tem **dois significados distintos** que causaram confusão durante o desenvolvimento:
- `File > Save As` — guarda a **sessão inteira** do HRC em formato proprietário. Ficheiros gigantes (centenas de MB). Não é o que o GTO Brain consome.
- `Hand > Export Strategies` — exporta **estratégias em JSON** (`settings.json` + `equity.json` + `nodes/*.json`). Tamanho controlado por Depth + Mode. **É este que o GTO Brain consome.**

### 8.5 Integração no replayer, não página separada

A informação aparece dentro da vista da mão, não numa página `/gto` standalone. A página `/gto` existe só para gestão (CRUD da biblioteca).

### 8.6 Cobertura > stack absoluto no matching (futuro do scoring)

O matching engine v3 actual (§5.3) usa scores por stack absoluto. Em ambos os formatos (Vanilla e PKO, ver §3.7), isto está sub-óptimo: penaliza diferenças que **não importam** desde que a cobertura se mantenha. PKO amplifica o efeito via bounty; Vanilla também o tem via bubble factor. Refinar o scoring para considerar primariamente a **relação de cobertura** entre os jogadores envolvidos no spot (e secundariamente o stack absoluto) é trabalho a fazer na Fase 3 ou depois, com base em observação de matches reais.

---

## 9. Tech debts conhecidos (relacionados com GTO Brain)

| ID | Severidade | Resumo |
|---|---|---|
| `#GTO-WATCHER-EXPORT-DEFAULT-DEPTH-2` | ✅ FECHADO (pt35) | ~~Watcher exporta em "Manual Selection" Depth 2 sem selecção = 1 nó.~~ Fechado na Fase 1: `export_strategies` (SWAP) muda o combo para "Complete Export" (idx 0→1, read-back), OK por `BM_CLICK`. Smoke real `GG-5944816316` = 44 MB (era 1 nó / ~6 KB). |
| `#GTO-IMPORT-AUTOMATICO-AUSENTE` | 🔴 HIGH | Pipeline auto Watcher → `gto_trees` não existe. Sem isto, biblioteca não cresce. Fase 2. |
| `#GTO-NAVIGATE-SO-HERO-NODE` | 🟡 MED | UI hoje só navega até ao nó do Hero. Para ver decisão de vilões (caso canónico do BTN 3-bettar vs open do MP), precisa de navegação multi-spot. Fase 3. |
| `#FIELD-PIPELINE-AUSENTE` | 🟡 MED | Lado Field completo por construir. Fase 3. |
| `#GTO-METADADOS-DERIVACAO-AUSENTE` | 🟢 LOW | Hoje o import manual exige o Rui preencher form com format/phase/hero_position. Para automatizar, helpers de derivação não estão prontos. Fase 2. |
| `#GTO-RANGE-VISUAL-VALIDACAO` | 🟢 LOW | Display em grelha 13×13 com pesos/EVs tem código mas não foi validado visualmente com dados reais. Fase 3. |

---

## 10. Cross-references

**Código:**
- `backend/app/routers/gto.py` — routers, matching engine, parser
- `frontend/src/pages/GTOBrain.jsx` — página de gestão da biblioteca
- `frontend/src/pages/ReplayerPage.jsx:239-360,627-815` — integração no replayer
- `backend/app/routers/queue.py` — recepção de zips do adapter (entrada futura do pipeline automático)
- `tools/watcher_src/patched_funcs.py` — watcher patches (a montante)
- `tools/hrc_adapter/hrc_adapter.py` — adapter Beelink (intermediário)

**Documentos:**
- `docs/VISAO_PRODUTO.md` — visão geral da app (menção breve ao GTO Brain)
- `docs/REGRAS_NEGOCIO.md` — regras operacionais (menção breve ao GTO Brain)
- `docs/HRC_ANATOMIA_OPERACIONAL.md` — anatomia operacional do HRC (peça a montante)
- `docs/JOURNAL_2026-05-22-pt30-pt34.md` — última sessão de trabalho no watcher
- `docs/MAPA_ACOPLAMENTO.md` — conceitos da app e quem os produz/consome
- `docs/TECH_DEBTS_INVENTARIO.md` — backlog actualizado de tech debts

---

## 11. Como manter este documento vivo

- Qualquer mudança que afecte o GTO Brain (schema, endpoints, UI, pipeline) → actualizar aqui na mesma sessão.
- Decisões novas que tomem caminhos diferentes do plano → registar em §7 ou §8 com data.
- Tech debts novos relacionados → §9.
- Quando uma das 3 fases fechar, marcar em §6 como completo e mover o respectivo conteúdo de §7 para um "Histórico" (não apagar — manter a evolução visível).
- Versão no cabeçalho aumenta de v1 → v2 → ... a cada actualização significativa.

---

**Fim do documento.**
