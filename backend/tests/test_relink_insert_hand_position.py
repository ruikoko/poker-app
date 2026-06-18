"""Re-link imagem-primeiro via _insert_hand (promoção de placeholder quando a HH
chega): se o placeholder tem siglas de posição (gold image), promove com
position_v3, NÃO stack-elimination. A ordem deixa de importar."""
import json
from unittest.mock import patch
from app.services.hand_service import _insert_hand


class _Cur:
    def __init__(self, existing): self.existing=existing; self.updates=[]; self.inserts=[]; self.deletes=[]; self._f=None
    def __enter__(self): return self
    def __exit__(self,*a): return False
    def execute(self, sql, params=None):
        s=sql.lower().strip()
        if "select id, raw, hm3_tags" in s: self._f=self.existing
        elif "delete from hands" in s: self.deletes.append(params)
        elif "insert into hands" in s: self.inserts.append(params)
        elif "update hands" in s: self.updates.append(params)
        else: self._f=None
    def fetchone(self): return self._f


class _Conn:
    def __init__(self, existing): self.cur=_Cur(existing); self.committed=False
    def cursor(self): return self.cur
    def commit(self): self.committed=True
    def rollback(self): pass
    def close(self): pass


def _placeholder(players_list):
    return {
        "id": 1, "raw": "", "hm3_tags": [], "origin": "ss_upload",
        "discord_tags": [], "placeholder_entry_id": 555, "screenshot_url": None,
        "tags": ["SSMatch"],
        "player_names": {"match_method": "discord_placeholder_no_hh",
                         "players_list": players_list, "hero": "Hero"},
    }


def _new_hand():
    return {"site":"GGPoker","hand_id":"GG-1","played_at":None,"stakes":None,"position":None,
            "hero_cards":[],"board":[],"result":0,"currency":"$","raw":"Poker Hand #TM1: ...",
            "all_players_actions":{"89ef4cba":{"actions":[]}},"tournament_id":None,"buy_in":None,
            "tournament_format":None,"tournament_name":None}


def _run(players_list):
    conn=_Conn(_placeholder(players_list))
    with patch("app.routers.screenshot._build_anon_to_real_map_by_position",
               return_value={"anon_map": {"89ef4cba": "Alice", "Hero": "Hero"}}) as bypos, \
         patch("app.routers.screenshot._build_anon_to_real_map",
               return_value={"89ef4cba": "StackName", "Hero": "Hero"}) as bystack, \
         patch("app.routers.screenshot._enrich_all_players_actions", return_value={}):
        ok=_insert_hand(conn, _new_hand(), entry_id=777, tournament_pk=None,
                        study_state="new", origin="hh_import")
    assert ok is True
    upd=conn.cur.updates[0]
    pn=json.loads(upd["player_names"]) if isinstance(upd.get("player_names"),str) else upd.get("player_names")
    return pn, bypos, bystack


def test_relink_placeholder_com_posicoes_promove_position_v3():
    pn, bypos, bystack = _run(
        [{"name":"Alice","position":"UTG"},{"name":"Hero","position":None}]
    )
    assert pn["match_method"] == "position_v3"
    bypos.assert_called_once()
    bystack.assert_not_called()


def test_relink_placeholder_sem_posicoes_cai_no_stack():
    pn, bypos, bystack = _run(
        [{"name":"Alice","position":None},{"name":"Hero","position":None}]
    )
    assert pn["match_method"] == "anchors_stack_elimination_v2"
    bystack.assert_called_once()
    bypos.assert_not_called()
