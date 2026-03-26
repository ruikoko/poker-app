"""
Parser de summaries GGPoker.
Aceita um ficheiro .txt individual ou .zip com múltiplos ficheiros.
Nota: GGPoker não inclui Tournament ID nos summaries — tid fica vazio.
"""
import re
import zipfile
import io
from datetime import date

# ── Classificação por nome ────────────────────────────────────────────────────

def _classify(name: str) -> tuple[str, str]:
    """Devolve (type, speed) a partir do nome do torneio."""
    n = name.lower()

    # Speed
    if any(x in n for x in ["hypersonic", "hyper", "daily hyper", "sunday hyper"]):
        speed = "hyper"
    elif any(x in n for x in ["speed racer", "turbo", "heater"]):
        speed = "turbo"
    else:
        speed = "normal"

    # Type
    if any(x in n for x in ["bounty", "bounty hunters", "ko", "knockout", "mystery bounty", "mystery"]):
        tour_type = "ko"
    else:
        tour_type = "nonko"

    return tour_type, speed

# ── Parser de ficheiro individual ─────────────────────────────────────────────

def _parse_one(text: str, filename: str = "") -> dict | None:
    """Parseia um summary GGPoker. Devolve dict ou None."""

    # Nome do torneio — primeira linha não vazia
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return None
    name = lines[0]

    # Data
    date_m = re.search(r"(\d{4})[/-](\d{2})[/-](\d{2})", text)
    if not date_m:
        # fallback: tentar formato "Jan 02, 2026"
        date_m2 = re.search(
            r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2}),?\s+(\d{4})", text
        )
        if date_m2:
            month_map = {"Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,
                         "Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12}
            m, d, y = date_m2.group(1), int(date_m2.group(2)), int(date_m2.group(3))
            tour_date = date(y, month_map[m], d)
        else:
            return None
    else:
        tour_date = date(int(date_m.group(1)), int(date_m.group(2)), int(date_m.group(3)))

    # Buy-in  (formato: $50+$5  ou  Buy-In: $50+$5)
    buyin_m = re.search(r"Buy-?[Ii]n\s*:?\s*\$?([\d.]+)\+\$?([\d.]+)(?:\+\$?([\d.]+))?", text)
    if buyin_m:
        buyin = sum(float(x) for x in buyin_m.groups() if x)
    else:
        # fallback: valor único
        single_m = re.search(r"Buy-?[Ii]n\s*:?\s*\$?([\d.]+)", text)
        buyin = float(single_m.group(1)) if single_m else 0.0

    # Prize / cashout
    prize_m = re.search(r"(?:You received|Prize|Won)\s*:?\s*\$?([\d,.]+)", text, re.I)
    cashout = float(prize_m.group(1).replace(",", "")) if prize_m else 0.0

    # Posição — vários formatos GG
    pos_m = re.search(r"You finished\s+(?:the tournament\s+)?(?:in\s+)?(\d+)(?:st|nd|rd|th)", text, re.I)
    if not pos_m:
        pos_m = re.search(r"(\d+)(?:st|nd|rd|th)\s*:\s*Hero", text, re.I)
    position = int(pos_m.group(1)) if pos_m else None

    # Jogadores
    players_m = re.search(r"(\d+)\s+players?", text, re.I)
    players = int(players_m.group(1)) if players_m else None

    tour_type, speed = _classify(name)

    return {
        "site":     "GGPoker",
        "tid":      "",          # GGPoker não expõe tid nos summaries
        "name":     name,
        "date":     tour_date,
        "buyin":    buyin,
        "cashout":  cashout,
        "position": position,
        "players":  players,
        "type":     tour_type,
        "speed":    speed,
        "currency": "$",
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
