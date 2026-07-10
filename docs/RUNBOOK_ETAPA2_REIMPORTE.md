# RUNBOOK — Etapa 2: reimporte do resto de 2026 (GG HH + TS)

**Objectivo:** meter na app o material GG de 2026 que ainda falta (Jan–Jun, + o que
falte de Jul), a partir do arquivo já organizado e verificado em
`C:\Users\User\Documents\Poker\GG\{HH|TS}\2026-MM\` (195 ficheiros, hashes
confirmados, Fase 2). **TS primeiro, HH depois.** Faseado, com checkpoints. A fila
HRC fica **parada** todo o tempo. No fim: **4 gates a 0 + 294738291 na edição certa +
roteiro do MAPA_AUDITORIA_VISUAL**.

> **Regra de ouro (do MAPA):** se em qualquer paragem aparecer um **🔴** (contaminação
> >0, GG anónima no Estudo, vilão em mão sem match), **PÁRA e reporta — nunca consertar
> à mão**. Os dados reimportam-se; o que interessa é o core.

---

## 🎯 ÂMBITO (decisão do Rui, 10 Jul) — SEM wipe, JUNHO → hoje

- **Continua-se POR CIMA do estado atual** (não há wipe). O **gatilho TS-tardio** cobre a ordem
  (TS pode chegar depois das HH; o reconcile resolve). Backup restore-verificado feito como novo
  ponto de partida (`_local_only/backup_etapa2_20260710/`, 24 884 mãos).
- **Âmbito = Junho → hoje.** **Jan–Maio NÃO se importa** — fica na cópia `Poker\GG\…\2026-0[1-5]\`
  como arquivo, **fora do plano**. (Se um dia se quiser, importa-se da cópia; não é para agora.)
- **Buracos que NÃO se tapam da cópia (confirmado por conteúdo, 10 Jul):** os dias sem mãos de
  Jun/Jul **não estão na cópia nem na BD** — `06-07/10/17/19/20/27/28/29` e `07-03→07-08`. Ou são
  **dias sem jogo**, ou a HH **só existe no backoffice**. A cópia cobre em Jul só `07-01/02/09`.
  → o que faltar mesmo (se jogaste) vai-se buscar ao **backoffice**, não à cópia.

## ⚠️ Antes de tudo — o que NÃO vai à app + tamanhos

- **Só GG HH/TS.** Não subir ao `/api/import`: **bundles HRC** (`hrc_GG-*.zip`,
  `GG-*.zip`, `queue_*.zip` — trazem `meta.json`/`payouts.json`/`script.js` ao lado de um
  `hh.txt`) nem **packs PS/WN** (`Poker_Hands_PS_*`, etc.). A pasta `Poker\GG\HH|TS\2026-MM\`
  já foi **limpa** destes intrusos (11 Jul) — importar a partir dela é seguro.
  - *Como se coaram no arquivo:* os bundles HRC têm um `hh.txt` GG lá dentro → passaram por HH;
    os packs PS/WN têm `tournament_number` → passaram pelo filtro. Regra: **GG = `GGPoker` no
    conteúdo**, não "tem torneio".
- **Tamanho.** Não há limite explícito no código; o bloqueio é do **proxy (Railway)/uvicorn**
  no upload manual de ficheiros grandes. Os zips **GG são pequenos (≤ ~17 MB)** → sem problema.
  **Usa o `appimport`** (pasta → um toque; posta **ficheiro-a-ficheiro**) em vez de arrastar
  zips grandes na UI: mata o bloqueio por tamanho de raiz. Se algum ficheiro GG for
  invulgarmente grande (>~50 MB), importa-o pela pasta/appimport (per-file) — **nunca**
  extrair para o partir.
- **NÃO subir ad-hoc fora de ordem** (lição desta sessão): um upload manual precipitado meteu
  ~9,9k mãos de meio-Junho **fora de ordem e incompleto** por cima do baseline. Segue as fases.

## 0. Pré-voo (antes de importar nada)

- [ ] **Salas de poker fechadas** (regra de ouro do CLAUDE.md) — nada de HM3/HUD/salas abertas.
- [ ] **Raiz 2 no ar** (deployed 11 Jul, `8332cba`): o resolver de edições + crivo estão
      LIVE. Confirma que o backend responde em `GET /api/gg-health/lobby-edition-scan`.
- [ ] **Fila HRC PARADA** e assim fica:
  - `GET /api/queue/hrc/gate` → confirmar fechada.
  - **NÃO** clicar "Enviar ao HRC" no painel `/hrc`; **NÃO** correr o adaptador no Beelink.
  - Os imports e o reconcile **não** disparam o robot sozinhos (fila 100% manual, pt68/pt92).
- [ ] **PASSO 0 — Backup + WIPE (operacional, do Rui; o Code só tem leitura de prod):**
  1. **Backup** da BD **restore-verificado** ANTES de tudo (padrão pt47/pt68).
  2. **WIPE**: `TRUNCATE … RESTART IDENTITY CASCADE` das tabelas de dados,
     **preservando `users`, `stat_ideals`, `monthly_stats`** (como nos wipes anteriores).
  3. Confirmar **tabelas de dados a 0** antes de importar (hands/tournament_summaries/
     tournament_payouts/lobby_processing_log/hrc_jobs = 0).
  > O reimporte só arranca **depois** deste Passo 0 confirmado. O Code não executa o wipe
  > (só tem `~/.pokerapp_db_ro.env`, leitura); dá suporte a cada fase a seguir.
- [ ] **Baseline dos 4 gates** (correr agora, ANTES; anotar os números — hoje o das edições
      dá **1**, tn 294738291; ver §4). Serve para comparar no fim.

---

## 1. FASE A — Tournament Summaries (TS) PRIMEIRO

**Porquê TS antes:** o resolver de edições (Raiz 2) e o funil das coroas dependem do TS —
`tournament_summaries` dá `start_time` + `buy_in_total` + `total_players` (as provas H1/H2 da
desambiguação) e `buy_in_bounty` (a base das coroas). Sem TS presente, o gluing de edições e o
scrub das coroas não têm chão. Por isso o TS entra **antes** das HH e da resolução de lobbys.

**Como (pasta → um toque, `tools/appimport`):**
1. Copiar os `.zip` de **`Documents\Poker\GG\TS\2026-MM\`** para a pasta de import
   `…\poker_import\gg_ts\` (o `PARENT_DIR` do `config_local.py`).
2. Duplo-clique em **`Import.bat`** → corre **dry-run** (mostra o plano, não envia).
3. Confirmar o plano e deixar enviar → `POST /api/tournament-summaries/import` por ficheiro.
   Dedup: TS é **upsert** por `(site, tournament_number)` → reenviar é seguro.
4. *(Alternativa sem appimport: upload dos `.zip` no botão de TS em `Tournaments.jsx`.)*

**Ordem sugerida:** por mês, do mais antigo ao mais recente (2026-01 → 2026-06 → resto de -07).
Um mês de cada vez torna os checkpoints legíveis.

**⚠️ Os 2 MISTOS estão em HH\ mas têm TS lá dentro** — `Nova pasta.zip` (02–03/2026) e
`jan.rar` (01/2026). Na Fase A, **incluir também estes 2** no lote de TS (metê-los em
`gg_ts\` além de ficarem no HH). O parser de TS extrai só a parte de summaries; o dedup
protege o duplo processamento. (Nota: `jan.rar` é `.rar` — o appimport lê `.zip/.txt`; se
não apanhar `.rar`, fazer o upload do que interessa pela UI, **sem extrair**, ou converter à
parte com ordem tua. Não extrair para temp.)

### ✅ Checkpoint A (fim da Fase A)
- [ ] `Saúde Import` → cano **hh_ts** sem falhas por explicar.
- [ ] `tournament_summaries` cresceu para o esperado (contagem por mês) — ver em Torneios/query.
- [ ] O **reconcile de lobbys** disparou (fire-and-forget no fim do import de TS): lobbys que
      estavam `tm_not_found`/`edition_quarantine` podem ter resolvido. **Não** forçar nada.
- [ ] **Nenhum 🔴.**

---

## 2. FASE B — Hand Histories (HH) DEPOIS

**Como:**
1. Copiar os `.zip` de **`Documents\Poker\GG\HH\2026-MM\`** para `…\poker_import\gg_hh\`.
2. `Import.bat` → dry-run → confirmar → `POST /api/import` por ficheiro. Dedup: HH por
   `hand_id` (placeholders GGDiscord tratados) → reenviar é seguro.
3. **Mês a mês**, do mais antigo ao mais recente, com checkpoint entre lotes.

**⚠️ Os 2 mistos** (`Nova pasta.zip`, `jan.rar`) entram aqui como HH normalmente (a parte de
mãos); a parte de TS já foi na Fase A. Não é preciso mais nada além de os deixar no `gg_hh\`.

**O que dispara sozinho no fim de cada import de HH (fire-and-forget, deixar correr):**
- `reconcile_lobby_logs` — re-resolve lobbys contra as mãos/TS agora presentes (com Raiz 2:
  edições ambíguas → `edition_quarantine`, não colam às cegas).
- `relink_orphan_table_ss` — liga capturas de mesa órfãs às mãos novas.
- `refresh_ft_boundaries` — repõe as fronteiras de FT (respeita decisões manuais).
- propagação de nomes (`build_name_map`) — desanon por hash nas tagadas.

### ✅ Checkpoint B (por lote / fim da Fase B)
- [ ] `Saúde Import` → cano **hands** sem falhas por explicar; `deanon.alert` **não** vermelho.
- [ ] `Dashboard` → "Total de mãos" sobe pelo esperado do mês.
- [ ] `Estudo` → **nenhuma GG anónima** aparece; as tagadas com nomes reais estão lá.
- [ ] `Saúde GG → "Nomes em conflito"` / `"Fronteira FT (rever)"` — sem cartões novos por
      decidir (ou carimba-os tu).
- [ ] **Nenhum 🔴.**

> Se um lote destapar um 🔴 (ex.: contaminação de coroa/edição >0), **pára aí** — não continues
> a empilhar meses por cima de um problema. Reporta.

---

## 3. FASE C — Lobbys / payouts (se aplicável)

Os **prémios** (`tournament_payouts`) que alimentam o ICM **não vêm das HH/TS** — vêm das
**capturas de lobby** (SS do `#lobbys` / pasta de lobby do IT / `LOBBY_DIR`). Se a Etapa 2
inclui repor payouts (ex.: pós-wipe), **re-ingerir os lobbys** é o que faz o crivo de edições e
das coroas ter o que medir:
- Correr o pipeline de lobby (appimport `lobby\` / `LOBBY_DIR`, ou o `#lobbys`) **com a Raiz 2
  no ar** → as edições resolvem por prova; ambíguas caem em **quarentena** (painel Saúde GG
  → "Edições de lobby"), não colam.
- **É aqui que o 294738291 se acerta:** com a Raiz 2 a resolver os lobbys do BH Deepstack $88,
  os prints com `entrants` 287/305 (>219) colam à edição **294711510** (irmã), e o
  294738291 nasce com o payout da **sua** edição. Se algum ficar ambíguo → quarentena, o Rui
  decide no painel (`POST /lobby-edition-resolve`).

### ✅ Checkpoint C
- [ ] `Lobbys` → os lobbys do período resolveram (ou aguardam TS em falta, com motivo claro).
- [ ] `Saúde GG → "Edições de lobby (Raiz 2)"` — a quarentena tem só o que é mesmo ambíguo.

---

## 4. ACEITAÇÃO (os 4 gates a 0 + 294738291 + roteiro visual)

Correr os **4 crivos read-only** (todos têm de dar **0**; `>0` = 🔴 PARAR):

| # | Gate | Endpoint | Campo = 0 |
|---|---|---|---|
| 1 | Coroa origem-Vision (verde-KO) | `GET /api/gg-health/eliminated-crown-scan` | `vision_origin_contamination` |
| 2 | Vivo-$0 | `GET /api/gg-health/live-crown-zero-scan` | contaminação |
| 3 | Coroa espúria em não-KO (vanilla) | `GET /api/gg-health/spurious-crown-non-ko-scan` | contaminação |
| 4 | **Edições (Raiz 2)** | `GET /api/gg-health/lobby-edition-scan` | `edition_contamination` |

- [ ] **Gates 1–3 (coroas) = 0** nas tagadas.
- [ ] **Gate 4 (edições) = 0** — e em particular **294738291 = LIMPO** no `lobby-edition-scan`
      (o escritor do payout re-resolve para 294738291; os prints contaminantes foram para
      294711510). Este é **o caso de aceitação do resolver novo** — a Raiz 2 a nascer certa de raiz.

**Roteiro visual — percorrer o `docs/MAPA_AUDITORIA_VISUAL.md` de cima a baixo (16 paragens):**
Dashboard → SS strip → Marcadas → Saúde Import → Saúde GG (nomes/FT) → **Saúde GG scans (agora
4, não 3)** → Mãos suspeitas → SS Mesa → Lobbys → Torneios → Estudo → Vilões → HM3 → Discord
(dormente) → HRC (fila parada, nada preso por engano) → GTO/HRC Sessões. Em cada paragem,
confirmar o veredicto esperado; **🔴 → parar e reportar**.

### Critério de aceitação da Etapa 2 (tudo verdade ao mesmo tempo)
1. **4 gates a 0.**
2. **294738291 na edição certa** (crivo de edições limpo nesse tn).
3. **Roteiro do MAPA_AUDITORIA_VISUAL** percorrido sem 🔴.
4. Fila HRC **intacta/parada** todo o reimporte (nada correu no robot).

Só depois disto se considera a Etapa 2 **aceite** — e só então (com ordem explícita tua) se
mexe na limpeza dos originais e se pondera soltar a fila HRC.

---

## Notas
- **Nada se extrai** em nenhum passo — importam-se os ficheiros-arquivo inteiros (a app lê-os);
  nunca descomprimir para disco.
- **Reenviar é seguro** (dedup: HH por `hand_id`, TS por upsert, SS por `file_hash`).
- **Não consertar à mão** nada que um 🔴 revele — reportar e deixar o reimporte/core resolver.
- Referências: `docs/MAPA_AUDITORIA_VISUAL.md` (roteiro), `docs/JOURNAL_2026-07-11.md` (Raiz 2),
  `docs/PENDENTES.md` (regra de largada + 294738291), `tools/appimport/README.md` (import por pasta).
