"""hrc_adapter.py — bridge entre API poker-app e watcher HRC no Beelink.

Loop contínuo que:
1. Puxa zips de mãos novas via GET /api/queue/hrc
2. Descomprime para C:\\Users\\Administrator\\Documents\\Teste completo\\<hand_id>\\
3. Espera o watcher local processar (zip em done\\ ou marker .failed em queue\\)
4. POST /api/queue/hrc/results com o zip ou com o motivo de falha
5. Mantém C:\\hrc\\adapter\\state.json como registo local

Decisões aprovadas em pt22 Passo 2 PASSO 1: D1-D10 + A1-A5.
"""
from __future__ import annotations

import io
import json
import logging
import logging.handlers
import os
import re
import shutil
import sys
import time
import traceback
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# pt25: helper para rewrite de script_path no payouts.json pós-unzip.
# Pure-stdlib, importável sem o resto do adapter (facilita pytest do backend).
from payouts_helpers import rewrite_script_path_in_meta


# ----- config -----
API_BASE_DEFAULT  = "https://poker-app-production-34a7.up.railway.app"
QUEUE_DIR_DEFAULT = r"C:\Users\Administrator\Documents\Teste completo"

DONE_SUBDIR       = "done"
ARQUIVO_SUBDIR    = "arquivo"
REPLIED_SUBDIR    = "replied"
RESERVED_NAMES    = {DONE_SUBDIR, ARQUIVO_SUBDIR, REPLIED_SUBDIR, "manifest.json"}

ADAPTER_HOME       = Path(r"C:\hrc\adapter")
LOG_DIR            = ADAPTER_HOME / "logs"
MANIFESTS_DIR      = LOG_DIR / "manifests"
STATE_FILE         = ADAPTER_HOME / "state.json"
LOG_FILE           = LOG_DIR / "hrc_adapter.log"
LOG_RETENTION_DAYS = 14
# pt82 (#HRC-TREES-PERSIST-BEELINK) — arquivo PERMANENTE dos trees de output no
# Beelink. O zip resolvido é COPIADO para cá (nome legível do meta), ANTES do
# move-para-replied. SEM limpeza automática — ficam aqui sempre; o Rui sobe ao
# estudo só os que escolher, pela porta manual (GTO Brain / HRC Sessions).
TREES_DIR          = Path(r"C:\hrc\trees")

POLL_INTERVAL_DEFAULT = 60
HAND_ID_RE = re.compile(r"^[A-Z]+-\d+(-\d+)*$")

ENV_API_KEY      = "HRC_WATCHER_API_KEY"
ENV_API_BASE     = "HRC_ADAPTER_API_BASE"
ENV_QUEUE_DIR    = "HRC_ADAPTER_QUEUE_DIR"
ENV_POLL_INTERVAL = "HRC_POLL_INTERVAL_S"

STATUS_PULLED     = "pulled"
STATUS_PROCESSING = "processing"  # reservado para futuro; MVP salta directo a done/failed
STATUS_DONE       = "done"
STATUS_FAILED     = "failed"

POST_DONE_TIMEOUT   = (10, 120)
POST_FAILED_TIMEOUT = (10, 60)
PULL_TIMEOUT        = (10, 120)
MAX_ERROR_LEN       = 500

logger = logging.getLogger("hrc_adapter")


# ============================================================
# logging
# ============================================================
def setup_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if logger.handlers:
        return

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    fh = logging.handlers.TimedRotatingFileHandler(
        LOG_FILE, when="midnight", interval=1,
        backupCount=LOG_RETENTION_DAYS, encoding="utf-8",
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)


# ============================================================
# state.json — atomic load / save
# ============================================================
def load_state() -> dict[str, dict[str, Any]]:
    if not STATE_FILE.exists():
        return {}
    try:
        with STATE_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            logger.warning("state.json não é dict (type=%s); a começar do zero",
                           type(data).__name__)
            return {}
        return data
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("state.json corrupto (%s) — a começar do zero", e)
        return {}


def save_state(state: dict[str, dict[str, Any]]) -> None:
    tmp = STATE_FILE.with_name(STATE_FILE.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True, ensure_ascii=False)
    os.replace(tmp, STATE_FILE)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ============================================================
# HTTP session com retry
# ============================================================
def build_session(api_key: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {api_key}"})
    # backoff_factor=5 -> sleep entre tentativas: ~5s, ~10s, ~20s
    # (fórmula urllib3 nativa: backoff_factor * 2**(retry-1))
    retry = Retry(
        total=3,
        backoff_factor=5,
        status_forcelist=[502, 503, 504],
        allowed_methods=frozenset(["GET", "POST"]),
        raise_on_status=False,
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


# ============================================================
# A1 — startup scan
# ============================================================
def startup_scan(queue_dir: Path, state: dict) -> int:
    """Detecta pastas existentes em queue_dir (de uma corrida anterior)
    e marca-as como 'pulled' no state se ainda não estiverem registadas.
    Previne race a frio: sem isto, o próximo pull descomprimiria por cima
    de mãos a meio do processamento."""
    discovered = 0
    for p in queue_dir.iterdir():
        if not p.is_dir():
            continue
        name = p.name
        # tolerar variante de sufixo <hand_id>.failed/
        base = name[:-len(".failed")] if name.endswith(".failed") else name
        if base in RESERVED_NAMES:
            continue
        if base in state:
            continue
        if not HAND_ID_RE.match(base):
            logger.warning("startup_scan: pasta com nome inesperado, skip: %s", name)
            continue
        state[base] = {
            "status": STATUS_PULLED,
            "pulled_at": now_iso(),
            "posted_at": None,
            "result_zip_size": None,
            "error": None,
            "note": "discovered_at_startup",
        }
        discovered += 1
        logger.info("startup_scan: %s -> pulled (descoberta)", base)
    return discovered


# ============================================================
# pull queue
# ============================================================
def pull_queue(session: requests.Session, api_base: str, queue_dir: Path,
               state: dict) -> int:
    """GET /api/queue/hrc, descomprime mãos novas, popula state.
    Devolve nº de mãos novas escritas."""
    url = f"{api_base.rstrip('/')}/api/queue/hrc"
    try:
        resp = session.get(url, params={"include_no_payout": "false"},
                           timeout=PULL_TIMEOUT)
    except requests.RequestException as e:
        logger.warning("pull: network error: %s", e)
        return 0

    if resp.status_code == 401:
        logger.error("pull: 401 — token inválido. Verifica %s no Beelink.",
                     ENV_API_KEY)
        return 0
    if resp.status_code >= 400:
        body = (resp.text or "")[:200]
        logger.warning("pull: HTTP %d body=%r", resp.status_code, body)
        return 0

    written = 0
    manifest_payload: Optional[dict] = None

    try:
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            # 1. agrupar entries por hand_id (e capturar manifest)
            entries_by_hand: dict[str, list[tuple[str, str]]] = {}
            for name in zf.namelist():
                if name == "manifest.json":
                    try:
                        manifest_payload = json.loads(zf.read(name).decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError) as e:
                        logger.warning("pull: manifest.json mal-formado: %s", e)
                    continue
                if "/" not in name:
                    logger.warning("pull: entrada zip sem '/': %r", name)
                    continue
                hand_id, _, fname = name.partition("/")
                if not fname:
                    continue
                entries_by_hand.setdefault(hand_id, []).append((name, fname))

            # pt83 (#HRC-SENT-LIST-AND-REQUEUE) — epoch de re-queue por mão (do
            # manifest). Derrota o dedup D10: re-queue no backend faz epoch++,
            # logo o servido fica > o guardado no state → re-puxa.
            served_epochs = {}
            if isinstance(manifest_payload, dict):
                for e in (manifest_payload.get("hands_included") or []):
                    if isinstance(e, dict) and e.get("hand_id"):
                        served_epochs[e["hand_id"]] = e.get("requeue_epoch", 0) or 0

            # 2. para cada hand_id novo, validar e descomprimir
            for hand_id, files in entries_by_hand.items():
                # A5 — validação defensiva
                if hand_id in RESERVED_NAMES:
                    logger.error("pull: hand_id reservado, SKIP: %s", hand_id)
                    continue
                if not HAND_ID_RE.match(hand_id):
                    logger.warning("pull: hand_id com formato inesperado, skip: %s",
                                   hand_id)
                    continue
                # D10 — state local manda, MAS o requeue_epoch (pt83) derrota o
                # dedup: re-puxa se o backend serviu um epoch > o do state.
                served_epoch = served_epochs.get(hand_id, 0)
                if hand_id in state and served_epoch <= (state[hand_id].get("requeue_epoch", 0)):
                    continue
                if hand_id in state:
                    logger.info("pull %s: re-queue (epoch %s > %s) — a re-puxar",
                                hand_id, served_epoch, state[hand_id].get("requeue_epoch", 0))
                    # limpa pack/markers stale (.failed/.done) antes de re-escrever,
                    # para o watcher voltar a apanhar a mão em get_pending.
                    _stale = queue_dir / hand_id
                    if _stale.exists():
                        _safe_rmtree(_stale)

                target_dir = queue_dir / hand_id
                try:
                    target_dir.mkdir(parents=True, exist_ok=True)
                    for name, fname in files:
                        target_file = target_dir / fname
                        target_file.parent.mkdir(parents=True, exist_ok=True)
                        with zf.open(name) as src, target_file.open("wb") as dst:
                            shutil.copyfileobj(src, dst)
                except OSError as e:
                    logger.error("pull %s: IO error: %s", hand_id, e)
                    # cleanup parcial — só apaga se nada do hand_id estava
                    # registado, para não pisar uma corrida concorrente
                    if hand_id not in state and target_dir.exists():
                        _safe_rmtree(target_dir)
                    continue

                # pt25 prune-in-gap-downstream: backend pode escrever script.js
                # no zip. Reescreve script_path no meta.json (pt42d — migrado
                # de payouts.json porque HRC rejeitava campos extra) com path
                # absoluto, para o watcher pegar via setup_scripting.
                script_js = target_dir / "script.js"
                meta_path = target_dir / "meta.json"
                if script_js.is_file() and meta_path.is_file():
                    if rewrite_script_path_in_meta(meta_path, str(script_js)):
                        logger.info(
                            "pull %s: script.js detected -> meta.script_path=%s",
                            hand_id, str(script_js),
                        )
                    else:
                        logger.warning(
                            "pull %s: script.js presente mas rewrite meta falhou",
                            hand_id,
                        )

                # pt82 — nome legível do tree (do meta do backend), guardado no
                # state p/ o reconcile_done copiar o output zip para C:\hrc\trees\.
                tree_filename = None
                if meta_path.is_file():
                    try:
                        with meta_path.open(encoding="utf-8") as mf:
                            tree_filename = (json.load(mf) or {}).get("tree_filename")
                    except (OSError, ValueError):
                        pass

                state[hand_id] = {
                    "status": STATUS_PULLED,
                    "pulled_at": now_iso(),
                    "posted_at": None,
                    "result_zip_size": None,
                    "error": None,
                    "tree_filename": tree_filename,
                    "requeue_epoch": served_epoch,  # pt83 — dedup epoch-aware
                }
                written += 1
                logger.info("pull %s OK (%d ficheiro(s)) -> %s",
                            hand_id, len(files), target_dir)
    except zipfile.BadZipFile as e:
        logger.error("pull: zip corrupto: %s", e)
        return 0

    if manifest_payload is not None:
        _persist_manifest(manifest_payload)

    return written


def _persist_manifest(payload: dict) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    mpath = MANIFESTS_DIR / f"manifest_{ts}.json"
    try:
        mpath.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as e:
        logger.warning("persist manifest %s falhou: %s", mpath, e)


# ============================================================
# detect resultados do watcher
# ============================================================
def detect_done_zips(queue_dir: Path) -> list[Path]:
    """Watcher Baltazar (Apr19) grava em `done/Exports/<hand>.zip` —
    descoberto no smoke real pt23 (zip órfão GG-5914506215). Mantemos também
    busca em `done/<hand>.zip` directo para compat com versões futuras ou
    qualquer caller que use o layout flat. Sem `rglob` (defensive: evita
    captura de zips em subpastas inesperadas tipo `done/archived/`)."""
    done_dir = queue_dir / DONE_SUBDIR
    if not done_dir.is_dir():
        return []
    zips: list[Path] = []
    zips.extend(done_dir.glob("*.zip"))
    exports_dir = done_dir / "Exports"
    if exports_dir.is_dir():
        zips.extend(exports_dir.glob("*.zip"))
    return sorted(zips)


def detect_failed_markers(queue_dir: Path) -> list[tuple[str, Path, str]]:
    """Devolve lista (hand_id, pasta_a_apagar, motivo). Cobre 2 layouts:
       1. queue_dir/<hand_id>/.failed       (ficheiro marker dentro da pasta)
       2. queue_dir/<hand_id>.failed/       (sufixo no nome da pasta)
    """
    out: list[tuple[str, Path, str]] = []
    if not queue_dir.is_dir():
        return out
    for p in queue_dir.iterdir():
        if not p.is_dir():
            continue
        name = p.name
        if name in RESERVED_NAMES:
            continue

        # Layout 2: <hand_id>.failed/
        if name.endswith(".failed"):
            hand_id = name[:-len(".failed")]
            if HAND_ID_RE.match(hand_id):
                out.append((hand_id, p, _read_motivo_from_folder(p)))
            continue

        # Layout 1: <hand_id>/.failed
        if not HAND_ID_RE.match(name):
            continue
        marker = p / ".failed"
        if marker.is_file():
            motivo = _read_motivo_file(marker) or _read_motivo_from_folder(p) or "unknown"
            out.append((name, p, motivo))
    return out


def _read_motivo_file(path: Path) -> str:
    try:
        txt = path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""
    return txt[:MAX_ERROR_LEN]


def _read_motivo_from_folder(folder: Path) -> str:
    """Procura motivo num marker dentro da pasta. Layout 2 não tem o ficheiro
    `.failed` standard — pode ter `failed.txt`, `error.txt` ou similar."""
    for cand in (".failed", "failed.txt", "error.txt", "FAILED", "error"):
        f = folder / cand
        if f.is_file():
            txt = _read_motivo_file(f)
            if txt:
                return txt
    return "unknown"


# ============================================================
# POST results
# ============================================================
def _ensure_meta_in_zip(zip_path: Path, hand_id: str) -> bytes:
    """pt23 fix: o watcher Baltazar Apr19 NÃO injecta `meta.json` directamente
    no export do HRC — confiava num "bot externo" que movia o zip para
    `done/replied/` e depois `inject_meta_into_zip` corria no main loop. Esse
    bot não existe na pipeline poker-app→adapter→watcher; logo o adapter
    assume essa responsabilidade aqui.

    Se o zip já contém `meta.json`, devolve os bytes intactos. Caso contrário,
    repacka o zip adicionando um `meta.json` minimal `{hand_id, exported_at,
    source, watcher_built_meta=False}`. Backend augmenta server-side com
    `received_at` + `received_from`.

    Tech debt: #WATCHER-META-INJECTION-BYPASSED — quando refactorizarmos o
    watcher (pt24+) o `inject_meta_into_zip` + `replied/` ficam mortos.
    """
    raw = zip_path.read_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        if "meta.json" in zf.namelist():
            return raw
        entries = [(n, zf.read(n)) for n in zf.namelist()]

    meta = {
        "hand_id": hand_id,
        "exported_at": now_iso(),
        "source": "hrc_adapter_inject",
        "watcher_built_meta": False,
    }
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf_out:
        for name, data in entries:
            zf_out.writestr(name, data)
        zf_out.writestr("meta.json", json.dumps(meta, ensure_ascii=False))
    return out.getvalue()


def post_done(session: requests.Session, api_base: str, hand_id: str,
              zip_path: Path) -> bool:
    url = f"{api_base.rstrip('/')}/api/queue/hrc/results"
    try:
        disk_size = zip_path.stat().st_size
    except OSError as e:
        logger.warning("post %s done: stat falhou: %s", hand_id, e)
        return False

    try:
        zip_bytes = _ensure_meta_in_zip(zip_path, hand_id)
    except (zipfile.BadZipFile, OSError) as e:
        logger.warning("post %s done: zip prep (meta inject) falhou: %s",
                       hand_id, e)
        return False

    upload_size = len(zip_bytes)
    meta_injected = upload_size != disk_size  # heurística simples; suficiente p/ log

    try:
        resp = session.post(
            url,
            params={"hand_id": hand_id, "status": "done"},
            files={"file": (zip_path.name, zip_bytes, "application/zip")},
            timeout=POST_DONE_TIMEOUT,
        )
    except requests.RequestException as e:
        logger.warning("post %s done: network error: %s", hand_id, e)
        return False

    if resp.status_code == 200:
        action = _safe_json(resp).get("action", "?")
        logger.info(
            "post %s done OK disk_size=%d upload_size=%d meta_injected=%s action=%s",
            hand_id, disk_size, upload_size, meta_injected, action,
        )
        return True

    logger.error("post %s done HTTP %d body=%r",
                 hand_id, resp.status_code, (resp.text or "")[:300])
    return False


def post_failed(session: requests.Session, api_base: str, hand_id: str,
                error: str) -> bool:
    url = f"{api_base.rstrip('/')}/api/queue/hrc/results"
    try:
        resp = session.post(
            url,
            params={"hand_id": hand_id, "status": "failed",
                    "error": (error or "unknown")[:MAX_ERROR_LEN]},
            timeout=POST_FAILED_TIMEOUT,
        )
    except requests.RequestException as e:
        logger.warning("post %s failed: network error: %s", hand_id, e)
        return False

    if resp.status_code == 200:
        action = _safe_json(resp).get("action", "?")
        logger.info("post %s failed OK error=%r action=%s",
                    hand_id, error[:80], action)
        return True

    logger.error("post %s failed HTTP %d body=%r",
                 hand_id, resp.status_code, (resp.text or "")[:300])
    return False


def _safe_json(resp: requests.Response) -> dict:
    try:
        return resp.json()
    except ValueError:
        return {}


# ============================================================
# reconcile (vigia + POST + cleanup)
# ============================================================
def reconcile_done(session: requests.Session, api_base: str,
                   queue_dir: Path, state: dict) -> None:
    for zip_path in detect_done_zips(queue_dir):
        hand_id = zip_path.stem
        if not HAND_ID_RE.match(hand_id):
            logger.warning("done zip com hand_id inesperado, skip: %s", zip_path.name)
            continue

        st = state.get(hand_id)
        if st and st.get("status") == STATUS_DONE:
            # já feito; só limpar o zip stale
            _safe_unlink(zip_path)
            continue

        if not post_done(session, api_base, hand_id, zip_path):
            continue  # tenta outra vez no próximo tick

        try:
            size = zip_path.stat().st_size
        except OSError:
            size = None
        state[hand_id] = {
            **(state.get(hand_id) or {}),
            "status": STATUS_DONE,
            "posted_at": now_iso(),
            "result_zip_size": size,
            "error": None,
        }
        # pt82 — persistência LOCAL permanente do tree de output, ANTES do move/
        # prune do replied/. Best-effort; não bloqueia a fila.
        _copy_to_trees(zip_path, (state.get(hand_id) or {}).get("tree_filename"))
        # pt61: MOVE para replied/ (não unlink) → desbloqueia o arquivar+avançar
        # do watcher Baltazar (#HRC-EXPORT-WRITES-BUT-FINALIZE-HANGS).
        _move_to_replied(zip_path)


def reconcile_failed(session: requests.Session, api_base: str,
                     queue_dir: Path, state: dict) -> None:
    for hand_id, folder, motivo in detect_failed_markers(queue_dir):
        st = state.get(hand_id)
        if st and st.get("status") == STATUS_FAILED:
            # já feito; limpar pasta stale
            _safe_rmtree(folder)
            continue

        if not post_failed(session, api_base, hand_id, motivo):
            continue

        state[hand_id] = {
            **(state.get(hand_id) or {}),
            "status": STATUS_FAILED,
            "posted_at": now_iso(),
            "result_zip_size": None,
            "error": motivo,
        }
        _safe_rmtree(folder)


def _safe_unlink(p: Path) -> None:
    try:
        p.unlink()
        logger.info("unlink %s OK", p)
    except OSError as e:
        logger.warning("unlink %s falhou: %s", p, e)


def _safe_rmtree(p: Path) -> None:
    try:
        shutil.rmtree(p)
        logger.info("rmtree %s OK", p)
    except OSError as e:
        logger.warning("rmtree %s falhou: %s", p, e)


# pt61 (#HRC-EXPORT-WRITES-BUT-FINALIZE-HANGS): após POST OK o adaptador MOVE o
# zip para `<dir_do_zip>/replied/` em vez de o apagar. O main loop do watcher
# Baltazar (`zip_is_ready`) só arquiva a mão + avança quando o zip aparece em
# `os.path.dirname(export_zip)/replied/<basename>` (EXPORT_WAIT_TIMEOUT=24h). Sem
# isto o watcher serial ficava preso em "Activas" por mão. Guardrails:
#  (i)  sem loop — `detect_done_zips` só varre `done/*.zip`+`done/Exports/*.zip`
#       (não `replied/`, que está em RESERVED_NAMES) → o zip sai do radar, 0 re-POST.
#  (ii) `replied/` não acumula — `prune_replied` apaga por idade (≥ RETENTION,
#       bem depois de o watcher ter consumido o zip; unlink puro, NUNCA POST).
REPLIED_RETENTION_S = 3600  # 1h: o watcher arquiva em segundos/minutos


def _copy_to_trees(zip_path: Path, tree_filename) -> None:
    """pt82 (#HRC-TREES-PERSIST-BEELINK) — COPIA (não move) o zip de output para
    `C:\\hrc\\trees\\<nome legível>` ANTES do move-para-replied. Best-effort: se
    falhar, o pipeline da fila segue na mesma (só não fica a cópia local). Sem
    limpeza automática — ficam lá sempre. Nome do meta do backend; fallback
    `<hand_id>.zip` quando ausente (packs antigos / zip não-pulled)."""
    name = (tree_filename or "").strip() or (zip_path.stem + ".zip")
    try:
        TREES_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(zip_path), str(TREES_DIR / name))   # sobrescreve = idempotente
        logger.info("trees: copiado %s -> %s", zip_path.name, TREES_DIR / name)
    except OSError as e:
        logger.warning("trees: copia de %s falhou (%s) — fila segue na mesma",
                       zip_path.name, e)


def _move_to_replied(zip_path: Path) -> None:
    """Move `zip_path` → `<parent>/replied/<name>` (a pasta que o `zip_is_ready`
    do watcher observa). Cobre os 2 layouts (`done/Exports/...` e `done/...`)
    porque usa o parent real do zip. Fallback unlink se o move falhar."""
    replied_dir = zip_path.parent / REPLIED_SUBDIR
    try:
        replied_dir.mkdir(parents=True, exist_ok=True)
        dest = replied_dir / zip_path.name
        if dest.exists():
            dest.unlink()
        shutil.move(str(zip_path), str(dest))
        logger.info("move %s -> %s OK", zip_path.name, replied_dir)
    except OSError as e:
        logger.warning("move %s -> replied falhou: %s — fallback unlink",
                       zip_path.name, e)
        _safe_unlink(zip_path)


def prune_replied(queue_dir: Path, max_age_s: int = REPLIED_RETENTION_S) -> None:
    """Apaga zips em `replied/` mais velhos que `max_age_s` (retention; o watcher
    já os consumiu). Unlink puro — NUNCA POST nem re-scan p/ POST (guardrail ii).
    Cobre `done/replied/` e `done/Exports/replied/`."""
    done_dir = queue_dir / DONE_SUBDIR
    candidates = [done_dir / REPLIED_SUBDIR, done_dir / "Exports" / REPLIED_SUBDIR]
    now = time.time()
    for rdir in candidates:
        if not rdir.is_dir():
            continue
        for zp in rdir.glob("*.zip"):
            try:
                if now - zp.stat().st_mtime >= max_age_s:
                    zp.unlink()
                    logger.info("prune_replied: unlink %s (idade > %ds)",
                                zp.name, max_age_s)
            except OSError as e:
                logger.warning("prune_replied: %s falhou: %s", zp.name, e)


# ============================================================
# main loop
# ============================================================
def main() -> int:
    setup_logging()

    api_key = os.environ.get(ENV_API_KEY)
    if not api_key:
        logger.critical(
            "env %s ausente — define com: setx %s <token>  (e abre nova shell)",
            ENV_API_KEY, ENV_API_KEY,
        )
        return 2

    api_base  = os.environ.get(ENV_API_BASE, API_BASE_DEFAULT)
    queue_dir = Path(os.environ.get(ENV_QUEUE_DIR, QUEUE_DIR_DEFAULT))
    try:
        poll_interval = int(os.environ.get(
            ENV_POLL_INTERVAL, str(POLL_INTERVAL_DEFAULT)))
    except ValueError:
        logger.warning("env %s inválido, usa default %ds",
                       ENV_POLL_INTERVAL, POLL_INTERVAL_DEFAULT)
        poll_interval = POLL_INTERVAL_DEFAULT

    if not queue_dir.is_dir():
        logger.critical("QUEUE_DIR não existe: %s", queue_dir)
        return 2

    logger.info("hrc_adapter startup")
    logger.info("  API_BASE      = %s", api_base)
    logger.info("  QUEUE_DIR     = %s", queue_dir)
    logger.info("  POLL_INTERVAL = %ds", poll_interval)
    logger.info("  STATE_FILE    = %s", STATE_FILE)
    logger.info("  LOG_FILE      = %s", LOG_FILE)
    logger.info("  retention     = %d days", LOG_RETENTION_DAYS)

    state = load_state()
    discovered = startup_scan(queue_dir, state)
    if discovered:
        save_state(state)
        logger.info("startup_scan: %d pasta(s) descoberta(s) marcadas pulled",
                    discovered)
    else:
        logger.info("startup_scan: nada pendente")

    session = build_session(api_key)
    logger.info("entering main loop")

    while True:
        try:
            n = pull_queue(session, api_base, queue_dir, state)
            reconcile_done(session, api_base, queue_dir, state)
            reconcile_failed(session, api_base, queue_dir, state)
            prune_replied(queue_dir)  # pt61: retention do replied/ (sem POST)
            save_state(state)
            if n:
                logger.info("tick: %d nova(s) puxada(s)", n)
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt — a sair")
            try:
                save_state(state)
            except Exception:
                pass
            return 0
        except Exception:
            # A4 — exceções amplas: log full traceback, sleep, continue
            logger.error("erro no tick:\n%s", traceback.format_exc())

        try:
            time.sleep(poll_interval)
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt no sleep — a sair")
            return 0


if __name__ == "__main__":
    sys.exit(main())
