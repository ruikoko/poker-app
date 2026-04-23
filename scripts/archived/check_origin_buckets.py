import psycopg2, os, sys

conn = psycopg2.connect(os.environ['DATABASE_PUBLIC_URL'])
c = conn.cursor()

print("=" * 70)
print("BREAKDOWN GERAL (2026+):")
print("=" * 70)
c.execute("""
    SELECT COALESCE(origin, 'NULL') AS origin, COUNT(*)
    FROM hands
    WHERE played_at >= '2026-01-01'
    GROUP BY origin
    ORDER BY COUNT(*) DESC
""")
for r in c.fetchall():
    print(f"  {r[0]:<20} {r[1]}")

print()
print("=" * 70)
print("PARTIÇÃO das origin=NULL por sinais distintivos:")
print("=" * 70)

c.execute("""
    SELECT
      CASE
        WHEN hm3_tags IS NOT NULL AND array_length(hm3_tags, 1) > 0
             AND NOT ('GGDiscord' = ANY(hm3_tags))
          THEN '1_hm3_tags_present'
        WHEN discord_tags IS NOT NULL AND array_length(discord_tags, 1) > 0
          THEN '2_discord_tags_present'
        WHEN site IN ('Winamax','PokerStars','WPN')
          THEN '3_non_gg_site (=>hh_import)'
        WHEN entry_id IS NOT NULL
             AND EXISTS (SELECT 1 FROM entries e WHERE e.id = hands.entry_id AND e.source = 'hh_text')
          THEN '4_entry_hh_text (=>hh_import)'
        WHEN site = 'GGPoker'
             AND EXISTS (SELECT 1 FROM mtt_hands mh WHERE mh.tm_number IS NOT NULL
                         AND replace(hands.hand_id, 'GG-', '') = replace(replace(mh.tm_number, 'TM', ''), '#',''))
          THEN '5_in_mtt_hands (=>mtt_import)'
        WHEN site = 'GGPoker' AND study_state = 'mtt_archive'
          THEN '6_gg_mtt_archive (=>mtt_import?)'
        WHEN site = 'GGPoker' AND study_state = 'new'
          THEN '7_gg_study_new (=>hh_import?)'
        ELSE '9_unknown'
      END AS bucket,
      COUNT(*) AS n
    FROM hands
    WHERE origin IS NULL AND played_at >= '2026-01-01'
    GROUP BY bucket
    ORDER BY bucket
""")
rows = c.fetchall()
total = 0
for r in rows:
    print(f"  {r[0]:<40} {r[1]}")
    total += r[1]
print(f"  {'TOTAL':<40} {total}")

print()
print("=" * 70)
print("AMOSTRAS por bucket (max 3):")
print("=" * 70)
for bucket_cond, label in [
    ("hm3_tags IS NOT NULL AND array_length(hm3_tags,1)>0 AND NOT ('GGDiscord' = ANY(hm3_tags))", "hm3_tags_present"),
    ("site IN ('Winamax','PokerStars','WPN')", "non_gg_site"),
    ("site='GGPoker' AND study_state='mtt_archive' AND (hm3_tags IS NULL OR array_length(hm3_tags,1)=0)", "gg_mtt_archive"),
    ("site='GGPoker' AND study_state='new' AND (hm3_tags IS NULL OR array_length(hm3_tags,1)=0) AND (discord_tags IS NULL OR array_length(discord_tags,1)=0)", "gg_study_new"),
]:
    print(f"\n-- {label} --")
    c.execute(f"""
        SELECT id, hand_id, site, played_at, study_state, hm3_tags, discord_tags, entry_id
        FROM hands
        WHERE origin IS NULL AND played_at >= '2026-01-01' AND ({bucket_cond})
        ORDER BY played_at DESC
        LIMIT 3
    """)
    for r in c.fetchall():
        print(f"  id={r[0]} hand_id={r[1]} site={r[2]} played={r[3]} study={r[4]} hm3={r[5]} disc={r[6]} entry={r[7]}")

print()
print("=" * 70)
print("CROSS-CHECK — entries.source das origin=NULL com entry_id:")
print("=" * 70)
c.execute("""
    SELECT COALESCE(e.source, '(no entry)') AS src,
           COALESCE(e.entry_type, '-') AS etype,
           COUNT(*) AS n
    FROM hands h
    LEFT JOIN entries e ON e.id = h.entry_id
    WHERE h.origin IS NULL AND h.played_at >= '2026-01-01'
    GROUP BY src, etype
    ORDER BY n DESC
""")
for r in c.fetchall():
    print(f"  source={r[0]:<15} entry_type={r[1]:<20} n={r[2]}")

c.close()
conn.close()
