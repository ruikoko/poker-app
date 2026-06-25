"""
tree_stats.py — leitura read-only das estatísticas da tree do HRC (Holdem Resources
Calculator) via screenshot + OCR, para registar por mão e permitir abort preventivo
de trees gigantes ANTES do Finish.

COMO FUNCIONA
-------------
1. PrintWindow(PW_RENDERFULLCONTENT) sobre a janela "Hand Setup" do HRC.
   -> resolve o problema do canvas SWT que sai PRETO com CopyFromScreen/BitBlt.
   -> funciona em background (não precisa de foco, não mexe no rato).
2. Localiza o grupo "Tree Statistics" por Win32 (o título do SWT_GROUP é legível) e lê
   o rect AO VIVO (sem coordenadas fixas -> robusto a mudança de posição/escala).
3. Recorta esse rect, faz upscale, e corre OCR nativo do Windows (Windows.Media.Ocr).
4. Faz parse por palavras-chave/ordem e devolve um dict.

CONTRATO DE RETORNO  (capture_tree_stats -> dict)
-------------------------------------------------
{
  "nodes":            int   | None,   # Total Nodes (ex.: 507581)
  "gb":               float | None,   # Total Tree Size em GB (ex.: 4.5)
  "hrc_available_gb": float | None,   # HRC available em GB (ex.: 20.3)
  "ok":               bool,           # True só se leitura coerente (ver _sanity)
  "raw":              str,            # texto bruto do OCR (debug)
}
Nunca lança: em erro devolve {... "ok": False, "raw": "err:..."}.

DEPENDÊNCIAS (para o rebuild do .exe)
-------------------------------------
  - winsdk      (pip install winsdk)   -> Windows.Media.Ocr nativo, sem instalar nada no SO
  - Pillow      (pip install Pillow)   -> manipulação de imagem (crop/upscale/encode)
  - ctypes      (stdlib)               -> Win32 (PrintWindow, Enum*, GetWindowRect, GDI)
PyInstaller (.spec / linha de comando):
  --collect-all winsdk   (winsdk são namespace packages; hidden-imports simples não chegam)
  Pillow é normalmente auto-detetado; se não, --collect-submodules PIL
Requisitos de SO: Windows 10/11 com o pack de idioma de OCR (PT ou EN) instalado
  (TryCreateFromUserProfileLanguages; fallback en-US incluído).

ESTADO DE VALIDAÇÃO
-------------------
A técnica (PrintWindow + Windows.Media.Ocr + parse) foi validada no HRC real via o
equivalente .NET/WinRT: leu nodes=507581, tree=4.5GB, hrc=20.3/20.4GB corretamente.
O glifo "GB" tende a sair como "6B" (G->6); está normalizado no parse.
NOTA: este ficheiro usa as bindings `winsdk`, que espelham a API WinRT validada, mas
não foi executado em Python na máquina de teste (winsdk não instalado lá). Fazer um
smoke-test (bloco __main__) no rebuild.
"""

from __future__ import annotations

import ctypes
import asyncio
import io
import re
from ctypes import wintypes

# ----------------------------------------------------------------------------- #
# Config
# ----------------------------------------------------------------------------- #
PW_RENDERFULLCONTENT = 2
TREE_STATS_GROUP_TEXT = "Tree Statistics"   # substring do título do SWT_GROUP
HAND_SETUP_TITLE = "Hand Setup"             # título da janela top-level do wizard
DEFAULT_UPSCALE = 3                         # ampliação do recorte antes do OCR

# ----------------------------------------------------------------------------- #
# Win32 (ctypes)
# ----------------------------------------------------------------------------- #
_user32 = ctypes.WinDLL("user32", use_last_error=True)
_gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

_WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

_user32.EnumWindows.argtypes = [_WNDENUMPROC, wintypes.LPARAM]
_user32.EnumChildWindows.argtypes = [wintypes.HWND, _WNDENUMPROC, wintypes.LPARAM]
_user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
_user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
_user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
_user32.IsWindowVisible.argtypes = [wintypes.HWND]
_user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
_user32.GetWindowDC.argtypes = [wintypes.HWND]
_user32.GetWindowDC.restype = wintypes.HDC
_user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
_user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
_user32.PrintWindow.restype = wintypes.BOOL

_gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
_gdi32.CreateCompatibleDC.restype = wintypes.HDC
_gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
_gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
_gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
_gdi32.SelectObject.restype = wintypes.HGDIOBJ
_gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
_gdi32.DeleteDC.argtypes = [wintypes.HDC]
_gdi32.GetDIBits.argtypes = [
    wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
    ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT,
]
_gdi32.GetDIBits.restype = ctypes.c_int

_BI_RGB = 0
_DIB_RGB_COLORS = 0


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class _BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", _BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


def _class_name(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(256)
    _user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def _window_text(hwnd) -> str:
    n = _user32.GetWindowTextLengthW(hwnd)
    if n <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    _user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def _window_rect(hwnd):
    r = wintypes.RECT()
    if _user32.GetWindowRect(hwnd, ctypes.byref(r)):
        return (r.left, r.top, r.right, r.bottom)
    return None


def _enum_children(top_hwnd):
    out = []

    @_WNDENUMPROC
    def _cb(h, _l):
        out.append(h)
        return True

    _user32.EnumChildWindows(top_hwnd, _cb, 0)
    return out


def find_hand_setup_window(title_substr: str = HAND_SETUP_TITLE):
    """Top-level cujo título contém `title_substr` (default 'Hand Setup').
    Usa EnumWindows porque FindWindow falha com janelas elevadas/título com espaços."""
    found = []

    @_WNDENUMPROC
    def _cb(h, _l):
        if _user32.IsWindowVisible(h):
            t = _window_text(h)
            if t and title_substr.lower() in t.lower():
                found.append(h)
        return True

    _user32.EnumWindows(_cb, 0)
    return found[0] if found else None


def find_tree_stats_group(top_hwnd):
    """(group_hwnd, (l,t,r,b)) do SWT_GROUP 'Tree Statistics' sob top_hwnd, ou (None, None)."""
    for k in _enum_children(top_hwnd):
        if _class_name(k) == "SWT_GROUP" and TREE_STATS_GROUP_TEXT.lower() in _window_text(k).lower():
            return k, _window_rect(k)
    return None, None


def _capture_window_rgb(hwnd):
    """PrintWindow(PW_RENDERFULLCONTENT) -> (PIL.Image RGB, (win_left, win_top)).
    Lança em falha. Requer Pillow."""
    from PIL import Image  # dep: Pillow

    rect = _window_rect(hwnd)
    if not rect:
        raise RuntimeError("sem rect da janela")
    l, t, r, b = rect
    w, h = r - l, b - t
    if w <= 0 or h <= 0:
        raise RuntimeError("dimensões inválidas")

    hwnd_dc = _user32.GetWindowDC(hwnd)
    mem_dc = _gdi32.CreateCompatibleDC(hwnd_dc)
    bmp = _gdi32.CreateCompatibleBitmap(hwnd_dc, w, h)
    old = _gdi32.SelectObject(mem_dc, bmp)
    try:
        ok = _user32.PrintWindow(hwnd, mem_dc, PW_RENDERFULLCONTENT)
        if not ok:
            raise RuntimeError("PrintWindow devolveu 0")

        bmi = _BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = w
        bmi.bmiHeader.biHeight = -h           # top-down
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = _BI_RGB

        buf = (ctypes.c_char * (w * h * 4))()
        scanned = _gdi32.GetDIBits(hwnd_dc, bmp, 0, h, buf, ctypes.byref(bmi), _DIB_RGB_COLORS)
        if scanned == 0:
            raise RuntimeError("GetDIBits falhou")

        img = Image.frombuffer("RGBA", (w, h), bytes(buf), "raw", "BGRA", 0, 1).convert("RGB")
        return img, (l, t)
    finally:
        _gdi32.SelectObject(mem_dc, old)
        _gdi32.DeleteObject(bmp)
        _gdi32.DeleteDC(mem_dc)
        _user32.ReleaseDC(hwnd, hwnd_dc)


def _crop_group(img, win_origin, group_rect, upscale: int):
    """Recorta `img` (janela inteira) ao `group_rect` absoluto, e amplia. Requer Pillow."""
    from PIL import Image  # dep: Pillow

    wl, wt = win_origin
    gl, gt, gr, gb = group_rect
    box = (gl - wl, gt - wt, gr - wl, gb - wt)
    box = (max(0, box[0]), max(0, box[1]),
           min(img.width, box[2]), min(img.height, box[3]))
    crop = img.crop(box)
    if upscale and upscale > 1:
        crop = crop.resize((crop.width * upscale, crop.height * upscale), Image.BICUBIC)
    return crop


# ----------------------------------------------------------------------------- #
# OCR (winsdk / Windows.Media.Ocr)
# ----------------------------------------------------------------------------- #
async def _ocr_async(png_bytes: bytes) -> str:
    # imports localizados: erro de dependência fica claro e não parte o import do módulo
    # dual-import: winsdk (Py<=3.13) OU winrt-* (Py 3.14+; API idêntica)
    try:
        from winsdk.windows.graphics.imaging import BitmapDecoder
        from winsdk.windows.media.ocr import OcrEngine
        from winsdk.windows.storage.streams import DataWriter, InMemoryRandomAccessStream
        from winsdk.windows.globalization import Language
    except ImportError:
        from winrt.windows.graphics.imaging import BitmapDecoder
        from winrt.windows.media.ocr import OcrEngine
        from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream
        from winrt.windows.globalization import Language

    stream = InMemoryRandomAccessStream()
    writer = DataWriter(stream.get_output_stream_at(0))
    # bytearray: aceite por winrt E winsdk. Se um build winsdk reclamar, reverter
    # SÓ este arg para list(png_bytes).
    writer.write_bytes(bytearray(png_bytes))
    await writer.store_async()
    await writer.flush_async()
    stream.seek(0)

    decoder = await BitmapDecoder.create_async(stream)
    bitmap = await decoder.get_software_bitmap_async()

    engine = OcrEngine.try_create_from_user_profile_languages()
    if engine is None:
        engine = OcrEngine.try_create_from_language(Language("en-US"))
    if engine is None:
        raise RuntimeError("sem engine OCR (faltam language packs?)")

    result = await engine.recognize_async(bitmap)
    return result.text or ""


def _ocr_text(pil_image) -> str:
    """PIL.Image -> texto OCR (uma linha). Corre o event loop interno."""
    buf = io.BytesIO()
    pil_image.save(buf, format="PNG")
    png = buf.getvalue()
    return asyncio.run(_ocr_async(png))


# ----------------------------------------------------------------------------- #
# Parse
# ----------------------------------------------------------------------------- #
# Layout observado no OCR (labels primeiro, depois valores, depois coluna direita):
#   "... Total Nodes Total Tree Size HRC available 507581 4.56B 20.36B / 20.46B Flop ..."
# -> nodes = 1.º inteiro após "Total Nodes"
# -> GBs em ordem: [tree_size, hrc_available, hrc_total]
_RE_NODES = re.compile(r"Total\s*Nodes\D*?(\d[\d.,]*)", re.IGNORECASE)
# "GB" sai por vezes como "6B"/"G8"; ")" é o "0" mal lido (normalizado antes)
_RE_GB = re.compile(r"([0-9][0-9.,]*?)\s*(?:GB|6B|G8)", re.IGNORECASE)


def _to_int(s):
    s = re.sub(r"[^\d]", "", s or "")
    return int(s) if s else None


def _to_float(s):
    s = (s or "").replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def _parse(text: str) -> dict:
    norm = text.replace(")", "0")  # ").4GB" -> "0.4GB"
    m = _RE_NODES.search(norm)
    nodes = _to_int(m.group(1)) if m else None
    gbs = [_to_float(g) for g in _RE_GB.findall(norm)]
    gbs = [g for g in gbs if g is not None]
    gb = gbs[0] if len(gbs) >= 1 else None              # Total Tree Size
    hrc_available = gbs[1] if len(gbs) >= 2 else None    # HRC available (1.º do par)
    return {"nodes": nodes, "gb": gb, "hrc_available_gb": hrc_available}


def _sanity(d: dict) -> bool:
    if d["nodes"] is None or d["nodes"] <= 0:
        return False
    if d["gb"] is None or d["gb"] < 0:
        return False
    if d["hrc_available_gb"] is not None and d["gb"] > d["hrc_available_gb"] * 4:
        # tree >> RAM disponível é fisicamente improvável de ler bem -> desconfiar
        return False
    return True


# ----------------------------------------------------------------------------- #
# API pública
# ----------------------------------------------------------------------------- #
def capture_tree_stats(top_hwnd=None, upscale: int = DEFAULT_UPSCALE) -> dict:
    """Lê as estatísticas da tree da página de setup do HRC (read-only, background-safe).

    top_hwnd: hwnd da janela 'Hand Setup'. Se None, é localizada por título.
    Devolve sempre um dict (ver contrato no topo); nunca lança.
    """
    base = {"nodes": None, "gb": None, "hrc_available_gb": None, "ok": False, "raw": ""}
    try:
        if top_hwnd is None:
            top_hwnd = find_hand_setup_window()
            if not top_hwnd:
                base["raw"] = "err:janela Hand Setup nao encontrada"
                return base

        group_hwnd, group_rect = find_tree_stats_group(top_hwnd)
        if not group_hwnd or not group_rect:
            base["raw"] = "err:grupo Tree Statistics nao encontrado"
            return base

        img, origin = _capture_window_rgb(top_hwnd)
        crop = _crop_group(img, origin, group_rect, upscale)
        text = _ocr_text(crop)

        parsed = _parse(text)
        parsed["raw"] = text
        parsed["ok"] = _sanity(parsed)
        return parsed
    except Exception as e:  # nunca rebenta o watcher
        base["raw"] = "err:%s" % e
        return base


if __name__ == "__main__":
    # smoke-test: abrir o HRC na pagina de setup com o painel Tree Statistics visivel.
    import json
    print(json.dumps(capture_tree_stats(), ensure_ascii=False, indent=2))
