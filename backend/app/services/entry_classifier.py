import re
from typing import Optional


def _detect_site(file_name: str, content: str) -> Optional[str]:
    name = (file_name or "").lower()
    text = (content or "")[:5000].lower()

    if "winamax" in name or "winamax" in text:
        return "Winamax"

    if "gg" in name or "ggpoker" in text or "poker hand #" in text:
        return "GGPoker"

    if "pokerstars" in name or "pokerstars" in text:
        return "PokerStars"

    if "wpn" in name or "americas cardroom" in text or "black chip" in text:
        return "WPN"

    return None


def _extract_external_id(file_name: str, content: str, site: Optional[str]) -> Optional[str]:
    text = content or ""

    if site == "GGPoker":
        m = re.search(r"Poker Hand #(\\d+)", text)
        if m:
            return m.group(1)

        m = re.search(r"Tournament #(\\d+)", text)
        if m:
            return m.group(1)

    if site == "Winamax":
        m = re.search(r"Tournament(?:\\s+ID)?[:#]?\\s*(\\d+)", text, re.IGNORECASE)
        if m:
            return m.group(1)

    if site == "PokerStars":
        m = re.search(r"\\bTournament\\s+(\\d+)\\b", text, re.IGNORECASE)
        if m:
            return m.group(1)

        m = re.search(r"^(\\d+)\\t", text)
        if m:
            return m.group(1)

    return None


def classify_entry(file_name: str, content: str) -> dict:
    text = content or ""
    stripped = text.strip()
    lines = [ln.strip() for ln in stripped.splitlines() if ln.strip()]
    head = "\\n".join(lines[:20]).lower()
    site = _detect_site(file_name, text)

    if stripped.startswith("Poker Hand #"):
        return {
            "source": "hh_text",
            "entry_type": "hand_history",
            "site": site or "GGPoker",
            "external_id": _extract_external_id(file_name, text, site or "GGPoker"),
            "confidence_level": "high",
        }

    tabular_markers = ["id\\t", "data\\t", "rede\\t", "nome\\t", "stake\\t"]
    if any(marker in head for marker in tabular_markers):
        return {
            "source": "report",
            "entry_type": "tabular_report",
            "site": site,
            "external_id": _extract_external_id(file_name, text, site),
            "confidence_level": "high",
        }

    summary_markers = [
        "buy-in",
        "prize",
        "position",
        "finished",
        "tournament summary",
        "summary",
    ]
    if any(marker in head for marker in summary_markers):
        return {
            "source": "summary",
            "entry_type": "tournament_summary",
            "site": site,
            "external_id": _extract_external_id(file_name, text, site),
            "confidence_level": "medium",
        }

    return {
        "source": "manual",
        "entry_type": "text",
        "site": site,
        "external_id": _extract_external_id(file_name, text, site),
        "confidence_level": "low",
    }
