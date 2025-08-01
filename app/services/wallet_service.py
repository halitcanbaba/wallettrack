"""
Wallet service - handles wallet-related business logic
"""
from typing import List
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import Blockchain, Wallet, WalletToken, Token, AsyncSessionLocal
from schemas import WalletWithBalances, TokenBalance, BlockchainResponse
from app.core.dependencies import eth_service, logger
from app.services.balance_service import BalanceService
from websocket_manager import manager

class WalletService:
    def __init__(self):
        self.balance_service = BalanceService()

    async def get_wallets_with_balances(self, db: AsyncSession, bypass_cache: bool = False) -> List[WalletWithBalances]:
        """Get all monitored wallets with their current balances"""
        
        logger.info(f"🚀 Fetching fresh wallet data (cache disabled)")
        
        # Get all active wallets with relationships
        result = await db.execute(
            select(Wallet)
            .options(
                selectinload(Wallet.blockchain_ref),
                selectinload(Wallet.wallet_tokens).selectinload(WalletToken.token)
            )
            .where(Wallet.is_active == True)
            .order_by(Wallet.created_at.desc())
        )
        
        wallets = result.scalars().all()
        
        wallet_list = []
        for wallet in wallets:
            # Build token balances
            balances = []
            total_usd_value = 0.0
            
            for wallet_token in wallet.wallet_tokens:
                # Only show positive balances and non-hidden tokens
                if wallet_token.balance > 0 and not wallet_token.is_hidden:
                    balance = TokenBalance(
                        wallet_id=wallet.id,  # Add wallet_id for hiding functionality
                        token_id=wallet_token.token.id,
                        token_symbol=wallet_token.token.symbol,
                        token_name=wallet_token.token.name,
                        balance=wallet_token.balance,
                        usd_value=wallet_token.usd_value,
                        last_updated=wallet_token.last_updated
                    )
                    balances.append(balance)
                    
                    if wallet_token.usd_value:
                        total_usd_value += wallet_token.usd_value
            
            # Sort balances by USD value (highest first)
            balances.sort(key=lambda x: x.usd_value or 0, reverse=True)
            
            wallet_response = WalletWithBalances(
                id=wallet.id,
                address=wallet.address,
                name=wallet.name,
                blockchain_id=wallet.blockchain_id,
                is_active=wallet.is_active,
                last_updated=wallet.last_updated,
                created_at=wallet.created_at,
                blockchain=BlockchainResponse(
                    id=wallet.blockchain_ref.id,
                    name=wallet.blockchain_ref.name,
                    display_name=wallet.blockchain_ref.display_name,
                    native_symbol=wallet.blockchain_ref.native_symbol,
                    is_active=wallet.blockchain_ref.is_active,
                    created_at=wallet.blockchain_ref.created_at
                ),
                balances=balances,
                total_usd_value=total_usd_value if total_usd_value > 0 else None
            )
            
            wallet_list.append(wallet_response)
        
        logger.info(f"✅ Returning {len(wallet_list)} wallets (no cache)")
        return wallet_list

    async def get_wallet_with_balances(self, db: AsyncSession, wallet_id: int) -> WalletWithBalances:
        """Get specific wallet details with balances"""
        
        result = await db.execute(
            select(Wallet)
            .options(
                selectinload(Wallet.blockchain_ref),
                selectinload(Wallet.wallet_tokens).selectinload(WalletToken.token)
            )
            .where(Wallet.id == wallet_id)
        )
        
        wallet = result.scalar_one_or_none()
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")
        
        # Build response (similar to get_wallets)
        balances = []
        total_usd_value = 0.0
        
        for wallet_token in wallet.wallet_tokens:
            # Only show positive balances and non-hidden tokens
            if wallet_token.balance > 0 and not wallet_token.is_hidden:
                balance = TokenBalance(
                    wallet_id=wallet.id,  # Add wallet_id for hiding functionality
                    token_id=wallet_token.token.id,
                    token_symbol=wallet_token.token.symbol,
                    token_name=wallet_token.token.name,
                    balance=wallet_token.balance,
                    usd_value=wallet_token.usd_value,
                    last_updated=wallet_token.last_updated
                )
                balances.append(balance)
                
                if wallet_token.usd_value:
                    total_usd_value += wallet_token.usd_value
        
        balances.sort(key=lambda x: x.usd_value or 0, reverse=True)
        
        return WalletWithBalances(
            id=wallet.id,
            address=wallet.address,
            name=wallet.name,
            blockchain_id=wallet.blockchain_id,
            is_active=wallet.is_active,
            last_updated=wallet.last_updated,
            created_at=wallet.created_at,
            blockchain=BlockchainResponse(
                id=wallet.blockchain_ref.id,
                name=wallet.blockchain_ref.name,
                display_name=wallet.blockchain_ref.display_name,
                native_symbol=wallet.blockchain_ref.native_symbol,
                is_active=wallet.blockchain_ref.is_active,
                created_at=wallet.blockchain_ref.created_at
            ),
            balances=balances,
            total_usd_value=total_usd_value if total_usd_value > 0 else None
        )

    async def refresh_wallet_balances(self, db: AsyncSession, wallet_id: int):
        """Manually refresh balances for a specific wallet and show all hidden tokens"""
        
        # Get wallet info
        result = await db.execute(
            select(Wallet)
            .options(selectinload(Wallet.blockchain_ref))
            .where(Wallet.id == wallet_id)
        )
        wallet = result.scalar_one_or_none()
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")
        
        try:
            # First, unhide all tokens for this wallet
            from sqlalchemy import update
            unhide_query = (
                update(WalletToken)
                .where(WalletToken.wallet_id == wallet_id)
                .values(is_hidden=False)
            )
            await db.execute(unhide_query)
            await db.commit()
            
            logger.info(f"Unhid all tokens for wallet {wallet_id}")
            
            if wallet.blockchain_ref.name == "ETH":
                # Get fresh balances from Ethereum
                balances = await eth_service.get_wallet_balances(wallet.address)
                # Get detailed token information
                discovered_tokens = await eth_service.discover_wallet_tokens(wallet.address)
                await self.balance_service.update_wallet_balances_with_tokens(
                    db, wallet_id, balances, discovered_tokens, "ETH"
                )
                
            elif wallet.blockchain_ref.name == "TRON":
                # TRON refresh will be handled by tron_service
                # For now, just update the timestamp
                wallet.last_updated = datetime.utcnow()
                await db.commit()
            
            return {"status": "success", "message": "Balances refreshed and all tokens shown"}
            
        except Exception as e:
            logger.error(f"Error refreshing balances for wallet {wallet_id}: {e}")
            raise HTTPException(status_code=500, detail="Error refreshing balances")

    async def fetch_initial_balances(self, wallet_id: int, address: str, blockchain_name: str):
        """Fetch initial balances for a new wallet"""
        try:
            async with AsyncSessionLocal() as db:
                if blockchain_name == "ETH":
                    # Get Ethereum balances with detailed token info
                    balances = await eth_service.get_wallet_balances(address)
                    # Get detailed token information
                    discovered_tokens = await eth_service.discover_wallet_tokens(address)
                    await self.balance_service.update_wallet_balances_with_tokens(
                        db, wallet_id, balances, discovered_tokens, blockchain_name
                    )
                elif blockchain_name == "TRON":
                    # TRON balances will be handled by existing tron_service monitor
                    pass
        except Exception as e:
            logger.error(f"Error fetching initial balances for {address}: {e}")
