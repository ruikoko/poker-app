"""Image utilities — magic-number MIME detection.

Extraído de discord_bot._detect_image_mime para reuso em:
- discord_bot._handle_lobby_message
- services.lobby_sync.run_sync
- routers.tournament_results
"""
from __future__ import annotations


def detect_image_mime(image_bytes: bytes) -> str:
    """Detecta mime type pelos magic numbers nos primeiros bytes.

    Discord pode reportar content_type errado (ex: 'image/webp' em bytes PNG),
    e Anthropic rejeita 400 quando media_type nao bate com magic. Esta funcao
    ignora o que vier do caller e usa os bytes como fonte de verdade.

    Fallback para 'image/png' se nenhum magic match (Anthropic e tolerante a
    PNG declarado para outros formatos comuns)."""
    if not image_bytes:
        return "image/png"
    if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if image_bytes[:3] == b"\xFF\xD8\xFF":
        return "image/jpeg"
    if (
        len(image_bytes) >= 12
        and image_bytes[:4] == b"RIFF"
        and image_bytes[8:12] == b"WEBP"
    ):
        return "image/webp"
    return "image/png"


def compress_image(
    image_bytes: bytes, max_width: int = 1280, quality: int = 85
) -> tuple[str, str]:
    """Comprime para guardar na BD: redimensiona a `max_width` e converte a JPEG.

    Espelho do padrão dos replayers (`screenshot._compress_image`, 1280px/JPEG85):
    o mesmo regime de poupança usado em `entries.raw_json.img_b64`, agora também
    para o table-SS. Devolve (base64_str, mime). Em qualquer falha de PIL devolve
    o original em base64 com o mime detectado (fail-safe — nunca rebenta o upload).
    """
    import base64
    import io
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")
        if img.width > max_width:
            ratio = max_width / img.width
            img = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        return base64.b64encode(buf.getvalue()).decode("ascii"), "image/jpeg"
    except Exception:
        return base64.b64encode(image_bytes).decode("ascii"), detect_image_mime(image_bytes)
