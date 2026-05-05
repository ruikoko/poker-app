"""Pipeline 1 - Etapa C/D + diagnostico extra. Read-only, 10 queries SELECT.
Corre via: railway run python scripts/p1_phaseC_validation.py"""
import os, sys, psycopg2

QUERIES = [
    ("Q1.1 maos HM3 recentes (LIMIT 50)", """
        SELECT id, hand_id, site, origin, hm3_tags, tags,
               played_at, tournament_name, tournament_number, buy_in,
               position, result, hero_cards,
               (raw IS NOT NULL AND raw <> '') AS has_raw
        FROM hands
        WHERE origin = 'hm3' AND played_at >= '2026-01-01'
          AND created_at >= NOW() - INTERVAL '30 minutes'
        ORDER BY created_at DESC
        LIMIT 50
    """),
    ("Q1.2 distribuicao por site", """
        SELECT site, COUNT(*) AS n
        FROM hands
        WHERE origin = 'hm3' AND created_at >= NOW() - INTERVAL '30 minutes'
        GROUP BY site ORDER BY site
    """),
    ("Q1.3 distribuicao por hm3_tags", """
        SELECT unnest(hm3_tags) AS tag, COUNT(*) AS n
        FROM hands
        WHERE origin = 'hm3' AND created_at >= NOW() - INTERVAL '30 minutes'
        GROUP BY tag ORDER BY n DESC
    """),
    ("Q1.4 invariante: zero GG via HM3", """
        SELECT COUNT(*) AS gg_via_hm3 FROM hands
        WHERE origin = 'hm3' AND site = 'GGPoker'
          AND created_at >= NOW() - INTERVAL '30 minutes'
    """),
    ("Q1.5 viloes nas maos HM3 recentes", """
        SELECT h.hand_id, h.site, h.hm3_tags, hv.category, COUNT(hv.id) AS n_villains
        FROM hands h
        LEFT JOIN hand_villains hv ON hv.hand_db_id = h.id
        WHERE h.origin = 'hm3' AND h.created_at >= NOW() - INTERVAL '30 minutes'
        GROUP BY h.id, h.hand_id, h.site, h.hm3_tags, hv.category
        ORDER BY h.created_at DESC
        LIMIT 30
    """),
    ("Q1.6 FRIEND_HEROES sanity (Karluz/flightrisk)", """
        SELECT hv.player_name, hv.category, COUNT(*) AS n
        FROM hand_villains hv
        JOIN hands h ON h.id = hv.hand_db_id
        WHERE h.origin = 'hm3' AND h.created_at >= NOW() - INTERVAL '30 minutes'
          AND LOWER(hv.player_name) IN ('karluz', 'flightrisk')
        GROUP BY hv.player_name, hv.category
    """),
    ("Q1.7 villain_notes (total + recent)", """
        SELECT COUNT(*) AS total_villain_notes,
               (SELECT COUNT(*) FROM villain_notes
                  WHERE updated_at >= NOW() - INTERVAL '30 minutes') AS recent
        FROM villain_notes
    """),
    ("D1 maos HM3 recentes com tag nota%", """
        SELECT COUNT(*) AS n_with_nota_tag
        FROM hands
        WHERE origin = 'hm3' AND created_at >= NOW() - INTERVAL '30 minutes'
          AND EXISTS (SELECT 1 FROM unnest(hm3_tags) t WHERE t ILIKE 'nota%')
    """),
    ("D2 maos HM3 recentes com Karluz/flightrisk como non-hero (via APA)", """
        WITH recent AS (
          SELECT id, hand_id, all_players_actions
          FROM hands
          WHERE origin = 'hm3' AND created_at >= NOW() - INTERVAL '30 minutes'
            AND all_players_actions IS NOT NULL
        ),
        flagged AS (
          SELECT r.id, r.hand_id,
                 array_agg(k) AS friend_keys
          FROM recent r,
               LATERAL jsonb_object_keys(r.all_players_actions) k
          WHERE k <> '_meta'
            AND LOWER(k) IN ('karluz', 'flightrisk')
          GROUP BY r.id, r.hand_id
        )
        SELECT
          (SELECT COUNT(*) FROM flagged) AS n_hands_with_friend,
          (SELECT array_agg(hand_id ORDER BY hand_id)
             FROM (SELECT hand_id FROM flagged LIMIT 10) s) AS sample_hand_ids
    """),
    ("D3 discrepancia 102 -> 94: hands com >=2 tags", """
        SELECT COUNT(*) AS hands_inseridas,
               SUM(cardinality(hm3_tags)) AS soma_tags,
               COUNT(*) FILTER (WHERE cardinality(hm3_tags) >= 2) AS hands_2_or_more_tags
        FROM hands
        WHERE origin = 'hm3' AND created_at >= NOW() - INTERVAL '30 minutes'
    """),
]

def main():
    url = os.environ.get("DATABASE_PUBLIC_URL")
    if not url:
        sys.exit("ERRO: DATABASE_PUBLIC_URL nao setado (correr via 'railway run').")
    host = url.split("@")[1].split("/")[0]
    print(f"DB: {host}")
    print("=" * 78)
    with psycopg2.connect(url) as conn, conn.cursor() as c:
        for label, sql in QUERIES:
            print(f"\n--- {label} ---")
            try:
                c.execute(sql)
                cols = [d[0] for d in c.description]
                rows = c.fetchall()
                print("cols:", cols)
                print(f"rows: {len(rows)}")
                for r in rows:
                    print(" ", r)
            except Exception as exc:
                print(f"  ERRO: {exc}")
                conn.rollback()
    print("\n" + "=" * 78)
    print("FIM. Read-only. Sem escrita.")

if __name__ == "__main__":
    main()
