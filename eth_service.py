import asyncio
import logging
import httpx
import os
import re
from typing import Dict, List, Optional
from datetime import datetime
from web3 import Web3

logger = logging.getLogger(__name__)

class EthereumService:
    def __init__(self, api_key: str = None, use_v2_api: bool = True):
        self.session = httpx.AsyncClient(timeout=30.0)
        
        # Rate limiting from environment variables
        self.min_request_interval = float(os.getenv('ETH_MIN_REQUEST_INTERVAL', '1.0'))
        self.max_retries = int(os.getenv('ETH_MAX_RETRIES', '3'))
        self.retry_delay = int(os.getenv('ETH_RETRY_DELAY', '3'))
        self.last_request_time = 0
        
        # API configuration from environment
        self.api_key = api_key or os.getenv('ETHERSCAN_API_KEY') or "H52NBFTJVAQBXDUHZ77Z1DC3SV58SISHM8"
        
        # Using Etherscan API V2 for higher rate limits (100+ calls/second vs 5/second in V1)
        self.use_v2_api = use_v2_api
        if use_v2_api:
            self.eth_api_base = os.getenv('ETHERSCAN_BASE_URL', "https://api.etherscan.io/v2/api")
            logger.info("Using Etherscan API v2 for higher rate limits")
        else:
            self.eth_api_base = "https://api.etherscan.io/api"
            logger.info("Using Etherscan API v1")
        
        logger.info(f"ETH Rate Limiting: interval={self.min_request_interval}s, retries={self.max_retries}, delay={self.retry_delay}s")
        
        # Initialize Web3 for direct blockchain access as backup
        try:
            # Use public RPC endpoints (replace with your own Infura/Alchemy key for production)
            public_rpc_endpoints = [
                'https://eth.llamarpc.com',
                'https://rpc.ankr.com/eth',
                'https://ethereum.blockpi.network/v1/rpc/public',
                'https://eth-mainnet.public.blastapi.io'
            ]
            
            # Try to connect to the first available endpoint
            self.web3_available = False
            for rpc_url in public_rpc_endpoints:
                try:
                    self.web3 = Web3(Web3.HTTPProvider(rpc_url))
                    if self.web3.is_connected():
                        self.web3_available = True
                        logger.info(f"Web3 connection established using {rpc_url}")
                        break
                except Exception:
                    continue
            
            if not self.web3_available:
                logger.warning("Web3 connection failed for all endpoints")
        except Exception as e:
            logger.warning(f"Web3 initialization failed: {e}")
            self.web3_available = False
    
    def is_legitimate_token(self, token_symbol: str, contract_address: str = None) -> bool:
        """Filter out scam tokens that use Unicode tricks to look like legitimate tokens"""
        
        # Known legitimate token contracts (case-insensitive)
        legitimate_token_contracts = {
            'USDT': '0xdAC17F958D2ee523a2206206994597C13D831ec7',  # Tether USD
            'USDC': '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',  # USD Coin
            'DAI': '0x6B175474E89094C44Da98b954EedeAC495271d0F',   # Dai Stablecoin
            'WETH': '0xC02aaA39b223FE8D0763b4DF1C5c72B3A7160096', # Wrapped Ether
            'UNI': '0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984',  # Uniswap
            'PEPE': '0x6982508145454ce325ddbe47a25d4ec3d2311933', # Pepe
            'SHIB': '0x95aD61b0a150d79219dCF64E1E6Cc01f0B64C4cE', # SHIBA INU
            'WBTC': '0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599', # Wrapped Bitcoin
            'LINK': '0x514910771AF9Ca656af840dff83E8264EcF986CA', # Chainlink
            'AAVE': '0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9', # Aave
            'COMP': '0xc00e94Cb662C3520282E6f5717214004A7f26888', # Compound
            'MKR': '0x9f8F72aA9304c8B593d555F12eF6589cC3A579A2',  # Maker
            'SUSHI': '0x6B3595068778DD592e39A122f4f5a5cF09C90fE2' # SushiSwap
        }
        
        # If contract address is provided, validate against known contracts for high-value tokens
        if contract_address:
            upper_token = token_symbol.upper()
            contract_address_lower = contract_address.lower()
            
            # For high-value tokens, enforce strict contract address matching
            if upper_token in legitimate_token_contracts:
                expected_contract = legitimate_token_contracts[upper_token].lower()
                if contract_address_lower == expected_contract:
                    logger.info(f"Validated legitimate token: {token_symbol} ({contract_address})")
                    return True
                else:
                    logger.info(f"Filtering out fake {token_symbol} token: contract {contract_address} != expected {expected_contract}")
                    return False
        
        # Check for suspicious Unicode characters
        suspicious_patterns = [
            r'[\u2060-\u206F]',  # Word joiner, zero-width space, etc.
            r'[\u200B-\u200D]',  # Zero-width space, ZWNJ, ZWJ
            r'[\u2062-\u2064]',  # Invisible times, separator, plus
            r'[\uFEFF]',         # Zero-width no-break space (BOM)
            r'[\u061C]',         # Arabic letter mark
            r'[\u180E]',         # Mongolian vowel separator
        ]
        
        # Check if token contains suspicious Unicode characters
        for pattern in suspicious_patterns:
            if re.search(pattern, token_symbol):
                logger.info(f"Filtering out scam token with Unicode tricks: '{token_symbol}'")
                return False
        
        # Check for common scam token patterns
        scam_patterns = [
            # Cyrillic letters that look like Latin
            r'[АВСДЕНКМОРТХУаосрехуе]',
            # Multiple consecutive special characters
            r'[^\w\s]{2,}',
            # Extremely long token names (likely scam)
            r'^.{20,}$'
        ]
        
        for pattern in scam_patterns:
            if re.search(pattern, token_symbol):
                logger.info(f"Filtering out scam token with suspicious pattern: '{token_symbol}'")
                return False
        
        # Whitelist of known legitimate tokens (case-insensitive) for tokens without contract validation
        legitimate_tokens = {
            'ETH', 'WETH', 'USDT', 'USDC', 'DAI', 'BUSD', 'UNI', 'LINK', 'AAVE', 'COMP',
            'MKR', 'CRV', 'SNX', 'YFI', 'SUSHI', '1INCH', 'BAT', 'ZRX', 'ENJ', 'MANA',
            'SAND', 'AXS', 'SHIB', 'PEPE', 'DOGE', 'MATIC', 'FTM', 'AVAX', 'BNB',
            'ADA', 'DOT', 'SOL', 'ATOM', 'NEAR', 'FIL', 'ICP', 'VET', 'ALGO', 'XTZ',
            'EGLD', 'HBAR', 'FLOW', 'CHZ', 'THETA', 'KLAY', 'HEX', 'LRC', 'GRT', 'FEI',
            'FRAX', 'LUSD', 'RAI', 'TRIBE', 'TUSD', 'PAXG', 'WBTC', 'RENBTC', 'HBTC',
            'STRK', 'POL', 'GALA', 'COMBO'
        }
        
        # Check against whitelist (case-insensitive)
        upper_token = token_symbol.upper()
        if upper_token in legitimate_tokens:
            # If no contract address provided, accept whitelisted tokens
            if not contract_address:
                return True
            # If contract address provided but not in our strict validation list, allow it
            elif upper_token not in legitimate_token_contracts:
                return True
        
        # Additional checks for potentially legitimate tokens
        # Allow if it's a simple alphanumeric token (2-10 chars) without suspicious patterns
        if re.match(r'^[A-Z0-9]{2,10}$', token_symbol, re.IGNORECASE):
            # Still check for obvious scams like multiple of the same letter
            if not re.search(r'(.)\1{3,}', token_symbol):
                return True
        
        # If we get here, it's likely a scam token
        logger.info(f"Filtering out potential scam token: '{token_symbol}' (contract: {contract_address})")
        return False
        
        # Common ERC-20 tokens to monitor - VERIFIED LATEST ADDRESSES
        self.tokens = {
            "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",  # Tether USD (6 decimals)
            "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",  # USD Coin (6 decimals)
            "DAI": "0x6B175474E89094C44Da98b954EedeAC495271d0F",   # Dai Stablecoin (18 decimals)
            "WETH": "0xC02aaA39b223FE8D0763b4DF1C5c72B3A7160096"  # Wrapped Ether (18 decimals) - FIXED
        }
    
    async def _rate_limit(self):
        """Implement rate limiting between API requests"""
        import time
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            logger.info(f"ETH Rate limiting: sleeping for {sleep_time:.2f} seconds")
            await asyncio.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    async def _make_request_with_retry(self, url: str, params: dict):
        """Make API request with retry logic for rate limiting"""
        for attempt in range(self.max_retries):
            try:
                await self._rate_limit()
                
                response = await self.session.get(url, params=params)
                
                # Handle rate limiting
                if response.status_code == 429:
                    if attempt < self.max_retries - 1:
                        retry_after = int(response.headers.get('Retry-After', self.retry_delay))
                        logger.warning(f"ETH API rate limited (429), retrying after {retry_after} seconds (attempt {attempt + 1})")
                        await asyncio.sleep(retry_after)
                        continue
                    else:
                        logger.error(f"ETH API max retries exceeded for rate limiting on {url}")
                        return None
                
                # Handle other HTTP errors
                if response.status_code >= 400:
                    logger.warning(f"ETH API HTTP {response.status_code} for {url}: {response.text}")
                    return None
                
                return response
                
            except Exception as e:
                if attempt < self.max_retries - 1:
                    logger.warning(f"ETH API request failed (attempt {attempt + 1}): {e}, retrying...")
                    await asyncio.sleep(self.retry_delay)
                    continue
                else:
                    logger.error(f"ETH API request failed after {self.max_retries} attempts: {e}")
                    return None
        
        return None
    
    async def get_eth_balance(self, address: str) -> float:
        """Get ETH balance for an address using API V2"""
        try:
            params = {
                "module": "account",
                "action": "balance", 
                "address": address,
                "tag": "latest",
                "apikey": self.api_key
            }
            
            # Add chainid for API v2 (required parameter)
            if self.use_v2_api:
                params["chainid"] = 1  # Ethereum mainnet
            
            response = await self._make_request_with_retry(self.eth_api_base, params)
            if response is None:
                return 0.0
                
            data = response.json()
            
            if data.get("status") == "1":
                # Convert from wei to ETH
                balance_wei = int(data.get("result", "0"))
                balance_eth = balance_wei / 10**18
                logger.info(f"ETH balance for {address}: {balance_eth}")
                return balance_eth
            else:
                logger.error(f"Error getting ETH balance: {data.get('message', 'Unknown error')}")
                return 0.0
                
        except Exception as e:
            logger.error(f"Exception getting ETH balance for {address}: {e}")
            return 0.0
    
    async def get_token_balance(self, address: str, token_contract: str, decimals: int = 18) -> float:
        """Get ERC-20 token balance for an address using API V2"""
        try:
            params = {
                "module": "account",
                "action": "tokenbalance",
                "contractaddress": token_contract,
                "address": address,
                "tag": "latest",
                "apikey": self.api_key
            }
            
            # Add chainid for API v2 (required parameter)
            if self.use_v2_api:
                params["chainid"] = 1  # Ethereum mainnet
            
            response = await self._make_request_with_retry(self.eth_api_base, params)
            if response is None:
                # Try Web3 fallback if API request failed
                return await self.get_token_balance_web3_fallback(address, token_contract, decimals)
                
            data = response.json()
            
            if data.get("status") == "1":
                balance_raw = int(data.get("result", "0"))
                balance = balance_raw / (10 ** decimals)
                
                # If API returns 0, try Web3 fallback for verification
                if balance == 0.0:
                    logger.warning(f"API returned 0 for {token_contract}, trying Web3 fallback...")
                    fallback_balance = await self.get_token_balance_web3_fallback(address, token_contract, decimals)
                    if fallback_balance > 0:
                        logger.info(f"Web3 fallback found balance: {fallback_balance}")
                        return fallback_balance
                
                return balance
            else:
                # API error (rate limit, etc.) - try Web3 fallback
                logger.warning(f"API error for {token_contract}: {data.get('message', 'Unknown')}, trying Web3 fallback...")
                fallback_balance = await self.get_token_balance_web3_fallback(address, token_contract, decimals)
                if fallback_balance > 0:
                    logger.info(f"Web3 fallback found balance after API error: {fallback_balance}")
                    return fallback_balance
                logger.error(f"Error getting token balance for {token_contract}: {data.get('message', 'Unknown error')} - Full response: {data}")
                return 0.0
                
        except Exception as e:
            logger.error(f"Exception getting token balance for {address}: {e}")
            return 0.0
    
    async def discover_wallet_tokens(self, address: str) -> List[Dict[str, str]]:
        """Discover all ERC-20 tokens held by a wallet"""
        try:
            # Get token transactions to discover what tokens this wallet has interacted with
            params = {
                "module": "account",
                "action": "tokentx",
                "address": address,
                "startblock": 0,
                "endblock": 99999999,
                "page": 1,
                "offset": 10000,  # Get more transactions to discover more tokens
                "sort": "desc",
                "apikey": self.api_key
            }
            
            # Add chainid for API v2 (required parameter)
            if self.use_v2_api:
                params["chainid"] = 1  # Ethereum mainnet
            
            response = await self._make_request_with_retry(self.eth_api_base, params)
            if response is None:
                logger.warning(f"Failed to discover tokens for {address}, using fallback tokens")
                # Return fallback tokens if discovery fails
                return [
                    {'symbol': 'USDT', 'name': 'Tether USD', 'contract': '0xdAC17F958D2ee523a2206206994597C13D831ec7', 'decimals': 6},
                    {'symbol': 'USDC', 'name': 'USD Coin', 'contract': '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', 'decimals': 6},
                    {'symbol': 'WETH', 'name': 'Wrapped Ether', 'contract': '0xC02aaA39b223FE8D0763b4DF1C5c72B3A7160096', 'decimals': 18},
                    {'symbol': 'DAI', 'name': 'Dai Stablecoin', 'contract': '0x6B175474E89094C44Da98b954EedeAC495271d0F', 'decimals': 18},
                    {'symbol': 'UNI', 'name': 'Uniswap', 'contract': '0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984', 'decimals': 18},
                    {'symbol': 'PEPE', 'name': 'Pepe', 'contract': '0x6982508145454ce325ddbe47a25d4ec3d2311933', 'decimals': 18},
                    {'symbol': 'SHIB', 'name': 'SHIBA INU', 'contract': '0x95aD61b0a150d79219dCF64E1E6Cc01f0B64C4cE', 'decimals': 18}
                ]
                
            data = response.json()
            
            tokens_found = {}
            
            if data.get("status") == "1" and data.get("result"):
                # Count token interactions to prioritize frequently used tokens
                token_interaction_count = {}
                
                for tx in data["result"]:
                    contract_address = tx.get("contractAddress", "").lower()
                    token_symbol = tx.get("tokenSymbol", "")
                    token_name = tx.get("tokenName", "")
                    token_decimals = int(tx.get("tokenDecimal", "18"))
                    
                    # Skip if we don't have essential info
                    if not contract_address or not token_symbol:
                        continue
                    
                    # Filter out scam tokens
                    if not self.is_legitimate_token(token_symbol, contract_address):
                        continue
                    
                    # Count interactions
                    if contract_address not in token_interaction_count:
                        token_interaction_count[contract_address] = 0
                    token_interaction_count[contract_address] += 1
                    
                    # Use contract address as key to avoid duplicates
                    if contract_address not in tokens_found:
                        tokens_found[contract_address] = {
                            'symbol': token_symbol,
                            'name': token_name,
                            'contract': contract_address,
                            'decimals': token_decimals,
                            'interactions': 0
                        }
                
                # Update interaction counts
                for contract_address, count in token_interaction_count.items():
                    if contract_address in tokens_found:
                        tokens_found[contract_address]['interactions'] = count
            
            # Convert to list and prioritize by interaction count
            discovered_tokens = list(tokens_found.values())
            discovered_tokens.sort(key=lambda x: x.get('interactions', 0), reverse=True)
            
            # Add our hardcoded high-value tokens at the beginning, removing them from their original positions if found
            priority_tokens = [
                {'symbol': 'USDT', 'name': 'Tether USD', 'contract': '0xdAC17F958D2ee523a2206206994597C13D831ec7', 'decimals': 6},
                {'symbol': 'USDC', 'name': 'USD Coin', 'contract': '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', 'decimals': 6},
                {'symbol': 'WETH', 'name': 'Wrapped Ether', 'contract': '0xC02aaA39b223FE8D0763b4DF1C5c72B3A7160096', 'decimals': 18},
                {'symbol': 'DAI', 'name': 'Dai Stablecoin', 'contract': '0x6B175474E89094C44Da98b954EedeAC495271d0F', 'decimals': 18},
                {'symbol': 'UNI', 'name': 'Uniswap', 'contract': '0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984', 'decimals': 18},
                {'symbol': 'PEPE', 'name': 'Pepe', 'contract': '0x6982508145454ce325ddbe47a25d4ec3d2311933', 'decimals': 18},
                {'symbol': 'SHIB', 'name': 'SHIBA INU', 'contract': '0x95aD61b0a150d79219dCF64E1E6Cc01f0B64C4cE', 'decimals': 18}
            ]
            
            # Remove priority tokens from discovered list if they exist there
            priority_contract_addresses = {token['contract'].lower() for token in priority_tokens}
            discovered_tokens = [token for token in discovered_tokens if token['contract'].lower() not in priority_contract_addresses]
            
            # Create final list with priority tokens first, then discovered tokens
            final_tokens = priority_tokens + discovered_tokens
            
            logger.info(f"Discovered {len(final_tokens)} unique tokens for {address} (prioritized by interaction frequency)")
            return final_tokens
            
        except Exception as e:
            logger.error(f"Error discovering tokens for {address}: {e}")
            # Return fallback tokens if discovery fails
            return [
                {'symbol': 'USDT', 'name': 'Tether USD', 'contract': '0xdAC17F958D2ee523a2206206994597C13D831ec7', 'decimals': 6},
                {'symbol': 'USDC', 'name': 'USD Coin', 'contract': '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', 'decimals': 6},
                {'symbol': 'WETH', 'name': 'Wrapped Ether', 'contract': '0xC02aaA39b223FE8D0763b4DF1C5c72B3A7160096', 'decimals': 18},
                {'symbol': 'DAI', 'name': 'Dai Stablecoin', 'contract': '0x6B175474E89094C44Da98b954EedeAC495271d0F', 'decimals': 18},
                {'symbol': 'UNI', 'name': 'Uniswap', 'contract': '0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984', 'decimals': 18},
                {'symbol': 'PEPE', 'name': 'Pepe', 'contract': '0x6982508145454ce325ddbe47a25d4ec3d2311933', 'decimals': 18},
                {'symbol': 'SHIB', 'name': 'SHIBA INU', 'contract': '0x95aD61b0a150d79219dCF64E1E6Cc01f0B64C4cE', 'decimals': 18}
            ]
    
    async def get_wallet_balances(self, address: str) -> Dict[str, float]:
        """Get all balances (ETH + tokens) for a wallet"""
        balances = {}
        
        # For development/demo: return mock data if API key is not configured
        if self.api_key == "YourApiKeyToken":
            logger.warning(f"Using mock data for {address} - No API key configured")
            return {
                "ETH": 0.1234,
                "USDT": 100.50,
                "USDC": 75.25,
                "DAI": 50.00,
                "WETH": 0.0567
            }
        
        # Get ETH balance
        eth_balance = await self.get_eth_balance(address)
        balances["ETH"] = eth_balance
        
        # Get all ERC-20 tokens held by this address
        discovered_tokens = await self.discover_wallet_tokens(address)
        logger.info(f"Discovered {len(discovered_tokens)} tokens for {address}")
        
        # Process tokens in smaller batches to avoid timeouts
        # Batch size based on API version (higher throughput with v2)
        batch_size = 50 if self.use_v2_api else 20  # Process more tokens at once with API v2
        tokens_with_balance = []
        
        for i in range(0, len(discovered_tokens), batch_size):
            batch = discovered_tokens[i:i + batch_size]
            logger.info(f"Processing token batch {i//batch_size + 1}/{(len(discovered_tokens) + batch_size - 1)//batch_size} ({len(batch)} tokens)")
            
            for token_info in batch:
                token_symbol = token_info['symbol']
                contract_address = token_info['contract']
                decimals = token_info['decimals']
                
                # Double-check token legitimacy before processing
                if not self.is_legitimate_token(token_symbol, contract_address):
                    continue
                
                token_balance = await self.get_token_balance(address, contract_address, decimals)
                if token_balance > 0:  # Only include tokens with positive balance
                    balances[token_symbol] = token_balance
                    tokens_with_balance.append(f"{token_symbol}: {token_balance}")
                
                # Small delay to avoid rate limiting (reduced for API v2)
                if self.use_v2_api:
                    await asyncio.sleep(0.05)  # Much faster with API v2 (100+ calls/second)
                else:
                    await asyncio.sleep(0.2)  # Conservative delay for API v1
            
            # Shorter delay between batches (API v2 handles higher throughput)
            if i + batch_size < len(discovered_tokens):
                logger.info(f"Batch {i//batch_size + 1} complete. Tokens with balance so far: {len(tokens_with_balance)}")
                if self.use_v2_api:
                    await asyncio.sleep(0.5)  # Much shorter delay with API v2
                else:
                    await asyncio.sleep(2)  # Conservative delay for API v1
        
        logger.info(f"Retrieved balances for {address}: {balances}")
        logger.info(f"Tokens with positive balances: {tokens_with_balance}")
        return balances
    
    async def get_wallet_transactions(self, address: str, limit: int = 50) -> List[Dict]:
        """Get recent transactions for a wallet"""
        # For development/demo: return mock data if API key is not configured
        if self.api_key == "YourApiKeyToken":
            logger.warning(f"Using mock transaction data for {address} - No API key configured")
            import time
            current_time = int(time.time())
            return [
                {
                    "hash": "0x123456789abcdef...",
                    "type": "ETH",
                    "amount": 0.5,
                    "from": "0x742b4D6E4C8D8B0F5a1B8E",
                    "to": address,
                    "timestamp": current_time - 3600,
                    "block": "19123456",
                    "status": "Success",
                    "blockchain": "ETH"
                },
                {
                    "hash": "0xabcdef123456789...",
                    "type": "USDT",
                    "amount": 100.0,
                    "from": address,
                    "to": "0x987fEDCBA123456789",
                    "timestamp": current_time - 7200,
                    "block": "19123400",
                    "status": "Success",
                    "blockchain": "ETH"
                }
            ]
        
        transactions = []
        
        try:
            # Get ETH transactions
            eth_txs = await self._get_eth_transactions(address, limit // 2)
            transactions.extend(eth_txs)
            
            # Get ERC-20 token transactions
            token_txs = await self._get_token_transactions(address, limit // 2)
            transactions.extend(token_txs)
            
            # Sort by timestamp (newest first)
            transactions.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
            
            return transactions[:limit]
            
        except Exception as e:
            logger.error(f"Error getting transactions for {address}: {e}")
            return []
    
    async def _get_eth_transactions(self, address: str, limit: int = 25) -> List[Dict]:
        """Get ETH transactions using API V2"""
        try:
            params = {
                "module": "account",
                "action": "txlist",
                "address": address,
                "startblock": 0,
                "endblock": 99999999,
                "page": 1,
                "offset": limit,
                "sort": "desc",
                "apikey": self.api_key
            }
            
            # Add chainid for API v2 (required parameter)
            if self.use_v2_api:
                params["chainid"] = 1  # Ethereum mainnet
            
            response = await self.session.get(self.eth_api_base, params=params)
            data = response.json()
            
            if data.get("status") == "1" and data.get("result"):
                transactions = []
                for tx in data["result"]:
                    # Format transaction
                    amount = float(tx.get("value", "0")) / 10**18  # Convert from wei
                    
                    transactions.append({
                        "hash": tx.get("hash"),
                        "type": "ETH",
                        "amount": amount,
                        "from": tx.get("from"),
                        "to": tx.get("to"),
                        "timestamp": int(tx.get("timeStamp", 0)),
                        "block": tx.get("blockNumber"),
                        "status": "Success" if tx.get("txreceipt_status") == "1" else "Failed",
                        "blockchain": "ETH"
                    })
                
                return transactions
            else:
                logger.warning(f"No ETH transactions found for {address}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting ETH transactions: {e}")
            return []
    
    async def _get_token_transactions(self, address: str, limit: int = 25) -> List[Dict]:
        """Get ERC-20 token transactions using API V2"""
        try:
            params = {
                "module": "account",
                "action": "tokentx",
                "address": address,
                "startblock": 0,
                "endblock": 99999999,
                "page": 1,
                "offset": limit,
                "sort": "desc",
                "apikey": self.api_key
            }
            
            # Add chainid for API v2 (required parameter)
            if self.use_v2_api:
                params["chainid"] = 1  # Ethereum mainnet
            
            response = await self._make_request_with_retry(self.eth_api_base, params)
            if response is None:
                logger.warning(f"Failed to get token transactions for {address}")
                return []
                
            data = response.json()
            
            if data.get("status") == "1" and data.get("result"):
                transactions = []
                for tx in data["result"]:
                    # Determine token symbol and decimals
                    token_symbol = tx.get("tokenSymbol", "TOKEN")
                    token_decimals = int(tx.get("tokenDecimal", "18"))
                    
                    # Convert amount
                    amount = float(tx.get("value", "0")) / (10 ** token_decimals)
                    
                    transactions.append({
                        "hash": tx.get("hash"),
                        "type": token_symbol,
                        "amount": amount,
                        "from": tx.get("from"),
                        "to": tx.get("to"),
                        "timestamp": int(tx.get("timeStamp", 0)),
                        "block": tx.get("blockNumber"),
                        "status": "Success",  # Token transactions that appear are usually successful
                        "blockchain": "ETH"
                    })
                
                return transactions
            else:
                logger.warning(f"No token transactions found for {address}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting token transactions: {e}")
            return []
    
    async def get_token_balance_web3_fallback(self, address: str, token_contract: str, decimals: int = 18) -> float:
        """Fallback method to get token balance using Web3 directly from blockchain"""
        try:
            import asyncio
            
            def _get_balance():
                # Use multiple public RPC providers as fallback
                rpc_providers = [
                    'https://eth.llamarpc.com',
                    'https://rpc.ankr.com/eth',
                    'https://ethereum.publicnode.com',
                    'https://eth.drpc.org'
                ]
                
                for rpc_url in rpc_providers:
                    try:
                        w3 = Web3(Web3.HTTPProvider(rpc_url))
                        
                        if not w3.is_connected():
                            continue
                        
                        # ERC-20 balanceOf function signature
                        balance_of_abi = [{
                            "constant": True,
                            "inputs": [{"name": "_owner", "type": "address"}],
                            "name": "balanceOf",
                            "outputs": [{"name": "balance", "type": "uint256"}],
                            "type": "function"
                        }]
                        
                        # Create contract instance
                        contract = w3.eth.contract(
                            address=Web3.to_checksum_address(token_contract),
                            abi=balance_of_abi
                        )
                        
                        # Call balanceOf function
                        balance_raw = contract.functions.balanceOf(Web3.to_checksum_address(address)).call()
                        balance = balance_raw / (10 ** decimals)
                        
                        logger.info(f"Web3 success with {rpc_url}")
                        return balance
                        
                    except Exception as e:
                        logger.warning(f"Web3 RPC {rpc_url} failed: {e}")
                        continue
                
                logger.error("All Web3 RPC providers failed")
                return 0.0
            
            # Run in thread pool to avoid blocking
            balance = await asyncio.get_event_loop().run_in_executor(None, _get_balance)
            logger.info(f"Web3 fallback: Token balance for {address} ({token_contract}): {balance}")
            return balance
            
        except Exception as e:
            logger.error(f"Web3 fallback failed for {address}: {e}")
            return 0.0

    async def close(self):
        """Close the HTTP session"""
        await self.session.aclose()
    
    async def get_wallet_balances_with_notifications(self, address: str, wallet_id: int) -> Dict[str, float]:
        """Get wallet balances and send WebSocket notifications for updates"""
        try:
            balances = await self.get_wallet_balances(address)
            
            # Send WebSocket notification for ETH balance update
            from websocket_manager import websocket_manager
            await websocket_manager.broadcast({
                "type": "eth_balance_update",
                "data": {
                    "wallet_id": wallet_id,
                    "address": address,
                    "blockchain": "ETH",
                    "token_balances": balances,
                    "timestamp": datetime.utcnow().isoformat()
                }
            })
            
            return balances
            
        except Exception as e:
            logger.error(f"Error getting ETH wallet balances with notifications: {e}")
            return {}

    async def get_recent_transactions_with_notifications(self, address: str, wallet_id: int, since_timestamp: int) -> list:
        """Get recent transactions and send WebSocket notifications for new ones"""
        try:
            # Get recent transactions with better time filtering
            # Convert timestamp to hours for filtering
            current_time = int(datetime.utcnow().timestamp())
            hours_back = max(1, (current_time - since_timestamp) // 3600)  # Convert to hours, minimum 1 hour
            
            transactions = await self.get_wallet_transactions_since(address, int(hours_back), 100)
            
            # Filter transactions newer than timestamp
            new_transactions = []
            
            for tx in transactions:
                tx_timestamp = tx.get('timestamp', 0)
                if isinstance(tx_timestamp, str):
                    # Convert from ISO string to timestamp
                    try:
                        tx_timestamp = int(datetime.fromisoformat(tx_timestamp.replace('Z', '+00:00')).timestamp())
                    except:
                        tx_timestamp = current_time
                
                # Handle millisecond timestamps
                if tx_timestamp > 10000000000:
                    tx_timestamp = tx_timestamp // 1000
                
                if tx_timestamp > since_timestamp:
                    new_transactions.append(tx)
                    
                    # Send WebSocket notification for each new transaction
                    from websocket_manager import manager
                    await manager.broadcast({
                        "type": "eth_transaction",
                        "data": {
                            "wallet_id": wallet_id,
                            "address": address,
                            "transaction": tx,
                            "blockchain": "ETH",
                            "timestamp": tx_timestamp
                        }
                    })
                    
                    # Also send transaction notification
                    transaction_msg = f"New ETH {tx.get('type', 'transaction')}: {tx.get('amount', 0)} {tx.get('type', 'ETH')}"
                    await manager.broadcast({
                        "type": "transaction_notification",
                        "data": {
                            "transaction": tx,
                            "message": transaction_msg,
                            "wallet_id": wallet_id,
                            "blockchain": "ETH"
                        }
                    })
                    
                    # Create balance history record after each new transaction
                    await self._create_transaction_balance_history(wallet_id, tx)
            
            return new_transactions
            
        except Exception as e:
            logger.error(f"Error getting recent ETH transactions with notifications: {e}")
            return []

    async def _create_transaction_balance_history(self, wallet_id: int, transaction: dict):
        """Create balance history record after a transaction"""
        try:
            from database import get_db, BalanceHistory, Token, Blockchain, Wallet
            from sqlalchemy import select
            
            async for db in get_db():
                try:
                    # Get ETH blockchain
                    eth_blockchain = await db.execute(
                        select(Blockchain).where(Blockchain.name == "ETH")
                    )
                    eth_blockchain = eth_blockchain.scalar_one_or_none()
                    if not eth_blockchain:
                        return
                    
                    # Determine token based on transaction type
                    token_symbol = "ETH" if transaction.get('type') == "ETH" else "USDT"
                    
                    # Get token
                    token = await db.execute(
                        select(Token).where(
                            Token.symbol == token_symbol,
                            Token.blockchain_id == eth_blockchain.id
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
                    if token_symbol == "ETH":
                        current_balance = await self.get_eth_balance(wallet.address)
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
                    
                    logger.info(f"Created ETH transaction balance history for wallet {wallet_id}, amount: {tx_amount}")
                    
                except Exception as db_error:
                    logger.error(f"Database error creating transaction balance history: {db_error}")
                    await db.rollback()
                finally:
                    break
                    
        except Exception as e:
            logger.error(f"Error creating transaction balance history: {e}")
    
    async def get_wallet_transactions_since(self, address: str, hours: int = 24, limit: int = 100) -> List[Dict]:
        """Get wallet transactions from the last N hours"""
        from datetime import datetime, timedelta
        
        # Calculate cutoff time
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        cutoff_timestamp = int(cutoff_time.timestamp())
        
        logger.info(f"Getting ETH transactions for {address} since {cutoff_time.isoformat()} (last {hours}h)")
        
        try:
            # Get more transactions to ensure we catch all within the time window
            all_transactions = await self.get_wallet_transactions(address, limit * 2)
            
            # Filter transactions by time
            recent_transactions = []
            for tx in all_transactions:
                tx_timestamp = tx.get('timestamp', 0)
                
                # Handle different timestamp formats
                if isinstance(tx_timestamp, str):
                    try:
                        tx_time = datetime.fromisoformat(tx_timestamp.replace('Z', '+00:00'))
                        tx_timestamp = int(tx_time.timestamp())
                    except:
                        continue
                
                # Handle millisecond timestamps
                if tx_timestamp > 10000000000:
                    tx_timestamp = tx_timestamp // 1000
                
                # Only include transactions from the time window
                if tx_timestamp >= cutoff_timestamp:
                    recent_transactions.append(tx)
            
            # Sort by timestamp (newest first)
            recent_transactions.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
            
            logger.info(f"Found {len(recent_transactions)} ETH transactions in last {hours} hours for {address}")
            return recent_transactions[:limit]
            
        except Exception as e:
            logger.error(f"Error getting recent ETH transactions: {e}")
            return []
