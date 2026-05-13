"""pt25 helpers para o adapter — pure stdlib, importável sem o requests/urllib3
do hrc_adapter.py (facilita pytest no backend env).

Função única: `rewrite_script_path_in_payouts(payouts_path, abs_script_path)`
que actualiza a key `script_path` num payouts.json on-disk com path absoluto
do JS gerado pelo backend (`<queue_dir>/<hand_id>/script.js`).

O backend escreve `script_path = "script.js"` (relativo) no zip; o adapter
reescreve para path absoluto depois do unzip, porque o watcher Baltazar
espera path absoluto no campo de file dialog do HRC scripting tab.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Union


def rewrite_script_path_in_payouts(
    payouts_path: Union[str, Path],
    abs_script_path: str,
) -> bool:
    """Lê payouts.json, actualiza key `script_path` com `abs_script_path`,
    grava de volta com mesma formatação (indent=2 ensure_ascii=False).

    Devolve True se actualizou com sucesso, False se algum erro (file
    missing, JSON invalido, etc.). Não levanta — caller decide o que fazer.

    Idempotente: se `script_path` já está no valor desejado, escreve na
    mesma (1 fsync extra mas seguro).

    Preserva todas as outras keys de payouts.json (CompletedTournament,
    equity_model, max_players, etc.).
    """
    p = Path(payouts_path)
    if not p.is_file():
        return False
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(data, dict):
        return False
    data["script_path"] = abs_script_path
    try:
        p.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        return False
    return True
