# AWS EC2 Deployment

This project is deployable on an Ubuntu EC2 instance with Docker Compose and Nginx as the public entrypoint.

## What gets deployed

- `nginx`: the only public service
- `app`: FastAPI API gateway
- `auth-service`: internal auth and 2FA service
- `user-service`: internal user/RBAC service
- `postgres-auth`: auth database
- `postgres-user`: user database
- `redis`: shared Redis with isolated DB indexes

## Important security note

Production browser auth uses `Secure` cookies. Health checks work over plain HTTP, but browser login, 2FA completion, refresh, and logout should be validated only after HTTPS termination is in place.

Recommended AWS setup:

- Put the EC2 instance behind an Application Load Balancer.
- Terminate TLS at the ALB with an ACM certificate.
- Forward traffic from the ALB to the EC2 instance on port `80`.
- Keep only `80` and `443` open to the internet.
- Do not open Postgres or Redis ports publicly.

## Ubuntu EC2 install commands

Run these on a fresh Ubuntu host:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker "$USER"
newgrp docker
```

## Clone and configure

```bash
git clone https://github.com/YOUR_ORG/backend-platform.git
cd backend-platform
cp .env.example .env
chmod 600 .env
```

Edit `.env` and set non-secret values:

- `AUTH_DB_PASSWORD`, `USER_DB_PASSWORD`, `REDIS_PASSWORD` (these are also mirrored
  into `secrets/*.txt` below — keep them identical)
- `CORS_ALLOWED_ORIGINS`
- `SERVER_NAME`
- `TRUSTED_PROXY_IPS`
- `SMTP_HOST`, `SMTP_USERNAME`, `SMTP_FROM_EMAIL`

## Provision secret files

All cryptographic material lives outside of `.env` to avoid `\n` escaping
issues in Compose and to shrink the blast radius if `.env` leaks.

```bash
mkdir -p secrets && chmod 700 secrets

# RSA 4096 keypair for JWT (PKCS8 / SPKI PEM)
openssl genpkey -algorithm RSA -out secrets/jwt_private.pem -pkeyopt rsa_keygen_bits:4096
openssl rsa -in secrets/jwt_private.pem -pubout -out secrets/jwt_public.pem

# Fernet symmetric key for TOTP secret encryption at rest
python3 -c "from cryptography.fernet import Fernet; open('secrets/totp_fernet.key','wb').write(Fernet.generate_key())"

# Peppers (48-byte random, url-safe base64)
python3 -c "import secrets; open('secrets/refresh_token_pepper.txt','w').write(__import__('base64').urlsafe_b64encode(secrets.token_bytes(48)).decode())"
python3 -c "import secrets; open('secrets/privacy_key_pepper.txt','w').write(__import__('base64').urlsafe_b64encode(secrets.token_bytes(48)).decode())"
python3 -c "import secrets; open('secrets/password_reset_pepper.txt','w').write(__import__('base64').urlsafe_b64encode(secrets.token_bytes(48)).decode())"

# SMTP relay password (example: AWS SES SMTP credentials)
printf '%s' 'YOUR_SMTP_PASSWORD' > secrets/smtp_password.txt

# DB / Redis — mirror the values from .env
awk -F= '/^AUTH_DB_PASSWORD=/{print $2}' .env  > secrets/auth_db_password.txt
awk -F= '/^USER_DB_PASSWORD=/{print $2}' .env  > secrets/user_db_password.txt
awk -F= '/^REDIS_PASSWORD=/{print $2}'    .env  > secrets/redis_password.txt

chmod 600 secrets/*
```

## Start the production stack

```bash
docker compose --env-file .env -f infra/compose/docker-compose.prod.yml up -d --build
```

This compose file runs DB migrations automatically before `auth-service` and `user-service` become healthy.

## Manual migration commands

Use these when you want to re-run migrations explicitly:

```bash
docker compose --env-file .env -f infra/compose/docker-compose.prod.yml run --rm auth-migrate
docker compose --env-file .env -f infra/compose/docker-compose.prod.yml run --rm user-migrate
```

## Check status and logs

```bash
docker compose --env-file .env -f infra/compose/docker-compose.prod.yml ps
docker compose --env-file .env -f infra/compose/docker-compose.prod.yml logs -f postgres-auth postgres-user redis auth-migrate user-migrate auth-service user-service app nginx
```

## Verify the running deployment

Replace `EC2_PUBLIC_DNS` with the instance DNS name or the ALB/DNS hostname.

```bash
curl -i http://EC2_PUBLIC_DNS/healthz
curl -i http://EC2_PUBLIC_DNS/v1/health/live
curl -i http://EC2_PUBLIC_DNS/v1/health/ready
```

Expected result:

- `/healthz` returns `200 OK` from Nginx
- `/v1/health/live` returns `200 OK`
- `/v1/health/ready` returns `200 OK` only when Redis and both internal services are ready

## Deploy updates

```bash
git pull --ff-only
docker compose --env-file .env -f infra/compose/docker-compose.prod.yml up -d --build
docker compose --env-file .env -f infra/compose/docker-compose.prod.yml ps
```

## Restart flow

```bash
docker compose --env-file .env -f infra/compose/docker-compose.prod.yml restart nginx app auth-service user-service redis postgres-auth postgres-user
```

## Stop the stack

```bash
docker compose --env-file .env -f infra/compose/docker-compose.prod.yml down
```
