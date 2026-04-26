"""
Backfill Bucket 1 Fase VI — anexa as 3 imagens Discord orfas conhecidas
(entries 13, 17, 87) as suas hands sibling (117, 115, 67) via worker
existente em app.routers.attachments.

Ver docs/SPEC_BUCKET_1_anexos_imagem.md §6 e CLAUDE.md "Imagens de
contexto Discord". Estes 3 matches foram identificados em 2026-04-26 com
janela ±90s e estao estaveis em prod desde entao (re-validados a 2026-04-27).

Modos:
  railway run --service Postgres python backfill_attach_orphan_images.py
      -> dry-run (mostra o que seria inserido, NAO escreve)
  railway run --service Postgres python backfill_attach_orphan_images.py --execute
      -> aplica os 3 INSERTs em hand_attachments + UPDATE entries.status
         (com snapshot CSV antes; transaccao unica)
  railway run --service Postgres python backfill_attach_orphan_images.py --rollback
      -> DELETE FROM hand_attachments WHERE entry_id IN (13,17,87)
         (idempotente — corre safe mesmo se ja foi feito rollback antes;
          NAO toca em entries.status, esse campo nunca e escrito pelo worker)

Seguranca:
  - Default dry-run.
  - Em --execute, snapshot CSV antes de qualquer escrita.
  - Transaccao unica via _apply_match (cada chamada commita por si — limitacao
    do worker existente; cobertura por idempotencia: ON CONFLICT DO NOTHING
    no INSERT garante que re-correr nao duplica).
  - Filtro explicito por entry_id IN (13,17,87) — NAO corre o worker
    indiscriminadamente. Os outros 5 candidatos orfaos (entries 6/7/35/46/133)
    ficam intactos.
  - Valida pre-condicoes antes de qualquer escrita: tabela vazia, entries
    com status='new', _compute_match_candidates retorna os 3 matches certos.
"""
import argparse
import csv
import io
import os
import sys
from datetime import datetime

# Force UTF-8 stdout (Windows + chars portugueses)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

# Strip PG* vars; usar so DATABASE_PUBLIC_URL para evitar conflito de encoding
for k in ("PGHOST", "PGUSER", "PGPASSWORD", "PGDATABASE", "PGPORT"):
    os.environ.pop(k, None)


TARGET_ENTRY_IDS = [13, 17, 87]
EXPECTED_MATCHES = {
    # entry_id -> (hand_db_id, delta_seconds_esperado, channel_name_esperado)
    13: (117, 18, "icm-pko"),
    17: (115, 23, "icm-pko"),
    87: (67, 78, "pos-pko"),
}


def _setup_dsn() -> str:
    dsn = os.environ.get("DATABASE_PUBLIC_URL") or os.environ.get("DATABASE_URL")
    if not dsn:
        sys.exit("DATABASE_PUBLIC_URL / DATABASE_URL nao definido.")
    try:
        dsn = dsn.encode("cp1252").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass
    return dsn


def _import_worker(dsn: str):
    """Adiciona backend/ ao sys.path + redirige DATABASE_URL para que
    app.db.get_conn() use o public URL."""
    HERE = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(HERE, "backend"))
    os.environ["DATABASE_URL"] = dsn
    from app.routers.attachments import _compute_match_candidates, _apply_match
    return _compute_match_candidates, _apply_match


def write_snapshot(path: str, entries_before: list, hands_before: list) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["section", "id", "field", "value"])
        for e in entries_before:
            for k, v in e.items():
                w.writerow(["entry", e["id"], k, str(v) if v is not None else ""])
        for h in hands_before:
            for k, v in h.items():
                w.writerow(["hand", h["id"], k, str(v) if v is not None else ""])


def _validate_preconditions(cur, _compute) -> bool:
    """Pre-condicoes obrigatorias antes de --execute. Retorna True se OK."""
    print("\n[pre-conds 1/4] hand_attachments count")
    cur.execute("SELECT COUNT(*) FROM hand_attachments")
    n = cur.fetchone()[0]
    print(f"    count = {n}")
    if n != 0:
        # Aceitar se as 3 rows ja la estao (re-correr o backfill e idempotente)
        cur.execute(
            "SELECT entry_id FROM hand_attachments WHERE entry_id = ANY(%s)",
            (TARGET_ENTRY_IDS,),
        )
        already = [r[0] for r in cur.fetchall()]
        if set(already) == set(TARGET_ENTRY_IDS) and n == 3:
            print("    INFO: as 3 rows-alvo ja existem. Backfill ja foi corrido — nada a fazer.")
            return False
        print(f"    FAIL: tabela com {n} rows mas nao sao as 3 alvo. Investigar.")
        return False

    print("\n[pre-conds 2/4] entries 13/17/87 com status != 'attached'")
    cur.execute(
        "SELECT id, status, source, entry_type FROM entries WHERE id = ANY(%s) ORDER BY id",
        (TARGET_ENTRY_IDS,),
    )
    rows = cur.fetchall()
    if len(rows) != 3:
        print(f"    FAIL: esperado 3 rows, vi {len(rows)}")
        return False
    for r in rows:
        eid, status, src, etype = r
        print(f"    entry {eid}: status={status} source={src} type={etype}")
        if status == "attached":
            print(f"    FAIL: entry {eid} ja attached")
            return False
        if src != "discord" or etype != "image":
            print(f"    FAIL: entry {eid} source/type errado")
            return False

    print("\n[pre-conds 3/4] hands 67/115/117 com played_at populado")
    cur.execute(
        "SELECT id, hand_id, played_at FROM hands WHERE id IN (67, 115, 117) ORDER BY id",
    )
    rows = cur.fetchall()
    if len(rows) != 3:
        print(f"    FAIL: esperado 3 rows, vi {len(rows)}")
        return False
    for r in rows:
        hid, hand_id, played = r
        print(f"    hand {hid}: hand_id={hand_id} played_at={played}")
        if played is None:
            print(f"    FAIL: hand {hid} sem played_at")
            return False

    print("\n[pre-conds 4/4] _compute_match_candidates retorna os 3 matches certos")
    cands = _compute(100)
    by_eid = {c["entry_id"]: c for c in cands}
    for eid, (exp_hand, exp_delta, _exp_channel) in EXPECTED_MATCHES.items():
        if eid not in by_eid:
            print(f"    FAIL: entry {eid} ausente do worker")
            return False
        m = by_eid[eid]["match"]
        if not m:
            print(f"    FAIL: entry {eid} sem match no worker")
            return False
        if m["hand_db_id"] != exp_hand:
            print(f"    FAIL: entry {eid} -> hand {m['hand_db_id']}, esperado {exp_hand}")
            return False
        if m["delta_seconds"] != exp_delta:
            print(f"    FAIL: entry {eid} delta={m['delta_seconds']}, esperado {exp_delta}")
            return False
        if m["match_method"] != "discord_channel_temporal":
            print(f"    FAIL: entry {eid} method={m['match_method']}, esperado discord_channel_temporal")
            return False
        print(f"    entry {eid} -> hand {exp_hand}, delta {exp_delta}s, OK")

    return True


def _validate_post_execute(cur, _compute) -> None:
    print("\n[validacao pos-execute 1/3] hand_attachments")
    cur.execute(
        """SELECT id, hand_db_id, entry_id, channel_name, match_method, delta_seconds,
                  img_b64 IS NOT NULL AS has_b64, mime_type
           FROM hand_attachments ORDER BY id"""
    )
    rows = cur.fetchall()
    print(f"    count={len(rows)} (esperado 3)")
    for r in rows:
        att_id, hdb, eid, ch, mm, ds, has_b64, mt = r
        print(f"    att_id={att_id} hand_db_id={hdb} entry_id={eid} channel={ch} "
              f"method={mm} delta={ds}s img_b64={has_b64} mime={mt}")

    print("\n[validacao pos-execute 2/3] count == 3")
    cur.execute("SELECT COUNT(*) FROM hand_attachments")
    n = cur.fetchone()[0]
    print(f"    hand_attachments count = {n} ({'OK' if n == 3 else 'FAIL'})")

    print("\n[validacao pos-execute 3/3] _compute_match_candidates re-corrido")
    cands = _compute(100)
    with_match = [c for c in cands if c["match"]]
    print(f"    total_pending={len(cands)} with_match={len(with_match)} (esperado pending=5, with_match=0)")


def _do_rollback(cur) -> int:
    """Remove rows de hand_attachments para os 3 entry_ids alvo. NAO toca em
    entries.status — esse campo nunca e escrito pelo worker (CHECK constraint
    nao inclui 'attached'; ver fix de 2026-04-26)."""
    print("\n[rollback] DELETE FROM hand_attachments WHERE entry_id IN (...)")
    cur.execute(
        "DELETE FROM hand_attachments WHERE entry_id = ANY(%s)",
        (TARGET_ENTRY_IDS,),
    )
    deleted = cur.rowcount
    print(f"    deleted: {deleted}")
    return deleted


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true",
                    help="Aplica os INSERTs. Sem flag, dry-run.")
    ap.add_argument("--rollback", action="store_true",
                    help="DELETE FROM hand_attachments WHERE entry_id IN (13,17,87) "
                         "+ UPDATE entries SET status='new'.")
    args = ap.parse_args()

    if args.execute and args.rollback:
        sys.exit("--execute e --rollback sao mutuamente exclusivos.")

    dsn = _setup_dsn()
    mode = "ROLLBACK" if args.rollback else ("EXECUTE" if args.execute else "DRY-RUN")
    print(f"Modo: {mode}")
    print(f"Host: {dsn.split('@')[-1].split('/')[0] if '@' in dsn else '?'}")
    print(f"Target entry_ids: {TARGET_ENTRY_IDS}")

    import psycopg2
    conn = psycopg2.connect(dsn, client_encoding="utf-8")
    conn.autocommit = False
    cur = conn.cursor()

    # ── Rollback path ────────────────────────────────────────────────
    if args.rollback:
        _do_rollback(cur)
        conn.commit()
        print("\nROLLBACK COMMITED.")
        cur.close()
        conn.close()
        return 0

    # ── Importar worker da app ───────────────────────────────────────
    _compute, _apply = _import_worker(dsn)

    # ── Pre-condicoes ────────────────────────────────────────────────
    if not _validate_preconditions(cur, _compute):
        cur.close()
        conn.close()
        print("\nPre-condicoes nao satisfeitas. Abortando.")
        return 1

    # ── Calcular candidates ──────────────────────────────────────────
    print("\n[step 1/3] A calcular candidates filtrados por target_entry_ids")
    cands = _compute(100)
    targets = [c for c in cands if c["entry_id"] in TARGET_ENTRY_IDS and c["match"]]
    print(f"    candidates filtrados: {len(targets)} (esperado 3)")
    for c in targets:
        m = c["match"]
        print(f"    entry {c['entry_id']} canal={c['channel']} -> hand {m['hand_db_id']} "
              f"({m['hand_id_text']}) delta={m['delta_seconds']}s method={m['match_method']}")

    if len(targets) != 3:
        print("    FAIL: esperado 3 candidates filtrados.")
        cur.close()
        conn.close()
        return 2

    # ── Dry-run? ─────────────────────────────────────────────────────
    if not args.execute:
        print("\n[step 2/3] Dry-run concluido. Usa --execute para aplicar.")
        cur.close()
        conn.close()
        return 0

    # ── Snapshot CSV ─────────────────────────────────────────────────
    print("\n[step 2/3] A gravar snapshot CSV")
    cur2 = conn.cursor()
    cur2.execute(
        """SELECT id, raw_text, discord_channel, discord_posted_at, status
           FROM entries WHERE id = ANY(%s) ORDER BY id""",
        (TARGET_ENTRY_IDS,),
    )
    entries_before = [
        dict(zip(["id", "raw_text", "discord_channel", "discord_posted_at", "status"], r))
        for r in cur2.fetchall()
    ]
    cur2.execute(
        "SELECT id, hand_id, played_at, origin FROM hands WHERE id IN (67, 115, 117) ORDER BY id"
    )
    hands_before = [
        dict(zip(["id", "hand_id", "played_at", "origin"], r))
        for r in cur2.fetchall()
    ]
    cur2.close()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_path = f"backfill_attach_orphan_images_snapshot_{ts}.csv"
    write_snapshot(snapshot_path, entries_before, hands_before)
    print(f"    snapshot gravado em {snapshot_path}")

    # Fechamos conexao psycopg2 directa antes de chamar _apply
    # (cada _apply abre/commita conn propria via app.db.get_conn).
    cur.close()
    conn.close()

    # ── Execute ──────────────────────────────────────────────────────
    print(f"\n[step 3/3] A aplicar {len(targets)} matches via _apply_match")
    results = []
    for c in targets:
        r = _apply(c)
        results.append(r)
        print(f"    entry {c['entry_id']}: status={r['status']} "
              f"{'attachment_id=' + str(r.get('attachment_id', '?')) if r['status'] == 'ok' else 'reason=' + str(r.get('reason'))}")
        if r["status"] == "ok":
            print(f"        img_b64_cached={r.get('img_b64_cached')}")

    applied = sum(1 for r in results if r["status"] == "ok")
    print(f"\n    applied={applied} skipped={sum(1 for r in results if r['status']=='skip')} "
          f"errors={sum(1 for r in results if r['status']=='error')}")

    if applied != 3:
        print("\nFAIL: applied != 3. Validacao pos-execute para diagnosticar.")

    # ── Validacao imediata ───────────────────────────────────────────
    conn = psycopg2.connect(dsn, client_encoding="utf-8")
    cur = conn.cursor()
    _validate_post_execute(cur, _compute)
    cur.close()
    conn.close()

    print(f"\nFeito. Snapshot disponivel em: {snapshot_path}")
    return 0 if applied == 3 else 3


if __name__ == "__main__":
    raise SystemExit(main())
