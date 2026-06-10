"""requeue_state.py — re-enfileira mãos no Beelink (sem editar JSON à mão).

Faz DUAS coisas para que o adapter re-puxe uma mão e o watcher use o pack NOVO:
  1. remove as entradas das mãos do `state.json` (o adapter salta `if hand_id
     in state`, dedup D10);
  2. apaga os packs/zips antigos dessas mãos (queue, arquivo, done\\Exports,
     replied) — o meta antigo (Max=2) não pode confundir.

Publicado como asset da Release watcher-pt67; descarregado e corrido pelo
`requeue_pt67.bat` (via o python da venv do adapter).

Uso:  python requeue_state.py [<hand_id> ...]    (default: as 2 mãos da re-smoke pt67)

⚠️ Lado backend (feito pelo Code via Railway, com OK do Rui): apagar as 2 linhas
de hrc_jobs (status='done') — senão a app NÃO re-serve as mãos.
"""
import json
import os
import shutil
import sys

STATE = r"C:\hrc\adapter\state.json"
QUEUE = r"C:\Users\Administrator\Documents\Teste completo"
DEFAULT_HANDS = ["GG-6029013400", "GG-6039094225"]


def clear_state(hands):
    try:
        with open(STATE, encoding="utf-8") as f:
            state = json.load(f)
        if not isinstance(state, dict):
            print("state.json nao e dict — abortado (nao toco).")
            return
    except FileNotFoundError:
        print(f"state.json nao existe ({STATE}) — nada a limpar.")
        return
    except (OSError, ValueError) as e:
        print(f"state.json ilegivel ({e}) — abortado.")
        return
    removed = [h for h in hands if h in state]
    for h in hands:
        state.pop(h, None)
    tmp = STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True, ensure_ascii=False)
    os.replace(tmp, STATE)  # atomic
    print(f"state.json: removidas {removed if removed else '(nenhuma — ja nao estavam)'}")


def clean_folders(hands):
    for h in hands:
        for d in (os.path.join(QUEUE, h), os.path.join(QUEUE, "arquivo", h)):
            if os.path.isdir(d):
                shutil.rmtree(d, ignore_errors=True)
                print(f"apagada pasta: {d}")
        # pt67 INTERINO (#HRC-RESULT-ZIP-413): com o cap a 200 MB, um zip de
        # resultado ANTIGO (offset errado) que tenha ficado em done\ deixa de
        # dar 413 e o adapter ENTREGA-O -> resultado errado entra em hrc_jobs.
        # Por isso limpamos TODOS os layouts plausiveis de done\ para a mao,
        # nao so done\Exports\.
        zips = (
            os.path.join(QUEUE, "done", h + ".zip"),
            os.path.join(QUEUE, "done", "replied", h + ".zip"),
            os.path.join(QUEUE, "done", "Exports", h + ".zip"),
            os.path.join(QUEUE, "done", "Exports", "replied", h + ".zip"),
        )
        for z in zips:
            if os.path.isfile(z):
                try:
                    os.remove(z)
                    print(f"apagado zip: {z}")
                except OSError as e:
                    print(f"[WARN] nao apaguei {z}: {e}")


def main() -> int:
    hands = sys.argv[1:] or DEFAULT_HANDS
    print(f"requeue: {hands}")
    clear_state(hands)
    clean_folders(hands)
    print("FEITO (lado Beelink). Arranca o adapter + watcher -> re-puxa packs "
          "NOVOS (Max=5) -> re-smoke.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
