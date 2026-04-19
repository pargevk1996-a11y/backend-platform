from __future__ import annotations

from pathlib import Path

import pytest

from shared.config import load_file_backed_env


def test_load_file_backed_env_reads_and_trims(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret_file = tmp_path / "pepper.txt"
    secret_file.write_text("super-secret-value\n\n", encoding="utf-8")
    monkeypatch.setenv("MY_PEPPER_FILE", str(secret_file))

    out = load_file_backed_env({"my_pepper": "MY_PEPPER_FILE"})

    # Trailing whitespace/newlines are stripped so PEM blocks round-trip intact
    # but bare values are not padded with `\n`.
    assert out == {"my_pepper": "super-secret-value"}


def test_load_file_backed_env_missing_file_is_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MY_PEPPER_FILE", str(tmp_path / "nope.txt"))

    # Silent fallback keeps the caller's inline env value in effect.
    assert load_file_backed_env({"my_pepper": "MY_PEPPER_FILE"}) == {}


def test_load_file_backed_env_missing_env_is_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MY_PEPPER_FILE", raising=False)

    assert load_file_backed_env({"my_pepper": "MY_PEPPER_FILE"}) == {}
