import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import AsyncSessionLocal, Blockchain, Token, Wallet, WalletToken, BalanceHistory
from tron_service import TronGridClient, tron_client
from websocket_manager import manager

logger = logging.getLogger(__name__)

class TronMonitor:
    def __init__(self, check_interval: int = None):
        # Load configuration from environment
        self.check_interval = check_interval or int(os.getenv('BALANCE_CHECK_INTERVAL', '60'))
        self.balance_update_threshold = float(os.getenv('BALANCE_UPDATE_THRESHOLD', '0.02'))
        self.min_balance_change = float(os.getenv('MIN_BALANCE_CHANGE', '0.001'))
        self.wallet_update_cooldown = int(os.getenv('WALLET_UPDATE_COOLDOWN', '1800'))
        self.enable_notifications = os.getenv('ENABLE_BALANCE_NOTIFICATIONS', 'true').lower() == 'true'
        
        self.tron_service = tron_client
        self.is_running = False
        self.task = None
        
        logger.info(f"TRON Monitor initialized with:")
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
            logger.info("Starting TRON balance monitoring loop...")
    
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
            await self.tron_service.close()
            logger.info("Stopped TRON balance monitoring")
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.is_running:
            try:
                await self._check_all_tron_wallets()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in TRON monitoring loop: {e}")
                await asyncio.sleep(30)  # Short delay before retrying
    
    async def _check_all_tron_wallets(self):
        """Check all TRON wallets for balance updates"""
        logger.info("🔍 TRON Monitor: Starting wallet check cycle...")
        async with AsyncSessionLocal() as db:
            try:
                # Get all active TRON wallets
                result = await db.execute(
                    select(Wallet)
                    .join(Blockchain)
                    .where(
                        and_(
                            Wallet.is_active == True,
                            Blockchain.name == "TRON"
                        )
                    )
                    .options(selectinload(Wallet.blockchain_ref))
                )
                
                tron_wallets = result.scalars().all()
                logger.info(f"Monitoring {len(tron_wallets)} TRON wallets...")
                
                for wallet in tron_wallets:
                    try:
                        logger.info(f"Updating balances for TRON wallet: {wallet.address}")
                        await self._update_wallet_balances(db, wallet)
                        
                        # Also check for new transactions (every other cycle to reduce load)
                        import time
                        current_cycle = int(time.time() / self.check_interval)
                        if current_cycle % 2 == 0:  # Every other cycle
                            try:
                                # Get transactions from last cycle
                                since_timestamp = int(time.time() - (self.check_interval * 2))
                                new_transactions = await self.tron_service.get_recent_transactions_with_notifications(
                                    wallet.address, wallet.id, since_timestamp
                                )
                                if new_transactions:
                                    logger.info(f"Found {len(new_transactions)} new TRON transactions for wallet {wallet.id}")
                            except Exception as tx_error:
                                logger.error(f"Error checking TRON transactions for wallet {wallet.id}: {tx_error}")
                        
                        # Small delay between wallets to avoid rate limiting
                        await asyncio.sleep(self.tron_service.min_request_interval)
                    except Exception as e:
                        logger.error(f"Error updating wallet {wallet.address}: {e}")
                
            except Exception as e:
                logger.error(f"Error in _check_all_tron_wallets: {e}")
    
    async def _update_wallet_balances(self, db: AsyncSession, wallet: Wallet):
        """Update balances for a single TRON wallet"""
        try:
            # Skip if wallet was updated recently (using configured cooldown)
            if wallet.last_updated:
                time_since_update = datetime.utcnow() - wallet.last_updated
                cooldown_seconds = timedelta(seconds=self.wallet_update_cooldown)
                if time_since_update < cooldown_seconds:
                    logger.debug(f"Skipping {wallet.address} - updated {time_since_update} ago (cooldown: {cooldown_seconds})")
                    return
            
            logger.debug(f"Updating balances for TRON wallet: {wallet.address}")
            
            # Get current balances from TRON network
            trx_balance, usdt_balance = await self._fetch_wallet_balances(wallet.address)
            
            # Create balances dictionary
            balances = {
                'TRX': trx_balance,
                'USDT': usdt_balance
            }
            
            # Update balances in database
            await self._update_wallet_balances_in_db(db, wallet.id, balances)
            
            # Update wallet timestamp
            wallet.last_updated = datetime.utcnow()
            await db.commit()
            
            # Log significant balances
            significant_balances = {
                symbol: balance for symbol, balance in balances.items() 
                if balance > 0.001  # Only log meaningful balances
            }
            if significant_balances:
                balance_str = ", ".join([f"{symbol}={balance:.6f}" for symbol, balance in significant_balances.items()])
                logger.debug(f"Updated TRON wallet {wallet.address}: {balance_str}")
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error updating wallet {wallet.address}: {e}")
    
    async def _update_wallet_balances_in_db(self, db: AsyncSession, wallet_id: int, balances: Dict[str, float]):
        """Update wallet balances in database"""
        try:
            # Get TRON blockchain ID
            blockchain_result = await db.execute(
                select(Blockchain).where(Blockchain.name == "TRON")
            )
            blockchain = blockchain_result.scalar_one_or_none()
            if not blockchain:
                return
            
            # Track which tokens have been updated (for cleanup)
            updated_token_ids = set()
            
            for token_symbol, balance in balances.items():
                # Set token properties based on symbol
                if token_symbol == 'TRX':
                    contract_address = None
                    token_name = 'TRON'
                    decimals = 6
                elif token_symbol == 'USDT':
                    contract_address = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
                    token_name = 'Tether USD'
                    decimals = 6
                else:
                    contract_address = None
                    token_name = token_symbol
                    decimals = 18
                
                # Find or create token
                token = await self._find_or_create_token(
                    db, token_symbol, contract_address, token_name, decimals, blockchain.id
                )
                
                if token:
                    updated_token_ids.add(token.id)
                    await self._update_single_wallet_token(db, wallet_id, token.id, balance)
            
            # Remove balances for tokens that are no longer held (balance = 0)
            await self._cleanup_zero_balances(db, wallet_id, updated_token_ids)
            
        except Exception as e:
            logger.error(f"Error updating wallet balances in DB: {e}")
            raise
    
    async def _find_or_create_token(self, db: AsyncSession, symbol: str, contract_address: Optional[str], 
                                   name: str, decimals: int, blockchain_id: int) -> Optional[Token]:
        """Find existing token or create new one"""
        try:
            # First try to find by symbol and blockchain
            token_result = await db.execute(
                select(Token).where(
                    and_(
                        Token.symbol == symbol,
                        Token.blockchain_id == blockchain_id
                    )
                )
            )
            token = token_result.scalar_one_or_none()
            
            # If not found and we have contract address, try to find by contract
            if not token and contract_address:
                token_result = await db.execute(
                    select(Token).where(
                        and_(
                            Token.contract_address == contract_address,
                            Token.blockchain_id == blockchain_id
                        )
                    )
                )
                token = token_result.scalar_one_or_none()
            
            if not token:
                # Create new token
                is_native = symbol in ['TRX', 'ETH', 'BNB']
                token = Token(
                    symbol=symbol,
                    name=name,
                    contract_address=contract_address,
                    decimals=decimals,
                    blockchain_id=blockchain_id,
                    is_native=is_native,
                    is_verified=True  # TRON tokens are generally verified
                )
                db.add(token)
                await db.flush()
                logger.debug(f"Created new TRON token: {symbol} ({contract_address})")
            else:
                # Update existing token with missing information
                updated = False
                if not token.contract_address and contract_address:
                    token.contract_address = contract_address
                    updated = True
                if token.name == token.symbol and name != symbol:
                    token.name = name
                    updated = True
                if token.decimals != decimals:
                    token.decimals = decimals
                    updated = True
                
                if updated:
                    logger.debug(f"Updated TRON token info for {symbol}")
            
            return token
            
        except Exception as e:
            logger.error(f"Error finding/creating TRON token {symbol}: {e}")
            return None
    
    async def _update_single_wallet_token(self, db: AsyncSession, wallet_id: int, token_id: int, balance: float):
        """Update a single wallet token balance and create history if significant change"""
        try:
            # Find existing wallet token balance
            wallet_token_result = await db.execute(
                select(WalletToken).where(
                    and_(
                        WalletToken.wallet_id == wallet_id,
                        WalletToken.token_id == token_id
                    )
                )
            )
            wallet_token = wallet_token_result.scalar_one_or_none()
            
            if wallet_token:
                # Update existing balance
                old_balance = wallet_token.balance
                wallet_token.balance = balance
                wallet_token.last_updated = datetime.utcnow()
                
                # Create history record for significant changes
                await self._create_balance_history_if_significant(
                    db, wallet_id, token_id, old_balance, balance, None
                )
            else:
                # Create new balance record (only if balance > 0)
                if balance > 0:
                    wallet_token = WalletToken(
                        wallet_id=wallet_id,
                        token_id=token_id,
                        balance=balance,
                        last_updated=datetime.utcnow()
                    )
                    db.add(wallet_token)
            
        except Exception as e:
            logger.error(f"Error updating TRON wallet token balance: {e}")
    
    async def _create_balance_history_if_significant(self, db: AsyncSession, wallet_id: int, 
                                                   token_id: int, old_balance: float, new_balance: float, transaction_hash: str = None):
        """Create balance history record if change is significant"""
        try:
            change_threshold = self.balance_update_threshold  # Use configured threshold
            min_change_amount = self.min_balance_change  # Use configured minimum change
            
            change_amount = new_balance - old_balance
            
            # Skip if new balance is 0 and old balance was > 0 (likely API error)
            if new_balance == 0.0 and old_balance > 1.0:
                logger.warning(f"Skipping suspicious balance change: {old_balance} -> {new_balance} (likely API error)")
                return
            
            # Skip if change is too small
            if abs(change_amount) < min_change_amount:
                logger.debug(f"Skipping small balance change: {change_amount}")
                return
            
            if (old_balance > 0 and 
                abs(change_amount) / old_balance > change_threshold):
                
                change_percentage = (change_amount / old_balance) * 100 if old_balance > 0 else None
                change_type = 'increase' if change_amount > 0 else 'decrease'
                
                history = BalanceHistory(
                    wallet_id=wallet_id,
                    token_id=token_id,
                    balance_before=old_balance,
                    balance_after=new_balance,
                    change_amount=change_amount,
                    change_percentage=change_percentage,
                    change_type=change_type,
                    transaction_hash=transaction_hash
                )
                db.add(history)
                
                logger.info(f"Created TRON balance history: {change_type} of {abs(change_amount):.6f} ({change_percentage:.2f}%)")
                
                # Send WebSocket notification for significant changes (if enabled)
                if self.enable_notifications:
                    # Get wallet and token info properly
                    wallet = await db.get(Wallet, wallet_id)
                    token = await db.get(Token, token_id)
                    
                    websocket_data = {
                        "type": "balance_update",
                        "data": {
                            "wallet_id": wallet_id,
                            "token_id": token_id,
                            "change_type": change_type,
                            "change_amount": change_amount,
                            "change_percentage": change_percentage,
                            "new_balance": new_balance,
                            "wallet_address": wallet.address if wallet else '',
                            "token_symbol": token.symbol if token else '',
                            "blockchain": "TRON"
                        }
                    }
                    logger.info(f"📡 Sending WebSocket balance update: {websocket_data}")
                    await manager.broadcast(websocket_data)
                
                logger.info("🔄 CRUD cache disabled - no cache invalidation needed")
                
        except Exception as e:
            logger.error(f"Error creating TRON balance history: {e}")
    
    async def _cleanup_zero_balances(self, db: AsyncSession, wallet_id: int, kept_token_ids: set):
        """Remove wallet token records for tokens that are no longer held"""
        try:
            # Find all current wallet tokens
            result = await db.execute(
                select(WalletToken).where(WalletToken.wallet_id == wallet_id)
            )
            all_wallet_tokens = result.scalars().all()
            
            # Remove tokens that are no longer in the balance list
            for wallet_token in all_wallet_tokens:
                if wallet_token.token_id not in kept_token_ids and wallet_token.balance <= 0.000001:
                    await db.delete(wallet_token)
                    logger.debug(f"Removed zero balance for TRON token ID {wallet_token.token_id}")
            
        except Exception as e:
            logger.error(f"Error cleaning up zero balances: {e}")
    
    async def _fetch_wallet_balances(self, wallet_address: str) -> tuple:
        """Fetch both TRX and USDT balances for a wallet"""
        import asyncio
        
        trx_balance, usdt_balance = await asyncio.gather(
            self.tron_service.get_trx_balance(wallet_address),
            self.tron_service.get_usdt_balance(wallet_address),
            return_exceptions=True
        )
        
        # Handle exceptions
        if isinstance(trx_balance, Exception):
            logger.error(f"TRX balance error: {trx_balance}")
            trx_balance = 0.0
        if isinstance(usdt_balance, Exception):
            logger.error(f"USDT balance error: {usdt_balance}")
            usdt_balance = 0.0
            
        return float(trx_balance), float(usdt_balance)

# Global instance
tron_monitor = TronMonitor()
