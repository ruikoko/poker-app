"""Import por pasta local → Poker App (#pt55). Estilo apphm3: corre no PC do Rui,
SÓ a pedido (duplo-clique depois da sessão de poker), nunca em background.

Varre 4 subpastas (uma por tipo) sob uma pasta-mãe configurável e envia para a
app SÓ o que é novo. A app faz o resto (Vision, matching). Reutiliza os MESMOS
endpoints do upload manual da UI — o agente é só um cliente HTTP autenticado.

Incremental + idempotente: ficheiro presente na subpasta = ainda por enviar.
Depois de enviar com SUCESSO (HTTP 2xx), MOVE o ficheiro para `done/<tipo>/`
(preserva o original; mover ≠ apagar). Se falhar, FICA → retry no próximo
duplo-clique. O nome original é SEMPRE preservado no upload (as SS do IT/manual
tiram o captured_at/TM do nome).

Routing é pela SUBPASTA (determinístico — nunca adivinha imagem IT vs SS manual).
HM3 fica de fora (tem o seu .bat); Discord/lobby ficam de fora (sync de rede).
"""
import os
import sys
import shutil
from datetime import datetime

try:
    import requests
except ImportError:
    print("ERRO: instala o módulo requests primeiro:")
    print("  pip install requests")
    sys.exit(1)

try:
    from config_local import PARENT_DIR, LOGIN_EMAIL, LOGIN_PASS
except ImportError:
    print("ERRO: config_local.py não encontrado.")
    print("Copia config_local.example.py para config_local.py e preenche")
    print("com a pasta-mãe + credenciais da poker app.")
    sys.exit(1)

# Fonte "lobby" (opcional): pasta EXTERNA (ex.: Capturas de Ecrã do Windows),
# lida DIRECTAMENTE, sem mover ficheiros. None se não configurada.
try:
    from config_local import LOBBY_DIR
except ImportError:
    LOBBY_DIR = None

# (OPCIONAL) Só processa lobbys com captura (mtime) >= esta data — evita correr
# Vision na história toda na 1ª corrida e mantém o scope (ex.: "2026-05-30").
try:
    from config_local import LOBBY_SINCE
except ImportError:
    LOBBY_SINCE = None

POKER_APP_URL = "https://poker-app-production-34a7.up.railway.app"

# (subpasta, endpoint, extensões aceites, mime por extensão)
_IMG = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
_DOC = {".zip": "application/zip", ".txt": "text/plain"}
TYPES = [
    ("gg_hh",  "/api/import",                        _DOC, "GG hand history (.zip/.txt)"),
    ("gg_ts",  "/api/tournament-summaries/import",   _DOC, "GG tournament summaries (.zip/.txt)"),
    ("it",     "/api/table-ss/upload",               _IMG, "SS de mesa Intuitive Tables (imagem)"),
    ("manual", "/api/screenshots",                   _IMG, "SS manual do replayer GG (imagem)"),
]


def login(session):
    r = session.post(
        f"{POKER_APP_URL}/api/auth/login",
        json={"email": LOGIN_EMAIL, "password": LOGIN_PASS},
        timeout=60,
    )
    if r.status_code != 200:
        print(f"ERRO login: {r.status_code} {r.text}")
        sys.exit(1)
    print(f"Login OK: {LOGIN_EMAIL}\n")


def scaffold():
    """Cria a pasta-mãe + subpastas por tipo + área done/ se faltarem."""
    for sub, *_ in TYPES:
        os.makedirs(os.path.join(PARENT_DIR, sub), exist_ok=True)
        os.makedirs(os.path.join(PARENT_DIR, "done", sub), exist_ok=True)


def _dest_no_clobber(done_dir, fname):
    """Caminho em done/ que não sobrescreve um ficheiro já lá (preserva originais)."""
    dest = os.path.join(done_dir, fname)
    if not os.path.exists(dest):
        return dest
    base, ext = os.path.splitext(fname)
    n = 2
    while os.path.exists(os.path.join(done_dir, f"{base} ({n}){ext}")):
        n += 1
    return os.path.join(done_dir, f"{base} ({n}){ext}")


def _summary_line(resp):
    """Resumo compacto da resposta da app (campos típicos por endpoint)."""
    try:
        j = resp.json()
    except Exception:
        return resp.text[:120]
    for keys in (
        ("hands_inserted", "hands_skipped"),   # /api/import (hands)
        ("ts_inserted", "ts_updated"),          # /api/import (ts) / summaries
        ("inserted", "updated"),                # /api/tournament-summaries/import
        ("result", "hand_matched"),             # /api/table-ss/upload
        ("message",),                           # /api/screenshots
        ("status",),
    ):
        if any(k in j for k in keys):
            return " ".join(f"{k}={j[k]}" for k in keys if k in j)
    return str(j)[:120]


def process_type(session, sub, endpoint, exts, label):
    src = os.path.join(PARENT_DIR, sub)
    done = os.path.join(PARENT_DIR, "done", sub)
    files = [f for f in sorted(os.listdir(src))
             if os.path.isfile(os.path.join(src, f))
             and os.path.splitext(f)[1].lower() in exts]
    sent = failed = skipped = 0
    others = [f for f in os.listdir(src)
              if os.path.isfile(os.path.join(src, f))
              and os.path.splitext(f)[1].lower() not in exts]
    skipped = len(others)

    print(f"── {sub}/  ({label})  — {len(files)} ficheiro(s) novo(s)")
    for fname in files:
        path = os.path.join(src, fname)
        ext = os.path.splitext(fname)[1].lower()
        mime = exts[ext]
        try:
            with open(path, "rb") as fh:
                # nome original SEMPRE preservado (captured_at/TM vêm do nome).
                r = session.post(
                    f"{POKER_APP_URL}{endpoint}",
                    files={"file": (fname, fh, mime)},
                    timeout=600,
                )
        except Exception as e:
            failed += 1
            print(f"   ✗ {fname}: EXC {type(e).__name__}: {e}")
            continue
        if 200 <= r.status_code < 300:
            sent += 1
            print(f"   ✓ {fname}: {_summary_line(r)}")
            shutil.move(path, _dest_no_clobber(done, fname))   # move ≠ apagar
        else:
            failed += 1
            print(f"   ✗ {fname}: HTTP {r.status_code} {r.text[:120]}")
    return sent, failed, skipped


# ── Fonte "lobby" — pasta externa lida directa (sem mover), dedup por manifesto ─

def _lobby_manifest_path():
    return os.path.join(PARENT_DIR, "lobby_sent.txt")


def _read_manifest(path):
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())


def _append_manifest(path, name):
    with open(path, "a", encoding="utf-8") as f:
        f.write(name + "\n")


def process_lobby_dir(session):
    """Lê a pasta de Capturas (LOBBY_DIR) DIRECTAMENTE — misturada com outros
    screenshots, NÃO se movem ficheiros. Dedup pelo nome (Windows traz data+hora
    = único) via manifesto `lobby_sent.txt`. O backend faz o gate 'é lobby?'
    (não-lobby → ignorado). Devolve (lobbies, nao_lobbies, falhas) ou None."""
    if not LOBBY_DIR:
        return None
    if not os.path.isdir(LOBBY_DIR):
        print(f"\n── lobby: LOBBY_DIR não existe ({LOBBY_DIR}) — salto")
        return None
    # LOBBY_SINCE: só capturas (mtime) >= esta data. Evita Vision na história toda.
    since = None
    if LOBBY_SINCE:
        try:
            since = datetime.fromisoformat(LOBBY_SINCE)
        except (ValueError, TypeError):
            print(f"   (aviso: LOBBY_SINCE inválido {LOBBY_SINCE!r} — ignorado)")
    mpath = _lobby_manifest_path()
    sent = _read_manifest(mpath)
    candidates = [f for f in sorted(os.listdir(LOBBY_DIR))
                  if os.path.isfile(os.path.join(LOBBY_DIR, f))
                  and os.path.splitext(f)[1].lower() in _IMG
                  and f not in sent]
    files, skipped_old = [], 0
    for f in candidates:
        mt = datetime.fromtimestamp(os.path.getmtime(os.path.join(LOBBY_DIR, f)))
        if since and mt < since:
            skipped_old += 1          # fora do scope — NÃO marca (re-filtra por data)
        else:
            files.append((f, mt))
    extra = f"  (fora de LOBBY_SINCE: {skipped_old})" if skipped_old else ""
    print(f"\n── lobby/  (pasta de Capturas, lida directa, sem mover)  — {len(files)} novo(s){extra}")
    lobby = nonlobby = failed = 0
    for fname, mt in files:
        path = os.path.join(LOBBY_DIR, fname)
        mime = _IMG[os.path.splitext(fname)[1].lower()]
        cap = mt.isoformat()          # captured_at = mtime (Lisboa) → âncora prestart
        try:
            with open(path, "rb") as fh:
                r = session.post(
                    f"{POKER_APP_URL}/api/lobbys/upload",
                    files={"file": (fname, fh, mime)},
                    data={"captured_at": cap}, timeout=300,
                )
        except Exception as e:
            failed += 1
            print(f"   ⟳ {fname}: EXC {type(e).__name__}: {e} → retry depois")
            continue
        if not (200 <= r.status_code < 300):
            failed += 1
            print(f"   ⟳ {fname}: HTTP {r.status_code} {r.text[:100]} → retry depois")
            continue
        j = {}
        try:
            j = r.json()
        except Exception:
            pass
        result = j.get("result")
        # Falha TRANSITÓRIA da Vision (vision_failed) → NÃO marca → retry na próxima
        # corrida. Distinto de não-lobby genuíno (json_invalid/site_undetected →
        # ignora + marca). Um soluço transitório nunca perde um lobby real.
        if result == "vision_failed":
            failed += 1
            print(f"   ⟳ {fname}: Vision falhou (transitório) → retry depois (não marcado)")
            continue
        if j.get("is_lobby"):
            lobby += 1
            print(f"   ✓ {fname}: LOBBY {j.get('site')} {j.get('tournament_name')!r} "
                  f"→ tn={j.get('tournament_number')} ({result})")
        else:
            nonlobby += 1
            print(f"   · {fname}: ignorado (não-lobby: {result})")
        _append_manifest(mpath, fname)   # lobby OU não-lobby genuíno → não re-Vision
    return (lobby, nonlobby, failed)


def main():
    if not os.path.isdir(PARENT_DIR):
        print(f"A criar a pasta-mãe: {PARENT_DIR}")
        os.makedirs(PARENT_DIR, exist_ok=True)
    scaffold()
    print(f"Pasta-mãe: {PARENT_DIR}")
    print(f"Poker App: {POKER_APP_URL}")
    print("─" * 56)

    session = requests.Session()
    login(session)

    totals = {}
    for sub, endpoint, exts, label in TYPES:
        totals[sub] = process_type(session, sub, endpoint, exts, label)

    lobby_res = process_lobby_dir(session)

    print("\n" + "═" * 56)
    print("RESUMO")
    print("═" * 56)
    tot_sent = tot_fail = 0
    for sub, *_ in TYPES:
        sent, failed, skipped = totals[sub]
        tot_sent += sent
        tot_fail += failed
        extra = f"  (ignorados por extensão: {skipped})" if skipped else ""
        print(f"  {sub:8} enviados={sent}  falhas={failed}{extra}")
    if lobby_res is not None:
        lob, nonlob, lfail = lobby_res
        tot_fail += lfail
        print(f"  {'lobby':8} lobbies={lob}  não-lobby(ignorados)={nonlob}  falhas={lfail}")
    print("─" * 56)
    print(f"  TOTAL enviados={tot_sent}  falhas={tot_fail}")
    if tot_fail:
        print("\n  ⚠ Ficheiros com falha FICARAM na subpasta — retry no próximo duplo-clique.")
    print(f"\n  Enviados movidos para: {os.path.join(PARENT_DIR, 'done')}")


if __name__ == "__main__":
    main()
