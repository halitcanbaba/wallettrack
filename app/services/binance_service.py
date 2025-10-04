"""
Binance API service for orderbook data
"""
import asyncio
import aiohttp
import json
import ssl
from typing import Dict, List, Optional
from app.core.config import BINANCE_BASE_URL, BINANCE_COMMISSION_BPS, KDV_RATE
from app.core.dependencies import logger

class BinanceService:
    def __init__(self):
        self.base_url = BINANCE_BASE_URL
        self.commission_bps = BINANCE_COMMISSION_BPS
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
        Get orderbook data from Binance API
        
        Args:
            symbol: Trading pair symbol (default: USDTTRY)
            limit: Number of levels to return (5, 10, 20, 50, 100, 500, 1000, 5000)
        
        Returns:
            Dict with bids and asks or None if error
        """
        try:
            session = await self.get_session()
            
            url = f"{self.base_url}/api/v3/depth"
            params = {
                "symbol": symbol.upper(),
                "limit": limit
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Convert to our format and take first 8 levels
                    orderbook = {
                        "bids": [[float(price), float(qty)] for price, qty in data["bids"][:8]],
                        "asks": [[float(price), float(qty)] for price, qty in data["asks"][:8]],
                        "symbol": symbol,
                        "lastUpdateId": data.get("lastUpdateId"),
                        "exchange": "binance"
                    }
                    
                    return orderbook
                else:
                    logger.error(f"❌ Binance API error: {response.status}")
                    return None
                    
        except asyncio.TimeoutError:
            logger.error("⏰ Binance API timeout")
            return None
        except Exception as e:
            logger.error(f"💥 Binance API error: {str(e)}")
            return None
    
    async def get_ticker_price(self, symbol: str = "USDTTRY") -> Optional[float]:
        """
        Get current price for a symbol
        
        Args:
            symbol: Trading pair symbol (default: USDTTRY)
            
        Returns:
            Current price or None if error
        """
        try:
            session = await self.get_session()
            
            url = f"{self.base_url}/api/v3/ticker/price"
            params = {"symbol": symbol.upper()}
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    price = float(data["price"])
                    logger.info(f"📊 Binance {symbol} price: {price}")
                    return price
                else:
                    logger.error(f"❌ Binance ticker API error: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"💥 Binance ticker error: {str(e)}")
            return None
    
    async def get_all_symbols(self) -> Optional[List[Dict]]:
        """
        Get all trading symbols from Binance
        
        Returns:
            List of symbol information or None if error
        """
        try:
            session = await self.get_session()
            
            url = f"{self.base_url}/api/v3/exchangeInfo"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    symbols = data.get("symbols", [])
                    logger.info(f"📋 Binance: {len(symbols)} symbols loaded")
                    return symbols
                else:
                    logger.error(f"❌ Binance exchangeInfo API error: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"💥 Binance exchangeInfo error: {str(e)}")
            return None
    
    async def get_24h_ticker(self, symbol: Optional[str] = None) -> Optional[Dict]:
        """
        Get 24h ticker data
        
        Args:
            symbol: Optional symbol filter, if None returns all symbols
            
        Returns:
            Dict or List of ticker data
        """
        try:
            session = await self.get_session()
            
            url = f"{self.base_url}/api/v3/ticker/24hr"
            params = {}
            if symbol:
                params["symbol"] = symbol.upper()
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    logger.error(f"❌ Binance 24h ticker API error: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"💥 Binance 24h ticker error: {str(e)}")
            return None
    
    async def get_all_coins_info(self) -> Optional[List[Dict]]:
        """
        Get all coins information (requires API key for withdrawal info)
        This is a public approximation using available data
        
        Returns:
            List of coin information or None if error
        """
        try:
            # Since withdrawal fees require authentication, we return exchange info instead
            symbols = await self.get_all_symbols()
            if not symbols:
                return None
            
            # Extract unique coins
            coins = {}
            for symbol_info in symbols:
                base = symbol_info.get('baseAsset')
                if base and base not in coins:
                    coins[base] = {
                        'coin': base,
                        'name': base,
                        'networkList': []
                    }
            
            return list(coins.values())
                    
        except Exception as e:
            logger.error(f"💥 Binance coins info error: {str(e)}")
            return None
    
    async def get_klines(self, symbol: str, interval: str = "1m", limit: int = 100, start_time: int = None, end_time: int = None) -> Optional[List[List]]:
        """
        Get kline/candlestick data
        
        Args:
            symbol: Trading pair symbol (e.g., USDTTRY)
            interval: Kline interval (1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M)
            limit: Number of klines to return (default: 100, max: 1000)
            start_time: Start time in milliseconds (optional)
            end_time: End time in milliseconds (optional)
        
        Returns:
            List of klines or None if error
            Each kline is: [openTime, open, high, low, close, volume, closeTime, quoteVolume, trades, takerBuyBase, takerBuyQuote, ignore]
        """
        try:
            session = await self.get_session()
            
            url = f"{self.base_url}/api/v3/klines"
            params = {
                "symbol": symbol.upper(),
                "interval": interval,
                "limit": limit
            }
            
            if start_time:
                params["startTime"] = start_time
            if end_time:
                params["endTime"] = end_time
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    logger.error(f"❌ Binance klines API error: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"💥 Binance klines error: {str(e)}")
            return None

# Create global instance
binance_service = BinanceService()
