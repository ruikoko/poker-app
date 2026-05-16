"""
hm3_scan_tags.py (v2)
---------------------
Lista todas as tags de marcação do HM3 com contagens por site.

Estrutura HM3 descoberta:
  - handmarkcategories (category_id, description) — definição das tags
  - hand_markings (marking_id, gamenumber, site_id)    — ligação tag→mão
    (marking_id = category_id)

Site IDs conhecidos: 2=PS, 22=Winamax, 24=WPN, 29=GG

Uso: python hm3_scan_tags.py
"""
import sys
import sqlite3
from pathlib import Path
from collections import defaultdict

try:
    from config_local import HM3_DB
except ImportError:
    print("ERRO: config_local.py não encontrado.")
    print("Copia config_local.example.py para config_local.py e preenche")
    print("com o teu caminho HM3.")
    sys.exit(1)

DB_PATH = Path(HM3_DB)

SITE_NAMES = {2: "PS", 22: "Winamax", 24: "WPN", 29: "GG"}


def main():
    if not DB_PATH.exists():
        print(f"BD nao encontrada: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT category_id, description FROM handmarkcategories ORDER BY description")
    categories = {r["category_id"]: r["description"] for r in cur.fetchall()}
    print(f"Total de tags definidas: {len(categories)}")
    print()

    cur.execute("""
        SELECT marking_id, site_id, COUNT(*) AS n
        FROM hand_markings
        GROUP BY marking_id, site_id
    """)
    per_tag_site = defaultdict(lambda: defaultdict(int))
    total_per_tag = defaultdict(int)
    for r in cur.fetchall():
        per_tag_site[r["marking_id"]][r["site_id"]] = r["n"]
        total_per_tag[r["marking_id"]] += r["n"]

    print(f"{'ID':<4} {'TAG':<30} {'TOTAL':>7}  {'PS':>6} {'WN':>6} {'WPN':>6} {'GG':>6}  {'OUTROS':>7}")
    print("-" * 86)

    sorted_ids = sorted(categories.keys(), key=lambda i: -total_per_tag.get(i, 0))
    for cat_id in sorted_ids:
        name = categories[cat_id]
        total = total_per_tag.get(cat_id, 0)
        if total == 0:
            continue
        by_site = per_tag_site.get(cat_id, {})
        ps = by_site.get(2, 0)
        wn = by_site.get(22, 0)
        wpn = by_site.get(24, 0)
        gg = by_site.get(29, 0)
        outros = total - (ps + wn + wpn + gg)
        print(f"{cat_id:<4} {str(name)[:30]:<30} {total:>7}  {ps:>6} {wn:>6} {wpn:>6} {gg:>6}  {outros:>7}")

    unused = [cat_id for cat_id in categories if total_per_tag.get(cat_id, 0) == 0]
    if unused:
        print()
        print(f"Tags definidas sem maos: {len(unused)}")
        for cat_id in unused[:20]:
            print(f"  {cat_id}: {categories[cat_id]}")
        if len(unused) > 20:
            print(f"  ... e mais {len(unused) - 20}")

    print()
    total_hands = sum(total_per_tag.values())
    print(f"Total de marcacoes (tag-hand pairs): {total_hands}")
    cur.execute("SELECT COUNT(DISTINCT gamenumber) FROM hand_markings")
    distinct = cur.fetchone()[0]
    print(f"Maos unicas marcadas: {distinct}")

    conn.close()


if __name__ == "__main__":
    main()
