# SMTP (Gmail) on AWS EC2

This runbook matches [`infra/compose/docker-compose.prod.yml`](../infra/compose/docker-compose.prod.yml) and [`infra/scripts/render_prod_env_from_secrets.py`](../infra/scripts/render_prod_env_from_secrets.py).

## Secret files (host paths, repo root)

| Purpose | Path (on EC2 clone) | In-container path (bind mount) |
|--------|------------------------|----------------------------------|
| Gmail **App Password** (16 characters) | `secrets/smtp_app_password.txt` | `/app/secrets/smtp_app_password.txt` |
| Legacy alias (fallback) | `secrets/smtp_password.txt` | `/app/secrets/smtp_password.txt` |
| Mailbox for login + From (one line) | `secrets/smtp_identity_email.txt` | `/app/secrets/smtp_identity_email.txt` |
| Optional overrides | `secrets/smtp_host.txt`, `smtp_username.txt`, `smtp_from_email.txt`, `smtp_from_name.txt` | same under `/app/secrets/` |

Do not commit these files; `secrets/` is gitignored.

`auth-service` loads the app password from env `SMTP_PASSWORD` first; if empty, it tries `SMTP_PASSWORD_FILE` (set in compose to `smtp_app_password.txt`), then `secrets/smtp_app_password.txt`, then `secrets/smtp_password.txt`.

[`render_prod_env_from_secrets.py`](../infra/scripts/render_prod_env_from_secrets.py) prefers `smtp_app_password.txt`, then `smtp_password.txt`, then `SMTP_PASSWORD` in `infra/compose/.env.compose`.

## AWS infrastructure

| Check | Action |
|-------|--------|
| Outbound **TCP 587** (and 465 if you use implicit TLS) | EC2 security group: allow egress to `0.0.0.0/0` or at least `smtp.gmail.com` |
| DNS | Instance must resolve public hostnames |

## Deploy / refresh env

From the repo root (same place as `infra/`, `secrets/`):

```bash
export CORS_ORIGINS="http://YOUR_PUBLIC_IP:8080,http://YOUR_PUBLIC_IP"
python3 infra/scripts/render_prod_env_from_secrets.py --cors-origins "${CORS_ORIGINS}"
bash infra/scripts/ec2_compose_up.sh
```

Or pull latest and redeploy (same `CORS_ORIGINS` as above):

```bash
export CORS_ORIGINS="http://YOUR_PUBLIC_IP:8080,http://YOUR_PUBLIC_IP"
# default is main; set when your EC2 tracks a feature branch:
# export BRANCH=deploy/smtp-ec2-mail-delivery
bash infra/scripts/ec2_update.sh
```

[`ec2_update.sh`](../infra/scripts/ec2_update.sh) runs `git fetch/checkout/pull` on `BRANCH` (default `main`) and then [`ec2_compose_up.sh`](../infra/scripts/ec2_compose_up.sh).

## File permissions

The container runs as non-root (`appuser`). Ensure secret files are readable (often `chmod 644` for files owned by `ubuntu`). Avoid `600` root-only if the bind-mounted UID cannot read.

## Strict SMTP required

After mail works, set in `infra/compose/.env.compose`:

```env
AUTH_ALLOW_MISSING_SMTP=false
```

The prod compose default is `${AUTH_ALLOW_MISSING_SMTP:-true}` so the stack starts while secrets are incomplete; turn off when Gmail is fully configured.

## Verify

```bash
docker logs auth-service 2>&1 | tail -100
```

Look for `email.smtp_attempt` / `email.sent` after a password reset, or SMTP errors.
