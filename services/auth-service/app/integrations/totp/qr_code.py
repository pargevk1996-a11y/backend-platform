from __future__ import annotations

import base64
from io import BytesIO

import qrcode  # type: ignore[import-untyped]
from qrcode import constants  # type: ignore[import-untyped]


def generate_qr_png_base64(data: str) -> str:
    # Explicit box_size/border: tiny default PNGs from qrcode.make() are flaky with OpenCV
    # QRCodeDetector in headless CI (e2e decodes the PNG for TOTP setup).
    qr = qrcode.QRCode(
        version=None,
        error_correction=constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")
