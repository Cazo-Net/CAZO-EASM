# Deployment Guide (EASM / AttackSec)

This guide covers deploying the platform to a real domain using Docker Compose
(the production stack in `docker-compose.yml` + `docker-compose.prod.yml`).
A bare-metal systemd path also exists under `scripts/` (see the note at the end).

## Prerequisites

1. **A server** with Docker + Docker Compose installed and a public IP.
2. **A domain** you control, with DNS **A/AAAA records** pointing at the server.
3. **Ports 80 and 443 open** inbound (port 80 is required for Let's Encrypt
   HTTP-01 validation).
4. **Postgres and Redis** are provided by the compose stack itself; you only
   need to set strong credentials.
5. **Secrets**: generate `SECRET_KEY` and `JWT_SECRET_KEY` (32+ random bytes
   each):
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

## Steps

1. Copy and edit the environment file:
   ```bash
   cp .env.example .env
   ```
   Fill in at least: `SECRET_KEY`, `JWT_SECRET_KEY`, `POSTGRES_PASSWORD`,
   `SERVER_NAME` (your real domain), and `ACME_EMAIL` (a real inbox you control
   for certificate expiry notices).

2. Bring up the stack (the prod file merges with the base):
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
   ```
   - `db` (Postgres) and `redis` start first.
   - `backend`/`worker` run `alembic upgrade head` on start (creates schema).
   - `nginx` starts once `backend` is healthy.
   - `certbot` **issues** a certificate on first run (if one does not exist),
     then renews every 12h.

3. Verify:
   ```bash
   curl -I https://${SERVER_NAME}/health   # expect 200
   docker compose logs -f certbot           # first run should show "Congratulations"
   ```
   If nginx fails to start, confirm the certificate was issued:
   `docker compose exec certbot ls /etc/letsencrypt/live`.

## Notes

- **First deploy needs port 80 reachable** so certbot can complete the ACME
  HTTP-01 challenge. The nginx template serves `/.well-known/acme-challenge/`
  from the shared `certbot-www` volume.
- **Renewals** are automatic (certbot renew loop). Certificates are stored in
  the `letsencrypt` volume.
- **Secrets must never be committed.** `.env` is git-ignored; only
  `.env.example` is tracked.
- **Bare-metal / systemd path**: the `scripts/*.service` units and
  `nginx/easm.conf` are for a non-Docker host. Before using them, edit
  `nginx/easm.conf` to replace the `your-domain.com` placeholder with your real
  domain and obtain TLS certs (e.g. `certbot --nginx -d your-domain.com`).

## Troubleshooting

- **nginx crash-loops on first deploy**: certbot did not issue a cert. Check
  `docker compose logs certbot` — usually DNS/port-80 or `ACME_EMAIL` missing.
- **Migrations**: if the schema changes, the backend/worker `migrate`/`api`
  modes run `alembic upgrade head` automatically; for manual runs use
  `docker compose run --rm backend migrate`.
