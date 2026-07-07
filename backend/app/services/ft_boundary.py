"""#FT-PROPAGATION — Propagação de FT (mesa final) por torneio.

O `players_left` só DESCE (jogadores só saem) → a partir do instante em que os que
restam <= tamanho da mesa final, é FT até ao fim. Este consumidor traça essa
FRONTEIRA por torneio e marca todas as mãos com `played_at >= fronteira`,
corrigindo a tag base → a sua `-ft` (icm→icm-ft, pos-pko→pos-pko-ft, …). A mão sai
do conflito de FASE e volta aos canais normais com a tag certa.

Fontes da fronteira, por prioridade:
  (a) PRINT DE LOBBY no início da FT — o `posted_at` do lobby É a fronteira (não
      depende da Vision para a POSIÇÃO; o players_left só confirma que é FT).
      Onde existe, MANDA (proveniência 'propagated_lobby').
  (b) Sem lobby → players_left das capturas IT, com SALVAGUARDA DE COERÊNCIA: só
      traça se o players_left descer de forma coerente (um valor isolado mal lido
      quebra o padrão → rejeita e SINALIZA, não corrige). Fronteira = o 1º momento
      `_ft_applies` (ocupados==restantes). Proveniência 'propagated_coherent'.

Puro quanto a escritas em modo dry_run (só lê). Idempotente: re-correr recomputa de
raiz e o `-ft` não duplica (fail-safe). Reusa: lobby_processing_log (players_left,
tournament_number, posted_at), table_ss_processing_log.players_left via
hands.context_table_ss_id, hands.tournament_number/played_at, tags_canonical.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.db import query, get_conn
from app.services.tags_canonical import canonicalize_tag

logger = logging.getLogger("ft_boundary")

# players_left <= FT_CAP num LOBBY ⇒ FT (cobre até mesa final de 9 lugares).
FT_CAP = 9
# Tolerância de jitter da Vision na verificação de coerência (fonte b).
COHERENCE_TOL = 2

# Tags-spot BASE que têm variante de fase '-ft' (formas canónicas). A '-ft' é
# mudança de FASE, ortogonal ao FORMATO → converter base→-ft NUNCA muda PKO/não-PKO
# (logo nunca nasce conflito de 'formato').
FT_BASE_SPOTS = frozenset({"icm", "icm-pko", "pos-pko", "pos-nko", "speed-racer"})


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
def _lobby_ft_boundary(tn: str):
    """Fonte (a): 1º posted_at (Lisboa-naive) de um lobby do torneio com
    players_left <= FT_CAP. None se não houver."""
    rows = query(
        """SELECT MIN(posted_at) AS b
             FROM lobby_processing_log
            WHERE tournament_number = %s
              AND players_left IS NOT NULL AND players_left <= %s
              AND posted_at IS NOT NULL""",
        (tn, FT_CAP),
    )
    return rows[0]["b"] if rows and rows[0]["b"] else None


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


def _it_ft_boundary(tn: str):
    """Fonte (b): (fronteira, coerente). Descarta o outlier isolado; fronteira = 1º
    played_at (entre os readings COERENTES) onde _ft_applies. Genuinamente
    incoerente → (None, False) [sinaliza, não corrige]."""
    readings = _it_readings(tn)
    if not readings:
        return None, True                     # sem dados: coerente-vazio, sem fronteira
    kept, coherent = _coherent_readings(readings)
    if not coherent:
        return None, False
    for r in kept:                             # kept preserva ordem (played_at)
        if _ft_applies(r["vision_json"] or {}):
            return r["played_at"], True
    return None, True


def compute_ft_boundary(tn: str) -> dict:
    """Fronteira do torneio, fonte (a) MANDA sobre (b). Devolve
    {boundary, source, status}. status ∈ {'lobby','coherent','incoherent_signal','none'}."""
    lb = _lobby_ft_boundary(tn)
    if lb is not None:
        return {"boundary": lb, "source": "propagated_lobby", "status": "lobby"}
    it_b, coherent = _it_ft_boundary(tn)
    if not coherent:
        return {"boundary": None, "source": None, "status": "incoherent_signal"}
    if it_b is not None:
        return {"boundary": it_b, "source": "propagated_coherent", "status": "coherent"}
    return {"boundary": None, "source": None, "status": "none"}


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
    """Torneios GG com ALGUM sinal de FT (lobby<=cap OU capturas IT com pl)."""
    rows = query(
        """SELECT DISTINCT tournament_number AS tn FROM lobby_processing_log
            WHERE players_left IS NOT NULL AND players_left <= %s
              AND tournament_number IS NOT NULL
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

    Devolve {tournaments, changed:[{hand_id, from, to, source}], signaled:[tn], skipped}.
    """
    tns = [tournament_number] if tournament_number else _candidate_tns()
    changed: list[dict] = []
    signaled: list[str] = []
    touched_tns = 0
    for tn in tns:
        b = compute_ft_boundary(tn)
        if b["status"] == "incoherent_signal":
            signaled.append(tn)
            continue
        if not b["boundary"]:
            continue
        touched_tns += 1
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
            "signaled": signaled, "n_changed": len(changed)}


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
