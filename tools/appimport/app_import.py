"""Import por pasta local → Poker App (#pt55, routing por NOME desde pt62).
Estilo apphm3: corre no PC do Rui, SÓ a pedido (duplo-clique depois da sessão de
poker), nunca em background.

Varre subpastas sob uma pasta-mãe configurável e envia para a app SÓ o que é
novo. A app faz o resto (Vision, matching). Reutiliza os MESMOS endpoints do
upload manual da UI — o agente é só um cliente HTTP autenticado.

Incremental + idempotente: ficheiro presente na subpasta = ainda por enviar.
Depois de enviar com SUCESSO (HTTP 2xx), MOVE o ficheiro para `done/<tipo>/`
(preserva o original; mover ≠ apagar). Se falhar, FICA → retry no próximo
duplo-clique. O nome original é SEMPRE preservado no upload (as SS do IT/manual
tiram o captured_at/TM/site do nome).

Routing:
  • gg_hh / gg_ts / manual — pela SUBPASTA (determinístico).
  • it — pasta ÚNICA do Intuitive Tables onde convivem SS de MESA e de LOBBY.
        O update recente do IT mete o nome da janela no ficheiro, por isso
        ROTEAMOS pela ANÁLISE DO NOME (ver `classify_it_file`): MESA → table-ss,
        LOBBY → lobbys; o que não tiver a cauda nova do IT é SKIP (legado).

MODO DE TESTE (dry-run) é o DEFEITO: imprime o plano (MESA|LOBBY|SKIP + site +
captured_at + endpoint) SEM enviar e SEM mover. Passar `--ao-vivo` para enviar a
sério. `LOBBY_DIR` (pasta externa de Capturas) passou a 2ª via MANUAL: só é lida
com `--lobby-dir`.

HM3 fica de fora (tem o seu .bat); o sync do Discord #lobbys é via rede, à parte.
"""
import argparse
import os
import re
import shutil
import sys
from datetime import datetime

try:
    import requests
except ImportError:                       # import sempre seguro (testes do classificador)
    requests = None

POKER_APP_URL = "https://poker-app-production-34a7.up.railway.app"

# (subpasta, endpoint, extensões aceites, mime por extensão) — routing pela subpasta.
_IMG = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
_DOC = {".zip": "application/zip", ".txt": "text/plain"}
TYPES = [
    ("gg_hh",  "/api/import",                        _DOC, "GG hand history (.zip/.txt)"),
    ("gg_ts",  "/api/tournament-summaries/import",   _DOC, "GG tournament summaries (.zip/.txt)"),
    ("manual", "/api/screenshots",                   _IMG, "SS manual do replayer GG (imagem)"),
]

# Pasta ÚNICA do Intuitive Tables (mesa + lobby misturados) — routing por NOME.
IT_SUB = "it"
# Subpasta dedicada drop-only-these p/ SS de lobby (back-compat; captured_at=mtime).
LOBBY_SUB = "lobby"

# Config local (preenchida por load_config; globals p/ as funções de envio).
PARENT_DIR = None
LOGIN_EMAIL = None
LOGIN_PASS = None
LOBBY_DIR = None        # pasta EXTERNA opcional (2ª via manual, só com --lobby-dir)
LOBBY_SINCE = None      # só capturas (mtime) >= esta data, na LOBBY_DIR


def load_config():
    """Carrega config_local.py para os globals. Chamada só em main() (mantém o
    `import app_import` seguro para os testes do classificador, que não precisam
    de credenciais)."""
    global PARENT_DIR, LOGIN_EMAIL, LOGIN_PASS, LOBBY_DIR, LOBBY_SINCE
    try:
        import config_local as cfg
    except ImportError:
        print("ERRO: config_local.py não encontrado.")
        print("Copia config_local.example.py para config_local.py e preenche")
        print("com a pasta-mãe + credenciais da poker app.")
        sys.exit(1)
    PARENT_DIR = cfg.PARENT_DIR
    LOGIN_EMAIL = cfg.LOGIN_EMAIL
    LOGIN_PASS = cfg.LOGIN_PASS
    LOBBY_DIR = getattr(cfg, "LOBBY_DIR", None)
    LOBBY_SINCE = getattr(cfg, "LOBBY_SINCE", None)


# ── Classificador determinístico por NOME (pasta única `it`) ──────────────────
# pt62 — o Intuitive Tables passou a usar UMA pasta para SS de mesa E de lobby,
# com o nome da janela no ficheiro. Decidimos o destino pelo NOME, não pela
# subpasta. O SITE sai do 1º token (mapa ÚNICO, espelho do backend `table_ss`).

# Mapa ÚNICO token→site (mesa E lobby). Chaves em minúsculas; o sufixo '.exe'
# (prefixo do nome do executável do IT, ex. 'GGnet.exe') é aparado antes do
# lookup. PONTO ÚNICO para acrescentar PS/WPN/CoinPoker depois.
_SITE_TOKEN_MAP = {
    "ggpoker": "GGPoker",
    "ggnet": "GGPoker",          # IT: GGnet.exe
    "winamax": "Winamax",        # IT: Winamax.exe
    "wpn": "WPN",
    "stars": "PokerStars",
    "pokerstars": "PokerStars",
}

# Cauda NOVA do IT, antes da extensão: `-YYYYMMDDHHMMSS-NN`. É o que distingue um
# ficheiro do IT novo de um legado (Shot<N>-…-YYYYMMDDHHMMSS, sem o `-NN`).
_IT_TAIL_RE = re.compile(r"-(\d{14})-\d+$")
# Marcador de MESA da Winamax no miolo do nome: `(#<dígitos>)` (nº de mesa).
_WN_TABLE_RE = re.compile(r"\(#\d+\)")
# pt68 — formato ANTIGO do Intuitive Tables: `Shot<N>-<Site>-<YYYYMMDDHHMMSS>`
# (sem cauda `-NN`, sem torneio/blinds no nome). O site é o token APÓS `Shot<N>-`.
# Roteamos como MESA (era a captura da mesa do IT antigo); o site + captured_at
# saem do nome e o match à mão faz-se pela janela temporal do backend (sem tn,
# que o formato antigo não tem). O backend já suporta este formato
# (`parse_table_ss_filename` Shot<N>- → site[1]; `derive_captured_at` \d{14};
# `compute_table_ss_match` filename_tn=None → janela). Coexiste com o NOVO.
_OLD_SHOT_RE = re.compile(r"^Shot\d+-(?P<site>.+)-(?P<ts>\d{14})$", re.IGNORECASE)


def normalize_site(token):
    """Token do 1º campo do nome → site canónico. Apara '.exe'; case-insensitive.
    None se desconhecido."""
    if not token:
        return None
    t = token.strip()
    if t.lower().endswith(".exe"):
        t = t[:-4]
    return _SITE_TOKEN_MAP.get(t.lower())


def classify_it_file(filename):
    """Classifica um ficheiro da pasta única `it` pela ANÁLISE DO NOME.

    Devolve (kind, site, captured_at_iso):
      • kind ∈ {'MESA', 'LOBBY', 'SKIP'}
      • site = site canónico do 1º token (ou None)
      • captured_at_iso = timestamp do nome (`-YYYYMMDDHHMMSS-NN`) em ISO, ou None

    Regras:
      • MESA (antigo, pt68) — `Shot<N>-<Site>-<YYYYMMDDHHMMSS>` (sem cauda `-NN`):
                site do token APÓS `Shot<N>-`, captured_at do timestamp; sem tn
                (o backend casa pela janela temporal). Ver `_OLD_SHOT_RE`.
      • MESA  — miolo com marcador de mesa: GG `" - Blinds "`/`" - Table "`, ou
                Winamax `(#<dígitos>)`.
      • LOBBY — qualquer outro ficheiro com cauda nova do IT.
      • SKIP  — sem cauda nova do IT E não é `Shot<N>-…` (desconhecido). Fica no sítio.
    """
    base = filename.rsplit(".", 1)[0] if "." in filename else filename
    m = _IT_TAIL_RE.search(base)
    if not m:
        # pt68 — formato ANTIGO `Shot<N>-<Site>-<YYYYMMDDHHMMSS>` → MESA.
        mo = _OLD_SHOT_RE.match(base)
        if mo:
            try:
                captured = datetime.strptime(
                    mo.group("ts"), "%Y%m%d%H%M%S").isoformat()
            except ValueError:
                captured = None
            return ("MESA", normalize_site(mo.group("site")), captured)
        return ("SKIP", None, None)
    try:
        captured = datetime.strptime(m.group(1), "%Y%m%d%H%M%S").isoformat()
    except ValueError:
        captured = None
    site = normalize_site(base.split("-", 1)[0])
    middle = base[:m.start()]          # tudo antes da cauda (prefixo + título)
    is_table = (" - Blinds " in middle or " - Table " in middle
                or _WN_TABLE_RE.search(middle) is not None)
    return ("MESA" if is_table else "LOBBY", site, captured)


def lobby_name_hint(filename):
    """Nome do torneio a partir de um filename de LOBBY do IT, ou None (pt63).

    O lobby do IT chama-se `<SiteToken>-<Título>-<YYYYMMDDHHMMSS>-<NN>.ext`. No GG
    o `<Título>` é o nome real do torneio (ex.: `Bounty Hunters Hyper Special $108`);
    na Winamax é só a palavra da app (`Winamax`) → sem hint útil. Devolvido ao
    backend como precedência/desempate sobre o nome lido pela Vision. None quando
    não há cauda do IT, não há título, ou o título é só o nome da sala/app."""
    base = filename.rsplit(".", 1)[0] if "." in filename else filename
    m = _IT_TAIL_RE.search(base)
    if not m:
        return None
    parts = base[:m.start()].split("-", 1)   # [site_token, título]
    if len(parts) < 2:
        return None
    title = parts[1].strip()
    # título vazio ou que é só a palavra da sala/app (ex.: 'Winamax') → sem hint
    if not title or normalize_site(title) is not None:
        return None
    return title


# ── HTTP / utils ──────────────────────────────────────────────────────────────

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
    """Cria a pasta-mãe + subpastas + área done/ se faltarem."""
    for sub, *_ in TYPES:
        os.makedirs(os.path.join(PARENT_DIR, sub), exist_ok=True)
        os.makedirs(os.path.join(PARENT_DIR, "done", sub), exist_ok=True)
    # 'it' (mista, classificada por nome) + 'lobby' (drop-only) — fora de TYPES.
    for sub in (IT_SUB, LOBBY_SUB):
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


def _imgs_in(folder):
    return [f for f in sorted(os.listdir(folder))
            if os.path.isfile(os.path.join(folder, f))
            and os.path.splitext(f)[1].lower() in _IMG]


# ── Envio de 1 ficheiro (reutilizado pelas várias fontes) ─────────────────────

def _post_table_ss(session, path, fname):
    """POST /api/table-ss/upload. Devolve (ok, resumo)."""
    mime = _IMG[os.path.splitext(fname)[1].lower()]
    try:
        with open(path, "rb") as fh:
            r = session.post(f"{POKER_APP_URL}/api/table-ss/upload",
                             files={"file": (fname, fh, mime)}, timeout=600)
    except Exception as e:
        return (False, f"EXC {type(e).__name__}: {e}")
    if 200 <= r.status_code < 300:
        return (True, _summary_line(r))
    return (False, f"HTTP {r.status_code} {r.text[:120]}")


def _post_lobby(session, path, fname, captured_iso, site_hint=None, name_hint=None):
    """POST /api/lobbys/upload. Devolve (status, resumo); status ∈
    {'lobby', 'nonlobby', 'retry'}. 'retry' = transitório (NÃO mover — um lobby
    real nunca se perde por um soluço de Vision).

    pt63 — `site_hint`/`name_hint` (do NOME do ficheiro, fonte `it`) viajam como
    form fields opcionais; o backend dá-lhes precedência sobre a Vision. A 2ª via
    LOBBY_DIR / subpasta `lobby` não os passam (None) → comportamento de sempre."""
    mime = _IMG[os.path.splitext(fname)[1].lower()]
    data = {"captured_at": captured_iso}
    if site_hint:
        data["site_hint"] = site_hint
    if name_hint:
        data["name_hint"] = name_hint
    try:
        with open(path, "rb") as fh:
            r = session.post(f"{POKER_APP_URL}/api/lobbys/upload",
                             files={"file": (fname, fh, mime)},
                             data=data, timeout=300)
    except Exception as e:
        return ("retry", f"EXC {type(e).__name__}: {e}")
    if not (200 <= r.status_code < 300):
        return ("retry", f"HTTP {r.status_code} {r.text[:100]}")
    j = {}
    try:
        j = r.json()
    except Exception:
        pass
    if j.get("result") == "vision_failed":
        return ("retry", "Vision falhou (transitório)")
    if j.get("is_lobby"):
        return ("lobby", f"LOBBY {j.get('site')} {j.get('tournament_name')!r} "
                         f"→ tn={j.get('tournament_number')} ({j.get('result')})")
    return ("nonlobby", f"não-lobby ({j.get('result')})")


def _mtime_iso(path):
    return datetime.fromtimestamp(os.path.getmtime(path)).isoformat()  # Lisboa naive


# ── Fontes por SUBPASTA (gg_hh / gg_ts / manual) ──────────────────────────────

def process_type(session, sub, endpoint, exts, label, live):
    src = os.path.join(PARENT_DIR, sub)
    done = os.path.join(PARENT_DIR, "done", sub)
    files = [f for f in sorted(os.listdir(src))
             if os.path.isfile(os.path.join(src, f))
             and os.path.splitext(f)[1].lower() in exts]
    skipped = len([f for f in os.listdir(src)
                   if os.path.isfile(os.path.join(src, f))
                   and os.path.splitext(f)[1].lower() not in exts])
    sent = failed = 0

    print(f"── {sub}/  ({label})  — {len(files)} ficheiro(s) novo(s)")
    for fname in files:
        if not live:
            sent += 1
            print(f"   [dry] {fname}  → {endpoint}")
            continue
        path = os.path.join(src, fname)
        mime = exts[os.path.splitext(fname)[1].lower()]
        try:
            with open(path, "rb") as fh:
                r = session.post(f"{POKER_APP_URL}{endpoint}",
                                 files={"file": (fname, fh, mime)}, timeout=600)
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


# ── Pasta única `it` — classificada por NOME (MESA | LOBBY | SKIP) ─────────────

def process_it_mixed(session, live):
    """Pasta única do Intuitive Tables (mesa + lobby). Cada ficheiro é
    classificado pelo NOME e roteado para o endpoint certo. MESA → table-ss
    (move → done/it); LOBBY → lobbys (move → done/lobby, retry transitório fica);
    SKIP → fica no sítio (formato não-IT). Em dry-run só imprime o plano.
    Devolve um dict de contagens."""
    src = os.path.join(PARENT_DIR, IT_SUB)
    done_table = os.path.join(PARENT_DIR, "done", IT_SUB)
    done_lobby = os.path.join(PARENT_DIR, "done", LOBBY_SUB)
    files = _imgs_in(src)
    c = {"mesa": 0, "lobby": 0, "nonlobby": 0, "skip": 0, "retry": 0, "fail": 0}

    print(f"── {IT_SUB}/  (Intuitive Tables — mesa+lobby, routing por nome)  "
          f"— {len(files)} ficheiro(s)")
    for fname in files:
        path = os.path.join(src, fname)
        kind, site, captured = classify_it_file(fname)
        if kind == "SKIP":
            c["skip"] += 1
            print(f"   ⤳ SKIP   {fname}  (formato não-IT)")
            continue
        cap = captured or _mtime_iso(path)   # fallback: mtime do ficheiro
        endpoint = "/api/table-ss/upload" if kind == "MESA" else "/api/lobbys/upload"
        # pt63 — hint de nome do torneio (GG), só relevante p/ LOBBY
        name_hint = lobby_name_hint(fname) if kind == "LOBBY" else None

        if not live:
            hint = f" name_hint={name_hint!r}" if name_hint else ""
            print(f"   [dry] {kind:5} site={site or '?':9} captured_at={cap}  "
                  f"→ {endpoint}{hint}  ({fname})")
            c["mesa" if kind == "MESA" else "lobby"] += 1
            continue

        if kind == "MESA":
            ok, msg = _post_table_ss(session, path, fname)
            if ok:
                c["mesa"] += 1
                print(f"   ✓ MESA   {fname}: {msg}")
                shutil.move(path, _dest_no_clobber(done_table, fname))
            else:
                c["fail"] += 1
                print(f"   ✗ MESA   {fname}: {msg} → retry depois")
        else:  # LOBBY — passa site (do filename) + name_hint (GG) como precedência
            status, msg = _post_lobby(session, path, fname, cap,
                                      site_hint=site, name_hint=name_hint)
            if status == "retry":
                c["retry"] += 1
                print(f"   ⟳ LOBBY  {fname}: {msg} → retry depois (não movido)")
            elif status == "lobby":
                c["lobby"] += 1
                print(f"   ✓ LOBBY  {fname}: {msg}")
                shutil.move(path, _dest_no_clobber(done_lobby, fname))
            else:  # nonlobby
                c["nonlobby"] += 1
                print(f"   · LOBBY  {fname}: {msg} — processado")
                shutil.move(path, _dest_no_clobber(done_lobby, fname))
    return c


# ── Subpasta dedicada "lobby" (drop-only-these; captured_at = mtime) ──────────

def process_lobby_subdir(session, live):
    """Subpasta PARENT_DIR/lobby: SÓ processa o que está cá dentro. captured_at =
    mtime do ficheiro (back-compat para nomes Windows sem timestamp embutido). O
    backend faz o gate 'é lobby?'. Mover: lobby/nonlobby → done/lobby; retry
    transitório → fica. Devolve (lobbies, nao_lobbies, falhas)."""
    src = os.path.join(PARENT_DIR, LOBBY_SUB)
    done = os.path.join(PARENT_DIR, "done", LOBBY_SUB)
    files = _imgs_in(src)
    print(f"── {LOBBY_SUB}/  (SS de lobby, drop-only-these)  — {len(files)} ficheiro(s)")
    lobby = nonlobby = failed = 0
    for fname in files:
        path = os.path.join(src, fname)
        cap = _mtime_iso(path)
        if not live:
            lobby += 1
            print(f"   [dry] LOBBY  captured_at={cap}  → /api/lobbys/upload  ({fname})")
            continue
        status, msg = _post_lobby(session, path, fname, cap)
        if status == "retry":
            failed += 1
            print(f"   ⟳ {fname}: {msg} → retry depois (não movido)")
            continue
        if status == "lobby":
            lobby += 1
            print(f"   ✓ {fname}: {msg}")
        else:
            nonlobby += 1
            print(f"   · {fname}: {msg} — processado")
        shutil.move(path, _dest_no_clobber(done, fname))
    return (lobby, nonlobby, failed)


# ── Fonte "lobby" externa LOBBY_DIR (2ª via MANUAL — só com --lobby-dir) ───────

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


def process_lobby_dir(session, live):
    """Lê a pasta externa LOBBY_DIR DIRECTAMENTE (sem mover), dedup por
    manifesto. 2ª via MANUAL desde pt62: só corre com --lobby-dir. captured_at =
    mtime. Devolve (lobbies, nao_lobbies, falhas) ou None."""
    if not LOBBY_DIR:
        print("\n── lobby (LOBBY_DIR): não configurada em config_local — salto")
        return None
    if not os.path.isdir(LOBBY_DIR):
        print(f"\n── lobby (LOBBY_DIR): não existe ({LOBBY_DIR}) — salto")
        return None
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
            skipped_old += 1
        else:
            files.append((f, mt))
    extra = f"  (fora de LOBBY_SINCE: {skipped_old})" if skipped_old else ""
    print(f"\n── lobby (LOBBY_DIR externa, lida directa, sem mover)  — {len(files)} novo(s){extra}")
    lobby = nonlobby = failed = 0
    for fname, mt in files:
        path = os.path.join(LOBBY_DIR, fname)
        cap = mt.isoformat()
        if not live:
            lobby += 1
            print(f"   [dry] LOBBY  captured_at={cap}  → /api/lobbys/upload  ({fname})")
            continue
        status, msg = _post_lobby(session, path, fname, cap)
        if status == "retry":
            failed += 1
            print(f"   ⟳ {fname}: {msg} → retry depois (não marcado)")
            continue
        if status == "lobby":
            lobby += 1
            print(f"   ✓ {fname}: {msg}")
        else:
            nonlobby += 1
            print(f"   · {fname}: {msg} — ignorado")
        _append_manifest(mpath, fname)
    return (lobby, nonlobby, failed)


# ── Entrada ────────────────────────────────────────────────────────────────--

def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Import por pasta local → Poker App (dry-run por defeito).")
    p.add_argument("--ao-vivo", dest="ao_vivo", action="store_true",
                   help="ENVIA a sério (e move). Sem esta flag = dry-run (só plano).")
    p.add_argument("--lobby-dir", dest="lobby_dir", action="store_true",
                   help="Lê também a LOBBY_DIR externa (2ª via manual; off por defeito).")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    live = args.ao_vivo
    load_config()

    if not os.path.isdir(PARENT_DIR):
        print(f"A criar a pasta-mãe: {PARENT_DIR}")
        os.makedirs(PARENT_DIR, exist_ok=True)
    scaffold()
    print(f"Pasta-mãe: {PARENT_DIR}")
    print(f"Poker App: {POKER_APP_URL}")
    if live:
        print("MODO: AO VIVO — envia e move ficheiros.")
    else:
        print("MODO: TESTE (dry-run) — NADA é enviado nem movido.")
        print("       Confirma o plano abaixo; depois corre com --ao-vivo.")
    print("─" * 56)

    session = None
    if live:
        if requests is None:
            print("ERRO: módulo 'requests' não instalado (pip install requests).")
            sys.exit(1)
        session = requests.Session()
        login(session)

    totals = {}
    for sub, endpoint, exts, label in TYPES:
        totals[sub] = process_type(session, sub, endpoint, exts, label, live)

    it_counts = process_it_mixed(session, live)
    lobby_sub_res = process_lobby_subdir(session, live)
    lobby_res = process_lobby_dir(session, live) if args.lobby_dir else None
    if not args.lobby_dir:
        print("\n── lobby (LOBBY_DIR externa): 2ª via manual — salto (usa --lobby-dir)")

    print("\n" + "═" * 56)
    print("RESUMO" + ("  (DRY-RUN — nada enviado)" if not live else ""))
    print("═" * 56)
    tot_sent = tot_fail = 0
    for sub, *_ in TYPES:
        sent, failed, skipped = totals[sub]
        tot_sent += sent
        tot_fail += failed
        extra = f"  (ignorados por extensão: {skipped})" if skipped else ""
        verb = "plano" if not live else "enviados"
        print(f"  {sub:8} {verb}={sent}  falhas={failed}{extra}")
    print(f"  {'it':8} mesa={it_counts['mesa']}  lobby={it_counts['lobby']}  "
          f"não-lobby={it_counts['nonlobby']}  skip={it_counts['skip']}  "
          f"retry={it_counts['retry']}  falhas={it_counts['fail']}")
    tot_sent += it_counts["mesa"] + it_counts["lobby"]
    tot_fail += it_counts["fail"] + it_counts["retry"]
    lob_s, nonlob_s, lfail_s = lobby_sub_res
    tot_sent += lob_s
    tot_fail += lfail_s
    print(f"  {'lobby':8} lobbies={lob_s}  não-lobby={nonlob_s}  falhas={lfail_s}   (subpasta drop-only)")
    if lobby_res is not None:
        lob, nonlob, lfail = lobby_res
        tot_fail += lfail
        print(f"  {'lobby*':8} lobbies={lob}  não-lobby={nonlob}  falhas={lfail}   (LOBBY_DIR externa)")
    print("─" * 56)
    label = "plano (would-send)" if not live else "enviados"
    print(f"  TOTAL {label}={tot_sent}  falhas={tot_fail}")
    if live and tot_fail:
        print("\n  ⚠ Ficheiros com falha FICARAM na subpasta — retry no próximo duplo-clique.")
    if live:
        print(f"\n  Enviados movidos para: {os.path.join(PARENT_DIR, 'done')}")
    else:
        print("\n  (dry-run) Volta a correr com --ao-vivo para enviar a sério.")


if __name__ == "__main__":
    main()
