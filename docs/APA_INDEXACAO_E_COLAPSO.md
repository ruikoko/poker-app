# APA — indexação por nome e colapso de lugares (investigação + ideia em discussão)

> **Estado (3 Jul 2026):** documento de **registo de investigação**. O **diagnóstico** (§A) está
> FECHADO. A **ideia de mudança do core** (§B) está **NÃO APROVADA** — há uma desconfiança do Rui
> por resolver (ver §B.4). **Nenhum código do core foi escrito.** O mapa de acoplamento completo
> (§C) é o PASSO 1 produzido nesta sessão. Cross-ref: `DESANON_ANATOMIA.md`, `MAPA_ACOPLAMENTO.md`
> (§2.1 match_method), `#DESANON-SITTING-OUT-NPLUS1-NO-UNIVERSAL-GUARD`, `#DESANON-GOLD-SCRAMBLE`.

## Contexto que motivou tudo

Os **dados actuais da app vão ser apagados e reimportados.** Por isso abandonou-se toda a **cura
de dados** (lote das 44 mãos partidas, propagação manual, demo com guardas). O objectivo passou a
ser **curar o CORE** para que os mesmos dados entrem direitos quando forem reimportados.

---

## §A. Diagnóstico (FECHADO)

### A.1 O sintoma
A secção MESA do detalhe mostra **menos lugares do que a mão tem**. O histórico bruto (HH) tem N
linhas `Seat`, mas o `all_players_actions` (apa) guardado tem N-1 ou N-2. Um jogador **desaparece
da MESA**. Caso âncora: **GG-6118579134** (5 no bruto, 4 na app — o `MaLong07` sumiu).

### A.2 Varrimento de integridade (read-only, universo de ESTUDO)
Endpoint `GET /api/table-ss/seat-integrity-scan?tagged_only=true` — só mãos GG 2026 **com etiqueta**
(hm3_tags OU discord_tags), que é o universo de estudo.

- **Universo: 738 mãos etiquetadas.**
- **189 com achados** (25,6%). Repartição por severidade:
  - **A — colapso de lugares: 44** (o bruto diz N, o apa tem N-1/N-2). **Todas `table_ss`/`unverified`.** É o problema a sério.
  - **B — hash por mapear: 98** (hash do bruto fora do anon_map; sem colapso = lacuna honesta).
  - **C — nome solto: 188** (nome no players_list sem hash — 81 são C-only = **sitting-outs/extras da Vision**, honesto, não é mão partida).
- Nenhuma das 7 mãos `verified` afetadas tinha **A (colapso)** — não há mão verificada com nome errado/jogador desaparecido.

### A.3 As DUAS causas do colapso (confirmadas)
1. **Colisão de nomes — dois hashes com o MESMO nome fundem lugares.** O apa é indexado por nome;
   se dois hashes recebem o mesmo `real_name`, a segunda escrita esmaga a primeira → um lugar cai.
   Caso: **GG-6118579134 / `MaLong07`** (o BB e o BTN colidiram num só nome; 5→4).
2. **Lugar sem nome cai — hash nunca mapeado não fica guardado.** Um hash que nunca entrou no
   anon_map perde-se na re-indexação por nome. Caso: **GG-6083416072** — um lugar (o **sitting-out**)
   não foi mapeado e sumiu.

### A.4 A raiz única
**`_enrich_all_players_actions` (`backend/app/routers/screenshot.py` ~L1033)** re-indexa o apa por
`real_name`: `enriched[real_name] = info`. É **a única linha** que transforma a chave-hash (segura,
1 por jogador) numa chave-nome (que colide e deixa cair). Todos os caminhos de escrita (SS-match,
`table_ss_deanon`, `/set-anon-map`, `/redeanon`, `reenrich-scrambled-gold`, `mtt._promote`,
`_insert_hand`) passam por este mesmo enrich.

### A.5 Contaminação descoberta — *wrong name is poison*
No torneio **290795101** (Bounty Hunters Big Game $215, Table 19), o hash **`90abe28`** está
**mal-etiquetado "V Bartko"** em **7 mãos**. O **V Bartko real é `f0a5886f`** (consistente; na
GG-6083416607 `f0a5886f`=V Bartko e `90abe28` está sem nome). Ou seja, `90abe28` é um jogador
**desconhecido** sistematicamente rotulado com o nome de outro (erro do stack-elimination repetido).

**Lição:** a propagação por maioria **confirmaria o erro** (7 mãos dizem "V Bartko" para `90abe28`).
A regra "um-hash→vários-nomes = conflito" NÃO apanha o inverso (**um nome em dois hashes**). Qualquer
propagação futura precisa da guarda **"não propor um nome já atribuído a OUTRO hash no torneio"**.
**Nome errado é veneno — não propagar.**

### A.6 A Vision não extrai sitting-outs (mesmo legíveis)
A IA que lê as imagens **não capta jogadores sentados que não jogaram a mão**, mesmo quando o nome
e a coroa estão perfeitamente legíveis na captura. Exemplo real do Rui: **J Rosenwasser**, com nome
e **coroa $50** bem visíveis, não foi extraído. Isto liga a causa A.3-(2): o sitting-out nem sequer
chega ao anon_map, e depois cai na re-indexação. (Frente futura: prompt da Vision extrair sitting-outs.)

---

## §B. Ideia em discussão — **NÃO APROVADA**

> **Estado: proposta. O Rui NÃO aprovou.** Há uma desconfiança por resolver (§B.4). Não escrever
> código do core até isso ficar resolvido e o desenho aprovado.

### B.1 A mudança
Mudar a **chave** do apa de `real_name` para a **identidade da HH**:
- **GG:** o **hash** (`89ef4cba`).
- **Outras salas (WN/PS/WPN):** o **nick real** (a HH traz nomes reais; o nick é a identidade).

O nome passa a **atributo** (`real_name`) que **pode estar vazio** (branco = por mapear, honesto).
A única mudança de escrita: `_enrich_all_players_actions` **deixa de re-indexar** — mantém a chave e
escreve `real_name = anon_map.get(hash) or ""`.

### B.2 Regra de leitura retro-compatível
Nome de exibição = **`real_name || chave`**. Funciona com o formato **antigo** (chave=nome) E **novo**
(chave=hash, real_name=nome ou vazio) → permite fasear **leitores → writer** sem janela partida.

### B.3 Compatibilidade prevista com as frentes SEGUINTES (não construídas)
- **Sitting-out (Vision):** entra como entry com `played:false` e sem `actions`; como a chave é a
  hash, coexiste sem fundir. Campo `played` reservado.
- **Guarda de nome-já-usado:** com os dois hashes visíveis (sem colapso), passa a poder detectar
  "duas hashes → mesmo `real_name`" (hoje o colapso escondia-o).
- **Propagação automática por torneio:** a chave-hash é a âncora estável (hash fixo por jogador) →
  a propagação escreve só o atributo, sem tocar na estrutura. (Com a guarda de A.5.)

### B.4 ⚠️ A dúvida do Rui a resolver ANTES de qualquer decisão
A relação entre **dois níveis de identidade** ainda não ficou convincente:
- **Nível-MÃO / torneio:** o **hash** é a identidade (fixo por jogador **dentro** do torneio; segue
  o jogador entre mesas — `DESANON_ANATOMIA §3.3`).
- **Nível-JOGADOR / entre torneios:** o **nome real** é a identidade (os **Vilões** agregam o mesmo
  jogador **através** de torneios; o hash muda de torneio para torneio).

A proposta usa o hash como chave do apa (nível-mão), mas os Vilões precisam do nome (nível-jogador).
**A explicação de como os dois níveis convivem sem se atropelarem ainda não convenceu o Rui.** É o
ponto a fechar antes de decidir.

### B.5 Decisão de contexto
Os dados vão ser **apagados e reimportados** → **sem migração**; a regra `real_name||chave` torna a
mudança de leitores segura mesmo antes do writer.

---

## §C. ANEXO — mapa de acoplamento do apa (PASSO 1, 3 Jul 2026)

Estrutura do apa: dict cujas CHAVES são hash (GG anón.) / nick real (pós-enrich ou não-GG) / `"Hero"`,
mais `_meta`. Cada valor: `seat, position, stack, stack_bb, is_hero, real_name, bounty_value_usd,
bounty_pct, cards, actions`.

### C.1 Writers (onde o apa é construído/guardado)
| Etapa | Ficheiro:função | Chave |
|---|---|---|
| Parser GG | `parsers/gg_hands.py:497-524` (`parse_hands`) | **hash** / `"Hero"` |
| Parser HM3/WN/PS | `routers/hm3.py:586-608`, `parsers/winamax.py`, `routers/import_.py:117-127` | **nick real** |
| **★ RE-KEY (raiz)** | **`routers/screenshot.py:995-1035` `_enrich_all_players_actions`** | **re-indexa por `real_name`** (L1033) |
| Guardar + `has_showdown` | `hand_service._insert_hand:203+` | grava a coluna |

Todos os caminhos de deanon/reparação chamam o **mesmo enrich** e depois `UPDATE all_players_actions`:
`screenshot` (SS-match, orphan, reenrich-scrambled-gold), `table_ss_deanon` (`deanon_hand`,
`reconcile_tournament_deanon` — faz `_rekey_apa_to_hashes` L310 antes, sintoma directo do problema),
`table_ss` (`/set-anon-map`, `/set-bounties`, `/redeanon`, restore), `hands` (redeanon, reenrich,
backfill-meta), `mtt._promote` (indexa por real_name), `hand_service._insert_hand`.

### C.2 Readers — usam a CHAVE como identidade (PARTEM com hash-key)
| Sítio | O que faz | Consequência |
|---|---|---|
| **`services/villain_rules.py:179` `_build_candidates`** | chave = nick → `hand_villains.player_name` + `villain_notes.nick`; salta `_is_anon_hash` | **ZERO vilões** |
| **`services/ire.py:351` `_assemble_ire`** | chave = `nick`; bounty por `bounty_by_nick.get(nick)`; `per_opponent.nick`=chave | IRE sem nome + bounty 0 |
| `services/hand_service.py:145` `_resolve_hashes_in_raw` | chave = nome real p/ reescrever o raw | raw fica com hashes |
| `routers/mtt.py:643` `apa_for_mapping` | chave = nome p/ criar vilões MTT | criação MTT parte |
| `routers/hands.py:637` filtro `all_players_actions ? %s` | query da chave como nick (param `villain`) | filtro parte |
| `routers/table_ss.py` `/set-anon-map` (1718), `/set-bounties` (1783/1797) | juntam `players_list.name`→chave | reparações partem |
| `routers/hm3.py:1665` backfill-actions | junta nomes parseados às chaves | (GG hash≈hash, ok) |

### C.3 Readers — já lêem o CAMPO (seguros)
`table_ss.hand_seats:2483` (`real_name` first), gold-crown backfill:2098, `hrc_verify`, `hrc_queue`,
`tournament_meta`, `table_ss` gap/fit/detail, e todos os leitores só-`_meta` (mtt/hm3/villains/equity list).

### C.4 ★ NÃO lêem o apa (fora do âmbito — menos ruptura)
- **`services/queue_export.py` (export HRC)** — lê `raw` + `player_names.players_list`, **não o apa**.
- **`routers/gg_health.py`**, **`routers/suspicious.py`**, **`services/deanon_status.py`** — não lêem apa.

### C.5 Frontend — TODOS usam a CHAVE como nome; `real_name` NUNCA é lido
| Sítio | Padrão |
|---|---|
| **`lib/handParser.js:109` (`parseHH`, CENTRAL)** | `.map(([name,info])=>({name,...info}))` — alimenta Replayer/HistoryViewer/ReplayerPage |
| `HandDetailPage.jsx:59`, `Hands.jsx:194` (`normaliseActions`) | chave = nome |
| `Villains.jsx` | `apa[villainNick]` (lookup directo) + `p.name === villainNick` |
| `ReplayerPage.jsx:244/259` | chave + `HERO_NAMES_ALL.has(key)` (GTO) |
| match por nome | IRE `o.nick === p.name` (HistoryViewer:258); ponte `nameMap` raw-hash→chave (`handParser:118-157`) |
| Seguros (só campos) | `HandRow` (`_meta`+`ire.main_villain`), loops SI (`is_hero`), `GGHealth` (estrutura à parte) |

### C.6 O que reduz o risco
O matching por nome (IRE `o.nick===p.name`, vilão `p.name===villainNick`) **continua a funcionar se
`p.name` passar a ser o `real_name`**. A mudança concentra-se em **quem CONSTRÓI o objecto-jogador**
(`handParser` no frontend; `_build_candidates`/`_assemble_ire`/`_resolve_hashes` no backend) — os
sítios de *comparação* não mudam. Chokepoints: `handParser` (frontend), `_enrich` (backend).

### C.7 Dimensão honesta
**~15-18 sítios**, quase todos mecânicos (`chave → real_name||chave`). **3 delicados:** `_enrich`
(writer), `villain_rules._build_candidates` (escreve nos vilões), `ire._assemble_ire`. HRC/Saúde
GG/suspeitas fora do âmbito. **Sem migração** (dados apagados). Frente **média-grande**, uma só.
Testes obrigatórios: criação de vilões, IRE, MESA/replayer, `has_showdown`, idempotência do re-enrich.
