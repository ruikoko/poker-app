# LEI DO SELO — coroas e nomes validados (18 Jul 2026)

> **Estado: ✅ LEI EM VIGOR.** Como a lei dos sizings, isto rege TODO o código
> que escreve coroas ($ bounty) ou nomes (desanon) numa mão GG — o que existe hoje
> e o que se escrever amanhã. Origem: decisão do Rui (18 Jul) + forense da 6570
> (GG-6104058222). Cross-ref: `JOURNAL_2026-07-18.md §4`, `DESANON_ANATOMIA §3.4`,
> `eliminated_bounty.py` (fonte única do selo).

## 1. O invariante (a lei, numa frase)

**O que o Rui valida fica SELADO — e NENHUM processo automático escreve por cima de
um valor selado. Salta e regista que saltou.** Os processos automáticos (re-leituras,
sweeps, fallback, propagação, re-deanon) continuam VÁLIDOS e a funcionar como sempre;
a única mudança de comportamento é: antes de escrever, perguntam **"selado? → salta"**.

## 2. O que é "selado" (fonte única — `eliminated_bounty.is_bounty_sealed`)

**Coroa selada** (por-seat) sse:
- `bounty_source ∈ {manual, green_ko, derived_green_ko}`, **ou**
- `bounty_confirmed == True` (exceção manual pré-existente; entra no selo).

**Nome selado** (por-mão): `player_names.verified_by_user == True`
(carimbo do editor Saúde GG; `deanon_status` já o faz vencer o `match_method`).

Fontes **NÃO** seladas (automáticas — podem ser reescritas): `gold`, `table_ss`
(fallback por testemunha), leitura crua da Vision sem marca. Um valor automático
**nunca** é carimbo; só a mão do Rui (endpoints manuais) sela.

## 3. Quem carimba (escritores MANUAIS → gravam a origem selada)

| Endpoint | Sela | Onde |
|---|---|---|
| `POST /api/table-ss/set-bounties` (valor) | `bounty_source='manual'` nos **dois** stores (apa + players_list) | `routers/table_ss.py` |
| `POST /api/table-ss/set-bounties` (confirm) | `bounty_confirmed=True` espelhado apa+players_list | `routers/table_ss.py` |
| Editor Saúde GG Fase 1-E (nomes) | `verified_by_user=True` | `routers/table_ss.py:/set-anon-map` |
| Fluxo Etapa-2 (bounties recuperáveis) | `bounty_source='derived_green_ko'` | (cura verde carimbada) |

## 4. Os caminhos AUTOMÁTICOS e a guarda do selo (os 7 corrigidos)

Todos consultam `is_bounty_sealed` (coroas) / `verified_by_user` (nomes) antes de escrever.

| # | Caminho | Quando dispara | Ficheiro | Guarda |
|---|---|---|---|---|
| 1 | `_enrich_all_players_actions` (re-fill do **apa**) | qualquer deanon/re-deanon (import, reconcile) | `routers/screenshot.py` | seat selado → preserva valor+source, salta a Vision |
| 2 | `_merge_sealed_crowns` (reconstrução do **players_list**) | dentro de `deanonymize_hand_from_table_ss` | `services/table_ss_deanon.py` | repõe as coroas seladas do players_list anterior (valor+source+confirmed) |
| 3 | `_guard_suspect_crowns` (guarda ½-base) | dentro do deanon + reread + fallback | `services/table_ss_deanon.py` | salta todo o selo (antes só `bounty_confirmed`) |
| 4 | `scrub_eliminated_bounties._handle` (funil verde-KO) | fire-and-forget após cada caminho automático | `services/eliminated_bounty.py` | selo intocável (excepção: refresh green_ko→green_ko) |
| 5 | `POST /crowns/reread` (re-leitura Vision) | manual, painel Coroas | `routers/gg_health.py` | salta seats selados no apply |
| 6 | `_enrich_hand_from_orphan_entry` (`force` re-Vision) | `revision-replayers?force=true` | `routers/screenshot.py` | selo só na coroa (país/VPIP refrescam) |
| 7 | Guarda 3-b de NOMES | dentro do deanon | `services/table_ss_deanon.py` | `verified_by_user` → `skip_verified_by_user` |

### Seguros por construção (verificados, sem alteração)
- **Backfills de coroa** (`backfill_crowns_from_capture`, backfills do `screenshot.py`):
  só preenchem seats vazios (`bounty_value_usd > 0 → continue`); um carimbo manual é
  sempre > 0 → nunca tocado.
- **`/crowns/fallback-fill`, `/crowns/high-reread-confirm`**: auto-derivados
  (source `gold`/`table_ss` ou consistência) — não são carimbo; não selam nem colidem.
- **`hand_service._insert_hand`** (Gold imagem-primeiro): passa pelo chokepoint nº1
  (`_enrich_all_players_actions`) → coberto transitivamente.

## 5. COEXISTÊNCIA e precedência (resposta à pergunta do Rui)

Cada escritor faz **ler → mutar em Python → `UPDATE hands`**, sem lock de linha.
Podem, em teoria, tocar a mesma mão em momentos próximos (import + reconcile +
scrub são disparados em sequência, fire-and-forget). Determinismo:

- **Valores SELADOS → determinísticos e imunes à ordem.** Os 7 caminhos saltam-nos;
  qualquer que seja a ordem, o valor selado **sobrevive sempre**. A corrida não importa.
- **Valores NÃO-selados → convergem para o mesmo resultado dado o mesmo input.** Todos
  os caminhos automáticos derivam das **mesmas fontes duráveis** (a leitura table-SS
  guardada em `vision_json` + o `raw`/HH) e o scrub é **idempotente** → calculam o mesmo
  valor independentemente da ordem. Não há lock, mas como o input é fixo, não há
  divergência (a única "corrida" — interleaving transitório de RMW — resolve no mesmo valor).
- **Precedência (para o MESMO seat, quem ganha):**
  1. **SELO** (manual/green_ko/derived_green_ko/confirmed) — absoluto, vence tudo o automático.
  2. **Guarda ½-base / eliminado** — anula valores impossíveis (mas salta os selados).
  3. **Fonte durável** (a leitura guardada, via deanon) — o valor-base automático.
  4. **Re-leitura fresca** (`/crowns/reread`, `force`) — sobrescreve o não-selado no
     momento, mas **NÃO é durável**: não actualiza o `vision_json` guardado → um
     re-deanon posterior repõe a fonte durável. **Por desenho** (a fonte durável vence
     o transitório). Uma re-leitura em que o Rui confia → **selar** (confirm) para a fixar.

**Limitação honesta (baixo risco):** sob concorrência VERDADEIRA na mesma mão sem lock,
um RMW pode perder uma escrita não-selada (lost-update clássico). Na prática os gatilhos
são sequenciais e idempotentes com input fixo → convergem. Hard-determinismo sob
concorrência real exigiria `SELECT … FOR UPDATE`; não foi feito porque os fluxos do Rui
são sequenciais e **o selo cobre exactamente os valores que importam**.

## 6. LEI PARA O FUTURO (o que impede o robô nº 8 de reabrir a ferida)

> **Qualquer caminho de escrita NOVO de coroa ou nome TEM de consultar o selo antes
> de escrever.** Coroa: `if is_bounty_sealed(seat): continue` (ou preservar o valor+source
> selado). Nome: respeitar `verified_by_user` (skip). Um carimbo do Rui é intocável para
> código automático — sem excepções "úteis".**

Checklist ao adicionar/rever um escritor de `bounty_value_usd` ou de nomes/anon_map:
1. É manual (mão do Rui)? → **grava a origem selada** (`bounty_source='manual'` / `verified_by_user=True`).
2. É automático? → **consulta o selo e salta** (log). Deriva de fonte durável, é idempotente.
3. Escreve nos **dois** stores (apa + `players_list`)? → sela/salta em **ambos** (ficam coerentes).
4. Acrescenta uma linha à tabela §4 deste documento.

A prova viva desta lei está em `backend/tests/test_crown_seal.py` (corrigir → forçar
re-apply → o valor sobrevive). Se um escritor novo partir essa prova, viola a lei.
