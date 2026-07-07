"""#FT-PROPAGATION — Propagação de FT (mesa final) por torneio.

O `players_left` só DESCE (jogadores só saem) → a partir do instante em que os que
restam <= tamanho da mesa final, é FT até ao fim. Este consumidor traça essa
FRONTEIRA por torneio e marca todas as mãos com `played_at >= fronteira`,
corrigindo a tag base → a sua `-ft` (icm→icm-ft, pos-pko→pos-pko-ft, …). A mão sai
do conflito de FASE e volta aos canais normais com a tag certa.

Fontes da fronteira, por prioridade:
  (a) PRINT DE LOBBY com a aba **Info** aberta (convenção 7 Jul) — é a aba onde se
      lê "N players at the final table"; o `posted_at` desse print É a fronteira e o
      `final_table_size` é o N. Prints de OUTRAS abas (Players/Prize Pool) NUNCA
      ancoram (um Prize Pool com poucos restantes já é FT-a-decorrer, não o
      arranque). MANDA onde existe (proveniência 'propagated_lobby').
  (b) Sem print do Info → players_left das capturas IT, com SALVAGUARDA DE
      COERÊNCIA: só traça se o players_left descer de forma coerente (um valor
      isolado mal lido quebra o padrão → rejeita e SINALIZA, não corrige). Fronteira
      = o 1º momento `_ft_applies` (ocupados==restantes); N = o players_left desse
      momento. Proveniência 'propagated_coherent'.

CROSS-CHECK (Adição 1, D2): o N (via a: `final_table_size`; via b: `players_left` da
fronteira) cruza-se com os SENTADOS da 1ª mão GG >= fronteira (devem bater). Vive em
`cross_check` do resultado; NÃO bloqueia nesta fase — quem decide quarentena é a F3.

Puro quanto a escritas em modo dry_run (só lê). Idempotente: re-correr recomputa de
raiz e o `-ft` não duplica (fail-safe). Reusa: lobby_processing_log (players_left,
tournament_number, posted_at), table_ss_processing_log.players_left via
hands.context_table_ss_id, hands.tournament_number/played_at, tags_canonical.
"""
from __future__ import annotations

import logging
import re
from datetime import timedelta
from typing import Optional

from app.db import query, get_conn
from app.services.tags_canonical import canonicalize_tag

logger = logging.getLogger("ft_boundary")

# players_left <= FT_CAP num LOBBY ⇒ FT (cobre até mesa final de 9 lugares).
FT_CAP = 9
# Tolerância de jitter da Vision na verificação de coerência (fonte b).
COHERENCE_TOL = 2
# Janela do SNAP-TO-N: recuar até 3 min da fronteira computada à procura da 1ª mão
# REAL da FT (sentados == N). Cobre os gaps observados (38-51 s) com folga sem
# apanhar a mesa PRÉ-FT do Hero (a ~5-6 min, com contagens diferentes).
SNAP_WINDOW_MIN = 3

# Tags-spot BASE que têm variante de fase '-ft' (formas canónicas). A '-ft' é
# mudança de FASE, ortogonal ao FORMATO → converter base→-ft NUNCA muda PKO/não-PKO
# (logo nunca nasce conflito de 'formato').
FT_BASE_SPOTS = frozenset({"icm", "icm-pko", "pos-pko", "pos-nko", "speed-racer"})

# Contagem canónica de sentados de uma HH GG (fonte ÚNICA, F2 — o router gg-health
# importa daqui). Linhas `Seat N:` do BLOCO DE SEATS (antes de HOLE CARDS); ignora
# o bloco `*** SUMMARY ***` (senão contava a dobrar).
_SEAT_RE = re.compile(r"(?m)^Seat \d+:")


def count_hh_seats(raw) -> Optional[int]:
    """Nº de sentados de uma HH GG = linhas `Seat N:` do bloco inicial. None se sem
    raw/legível."""
    if not raw or not isinstance(raw, str):
        return None
    head = raw.split("*** HOLE CARDS ***", 1)[0]
    if head == raw:                       # sem esse marcador → corta no 1º "*** "
        idx = raw.find("*** ")
        head = raw[:idx] if idx != -1 else raw
    return len(_SEAT_RE.findall(head)) or None


# ── Detetor FT (réplica pura do _ft_applies do router, p/ evitar import circular) ─
def _ft_applies(vision_json) -> bool:
    """FT = nº de bancos OCUPADOS (com nick) == players_left, ambos da Vision.
    Fail-safe: qualquer um ausente/0 → False."""
    if not isinstance(vision_json, dict):
        return False
    seats = vision_json.get("seats") or []
    occupied = [s for s in seats if isinstance(s, dict) and (s.get("nick") or "").strip()]
    pl = vision_json.get("players_left")
    return (bool(occupied) and isinstance(pl, int) and not isinstance(pl, bool)
            and pl > 0 and len(occupied) == pl)


# ── Fronteira ────────────────────────────────────────────────────────────────
def _manual_ft_boundary(tn: str):
    """Fonte (0) PRIMÁRIA (arquitetura 7 Jul) — 1ª mão GG do torneio com tag `-ft`
    MANUAL do Rui: `folder_ft_source = 'manual'` (a PASTA do IT chamava-se `-ft`, ex.
    "ICM PKO FT" → mesa final CONFIRMADA à mão; ver `_folder_tag_ft_source` em
    `table_ss.py`). Devolve o `played_at` dessa mão, ou None. **Não-circular:** exclui
    o `-ft` `'auto'` (adivinhado pela Vision OU pela nossa propagação). O snap-to-N
    refina para trás (apanha as 2-3 mãos jogadas antes de o Rui marcar)."""
    rows = query(
        """SELECT MIN(played_at) AS b FROM hands
            WHERE site='GGPoker' AND tournament_number = %s
              AND folder_ft_source = 'manual'""",
        (tn,),
    )
    return rows[0]["b"] if rows and rows[0]["b"] else None


def _lobby_ft_boundary(tn: str):
    """Fonte (a) — CONVENÇÃO 7 Jul: só o print de lobby com a aba **Info** aberta
    marca o ARRANQUE da FT (é onde se lê 'N players at the final table'). Devolve
    (posted_at, N=final_table_size) do print Info mais cedo com N legível; (None,
    None) se não houver. Prints de outras abas (Players/Prize Pool) NUNCA ancoram.

    O gate é `open_tab='Info'` + `final_table_size` legível (guarda `~ '^[0-9]+$'`
    antes do cast → um valor malformado da Vision nunca rebenta a query)."""
    rows = query(
        """SELECT posted_at,
                  (vision_json->>'final_table_size')::int AS n
             FROM lobby_processing_log
            WHERE tournament_number = %s
              AND posted_at IS NOT NULL
              AND vision_json->>'open_tab' = 'Info'
              AND vision_json->>'final_table_size' ~ '^[0-9]+$'
            ORDER BY posted_at ASC
            LIMIT 1""",
        (tn,),
    )
    if rows and rows[0]["posted_at"]:
        return rows[0]["posted_at"], rows[0]["n"]
    return None, None


def _it_readings(tn: str) -> list[dict]:
    """(played_at, players_left, vision_json) das mãos GG do torneio com captura IT
    ligada e players_left lido, ordenadas por played_at."""
    return [dict(r) for r in query(
        """SELECT h.played_at, l.players_left, l.vision_json
             FROM hands h
             JOIN table_ss_processing_log l ON l.id = h.context_table_ss_id
            WHERE h.site='GGPoker' AND h.tournament_number = %s
              AND l.players_left IS NOT NULL
            ORDER BY h.played_at ASC""",
        (tn,),
    )]


def _monotone_noninc(pls: list[int]) -> bool:
    """Sequência não-crescente dentro de COHERENCE_TOL (jitter da Vision)."""
    for k in range(1, len(pls)):
        if pls[k] > pls[k - 1] + COHERENCE_TOL:
            return False
    return True


def _coherent_readings(readings: list[dict]) -> tuple[list[dict], bool]:
    """DESCARTA um OUTLIER ISOLADO (um players_left que SOBE — fisicamente
    impossível, os jogadores só descem) e usa a tendência coerente do resto.

    Coerente se: já é monótona-decrescente, OU fica monótona removendo UM ponto
    (o outlier isolado — devolve o resto). Se precisar remover 2+ (vários saltos,
    sem tendência clara) → genuinamente incoerente → (readings, False)."""
    vals = [r for r in readings if isinstance(r.get("players_left"), int)]
    pls = [r["players_left"] for r in vals]
    if len(pls) <= 1 or _monotone_noninc(pls):
        return vals, True
    for i in range(len(pls)):
        if _monotone_noninc(pls[:i] + pls[i + 1:]):
            return vals[:i] + vals[i + 1:], True   # descarta o outlier isolado
    return vals, False                             # vários saltos → incoerente


def _post_peak_tail(readings: list[dict]) -> list[dict]:
    """Q-A (política 7 Jul) — corta as leituras à **CAUDA DESCENDENTE PÓS-PICO**. O
    PICO do players_left = fecho do late-reg (com re-entradas, o pico FINAL); a
    subida ANTES do pico é vida normal do torneio, NÃO incoerência. Devolve as
    leituras do ÚLTIMO pico em diante (dentro da cauda mantém-se o rigor do
    `_coherent_readings`: descarte de 1 outlier, incoerente com 2+ saltos)."""
    vals = [r for r in readings
            if isinstance(r.get("players_left"), int) and not isinstance(r.get("players_left"), bool)]
    if len(vals) <= 1:
        return vals
    mx = max(r["players_left"] for r in vals)
    peak = max(i for i, r in enumerate(vals) if r["players_left"] == mx)  # último pico
    return vals[peak:]


def _it_ft_boundary(tn: str):
    """Fonte (b): (fronteira, coerente, N). Avalia SÓ a cauda descendente pós-pico
    (Q-A); dentro dela descarta o outlier isolado; fronteira = 1º played_at (entre
    os readings COERENTES) onde _ft_applies e N = o `players_left` desse momento
    (D2: N da fronteira = tamanho da FT). Cauda genuinamente incoerente →
    (None, False, None) [sinaliza, não corrige]."""
    readings = _it_readings(tn)
    if not readings:
        return None, True, None               # sem dados: coerente-vazio, sem fronteira
    tail = _post_peak_tail(readings)           # Q-A: só a cauda pós-pico (late-reg)
    kept, coherent = _coherent_readings(tail)
    if not coherent:
        return None, False, None
    for r in kept:                             # kept preserva ordem (played_at)
        if _ft_applies(r["vision_json"] or {}):
            return r["played_at"], True, r["players_left"]
    return None, True, None


# ── Cross-check HH (Adição 1, D2) ─────────────────────────────────────────────
def _first_hand_seats_after(tn: str, boundary) -> Optional[int]:
    """Sentados da 1ª mão GG do torneio com played_at >= fronteira. None se não
    houver mão ou o raw for ilegível."""
    rows = query(
        """SELECT raw FROM hands
            WHERE site='GGPoker' AND tournament_number = %s
              AND played_at >= %s
            ORDER BY played_at ASC LIMIT 1""",
        (tn, boundary),
    )
    return count_hh_seats(rows[0]["raw"]) if rows else None


def _cross_check(tn: str, boundary, n) -> dict:
    """Cruza o N (mesa final) com os sentados da 1ª mão GG pós-fronteira. match=True
    sse ambos legíveis e iguais; qualquer um ilegível → match=None (sem veredicto, não
    bloqueia — a decisão de quarentena é F3)."""
    hh_seats = _first_hand_seats_after(tn, boundary)
    match = (hh_seats == n) if (n is not None and hh_seats is not None) else None
    return {"n": n, "hh_seats": hh_seats, "match": match}


# ── SNAP-TO-N (política da fronteira, 7 Jul) ─────────────────────────────────
def _starts_drainage(seats_from_here: list, n: int) -> bool:
    """A sequência de sentados a partir de um candidato INICIA a drenagem da FT?
    True sse o 1º == N e a sequência (ignorando ilegíveis) é NÃO-CRESCENTE — a FT só
    perde jogadores (7→6→5…); a mesa PRÉ-FT do Hero volta a SUBIR (…3→7) → quebra."""
    vals = [s for s in seats_from_here if isinstance(s, int)]
    if not vals or vals[0] != n:
        return False
    return all(b <= a for a, b in zip(vals, vals[1:]))


def _infer_ft_size(tn: str, boundary) -> Optional[int]:
    """N inferido para a fonte (0) quando NÃO há lobby Info: o MÁX. de sentados na
    janela do snap [boundary−3min, boundary] = tamanho de ARRANQUE da FT (a FT só
    drena; a 1ª mão tem o máximo). None se sem mãos legíveis na janela."""
    if boundary is None:
        return None
    lo = boundary - timedelta(minutes=SNAP_WINDOW_MIN)
    rows = query(
        "SELECT raw FROM hands WHERE site='GGPoker' AND tournament_number = %s "
        "AND played_at >= %s AND played_at <= %s", (tn, lo, boundary))
    seats = [s for s in (count_hh_seats(r["raw"]) for r in rows) if isinstance(s, int)]
    return max(seats) if seats else None


def _far_apart(a, b) -> bool:
    """Dois momentos apontam a FT em instantes INCOMPATÍVEIS (para lá da janela do
    snap)? Wall-clock em segundos (naive de hands e tz de lobby coexistem → normaliza
    a naive). Defensivo: erro → False (não bloqueia por engano)."""
    try:
        a = a.replace(tzinfo=None) if getattr(a, "tzinfo", None) else a
        b = b.replace(tzinfo=None) if getattr(b, "tzinfo", None) else b
        return abs((a - b).total_seconds()) > SNAP_WINDOW_MIN * 60
    except Exception:
        return False


def _snap_to_n(tn: str, boundary, n):
    """SNAP-TO-N — a fronteira computada (via-a print / via-b coherent) cai ~1 mão
    TARDE (o sinal chega segundos depois de a FT arrancar). Recua até
    `SNAP_WINDOW_MIN` e devolve o played_at da mão MAIS CEDO com `sentados == N` que
    INICIA a drenagem (==N seguida de mãos ≤N). Se não houver → devolve a fronteira
    computada (fallback Q-B: segue para o cross-check normal → mismatch → quarentena
    F3/F4, nunca promove às cegas)."""
    if not isinstance(n, int) or isinstance(n, bool) or n <= 0 or boundary is None:
        return boundary
    lo = boundary - timedelta(minutes=SNAP_WINDOW_MIN)
    rows = query(
        """SELECT played_at, raw FROM hands
            WHERE site='GGPoker' AND tournament_number = %s
              AND played_at >= %s AND played_at <= %s
            ORDER BY played_at ASC""",
        (tn, lo, boundary),
    )
    seats = [count_hh_seats(r["raw"]) for r in rows]
    for i in range(len(rows)):
        if _starts_drainage(seats[i:], n):
            return rows[i]["played_at"]
    return boundary                            # sem mão ==N na janela → fallback


def compute_ft_boundary(tn: str) -> dict:
    """Fronteira do torneio, fonte (a) MANDA sobre (b). Devolve
    {boundary, source, status, n, cross_check}.

    CASCATA (arquitetura 7 Jul): **(0) tag manual → (a) lobby Info → (b) coerente →
    none**. A fonte (0) VAZIA não mata o torneio (cai na salvaguarda). Toda a
    fronteira passa pelo **SNAP-TO-N** (recua à 1ª mão real da FT, `sentados==N`); o
    `cross_check` cruza N com os sentados da 1ª mão GG >= fronteira JÁ SNAPPED. `n` =
    via (a) `final_table_size`; via (b) `players_left`; via (0) o do lobby se existir,
    senão inferido (máx. de sentados na janela). NÃO bloqueia (quarentena é F3).
    status ∈ {'manual','lobby','coherent','quarantine_disagreement','incoherent_signal','none'}."""
    lb, lb_n = _lobby_ft_boundary(tn)          # salvaguarda: dá N + é a via (a)

    # (0) PRIMÁRIA — tag -ft MANUAL do Rui.
    m = _manual_ft_boundary(tn)
    if m is not None:
        n = lb_n if lb_n is not None else _infer_ft_size(tn, m)
        m_snap = _snap_to_n(tn, m, n)
        # DISCORDÂNCIA tag×lobby (momentos incompatíveis, p/ lá da janela) → quarentena.
        if lb is not None:
            lb_snap = _snap_to_n(tn, lb, lb_n)
            if _far_apart(m_snap, lb_snap):
                return {"boundary": None, "source": None,
                        "status": "quarantine_disagreement", "n": lb_n,
                        "cross_check": {"manual": str(m_snap), "lobby": str(lb_snap),
                                        "match": False}}
        return {"boundary": m_snap, "source": "manual_ft_tag", "status": "manual",
                "n": lb_n if lb_n is not None else n,
                "cross_check": _cross_check(tn, m_snap, lb_n)}

    # (a) SALVAGUARDA — lobby Info (histórico sem tag manual).
    if lb is not None:
        snapped = _snap_to_n(tn, lb, lb_n)
        return {"boundary": snapped, "source": "propagated_lobby", "status": "lobby",
                "n": lb_n, "cross_check": _cross_check(tn, snapped, lb_n)}

    # (b) SALVAGUARDA — capturas coerentes (último degrau).
    it_b, coherent, it_n = _it_ft_boundary(tn)
    if not coherent:
        return {"boundary": None, "source": None, "status": "incoherent_signal",
                "n": None, "cross_check": None}
    if it_b is not None:
        snapped = _snap_to_n(tn, it_b, it_n)
        return {"boundary": snapped, "source": "propagated_coherent", "status": "coherent",
                "n": it_n, "cross_check": _cross_check(tn, snapped, it_n)}
    return {"boundary": None, "source": None, "status": "none",
            "n": None, "cross_check": None}


# ── Correção da tag (base → -ft), canónica, sem duplicar sufixo ───────────────
def _to_ft(tag: str) -> Optional[str]:
    """Forma canónica base-spot → a sua '-ft'. Já '-ft'/neutra/desconhecida → None
    (sem mudança). Fail-safe contra '-ft-ft'."""
    canon = canonicalize_tag(tag)
    if canon in FT_BASE_SPOTS:
        return f"{canon}-ft"
    return None


def ft_correct_array(tags) -> tuple[list, bool]:
    """Converte base-spots → '-ft' numa lista de tags; colapsa base+ft duplicado;
    preserva ordem, tudo o resto intacto. Devolve (nova_lista, mudou)."""
    out: list = []
    changed = False
    for t in (tags or []):
        ft = _to_ft(t)
        keep = ft if ft else t
        if ft and ft != t:
            changed = True
        if keep not in out:
            out.append(keep)
        else:
            changed = True                     # colapsou duplicado (base+ft)
    return out, changed


# ── Propagação ───────────────────────────────────────────────────────────────
def _candidate_tns() -> list[str]:
    """Torneios GG com ALGUM sinal de FT: print do Info (via a), lobby<=cap, ou
    capturas IT com players_left (via b). O ramo Info garante que um torneio cujo
    ÚNICO sinal é um print do Info (players_left ilegível mas N legível) não escapa
    ao varrimento 'todos os candidatos'."""
    rows = query(
        """SELECT DISTINCT tournament_number AS tn FROM lobby_processing_log
            WHERE tournament_number IS NOT NULL
              AND ((players_left IS NOT NULL AND players_left <= %s)
                   OR (vision_json->>'open_tab' = 'Info'
                       AND vision_json->>'final_table_size' ~ '^[0-9]+$'))
           UNION
           SELECT DISTINCT h.tournament_number
             FROM hands h JOIN table_ss_processing_log l ON l.id=h.context_table_ss_id
            WHERE h.site='GGPoker' AND l.players_left IS NOT NULL
              AND h.tournament_number IS NOT NULL""",
        (FT_CAP,),
    )
    return [r["tn"] for r in rows if r["tn"]]


def propagate_ft(tournament_number: Optional[str] = None, *, dry_run: bool = False) -> dict:
    """Traça a fronteira e marca/corrige as mãos FT de um torneio (ou de todos os
    candidatos). Só toca mãos GG do torneio com played_at >= fronteira que tenham
    uma tag base-spot a converter. dry_run=True → não escreve, devolve o plano.

    Devolve {tournaments, changed:[{hand_id, from, to, source}], signaled:[tn],
    cross_checks:[{tn, source, n, hh_seats, match}], n_changed}. `cross_checks`
    (D2) é o sinal que o revisor manual (dry-run → OK do Rui) inspeciona antes de
    aprovar — um `match: false` avisa que a fronteira pode estar errada.
    """
    tns = [tournament_number] if tournament_number else _candidate_tns()
    changed: list[dict] = []
    signaled: list[str] = []
    cross_checks: list[dict] = []
    touched_tns = 0
    for tn in tns:
        b = compute_ft_boundary(tn)
        if b["status"] == "incoherent_signal":
            signaled.append(tn)
            continue
        if not b["boundary"]:
            continue
        touched_tns += 1
        cross_checks.append({"tn": tn, "source": b["source"], **(b.get("cross_check") or {})})
        rows = query(
            """SELECT id, hand_id, discord_tags, hm3_tags, folder_ft_source
                 FROM hands
                WHERE site='GGPoker' AND tournament_number = %s
                  AND played_at >= %s""",
            (tn, b["boundary"]),
        )
        for h in rows:
            nd, cd = ft_correct_array(list(h["discord_tags"] or []))
            nh, ch = ft_correct_array(list(h["hm3_tags"] or []))
            if not (cd or ch):
                continue                        # nada a corrigir nesta mão
            changed.append({
                "hand_id": h["hand_id"],
                "from": sorted(set(list(h["discord_tags"] or []) + list(h["hm3_tags"] or []))),
                "to": sorted(set(nd + nh)),
                "source": b["source"],
            })
            if not dry_run:
                _persist_ft_correction(h["id"], nd, nh, b["source"])
    return {"tournaments": touched_tns, "changed": changed,
            "signaled": signaled, "cross_checks": cross_checks,
            "n_changed": len(changed)}


def _persist_ft_correction(hand_db_id: int, discord_tags, hm3_tags, source: str) -> None:
    """Escreve tags corrigidas + `folder_ft_source` e re-avalia vilões (Estudo/Vilões).

    D3 (emenda pt-FT): a coluna `folder_ft_source` tem domínio {NULL,'manual','auto'}
    — é a proveniência que o badge âmbar e o filtro "-ft auto" da Estudo (`hands.py`)
    leem. A propagação é uma adivinha automática → grava **'auto'** (reusa o filtro de
    revisão do Rui), NUNCA a string da via (`propagated_lobby`/`propagated_coherent`),
    que poluiria a coluna e cegaria o filtro. A via fina vive no ensaio/quarentena,
    não aqui; o `source` fica só para log/auditoria.

    Convivência com o manual (ponto 5): a pasta -ft do Rui MANDA sempre → o CASE
    **nunca rebaixa** um `'manual'` existente para `'auto'`.
    Defensivo: falha aqui nunca rebenta o trigger."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE hands SET discord_tags=%s, hm3_tags=%s, "
                "folder_ft_source = CASE WHEN folder_ft_source='manual' "
                "THEN 'manual' ELSE 'auto' END "
                "WHERE id=%s",
                (discord_tags, hm3_tags, hand_db_id),
            )
        conn.commit()
        logger.debug("[ft_boundary] hand %s corrigida (via %s → folder_ft_source=auto)",
                     hand_db_id, source)
        try:
            from app.services.villain_rules import apply_villain_rules
            apply_villain_rules(hand_db_id)
        except Exception as e:
            logger.error("[ft_boundary] villain_rules hand %s falhou: %s", hand_db_id, e)
    finally:
        conn.close()


def trigger_ft_propagation(tournament_number: Optional[str] = None) -> None:
    """Wrapper fire-and-forget (defensivo) para os triggers de import/lobby."""
    try:
        res = propagate_ft(tournament_number)
        if res["n_changed"] or res["signaled"]:
            logger.info("[ft_boundary] tns=%d changed=%d signaled=%d",
                        res["tournaments"], res["n_changed"], len(res["signaled"]))
    except Exception as e:
        logger.error("[ft_boundary] propagate falhou: %s", e)
