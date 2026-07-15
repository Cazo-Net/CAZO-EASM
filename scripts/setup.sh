#!/bin/bash

# EASM Platform Setup Script
# Run this on a fresh Ubuntu/Debian server

set -e

echo "=== EASM Platform Setup ==="

# Update system
echo "Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install Python 3.11+
echo "Installing Python..."
sudo apt install -y python3.11 python3.11-venv python3-pip

# Install Node.js 18+
echo "Installing Node.js..."
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# Install PostgreSQL
echo "Installing PostgreSQL..."
sudo apt install -y postgresql postgresql-contrib

# Install Nginx
echo "Installing Nginx..."
sudo apt install -y nginx

# Install Nmap
echo "Installing Nmap..."
sudo apt install -y nmap

# Install Go (for subfinder)
echo "Installing Go..."
wget https://go.dev/dl/go1.21.0.linux-amd64.tar.gz
sudo tar -C /usr/local -xzf go1.21.0.linux-amd64.tar.gz
echo 'export PATH=$PATH:/usr/local/go/bin' >> ~/.bashrc
source ~/.bashrc

# Install subfinder
echo "Installing subfinder..."
go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest

# Create application directory
echo "Creating application directory..."
sudo mkdir -p /opt/easm
sudo chown $USER:$USER /opt/easm

# Clone repository (replace with your repo)
# git clone <your-repo-url> /opt/easm

echo "=== Setup Complete ==="
echo "Next steps:"
echo "1. Clone your repository to /opt/easm"
echo "2. Run: cd /opt/easm/backend && python3.11 -m venv venv"
echo "3. Run: source venv/bin/activate && pip install -r requirements.txt"
echo "4. Configure PostgreSQL database"
echo "5. Run: cp .env.example .env and edit"
echo "6. Run: alembic upgrade head"
echo "7. Run: cd /opt/easm/frontend && npm install && npm run build"
echo "8. Configure Nginx and systemd services"
