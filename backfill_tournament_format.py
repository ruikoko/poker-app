"""
backfill_tournament_format.py — v2 com sinais estruturais por sala.

Regras:
  1. Nome ganha sempre (mystery/pko/bounty/knockout/ ko ).
  2. Se nome → vanilla, tenta sinal estrutural:
     - Winamax:   raw ~ r'\\d+€ bounty\\)'                         → PKO
     - PokerStars: primeiras 5 linhas do raw ~ r'[$€]X+[$€]Y+[$€]Z' → PKO
     - GGPoker:   bounty_pct > 0 em hand_villains OU em player_names.players_list → PKO
     - WPN:       só nome, fica vanilla

Dry-run default. --execute para persistir. Snapshot CSV sempre.
Transaction única, rollback em falha.
"""
import psycopg2, os, re, csv, sys, argparse, json
from collections import defaultdict, Counter
from datetime import datetime


# ── Regex idênticas a backend/app/utils/tournament_format.py ─────────────────
_MYSTERY_RE   = re.compile(r"mystery", re.I)
_PKO_RE       = re.compile(r"bounty|pko|knockout", re.I)
_KO_RE        = re.compile(r"\s+ko(\s|$)", re.I)
_WN_BOUNTY_RE = re.compile(r"\d+(?:\.\d+)?\s*€\s*bounty\)", re.I)
_PS_3COMP_RE  = re.compile(
    r"[$€]\d+(?:\.\d+)?\+[$€]\d+(?:\.\d+)?\+[$€]\d+(?:\.\d+)?"
)


def classify_by_name(name):
    if not name:
        return None
    if _MYSTERY_RE.search(name): return "mystery"
    if _PKO_RE.search(name):     return "PKO"
    if _KO_RE.search(name):      return "KO"
    return None


def detect(name, *, site=None, raw_hh=None, has_player_bounty=None):
    by_name = classify_by_name(name)
    if by_name is not None:
        return by_name
    if site:
        s = site.lower()
        if s == "winamax" and raw_hh and _WN_BOUNTY_RE.search(raw_hh):
            return "PKO"
        if s == "pokerstars" and raw_hh:
            header = "\n".join(raw_hh.splitlines()[:5])
            if _PS_3COMP_RE.search(header):
                return "PKO"
        if s == "ggpoker" and has_player_bounty:
            return "PKO"
    return "vanilla"


def gg_has_player_bounty(cur, hand_id, player_names_json):
    """True se hand_villains ou player_names.players_list tiver bounty_pct > 0."""
    cur.execute("""
        SELECT 1 FROM hand_villains
        WHERE hand_db_id = %s
          AND bounty_pct IS NOT NULL
          AND bounty_pct ~ '[1-9]'
        LIMIT 1
    """, (hand_id,))
    if cur.fetchone():
        return True
    if player_names_json:
        try:
            pn = player_names_json if isinstance(player_names_json, dict) else json.loads(player_names_json)
            for p in pn.get("players_list", []) or []:
                if isinstance(p, dict) and (p.get("bounty_pct") or 0) > 0:
                    return True
        except Exception:
            pass
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--execute', action='store_true',
                    help='Persistir UPDATEs. Sem esta flag: dry-run.')
    ap.add_argument('--recompute', action='store_true',
                    help='Recalcula mesmo para mãos que já têm tournament_format '
                         '(p/ aplicar regras novas sobre valores antigos).')
    args = ap.parse_args()

    conn = psycopg2.connect(os.environ['DATABASE_PUBLIC_URL'])
    cur = conn.cursor()

    where_clause = "WHERE played_at >= '2026-01-01'"
    if not args.recompute:
        where_clause += " AND tournament_format IS NULL"

    cur.execute(f"""
        SELECT id, hand_id, site, stakes, played_at, raw, player_names,
               tournament_format AS current_fmt
        FROM hands
        {where_clause}
        ORDER BY played_at DESC
    """)
    rows = cur.fetchall()
    print(f"Mãos elegíveis (2026+{', TODAS' if args.recompute else ', NULL only'}): {len(rows)}")

    plan = []
    for hid, hand_id, site, stakes, played, raw, player_names, current_fmt in rows:
        kw = {}
        if site == "Winamax":
            kw = {"site": "Winamax", "raw_hh": raw}
        elif site == "PokerStars":
            kw = {"site": "PokerStars", "raw_hh": raw}
        elif site == "GGPoker":
            kw = {"site": "GGPoker", "has_player_bounty": gg_has_player_bounty(cur, hid, player_names)}
        # WPN/outros: só nome

        fmt = detect(stakes, **kw)
        plan.append({
            'id': hid, 'hand_id': hand_id, 'site': site,
            'stakes': stakes, 'played_at': played,
            'current': current_fmt, 'target': fmt,
        })

    # Breakdown
    dist = Counter(p['target'] for p in plan)
    print("\nBreakdown target (nova regra):")
    for fmt in ['PKO', 'KO', 'mystery', 'vanilla']:
        print(f"  {fmt:<10} {dist.get(fmt, 0)}")

    # Breakdown por site (só não-vanilla)
    print("\nNão-vanilla por site:")
    nv_by_site = Counter((p['site'], p['target']) for p in plan if p['target'] != 'vanilla')
    for (site, fmt), n in sorted(nv_by_site.items()):
        print(f"  {site:<12} {fmt:<8} {n}")

    # Diffs vs current (só aparecem com --recompute)
    if args.recompute:
        changed = [p for p in plan if p['current'] != p['target']]
        print(f"\nMudanças vs estado actual: {len(changed)}")
        dist_change = Counter((p['current'], p['target']) for p in changed)
        for (old, new), n in dist_change.most_common(20):
            print(f"  {str(old):<10} → {str(new):<10} {n}")

    # CSV snapshot sempre
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    snap = f"backfill_tournament_format_snapshot_{ts}.csv"
    with open(snap, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['id', 'hand_id', 'site', 'played_at', 'stakes',
                    'current_fmt', 'target_fmt'])
        for p in plan:
            w.writerow([
                p['id'], p['hand_id'], p['site'], p['played_at'],
                p['stakes'] or '',
                p['current'] or '', p['target'],
            ])
    print(f"\nSnapshot: {snap}")

    if not args.execute:
        print("\nDRY-RUN — nada escrito. Re-corre com --execute para aplicar.")
        return

    to_write = [p for p in plan if p['target'] != p['current']]
    if not to_write:
        print("\nNada para actualizar. A sair.")
        return

    print(f"\nA aplicar {len(to_write)} UPDATEs (agrupados por target)...")
    by_target = defaultdict(list)
    for p in to_write:
        by_target[p['target']].append(p['id'])

    try:
        for target, ids in by_target.items():
            if args.recompute:
                cur.execute("""
                    UPDATE hands SET tournament_format = %s
                    WHERE id = ANY(%s::bigint[])
                """, (target, ids))
            else:
                cur.execute("""
                    UPDATE hands SET tournament_format = %s
                    WHERE id = ANY(%s::bigint[])
                      AND tournament_format IS NULL
                """, (target, ids))
            print(f"  {target:<10} {cur.rowcount}/{len(ids)} rows")
        conn.commit()
        print("\nOK — commit feito.")
    except Exception as e:
        conn.rollback()
        print(f"\nFALHA — rollback. Erro: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
