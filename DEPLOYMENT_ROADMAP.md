# 🚀 WalletTrack Production Deployment Roadmap

## 📋 Mevcut Durum
- ✅ GitHub'da güncel kod
- ✅ Geliştirme ortamında test edilmiş
- ✅ TronGrid API entegrasyonu çalışıyor
- ✅ Monitor performansı optimize edildi

## 🎯 Deployment Stratejisi

### 1. Immediate Deployment (Hızlı Çözüm)
**Süre: 5-10 dakika**

```bash
# Production sunucusunda:
cd /path/to/wallettrack
git pull origin main
sudo systemctl restart wallettrack
sudo systemctl status wallettrack
```

### 2. Automated CI/CD Pipeline (Önerilen)
**Süre: 30-45 dakika kurulum**

#### A. GitHub Actions Workflow
```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v3
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    
    - name: Run tests
      run: |
        python -m pytest tests/
    
    - name: Deploy to Production
      if: github.ref == 'refs/heads/main'
      run: |
        # SSH to production server and deploy
        ssh ${{ secrets.PROD_SERVER }} 'cd /path/to/wallettrack && git pull origin main && sudo systemctl restart wallettrack'
```

#### B. Docker Container Deployment
```dockerfile
# Dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "main.py"]
```

```yaml
# docker-compose.yml
version: '3.8'
services:
  wallettrack:
    build: .
    ports:
      - "8000:8000"
    environment:
      - TRONGRID_API_KEY=${TRONGRID_API_KEY}
      - ETHERSCAN_API_KEY=${ETHERSCAN_API_KEY}
    volumes:
      - ./wallettrack.db:/app/wallettrack.db
      - ./.env:/app/.env
    restart: unless-stopped
```

### 3. Zero-Downtime Deployment
**Süre: 1-2 saat kurulum**

#### A. Blue-Green Deployment
```bash
# Production sunucusunda:
# 1. Yeni version'ı port 8001'de başlat
cd /path/to/wallettrack-new
git pull origin main
PORT=8001 python main.py &

# 2. Health check
curl http://localhost:8001/api/system/health

# 3. Load balancer'da trafiği yönlendir
sudo nginx -s reload

# 4. Eski version'ı durdur
sudo systemctl stop wallettrack
```

#### B. Rolling Update with PM2
```json
// ecosystem.config.js
module.exports = {
  apps: [{
    name: 'wallettrack',
    script: 'python',
    args: 'main.py',
    instances: 2,
    exec_mode: 'cluster',
    env: {
      PORT: 8000
    }
  }]
};
```

```bash
# Deployment
pm2 reload ecosystem.config.js
```

## 🔧 Deployment Araçları

### 1. Basit Deployment Script
```bash
#!/bin/bash
# deploy.sh

echo "🚀 Starting WalletTrack Deployment..."

# Backup current version
cp -r /path/to/wallettrack /path/to/wallettrack-backup-$(date +%Y%m%d_%H%M%S)

# Pull latest changes
cd /path/to/wallettrack
git pull origin main

# Install/update dependencies
pip install -r requirements.txt

# Run database migrations (if any)
python -c "from database import init_db; init_db()"

# Restart service
sudo systemctl restart wallettrack

# Health check
sleep 5
curl -f http://localhost:8000/api/system/health || {
  echo "❌ Health check failed! Rolling back..."
  sudo systemctl stop wallettrack
  # Restore backup
  exit 1
}

echo "✅ Deployment completed successfully!"
```

### 2. Ansible Playbook
```yaml
# deploy.yml
---
- name: Deploy WalletTrack
  hosts: production
  become: yes
  
  tasks:
    - name: Pull latest code
      git:
        repo: https://github.com/halitcanbaba/wallettrack.git
        dest: /opt/wallettrack
        version: main
    
    - name: Install dependencies
      pip:
        requirements: /opt/wallettrack/requirements.txt
    
    - name: Restart service
      systemd:
        name: wallettrack
        state: restarted
    
    - name: Health check
      uri:
        url: http://localhost:8000/api/system/health
        method: GET
      register: health_check
      retries: 5
      delay: 10
```

### 3. Production Environment Setup
```bash
# production-setup.sh
#!/bin/bash

echo "🔧 Setting up production environment..."

# Install system dependencies
sudo apt update
sudo apt install -y python3 python3-pip nginx supervisor

# Setup application user
sudo useradd -m -s /bin/bash wallettrack
sudo mkdir -p /opt/wallettrack
sudo chown wallettrack:wallettrack /opt/wallettrack

# Clone repository
sudo -u wallettrack git clone https://github.com/halitcanbaba/wallettrack.git /opt/wallettrack

# Setup Python environment
cd /opt/wallettrack
sudo -u wallettrack python3 -m venv venv
sudo -u wallettrack venv/bin/pip install -r requirements.txt

# Setup systemd service
sudo tee /etc/systemd/system/wallettrack.service > /dev/null <<EOF
[Unit]
Description=WalletTrack Multi-Blockchain Monitor
After=network.target

[Service]
Type=simple
User=wallettrack
WorkingDirectory=/opt/wallettrack
Environment=PATH=/opt/wallettrack/venv/bin
ExecStart=/opt/wallettrack/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable wallettrack
sudo systemctl start wallettrack

echo "✅ Production environment setup completed!"
```

## 🚨 Rollback Stratejisi

### 1. Quick Rollback
```bash
# rollback.sh
#!/bin/bash

echo "🔄 Rolling back to previous version..."

# Stop current service
sudo systemctl stop wallettrack

# Restore from backup
BACKUP_DIR=$(ls -td /path/to/wallettrack-backup-* | head -1)
rm -rf /path/to/wallettrack
cp -r $BACKUP_DIR /path/to/wallettrack

# Restart service
sudo systemctl start wallettrack

# Health check
curl -f http://localhost:8000/api/system/health && echo "✅ Rollback successful!"
```

### 2. Database Rollback
```bash
# Database backup before deployment
cp wallettrack.db wallettrack.db.backup-$(date +%Y%m%d_%H%M%S)

# Restore database if needed
cp wallettrack.db.backup-TIMESTAMP wallettrack.db
```

## 📊 Monitoring & Alerting

### 1. Health Check Endpoint
```python
# app/api/system.py
@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "tron_monitor": "running",
            "eth_monitor": "running",
            "websocket": "connected"
        }
    }
```

### 2. Deployment Notification
```bash
# notify-deployment.sh
#!/bin/bash

VERSION=$(git rev-parse --short HEAD)
MESSAGE="🚀 WalletTrack deployed successfully! Version: $VERSION"

# Slack notification
curl -X POST -H 'Content-type: application/json' \
  --data '{"text":"'$MESSAGE'"}' \
  $SLACK_WEBHOOK_URL

# Email notification
echo $MESSAGE | mail -s "WalletTrack Deployment" admin@example.com
```

## 📅 Deployment Checklist

### Pre-Deployment
- [ ] Kod review tamamlandı
- [ ] Tests geçti
- [ ] Staging ortamında test edildi
- [ ] Database backup alındı
- [ ] API key'ler doğrulandı

### Deployment
- [ ] Production sunucusuna erişim
- [ ] Git pull origin main
- [ ] Dependencies güncellendi
- [ ] Service restart edildi
- [ ] Health check başarılı

### Post-Deployment
- [ ] Monitoring aktif
- [ ] Performance metrikleri normal
- [ ] Error logları kontrol edildi
- [ ] Kullanıcı bildirimi yapıldı

## 🎯 Önerilen Deployment Yaklaşımı

### Hemen Uygulanabilir (5 dakika):
1. SSH ile production sunucusuna bağlan
2. `git pull origin main`
3. `sudo systemctl restart wallettrack`
4. Health check yap

### Uzun Vadeli (1-2 hafta):
1. GitHub Actions workflow'u kur
2. Docker container'ı hazırla
3. Blue-green deployment setup'ı yap
4. Monitoring ve alerting ekle

Bu roadmap ile gelecekteki tüm güncellemeler otomatik olarak production'a deploy edilebilir! 🚀
