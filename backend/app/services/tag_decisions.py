"""SELO DA TAG (`tag_decisions`) — ordem do Rui, 18 Jul 2026.

PROBLEMA QUE FECHA: o Rui não conseguia CORRIGIR uma tag. Se a tirasse de uma mão, ela
VOLTAVA — há 10 sítios que reescrevem `hands.discord_tags` por APPEND a partir do folder_tag
da captura (ou do canal Discord), a cada reprocessamento/reconcile. A decisão manual do Rui
era apagada pelo automático e ele não dava por nada.

É o mesmo problema que a LEI DO SELO resolveu para as coroas: **o que o Rui decide manda sobre
o que os robôs escrevem.**

DESENHO (o mais barato que serve — fixado pelo Rui):
- **Tabela `tag_decisions(hand_id, tag, action)`**, action ∈ {add, remove} — as decisões
  seladas. Mover uma tag de A para B = (A, tag, remove) + (B, tag, add); B pode ser QUALQUER
  mão (o Rui re-taga minutos depois e a dona pode estar várias mãos atrás).
- **SÓ-ACRESCENTO** (rasto): nunca se apaga nem edita. Corrigir/mudar de ideias = INSERT NOVO;
  a decisão EFECTIVA por (hand_id, tag) é a do registo MAIS RECENTE (latest-wins). Garantido na
  BD por regras `DO INSTEAD NOTHING` (UPDATE/DELETE ad-hoc não pegam). Para mexer algum dia:
  `DROP RULE tag_decisions_no_update ON tag_decisions;` (idem `_no_delete`) — decisão do Rui.
- **`apply_tag_decisions(hand_id, base[])`** (função SQL) = `(base ∪ adds) − removes`, com os
  removes aplicados POR ÚLTIMO (ganham sempre). É a `recompute_discord_tags` do desenho, mas
  ao NÍVEL DA ESCRITA: todos os 10 writers de `discord_tags` embrulham o seu RHS nesta função,
  logo a decisão do Rui sobrevive a TODO o reprocessamento, de forma ATÓMICA (sem janela em que
  a tag reaparece). `hm3_tags` fica INTACTA (o selo só toca `discord_tags`).
- **`discord_tags` continua materializada** como hoje — os leitores (Vilões, Estudo, ~20
  painéis, índice GIN) NÃO mudam.

RASTO: como no `crown_seal_log` — quem, quando, que mão, que tag, que acção. Append-only,
protegido na BD. Uma linha por mão (em lote, uma por cada mão), como se fosse feita à mão.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("tag_decisions")

# Origens (rota/fluxo) — constantes p/ não haver rótulos soltos a divergir entre call sites.
ORIGIN_HAND_PAGE = "tag_decisions.hand_page"        # botão "tirar tag" na página da mão
ORIGIN_BATCH = "tag_decisions.batch"                # selecção em lote no painel
ORIGIN_GG_HEALTH_TAG = "gg_health.tag"              # ferramenta manual "Aplicar" (add)
ORIGIN_GG_HEALTH_UNTAG = "gg_health.untag"          # ferramenta manual "Remover" (remove)
ORIGIN_REGRA_6S = "regra6s.move"                    # régua dos 6s: mover MANUAL (painel)
ORIGIN_REGRA_6S_AUTO = "regra6s.auto"               # régua dos 6s: a app moveu SOZINHA (rasto)

VALID_ACTIONS = ("add", "remove")


def ensure_tag_decisions_schema():
    """Tabela + índices + regras só-acrescento + a função `apply_tag_decisions`. Idempotente
    (corre no lifespan)."""
    from app.db import get_conn
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "CREATE TABLE IF NOT EXISTS tag_decisions ("
                "  id BIGSERIAL PRIMARY KEY,"
                "  hand_id TEXT NOT NULL,"              # nº GG da mão (ex. GG-6132923055)
                "  tag TEXT NOT NULL,"                  # a tag EXACTA (string), como está na mão
                "  action TEXT NOT NULL CHECK (action IN ('add','remove')),"
                "  actor TEXT,"                         # quem (email da sessão) ou 'api_key'
                "  origin TEXT NOT NULL,"               # rota/fluxo que decidiu
                "  created_at TIMESTAMPTZ NOT NULL DEFAULT now())")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tag_decisions_hand "
                        "ON tag_decisions (hand_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tag_decisions_created "
                        "ON tag_decisions (created_at DESC)")
            # SÓ-ACRESCENTO na própria BD (como o crown_seal_log): nem a app nem uma query
            # ad-hoc editam/apagam. Corrigir = INSERT novo (latest-wins).
            cur.execute("CREATE OR REPLACE RULE tag_decisions_no_update "
                        "AS ON UPDATE TO tag_decisions DO INSTEAD NOTHING")
            cur.execute("CREATE OR REPLACE RULE tag_decisions_no_delete "
                        "AS ON DELETE TO tag_decisions DO INSTEAD NOTHING")
            # A função da recompute, ao nível da escrita. Latest-wins por tag (DISTINCT ON
            # id DESC): a decisão mais recente por (hand_id, tag) manda — deixa o Rui
            # corrigir-se (remover e depois voltar a pôr). Removes aplicados por último.
            cur.execute(
                "CREATE OR REPLACE FUNCTION apply_tag_decisions(p_hand_id text, p_base text[]) "
                "RETURNS text[] AS $$ "
                "  WITH latest AS ("
                "    SELECT DISTINCT ON (tag) tag, action FROM tag_decisions "
                "     WHERE hand_id = p_hand_id ORDER BY tag, id DESC) "
                "  SELECT ARRAY("
                "    SELECT DISTINCT t FROM ("
                "      SELECT unnest(COALESCE(p_base, '{}'::text[])) AS t "
                "      UNION SELECT tag FROM latest WHERE action='add') u "
                "    WHERE NOT EXISTS (SELECT 1 FROM latest l WHERE l.tag=u.t AND l.action='remove')) "
                "$$ LANGUAGE sql STABLE")
        conn.commit()
    finally:
        conn.close()


def actor_of(current_user) -> str:
    """Etiqueta defensiva de quem decidiu (igual ao crown_seal_log)."""
    try:
        if isinstance(current_user, dict):
            return str(current_user.get("email") or current_user.get("id") or "?")[:200]
        return str(current_user)[:200] if current_user else "?"
    except Exception:  # pragma: no cover - defensivo
        return "?"


def apply_decisions_py(base, decisions) -> list:
    """Espelho PURO da função SQL, para testes e uso Python. `decisions` = iterável de
    (tag, action, id) OU dicts {tag, action, id}; latest-wins por tag (maior id). Devolve a
    lista final `(base ∪ adds) − removes`, ordem estável (base primeiro, depois adds novos)."""
    latest = {}   # tag -> (id, action)
    for d in (decisions or []):
        if isinstance(d, dict):
            tag, action, did = d.get("tag"), d.get("action"), d.get("id") or 0
        else:
            tag, action, did = d[0], d[1], (d[2] if len(d) > 2 else 0)
        if tag is None:
            continue
        prev = latest.get(tag)
        if prev is None or did >= prev[0]:
            latest[tag] = (did, action)
    removes = {t for t, (_, a) in latest.items() if a == "remove"}
    adds = [t for t, (_, a) in latest.items() if a == "add"]
    out, seen = [], set()
    for t in list(base or []) + adds:
        if t in removes or t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def log_decision(cur, hand_id: str, tag: str, action: str, *, actor: str, origin: str) -> None:
    """INSERT do rasto/decisão (append-only). Usa o cursor da transacção do call site: a
    decisão é a FONTE de verdade da recompute, logo tem de estar visível na MESMA transacção
    em que se recomputa `discord_tags` (não é log-pós-commit como a coroa)."""
    cur.execute(
        "INSERT INTO tag_decisions (hand_id, tag, action, actor, origin) "
        "VALUES (%s, %s, %s, %s, %s)",
        (hand_id, tag, action, actor, origin))


def seal_and_recompute(cur, hand_id: str, tag: str, action: str, *, actor: str,
                       origin: str) -> list:
    """Sela UMA decisão (INSERT no rasto) e RECOMPUTA `discord_tags` das mão(s) com esse
    `hand_id`, de forma atómica (mesma transacção — o call site faz o commit). Devolve os
    ids das mãos afectadas (p/ o call site re-avaliar vilões pós-commit). NÃO toca `hm3_tags`.

    A recompute passa por `apply_tag_decisions(hand_id, discord_tags)` — como a decisão
    acabou de ser inserida no mesmo cursor, já é visível → a tirada some NA HORA."""
    if action not in VALID_ACTIONS:
        raise ValueError(f"acção inválida: {action!r}")
    log_decision(cur, hand_id, tag, action, actor=actor, origin=origin)
    cur.execute(
        "UPDATE hands SET discord_tags = "
        "  apply_tag_decisions(hand_id, COALESCE(discord_tags, '{}'::text[])) "
        "WHERE hand_id = %s RETURNING id",
        (hand_id,))
    return [r["id"] if isinstance(r, dict) else r[0] for r in cur.fetchall()]
