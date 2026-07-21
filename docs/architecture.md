# CAZO EASM Architecture

> External Attack Surface Management (EASM) for authorized security
> assessments. The platform is built around a pluggable discovery architecture,
> an authorized-scope registry that gates all scanning, and a normalized asset
> inventory with scoring and change tracking.

## System Overview

```
                    Browser
                       │
                Next.js Dashboard
                       │
                REST API / WebSocket
                       │
             FastAPI (Python Backend)
                       │
     ┌─────────────────┼─────────────────┐
     │                 │                 │
 Scan Manager      Job Queue        Database
     │              Celery           PostgreSQL
     │                 │            (SQLite in dev)
     │                 │
 ┌───┴─────────────────┴───────────────────────────────┐
  │              Pluggable Discovery Registry            │
  │  subdomain │ bruteforce │ permutations │ dns │ whois  │
  │  ssl │ ports │ technology │ security-findings │ cve    │
  └─────────────────────────────────────────────────────┘
                       │
        ┌──────────────┼───────────────────────────┐
        │              │                           │
 Authorized-      Asset Inventory          Audit / Cache
   Scope              + Graph                (cross-cutting)
   Registry        + Scores + Timeline
```

## Components

### Frontend (Next.js)
- Dashboard with scan overview
- Scan creation form
- Real-time progress display
- Results visualization (tables, charts, graphs)
- Asset inventory management
- Authorized scope management
- Command palette (`Cmd/Ctrl + K`)

### Backend (FastAPI)
- REST API endpoints
- JWT authentication + API keys
- Scan orchestration
- Pluggable scanner registry
- Authorized-scope enforcement
- Asset inventory, scoring, and change tracking
- Generic audit logging + caching layer
- Risk scoring engine

### Database (PostgreSQL)
- User / organization / project management
- Scan results storage
- Authorized scopes
- Asset inventory + relationships
- Asset scores, change timeline
- Audit events

### Pluggable Discovery Registry
Scanners are registered via `app/scanners/registry.py` (`@register_scanner`)
and resolved at runtime by `ScanRunner`. New sources (e.g. a custom API, cloud
enumeration) can be added without touching orchestration code. Each plugin
declares a `category` and `capabilities`.

- **Subdomain Scanner** (`subdomain`) — passive discovery (crt.sh / OTX / AlienVault)
- **Subdomain Brute-force** (`subdomain-bruteforce`) — pure dnspython DNS brute-force
- **Subdomain Permutations** (`subdomain-permutations`) — pure string permutations
- **DNS Scanner** (`dns`) — resolves DNS records via dnspython
- **WHOIS Scanner** (`whois`) — domain registration info via python-whois
- **SSL Scanner** (`ssl`) — TLS certificate + chain + weak-protocol/cipher analysis
- **Port Scanner** (`ports`) — pure asyncio TCP connect + banner grab (no nmap)
- **Technology Scanner** (`technology`) — pure pattern engine (no Wappalyzer)
- **Security Findings** (`security-findings`) — pure HTTP misconfig + version-disclosure checks
- **CVE Correlation** (`cve-correlation`) — version-based CVE matching vs local NVD snapshot

> **Binary-free by design.** The scanner runs as plain Python/Node with zero
> external CLI binaries (nmap, nuclei, amass, subfinder, Wappalyzer were
> removed). This makes it deployable on serverless platforms (e.g. Vercel)
> without a binary-install phase. Honest tradeoffs: no live exploit
> verification (CVE findings are `verified=False` / UNVERIFIED), banner-only
> service fingerprinting (no nmap `-sV` deep OS/service detection), and a
> smaller tech-signature set than Wappalyzer.

The active plugin set is exposed at `GET /api/v1/scans/discovery/plugins`.

## Authorized-Scope Enforcement

Every scan target is checked against the organization's authorized scopes
(`domain`, `wildcard`, `ip`, `cidr`). A target that is not in scope (when
`REQUIRE_EXPLICIT_SCOPE` is enabled) causes the scan to be rejected with `403
Forbidden`. Scope values are validated on write; out-of-band ownership
verification is pluggable via `app/core/scope.py` (`ScopeVerifier`).

## Data Flow

1. Admin registers authorized scopes for the organization.
2. User submits a domain via the dashboard or API.
3. Backend checks the target against authorized scopes (rejects if out of scope).
4. `ScanRunner` resolves the relevant plugins from the discovery registry.
5. Subdomain scanner discovers subdomains; for each, parallel scans run:
   - DNS resolution
   - SSL certificate analysis
   - Port scanning
   - Technology detection
6. WHOIS lookup on the main domain.
7. Results are stored and backfilled into the **asset inventory**; relationships
   (e.g. `subdomain_of`) are derived.
8. Health and exposure scores are computed for each asset.
9. A **change-detection** pass diffs the new snapshot against the previous scan
   and records timeline entries.
10. All privileged actions are written to the **audit log**.
11. Dashboard updates with live progress.

## Security

- JWT-based authentication
- API key support for programmatic access
- RBAC (`admin`/`member`/`viewer`) with fine-grained `Permission` checks
- Authorized-scope enforcement on all discovery
- Audit logging of privileged actions
- Rate limiting
- CORS configuration
- Input validation
