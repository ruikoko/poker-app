"""
backfill_origin.py — Parte B do plano origin.

Popula hands.origin para mãos de 2026+ onde está NULL. Derivação:

  entries.source='discord'                              → 'discord'
  entries.source='hm'                                   → 'hm3'
  entries.source='hh_text' AND entry_type='hand_history'→ 'hh_import'
  entries.entry_type='image'                            → 'ss_upload'
  entry_id IS NULL AND hm3_tags não-vazio               → 'hm3'
  outros                                                → NULL (fica por decidir)

Dry-run default. --execute para persistir. Snapshot CSV sempre.
Transaction única, rollback em falha.
"""
import psycopg2, os, csv, sys, argparse
from collections import defaultdict
from datetime import datetime


def derive(source, entry_type, has_entry, hm3_tags):
    if has_entry:
        if source == 'discord':
            return 'discord', 'entry.source=discord'
        if source == 'hm':
            return 'hm3', 'entry.source=hm'
        if source == 'hh_text' and entry_type == 'hand_history':
            return 'hh_import', 'entry.source=hh_text+type=hand_history'
        if entry_type == 'image':
            return 'ss_upload', 'entry.type=image'
        if source == 'screenshot':
            return 'ss_upload', 'entry.source=screenshot'
        if entry_type == 'screenshot':
            return 'ss_upload', 'entry.type=screenshot'
        return None, f'entry(source={source},type={entry_type})_uncovered'
    else:
        if hm3_tags and len(hm3_tags) > 0:
            return 'hm3', 'no_entry+hm3_tags_populated'
        return None, 'no_entry+no_hm3_tags'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--execute', action='store_true',
                    help='Persistir UPDATEs. Sem esta flag: dry-run.')
    args = ap.parse_args()

    conn = psycopg2.connect(os.environ['DATABASE_PUBLIC_URL'])
    cur = conn.cursor()

    cur.execute("""
        SELECT h.id, h.hand_id, h.site, h.played_at,
               h.origin AS current_origin,
               h.hm3_tags,
               h.entry_id,
               e.source AS e_source,
               e.entry_type AS e_type
        FROM hands h
        LEFT JOIN entries e ON e.id = h.entry_id
        WHERE h.played_at >= '2026-01-01'
          AND h.origin IS NULL
        ORDER BY h.played_at DESC
    """)
    rows = cur.fetchall()
    print(f"Mãos elegíveis (2026+, origin IS NULL): {len(rows)}")

    plan = []
    for r in rows:
        hid, hand_id, site, played, cur_origin, hm3_tags, entry_id, e_source, e_type = r
        has_entry = entry_id is not None
        target, reason = derive(e_source, e_type, has_entry, hm3_tags)
        plan.append({
            'id': hid, 'hand_id': hand_id, 'site': site, 'played_at': played,
            'current': cur_origin, 'target': target, 'reason': reason,
            'entry_id': entry_id, 'e_source': e_source, 'e_type': e_type,
            'hm3_tags': hm3_tags,
        })

    # Breakdown por target
    counts = defaultdict(int)
    for p in plan:
        counts[p['target']] += 1
    print("\nBreakdown do target:")
    for k in sorted(counts, key=lambda x: (x is None, str(x))):
        print(f"  {str(k):<15} {counts[k]}")

    # Amostra dos NULL (casos não cobertos)
    nulls = [p for p in plan if p['target'] is None]
    if nulls:
        print(f"\nAmostra de casos NULL ({min(10, len(nulls))} de {len(nulls)}):")
        for p in nulls[:10]:
            print(f"  id={p['id']} hand_id={p['hand_id']:<25} reason={p['reason']} "
                  f"entry_id={p['entry_id']} e_source={p['e_source']} e_type={p['e_type']}")

    # CSV snapshot sempre
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    snap = f"backfill_origin_snapshot_{ts}.csv"
    with open(snap, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['id', 'hand_id', 'site', 'played_at',
                    'origin_old', 'origin_new', 'reason',
                    'entry_id', 'e_source', 'e_type', 'hm3_tags'])
        for p in plan:
            w.writerow([p['id'], p['hand_id'], p['site'], p['played_at'],
                        p['current'] or '', p['target'] or '', p['reason'],
                        p['entry_id'] or '', p['e_source'] or '', p['e_type'] or '',
                        '|'.join(p['hm3_tags']) if p['hm3_tags'] else ''])
    print(f"\nSnapshot: {snap}")

    to_write = [p for p in plan if p['target'] is not None]
    print(f"\nMãos com target definido: {len(to_write)}")
    print(f"Mãos sem target (NULL):   {len(nulls)}")

    if not args.execute:
        print("\nDRY-RUN — nada escrito. Re-corre com --execute para aplicar.")
        return
    if not to_write:
        print("\nNada para actualizar. A sair.")
        return

    # Agrupar por target e UPDATE em batch numa única transacção
    print(f"\nA aplicar {len(to_write)} UPDATEs (agrupados por target)...")
    by_target = defaultdict(list)
    for p in to_write:
        by_target[p['target']].append(p['id'])

    try:
        for target, ids in by_target.items():
            cur.execute("""
                UPDATE hands
                SET origin = %s
                WHERE id = ANY(%s::bigint[])
                  AND origin IS NULL
            """, (target, ids))
            print(f"  {target:<12} {cur.rowcount}/{len(ids)} rows actualizadas")
        conn.commit()
        print("\nOK — commit feito.")
    except Exception as e:
        conn.rollback()
        print(f"\nFALHA — rollback. Erro: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
