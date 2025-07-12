#!/bin/bash

# 🚀 WalletTrack Quick Deployment Script
# Bu script production sunucusunda çalıştırılmalıdır

echo "🚀 WalletTrack Deployment Started..."
echo "📅 $(date)"

# Configuration
APP_DIR="/opt/wallettrack"
BACKUP_DIR="/opt/wallettrack-backups"
SERVICE_NAME="wallettrack"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   print_error "This script must be run as root (use sudo)"
   exit 1
fi

# Create backup directory if it doesn't exist
mkdir -p $BACKUP_DIR

# Step 1: Create backup
print_status "Creating backup..."
BACKUP_NAME="wallettrack-backup-$(date +%Y%m%d_%H%M%S)"
cp -r $APP_DIR $BACKUP_DIR/$BACKUP_NAME
print_status "Backup created: $BACKUP_DIR/$BACKUP_NAME"

# Step 2: Stop service
print_status "Stopping $SERVICE_NAME service..."
systemctl stop $SERVICE_NAME
if [ $? -eq 0 ]; then
    print_status "Service stopped successfully"
else
    print_error "Failed to stop service"
    exit 1
fi

# Step 3: Pull latest changes
print_status "Pulling latest changes from GitHub..."
cd $APP_DIR
git pull origin main
if [ $? -eq 0 ]; then
    print_status "Git pull successful"
else
    print_error "Git pull failed"
    print_warning "Rolling back..."
    systemctl start $SERVICE_NAME
    exit 1
fi

# Step 4: Install/Update dependencies
print_status "Installing/updating dependencies..."
pip install -r requirements.txt
if [ $? -eq 0 ]; then
    print_status "Dependencies updated successfully"
else
    print_warning "Dependencies update failed, but continuing..."
fi

# Step 5: Start service
print_status "Starting $SERVICE_NAME service..."
systemctl start $SERVICE_NAME
if [ $? -eq 0 ]; then
    print_status "Service started successfully"
else
    print_error "Failed to start service"
    print_warning "Rolling back..."
    systemctl stop $SERVICE_NAME
    rm -rf $APP_DIR
    cp -r $BACKUP_DIR/$BACKUP_NAME $APP_DIR
    systemctl start $SERVICE_NAME
    exit 1
fi

# Step 6: Health check
print_status "Performing health check..."
sleep 5

# Try health check 5 times
for i in {1..5}; do
    print_status "Health check attempt $i/5..."
    HEALTH_CHECK=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/system/health)
    
    if [ "$HEALTH_CHECK" = "200" ]; then
        print_status "✅ Health check passed!"
        break
    else
        if [ $i -eq 5 ]; then
            print_error "❌ Health check failed after 5 attempts"
            print_warning "Rolling back..."
            systemctl stop $SERVICE_NAME
            rm -rf $APP_DIR
            cp -r $BACKUP_DIR/$BACKUP_NAME $APP_DIR
            systemctl start $SERVICE_NAME
            exit 1
        else
            print_warning "Health check failed, retrying in 5 seconds..."
            sleep 5
        fi
    fi
done

# Step 7: Check service status
print_status "Checking service status..."
systemctl status $SERVICE_NAME --no-pager
if [ $? -eq 0 ]; then
    print_status "Service is running properly"
else
    print_error "Service has issues"
fi

# Step 8: Show recent logs
print_status "Recent logs:"
journalctl -u $SERVICE_NAME -n 10 --no-pager

# Step 9: Cleanup old backups (keep last 5)
print_status "Cleaning up old backups..."
ls -t $BACKUP_DIR | tail -n +6 | xargs -I {} rm -rf $BACKUP_DIR/{}
print_status "Old backups cleaned up"

# Final status
print_status "🎉 Deployment completed successfully!"
print_status "📊 Current version: $(cd $APP_DIR && git rev-parse --short HEAD)"
print_status "🔗 Application URL: http://localhost:8000"
print_status "📅 Deployment time: $(date)"

echo ""
echo "=========================="
echo "   DEPLOYMENT SUMMARY"
echo "=========================="
echo "Status: ✅ SUCCESS"
echo "Backup: $BACKUP_DIR/$BACKUP_NAME"
echo "Version: $(cd $APP_DIR && git rev-parse --short HEAD)"
echo "Time: $(date)"
echo "=========================="
