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
    print("─" * 56)
    print(f"  TOTAL enviados={tot_sent}  falhas={tot_fail}")
    if tot_fail:
        print("\n  ⚠ Ficheiros com falha FICARAM na subpasta — retry no próximo duplo-clique.")
    print(f"\n  Enviados movidos para: {os.path.join(PARENT_DIR, 'done')}")


if __name__ == "__main__":
    main()
