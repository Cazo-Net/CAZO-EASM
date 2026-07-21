# CAZO EASM API Documentation

> External Attack Surface Management (EASM) platform for authorized security
> assessments. All discovery is gated by an authorized-scope registry so that
> only in-scope targets can be scanned.

## Base URL

```
http://localhost:8000/api/v1
```

## Authentication

### JWT Token

Include in request header:
```
Authorization: Bearer <token>
```

### API Key

Include in request header:
```
X-API-Key: easm_<your-api-key>
```

## Endpoints

### Authentication

#### Register
```http
POST /auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword",
  "full_name": "John Doe"
}
```

**Response:**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "John Doe",
  "role": "member",
  "created_at": "2024-01-01T00:00:00Z"
}
```

#### Login
```http
POST /auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword"
}
```

**Response:**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

### Scans

#### Create Scan
```http
POST /scans/
Authorization: Bearer <token>
Content-Type: application/json

{
  "domain": "example.com",
  "scan_type": "full"
}
```

**Response:**
```json
{
  "id": "uuid",
  "domain": "example.com",
  "status": "pending",
  "progress": 0,
  "scan_type": "full",
  "created_at": "2024-01-01T00:00:00Z"
}
```

#### List Scans
```http
GET /scans/?skip=0&limit=20
Authorization: Bearer <token>
```

**Response:**
```json
[
  {
    "id": "uuid",
    "domain": "example.com",
    "status": "completed",
    "progress": 100,
    "scan_type": "full",
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

#### Get Scan Details
```http
GET /scans/{scan_id}
Authorization: Bearer <token>
```

**Response:**
```json
{
  "id": "uuid",
  "domain": "example.com",
  "status": "completed",
  "progress": 100,
  "scan_type": "full",
  "subdomains_count": 45,
  "risk_score": 65,
  "created_at": "2024-01-01T00:00:00Z",
  "completed_at": "2024-01-01T00:05:00Z"
}
```

### Assets

#### List Subdomains
```http
GET /assets/subdomains?scan_id={scan_id}
Authorization: Bearer <token>
```

**Response:**
```json
[
  {
    "id": "uuid",
    "hostname": "api.example.com",
    "ip_addresses": ["1.2.3.4"],
    "is_alive": true,
    "discovered_at": "2024-01-01T00:01:00Z"
  }
]
```

#### List Ports
```http
GET /assets/ports?scan_id={scan_id}
Authorization: Bearer <token>
```

**Response:**
```json
[
  {
    "id": "uuid",
    "hostname": "api.example.com",
    "port_number": 443,
    "state": "open",
    "service": "https",
    "version": "nginx"
  }
]
```

### Reports

#### Generate Report
```http
POST /reports/?scan_id={scan_id}&format=pdf
Authorization: Bearer <token>
```

**Response:**
```json
{
  "id": "uuid",
  "scan_id": "uuid",
  "format": "pdf",
  "status": "generated",
  "download_url": "/api/v1/reports/{report_id}/download"
}
```

## Authorized Scopes

Discovery is gated by an organization's registered scopes. Only `domain`,
`wildcard`, `ip`, and `cidr` entries may be added, and values are validated on
write. Creating or removing a scope requires the `manage_org` permission and is
audited.

#### List Scopes
```http
GET /scopes
Authorization: Bearer <token>
```
**Response:**
```json
[
  {
    "id": "uuid",
    "organization_id": "uuid",
    "scope_type": "domain",
    "value": "example.com",
    "verified": false,
    "note": "Production perimeter",
    "added_by": "uuid",
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

#### Create Scope
```http
POST /scopes
Authorization: Bearer <token>
Content-Type: application/json

{
  "scope_type": "wildcard",
  "value": "*.example.com",
  "note": "Subdomains of example.com"
}
```
**Response:** `201 Created` with the created scope object. Returns `422` if the
value is invalid for the chosen `scope_type`.

#### Delete Scope
```http
DELETE /scopes/{scope_id}
Authorization: Bearer <token>
```
**Response:** `204 No Content`.

#### Check Authorization
```http
POST /scopes/check
Authorization: Bearer <token>
Content-Type: application/json

{ "scope_type": "domain", "value": "api.example.com" }
```
**Response:**
```json
{
  "target": "api.example.com",
  "authorized": true,
  "reason": "matched wildcard *.example.com",
  "matched_scope_id": "uuid"
}
```

### Discovery

#### List Discovery Plugins
```http
GET /scans/discovery/plugins
Authorization: Bearer <token>
```
Returns the registered, pluggable discovery scanners (subdomain,
subdomain-bruteforce, subdomain-permutations, dns, whois, ssl, ports,
technology, security-findings, cve-correlation) with category and capabilities.
All scanners are pure application code (no external CLI binaries).
**Response:**
```json
{
  "plugins": [
    {
      "name": "subdomain",
      "category": "subdomain",
      "capabilities": ["discover_subdomains"],
      "description": "Subdomain enumeration"
    }
  ]
}
```

### Asset Inventory

#### List Inventory
```http
GET /assets/inventory?scan_id={scan_id}&asset_type={type}
Authorization: Bearer <token>
```
**Response:**
```json
{
  "assets": [
    {
      "id": "uuid",
      "asset_type": "subdomain",
      "key": "api.example.com",
      "label": "api.example.com",
      "first_seen": "2024-01-01T00:00:00Z",
      "last_seen": "2024-01-02T00:00:00Z",
      "metadata": {}
    }
  ],
  "relationships": [
    {
      "id": "uuid",
      "source_key": "example.com",
      "target_key": "api.example.com",
      "relationship_type": "subdomain_of"
    }
  ]
}
```

#### Asset Graph
```http
GET /assets/inventory/graph?scan_id={scan_id}
Authorization: Bearer <token>
```
Returns nodes and edges suitable for graph visualization.

### Asset Scores

#### Recompute Scores
```http
POST /assets/scores/recompute
Authorization: Bearer <token>
```
Recomputes health and exposure scores for all assets in the organization.

#### List Scores
```http
GET /assets/scores?asset_type={type}&limit=50
Authorization: Bearer <token>
```
**Response:**
```json
{
  "scores": [
    {
      "asset_key": "api.example.com",
      "asset_type": "subdomain",
      "health_score": 82,
      "exposure_score": 64,
      "computed_at": "2024-01-02T00:00:00Z"
    }
  ]
}
```

### Change Timeline

#### Asset Timeline
```http
GET /assets/timeline?asset_key={key}&limit=50
Authorization: Bearer <token>
```
Returns a chronological list of detected changes (new/removed subdomains, ports,
certificates, technologies) for an asset or the whole organization.
**Response:**
```json
{
  "changes": [
    {
      "id": "uuid",
      "change_type": "subdomain_added",
      "asset_key": "api.example.com",
      "detail": { "is_alive": true },
      "detected_at": "2024-01-02T00:05:00Z"
    }
  ]
}
```

### Audit Events

#### List Audit Events
```http
GET /audit/events?action={action}&limit=50
Authorization: Bearer <token>
```
**Response:**
```json
{
  "events": [
    {
      "id": "uuid",
      "action": "scope.create",
      "actor_id": "uuid",
      "target_type": "scope",
      "target_id": "uuid",
      "detail": { "value": "example.com" },
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

## Error Responses

```json
{
  "detail": "Error message"
}
```

Common HTTP codes:
- `400` - Bad request
- `401` - Unauthorized
- `403` - Forbidden (also returned when a scan target is outside authorized scope)
- `404` - Not found
- `422` - Validation error (e.g. invalid scope value)
- `429` - Rate limit exceeded
