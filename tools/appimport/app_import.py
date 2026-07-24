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
from datetime import datetime, timedelta

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
# Nome da área done/ das gold images (pasta EXTERNA GOLD_DIR → done/gold).
GOLD_SUB = "gold"

# Config local (preenchida por load_config; globals p/ as funções de envio).
PARENT_DIR = None
LOGIN_EMAIL = None
LOGIN_PASS = None
LOBBY_DIR = None        # pasta EXTERNA opcional (2ª via manual, só com --lobby-dir)
LOBBY_SINCE = None      # só capturas (mtime) >= esta data, na LOBBY_DIR
GOLD_DIR = None         # pasta EXTERNA das gold images (descarga do replayer GG, ex. Documents)
IMPORT_DESDE = None     # janela das IMAGENS: dia-de-jogo inicial YYYY-MM-DD (ou None = sem início)
IMPORT_ATE = None       # janela das IMAGENS: dia-de-jogo final inclusive YYYY-MM-DD (ou None = sem fim)


def load_config():
    """Carrega config_local.py para os globals. Chamada só em main() (mantém o
    `import app_import` seguro para os testes do classificador, que não precisam
    de credenciais)."""
    global PARENT_DIR, LOGIN_EMAIL, LOGIN_PASS, LOBBY_DIR, LOBBY_SINCE, GOLD_DIR
    global IMPORT_DESDE, IMPORT_ATE
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
    GOLD_DIR = getattr(cfg, "GOLD_DIR", None)
    IMPORT_DESDE = getattr(cfg, "IMPORT_DESDE", None)
    IMPORT_ATE = getattr(cfg, "IMPORT_ATE", None)


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
    "yapoker": "WPN",            # skin WPN do Rui (IT: YaPoker.exe) → tratar como WPN
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
    # 'gold' — destino done/ das gold images da pasta EXTERNA GOLD_DIR (Documents).
    os.makedirs(os.path.join(PARENT_DIR, "done", GOLD_SUB), exist_ok=True)


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

def _post_table_ss(session, path, fname, folder_tag=None):
    """POST /api/table-ss/upload. Devolve (status, resumo); status ∈
    {'table', 'retry', 'fail'}. 'retry' = transitório — result == 'vision_failed'
    (a Vision falhou apesar do 200: soluço/créditos) → NÃO mover, re-envia no
    próximo run (paridade com _post_lobby; retry infinito do lado do ficheiro).
    `folder_tag` (pasta-como-tag, pt72) viaja como form field opcional; o backend
    aplica-o à mão casada.

    Âmbito do retry = SÓ vision_failed. json_invalid/site_undetected seguem como
    'table' (move), como antes — não melhoram com retry cego. O backend guarda
    img_b64 + folder_tag e tem POST /api/table-ss/reprocess-failed p/ esses casos."""
    mime = _IMG[os.path.splitext(fname)[1].lower()]
    data = {"folder_tag": folder_tag} if folder_tag else None
    try:
        with open(path, "rb") as fh:
            r = session.post(f"{POKER_APP_URL}/api/table-ss/upload",
                             files={"file": (fname, fh, mime)}, data=data,
                             timeout=600)
    except Exception as e:
        return ("fail", f"EXC {type(e).__name__}: {e}")
    if not (200 <= r.status_code < 300):
        return ("fail", f"HTTP {r.status_code} {r.text[:120]}")
    j = {}
    try:
        j = r.json()
    except Exception:
        pass
    if j.get("result") == "vision_failed":
        return ("retry", "Vision falhou (transitório)")
    return ("table", _summary_line(r))


def _post_screenshot(session, path, fname):
    """POST /api/screenshots (gold image / SS do replayer). Devolve (ok, resumo).
    O backend tira o TM/hand-id do NOME e faz Vision+match+desanon (position_v3).
    Dedup é server-side por file_hash — 2ª importação devolve status='duplicate'."""
    mime = _IMG[os.path.splitext(fname)[1].lower()]
    try:
        with open(path, "rb") as fh:
            r = session.post(f"{POKER_APP_URL}/api/screenshots",
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


# ── Janela de datas das IMAGENS (it / manual / lobby) — dia-de-jogo 12:00→12:00 ─
# Só filtra IMAGENS. gg_hh/gg_ts (HH/TS) NÃO são filtrados: entram sempre por
# inteiro (duplicados impossíveis; o despejo não incomoda). Tudo Lisboa-naive
# (pt51): mtime = hora local do PC do Rui (= Lisboa); timestamp do nome do IT idem.

# Régua GLOBAL do «início de dia» (24 Jul 2026, regra do Rui): o dia de jogo
# começa às 12h00 e vai até às 11h59 do dia seguinte. Razão: o Rui nunca joga
# entre as 12h e as ~17h (vazio real medido: madrugada mais tardia 09:45, tarde
# mais cedo 16:24) → o corte nunca atravessa uma sessão. Era 15h00 até 24 Jul
# (contagem de mãos 12h–15h em 2026: 0 → mudança indolor). O espelho no backend
# vive em routers/import_health.py (mesma constante, mesmo valor).
GAME_DAY_START_HOUR = 12

def _parse_day(s):
    """'YYYY-MM-DD' → datetime à meia-noite (Lisboa naive). None se vazio/inválido."""
    if not s:
        return None
    try:
        return datetime.strptime(str(s).strip(), "%Y-%m-%d")
    except (ValueError, TypeError):
        print(f"   (aviso: data {s!r} inválida — ignorada)")
        return None


def window_bounds(desde, ate):
    """(desde, ate) 'YYYY-MM-DD' → (lo, hi) do conceito DIA-DE-JOGO
    (GAME_DAY_START_HOUR→GAME_DAY_START_HOUR, hoje 12:00→12:00):
      lo = desde às 12:00 (inclusive); hi = (ate+1) às 12:00 (EXCLUSIVO) → cobre o
      dia-de-jogo `ate` inteiro. Cada lado pode ser None (sem limite desse lado).
      (None, None) = sem janela."""
    d = _parse_day(desde)
    a = _parse_day(ate)
    lo = d.replace(hour=GAME_DAY_START_HOUR) if d else None
    hi = (a + timedelta(days=1)).replace(hour=GAME_DAY_START_HOUR) if a else None
    return (lo, hi)


def date_in_window(dt, window):
    """dt (datetime ou ISO str) vs window=(lo, hi) semiaberto [lo, hi). Devolve
    (dentro: bool, motivo: str|None). dt None/inparseável OU window vazia →
    (True, None) (não filtra — comportamento de sempre)."""
    if not window or (window[0] is None and window[1] is None):
        return (True, None)
    lo, hi = window
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except (ValueError, TypeError):
            return (True, None)
    if not isinstance(dt, datetime):
        return (True, None)
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    if lo is not None and dt < lo:
        return (False, f"{dt:%Y-%m-%d %H:%M} < desde {lo:%Y-%m-%d %H:%M}")
    if hi is not None and dt >= hi:
        return (False, f"{dt:%Y-%m-%d %H:%M} >= fim {hi:%Y-%m-%d %H:%M}")
    return (True, None)


def _img_date(path, captured_iso=None):
    """Data de uma imagem p/ a janela: o timestamp do NOME (captured_iso, fonte
    `it`) ganha; senão o mtime do ficheiro (manual/lobby). Devolve datetime."""
    if captured_iso:
        try:
            return datetime.fromisoformat(captured_iso)
        except (ValueError, TypeError):
            pass
    return datetime.fromtimestamp(os.path.getmtime(path))


# ── Data-de-jogo das gold images a partir do NOME (pt91) ──────────────────────
# As gold images (descarga do replayer GG) têm o nome
# "YYYY-MM-DD_ HH-MM_PM_$SB_$BB_#TM.png". A data/hora de DOWNLOAD = data/hora de
# JOGO na prática (decisão do Rui, pt91: descarrega a mão no momento em que a joga),
# por isso a objecção download-vs-hora-de-jogo não se aplica aqui. Regexes alinhadas
# com o backend (screenshot._parse_filename) para não divergirem.
def _gold_name_date(fname):
    """Data-de-jogo de uma gold image lida do NOME, como datetime Lisboa-naive.
    Devolve None se o nome não tiver data+hora legíveis → o chamador INCLUI por
    defeito ('na dúvida, inclui') e regista aviso, nunca descarta em silêncio."""
    dm = re.search(r'(\d{4}-\d{2}-\d{2})', fname)
    tm = re.search(r'(\d{1,2})[-_](\d{2})[-_](AM|PM)', fname, re.IGNORECASE)
    if not dm or not tm:
        return None
    try:
        d = datetime.strptime(dm.group(1), "%Y-%m-%d")
    except (ValueError, TypeError):
        return None
    h, mi, period = int(tm.group(1)), int(tm.group(2)), tm.group(3).upper()
    if period == "PM" and h != 12:
        h += 12
    elif period == "AM" and h == 12:
        h = 0
    if not (0 <= h <= 23 and 0 <= mi <= 59):
        return None
    return d.replace(hour=h, minute=mi)


# ── Fontes por SUBPASTA (gg_hh / gg_ts / manual) ──────────────────────────────

def process_type(session, sub, endpoint, exts, label, live, window=None):
    """`window` (=(lo,hi) ou None) só é passado para canais de IMAGEM (manual);
    gg_hh/gg_ts chamam sempre com window=None → entram por inteiro. A data de uma
    imagem é o mtime (manual não tem timestamp no nome)."""
    src = os.path.join(PARENT_DIR, sub)
    done = os.path.join(PARENT_DIR, "done", sub)
    files = [f for f in sorted(os.listdir(src))
             if os.path.isfile(os.path.join(src, f))
             and os.path.splitext(f)[1].lower() in exts]
    skipped = len([f for f in os.listdir(src)
                   if os.path.isfile(os.path.join(src, f))
                   and os.path.splitext(f)[1].lower() not in exts])
    sent = failed = fora = 0

    print(f"── {sub}/  ({label})  — {len(files)} ficheiro(s) novo(s)")
    for fname in files:
        path = os.path.join(src, fname)
        if window:
            dentro, motivo = date_in_window(_img_date(path), window)
            if not dentro:
                fora += 1
                print(f"   [fora] {fname}  ({motivo})")
                continue
        if not live:
            sent += 1
            print(f"   [dry{' dentro' if window else ''}] {fname}  → {endpoint}")
            continue
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
    return sent, failed, skipped, fora


# ── Pasta-como-tag (pt72/pt73): subpasta de it\ → tag de estudo ───────────────
# A PASTA escolhida no IT no momento da captura É a tag (substitui o canal
# Discord, morto com o replayer GG). Chave = nome da subpasta normalizado
# (lowercase, espaços colapsados); valor = tag (BASE ou já com '-ft').
#
# Duas famílias de pasta (pt73):
#   • SEM '-ft' (icm, icm-pko, pos-pko, pos-nko, speed-racer): o sufixo de fase
#     '-ft' é decidido pelo BACKEND a partir da Vision (bancos == players_left).
#     Quando aplicado assim, fica MARCADO como AUTOMÁTICO (o Rui revê-o).
#   • JÁ com '-ft' (icm-pko-ft, pos-pko-ft): o Rui escolheu a pasta de mesa final
#     à mão → FT MANUAL, confirmado. O backend NÃO re-verifica nem re-acrescenta.
#
# 'nota' → tag 'nota' (dispara Vilões, regra C). Sem família de fase.
# EXTENSÍVEL: o Rui cria mais pastas no IT → acrescenta-se aqui a linha. Subpasta
# fora desta tabela → processada SEM tag (não inventa) + aviso.
# ⚠️ MIRROR do cliente. A AUTORIDADE é o backend `app/services/tags_canonical.py`
# (`canonicalize_tag`), que canonicaliza o folder_tag recebido. Este mapa só
# precisa de MANDAR uma forma reconhecível por pasta; o backend faz o resto.
IT_FOLDER_TAGS = {
    "icm":         "icm",
    "icm pko":     "icm-pko",
    "pko pos":     "pos-pko",
    "pos pko":     "pos-pko",      # forma directa (além da invertida "pko pos")
    "npko pos":    "pos-nko",      # nome ANTIGO "NPKO Pos" (histórico mantido)
    "nko pos":     "pos-nko",      # 🆕 "NKO Pos" (renomeada)
    "icm pko ft":  "icm-pko-ft",   # FT MANUAL — pasta de mesa final escolhida pelo Rui
    "pko pos ft":  "pos-pko-ft",   # FT MANUAL
    "icm ft":      "icm-ft",       # 🆕 pasta "ICM FT"
    "nko pos ft":  "pos-nko-ft",   # 🆕 pasta "NKO Pos FT"
    "pos nko ft":  "pos-nko-ft",   # 🆕 forma directa
    "speedracer":  "speed-racer",
    "speed racer": "speed-racer",  # tolera grafia com espaço
    "speed racer ft": "speed-racer-ft",  # 🆕 pasta "Speed Racer FT"
    "speedracer ft":  "speed-racer-ft",
    "nota":        "nota",         # → Vilões (regra C); sem fase pré/pós
}


def _folder_tag_for(subdir_name):
    """Nome de uma subpasta de it\\ → tag (BASE ou já com '-ft'); None se não está
    na tabela. Pastas que já trazem '-ft' (ICM PKO FT, PKO Pos FT) = FT MANUAL."""
    key = re.sub(r"\s+", " ", (subdir_name or "").strip().lower())
    return IT_FOLDER_TAGS.get(key)


# Reverso: tag → NOME de subpasta canónico (para reconstruir o done achatado,
# #ICM-FT-TAG-NOT-LANDING). Cada nome tem de voltar a bater no `_folder_tag_for`
# (senão o reimporte lê a subpasta e não reconhece a tag) — garantido por teste.
CANONICAL_FOLDER_FOR_TAG = {
    "icm":            "ICM",
    "icm-pko":        "ICM PKO",
    "pos-pko":        "PKO Pos",
    "pos-nko":        "NPKO Pos",   # nome da pasta VIVA no disco do Rui (não "NKO Pos" — o
                                    # move ia criar pasta diferente da viva; ambos round-trip)
    "icm-pko-ft":     "ICM PKO FT",
    "pos-pko-ft":     "PKO Pos FT",
    "icm-ft":         "ICM FT",
    "pos-nko-ft":     "NKO Pos FT",
    "speed-racer":    "SpeedRacer",
    "speed-racer-ft": "Speed Racer FT",
    "nota":           "Nota",
}


def _done_subdir(done_root, sublbl):
    """Destino no done PRESERVANDO a subpasta de origem. A subpasta É a etiqueta
    (pt72) → achatar o done destruía a informação NO DISCO e um reimporte a partir
    do done nascia SEM tag (#ICM-FT-TAG-NOT-LANDING, descoberto pelo Rui). Raiz
    (sublbl vazio) → done_root; subpasta → done_root\\<sublbl>."""
    return os.path.join(done_root, sublbl) if sublbl else done_root


def _it_subfolder_matches(entry, subfilter):
    """A subpasta `entry` corresponde ao filtro `--only it/<subfilter>`? Case-insensitive
    exacto OU mesma tag (tolera 'Speed Racer' vs 'SpeedRacer', 'NKO Pos' vs 'NPKO Pos')."""
    if entry.strip().lower() == subfilter.strip().lower():
        return True
    t = _folder_tag_for(entry)
    return t is not None and t == _folder_tag_for(subfilter)


# ── Pasta `it` — classificada por NOME (MESA | LOBBY | SKIP) + tag da subpasta ──

def _process_it_dir(session, live, src, folder_tag, window, c, done_table, done_lobby):
    """Processa as imagens de UMA pasta de captura do IT (a raiz de it\\ ou uma
    subpasta). `folder_tag` (ou None) = tag BASE da pasta-como-tag (pt72): viaja
    no POST de MESA → o backend aplica-a à mão casada (o FT '-ft' é decidido lá,
    pela Vision). LOBBY ignora a tag (não é mão de estudo). Muta `c`."""
    files = _imgs_in(src)
    label = os.path.basename(src.rstrip("\\/")) or IT_SUB
    sublbl = "" if label == IT_SUB else label
    # PRESERVAR a subpasta no done (a subpasta É a tag — #ICM-FT-TAG-NOT-LANDING).
    mesa_done = _done_subdir(done_table, sublbl)
    lobby_done = _done_subdir(done_lobby, sublbl)
    tag_lbl = f"  tag={folder_tag}" if folder_tag else ""
    print(f"── {IT_SUB}/{sublbl}  (Intuitive Tables — routing por nome{tag_lbl})  "
          f"— {len(files)} ficheiro(s)")
    for fname in files:
        path = os.path.join(src, fname)
        kind, site, captured = classify_it_file(fname)
        if kind == "SKIP":
            c["skip"] += 1
            print(f"   ⤳ SKIP   {fname}  (formato não-IT)")
            continue
        if window:
            dentro, motivo = date_in_window(_img_date(path, captured), window)
            if not dentro:
                c["fora"] += 1
                print(f"   [fora] {kind:5} {fname}  ({motivo})")
                continue
        cap = captured or _mtime_iso(path)   # fallback: mtime do ficheiro
        endpoint = "/api/table-ss/upload" if kind == "MESA" else "/api/lobbys/upload"
        # pt63 — hint de nome do torneio (GG), só relevante p/ LOBBY
        name_hint = lobby_name_hint(fname) if kind == "LOBBY" else None

        if not live:
            hint = f" name_hint={name_hint!r}" if name_hint else ""
            tg = f" folder_tag={folder_tag}" if (folder_tag and kind == "MESA") else ""
            print(f"   [dry] {kind:5} site={site or '?':9} captured_at={cap}  "
                  f"→ {endpoint}{hint}{tg}  ({fname})")
            c["mesa" if kind == "MESA" else "lobby"] += 1
            continue

        if kind == "MESA":
            status, msg = _post_table_ss(session, path, fname, folder_tag=folder_tag)
            if status == "retry":
                c["retry"] += 1
                print(f"   ⟳ MESA   {fname}: {msg} → retry depois (não movido)")
            elif status == "table":
                c["mesa"] += 1
                print(f"   ✓ MESA   {fname}: {msg}")
                os.makedirs(mesa_done, exist_ok=True)
                shutil.move(path, _dest_no_clobber(mesa_done, fname))
            else:  # fail (exceção / HTTP não-2xx) — comportamento de sempre
                c["fail"] += 1
                print(f"   ✗ MESA   {fname}: {msg} → retry depois")
        else:  # LOBBY — tag da pasta NÃO se aplica (lobby ≠ mão de estudo)
            status, msg = _post_lobby(session, path, fname, cap,
                                      site_hint=site, name_hint=name_hint)
            if status == "retry":
                c["retry"] += 1
                print(f"   ⟳ LOBBY  {fname}: {msg} → retry depois (não movido)")
            elif status == "lobby":
                c["lobby"] += 1
                print(f"   ✓ LOBBY  {fname}: {msg}")
                os.makedirs(lobby_done, exist_ok=True)
                shutil.move(path, _dest_no_clobber(lobby_done, fname))
            else:  # nonlobby
                c["nonlobby"] += 1
                print(f"   · LOBBY  {fname}: {msg} — processado")
                os.makedirs(lobby_done, exist_ok=True)
                shutil.move(path, _dest_no_clobber(lobby_done, fname))


def process_it_mixed(session, live, window=None, subfilter=None):
    """Pasta do Intuitive Tables (mesa + lobby), classificada por NOME e roteada
    para o endpoint certo. MESA → table-ss (move → done/it); LOBBY → lobbys (move
    → done/lobby, retry transitório fica); SKIP → fica no sítio (formato não-IT).
    Em dry-run só imprime o plano.

    pt72/pt73 — PASTA-COMO-TAG: além da RAIZ de it\\ (sem tag, back-compat),
    processa as SUBPASTAS de it\\ (ICM, ICM PKO, PKO Pos, NPKO Pos, ICM PKO FT,
    PKO Pos FT, SpeedRacer, Nota, …). A subpasta É a tag (IT_FOLDER_TAGS); viaja
    no POST de MESA. Pastas com '-ft' no nome = FT MANUAL (confirmado pelo Rui);
    as restantes recebem '-ft' AUTO do backend se a Vision indicar mesa final.
    Subpasta fora da tabela → processa SEM tag (não inventa) + aviso. `window`
    filtra por data. Devolve contagens."""
    src_root = os.path.join(PARENT_DIR, IT_SUB)
    done_table = os.path.join(PARENT_DIR, "done", IT_SUB)
    done_lobby = os.path.join(PARENT_DIR, "done", LOBBY_SUB)
    c = {"mesa": 0, "lobby": 0, "nonlobby": 0, "skip": 0, "retry": 0, "fail": 0,
         "fora": 0, "untagged_folder": 0}

    # 1) raiz de it\ — sem tag (back-compat: ficheiros largados directamente).
    #    Com --only it/<subpasta>, salta-se a raiz (só interessa a subpasta pedida).
    if subfilter:
        print(f"── {IT_SUB} (--only it/{subfilter}): SALTO a raiz de it\\ e as outras subpastas")
    else:
        _process_it_dir(session, live, src_root, None, window, c, done_table, done_lobby)

    # 2) subpastas de it\ — a subpasta É a tag (pasta-como-tag).
    matched = 0
    for entry in sorted(os.listdir(src_root)):
        sub = os.path.join(src_root, entry)
        if not os.path.isdir(sub):
            continue
        if subfilter and not _it_subfolder_matches(entry, subfilter):
            continue                                  # --only it/<x>: salta as outras
        matched += 1
        tag = _folder_tag_for(entry)
        if tag is None:
            c["untagged_folder"] += 1
            print(f"── {IT_SUB}/{entry}  ⚠ subpasta fora da tabela de tradução "
                  f"(IT_FOLDER_TAGS) → processada SEM tag")
        _process_it_dir(session, live, sub, tag, window, c, done_table, done_lobby)
    if subfilter and matched == 0:
        print(f"── {IT_SUB}/{subfilter}: ⚠ nenhuma subpasta com esse nome em it\\ "
              f"(nada a fazer). Confirma o nome exacto da pasta.")
    return c


# ── Subpasta dedicada "lobby" (drop-only-these; captured_at = mtime) ──────────

def process_lobby_subdir(session, live, window=None):
    """Subpasta PARENT_DIR/lobby: SÓ processa o que está cá dentro. captured_at =
    mtime do ficheiro (back-compat para nomes Windows sem timestamp embutido). O
    backend faz o gate 'é lobby?'. Mover: lobby/nonlobby → done/lobby; retry
    transitório → fica. `window` (=(lo,hi) ou None) filtra por mtime. Devolve
    (lobbies, nao_lobbies, falhas, fora_da_janela)."""
    src = os.path.join(PARENT_DIR, LOBBY_SUB)
    done = os.path.join(PARENT_DIR, "done", LOBBY_SUB)
    files = _imgs_in(src)
    print(f"── {LOBBY_SUB}/  (SS de lobby, drop-only-these)  — {len(files)} ficheiro(s)")
    lobby = nonlobby = failed = fora = 0
    for fname in files:
        path = os.path.join(src, fname)
        cap = _mtime_iso(path)
        if window:
            dentro, motivo = date_in_window(_img_date(path), window)
            if not dentro:
                fora += 1
                print(f"   [fora] {fname}  ({motivo})")
                continue
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
    return (lobby, nonlobby, failed, fora)


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


def process_lobby_dir(session, live, window=None):
    """Lê a pasta externa LOBBY_DIR DIRECTAMENTE (sem mover), dedup por
    manifesto. 2ª via MANUAL desde pt62: só corre com --lobby-dir. captured_at =
    mtime. `window` (=(lo,hi) ou None) é um filtro ADICIONAL por mtime: o piso
    efectivo é o MAIS restritivo de LOBBY_SINCE e da janela `desde`; o `até` da
    janela também se aplica. Devolve (lobbies, nao_lobbies, falhas, fora) ou None."""
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
    files, skipped_old, fora = [], 0, 0
    for f in candidates:
        mt = datetime.fromtimestamp(os.path.getmtime(os.path.join(LOBBY_DIR, f)))
        if since and mt < since:
            skipped_old += 1
            continue
        if window:
            dentro, _motivo = date_in_window(mt, window)
            if not dentro:
                fora += 1
                continue
        files.append((f, mt))
    extra = f"  (fora de LOBBY_SINCE: {skipped_old})" if skipped_old else ""
    extra += f"  (fora da janela: {fora})" if fora else ""
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
    return (lobby, nonlobby, failed, fora)


# ── Fonte "gold" externa GOLD_DIR (gold images do replayer GG — ex. Documents) ─

def process_gold_dir(session, live, window=None):
    """Lê a pasta EXTERNA GOLD_DIR (gold images = descarga completa da mão pelo
    botão do replayer GG; ex. Documents) e envia TODAS as imagens (.png/.jpg)
    para /api/screenshots. `window` (=(lo,hi) ou None) filtra pela DATA-DE-JOGO
    lida do NOME (pt91 — a hora de download = hora de jogo); ficheiro sem data/hora
    legível NÃO se perde (entra por defeito + aviso, 'na dúvida inclui'). Em 2xx
    MOVE o ficheiro para PARENT_DIR/done/gold
    (sai da GOLD_DIR → dedup natural no cliente; o backend dedupa por file_hash).

    A jusante reutiliza o pipeline do upload manual: Vision → match por hand-id
    (GG-<TM> do nome) → desanon position_v3 → vilões. Sem HH ainda, o entry fica
    ÓRFÃO (sem erro) e liga-se sozinho quando a HH for importada (re-link de
    órfãos, já existente). Devolve (enviadas, falhas, fora) ou None se não
    configurada."""
    if not GOLD_DIR:
        print("\n── gold (GOLD_DIR): não configurada em config_local — salto")
        return None
    if not os.path.isdir(GOLD_DIR):
        print(f"\n── gold (GOLD_DIR): não existe ({GOLD_DIR}) — salto")
        return None
    done = os.path.join(PARENT_DIR, "done", GOLD_SUB)
    files = _imgs_in(GOLD_DIR)
    print(f"\n── gold (GOLD_DIR externa: gold images → /api/screenshots)  — {len(files)} ficheiro(s)")
    sent = failed = fora = 0
    for fname in files:
        path = os.path.join(GOLD_DIR, fname)
        if window:
            dt = _gold_name_date(fname)
            if dt is None:
                print(f"   [aviso] {fname}  (sem data/hora legível no nome — incluído por defeito)")
            else:
                dentro, motivo = date_in_window(dt, window)
                if not dentro:
                    fora += 1
                    print(f"   [fora] {fname}  ({motivo})")
                    continue
        if not live:
            sent += 1
            print(f"   [dry{' dentro' if window else ''}] {fname}  → /api/screenshots")
            continue
        ok, msg = _post_screenshot(session, path, fname)
        if ok:
            sent += 1
            print(f"   ✓ {fname}: {msg}")
            shutil.move(path, _dest_no_clobber(done, fname))   # sai da GOLD_DIR
        else:
            failed += 1
            print(f"   ✗ {fname}: {msg} → retry depois (não movido)")
    return (sent, failed, fora)


# ── Entrada ────────────────────────────────────────────────────────────────--

def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Import por pasta local → Poker App (dry-run por defeito).")
    p.add_argument("--ao-vivo", dest="ao_vivo", action="store_true",
                   help="ENVIA a sério (e move). Sem esta flag = dry-run (só plano).")
    p.add_argument("--lobby-dir", dest="lobby_dir", action="store_true",
                   help="Lê também a LOBBY_DIR externa (2ª via manual; off por defeito).")
    p.add_argument("--only", dest="only", default=None, metavar="CANAL[/SUBPASTA]",
                   help="Corre SÓ este canal (gg_hh|gg_ts|manual|it|gold|lobby). Sem esta "
                        "flag = todos. Filtro por subpasta do it: --only \"it/SpeedRacer\" "
                        "(nomes com espaço entre aspas).")
    p.add_argument("--desde", dest="desde", default=None, metavar="YYYY-MM-DD",
                   help="Janela das IMAGENS (it/manual/lobby): dia-de-jogo inicial. "
                        "Sobrepõe IMPORT_DESDE da config. HH/TS entram SEMPRE por inteiro.")
    p.add_argument("--ate", dest="ate", default=None, metavar="YYYY-MM-DD",
                   help="Janela das IMAGENS: dia-de-jogo final inclusive. Sobrepõe IMPORT_ATE.")
    return p.parse_args(argv)


_ONLY_CHANNELS = {"gg_hh", "gg_ts", "manual", "it", "gold", "lobby"}


def _parse_only(val):
    """`--only` → (canal, subpasta). 'it/SpeedRacer' ou 'it\\SpeedRacer' →
    ('it','SpeedRacer'); 'it' → ('it',''); None → (None,'')."""
    if not val:
        return None, ""
    ch, _, sub = val.replace("\\", "/").partition("/")
    return ch.strip(), sub.strip()


def main(argv=None, overrides=None):
    """`overrides` (dict opcional, usado pelo appmaster/run_all) aplica-se DEPOIS
    do load_config para sobrepor globals desta corrida sem tocar o config_local —
    chaves aceites: LOBBY_SINCE, LOBBY_DIR, IMPORT_DESDE, IMPORT_ATE. As flags da
    CLI (--desde/--ate) continuam a ganhar à config/overrides."""
    global LOBBY_SINCE, LOBBY_DIR, IMPORT_DESDE, IMPORT_ATE
    args = parse_args(argv)
    live = args.ao_vivo
    load_config()
    if overrides:
        for k in ("LOBBY_SINCE", "LOBBY_DIR", "IMPORT_DESDE", "IMPORT_ATE"):
            if k in overrides:
                globals()[k] = overrides[k]

    # Janela das IMAGENS: flag da CLI ganha à config (IMPORT_DESDE/ATE).
    desde = args.desde if args.desde is not None else IMPORT_DESDE
    ate = args.ate if args.ate is not None else IMPORT_ATE
    wb = window_bounds(desde, ate)
    img_window = wb if (wb[0] or wb[1]) else None

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
    if img_window:
        lo, hi = img_window
        ini = f"desde {lo:%Y-%m-%d %H:%M}" if lo else "sem início"
        fim = f"até {hi:%Y-%m-%d %H:%M} (excl.)" if hi else "sem fim"
        print(f"JANELA de IMAGENS (it/manual/lobby): {ini} · {fim}")
        print(f"       (dia-de-jogo {GAME_DAY_START_HOUR}:00→{GAME_DAY_START_HOUR}:00; "
              "gg_hh/gg_ts entram SEMPRE por inteiro)")
    else:
        print("JANELA de IMAGENS: nenhuma — entra tudo (it/manual/lobby).")
    print("─" * 56)

    session = None
    if live:
        if requests is None:
            print("ERRO: módulo 'requests' não instalado (pip install requests).")
            sys.exit(1)
        session = requests.Session()
        login(session)

    # --only: corre SÓ um canal (cano-a-cano). Canais saltados devolvem vazios
    # (mesma forma) para o RESUMO não quebrar.
    only_ch, only_sub = _parse_only(args.only)
    if only_ch is not None and only_ch not in _ONLY_CHANNELS:
        print(f"ERRO: canal --only inválido: {only_ch!r}. Usa um de {sorted(_ONLY_CHANNELS)} "
              f"(ou 'it/<subpasta>').")
        sys.exit(2)
    if only_sub and only_ch != "it":
        print("ERRO: filtro por subpasta só é suportado no canal 'it' (--only \"it/<subpasta>\").")
        sys.exit(2)

    def _run(ch):
        return only_ch is None or only_ch == ch
    if args.only:
        extra = f" · subpasta '{only_sub}'" if only_sub else ""
        print(f"\n[--only {args.only}] SÓ o canal '{only_ch}'{extra}; o resto é saltado.")
    _EMPTY_IT = {"mesa": 0, "lobby": 0, "nonlobby": 0, "skip": 0, "retry": 0,
                 "fail": 0, "fora": 0, "untagged_folder": 0}

    totals = {}
    for sub, endpoint, exts, label in TYPES:
        if _run(sub):
            w = img_window if sub == "manual" else None   # HH/TS nunca filtrados
            totals[sub] = process_type(session, sub, endpoint, exts, label, live, window=w)
        else:
            totals[sub] = (0, 0, 0, 0)

    it_counts = process_it_mixed(session, live, window=img_window,
                                 subfilter=(only_sub or None)) if _run("it") else dict(_EMPTY_IT)
    lobby_sub_res = process_lobby_subdir(session, live, window=img_window) if _run("lobby") else (0, 0, 0, 0)
    gold_res = process_gold_dir(session, live, window=img_window) if _run("gold") else None
    lobby_res = process_lobby_dir(session, live, window=img_window) if (args.lobby_dir and _run("lobby")) else None
    if not args.lobby_dir and _run("lobby"):
        print("\n── lobby (LOBBY_DIR externa): 2ª via manual — salto (usa --lobby-dir)")

    print("\n" + "═" * 56)
    print("RESUMO" + ("  (DRY-RUN — nada enviado)" if not live else ""))
    print("═" * 56)
    tot_sent = tot_fail = tot_fora = 0
    for sub, *_ in TYPES:
        sent, failed, skipped, fora = totals[sub]
        tot_sent += sent
        tot_fail += failed
        tot_fora += fora
        extra = f"  (ignorados por extensão: {skipped})" if skipped else ""
        extra += f"  fora da janela={fora}" if fora else ""
        verb = "plano" if not live else "enviados"
        print(f"  {sub:8} {verb}={sent}  falhas={failed}{extra}")
    it_fora = f"  fora da janela={it_counts['fora']}" if it_counts["fora"] else ""
    print(f"  {'it':8} mesa={it_counts['mesa']}  lobby={it_counts['lobby']}  "
          f"não-lobby={it_counts['nonlobby']}  skip={it_counts['skip']}  "
          f"retry={it_counts['retry']}  falhas={it_counts['fail']}{it_fora}")
    tot_sent += it_counts["mesa"] + it_counts["lobby"]
    tot_fail += it_counts["fail"] + it_counts["retry"]
    tot_fora += it_counts["fora"]
    lob_s, nonlob_s, lfail_s, lfora_s = lobby_sub_res
    tot_sent += lob_s
    tot_fail += lfail_s
    tot_fora += lfora_s
    lsub_fora = f"  fora da janela={lfora_s}" if lfora_s else ""
    print(f"  {'lobby':8} lobbies={lob_s}  não-lobby={nonlob_s}  falhas={lfail_s}{lsub_fora}   (subpasta drop-only)")
    if gold_res is not None:
        g_sent, g_fail, g_fora = gold_res
        tot_sent += g_sent
        tot_fail += g_fail
        tot_fora += g_fora
        verb = "plano" if not live else "enviadas"
        g_fora_lbl = f"  fora da janela={g_fora}" if g_fora else ""
        print(f"  {'gold':8} {verb}={g_sent}  falhas={g_fail}{g_fora_lbl}   (GOLD_DIR externa → /api/screenshots)")
    if lobby_res is not None:
        lob, nonlob, lfail, lfora = lobby_res
        tot_fail += lfail
        tot_fora += lfora
        ldir_fora = f"  fora da janela={lfora}" if lfora else ""
        print(f"  {'lobby*':8} lobbies={lob}  não-lobby={nonlob}  falhas={lfail}{ldir_fora}   (LOBBY_DIR externa)")
    print("─" * 56)
    label = "plano (would-send)" if not live else "enviados"
    fora_lbl = f"  fora da janela={tot_fora}" if tot_fora else ""
    print(f"  TOTAL {label}={tot_sent}  falhas={tot_fail}{fora_lbl}")
    if live and tot_fail:
        print("\n  ⚠ Ficheiros com falha FICARAM na subpasta — retry no próximo duplo-clique.")
    if live:
        print(f"\n  Enviados movidos para: {os.path.join(PARENT_DIR, 'done')}")
    else:
        print("\n  (dry-run) Volta a correr com --ao-vivo para enviar a sério.")


if __name__ == "__main__":
    main()
