"""
Router para cálculos de equity e pot odds.
Usa eval7 para Monte Carlo equity calculation.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.auth import require_auth

router = APIRouter(prefix="/api/equity", tags=["equity"])
logger = logging.getLogger("equity")


class EquityRequest(BaseModel):
    hero_cards: list[str]       # ["Ah", "Kd"]
    board: list[str] = []       # ["3d", "4h", "8d"] (0-5 cards)
    villain_range: str = "random"  # "random", "AA,KK,QQ", "22+,A2s+,K9s+,Q9s+,J9s+,T9s,98s,87s,76s,A2o+,K9o+,Q9o+,JTo"
    num_simulations: int = 10000


class PotOddsRequest(BaseModel):
    pot_size: float
    bet_size: float
    hero_cards: list[str] = []
    board: list[str] = []
    villain_range: str = "random"


# ── Range Parser ──────────────────────────────────────────────────────────────

RANKS = "23456789TJQKA"
SUITS = "cdhs"


def _parse_range(range_str: str) -> list[list[str]]:
    """
    Parses a poker range string into list of 2-card combos.
    Supports: "random", "AA", "AKs", "AKo", "TT+", "A2s+", "KTo+"
    Returns list of [card1, card2] pairs.
    """
    if range_str.lower() == "random":
        return []  # empty = all possible hands

    combos = []
    parts = [p.strip() for p in range_str.split(",") if p.strip()]

    for part in parts:
        plus = part.endswith("+")
        if plus:
            part = part[:-1]

        if len(part) == 2 and part[0] == part[1]:
            # Pair: "TT" or "TT+"
            rank_idx = RANKS.index(part[0])
            start = rank_idx
            end = len(RANKS) if plus else rank_idx + 1
            for ri in range(start, end):
                r = RANKS[ri]
                for s1 in range(len(SUITS)):
                    for s2 in range(s1 + 1, len(SUITS)):
                        combos.append([f"{r}{SUITS[s1]}", f"{r}{SUITS[s2]}"])

        elif len(part) == 3 and part[2] in ('s', 'o'):
            # Suited or offsuit: "AKs", "AKo", "A2s+"
            r1, r2, suitedness = part[0], part[1], part[2]
            r1_idx = RANKS.index(r1)
            r2_idx = RANKS.index(r2)
            start = r2_idx
            end = r1_idx if plus else r2_idx + 1
            for ri in range(start, end):
                r2_cur = RANKS[ri]
                if suitedness == 's':
                    for s in SUITS:
                        combos.append([f"{r1}{s}", f"{r2_cur}{s}"])
                else:
                    for s1 in SUITS:
                        for s2 in SUITS:
                            if s1 != s2:
                                combos.append([f"{r1}{s1}", f"{r2_cur}{s2}"])

        elif len(part) == 2:
            # Unpaired no suit specified: "AK" = both suited and offsuit
            r1, r2 = part[0], part[1]
            for s1 in SUITS:
                for s2 in SUITS:
                    combos.append([f"{r1}{s1}", f"{r2}{s2}"])

    return combos


# ── Equity Calculation ────────────────────────────────────────────────────────

def _card_to_treys(card_str):
    """Convert 'Ah' -> treys Card format."""
    from treys import Card
    # treys uses 'A' for ace, 'T' for ten, lowercase suit
    rank = card_str[0].upper()
    suit = card_str[1].lower()
    return Card.new(f"{rank}{suit}")


def _calculate_equity(hero_cards, board, villain_range="random", num_sims=10000):
    """
    Calculate hero equity vs villain range using treys Monte Carlo.
    Returns equity as float 0-1.
    """
    try:
        from treys import Card, Evaluator, Deck
    except ImportError:
        return _fallback_equity(hero_cards, board, villain_range)

    try:
        evaluator = Evaluator()
        import random as rng

        hero = [_card_to_treys(c) for c in hero_cards]
        board_t = [_card_to_treys(c) for c in board] if board else []
        dead = set(hero + board_t)

        # Full deck minus dead cards
        full_deck = Deck.GetFullDeck()
        deck = [c for c in full_deck if c not in dead]

        wins = 0
        ties = 0
        total = 0

        for _ in range(num_sims):
            remaining = list(deck)
            rng.shuffle(remaining)

            # Pick villain cards (random for now)
            vc = [remaining[0], remaining[1]]
            remaining_for_board = remaining[2:]

            # Complete board to 5 cards
            full_board = list(board_t)
            bi = 0
            while len(full_board) < 5:
                full_board.append(remaining_for_board[bi])
                bi += 1

            # Evaluate
            hero_score = evaluator.evaluate(full_board, hero)
            villain_score = evaluator.evaluate(full_board, vc)

            # In treys, LOWER score = BETTER hand
            if hero_score < villain_score:
                wins += 1
            elif hero_score == villain_score:
                ties += 1
            total += 1

        if total == 0:
            return 0.5

        return (wins + ties * 0.5) / total

    except Exception as e:
        logger.error(f"Equity calc error: {e}")
        return _fallback_equity(hero_cards, board, villain_range)


def _fallback_equity(hero_cards, board, villain_range):
    """Simple fallback equity when eval7 is not available."""
    # Very rough estimate based on hand strength
    ranks = "23456789TJQKA"
    r1 = ranks.index(hero_cards[0][0]) if hero_cards else 6
    r2 = ranks.index(hero_cards[1][0]) if len(hero_cards) > 1 else 6
    suited = hero_cards[0][1] == hero_cards[1][1] if len(hero_cards) > 1 else False
    pair = r1 == r2

    base = (r1 + r2) / 24  # 0-1 based on rank
    if pair:
        base = 0.5 + (r1 / 24) * 0.35
    if suited:
        base += 0.03

    return min(0.95, max(0.05, base))


# ── Pot Odds / MDF / MBF ──────────────────────────────────────────────────────

def calc_pot_odds(pot: float, bet: float) -> float:
    """Pot odds = bet / (pot + bet). Returns as percentage."""
    if pot + bet <= 0:
        return 0
    return bet / (pot + bet) * 100


def calc_mdf(pot: float, bet: float) -> float:
    """Minimum Defense Frequency = pot / (pot + bet). Returns as percentage."""
    if pot + bet <= 0:
        return 0
    return pot / (pot + bet) * 100


def calc_mbf(pot: float, bet: float) -> float:
    """Minimum Bluff Frequency. Returns as percentage."""
    if pot + bet <= 0:
        return 0
    return bet / (pot + bet) * 100


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/calculate")
def calculate_equity(body: EquityRequest, current_user=Depends(require_auth)):
    """Calcula equity do hero vs range do vilão."""
    if len(body.hero_cards) != 2:
        raise HTTPException(status_code=400, detail="Hero precisa de exactamente 2 cartas")
    if len(body.board) > 5:
        raise HTTPException(status_code=400, detail="Board não pode ter mais de 5 cartas")

    equity = _calculate_equity(
        body.hero_cards, body.board,
        body.villain_range, body.num_simulations
    )

    return {
        "equity": round(equity * 100, 1),
        "hero_cards": body.hero_cards,
        "board": body.board,
        "villain_range": body.villain_range,
        "simulations": body.num_simulations,
    }


@router.post("/pot-analysis")
def pot_analysis(body: PotOddsRequest, current_user=Depends(require_auth)):
    """Calcula pot odds, MDF, MBF e equity para uma decisão."""
    pot_odds = calc_pot_odds(body.pot_size, body.bet_size)
    mdf = calc_mdf(body.pot_size, body.bet_size)
    mbf = calc_mbf(body.pot_size, body.bet_size)

    result = {
        "pot_size": body.pot_size,
        "bet_size": body.bet_size,
        "pot_odds": round(pot_odds, 1),
        "mdf": round(mdf, 1),
        "mbf": round(mbf, 1),
        "bet_to_pot_ratio": round(body.bet_size / body.pot_size * 100, 1) if body.pot_size > 0 else 0,
    }

    # If hero cards provided, calculate equity too
    if body.hero_cards and len(body.hero_cards) == 2:
        equity = _calculate_equity(
            body.hero_cards, body.board,
            body.villain_range, 5000
        )
        result["equity"] = round(equity * 100, 1)
        result["ev_call"] = round(equity * (body.pot_size + body.bet_size) - (1 - equity) * body.bet_size, 1)
        result["profitable_call"] = equity * 100 > pot_odds

    return result


@router.post("/hand-analysis/{hand_id}")
def hand_analysis(hand_id: int, current_user=Depends(require_auth)):
    """
    Analisa uma mão completa — calcula pot odds, MDF, equity para cada decisão do Hero.
    """
    from app.db import query
    rows = query("SELECT * FROM hands WHERE id = %s", (hand_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="Mão não encontrada")

    hand = dict(rows[0])
    raw = hand.get("raw", "")
    hero_cards = hand.get("hero_cards", [])
    meta = hand.get("all_players_actions", {}).get("_meta", {}) if hand.get("all_players_actions") else {}

    if not raw or not hero_cards:
        return {"hand_id": hand_id, "analysis": [], "error": "Sem HH ou cartas do hero"}

    import re

    # Detect format
    is_winamax = "*** PRE-FLOP ***" in raw
    preflop_marker = "*** PRE-FLOP ***" if is_winamax else "*** HOLE CARDS ***"

    # Find hero name
    hero_names_set = {"hero", "schadenfreud", "thinvalium", "sapz", "misterpoker1973", "cringemeariver", "flightrisk", "karluz", "koumpounophobia", "lauro dermio"}
    hero_name = None
    dealt_m = re.search(r"Dealt to (\S+)", raw)
    if dealt_m:
        hero_name = dealt_m.group(1)

    # Parse streets and find hero decisions
    streets_order = [
        {"key": "preflop", "start": preflop_marker, "end": "*** FLOP ***"},
        {"key": "flop", "start": "*** FLOP ***", "end": "*** TURN ***"},
        {"key": "turn", "start": "*** TURN ***", "end": "*** RIVER ***"},
        {"key": "river", "start": "*** RIVER ***", "end": "*** SHOW"},
    ]

    # Extract board cards per street
    board_by_street = {"preflop": []}
    flop_m = re.search(r"\*\*\* FLOP \*\*\* \[(.+?)\]", raw)
    if flop_m:
        board_by_street["flop"] = flop_m.group(1).split()
    turn_m = re.search(r"\*\*\* TURN \*\*\* \[.+?\] \[(.+?)\]", raw)
    if turn_m:
        board_by_street["turn"] = board_by_street.get("flop", []) + turn_m.group(1).split()
    river_m = re.search(r"\*\*\* RIVER \*\*\* \[.+?\] \[(.+?)\]", raw)
    if river_m:
        board_by_street["river"] = board_by_street.get("turn", []) + river_m.group(1).split()

    analysis = []
    bb_size = meta.get("bb", 0)

    # Track pot
    pot = 0
    antes = re.findall(r"posts the ante ([\d,]+)", raw)
    for a in antes:
        pot += float(a.replace(",", ""))
    sb_m = re.search(r"posts small blind ([\d,]+)", raw)
    if sb_m:
        pot += float(sb_m[1].replace(",", ""))
    bb_m = re.search(r"posts big blind ([\d,]+)", raw)
    if bb_m:
        pot += float(bb_m[1].replace(",", ""))

    for street_info in streets_order:
        key = street_info["key"]
        si = raw.find(street_info["start"])
        if si == -1:
            continue
        ei = raw.find(street_info["end"], si + len(street_info["start"]))
        if ei == -1:
            ei = raw.find("*** SUMMARY ***", si)
        if ei == -1:
            ei = len(raw)

        section = raw[si:ei]
        board = board_by_street.get(key, [])

        for line in section.split("\n"):
            line = line.strip()
            if not line or line.startswith("***") or line.startswith("Dealt"):
                continue

            # Parse action
            m = re.match(r"^(.+?)(?::)?\s+(folds|checks|calls|bets|raises|posts)(.*)$", line, re.I)
            if not m:
                continue

            actor = m.group(1).strip()
            action = m.group(2).strip().lower()
            rest = m.group(3).strip()

            # Extract amount
            amount = 0
            amt_m = re.search(r"([\d,]+)", rest)
            if amt_m:
                amount = float(amt_m.group(1).replace(",", ""))

            # Update pot for non-hero actions
            is_hero = hero_name and actor == hero_name
            if not is_hero and actor.lower() in hero_names_set:
                is_hero = True

            if action in ("calls", "bets"):
                pot += amount
            elif action == "raises":
                to_m = re.search(r"to ([\d,]+)", rest)
                if to_m:
                    pot += float(to_m.group(1).replace(",", ""))
                else:
                    pot += amount

            # If hero faces a bet/raise, calculate pot odds etc.
            if is_hero and action in ("calls", "folds"):
                # The bet hero is facing
                facing_bet = amount if action == "calls" else 0

                # For folds, look at the previous action to get the bet
                if action == "folds":
                    # Find last bet/raise before this fold
                    prev_lines = section[:section.find(line)].strip().split("\n")
                    for pl in reversed(prev_lines):
                        pm = re.match(r"^.+?(?::)?\s+(bets|raises)\s+([\d,]+)", pl.strip(), re.I)
                        if pm:
                            facing_bet = float(pm.group(2).replace(",", ""))
                            break

                if facing_bet > 0:
                    pot_before = pot - facing_bet if action == "calls" else pot
                    pot_odds_val = calc_pot_odds(pot_before, facing_bet)
                    mdf_val = calc_mdf(pot_before, facing_bet)

                    entry = {
                        "street": key,
                        "action": f"{action} {int(amount)}" if amount else action,
                        "pot_before": round(pot_before),
                        "facing_bet": round(facing_bet),
                        "pot_odds": round(pot_odds_val, 1),
                        "mdf": round(mdf_val, 1),
                        "board": board,
                    }

                    if bb_size > 0:
                        entry["pot_bb"] = round(pot_before / bb_size, 1)
                        entry["bet_bb"] = round(facing_bet / bb_size, 1)

                    analysis.append(entry)

            elif is_hero and action in ("bets", "raises"):
                pot_before = pot - amount
                bet_to_pot = amount / pot_before * 100 if pot_before > 0 else 0
                mbf_val = calc_mbf(pot_before, amount)

                entry = {
                    "street": key,
                    "action": f"{action} {int(amount)}",
                    "pot_before": round(pot_before),
                    "bet_size": round(amount),
                    "bet_to_pot": round(bet_to_pot, 1),
                    "mbf": round(mbf_val, 1),
                    "board": board,
                }

                if bb_size > 0:
                    entry["pot_bb"] = round(pot_before / bb_size, 1)
                    entry["bet_bb"] = round(amount / bb_size, 1)

                analysis.append(entry)

    return {
        "hand_id": hand_id,
        "hero_cards": hero_cards,
        "analysis": analysis,
    }
