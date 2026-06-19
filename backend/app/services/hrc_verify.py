"""pt85 — verificação de correção HH-vs-HRC das mãos resolvidas (#HRC-VERIFY).

Read-only. Abre o `result_zip` do HRC (settings.json / meta.json / equity.json) e
cruza com a HH (`hands.raw` + `all_players_actions`). C1-C5 (v1); C6 (nó da
decisão / target_node_offset vs spot do Hero) fica para v2.

Facto-chave do join: **chips HRC = chips HH × scale**, com `scale` derivado das
blinds (HRC_BB / HH_BB) — tipicamente 100. Tudo normalizado por esse scale.

Veredicto por mão: FAIL (qualquer check estrutural C1/C2/C3/C5 falha → árvore do
spot errado), WARN (C4 alarme de equity model), OK.
"""
from __future__ import annotations

import io
import json
import re
import zipfile

_LEVEL_RE = re.compile(
    r"Level\s*\d+\s*\(\s*([\d,]+)\s*/\s*([\d,]+)\s*(?:\(\s*([\d,]+)\s*\))?",
    re.I,
)
_PKO_FORMATS = {"pko", "super ko", "ko", "superko", "bounty"}


def _num(s) -> float | None:
    try:
        return float(str(s).replace(",", "").strip())
    except (ValueError, TypeError, AttributeError):
        return None


def parse_hh_blinds(raw: str):
    """(sb, bb, ante) das blinds do header da HH; None se não parsear."""
    if not raw:
        return None
    m = _LEVEL_RE.search(raw)
    if not m:
        return None
    sb, bb = _num(m.group(1)), _num(m.group(2))
    ante = _num(m.group(3)) if m.group(3) else 0.0
    if sb is None or bb is None:
        return None
    return (sb, bb, ante)


_SEAT_RE = re.compile(r"Seat\s+\d+:.*?\((\d[\d,]*)", re.I)
_BB_FALLBACK_RE = re.compile(r"posts?\s+big\s+blind\s+([\d,]+)", re.I)


def _hh_seat_stacks(raw: str) -> list[float]:
    """Stacks (chips) dos Seat lines do `raw` — AUTORITÁRIO (GG '(X in chips)' e
    WN '(X, Y€ bounty)'). Mais fiável que all_players_actions (que pode faltar
    seats não-desanonimizados em GG table-SS)."""
    if not raw:
        return []
    return [v for v in (_num(x) for x in _SEAT_RE.findall(raw)) if v is not None]


def _hh_player_stacks(all_players_actions) -> list[float]:
    """Fallback: stacks de all_players_actions (exclui `_meta`)."""
    out = []
    if isinstance(all_players_actions, dict):
        for k, v in all_players_actions.items():
            if k == "_meta" or not isinstance(v, dict):
                continue
            s = _num(v.get("stack"))
            if s is not None:
                out.append(s)
    return out


def _hh_bb(raw: str, hh_blinds):
    """BB da HH: do level (GG) ou do 'posts big blind' (WN/PS)."""
    if hh_blinds:
        return hh_blinds[1]
    m = _BB_FALLBACK_RE.search(raw or "")
    return _num(m.group(1)) if m else None


def _derive_scale(hrc_blinds, hh_bb, hrc_stacks, hh_stacks):
    """chips HRC = chips HH × scale. Das blinds (HRC_BB/HH_BB) se houver; senão do
    rácio dos maiores stacks, snapped a uma potência limpa (1/100/1000)."""
    if hrc_blinds and hh_bb:
        return hrc_blinds[0] / hh_bb
    if hrc_stacks and hh_stacks:
        ratio = max(hrc_stacks) / max(hh_stacks)
        for cand in (1.0, 100.0, 1000.0):
            if abs(ratio - cand) <= cand * 0.05:
                return cand
    return None


def _read_json(zf, suffix):
    for n in zf.namelist():
        if n.endswith(suffix):
            try:
                return json.loads(zf.read(n))
            except (ValueError, KeyError):
                return None
    return None


def _chk(key, ok, detail):
    return {"check": key, "status": ("ok" if ok else "fail"), "detail": detail}


def verify_hand(hand: dict, zip_bytes: bytes) -> dict:
    """Corre C1-C5 sobre uma mão resolvida. `hand`: row de `hands` (raw,
    all_players_actions, tournament_format). `zip_bytes`: result_zip do HRC."""
    hand_id = hand.get("hand_id")
    checks, notes = [], []
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile:
        return {"hand_id": hand_id, "verdict": "fail",
                "checks": [_chk("zip", False, "result_zip inválido")]}

    settings = _read_json(zf, "settings.json") or {}
    meta = _read_json(zf, "meta.json") or {}
    equity = _read_json(zf, "equity.json") or {}
    hd = settings.get("handdata") or {}
    hrc_stacks = [s for s in (hd.get("stacks") or []) if isinstance(s, (int, float))]
    hrc_blinds = [b for b in (hd.get("blinds") or []) if isinstance(b, (int, float))]

    raw = hand.get("raw") or ""
    hh_blinds = parse_hh_blinds(raw)
    hh_stacks = _hh_seat_stacks(raw) or _hh_player_stacks(hand.get("all_players_actions"))
    hh_bb = _hh_bb(raw, hh_blinds)
    scale = _derive_scale(hrc_blinds, hh_bb, hrc_stacks, hh_stacks)

    # C3 — blinds + ante (proporcionais ao scale; SB/ante coerentes com BB)
    if hh_blinds and len(hrc_blinds) >= 2 and scale:
        sb, bb, ante = hh_blinds
        bb_ok = abs(hrc_blinds[0] / scale - bb) <= max(1.0, bb * 0.001)
        sb_ok = abs(hrc_blinds[1] / scale - sb) <= max(1.0, sb * 0.001)
        ante_ok = (len(hrc_blinds) < 3) or (abs(hrc_blinds[2] / scale - ante) <= max(1.0, (ante or 1) * 0.01))
        checks.append(_chk("C3_blinds", bb_ok and sb_ok and ante_ok,
                           f"HH(sb={sb:.0f},bb={bb:.0f},ante={ante:.0f}) vs HRC/{scale:.0f}={[round(b/scale) for b in hrc_blinds]}"))
    else:
        checks.append(_chk("C3_blinds", True, "sem blinds parseáveis — skip (não-fatal)"))
        notes.append("blinds não comparáveis")

    # C1 — player count (HRC tree vs max_players pedido / nº reais na HH)
    hrc_n = len(hrc_stacks)
    mp = meta.get("max_players")
    if mp is not None:
        checks.append(_chk("C1_players", hrc_n == mp,
                           f"HRC stacks={hrc_n} vs meta.max_players={mp}"))
    else:
        ok = (0 < hrc_n <= len(hh_stacks)) if hh_stacks else (hrc_n > 0)
        checks.append(_chk("C1_players", ok, f"HRC stacks={hrc_n} (HH reais={len(hh_stacks)}; sem meta.max_players)"))

    # C2 — stacks: cada stack HRC/scale tem de bater com um stack da HH (tol)
    if hrc_stacks and hh_stacks and scale:
        pool = list(hh_stacks)
        unmatched = []
        for hs in hrc_stacks:
            target = hs / scale
            hit = next((p for p in pool if abs(p - target) <= max(1.0, target * 0.02)), None)
            if hit is None:
                unmatched.append(round(target))
            else:
                pool.remove(hit)
        checks.append(_chk("C2_stacks", not unmatched,
                           f"{len(hrc_stacks)} stacks HRC/{scale:.0f}; sem-match na HH: {unmatched or 'nenhum'}"))
    else:
        checks.append(_chk("C2_stacks", True, "stacks não comparáveis — skip"))
        notes.append("stacks não comparáveis")

    # C4 — equity model vs players_left (FT ⇔ players_left ≤ jogadores na mesa)
    em = meta.get("equity_model")
    pl = meta.get("players_left")
    if em and pl is not None and hrc_n:
        is_ft_model = (em == "malmuth_harville_icm")
        looks_ft = (pl <= hrc_n)
        warn = (is_ft_model and not looks_ft) or ((not is_ft_model) and looks_ft)
        checks.append({"check": "C4_equity", "status": ("warn" if warn else "ok"),
                       "detail": f"model={em} players_left={pl} seats={hrc_n}"})
    else:
        checks.append({"check": "C4_equity", "status": "ok", "detail": "sem dados — skip"})

    # C5 — bounty presente em PKO (handdata.bounties[] não-vazio e algum > 0)
    fmt = (hand.get("tournament_format") or "").strip().lower()
    if fmt in _PKO_FORMATS:
        bounties = [b for b in (hd.get("bounties") or []) if isinstance(b, (int, float))]
        avg = (settings.get("eqmodel") or {}).get("otheravgbounty")
        has_b = (bool(bounties) and any(b > 0 for b in bounties)) or (isinstance(avg, (int, float)) and avg > 0)
        checks.append(_chk("C5_bounty", has_b,
                           f"format={fmt} bounties={bounties[:3]}{'…' if len(bounties)>3 else ''} avg={avg}"))
    else:
        checks.append(_chk("C5_bounty", True, f"format={fmt or '—'} (não-PKO; skip)"))

    statuses = [c["status"] for c in checks]
    verdict = "fail" if "fail" in statuses else ("warn" if "warn" in statuses else "ok")
    return {"hand_id": hand_id, "verdict": verdict, "scale": scale,
            "checks": checks, "notes": notes}
