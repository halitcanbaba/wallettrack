"""
Transaction management API endpoints
"""
from typing import List, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from app.core.dependencies import logger
from app.services.transaction_service import TransactionService
from websocket_manager import manager

router = APIRouter(prefix="/api", tags=["transactions"])
transaction_service = TransactionService()

@router.get("/transactions")
async def get_all_transactions(
    limit: int = 50,
    hours: int = 24,  # Filter transactions from last N hours
    db: AsyncSession = Depends(get_db)
):
    """Get recent transactions from all wallets within specified hours"""
    logger.info(f"API: Getting transactions with limit={limit}, hours={hours}")
    result = await transaction_service.get_all_transactions(db, limit, hours)
    
    # Debug: Count ETH vs TRON transactions
    eth_count = len([tx for tx in result if tx.get('blockchain') == 'ETH'])
    tron_count = len([tx for tx in result if tx.get('blockchain') == 'TRON'])
    logger.info(f"API: Returning {len(result)} transactions: {eth_count} ETH, {tron_count} TRON")
    
    return result

@router.get("/transactions/live")
async def get_live_transactions(
    since_timestamp: Optional[int] = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """Get new transactions since a given timestamp for real-time updates"""
    return await transaction_service.get_live_transactions(db, since_timestamp, limit)

@router.post("/transactions/notify")
async def notify_new_transaction(
    wallet_address: str,
    transaction_hash: str,
    amount: float,
    token_symbol: str,
    transaction_type: str,
    db: AsyncSession = Depends(get_db)
):
    """Endpoint for external services to notify about new transactions"""
    return await transaction_service.notify_new_transaction(
        db, wallet_address, transaction_hash, amount, token_symbol, transaction_type
    )

@router.get("/wallets/{wallet_id}/transactions")
async def get_wallet_transactions(
    wallet_id: int, 
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """Get recent transactions for a wallet"""
    return await transaction_service.get_wallet_transactions(db, wallet_id, limit)
