"""
HM3 → Poker App — Exporta mãos tagadas do HM3 e envia para a API.

Uso:
  python hm3_export.py                    # todas as mãos tagadas
  python hm3_export.py --days 7           # últimos 7 dias
  python hm3_export.py --tag "nota++"     # só mãos com tag "nota++"
  python hm3_export.py --tag "nota++" --days 3
  python hm3_export.py --dry-run          # só mostra o que faria, não envia

Requisitos:
  - Python 3.10+
  - Módulo requests: pip install requests
  - HM3 pode estar aberto (SQLite lê sem bloquear)
  - config_local.py preenchido (ver config_local.example.py)
"""

import sqlite3
import csv
import io
import os
import sys
import argparse
from datetime import datetime, timedelta, timezone

try:
    import requests
except ImportError:
    print("ERRO: instala o módulo requests primeiro:")
    print("  pip install requests")
    sys.exit(1)

# ── Configuração ──────────────────────────────────────────────────────────────

try:
    from config_local import HM3_DB, LOGIN_EMAIL, LOGIN_PASS
except ImportError:
    print("ERRO: config_local.py não encontrado.")
    print("Copia config_local.example.py para config_local.py e preenche")
    print("com o teu caminho HM3 + credenciais da poker app.")
    sys.exit(1)

POKER_APP_URL = "https://poker-app-production-34a7.up.railway.app"

# ── Funções ───────────────────────────────────────────────────────────────────

def login(session):
    """Autentica na poker app e guarda o cookie de sessão."""
    r = session.post(
        f"{POKER_APP_URL}/api/auth/login",
        json={"email": LOGIN_EMAIL, "password": LOGIN_PASS},
    )
    if r.status_code != 200:
        print(f"ERRO login: {r.status_code} {r.text}")
        sys.exit(1)
    print(f"Login OK: {LOGIN_EMAIL}")


def fetch_tagged_hands(db_path, tag_filter=None, days_back=None):
    """Lê mãos tagadas da BD SQLite do HM3.

    Returns list of dicts com colunas:
      gamenumber, site_id, tag, handtimestamp, tournament_number, handhistory
    """
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    # Buscar mapa de tags (category_id → description)
    tag_map = {}
    for row in conn.execute("SELECT category_id, description FROM handmarkcategories"):
        tag_map[row["category_id"]] = row["description"]

    print(f"Tags no HM3: {len(tag_map)}")

    # Query: mãos que têm pelo menos uma marcação
    query = """
        SELECT DISTINCT
            hh.gamenumber,
            hh.pokersite_id AS site_id,
            hm.marking_id,
            hh.handtimestamp,
            hh.tournament_number,
            hh.handhistory
        FROM hand_markings hm
        JOIN handhistories hh
            ON hh.gamenumber = hm.gamenumber
            AND hh.pokersite_id = hm.site_id
        WHERE 1=1
    """
    params = []

    if tag_filter:
        # Encontrar category_id para esta tag
        cat_ids = [cid for cid, desc in tag_map.items()
                   if desc.lower().strip() == tag_filter.lower().strip()]
        if not cat_ids:
            # Tentar match parcial
            cat_ids = [cid for cid, desc in tag_map.items()
                       if tag_filter.lower() in desc.lower()]
        if not cat_ids:
            print(f"ERRO: tag '{tag_filter}' não encontrada no HM3.")
            print(f"Tags disponíveis: {', '.join(sorted(tag_map.values()))}")
            conn.close()
            return []
        placeholders = ",".join("?" * len(cat_ids))
        query += f" AND hm.marking_id IN ({placeholders})"
        params.extend(cat_ids)
        print(f"Filtro tag: '{tag_filter}' → IDs {cat_ids}")

    if days_back:
        cutoff = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days_back)).strftime("%Y-%m-%d %H:%M:%S")
        query += " AND hh.handtimestamp >= ?"
        params.append(cutoff)
        print(f"Filtro data: últimos {days_back} dias (desde {cutoff})")

    query += " ORDER BY hh.handtimestamp DESC"

    rows = conn.execute(query, params).fetchall()
    print(f"Mãos encontradas: {len(rows)}")

    # Agrupar por (gamenumber, site_id) para juntar tags múltiplas
    hands = {}
    for row in rows:
        key = (row["gamenumber"], str(row["site_id"]))
        if key not in hands:
            hands[key] = {
                "gamenumber": row["gamenumber"],
                "site_id": str(row["site_id"]),
                "tags": [],
                "handtimestamp": row["handtimestamp"] or "",
                "tournament_number": row["tournament_number"] or "",
                "handhistory": row["handhistory"] or "",
            }
        tag_name = tag_map.get(row["marking_id"], f"tag_{row['marking_id']}")
        if tag_name not in hands[key]["tags"]:
            hands[key]["tags"].append(tag_name)

    conn.close()

    # Expandir: uma row por (mão, tag) — formato que o endpoint espera
    result = []
    for data in hands.values():
        for tag in data["tags"]:
            result.append({
                "gamenumber": data["gamenumber"],
                "site_id": data["site_id"],
                "tag": tag,
                "handtimestamp": data["handtimestamp"],
                "tournament_number": data["tournament_number"],
                "handhistory": data["handhistory"],
            })

    print(f"Rows CSV (mãos × tags): {len(result)}")
    return result


def build_csv(rows):
    """Constrói CSV em memória no formato que /api/hm3/import espera."""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        "gamenumber", "site_id", "tag", "handtimestamp",
        "tournament_number", "handhistory"
    ])
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return output.getvalue()


def send_to_api(session, csv_text, days_back=None):
    """Envia o CSV para POST /api/hm3/import."""
    files = {"file": ("hm3_export.csv", csv_text.encode("utf-8"), "text/csv")}
    params = {}
    if days_back:
        params["days_back"] = days_back

    url = f"{POKER_APP_URL}/api/hm3/import"
    r = session.post(url, files=files, params=params)

    if r.status_code != 200:
        print(f"ERRO API: {r.status_code} {r.text}")
        return None

    return r.json()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Exporta mãos tagadas do HM3 e envia para a Poker App"
    )
    parser.add_argument("--days", type=int, help="Últimos N dias (default: tudo)")
    parser.add_argument("--tag", type=str, help="Filtrar por tag específica")
    parser.add_argument("--dry-run", action="store_true",
                        help="Só mostra o que faria, não envia")
    parser.add_argument("--save-csv", type=str,
                        help="Guarda o CSV num ficheiro (ex: export.csv)")
    args = parser.parse_args()

    # Verificar BD
    if not os.path.exists(HM3_DB):
        print(f"ERRO: BD não encontrada em {HM3_DB}")
        sys.exit(1)

    print(f"BD HM3: {HM3_DB}")
    print(f"Poker App: {POKER_APP_URL}")
    print("─" * 50)

    # Extrair mãos
    rows = fetch_tagged_hands(HM3_DB, tag_filter=args.tag, days_back=args.days)
    if not rows:
        print("Nenhuma mão para exportar.")
        return

    # Construir CSV
    csv_text = build_csv(rows)
    csv_size_kb = len(csv_text.encode("utf-8")) / 1024
    print(f"CSV gerado: {csv_size_kb:.0f} KB")

    # Guardar CSV se pedido
    if args.save_csv:
        with open(args.save_csv, "w", encoding="utf-8") as f:
            f.write(csv_text)
        print(f"CSV guardado em: {args.save_csv}")

    if args.dry_run:
        print("\n[DRY RUN] Não enviado. Usa sem --dry-run para enviar.")
        # Mostrar resumo de tags
        tag_counts = {}
        for r in rows:
            tag_counts[r["tag"]] = tag_counts.get(r["tag"], 0) + 1
        print("\nResumo por tag:")
        for tag, count in sorted(tag_counts.items(), key=lambda x: -x[1]):
            print(f"  {tag}: {count} mãos")
        return

    # Login e enviar
    print("─" * 50)
    session = requests.Session()
    login(session)

    print("A enviar para a API...")
    result = send_to_api(session, csv_text)

    if result:
        print("─" * 50)
        print(f"Status: {result.get('status', '?')}")
        print(f"Inseridas: {result.get('inserted', 0)}")
        print(f"Duplicados: {result.get('skipped_duplicates', 0)}")
        print(f"Filtradas por data: {result.get('skipped_date_filter', 0)}")
        print(f"Vilões criados: {result.get('villains_created', 0)}")
        print(f"Erros: {result.get('errors', 0)}")
        error_log = result.get('error_log') or []
        if error_log:
            print("─" * 50)
            print("Detalhe dos erros:")
            for msg in error_log:
                print(f"  • {msg}")
    else:
        print("Falha no envio.")


if __name__ == "__main__":
    main()
