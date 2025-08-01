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
                    
                    logger.info(f"✅ Binance orderbook fetched: {len(orderbook['bids'])} bids, {len(orderbook['asks'])} asks")
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
    
    async def get_24hr_ticker(self, symbol: str = "USDTTRY") -> Optional[Dict]:
        """
        Get 24hr ticker statistics
        
        Args:
            symbol: Trading pair symbol (default: USDTTRY)
            
        Returns:
            24hr ticker data or None if error
        """
        try:
            session = await self.get_session()
            
            url = f"{self.base_url}/api/v3/ticker/24hr"
            params = {"symbol": symbol.upper()}
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    ticker = {
                        "symbol": data["symbol"],
                        "price": float(data["lastPrice"]),
                        "change": float(data["priceChange"]),
                        "changePercent": float(data["priceChangePercent"]),
                        "high": float(data["highPrice"]),
                        "low": float(data["lowPrice"]),
                        "volume": float(data["volume"]),
                        "quoteVolume": float(data["quoteVolume"])
                    }
                    
                    logger.info(f"📈 Binance 24hr ticker for {symbol}: {ticker['price']} ({ticker['changePercent']:+.2f}%)")
                    return ticker
                else:
                    logger.error(f"❌ Binance 24hr ticker API error: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"💥 Binance 24hr ticker error: {str(e)}")
            return None

# Create global instance
binance_service = BinanceService()
