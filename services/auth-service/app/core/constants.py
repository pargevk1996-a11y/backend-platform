from __future__ import annotations

AUDIT_LOGIN_SUCCESS = "auth.login.success"
AUDIT_LOGIN_FAILED = "auth.login.failed"
AUDIT_REGISTER_SUCCESS = "auth.register.success"
AUDIT_REFRESH_SUCCESS = "auth.refresh.success"
AUDIT_REFRESH_REVOKED = "auth.refresh.revoked"
AUDIT_REFRESH_REUSE_DETECTED = "auth.refresh.reuse_detected"
AUDIT_2FA_ENABLED = "auth.2fa.enabled"
AUDIT_2FA_DISABLED = "auth.2fa.disabled"
AUDIT_2FA_SETUP_INITIATED = "auth.2fa.setup.initiated"
AUDIT_2FA_VERIFICATION_FAILED = "auth.2fa.verification.failed"
AUDIT_BACKUP_CODES_REGENERATED = "auth.2fa.backup.regenerated"
AUDIT_PASSWORD_RESET_REQUESTED = "auth.password_reset.requested"
AUDIT_PASSWORD_RESET_COMPLETED = "auth.password_reset.completed"

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"
