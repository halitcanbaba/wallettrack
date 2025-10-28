import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import AsyncSessionLocal, Blockchain, Token, Wallet, WalletToken, BalanceHistory
from btc_service import btc_client
from websocket_manager import manager

logger = logging.getLogger(__name__)

class BitcoinMonitor:
    def __init__(self, check_interval: int = None):
        # Load configuration from environment
        self.check_interval = check_interval or int(os.getenv('BALANCE_CHECK_INTERVAL', '10'))
        self.balance_update_threshold = float(os.getenv('BALANCE_UPDATE_THRESHOLD', '0.001'))
        self.min_balance_change = float(os.getenv('MIN_BALANCE_CHANGE', '0.0001'))
        self.wallet_update_cooldown = int(os.getenv('WALLET_UPDATE_COOLDOWN', '10'))
        self.enable_notifications = os.getenv('ENABLE_BALANCE_NOTIFICATIONS', 'true').lower() == 'true'
        
        self.btc_service = btc_client
        self.is_running = False
        self.task = None
        
        logger.info(f"BTC Monitor initialized with:")
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
            logger.info("Starting Bitcoin balance monitoring loop...")
    
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
            await self.btc_service.close()
            logger.info("Stopped Bitcoin balance monitoring")
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.is_running:
            try:
                await self._check_all_btc_wallets()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in Bitcoin monitoring loop: {e}")
                await asyncio.sleep(30)  # Short delay before retrying
    
    async def _check_all_btc_wallets(self):
        """Check all Bitcoin wallets for balance updates"""
        logger.info("🔍 BTC Monitor: Starting wallet check cycle...")
        async with AsyncSessionLocal() as db:
            try:
                # Get all active Bitcoin wallets
                result = await db.execute(
                    select(Wallet)
                    .join(Blockchain)
                    .where(
                        and_(
                            Wallet.is_active == True,
                            Blockchain.name == "BTC"
                        )
                    )
                    .options(selectinload(Wallet.blockchain_ref))
                )
                
                btc_wallets = result.scalars().all()
                logger.info(f"Monitoring {len(btc_wallets)} Bitcoin wallets...")
                
                for wallet in btc_wallets:
                    try:
                        logger.info(f"Updating balances for Bitcoin wallet: {wallet.address}")
                        await self._update_wallet_balances(db, wallet)
                    except Exception as e:
                        logger.error(f"Error updating Bitcoin wallet {wallet.address}: {e}")
                        continue
                
            except Exception as e:
                logger.error(f"Error in BTC wallet check cycle: {e}")
    
    async def _update_wallet_balances(self, db: AsyncSession, wallet: Wallet):
        """Update balances for a specific Bitcoin wallet"""
        try:
            # Get current BTC balance
            btc_balance = await self.btc_service.get_btc_balance(wallet.address)
            
            # Get or create BTC token entry
            btc_token = await self._get_or_create_btc_token(db)
            
            # Get or create wallet_token entry
            result = await db.execute(
                select(WalletToken).where(
                    and_(
                        WalletToken.wallet_id == wallet.id,
                        WalletToken.token_id == btc_token.id
                    )
                )
            )
            wallet_token = result.scalar_one_or_none()
            
            if wallet_token is None:
                # Create new wallet_token entry
                wallet_token = WalletToken(
                    wallet_id=wallet.id,
                    token_id=btc_token.id,
                    balance=btc_balance,
                    last_updated=datetime.utcnow()
                )
                db.add(wallet_token)
                logger.info(f"Created new BTC balance entry: {btc_balance} BTC")
            else:
                old_balance = wallet_token.balance
                
                # Check if balance changed significantly
                if old_balance > 0:
                    change_percent = abs(btc_balance - old_balance) / old_balance
                else:
                    change_percent = 1.0 if btc_balance > 0 else 0.0
                
                balance_diff = abs(btc_balance - old_balance)
                
                if change_percent >= self.balance_update_threshold or balance_diff >= self.min_balance_change:
                    logger.info(f"BTC balance changed: {old_balance} -> {btc_balance} ({change_percent*100:.2f}%)")
                    
                    # Update wallet_token
                    wallet_token.balance = btc_balance
                    wallet_token.last_updated = datetime.utcnow()
                    
                    # Record in balance history
                    change_type = "increase" if btc_balance > old_balance else "decrease"
                    history_entry = BalanceHistory(
                        wallet_id=wallet.id,
                        token_id=btc_token.id,
                        balance_before=old_balance,
                        balance_after=btc_balance,
                        change_amount=btc_balance - old_balance,
                        change_percentage=change_percent * 100,
                        change_type=change_type,
                        timestamp=datetime.utcnow()
                    )
                    db.add(history_entry)
                    
                    # Send WebSocket notification
                    if self.enable_notifications:
                        await manager.broadcast({
                            "type": "btc_balance_update",
                            "data": {
                                "wallet_id": wallet.id,
                                "address": wallet.address,
                                "blockchain": "BTC",
                                "token": "BTC",
                                "balance": btc_balance,
                                "old_balance": old_balance,
                                "change_percent": change_percent * 100,
                                "timestamp": datetime.utcnow().isoformat()
                            }
                        })
            
            # Update wallet last_updated timestamp
            wallet.last_updated = datetime.utcnow()
            
            await db.commit()
            logger.info(f"Updated Bitcoin wallet {wallet.address}: {btc_balance} BTC")
            
        except Exception as e:
            logger.error(f"Error updating Bitcoin wallet balances: {e}")
            await db.rollback()
    
    async def _get_or_create_btc_token(self, db: AsyncSession) -> Token:
        """Get or create BTC token entry"""
        # Get BTC blockchain
        btc_blockchain_result = await db.execute(
            select(Blockchain).where(Blockchain.name == "BTC")
        )
        btc_blockchain = btc_blockchain_result.scalar_one()
        
        # Check if BTC token exists
        result = await db.execute(
            select(Token).where(
                and_(
                    Token.symbol == "BTC",
                    Token.blockchain_id == btc_blockchain.id
                )
            )
        )
        btc_token = result.scalar_one_or_none()
        
        if btc_token is None:
            # Create BTC token
            btc_token = Token(
                symbol="BTC",
                name="Bitcoin",
                contract_address=None,  # BTC is native
                decimals=8,
                blockchain_id=btc_blockchain.id,
                is_native=True,
                is_verified=True
            )
            db.add(btc_token)
            await db.commit()
            await db.refresh(btc_token)
            logger.info("Created BTC token entry")
        
        return btc_token

# Global instance
btc_monitor = BitcoinMonitor()
