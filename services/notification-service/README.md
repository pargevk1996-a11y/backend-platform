# notification-service

Notification delivery is intentionally WIP. The service currently exposes health probes and
baseline security middleware so it can be built, scanned, and tested consistently with the other
microservices.

## Status

- `GET /v1/health/live`
- `GET /v1/health/ready`

Do not wire this service into production traffic until a real delivery provider, queue boundary,
retry policy, and delivery audit trail are implemented and covered by tests.
