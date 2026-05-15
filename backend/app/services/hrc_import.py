"""Parser do formato Complete Export do HRC (Hold'em Resources Calculator).

Formato (validado com `teste app.zip` 26MB / 9523 ficheiros, sessao `mko.hrcz`):
- `settings.json`             — handdata (stacks/blinds/ante), eqmodel (id, structure,
                                 prizes, otherstacks), treeconfig, engine.
- `equity.json`               — preHandEquity (array por seat), bubbleFactors (matriz NxN),
                                 conversionFactors (toUSD, toRegularPrizePercent).
- `nodes/<N>.json` × total    — um JSON por node da arvore preflop. Cada node tem
                                 `player` (int), `street` (int), `children` (int),
                                 `sequence` (path de accoes desde a raiz),
                                 `actions` (lista de {type:F|C|R|B, amount, [node]}),
                                 `hands` (dict de 169 entries — combos AA/AKs/AKo/etc —
                                  cada uma com {weight, played[N], evs[N]}).

Validacao minima:
- Zip parseavel + contem `settings.json` + `equity.json` + pelo menos `nodes/0.json`.
- `settings.json` e `equity.json` sao JSON validos.
- Cada `nodes/<N>.json` e JSON valido e tem os campos esperados.

Iteracao lazy: nao carregamos os 9521 nodes em RAM ao mesmo tempo —
`iter_nodes(zip_file)` faz yield (idx, node_dict) um a um.
"""
from __future__ import annotations

import io
import json
import re
import zipfile
from typing import Iterator, Tuple


# Regex para nomes de ficheiros de nodes dentro do zip.
# Aceita "nodes/0.json", "nodes/9521.json", etc.
_NODE_FILENAME_RE = re.compile(r"^nodes/(\d+)\.json$")

# Campos obrigatorios em cada node JSON.
_REQUIRED_NODE_FIELDS = ("player", "street", "sequence", "actions", "hands")


class HRCImportError(ValueError):
    """Erro de parsing/validacao do export HRC."""


def _validate_settings(settings: dict) -> None:
    if not isinstance(settings, dict):
        raise HRCImportError("settings.json: top-level nao e objecto JSON")
    if "handdata" not in settings:
        raise HRCImportError("settings.json: falta campo 'handdata'")


def _validate_equity(equity: dict) -> None:
    if not isinstance(equity, dict):
        raise HRCImportError("equity.json: top-level nao e objecto JSON")


def _validate_node(idx: int, node: dict) -> None:
    if not isinstance(node, dict):
        raise HRCImportError(f"nodes/{idx}.json: top-level nao e objecto JSON")
    missing = [f for f in _REQUIRED_NODE_FIELDS if f not in node]
    if missing:
        raise HRCImportError(
            f"nodes/{idx}.json: faltam campos obrigatorios {missing}"
        )


def open_hrc_zip(zip_bytes: bytes) -> zipfile.ZipFile:
    """Abre o zip a partir dos bytes em memoria. ZipFile fica aberto —
    caller e responsavel por fechar (usar como context manager)."""
    try:
        return zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile as exc:
        raise HRCImportError(f"Zip invalido: {exc}") from exc


def list_node_indices(zf: zipfile.ZipFile) -> list[int]:
    """Devolve a lista ordenada de indices de nodes encontrados no zip."""
    indices: list[int] = []
    for name in zf.namelist():
        m = _NODE_FILENAME_RE.match(name)
        if m:
            indices.append(int(m.group(1)))
    indices.sort()
    return indices


def read_settings(zf: zipfile.ZipFile) -> dict:
    if "settings.json" not in zf.namelist():
        raise HRCImportError("zip nao contem settings.json")
    try:
        settings = json.loads(zf.read("settings.json"))
    except json.JSONDecodeError as exc:
        raise HRCImportError(f"settings.json: JSON invalido — {exc}") from exc
    _validate_settings(settings)
    return settings


def read_equity(zf: zipfile.ZipFile) -> dict:
    if "equity.json" not in zf.namelist():
        raise HRCImportError("zip nao contem equity.json")
    try:
        equity = json.loads(zf.read("equity.json"))
    except json.JSONDecodeError as exc:
        raise HRCImportError(f"equity.json: JSON invalido — {exc}") from exc
    _validate_equity(equity)
    return equity


def iter_nodes(
    zf: zipfile.ZipFile, indices: list[int] | None = None
) -> Iterator[Tuple[int, dict]]:
    """Yields (node_idx, node_dict) por ordem crescente de idx.

    Lazy — le e parseia um node de cada vez para evitar reter 9000+ dicts
    em memoria simultaneamente.
    """
    if indices is None:
        indices = list_node_indices(zf)
    for idx in indices:
        name = f"nodes/{idx}.json"
        try:
            node = json.loads(zf.read(name))
        except KeyError as exc:
            raise HRCImportError(f"node {idx}: ficheiro {name} ausente") from exc
        except json.JSONDecodeError as exc:
            raise HRCImportError(f"{name}: JSON invalido — {exc}") from exc
        _validate_node(idx, node)
        yield idx, node


def parse_hrc_zip_summary(zip_bytes: bytes) -> dict:
    """Validacao + summary leve (sem carregar nodes em memoria).

    Devolve {settings, equity, total_nodes, node_indices}. Util para
    pre-flight checks antes de iniciar import pesado.
    """
    zf = open_hrc_zip(zip_bytes)
    try:
        settings = read_settings(zf)
        equity = read_equity(zf)
        indices = list_node_indices(zf)
        if not indices:
            raise HRCImportError("zip nao contem nenhum ficheiro nodes/N.json")
        if 0 not in indices:
            raise HRCImportError("zip nao contem nodes/0.json (root node)")
    finally:
        zf.close()
    return {
        "settings": settings,
        "equity": equity,
        "total_nodes": len(indices),
        "node_indices": indices,
    }
