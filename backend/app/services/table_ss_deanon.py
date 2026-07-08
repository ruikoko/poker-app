"""Desanonimização de mão GG via SS de mesa (Intuitive Tables) — Estágio 3.

Estende a maquinaria de match banco-a-banco do pt7 (âncoras + aritmética de
stacks + atribuição óptima, em `routers/screenshot.py`) à **SS de mesa**: a
Vision do table-SS lê (nick, stack_bb, herói) por banco; esta camada cruza
isso com a HH GG anonimizada (hashes) já ligada à SS (`context_table_ss_id`)
e produz `player_names` + `match_method='table_ss'` + `all_players_actions`
enriquecido — pela MESMA porta que o caminho do replayer, para a mão entrar
no Estudo/Vilões sem excepção ao gate.

PRINCÍPIO (Rui, pt-desanon): a captura é o sinal de interesse; os nicks reais
estão na imagem do IT, a HH tem tudo menos nomes. Cruzam-se.

NÃO toca no caminho actual do screenshot.py — só **reutiliza** os seus
helpers puros (`_build_anon_to_real_map`, `_enrich_all_players_actions`),
importados lazy para evitar ciclos e custo de import.

Guardas (invariantes):
- Só mão **GG** com **HH real** (`raw` populado) e `all_players_actions` com
  jogadores (não placeholder só-`_meta`).
- Só se a mão **ainda não tem match real** (`match_method` ausente ou
  `discord_placeholder_*`). **Discord prevalece** — nunca sobrescreve um
  `anchors_stack_elimination_v2`. Re-correr sobre uma mão já `table_ss` é
  permitido (idempotente — re-deriva o mesmo map).
- A decisão "esta mão é elegível" (sem Discord, etc.) é do CALL SITE; aqui
  ficam só as guardas de segurança de dados.

Aproximação conhecida (documentada): a SS de mesa casa com a mão GG mais
próxima no TEMPO (não necessariamente a mão exacta da captura). Os stacks
podem ter deriva de algumas mãos; a tolerância (2%/20 fichas nos folds) + a
atribuição global óptima resolvem pela ORDEM relativa dos stacks, que se
mantém ao longo de poucas mãos. Bancos em ALL-IN (stack desconhecido) só
resolvem por eliminação 1-1.
"""
from __future__ import annotations

import json
import logging
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from typing import Any, Optional

logger = logging.getLogger("table_ss_deanon")

MATCH_METHOD = "table_ss"
# match_methods que NÃO devemos sobrescrever (match real já existente).
# #IT-MATCHER-GOLD-MANDA: 'position_v3' é o deanon da GOLD (replayer, por posição
# — screenshot.py:886), o método PREMIUM. Estava fora deste conjunto → ligar um IT
# sobrescrevia os nomes da Gold. Agora protegido: o table-SS nunca escreve por cima
# da Gold (Gold manda). 'anchors_stack_elimination_v2' = fallback stack do replayer.
_REAL_MATCH_METHODS = frozenset({"anchors_stack_elimination_v2", "position_v3"})


def _seats_to_vision_data(seats: list[dict], hero_nick: Optional[str]) -> dict:
    """Converte os `seats` da Vision do table-SS para o shape que o
    `_build_anon_to_real_map` consome (igual ao do replayer).

    - stack em BB → `stack_unit='bb'` + `stack_raw=<bb>` (o helper normaliza
      para fichas com o bb_size da HH). 'ALLIN'/None → sem stack (resolve por
      eliminação).
    - `vision_sb`/`vision_bb` = None: o table-SS não identifica SB/BB por nome,
      logo as âncoras SB/BB do helper são saltadas (os bancos caem nas fases de
      stack/eliminação). O Hero ancora à mesma (nick = hero_nick).
    """
    players_list: list[dict] = []
    for s in seats or []:
        nick = (s.get("nick") or "").strip()
        if not nick:
            continue
        p: dict[str, Any] = {"name": nick}
        stack = s.get("stack_bb")
        if isinstance(stack, (int, float)) and not isinstance(stack, bool) and stack > 0:
            p["stack_unit"] = "bb"
            p["stack_raw"] = float(stack)
        # 'ALLIN'/None → sem stack (name-only); bounty preservado p/ enrich.
        if s.get("bounty_usd") is not None:
            p["bounty_value_usd"] = s.get("bounty_usd")
        players_list.append(p)
    return {
        "players_list": players_list,
        "players_by_position": {},
        "hero": hero_nick,
        "vision_sb": None,
        "vision_bb": None,
    }


def _has_usable_stack(seat: dict) -> bool:
    """Banco tem stack numérico > 0 (não 'ALLIN', não None, não 0)."""
    s = seat.get("stack_bb")
    return isinstance(s, (int, float)) and not isinstance(s, bool) and s > 0


def _filter_ambiguous_stackless(seats: list[dict]) -> tuple[list[dict], bool]:
    """Afinação Web (anti-envenenamento): se há **≥2 bancos NÃO-herói sem stack
    utilizável**, a atribuição óptima do pt7 mapearia-os por palpite (todos os
    diffs = stack vs 0 → permutação arbitrária). Em vez disso, **removem-se** do
    pool → ficam POR MAPEAR (hash mantido). Nome em falta é honesto; nome
    trocado envenena fichas de vilões. O Hero nunca é removido (ancora por nick).
    1 só banco sem stack mantém-se (a eliminação 1-1 do pt7 é segura).

    Devolve (seats_para_o_helper, removeu_algum)."""
    nonhero_stackless = [
        s for s in seats
        if (s.get("nick") or "").strip()
        and not s.get("is_hero")
        and not _has_usable_stack(s)
    ]
    if len(nonhero_stackless) >= 2:
        kept = [s for s in seats if s.get("is_hero") or _has_usable_stack(s)]
        return kept, True
    return seats, False


def build_anon_map_from_seats(
    matched_hand: dict, seats: list[dict], hero_nick: Optional[str]
) -> dict:
    """Núcleo puro/testável: hash→nick para `matched_hand` a partir dos `seats`
    do table-SS. Reutiliza `_build_anon_to_real_map` (pt7) DEPOIS de remover os
    bancos ambíguos (≥2 sem stack) — ver `_filter_ambiguous_stackless`. {} se
    não mapeia."""
    from app.routers.screenshot import _build_anon_to_real_map  # lazy
    seats_for_map, _ = _filter_ambiguous_stackless(seats)
    vision_data = _seats_to_vision_data(seats_for_map, hero_nick)
    if not vision_data["players_list"]:
        return {}
    return _build_anon_to_real_map(matched_hand, vision_data)


def _num_stack(x):
    """stack_bb → float; 'ALLIN'/None/inválido → None."""
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def build_anon_map_by_hero_button(image_seats: list, hh_pos: dict, num_players: int,
                                  hh_stacks: dict = None):
    """pt96 (#DESANON-HERO-BUTTON-ANCHOR): desanon do table-SS por ÂNCORA Hero+botão +
    propagação circular — TEXTO (HH) manda na estrutura, imagem só dá NOMES, stacks NÃO
    entram. Método primário do table-SS (substitui o stack-elimination, que trocava
    nicks em stacks próximos).

    Args:
        image_seats: lista ORDENADA (horário do Hero) de dicts {nick, is_hero, is_button}
                     da Vision estendida.
        hh_pos: {hash: position} da HH (SB/BB/BTN/UTG/... por hash, do parser).
        num_players: nº de jogadores da HH.

    Devolve (anon_map hash→nick, alarm). **alarm != None → NÃO desanonimizar às cegas**
    (mão para revisão): contagens diferem (sitting-out/mesa incompleta), botão não bate,
    sem Hero, etc. Regra dura: o Hero fica no índice 0 fixo → NUNCA mapeado a um vilão.
    """
    from app.parsers.gg_hands import POSITION_MAPS
    pm = POSITION_MAPS.get(num_players)
    if not pm:
        return {}, "hh_no_position_map_%s" % num_players
    by_pos = {p: h for h, p in (hh_pos or {}).items()}
    # roda da HH: horário por seat_num (SB, BB, ..., CO, BTN), rodada p/ Hero no índice 0
    cw = ["SB", "BB"] + pm[:-3] + ["BTN"]
    order = [by_pos[p] for p in cw if p in by_pos]
    if "Hero" not in order:
        return {}, "hh_no_hero"
    hi = order.index("Hero")
    hh_wheel = order[hi:] + order[:hi]
    btn_hash = by_pos.get("BTN")
    btn_idx_hh = hh_wheel.index(btn_hash) if btn_hash in hh_wheel else None

    # SALVAGUARDA 1: contagens diferem (sitting-out / mesa incompleta) → alarme, não cegar.
    if len(image_seats or []) != len(hh_wheel):
        return {}, "seat_count_mismatch_img%d_hh%d" % (len(image_seats or []), len(hh_wheel))

    # roda da imagem: Hero no índice 0
    heroes = [i for i, s in enumerate(image_seats) if s.get("is_hero")]
    if len(heroes) != 1:
        return {}, "image_hero_count_%d" % len(heroes)
    img = image_seats[heroes[0]:] + image_seats[:heroes[0]]

    # DIRECÇÃO da roda (1 de 2). O Hero está FIXO (índice 0); falta só escolher horário
    # vs invertido. 2ª âncora = BOTÃO; fallback = STACKS (SÓ para a direcção, NUNCA para
    # mapear nomes — os nomes vêm da ordem). Botão+stacks concordam → alta confiança;
    # discordam → alarme. Isto é inócuo (escolhe 1 de 2 sentidos, não atribui nicks).
    if len(hh_wheel) <= 2:
        direction = "fwd"                       # heads-up: 1 vilão, direcção trivial
    else:
        # (a) botão (2ª âncora)
        btn_dir = None
        if btn_idx_hh is not None:
            btns = [i for i, s in enumerate(img) if s.get("is_button")]
            if len(btns) == 1:
                if btns[0] == btn_idx_hh:
                    btn_dir = "fwd"
                elif btns[0] == (len(img) - btn_idx_hh) % len(img):
                    btn_dir = "rev"
        # (b) stacks (fallback — só direcção; margem clara exigida)
        stack_dir = None
        if hh_stacks:
            def _dir_err(rev):
                seq = [img[0]] + (img[1:][::-1] if rev else img[1:])
                e = cnt = 0.0
                for k in range(1, len(hh_wheel)):
                    a = _num_stack(seq[k].get("stack_bb"))
                    b = _num_stack(hh_stacks.get(hh_wheel[k]))
                    if a is not None and b is not None:
                        e += abs(a - b); cnt += 1
                return (e / cnt if cnt else None), cnt
            eF, cF = _dir_err(False)
            eR, cR = _dir_err(True)
            if eF is not None and eR is not None and min(cF, cR) >= 2:
                lo, hi2 = min(eF, eR), max(eF, eR)
                if (hi2 - lo) / (lo + 0.5) >= 0.5:      # margem clara (>=50%)
                    stack_dir = "fwd" if eF < eR else "rev"
        # (c) decidir (cruzamento)
        if btn_dir and stack_dir:
            if btn_dir != stack_dir:
                return {}, "button_stack_direction_disagree"
            direction = btn_dir                 # concordam → alta confiança
        elif btn_dir:
            direction = btn_dir
        elif stack_dir:
            direction = stack_dir
        else:
            return {}, "direction_unresolved"   # nem botão nem stacks decidem → revisão
    if direction == "rev":
        img = [img[0]] + img[1:][::-1]           # inverter (Hero fixo no 0)

    # mapear pela roda alinhada. Hero (índice 0) fixo → nunca a um vilão.
    anon_map = {}
    for k in range(len(hh_wheel)):
        nick = (img[k].get("nick") or "").strip()
        if not nick:
            return {}, "image_empty_nick_at_%d" % k
        anon_map[hh_wheel[k]] = nick
    # sanidade: nicks distintos (2 seats com o mesmo nome = leitura má) → alarme.
    if len(set(anon_map.values())) != len(anon_map):
        return {}, "duplicate_nicks"
    return anon_map, None


def _existing_match_method(player_names: Any) -> Optional[str]:
    pn = player_names
    if isinstance(pn, str):
        try:
            pn = json.loads(pn)
        except (ValueError, TypeError):
            pn = {}
    return pn.get("match_method") if isinstance(pn, dict) else None


# ── Guarda UNIVERSAL de consistência de desanon (#DESANON-SITTING-OUT-NPLUS1) ──

_SEAT_HASH_RE = re.compile(r'^Seat \d+: ([0-9a-f]{4,8}) \(', re.M)   # hashes anón
# nº do seat (grupo). Contamos seats DISTINTOS (set), não linhas: o GG/PS repete
# "Seat N: …" na secção *** SUMMARY *** (folded/showed) → contar linhas duplicava o
# seat_count (~2×) e a guarda C0 bloqueava TODA a mão com resumo (regressão apanhada
# no reimport, Cano 3). `raw_hashes` já é set (dedup header+summary), só isto faltava.
_SEAT_NUM_RE = re.compile(r'^Seat (\d+):', re.M)
_HASHLIKE_RE = re.compile(r'^[0-9a-f]{4,8}$')


def assert_deanon_consistency(raw, apa, anon_map, *, vision_seat_count=None,
                              by_order=False) -> tuple:
    """Invariante UNIVERSAL de desanon — pura, partilhada por todos os caminhos de escrita.
    Compara o apa (real_name || chave) com os Seats do RAW + o `anon_map`. Devolve
    `(level, viols)` com `level ∈ {'ok','alarm','block'}`:
      - **block** → NÃO persistir (mão para revisão): nome REAL repetido na mão (C2, veneno —
        nicks GG únicos por conta), nome injetado/seat perdido (C1, o apa desliza vs anon_map),
        contagem apa≠HH (colapso/injeção), OU img≠HH num caminho por ORDEM/STACK (C3).
      - **alarm** → persistir com `deanon_partial` (seat por mapear = branco honesto).
      - **ok**.
    `position_v3` (por RÓTULO) passa `by_order=False` → isento do C3 (larga o extra sem rótulo,
    corretamente). Ver `DESANON_ANATOMIA §3.2.4` (caso `GG-6083771298`, Afonso Neto N+1)."""
    raw = raw or ""
    apa = apa if isinstance(apa, dict) else {}
    anon = anon_map or {}
    raw_hashes = set(_SEAT_HASH_RE.findall(raw))
    seat_count = len(set(_SEAT_NUM_RE.findall(raw)))   # seats DISTINTOS (ignora repetição no SUMMARY)
    # Sem HH parseável (placeholder / raw vazio) OU sem hashes anón (não-GG, nicks reais) →
    # a guarda não tem contra o quê validar → ABSTÉM-SE (não bloqueia).
    if seat_count == 0 or not raw_hashes:
        return "ok", []
    players = [(k, v) for k, v in apa.items() if k != "_meta" and isinstance(v, dict)]

    def _disp(k, v):
        return (v.get("real_name") or k or "")

    def _is_hash(n):
        return bool(_HASHLIKE_RE.match(n or ""))

    hero = next((_disp(k, v) for k, v in players if v.get("is_hero")), None)
    named = [_disp(k, v) for k, v in players]
    real = [n for n in named if n and not _is_hash(n)]   # nomes reais no apa (não hash/branco)
    viols, level = [], "ok"

    # C2 — nome real repetido DENTRO da mão → veneno estrutural (sempre bloqueia)
    dups = sorted({n for n, c in Counter(real).items() if c > 1})
    if dups:
        viols.append("dup_name:" + ",".join(dups)); level = "block"

    # C0 — contagem: o apa tem de ter tantos jogadores como Seats na HH (injeção/colapso)
    if seat_count and len(players) != seat_count:
        viols.append("count:apa%d_ne_hh%d" % (len(players), seat_count)); level = "block"

    # C1 — cobertura: os nomes REAIS do apa == os que a HH+anon_map dizem (Hero incluído).
    hh_names = {anon[h] for h in raw_hashes if h in anon and (anon[h] or "").strip()}
    if hero:
        hh_names.add(hero)
    apa_real = set(real)
    injected = apa_real - hh_names        # nome no apa que não pertence à mão (ex. Afonso Neto)
    lost = hh_names - apa_real            # nome que a HH tem mas o apa perdeu (ex. SB colapsado)
    if injected:
        viols.append("name_injected:" + ",".join(sorted(injected))); level = "block"
    if lost:
        viols.append("seat_lost:" + ",".join(sorted(lost))); level = "block"

    # seat por mapear (hash no raw sem nome) → alarme HONESTO (branco > errado), não bloqueia
    unmapped = [h for h in raw_hashes if not (anon.get(h) or "").strip()]
    if unmapped and level == "ok":
        level = "alarm"; viols.append("unmapped:%d" % len(unmapped))

    # C3 — img≠HH só nos caminhos por ORDEM/STACK (position_v3 por rótulo é isento)
    if by_order and vision_seat_count is not None and vision_seat_count != seat_count:
        viols.append("img%d_ne_hh%d" % (vision_seat_count, seat_count)); level = "block"

    return level, viols


def deanonymize_hand_from_table_ss(
    hand_db_id: int, seats: list[dict], hero_nick: Optional[str]
) -> dict:
    """Desanonimiza a mão `hand_db_id` com os bancos lidos do table-SS.

    Escreve `player_names` (com anon_map + match_method='table_ss') +
    `all_players_actions` enriquecido, e dispara `apply_villain_rules`.
    Devolve {status, mapped, ...}. Idempotente sob re-corrida table_ss.

    status: 'deanonymized' | 'no_map' | 'skip_real_match' | 'skip_no_hh' |
            'skip_not_gg' | 'hand_not_found'
    """
    from app.db import get_conn, query
    from app.routers.screenshot import _enrich_all_players_actions  # lazy

    rows = query(
        "SELECT id, hand_id, site, raw, all_players_actions, player_names "
        "FROM hands WHERE id = %s",
        (hand_db_id,),
    )
    if not rows:
        return {"status": "hand_not_found", "hand_db_id": hand_db_id}
    h = dict(rows[0])

    # Guarda 1: GG only (o table-SS desanon é específico da GG anonimizada).
    if h.get("site") != "GGPoker":
        return {"status": "skip_not_gg", "hand_db_id": hand_db_id}

    # Guarda 2: HH real (sem raw a mão nunca entra em Estudo — regra dura).
    if not (h.get("raw") or "").strip():
        return {"status": "skip_no_hh", "hand_db_id": hand_db_id}

    # Guarda 3: não sobrescrever match real (Discord prevalece).
    existing_mm = _existing_match_method(h.get("player_names"))
    if existing_mm in _REAL_MATCH_METHODS:
        return {"status": "skip_real_match", "hand_db_id": hand_db_id,
                "match_method": existing_mm}

    apa_raw = h.get("all_players_actions") or {}
    if isinstance(apa_raw, str):
        try:
            apa_raw = json.loads(apa_raw)
        except (ValueError, TypeError):
            apa_raw = {}
    # pt95 (#REDEANON-NOT-IDEMPOTENT): se a mão já foi desanonimizada, o apa está
    # name-keyed (o `_enrich_all_players_actions` abaixo renomeia hash→name).
    # Re-correr SEM re-keyar faria o `build_anon_map_from_seats` usar os NOMES como
    # chave → mapa name→name (corrompe — foi o que partiu a GG-6113994321 ao
    # re-correr o /redeanon ~20×). Re-keyar a hashes ANTES, via o anon_map
    # existente — exactamente o que o `reconcile_tournament_deanon` faz (l.411).
    _prev_pn = h.get("player_names") or {}
    if isinstance(_prev_pn, str):
        try:
            _prev_pn = json.loads(_prev_pn)
        except (ValueError, TypeError):
            _prev_pn = {}
    _prev_map = _prev_pn.get("anon_map") or {}
    if _prev_map:
        apa_raw = _rekey_apa_to_hashes(apa_raw, _prev_map)
    # apa placeholder-only (só _meta) → nada a mapear.
    if not [k for k in apa_raw if k != "_meta"]:
        return {"status": "no_map", "hand_db_id": hand_db_id, "reason": "apa_meta_only"}

    # pt96 (#DESANON-HERO-BUTTON-ANCHOR): se a Vision deu is_button (pipeline novo), usa a
    # ÂNCORA Hero+botão (PRIMÁRIO — texto manda na estrutura, imagem só dá nomes, stacks
    # NÃO entram). Alarme (sitting-out / botão não bate) → mão para REVISÃO, NÃO escreve
    # às cegas (nunca sai com nomes trocados em silêncio). Sem is_button (dados antigos) →
    # fallback stack-elimination (o método antigo, que trocava nicks em stacks próximos).
    if any(s.get("is_button") for s in (seats or [])):
        hh_pos = {k: (v or {}).get("position")
                  for k, v in apa_raw.items() if k != "_meta"}
        hh_stacks = {k: (v or {}).get("stack_bb")
                     for k, v in apa_raw.items() if k != "_meta"}
        n_players = len([k for k in apa_raw if k != "_meta"])
        anon_map, alarm = build_anon_map_by_hero_button(
            seats, hh_pos, n_players, hh_stacks)
        if alarm:
            logger.info("[table_ss_deanon] hand %s ÂNCORA alarme=%s → revisão (não escreve)",
                        hand_db_id, alarm)
            return {"status": "review_alarm", "hand_db_id": hand_db_id, "alarm": alarm}
    else:
        anon_map = build_anon_map_from_seats(h, seats, hero_nick)
    if not anon_map:
        return {"status": "no_map", "hand_db_id": hand_db_id}

    vision_data = _seats_to_vision_data(seats, hero_nick)
    enriched_apa = _enrich_all_players_actions(apa_raw, anon_map, vision_data)

    # Guarda UNIVERSAL de consistência (#DESANON-SITTING-OUT-NPLUS1): assere o apa enriquecido
    # vs raw+anon_map. by_order = fallback stack (sem is_button) → sujeito ao C3 img≠HH; a
    # âncora já tem o seu count-abort. block → NÃO escreve (mão para revisão).
    _by_order = not any(s.get("is_button") for s in (seats or []))
    _lvl, _viols = assert_deanon_consistency(
        h.get("raw"), enriched_apa, anon_map,
        vision_seat_count=len(seats or []), by_order=_by_order)
    if _lvl == "block":
        logger.warning("[table_ss_deanon] hand %s CONSISTÊNCIA=%s → revisão (não escreve)",
                       hand_db_id, _viols)
        return {"status": "review_alarm", "hand_db_id": hand_db_id,
                "alarm": "consistency:" + ";".join(_viols)}

    # Afinação Web: flag honesta quando NEM todos os hashes foram mapeados
    # (bancos ambíguos removidos, ou stacks que não chegaram a todos). Hashes
    # por mapear MANTÊM-SE como chave em all_players_actions (não inventamos
    # nomes). A flag fica visível em player_names para a triagem/Vilões.
    total_hh = len([k for k in apa_raw if k != "_meta"])
    deanon_partial = len(anon_map) < total_hh

    player_names_json = {
        "players_list": vision_data["players_list"],
        "hero": hero_nick,
        "anon_map": anon_map,
        "match_method": MATCH_METHOD,
        "source": "table_ss",
        "deanon_partial": deanon_partial,
    }

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE hands SET all_players_actions = %s, player_names = %s "
                "WHERE id = %s",
                (json.dumps(enriched_apa), json.dumps(player_names_json), hand_db_id),
            )
        conn.commit()
    finally:
        conn.close()

    # Vilões pela porta normal (Regra C/D lêem player_names + discord_tags/nick).
    try:
        from app.services.villain_rules import apply_villain_rules
        apply_villain_rules(hand_db_id)
    except Exception as e:  # pragma: no cover - defensivo
        logger.error("apply_villain_rules falhou hand %s: %s", hand_db_id, e)

    logger.info(
        "[table_ss_deanon] hand %s (%s) desanonimizada: %d/%d bancos mapeados",
        hand_db_id, h.get("hand_id"), len(anon_map),
        len([k for k in apa_raw if k != "_meta"]),
    )

    # ── Camada de consistência cross-mão por torneio ────────────────────────
    # Invariante (forense Jun-2026): o hash GG é FIXO por jogador dentro do
    # torneio (0 violações cross-torneio em 1059 hashes; 94% persistem ≥2 mãos).
    # → votar o mapeamento entre TODAS as mãos table_ss do torneio corrige swaps
    # do per-mão (stacks próximos / all-in). Empates ficam por mapear (veneno).
    try:
        tn = h.get("tournament_number") or _hand_tournament_number(hand_db_id)
        if tn:
            reconcile_tournament_deanon(tn)
    except Exception as e:  # pragma: no cover - defensivo
        logger.error("[table_ss_deanon] reconcile torneio falhou hand %s: %s",
                     hand_db_id, e)

    return {"status": "deanonymized", "hand_db_id": hand_db_id,
            "mapped": len(anon_map), "total": total_hh,
            "deanon_partial": deanon_partial, "anon_map": anon_map}


# ── Votação cross-mão por torneio (consistência hash→nick) ───────────────────

def _norm_nick(s: Any) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def cluster_vote(nicks: list[str]) -> tuple[Optional[str], str]:
    """Vota um nick canónico a partir das grafias observadas (1 por mão).

    Agrupa grafias semelhantes (SequenceMatcher ≥ 0.88 — absorve variância OCR
    'justdoitttttt'≈'justdoittttt'). Vencedor = maior cluster com **pluralidade
    estrita** (top > 2º). Empate/sem pluralidade → (None, 'tie') = POR MAPEAR
    (regra do veneno). 1 voto → singleton (mantém-se). Canónico = grafia mais
    frequente no cluster vencedor (desempate: mais longa). Devolve (nick|None, kind).
    """
    clusters: list[dict] = []
    for nk in nicks:
        if not nk:
            continue
        nn = _norm_nick(nk)
        placed = False
        for cl in clusters:
            if SequenceMatcher(None, nn, cl["key"]).ratio() >= 0.88:
                cl["members"].append(nk)
                placed = True
                break
        if not placed:
            clusters.append({"members": [nk], "key": nn})
    if not clusters:
        return None, "none"
    clusters.sort(key=lambda c: -len(c["members"]))
    if len(clusters) > 1 and len(clusters[1]["members"]) == len(clusters[0]["members"]):
        return None, "tie"
    cnt = Counter(clusters[0]["members"])
    canonical = max(cnt.items(), key=lambda kv: (kv[1], len(kv[0])))[0]
    kind = "unanimous" if len(clusters) == 1 else "majority"
    return canonical, kind


def vote_tournament_maps(anon_maps: list[dict]) -> tuple[dict, dict]:
    """anon_maps: lista de mapas hash→nick (1 por mão, inclui 'Hero').
    Devolve (canonical {hash: nick} só para hashes com vencedor, stats por kind).
    'Hero' é votado como um hash normal (nick do herói — consistente)."""
    votes: dict = defaultdict(list)
    for am in anon_maps:
        for hsh, nk in (am or {}).items():
            votes[hsh].append(nk)
    canonical: dict = {}
    stats = {"unanimous": 0, "majority": 0, "tie": 0, "singleton": 0}
    for hsh, nks in votes.items():
        if len(nks) == 1:
            canonical[hsh] = nks[0]
            stats["singleton"] += 1
            continue
        nick, kind = cluster_vote(nks)
        stats[kind if kind in stats else "tie"] += 1
        if nick is not None:
            canonical[hsh] = nick
    return canonical, stats


def _invert_anon_map(anon_map: dict) -> dict:
    """nick→hash a partir de hash→nick (para re-keyar apa de nicks p/ hashes)."""
    inv = {}
    for hsh, nk in (anon_map or {}).items():
        if nk:
            inv[nk] = hsh
    return inv


def _rekey_apa_to_hashes(apa_nick_keyed: dict, anon_map: dict) -> dict:
    """apa com keys=nicks (pós-enrich) → keys=hashes, via inverso do anon_map.
    Preserva '_meta'. Keys sem inverso ficam como estão (best-effort)."""
    inv = _invert_anon_map(anon_map)
    out: dict = {}
    for k, v in (apa_nick_keyed or {}).items():
        if k == "_meta":
            out[k] = v
            continue
        out[inv.get(k, k)] = v
    return out


def _hand_tournament_number(hand_db_id: int) -> Optional[str]:
    from app.db import query
    rows = query("SELECT tournament_number FROM hands WHERE id = %s", (hand_db_id,))
    return rows[0]["tournament_number"] if rows else None


def capture_deanon_agreement() -> dict:
    """Guarda epistémica (Saúde do Import): estado da desanonimização por
    table-SS. Alerta se a fracção de mãos PARCIAIS (algum banco por mapear =
    empates da votação cross-mão) for alta — sinal de que as MAIORIAS colapsam
    (hash-estabilidade a degradar ou Vision pior). Read-only.

    A `agree_rate` por torneio é logada em cada `reconcile_tournament_deanon`;
    aqui dá-se a foto agregada barata a partir do estado guardado."""
    from app.db import query
    rows = query(
        "SELECT (player_names->>'deanon_partial') = 'true' AS partial "
        "FROM hands WHERE site = 'GGPoker' AND (player_names->>'match_method') = %s",
        (MATCH_METHOD,),
    )
    total = len(rows)
    partial = sum(1 for r in rows if r["partial"])
    rate = (partial / total) if total else 0.0
    return {
        "total": total, "complete": total - partial, "partial": partial,
        "partial_rate": round(rate, 3),
        # alerta só com amostra mínima; >35% parciais = maiorias a colapsar.
        "alert": total >= 10 and rate > 0.35,
    }


def reconcile_tournament_deanon(tournament_number: str, *, conn=None) -> dict:
    """Vota o mapeamento hash→nick entre TODAS as mãos `table_ss` do torneio e
    reescreve cada mão com o mapa votado (corrige swaps do per-mão). Empates →
    por mapear + `deanon_partial`. Coerência a jusante: mãos cujo mapa MUDA têm
    `hand_villains` limpos + `apply_villain_rules` re-disparadas (nick novo).
    Idempotente. Devolve stats (incl. concordância, p/ a guarda epistémica)."""
    from app.db import get_conn, query
    from app.routers.screenshot import _enrich_all_players_actions

    rows = query(
        "SELECT id, hand_id, all_players_actions, player_names "
        "FROM hands WHERE tournament_number = %s AND site = 'GGPoker' "
        "AND (player_names->>'match_method') = %s",
        (tournament_number, MATCH_METHOD),
    )
    if not rows:
        return {"tournament": tournament_number, "hands": 0, "changed": 0}

    per_hand = []
    anon_maps = []
    for r in rows:
        pn = r.get("player_names") or {}
        if isinstance(pn, str):
            try:
                pn = json.loads(pn)
            except (ValueError, TypeError):
                pn = {}
        apa = r.get("all_players_actions") or {}
        if isinstance(apa, str):
            try:
                apa = json.loads(apa)
            except (ValueError, TypeError):
                apa = {}
        am = pn.get("anon_map") or {}
        anon_maps.append(am)
        per_hand.append((r["id"], am, apa, pn))

    canonical, stats = vote_tournament_maps(anon_maps)

    own = conn is None
    if own:
        conn = get_conn()
    changed = 0
    try:
        from app.services.villain_rules import apply_villain_rules
        for hand_db_id, old_map, apa, pn in per_hand:
            hash_apa = _rekey_apa_to_hashes(apa, old_map)
            hashes = [k for k in hash_apa if k != "_meta"]
            new_map = {hsh: canonical[hsh] for hsh in hashes if hsh in canonical}
            new_partial = len(new_map) < len(hashes)
            if new_map == (old_map or {}) and bool(pn.get("deanon_partial")) == new_partial:
                continue  # nada mudou nesta mão
            vision_data = {"players_list": pn.get("players_list") or []}
            new_apa = _enrich_all_players_actions(hash_apa, new_map, vision_data)
            new_pn = {**pn, "anon_map": new_map, "deanon_partial": new_partial}
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE hands SET all_players_actions = %s, player_names = %s WHERE id = %s",
                    (json.dumps(new_apa), json.dumps(new_pn), hand_db_id),
                )
                # Coerência a jusante: limpa vilões do nick antigo desta mão…
                cur.execute("DELETE FROM hand_villains WHERE hand_db_id = %s", (hand_db_id,))
            apply_villain_rules(hand_db_id, conn=conn)  # …e re-cria com o nick votado
            changed += 1
        if own:
            conn.commit()
    finally:
        if own:
            conn.close()

    # Guarda epistémica: concordância (alerta se as maiorias colapsarem).
    multi = stats["unanimous"] + stats["majority"] + stats["tie"]
    agree_rate = (stats["unanimous"] + stats["majority"]) / multi if multi else 1.0
    logger.info(
        "[table_ss_reconcile_vote] tn=%s hands=%d changed=%d "
        "unanimous=%d majority=%d tie=%d singleton=%d agree=%.2f",
        tournament_number, len(rows), changed, stats["unanimous"],
        stats["majority"], stats["tie"], stats["singleton"], agree_rate,
    )
    # APA §B.6 Fase 3: mudou a desanon deste torneio → re-espalha os nomes por hash
    # nas tagadas (F&F, idempotente, respeita a quarentena). Nunca parte o reconcile.
    if changed:
        try:
            from app.services.name_propagation import trigger_name_propagation
            trigger_name_propagation(tournament_number)
        except Exception:
            logger.exception("[table_ss_reconcile] trigger name_propagation falhou tn=%s",
                             tournament_number)

    return {"tournament": tournament_number, "hands": len(rows), "changed": changed,
            "stats": stats, "agree_rate": round(agree_rate, 3)}
