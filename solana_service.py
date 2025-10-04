import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

class SolanaService:
    """Service for interacting with Solana blockchain"""
    
    def __init__(self):
        # Use public RPC endpoints
        self.rpc_urls = [
            "https://api.mainnet-beta.solana.com",
            "https://solana-api.projectserum.com",
            "https://rpc.ankr.com/solana"
        ]
        self.current_rpc_index = 0
        
        # Solscan API for better data
        self.solscan_url = "https://public-api.solscan.io"
        self.solscan_api_key = os.getenv('SOLSCAN_API_KEY', '')
        
        self.session = httpx.AsyncClient(timeout=30.0)
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 0.5  # 0.5 seconds between requests
        
        # Common Solana tokens (SPL tokens)
        self.common_tokens = {
            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": {"symbol": "USDC", "decimals": 6, "name": "USD Coin"},
            "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": {"symbol": "USDT", "decimals": 6, "name": "Tether USD"},
            "7dHbWXmci3dT8UFYWYZweBLXgycu7Y3iL6trKn1Y7ARj": {"symbol": "stSOL", "decimals": 9, "name": "Lido Staked SOL"},
            "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So": {"symbol": "mSOL", "decimals": 9, "name": "Marinade Staked SOL"},
        }
        
        logger.info("Solana Service initialized")
        if self.solscan_api_key:
            logger.info(f"Solscan API Key configured: {self.solscan_api_key[:8]}...")
    
    async def _rate_limit(self):
        """Implement rate limiting"""
        current_time = asyncio.get_event_loop().time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            await asyncio.sleep(self.min_request_interval - time_since_last)
        
        self.last_request_time = asyncio.get_event_loop().time()
    
    def _get_current_rpc_url(self) -> str:
        """Get current RPC URL"""
        return self.rpc_urls[self.current_rpc_index]
    
    def _rotate_rpc(self):
        """Rotate to next RPC endpoint"""
        self.current_rpc_index = (self.current_rpc_index + 1) % len(self.rpc_urls)
        logger.info(f"Rotating to RPC: {self._get_current_rpc_url()}")
    
    async def _make_rpc_request(self, method: str, params: list, max_retries: int = 3):
        """Make JSON-RPC request with retry logic"""
        for attempt in range(max_retries):
            try:
                await self._rate_limit()
                
                rpc_url = self._get_current_rpc_url()
                
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": method,
                    "params": params
                }
                
                response = await self.session.post(rpc_url, json=payload)
                
                if response.status_code == 200:
                    data = response.json()
                    if 'result' in data:
                        return data['result']
                    elif 'error' in data:
                        logger.error(f"RPC error: {data['error']}")
                        # Try next RPC endpoint
                        self._rotate_rpc()
                else:
                    logger.warning(f"RPC request failed with status {response.status_code}")
                    self._rotate_rpc()
                
            except Exception as e:
                logger.error(f"RPC request error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    self._rotate_rpc()
                    await asyncio.sleep((attempt + 1) * 2)
        
        return None
    
    async def get_sol_balance(self, address: str) -> float:
        """Get SOL balance for an address (in SOL, not lamports)"""
        try:
            result = await self._make_rpc_request(
                "getBalance",
                [address]
            )
            
            if result and 'value' in result:
                lamports = result['value']
                # Convert lamports to SOL (1 SOL = 1,000,000,000 lamports)
                sol_balance = lamports / 1_000_000_000
                logger.info(f"SOL balance for {address}: {sol_balance} SOL")
                return sol_balance
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error getting SOL balance for {address}: {e}")
            return 0.0
    
    async def get_token_accounts(self, address: str) -> List[Dict]:
        """Get all SPL token accounts for an address"""
        try:
            result = await self._make_rpc_request(
                "getTokenAccountsByOwner",
                [
                    address,
                    {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
                    {"encoding": "jsonParsed"}
                ]
            )
            
            if result and 'value' in result:
                token_accounts = []
                
                for account in result['value']:
                    try:
                        parsed_data = account['account']['data']['parsed']['info']
                        token_amount = parsed_data['tokenAmount']
                        
                        mint = parsed_data['mint']
                        decimals = token_amount['decimals']
                        balance = float(token_amount['uiAmountString'] or 0)
                        
                        # Get token info
                        token_info = self.common_tokens.get(mint, {
                            "symbol": mint[:8] + "...",
                            "decimals": decimals,
                            "name": "Unknown Token"
                        })
                        
                        if balance > 0:  # Only include tokens with balance
                            token_accounts.append({
                                "mint": mint,
                                "symbol": token_info["symbol"],
                                "name": token_info["name"],
                                "balance": balance,
                                "decimals": decimals
                            })
                    
                    except Exception as e:
                        logger.debug(f"Error parsing token account: {e}")
                        continue
                
                logger.info(f"Found {len(token_accounts)} SPL tokens for {address}")
                return token_accounts
            
            return []
            
        except Exception as e:
            logger.error(f"Error getting token accounts for {address}: {e}")
            return []
    
    async def get_wallet_balances(self, address: str) -> Dict[str, float]:
        """Get all balances (SOL + SPL tokens) for a wallet"""
        balances = {}
        
        try:
            # Get SOL balance
            sol_balance = await self.get_sol_balance(address)
            balances["SOL"] = sol_balance
            
            # Get SPL token balances
            token_accounts = await self.get_token_accounts(address)
            
            for token in token_accounts:
                symbol = token['symbol']
                balance = token['balance']
                
                # Filter out dust amounts
                if balance > 0.000001:
                    balances[symbol] = balance
            
            logger.info(f"Retrieved balances for {address}: {balances}")
            return balances
            
        except Exception as e:
            logger.error(f"Error getting wallet balances for {address}: {e}")
            return balances
    
    async def get_wallet_transactions(self, address: str, limit: int = 50) -> List[Dict]:
        """Get recent transactions for a Solana wallet"""
        try:
            # Use Solscan API if available
            if self.solscan_api_key:
                return await self._get_transactions_solscan(address, limit)
            
            # Fallback to RPC
            return await self._get_transactions_rpc(address, limit)
            
        except Exception as e:
            logger.error(f"Error getting Solana transactions for {address}: {e}")
            return []
    
    async def _get_transactions_rpc(self, address: str, limit: int = 50) -> List[Dict]:
        """Get transactions using RPC"""
        try:
            result = await self._make_rpc_request(
                "getSignaturesForAddress",
                [address, {"limit": min(limit, 100)}]
            )
            
            if result:
                transactions = []
                
                for sig_info in result[:limit]:
                    signature = sig_info.get('signature')
                    
                    # Get transaction details
                    tx_result = await self._make_rpc_request(
                        "getTransaction",
                        [signature, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}]
                    )
                    
                    if tx_result and 'transaction' in tx_result:
                        tx_data = tx_result['transaction']
                        block_time = tx_result.get('blockTime', 0)
                        slot = tx_result.get('slot', 0)
                        
                        # Parse transaction to extract amount (simplified)
                        amount = 0.0
                        tx_type = "SOL"
                        
                        # Check if it's a SOL transfer
                        if 'meta' in tx_result and 'postBalances' in tx_result['meta']:
                            pre_balances = tx_result['meta'].get('preBalances', [])
                            post_balances = tx_result['meta'].get('postBalances', [])
                            
                            if len(pre_balances) > 0 and len(post_balances) > 0:
                                # Calculate balance change (in lamports)
                                balance_change = post_balances[0] - pre_balances[0]
                                amount = abs(balance_change) / 1_000_000_000  # Convert to SOL
                        
                        transactions.append({
                            "hash": signature,
                            "type": tx_type,
                            "amount": amount,
                            "timestamp": block_time,
                            "block": slot,
                            "status": "Success" if sig_info.get('err') is None else "Failed",
                            "blockchain": "SOL"
                        })
                
                logger.info(f"Retrieved {len(transactions)} Solana transactions")
                return transactions
            
            return []
            
        except Exception as e:
            logger.error(f"RPC transactions error: {e}")
            return []
    
    async def _get_transactions_solscan(self, address: str, limit: int = 50) -> List[Dict]:
        """Get transactions using Solscan API"""
        try:
            url = f"{self.solscan_url}/account/transactions"
            params = {
                "account": address,
                "limit": limit
            }
            
            headers = {}
            if self.solscan_api_key:
                headers["token"] = self.solscan_api_key
            
            await self._rate_limit()
            response = await self.session.get(url, params=params, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                transactions = []
                
                for tx in data.get('data', [])[:limit]:
                    transactions.append({
                        "hash": tx.get('txHash'),
                        "type": "SOL",
                        "amount": tx.get('lamport', 0) / 1_000_000_000,
                        "timestamp": tx.get('blockTime', 0),
                        "block": tx.get('slot', 0),
                        "status": "Success" if tx.get('status') == 'Success' else "Failed",
                        "blockchain": "SOL"
                    })
                
                logger.info(f"Retrieved {len(transactions)} Solana transactions from Solscan")
                return transactions
            
            return []
            
        except Exception as e:
            logger.error(f"Solscan API error: {e}")
            return []
    
    async def get_wallet_transactions_since(self, address: str, hours: int = 1, limit: int = 100) -> List[Dict]:
        """Get transactions since a certain time"""
        try:
            all_transactions = await self.get_wallet_transactions(address, limit)
            
            # Filter by time
            cutoff_time = datetime.utcnow().timestamp() - (hours * 3600)
            recent_transactions = [tx for tx in all_transactions if tx.get('timestamp', 0) > cutoff_time]
            
            logger.info(f"Found {len(recent_transactions)} Solana transactions in last {hours} hours")
            return recent_transactions
            
        except Exception as e:
            logger.error(f"Error getting recent Solana transactions: {e}")
            return []
    
    async def close(self):
        """Close the HTTP session"""
        await self.session.aclose()

# Global instance
solana_client = SolanaService()
