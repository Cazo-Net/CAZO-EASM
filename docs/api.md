# API Documentation

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

## Error Responses

```json
{
  "detail": "Error message"
}
```

Common HTTP codes:
- `400` - Bad request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not found
- `429` - Rate limit exceeded
