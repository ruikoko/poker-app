"""pt81 (#WN-LOBBY-NO-AUTO-RETRY) — o caminho HM3 (`import_hm3`) passa a disparar
os MESMOS gatilhos fire-and-forget que o `import_` (`import_file`): relink de SS
de mesa órfãs + reconcile de lobbys pendentes.

Raiz fechada: as mãos WN entram pelo .bat do HM3 (`import_hm3`), que — ao
contrário do `import_.py` — não re-corria `reconcile_lobby_logs`. Resultado: os
lobbys ficavam `tm_not_found` para sempre mesmo depois de as mãos chegarem.

Padrão: inspeção de source (igual a `test_order_convergence_pt50::test_fix_a`),
porque os gatilhos são fire-and-forget (`asyncio.create_task`) — o que importa é
estarem CABLADOS no caminho HM3, alinhados com o import_.
"""
from __future__ import annotations
import inspect

from app.routers.hm3 import import_hm3
from app.routers.import_ import import_file


def _norm(fn):
    return " ".join(inspect.getsource(fn).split())


def test_import_hm3_wires_lobby_reconcile_trigger():
    s = _norm(import_hm3)
    assert "reconcile_lobby_logs" in s
    assert "asyncio.to_thread(reconcile_lobby_logs)" in s
    assert "_lobby_reconcile_async" in s
    assert "asyncio.create_task(_lobby_reconcile_async())" in s


def test_import_hm3_keeps_table_ss_relink_trigger():
    s = _norm(import_hm3)
    assert "relink_orphan_table_ss" in s
    assert "asyncio.create_task(_table_ss_relink_async())" in s


def test_import_hm3_aligned_with_import_file_triggers():
    """O caminho HM3 fica IGUAL ao import_ nos dois gatilhos relevantes."""
    hm3 = _norm(import_hm3)
    imp = _norm(import_file)
    for token in ("relink_orphan_table_ss",
                  "asyncio.to_thread(reconcile_lobby_logs)"):
        assert token in imp, f"import_file devia ter {token}"
        assert token in hm3, f"import_hm3 devia ter {token} (alinhamento)"
