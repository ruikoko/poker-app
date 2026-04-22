"""Central list of hero aliases and friend group — single source of truth.

HERO_NAMES   → user's own accounts across all poker sites.
               Used to mark the hero seat in HH parsing, screenshots,
               MTT processing and equity calculations.

FRIEND_NICKS → hero + team/friend accounts that should be EXCLUDED
               from the villain database (routers/villains.py,
               routers/mtt.py friend filter, etc.).

Matching is always case-insensitive. Values are stored lowercase.
When a nickname appears in different forms on different sites
(ex. "freeolivença" vs "freeoliven&ccedil;a"), both variants are
listed so all formats match.
"""

HERO_NAMES: set[str] = {
    # Generic marker used by anonymised HH
    "hero",

    # Lobbarize account list (April 2026)
    "thinvalium",
    "lauro dermio",
    "lauro derm",          # truncated form seen in some screenshots
    "schadenfreud",
    "kabalaharris",
    "ruing",               # 888 account
    "misterpoker1973",
    "gajodopao",
    "koumpounophobia",
    "cringemeariver",
    "cr7dagreta",
    "rail iota",
    "queleiteon",
    "trapatonigpt",
    "dapanal",
    "dapanal?",            # literal ? as it appears on some sites
    "narsa114",
    "patodesisto",
    "nuncabatman",
    "proctocolectomy",
    "pelosinthenancy",
    "pelosintenancy",      # alternate spelling on another site
    "pelosithenancy",      # variant seen in legacy data
    "pagachorari",
    "sticklapisse",
    "autoswiperight",
    "paidaskengas",
    "freeolivença",
    "freeoliven&ccedil;a", # HTML-encoded variant
    "robyoungbff",
    "pokerfan1967",
    "kokonakueka",
    "cunetejaune",
    "leportugay8",
    "cr7dapussy",
    "ederbutdor",
    "opaidasputas",
    "hollywoodpimp",
    "aturatu",
    "opaidelas",
    "covfef3",
    "iuse2bspewer",
}

# Friend / team group nicks — NOT hero, but also NOT villains.
# Used to filter these players out of the villain profile database.
_FRIEND_ONLY_NICKS: set[str] = {
    "1otario", "a lagardere", "abutrinzi", "algorhythm",
    "amazeswhores", "arr0zdepat0", "avecamos", "beijamyrola",
    "cattleking", "cavalitos", "cmaculatum", "coconacueca",
    "crashcow", "decode", "deusfumo", "djobidjoba87",
    "dlncredible", "eitaqdelicia", "el kingzaur", "etonelespute",
    "flightrisk", "floptwist", "godsmoke", "golimar666",
    "grenouille", "grenouiile", "hmhm", "huntermilf",
    "i<3kebab", "ipaysor", "jackpito", "joao barbosa",
    "johngeologic", "karluz", "klklwoku", "lendiadbisca",
    "lewinsky", "ltbau", "luckytobme", "luckytobvsu",
    "milffinder", "milfodds", "mmaboss", "mrpeco",
    "mrpecoo", "neurose", "obviamente.", "ohum",
    "pec0", "priest lucy", "quimterro", "quimtrega",
    "rapinzi", "rapinzi12", "rapinzi1988", "rapinzigg",
    "rosanorte", "ryandays", "sapinzi", "sapz",
    "shaamp00", "shrug", "takiozaur", "thanatos",
    "toniextractor", "tonixtractor", "tonixtractor2",
    "traumatizer", "vanaldinho", "vascodagamba",
    "vtmizer", "zen17", "zen1to",
    # Hash-based nick seen on Winamax.fr
    "c78d63886ce0850aa6e75c3b58d63b",
    # Historical aliases preserved from legacy FRIEND_NICKS
    "andacasa", "jeandouca",
}

# FRIEND_NICKS = all hero accounts + friend-only accounts
FRIEND_NICKS: set[str] = HERO_NAMES | _FRIEND_ONLY_NICKS


# ── Distribuição por sala (site-detection) ──────────────────────────────────
# Usado pelo fallback do parser HM3 quando o site_id vem errado na BD HM3.
# Lowercased para matching case-insensitive.

HERO_NICKS_BY_SITE: dict[str, list[str]] = {
    "PokerStars": ["kokonakueka", "misterpoker1973"],
    "Winamax":    ["thinvalium"],
    "WPN":        ["cringemeariver"],
    "GGPoker":    ["lauro dermio", "koumpounophobia"],
}

FRIEND_NICKS_BY_SITE: dict[str, list[str]] = {
    "GGPoker": ["karluz", "flightrisk"],
}

# Nicks combinados por sala (hero + amigos)
ALL_NICKS_BY_SITE: dict[str, list[str]] = {
    site: HERO_NICKS_BY_SITE.get(site, []) + FRIEND_NICKS_BY_SITE.get(site, [])
    for site in set(HERO_NICKS_BY_SITE) | set(FRIEND_NICKS_BY_SITE)
}


def is_hero(name: str | None) -> bool:
    """Case-insensitive hero check. Returns False for None/empty."""
    if not name:
        return False
    return name.lower().strip() in HERO_NAMES


def is_friend(name: str | None) -> bool:
    """Case-insensitive friend check (includes hero). Returns False for None/empty."""
    if not name:
        return False
    return name.lower().strip() in FRIEND_NICKS


def is_friend_prefix(name: str | None) -> bool:
    """Case-insensitive friend check with starts-with support.

    Useful for truncated nicks returned by some sites (ex: "thinvali" for "thinvalium").
    """
    if not name:
        return False
    n = name.lower().strip()
    if n in FRIEND_NICKS:
        return True
    return any(f.startswith(n) or n.startswith(f) for f in FRIEND_NICKS if len(f) >= 4)


def detect_site_from_hh(raw_hh: str | None) -> str | None:
    """Varre 'Seat N: <nick>' no raw e retorna a sala cujos nicks batem.

    Prioridade: sala com mais matches. Empate → None (evita adivinhação).
    Sem matches → None.
    Case-insensitive.
    """
    import re
    if not raw_hh:
        return None
    seat_names = [
        m.group(1).lower().strip()
        for m in re.finditer(r"Seat\s+\d+:\s*(.+?)\s*\(", raw_hh)
    ]
    if not seat_names:
        return None
    score: dict[str, int] = {}
    for site, nicks in ALL_NICKS_BY_SITE.items():
        lowered = {n.lower() for n in nicks}
        score[site] = sum(1 for n in seat_names if n in lowered)
    if not score:
        return None
    best_score = max(score.values())
    if best_score == 0:
        return None
    top_sites = [s for s, sc in score.items() if sc == best_score]
    if len(top_sites) > 1:
        return None
    return top_sites[0]
