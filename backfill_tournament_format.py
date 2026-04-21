"""
backfill_tournament_format.py — Retroactivo para hands.tournament_format.

Para cada mão 2026+ com tournament_format IS NULL, aplica detect_tournament_format(stakes)
(lógica duplicada intencional — script standalone).

Dry-run default. --execute para persistir. Snapshot CSV sempre.
Transaction única, rollback em falha.
"""
import psycopg2, os, csv, sys, argparse
from collections import defaultdict, Counter
from datetime import datetime


def detect_tournament_format(tournament_name):
    """Duplicado de app/utils/tournament_format.py (intencional, script standalone)."""
    if not tournament_name:
        return "vanilla"
    name_lower = tournament_name.lower()
    if "mystery" in name_lower:
        return "mystery"
    if "bounty" in name_lower or "pko" in name_lower or "knockout" in name_lower:
        return "PKO"
    if " ko " in name_lower or name_lower.endswith(" ko"):
        return "KO"
    return "vanilla"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--execute', action='store_true',
                    help='Persistir UPDATEs. Sem esta flag: dry-run.')
    args = ap.parse_args()

    conn = psycopg2.connect(os.environ['DATABASE_PUBLIC_URL'])
    cur = conn.cursor()

    cur.execute("""
        SELECT id, hand_id, site, stakes, played_at
        FROM hands
        WHERE played_at >= '2026-01-01'
          AND tournament_format IS NULL
        ORDER BY played_at DESC
    """)
    rows = cur.fetchall()
    print(f"Mãos elegíveis (2026+, tournament_format IS NULL): {len(rows)}")

    plan = []
    for hid, hand_id, site, stakes, played in rows:
        fmt = detect_tournament_format(stakes)
        plan.append({
            'id': hid, 'hand_id': hand_id, 'site': site,
            'stakes': stakes, 'played_at': played, 'tournament_format': fmt,
        })

    # Breakdown por formato
    dist = Counter(p['tournament_format'] for p in plan)
    print("\nBreakdown derivado:")
    for fmt in ['PKO', 'KO', 'mystery', 'vanilla']:
        print(f"  {fmt:<10} {dist.get(fmt, 0)}")

    # Breakdown vanilla por site (para validar — ex: muitos WPN cash serão vanilla)
    vanilla_by_site = Counter(
        p['site'] for p in plan if p['tournament_format'] == 'vanilla'
    )
    if vanilla_by_site:
        print("\nVanilla por site:")
        for s, n in vanilla_by_site.most_common():
            print(f"  {str(s):<12} {n}")

    # Amostras não-vanilla
    non_vanilla_sample = [p for p in plan if p['tournament_format'] != 'vanilla'][:10]
    if non_vanilla_sample:
        print("\nAmostra não-vanilla (10):")
        for p in non_vanilla_sample:
            print(f"  id={p['id']} fmt={p['tournament_format']:<8} stakes={p['stakes']!r}")

    # CSV snapshot sempre
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    snap = f"backfill_tournament_format_snapshot_{ts}.csv"
    with open(snap, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['id', 'hand_id', 'site', 'played_at', 'stakes', 'tournament_format_derived'])
        for p in plan:
            w.writerow([
                p['id'], p['hand_id'], p['site'], p['played_at'],
                p['stakes'] or '', p['tournament_format'],
            ])
    print(f"\nSnapshot: {snap}")

    if not args.execute:
        print("\nDRY-RUN — nada escrito. Re-corre com --execute para aplicar.")
        return
    if not plan:
        print("\nNada para actualizar. A sair.")
        return

    # UPDATE em batch por valor
    print(f"\nA aplicar {len(plan)} UPDATEs (agrupados por formato)...")
    by_fmt = defaultdict(list)
    for p in plan:
        by_fmt[p['tournament_format']].append(p['id'])

    try:
        for fmt, ids in by_fmt.items():
            cur.execute("""
                UPDATE hands
                SET tournament_format = %s
                WHERE id = ANY(%s::bigint[])
                  AND tournament_format IS NULL
            """, (fmt, ids))
            print(f"  {fmt:<10} {cur.rowcount}/{len(ids)} rows")
        conn.commit()
        print("\nOK — commit feito.")
    except Exception as e:
        conn.rollback()
        print(f"\nFALHA — rollback. Erro: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
