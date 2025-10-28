import asyncio
import base58
import hashlib
import logging
import os
import time
from datetime import datetime
from typing import List, Optional, Dict
from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tronpy import Tron
from tronpy.exceptions import AddressNotFound

from database import get_db, Wallet, WalletToken, Token, Blockchain, BalanceHistory
from websocket_manager import manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class BalanceCache:
    trx_balance: float
    usdt_balance: float
    timestamp: float

class TronGridClient:
    """Client for interacting with TronGrid API"""
    
    def __init__(self):
        self.base_url = "https://api.trongrid.io"
        
        # Get API key from environment
        self.api_key = os.getenv('TRONGRID_API_KEY')
        
        # Set up headers with API key
        headers = {}
        if self.api_key:
            headers['TRON-PRO-API-KEY'] = self.api_key
            logger.info(f"TronGrid API Key configured: {self.api_key[:8]}...")
        else:
            logger.warning("TronGrid API Key not found in environment variables")
        
        self.client = httpx.AsyncClient(timeout=30.0, headers=headers)
        self.tron = Tron(network='mainnet')
        
        # USDT TRC20 contract
        self.usdt_contract_address = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
        
        # Rate limiting - from environment variables
        self.last_request_time = 0
        self.min_request_interval = float(os.getenv('TRON_MIN_REQUEST_INTERVAL', '1.5'))
        self.max_retries = int(os.getenv('TRON_MAX_RETRIES', '3'))
        self.retry_delay = int(os.getenv('TRON_RETRY_DELAY', '5'))
        self.rate_limit_enabled = os.getenv('TRON_RATE_LIMIT_ENABLED', 'true').lower() == 'true'
        
        # Balance cache for faster consecutive requests
        self.balance_cache: Dict[str, BalanceCache] = {}
        self.cache_ttl = 30  # Cache valid for 30 seconds
        
        logger.info(f"TRON Rate Limiting: interval={self.min_request_interval}s, retries={self.max_retries}, enabled={self.rate_limit_enabled}")
    
    async def get_trx_balance(self, address: str) -> float:
        """Get TRX balance for an address"""
        try:
            url = f"{self.base_url}/v1/accounts/{address}"
            response = await self._make_request_with_retry('GET', url)
            
            if response is None:
                return 0.0
            
            data = response.json()
            if 'data' in data and len(data['data']) > 0:
                balance_sun = data['data'][0].get('balance', 0)
                # Convert from SUN to TRX (1 TRX = 1,000,000 SUN)
                return balance_sun / 1_000_000
            return 0.0
        except Exception as e:
            logger.error(f"Error fetching TRX balance for {address}: {e}")
            return 0.0
    
    async def get_usdt_balance(self, address: str) -> float:
        """Get USDT (TRC20) balance for an address"""
        try:
            # Method 1: Try using TronGrid API directly (primary method)
            balance = await self._get_usdt_via_api(address)
            if balance > 0:
                return balance
                
            # Method 2: Try using contract call (fallback)
            return await self._get_usdt_via_contract(address)
            
        except Exception as e:
            logger.error(f"Error fetching USDT balance for {address}: {e}")
            return 0.0
    
    async def _get_usdt_via_api(self, address: str) -> float:
        """Get USDT balance using TronGrid API"""
        try:
            # Use TronGrid API account endpoint which includes TRC20 balances
            url = f"{self.base_url}/v1/accounts/{address}"
            
            response = await self._make_request_with_retry('GET', url)
            if response and response.status_code == 200:
                data = response.json()
                
                # Check if the response is successful and contains data
                if data.get('success') and 'data' in data and data['data']:
                    account_data = data['data'][0]
                    
                    # Check TRC20 tokens in the account data
                    if 'trc20' in account_data:
                        for token_data in account_data['trc20']:
                            if token_data.get(self.usdt_contract_address):
                                balance_str = token_data[self.usdt_contract_address]
                                try:
                                    balance = float(balance_str) / 1_000_000
                                    logger.info(f"USDT balance (TronGrid) for {address}: {balance}")
                                    return balance
                                except (ValueError, TypeError):
                                    logger.warning(f"Invalid USDT balance format: {balance_str}")
                                    continue
                    
                    # If no USDT balance found, return 0
                    logger.debug(f"No USDT tokens found for {address}")
                    return 0.0
                else:
                    logger.warning(f"TronGrid API returned invalid data for {address}")
                    return 0.0
            else:
                logger.warning(f"TronGrid API failed for {address}")
                return 0.0
            
        except Exception as e:
            logger.error(f"TronGrid API method failed for USDT balance {address}: {e}")
            return 0.0
    
    async def _get_usdt_via_contract(self, address: str) -> float:
        """Get USDT balance using smart contract call"""
        try:
            # Primary method - TronScan API (most reliable)
            tronscan_url = "https://apilist.tronscan.org/api/account"
            params = {
                "address": address
            }
            
            response = await self._make_request_with_retry('GET', tronscan_url, params=params)
            if response and response.status_code == 200:
                data = response.json()
                
                # Check TRC20 tokens
                if 'trc20token_balances' in data and data['trc20token_balances']:
                    for token in data['trc20token_balances']:
                        if token.get('tokenId') == self.usdt_contract_address:
                            balance_str = token.get('balance', '0')
                            try:
                                balance = float(balance_str) / 1_000_000
                                logger.debug(f"USDT balance (TronScan) for {address}: {balance}")
                                return balance
                            except (ValueError, TypeError):
                                logger.warning(f"Invalid USDT balance format: {balance_str}")
                                continue
                
                # If no USDT balance found, return 0 (don't try fallback to avoid more rate limits)
                logger.debug(f"No USDT tokens found for {address}")
                return 0.0
            
            # If TronScan API fails, return 0 instead of trying fallback to avoid rate limits
            logger.warning(f"TronScan API failed for {address}, returning 0 USDT to avoid rate limits")
            return 0.0
            
        except Exception as e:
            logger.error(f"TronScan method failed for USDT balance {address}: {e}")
            # Return 0 instead of trying fallback during rate limiting
            return 0.0
    
    async def _get_usdt_contract_fallback(self, address: str) -> float:
        """Fallback contract method"""
        try:
            # Simple contract call without tronpy conversion
            url = f"{self.base_url}/wallet/triggerconstantcontract"
            
            # Convert T address to hex manually (simplified)
            if address.startswith('T'):
                # This is a basic conversion - for production use proper base58 decode
                address_hex = "41" + address[1:].encode().hex()
            else:
                address_hex = address
                
            contract_data = {
                "owner_address": "410000000000000000000000000000000000000000",
                "contract_address": "41a614f803b6fd780986a42c78ec9c7f77e6ded13c",  # USDT contract in hex
                "function_selector": "balanceOf(address)",
                "parameter": f"000000000000000000000000{address_hex[2:]}".ljust(64, '0')
            }
            
            response = await self._make_request_with_retry('POST', url, json=contract_data)
            if response.status_code == 200:
                data = response.json()
                if 'constant_result' in data and data['constant_result']:
                    hex_balance = data['constant_result'][0]
                    if hex_balance and hex_balance != '0':
                        balance = int(hex_balance, 16) / 1_000_000
                        logger.info(f"USDT balance (contract fallback) for {address}: {balance}")
                        return balance
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Contract fallback failed for USDT balance {address}: {e}")
            return 0.0
    
    async def get_wallet_transactions(self, address: str, limit: int = 50, hours: int = None) -> list:
        """Get recent transactions for a wallet using both TronGrid and TronScan APIs"""
        try:
            all_transactions = []
            
            # Get transactions from TronGrid (primary source)
            trongrid_transactions = await self._get_wallet_transactions_trongrid(address, limit, hours)
            all_transactions.extend(trongrid_transactions)
            
            # Get transactions from TronScan (backup/additional source)
            tronscan_transactions = await self.get_wallet_transactions_tronscan(address, limit, hours)
            
            # Merge transactions, avoiding duplicates
            seen_hashes = {tx.get("hash") for tx in all_transactions if tx.get("hash")}
            
            for tx in tronscan_transactions:
                if tx.get("hash") and tx.get("hash") not in seen_hashes:
                    all_transactions.append(tx)
                    seen_hashes.add(tx.get("hash"))
            
            # Sort by timestamp (newest first)
            all_transactions.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
            
            # Apply time filtering if hours specified (since API filtering might not work)
            if hours:
                from datetime import datetime, timedelta
                cutoff_time = datetime.utcnow() - timedelta(hours=hours)
                cutoff_timestamp = int(cutoff_time.timestamp())
                
                # Filter transactions by time
                time_filtered = []
                for tx in all_transactions:
                    tx_timestamp = tx.get('timestamp', 0)
                    if tx_timestamp >= cutoff_timestamp:
                        time_filtered.append(tx)
                
                all_transactions = time_filtered
                logger.info(f"Time filtered to {len(all_transactions)} transactions (last {hours}h)")
            
            # Filter out zero amount transactions
            filtered_transactions = []
            for tx in all_transactions:
                amount = tx.get('amount', 0)
                if isinstance(amount, (int, float)) and amount > 0.000001:
                    filtered_transactions.append(tx)
            
            logger.info(f"Combined APIs returned {len(filtered_transactions)} valid transactions for {address} (TronGrid: {len(trongrid_transactions)}, TronScan: {len(tronscan_transactions)})")
            return filtered_transactions[:limit]
            
        except Exception as e:
            logger.error(f"Error fetching transactions for {address}: {e}")
            return []

    async def _get_wallet_transactions_trongrid(self, address: str, limit: int = 50, hours: int = None) -> list:
        """Get recent transactions from TronGrid API (primary source)"""
        try:
            # Calculate minimum timestamp if hours specified
            min_timestamp = None
            if hours:
                from datetime import datetime, timedelta
                cutoff_time = datetime.utcnow() - timedelta(hours=hours)
                min_timestamp = int(cutoff_time.timestamp() * 1000)  # TronGrid expects milliseconds
            
            # Get TRX transactions
            trx_url = f"{self.base_url}/v1/accounts/{address}/transactions"
            trx_params = {"limit": min(limit, 200)}  # TronGrid max is usually 200
            if min_timestamp:
                trx_params["min_timestamp"] = min_timestamp
            
            trx_response = await self._make_request_with_retry('GET', trx_url, params=trx_params)
            trx_data = trx_response.json() if trx_response and trx_response.status_code == 200 else {"data": []}
            
            # Get TRC20 transactions (USDT) - increase limit significantly
            trc20_url = f"{self.base_url}/v1/accounts/{address}/transactions/trc20"
            trc20_params = {"limit": min(limit * 2, 200), "contract_address": self.usdt_contract_address}
            if min_timestamp:
                trc20_params["min_timestamp"] = min_timestamp
            
            trc20_response = await self._make_request_with_retry('GET', trc20_url, params=trc20_params)
            trc20_data = trc20_response.json() if trc20_response and trc20_response.status_code == 200 else {"data": []}
            
            logger.info(f"TronGrid TRC20 returned {len(trc20_data.get('data', []))} USDT transactions for {address} (hours: {hours})")
            
            transactions = []
            
            # Process TRX transactions
            for tx in trx_data.get("data", []):
                contract_data = tx.get("raw_data", {}).get("contract", [{}])[0]
                contract_type = contract_data.get("type", "")
                parameter_value = contract_data.get("parameter", {}).get("value", {})
                
                # Handle different contract types
                from_addr = ""
                to_addr = ""
                amount = 0
                
                if contract_type == "TransferContract":
                    from_addr = parameter_value.get("owner_address", "")
                    to_addr = parameter_value.get("to_address", "")
                    amount = parameter_value.get("amount", 0) / 1_000_000
                elif contract_type == "TriggerSmartContract":
                    from_addr = parameter_value.get("owner_address", "")
                    to_addr = parameter_value.get("contract_address", "")
                    amount = parameter_value.get("call_value", 0) / 1_000_000
                
                # Fix timestamp - ensure it's in seconds (not milliseconds)
                timestamp = tx.get("block_timestamp", 0)
                if timestamp > 10000000000:  # If it's in milliseconds, convert to seconds
                    timestamp = timestamp // 1000

                # Get actual block number
                block_number = tx.get("blockNumber", tx.get("block_number", 0))

                transactions.append({
                    "hash": tx.get("txID", ""),
                    "type": "TRX",
                    "from": self._convert_hex_to_address(from_addr),
                    "to": self._convert_hex_to_address(to_addr),
                    "amount": amount,
                    "timestamp": timestamp,
                    "block": block_number,
                    "status": "Success" if tx.get("ret", [{}])[0].get("contractRet") == "SUCCESS" else "Failed",
                    "contract_type": contract_type
                })
            
            # Process TRC20 transactions
            for tx in trc20_data.get("data", []):
                # Fix timestamp - ensure it's in seconds (not milliseconds)  
                timestamp = tx.get("block_timestamp", 0)
                if timestamp > 10000000000:  # If it's in milliseconds, convert to seconds
                    timestamp = timestamp // 1000
                
                # Get actual block number
                block_number = tx.get("block", tx.get("block_number", 0))
                    
                transactions.append({
                    "hash": tx.get("transaction_id", ""),
                    "type": "USDT",
                    "from": tx.get("from", ""),
                    "to": tx.get("to", ""),
                    "amount": float(tx.get("value", 0)) / 1_000_000,
                    "timestamp": timestamp,
                    "block": block_number,
                    "status": "Success"
                })
            
            # Sort by timestamp (newest first)
            transactions.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
            
            # Filter out zero amount transactions as requested
            filtered_transactions = []
            for tx in transactions:
                amount = tx.get('amount', 0)
                if isinstance(amount, (int, float)) and amount > 0.000001:  # Filter out dust transactions
                    filtered_transactions.append(tx)
            
            return filtered_transactions[:limit]
            
        except Exception as e:
            logger.error(f"Error fetching transactions for {address}: {e}")
            return []

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()

    def _convert_hex_to_address(self, hex_address: str) -> str:
        """Convert hex address to TRON address format"""
        if not hex_address:
            return ""
        
        try:
            if hex_address.startswith("41") and len(hex_address) == 42:
                # Manual base58 conversion for TRON addresses
                # Convert hex to bytes
                address_bytes = bytes.fromhex(hex_address)
                
                # Calculate checksum
                hash1 = hashlib.sha256(address_bytes).digest()
                hash2 = hashlib.sha256(hash1).digest()
                checksum = hash2[:4]
                
                # Combine address and checksum
                full_address = address_bytes + checksum
                
                # Encode to base58
                return base58.b58encode(full_address).decode('utf-8')
                
            elif hex_address.startswith("T") and len(hex_address) == 34:
                return hex_address
            else:
                return hex_address
        except Exception as e:
            logger.warning(f"Address conversion failed for {hex_address}: {e}")
            # Return original hex address if conversion fails
            return hex_address


    async def fetch_wallet_balances(self, address: str) -> tuple:
        """Fetch TRX and USDT balances for a wallet with caching"""
        try:
            current_time = time.time()
            
            # Check cache first
            if address in self.balance_cache:
                cached = self.balance_cache[address]
                if current_time - cached.timestamp < self.cache_ttl:
                    logger.debug(f"Using cached balances for {address}")
                    return cached.trx_balance, cached.usdt_balance
            
            # Fetch fresh balances
            trx_balance = await self.get_trx_balance(address)
            usdt_balance = await self.get_usdt_balance(address)
            
            # Update cache
            self.balance_cache[address] = BalanceCache(
                trx_balance=trx_balance,
                usdt_balance=usdt_balance,
                timestamp=current_time
            )
            
            return trx_balance, usdt_balance
        except Exception as e:
            logger.error(f"Error fetching wallet balances for {address}: {e}")
            return 0.0, 0.0
    
    async def get_recent_transactions_with_notifications(self, address: str, wallet_id: int, since_timestamp: int) -> list:
        """Get recent transactions and send WebSocket notifications for new ones"""
        try:
            # Get recent transactions
            transactions = await self.get_wallet_transactions(address, limit=50)
            
            # Filter transactions newer than timestamp
            new_transactions = []
            current_time = int(datetime.utcnow().timestamp())
            
            for tx in transactions:
                tx_timestamp = tx.get('timestamp', 0)
                if isinstance(tx_timestamp, str):
                    # Convert from ISO string to timestamp
                    try:
                        tx_timestamp = int(datetime.fromisoformat(tx_timestamp.replace('Z', '+00:00')).timestamp())
                    except:
                        tx_timestamp = current_time
                
                if tx_timestamp > since_timestamp:
                    new_transactions.append(tx)
                    
                    # Send WebSocket notification for each new transaction
                    await manager.broadcast({
                        "type": "tron_transaction",
                        "data": {
                            "wallet_id": wallet_id,
                            "address": address,
                            "transaction": tx,
                            "blockchain": "TRON",
                            "timestamp": tx_timestamp
                        }
                    })
                    
                    # Also send transaction notification
                    transaction_msg = f"New TRON {tx.get('type', 'transaction')}: {tx.get('amount', 0)} {tx.get('type', 'TRX')}"
                    await manager.broadcast({
                        "type": "transaction_notification",
                        "data": {
                            "transaction": tx,
                            "message": transaction_msg,
                            "wallet_id": wallet_id,
                            "blockchain": "TRON"
                        }
                    })
                    
                    # Create balance history record after each new transaction
                    await self._create_transaction_balance_history(wallet_id, tx)
            
            return new_transactions
            
        except Exception as e:
            logger.error(f"Error getting recent TRON transactions with notifications: {e}")
            return []

    async def _create_transaction_balance_history(self, wallet_id: int, transaction: dict):
        """Create balance history record after a transaction"""
        try:
            from database import AsyncSessionLocal, BalanceHistory, Token, Blockchain, Wallet
            
            async with AsyncSessionLocal() as db:
                try:
                    # Get TRON blockchain
                    tron_blockchain = await db.execute(
                        select(Blockchain).where(Blockchain.name == "TRON")
                    )
                    tron_blockchain = tron_blockchain.scalar_one_or_none()
                    if not tron_blockchain:
                        return
                    
                    # Determine token based on transaction type
                    token_symbol = "TRX" if transaction.get('type') == "TRX" else "USDT"
                    
                    # Get token
                    token = await db.execute(
                        select(Token).where(
                            Token.symbol == token_symbol,
                            Token.blockchain_id == tron_blockchain.id
                        )
                    )
                    token = token.scalar_one_or_none()
                    if not token:
                        return
                    
                    # Get current wallet address to fetch fresh balance
                    wallet = await db.execute(
                        select(Wallet).where(Wallet.id == wallet_id)
                    )
                    wallet = wallet.scalar_one_or_none()
                    if not wallet:
                        return
                    
                    # Fetch current balance
                    if token_symbol == "TRX":
                        current_balance = await self.get_trx_balance(wallet.address)
                    else:
                        current_balance = await self.get_usdt_balance(wallet.address)
                    
                    # Create balance history with transaction context
                    tx_amount = transaction.get('amount', 0)
                    change_type = 'transaction_detected'
                    
                    history = BalanceHistory(
                        wallet_id=wallet_id,
                        token_id=token.id,
                        balance_before=current_balance - tx_amount,  # Approximate previous balance
                        balance_after=current_balance,
                        change_amount=tx_amount,
                        change_percentage=None,
                        change_type=change_type,
                        transaction_hash=transaction.get('hash', '')
                    )
                    db.add(history)
                    await db.commit()
                    
                    logger.info(f"Created TRON transaction balance history for wallet {wallet_id}, amount: {tx_amount}")
                    
                except Exception as db_error:
                    logger.error(f"Database error creating transaction balance history: {db_error}")
                    await db.rollback()
                    
        except Exception as e:
            logger.error(f"Error creating transaction balance history: {e}")

    async def _rate_limit(self):
        """Implement rate limiting between API requests"""
        if not self.rate_limit_enabled:
            return
            
        import time
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            logger.info(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            await asyncio.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    async def _make_request_with_retry(self, method: str, url: str, **kwargs):
        """Make API request with retry logic for rate limiting"""
        for attempt in range(self.max_retries):
            try:
                await self._rate_limit()
                
                if method.upper() == 'GET':
                    response = await self.client.get(url, **kwargs)
                elif method.upper() == 'POST':
                    response = await self.client.post(url, **kwargs)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                # Handle rate limiting
                if response.status_code == 429:
                    if attempt < self.max_retries - 1:
                        retry_after = int(response.headers.get('Retry-After', self.retry_delay))
                        logger.warning(f"Rate limited (429), retrying after {retry_after} seconds (attempt {attempt + 1})")
                        await asyncio.sleep(retry_after)
                        continue
                    else:
                        logger.error(f"Max retries exceeded for rate limiting on {url}")
                        return None
                
                # Handle other HTTP errors
                if response.status_code >= 400:
                    logger.warning(f"HTTP {response.status_code} for {url}: {response.text}")
                    return None
                
                return response
                
            except Exception as e:
                if attempt < self.max_retries - 1:
                    logger.warning(f"Request failed (attempt {attempt + 1}): {e}, retrying...")
                    await asyncio.sleep(self.retry_delay)
                    continue
                else:
                    logger.error(f"Request failed after {self.max_retries} attempts: {e}")
                    return None
        
        return None

    async def get_wallet_transactions_tronscan(self, address: str, limit: int = 50, hours: int = None) -> list:
        """Get recent transactions from TronScan API (backup method)"""
        try:
            transactions = []
            
            # Calculate minimum timestamp if hours specified
            min_timestamp = None
            if hours:
                from datetime import datetime, timedelta
                cutoff_time = datetime.utcnow() - timedelta(hours=hours)
                min_timestamp = int(cutoff_time.timestamp() * 1000)  # TronScan expects milliseconds
            
            # Get USDT transactions from TronScan (fetch maximum and filter manually)
            usdt_url = "https://apilist.tronscanapi.com/api/token_trc20/transfers"
            usdt_params = {
                "sort": "-timestamp",
                "count": "true", 
                "limit": 1000,  # Fetch maximum to ensure we get historical data
                "relatedAddress": address,
                "contract_address": self.usdt_contract_address
            }
            
            # Remove time filtering params since they don't work reliably on TronScan
            # We'll do manual filtering after getting the data
            
            try:
                response = await self.client.get(usdt_url, params=usdt_params)
                if response.status_code == 200:
                    data = response.json()
                    usdt_count = 0
                    for tx in data.get("token_transfers", []):
                        if tx.get("transaction_id") and tx.get("quant"):
                            # Convert amount from quant field (TronScan uses quant instead of amount_str)
                            quant_str = tx.get("quant", "0")
                            try:
                                amount = float(quant_str) / 1_000_000  # USDT has 6 decimals
                            except (ValueError, TypeError):
                                continue
                            
                            # Convert timestamp from milliseconds to seconds
                            timestamp = tx.get("block_ts", 0)  # TronScan uses block_ts
                            if timestamp and timestamp > 10000000000:
                                timestamp = timestamp // 1000
                            elif not timestamp:
                                # Use current timestamp if not available
                                timestamp = int(datetime.utcnow().timestamp())
                            
                            transactions.append({
                                "hash": tx.get("transaction_id", ""),
                                "type": "USDT",
                                "from": tx.get("from_address", ""),
                                "to": tx.get("to_address", ""),
                                "amount": amount,
                                "timestamp": timestamp,
                                "block": tx.get("block", 0),
                                "status": "Success",
                                "source": "tronscan"
                            })
                            usdt_count += 1
                    
                    logger.info(f"TronScan USDT API returned {usdt_count} transactions for {address} (hours: {hours})")
            except Exception as e:
                logger.warning(f"TronScan USDT API failed: {e}")
            
            # Get TRX transactions from TronScan (fetch maximum and filter manually)
            trx_url = "https://apilist.tronscanapi.com/api/transaction"
            trx_params = {
                "sort": "-timestamp",
                "count": "true", 
                "limit": 500,  # Fetch maximum TRX transactions
                "address": address
            }
            
            # Remove time filters since TronScan doesn't handle them reliably
            
            try:
                response = await self.client.get(trx_url, params=trx_params)
                if response.status_code == 200:
                    data = response.json()
                    trx_count = 0
                    for tx in data.get("data", []):
                        # Only process TransferContract (TRX transfers)
                        if tx.get("contractType") == 1:  # TransferContract
                            # Safely convert amount from string to float
                            amount_raw = tx.get("amount", "0")
                            try:
                                if isinstance(amount_raw, str):
                                    amount = float(amount_raw) / 1_000_000  # TRX conversion
                                else:
                                    amount = float(amount_raw) / 1_000_000
                            except (ValueError, TypeError):
                                logger.warning(f"Invalid amount in TronScan TRX transaction: {amount_raw}")
                                continue
                            
                            # Convert timestamp from milliseconds to seconds
                            timestamp = tx.get("timestamp", 0)
                            if timestamp > 10000000000:
                                timestamp = timestamp // 1000
                            
                            transactions.append({
                                "hash": tx.get("hash", ""),
                                "type": "TRX",
                                "from": tx.get("ownerAddress", ""),
                                "to": tx.get("toAddress", ""),
                                "amount": amount,
                                "timestamp": timestamp,
                                "block": tx.get("block", 0),
                                "status": "Success" if tx.get("confirmed") else "Pending",
                                "source": "tronscan"
                            })
                            trx_count += 1
                    
                    logger.info(f"TronScan TRX API returned {trx_count} transactions for {address} (hours: {hours})")
            except Exception as e:
                logger.warning(f"TronScan TRX API failed: {e}")
            
            # Sort by timestamp (newest first)
            transactions.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
            
            # Filter out zero amount transactions
            filtered_transactions = []
            for tx in transactions:
                amount = tx.get('amount', 0)
                if isinstance(amount, (int, float)) and amount > 0.000001:
                    filtered_transactions.append(tx)
            
            logger.info(f"TronScan API returned {len(filtered_transactions)} valid transactions for {address}")
            return filtered_transactions[:limit]
            
        except Exception as e:
            logger.error(f"Error fetching transactions from TronScan for {address}: {e}")
            return []

# Global TronGridClient instance
tron_client = TronGridClient()
