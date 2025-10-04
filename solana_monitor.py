import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import AsyncSessionLocal, Blockchain, Token, Wallet, WalletToken, BalanceHistory
from solana_service import solana_client
from websocket_manager import manager

logger = logging.getLogger(__name__)

class SolanaMonitor:
    def __init__(self, check_interval: int = None):
        # Load configuration from environment
        self.check_interval = check_interval or int(os.getenv('BALANCE_CHECK_INTERVAL', '10'))
        self.balance_update_threshold = float(os.getenv('BALANCE_UPDATE_THRESHOLD', '0.001'))
        self.min_balance_change = float(os.getenv('MIN_BALANCE_CHANGE', '0.0001'))
        self.wallet_update_cooldown = int(os.getenv('WALLET_UPDATE_COOLDOWN', '10'))
        self.enable_notifications = os.getenv('ENABLE_BALANCE_NOTIFICATIONS', 'true').lower() == 'true'
        
        self.solana_service = solana_client
        self.is_running = False
        self.task = None
        
        logger.info(f"Solana Monitor initialized with:")
        logger.info(f"  - Check interval: {self.check_interval}s")
        logger.info(f"  - Balance threshold: {self.balance_update_threshold*100}%")
        logger.info(f"  - Min change: {self.min_balance_change}")
        logger.info(f"  - Wallet cooldown: {self.wallet_update_cooldown}s")
        logger.info(f"  - Notifications: {self.enable_notifications}")
    
    async def start_monitoring(self):
        """Start the background monitoring task"""
        if not self.is_running:
            self.is_running = True
            self.task = asyncio.create_task(self._monitoring_loop())
            logger.info("Starting Solana balance monitoring loop...")
    
    async def stop_monitoring(self):
        """Stop the monitoring task"""
        if self.is_running:
            self.is_running = False
            if self.task:
                self.task.cancel()
                try:
                    await self.task
                except asyncio.CancelledError:
                    pass
            await self.solana_service.close()
            logger.info("Stopped Solana balance monitoring")
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.is_running:
            try:
                await self._check_all_solana_wallets()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in Solana monitoring loop: {e}")
                await asyncio.sleep(30)  # Short delay before retrying
    
    async def _check_all_solana_wallets(self):
        """Check all Solana wallets for balance updates"""
        logger.info("🔍 Solana Monitor: Starting wallet check cycle...")
        async with AsyncSessionLocal() as db:
            try:
                # Get all active Solana wallets
                result = await db.execute(
                    select(Wallet)
                    .join(Blockchain)
                    .where(
                        and_(
                            Wallet.is_active == True,
                            Blockchain.name == "SOL"
                        )
                    )
                    .options(selectinload(Wallet.blockchain_ref))
                )
                
                solana_wallets = result.scalars().all()
                logger.info(f"Monitoring {len(solana_wallets)} Solana wallets...")
                
                for wallet in solana_wallets:
                    try:
                        logger.info(f"Updating balances for Solana wallet: {wallet.address}")
                        await self._update_wallet_balances(db, wallet)
                    except Exception as e:
                        logger.error(f"Error updating Solana wallet {wallet.address}: {e}")
                        continue
                
            except Exception as e:
                logger.error(f"Error in Solana wallet check cycle: {e}")
    
    async def _update_wallet_balances(self, db: AsyncSession, wallet: Wallet):
        """Update balances for a specific Solana wallet"""
        try:
            # Get all balances (SOL + SPL tokens)
            balances = await self.solana_service.get_wallet_balances(wallet.address)
            
            if not balances:
                logger.warning(f"No balances retrieved for Solana wallet {wallet.address}")
                return
            
            # Get Solana blockchain
            sol_blockchain_result = await db.execute(
                select(Blockchain).where(Blockchain.name == "SOL")
            )
            sol_blockchain = sol_blockchain_result.scalar_one()
            
            token_balances = {}
            
            # Process each token balance
            for token_symbol, balance in balances.items():
                # Get or create token
                token = await self._get_or_create_token(db, token_symbol, sol_blockchain.id)
                
                # Get or create wallet_token entry
                result = await db.execute(
                    select(WalletToken).where(
                        and_(
                            WalletToken.wallet_id == wallet.id,
                            WalletToken.token_id == token.id
                        )
                    )
                )
                wallet_token = result.scalar_one_or_none()
                
                if wallet_token is None:
                    # Create new wallet_token entry
                    wallet_token = WalletToken(
                        wallet_id=wallet.id,
                        token_id=token.id,
                        balance=balance,
                        last_updated=datetime.utcnow()
                    )
                    db.add(wallet_token)
                    logger.info(f"Created new {token_symbol} balance entry: {balance}")
                else:
                    old_balance = wallet_token.balance
                    
                    # Check if balance changed significantly
                    if old_balance > 0:
                        change_percent = abs(balance - old_balance) / old_balance
                    else:
                        change_percent = 1.0 if balance > 0 else 0.0
                    
                    balance_diff = abs(balance - old_balance)
                    
                    if change_percent >= self.balance_update_threshold or balance_diff >= self.min_balance_change:
                        logger.info(f"{token_symbol} balance changed: {old_balance} -> {balance} ({change_percent*100:.2f}%)")
                        
                        # Update wallet_token
                        wallet_token.balance = balance
                        wallet_token.last_updated = datetime.utcnow()
                        
                        # Record in balance history
                        history_entry = BalanceHistory(
                            wallet_id=wallet.id,
                            token_id=token.id,
                            balance=balance,
                            change_amount=balance - old_balance,
                            change_percent=change_percent * 100,
                            timestamp=datetime.utcnow()
                        )
                        db.add(history_entry)
                
                token_balances[token_symbol] = balance
            
            # Update wallet last_updated timestamp
            wallet.last_updated = datetime.utcnow()
            
            await db.commit()
            
            # Send WebSocket notification
            if self.enable_notifications and token_balances:
                await manager.broadcast({
                    "type": "solana_balance_update",
                    "data": {
                        "wallet_id": wallet.id,
                        "address": wallet.address,
                        "blockchain": "SOL",
                        "token_balances": token_balances,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                })
            
            logger.info(f"Updated Solana wallet {wallet.address}: {token_balances}")
            
        except Exception as e:
            logger.error(f"Error updating Solana wallet balances: {e}")
            await db.rollback()
    
    async def _get_or_create_token(self, db: AsyncSession, symbol: str, blockchain_id: int) -> Token:
        """Get or create token entry"""
        # Check if token exists
        result = await db.execute(
            select(Token).where(
                and_(
                    Token.symbol == symbol,
                    Token.blockchain_id == blockchain_id
                )
            )
        )
        token = result.scalar_one_or_none()
        
        if token is None:
            # Create token
            is_native = (symbol == "SOL")
            
            # Get token name from service
            token_name = symbol
            if is_native:
                token_name = "Solana"
            else:
                # Check if it's a known token
                for mint, info in self.solana_service.common_tokens.items():
                    if info['symbol'] == symbol:
                        token_name = info['name']
                        break
            
            token = Token(
                symbol=symbol,
                name=token_name,
                contract_address=None,  # Could store mint address here
                decimals=9 if is_native else 6,  # Default decimals
                blockchain_id=blockchain_id,
                is_native=is_native,
                is_verified=is_native  # Only native SOL is auto-verified
            )
            db.add(token)
            await db.commit()
            await db.refresh(token)
            logger.info(f"Created {symbol} token entry")
        
        return token

# Global instance
solana_monitor = SolanaMonitor()
