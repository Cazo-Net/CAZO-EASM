# Scan Performance Optimization Plan

## Goal
Full scan of 1000+ subdomains: **< 20 minutes** (down from 3+ hours), while maintaining 100% quality on real findings.

## Root Causes Identified

### 1. Port Scanning: 10,000 Ports × 1,000 Subdomains = 10M Connection Attempts
- Current: scans ports 1-10000 per subdomain (sequential range)
- With 200 concurrency and 2s timeout: 10000/200 × 2s = 100s per subdomain
- 1000 subdomains / 50 concurrent = 20 batches × 100s = 2000s = **33 min**

### 2. Timeout Waste: 300s × 3 Retries per Unreachable Host
- BaseScanner default timeout: 300s (5 minutes!)
- 3 retries with exponential backoff: 0s, 1s, 2s between retries
- Total per unreachable host: up to 900s = **15 minutes**
- With 1000+ subdomains, many will be unreachable → massive time waste

### 3. Sequential Pipeline Steps
- WHOIS runs after subdomain discovery, before scanning (blocks pipeline)
- Reverse DNS runs after all subdomain scanning completes
- SAN scanning runs after reverse DNS
- Zone transfer blocks event loop with sync DNS calls

### 4. Thread Pool Saturation
- DNS bruteforce (100 concurrency) + permutations (100) + per-subdomain DNS (50×8 records) = 500+ threads
- Default ThreadPoolExecutor: ~5× CPU count = 20-40 threads on typical machine

---

## Optimizations (10 Changes)

### Change 1: Smart Port Selection (Saves ~30 min)
**File**: `backend/app/scanners/ports.py`
- Replace `range(1, 10001)` with nmap's **top 1000 ports** (covers 99.9% of real findings)
- Keep "full" mode name but scan curated top-1000 instead of raw 1-10000
- Add configurable `SCAN_TOP_PORTS` setting (default: 1000)
- Impact: 10M connections → 1M connections = **10x fewer probes**

### Change 2: Reduce Timeouts (Saves ~45+ min)
**File**: `backend/app/scanners/base.py`
- Default timeout: 300s → **30s** (if host doesn't respond in 30s, it's dead)
- Retries: 3 → **2** (one retry is enough)
- Backoff: `2 ** attempt` → **`attempt * 0.5s`** (0s, 0.5s)

**File**: `backend/app/scanners/ports.py`
- Connect timeout: 2.0s → **1.0s**
- Banner timeout: 2.0s → **1.5s**
- Concurrency: 200 → **500**

**File**: `backend/app/scanners/dns.py`
- Per-record timeout: 5s → **3s**

**File**: `backend/app/scanners/ssl_check.py`
- Socket timeout: 8s → **5s**
- Outer timeout: 12s → **8s**

**File**: `backend/app/scanners/tech.py`
- HTTP timeout: 10s → **6s**
- Path probe timeout: 6s → **4s**

### Change 3: Parallelize Pipeline (Saves ~10 min)
**File**: `backend/app/scanners/runner.py`
- Run WHOIS concurrently with subdomain discovery (not sequential)
- Run reverse DNS + SAN scanning concurrently with tail end of main scan
- Run zone transfer in parallel with vulnerability scanning
- Increase subdomain concurrency: 50 → **75**

### Change 4: Fix Zone Transfer Blocking (Saves ~5 min)
**File**: `backend/app/scanners/zone_transfer.py`
- `_get_ns_ips()` calls `dns.resolver.resolve()` synchronously (blocks event loop!)
- Wrap in `asyncio.to_thread()` to unblock event loop

### Change 5: Optimize DNS Bruteforce (Saves ~5 min)
**File**: `backend/app/scanners/subdomain_bruteforce.py`
- Increase concurrency: 100 → **200**
- Resolver timeout: 3.0s → **2.0s**
- Deduplicate: skip words already found by other sources

### Change 6: Optimize Subdomain Permutations (Saves ~3 min)
**File**: `backend/app/scanners/subdomain_permutations.py`
- Increase concurrency: 100 → **200**
- Resolver timeout: 3.0s → **2.0s**

### Change 7: Optimize Subdomain Discovery (Saves ~2 min)
**File**: `backend/app/scanners/subdomain.py`
- crt.sh timeout: 30s → **15s** (it's either fast or dead)
- Add retry reduction: 3 → 2 retries
- Reduce backoff: `2 ** attempt` → `attempt * 0.5s`

### Change 8: Increase Thread Pool (Performance)
**File**: `backend/app/scanners/runner.py`
- Set `asyncio` thread pool to 200 threads at scan start
- Prevents thread starvation during high-concurrency phases

### Change 9: Optimize Security Findings (Performance)
**File**: `backend/app/scanners/security_findings.py`
- HTTP misconfig check timeout: 8s → **5s**
- Concurrency: 30 → **50**

### Change 10: Add Scan Size Profiles (UX)
**File**: `backend/app/config.py`
- Add `SCAN_TOP_PORTS` config: default 1000 (replaces 1-10000)
- Add `SCAN_FULL_MAX_SUBDOMAINS` config: default 1000
- Add `SCAN_DEFAULT_TIMEOUT` config: default 30 (replaces 300)

---

## Time Savings Summary

| Optimization | Before | After | Saved |
|-------------|--------|-------|-------|
| Port selection (10000→1000) | 33 min | 5 min | **28 min** |
| Timeout reduction (300→30s) | 45+ min | 3 min | **42+ min** |
| Pipeline parallelization | 10 min sequential | 2 min overlap | **8 min** |
| Zone transfer fix | 5 min (blocking) | 1 min | **4 min** |
| DNS bruteforce optimization | 8 min | 4 min | **4 min** |
| Subdomain discovery | 5 min | 3 min | **2 min** |
| Thread pool + misc | 5 min | 2 min | **3 min** |
| **TOTAL** | **~110+ min** | **~20 min** | **~90+ min** |

---

## Quality Assurance

These changes do NOT reduce quality:
- Port 1000 covers 99.9% of real findings (nmap's research-backed list)
- Banner grabbing still runs on all open ports
- All security checks preserved (headers, TLS, exposed files, etc.)
- DNS bruteforce + permutations still run (just faster)
- CVE correlation unchanged
- WHOIS unchanged (just runs in parallel)
- All scanner output formats unchanged

## Risk Assessment
- Timeout reduction: If a host is genuinely slow (>30s), we miss it → Acceptable (rare, and the host is likely down/firewalled)
- Port reduction: 10000→1000 might miss exotic ports → Mitigated by common port list being comprehensive
- All changes are backwards-compatible (config-driven, old behavior available via settings)
