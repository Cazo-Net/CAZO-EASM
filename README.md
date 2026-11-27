# CAZO EASM Platform

External Attack Surface Management (EASM) platform for authorized security assessments. Discovery is gated by an authorized-scope registry, built on a pluggable scanner architecture with a normalized asset inventory, scoring, and change tracking.

## Architecture

```
easm-platform/
├── backend/          # FastAPI (port 8000) — 48+ models, 38+ API routers
│   └── app/
│       ├── services/blockchain/   # Blockchain Intelligence (consolidated)
│       │   ├── providers/         # ChainProvider ABC + ETH/BTC/TRON providers
│       │   ├── labels/            # Curated labels (13 entities)
│       │   ├── clustering/        # Address clustering heuristics
│       │   ├── graph/             # NetworkX graph analytics
│       │   ├── ml/                # IsolationForest anomaly scoring
│       │   ├── monitoring/        # Watch lists + alert dispatch
│       │   ├── copilot/           # NL query copilot
│       │   ├── cases/             # Case management
│       │   ├── security.py        # RBAC, rate limits, audit logs
│       │   ├── intel.py           # OFAC/Etherscan external intel
│       │   ├── bridges.py         # Cross-chain bridge tracking
│       │   ├── attribution.py     # Entity attribution service
│       │   └── risk.py            # Risk scoring engine
│       └── schemas/blockchain.py  # 30+ Pydantic models (single source of truth)
├── frontend/         # Next.js (port 3000) — user-facing dashboard
├── modules/
│   └── darkweb-intel/             # Dark Web Intelligence (domain models)
├── admin-panel/      # Standalone admin console (port 9000/3001)
│   ├── backend/      # FastAPI admin API (port 9000)
│   └── frontend/     # Next.js admin UI (port 3001)
└── docs/             # Architecture PDF, deployment guides
```

## Features

### EASM Platform (Backend + Frontend)
- **Authorized-Scope Registry** — Register domains, wildcards, IPs, and CIDRs you are cleared to test
- **Pluggable Discovery** — Subdomain, DNS, WHOIS, SSL, port, technology, and Nuclei scanners
- **Asset Inventory** — Normalized assets and relationships with health/exposure scoring
- **Change Timeline** — Detects new/removed subdomains, ports, certificates, and technologies
- **Vulnerability Management** — Severity tracking, assignment, evidence, audit trail
- **Intelligence Canvas** — Visual attack surface maps with nodes and edges
- **Shadow Asset Detection** — Unknown/suspected assets for review
- **OSINT Intelligence** — Cached OSINT data aggregation
- **Multi-tenant** — Organization, project, and role-based access
- **Scanner V2** — Multi-stage pipeline: Asset Discovery → DNS Intelligence → Network Intelligence → Technology Fingerprint → Certificate Analysis → Risk Evaluation → Graph Mapping. Supports partial success reporting, cloud bucket scanning, vendor-type tagging, and 15-risky-port alignment.
- **Blockchain Intelligence** — On-chain analytics for Ethereum (Etherscan API), Bitcoin (Blockstream API), and TRON (TronGrid API).
  - **Core**: Wallet summary, transaction history with pagination, contract detection, token balances
  - **Attribution**: 13 curated entity labels (exchanges, DeFi, stablecoins, sanctioned addresses)
  - **Risk Engine**: Multi-factor risk scoring with sanctions-aware escalation
  - **Clustering**: Common-input ownership, change-address detection, deployer-reuse, gas-payer heuristics
  - **Bridge Tracking**: 8 known bridge contracts, cross-chain hop tracing, aggregate volume stats
  - **Graph Analytics**: NetworkX-powered PageRank, betweenness centrality, Louvain community detection
  - **ML Anomaly Detection**: IsolationForest with 11 behavioral features and explainable outputs
  - **Monitoring**: Watch lists, alert dispatch (new tx, risk threshold, sanctions match)
  - **Copilot**: Natural language query → structured investigation
  - **Case Management**: Investigation cases, annotations, member assignments, audit trail
  - **External Intel**: OFAC SDN sanctions list, Etherscan labels, Chainalysis placeholder
  - **Enterprise Hardening**: Per-endpoint rate limiting, RBAC (admin/analyst/viewer), audit logging
  - **30+ API endpoints** covering all capabilities
- **Dark Web Intelligence** — Dark web monitoring framework with domain models for mentions, onion services, credential exposures, threat actors, and monitoring targets. Frontend search UI with threat-level badges, source icons, and fuzzy matching across 18+ threat categories.
- **Support Chat Widget** — Floating chat button (CAZO logo + green dot indicator) with real-time messaging between users and admins. User creates conversations, admin replies from admin panel Support tab. Polls for new messages every 10 seconds.
- **Collapsible Sidebar** — Sections (DISCOVERY, OUTPUT, RESOURCES, COLLABORATION) are collapsible with chevron toggle. Active pages auto-expand their section.
- **WebAuthn Passkeys** — Passwordless authentication support
- **REST API** — Full API with JWT + API key authentication

### Admin Panel (Standalone)
- **14 management tabs** — Overview, Users, Organizations, Scans, Vulnerabilities, Assets, Sessions, Audit Log, Notifications, API Keys, Feature Flags, Database, System, Blockchain, Support
- **User control** — Profile editing, password reset, role change, MFA enforcement, session revocation, account enable/disable/unlock
- **Organization management** — Plan, status, MFA enforcement, user/scan/project counts
- **Scan management** — Status monitoring, cancellation, scan history
- **Vulnerability tracking** — Severity filtering, status management
- **Asset inventory** — Type filtering, search, inventory status
- **Session management** — View/revoke active sessions with browser/OS/IP details
- **Audit trail** — Action/actor/target tracking with status
- **Notifications** — Read management, broadcast capability
- **API key management** — View/revoke API keys
- **Feature flags** — Toggle features by plan
- **System monitoring** — CPU, memory, disk, processes, network I/O, load average
- **Database inspection** — Table row counts, schema introspection
- **Blockchain** — Provider stats, OFAC sanctions, curated labels, watches, alerts, cases, travel rule, graph sync, search, compliance
- **Support** — View all user conversations, message thread, reply, mark read, update status

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 14 + React 18 + TypeScript + Tailwind CSS |
| Admin Frontend | Next.js 14 + React 18 + TypeScript + Tailwind CSS |
| Backend | FastAPI + Python 3.11+ |
| Admin Backend | FastAPI + Python 3.11+ |
| Database | PostgreSQL (SQLite for dev), PgBouncer (production) |
| ORM | SQLAlchemy 2.0 + Alembic |
| Auth | JWT + API Keys + WebAuthn Passkeys + TOTP MFA |
| Task Queue | Celery + Redis |
| Scanners | subfinder, dnspython, nmap, wappalyzer, nuclei, httpx |
| Blockchain | Etherscan API, Blockstream.info API, TronGrid API |
| Graph | NetworkX (in-memory), Neo4j (optional) |
| ML | scikit-learn (IsolationForest), pandas, numpy |
| PDF | fpdf2 |

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL (or SQLite for dev)
- Nmap
- Go (for subfinder)

### 1. Clone

```bash
git clone https://github.com/Cazo-Net/CAZO-EASM.git
cd CAZO-EASM
```

### 2. Backend (EASM Platform)

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your database URL and settings

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend (EASM Platform)

```bash
cd frontend
npm install
npm run dev
```

### 4. Admin Panel

```bash
# Backend
cd admin-panel/backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --host 0.0.0.0 --port 9000

# Frontend (new terminal)
cd admin-panel/frontend
npm install
npm run dev
```

### 5. Access

| Service | URL |
|---------|-----|
| EASM Frontend | http://localhost:3000 |
| EASM API Docs | http://localhost:8000/docs |
| Admin Panel | http://localhost:3001 |
| Admin API | http://localhost:9000 |

### Default Admin Credentials

Sign in with a platform admin (superuser) account stored in the database.
Create it, or reset its password, from `backend/` (on Railway: `railway run`):

```bash
python -m app.utils.create_admin --email you@example.com
```

It prompts for the password (12+ characters). `ADMIN_PASSWORD` is no longer
needed; if you set `ADMIN_EMAIL`/`ADMIN_PASSWORD` (12+ characters) they only act
as a fallback login when no database superuser matches.

## Production Deployment

```bash
# Docker Compose (recommended)
docker-compose up -d

# Services started:
# - PostgreSQL (port 5432) with PgBouncer (transaction mode, 1000 max connections)
# - Redis (port 6379)
# - Backend (port 8000)
# - Frontend (port 3000)
# - Celery worker + beat
```

### Database Production Settings (1M+ users)

- **Connection Pool**: 30 pool size, 50 overflow, pre-ping enabled
- **Statement Cache**: 1000 entries
- **Read Replica**: Supported via `DATABASE_READ_URL`
- **Partitioning**: Available via `DB_PARTITION_ENABLED`
- **Composite Indexes**: 50+ indexes across all tables

## API Reference

### EASM Platform API (`/api/v1/`)

| Prefix | Purpose |
|--------|---------|
| `/api/v1/auth` | Login, register, 2FA, password reset |
| `/api/v1/users` | User CRUD, profile |
| `/api/v1/scans` | Scan create/list/track |
| `/api/v1/assets` | Asset inventory, graph, scores, timeline |
| `/api/v1/vulnerabilities` | Vulnerability management |
| `/api/v1/reports` | Report generation/download |
| `/api/v1/organizations` | Org management |
| `/api/v1/projects` | Project CRUD |
| `/api/v1/api-keys` | API key management |
| `/api/v1/notifications` | Notification center |
| `/api/v1/sessions` | Session management |
| `/api/v1/scopes` | Authorized scope management |
| `/api/v1/admin` | Admin user management |
| `/api/v1/security` | Security center |
| `/api/v1/canvases` | Intelligence canvas |
| `/api/v1/findings` | Evidence center |
| `/api/v1/shadow-assets` | Shadow asset detection |
| `/api/v1/osint` | OSINT intelligence |
| `/api/v1/blockchain` | Blockchain intelligence (30+ endpoints) |
| `/api/v1/support` | Support chat (conversations, messages, unread) |

#### Blockchain Intelligence Endpoints

| Endpoint | Purpose |
|----------|---------|
| **Core** | |
| `GET /chains` | List supported blockchains |
| `GET /wallet/{address}` | Wallet summary + attribution + risk score |
| `GET /wallet/{address}/transactions` | Paginated transaction history |
| `GET /transaction/{tx_hash}` | Transaction detail |
| `GET /contract/{address}` | Contract details |
| `GET /wallet/{address}/tokens` | Token balances |
| `GET /wallet/{address}/risk` | Detailed risk assessment |
| `GET /wallet/{address}/attribution` | Entity attribution |
| `GET /search` | Search addresses, entities, contracts |
| **Phase 2: Analytics** | |
| `GET /wallet/{address}/cluster` | Clustering heuristics (common-input, deployer-reuse, etc.) |
| `GET /wallet/{address}/bridges` | Bridge interaction detection |
| `GET /wallet/{address}/bridge-volume` | Aggregate bridge volume |
| `GET /bridges/known` | List known bridge contracts |
| `GET /wallet/{address}/graph` | Graph analytics (PageRank, communities, centrality) |
| `GET /wallet/{address}/anomaly` | ML anomaly score with explainability |
| `GET /wallet/{address}/intel` | External intel (OFAC, Etherscan labels) |
| `GET /wallet/{address}/sanctions` | OFAC sanctions check |
| **Phase 2: Monitoring** | |
| `POST /watches` | Create address watch |
| `GET /watches` | List watches |
| `DELETE /watches/{id}` | Delete watch |
| `GET /alerts` | List alerts |
| `POST /alerts/{id}/acknowledge` | Acknowledge alert |
| `GET /alerts/stats` | Alert statistics |
| **Phase 2: Investigation** | |
| `POST /copilot/ask` | Natural language investigation query |
| `POST /cases` | Create investigation case |
| `GET /cases` | List cases |
| `GET /cases/{id}` | Get case with annotations, members, audit |
| `PUT /cases/{id}` | Update case |
| `POST /cases/{id}/annotations` | Add annotation |
| `POST /cases/{id}/members` | Add team member |
| `GET /cases/stats` | Case statistics |

#### Support Chat Endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /support/conversations` | Create new conversation with initial message |
| `GET /support/conversations` | List current user's conversations |
| `GET /support/conversations/{id}/messages` | Get messages (marks admin messages as read) |
| `POST /support/conversations/{id}/messages` | Send message in conversation |
| `GET /support/unread` | Get total unread admin messages |

### Admin Panel API (port 9000)

| Endpoint | Purpose |
|----------|---------|
| `POST /auth/login` | Admin login |
| `GET /stats` | Platform-wide statistics |
| `GET /health` | System health (CPU, memory, disk, processes) |
| `GET/PUT /users` | User list, profile edit, password reset, MFA control |
| `GET/PUT /organizations` | Org list, toggle active |
| `GET/DELETE /scans` | Scan list, cancel |
| `GET /vulnerabilities` | Vulnerability list (severity filter) |
| `GET /assets` | Asset inventory (type/search filter) |
| `GET/DELETE /sessions` | Session list, revoke |
| `GET /audit-events` | Audit event stream |
| `GET /notifications` | Notification list, mark read |
| `GET /api-keys` | API key list, revoke |
| `GET /feature-flags` | Feature flag list, toggle |
| `GET /roles` | Role list |
| `GET /scan-history` | Scan execution history |
| `GET /system/processes` | Running processes |
| `GET /database/stats` | Table row counts |
| `GET /database/table/{name}` | Schema introspection |
| `GET /blockchain/stats` | Blockchain stats |
| `GET /blockchain/providers` | Blockchain providers |
| `GET /blockchain/ofac` | OFAC sanctions list |
| `GET /blockchain/labels` | Curated labels |
| `GET /blockchain/watches` | Watch lists |
| `GET /blockchain/alerts` | Alerts |
| `GET /blockchain/cases` | Cases |
| `GET /blockchain/travel-rule` | Travel rule records |
| `GET /support/conversations` | List all support conversations |
| `GET /support/conversations/{id}/messages` | Get conversation messages |
| `POST /support/conversations/{id}/messages` | Reply to conversation |
| `PUT /support/conversations/{id}/status` | Update conversation status |
| `GET /support/unread` | Total unread user messages |

## Database Schema (52 tables)

| Category | Tables |
|----------|--------|
| **Core** | users, organizations, projects, roles |
| **Scanning** | scans, scan_jobs, scan_history, monitor_schedules |
| **Assets** | subdomains, ports, dns_records, ssl_certificates, whois_records, technologies |
| **Vulnerabilities** | vulnerabilities, finding_history, finding_evidence |
| **Inventory** | assets, asset_relationships, asset_scores, asset_changes, asset_lifecycle, asset_comments |
| **Auth** | user_sessions, trusted_devices, recovery_codes, auth_audit_logs, passkeys, api_keys |
| **Notifications** | notifications, notification_preferences, notification_email_log, notification_triggers |
| **Intelligence** | risk_scores, reports, canvases, canvas_nodes, canvas_edges, osint_cache |
| **Governance** | authorized_scopes, audit_logs, audit_events, tags, asset_tags, favorites, feature_flags, invitations |
| **Support** | support_conversations, support_messages |

## License

MIT
