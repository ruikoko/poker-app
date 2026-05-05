"""Cross-cutting X1-X5 — validacao de regras duras globais.
Read-only. Corre via: railway run python scripts/cross_cutting_validation.py
Queries literais do playbook docs/VERIFICACAO_PIPELINES.md seccao Cross-cutting."""
import os, sys, psycopg2

QUERIES = [
    # X1 — Estudo respeita regras duras
    ("X1.1 R1: zero hands GG sem mm real em Estudo (esp 0)", """
        SELECT COUNT(*) AS violations FROM hands h
        WHERE h.played_at >= '2026-01-01'
          AND h.site = 'GGPoker'
          AND h.study_state IN ('new', 'resolved')
          AND ((h.player_names ->> 'match_method') IS NULL
               OR (h.player_names ->> 'match_method') LIKE 'discord_placeholder_%')
    """),
    ("X1.1b sample violations X1.1 (LIMIT 5)", """
        SELECT id, hand_id, study_state,
               (player_names ->> 'match_method') AS mm
        FROM hands h
        WHERE h.played_at >= '2026-01-01'
          AND h.site = 'GGPoker'
          AND h.study_state IN ('new', 'resolved')
          AND ((h.player_names ->> 'match_method') IS NULL
               OR (h.player_names ->> 'match_method') LIKE 'discord_placeholder_%')
        LIMIT 5
    """),
    ("X1.2 R3: zero hands sem HH em Estudo (esp 0)", """
        SELECT COUNT(*) AS violations FROM hands h
        WHERE h.played_at >= '2026-01-01'
          AND h.study_state IN ('new', 'resolved')
          AND (h.raw IS NULL OR h.raw = '')
    """),
    ("X1.2b sample violations X1.2 (LIMIT 5)", """
        SELECT id, hand_id, origin, study_state, hm3_tags, discord_tags
        FROM hands h
        WHERE h.played_at >= '2026-01-01'
          AND h.study_state IN ('new', 'resolved')
          AND (h.raw IS NULL OR h.raw = '')
        LIMIT 5
    """),
    ("X1.3 R2: zero hands so com tag 'nota' em Estudo (esp 0)", """
        SELECT COUNT(*) AS violations FROM hands h
        WHERE h.played_at >= '2026-01-01'
          AND h.study_state IN ('new', 'resolved')
          AND NOT EXISTS (
            SELECT 1 FROM unnest(COALESCE(h.hm3_tags, '{}')) t WHERE t NOT ILIKE 'nota%'
          )
          AND NOT EXISTS (
            SELECT 1 FROM unnest(COALESCE(h.discord_tags, '{}')) t WHERE t != 'nota'
          )
    """),

    # X2 — Vilões A∨C∨D + invariante GG anon
    ("X2.1 distribuicao por category em hand_villains (esp nota+friend; sd histor/0)", """
        SELECT category, COUNT(*) AS n
        FROM hand_villains hv
        JOIN hands h ON h.id = hv.hand_db_id
        WHERE h.played_at >= '2026-01-01'
        GROUP BY category
        ORDER BY category
    """),
    ("X2.3 invariante GG anon: zero villains em hands sem mm real (esp 0)", """
        SELECT COUNT(*) AS bad_villains
        FROM hand_villains hv
        JOIN hands h ON h.id = hv.hand_db_id
        WHERE h.site = 'GGPoker'
          AND ((h.player_names ->> 'match_method') IS NULL
               OR (h.player_names ->> 'match_method') LIKE 'discord_placeholder_%')
          AND h.played_at >= '2026-01-01'
    """),

    # X3 — Cross-post Discord
    ("X3.1 hands com 2+ canais Discord (LIMIT 30)", """
        SELECT hand_id, discord_tags, origin, (player_names ->> 'match_method') AS mm
        FROM hands
        WHERE played_at >= '2026-01-01'
          AND cardinality(COALESCE(discord_tags, '{}'::text[])) >= 2
        ORDER BY hand_id DESC LIMIT 30
    """),
    ("X3.2 cross-posts sem reflexao em discord_tags (esp 0)", """
        WITH cross_tms AS (
          SELECT raw_json->>'tm' AS tm, COUNT(*) AS n_entries
          FROM entries
          WHERE source = 'discord' AND raw_json->>'tm' IS NOT NULL
          GROUP BY raw_json->>'tm'
          HAVING COUNT(*) >= 2
        )
        SELECT 'GG-' || cross_tms.tm AS hand_id_expected,
               cross_tms.n_entries
        FROM cross_tms
        LEFT JOIN hands h ON h.hand_id = 'GG-' || REPLACE(cross_tms.tm, 'TM', '')
        WHERE h.id IS NULL OR cardinality(COALESCE(h.discord_tags, '{}'::text[])) < 2
    """),

    # X4 — Counters Dashboard
    ("X4.2 ss_match_pending counter (esp 0 nesta sessao)", """
        SELECT COUNT(*) AS ss_match_pending FROM hands
        WHERE origin = 'ss_upload'
          AND (player_names ->> 'match_method') = 'discord_placeholder_no_hh'
    """),
    ("X4.3 GG Discord placeholders (esp 0 nesta sessao)", """
        SELECT COUNT(*) AS gg_discord_placeholders FROM hands
        WHERE 'GGDiscord' = ANY(hm3_tags)
    """),

    # X5 — Health checks
    ("X5.1 distribuicao por origin (2026)", """
        SELECT origin, COUNT(*) AS n
        FROM hands
        WHERE played_at >= '2026-01-01'
        GROUP BY origin
        ORDER BY origin
    """),
    ("X5.2 distribuicao study_state (esp 'new'/'resolved'/'mtt_archive')", """
        SELECT study_state, COUNT(*) AS n FROM hands
        WHERE played_at >= '2026-01-01'
        GROUP BY study_state
    """),
    ("X5.3 entries por (source, entry_type)", """
        SELECT source, entry_type, COUNT(*) AS n FROM entries
        GROUP BY source, entry_type
        ORDER BY source, entry_type
    """),
    ("X5.4 hand_villains UNIQUE composto (esp 0 dups)", """
        SELECT hand_db_id, player_name, category, COUNT(*) AS dup
        FROM hand_villains
        GROUP BY hand_db_id, player_name, category
        HAVING COUNT(*) > 1
    """),
    ("X5.5 villain_notes hands_seen sanity", """
        SELECT COUNT(*) AS notes_total,
               COUNT(*) FILTER (WHERE hands_seen > 0) AS notes_active,
               SUM(hands_seen) AS sum_hands_seen
        FROM villain_notes
    """),
    ("X5.6 hands NULLs em campos required (origin/site/played_at)", """
        SELECT
          COUNT(*) FILTER (WHERE origin IS NULL) AS null_origin,
          COUNT(*) FILTER (WHERE site IS NULL) AS null_site,
          COUNT(*) FILTER (WHERE played_at IS NULL) AS null_played_at
        FROM hands
        WHERE played_at >= '2026-01-01' OR played_at IS NULL
    """),
    ("X5.7 hand_villains FK orphans (hand_db_id sem hand)", """
        SELECT COUNT(*) AS orphans
        FROM hand_villains hv
        LEFT JOIN hands h ON h.id = hv.hand_db_id
        WHERE h.id IS NULL
    """),
]

def main():
    url = os.environ.get("DATABASE_PUBLIC_URL")
    if not url:
        sys.exit("ERRO: DATABASE_PUBLIC_URL nao setado.")
    print(f"DB: {url.split('@')[1].split('/')[0]}")
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
    print("FIM. Read-only.")


if __name__ == "__main__":
    main()
