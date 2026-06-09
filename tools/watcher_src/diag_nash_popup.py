"""DIAGNÓSTICO pt64 — enumerar a árvore de controlos do popup Nash do HRC.

Objectivo: descobrir COMO o controlo "Scope" do popup Nash está realmente
implementado, porque a via Win32 actual (`CB_SETCURSEL` sobre um filho de classe
== "ComboBox") NÃO o encontra (`_find_combo_with_item` devolve (None, None)).
Hipótese forte: é um SWT **CCombo** (composto Text+Button+List, classe genérica
"SWT_Window0"), que NÃO responde a mensagens CB_* — daí a falha.

COMO CORRER (no Beelink, perfil que corre o HRC):
  1. Abre o HRC e leva uma mão até abrir o popup **Nash Calculation** (clica
     Calculate). DEIXA O POPUP ABERTO.
  2. Noutra janela, corre:  py diag_nash_popup.py
     (tens 8s de contagem decrescente para garantir que o popup está à frente.)
  3. Cola-me o ficheiro `nash_popup_dump.txt` que fica ao lado do script.

NÃO altera nada no HRC — é só leitura (enumeração de janelas + UIA read-only).

Secção A (Win32, sem dependências): classe/texto/rect/ctrl-id de TODOS os
descendentes do popup + teste CB_GETCOUNT (apanha combos de classe não-padrão).
Secção B (UIA, opcional): ControlType + Name + padrões suportados
(ExpandCollapse/SelectionItem/Selection/Value) — diz-nos se dá para conduzir o
Scope por UI Automation. Requer `py -m pip install uiautomation` (se faltar, a
secção A já chega para decidir).
"""
import ctypes
from ctypes import wintypes
import sys
import time

POPUP_TITLE_SUBSTR = "nash calculation"   # lower; igual ao hint do watcher

u32 = ctypes.WinDLL("user32", use_last_error=True)

# --- assinaturas Win32 ---
u32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
u32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
u32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
u32.IsWindowVisible.argtypes = [wintypes.HWND]
u32.GetParent.argtypes = [wintypes.HWND]
u32.GetDlgCtrlID.argtypes = [wintypes.HWND]
u32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
u32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
u32.SendMessageW.restype = wintypes.LPARAM
u32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

CB_GETCOUNT = 0x0146
CB_GETLBTEXTLEN = 0x0149
CB_GETLBTEXT = 0x0148
CB_GETCURSEL = 0x0147
GWL_STYLE = -16


def _text(hwnd):
    n = u32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    u32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def _cls(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    u32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def _rect(hwnd):
    r = wintypes.RECT()
    u32.GetWindowRect(hwnd, ctypes.byref(r))
    return (r.left, r.top, r.right - r.left, r.bottom - r.top)


def _combo_items(hwnd):
    """Se o controlo responder a CB_GETCOUNT (>0), devolve a lista de itens —
    apanha combos mesmo que a classe não seja exactamente 'ComboBox'."""
    cnt = u32.SendMessageW(hwnd, CB_GETCOUNT, 0, 0)
    if not isinstance(cnt, int) or cnt <= 0 or cnt > 200:
        return None
    items = []
    for i in range(cnt):
        ln = u32.SendMessageW(hwnd, CB_GETLBTEXTLEN, i, 0)
        if not isinstance(ln, int) or ln <= 0:
            items.append("")
            continue
        b = ctypes.create_unicode_buffer(ln + 1)
        u32.SendMessageW(hwnd, CB_GETLBTEXT, i, ctypes.addressof(b))
        items.append(b.value)
    cur = u32.SendMessageW(hwnd, CB_GETCURSEL, 0, 0)
    return {"count": cnt, "items": items, "cursel": cur}


def find_popup():
    hits = []

    def _enum(h, _l):
        if not u32.IsWindowVisible(h):
            return True
        t = _text(h).lower()
        if POPUP_TITLE_SUBSTR in t:
            hits.append(h)
        return True

    u32.EnumWindows(WNDENUMPROC(_enum), 0)
    return hits


def dump_descendants(popup, out):
    rows = []

    def _enum(h, _l):
        rows.append(h)
        return True

    u32.EnumChildWindows(popup, WNDENUMPROC(_enum), 0)
    out.append(f"--- {len(rows)} descendentes do popup hwnd={popup} ---")
    # índice hwnd->n para reconstruir a hierarquia pelo parent
    for h in rows:
        cls = _cls(h)
        txt = _text(h)
        rect = _rect(h)
        cid = u32.GetDlgCtrlID(h)
        parent = u32.GetParent(h)
        style = u32.GetWindowLongW(h, GWL_STYLE) & 0xFFFFFFFF
        line = (f"hwnd={h} parent={parent} cid={cid} class={cls!r} "
                f"text={txt!r} rect(x,y,w,h)={rect} style=0x{style:08x}")
        combo = _combo_items(h)
        if combo is not None:
            line += f"\n      >>> RESPONDE A CB_*: cursel={combo['cursel']} items={combo['items']}"
        out.append(line)
        # destaca o label "Scope" como âncora + vizinhos à direita
        if "scope" in txt.lower():
            out.append(f"      ^^^ ÂNCORA 'Scope' — procura o controlo à direita "
                       f"(x>{rect[0]+rect[2]}, y≈{rect[1]})")
    return rows


def uia_probe(popup, out):
    out.append("\n=== SECÇÃO B — UI Automation ===")
    try:
        import uiautomation as auto
    except Exception as e:
        out.append(f"[skip] uiautomation não instalado ({e}). "
                   f"Corre: py -m pip install uiautomation  e repete.")
        return
    try:
        ctrl = auto.ControlFromHandle(popup)
    except Exception as e:
        out.append(f"[erro] ControlFromHandle falhou: {e}")
        return

    def patterns(c):
        names = []
        for pat in ("ExpandCollapsePattern", "SelectionItemPattern",
                    "SelectionPattern", "ValuePattern", "LegacyIAccessiblePattern"):
            try:
                if getattr(c, "Get" + pat)(0) is not None:
                    names.append(pat.replace("Pattern", ""))
            except Exception:
                pass
        return names

    def walk(c, depth):
        if depth > 8:
            return
        try:
            ct = c.ControlTypeName
            nm = c.Name
            cls = c.ClassName
            rc = c.BoundingRectangle
        except Exception as e:
            out.append("  " * depth + f"[erro a ler control: {e}]")
            return
        pats = patterns(c)
        val = ""
        try:
            vp = c.GetValuePattern(0)
            if vp is not None:
                val = f" value={vp.Value!r}"
        except Exception:
            pass
        flag = "  <<< COMBO?" if ct in ("ComboBoxControl", "ListControl") or "Combo" in cls else ""
        out.append("  " * depth + f"[{ct}] name={nm!r} class={cls!r} "
                   f"rect={rc} patterns={pats}{val}{flag}")
        for ch in c.GetChildren():
            walk(ch, depth + 1)

    walk(ctrl, 0)


def main():
    print("Abre o popup Nash Calculation no HRC e deixa-o à frente.")
    for s in range(8, 0, -1):
        print(f"  a enumerar em {s}s...", end="\r")
        time.sleep(1)
    print(" " * 40, end="\r")

    popups = find_popup()
    out = [f"== DIAG pt64 — popup Nash ({time.strftime('%Y-%m-%d %H:%M:%S')}) =="]
    if not popups:
        out.append(f"[FALHA] nenhuma janela visível com título a conter "
                   f"{POPUP_TITLE_SUBSTR!r}. O popup está aberto e à frente?")
        print("\n".join(out))
        return
    for p in popups:
        out.append(f"\n###### POPUP hwnd={p} title={_text(p)!r} rect={_rect(p)} ######")
        out.append("\n=== SECÇÃO A — Win32 (descendentes + teste CB_*) ===")
        dump_descendants(p, out)
        uia_probe(p, out)

    text = "\n".join(out)
    with open("nash_popup_dump.txt", "w", encoding="utf-8") as f:
        f.write(text)
    print(text)
    print("\n\n>>> Escrito tambem em nash_popup_dump.txt (cola-me esse ficheiro).")


if __name__ == "__main__":
    main()
