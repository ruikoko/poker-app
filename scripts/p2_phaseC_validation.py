"""Pipeline 2 - Etapa C/D/E + diagnostico extra. Read-only, 13 queries SELECT.
Corre via: railway run python scripts/p2_phaseC_validation.py
Janela INTERVAL ajustada para 60 minutes para apanhar tudo do upload recente."""
import os, sys, psycopg2

QUERIES = [
    ("Q2.1 maos hh_import recentes (LIMIT 50)", """
        SELECT id, hand_id, origin, site, played_at, tournament_name, tournament_number,
               (player_names ->> 'match_method') AS mm,
               cardinality(COALESCE(discord_tags, '{}'::text[])) AS n_discord_tags
        FROM hands
        WHERE origin = 'hh_import' AND played_at >= '2026-01-01'
          AND created_at >= NOW() - INTERVAL '60 minutes'
        ORDER BY created_at DESC
        LIMIT 50
    """),
    ("Q2.2 placeholders Discord substituidos", """
        SELECT h.hand_id, (h.player_names ->> 'match_method') AS mm,
               h.discord_tags, h.origin
        FROM hands h
        WHERE h.hand_id LIKE 'GG-%'
          AND h.created_at >= NOW() - INTERVAL '60 minutes'
          AND cardinality(COALESCE(h.discord_tags, '{}'::text[])) > 0
        ORDER BY h.created_at DESC
        LIMIT 30
    """),
    ("Q2.3 cross-post: discord_tags com 2+ canais (R4)", """
        SELECT hand_id, discord_tags, origin, (player_names ->> 'match_method') AS mm
        FROM hands
        WHERE created_at >= NOW() - INTERVAL '60 minutes'
          AND cardinality(COALESCE(discord_tags, '{}'::text[])) >= 2
        ORDER BY hand_id
    """),
    ("Q2.4 tournaments_meta para TMs GG da nova importacao", """
        SELECT tournament_number, site, tournament_name, buy_in, currency,
               tournament_format, starting_stack, hand_count, updated_at
        FROM tournaments_meta
        WHERE site = 'GGPoker'
          AND updated_at >= NOW() - INTERVAL '60 minutes'
        ORDER BY updated_at DESC
    """),
    ("Q2.5 sanity Stack Inicial (nao mid-tournament)", """
        SELECT tournament_number, starting_stack, tournament_name
        FROM tournaments_meta
        WHERE site = 'GGPoker'
          AND updated_at >= NOW() - INTERVAL '60 minutes'
          AND (starting_stack IS NULL OR starting_stack < 1000)
        ORDER BY tournament_number
    """),
    ("Q2.6 invariante: zero rows non-GG em tournaments_meta", """
        SELECT COUNT(*) AS non_gg_rows FROM tournaments_meta WHERE site != 'GGPoker'
    """),
    ("Q2.7 hands ZIP que ganharam mm v2 retroactivamente", """
        SELECT h.hand_id, (h.player_names ->> 'match_method') AS mm,
               jsonb_typeof(h.player_names -> 'anon_map') AS anon_type,
               h.discord_tags
        FROM hands h
        WHERE h.origin = 'hh_import'
          AND h.created_at >= NOW() - INTERVAL '60 minutes'
          AND (h.player_names ->> 'match_method') = 'anchors_stack_elimination_v2'
        LIMIT 5
    """),
    ("Q2.8 anon_map nunca vazio quando mm=v2 (#B32 fix)", """
        SELECT h.hand_id,
               jsonb_typeof(h.player_names -> 'anon_map') AS anon_type,
               (h.player_names -> 'anon_map') = '{}'::jsonb AS is_empty_object
        FROM hands h
        WHERE (h.player_names ->> 'match_method') = 'anchors_stack_elimination_v2'
          AND h.created_at >= NOW() - INTERVAL '60 minutes'
          AND (
            (h.player_names -> 'anon_map') IS NULL
            OR jsonb_typeof(h.player_names -> 'anon_map') != 'object'
            OR (h.player_names -> 'anon_map') = '{}'::jsonb
          )
    """),
    ("Q2.9 viloes em hh_import com discord_tags 'nota' (Regra C)", """
        SELECT h.hand_id, h.discord_tags, hv.category, hv.player_name
        FROM hands h
        JOIN hand_villains hv ON hv.hand_db_id = h.id
        WHERE h.origin = 'hh_import'
          AND h.created_at >= NOW() - INTERVAL '60 minutes'
          AND 'nota' = ANY(h.discord_tags)
        ORDER BY h.hand_id
    """),
    ("D1 invariante GG anon: zero villains em hands ZIP recentes", """
        SELECT COUNT(*) AS villains_em_gg_zip
        FROM hand_villains hv
        JOIN hands h ON h.id = hv.hand_db_id
        WHERE h.origin = 'hh_import' AND h.site = 'GGPoker'
          AND h.created_at >= NOW() - INTERVAL '60 minutes'
    """),
    ("D2 R12: zero maos pre-2026 inseridas", """
        SELECT COUNT(*) AS hands_pre_2026
        FROM hands
        WHERE origin = 'hh_import' AND played_at < '2026-01-01'
          AND created_at >= NOW() - INTERVAL '60 minutes'
    """),
    ("D3 distribuicao por tournament_number (quantos torneios?)", """
        SELECT tournament_number, COUNT(*) AS n_hands
        FROM hands
        WHERE origin = 'hh_import'
          AND created_at >= NOW() - INTERVAL '60 minutes'
        GROUP BY tournament_number
        ORDER BY n_hands DESC
    """),
    ("D4 sanity tournaments_meta vs hands (1 row por TM)", """
        SELECT
          (SELECT COUNT(DISTINCT tournament_number) FROM hands
            WHERE origin='hh_import' AND created_at >= NOW() - INTERVAL '60 minutes') AS tms_em_hands,
          (SELECT COUNT(*) FROM tournaments_meta
            WHERE site='GGPoker' AND updated_at >= NOW() - INTERVAL '60 minutes') AS rows_em_meta
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
