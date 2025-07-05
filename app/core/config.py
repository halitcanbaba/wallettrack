"""
Core configuration and dependencies for WalletTrack
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# App Configuration
APP_TITLE = "WalletTrack - Multi-Blockchain Wallet Monitor"
APP_DESCRIPTION = "Advanced cryptocurrency wallet monitoring with scam token filtering"
APP_VERSION = "2.0.0"

# WebSocket Configuration
WEBSOCKET_HOST = os.getenv("WEBSOCKET_HOST", "localhost")
WEBSOCKET_PORT = int(os.getenv("WEBSOCKET_PORT", "8000"))
WEBSOCKET_PROTOCOL = os.getenv("WEBSOCKET_PROTOCOL", "ws")

# Frontend Configuration
FRONTEND_REFRESH_INTERVAL = int(os.getenv("FRONTEND_REFRESH_INTERVAL", "30000"))
TRANSACTION_REFRESH_INTERVAL = int(os.getenv("TRANSACTION_REFRESH_INTERVAL", "60000"))
MAX_TRANSACTIONS_DISPLAY = int(os.getenv("MAX_TRANSACTIONS_DISPLAY", "20"))

# Monitoring Configuration
CHANGE_THRESHOLD = 0.01  # 1% change threshold for balance history
MIN_CHANGE_AMOUNT = 0.001  # Minimum change amount to record
DUST_FILTER_THRESHOLD = 0.000001  # Filter out dust transactions
