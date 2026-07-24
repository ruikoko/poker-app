"""Import mestre — orquestra appimport + apphm3 + Discord num clique.

ORQUESTRAÇÃO PURA — não muda a lógica de nenhuma pipeline:
  1. appimport corre IN-PROCESS (import do módulo): só sobrepõe o módulo-global
     `LOBBY_SINCE` para ESTA corrida (o config_local fica intacto) e chama main().
  2. apphm3 corre como SUBPROCESSO `hm3_export.py --days N` (já aceita --days;
     salta o prompt interactivo do .bat).
  3. Discord é uma chamada HTTP (login + POST /api/discord/sync-and-process) com
     as MESMAS credenciais do config_local do appimport.
Os reconciles de lobby disparam sozinhos a seguir aos imports de HH/TS (já fazem).

Menu curto no arranque: janelas PRÉ-PREENCHIDAS com defaults (Enter aceita,
escrever faz override). Só os 3 que têm janela; GG e IT processam o que está na
pasta (sem entrada).
"""
import os
import sys
import subprocess
from datetime import datetime

# ── Localizar os tools irmãos (tools/appimport, tools/apphm3) ────────────────
HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
APPIMPORT_DIR = os.path.join(TOOLS, "appimport")
APPHM3_DIR = os.path.join(TOOLS, "apphm3")
APPHM3_SCRIPT = os.path.join(APPHM3_DIR, "hm3_export.py")

# Defaults do menu
DEFAULT_HM3_DAYS = 3          # últimos N dias (HM3)
DEFAULT_HM3_TAG = ""          # tag HM3 (vazio = todas → corre sem --tag)
DEFAULT_DISCORD = "72h"       # janela Discord

# ── Carregar o appimport como módulo (zero-touch; dá-nos LOBBY_SINCE + creds) ─
sys.path.insert(0, APPIMPORT_DIR)
try:
    import app_import  # noqa: E402  (config_local do appimport tem de existir)
except SystemExit:
    print("\nERRO: o appimport não conseguiu carregar (config_local em falta?).")
    print(f"      Confirma {os.path.join(APPIMPORT_DIR, 'config_local.py')}")
    sys.exit(1)

try:
    import requests  # noqa: E402
except ImportError:
    print("ERRO: instala o módulo requests:  pip install requests")
    sys.exit(1)

URL = app_import.POKER_APP_URL


# ── Menu ─────────────────────────────────────────────────────────────────────

def ask(label, default, empty_label="(tudo)"):
    d = "" if default is None else str(default)
    shown = d if d else empty_label
    v = input(f"  {label:34} [{shown}]: ").strip()
    return v if v else d


def menu():
    print("=" * 56)
    print("  IMPORT MESTRE — janelas (Enter = default, escrever = override)")
    print("=" * 56)
    hm3_days = ask("HM3 — últimos N dias (ou 'all')", DEFAULT_HM3_DAYS)
    hm3_tag = ask("HM3 — tag (Enter = todas)", DEFAULT_HM3_TAG, empty_label="todas")
    lobby_since = ask("Lobbys — desde (YYYY-MM-DD)", app_import.LOBBY_SINCE)
    # Janela das IMAGENS (it/manual/lobby) — dia-de-jogo 12:00→12:00. HH/TS entram
    # sempre por inteiro (sem janela). Enter = config IMPORT_DESDE/ATE (ou tudo).
    img_desde = ask("Imagens — desde (YYYY-MM-DD)", getattr(app_import, "IMPORT_DESDE", None))
    img_ate = ask("Imagens — até   (YYYY-MM-DD)", getattr(app_import, "IMPORT_ATE", None))
    discord = ask("Discord — 72h | 24h/7d/15d/30d | YYYY-MM-DD", DEFAULT_DISCORD)
    print("=" * 56)
    return hm3_days, hm3_tag, lobby_since, img_desde, img_ate, discord


# ── Discord: janela do menu → body do sync-and-process ───────────────────────

_WINDOW_KEYS = {"24h", "72h", "7d", "15d", "30d"}


def discord_body(win):
    w = (win or "").strip().lower()
    if not w:
        return {"window": DEFAULT_DISCORD}
    if w in _WINDOW_KEYS:
        return {"window": w}
    # senão tratar como data YYYY-MM-DD (custom: desde essa data até agora)
    try:
        datetime.strptime(w, "%Y-%m-%d")
        return {"window": "custom", "from": f"{w}T00:00:00"}
    except ValueError:
        print(f"  (aviso: janela Discord {win!r} inválida — uso {DEFAULT_DISCORD})")
        return {"window": DEFAULT_DISCORD}


# ── Execução das 3 pipelines ─────────────────────────────────────────────────

def run_appimport(lobby_since, img_desde, img_ate, summary):
    win = (f"desde {img_desde or '—'} até {img_ate or '—'}"
           if (img_desde or img_ate) else "(tudo)")
    print("\n" + "#" * 56)
    print("# 1/3  APPIMPORT  (gg_hh + gg_ts + it + manual + lobby)  *** AO VIVO ***")
    print(f"#       LOBBY_SINCE desta corrida = {lobby_since or '(tudo)'}")
    print(f"#       JANELA de imagens (it/manual/lobby) = {win}")
    print("#" * 56)
    # AO VIVO + janela injectados por argv (--ao-vivo + --desde/--ate). LOBBY_SINCE
    # vai por `overrides` (aplicado DEPOIS do load_config, que de outro modo o
    # esmagaria). O config_local do appimport NÃO é tocado.
    argv = ["--ao-vivo"]
    if img_desde:
        argv += ["--desde", img_desde]
    if img_ate:
        argv += ["--ate", img_ate]
    lobby_lbl = f"lobby desde {lobby_since or 'tudo'}; janela {win}"
    # IMPORTANTE: app_import.main() pode terminar com sys.exit (ex.: login()
    # falha → sys.exit(1)). Apanhamos SystemExit (incl. sys.exit(0)) AQUI para
    # NÃO deixar o exit do appimport derrubar o orquestrador — a cadeia tem de
    # prosseguir ao HM3 e ao Discord. Idem para qualquer Exception.
    try:
        app_import.main(argv=argv, overrides={"LOBBY_SINCE": lobby_since or None})
        summary["appimport"] = f"OK ({lobby_lbl})"
    except SystemExit as e:
        code = e.code if e.code is not None else 0
        if code == 0:
            summary["appimport"] = f"OK ({lobby_lbl}; sys.exit 0)"
        else:
            summary["appimport"] = f"sys.exit({code}) — cadeia continuou ({lobby_lbl})"
    except Exception as e:
        summary["appimport"] = f"FALHOU: {type(e).__name__}: {e} — cadeia continuou"


def run_apphm3(hm3_days, hm3_tag, summary):
    cmd = [sys.executable, APPHM3_SCRIPT]
    d = str(hm3_days).strip().lower()
    label = "todas as datas"
    if d and d not in ("all", "tudo", "0"):
        cmd += ["--days", d]
        label = f"últimos {d} dias"
    tag = (hm3_tag or "").strip()
    if tag:
        cmd += ["--tag", tag]   # --tag já existe no hm3_export.py (exacto, senão "contém")
        label += f", tag '{tag}'"
    print("\n" + "#" * 56)
    print(f"# 2/3  APPHM3  ({label})")
    print("#" * 56)
    try:
        r = subprocess.run(cmd, cwd=APPHM3_DIR)
        # tag inexistente → hm3_export.py erra e LISTA as disponíveis (exit != 0);
        # não escondemos a mensagem (stdout passa directo).
        summary["apphm3"] = f"OK ({label})" if r.returncode == 0 else f"exit {r.returncode} ({label})"
    except Exception as e:
        summary["apphm3"] = f"FALHOU: {type(e).__name__}: {e}"


def run_discord(discord_win, summary):
    print("\n" + "#" * 56)
    print(f"# 3/3  DISCORD  (sync-and-process, janela {discord_win})")
    print("#" * 56)
    body = discord_body(discord_win)
    try:
        s = requests.Session()
        lg = s.post(f"{URL}/api/auth/login",
                    json={"email": app_import.LOGIN_EMAIL, "password": app_import.LOGIN_PASS},
                    timeout=60)
        if lg.status_code != 200:
            summary["discord"] = f"login falhou ({lg.status_code})"
            print(f"  ERRO login: {lg.status_code}")
            return
        r = s.post(f"{URL}/api/discord/sync-and-process", json=body, timeout=300)
        if r.status_code != 200:
            summary["discord"] = f"HTTP {r.status_code}: {r.text[:120]}"
            print(f"  ERRO: {r.status_code} {r.text[:200]}")
            return
        j = r.json()
        ls = j.get("last_sync") or {}
        n, m, k = ls.get("n_links"), ls.get("m_canais"), ls.get("k_match_hh")
        print(f"  OK: N={n} links · M={m} canais · K={k} match HH (foto precoce)")
        print("  (o K assenta no refresh da página /discord ~30s; Vision corre em background)")
        summary["discord"] = f"OK ({body.get('window')}) N={n} M={m} K={k}*"
    except Exception as e:
        summary["discord"] = f"FALHOU: {type(e).__name__}: {e}"


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print(f"Poker App: {URL}")
    print(f"appimport: {APPIMPORT_DIR}")
    print(f"apphm3   : {APPHM3_DIR}\n")
    hm3_days, hm3_tag, lobby_since, img_desde, img_ate, discord = menu()

    summary = {}
    run_appimport(lobby_since, img_desde, img_ate, summary)   # 1 — HH/TS/IT/manual/lobby (dispara reconciles)
    run_apphm3(hm3_days, hm3_tag, summary)     # 2 — HM3 sem prompt (dias + tag opcional)
    run_discord(discord, summary)              # 3 — sync Discord

    print("\n" + "=" * 56)
    print("  RESUMO MESTRE")
    print("=" * 56)
    for k in ("appimport", "apphm3", "discord"):
        print(f"  {k:10} : {summary.get(k, '(não corrido)')}")
    print("-" * 56)
    print("  Reconciles de lobby disparam sozinhos a seguir aos imports.")
    print("  * K Discord = foto precoce; assenta no refresh de /discord.")


if __name__ == "__main__":
    main()
