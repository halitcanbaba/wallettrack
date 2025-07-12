#!/bin/bash

# 🔄 WalletTrack Rollback Script
# Bu script production sunucusunda sorun durumunda çalıştırılmalıdır

echo "🔄 WalletTrack Rollback Started..."
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

# Find latest backup
LATEST_BACKUP=$(ls -t $BACKUP_DIR | head -1)

if [ -z "$LATEST_BACKUP" ]; then
    print_error "No backup found in $BACKUP_DIR"
    exit 1
fi

print_status "Found latest backup: $LATEST_BACKUP"

# Confirm rollback
read -p "Are you sure you want to rollback to $LATEST_BACKUP? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_status "Rollback cancelled"
    exit 0
fi

# Step 1: Stop service
print_status "Stopping $SERVICE_NAME service..."
systemctl stop $SERVICE_NAME
if [ $? -eq 0 ]; then
    print_status "Service stopped successfully"
else
    print_error "Failed to stop service"
    exit 1
fi

# Step 2: Backup current version (just in case)
print_status "Creating backup of current version..."
CURRENT_BACKUP="current-before-rollback-$(date +%Y%m%d_%H%M%S)"
cp -r $APP_DIR $BACKUP_DIR/$CURRENT_BACKUP
print_status "Current version backed up as: $CURRENT_BACKUP"

# Step 3: Restore from backup
print_status "Restoring from backup..."
rm -rf $APP_DIR
cp -r $BACKUP_DIR/$LATEST_BACKUP $APP_DIR
if [ $? -eq 0 ]; then
    print_status "Backup restored successfully"
else
    print_error "Failed to restore backup"
    exit 1
fi

# Step 4: Start service
print_status "Starting $SERVICE_NAME service..."
systemctl start $SERVICE_NAME
if [ $? -eq 0 ]; then
    print_status "Service started successfully"
else
    print_error "Failed to start service"
    exit 1
fi

# Step 5: Health check
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
            print_error "Rollback may have failed"
            exit 1
        else
            print_warning "Health check failed, retrying in 5 seconds..."
            sleep 5
        fi
    fi
done

# Step 6: Check service status
print_status "Checking service status..."
systemctl status $SERVICE_NAME --no-pager
if [ $? -eq 0 ]; then
    print_status "Service is running properly"
else
    print_error "Service has issues"
fi

# Step 7: Show recent logs
print_status "Recent logs:"
journalctl -u $SERVICE_NAME -n 10 --no-pager

# Final status
print_status "🎉 Rollback completed successfully!"
print_status "📊 Current version: $(cd $APP_DIR && git rev-parse --short HEAD)"
print_status "🔗 Application URL: http://localhost:8000"
print_status "📅 Rollback time: $(date)"

echo ""
echo "=========================="
echo "   ROLLBACK SUMMARY"
echo "=========================="
echo "Status: ✅ SUCCESS"
echo "Restored: $LATEST_BACKUP"
echo "Current backup: $CURRENT_BACKUP"
echo "Version: $(cd $APP_DIR && git rev-parse --short HEAD)"
echo "Time: $(date)"
echo "=========================="
