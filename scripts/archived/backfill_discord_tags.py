"""
backfill_discord_tags.py — FASE 2 do fix retroactivo de entries Discord canal nota.

Para cada entry status=new do canal nota:
  - Extrai TM number
  - Procura mão em hands (played_at >= 2026-01-01)
  - Se encontrar: re-aponta hands.entry_id para a entry Discord
                  e adiciona 'nota' a hands.discord_tags (idempotente).

Default: DRY-RUN. Use --execute para persistir.
Snapshot CSV é escrito sempre (dry-run inclusive) para auditoria.
"""
import psycopg2, os, re, json, csv, sys, argparse
from datetime import datetime

CHANNEL_NOTA_ID = '1410311700023869522'
TM_RE = re.compile(r'TM(\d{6,})', re.IGNORECASE)


def extract_tm(*texts):
    for t in texts:
        if not t:
            continue
        s = t if isinstance(t, str) else json.dumps(t)
        m = TM_RE.search(s)
        if m:
            return m.group(1)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--execute', action='store_true',
                    help='Persistir UPDATEs. Sem esta flag é dry-run.')
    args = ap.parse_args()

    conn = psycopg2.connect(os.environ['DATABASE_PUBLIC_URL'])
    cur = conn.cursor()

    # 1. Fetch entries do canal nota
    cur.execute("""
        SELECT id, external_id, raw_text, raw_json, status, created_at
        FROM entries
        WHERE source = 'discord'
          AND discord_channel = %s
        ORDER BY created_at DESC
    """, (CHANNEL_NOTA_ID,))
    entries = cur.fetchall()
    print(f"Entries canal nota: {len(entries)}")

    # 2. Para cada entry: encontrar mão candidata
    plan = []  # dicts com decisão por entry
    for eid, ext_id, raw_text, raw_json, status, created in entries:
        raw_text_str = raw_text or ''
        raw_json_str = json.dumps(raw_json) if raw_json else ''
        tm = extract_tm(ext_id, raw_text_str, raw_json_str)

        if not tm:
            plan.append({'entry_id': eid, 'tm': None, 'hand': None,
                         'action': 'skip_no_tm'})
            continue

        cur.execute("""
            SELECT id, hand_id, entry_id, discord_tags
            FROM hands
            WHERE hand_id LIKE %s
              AND played_at >= '2026-01-01'
            ORDER BY played_at DESC
            LIMIT 1
        """, (f"GG-{tm}%",))
        h = cur.fetchone()
        if not h:
            plan.append({'entry_id': eid, 'tm': tm, 'hand': None,
                         'action': 'skip_no_hand'})
            continue

        hid, hand_id, h_entry, tags_old = h
        tags_old = tags_old or []
        needs_entry_fix = (h_entry != eid)
        needs_tag = ('nota' not in tags_old)

        if not needs_entry_fix and not needs_tag:
            action = 'noop'
        else:
            action = 'update'

        plan.append({
            'entry_id': eid,
            'tm': tm,
            'hand': {
                'id': hid, 'hand_id': hand_id,
                'entry_id_old': h_entry, 'tags_old': tags_old,
                'needs_entry_fix': needs_entry_fix,
                'needs_tag': needs_tag,
            },
            'action': action,
        })

    # 3. Imprimir plano + escrever snapshot CSV
    mode = 'EXECUTE' if args.execute else 'DRY-RUN'
    print(f"\nModo: {mode}")
    print("=" * 90)
    print(f"{'entry':<8} {'TM':<14} {'hand.id':<10} {'hand_id':<22} {'entry_old':<10} {'tags_old':<20} {'action'}")
    print("-" * 90)
    for p in plan:
        h = p['hand']
        if h:
            print(f"{p['entry_id']:<8} {str(p['tm']):<14} {h['id']:<10} {h['hand_id']:<22} "
                  f"{str(h['entry_id_old']):<10} {str(h['tags_old']):<20} {p['action']}")
        else:
            print(f"{p['entry_id']:<8} {str(p['tm']):<14} {'-':<10} {'-':<22} {'-':<10} {'-':<20} {p['action']}")

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    snap = f"backfill_discord_tags_snapshot_{ts}.csv"
    with open(snap, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['entry_discord_id', 'tm', 'hand_id_pk', 'hand_id',
                    'entry_id_old', 'entry_id_new',
                    'tags_old', 'tags_new', 'action'])
        for p in plan:
            h = p['hand']
            if h:
                tags_new = list(h['tags_old'])
                if 'nota' not in tags_new:
                    tags_new.append('nota')
                w.writerow([p['entry_id'], p['tm'], h['id'], h['hand_id'],
                            h['entry_id_old'], p['entry_id'],
                            '|'.join(h['tags_old']), '|'.join(tags_new),
                            p['action']])
            else:
                w.writerow([p['entry_id'], p['tm'] or '', '', '',
                            '', '', '', '', p['action']])
    print(f"\nSnapshot: {snap}")

    # 4. Resumo
    updated = sum(1 for p in plan if p['action'] == 'update')
    noop    = sum(1 for p in plan if p['action'] == 'noop')
    skip_nt = sum(1 for p in plan if p['action'] == 'skip_no_tm')
    skip_nh = sum(1 for p in plan if p['action'] == 'skip_no_hand')
    print(f"\nResumo: total={len(plan)} update={updated} noop={noop} "
          f"skip_no_tm={skip_nt} skip_no_hand={skip_nh}")

    if not args.execute:
        print("\nDRY-RUN — nada escrito. Re-corre com --execute para aplicar.")
        return

    if updated == 0:
        print("\nNada para actualizar. A sair.")
        return

    # 5. Execute numa transacção única
    print(f"\nA aplicar {updated} UPDATEs...")
    try:
        for p in plan:
            if p['action'] != 'update':
                continue
            h = p['hand']
            cur.execute("""
                UPDATE hands
                SET entry_id = %s,
                    discord_tags = CASE
                        WHEN 'nota' = ANY(COALESCE(discord_tags, '{}'::text[]))
                          THEN COALESCE(discord_tags, '{}'::text[])
                        ELSE array_append(COALESCE(discord_tags, '{}'::text[]), 'nota')
                    END
                WHERE id = %s
            """, (p['entry_id'], h['id']))
        conn.commit()
        print(f"OK — {updated} mãos actualizadas, commit feito.")
    except Exception as e:
        conn.rollback()
        print(f"FALHA — rollback. Erro: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
