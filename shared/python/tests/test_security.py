from __future__ import annotations

from shared.security import normalize_optional, stable_hmac_digest


def test_stable_hmac_digest_is_deterministic() -> None:
    a = stable_hmac_digest(value="user@example.com", pepper="p" * 48)
    b = stable_hmac_digest(value="user@example.com", pepper="p" * 48)
    assert a == b
    assert len(a) == 64  # sha256 hex digest length


def test_stable_hmac_digest_changes_with_pepper() -> None:
    a = stable_hmac_digest(value="v", pepper="pepper-a" + "x" * 40)
    b = stable_hmac_digest(value="v", pepper="pepper-b" + "x" * 40)
    assert a != b


def test_normalize_optional_handles_none_empty_and_whitespace() -> None:
    assert normalize_optional(None) == "<none>"
    assert normalize_optional("") == "<empty>"
    assert normalize_optional("   ") == "<empty>"
    assert normalize_optional("  hello  ") == "hello"
