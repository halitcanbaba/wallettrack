import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

class BitcoinService:
    """Service for interacting with Bitcoin blockchain"""
    
    def __init__(self):
        self.base_url = "https://blockchain.info"
        self.blockchair_url = "https://api.blockchair.com/bitcoin"
        
        # Get API keys from environment (optional for blockchain.info, required for better limits on blockchair)
        self.blockchair_api_key = os.getenv('BLOCKCHAIR_API_KEY', '')
        
        self.session = httpx.AsyncClient(timeout=30.0)
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 1.0  # 1 second between requests
        
        logger.info("Bitcoin Service initialized")
        if self.blockchair_api_key:
            logger.info(f"Blockchair API Key configured: {self.blockchair_api_key[:8]}...")
    
    async def _rate_limit(self):
        """Implement rate limiting"""
        current_time = asyncio.get_event_loop().time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            await asyncio.sleep(self.min_request_interval - time_since_last)
        
        self.last_request_time = asyncio.get_event_loop().time()
    
    async def _make_request_with_retry(self, url: str, params: dict = None, max_retries: int = 3):
        """Make HTTP request with retry logic"""
        for attempt in range(max_retries):
            try:
                await self._rate_limit()
                response = await self.session.get(url, params=params)
                
                if response.status_code == 200:
                    return response
                elif response.status_code == 429:  # Rate limited
                    wait_time = (attempt + 1) * 5
                    logger.warning(f"Rate limited, waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.warning(f"Request failed with status {response.status_code}: {response.text}")
                    
            except Exception as e:
                logger.error(f"Request error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep((attempt + 1) * 2)
        
        return None
    
    async def get_btc_balance(self, address: str) -> float:
        """Get BTC balance for an address (in BTC, not satoshis)"""
        try:
            # Use blockchain.info as primary (no API key needed, reliable)
            balance = await self._get_balance_blockchain_info(address)
            if balance > 0:
                return balance
            
            # Try Blockchair only if blockchain.info fails
            if self.blockchair_api_key:
                balance = await self._get_balance_blockchair(address)
                if balance is not None:
                    return balance
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error getting BTC balance for {address}: {e}")
            return 0.0
    
    async def _get_balance_blockchair(self, address: str) -> Optional[float]:
        """Get balance using Blockchair API"""
        try:
            url = f"{self.blockchair_url}/dashboards/address/{address}"
            params = {}
            if self.blockchair_api_key:
                params['key'] = self.blockchair_api_key
            
            response = await self._make_request_with_retry(url, params)
            
            if response and response.status_code == 200:
                data = response.json()
                
                if 'data' in data and address in data['data']:
                    address_data = data['data'][address]['address']
                    balance_satoshi = address_data.get('balance', 0)
                    # Convert satoshi to BTC
                    balance_btc = balance_satoshi / 100_000_000
                    logger.info(f"Blockchair: BTC balance for {address}: {balance_btc} BTC")
                    return balance_btc
            
            return None
            
        except Exception as e:
            logger.error(f"Blockchair API error: {e}")
            return None
    
    async def _get_balance_blockchain_info(self, address: str) -> float:
        """Get balance using Blockchain.info API"""
        try:
            url = f"{self.base_url}/q/addressbalance/{address}"
            
            response = await self._make_request_with_retry(url)
            
            if response and response.status_code == 200:
                balance_satoshi = int(response.text)
                # Convert satoshi to BTC
                balance_btc = balance_satoshi / 100_000_000
                logger.info(f"Blockchain.info: BTC balance for {address}: {balance_btc} BTC")
                return balance_btc
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Blockchain.info API error: {e}")
            return 0.0
    
    async def get_wallet_transactions(self, address: str, limit: int = 50) -> List[Dict]:
        """Get recent transactions for a BTC wallet"""
        try:
            # Use blockchain.info as primary (no rate limits for reasonable usage)
            transactions = await self._get_transactions_blockchain_info(address, limit)
            if transactions:
                return transactions
            
            # Try Blockchair only if blockchain.info fails and we have API key
            if self.blockchair_api_key:
                transactions = await self._get_transactions_blockchair(address, limit)
                if transactions:
                    return transactions
            
            return []
            
        except Exception as e:
            logger.error(f"Error getting BTC transactions for {address}: {e}")
            return []
    
    async def _get_transactions_blockchair(self, address: str, limit: int = 50) -> List[Dict]:
        """Get transactions using Blockchair API"""
        try:
            url = f"{self.blockchair_url}/dashboards/address/{address}"
            params = {'limit': min(limit, 100)}
            if self.blockchair_api_key:
                params['key'] = self.blockchair_api_key
            
            response = await self._make_request_with_retry(url, params)
            
            if response and response.status_code == 200:
                data = response.json()
                
                if 'data' in data and address in data['data']:
                    transactions = []
                    tx_list = data['data'][address].get('transactions', [])
                    
                    for tx_hash in tx_list[:limit]:
                        # Get transaction details
                        tx_url = f"{self.blockchair_url}/dashboards/transaction/{tx_hash}"
                        tx_params = {}
                        if self.blockchair_api_key:
                            tx_params['key'] = self.blockchair_api_key
                        
                        tx_response = await self._make_request_with_retry(tx_url, tx_params)
                        if tx_response and tx_response.status_code == 200:
                            tx_data = tx_response.json()
                            
                            if 'data' in tx_data and tx_hash in tx_data['data']:
                                tx_info = tx_data['data'][tx_hash]['transaction']
                                
                                # Calculate amount for this address
                                amount = 0.0
                                tx_type = "unknown"
                                
                                # Check inputs and outputs to determine direction
                                inputs = tx_data['data'][tx_hash].get('inputs', [])
                                outputs = tx_data['data'][tx_hash].get('outputs', [])
                                
                                is_sender = any(inp.get('recipient') == address for inp in inputs)
                                is_receiver = any(out.get('recipient') == address for out in outputs)
                                
                                if is_receiver:
                                    # Calculate received amount
                                    for output in outputs:
                                        if output.get('recipient') == address:
                                            amount += output.get('value', 0) / 100_000_000
                                    tx_type = "received"
                                elif is_sender:
                                    # Calculate sent amount
                                    for inp in inputs:
                                        if inp.get('recipient') == address:
                                            amount += inp.get('value', 0) / 100_000_000
                                    tx_type = "sent"
                                
                                transactions.append({
                                    "hash": tx_hash,
                                    "type": "BTC",
                                    "amount": amount,
                                    "direction": tx_type,
                                    "timestamp": datetime.fromisoformat(tx_info['time'].replace('Z', '+00:00')).timestamp(),
                                    "block": tx_info.get('block_id'),
                                    "confirmations": tx_info.get('confirmations', 0),
                                    "blockchain": "BTC"
                                })
                    
                    logger.info(f"Retrieved {len(transactions)} BTC transactions from Blockchair")
                    return transactions
            
            return []
            
        except Exception as e:
            logger.error(f"Blockchair transactions error: {e}")
            return []
    
    async def _get_transactions_blockchain_info(self, address: str, limit: int = 50) -> List[Dict]:
        """Get transactions using Blockchain.info API"""
        try:
            url = f"{self.base_url}/rawaddr/{address}"
            params = {'limit': limit}
            
            response = await self._make_request_with_retry(url, params)
            
            if response and response.status_code == 200:
                data = response.json()
                transactions = []
                
                for tx in data.get('txs', [])[:limit]:
                    # Calculate amount for this address
                    amount = 0.0
                    tx_type = "unknown"
                    
                    # Check inputs to see if we're the sender
                    is_sender = any(inp.get('prev_out', {}).get('addr') == address for inp in tx.get('inputs', []))
                    
                    # Check outputs to see if we're the receiver
                    received_amount = 0
                    for output in tx.get('out', []):
                        if output.get('addr') == address:
                            received_amount += output.get('value', 0)
                    
                    if received_amount > 0:
                        amount = received_amount / 100_000_000
                        tx_type = "received"
                    elif is_sender:
                        # Calculate sent amount (sum of inputs from this address)
                        sent_amount = 0
                        for inp in tx.get('inputs', []):
                            prev_out = inp.get('prev_out', {})
                            if prev_out.get('addr') == address:
                                sent_amount += prev_out.get('value', 0)
                        amount = sent_amount / 100_000_000
                        tx_type = "sent"
                    
                    transactions.append({
                        "hash": tx.get('hash'),
                        "type": "BTC",
                        "amount": amount,
                        "direction": tx_type,
                        "timestamp": tx.get('time', 0),
                        "block": tx.get('block_height'),
                        "confirmations": data.get('n_tx', 0),
                        "blockchain": "BTC"
                    })
                
                logger.info(f"Retrieved {len(transactions)} BTC transactions from Blockchain.info")
                return transactions
            
            return []
            
        except Exception as e:
            logger.error(f"Blockchain.info transactions error: {e}")
            return []
    
    async def get_wallet_transactions_since(self, address: str, hours: int = 1, limit: int = 100) -> List[Dict]:
        """Get transactions since a certain time"""
        try:
            all_transactions = await self.get_wallet_transactions(address, limit)
            
            # Filter by time
            cutoff_time = datetime.utcnow().timestamp() - (hours * 3600)
            recent_transactions = [tx for tx in all_transactions if tx.get('timestamp', 0) > cutoff_time]
            
            logger.info(f"Found {len(recent_transactions)} BTC transactions in last {hours} hours")
            return recent_transactions
            
        except Exception as e:
            logger.error(f"Error getting recent BTC transactions: {e}")
            return []
    
    async def close(self):
        """Close the HTTP session"""
        await self.session.aclose()

# Global instance
btc_client = BitcoinService()
