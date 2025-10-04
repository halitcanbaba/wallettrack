"""
Core dependencies and utilities
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

from database import init_db, seed_initial_data, AsyncSessionLocal
from tron_monitor import tron_monitor
from eth_monitor import ethereum_monitor
from btc_monitor import btc_monitor
from solana_monitor import solana_monitor
from eth_service import EthereumService
from tron_service import tron_client
from btc_service import btc_client
from solana_service import solana_client
from websocket_manager import manager

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize services
eth_service = EthereumService(use_v2_api=True)
tron_service = tron_client  # Alias for backward compatibility

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    logger.info("Starting Multi-Blockchain Wallet Monitor...")
    await init_db()
    await seed_initial_data()
    await tron_monitor.start_monitoring()
    await ethereum_monitor.start_monitoring()
    await btc_monitor.start_monitoring()
    await solana_monitor.start_monitoring()
    logger.info("Application started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Wallet Monitor...")
    await tron_monitor.stop_monitoring()
    await ethereum_monitor.stop_monitoring()
    await btc_monitor.stop_monitoring()
    await solana_monitor.stop_monitoring()
    await eth_service.close()
    await tron_client.close()
    await btc_client.close()
    await solana_client.close()
    logger.info("Application shutdown complete")
