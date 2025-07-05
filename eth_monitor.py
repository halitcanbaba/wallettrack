import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import AsyncSessionLocal, Blockchain, Token, Wallet, WalletToken, BalanceHistory
from eth_service import EthereumService
from websocket_manager import manager

logger = logging.getLogger(__name__)

class EthereumMonitor:
    def __init__(self, check_interval: int = None):
        # Load check interval from environment
        self.check_interval = check_interval or int(os.getenv('BALANCE_CHECK_INTERVAL', '60'))
        self.eth_service = EthereumService(use_v2_api=True)
        self.is_running = False
        self.task = None
        
        logger.info(f"ETH Monitor initialized with check interval: {self.check_interval}s")
        
    async def start_monitoring(self):
        """Start the background monitoring task"""
        if not self.is_running:
            self.is_running = True
            self.task = asyncio.create_task(self._monitoring_loop())
            logger.info("Starting Ethereum balance monitoring loop...")
    
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
            await self.eth_service.close()
            logger.info("Stopped Ethereum balance monitoring")
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.is_running:
            try:
                await self._check_all_ethereum_wallets()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in Ethereum monitoring loop: {e}")
                await asyncio.sleep(30)  # Short delay before retrying
    
    async def _check_all_ethereum_wallets(self):
        """Check all Ethereum wallets for balance updates"""
        async with AsyncSessionLocal() as db:
            try:
                # Get all active Ethereum wallets
                result = await db.execute(
                    select(Wallet)
                    .join(Blockchain)
                    .where(
                        and_(
                            Wallet.is_active == True,
                            Blockchain.name == "ETH"
                        )
                    )
                    .options(selectinload(Wallet.blockchain_ref))
                )
                
                eth_wallets = result.scalars().all()
                logger.info(f"Monitoring {len(eth_wallets)} Ethereum wallets...")
                
                for wallet in eth_wallets:
                    try:
                        await self._update_wallet_balances(db, wallet)
                        
                        # Also check for new transactions (every other cycle to reduce load)
                        import time
                        current_cycle = int(time.time() / self.check_interval)
                        if current_cycle % 2 == 0:  # Every other cycle
                            try:
                                # Get transactions from last cycle
                                since_timestamp = int(time.time() - (self.check_interval * 2))
                                new_transactions = await self.eth_service.get_recent_transactions_with_notifications(
                                    wallet.address, wallet.id, since_timestamp
                                )
                                if new_transactions:
                                    logger.info(f"Found {len(new_transactions)} new ETH transactions for wallet {wallet.id}")
                            except Exception as tx_error:
                                logger.error(f"Error checking ETH transactions for wallet {wallet.id}: {tx_error}")
                        
                        # Small delay between wallets to avoid rate limiting
                        await asyncio.sleep(5)
                    except Exception as e:
                        logger.error(f"Error updating wallet {wallet.address}: {e}")
                
            except Exception as e:
                logger.error(f"Error in _check_all_ethereum_wallets: {e}")
    
    async def _update_wallet_balances(self, db: AsyncSession, wallet: Wallet):
        """Update balances for a single Ethereum wallet"""
        try:
            # Skip if wallet was updated recently (less than 1 hour ago)
            if wallet.last_updated:
                time_since_update = datetime.utcnow() - wallet.last_updated
                if time_since_update < timedelta(hours=1):
                    logger.debug(f"Skipping {wallet.address} - updated {time_since_update} ago")
                    return
            
            logger.info(f"Updating balances for Ethereum wallet: {wallet.address}")
            
            # Get current balances from Ethereum network
            balances = await self.eth_service.get_wallet_balances(wallet.address)
            discovered_tokens = await self.eth_service.discover_wallet_tokens(wallet.address)
            
            # Update balances in database
            await self._update_wallet_balances_in_db(db, wallet.id, balances, discovered_tokens)
            
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
                logger.info(f"Updated Ethereum wallet {wallet.address}: {balance_str}")
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error updating wallet {wallet.address}: {e}")
    
    async def _update_wallet_balances_in_db(self, db: AsyncSession, wallet_id: int, balances: Dict[str, float], token_info_list: List[Dict]):
        """Update wallet balances in database with detailed token information"""
        try:
            # Get Ethereum blockchain ID
            blockchain_result = await db.execute(
                select(Blockchain).where(Blockchain.name == "ETH")
            )
            blockchain = blockchain_result.scalar_one_or_none()
            if not blockchain:
                return
            
            # Create a mapping of token symbols to their detailed info
            token_info_map = {token_info['symbol']: token_info for token_info in token_info_list}
            
            # Track which tokens have been updated (for cleanup)
            updated_token_ids = set()
            
            for token_symbol, balance in balances.items():
                # Get detailed token info
                token_info = token_info_map.get(token_symbol, {})
                contract_address = token_info.get('contract')
                token_name = token_info.get('name', token_symbol)
                decimals = token_info.get('decimals', 18)
                
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
                is_native = symbol in ['ETH', 'TRX', 'BNB']
                token = Token(
                    symbol=symbol,
                    name=name,
                    contract_address=contract_address,
                    decimals=decimals,
                    blockchain_id=blockchain_id,
                    is_native=is_native,
                    is_verified=self.eth_service.is_legitimate_token(symbol, contract_address)
                )
                db.add(token)
                await db.flush()
                logger.info(f"Created new token: {symbol} ({contract_address})")
            else:
                # Update existing token with missing information
                updated = False
                if not token.contract_address and contract_address:
                    token.contract_address = contract_address
                    updated = True
                if token.name == token.symbol and name != symbol:
                    token.name = name
                    updated = True
                if token.decimals == 18 and decimals != 18:
                    token.decimals = decimals
                    updated = True
                
                if updated:
                    logger.debug(f"Updated token info for {symbol}")
            
            return token
            
        except Exception as e:
            logger.error(f"Error finding/creating token {symbol}: {e}")
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
            logger.error(f"Error updating wallet token balance: {e}")
    
    async def _create_balance_history_if_significant(self, db: AsyncSession, wallet_id: int, 
                                                   token_id: int, old_balance: float, new_balance: float, transaction_hash: str = None):
        """Create balance history record if change is significant"""
        try:
            change_threshold = 0.02  # 2% change threshold
            min_change_amount = 0.001  # Minimum change amount to record
            
            change_amount = new_balance - old_balance
            
            if (old_balance > 0 and 
                abs(change_amount) > min_change_amount and
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
                
                logger.info(f"Created balance history: {change_type} of {abs(change_amount):.6f} ({change_percentage:.2f}%)")
                
                # Send WebSocket notification for significant changes
                await manager.broadcast({
                    "type": "balance_update",
                    "data": {
                        "wallet_id": wallet_id,
                        "token_id": token_id,
                        "change_type": change_type,
                        "change_amount": change_amount,
                        "change_percentage": change_percentage,
                        "new_balance": new_balance,
                        "wallet_address": getattr(await db.get(Wallet, wallet_id), 'address', ''),
                        "token_symbol": getattr(await db.get(Token, token_id), 'symbol', '')
                    }
                })
                
        except Exception as e:
            logger.error(f"Error creating balance history: {e}")
    
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
                    logger.debug(f"Removed zero balance for token ID {wallet_token.token_id}")
            
        except Exception as e:
            logger.error(f"Error cleaning up zero balances: {e}")

# Global instance
ethereum_monitor = EthereumMonitor()
