# Runbook: Security Incident Response

## Trigger Conditions
- Abnormal login failures spike.
- Token reuse detection spike.
- Suspicious role assignments.

## Immediate Actions
1. Declare incident and assign commander.
2. Freeze non-essential deployments.
3. Capture:
   - gateway logs
   - auth/user audit events
   - Redis brute-force counters
4. Contain:
   - revoke suspicious refresh families
   - disable affected accounts if needed

## Investigation Checklist
- Was 2FA enabled on impacted users?
- Were backup codes consumed unexpectedly?
- Were admin roles modified?
- Any anomalous source IP/user-agent patterns?

## Recovery
- Rotate JWT keys if token leakage suspected.
- Reset credentials and regenerate backup codes for impacted users.
- Validate normal auth flow end-to-end.

## Postmortem
- Document timeline, root cause, blast radius, and remediation items.
- Add detection rules/tests to prevent recurrence.
