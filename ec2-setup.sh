#!/usr/bin/env bash
# EC2 setup script for HelpingHands backend.
# Run once on a fresh Ubuntu 22.04 t3.small instance as the ubuntu user.
# Usage: bash ec2-setup.sh

set -euo pipefail

echo "==> Updating packages"
sudo apt-get update -y && sudo apt-get upgrade -y

echo "==> Installing Docker"
sudo apt-get install -y ca-certificates curl gnupg lsb-release
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update -y
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo usermod -aG docker ubuntu
echo "Docker installed. You may need to log out and back in for group membership to take effect."

echo "==> Installing nginx"
sudo apt-get install -y nginx

echo "==> Installing certbot"
sudo apt-get install -y certbot python3-certbot-nginx

echo "==> Creating app directory"
sudo mkdir -p /opt/helpinghands/backend
sudo chown ubuntu:ubuntu /opt/helpinghands/backend

echo ""
echo "=== Setup complete. Next steps ==="
echo ""
echo "1. Copy your backend files to /opt/helpinghands/backend/"
echo "   scp -r donation-backend/ ubuntu@<EC2_IP>:/opt/helpinghands/backend/"
echo ""
echo "2. Create /opt/helpinghands/backend/.env with production values"
echo "   (copy .env.example and fill in real values)"
echo ""
echo "3. Get SSL cert:"
echo "   sudo certbot --nginx -d api.yourdomain.com"
echo ""
echo "4. Copy nginx config:"
echo "   sudo cp /opt/helpinghands/backend/nginx.conf.template /etc/nginx/sites-available/helpinghands-api"
echo "   Edit it: replace YOUR_DOMAIN with api.yourdomain.com"
echo "   sudo ln -s /etc/nginx/sites-available/helpinghands-api /etc/nginx/sites-enabled/"
echo "   sudo nginx -t && sudo systemctl reload nginx"
echo ""
echo "5. Start the backend:"
echo "   cd /opt/helpinghands/backend"
echo "   docker compose -f docker-compose.prod.yml --env-file .env up -d"
echo ""
echo "6. Run database migrations:"
echo "   docker exec donations-backend poetry run alembic upgrade head"
echo ""
echo "7. Verify:"
echo "   curl https://api.yourdomain.com/health"
