from __future__ import annotations

import base64
from io import BytesIO

import qrcode


def generate_qr_png_base64(data: str) -> str:
    image = qrcode.make(data)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")
