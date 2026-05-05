"""Pipeline 4 - Etapa C/D/E + diagnostico extra. Read-only.
Corre via: railway run python scripts/p4_phaseC_validation.py
Janela INTERVAL '60 minutes' para apanhar os uploads recentes."""
import os, sys, psycopg2

def main():
    url = os.environ.get("DATABASE_PUBLIC_URL")
    if not url:
        sys.exit("ERRO: DATABASE_PUBLIC_URL nao setado.")
    print(f"DB: {url.split('@')[1].split('/')[0]}")
    print("=" * 78)

    conn = psycopg2.connect(url)
    c = conn.cursor()

    print("\n--- Q4.1 entries SS uploaded (Vision feito, com TM) ---")
    c.execute("""
        SELECT id, file_name, status,
               raw_json->>'tm' AS tm,
               (raw_json->>'vision_done')::boolean AS vd,
               raw_json->>'hero' AS hero,
               jsonb_array_length(COALESCE(raw_json->'players_list', '[]'::jsonb)) AS n_players
        FROM entries
        WHERE source = 'screenshot' AND created_at >= NOW() - INTERVAL '60 minutes'
        ORDER BY created_at DESC;
    """)
    cols = [d[0] for d in c.description]
    print("cols:", cols)
    rows_q41 = c.fetchall()
    print(f"rows: {len(rows_q41)}")
    for r in rows_q41:
        print(" ", r)
    ss_tms = [r[3] for r in rows_q41 if r[3]]

    print("\n--- Q4.2 placeholders ss_upload (matched=NO ainda) ---")
    c.execute("""
        SELECT h.id, h.hand_id, h.origin, h.tags, h.hm3_tags,
               (h.player_names ->> 'match_method') AS mm
        FROM hands h
        WHERE h.origin = 'ss_upload' AND h.created_at >= NOW() - INTERVAL '60 minutes'
        ORDER BY h.created_at DESC;
    """)
    cols = [d[0] for d in c.description]
    print("cols:", cols)
    rows = c.fetchall()
    print(f"rows: {len(rows)}")
    for r in rows:
        print(" ", r)

    print("\n--- Q4.3 painel SSMatch counter ---")
    c.execute("""
        SELECT COUNT(*) AS ss_match_pending
        FROM hands
        WHERE origin = 'ss_upload'
          AND (player_names ->> 'match_method') = 'discord_placeholder_no_hh';
    """)
    print(" ", c.fetchone())

    if ss_tms:
        in_clause = ",".join(f"'GG-{t.replace('TM','')}'" for t in ss_tms)
        print(f"\n--- Q4.4 estado das hands cujo TM bate com SSs uploaded ---")
        c.execute(f"""
            SELECT h.id, h.hand_id, h.origin, h.tags,
                   h.played_at, h.tournament_name, h.position, h.result, h.hero_cards,
                   (h.player_names ->> 'match_method') AS mm,
                   (h.raw IS NOT NULL AND h.raw <> '') AS has_raw
            FROM hands h
            WHERE h.hand_id IN ({in_clause})
            ORDER BY h.hand_id;
        """)
        cols = [d[0] for d in c.description]
        print("cols:", cols)
        rows_q44 = c.fetchall()
        print(f"rows: {len(rows_q44)}")
        for r in rows_q44:
            print(" ", r)

        print(f"\n--- Q4.5 hashes restantes em apa pos-enrich (zero esperado) ---")
        c.execute(f"""
            SELECT h.hand_id,
                   (SELECT array_agg(k) FROM jsonb_object_keys(h.all_players_actions) k
                    WHERE k != '_meta' AND k ~ '^[0-9a-f]{{8}}$') AS hashes_remaining
            FROM hands h
            WHERE h.hand_id IN ({in_clause});
        """)
        cols = [d[0] for d in c.description]
        print("cols:", cols)
        rows = c.fetchall()
        print(f"rows: {len(rows)}")
        for r in rows:
            print(" ", r)

        print(f"\n--- Q4.6 anon_map populado quando mm='v2' ---")
        c.execute(f"""
            SELECT h.hand_id,
                   jsonb_typeof(h.player_names -> 'anon_map') AS anon_type,
                   (h.player_names -> 'anon_map') IS NOT NULL AS has_anon
            FROM hands h
            WHERE h.hand_id IN ({in_clause})
              AND (h.player_names ->> 'match_method') = 'anchors_stack_elimination_v2';
        """)
        cols = [d[0] for d in c.description]
        print("cols:", cols)
        rows = c.fetchall()
        print(f"rows: {len(rows)}")
        for r in rows:
            print(" ", r)

        print(f"\n--- Q4.7 viloes A∨C∨D nas 3 hands ---")
        c.execute(f"""
            SELECT h.hand_id, hv.player_name, hv.category
            FROM hands h
            JOIN hand_villains hv ON hv.hand_db_id = h.id
            WHERE h.hand_id IN ({in_clause})
            ORDER BY h.hand_id, hv.player_name;
        """)
        cols = [d[0] for d in c.description]
        print("cols:", cols)
        rows = c.fetchall()
        print(f"rows: {len(rows)}")
        for r in rows:
            print(" ", r)
    else:
        print("\n[Q4.4-Q4.7 saltados: nenhum TM extraido das SSs]")

    print("\n" + "=" * 78)
    print("DIAGNOSTICOS EXTRA")
    print("=" * 78)

    print("\n--- D1 estado das 3 entries SS recem-criadas ---")
    c.execute("""
        SELECT id, source, entry_type, status, file_name,
               raw_json->>'tm' AS tm,
               raw_json->>'hero' AS hero,
               (raw_json->>'vision_done')::boolean AS vd,
               created_at
        FROM entries
        WHERE created_at >= NOW() - INTERVAL '60 minutes'
          AND source != 'discord'
        ORDER BY id DESC;
    """)
    cols = [d[0] for d in c.description]
    print("cols:", cols)
    for r in c.fetchall():
        print(" ", r)

    print("\n--- D2 cross-check TMs SS vs TMs ZIP ---")
    c.execute("""
        WITH ss_tms AS (
          SELECT DISTINCT raw_json->>'tm' AS tm
          FROM entries
          WHERE created_at >= NOW() - INTERVAL '60 minutes'
            AND source != 'discord'
            AND raw_json->>'tm' IS NOT NULL
        ),
        zip_hand_tms AS (
          SELECT DISTINCT 'TM' || REPLACE(hand_id, 'GG-', '') AS tm
          FROM hands
          WHERE origin = 'hh_import' AND site = 'GGPoker'
        )
        SELECT
          (SELECT COUNT(*) FROM ss_tms) AS ss_tms_count,
          (SELECT COUNT(*) FROM ss_tms WHERE tm IN (SELECT tm FROM zip_hand_tms)) AS ss_tms_match_zip,
          (SELECT array_agg(tm) FROM ss_tms WHERE tm NOT IN (SELECT tm FROM zip_hand_tms)) AS ss_tms_fora_zip;
    """)
    cols = [d[0] for d in c.description]
    print("cols:", cols)
    for r in c.fetchall():
        print(" ", r)

    print("\n--- D3 delta hands mm='v2' / placeholders ss_upload ---")
    c.execute("""
        SELECT
          COUNT(*) FILTER (WHERE (player_names->>'match_method') = 'anchors_stack_elimination_v2') AS hands_mm_v2,
          COUNT(*) FILTER (WHERE origin = 'ss_upload') AS placeholders_ss
        FROM hands;
    """)
    cols = [d[0] for d in c.description]
    print("cols:", cols)
    for r in c.fetchall():
        print(" ", r)

    print("\n--- D4 delta hand_villains ---")
    c.execute("""
        SELECT COUNT(*) AS hand_villains_total,
               COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '60 minutes') AS hand_villains_novos
        FROM hand_villains;
    """)
    cols = [d[0] for d in c.description]
    print("cols:", cols)
    for r in c.fetchall():
        print(" ", r)

    print("\n--- D5 principio invariante GG anon ---")
    c.execute("""
        SELECT COUNT(*) AS bad_villains
        FROM hand_villains hv
        JOIN hands h ON h.id = hv.hand_db_id
        WHERE h.origin IN ('hh_import', 'ss_upload') AND h.site = 'GGPoker'
          AND (h.player_names->>'match_method') IS NULL;
    """)
    cols = [d[0] for d in c.description]
    print("cols:", cols)
    for r in c.fetchall():
        print(" ", r)

    print("\n--- D6 fix #P10 funcional: tm extraido em todos os SSs ---")
    c.execute("""
        SELECT COUNT(*) AS ss_total,
               COUNT(*) FILTER (WHERE raw_json->>'tm' IS NOT NULL) AS ss_com_tm
        FROM entries
        WHERE created_at >= NOW() - INTERVAL '60 minutes'
          AND source != 'discord';
    """)
    cols = [d[0] for d in c.description]
    print("cols:", cols)
    for r in c.fetchall():
        print(" ", r)

    conn.close()
    print("\n" + "=" * 78)
    print("FIM. Read-only.")


if __name__ == "__main__":
    main()
