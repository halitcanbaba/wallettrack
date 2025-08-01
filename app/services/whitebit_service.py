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
                        
                        logger.info(f"✅ WhiteBit orderbook fetched: {len(orderbook['bids'])} bids, {len(orderbook['asks'])} asks")
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
                        
                        ticker = {
                            "symbol": symbol,
                            "price": float(ticker_data["last"]),
                            "change": float(ticker_data.get("change", "0")),
                            "changePercent": float(ticker_data.get("change", "0")),  # WhiteBit change is in percentage
                            "high": float(ticker_data.get("high", ticker_data["last"])),
                            "low": float(ticker_data.get("low", ticker_data["last"])),
                            "volume": float(ticker_data.get("volume", "0")),
                            "quoteVolume": float(ticker_data.get("deal", "0"))
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

# Create global instance
whitebit_service = WhiteBitService()
