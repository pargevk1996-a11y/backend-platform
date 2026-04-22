from __future__ import annotations

from app.core.validation import sanitize_validation_errors


def test_validation_error_log_sanitization_removes_input() -> None:
    errors = [
        {
            "type": "missing",
            "loc": ("body", "authorization"),
            "msg": "Field required",
            "input": "Bearer secret",
        }
    ]

    sanitized = sanitize_validation_errors(errors)

    assert "input" not in sanitized[0]
    assert sanitized[0]["loc"] == ("body", "authorization")
