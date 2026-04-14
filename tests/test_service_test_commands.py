from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_make_test_runs_service_suites() -> None:
    result = subprocess.run(
        ["make", "test"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
