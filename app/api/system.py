"""
System status and monitoring API endpoints
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db, Blockchain, Wallet, Token, BalanceHistory, WalletToken
from app.core.config import APP_VERSION

router = APIRouter(prefix="/api", tags=["system"])

@router.get("/status")
async def get_system_status(db: AsyncSession = Depends(get_db)):
    """Get overall system status and statistics"""
    
    # Get blockchain stats
    blockchain_result = await db.execute(
        select(Blockchain).where(Blockchain.is_active == True)
    )
    blockchains = blockchain_result.scalars().all()
    
    # Get wallet counts by blockchain
    wallet_stats = {}
    total_wallets = 0
    
    for blockchain in blockchains:
        wallet_count_result = await db.execute(
            select(func.count(Wallet.id))
            .where(
                and_(
                    Wallet.blockchain_id == blockchain.id,
                    Wallet.is_active == True
                )
            )
        )
        wallet_count = wallet_count_result.scalar()
        wallet_stats[blockchain.name] = wallet_count
        total_wallets += wallet_count
    
    # Get token count
    token_count_result = await db.execute(
        select(func.count(Token.id)).where(Token.is_verified == True)
    )
    total_tokens = token_count_result.scalar()
    
    # Get recent balance changes
    recent_changes_result = await db.execute(
        select(func.count(BalanceHistory.id))
        .where(BalanceHistory.timestamp >= datetime.utcnow() - timedelta(hours=24))
    )
    recent_changes = recent_changes_result.scalar()
    
    return {
        "status": "running",
        "version": APP_VERSION,
        "uptime_info": "Multi-blockchain wallet monitoring active",
        "statistics": {
            "total_wallets": total_wallets,
            "total_tokens": total_tokens,
            "wallet_distribution": wallet_stats,
            "balance_changes_24h": recent_changes
        },
        "supported_blockchains": [
            {
                "name": blockchain.name,
                "display_name": blockchain.display_name,
                "native_symbol": blockchain.native_symbol
            }
            for blockchain in blockchains
        ],
        "monitoring": {
            "tron_monitor": "active",
            "ethereum_monitor": "active"
        }
    }

@router.get("/summary")
async def get_portfolio_summary(db: AsyncSession = Depends(get_db)):
    """Get portfolio summary across all wallets"""
    
    # Get all wallets with balances
    result = await db.execute(
        select(Wallet)
        .options(
            selectinload(Wallet.blockchain_ref),
            selectinload(Wallet.wallet_tokens).selectinload(WalletToken.token)
        )
        .where(Wallet.is_active == True)
    )
    
    wallets = result.scalars().all()
    
    # Aggregate data
    portfolio_summary = {
        "total_wallets": len(wallets),
        "blockchains": {},
        "top_tokens": {},
        "total_positions": 0
    }
    
    for wallet in wallets:
        blockchain_name = wallet.blockchain_ref.name
        
        if blockchain_name not in portfolio_summary["blockchains"]:
            portfolio_summary["blockchains"][blockchain_name] = {
                "wallet_count": 0,
                "total_tokens": 0,
                "top_balances": []
            }
        
        portfolio_summary["blockchains"][blockchain_name]["wallet_count"] += 1
        
        for wallet_token in wallet.wallet_tokens:
            if wallet_token.balance > 0:
                portfolio_summary["total_positions"] += 1
                portfolio_summary["blockchains"][blockchain_name]["total_tokens"] += 1
                
                token_symbol = wallet_token.token.symbol
                if token_symbol not in portfolio_summary["top_tokens"]:
                    portfolio_summary["top_tokens"][token_symbol] = {
                        "total_balance": 0,
                        "wallet_count": 0,
                        "blockchain": blockchain_name
                    }
                
                portfolio_summary["top_tokens"][token_symbol]["total_balance"] += wallet_token.balance
                portfolio_summary["top_tokens"][token_symbol]["wallet_count"] += 1
    
    # Sort top tokens by occurrence across wallets
    top_tokens_list = sorted(
        [
            {
                "symbol": symbol,
                "total_balance": data["total_balance"],
                "wallet_count": data["wallet_count"],
                "blockchain": data["blockchain"]
            }
            for symbol, data in portfolio_summary["top_tokens"].items()
        ],
        key=lambda x: (x["wallet_count"], x["total_balance"]),
        reverse=True
    )[:10]  # Top 10 tokens
    
    portfolio_summary["top_tokens"] = top_tokens_list
    
    return portfolio_summary

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@router.get("/config")
async def get_frontend_config():
    """Get frontend configuration"""
    from app.core.config import (
        WEBSOCKET_HOST, WEBSOCKET_PORT, WEBSOCKET_PROTOCOL,
        FRONTEND_REFRESH_INTERVAL, TRANSACTION_REFRESH_INTERVAL, 
        MAX_TRANSACTIONS_DISPLAY
    )
    
    return {
        "websocket": {
            "host": WEBSOCKET_HOST,
            "port": WEBSOCKET_PORT,
            "protocol": WEBSOCKET_PROTOCOL
        },
        "frontend": {
            "refresh_interval": FRONTEND_REFRESH_INTERVAL,
            "transaction_refresh_interval": TRANSACTION_REFRESH_INTERVAL,
            "max_transactions_display": MAX_TRANSACTIONS_DISPLAY
        }
    }
