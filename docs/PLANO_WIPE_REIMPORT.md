# PLANO — WIPE + REIMPORT (v1, 8 Jul 2026) — LER COM CALMA, NÃO EXECUTAR

> **Isto é um PLANO para o Rui ler antes de puxar qualquer gatilho.** Não executa nada.
> Não apaga, não reimporta, não alimenta a fila HRC, não toca o watcher. Descreve **o quê**,
> **por que ordem**, **o que medir para aceitar** e **como voltar atrás**. O gatilho é do Rui;
> as operações contra a produção correm pelo **servidor/ritual manual**, nunca por script local.

---

## 1. Porquê o wipe (em claro)

Os dados GG atuais foram desanonimizados em Junho, **antes** de o core estar curado e antes do
prompt chama-vs-coroa. Carregam **cicatrizes** que não vale a pena curar mão-a-mão: coroas mal
lidas (chama/VPIP no lugar do bounty), lugares colapsados (jogador some da mesa), nomes fracos
agarrados a hashes errados. A decisão do Rui (3 Jul) foi **curar o CORE, não os dados** — e o
core já está curado (apa-por-hash Fases 1–3 LIVE, guarda de desanon universal, propagação de
nomes por hash, detetor de re-entrada). **O wipe+reimport é o teste de aceitação do core:** com
o pipeline curado, as mãos GG tagadas devem entrar **desanonimizadas à primeira**, sem trabalho
manual. Se entrarem, o core está provado; se não, o reimport diz-nos exatamente onde falha.

## 2. O que este plano NÃO faz (limites)

- **Não alimenta a fila HRC** durante o reimport (a fila fica fechada; o robot não corre).
- **Não toca o watcher** nem o resolve das trees stale (`#F6` dorme; `origin/watcher-gate`
  arruma-se depois — `PENDENTES`).
- **Não estende o âmbito de disco** (`FLUXO §11`): as HH/TS GG vêm do ritual manual do Rui
  (backoffice → pastas); o Code não vasculha o disco.
- **Não decide produto por iniciativa própria** (`FLUXO §12`): qualquer surpresa que mude
  arquitetura pára e vai ao Rui.

## 3. Pré-requisitos (gates ANTES do gatilho)

Nenhum destes é opcional. O wipe só arranca com todos verdes.

| # | Gate | Estado hoje | Porquê é bloqueante |
|---|---|---|---|
| P1 | **`#HRC-REIMPORT-REDEANON-CASADAS` fechado** (item 1 da casa-limpa) | ✅ LIVE | Sem ele, ao reimportar as HH por cima, as capturas casadas **não re-desanonimizavam** (o `_persist_table_ss_match` comparava o `hand_id` string, via `changed=False`) → **todas** as mãos GG com captura casada nasciam **anónimas**. Era o pré-requisito nº1 do wipe. |
| P2 | **Guarda universal de desanon** (item 2, `#DESANON-SITTING-OUT-NPLUS1`) | ✅ LIVE | Impede, na reingestão, o nome do Hero num vilão e o colapso de lugares N+1. Branco honesto > nome errado. |
| P3 | **Restantes fixes da casa-limpa deployados** (itens 3–9) | ✅ LIVE (`ca1134b`) | parser-seats (4), WPN/PS por nick (5), trio IRE (6/8), resolver late-reg GG (9). Confirmar cada um no backend deployado (OpenAPI/liveness), não só em `main`. |
| P4 | **Quarentena de nomes a ZERO** | ⏳ 3 cartões pendentes do carimbo do Rui: **OHmyBUDDHA** (`confirmed`), **M_R_Z_E_** (`confirmed`), **Silin O** (`likely`) | Enquanto houver conflitos por decidir, o pipeline de propagação não está calibrado à mão-cheia. Carimbar → a quarentena zera → o reimport testa a propagação limpa. |
| P5 | **Backup lógico restore-VERIFICADO** | ritual pt47/pt68 | O único “desfazer”. Backup completo + **restaurar num destino de teste e confirmar contagens** ANTES de qualquer TRUNCATE. Sem restore verificado, não há gatilho. |
| P6 | **Fila HRC vazia / fechada; `hrc_jobs` sem trabalho pendente** | a confirmar no dia | O reimport muda os `id`s (RESTART IDENTITY) — qualquer `hand_db_id` em voo fica órfão. |

## 4. O que se PRESERVA vs o que se APAGA

- **Preservar (não tocar):** `users`, `stat_ideals`, `monthly_stats`, `gto_trees`/`gto_nodes`
  (a biblioteca GTO). *(Confirmar a lista exata contra o schema no dia — o ritual pt68 preservou
  estas.)*
- **Apagar:** todas as outras (mãos, entries, torneios, capturas, logs de processamento,
  payouts, hrc_jobs, reviews de FT/nomes, …) via **`TRUNCATE … RESTART IDENTITY CASCADE`** numa
  **transação atómica com assert-zero** (o padrão pt47/pt68). RESTART IDENTITY para os `id`s
  recomeçarem do 1 (limpo).

## 5. Ordem do reimport (os canos) e PORQUÊ a ordem

A ordem importa: cada cano prepara o terreno para o seguinte (re-links e enriquecimento são
fire-and-forget nos imports). Referência: os **6 canos** validados na Etapa 1 do pt68.

1. **HH GG (import manual / appimport `gg_hh`)** → cria as mãos GG **anónimas** (`origin='hh_import'`,
   `study_state='mtt_archive'` na prática escondidas do Estudo até desanon).
2. **TS GG (`tournament_summaries`, `gg_ts`)** → autoritativo pós-jogo: **bounty base**
   (`buy_in_bounty`), payouts/posição, e o **TIER 0** do resolver. Deve entrar cedo — muitos
   gates dependem dele (bounty do HRC, IRE, coroas>=base/2).
3. **Capturas de MESA do IT (`it`, table-SS)** → **desanon** (nomes reais) por **tn/hand-id do
   nome do ficheiro** (autoritário desde pt56/pt60) + **tags** (nome da pasta → `discord_tags`).
   É aqui que as tagadas ganham nicks reais.
4. **Gold (replayer, `position_v3`)** → nomes **fortes** (por posição, do log de ação) + **coroas**
   ($ bounty). A Gold vence o IT onde ambos existem (via premium).
5. **Lobbys (`lobby` / Capturas)** → `tournament_payouts` (estrutura de prémios). Resolver com o
   anchor prestart + o fix late-reg GG do item 9.
6. **HM3 (.bat) não-GG (PS/WN/WPN)** → mãos de **estudo** com nicks reais (entram em `'new'`).
7. **(Discord — dormente)** → histórico; não se sincroniza (morreu com o replayer-image).
8. **Propagação de nomes (Fase 3)** — fire-and-forget nos hooks de import: propaga os nomes
   **fortes** pelos **brancos** das mãos **tagadas** do torneio (`hash_propagation_v1`, guardas
   a–d); casos limpos auto-escritos, conflitos → quarentena (manual).
9. **FT boundaries** — `refresh_ft_boundaries` fire-and-forget nos imports/reconcile; **escreve
   as tags `-ft` só por aprovação manual** (cascata das 3 fontes, ver §6).

## 6. Critérios de aceitação (o que MEDIR depois) — o coração do plano

Cada critério tem um **alvo** e um **instrumento** (endpoint/query read-only). O reimport só se
declara bom quando todos batem; qualquer desvio grande é um sinal de regressão a investigar,
**não** a ignorar.

### Acordados com o Rui

| Critério | Alvo | Como medir |
|---|---|---|
| **A1 — Mãos suspeitas (coroas) ~0** | Nascer **~0**; só bordos legítimos coroa-verde/eliminação (subconjunto 1-seat). Se ressurgirem mãos **multi-seat** (≥3), a leitura chama/coroa **regrediu**. | Contador da secção “Mãos suspeitas” (`_bounty_below_half_hands`, GG PKO/KO com coroa < base÷2). Comparar o **perfil** (n.º de seats/mão) com o pré-wipe: os ≥7-seat (24 hoje) **não podem voltar**. |
| **A2 — Tagadas GG desanonimizadas à primeira** | **~100%** das mãos GG **tagadas** entram com nicks reais (`match_method` real), sem intervenção manual. | Query: mãos GG tagadas 2026 com `player_names->>'match_method'` **real** (não `discord_placeholder_*`, não branco) ÷ total tagadas. Brancos honestos só onde a fonte forte falta (a quantificar). |
| **A3 — Re-entradas resolvidas** | Os hashes de re-entry do **mesmo humano** partilham nome sem gerar veneno falso; os cartões `reentry_hint` aparecem corretos (`confirmed`/`likely`). | Painel de quarentena de nomes: cartões de re-entrada detetados; 0 “nome→2 hashes” marcados veneno que sejam afinal re-entry. Casos-âncora: Olisadebee, AmigoCrypto, M_R_Z_E_. |
| **A4 — FT boundaries pelas 3 fontes** | As fronteiras de mesa final propagam pela cascata `(0)` tag `-ft` manual → `(a)` lobby aba Info → `(b)` capturas coerentes; **snap-to-N** recua à 1ª mão real da FT. | `GET /api/gg-health/ft/preview` + o painel de quarentena FT: quantas FT por cada fonte; 0 escritas de payout pelo print do Info (`#LOBBY-INFO-NO-PAYOUT`); coerência só na cauda pós-pico. |

### Extra que o plano também deve medir

| Critério | Alvo | Como medir |
|---|---|---|
| **B1 — Guarda de desanon (Hero num vilão / colapso N+1)** | **0** mãos com nome do Hero num vilão; **0** colapsos de lugares. | A secção “Mãos suspeitas” veneno-2 (`_hero_name_on_villain_hands`) → 0; `seat-integrity-scan` read-only → 0 misfits novos. |
| **B2 — Parser de seats (item 4)** | **0** mãos GG/WPN perdidas por falha do parser de seats. | Contagem de `no_seats_at_table`/skips no manifesto vs total; o WPN “the” não pode reaparecer. |
| **B3 — table-SS match (item 5)** | **0** mis-matches WPN/PS por tempo-só (validação por nick-fit). | Logs do resolver + `table_ss_processing_log`: casos `wpn_ps_nick_mismatch` (orphan honesto) vs matches; nenhum match com nicks divergentes. |
| **B4 — Resolver lobbys GG no intervalo sem TS (item 9)** | Lobbys GG resolvem quando o TS ainda não chegou; falha = **`tm_not_found` honesto**, nunca mis-resolve para o dia errado. | `lobby_processing_log`: `tm_not_found` vs mis-resolves; re-tentar após import do TS (reconcile) deve fechar. |
| **B5 — IRE** | IRE aparece nas GG-via-replayer e WN PKO; estado **“bounty ilegível”** só onde a Vision falhou (não onde não há bounty). | Página Mãos: badges IRE presentes; chip âmbar “IRE — bounty ilegível” só em PKO com coroa por ler. |
| **B6 — Contagens de sanidade** | Bater com o snapshot pré-wipe (± o que se explica pela reingestão). | N.º de mãos por sala/mês, n.º de torneios, n.º de vilões (`villains_unique`), n.º de tagadas. Guardar o snapshot **antes** do TRUNCATE. |
| **B7 — Órfãos** | SS sem HH e HH sem SS reconciliam à medida que os canos correm (não ficam presos). | `GET /api/import-health?day=YYYY-MM-DD` (janela dia-de-jogo 15:00→15:00): por cano, contagens + falhas/sem-match com motivo. É **o** instrumento de validação da Etapa. |
| **B8 — Tags canónicas** | As tags entram normalizadas (fonte única `tags_canonical`). | Distribuição de `hm3_tags`/`discord_tags` sem grafias fora da lista canónica. |
| **B9 — Study-state** | Não-GG em `'new'` (estudo); GG bulk em `'new'` (mislabel cosmético inócuo, escondido do Estudo pelo gate `match_method`). | Confirmar que nenhuma GG anónima aparece no Estudo e que as não-GG aparecem. |

## 7. Instrumento central de medição

**`GET /api/import-health?day=YYYY-MM-DD`** — por pipeline (hands/mesa/lobby/hh_ts/inbox):
contagens + falhas/sem-match com motivo. Correr **por cada dia reimportado**, logo a seguir a
cada cano, para apanhar buracos cedo (foi o instrumento da Etapa 1 do pt68). Complementar com as
queries read-only dos critérios A/B acima (via `~/.pokerapp_db_ro.env`, só-leitura).

## 8. Rollback / segurança

- O **backup restore-verificado (P5)** é o único desfazer. Enquanto ele estiver confirmado, o
  wipe é reversível.
- O `TRUNCATE` corre **numa transação com assert-zero** (aborta se as contagens não baterem).
- Operação de prod = **servidor / ritual manual do Rui**, nunca script local com credenciais
  (`feedback_no_local_prod_execution`). O Code prepara e mede; **o Rui puxa o gatilho**.

## 9. Faseamento sugerido (para não engolir tudo de uma vez)

Espelha o pt68: **Etapa 1** = um bloco pequeno de dias (validar os canos e os critérios num
volume gerível) → ler o `import-health` + os critérios A/B → só depois **Etapa 2** = o resto.
Assim um problema aparece cedo, num volume pequeno, e não contamina o reimport inteiro.

## 10. Depois do wipe (fora do gatilho, para arrumar a seguir)

- Reconciliar `origin/watcher-gate` → `main` (pt87–95 do watcher) e só então rebuildar o `.exe`.
- Reavaliar `#F6` (re-solve HRC stale) e reabrir a alimentação da fila HRC **depois** de o core
  estar provado.
- Melhoria opcional (não pré-wipe): universalizar a guarda `crown>=base/2` no live path **só se**
  vier com superfície para os rejeitados (decisão Opção A do Rui, `REGISTO_CONCEITO 8 Jul`).

---

### Estado da casa-limpa (pré-requisito deste plano) — 9/9 fechados e LIVE

1. `#HRC-REIMPORT-REDEANON-CASADAS` ✅ · 2. `#DESANON-SITTING-OUT-NPLUS1` (guarda universal) ✅ ·
3. `#NORAISE-ANCHOR` ✅ (fechado-por-arrasto) · 4. `#PARSER-SEATS-FAILURES` ✅ ·
5. `#WPN-PS-TABLE-SS-TIME-ONLY-MATCH` ✅ · 6. `#IRE-CL` ✅ · 7. `#IRE-SK` (deferido a D, aguarda
fração instantânea empírica do Rui) · 8. `#IRE-VB` ✅ · 9. `#META-START-TIME` (re-escopado
GG-only) ✅. **Falta só carimbar os 3 cartões de nomes (P4) e o ritual de backup (P5).**
