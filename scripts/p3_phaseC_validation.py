"""Pipeline 3 - Etapa C/D/E + diagnostico extra. Read-only, 12 queries SELECT.
Corre via: railway run python scripts/p3_phaseC_validation.py
Janela INTERVAL ajustada para 60 minutes para apanhar tudo do sync recente."""
import os, sys, psycopg2

QUERIES = [
    ("Q3.1 entries Discord recentes (LIMIT 50)", """
        SELECT id, entry_type, discord_channel, discord_posted_at, status,
               raw_json->>'tm' AS tm,
               (raw_json->>'vision_done')::boolean AS vd,
               raw_json->>'hero' AS hero
        FROM entries
        WHERE source = 'discord' AND created_at >= NOW() - INTERVAL '60 minutes'
        ORDER BY created_at DESC
        LIMIT 50
    """),
    ("Q3.2 placeholders Discord criados", """
        SELECT h.id, h.hand_id, h.origin, h.hm3_tags, h.discord_tags,
               (h.player_names ->> 'match_method') AS mm
        FROM hands h
        WHERE h.origin = 'discord' AND h.created_at >= NOW() - INTERVAL '60 minutes'
        ORDER BY h.created_at DESC
        LIMIT 30
    """),
    ("Q3.3 cutoff 2026 respeitado (zero entries pre-cutoff)", """
        SELECT COUNT(*) AS pre_cutoff
        FROM entries
        WHERE source = 'discord' AND discord_posted_at < '2026-01-01 00:00:00+00'
          AND created_at >= NOW() - INTERVAL '60 minutes'
    """),
    ("Q3.4 TMs com 2+ entries Discord (cross-post real)", """
        SELECT raw_json->>'tm' AS tm, COUNT(*) AS n_entries,
               array_agg(DISTINCT discord_channel) AS channels
        FROM entries
        WHERE source = 'discord' AND raw_json->>'tm' IS NOT NULL
          AND created_at >= NOW() - INTERVAL '60 minutes'
        GROUP BY raw_json->>'tm'
        HAVING COUNT(*) >= 2
    """),
    ("Q3.5 cross-post propaga discord_tags (R4)", """
        WITH cross_tms AS (
          SELECT raw_json->>'tm' AS tm,
                 COUNT(*) AS n_entries,
                 array_agg(DISTINCT discord_channel) AS channels
          FROM entries
          WHERE source = 'discord' AND raw_json->>'tm' IS NOT NULL
            AND created_at >= NOW() - INTERVAL '60 minutes'
          GROUP BY raw_json->>'tm'
          HAVING COUNT(*) >= 2
        )
        SELECT h.hand_id, h.discord_tags, h.origin,
               cardinality(COALESCE(h.discord_tags, '{}'::text[])) AS n_discord_tags,
               cross_tms.n_entries AS n_entries_discord
        FROM cross_tms
        JOIN hands h ON h.hand_id = 'GG-' || cross_tms.tm
        ORDER BY h.hand_id
    """),
    ("Q3.6 hands ex-Discord com mm='v2' (preservando discord_tags)", """
        SELECT h.hand_id, (h.player_names ->> 'match_method') AS mm,
               h.discord_tags, h.origin,
               (h.raw IS NOT NULL AND h.raw <> '') AS has_raw
        FROM hands h
        WHERE h.discord_tags && ARRAY['nota','icm','pos-pko','icm-pko','pos','speed-racer']
          AND h.created_at >= NOW() - INTERVAL '60 minutes'
        ORDER BY h.hand_id
    """),
    ("Q3.7 Regra C: villains em canais 'nota' com match real", """
        SELECT h.hand_id, h.discord_tags, hv.player_name, hv.category
        FROM hands h
        JOIN hand_villains hv ON hv.hand_db_id = h.id
        WHERE 'nota' = ANY(h.discord_tags)
          AND (h.player_names ->> 'match_method') IS NOT NULL
          AND (h.player_names ->> 'match_method') NOT LIKE 'discord_placeholder_%'
          AND h.created_at >= NOW() - INTERVAL '60 minutes'
    """),
    ("Q3.8 invariante GG anon: zero villains em hands sem match", """
        SELECT COUNT(*) AS bad_villains
        FROM hand_villains hv
        JOIN hands h ON h.id = hv.hand_db_id
        WHERE h.site = 'GGPoker'
          AND ((h.player_names ->> 'match_method') IS NULL
               OR (h.player_names ->> 'match_method') LIKE 'discord_placeholder_%')
          AND h.played_at >= '2026-01-01'
    """),
    ("D1 estado Vision das entries Discord recentes", """
        SELECT
          COUNT(*) AS total_entries_discord,
          COUNT(*) FILTER (WHERE (raw_json->>'vision_done')::boolean = true) AS vision_done,
          COUNT(*) FILTER (WHERE (raw_json->>'vision_done')::boolean = false
                              OR raw_json->>'vision_done' IS NULL) AS vision_pending,
          COUNT(*) FILTER (WHERE entry_type = 'replayer_link') AS replayer_links,
          COUNT(*) FILTER (WHERE entry_type = 'image') AS images,
          COUNT(*) FILTER (WHERE entry_type = 'hand_history') AS hh_text
        FROM entries
        WHERE source = 'discord' AND created_at >= NOW() - INTERVAL '60 minutes'
    """),
    ("D2 cross-check: TMs Discord vs TMs ZIP", """
        WITH discord_tms AS (
          SELECT DISTINCT raw_json->>'tm' AS tm
          FROM entries
          WHERE source = 'discord' AND created_at >= NOW() - INTERVAL '60 minutes'
            AND raw_json->>'tm' IS NOT NULL
        ),
        zip_tms AS (
          SELECT DISTINCT tournament_number::text AS tm
          FROM hands
          WHERE origin = 'hh_import' AND created_at >= NOW() - INTERVAL '60 minutes'
        )
        SELECT
          (SELECT COUNT(*) FROM discord_tms) AS tms_em_discord,
          (SELECT COUNT(*) FROM zip_tms) AS tms_em_zip,
          (SELECT COUNT(*) FROM discord_tms WHERE tm IN (SELECT tm FROM zip_tms)) AS interseccao,
          (SELECT array_agg(tm) FROM (SELECT tm FROM discord_tms
            WHERE tm NOT IN (SELECT tm FROM zip_tms) LIMIT 10) s) AS tms_discord_sem_zip
    """),
    ("D3 hands ZIP promovidas a mm='v2'", """
        SELECT COUNT(*) AS hands_promovidas
        FROM hands
        WHERE origin = 'hh_import' AND site = 'GGPoker'
          AND (player_names ->> 'match_method') = 'anchors_stack_elimination_v2'
          AND created_at >= NOW() - INTERVAL '60 minutes'
    """),
    ("D4 viloes via Regra C nesta sessao", """
        SELECT h.hand_id, h.discord_tags, hv.player_name, hv.category
        FROM hands h
        JOIN hand_villains hv ON hv.hand_db_id = h.id
        WHERE h.origin = 'hh_import'
          AND 'nota' = ANY(h.discord_tags)
          AND (h.player_names ->> 'match_method') = 'anchors_stack_elimination_v2'
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
