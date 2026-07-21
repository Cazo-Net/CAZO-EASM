# Deployment Guide

## Prerequisites

- Ubuntu 20.04+ or Debian 11+
- Python 3.11+
- Node.js 18+
- PostgreSQL 14+
- Nginx
- Nmap
- Go 1.21+ (for subfinder)

## Production Deployment

### 1. Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3.11 python3.11-venv python3-pip \
    nodejs npm postgresql postgresql-contrib nginx nmap

# Install Go
wget https://go.dev/dl/go1.21.0.linux-amd64.tar.gz
sudo tar -C /usr/local -xzf go1.21.0.linux-amd64.tar.gz
echo 'export PATH=$PATH:/usr/local/go/bin' >> ~/.bashrc
source ~/.bashrc

# Install subfinder
go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
```

### 2. Application Setup

```bash
# Create app directory
sudo mkdir -p /opt/easm
sudo chown $USER:$USER /opt/easm

# Clone repository
git clone <your-repo-url> /opt/easm
cd /opt/easm

# Setup backend
cd backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Setup database
sudo -u postgres createdb easm
sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'your-password';"
alembic upgrade head

# Setup frontend
cd ../frontend
npm install
npm run build
```

### 3. Nginx Configuration

```bash
# Copy nginx config
sudo cp nginx/easm.conf /etc/nginx/sites-available/easm
sudo ln -s /etc/nginx/sites-available/easm /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default

# Test and restart
sudo nginx -t
sudo systemctl restart nginx
```

### 4. Systemd Services

```bash
# Copy service files
sudo cp scripts/easm-backend.service /etc/systemd/system/

# Enable and start services
sudo systemctl enable easm-backend
sudo systemctl start easm-backend
```

### 5. SSL Certificate (Optional)

```bash
# Install certbot
sudo apt install -y certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d your-domain.com
```

## Docker Deployment (Alternative)

```bash
# Build and run
docker-compose up -d

# Run migrations
docker-compose exec backend alembic upgrade head

# Create admin user (idempotent; prompts if flags/env not set)
docker-compose exec backend python -m app.utils.create_admin \
    --email admin@your-domain.com --password 'change-this-strong-password'
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://postgres:postgres@localhost:5432/easm` |
| `JWT_SECRET_KEY` | Secret for JWT tokens | Required |
| `SECRET_KEY` | Application secret key | Required |
| `CORS_ORIGINS` | Allowed origins | `["http://localhost:3000"]` |

## Monitoring

- Health check: `GET /health`
- API docs: `GET /api/docs`
- Logs: `journalctl -u easm-backend -f`

## Backup

```bash
# Database backup
pg_dump easm > backup_$(date +%Y%m%d).sql

# Restore
psql easm < backup_20240101.sql
```
