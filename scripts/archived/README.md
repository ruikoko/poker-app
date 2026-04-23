# scripts/archived

Arquivo de scripts standalone e snapshots CSV que foram usados **uma única vez**
para backfill retroactivo da BD em produção durante Abril 2026, antes do
pipeline live passar a cobrir estes casos nativamente.

## ⚠️ NÃO RE-EXECUTAR

Os scripts foram **substituídos pelo pipeline live** nos commits:

- **`8b60710`** `feat(discord): write origin and discord_tags from live ingest pipeline (Opção X)`
- **`87c79c2`** `feat(discord): write discord_tags + origin from replayer-link and SS-match paths`
- **`2844b94`** `fix(import): populate origin='hh_import' on ZIP/TXT HH import`

A partir destes commits, mãos novas vindas de Discord (HH texto, placeholders
de replayer_link, match SS↔HH) recebem `hands.origin = 'discord'` e
`hands.discord_tags = [channel_name]` **no momento da criação/enriquecimento**.
Correr estes scripts de novo é redundante e pode mascarar bugs se o pipeline
deixar de escrever algo — o script tapará o sintoma sem revelar a regressão.

Mantidos aqui apenas por auditoria e para reconstrução mental caso seja
preciso investigar execuções passadas.

## Ficheiros

### Scripts

- **`backfill_origin.py`** — popula `hands.origin` (2026+, NULL) com derivação
  por `entries.source` / `entry_type` / `hm3_tags`. Idempotente via
  `WHERE origin IS NULL`. Usa `DATABASE_PUBLIC_URL` env var para ligação directa
  à BD Railway.

- **`backfill_discord_tags.py`** — para entries do **canal `nota` apenas**
  (`CHANNEL_NOTA_ID = '1410311700023869522'`): extrai TM number da entry, procura
  a mão correspondente em `hands` (`GG-{TM}%`), actualiza `hands.entry_id` e
  faz append idempotente de `'nota'` a `hands.discord_tags`.

  **Limitação crítica** do script original: só cobria o canal `nota`. Outros
  canais Discord (icm, pos-pko, mw-pko, etc.) ficavam sem `discord_tags`. O
  pipeline live resolve isto — agora **todos** os canais populam `discord_tags`
  com o nome bruto do canal.

- **`check_origin_buckets.py`** — diagnóstico read-only (23 Abr 2026) que
  particionou `hands` com `origin IS NULL` (2026+) por sinais distintivos
  (entry.source, site, study_state, hm3_tags, discord_tags). Confirmou que
  todas as 1146 NULL partilhavam a mesma impressão digital
  (`entry.source='hh_text'`), todas vindas de `/api/import`. Só print — sem
  CSV nem UPDATE.

- **`backfill_origin_hh_import.py`** — backfill único (23 Abr 2026) que
  preencheu `origin='hh_import'` nas 1146 mãos órfãs do `/api/import`
  (bug fixado em `2844b94`). Guard EXISTS: só toca `hands` cujo `entry_id`
  aponta para `entries.source='hh_text' AND entry_type='hand_history'`.
  Aborta se o COUNT pré-UPDATE divergir de 1146; rollback se o UPDATE
  rowcount divergir. Não escreve CSV.

### Snapshots CSV (gitignored — não versionados)

Cada run do script (dry-run ou execute) escreve um CSV com o plano completo
para auditoria. Filename format: `backfill_<target>_snapshot_YYYYMMDD_HHMMSS.csv`.

Estes ficheiros **ficam só no disco local** — o `.gitignore` exclui o padrão
`scripts/archived/backfill_*_snapshot_*.csv` (e o equivalente no root) porque
são logs ad-hoc de execução única, volumosos (cada um ~5000 linhas para o
`backfill_origin`) e sem valor para versionamento. Se precisares de auditar
um run passado, os ficheiros continuam físicamente nesta pasta no disco do
desenvolvedor; não estão no GitHub.

CSVs conhecidos de 21 Abr 2026 (existentes no disco local, gitignored):

- `backfill_discord_tags_snapshot_20260421_130053.csv` — dry-run 21 Abr 13:00
- `backfill_discord_tags_snapshot_20260421_130134.csv` — execute 21 Abr 13:01
- `backfill_origin_snapshot_20260421_183522.csv` — dry-run 21 Abr 18:35
- `backfill_origin_snapshot_20260421_184023.csv` — dry-run adicional 21 Abr 18:40
- `backfill_origin_snapshot_20260421_184057.csv` — execute 21 Abr 18:40

### Última execução conhecida

**23 de Abril de 2026** — `backfill_origin_hh_import.py` (1146 linhas
actualizadas). Antes disso:

- **21 de Abril de 2026** — `backfill_origin.py` + `backfill_discord_tags.py`
  (inferido dos timestamps dos CSVs). Pipeline live passou a escrever
  `origin` + `discord_tags` nativamente (commits `8b60710` e `87c79c2`).
- **23 de Abril de 2026** — `/api/import` passou a escrever `origin='hh_import'`
  nativamente (commit `2844b94`).

Auditoria read-only disponível via `GET /api/hm3/admin/audit-discord-state`
(endpoint permanente).

## Cenários onde *talvez* reactivar

A única razão legítima para reactivar um destes scripts é:

- Descobrir um bloco de mãos legacy (pré-21-Abr-2026) que ainda tenha `origin`
  ou `discord_tags` em NULL, **e** for possível reconstruir a derivação
  correcta a partir de `entries.source` / `discord_channel`.

Nesse caso:

1. Corre **sempre** em dry-run primeiro (sem `--execute`).
2. Inspecciona o CSV gerado.
3. Só depois corre com `--execute`.
4. Arquiva o novo CSV aqui.

Caso contrário, **não executar**.
