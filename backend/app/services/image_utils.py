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
