"""
Parser de summaries Winamax.
Aceita um ficheiro .txt individual ou um .zip com múltiplos ficheiros.
Devolve lista de dicts prontos para inserção em tournaments.
"""
import re
import zipfile
import io
from datetime import date
from typing import Iterator

# ── Mapeamentos ───────────────────────────────────────────────────────────────

SPEED_MAP = {
    "normal":    "normal",
    "semiturbo": "turbo",
    "turbo":     "hyper",
}

TYPE_MAP = {
    "knockout": "ko",
    "normal":   "nonko",
    "flight":   "ko",   # multi-day com bounty
}

# ── Parser de ficheiro individual ─────────────────────────────────────────────

def _parse_one(text: str, filename: str = "") -> dict | None:
    """Parseia um summary Winamax. Devolve dict ou None se não reconhecido."""

    # Tournament ID
    tid_m = re.search(r"Tournament\s+#(\d+)", text)
    if not tid_m:
        return None
    tid = tid_m.group(1)

    # Nome
    name_m = re.search(r"Tournament name\s*:\s*(.+)", text)
    name = name_m.group(1).strip() if name_m else filename

    # Data  (formato: 2026/01/15 ou 2026-01-15)
    date_m = re.search(r"(\d{4})[/-](\d{2})[/-](\d{2})", text)
    if not date_m:
        return None
    tour_date = date(int(date_m.group(1)), int(date_m.group(2)), int(date_m.group(3)))

    # Buy-in
    buyin_m = re.search(r"Buy-[Ii]n\s*:\s*([\d,.]+)\s*€", text)
    buyin = float(buyin_m.group(1).replace(",", ".")) if buyin_m else 0.0

    # Cashout (prize)
    prize_m = re.search(r"(?:You won|Prize)\s*:\s*([\d,.]+)\s*€", text)
    cashout = float(prize_m.group(1).replace(",", ".")) if prize_m else 0.0

    # Posição
    pos_m = re.search(r"(?:You finished|Finished)\s+(?:in\s+)?(\d+)(?:st|nd|rd|th)?", text, re.I)
    position = int(pos_m.group(1)) if pos_m else None

    # Jogadores
    players_m = re.search(r"(\d+)\s+players?", text, re.I)
    players = int(players_m.group(1)) if players_m else None

    # Tipo
    type_raw = ""
    type_m = re.search(r"^Type\s*:\s*(.+)$", text, re.M)
    if type_m:
        type_raw = type_m.group(1).strip().lower()
    tour_type = TYPE_MAP.get(type_raw, "nonko")

    # Speed
    speed_raw = ""
    speed_m = re.search(r"^Speed\s*:\s*(.+)$", text, re.M)
    if speed_m:
        speed_raw = speed_m.group(1).strip().lower()
    speed = SPEED_MAP.get(speed_raw, "normal")

    return {
        "site":     "Winamax",
        "tid":      tid,
        "name":     name,
        "date":     tour_date,
        "buyin":    buyin,
        "cashout":  cashout,
        "position": position,
        "players":  players,
        "type":     tour_type,
        "speed":    speed,
        "currency": "€",
    }

# ── Interface pública ─────────────────────────────────────────────────────────

def parse_file(content: bytes, filename: str) -> tuple[list[dict], list[str]]:
    """
    Aceita bytes de um .txt ou .zip.
    Devolve (records, errors).
    """
    records = []
    errors = []

    if filename.lower().endswith(".zip"):
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                for name in zf.namelist():
                    if not name.lower().endswith(".txt"):
                        continue
                    try:
                        text = zf.read(name).decode("utf-8", errors="replace")
                        rec = _parse_one(text, name)
                        if rec:
                            records.append(rec)
                        else:
                            errors.append(f"Não reconhecido: {name}")
                    except Exception as e:
                        errors.append(f"Erro em {name}: {e}")
        except Exception as e:
            errors.append(f"ZIP inválido: {e}")

    elif filename.lower().endswith(".txt"):
        try:
            text = content.decode("utf-8", errors="replace")
            rec = _parse_one(text, filename)
            if rec:
                records.append(rec)
            else:
                errors.append(f"Não reconhecido: {filename}")
        except Exception as e:
            errors.append(f"Erro: {e}")

    else:
        errors.append(f"Formato não suportado: {filename}")

    return records, errors
