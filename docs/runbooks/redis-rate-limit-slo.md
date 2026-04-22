# Runbook: Redis, rate limiting, and TRUSTED_PROXY_IPS (operations SLO)

## Role of Redis

- **api-gateway** and **auth-service** use Redis for rate limiting, session markers (e.g. access-session revoked keys), and related counters.
- If Redis is **unavailable**, clients may see **HTTP 503** (or the gateway’s “service unavailable” mapping) rather than unbounded access — this is intentional: **failing closed** avoids silent bypass of abuse protections.

## SLO / expectations

| Symptom | Operational meaning |
|--------|----------------------|
| Spike of **503** on auth or gateway | Treat Redis connectivity as **degraded** until restored; scale or fail over Redis. |
| Rate limits **too strict** for legitimate users | Check **client IP derivation**: if traffic passes through a reverse proxy, `TRUSTED_PROXY_IPS` must list the proxy’s **outbound** addresses or CIDRs so `X-Forwarded-For` is trusted only from those hops. Wrong settings can lump users behind one IP or ignore real client IPs. |
| Rate limits **too loose** | Verify you are not trusting `X-Forwarded-For` from arbitrary clients: only trusted proxies should allow XFF to override the socket peer IP. See [trusted-proxy-ips.md](trusted-proxy-ips.md). |

## Monitoring checklist

1. **Redis**: memory, replication lag (if clustered), eviction policies, AUTH / TLS in line with your network model.
2. **Application**: error rate on `rate_limit.*` / Redis errors in logs; correlation with 503 from gateway.
3. **Deploy**: after changing **edge topology**, revisit `TRUSTED_PROXY_IPS` on both gateway and auth-service so it matches the real proxy IPs.

## When Redis recovers

- No special migration is required for pure rate-limit keys; traffic should normalize as buckets refill.
- If you extended TTLs or incident holds elsewhere, follow your incident runbook.

## Related docs

- [trusted-proxy-ips.md](trusted-proxy-ips.md) — XFF trust model and tests.
- [rate-limiting.md](../architecture/rate-limiting.md) — product-facing rate limit behavior (if present).
