"""pt81 (#WN-LOBBY-NO-AUTO-RETRY) — o caminho HM3 (`import_hm3`) passa a disparar
os MESMOS gatilhos fire-and-forget que o `import_` (`import_file`): relink de SS
de mesa órfãs + reconcile de lobbys pendentes.

Raiz fechada: as mãos WN entram pelo .bat do HM3 (`import_hm3`), que — ao
contrário do `import_.py` — não re-corria `reconcile_lobby_logs`. Resultado: os
lobbys ficavam `tm_not_found` para sempre mesmo depois de as mãos chegarem.

Padrão: inspeção de source, porque os gatilhos são fire-and-forget — o que importa
é estarem CABLADOS no caminho HM3, alinhados com o import_.

⚠️ Atualizado (14 Jul): desde a consolidação de 13 Jul
(#HM3-IMPORT-NO-RECONCILE-REDISPATCH) os dois `asyncio.create_task` separados
(_lobby_reconcile_async / _table_ss_relink_async) foram fundidos num único
`trigger_import_reconciles(...)` num DAEMON THREAD robusto (sobrevive ao timeout do
request). Estes testes passam a verificar esse gatilho consolidado — mesma intenção
(relink de SS órfãs + reconcile de lobbys pendentes cablados no caminho HM3).
"""
from __future__ import annotations
import inspect

from app.routers.hm3 import import_hm3
from app.routers.import_ import import_file


def _norm(fn):
    return " ".join(inspect.getsource(fn).split())


def test_import_hm3_wires_reconcile_trigger():
    s = _norm(import_hm3)
    assert "trigger_import_reconciles" in s
    assert 'reason="import_hm3"' in s


def test_import_hm3_keeps_table_ss_relink_trigger():
    # o trigger consolidado corre o relink de SS órfãs (via reconcile_table_ss).
    s = _norm(import_hm3)
    assert "trigger_import_reconciles" in s


def test_import_hm3_aligned_with_import_file_triggers():
    """O caminho HM3 fica IGUAL ao import_ no gatilho consolidado."""
    hm3 = _norm(import_hm3)
    imp = _norm(import_file)
    assert "trigger_import_reconciles" in imp, "import_file devia disparar o trigger"
    assert "trigger_import_reconciles" in hm3, "import_hm3 devia disparar o trigger (alinhamento)"
