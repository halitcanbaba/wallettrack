"""
Transaction service - handles transaction-related business logic
"""
from typing import List, Optional
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import Wallet
from app.core.dependencies import eth_service, tron_service, logger
from app.core.config import DUST_FILTER_THRESHOLD
from websocket_manager import manager

class TransactionService:
    
    async def get_all_transactions(self, db: AsyncSession, limit: int = 50, hours: int = 24):
        """Get recent transactions from all wallets within specified hours"""
        try:
            # Calculate cutoff time for "recent" transactions
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            cutoff_timestamp = int(cutoff_time.timestamp())
            
            logger.info(f"Fetching transactions from last {hours} hours (since {cutoff_time.isoformat()})")
            
            # Get all active wallets
            result = await db.execute(
                select(Wallet)
                .options(selectinload(Wallet.blockchain_ref))
                .where(Wallet.is_active == True)
            )
            wallets = result.scalars().all()
            logger.info(f"Found {len(wallets)} active wallets for transactions")
            
            all_transactions = []
            
            # Fetch transactions from all wallets
            for wallet in wallets:
                try:
                    # Increase per-wallet limit significantly to get more historical data
                    wallet_limit = max(200, limit * 2)  # Always fetch at least 200 transactions per wallet
                    transactions = []
                    
                    if wallet.blockchain_ref.name == "ETH":
                        logger.info(f"Getting transactions for ETH wallet: {wallet.address}")
                        transactions = await eth_service.get_wallet_transactions(wallet.address, wallet_limit)
                    elif wallet.blockchain_ref.name == "TRON":
                        logger.info(f"Getting transactions for TRON wallet: {wallet.address} (last {hours}h)")
                        transactions = await tron_service.get_wallet_transactions(wallet.address, wallet_limit, hours)
                    
                    logger.info(f"Got {len(transactions)} transactions for wallet {wallet.address}")
                    
                    # Filter transactions by time and amount
                    for tx in transactions:
                        # Skip transactions with zero or very small amounts
                        amount = tx.get('amount', 0)
                        if not isinstance(amount, (int, float)) or amount <= DUST_FILTER_THRESHOLD:
                            continue
                        
                        # Check if transaction is recent enough
                        tx_timestamp = tx.get('timestamp', 0)
                        if isinstance(tx_timestamp, str):
                            try:
                                # Try to parse ISO string
                                tx_time = datetime.fromisoformat(tx_timestamp.replace('Z', '+00:00'))
                                tx_timestamp = int(tx_time.timestamp())
                            except:
                                continue
                        
                        # Handle timestamp in milliseconds
                        if tx_timestamp > 10000000000:
                            tx_timestamp = tx_timestamp // 1000
                        
                        # Only include transactions from the specified time window
                        if tx_timestamp >= cutoff_timestamp:
                            tx["wallet_id"] = wallet.id
                            tx["wallet_address"] = wallet.address
                            tx["wallet_name"] = wallet.name
                            tx["blockchain"] = wallet.blockchain_ref.name
                            # Ensure timestamp is in seconds for frontend
                            tx["timestamp"] = tx_timestamp
                            all_transactions.append(tx)
                            
                except Exception as e:
                    logger.error(f"Error getting transactions for wallet {wallet.id}: {e}")
                    continue
            
            # Sort all transactions by timestamp (newest first)
            all_transactions.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
            
            recent_count = len(all_transactions[:limit])
            total_count = len(all_transactions)
            
            logger.info(f"Found {total_count} recent transactions (last {hours}h), returning top {recent_count}")
            
            # Send WebSocket notification for new transactions
            if all_transactions:
                await manager.broadcast({
                    "type": "transactions_update",
                    "data": {
                        "transaction_count": len(all_transactions[:limit]),
                        "latest_transactions": all_transactions[:5]  # Send latest 5 for real-time display
                    }
                })
            
            # Return the most recent transactions up to the limit
            return all_transactions[:limit]
            
        except Exception as e:
            logger.error(f"Error getting transactions: {e}")
            raise HTTPException(status_code=500, detail="Error fetching transactions")

    async def get_live_transactions(self, db: AsyncSession, since_timestamp: Optional[int] = None, limit: int = 20):
        """Get new transactions since a given timestamp for real-time updates"""
        try:
            # Get all active wallets
            result = await db.execute(
                select(Wallet)
                .options(selectinload(Wallet.blockchain_ref))
                .where(Wallet.is_active == True)
            )
            wallets = result.scalars().all()
            
            all_new_transactions = []
            
            # If no timestamp provided, get recent transactions from last 5 minutes
            if since_timestamp is None:
                since_timestamp = int((datetime.utcnow() - timedelta(minutes=5)).timestamp())
            
            # Fetch new transactions from all wallets
            for wallet in wallets:
                try:
                    transactions = []
                    
                    if wallet.blockchain_ref.name == "ETH":
                        # Use enhanced ETH transaction method with notifications
                        transactions = await eth_service.get_recent_transactions_with_notifications(
                            wallet.address, wallet.id, since_timestamp
                        )
                    elif wallet.blockchain_ref.name == "TRON":
                        # Use enhanced TRON transaction method with notifications
                        transactions = await tron_service.get_recent_transactions_with_notifications(
                            wallet.address, wallet.id, since_timestamp
                        )
                    
                    # Filter transactions newer than since_timestamp and with meaningful amounts
                    for tx in transactions:
                        tx_timestamp = tx.get('timestamp', 0)
                        amount = tx.get('amount', 0)
                        
                        if (tx_timestamp > since_timestamp and 
                            isinstance(amount, (int, float)) and 
                            amount > DUST_FILTER_THRESHOLD):
                            
                            tx["wallet_id"] = wallet.id
                            tx["wallet_address"] = wallet.address
                            tx["wallet_name"] = wallet.name
                            tx["blockchain"] = wallet.blockchain_ref.name
                            all_new_transactions.append(tx)
                            
                except Exception as e:
                    logger.error(f"Error getting live transactions for wallet {wallet.id}: {e}")
                    continue
            
            # Sort by timestamp (newest first)
            all_new_transactions.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
            
            # If there are new transactions, broadcast via WebSocket
            if all_new_transactions:
                await manager.broadcast({
                    "type": "new_transactions",
                    "data": {
                        "count": len(all_new_transactions),
                        "transactions": all_new_transactions[:10],  # Send top 10 new transactions
                        "timestamp": int(datetime.utcnow().timestamp())
                    }
                })
                
            logger.info(f"Found {len(all_new_transactions)} new transactions since {since_timestamp}")
            
            return {
                "new_transactions": all_new_transactions[:limit],
                "count": len(all_new_transactions),
                "since_timestamp": since_timestamp,
                "current_timestamp": int(datetime.utcnow().timestamp())
            }
            
        except Exception as e:
            logger.error(f"Error getting live transactions: {e}")
            raise HTTPException(status_code=500, detail="Error fetching live transactions")

    async def get_wallet_transactions(self, db: AsyncSession, wallet_id: int, limit: int = 50):
        """Get recent transactions for a wallet"""
        
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
            transactions = []
            
            if wallet.blockchain_ref.name == "ETH":
                # Get transactions from Ethereum service
                transactions = await eth_service.get_wallet_transactions(wallet.address, limit)
            elif wallet.blockchain_ref.name == "TRON":
                # Get transactions from TRON service
                transactions = await tron_service.get_wallet_transactions(wallet.address, limit)
            
            # Filter out zero amount transactions
            filtered_transactions = []
            for tx in transactions:
                amount = tx.get('amount', 0)
                if isinstance(amount, (int, float)) and amount > DUST_FILTER_THRESHOLD:
                    filtered_transactions.append(tx)
            
            # Send WebSocket notification for wallet transactions
            if filtered_transactions:
                await manager.broadcast({
                    "type": "wallet_transactions_update",
                    "data": {
                        "wallet_id": wallet_id,
                        "wallet_address": wallet.address,
                        "blockchain": wallet.blockchain_ref.name,
                        "transaction_count": len(filtered_transactions),
                        "latest_transactions": filtered_transactions[:3]  # Send latest 3 for real-time display
                    }
                })
            
            return {
                "wallet_id": wallet_id,
                "wallet_address": wallet.address,
                "blockchain": wallet.blockchain_ref.name,
                "transactions": filtered_transactions
            }
                
        except Exception as e:
            logger.error(f"Error getting transactions for wallet {wallet_id}: {e}")
            raise HTTPException(status_code=500, detail="Error fetching transactions")

    async def notify_new_transaction(
        self, db: AsyncSession, wallet_address: str, transaction_hash: str, 
        amount: float, token_symbol: str, transaction_type: str
    ):
        """Endpoint for external services to notify about new transactions"""
        try:
            # Find the wallet
            result = await db.execute(
                select(Wallet)
                .options(selectinload(Wallet.blockchain_ref))
                .where(Wallet.address == wallet_address)
            )
            wallet = result.scalar_one_or_none()
            
            if not wallet:
                raise HTTPException(status_code=404, detail="Wallet not found")
            
            # Create transaction notification
            transaction_data = {
                "hash": transaction_hash,
                "amount": amount,
                "token_symbol": token_symbol,
                "type": transaction_type,
                "timestamp": int(datetime.utcnow().timestamp()),
                "wallet_id": wallet.id,
                "wallet_address": wallet.address,
                "wallet_name": wallet.name,
                "blockchain": wallet.blockchain_ref.name
            }
            
            # Broadcast via WebSocket
            await manager.broadcast({
                "type": "transaction_notification",
                "data": {
                    "transaction": transaction_data,
                    "message": f"New {transaction_type} transaction: {amount} {token_symbol}"
                }
            })
            
            logger.info(f"Transaction notification sent for {wallet_address}: {transaction_hash}")
            
            return {"status": "success", "message": "Transaction notification sent"}
            
        except Exception as e:
            logger.error(f"Error sending transaction notification: {e}")
            raise HTTPException(status_code=500, detail="Error sending notification")
