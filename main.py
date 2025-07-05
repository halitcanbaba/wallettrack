import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, desc, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

# Load environment variables
load_dotenv()

# Import database models
from database import init_db, get_db, seed_initial_data
from database import Blockchain, Token, Wallet, WalletToken, BalanceHistory
from schemas import (
    WalletCreate, WalletResponse, WalletWithBalances, TokenBalance, 
    BlockchainResponse, TokenResponse, WalletTokenResponse,
    LegacyWalletCreate, LegacyWalletResponse, LegacyTokenBalance  # For backward compatibility
)
from tron_service import monitor as tron_monitor, TronGridClient
from eth_service import EthereumService
from eth_monitor import ethereum_monitor
from websocket_manager import manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize services
eth_service = EthereumService(use_v2_api=True)
tron_service = TronGridClient()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Multi-Blockchain Wallet Monitor...")
    await init_db()
    await seed_initial_data()
    tron_monitor.start_monitoring()
    await ethereum_monitor.start_monitoring()
    logger.info("Application started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Wallet Monitor...")
    await tron_monitor.close()
    await ethereum_monitor.stop_monitoring()
    await eth_service.close()
    await tron_service.close()
    logger.info("Application shutdown complete")

app = FastAPI(
    title="WalletTrack - Multi-Blockchain Wallet Monitor",
    description="Advanced cryptocurrency wallet monitoring with scam token filtering",
    version="2.0.0",
    lifespan=lifespan
)

# Templates
templates = Jinja2Templates(directory="templates")

# Static files
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except Exception:
    logger.warning("Static directory not found, continuing without static files")

# Root endpoint
@app.get("/")
async def read_root(request: Request):
    """Serve the main dashboard"""
    return templates.TemplateResponse("index_clean.html", {"request": request})

@app.get("/history")
async def history_page(request: Request):
    """Serve the balance history page"""
    return templates.TemplateResponse("history.html", {"request": request})

# Dashboard endpoints
@app.get("/v2")
async def dashboard_v2(request: Request):
    """Serve the new v2 dashboard"""
    return templates.TemplateResponse("dashboard_v2.html", {"request": request})

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.get("/api/config")
async def get_frontend_config():
    """Get frontend configuration"""
    return {
        "websocket": {
            "host": os.getenv("WEBSOCKET_HOST", "localhost"),
            "port": int(os.getenv("WEBSOCKET_PORT", "8000")),
            "protocol": os.getenv("WEBSOCKET_PROTOCOL", "ws")
        },
        "frontend": {
            "refresh_interval": int(os.getenv("FRONTEND_REFRESH_INTERVAL", "30000")),
            "transaction_refresh_interval": int(os.getenv("TRANSACTION_REFRESH_INTERVAL", "60000")),
            "max_transactions_display": int(os.getenv("MAX_TRANSACTIONS_DISPLAY", "20"))
        }
    }

# =====================================================
# BLOCKCHAIN ENDPOINTS
# =====================================================

@app.get("/api/blockchains", response_model=List[BlockchainResponse])
async def get_blockchains(db: AsyncSession = Depends(get_db)):
    """Get all supported blockchains"""
    result = await db.execute(select(Blockchain).where(Blockchain.is_active == True))
    blockchains = result.scalars().all()
    return blockchains

# =====================================================
# WALLET MANAGEMENT ENDPOINTS
# =====================================================

@app.post("/api/wallets", response_model=WalletResponse)
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
    asyncio.create_task(fetch_initial_balances(wallet.id, wallet.address, blockchain.name))
    
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

@app.get("/api/wallets", response_model=List[WalletWithBalances])
async def get_wallets(db: AsyncSession = Depends(get_db)):
    """Get all monitored wallets with their current balances"""
    
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
            if wallet_token.balance > 0:  # Only show positive balances
                balance = TokenBalance(
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
    
    return wallet_list

@app.get("/api/wallets/{wallet_id}", response_model=WalletWithBalances)
async def get_wallet(wallet_id: int, db: AsyncSession = Depends(get_db)):
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
        if wallet_token.balance > 0:
            balance = TokenBalance(
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

@app.delete("/api/wallets/{wallet_id}")
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

# =====================================================
# BALANCE HISTORY ENDPOINTS  
# =====================================================

@app.get("/api/wallets/{wallet_id}/history")
async def get_balance_history(
    wallet_id: int,
    hours: int = 24,
    days: int = 7,
    db: AsyncSession = Depends(get_db)
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

@app.get("/api/wallets/history/all")
async def get_all_wallets_history(
    days: int = 7,
    hours: int = 0,
    db: AsyncSession = Depends(get_db)
):
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

# =====================================================
# BALANCE AND TRANSACTION ENDPOINTS
# =====================================================

@app.post("/api/wallets/{wallet_id}/refresh")
async def refresh_wallet_balances(wallet_id: int, db: AsyncSession = Depends(get_db)):
    """Manually refresh balances for a specific wallet"""
    
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
        if wallet.blockchain_ref.name == "ETH":
            # Get fresh balances from Ethereum
            balances = await eth_service.get_wallet_balances(wallet.address)
            # Get detailed token information
            discovered_tokens = await eth_service.discover_wallet_tokens(wallet.address)
            await update_wallet_balances_with_tokens(db, wallet_id, balances, discovered_tokens, "ETH")
            
        elif wallet.blockchain_ref.name == "TRON":
            # TRON refresh will be handled by tron_service
            # For now, just update the timestamp
            wallet.last_updated = datetime.utcnow()
            await db.commit()
        
        return {"status": "success", "message": "Balances refreshed successfully"}
        
    except Exception as e:
        logger.error(f"Error refreshing balances for wallet {wallet_id}: {e}")
        raise HTTPException(status_code=500, detail="Error refreshing balances")

@app.get("/api/wallets/{wallet_id}/transactions")
async def get_wallet_transactions(
    wallet_id: int, 
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
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
            if isinstance(amount, (int, float)) and amount > 0.000001:  # Filter out dust transactions
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

@app.get("/api/wallets/{wallet_id}/balance-history")
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

# =====================================================
# TOKEN DISCOVERY ENDPOINTS  
# =====================================================

@app.get("/api/tokens")
async def get_tokens(
    blockchain_id: Optional[int] = None,
    verified_only: bool = True,
    db: AsyncSession = Depends(get_db)
):
    """Get available tokens, optionally filtered by blockchain"""
    
    query = select(Token).options(selectinload(Token.blockchain_ref))
    
    if blockchain_id:
        query = query.where(Token.blockchain_id == blockchain_id)
    
    if verified_only:
        query = query.where(Token.is_verified == True)
    
    query = query.order_by(Token.symbol)
    
    result = await db.execute(query)
    tokens = result.scalars().all()
    
    token_list = []
    for token in tokens:
        token_response = TokenResponse(
            id=token.id,
            symbol=token.symbol,
            name=token.name,
            contract_address=token.contract_address,
            decimals=token.decimals,
            blockchain_id=token.blockchain_id,
            is_native=token.is_native,
            is_verified=token.is_verified,
            created_at=token.created_at,
            blockchain=BlockchainResponse(
                id=token.blockchain_ref.id,
                name=token.blockchain_ref.name,
                display_name=token.blockchain_ref.display_name,
                native_symbol=token.blockchain_ref.native_symbol,
                is_active=token.blockchain_ref.is_active,
                created_at=token.blockchain_ref.created_at
            )
        )
        token_list.append(token_response)
    
    return token_list

@app.get("/api/transactions")
async def get_all_transactions(
    limit: int = 50,
    hours: int = 24,  # Filter transactions from last N hours
    db: AsyncSession = Depends(get_db)
):
    """Get recent transactions from all wallets within specified hours"""
    try:
        # Calculate cutoff time for "recent" transactions
        from datetime import datetime, timedelta
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
                    if not isinstance(amount, (int, float)) or amount <= 0.000001:
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

# =====================================================
# REAL-TIME TRANSACTION MONITORING
# =====================================================

@app.get("/api/transactions/live")
async def get_live_transactions(
    since_timestamp: Optional[int] = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
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
                        amount > 0.000001):
                        
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

@app.post("/api/transactions/notify")
async def notify_new_transaction(
    wallet_address: str,
    transaction_hash: str,
    amount: float,
    token_symbol: str,
    transaction_type: str,
    db: AsyncSession = Depends(get_db)
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

# =====================================================
# SYSTEM STATUS AND SUMMARY ENDPOINTS
# =====================================================

@app.get("/api/status")
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
        "version": "2.0.0",
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

@app.get("/api/summary")
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

# =====================================================
# LEGACY API ENDPOINTS (for backward compatibility)
# ====================================================

@app.post("/api/wallets/legacy", response_model=LegacyWalletResponse)
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

# =====================================================
# UTILITY FUNCTIONS
# =====================================================

async def fetch_initial_balances(wallet_id: int, address: str, blockchain_name: str):
    """Fetch initial balances for a new wallet"""
    try:
        async with AsyncSessionLocal() as db:
            if blockchain_name == "ETH":
                # Get Ethereum balances with detailed token info
                balances = await eth_service.get_wallet_balances(address)
                # Get detailed token information
                discovered_tokens = await eth_service.discover_wallet_tokens(address)
                await update_wallet_balances_with_tokens(db, wallet_id, balances, discovered_tokens, blockchain_name)
            elif blockchain_name == "TRON":
                # TRON balances will be handled by existing tron_service monitor
                pass
    except Exception as e:
        logger.error(f"Error fetching initial balances for {address}: {e}")

async def update_wallet_balances(db: AsyncSession, wallet_id: int, balances: dict, blockchain_name: str):
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
            await update_single_wallet_token(db, wallet_id, token.id, balance)
        
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

async def update_wallet_balances_with_tokens(db: AsyncSession, wallet_id: int, balances: dict, token_info_list: list, blockchain_name: str):
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
            await update_single_wallet_token(db, wallet_id, token.id, balance)
        
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

async def update_single_wallet_token(db: AsyncSession, wallet_id: int, token_id: int, balance: float):
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
        change_threshold = 0.01  # 1% change threshold
        min_change_amount = 0.001  # Minimum change amount to record
        
        if (old_balance > 0 and 
            abs(balance - old_balance) > min_change_amount and
            abs(balance - old_balance) / old_balance > change_threshold):
            
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

# =====================================================
# WEBSOCKET ENDPOINT
# =====================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Enhanced WebSocket endpoint for real-time updates"""
    await manager.connect(websocket)
    logger.info(f"WebSocket client connected from {websocket.client}")
    
    try:
        # Send initial connection message
        await websocket.send_json({
            "type": "connection_established",
            "data": {
                "message": "Connected to WalletTrack Pro v2",
                "timestamp": datetime.utcnow().isoformat(),
                "server_version": "2.0.0"
            }
        })
        
        # Send initial status
        await websocket.send_json({
            "type": "system_status", 
            "data": {
                "wallets_count": await get_wallets_count(),
                "active_connections": manager.get_connection_count()
            }
        })
        
        while True:
            try:
                # Wait for client messages with timeout
                message = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                
                try:
                    data = json.loads(message) if message else {}
                    await handle_client_message(websocket, data)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON received: {message}")
                    
            except asyncio.TimeoutError:
                # Send heartbeat
                try:
                    await websocket.send_json({
                        "type": "heartbeat",
                        "data": {
                            "timestamp": datetime.utcnow().isoformat(),
                            "active_connections": manager.get_connection_count()
                        }
                    })
                except Exception as heartbeat_error:
                    logger.warning(f"Heartbeat failed: {heartbeat_error}")
                    break
                    
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected normally")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        manager.disconnect(websocket)

async def handle_client_message(websocket: WebSocket, data: dict):
    """Handle messages from WebSocket clients"""
    message_type = data.get("type")
    
    if message_type == "ping":
        await websocket.send_json({
            "type": "pong",
            "data": {"timestamp": datetime.utcnow().isoformat()}
        })
    elif message_type == "request_wallet_update":
        wallet_id = data.get("wallet_id")
        if wallet_id:
            # Trigger wallet update
            await websocket.send_json({
                "type": "wallet_update_requested",
                "data": {"wallet_id": wallet_id}
            })
    elif message_type == "request_status":
        # Send current system status
        await websocket.send_json({
            "type": "system_status",
            "data": {
                "wallets_count": await get_wallets_count(),
                "active_connections": manager.get_connection_count(),
                "timestamp": datetime.utcnow().isoformat()
            }
        })

async def get_wallets_count() -> int:
    """Get current wallet count"""
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(func.count(Wallet.id)).where(Wallet.is_active == True)
            )
            return result.scalar() or 0
    except Exception:
        return 0

# Import AsyncSessionLocal for background tasks
from database import AsyncSessionLocal

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
