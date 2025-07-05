"""
Balance and history management API endpoints
"""
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db, Wallet, BalanceHistory, Token, WalletToken
from app.core.dependencies import logger
from app.services.balance_service import BalanceService

router = APIRouter(prefix="/api", tags=["balances"])
balance_service = BalanceService()

@router.get("/wallets/{wallet_id}/history")
async def get_balance_history(
    wallet_id: int,
    hours: int = 24,
    days: int = 7,
    db: AsyncSession = Depends(get_db)
):
    """Get balance history for a wallet with enhanced data"""
    return await balance_service.get_wallet_balance_history(db, wallet_id, hours, days)

@router.get("/wallets/history/all")
async def get_all_wallets_history(
    days: int = 7,
    hours: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """Get balance history for all wallets"""
    return await balance_service.get_all_wallets_history(db, days, hours)

@router.get("/wallets/{wallet_id}/balance-history")
async def get_wallet_balance_history(
    wallet_id: int,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """Get balance change history for a wallet"""
    
    # Verify wallet exists
    wallet_result = await db.execute(
        select(Wallet).where(Wallet.id == wallet_id)
    )
    wallet = wallet_result.scalar_one_or_none()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    
    # Get balance history
    result = await db.execute(
        select(BalanceHistory)
        .join(Token)
        .where(BalanceHistory.wallet_id == wallet_id)
        .order_by(desc(BalanceHistory.timestamp))
        .limit(limit)
    )
    
    history_records = result.scalars().all()
    
    # Get token info for each record
    history_list = []
    for record in history_records:
        token_result = await db.execute(
            select(Token).where(Token.id == record.token_id)
        )
        token = token_result.scalar_one_or_none()
        
        if token:
            history_list.append({
                "id": record.id,
                "token_symbol": token.symbol,
                "token_name": token.name,
                "balance_before": record.balance_before,
                "balance_after": record.balance_after,
                "change_amount": record.change_amount,
                "change_percentage": record.change_percentage,
                "change_type": record.change_type,
                "timestamp": record.timestamp,
                "transaction_hash": record.transaction_hash
            })
    return {
        "wallet_id": wallet_id,
        "history": history_list
    }
