"""#ICM-FT-TAG-NOT-LANDING — arruma o `done\\it` ACHATADO.

O move antigo do appimport achatava o done (perdia a subpasta = perdia a tag no disco).
Este script realoja cada print que já lá está na subpasta da SUA tag, usando a BD como
FONTE DE VERDADE (via GET /api/table-ss/folder-tags: nome de ficheiro → folder_tag).

Regras (decisão do Rui):
- Print COM tag conhecida na BD → move para done\\it\\<subpasta canónica da tag>\\.
- Print SEM tag na BD → NÃO adivinhar → fica na raiz do done (branco é honesto).
- DRY-RUN por defeito (lista completa + contagens); `--apply` move a sério.
- Só mexe DENTRO de Batmen\\ (done\\it). Ficheiros já em subpastas ficam intactos.
"""
import argparse
import os
import shutil
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app_import as ai


def resolve_done_it():
    """Resolve `done\\it` pelo MESMO mecanismo dos outros bats: `ai.load_config()` lê o
    `config_local.py` e preenche `PARENT_DIR` (o `import app_import` sozinho NÃO o faz — foi
    o bug do 1º dry-run: PARENT_DIR=None → TypeError). Guarda de arranque: pasta-mãe/subpasta
    vazias → mensagem PT clara + SystemExit, nunca traceback."""
    ai.load_config()
    if not ai.PARENT_DIR or not ai.IT_SUB:
        print("ERRO: pasta-mãe não configurada — preenche PARENT_DIR em "
              "tools/appimport/config_local.py (o mesmo que os outros imports usam).")
        raise SystemExit(1)
    return os.path.join(ai.PARENT_DIR, "done", ai.IT_SUB)


def plan_moves(files, name2tag):
    """PURO. Dado os ficheiros na RAIZ de done\\it e o mapa nome→tag da BD, devolve
    (plan, no_ev): plan = [(fname, tag, subpasta)] a realojar; no_ev = [fname] sem
    evidência (ficam na raiz). Não toca disco."""
    plan, no_ev = [], []
    for f in files:
        tag = name2tag.get(f)
        sub = ai.CANONICAL_FOLDER_FOR_TAG.get(tag) if tag else None
        if sub:
            plan.append((f, tag, sub))
        else:
            no_ev.append(f)
    return plan, no_ev


def main(argv=None):
    p = argparse.ArgumentParser(description="Arruma o done\\it achatado (realoja por tag da BD).")
    p.add_argument("--apply", action="store_true", help="mover a sério (default = dry-run)")
    args = p.parse_args(argv)

    if ai.requests is None:
        print("ERRO: módulo 'requests' não instalado (pip install requests)."); sys.exit(1)

    done_it = resolve_done_it()   # load_config + guarda (mesmo mecanismo dos outros bats)
    print(f"Pasta-mãe: {ai.PARENT_DIR}")
    if not os.path.isdir(done_it):
        print(f"done\\it ainda não existe: {done_it} — nada a arrumar."); return

    session = ai.requests.Session()
    ai.login(session)
    r = session.get(f"{ai.POKER_APP_URL}/api/table-ss/folder-tags", timeout=120)
    r.raise_for_status()
    name2tag = r.json().get("map", {})
    print(f"Fonte de verdade (BD): {len(name2tag)} ficheiros com tag conhecida.")

    # SÓ a raiz do done\it (os que já estão em subpasta estão bem colocados)
    files = [f for f in sorted(os.listdir(done_it))
             if os.path.isfile(os.path.join(done_it, f))]
    plan, no_ev = plan_moves(files, name2tag)

    by_tag = Counter(t for _, t, _ in plan)
    print(f"\n{'APLICAR' if args.apply else 'DRY-RUN'} — na raiz do done\\it: {len(files)} ficheiro(s)")
    print(f"  realojar: {len(plan)}   ·   ficam na raiz (sem tag na BD): {len(no_ev)}")
    for tag, n in by_tag.most_common():
        print(f"   {n:4}  → done\\it\\{ai.CANONICAL_FOLDER_FOR_TAG[tag]}\\   (tag {tag})")

    if not args.apply:
        print("\n--- plano completo (dry-run) ---")
        for f, tag, sub in plan:
            print(f"   {sub+chr(92):18}  {f}")
        if no_ev:
            print(f"\n   ({len(no_ev)} sem tag → ficam na raiz; não se adivinha)")
        print("\n(DRY-RUN — nada movido. Aprova e corre com --apply para mover.)")
        return

    moved = 0
    for f, tag, sub in plan:
        dest_dir = os.path.join(done_it, sub)
        os.makedirs(dest_dir, exist_ok=True)
        shutil.move(os.path.join(done_it, f), ai._dest_no_clobber(dest_dir, f))
        moved += 1
    print(f"\n✓ Realojados {moved}. {len(no_ev)} ficaram na raiz (sem evidência).")


if __name__ == "__main__":
    main()
