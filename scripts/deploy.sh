#!/bin/bash

# EASM Platform Deployment Script (bare-metal / systemd)

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/easm}"
BACKEND_DIR="$APP_DIR/backend"
FRONTEND_DIR="$APP_DIR/frontend"

echo "=== Deploying EASM Platform ==="

cd "$APP_DIR"

echo "Pulling latest changes..."
git pull origin main

echo "Setting up backend..."
cd "$BACKEND_DIR"
# shellcheck disable=SC1091
source venv/bin/activate
pip install -r requirements.txt

echo "Running database migrations..."
alembic upgrade head

echo "Building frontend..."
cd "$FRONTEND_DIR"
npm ci
BACKEND_URL="http://127.0.0.1:8000" npm run build
# copy static + public into standalone output so the node server can serve them
cp -r .next/static .next/standalone/.next/static
cp -r public .next/standalone/public 2>/dev/null || true

echo "Restarting services..."
sudo systemctl restart easm-backend
sudo systemctl restart easm-worker
sudo systemctl restart easm-frontend
sudo systemctl reload nginx

echo "=== Deployment Complete ==="
