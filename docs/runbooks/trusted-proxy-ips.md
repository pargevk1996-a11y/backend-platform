# Runbook: `TRUSTED_PROXY_IPS` and `X-Forwarded-For`

## Why it matters

Rate limiting and some audit paths derive a **client IP** from the request. When the gateway or auth-service sits behind a reverse proxy or load balancer, the direct TCP peer is often the proxy, not the end user. The end user IP may appear in `X-Forwarded-For` (XFF).

If you **trust** XFF from every client, an attacker can send `X-Forwarded-For: <victim-ip>` **directly** to the API and poison rate-limit buckets or audit metadata. Therefore the code only trusts XFF when the **immediate** peer ( `request.client.host` ) matches **`TRUSTED_PROXY_IPS`**.

## Configuration

- Set `TRUSTED_PROXY_IPS` to the IPs or CIDRs of your **real** edge proxies only (e.g. load balancer private IPs, Kubernetes ingress pods, or `127.0.0.1` for local chained proxies).
- Omit it or leave it empty if the service is reached **only** by end clients (no trusted hop). In that case XFF is **ignored** and the peer IP is used.

Format: comma-separated list, e.g. `10.0.0.10,172.20.0.0/16`.

## Verification checklist (production)

1. Confirm the observed `request.client.host` at the app matches your proxy’s outbound address (same network namespace / security group).
2. From a client **without** going through the proxy, send a request with `X-Forwarded-For: 203.0.113.50`. The effective client IP used for rate limiting must **not** become `203.0.113.50` unless that client is actually the trusted proxy.
3. From behind the real proxy, confirm the left-most XFF entry matches the expected public client IP.

## Automated tests

Unit tests in `services/api-gateway/tests/unit/test_security.py` cover:

- Ignoring XFF when the peer is not trusted.
- Honoring the first XFF hop when the peer matches a trusted IP or CIDR.

Run:

`PYTHONPATH=services/api-gateway pytest services/api-gateway/tests/unit/test_security.py -q`

## Related

- [redis-rate-limit-slo.md](redis-rate-limit-slo.md) — Redis availability and rate limiting SLO.
