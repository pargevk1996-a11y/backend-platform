from __future__ import annotations

import pyotp


def generate_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(*, secret: str, account_name: str, issuer_name: str) -> str:
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=account_name, issuer_name=issuer_name)
