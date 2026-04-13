from __future__ import annotations

TOKEN_TYPE_ACCESS = "access"

PUBLIC_ENDPOINTS = {
    ("POST", "/v1/auth/register"),
    ("POST", "/v1/auth/login"),
    ("POST", "/v1/auth/login/2fa"),
    ("POST", "/v1/tokens/refresh"),
    ("POST", "/v1/tokens/revoke"),
    ("GET", "/v1/health/live"),
    ("GET", "/v1/health/ready"),
}
