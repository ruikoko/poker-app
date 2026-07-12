"""#HM3-IMPORT-NO-RECONCILE-REDISPATCH — o trigger robusto corre OS DOIS reconciles
(table-SS relink + lobbys) num daemon thread. O padrão anterior (asyncio.create_task)
perdia-se em imports sync-pesados/timeout (a leva WN ficou sem re-match até correr à mão).
"""
from app.services import lobby_sync


def test_trigger_import_reconciles_corre_ambos(monkeypatch):
    calls = []
    # o helper importa relink_orphan_table_ss LAZY de app.routers.table_ss
    import app.routers.table_ss as ts
    monkeypatch.setattr(ts, "relink_orphan_table_ss",
                        lambda: (calls.append("ss"), {"success": 3, "changed": 3, "orphan": 0, "checked": 3})[1])
    monkeypatch.setattr(lobby_sync, "reconcile_lobby_logs",
                        lambda: (calls.append("lobby"), {"resolved": 2, "written": 2, "still_unresolved": 0, "scanned": 5})[1])

    # thread síncrono (para o teste ser determinístico)
    class _SyncThread:
        def __init__(self, target=None, daemon=None):
            self._t = target

        def start(self):
            self._t()

    monkeypatch.setattr("threading.Thread", _SyncThread)
    lobby_sync.trigger_import_reconciles(reason="test")
    # ordem: primeiro table-SS relink, depois lobbys
    assert calls == ["ss", "lobby"]


def test_trigger_import_reconciles_defensivo(monkeypatch):
    """Se um reconcile lança, o outro corre na mesma e o trigger NUNCA rebenta."""
    calls = []
    import app.routers.table_ss as ts
    def _boom():
        raise RuntimeError("relink falhou")
    monkeypatch.setattr(ts, "relink_orphan_table_ss", _boom)
    monkeypatch.setattr(lobby_sync, "reconcile_lobby_logs",
                        lambda: (calls.append("lobby"), {})[1])

    class _SyncThread:
        def __init__(self, target=None, daemon=None):
            self._t = target

        def start(self):
            self._t()

    monkeypatch.setattr("threading.Thread", _SyncThread)
    lobby_sync.trigger_import_reconciles(reason="test")   # não lança
    assert calls == ["lobby"]                             # o lobby correu apesar do erro no SS
