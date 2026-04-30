"""
Serviço de processamento de mãos.
Liga entries a hands: extrai mãos de uma entry e insere-as na tabela hands.
"""
import json
import re
from app.db import get_conn, query, execute_returning
from app.parsers.gg_hands import parse_hands


# ─── Tech Debt #4: classificar villain em A∨B∨C∨D ────────────────────────────

# Hash GG anonimizado: 6-8 hex chars (ex: "697d60de", "53e253c7", "ed861052").
# Nicks reais nunca correspondem a este padrão estrito.
_ANON_HASH_RE = re.compile(r'^[0-9a-f]{6,8}$')


def _is_anon_hash(nick: str | None) -> bool:
    """True se `nick` parece ser hash GG anonimizado (sem match SS)."""
    if not nick:
        return True
    return bool(_ANON_HASH_RE.match(nick.strip().lower()))


def _classify_villain_categories(
    hand_meta: dict,
    villain_nick: str,
    has_cards: bool,
    has_vpip: bool,
) -> list[str]:
    """
    Aplica regras canónicas A∨C∨D, devolve as categorias aplicáveis a
    um par (hand, villain) para Tech Debt #4 (re-arquitectura página Vilões).

    Regras:
        A — hm3_tags contém tag ~ 'nota%'                        → 'nota'
        C — 'nota' em discord_tags + match real válido            → 'nota'
        D — villain_nick em FRIEND_HEROES (Karluz/flightrisk)     → 'friend'

    Tech Debt #B8 (29-Abr pt7): regra B (showdown automático →
    'sd') removida. Era falso positivo: 22/22 cat='sd' em FASE 1
    eram criados sem tag 'nota' (sample: NemoTT mostrou cards em
    icm-pko mas Rui não tinha marcado a mão para estudo). Regra de
    negócio real é "tag 'nota' explícita → entra em Vilões";
    showdown sem tag não interessa. Cards continuam visíveis no
    apa para qualquer caller.

    Filosofia "nota" inclusiva: villain criado para non-hero com VPIP
    preflop OU showdown cards (não exige ambos).

    Pré-condições (caller responsável):
      - villain_nick NÃO em HERO_NAMES (Rui aliases puros).
      - villain_nick NÃO é hash anónimo (_is_anon_hash False).
      - has_cards e/ou has_vpip True (caso contrário devolve []).

    Args:
      hand_meta: dict com keys hm3_tags, discord_tags, has_showdown,
                 match_method (todos opcionais — função tolera ausência).
      villain_nick: nick do villain (case preservado para INSERT).
      has_cards: villain mostrou cards no showdown.
      has_vpip: villain entrou em VPIP preflop (call/raise/bet).

    Returns:
      Lista ordenada de categorias (set→sorted) — INSERT determinístico.
      [] se nem VPIP nem cards (não é villain a registar).
    """
    # #B19 (REGRAS_NEGOCIO.md §3.3 + caso canónico 2): excepção à pré-condição.
    # Quando a mão tem tag HM3 'nota%' (intenção explícita do Rui de marcar
    # villain), aceitar non-hero sem VPIP nem cards — basta ter sido adicionado
    # pelo alargamento postflop em mtt._create_villains_for_hand. Apenas para
    # tag HM3 'nota%'; Discord e outros casos mantêm pré-condição original.
    hm3_tags_for_gate = hand_meta.get('hm3_tags') or []
    has_hm3_nota = any((t or '').lower().startswith('nota') for t in hm3_tags_for_gate)
    if not (has_cards or has_vpip) and not has_hm3_nota:
        return []

    from app.hero_names import FRIEND_HEROES

    cats: set[str] = set()
    mm = (hand_meta.get('match_method') or '')
    has_real_match = bool(mm) and not mm.startswith('discord_placeholder_')
    nick_lower = villain_nick.lower().strip()

    # D — friend (Karluz/flightrisk como villain quando aparecem em mãos do Rui)
    if nick_lower in FRIEND_HEROES:
        cats.add('friend')

    # A — HM3 tag começa por 'nota'
    hm3_tags = hand_meta.get('hm3_tags') or []
    if any((t or '').startswith('nota') for t in hm3_tags):
        cats.add('nota')

    # C — Discord canal #nota + match real
    discord_tags = hand_meta.get('discord_tags') or []
    if 'nota' in discord_tags and has_real_match:
        cats.add('nota')

    return sorted(cats)


# ─── Tech Debt #5: pré-resolver hashes GG anonimizados no raw HH ─────────────

_SEAT_RE = re.compile(r'Seat (\d+): (.+?) \(')


def _resolve_hashes_in_raw(raw: str | None, apa: dict | None) -> str | None:
    """
    Pré-resolve hashes GG anonimizados (`3d454afe`, etc.) no raw HH para os
    nicks reais que estão em `all_players_actions`.

    O cliente (HandDetailPage.jsx) já tenta fazer este mapping, mas há um
    bug visual em que apenas `Hero` é resolvido — os outros 6/7 hashes
    aparecem literalmente na secção HAND HISTORY apesar do algoritmo
    parecer correcto. Mover a resolução para o backend elimina dependência
    de cache/build state do frontend e dá garantia determinística.

    Args:
        raw: string HH original (ex: "Seat 2: ed861052 (18,804 in chips)\n...")
        apa: all_players_actions JSONB — keys são nicks reais com info.seat

    Returns:
        raw com hashes substituídos por nicks. Se `name_map` ficar vazio
        (apa sem seats), devolve raw original sem alterações. Hashes que
        não estejam no map são mantidos (não há substituição aleatória).

    Bordas tratadas (cobre todos os locais onde GG escreve o nome do
    jogador no HH):
      - "Seat N: <hash> ("
      - "<hash>: " (action lines)
      - "Dealt to <hash>"
      - "<hash> shows"
      - "<hash> collected"
      - "<hash> mucks"
      - "Uncalled bet (...) returned to <hash>"
    """
    if not raw or not apa:
        return raw

    # 1) Construir name_map cruzando "Seat N: <hash>" com apa[name].seat
    seat_to_real = {}
    for name, info in apa.items():
        if name == "_meta" or not isinstance(info, dict):
            continue
        seat = info.get("seat")
        if isinstance(seat, int):
            seat_to_real[seat] = name

    name_map: dict[str, str] = {}
    for m in _SEAT_RE.finditer(raw):
        seat_num = int(m.group(1))
        anon_name = m.group(2).strip()
        real_name = seat_to_real.get(seat_num)
        if real_name and real_name != anon_name:
            name_map[anon_name] = real_name

    if not name_map:
        return raw

    # 2) Substituição segura por hash. Ordem desc por comprimento evita
    #    substring conflicts (ex: hash que é prefixo de outro).
    resolved = raw
    for anon in sorted(name_map.keys(), key=len, reverse=True):
        real = name_map[anon]
        # Word boundary defensivo: hash seguido por ":", " ", "(" ou
        # antecedido por "to ", "Seat N: ", início de linha, etc.
        # Usamos lookbehind para "Dealt to ", "returned to "; padrão
        # geral cobre o resto.
        # Escape do anon (pode ter caracteres ., ! como nicks Vision).
        anon_esc = re.escape(anon)
        # (?<![\w.]) e (?![\w.]) — boundaries que tratam '.' como parte
        # do nick (nicks Vision podem terminar em ".." truncados).
        pattern = rf'(?<![\w.]){anon_esc}(?![\w.])'
        resolved = re.sub(pattern, real, resolved)

    return resolved


def _get_or_create_tournament_pk(conn, tournament_id_str: str, site: str) -> int | None:
    """
    Dado o tournament_id string do parser (ex: "1234567"),
    devolve o PK da tabela tournaments (ou None se não existir).
    """
    if not tournament_id_str:
        return None
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM tournaments WHERE tid = %s AND site ILIKE %s",
            (tournament_id_str, f"%{site}%")
        )
        row = cur.fetchone()
        if row:
            return row["id"]
    return None


import logging
logger = logging.getLogger("hand_service")

def _insert_hand(conn, h: dict, entry_id: int | None, tournament_pk: int | None = None, study_state: str = 'mtt_archive', origin: str | None = None) -> bool:
    """Insere uma mão na BD. Retorna True se inserida, False se duplicada."""
    placeholder_metadata = None
    with conn.cursor() as cur:
        if h["hand_id"]:
            logger.info(f"[_insert_hand] Processando hand_id: {h['hand_id']}")
            cur.execute(
                """
                SELECT id, raw, hm3_tags,
                       origin, discord_tags, entry_id AS placeholder_entry_id,
                       player_names, screenshot_url, tags
                FROM hands WHERE hand_id = %s
                """,
                (h["hand_id"],),
            )
            existing = cur.fetchone()
            if existing:
                logger.info(f"[_insert_hand] hand_id {h['hand_id']} já existe. ID: {existing['id']}, raw_len: {len(existing['raw']) if existing['raw'] else 0}, tags: {existing['hm3_tags']}")
                # Se for placeholder (raw vazio + marker de placeholder), apaga-o para dar
                # lugar à HH real. Captura metadados antes do DELETE para reaplicar via
                # UPDATE pós-INSERT — senão perdíamos origin, discord_tags, entry_id,
                # player_names (Vision) e screenshot_url.
                #
                # Marker canónico: player_names.match_method LIKE 'discord_placeholder_%'.
                # Fallbacks preservados para compat com rows antigos: GGDiscord em hm3_tags
                # (legado Discord) e SSMatch em tags (legado SS upload).
                existing_pn = existing.get("player_names") or {}
                if isinstance(existing_pn, str):
                    try:
                        existing_pn = json.loads(existing_pn)
                    except (ValueError, TypeError):
                        existing_pn = {}
                existing_mm = existing_pn.get("match_method", "") if isinstance(existing_pn, dict) else ""
                is_placeholder = (
                    (not existing["raw"] or existing["raw"].strip() == "")
                    and (
                        existing_mm.startswith("discord_placeholder_")
                        or "GGDiscord" in (existing["hm3_tags"] or [])
                        or "SSMatch" in (existing["tags"] or [])
                    )
                )
                if is_placeholder:
                    logger.info(f"[_insert_hand] hand_id {h['hand_id']} é placeholder (mm={existing_mm!r}, hm3_tags={existing['hm3_tags']}, tags={existing['tags']}). Capturando metadados antes do DELETE.")
                    # Stripar placeholder marker: HH real agora presente, mas preserva
                    # dados Vision (hero, board, players_list). Sem isto, a hand canonical
                    # ficaria com match_method='discord_placeholder_*' e continuaria
                    # excluída de Estudo pelo STUDY_VIEW_GG_MATCH_FILTER.
                    pn_clean = dict(existing_pn) if isinstance(existing_pn, dict) else {}
                    if pn_clean.get("match_method", "").startswith("discord_placeholder_"):
                        if pn_clean.get("players_list"):
                            # Há dados Vision → upgrade para marker de match real.
                            pn_clean["match_method"] = "anchors_stack_elimination_v2"
                        else:
                            pn_clean.pop("match_method", None)
                    placeholder_metadata = {
                        "origin": existing.get("origin"),
                        "discord_tags": existing.get("discord_tags"),
                        "hm3_tags": existing.get("hm3_tags"),
                        "entry_id": existing.get("placeholder_entry_id"),
                        "player_names": pn_clean,
                        "screenshot_url": existing.get("screenshot_url"),
                        "tags": existing.get("tags"),
                    }
                    cur.execute("DELETE FROM hands WHERE id = %s", (existing["id"],))
                else:
                    logger.info(f"[_insert_hand] hand_id {h['hand_id']} NÃO é placeholder. Ignorando (duplicado).")
                    return False
            else:
                logger.info(f"[_insert_hand] hand_id {h['hand_id']} é novo. A inserir.")

        all_actions = h.get("all_players_actions")
        all_actions_json = json.dumps(all_actions) if all_actions else None

        # Detect showdown: any non-hero player with cards shown
        has_showdown = False
        if isinstance(all_actions, dict):
            for p, pdata in all_actions.items():
                if p == "_meta":
                    continue
                if isinstance(pdata, dict) and not pdata.get("is_hero") and pdata.get("cards"):
                    has_showdown = True
                    break

        # Resolve tournament_pk from the hand's tournament_id string if not provided
        t_pk = tournament_pk
        if t_pk is None and h.get("tournament_id"):
            t_pk = _get_or_create_tournament_pk(conn, h["tournament_id"], h.get("site", ""))

        cur.execute(
            """
            INSERT INTO hands
                (site, hand_id, played_at, stakes, position,
                 hero_cards, board, result, currency,
                 raw, entry_id, study_state, all_players_actions, tournament_id,
                 has_showdown, buy_in, tournament_format, tournament_name, tournament_number, origin)
            VALUES
                (%(site)s, %(hand_id)s, %(played_at)s, %(stakes)s, %(position)s,
                 %(hero_cards)s, %(board)s, %(result)s, %(currency)s,
                 %(raw)s, %(entry_id)s, %(study_state)s, %(all_players_actions)s, %(tournament_id)s,
                 %(has_showdown)s, %(buy_in)s, %(tournament_format)s, %(tournament_name)s, %(tournament_number)s, %(origin)s)
            """,
            {
                "site": h["site"],
                "hand_id": h["hand_id"],
                "played_at": h["played_at"],
                "stakes": h["stakes"],
                "position": h["position"],
                "hero_cards": h["hero_cards"] or [],
                "board": h["board"] or [],
                "result": h["result"],
                "currency": h["currency"],
                "raw": h.get("raw", ""),
                "entry_id": entry_id,
                "study_state": study_state,
                "all_players_actions": all_actions_json,
                "tournament_id": t_pk,
                "has_showdown": has_showdown,
                "buy_in": h.get("buy_in"),
                "tournament_format": h.get("tournament_format"),
                # tournament_name: nome real limpo devolvido pelo parser GG.
                # tournament_number: string crua do raw; o parser GG chama-lhe
                # "tournament_id" por historia, mas o valor string vai para
                # a coluna nova hands.tournament_number TEXT. A coluna FK
                # hands.tournament_id BIGINT continua a receber o t_pk resolvido.
                "tournament_name": h.get("tournament_name"),
                "tournament_number": h.get("tournament_id"),
                "origin": origin,
            },
        )

        # Reaplica metadados do placeholder Discord (se aplicável).
        # COALESCE normal para campos onde queremos preservar o que o INSERT já escreveu;
        # reverse COALESCE em entry_id para preferir a entry Discord (primeira fonte no ciclo).
        if placeholder_metadata:
            logger.info(f"[_insert_hand] Reaplicando metadados Discord do placeholder para hand_id {h['hand_id']}.")
            cur.execute(
                """
                UPDATE hands SET
                    -- reverse COALESCE em origin: preserva o origin do placeholder (ex: 'discord')
                    -- sobre o que o INSERT acabou de escrever (ex: 'hh_import' vindo de ZIP import).
                    -- Regra: primeiro ingress ganha no campo scalar origin; outras fontes ficam
                    -- rastreáveis via discord_tags / hm3_tags.
                    origin         = COALESCE(%(origin)s, origin),
                    -- NULLIF obrigatório nas colunas TEXT[]: schema default é ARRAY[]::text[]
                    -- (empty, não NULL). COALESCE nu preserva o array vazio do INSERT e
                    -- descarta o valor do placeholder. Com NULLIF, empty-array → NULL →
                    -- COALESCE cai no placeholder_metadata.
                    discord_tags   = COALESCE(NULLIF(discord_tags, ARRAY[]::text[]), %(discord_tags)s),
                    -- hm3_tags: preservar + strip 'GGDiscord' (marker interno de placeholder
                    -- Discord, não deve persistir no row final). Se hm3_tags real for None,
                    -- array_remove aplica-se a '{}' que é no-op.
                    hm3_tags       = array_remove(
                                        COALESCE(NULLIF(hm3_tags, ARRAY[]::text[]), %(hm3_tags)s),
                                        'GGDiscord'
                                     ),
                    entry_id       = COALESCE(%(placeholder_entry_id)s, entry_id),
                    player_names   = COALESCE(player_names, %(player_names)s),
                    screenshot_url = COALESCE(screenshot_url, %(screenshot_url)s),
                    -- tags: manter pattern aditivo (merge dedup), com NULLIF defensivo
                    -- nos dois lados para normalizar empty-array → NULL antes do COALESCE.
                    tags           = ARRAY(SELECT DISTINCT unnest(
                                        COALESCE(NULLIF(tags, ARRAY[]::text[]), '{}'::text[])
                                        || COALESCE(NULLIF(%(tags)s, ARRAY[]::text[]), '{}'::text[])
                                     ))
                WHERE hand_id = %(hand_id)s
                """,
                {
                    "origin": placeholder_metadata["origin"],
                    "discord_tags": placeholder_metadata["discord_tags"],
                    "hm3_tags": placeholder_metadata["hm3_tags"],
                    "placeholder_entry_id": placeholder_metadata["entry_id"],
                    "player_names": json.dumps(placeholder_metadata["player_names"]) if placeholder_metadata["player_names"] else None,
                    "screenshot_url": placeholder_metadata["screenshot_url"],
                    "tags": placeholder_metadata["tags"],
                    "hand_id": h["hand_id"],
                },
            )
        return True


def process_entry_to_hands(entry_id: int) -> dict:
    """
    Processa uma entry do tipo hand_history e cria as mãos correspondentes.
    Retorna um resumo: { inserted, skipped, errors }
    """
    rows = query("SELECT * FROM entries WHERE id = %s", (entry_id,))
    if not rows:
        return {"inserted": 0, "skipped": 0, "errors": ["Entry não encontrada"]}

    entry = rows[0]

    if entry["entry_type"] != "hand_history":
        return {"inserted": 0, "skipped": 0, "errors": ["Entry não é hand_history"]}

    raw_text = entry.get("raw_text") or ""
    file_name = entry.get("file_name") or "unknown"

    content = raw_text.encode("utf-8")
    parsed_hands, parse_errors = parse_hands(content, file_name)

    inserted = 0
    skipped = 0

    conn = get_conn()
    try:
        for h in parsed_hands:
            ok = _insert_hand(conn, h, entry_id)
            if ok:
                inserted += 1
            else:
                skipped += 1

        # Actualizar o estado da entry
        new_status = "processed" if not parse_errors else (
            "partial" if inserted > 0 else "failed"
        )
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE entries SET status = %s WHERE id = %s",
                (new_status, entry_id)
            )

        conn.commit()
    except Exception as e:
        conn.rollback()
        parse_errors.append(f"Erro de BD: {e}")
    finally:
        conn.close()

    return {
        "entry_id": entry_id,
        "inserted": inserted,
        "skipped": skipped,
        "errors": parse_errors,
    }


# ─── Append discord_tags helper (#B12, pt9) ──────────────────────────────────

def append_discord_channel_to_hand(hand_db_id: int, entry_id: int) -> dict:
    """
    Faz append idempotente do canal Discord (resolvido a partir de entry_id)
    a hands.discord_tags, e marca a entry como resolved.

    Regra de negócio (docs/VISAO_PRODUTO.md, secção "Regra de cross-post
    Discord"): toda mão que apareça num canal Discord deve ter o nome desse
    canal em discord_tags. Cross-post em N canais → discord_tags com N nomes.
    Idempotência via DISTINCT unnest (chamadas repetidas não duplicam canal).

    Single source of truth para append discord_tags. Chamado por:
      - routers/discord.py::backfill_ggdiscord (cross-post replayer_link
        cuja hand já existe).
      - routers/screenshot.py::_link_second_discord_entry_to_existing_hand
        (cross-post via Vision SS pipeline).

    NÃO dispara regra C villain — quem precisar chama
    _maybe_create_rule_c_villain_for_hand em separado.

    Devolve: {"channel_added": str|None, "discord_tags": list[str], "resolved": bool}.
    Em caso de excepção: rollback, log, devolve resolved=False.
    """
    from app.discord_bot import _resolve_channel_name_for_entry

    channel = _resolve_channel_name_for_entry(entry_id)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if channel:
                cur.execute(
                    """UPDATE hands SET
                         discord_tags = ARRAY(SELECT DISTINCT unnest(
                           COALESCE(discord_tags, '{}'::text[]) || %s::text[]
                         ))
                       WHERE id = %s
                       RETURNING discord_tags""",
                    ([channel], hand_db_id),
                )
            else:
                cur.execute(
                    "SELECT discord_tags FROM hands WHERE id = %s",
                    (hand_db_id,),
                )
            row = cur.fetchone()
            cur.execute(
                "UPDATE entries SET status = 'resolved' WHERE id = %s",
                (entry_id,),
            )
        conn.commit()
        result_tags = list(row["discord_tags"]) if row and row["discord_tags"] else []
        logger.info(
            f"append_discord_channel_to_hand: hand={hand_db_id} entry={entry_id} "
            f"channel={channel} discord_tags={result_tags}"
        )
        return {
            "channel_added": channel,
            "discord_tags": result_tags,
            "resolved": True,
        }
    except Exception as e:
        conn.rollback()
        logger.error(
            f"append_discord_channel_to_hand failed hand={hand_db_id} entry={entry_id}: {e}"
        )
        return {"channel_added": None, "discord_tags": [], "resolved": False}
    finally:
        conn.close()
