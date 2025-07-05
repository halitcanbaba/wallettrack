"""
Wallet management API endpoints
"""
from typing import List
import asyncio
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db, Blockchain, Wallet
from schemas import (
    WalletCreate, WalletResponse, WalletWithBalances, TokenBalance,
    BlockchainResponse, LegacyWalletCreate, LegacyWalletResponse
)
from app.core.dependencies import logger
from app.services.wallet_service import WalletService
from websocket_manager import manager

router = APIRouter(prefix="/api", tags=["wallets"])
wallet_service = WalletService()

@router.get("/blockchains", response_model=List[BlockchainResponse])
async def get_blockchains(db: AsyncSession = Depends(get_db)):
    """Get all supported blockchains"""
    result = await db.execute(select(Blockchain).where(Blockchain.is_active == True))
    blockchains = result.scalars().all()
    return blockchains

@router.post("/wallets", response_model=WalletResponse)
async def create_wallet(wallet_data: WalletCreate, db: AsyncSession = Depends(get_db)):
    """Add a new wallet for monitoring"""
    
    # Check if wallet already exists
    existing = await db.execute(
        select(Wallet).where(
            and_(
                Wallet.address == wallet_data.address,
                Wallet.blockchain_id == wallet_data.blockchain_id
            )
        )
    )
    
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Wallet already exists")
    
    # Verify blockchain exists
    blockchain_result = await db.execute(
        select(Blockchain).where(Blockchain.id == wallet_data.blockchain_id)
    )
    blockchain = blockchain_result.scalar_one_or_none()
    if not blockchain:
        raise HTTPException(status_code=400, detail="Invalid blockchain ID")
    
    # Create wallet
    wallet = Wallet(
        address=wallet_data.address,
        name=wallet_data.name,
        blockchain_id=wallet_data.blockchain_id
    )
    
    db.add(wallet)
    await db.commit()
    await db.refresh(wallet)
    
    # Start initial balance fetch in background
    asyncio.create_task(wallet_service.fetch_initial_balances(wallet.id, wallet.address, blockchain.name))
    
    # Send WebSocket notification
    await manager.broadcast({
        "type": "wallet_added",
        "data": {
            "wallet_id": wallet.id,
            "address": wallet.address,
            "blockchain": blockchain.name
        }
    })
    
    logger.info(f"New wallet added: {wallet.address} on {blockchain.name}")
    return wallet

@router.get("/wallets", response_model=List[WalletWithBalances])
async def get_wallets(db: AsyncSession = Depends(get_db)):
    """Get all monitored wallets with their current balances"""
    return await wallet_service.get_wallets_with_balances(db)

@router.get("/wallets/{wallet_id}", response_model=WalletWithBalances)
async def get_wallet(wallet_id: int, db: AsyncSession = Depends(get_db)):
    """Get specific wallet details with balances"""
    return await wallet_service.get_wallet_with_balances(db, wallet_id)

@router.delete("/wallets/{wallet_id}")
async def delete_wallet(wallet_id: int, db: AsyncSession = Depends(get_db)):
    """Remove a wallet from monitoring"""
    
    result = await db.execute(select(Wallet).where(Wallet.id == wallet_id))
    wallet = result.scalar_one_or_none()
    
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    
    await db.delete(wallet)
    await db.commit()
    
    # Send WebSocket notification
    await manager.broadcast({
        "type": "wallet_removed",
        "data": {"wallet_id": wallet_id}
    })
    
    logger.info(f"Wallet removed: {wallet.address}")
    return {"message": "Wallet removed successfully"}

@router.post("/wallets/{wallet_id}/refresh")
async def refresh_wallet_balances(wallet_id: int, db: AsyncSession = Depends(get_db)):
    """Manually refresh balances for a specific wallet"""
    return await wallet_service.refresh_wallet_balances(db, wallet_id)

# Legacy endpoint for backward compatibility
@router.post("/wallets/legacy", response_model=LegacyWalletResponse)
async def create_wallet_legacy(wallet_data: LegacyWalletCreate, db: AsyncSession = Depends(get_db)):
    """Legacy endpoint for backward compatibility"""
    
    # Map blockchain name to ID
    blockchain_result = await db.execute(
        select(Blockchain).where(Blockchain.name == wallet_data.blockchain.upper())
    )
    blockchain = blockchain_result.scalar_one_or_none()
    
    if not blockchain:
        raise HTTPException(status_code=400, detail=f"Unsupported blockchain: {wallet_data.blockchain}")
    
    # Create using new schema
    new_wallet_data = WalletCreate(
        address=wallet_data.address,
        name=wallet_data.name,
        blockchain_id=blockchain.id
    )
    
    wallet = await create_wallet(new_wallet_data, db)
    
    # Return in legacy format
    return LegacyWalletResponse(
        id=wallet.id,
        address=wallet.address,
        name=wallet.name,
        blockchain=blockchain.name,
        balances=[],  # Will be populated by balance updates
        last_updated=wallet.last_updated,
        created_at=wallet.created_at
    )
