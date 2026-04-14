from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

SERVICE_ROOT = Path(__file__).resolve().parents[1]
SERVICE_ROOT_STR = str(SERVICE_ROOT)
SERVICE_ROOTS = {str(path) for path in SERVICE_ROOT.parent.iterdir() if path.is_dir()}
sys.path[:] = [path for path in sys.path if path not in SERVICE_ROOTS]
sys.path.insert(0, SERVICE_ROOT_STR)
for module_name in list(sys.modules):
    if module_name == "app" or module_name.startswith("app."):
        del sys.modules[module_name]


@pytest.fixture(autouse=True)
def _configure_test_env() -> None:
    os.environ["REDIS_URL"] = "redis://localhost:6379/2"
    os.environ["AUTH_SERVICE_URL"] = "http://auth-service:8001"
    os.environ["USER_SERVICE_URL"] = "http://user-service:8002"
    os.environ["JWT_ALGORITHM"] = "HS256"
    os.environ["JWT_ISSUER"] = "backend-platform"
    os.environ["JWT_AUDIENCE"] = "backend-clients"
    os.environ["JWT_PUBLIC_KEY"] = "gateway-test-key"
    os.environ["PRIVACY_KEY_PEPPER"] = "gateway-test-privacy-pepper-very-long"

    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
