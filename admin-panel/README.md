# CAZO Admin Panel

Standalone administration console for the CAZO EASM platform. Runs on separate ports (9000/3001) from the main platform.

## Quick Start

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --host 0.0.0.0 --port 9000

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

- Admin UI: http://localhost:3001
- Admin API: http://localhost:9000

## Default Credentials

Sign in with a platform admin (superuser) account stored in the database.
Create it, or reset its password, from `backend/` (on Railway: `railway run`):

```bash
python -m app.utils.create_admin --email you@example.com
```

It prompts for the password (12+ characters). `ADMIN_PASSWORD` is no longer
needed; if you set `ADMIN_EMAIL`/`ADMIN_PASSWORD` (12+ characters) they only act
as a fallback login when no database superuser matches.

Also set a random `ADMIN_JWT_SECRET` so admin sessions survive restarts:
```bash
ADMIN_JWT_SECRET=your-jwt-secret
```

## Dashboard Tabs

| Tab | Description |
|-----|-------------|
| **Overview** | Platform stats, vulnerability breakdown, scan status, 12 system health metrics |
| **Users** | User list with search/role filter, click to open detail modal |
| **Organizations** | Org list with plan, status, user/scan/project counts |
| **Scans** | Scan list with status filter, progress bars, cancel running scans |
| **Vulnerabilities** | Vulnerability list with severity filter |
| **Assets** | Asset inventory with type/search filter, inventory status |
| **Sessions** | Active sessions with browser/OS/IP, revoke single or all |
| **Audit Log** | Audit event stream with action/actor/target tracking |
| **Notifications** | Notification list, mark read, broadcast to all users |
| **API Keys** | API key list with prefix display, revoke |
| **Feature Flags** | Feature flag cards with ON/OFF toggle, plan restrictions |
| **Database** | Table row counts sorted by size |
| **System** | 8 system metrics, top 30 processes by memory, configuration |

## User Management

Click any user row to open the detail modal with:

### Profile Editing
- Full name, email, role (member/admin/superuser)
- Save profile changes
- Enable/disable account
- Unlock locked accounts
- Revoke all sessions

### Password Reset
- Enter new password (min 8 characters)
- Auto-revokes all active sessions
- Increments token version (invalidates old JWTs)

### MFA Control
- Enforce or remove MFA requirement per user
- View TOTP enrollment status

### User Info
- User ID, organization, created date, last login
- Password changed date, token version
- Email verified status, lock status
- Session count, scan count, API key count

## Backend Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/login` | POST | Admin JWT login |
| `/auth/me` | GET | Current admin info |
| `/stats` | GET | Platform-wide statistics |
| `/health` | GET | System health metrics |
| `/users` | GET | List users (search, role, active filters) |
| `/users/{id}` | GET | User detail with counts |
| `/users/{id}/profile` | PUT | Update user profile |
| `/users/{id}/reset-password` | POST | Reset user password |
| `/users/{id}/mfa` | PUT | Toggle MFA enforcement |
| `/users/{id}/disable` | PUT | Disable user account |
| `/users/{id}/enable` | PUT | Enable user account |
| `/users/{id}/unlock` | PUT | Unlock user account |
| `/users/{id}/role` | PUT | Change user role |
| `/users/{id}/sessions` | DELETE | Revoke user sessions |
| `/users/{id}` | DELETE | Delete user |
| `/organizations` | GET | List organizations |
| `/organizations/{id}/toggle` | PUT | Toggle org active status |
| `/scans` | GET | List scans (status filter) |
| `/scans/{id}` | DELETE | Cancel scan |
| `/scan-history` | GET | Scan execution history |
| `/vulnerabilities` | GET | List vulnerabilities (severity filter) |
| `/assets` | GET | List assets (type/search filter) |
| `/sessions` | GET | List active sessions |
| `/sessions/{id}` | DELETE | Revoke session |
| `/sessions` | DELETE | Revoke all sessions |
| `/audit-events` | GET | List audit events |
| `/notifications` | GET | List notifications |
| `/notifications/{id}/read` | PUT | Mark notification read |
| `/notifications/mark-all-read` | PUT | Mark all as read |
| `/notifications/broadcast` | POST | Broadcast to all users |
| `/api-keys` | GET | List API keys |
| `/api-keys/{id}` | DELETE | Revoke API key |
| `/feature-flags` | GET | List feature flags |
| `/feature-flags/{id}/toggle` | PUT | Toggle feature flag |
| `/roles` | GET | List roles |
| `/invitations` | GET | List invitations |
| `/reports` | GET | List reports |
| `/auth-audit` | GET | Auth audit logs |
| `/system/processes` | GET | Running processes |
| `/database/stats` | GET | Table row counts |
| `/database/table/{name}` | GET | Table schema |

## Tech Stack

- **Backend**: FastAPI, SQLAlchemy, python-jose (JWT), bcrypt, psutil
- **Frontend**: Next.js 14, React 18, TypeScript, Tailwind CSS, Lucide icons, Axios
- **Database**: Connects to EASM platform database (SQLite or PostgreSQL)

## Architecture

The admin panel is a completely separate application from the EASM platform:

- Separate codebase in `admin-panel/`
- Separate backend on port 9000
- Separate frontend on port 3001
- Separate JWT secret and credentials
- Connects to the same EASM database (read/write)
- No dependency on the main platform's backend
