"""
IRE v2 (Indice de Reducao de Equity / Bounty Power) — GG-only.

#IRE-MB (2026-05-29): a constante do bounty é DERIVADA por torneio
(KOP_fraction × instant_fraction), já não é fixa em 25%. Default 0.25 =
PKO standard 50/50. Ver `derive_constant`.

Lookup numa tabela hardcoded W3cray (SI/KO_inicial = 4 = constante 0.25) com
nearest-neighbour clamp e fallback formula quando a celula = None ou
(stack_si, ko_units) cai fora da tabela. Decisão (a) do #IRE-MB: a tabela só é
valida para a constante 0.25 (banda ±0.01); outras constantes usam a formula.

Filtros de activacao (qualquer falha => return None, IRE escondido):
    - hand.site == 'GGPoker'
    - match_method real (nao discord_placeholder_*)
    - tag *ko* em hm3_tags ou discord_tags (case-insens)
    - tournament_format in {'PKO', 'Mystery KO'}
    - tournaments_meta com starting_stack > 0
    - tournament_name NAO contem 'Super KO' (= ratio 40%). MANTIDO escondido
      mesmo com a constante derivavel (decisao b, #IRE-MB T4): falta validacao
      empirica da instant_fraction do Super KO (so 50/50 e 70/30 confirmados).
    - tournament_meta com buy_in_bounty > 0 (base de ko_units = bounty/bounty_inicial)
    - >= 1 oponente (non-hero) com bounty REAL > 0 (coroa, bounty_value_usd)

Output (quando aplicavel):
    {
      "main_villain": {nick, position, stack_chips, stack_bb, stack_si,
                       ko_pct, ko_units, ire_pct, is_covered},
      "per_opponent": [
        {nick, position, stack_chips, stack_bb, stack_si, ko_pct, ko_units,
         ire_pct, is_main, is_active, is_covered},
        ...   # ordenado por SEAT_ORDER (UTG -> BTN -> SB -> BB)
      ],
    }

per_opponent inclui foldados (com is_active=False, ire_pct calculado se
ko_pct>0). Hero excluido.
"""
from __future__ import annotations
import json
import logging
import re
from typing import Optional

# Reuso do regex dos 3 componentes do header PS (anti-drift com o classificador).
from app.utils.tournament_format import _PS_3COMP_AMOUNTS_RE

logger = logging.getLogger(__name__)


ALLOWED_FORMATS = {"PKO", "Mystery KO"}
KO_TAG_NEEDLE = "ko"
# Família Speed Racer (GG hyper PKO) — a tag NÃO contém "ko", por isso é
# reconhecida explicitamente como tag de estudo PKO (apanha 'speed-racer' e
# 'speed-racer-ft' via normalização hyphen→espaço).
SPEED_RACER_NEEDLE = "speed racer"
SUPER_KO_NEEDLE = "super ko"

# #IRE-MB — a constante do bounty (bounty_si = ko_units × constante) decompõe-se
# em KOP_fraction × instant_fraction. 0.25 = PKO standard 50/50 (0.5 × 0.5).
# Decisão (a): a tabela W3cray só é válida para 0.25; outras constantes usam a
# fórmula pura. O default mantém o comportamento legacy byte-a-byte.
_DEFAULT_CONSTANT = 0.25
# Banda de "standard" à volta de 0.25: absorve o ruído do rake no split GG
# (50/50 real ~0.247) -> usa a tabela W3cray calibrada. Formatos genuinamente
# diferentes (Big Bounty 0.35, Super KO 0.40) caem fora -> fórmula (decisão α).
_TABLE_CONSTANT_BAND = 0.01
# instant_fraction: parte do bounty ganha em CASH imediato ao eliminar. Confirmada
# empiricamente = 0.5 no PKO standard E no Big Bounty HR do GG (#IRE-MB ponto 6,
# 2026-05-29). ⚠️ NÃO confundir com o progressiveFactor do HRC / lobby_vision.py
# — são convenções distintas. Const nomeada para futura parametrização (Mystery).
_INSTANT_FRACTION = 0.5
_STREETS = ("preflop", "flop", "turn", "river")

# Ordem visual da mesa (mesma de HandDetailPage.jsx).
_SEAT_ORDER = ["UTG", "UTG1", "UTG+1", "UTG2", "UTG+2", "MP", "MP1", "MP+1",
               "HJ", "CO", "BTN", "SB", "BB"]


# ── Tabela W3cray (ratio 25%) ────────────────────────────────────────────────
# Validada via Mathematics.xlsx sheet "IRE". Linhas = stack_op em SI;
# colunas = ko_op em KO_inicial. Valores em % (None = celula vazia).

W3CRAY_TABLE_25PCT = {
    "rows_si": [0.25, 0.33, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0],
    "cols_ko": [1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5],
    "values_pct": {
        0.25: [13.0, None, None, None, None, None, None, None, None],
        0.33: [11.8, None, None, None, None, None, None, None, None],
        0.5:  [8.8, 11.8, 13.0, None, None, None, None, None, None],
        0.75: [6.5, 8.8, 9.5, 12.1, 13.0, None, None, None, None],
        1.0:  [5.1, 7.1, 8.8, 10.4, 11.8, 12.5, 13.0, None, None],
        1.5:  [3.9, 5.1, 6.5, 7.8, 8.8, 10.0, 10.8, None, None],
        2.0:  [2.6, 4.2, 5.1, 6.4, 7.1, 8.1, 8.8, None, None],
        2.5:  [2.0, 3.5, 4.3, 5.1, 6.0, 6.8, 7.8, None, None],
        3.0:  [1.7, 2.6, 3.7, 4.4, 5.1, 5.9, 6.5, None, None],
        3.5:  [1.4, 2.1, 3.0, 3.9, 4.6, 5.1, 5.7, None, None],
        4.0:  [1.2, 1.8, 2.6, 3.6, 4.2, 4.5, 5.1, None, None],
        4.5:  [0.9, 1.7, 2.5, 3.0, 3.7, 4.2, 4.6, 5.1, None],
        5.0:  [0.8, 1.5, 2.0, 2.6, 3.5, 3.9, 4.3, None, 5.1],
        5.5:  [0.7, 1.3, 1.8, 2.5, 3.0, 3.6, 4.0, None, None],
        6.0:  [0.5, 1.2, 1.6, 2.0, 2.6, 3.2, 3.7, None, None],
        6.5:  [0.4, 1.0, 1.5, 1.8, 2.5, 2.8, 3.5, None, None],
        7.0:  [0.2, 0.8, 1.4, 1.7, 2.2, 2.6, 3.2, None, None],
    },
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _has_ko_tag(hm3_tags, discord_tags) -> bool:
    """True se alguma tag (HM3 ou Discord) é tag de estudo PKO: contém "ko"
    (apanha pko/icm-pko/ko/...) OU é da família speed-racer (GG hyper PKO,
    cuja tag não tem "ko"). Normaliza hyphen→espaço."""
    for tag in list(hm3_tags or []) + list(discord_tags or []):
        if not tag:
            continue
        norm = tag.replace("-", " ").lower()
        if KO_TAG_NEEDLE in norm or SPEED_RACER_NEEDLE in norm:
            return True
    return False


def _coerce_apa(apa) -> Optional[dict]:
    if isinstance(apa, str):
        try:
            apa = json.loads(apa)
        except (ValueError, TypeError):
            return None
    return apa if isinstance(apa, dict) else None


def _coerce_pn(pn) -> dict:
    if isinstance(pn, str):
        try:
            pn = json.loads(pn)
        except (ValueError, TypeError):
            return {}
    return pn if isinstance(pn, dict) else {}


def _coerce_float(v) -> float:
    """bounty_value_usd vem como float/int/TEXT/None. Coerce robusta."""
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    try:
        m = re.search(r"\d+(?:\.\d+)?", str(v))
        return float(m.group(0)) if m else 0.0
    except (ValueError, TypeError):
        return 0.0


def _is_active(actions: Optional[dict]) -> bool:
    """Activo = nao tem 'Fold' em nenhuma das suas accoes em qualquer rua.
    Sem accoes (sit-out / dealt-fold) = inactivo."""
    if not actions:
        return False
    has_any = False
    for street in _STREETS:
        for a in actions.get(street, []) or []:
            if not isinstance(a, str):
                continue
            has_any = True
            if a.startswith("Fold"):
                return False
    return has_any


def _seat_order_key(position: Optional[str]) -> int:
    if not position:
        return 99
    try:
        return _SEAT_ORDER.index(position)
    except ValueError:
        return 99


# ── Lookup ───────────────────────────────────────────────────────────────────

def _nearest_idx(value: float, axis: list) -> int:
    if value <= axis[0]:
        return 0
    if value >= axis[-1]:
        return len(axis) - 1
    return min(range(len(axis)), key=lambda i: abs(axis[i] - value))


def _formula_fallback(stack_si: float, ko_units: float,
                      constant: float = _DEFAULT_CONSTANT) -> Optional[float]:
    """IRE_pct = bounty_si / (4*stack_si + 2*bounty_si) * 100, com bounty_si
    = ko_units * `constant` (= KOP_fraction × instant_fraction expresso em SI).
    `constant` default 0.25 = PKO standard 50/50."""
    if ko_units <= 0 or stack_si <= 0:
        return None
    bounty_si = ko_units * constant
    denom = 4.0 * stack_si + 2.0 * bounty_si
    if denom <= 0:
        return None
    return (bounty_si / denom) * 100.0


def lookup_ire_pct(stack_si: float, ko_units: float,
                   constant: float = _DEFAULT_CONSTANT) -> Optional[float]:
    """Devolve IRE % para (stack_op_em_SI, ko_op_em_KO_inicial).
    `constant` = KOP_fraction × instant_fraction. Para `constant == 0.25`
    (PKO standard) usa a tabela W3cray calibrada; para qualquer outra constante
    (decisão (a) do #IRE-MB) usa a fórmula pura — a tabela não é válida fora de
    0.25. None quando ko_units<=0 ou stack invalido."""
    if ko_units <= 0 or stack_si <= 0:
        return None
    if abs(constant - _DEFAULT_CONSTANT) > _TABLE_CONSTANT_BAND:
        return _formula_fallback(stack_si, ko_units, constant)
    rows = W3CRAY_TABLE_25PCT["rows_si"]
    cols = W3CRAY_TABLE_25PCT["cols_ko"]
    y_idx = _nearest_idx(stack_si, rows)
    x_idx = _nearest_idx(ko_units, cols)
    cell = W3CRAY_TABLE_25PCT["values_pct"][rows[y_idx]][x_idx]
    if cell is not None:
        return float(cell)
    return _formula_fallback(stack_si, ko_units, constant)


# ── Derivação da constante por torneio (#IRE-MB) ─────────────────────────────

def _kop_from_parts(entry, bounty) -> Optional[float]:
    """GG: KOP_fraction = bounty / (entry + bounty). Rake NÃO entra no
    denominador (fracção líquida). None se inputs inválidos ou bounty<=0."""
    try:
        e = float(entry) if entry is not None else None
        b = float(bounty) if bounty is not None else None
    except (TypeError, ValueError):
        return None
    if b is None or b <= 0 or e is None or e < 0:
        return None
    net = e + b
    if net <= 0:
        return None
    return b / net


def _kop_from_ps_header(raw_hh: Optional[str]) -> Optional[float]:
    """PS: 3 componentes no header `$A+$B+$C`. ORDEM PS = [A=PP, B=KOP, C=rake]
    (≠ GG TS [PP, rake, KOP]). KOP_fraction = B / (A + B). None se não parseável."""
    if not raw_hh:
        return None
    header = raw_hh[:2000]
    m = _PS_3COMP_AMOUNTS_RE.search(header)
    if not m:
        return None
    try:
        a = float(m.group(1))   # PP
        b = float(m.group(2))   # KOP
    except (ValueError, IndexError):
        return None
    net = a + b
    if b <= 0 or net <= 0:
        return None
    return b / net


def derive_kop_fraction(
    site: Optional[str],
    *,
    buy_in_entry=None,
    buy_in_bounty=None,
    raw_hh: Optional[str] = None,
) -> Optional[float]:
    """Fracção líquida do buy-in que vai para o bounty pool (KOP), por sala.
    None => caller usa o default 0.25 (degradação graciosa).

    - GG:          de tournament_summaries (buy_in_entry/buy_in_bounty).
    - Winamax/WPN: None (constante fixa 0.25 — só PKO 50/50 progressive).
    - PS:          dos 3 componentes do header do raw_hh.
    """
    s = (site or "").lower()
    if s == "ggpoker":
        return _kop_from_parts(buy_in_entry, buy_in_bounty)
    if s in ("winamax", "wpn"):
        return None
    if s == "pokerstars":
        return _kop_from_ps_header(raw_hh)
    return None


def derive_constant(
    site: Optional[str],
    *,
    buy_in_entry=None,
    buy_in_bounty=None,
    raw_hh: Optional[str] = None,
) -> float:
    """Constante do bounty = KOP_fraction × instant_fraction. Quando o
    KOP_fraction não é derivável (None) devolve o default 0.25 (comportamento
    legacy). Ex.: GG Big Bounty 30/70 → 0.70 × 0.5 = 0.35."""
    kop = derive_kop_fraction(
        site, buy_in_entry=buy_in_entry, buy_in_bounty=buy_in_bounty, raw_hh=raw_hh
    )
    if kop is None:
        return _DEFAULT_CONSTANT
    return kop * _INSTANT_FRACTION


# ── Vilao principal (regra D) ────────────────────────────────────────────────

def _pick_main_villain(per_opponent: list, hero_stack_chips: float) -> Optional[dict]:
    """Headline da lista (regra D). 1→N: o IRE é calculado por-oponente; isto só
    escolhe o oponente a destacar no badge da lista. Prefere ACTIVOS com bounty;
    se nenhum activo, faz fallback ao oponente com coroa de maior `ire_pct`
    (foldados incluídos). `None` só se nenhum oponente tem `ko_units>0`."""
    activos = [op for op in per_opponent if op["is_active"] and op["ko_units"] > 0]
    if not activos:
        # fallback 1→N: sem activo com coroa -> melhor foldado com coroa.
        com_coroa = [op for op in per_opponent if op["ko_units"] > 0]
        if not com_coroa:
            return None
        return max(com_coroa, key=lambda op: (op["ire_pct"] or 0.0))
    if len(activos) == 1:
        return activos[0]
    cobertos = [op for op in activos if op["stack_chips"] <= hero_stack_chips]
    if len(cobertos) == 1:
        return cobertos[0]
    if cobertos:
        return max(cobertos, key=lambda op: op["stack_chips"])
    return max(activos, key=lambda op: op["stack_chips"])


# ── API publica ──────────────────────────────────────────────────────────────

def compute_ire(hand: dict, tournament_meta: Optional[dict]) -> Optional[dict]:
    """Devolve {main_villain, per_opponent} ou None.
    Hero e excluido de per_opponent. Vilao principal escolhido pela regra D."""
    if hand.get("site") != "GGPoker":
        return None

    pn = _coerce_pn(hand.get("player_names"))
    mm = pn.get("match_method")
    if not mm or (isinstance(mm, str) and mm.startswith("discord_placeholder_")):
        return None

    if hand.get("tournament_format") not in ALLOWED_FORMATS:
        return None

    if not _has_ko_tag(hand.get("hm3_tags"), hand.get("discord_tags")):
        return None

    if not tournament_meta or not tournament_meta.get("starting_stack"):
        return None
    try:
        si = float(tournament_meta["starting_stack"])
    except (TypeError, ValueError):
        return None
    if si <= 0:
        return None

    # #BOUNTY-PCT-VPIP-FIX: o IRE passa a usar o bounty REAL ($, coroa dourada =
    # bounty_value_usd) em vez de bounty_pct (que era VPIP, chama laranja).
    # ko_units = bounty_value_usd / buy_in_bounty (múltiplos do bounty inicial;
    # jogador fresco = 1). Sem buy_in_bounty (TS) não há base de conversão -> oculto.
    try:
        bib = float((tournament_meta or {}).get("buy_in_bounty") or 0)
    except (TypeError, ValueError):
        bib = 0.0
    if bib <= 0:
        return None

    tname = (tournament_meta.get("tournament_name") or "").lower()
    if SUPER_KO_NEEDLE in tname:
        # #IRE-MB T4 (decisao b): escondido ate validar empiricamente a
        # instant_fraction do Super KO. A constante seria derivavel, mas sem
        # esse dado o IRE ficaria potencialmente errado -> preferimos esconder.
        return None

    apa = _coerce_apa(hand.get("all_players_actions"))
    if not apa:
        return None
    bb = (apa.get("_meta") or {}).get("bb") or 0
    if bb <= 0:
        return None

    # #IRE-MB — constante do bounty por torneio (KOP_fraction × instant_fraction).
    # GG: de buy_in_entry/buy_in_bounty (tournament_summaries, via JOIN no caller).
    # Ausente/non-derivável -> default 0.25 (legacy). raw_hh=None: ramo PS dormante.
    #
    # T5 (#MYSTERY-KO-DUAL-SUPPORT): SÓ o PKO usa a constante derivada. No Mystery
    # KO o bounty é aleatório/desconhecido até ao KO -> a fórmula de bounty fixo
    # não aplica; mantém-se em 0.25 (legacy) até suporte dedicado. ⚠️ Mystery PS
    # (Seat bounty random) precisa de confirmação empírica futura — sub-item adiado.
    if hand.get("tournament_format") == "PKO":
        constant = derive_constant(
            hand.get("site"),
            buy_in_entry=(tournament_meta or {}).get("buy_in_entry"),
            buy_in_bounty=(tournament_meta or {}).get("buy_in_bounty"),
            raw_hh=None,
        )
    else:
        constant = _DEFAULT_CONSTANT

    pl_by_name = {}
    for p in (pn.get("players_list") or []):
        if isinstance(p, dict):
            for key in ("name", "real_name"):
                v = p.get(key)
                if v:
                    pl_by_name.setdefault(v, p)

    hero_stack = None
    per_opponent: list[dict] = []
    for nick, info in apa.items():
        if nick == "_meta" or not isinstance(info, dict):
            continue
        if info.get("is_hero"):
            hero_stack = info.get("stack")
            continue
        try:
            stack_chips = float(info.get("stack") or 0)
        except (TypeError, ValueError):
            stack_chips = 0.0
        # Bounty real ($) = coroa dourada; vive em player_names.players_list
        # (o apa só carrega bounty_pct=VPIP). ko_units = bounty_$ / bounty_inicial_$.
        bounty_usd = _coerce_float((pl_by_name.get(nick) or {}).get("bounty_value_usd"))
        ko_units = bounty_usd / bib if bounty_usd > 0 else 0.0
        stack_si = stack_chips / si if si > 0 else 0.0
        ire_pct = lookup_ire_pct(stack_si, ko_units, constant) if ko_units > 0 else None
        per_opponent.append({
            "nick": nick,
            "position": info.get("position"),
            "stack_chips": int(round(stack_chips)),
            "stack_bb": round(stack_chips / bb, 1) if bb else None,
            "stack_si": round(stack_si, 3),
            "ko_pct": round(ko_units * 100),   # bounty em % do inicial (derivado; ko_units é o canónico)
            "ko_units": round(ko_units, 2),
            "ire_pct": round(ire_pct, 1) if ire_pct is not None else None,
            "is_main": False,
            "is_active": _is_active(info.get("actions")),
            "is_covered": False,  # preenchido depois quando soubermos hero_stack
        })

    if not per_opponent:
        return None

    # nenhum oponente com bounty real (coroa) > 0 => escondido
    if not any(op["ko_units"] > 0 for op in per_opponent):
        return None

    if hero_stack is None or hero_stack <= 0:
        return None
    hero_stack_f = float(hero_stack)

    for op in per_opponent:
        op["is_covered"] = op["stack_chips"] <= hero_stack_f

    # 1→N (#BOUNTY-PCT-VPIP-FIX): o IRE é calculado por-oponente (per_opponent,
    # foldados incluídos). `main_villain` mantém-se só como headline da lista
    # (HandRow). Já NÃO é gate: a partir do guard `any(ko_units>0)` acima, há
    # sempre ≥1 oponente com coroa, e `_pick_main_villain` escolhe sempre um
    # (fallback ao melhor foldado se nenhum activo). `_is_active` deixou de ser
    # gate — fica só como campo de display (tooltip "folded").
    main = _pick_main_villain(per_opponent, hero_stack_f)
    if main is not None:
        for op in per_opponent:
            if op["nick"] == main["nick"]:
                op["is_main"] = True
                break

    per_opponent.sort(key=lambda op: _seat_order_key(op.get("position")))

    main_out = None
    if main is not None:
        main_out = {
            "nick": main["nick"],
            "position": main.get("position"),
            "stack_chips": main["stack_chips"],
            "stack_bb": main["stack_bb"],
            "stack_si": main["stack_si"],
            "ko_pct": main["ko_pct"],
            "ko_units": main["ko_units"],
            "ire_pct": main["ire_pct"],
            "is_covered": main["is_covered"],
        }
    return {"main_villain": main_out, "per_opponent": per_opponent}
