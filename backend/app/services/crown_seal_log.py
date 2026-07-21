"""RASTO DOS SELOS DE COROA (`crown_seal_log`) — ordem do Rui, 16 Jul 2026.

PROBLEMA QUE FECHA: um selo de coroa não deixava rasto. Sem data, sem valor anterior,
sem origem. Consequências vistas no mesmo dia: o card do Anton Efimov apareceu carimbado
($70 `manual`) sem se saber quando nem por que fluxo, e as "14 mesas-toda-$0" do journal
16.2 ficaram IRRECONCILIÁVEIS (hoje 10; as 4 que saíram não são recuperáveis, porque
`hands` não tem `updated_at` e o selo vive dentro do JSON sem carimbo temporal).

DESENHO (fixado pelo Rui):
- **1 registo por cada escrita de selo**: mão (nº GG), jogador, valor ANTES (NULL se não
  havia), valor DEPOIS, origem (rota/fluxo) e momento.
- **SÓ-ACRESCENTO**: nunca se apaga nem se edita um registo. Um selo desfeito/corrigido
  gera um registo NOVO (o antigo fica). Garantido no CÓDIGO (não há UPDATE/DELETE em lado
  nenhum) **e na BD** (regras `DO INSTEAD NOTHING`) — um UPDATE/DELETE ad-hoc não pega.
  Para alguma vez mexer: `DROP RULE crown_seal_log_no_update ON crown_seal_log;` (idem
  `_no_delete`) — decisão do Rui, nunca de um automático.
- **Sem UI**: só grava; consulta-se por query. UI de histórico = decisão futura.
- **Nada retroativo**: os selos existentes ficam como estão, sem registos inventados. O
  rasto começa no dia em que isto entra no ar.

O QUE CONTA COMO SELO: o seat fica com `bounty_source` em `SEALED_BOUNTY_SOURCES`
(manual, green_ko, derived_green_ko, cross_capture, cross_conflict, cross_exclusion) OU
com o flag `bounty_confirmed` — o mesmo crivo do `is_bounty_sealed`, a fonte única do
invariante. Escritas de coroa NÃO-seladas (ex. `crowns/fallback-fill`, que grava
`bounty_source='gold'|'table_ss'`) ficam de fora: não são selos.

REGRA DE OURO DOS CALL SITES: só se regista DEPOIS do `conn.commit()` do caminho que
escreve. Registar antes mentiria se a transação falhasse. O padrão é: juntar as linhas
numa lista enquanto se muta → `log_seals(pending, origin=...)` depois do commit.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("crown_seal_log")

# Origens (rota/fluxo). Constantes p/ não haver rótulos soltos a divergir entre call sites.
ORIGIN_SET_BOUNTIES = "table_ss.set_bounties"            # carimbo do card / correção manual
ORIGIN_CROSSING_APPLY = "gg_health.crossing_apply"       # LEI DO CRUZAMENTO — carimbo em lote
ORIGIN_CROSSING_CONFLICT_AUTO = "gg_health.crossing_conflicts_auto"   # (B) crescimento óbvio
ORIGIN_CROSSING_EYE = "gg_health.crossing_conflicts_eye"  # o OLHO: "Mantém $X" / campo livre
ORIGIN_CROSSING_EXCLUSION = "gg_health.crossing_exclusion"            # exclusão de partes
ORIGIN_HIGH_REREAD_CONFIRM = "gg_health.crowns_high_reread_confirm"   # confirmação de releitura
ORIGIN_SCRUB_GREEN_KO = "eliminated_bounty.scrub_and_persist"         # verde-KO (automático)


def ensure_crown_seal_log_schema():
    """Tabela + índices + as regras do só-acrescento. Idempotente (corre no lifespan)."""
    from app.db import get_conn
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "CREATE TABLE IF NOT EXISTS crown_seal_log ("
                "  id BIGSERIAL PRIMARY KEY,"
                "  hand_id TEXT NOT NULL,"              # nº GG da mão (ex. GG-6114944742)
                "  player TEXT NOT NULL,"               # nick como está na app
                "  old_value NUMERIC(12,2),"            # coroa ANTES (NULL = não havia)
                "  new_value NUMERIC(12,2),"            # coroa DEPOIS
                "  old_source TEXT,"                    # bounty_source antes (NULL = sem selo)
                "  new_source TEXT,"                    # bounty_source depois
                "  confirmed BOOLEAN NOT NULL DEFAULT FALSE,"   # selo pelo flag bounty_confirmed
                "  origin TEXT NOT NULL,"               # rota/fluxo que escreveu
                "  actor TEXT,"                         # quem (email da sessão) ou 'api_key'
                "  created_at TIMESTAMPTZ NOT NULL DEFAULT now())")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_crown_seal_log_hand "
                        "ON crown_seal_log (hand_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_crown_seal_log_created "
                        "ON crown_seal_log (created_at DESC)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_crown_seal_log_player "
                        "ON crown_seal_log (player)")
            # Regra dos DOIS CARIMBOS (21 Jul): 'placa' | 'aceitacao' | NULL (legado/
            # automático). Coluna aditiva — o só-acrescento mantém-se intacto.
            cur.execute("ALTER TABLE crown_seal_log "
                        "ADD COLUMN IF NOT EXISTS stamp TEXT")
            # SÓ-ACRESCENTO na própria BD: nem a app nem uma query ad-hoc editam/apagam.
            cur.execute("CREATE OR REPLACE RULE crown_seal_log_no_update "
                        "AS ON UPDATE TO crown_seal_log DO INSTEAD NOTHING")
            cur.execute("CREATE OR REPLACE RULE crown_seal_log_no_delete "
                        "AS ON DELETE TO crown_seal_log DO INSTEAD NOTHING")
        conn.commit()
    finally:
        conn.close()


def actor_of(current_user) -> str:
    """Etiqueta de quem escreveu, defensiva (o `require_auth` devolve a row do user; o
    `require_auth_or_api_key` devolve a marca da chave do watcher)."""
    try:
        if isinstance(current_user, dict):
            return str(current_user.get("email") or current_user.get("id") or "?")[:200]
        return str(current_user)[:200] if current_user else "?"
    except Exception:  # pragma: no cover - defensivo
        return "?"


def _num(v):
    if v is None or v == "":
        return None
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None


def seal_row(hand_id, player, old_value, new_value, *, old_source=None,
             new_source=None, confirmed=False, stamp=None) -> dict:
    """Constrói UMA linha do rasto (não grava — o call site junta e grava pós-commit).
    `stamp`: 'placa' | 'aceitacao' | None (regra dos DOIS CARIMBOS, 21 Jul)."""
    return {"hand_id": hand_id, "player": player,
            "old_value": _num(old_value), "new_value": _num(new_value),
            "old_source": old_source, "new_source": new_source,
            "confirmed": bool(confirmed), "stamp": stamp}


def log_seals(rows, *, origin: str, actor: str = "?") -> int:
    """Grava o rasto (INSERT em lote). DEFENSIVO POR DESENHO: uma falha aqui NUNCA parte o
    caminho que escreveu a coroa — o selo é o trabalho, o rasto é a auditoria. Devolve
    quantas linhas gravou (0 se falhou/nada a gravar)."""
    rows = [r for r in (rows or []) if r]
    if not rows:
        return 0
    from app.db import get_conn
    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO crown_seal_log (hand_id, player, old_value, new_value, "
                "  old_source, new_source, confirmed, origin, actor, stamp) "
                "VALUES (%(hand_id)s, %(player)s, %(old_value)s, %(new_value)s, "
                "        %(old_source)s, %(new_source)s, %(confirmed)s, %(origin)s, "
                "        %(actor)s, %(stamp)s)",
                [dict({"stamp": None}, **r, origin=origin, actor=actor) for r in rows])
        conn.commit()
        return len(rows)
    except Exception:  # pragma: no cover - defensivo
        logger.exception("[crown-seal-log] falhou a gravar %d linha(s) de %s", len(rows), origin)
        return 0
    finally:
        if conn is not None:
            conn.close()
