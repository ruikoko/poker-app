"""HRC export — converte raw HH GG para formato PokerStars-compativel.

FASE 1 cobre apenas a conversao de uma mao. O packaging em zip (build_queue_zip)
fica para COMMIT 3.

Decisoes (D1-D4 do plano FASE 1):
  D1: linha 1 mantem prefixo `Poker Hand #` (validado pt16 commit 0d18c52).
  D2: header LevelN(SB/BB(ante)) -> LevelN (SB/BB) sem ante embutido.
      Razao: HRC tem bug parsing ante na 2a parens (ja confirmado em pt16).
      Antes continuam nas linhas `<player>: posts the ante X` no corpo da HH.
  D3: hashes 7-8 hex sao substituidos por nicks reais via player_names.anon_map
      quando este existir. Sem anon_map -> hashes ficam (degrade graceful).
  D4: bounty inline em seats NAO e adicionado em FASE 1. HRC le do payouts.json.
      (pt24: REVISTO — `_inject_bounties_into_seat_lines` injecta bounty $
      em cada Seat line quando `players_list[].bounty_value_usd` existe.
      Fecha `#HRC-GG-KOS-EXTRACTION` para mãos GG com Vision pt24+ ingestion.)
"""
from __future__ import annotations
import io
import json
import logging
import re
import zipfile
from datetime import datetime, timezone
from typing import Any, Optional

from app.services.derive_max_players import derive_max_players

logger = logging.getLogger("queue_export")


# pt23 fix Bug A: tags que disparam Malmuth-Harville ICM (FT-style equity).
# Restantes mãos default → multi_table_icm. HM3 usa nomes capitalizados;
# Discord usa nomes lowercase hyphenated.
_EQUITY_FT_HM3 = {"ICM FT", "ICM PKO FT"}
_EQUITY_FT_DISCORD = {"icm-ft", "icm-pko-ft"}


# Captura `LevelN(SB/BB(ante))` com numeros podendo ter virgulas de milhar.
# Ex: `Level17(2,500/5,000(600))` -> grupos: 17, 2,500, 5,000, 600.
_LEVEL_RE = re.compile(
    r"\bLevel(\d+)\(([\d,]+)/([\d,]+)\(([\d,]+)\)\)"
)


def _format_level_line(text: str) -> str:
    """Transforma `LevelN(SB/BB(ante))` em `LevelN (SB/BB)` (sem ante,
    sem virgulas)."""
    def repl(m: re.Match) -> str:
        n, sb, bb, _ante = m.groups()
        return f"Level{n} ({sb.replace(',', '')}/{bb.replace(',', '')})"
    return _LEVEL_RE.sub(repl, text)


def _replace_hashes(text: str, anon_map: dict) -> str:
    """Substitui literalmente cada hash do anon_map pelo respectivo nick.
    Mantem `Hero` intacto. Hashes nao mapeados ficam tal e qual.

    Ordena hashes por comprimento decrescente para evitar matches parciais
    quando dois hashes partilham prefixo (caso raro mas defensivo)."""
    if not anon_map:
        return text
    items = [
        (h, nick) for h, nick in anon_map.items()
        if h and h != "Hero" and nick
    ]
    items.sort(key=lambda kv: -len(kv[0]))
    for hash_id, nick in items:
        pat = re.compile(r"\b" + re.escape(hash_id) + r"\b")
        text = pat.sub(lambda m, n=nick: n, text)
    return text


def _coerce_player_names(pn) -> dict:
    if isinstance(pn, str):
        try:
            pn = json.loads(pn)
        except (ValueError, TypeError):
            return {}
    return pn if isinstance(pn, dict) else {}


# pt24: regex para Seat lines no HH GG. Captura prefix + nick (lazy, tolera
# espaços em nomes pós-_replace_hashes, ex: "Vlad Martyn.." ou "R Aziz Alves")
# + " (CHIPS in chips" — o `)` final fica fora dos grupos para podermos
# injectar conteúdo antes de o fechar.
_SEAT_RE = re.compile(r"^(Seat \d+: )(.+?)( \([\d,]+ in chips)\)", re.MULTILINE)


def _detect_currency_symbol(hh_text: str) -> str:
    """Detecta currency a partir do tournament header (1ª linha).

    GG headers tipicamente: '... Bounty Hunters Big Game $215 ...' → USD;
    PS/WN-style adaptado: '€45+€45+€10 EUR' → EUR. Default $: a maioria
    dos GG PKO em prod é USD."""
    first_line = hh_text.split("\n", 1)[0] if hh_text else ""
    return "€" if "€" in first_line else "$"


def _inject_bounties_into_seat_lines(
    hh_text: str, players_list, anon_map: dict
) -> str:
    """pt24 fix `#HRC-GG-KOS-EXTRACTION`.

    Injecta `, $X.XX bounty` em cada Seat line do HH PS-compat quando o player
    correspondente tem `bounty_value_usd > 0` em `players_list` (extraído por
    Vision pt24 da coroa dourada na SS).

    Resolução de nomes:
    - Pós-`_replace_hashes`, Seat lines têm nicks reais excepto `Hero` (que fica
      literal). Para a linha do Hero, resolvemos via `anon_map["Hero"]`.
    - Lookup em players_list é case-sensitive, name-exact match. Nomes sem
      match em bounty_by_name → linha intacta (graceful: GG players ainda
      em jogo às vezes não têm crown visível na SS, ou Vision falhou crown
      para esse seat).

    Currency: $ por defeito (GG USD); € se header contém '€'.

    No-op se `players_list` vazio ou todos os bounty_value_usd <= 0.
    """
    if not hh_text or not players_list:
        return hh_text

    bounty_by_name: dict = {}
    for p in players_list:
        name = (p.get("name") or "").strip()
        bv = p.get("bounty_value_usd")
        if name and isinstance(bv, (int, float)) and bv > 0:
            bounty_by_name[name] = float(bv)

    if not bounty_by_name:
        return hh_text

    hero_real = (anon_map or {}).get("Hero")
    currency = _detect_currency_symbol(hh_text)

    def _repl(m: re.Match) -> str:
        prefix, nick, mid = m.group(1), m.group(2), m.group(3)
        lookup = hero_real if (nick == "Hero" and hero_real) else nick
        bounty = bounty_by_name.get(lookup)
        if bounty is None:
            return m.group(0)
        return f"{prefix}{nick}{mid}, {currency}{bounty:.2f} bounty)"

    return _SEAT_RE.sub(_repl, hh_text)


def convert_gg_hh_to_pokerstars_compatible(hand: dict) -> str:
    """Converte raw HH GG para formato compativel com HRC.

    Hands non-GG (PokerStars, Winamax) passam tal e qual (pass-through) —
    Fase 2 tratara conversoes especificas se HRC reclamar de Winamax.

    Hands com `raw` vazio devolvem string vazia (caller deve filtrar).

    pt24: adicionada injecção de bounty_value_usd nas Seat lines pós-replace
    via `_inject_bounties_into_seat_lines` (fecha `#HRC-GG-KOS-EXTRACTION`)."""
    raw = (hand.get("raw") or "").strip()
    if not raw:
        return ""
    if hand.get("site") != "GGPoker":
        return hand.get("raw") or ""

    pn = _coerce_player_names(hand.get("player_names"))
    anon_map = pn.get("anon_map") or {}
    players_list = pn.get("players_list") or []

    out = _format_level_line(raw)
    out = _replace_hashes(out, anon_map)
    out = _inject_bounties_into_seat_lines(out, players_list, anon_map)
    return out


def _derive_equity_model(hm3_tags, discord_tags) -> str:
    """pt23 fix Bug A. Decide equity model hint based on tag membership.

    Devolve 'malmuth_harville_icm' se houver tag FT (HM3 ou Discord);
    caso contrário 'multi_table_icm' (default p/ mid-MTT).
    """
    hm3 = set(hm3_tags or [])
    disc = set(discord_tags or [])
    if hm3 & _EQUITY_FT_HM3 or disc & _EQUITY_FT_DISCORD:
        return "malmuth_harville_icm"
    return "multi_table_icm"


def _build_watcher_hints(hand: dict, hh_text: str) -> dict:
    """pt23 fix A/B/C — 3 hints que o watcher patched lê em setup_hand.

    Defensivo: cada hint é wrapped em try/except. Falha individual → omite
    a key (watcher cai no default seguro). Falha total → dict vazio.
    """
    hints: dict = {}
    try:
        hints["equity_model"] = _derive_equity_model(
            hand.get("hm3_tags"), hand.get("discord_tags"),
        )
    except Exception:
        logger.exception(
            "derive equity_model falhou hand_id=%s", hand.get("hand_id"),
        )
    try:
        hints["max_players"] = derive_max_players(hh_text)
    except Exception:
        logger.exception(
            "derive max_players falhou hand_id=%s", hand.get("hand_id"),
        )
    # pt24+: derivar script_path por tag/profundidade. Por agora None.
    hints["script_path"] = None
    return hints


def build_queue_zip(
    hands: list[dict],
    payouts_by_key: dict[tuple[str, str], Any],
    *,
    include_no_payout: bool = False,
    filters_meta: Optional[dict] = None,
) -> bytes:
    """Constroi um zip com pasta por mao + manifest.json no root.

    Args:
      hands: lista de dicts com keys: id, hand_id, site, tournament_number,
             raw, player_names, played_at.
      payouts_by_key: lookup {(site, tournament_number): payouts_json_blob}.
      include_no_payout: se True, mao sem payout entra no zip sem payouts.json.
                         Se False, mao sem payout e excluida (vai para
                         manifest.missing_payouts).
      filters_meta: dict de filters echoado no manifest (observabilidade).

    Estrutura:
      <hand_id_1>/hh.txt
      <hand_id_1>/payouts.json    # se houver payouts ou include_no_payout=True
      <hand_id_2>/hh.txt
      ...
      manifest.json
    """
    hands_included = []
    missing_payouts = []
    skipped = []

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for h in hands:
            hand_id = h.get("hand_id")
            site = h.get("site")
            tnum = h.get("tournament_number")

            if not hand_id:
                skipped.append({"hand_id": None, "reason": "no_hand_id"})
                continue

            hh_text = convert_gg_hh_to_pokerstars_compatible(h)
            if not hh_text:
                skipped.append({"hand_id": hand_id, "reason": "no_raw_hh"})
                continue

            key = (site, tnum) if site and tnum else None
            payout_blob = payouts_by_key.get(key) if key else None

            if payout_blob is None and not include_no_payout:
                missing_payouts.append({
                    "hand_id": hand_id,
                    "tournament_number": tnum,
                    "site": site,
                    "reason": "no_row_in_tournament_payouts",
                })
                continue

            zf.writestr(f"{hand_id}/hh.txt", hh_text)

            # pt23: merge hints (equity_model, max_players, script_path) com
            # o payout_blob. Hints aplicam-se sempre — mesmo sem blob, escreve
            # payouts.json só com hints para o watcher os ler.
            hints = _build_watcher_hints(h, hh_text)
            if payout_blob is not None:
                merged: dict = dict(payout_blob) if isinstance(payout_blob, dict) else {"_blob": payout_blob}
                merged.update(hints)
                zf.writestr(
                    f"{hand_id}/payouts.json",
                    json.dumps(merged, indent=2, ensure_ascii=False),
                )
            else:
                zf.writestr(
                    f"{hand_id}/payouts.json",
                    json.dumps(hints, indent=2, ensure_ascii=False),
                )

            hands_included.append({
                "hand_id": hand_id,
                "tournament_number": tnum,
                "site": site,
                "has_payouts": payout_blob is not None,
                "converted_format": (
                    "pokerstars_compat" if site == "GGPoker" else "passthrough"
                ),
            })

        manifest = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "filters": filters_meta or {},
            "total_hands_queried": len(hands),
            "total_in_zip": len(hands_included),
            "hands_included": hands_included,
            "missing_payouts": missing_payouts,
            "skipped": skipped,
        }
        zf.writestr(
            "manifest.json",
            json.dumps(manifest, indent=2, ensure_ascii=False),
        )

    return buf.getvalue()
