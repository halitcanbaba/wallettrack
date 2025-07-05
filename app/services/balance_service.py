"""
Balance service - handles balance and history-related business logic
"""
from typing import List
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import (
    Blockchain, Token, Wallet, WalletToken, BalanceHistory
)
from app.core.dependencies import eth_service, logger
from app.core.config import CHANGE_THRESHOLD, MIN_CHANGE_AMOUNT
from websocket_manager import manager

class BalanceService:

    async def get_wallet_balance_history(
        self, db: AsyncSession, wallet_id: int, hours: int = 24, days: int = 7
    ):
        """Get balance history for a wallet with enhanced data"""
        
        # Verify wallet exists
        wallet_result = await db.execute(
            select(Wallet)
            .options(selectinload(Wallet.blockchain_ref))
            .where(Wallet.id == wallet_id)
        )
        wallet = wallet_result.scalar_one_or_none()
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")
        
        # Calculate time range - use days if provided, otherwise hours
        if days > 0:
            since = datetime.utcnow() - timedelta(days=days)
        else:
            since = datetime.utcnow() - timedelta(hours=hours)
        
        # Get balance history records
        history_result = await db.execute(
            select(BalanceHistory)
            .options(selectinload(BalanceHistory.token))
            .where(
                and_(
                    BalanceHistory.wallet_id == wallet_id,
                    BalanceHistory.timestamp >= since
                )
            )
            .order_by(BalanceHistory.timestamp.desc())
            .limit(1000)  # Increased limit for historical data
        )
        
        history_records = history_result.scalars().all()
        
        # Get current balances as the latest data point
        current_result = await db.execute(
            select(WalletToken)
            .options(selectinload(WalletToken.token))
            .where(WalletToken.wallet_id == wallet_id)
        )
        
        current_balances = current_result.scalars().all()
        
        # Organize data by token for time series
        token_histories = {}
        
        # Add historical data
        for record in history_records:
            token_symbol = record.token.symbol
            if token_symbol not in token_histories:
                token_histories[token_symbol] = {
                    "token_id": record.token.id,
                    "token_symbol": token_symbol,
                    "token_name": record.token.name,
                    "data_points": []
                }
            
            token_histories[token_symbol]["data_points"].append({
                "timestamp": record.timestamp.isoformat(),
                "balance_before": record.balance_before,
                "balance_after": record.balance_after,
                "change_amount": record.change_amount,
                "change_percentage": record.change_percentage,
                "change_type": record.change_type,
                "transaction_hash": record.transaction_hash
            })
        
        # Add current balances as latest data points
        for current_balance in current_balances:
            if current_balance.balance > 0:
                token_symbol = current_balance.token.symbol
                if token_symbol not in token_histories:
                    token_histories[token_symbol] = {
                        "token_id": current_balance.token.id,
                        "token_symbol": token_symbol,
                        "token_name": current_balance.token.name,
                        "data_points": []
                    }
                
                # Add current balance as latest point
                token_histories[token_symbol]["data_points"].insert(0, {
                    "timestamp": current_balance.last_updated.isoformat(),
                    "balance_before": current_balance.balance,
                    "balance_after": current_balance.balance,
                    "change_amount": 0,
                    "change_percentage": 0,
                    "change_type": "current",
                    "transaction_hash": None
                })
        
        # Sort data points by timestamp for each token
        for token_data in token_histories.values():
            token_data["data_points"].sort(key=lambda x: x["timestamp"], reverse=True)
        
        # Create summary statistics
        total_tokens = len(token_histories)
        total_changes = sum(len(token_data["data_points"]) for token_data in token_histories.values())
        
        return {
            "wallet_id": wallet_id,
            "wallet_address": wallet.address,
            "wallet_name": wallet.name,
            "blockchain": wallet.blockchain_ref.name,
            "time_range": {
                "since": since.isoformat(),
                "hours": hours if days == 0 else days * 24,
                "days": days
            },
            "summary": {
                "total_tokens": total_tokens,
                "total_changes": total_changes,
                "period": f"{days} days" if days > 0 else f"{hours} hours"
            },
            "token_histories": list(token_histories.values())
        }

    async def get_all_wallets_history(self, db: AsyncSession, days: int = 7, hours: int = 0):
        """Get balance history for all wallets"""
        try:
            # Get all active wallets
            wallets_result = await db.execute(
                select(Wallet)
                .options(selectinload(Wallet.blockchain_ref))
                .where(Wallet.is_active == True)
            )
            wallets = wallets_result.scalars().all()
            
            all_histories = []
            
            # Get history for each wallet
            for wallet in wallets:
                # Calculate time range
                if days > 0:
                    since = datetime.utcnow() - timedelta(days=days)
                else:
                    since = datetime.utcnow() - timedelta(hours=hours or 24)
                
                # Get balance history for this wallet
                history_result = await db.execute(
                    select(BalanceHistory)
                    .options(selectinload(BalanceHistory.token))
                    .where(
                        and_(
                            BalanceHistory.wallet_id == wallet.id,
                            BalanceHistory.timestamp >= since
                        )
                    )
                    .order_by(BalanceHistory.timestamp.desc())
                    .limit(100)
                )
                
                history_records = history_result.scalars().all()
                
                # Get current balances
                current_result = await db.execute(
                    select(WalletToken)
                    .options(selectinload(WalletToken.token))
                    .where(WalletToken.wallet_id == wallet.id)
                )
                
                current_balances = current_result.scalars().all()
                
                # Format wallet history
                wallet_history = {
                    "wallet_id": wallet.id,
                    "wallet_address": wallet.address,
                    "wallet_name": wallet.name,
                    "blockchain": wallet.blockchain_ref.name,
                    "current_tokens": len([b for b in current_balances if b.balance > 0]),
                    "total_changes": len(history_records),
                    "recent_changes": []
                }
                
                # Add recent balance changes
                for record in history_records[:10]:  # Last 10 changes
                    wallet_history["recent_changes"].append({
                        "timestamp": record.timestamp.isoformat(),
                        "token_symbol": record.token.symbol,
                        "balance_before": record.balance_before,
                        "balance_after": record.balance_after,
                        "change_amount": record.change_amount,
                        "change_percentage": record.change_percentage,
                        "change_type": record.change_type
                    })
                
                all_histories.append(wallet_history)
            
            return {
                "period": f"{days} days" if days > 0 else f"{hours or 24} hours",
                "total_wallets": len(wallets),
                "summary": {
                    "total_wallets": len(wallets),
                    "total_tokens": sum(wallet_history["current_tokens"] for wallet_history in all_histories),
                    "total_changes": sum(wallet_history["total_changes"] for wallet_history in all_histories),
                    "period": f"{days} days" if days > 0 else f"{hours or 24} hours"
                },
                "wallets": all_histories
            }
            
        except Exception as e:
            logger.error(f"Error getting all wallets history: {e}")
            raise HTTPException(status_code=500, detail="Error fetching wallet histories")

    async def update_wallet_balances(self, db: AsyncSession, wallet_id: int, balances: dict, blockchain_name: str):
        """Update wallet balances in the new schema (simple version)"""
        try:
            # Get blockchain ID
            blockchain_result = await db.execute(
                select(Blockchain).where(Blockchain.name == blockchain_name)
            )
            blockchain = blockchain_result.scalar_one_or_none()
            if not blockchain:
                return
            
            for token_symbol, balance in balances.items():
                if balance <= 0:
                    continue
                    
                # Find existing token
                token_result = await db.execute(
                    select(Token).where(
                        and_(
                            Token.symbol == token_symbol,
                            Token.blockchain_id == blockchain.id
                        )
                    )
                )
                token = token_result.scalar_one_or_none()
                
                if not token:
                    # Create basic token record
                    token = Token(
                        symbol=token_symbol,
                        name=token_symbol,  # Use symbol as name for now
                        blockchain_id=blockchain.id,
                        is_verified=eth_service.is_legitimate_token(token_symbol) if blockchain_name == "ETH" else True
                    )
                    db.add(token)
                    await db.flush()
                
                # Update or create wallet token balance
                await self.update_single_wallet_token(db, wallet_id, token.id, balance)
            
            # Update wallet last_updated
            wallet_result = await db.execute(select(Wallet).where(Wallet.id == wallet_id))
            wallet = wallet_result.scalar_one_or_none()
            if wallet:
                wallet.last_updated = datetime.utcnow()
            
            await db.commit()
            
            # Send WebSocket notification
            await manager.broadcast({
                "type": "balance_update",
                "data": {
                    "wallet_id": wallet_id,
                    "balances": balances
                }
            })
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error updating wallet balances: {e}")

    async def update_wallet_balances_with_tokens(
        self, db: AsyncSession, wallet_id: int, balances: dict, token_info_list: list, blockchain_name: str
    ):
        """Update wallet balances with detailed token information"""
        try:
            # Get blockchain ID
            blockchain_result = await db.execute(
                select(Blockchain).where(Blockchain.name == blockchain_name)
            )
            blockchain = blockchain_result.scalar_one_or_none()
            if not blockchain:
                return
            
            # Create a mapping of token symbols to their detailed info
            token_info_map = {token_info['symbol']: token_info for token_info in token_info_list}
            
            for token_symbol, balance in balances.items():
                if balance <= 0:
                    continue
                    
                # Get detailed token info
                token_info = token_info_map.get(token_symbol, {})
                contract_address = token_info.get('contract')
                token_name = token_info.get('name', token_symbol)
                decimals = token_info.get('decimals', 18)
                
                # Find existing token by symbol and blockchain first
                token_result = await db.execute(
                    select(Token).where(
                        and_(
                            Token.symbol == token_symbol,
                            Token.blockchain_id == blockchain.id
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
                                Token.blockchain_id == blockchain.id
                            )
                        )
                    )
                    token = token_result.scalar_one_or_none()
                
                if not token:
                    # Create new token with detailed information
                    is_native = token_symbol in ['ETH', 'TRX', 'BNB']  # Native tokens
                    token = Token(
                        symbol=token_symbol,
                        name=token_name,
                        contract_address=contract_address,
                        decimals=decimals,
                        blockchain_id=blockchain.id,
                        is_native=is_native,
                        is_verified=eth_service.is_legitimate_token(token_symbol, contract_address) if blockchain_name == "ETH" else True
                    )
                    db.add(token)
                    await db.flush()
                else:
                    # Update existing token with missing information
                    if not token.contract_address and contract_address:
                        token.contract_address = contract_address
                    if token.name == token.symbol and token_name != token_symbol:
                        token.name = token_name
                    if token.decimals == 18 and decimals != 18:
                        token.decimals = decimals
                
                # Update wallet token balance
                await self.update_single_wallet_token(db, wallet_id, token.id, balance)
            
            # Update wallet last_updated
            wallet_result = await db.execute(select(Wallet).where(Wallet.id == wallet_id))
            wallet = wallet_result.scalar_one_or_none()
            if wallet:
                wallet.last_updated = datetime.utcnow()
            
            await db.commit()
            
            # Send WebSocket notification
            await manager.broadcast({
                "type": "balance_update",
                "data": {
                    "wallet_id": wallet_id,
                    "balances": balances
                }
            })
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error updating wallet balances with tokens: {e}")

    async def update_single_wallet_token(self, db: AsyncSession, wallet_id: int, token_id: int, balance: float):
        """Update a single wallet token balance and create history if significant change"""
        
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
            if (old_balance > 0 and 
                abs(balance - old_balance) > MIN_CHANGE_AMOUNT and
                abs(balance - old_balance) / old_balance > CHANGE_THRESHOLD):
                
                history = BalanceHistory(
                    wallet_id=wallet_id,
                    token_id=token_id,
                    balance_before=old_balance,
                    balance_after=balance,
                    change_amount=balance - old_balance,
                    change_percentage=((balance - old_balance) / old_balance) * 100 if old_balance > 0 else None,
                    change_type='increase' if balance > old_balance else 'decrease'
                )
                db.add(history)
        else:
            # Create new balance record
            wallet_token = WalletToken(
                wallet_id=wallet_id,
                token_id=token_id,
                balance=balance,
                last_updated=datetime.utcnow()
            )
            db.add(wallet_token)
