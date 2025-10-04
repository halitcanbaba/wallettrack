"""
CoinTR API service for orderbook data
"""
import asyncio
import aiohttp
import json
import ssl
from typing import Dict, List, Optional
from app.core.config import COINTR_BASE_URL, COINTR_COMMISSION_BPS, KDV_RATE
from app.core.dependencies import logger

class CoinTRService:
    def __init__(self):
        self.base_url = COINTR_BASE_URL
        self.commission_bps = COINTR_COMMISSION_BPS
        self.kdv_rate = KDV_RATE
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            # Create SSL context that doesn't verify certificates
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10),
                connector=connector
            )
        return self.session
    
    async def close(self):
        """Close the aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    def calculate_commission(self, amount: float) -> float:
        """Calculate commission from amount using bps"""
        return amount * (self.commission_bps / 10000)
    
    def calculate_kdv(self, commission: float) -> float:
        """Calculate KDV from commission"""
        return commission * self.kdv_rate
    
    def calculate_net_price(self, price: float, amount: float) -> Dict[str, float]:
        """Calculate all price components"""
        commission = self.calculate_commission(amount)
        kdv = self.calculate_kdv(commission)
        net_price = price - commission - kdv
        
        return {
            "raw_price": price,
            "commission": commission,
            "kdv": kdv,
            "net_price": net_price,
            "total_fees": commission + kdv
        }
    
    async def get_orderbook(self, symbol: str = "USDTTRY", limit: int = 20) -> Optional[Dict]:
        """
        Get orderbook data from CoinTR API
        
        Args:
            symbol: Trading pair symbol (default: USDTTRY)
            limit: Number of levels to return (max 150)
        
        Returns:
            Dict with bids and asks or None if error
        """
        try:
            session = await self.get_session()
            
            # CoinTR orderbook endpoint - v2 API
            url = f"{self.base_url}/api/v2/spot/market/orderbook"
            params = {
                "symbol": symbol,
                "type": "step0",  # No aggregation
                "limit": min(limit, 150)  # CoinTR max limit is 150
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # CoinTR API returns {code: "00000", data: {asks: [[price, amount]], bids: [[price, amount]]}}
                    if data.get("code") == "00000" and "data" in data:
                        orderbook_data = data["data"]
                        if "asks" in orderbook_data and "bids" in orderbook_data:
                            # Convert to our format and take first 8 levels
                            orderbook = {
                                "bids": [[float(item[0]), float(item[1])] for item in orderbook_data["bids"][:8]],
                                "asks": [[float(item[0]), float(item[1])] for item in orderbook_data["asks"][:8]],
                                "symbol": symbol,
                                "exchange": "cointr"
                            }
                            
                            return orderbook
                        else:
                            logger.error(f"❌ CoinTR API missing orderbook data: {orderbook_data}")
                            return None
                    else:
                        logger.error(f"❌ CoinTR API error response: {data}")
                        return None
                else:
                    logger.error(f"❌ CoinTR API error: {response.status}")
                    return None
                    
        except asyncio.TimeoutError:
            logger.error("⏰ CoinTR API timeout")
            return None
        except Exception as e:
            logger.error(f"💥 CoinTR API error: {str(e)}")
            return None
    
    async def get_ticker_price(self, symbol: str = "USDTTRY") -> Optional[float]:
        """
        Get current price for a symbol from CoinTR
        
        Args:
            symbol: Trading pair symbol (default: USDTTRY)
            
        Returns:
            Current price or None if error
        """
        try:
            session = await self.get_session()
            
            # CoinTR ticker endpoint
            url = f"{self.base_url}/api/v2/spot/market/tickers"
            params = {"symbol": symbol}
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get("code") == "00000" and "data" in data:
                        ticker_data = data["data"]
                        if "lastPrice" in ticker_data:
                            price = float(ticker_data["lastPrice"])
                            logger.info(f"📊 CoinTR {symbol} price: {price}")
                            return price
                        else:
                            logger.error(f"❌ CoinTR ticker missing lastPrice: {ticker_data}")
                            return None
                    else:
                        logger.error(f"❌ CoinTR ticker API error: {data}")
                        return None
                else:
                    logger.error(f"❌ CoinTR ticker API error: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"💥 CoinTR ticker error: {str(e)}")
            return None
    
    async def get_24hr_ticker(self, symbol: str) -> Optional[Dict]:
        """
        Get 24hr ticker data from CoinTR API v2 public endpoint
        
        Args:
            symbol: Trading pair symbol (e.g., BTCTRY, ETHTRY)
        
        Returns:
            Dict with ticker data including price, volume, change
        """
        try:
            session = await self.get_session()
            
            # CoinTR v2 API - tickers endpoint
            url = f"{self.base_url}/api/v2/spot/market/tickers"
            params = {"symbol": symbol}
            
            logger.info(f"� CoinTR fetching ticker for {symbol}")
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # CoinTR returns: {code: "00000", msg: "success", data: [{...}]}
                    if data.get('code') == '00000' and data.get('data'):
                        ticker_list = data['data']
                        
                        if isinstance(ticker_list, list) and len(ticker_list) > 0:
                            ticker = ticker_list[0]
                            
                            # Parse CoinTR response fields
                            ticker_data = {
                                'symbol': ticker.get('symbol', symbol),
                                'price': float(ticker.get('lastPr', 0)),
                                'volume': float(ticker.get('baseVolume', 0)),
                                'quoteVolume': float(ticker.get('quoteVolume', 0)),
                                'change': float(ticker.get('change24h', 0)),
                                'changePercent': float(ticker.get('change24h', 0)) * 100,  # Convert to percentage
                                'high': float(ticker.get('high24h', 0)),
                                'low': float(ticker.get('low24h', 0)),
                                'open': float(ticker.get('open', 0))
                            }
                            
                            logger.info(f"✅ CoinTR ticker for {symbol}: Price={ticker_data['price']}, Vol={ticker_data['quoteVolume']}")
                            return ticker_data
                        else:
                            logger.warning(f"⚠️ CoinTR: No data in response for {symbol}")
                            return None
                    else:
                        logger.error(f"❌ CoinTR API error for {symbol}: code={data.get('code')}, msg={data.get('msg')}")
                        return None
                else:
                    error_text = await response.text()
                    logger.error(f"❌ CoinTR API HTTP error for {symbol}: {response.status} - {error_text[:200]}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ CoinTR Exception getting ticker for {symbol}: {str(e)}")
            return None
    
    async def get_all_symbols(self, quote_asset: Optional[str] = None) -> List[str]:
        """
        Get all trading symbols from CoinTR
        
        Args:
            quote_asset: Filter by quote asset (e.g., "TRY")
        
        Returns:
            List of symbol strings
        """
        try:
            # Use tickers endpoint to get all symbols with their data
            session = await self.get_session()
            url = f"{self.base_url}/api/v2/spot/market/tickers"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get('code') == '00000' and data.get('data'):
                        tickers = data['data']
                        symbols = []
                        
                        for ticker in tickers:
                            symbol = ticker.get('symbol', '')
                            if symbol:
                                # Filter by quote asset if specified
                                if quote_asset is None or symbol.endswith(quote_asset):
                                    symbols.append(symbol)
                        
                        logger.info(f"📋 CoinTR: {len(symbols)} symbols loaded" + 
                                  (f" (filtered by {quote_asset})" if quote_asset else ""))
                        return symbols
                    else:
                        logger.error(f"❌ CoinTR tickers API error: code={data.get('code')}")
                        return []
                else:
                    logger.error(f"❌ CoinTR tickers API HTTP error: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"💥 CoinTR get_all_symbols error: {str(e)}")
            return []
    
    async def get_trading_pairs(self) -> Optional[List[Dict]]:
        """
        Get all trading pairs from CoinTR
        
        Returns:
            List of trading pair information or None if error
        """
        try:
            session = await self.get_session()
            
            # CoinTR symbols endpoint
            url = f"{self.base_url}/api/v2/spot/market/symbols"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get("code") == "00000" and "data" in data:
                        pairs = []
                        for pair in data["data"]:
                            pairs.append({
                                "symbol": pair.get("symbol", ""),
                                "base_currency": pair.get("baseCurrency", ""),
                                "counter_currency": pair.get("quoteCurrency", ""),
                                "status": pair.get("status", "")
                            })
                        
                        logger.info(f"📋 CoinTR: {len(pairs)} trading pairs loaded")
                        return pairs
                    else:
                        logger.error(f"❌ CoinTR symbols API error: {data}")
                        return None
                else:
                    logger.error(f"❌ CoinTR symbols API error: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"💥 CoinTR trading pairs error: {str(e)}")
            return None
    
    async def get_ticker(self, base: str, quote: str) -> Optional[Dict]:
        """
        Get ticker for a specific trading pair
        
        Args:
            base: Base currency (e.g., "USDT")
            quote: Quote currency (e.g., "TRY")
            
        Returns:
            Ticker data or None if error
        """
        symbol = f"{base}{quote}"
        return await self.get_24hr_ticker(symbol)
    
    async def get_order_book(self, base: str, quote: str, limit: int = 20) -> Optional[Dict]:
        """
        Get order book for a specific trading pair
        
        Args:
            base: Base currency (e.g., "USDT")
            quote: Quote currency (e.g., "TRY")
            limit: Number of levels to return
            
        Returns:
            Order book data or None if error
        """
        symbol = f"{base}{quote}"
        orderbook = await self.get_orderbook(symbol, limit)
        
        if orderbook:
            # Convert to format expected by analytics API
            return {
                "bid": [[price, amt] for price, amt in orderbook["bids"]],
                "ask": [[price, amt] for price, amt in orderbook["asks"]],
                "symbol": symbol
            }
        return None
    
    async def get_klines(self, symbol: str, interval: str = "1m", limit: int = 100, start_time: int = None, end_time: int = None) -> Optional[List[List]]:
        """
        Get kline/candlestick data from CoinTR
        
        Args:
            symbol: Trading pair symbol (e.g., USDTTRY)
            interval: Time interval (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w, 1M)
            limit: Number of klines to return (max 200)
            start_time: Start time in milliseconds (optional)
            end_time: End time in milliseconds (optional)
            
        Returns:
            List of klines or None if error
            Each kline: [timestamp, open, high, low, close, volume]
        """
        try:
            session = await self.get_session()
            
            # CoinTR interval mapping (convert from standard to CoinTR granularity format)
            interval_map = {
                "1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min",
                "1h": "1h", "4h": "4h", "6h": "6h", "12h": "12h",
                "1d": "1day", "3d": "3day", "1w": "1week", "1M": "1M"
            }
            granularity = interval_map.get(interval, "1min")
            
            # Get current time in milliseconds for endTime if not provided
            if not end_time:
                import time
                end_time = int(time.time() * 1000)
            
            # CoinTR history candles endpoint - v2 API
            url = f"{self.base_url}/api/v2/spot/market/history-candles"
            params = {
                "symbol": symbol,
                "granularity": granularity,
                "endTime": str(end_time),
                "limit": str(min(limit, 200))  # CoinTR max is 200
            }
            
            # CoinTR doesn't have startTime parameter, only endTime
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # CoinTR returns: {code: "00000", data: [[timestamp, open, high, low, close, volume, quoteVolume, usdtVolume]]}
                    if data.get("code") == "00000" and "data" in data:
                        klines = data["data"]
                        # Convert to standard format: [timestamp, open, high, low, close, volume]
                        formatted_klines = []
                        for k in klines:
                            formatted_klines.append([
                                int(k[0]),       # timestamp already in milliseconds
                                float(k[1]),     # open
                                float(k[2]),     # high
                                float(k[3]),     # low
                                float(k[4]),     # close
                                float(k[5])      # volume (base currency)
                            ])
                        logger.info(f"📊 CoinTR: Fetched {len(formatted_klines)} klines for {symbol}")
                        return formatted_klines
                    else:
                        error_msg = data.get("msg", "Unknown error")
                        logger.warning(f"⚠️ CoinTR klines API error: {error_msg}")
                        return None
                else:
                    error_text = await response.text()
                    logger.error(f"❌ CoinTR klines HTTP error: {response.status} - {error_text}")
                    return None
                    
        except asyncio.TimeoutError:
            logger.error("⏰ CoinTR klines API timeout")
            return None
        except Exception as e:
            logger.error(f"💥 CoinTR klines error: {str(e)}")
            return None
    
    async def get_klines_paginated(self, symbol: str, interval: str = "1m", total_limit: int = 1000, start_time: int = None, end_time: int = None) -> Optional[List[List]]:
        """
        Get kline/candlestick data with pagination to fetch more than 200 candles
        
        Args:
            symbol: Trading pair symbol (e.g., USDTTRY)
            interval: Time interval (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w, 1M)
            total_limit: Total number of klines to fetch (will make multiple requests)
            start_time: Start time in milliseconds (optional)
            end_time: End time in milliseconds (optional)
            
        Returns:
            List of all klines or None if error
        """
        try:
            import time
            
            all_klines = []
            remaining = total_limit
            
            # Use provided end_time or current time
            if not end_time:
                end_time = int(time.time() * 1000)
            
            # CoinTR interval mapping
            interval_map = {
                "1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min",
                "1h": "1h", "4h": "4h", "6h": "6h", "12h": "12h",
                "1d": "1day", "3d": "3day", "1w": "1week", "1M": "1M"
            }
            granularity = interval_map.get(interval, "1min")
            
            # Calculate milliseconds per candle
            interval_ms = {
                "1min": 60 * 1000,
                "5min": 5 * 60 * 1000,
                "15min": 15 * 60 * 1000,
                "30min": 30 * 60 * 1000,
                "1h": 60 * 60 * 1000,
                "4h": 4 * 60 * 60 * 1000,
                "6h": 6 * 60 * 60 * 1000,
                "12h": 12 * 60 * 60 * 1000,
                "1day": 24 * 60 * 60 * 1000,
                "3day": 3 * 24 * 60 * 60 * 1000,
                "1week": 7 * 24 * 60 * 60 * 1000,
                "1M": 30 * 24 * 60 * 60 * 1000
            }
            candle_duration = interval_ms.get(granularity, 60 * 1000)
            
            while remaining > 0:
                # Fetch batch (max 200 per request)
                batch_size = min(remaining, 200)
                
                session = await self.get_session()
                url = f"{self.base_url}/api/v2/spot/market/history-candles"
                params = {
                    "symbol": symbol,
                    "granularity": granularity,
                    "endTime": str(end_time),
                    "limit": str(batch_size)
                }
                
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        break
                    
                    data = await response.json()
                    
                    if data.get("code") != "00000" or "data" not in data:
                        break
                    
                    klines = data["data"]
                    
                    if not klines or len(klines) == 0:
                        break
                    
                    # Convert to standard format
                    for k in klines:
                        all_klines.append([
                            int(k[0]),       # timestamp
                            float(k[1]),     # open
                            float(k[2]),     # high
                            float(k[3]),     # low
                            float(k[4]),     # close
                            float(k[5])      # volume
                        ])
                    
                    remaining -= len(klines)
                    
                    # If we got less than requested, no more data available
                    if len(klines) < batch_size:
                        break
                    
                    # Set endTime to the oldest timestamp minus one candle duration for next batch
                    # CoinTR returns data in descending order (newest first)
                    oldest_timestamp = int(klines[-1][0])
                    end_time = oldest_timestamp - candle_duration
                    
                    # Small delay to avoid rate limiting (20 req/sec limit)
                    await asyncio.sleep(0.05)
            
            # CoinTR returns newest first, but we want chronological order
            all_klines.reverse()
            
            logger.info(f"📊 CoinTR: Fetched {len(all_klines)} klines for {symbol} (paginated)")
            return all_klines if all_klines else None
                    
        except Exception as e:
            logger.error(f"❌ CoinTR paginated klines error: {str(e)}")
            return None

# Create global instance
cointr_service = CoinTRService()
