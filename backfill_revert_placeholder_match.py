"""
Reverte match_method das maos GG que ficaram com 'anchors_stack_elimination_v2'
mas SEM HH real (raw IS NULL ou vazio).

Causa do bug: _enrich_hand_from_orphan_entry promovia match_method
incondicionalmente quando uma 2a entry Discord chegava para o mesmo TM,
mesmo que a HH nunca tivesse chegado. Resultado: 25 maos com etiqueta de
match completo mas sem raw, que escapavam ao filtro do Estudo.

O fix do bug ja esta em produção (commit 834c2b6); este script limpa o
estado historico das 25 maos afectadas.

Modos:
  railway run --service Postgres python backfill_revert_placeholder_match.py
      -> dry-run (lista candidatos, NAO escreve)
  railway run --service Postgres python backfill_revert_placeholder_match.py --execute
      -> UPDATE real (com snapshot CSV antes)

Seguranca:
  - Default dry-run.
  - Em --execute, snapshot CSV antes do UPDATE (1 linha por mao afectada).
  - Transaccao unica.
  - ZERO DELETEs. So UPDATE em hands.player_names.
  - hand_villains de mãos afectadas SO sao listados (nao apagados) — decisao
    fica para depois do dry-run ver quantos sao.
"""
import argparse
import csv
import io
import json
import os
import sys
from datetime import datetime

# Force UTF-8 stdout (Windows + Portuguese chars in env vars)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
# Strip PG* vars; usar só DATABASE_PUBLIC_URL para evitar conflito de encoding
for k in ("PGHOST", "PGUSER", "PGPASSWORD", "PGDATABASE", "PGPORT"):
    os.environ.pop(k, None)

import psycopg2
from psycopg2.extras import RealDictCursor


SELECT_TARGETS_SQL = """
    SELECT id,
           hand_id,
           played_at,
           origin,
           player_names ->> 'match_method' AS mm,
           all_players_actions -> '_meta' ->> 'from_discord_placeholder' AS from_disc,
           screenshot_url,
           entry_id
    FROM hands
    WHERE site = 'GGPoker'
      AND (raw IS NULL OR raw = '')
      AND player_names ->> 'match_method' = 'anchors_stack_elimination_v2'
      AND (
        (all_players_actions -> '_meta' ->> 'from_discord_placeholder')::boolean = true
        OR origin = 'discord'
      )
      AND played_at >= '2026-01-01'
    ORDER BY id
"""


SELECT_VILLAINS_SQL = """
    SELECT hv.hand_db_id, hv.player_name, hv.position, hv.stack
    FROM hand_villains hv
    WHERE hv.hand_db_id = ANY(%s)
    ORDER BY hv.hand_db_id, hv.player_name
"""


UPDATE_SQL = """
    UPDATE hands
    SET player_names = jsonb_set(
        player_names,
        '{match_method}',
        '"discord_placeholder_no_hh"'::jsonb,
        false
    )
    WHERE id = ANY(%s)
"""


def write_snapshot(path: str, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "id", "hand_id", "played_at", "origin",
            "match_method_before", "match_method_after",
            "from_discord_placeholder", "screenshot_url", "entry_id",
        ])
        for r in rows:
            w.writerow([
                r["id"], r["hand_id"],
                r["played_at"].isoformat() if r["played_at"] else "",
                r["origin"] or "",
                r["mm"] or "",
                "discord_placeholder_no_hh",
                r["from_disc"] or "",
                r["screenshot_url"] or "",
                r["entry_id"] or "",
            ])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true",
                    help="Aplica o UPDATE. Sem flag, so dry-run.")
    args = ap.parse_args()

    dsn = os.environ.get("DATABASE_PUBLIC_URL") or os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_PUBLIC_URL / DATABASE_URL nao definido.")
        return 1

    # Workaround Windows: re-encode mojibake utf-8 → cp1252 → utf-8
    try:
        dsn = dsn.encode("cp1252").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass

    mode = "EXECUTE" if args.execute else "DRY-RUN"
    print(f"Modo: {mode}")
    print(f"Host: {dsn.split('@')[-1].split('/')[0] if '@' in dsn else '?'}")

    conn = psycopg2.connect(dsn, client_encoding="utf-8")
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # ── Fase 1: identificar candidatos ─────────────────────────────────
    print("\n[1/3] A identificar candidatos...")
    cur.execute(SELECT_TARGETS_SQL)
    targets = cur.fetchall()
    print(f"      Total candidatos: {len(targets)}")

    if not targets:
        print("\nNada a fazer.")
        cur.close()
        conn.close()
        return 0

    # Dump verboso de cada mão (id, played_at, mm antes→depois)
    print(f"\n{'id':>7}  {'hand_id':<24}  {'played_at':<25}  {'origin':<10}  match_method")
    print("-" * 110)
    for r in targets:
        played = r["played_at"].isoformat() if r["played_at"] else "(NULL)"
        print(f"{r['id']:>7}  {r['hand_id']:<24}  {played:<25}  {(r['origin'] or '?'):<10}  "
              f"{r['mm']} -> discord_placeholder_no_hh")

    # ── Fase 2: listar hand_villains potencialmente espurios ───────────
    print(f"\n[2/3] A verificar hand_villains associados...")
    ids = [r["id"] for r in targets]
    cur.execute(SELECT_VILLAINS_SQL, (ids,))
    vil_rows = cur.fetchall()
    print(f"      hand_villains rows nas mãos afectadas: {len(vil_rows)}")
    if vil_rows:
        # Agregar por mão
        by_hand: dict = {}
        for v in vil_rows:
            by_hand.setdefault(v["hand_db_id"], []).append(v["player_name"])
        print(f"      Mãos afectadas com >=1 villain: {len(by_hand)}")
        print("      Detalhe:")
        for hand_id, nicks in sorted(by_hand.items()):
            print(f"        hand_db_id={hand_id}: {len(nicks)} villain(s) -> {nicks}")
        print("\n      DECISAO PENDENTE: estes hand_villains foram criados sob match")
        print("      etiquetado mas sem HH real. Decidir manualmente se apagar — este")
        print("      script NAO os apaga.")
    else:
        print("      Nenhum hand_villains associado. Nada a limpar deste lado.")

    # ── Fase 3: dry-run ou execute ─────────────────────────────────────
    if not args.execute:
        print("\n[3/3] Dry-run concluido. Usa --execute para aplicar UPDATE.")
        cur.close()
        conn.close()
        return 0

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_path = f"backfill_revert_placeholder_match_snapshot_{ts}.csv"
    print(f"\n[3/3] A gravar snapshot em {snapshot_path}...")
    write_snapshot(snapshot_path, targets)
    print(f"      Snapshot gravado ({len(targets)} linhas).")

    print(f"\n      A executar UPDATE em {len(ids)} mãos...")
    cur.execute(UPDATE_SQL, (ids,))
    affected = cur.rowcount
    print(f"      UPDATE devolveu rowcount={affected}")

    if affected != len(ids):
        print(f"\n!!! ROLLBACK: rowcount ({affected}) != ids ({len(ids)}). "
              "Nada foi commitado.")
        conn.rollback()
        cur.close()
        conn.close()
        return 2

    conn.commit()
    print("      COMMIT efectuado.")
    cur.close()
    conn.close()
    print(f"\nFeito. Snapshot disponivel em: {snapshot_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
