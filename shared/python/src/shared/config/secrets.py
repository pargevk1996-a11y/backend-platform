"""Docker-secrets helper: read ``<FIELD>_FILE`` env vars from files."""
from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path


def load_file_backed_env(field_to_env: Mapping[str, str]) -> dict[str, str]:
    """Resolve file-backed secret values.

    ``field_to_env`` maps Pydantic field name (e.g. ``jwt_private_key``) to the
    environment variable name whose *value* is the path to the secret file
    (e.g. ``JWT_PRIVATE_KEY_FILE``). For each mapping entry, if the env var is
    set and the file is readable, its trimmed contents are returned under the
    field name. Missing/invalid paths are silently skipped so that callers can
    always fall back to inline env values.
    """
    resolved: dict[str, str] = {}
    for field_name, file_env in field_to_env.items():
        path = os.getenv(file_env)
        if not path:
            continue
        try:
            resolved[field_name] = Path(path).read_text(encoding="utf-8").strip()
        except OSError:
            continue
    return resolved
