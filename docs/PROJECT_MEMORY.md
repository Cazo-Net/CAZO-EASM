# EASM Platform — Project Memory

_Last updated: 2026-07-19 22:16_

## Objective
External Attack Surface Management (EASM) platform with Shadow Asset Detection, Historical Continuity signals, OSINT Intelligence Engine, and unified discovery. Currently executing **scan engine correctness fixes** — diagnosing and fixing silent-failure issues across nuclei, amass, Wappalyzer, DNS TTL, NS records, and port banner data. Earlier completed a full design consistency pass across every frontend page.

## Important Details
- Backend: FastAPI + SQLAlchemy + SQLite (dev), PostgreSQL (prod via Docker Compose), JWT auth
- Frontend: Next.js 14 + React + TypeScript + Tailwind CSS
- Admin login: set via ADMIN_EMAIL / ADMIN_PASSWORD env vars (never commit credentials)
- PowerShell 5.1 shell — no `&&`, no `grep`, no `tail`; use `;` and `Select-String`
- Dev servers: frontend `http://localhost:3000`, backend `http://localhost:8000`
- Python 3.14 on dev machine — run uvicorn WITHOUT `--reload` (FD limit crash on Windows)
- `.venv` does NOT exist on dev machine — use global Python `C:\Python314\python.exe` which has FastAPI/uvicorn installed globally
- SQLite DB is at `D:\Books\Project\easm-platform\backend\data\easm.db`
- All AI code removed from platform
- Design system colors: Void `#0A0B0F`, Obsidian `#12131A`, Graphite `#1C1D2A`, Phosphor `#00FF88`, Cyan `#00D4FF`, Signal Red `#FF3366`, Amber `#FFAA00`
- Typography: Space Grotesk (headings via `font-display`), Inter (body), JetBrains Mono (`font-mono`) for all numbers, IPs, domains, timestamps, technical data
- Constraint: additive-only schema changes; no subdomain enumeration/port scan rebuild
- nuclei binary NOT installed on dev machine — scanner returns error, pure-Python `security_findings.py` scanner always runs as fallback
- hackertarget API rate-limited on dev machine ("API count exceeded") — subdomain results limited
- certspotter returns 0 entries for test domains (testphp.vulnweb.com, scanme.nmap.org)
- testphp.vulnweb.com behind CloudFront CDN — drops raw TCP from non-browser; port scans time out
- scanme.nmap.org reachable — ports 22 (OpenSSH_6.6.1p1) and 80 (Apache/2.4.7) confirmed open
- PowerShell Python string escaping: always write test scripts to files rather than inline `-c` commands
- Set `$env:PYTHONPATH = "D:\Books\Project\easm-platform\backend"` before running test scripts

## Work State

### Completed
- **Evidence Center** — migration `j3k4l5m6n7o8` applied; Vulnerability model + FindingHistory + FindingEvidence models; all routes wired and tested
- **Evidence Center 500 bug FIXED** — `VulnerabilityResponse` field_validator coercing None→[]
- **Persist SAN + ASN + relationships** — `san` column on SSLCertificate + migration `k4l5m6n7o8p9`; shared ASN resolver; shared_registrar O(n²) fixed
- **Shadow-detection service** — `shadow_assets.py` with confidence weights; `AssetReviewLog` model + migration `l5m6n7o8p9q0`
- **Shadow Assets API + UI** — dedicated view + inline badge on asset cards
- **Historical Continuity badge** — "New · Nd ago" badge using `first_seen`
- **OSINT Intelligence Engine** — 6 key-free sources, caching, frontend with import button
- **Host Intelligence panel** — ASN/ISP, ports+banners, tech, certs, vulns on asset 360°
- **OSINT caching** — `OsintCache` model, migration `m6n7o8p9q0r1`, 40.6s→2.1s (20x speedup)
- **Design consistency pass — ALL 19 PAGE FILE GROUPS COMPLETE**
- **Landing page design system pass** — all hardcoded colors → design tokens, `font-display` on headings, `font-mono` on technical data, `HeroStages.tsx` WAAPI offset bug fixed
- **All 69 pages tested and passing** — 41 public + 24 authenticated + 3 dynamic + 15 API endpoints
- **empty/type page fixed** — `return null` replaced with fallback UI
- **scan/[id] page fixed** — wrapped in `<Suspense>` for SSR compatibility
- **OSINT Intel page full diagnosis + fixes** — 4 bugs found and fixed (rate-limit silent, no IPs resolved, port dedupe, hardcoded CVE keywords, empty panels, status badges)
- **SCAN ENGINE CORRECTNESS — ALL 6 ITEMS COMPLETE (2026-07-19)**
  1. **Nuclei**: Added `scanner_status` dict to runner + `Scan.scanner_status` column (migration `dc6f43394004`) + ScanDetail schema + API response + frontend Scanner Health panel. Shows "skipped: nuclei binary not found"
  2. **Amass + Subfinder**: Scanners now return `success: False` when binary missing; runner checks `is_available` property to report "not installed" (was falsely "ok (0 found)")
  3. **Wappalyzer (tech.py)**: Added HTTP fallback when HTTPS fails; Wappalyzer.latest() wrapped in try/except; `_basic_detection` tries HTTP when HTTPS fails; returns `success: False` on connection failure
  4. **DNS TTL (dns.py)**: Fixed TTL extraction — uses `answers.ttl` (RRset TTL) instead of `rdata.ttl` (which is None in dnspython). TTL now stored correctly
  5. **NS Records**: Verified working for apex domains (nmap.org shows 5 NS records with TTL). Not a bug — subdomains correctly have no NS records at host level
  6. **Port version/banner (ports.py)**: Added banner grabbing to Python socket fallback (sends probe, reads response, extracts version via regex). Fixed nmap full scan range 1-1000→1-10000
  - **CRITICAL BUG FIX**: `_plugin_instance()` registry helper was resolving `security-findings` and `cve-correlation` scanners to the FIRST VULNERABILITY plugin (NucleiScanner) instead of their actual classes. Fixed by instantiating scanner classes directly in `ScanRunner.__init__`. This caused security-findings/cve-correlation to always "fail" when nuclei binary was missing.

### Active
- (none — all 6 items complete)

### Blocked
- (none)

## Next Move
All scan engine correctness items are complete and verified end-to-end. Potential follow-ups:
- Test with nuclei/amass/subfinder binaries installed to verify "ok" paths
- Consider adding parent-domain NS scanning when scanning a subdomain (design decision)
- Run full regression test suite

## Relevant Files
- `backend/app/scanners/runner.py` — scan orchestrator (scanner_status tracking for ALL scanners; fixed _plugin_instance bug)
- `backend/app/scanners/nuclei_scanner.py` — nuclei scanner (binary not installed, returns error)
- `backend/app/scanners/security_findings.py` — pure-Python vulnerability scanner (always runs)
- `backend/app/scanners/amass.py` — amass subdomain scanner (is_available property, returns success:False when missing)
- `backend/app/scanners/subfinder.py` — subfinder scanner (is_available property, returns success:False when missing)
- `backend/app/scanners/tech.py` — technology fingerprinting (HTTP fallback, Wappalyzer.latest() guarded)
- `backend/app/scanners/dns.py` — DNS scanner (TTL from answers.ttl, NS/MX/TXT/DMARC/DKIM)
- `backend/app/scanners/ports.py` — port scanner (banner grabbing in python fallback, 1-10000 range)
- `backend/app/models/scan.py` — Scan model (scanner_status column + property)
- `backend/app/schemas/scan.py` — ScanDetail schema (scanner_status field)
- `backend/app/api/v1/scan.py` — scan API (returns scanner_status)
- `backend/app/services/scan_service.py` — stores scanner_status to Scan
- `frontend/src/app/scan/[id]/page.tsx` — scan detail page (Scanner Health panel)
- `frontend/src/types/index.ts` — ScanDetail type (scanner_status, ports_count)
- `frontend/src/app/dns/page.tsx` — DNS records page (TTL display)
- `alembic/versions/dc6f43394004_add_scanner_status_to_scans.py` — migration for scanner_status column
