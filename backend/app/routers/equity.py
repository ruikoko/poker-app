"""
Router para cálculos de equity e pot odds.
Usa eval7 para Monte Carlo equity calculation.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.auth import require_auth
from app.hero_names import HERO_NAMES

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


# ── Equity Calculation (pyeval7) ─────────────────────────────────────────────

def _calculate_equity(hero_cards, board, villain_range="random", num_sims=10000):
    """
    Calculate hero equity vs villain range using pyeval7 Monte Carlo.
    ~50ms for 10k sims. Supports specific ranges like "TT+,AKs,AKo".
    Returns equity as float 0-1.
    """
    try:
        import eval7
    except ImportError:
        logger.warning("pyeval7 not installed, trying treys fallback")
        return _calculate_equity_treys(hero_cards, board, villain_range, num_sims)

    try:
        import random as rng

        # Auto-detect eval7 score direction:
        # Compare AA vs 72 on a fixed board - AA must win
        _aa = [eval7.Card('As'), eval7.Card('Ad')]
        _72 = [eval7.Card('7c'), eval7.Card('2h')]
        _test_board = [eval7.Card('3d'), eval7.Card('8h'), eval7.Card('Ks'), eval7.Card('4c'), eval7.Card('9s')]
        _aa_score = eval7.evaluate(_aa + _test_board)
        _72_score = eval7.evaluate(_72 + _test_board)
        logger.info(f"eval7 calibration: AA_score={_aa_score}, 72_score={_72_score}")
        # If AA score < 72 score, then lower is better
        higher_is_better = _aa_score > _72_score
        logger.info(f"eval7 higher_is_better={higher_is_better}")

        # All work done with strings, only convert to eval7.Card for evaluation
        dead = set(hero_cards + (board or []))

        # Full deck as strings minus dead
        all_cards = [f"{r}{su}" for r in "23456789TJQKA" for su in "cdhs"]
        deck = [c for c in all_cards if c not in dead]

        # Parse villain range
        range_combos = _parse_range(villain_range)

        # Filter combos that use dead cards
        if range_combos:
            valid_combos = []
            for combo in range_combos:
                c1, c2 = combo[0], combo[1]
                if c1 not in dead and c2 not in dead and c1 != c2:
                    valid_combos.append((c1, c2))
            if not valid_combos:
                return 0.5
        else:
            valid_combos = None

        wins = 0
        ties = 0
        total = 0
        board_strs = list(board or [])
        cards_needed = 5 - len(board_strs)

        for _ in range(num_sims):
            if valid_combos:
                vc1, vc2 = rng.choice(valid_combos)
                remaining = [c for c in deck if c != vc1 and c != vc2]
            else:
                deck_copy = list(deck)
                rng.shuffle(deck_copy)
                vc1, vc2 = deck_copy[0], deck_copy[1]
                remaining = deck_copy[2:]

            # Complete board to 5 cards
            rng.shuffle(remaining)
            full_board_strs = board_strs + remaining[:cards_needed]

            # Convert to eval7 cards and evaluate
            try:
                hero_hand = [eval7.Card(c) for c in hero_cards + full_board_strs]
                villain_hand = [eval7.Card(c) for c in [vc1, vc2] + full_board_strs]

                hero_score = eval7.evaluate(hero_hand)
                villain_score = eval7.evaluate(villain_hand)

                if higher_is_better:
                    if hero_score > villain_score:
                        wins += 1
                    elif hero_score == villain_score:
                        ties += 1
                else:
                    if hero_score < villain_score:
                        wins += 1
                    elif hero_score == villain_score:
                        ties += 1
                total += 1
            except Exception:
                continue

        if total == 0:
            return 0.5

        return (wins + ties * 0.5) / total

    except Exception as e:
        logger.error(f"pyeval7 equity calc error: {e}")
        return _calculate_equity_treys(hero_cards, board, villain_range, num_sims)


def _calculate_equity_treys(hero_cards, board, villain_range="random", num_sims=10000):
    """Fallback: Calculate equity using treys. Supports ranges."""
    try:
        from treys import Card, Evaluator, Deck
    except ImportError:
        return _fallback_equity(hero_cards, board, villain_range)

    def _card_to_treys(card_str):
        return Card.new(f"{card_str[0].upper()}{card_str[1].lower()}")

    try:
        evaluator = Evaluator()
        import random as rng

        hero = [_card_to_treys(c) for c in hero_cards]
        board_t = [_card_to_treys(c) for c in board] if board else []
        dead_strs = set(hero_cards + (board or []))

        # Build deck as strings, excluding dead cards
        all_card_strs = [f"{r}{su}" for r in "23456789TJQKA" for su in "cdhs"]
        deck_strs = [c for c in all_card_strs if c not in dead_strs]

        # Parse villain range
        range_combos = _parse_range(villain_range)

        if range_combos:
            valid_combos = []
            for combo in range_combos:
                c1, c2 = combo[0], combo[1]
                if c1 not in dead_strs and c2 not in dead_strs and c1 != c2:
                    valid_combos.append((c1, c2))
            if not valid_combos:
                return 0.5
        else:
            valid_combos = None

        wins = 0
        ties = 0
        total = 0
        cards_needed = 5 - len(board_t)

        for _ in range(num_sims):
            if valid_combos:
                vc1_str, vc2_str = rng.choice(valid_combos)
                remaining = [c for c in deck_strs if c != vc1_str and c != vc2_str]
                vc = [_card_to_treys(vc1_str), _card_to_treys(vc2_str)]
            else:
                deck_copy = list(deck_strs)
                rng.shuffle(deck_copy)
                vc1_str, vc2_str = deck_copy[0], deck_copy[1]
                remaining = deck_copy[2:]
                vc = [_card_to_treys(vc1_str), _card_to_treys(vc2_str)]

            # Complete board
            rng.shuffle(remaining)
            full_board = list(board_t)
            for bi in range(cards_needed):
                full_board.append(_card_to_treys(remaining[bi]))

            # In treys, LOWER score = BETTER hand
            hero_score = evaluator.evaluate(full_board, hero)
            villain_score = evaluator.evaluate(full_board, vc)

            if hero_score < villain_score:
                wins += 1
            elif hero_score == villain_score:
                ties += 1
            total += 1

        if total == 0:
            return 0.5

        return (wins + ties * 0.5) / total

    except Exception as e:
        logger.error(f"treys equity calc error: {e}")
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
            if not is_hero and actor.lower() in HERO_NAMES:
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
