from __future__ import annotations

from pathlib import Path


def _has_explicit_test_path(config) -> bool:
    args = [str(arg) for arg in config.invocation_params.args]
    return any(arg.startswith(("services/", "tests/")) for arg in args)


def pytest_ignore_collect(collection_path, config) -> bool:
    if _has_explicit_test_path(config):
        return False

    path = Path(str(collection_path))
    parts = path.parts
    if "services" in parts and "tests" in parts:
        return True
    if "tests" in parts and "e2e" in parts:
        return True
    return False
