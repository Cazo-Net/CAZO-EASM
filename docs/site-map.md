# CAZO EASM site map and page test results

Tested 2026-11-28 on the redesign branch (PR #5).

## How it was tested

Every page was opened in Chromium at desktop (1440 px) and phone (390 px)
width against the real backend running locally on SQLite, with a real
sign-up, onboarding and sign-in. A page passes when it loads with no script
error, no error page, no failed API call, no blank screen and no sideways
scroll.

What this does not cover: pages were tested on a new, empty account, so
tables full of real scan data were only checked earlier against sample data.
No scan was run, because a scan probes a real domain. Payments, email links,
Google sign-in and MFA were not exercised end to end.

## Result

42 page types, 84 loads, all passing after the fixes below. Another 35
static pages (13 docs articles, 3 more legal pages, 17 error-code pages
under `/errors/*` and 16 status pages under `/status/*`) also load cleanly.

## Pages

### Public pages (signed out)

| Page | What it is for | Desktop | Phone |
| --- | --- | --- | --- |
| `/` | Landing page | pass | pass |
| `/pricing` | Plans and prices | pass | pass |
| `/login` | Sign in | pass | pass |
| `/register` | Create account | pass | pass |
| `/forgot-password` | Request a password reset | pass | pass |
| `/auth/reset-password` | Set a new password (from email link) | pass | pass |
| `/auth/verify-email` | Confirm email (from email link) | pass | pass |
| `/docs` | Documentation home, plus 13 articles | pass | pass |
| `/legal/terms` | Terms; also privacy, acceptable use, authorized scanning | pass | pass |

### Setup

| Page | What it is for | Desktop | Phone |
| --- | --- | --- | --- |
| `/onboarding` | Welcome, create organization, first scope, MFA | pass | pass |
| `/onboarding/first-scan` | Runs the first scan | pass | pass |
| `/onboarding/first-scan/summary` | First scan results | pass | pass |

### Overview

| Page | What it is for | Desktop | Phone |
| --- | --- | --- | --- |
| `/dashboard` | Totals, findings by severity, inventory, activity, recent scans | pass | pass |
| `/change-feed` | What changed between scans | pass | pass |

### Attack surface

| Page | What it is for | Desktop | Phone |
| --- | --- | --- | --- |
| `/assets` | Hosts and subdomains | pass | pass |
| `/shadow-assets` | Assets that look like yours but are unconfirmed | pass | pass |
| `/assets/360` | Per-asset full view (list) | pass | pass |
| `/graph` | Attack graph | pass | pass |
| `/dns` | DNS records | pass | pass |
| `/whois` | WHOIS records | pass | pass |

### Risk

| Page | What it is for | Desktop | Phone |
| --- | --- | --- | --- |
| `/vulnerabilities` | Findings, filter by severity and scan | pass | pass |
| `/supply-chain` | Third-party vendors seen on your assets | pass | pass |

### Operations

| Page | What it is for | Desktop | Phone |
| --- | --- | --- | --- |
| `/scans` | All scans | pass | pass |
| `/scan/new` | Start a scan | pass | pass |
| `/scanner-v2` | Live scan pipeline view | pass | pass |
| `/scopes` | Authorized scopes and domain verification | pass | pass |

### Intelligence

| Page | What it is for | Desktop | Phone |
| --- | --- | --- | --- |
| `/intel` | OSINT lookups | pass | pass |
| `/darkweb` | Dark web search | pass | pass |
| `/blockchain` | Wallet lookup | pass | pass |

### Reporting

| Page | What it is for | Desktop | Phone |
| --- | --- | --- | --- |
| `/reports` | Generated reports | pass | pass |
| `/reports/executive` | Executive summary | pass | pass |
| `/compare` | Compare two scans | pass | pass |
| `/canvas` | Investigation canvas | pass | pass |
| `/replay` | Exposure timeline | pass | pass |

### Account and team

| Page | What it is for | Desktop | Phone |
| --- | --- | --- | --- |
| `/settings` | Profile, security, API keys, webhooks, notifications | pass | pass |
| `/settings/organization` | Organization profile and members | pass | pass |
| `/security-center` | Sessions, devices, login history | pass | pass |
| `/billing` | Plan, usage, invoices, payment methods | pass | pass |
| `/billing/checkout` | Choose plan and pay | pass | pass |
| `/billing/success` | After payment | pass | pass |
| `/collab-demo` | Comments on assets | pass | pass |
| `/search` | Global search | pass | pass |

### Detail pages

| Page | What it is for | Checked |
| --- | --- | --- |
| `/scan/[id]` | Scan results: risk, findings, subdomains, ports, TLS | Unknown id shows "Scan not found" with a way back |
| `/assets/[id]` | Asset 360 view | Unknown id shows "Asset not found" with a way back |
| `/blockchain/[address]` | Wallet analysis | Loads; scrolls sideways by about 50 px on phones |
| any unknown address | 404 page | Shows the not-found page with links |

## Flows walked through in the browser

1. Sign up at `/register`, which lands on `/onboarding`.
2. Onboarding: welcome, then create an organization. Stopped at "add your
   first scope", because the next step starts a real scan.
3. Sign in at `/login` with "Remember me" on, which lands on `/dashboard`.
4. Opening any app page while signed out sends you to `/login`.

## Problems found and fixed in this PR

| Problem | Effect | Fix |
| --- | --- | --- |
| `/api/v1/reports/executive` was captured by `/reports/{report_id}` | The executive report page always showed "not found" | Register the executive router first (`backend/app/main.py`) |
| Blockchain and dark web pages called the API with no sign-in token | Every request was refused with 401, so those pages never showed data | New `authFetch` helper in `frontend/src/lib/api.ts`, used by the three callers |
| `packaging` missing from `backend/requirements.txt` | A clean install could not start the API | Added |
| 7 app pages were not behind the sign-in check | Signed out, `/security-center` rendered blank and others showed empty shells | Wrapped in `ProtectedRoute` |
| Sidebar showed the organization's raw ID | Looked broken | Shows the organization name |
| Onboarding rendered inside the full app sidebar | New users saw the whole menu before setup | Onboarding runs without the app shell |
| Scans, findings, scanner and onboarding scrolled sideways on phones | Controls were cut off | Toolbars wrap |
| Shadow assets, executive report and organization settings crashed when a list was missing from a response | Error page | Fall back to empty |
| Logo link nested inside another link in docs and legal headers | Hydration error on `/docs` | Removed the outer link |

## Open observations, not changed

- **Sign-in is per tab unless "Remember me" is ticked.** Without it, opening
  an app link in a new tab asks you to sign in again. This is how the token
  storage was built, but most users will read it as being logged out.
- **A new account has no organization until onboarding creates one.** If a
  user skips onboarding, scopes, shadow assets, replay and billing answer
  "create an organization first". Billing says so clearly; the other pages
  show a generic error.
- **Wallet analysis shows figures for any address without a provider key.**
  The all-zero address returned a balance and transaction history, which
  looks like sample data. It should be labelled as such or hidden until a
  provider is configured.
- The wallet page scrolls sideways slightly on phones.
