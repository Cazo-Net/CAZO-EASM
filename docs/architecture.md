# EASM Platform Architecture

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
     │              Celery            PostgreSQL
     │
 ┌───┴──────────────────────────────────────────┐
 │                                              │
 │ Subdomain Module     → subfinder             │
 │ DNS Module           → dnspython             │
 │ WHOIS Module         → python-whois          │
 │ SSL Module           → ssl + socket          │
 │ Port Scan Module     → python-nmap           │
 │ Technology Module    → Wappalyzer            │
 └──────────────────────────────────────────────┘
```

## Components

### Frontend (Next.js)
- Dashboard with scan overview
- Scan creation form
- Real-time progress display
- Results visualization (tables, charts, graphs)
- Asset inventory management

### Backend (FastAPI)
- REST API endpoints
- JWT authentication
- Scan orchestration
- Scanner modules
- Risk scoring engine

### Database (PostgreSQL)
- User management
- Scan results storage
- Asset inventory
- Audit logging

### Scanner Modules
- **Subdomain Scanner**: Discovers subdomains using subfinder
- **DNS Scanner**: Resolves DNS records using dnspython
- **WHOIS Scanner**: Retrieves domain registration info
- **SSL Scanner**: Analyzes SSL/TLS certificates
- **Port Scanner**: Scans for open ports using nmap
- **Technology Scanner**: Detects technologies using Wappalyzer

## Data Flow

1. User submits domain via dashboard
2. Backend creates scan job
3. Subdomain scanner discovers subdomains
4. For each subdomain, parallel scans run:
   - DNS resolution
   - SSL certificate analysis
   - Port scanning
   - Technology detection
5. WHOIS lookup on main domain
6. Risk score calculated
7. Results stored in database
8. Dashboard updates with live progress

## Security

- JWT-based authentication
- API key support for programmatic access
- RBAC (admin/member/viewer roles)
- Rate limiting
- CORS configuration
- Input validation
