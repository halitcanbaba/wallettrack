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
            
            logger.info(f"🔍 Getting CoinTR orderbook for {symbol}")
            
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
                            
                            logger.info(f"✅ CoinTR orderbook fetched: {len(orderbook['bids'])} bids, {len(orderbook['asks'])} asks")
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
    
    async def get_24hr_ticker(self, symbol: str = "USDTTRY") -> Optional[Dict]:
        """
        Get 24hr ticker statistics from CoinTR
        
        Args:
            symbol: Trading pair symbol (default: USDTTRY)
            
        Returns:
            24hr ticker data or None if error
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
                        
                        ticker = {
                            "symbol": symbol,
                            "price": float(ticker_data.get("lastPrice", "0")),
                            "change": float(ticker_data.get("priceChange", "0")),
                            "changePercent": float(ticker_data.get("priceChangePercent", "0")),
                            "high": float(ticker_data.get("highPrice", ticker_data.get("lastPrice", "0"))),
                            "low": float(ticker_data.get("lowPrice", ticker_data.get("lastPrice", "0"))),
                            "volume": float(ticker_data.get("volume", "0")),
                            "quoteVolume": float(ticker_data.get("quoteVolume", "0"))
                        }
                        
                        logger.info(f"📈 CoinTR 24hr ticker for {symbol}: {ticker['price']} ({ticker['changePercent']:+.2f}%)")
                        return ticker
                    else:
                        logger.error(f"❌ CoinTR 24hr ticker API error: {data}")
                        return None
                else:
                    logger.error(f"❌ CoinTR 24hr ticker API error: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"💥 CoinTR 24hr ticker error: {str(e)}")
            return None

# Create global instance
cointr_service = CoinTRService()
