# CAZO EASM

External Attack Surface Management (EASM) platform for authorized security
assessments. Discovery is gated by an authorized-scope registry, built on a
pluggable scanner architecture with a normalized asset inventory, scoring, and
change tracking.

## Features

- **Authorized-Scope Registry** - Register domains, wildcards, IPs, and CIDRs you are cleared to test; out-of-scope targets are blocked from discovery
- **Pluggable Discovery** - Subdomain, DNS, WHOIS, SSL, port, technology, and Nuclei scanners registered via a discovery registry
- **Asset Inventory** - Normalized assets and relationships (e.g. `subdomain_of`) derived from scans
- **Health & Exposure Scoring** - Per-asset health and exposure scores
- **Change Timeline** - Detects new/removed subdomains, ports, certificates, and technologies between scans
- **Audit Logging** - Privileged actions are recorded for accountability
- **Subdomain Discovery** - Using subfinder
- **DNS Analysis** - Using dnspython
- **SSL/TLS Analysis** - Certificate validation and grading
- **Port Scanning** - Using nmap
- **Technology Detection** - Using Wappalyzer
- **WHOIS Lookups** - Domain registration info
- **Risk Scoring** - Automated risk assessment
- **Multi-tenant** - Organization and workspace support
- **REST API** - Full API access with authentication
- **Web Dashboard** - Modern Next.js frontend with command palette (`Cmd/Ctrl + K`)

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 14 + React + TypeScript + Tailwind CSS |
| Backend | FastAPI + Python 3.11+ |
| Database | PostgreSQL (SQLite for dev) |
| ORM | SQLAlchemy + Alembic |
| Auth | JWT + API Keys |
| Proxy | Nginx |

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL
- Nmap
- Go (for subfinder)

### Installation

1. Clone the repository:
```bash
git clone <your-repo-url>
cd easm-platform
```

2. Setup backend:
```bash
cd backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your settings
```

3. Setup database:
```bash
# PostgreSQL
sudo -u postgres createdb easm
sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'your-password';"

# Run migrations
alembic upgrade head
```

4. Setup frontend:
```bash
cd ../frontend
npm install
npm run dev
```

5. Install security tools:
```bash
# Install subfinder
go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest

# Nmap (Ubuntu/Debian)
sudo apt install nmap
```

6. Start the application:
```bash
# Backend
cd ../backend
uvicorn app.main:app --reload --port 8000

# Frontend (new terminal)
cd ../frontend
npm run dev
```

7. Access the application:
- Frontend: http://localhost:3000
- API Docs: http://localhost:8000/api/docs

## API Endpoints

### Authentication
- `POST /api/v1/auth/register` - Create account
- `POST /api/v1/auth/login` - Login
- `GET /api/v1/auth/me` - Get current user

### Scans
- `POST /api/v1/scans/` - Create new scan
- `GET /api/v1/scans/` - List scans
- `GET /api/v1/scans/{id}` - Get scan details
- `DELETE /api/v1/scans/{id}` - Delete scan

### Assets
- `GET /api/v1/assets/subdomains` - List subdomains
- `GET /api/v1/assets/ports` - List ports
- `GET /api/v1/assets/ssl` - List SSL certificates
- `GET /api/v1/assets/technologies` - List technologies
- `GET /api/v1/assets/inventory` - Asset inventory + relationships
- `GET /api/v1/assets/inventory/graph` - Asset graph
- `GET /api/v1/assets/scores` - Asset health/exposure scores
- `POST /api/v1/assets/scores/recompute` - Recompute scores
- `GET /api/v1/assets/timeline` - Change timeline

### Authorized Scopes
- `GET /api/v1/scopes` - List authorized scopes
- `POST /api/v1/scopes` - Add authorized scope
- `DELETE /api/v1/scopes/{id}` - Remove authorized scope
- `POST /api/v1/scopes/check` - Check if a target is authorized

### Discovery
- `GET /api/v1/scans/discovery/plugins` - List discovery plugins

### Audit
- `GET /api/v1/audit/events` - List audit events

### Reports
- `POST /api/v1/reports/` - Generate report
- `GET /api/v1/reports/` - List reports
- `GET /api/v1/reports/{id}/download` - Download report

## Deployment

See [docs/deployment.md](docs/deployment.md) for production deployment instructions.

## License

MIT
