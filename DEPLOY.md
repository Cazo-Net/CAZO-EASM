# Deployment Guide (EASM / CAZO EASM)

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
   - `backend` runs `python -m app.db_migrate` on start (creates or upgrades
     the schema, and stops the deploy if that fails).
   - `scan-worker` runs queued scans, scheduled scans and periodic jobs.
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

## Scans, workers and scope

Scans never run inside a web request. The API writes each scan to the
`scan_jobs` table and scan workers run it. Workers send heartbeats, enforce a
time limit, retry failures with backoff, give each organization a fair share
(`SCAN_MAX_RUNNING_PER_ORG`), and put unfinished work back in the queue when
they are stopped. They also turn due schedules into scans and run the daily
and weekly maintenance jobs, once across all workers.

- **Add capacity**: `docker compose up -d --scale scan-worker=3`, or raise
  `SCAN_WORKER_CONCURRENCY`.
- **Queue health**: `GET /health/scans` shows the mode, job counts and how long
  the oldest job has been waiting. If that keeps growing, no worker is running.
- **Scope**: with `ENVIRONMENT=production` the default is
  `SCOPE_ENFORCEMENT=registered`: a target must be on the organization's
  Authorized Scopes list, which an organization admin maintains. This records
  who claimed which domain but does not prove ownership. Set
  `SCOPE_ENFORCEMENT=verified` to also require proof: domains are verified with
  a DNS TXT record (shown on the Authorized Scopes page with a Verify button),
  IP and CIDR scopes by a platform administrator (set `verified = true` on the
  `authorized_scopes` row from the admin panel or SQL). Private, loopback and
  cloud-metadata addresses are always blocked.

### Upgrading an existing deployment

- Scope enforcement was switched off in an earlier release; this one turns it
  back on in production as `SCOPE_ENFORCEMENT=registered`. After the upgrade,
  scans and schedules for a domain are refused until an organization admin
  adds that domain on the Scopes page. Schedule owners get a notification when
  a scheduled scan is skipped for this reason.
- `registered` does not prove ownership: an organization admin can list any
  public domain. Verification is already available on the Scopes page, so ask
  customers to publish their TXT records, then switch to
  `SCOPE_ENFORCEMENT=verified`. `open` restores the previous behaviour.
- Only people who can manage the organization can add a domain to the scope
  list; other members see "not in your authorized scope" until an admin adds it.
- OSINT lookups (`/api/v1/osint`) follow the same scope rules as scans.

## Railway

Railway builds each service from the repository root. Set each service's
config file path in its settings:

| Service | Config file | Notes |
| --- | --- | --- |
| API | `backend/railway.json` | Runs migrations, then the API. |
| Scan worker | `backend/railway.worker.json` | Uses the scan-engine image (nmap, subfinder, amass, nuclei). Give it the same `DATABASE_URL`, `SECRET_KEY` and `JWT_SECRET_KEY` as the API. |
| Frontend | `frontend/railway.json` | |

Until the scan worker service exists, the API runs an embedded worker
(`RUN_EMBEDDED_WORKER=true`, the default), so scans keep working. Once the
worker service is up, set `RUN_EMBEDDED_WORKER=false` on the API.

## Troubleshooting

- **nginx crash-loops on first deploy**: certbot did not issue a cert. Check
  `docker compose logs certbot` — usually DNS/port-80 or `ACME_EMAIL` missing.
- **Migrations**: the `api` mode runs `python -m app.db_migrate`
  automatically. It handles empty databases, Alembic-managed ones, and ones
  that were built with `create_all` and never stamped. For a manual run use
  `docker compose run --rm backend sh /app/entrypoint.sh migrate`.
- **Scans stay "pending"**: check `GET /health/scans`. Either no scan worker is
  running or `RUN_EMBEDDED_WORKER` is off with no worker service deployed.
