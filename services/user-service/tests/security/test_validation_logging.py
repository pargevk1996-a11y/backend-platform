from __future__ import annotations

from app.core.validation import sanitize_validation_errors


def test_validation_error_log_sanitization_removes_input() -> None:
    errors = [
        {
            "type": "string_too_long",
            "loc": ("body", "display_name"),
            "msg": "String should have at most 100 characters",
            "input": "private profile value",
        }
    ]

    sanitized = sanitize_validation_errors(errors)

    assert "input" not in sanitized[0]
    assert sanitized[0]["loc"] == ("body", "display_name")
