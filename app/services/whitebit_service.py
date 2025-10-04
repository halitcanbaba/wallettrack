"""
WhiteBit API service for orderbook data
"""
import asyncio
import aiohttp
import json
import ssl
from typing import Dict, List, Optional
from app.core.config import WHITEBIT_BASE_URL, WHITEBIT_COMMISSION_BPS, KDV_RATE
from app.core.dependencies import logger

class WhiteBitService:
    def __init__(self):
        self.base_url = WHITEBIT_BASE_URL
        self.commission_bps = WHITEBIT_COMMISSION_BPS
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
    
    async def get_orderbook(self, symbol: str = "USDT_TRY", limit: int = 20) -> Optional[Dict]:
        """
        Get orderbook data from WhiteBit API
        
        Args:
            symbol: Trading pair symbol (default: USDT_TRY)
            limit: Number of levels to return (max 100)
        
        Returns:
            Dict with bids and asks or None if error
        """
        try:
            session = await self.get_session()
            
            # WhiteBit orderbook endpoint - v4 API
            url = f"{self.base_url}/api/v4/public/orderbook/{symbol}"
            params = {
                "limit": min(limit, 100)  # WhiteBit max limit is 100
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # WhiteBit v4 returns {asks: [[price, amount]], bids: [[price, amount]]}
                    if "asks" in data and "bids" in data:
                        # Convert to our format and take first 8 levels
                        orderbook = {
                            "bids": [[float(item[0]), float(item[1])] for item in data["bids"][:8]],
                            "asks": [[float(item[0]), float(item[1])] for item in data["asks"][:8]],
                            "symbol": symbol,
                            "exchange": "whitebit"
                        }
                        
                        return orderbook
                    else:
                        logger.error(f"❌ WhiteBit API unexpected response format: {data}")
                        return None
                else:
                    logger.error(f"❌ WhiteBit API error: {response.status}")
                    return None
                    
        except asyncio.TimeoutError:
            logger.error("⏰ WhiteBit API timeout")
            return None
        except Exception as e:
            logger.error(f"💥 WhiteBit API error: {str(e)}")
            return None
    
    async def get_ticker_price(self, symbol: str = "USDT_TRY") -> Optional[float]:
        """
        Get current price for a symbol from WhiteBit
        
        Args:
            symbol: Trading pair symbol (default: USDT_TRY)
            
        Returns:
            Current price or None if error
        """
        try:
            session = await self.get_session()
            
            # WhiteBit v4 ticker endpoint
            url = f"{self.base_url}/api/v4/public/ticker"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if symbol in data:
                        price = float(data[symbol]["last"])
                        logger.info(f"📊 WhiteBit {symbol} price: {price}")
                        return price
                    else:
                        logger.error(f"❌ WhiteBit symbol {symbol} not found")
                        return None
                else:
                    logger.error(f"❌ WhiteBit ticker API error: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"💥 WhiteBit ticker error: {str(e)}")
            return None
    
    async def get_24hr_ticker(self, symbol: str = "USDT_TRY") -> Optional[Dict]:
        """
        Get 24hr ticker statistics from WhiteBit
        
        Args:
            symbol: Trading pair symbol (default: USDT_TRY)
            
        Returns:
            24hr ticker data or None if error
        """
        try:
            session = await self.get_session()
            
            # WhiteBit v4 ticker endpoint
            url = f"{self.base_url}/api/v4/public/ticker"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if symbol in data:
                        ticker_data = data[symbol]
                        
                        # WhiteBit v4 API response format:
                        # {base_id, quote_id, last_price, quote_volume, base_volume, isFrozen, change}
                        last_price = float(ticker_data.get("last_price", 0))
                        
                        ticker = {
                            "symbol": symbol,
                            "price": last_price,
                            "lastPrice": last_price,
                            "change": float(ticker_data.get("change", "0")),
                            "changePercent": float(ticker_data.get("change", "0")),  # WhiteBit change is already in percentage
                            "high": last_price,  # WhiteBit doesn't provide high/low
                            "low": last_price,
                            "volume": float(ticker_data.get("base_volume", "0")),
                            "quoteVolume": float(ticker_data.get("quote_volume", "0"))
                        }
                        
                        logger.info(f"📈 WhiteBit 24hr ticker for {symbol}: {ticker['price']} ({ticker['changePercent']:+.2f}%)")
                        return ticker
                    else:
                        logger.error(f"❌ WhiteBit symbol {symbol} not found in ticker")
                        return None
                else:
                    logger.error(f"❌ WhiteBit 24hr ticker API error: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"💥 WhiteBit 24hr ticker error: {str(e)}")
            return None
    
    async def get_markets(self) -> Optional[Dict]:
        """
        Get all markets from WhiteBit
        
        Returns:
            Dict of market information or None if error
        """
        try:
            session = await self.get_session()
            
            # WhiteBit markets endpoint
            url = f"{self.base_url}/api/v4/public/markets"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"📋 WhiteBit: {len(data)} markets loaded")
                    return data
                else:
                    logger.error(f"❌ WhiteBit markets API error: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"💥 WhiteBit markets error: {str(e)}")
            return None
    
    async def get_klines(self, symbol: str, interval: str = "1m", limit: int = 1440) -> Optional[List[List]]:
        """
        Get kline/candlestick data from WhiteBit
        
        Args:
            symbol: Trading pair symbol (e.g., USDT_TRY)
            interval: Time interval (1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 1w)
            limit: Number of klines to return (max 1440)
            
        Returns:
            List of klines or None if error
            Each kline: [timestamp, open, high, low, close, volume]
        """
        try:
            session = await self.get_session()
            
            # WhiteBit interval mapping - they might use different format
            # Try converting: 1m -> 1, 5m -> 5, 1h -> 60, 1d -> 1440
            interval_to_minutes = {
                "1m": "1", "3m": "3", "5m": "5", "15m": "15", "30m": "30",
                "1h": "60", "2h": "120", "4h": "240", "6h": "360", "8h": "480", "12h": "720",
                "1d": "1440", "1w": "10080"
            }
            whitebit_interval = interval_to_minutes.get(interval, "1")
            
            # WhiteBit klines endpoint - v1 API
            url = f"{self.base_url}/api/v1/public/kline"
            params = {
                "market": symbol,
                "interval": whitebit_interval,
                "limit": min(limit, 1440)  # WhiteBit max is 1440
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # WhiteBit returns: [[timestamp, open, close, high, low, volume, deal]]
                    if isinstance(data, list) and len(data) > 0:
                        # Convert to standard format: [timestamp, open, high, low, close, volume]
                        formatted_klines = []
                        for k in data:
                            formatted_klines.append([
                                int(k[0]) * 1000,  # Convert to milliseconds
                                float(k[1]),  # open
                                float(k[3]),  # high
                                float(k[4]),  # low
                                float(k[2]),  # close
                                float(k[5])   # volume
                            ])
                        logger.info(f"📊 WhiteBit: Fetched {len(formatted_klines)} klines for {symbol}")
                        return formatted_klines
                    else:
                        logger.warning(f"⚠️ WhiteBit klines empty response for {symbol}")
                        return None
                else:
                    error_text = await response.text()
                    logger.error(f"❌ WhiteBit klines HTTP error: {response.status} - {error_text}")
                    return None
                    
        except asyncio.TimeoutError:
            logger.error("⏰ WhiteBit klines API timeout")
            return None
        except Exception as e:
            logger.error(f"💥 WhiteBit klines error: {str(e)}")
            return None

# Create global instance
whitebit_service = WhiteBitService()
