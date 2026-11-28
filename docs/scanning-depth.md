# Scan depth and exposure detection

This page describes what a v2 scan checks on a customer's **in-scope**
domain, how hard it pushes each host, and which optional open-source tools
it can use. Scope rules are unchanged: a scan only starts for a domain the
organization has added to its Scopes (`SCOPE_ENFORCEMENT`), discovered hosts
outside that domain are recorded but never contacted, and private, loopback,
link-local and cloud-metadata addresses are always blocked.

## Profiles

Defined in `backend/app/scanners/v2/profiles.py`.

| Profile | Used by | TCP ports per host | Hosts port-scanned | Web services checked | Requests per host | Pipeline budget |
|---|---|---|---|---|---|---|
| quick | `scan_type=quick` | 23 common web/admin/DB ports | 5 | (quick scans skip web checks) | 80 | 5 min |
| standard | `scan_type=full` (default) | ~1,300 (common ports, web, sensitive services, all of 1-1024) | 25 unique IPs | 40 | 220 at 5 req/s | 25 min |
| deep | `scan_options.depth = "deep"` | ~10,000 (1-10000 plus sensitive high ports) | 50 unique IPs | 80 | 320 at 5 req/s | 40 min |

The pipeline budget is always capped below the queue's job timeout
(`SCAN_TIMEOUT_FULL_MINUTES`, default 45) so the worker, not the reaper,
ends a long scan. Hosts that share an IP (CDNs, load balancers) are port
scanned once.

Before this change every full scan was silently cut to 10 ports on the apex
domain only, vulnerability-stage results were dropped before storage, and
TLS ports were never actually upgraded to TLS.

## What each stage now does

1. **Asset discovery**: certificate transparency and passive DNS sources,
   `subfinder` when installed, and DNS brute force with wildcard DNS
   filtering.
2. **Network**: TCP connect scan per profile, banner and HTTP probes,
   working TLS upgrade, then `nmap -sV --version-light` on the ports that
   were found open (when nmap is installed) for exact versions.
3. **Certificates**: every in-scope TLS endpoint the port scan found: issuer,
   SANs, key type and size, signature algorithm, expiry, browser trust,
   host-name match, and whether TLS 1.0/1.1 is still accepted.
4. **Web exposure** (`web_exposure.py`), for every in-scope web service:
   - fingerprint: title, status, server, redirect chain, technologies with
     versions (headers, meta generator, existing fingerprint set);
   - security headers, session cookie flags, version disclosure, internal IPs
     in headers, login forms over plain HTTP;
   - exposed files and endpoints, each confirmed by content: `.env`, `.git`,
     `.svn`, `.hg`, config backups (`wp-config.php.bak`, `web.config`,
     `appsettings.json`, Spring config, `docker-compose.yml`, `.npmrc`,
     `.aws/credentials`, SSH keys, `.htpasswd`), SQL dumps and backup
     archives (including ones named after the site), debug pages (phpinfo,
     server-status, Spring actuator, pprof, Symfony profiler, ELMAH,
     Werkzeug console), logs, Prometheus metrics, OpenAPI/Swagger, GraphQL;
   - open directory listings;
   - admin and management panels (phpMyAdmin, Adminer, Tomcat Manager,
     Jenkins, Grafana, Kibana, Solr, Jupyter, H2, Portainer, Webmin,
     Kubernetes dashboard, Traefik, Argo CD and more), plus unauthenticated
     Elasticsearch and CouchDB;
   - credentials visible in public content: the home page and up to N
     same-site scripts are checked for AWS, Google, Stripe, GitHub, GitLab,
     Slack, Twilio, SendGrid, Mailgun, OpenAI, Anthropic keys, private keys,
     database URLs with passwords, JWTs and hard-coded passwords.
5. **Vulnerability assessment**: security-findings and CVE correlation now
   receive the earlier stages' data (they previously got nothing), cloud
   storage with a name matching the domain is reported only when it is
   publicly listable, and exposure-validation keeps CORS, open-redirect and
   takeover checks.

## Safety rules the checks follow

- Only GET requests that any visitor could make. No logins, default
  credentials, form posts, payloads, fuzzing or exploitation.
- Response bodies are read up to 64 KB (2 MB for scripts), so an exposed
  backup is recognised from its first bytes and never downloaded.
- A path is only reported when its content matches what it claims to be,
  and a random-path request first learns how the site answers missing pages.
- Secrets are never stored. A finding keeps the type, location, a redacted
  preview (`AKIAIO…MPLQ (20 chars)`) and a SHA-256 fingerprint so the same
  key can be tracked until it is rotated.
- Redirects are only followed while they stay inside the authorized domain;
  third-party scripts are not fetched.
- Per host: a few requests in flight, about 5 requests a second, and a hard
  request budget. Port scanning uses 100-200 concurrent connects per host
  (was 2,000) with a per-host time budget.
- The scanner identifies itself: `CAZO-EASM/2.1 (+https://cazoeasm.io; attack surface monitoring)`.

## Optional open-source tools

Each is used only if its binary is in the image. None is installed by this
change.

| Tool | Setting | Default | Use |
|---|---|---|---|
| nmap | (always when present) | on | `-sV` on ports already found open |
| subfinder | `SCAN_ENABLE_SUBFINDER` | on | passive subdomain sources |
| nuclei | `SCAN_ENABLE_NUCLEI`, `NUCLEI_RATE_LIMIT` | **off** | exposure, misconfiguration, panel, tech, token, TLS and takeover templates only; intrusive, brute-force, fuzzing, DoS, default-login, injection and out-of-band tags excluded; interactsh off; 10 req/s |

httpx, naabu and amass were considered: httpx and naabu duplicate the
built-in fingerprinting and port scan, and amass is too slow for the request
path. They fit a dedicated scan fleet better.
