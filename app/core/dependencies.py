"""
Core dependencies and utilities
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

from database import init_db, seed_initial_data, AsyncSessionLocal
from tron_service import monitor as tron_monitor
from eth_monitor import ethereum_monitor
from eth_service import EthereumService
from tron_service import TronGridClient
from websocket_manager import manager

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize services
eth_service = EthereumService(use_v2_api=True)
tron_service = TronGridClient()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    logger.info("Starting Multi-Blockchain Wallet Monitor...")
    await init_db()
    await seed_initial_data()
    tron_monitor.start_monitoring()
    await ethereum_monitor.start_monitoring()
    logger.info("Application started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Wallet Monitor...")
    await tron_monitor.close()
    await ethereum_monitor.stop_monitoring()
    await eth_service.close()
    await tron_service.close()
    logger.info("Application shutdown complete")
