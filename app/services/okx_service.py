"""
OKX Exchange Service
Handles orderbook and market data from OKX Exchange
"""

import httpx
import logging
import asyncio
from typing import Dict, List, Optional, Any
from app.core.config import OKX_BASE_URL, OKX_COMMISSION_BPS, KDV_RATE

logger = logging.getLogger(__name__)

class OKXService:
    def __init__(self):
        self.base_url = OKX_BASE_URL
        self.api_url = f"{self.base_url}/api/v5"
        self.commission_bps = OKX_COMMISSION_BPS
        self.kdv_rate = KDV_RATE
        
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
            "net_price": net_price
        }
        
    async def get_orderbook(self, symbol: str = "USDT-TRY", limit: int = 20) -> Optional[Dict]:
        """
        Get orderbook data from OKX
        
        Args:
            symbol: Trading pair (e.g., "USDT-TRY")
            limit: Number of levels to return
            
        Returns:
            Dict containing orderbook data or None if error
        """
        try:
            # OKX uses different symbol format - convert USDT-TRY to USDT-TRY
            okx_symbol = symbol.replace("-", "-")  # OKX uses dash format
            
            # OKX orderbook endpoint
            url = f"{self.api_url}/market/books"
            params = {
                "instId": okx_symbol,
                "sz": str(limit)
            }
            
            logger.info(f"🔄 Fetching OKX orderbook for {okx_symbol}")
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("code") == "0" and data.get("data"):
                    orderbook_data = data["data"][0]  # First item contains the orderbook
                    
                    # Format data to match our standard structure
                    formatted_data = {
                        "symbol": symbol,
                        "bids": [],
                        "asks": [],
                        "timestamp": orderbook_data.get("ts", ""),
                        "exchange": "okx"
                    }
                    
                    # Parse bids (buyers) - format: [price, size, liquidated_orders, order_count]
                    if "bids" in orderbook_data:
                        for bid in orderbook_data["bids"][:limit]:
                            if len(bid) >= 2:
                                formatted_data["bids"].append({
                                    "price": float(bid[0]),
                                    "amount": float(bid[1])
                                })
                    
                    # Parse asks (sellers) - format: [price, size, liquidated_orders, order_count]
                    if "asks" in orderbook_data:
                        for ask in orderbook_data["asks"][:limit]:
                            if len(ask) >= 2:
                                formatted_data["asks"].append({
                                    "price": float(ask[0]),
                                    "amount": float(ask[1])
                                })
                    
                    logger.info(f"✅ OKX orderbook fetched: {len(formatted_data['bids'])} bids, {len(formatted_data['asks'])} asks")
                    return formatted_data
                    
                else:
                    logger.warning(f"⚠️ OKX API error: {data.get('msg', 'Unknown error')}")
                    return None
                    
        except httpx.TimeoutException:
            logger.error("⏰ OKX API timeout")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ OKX API HTTP error: {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"❌ OKX API error: {str(e)}")
            return None
    
    async def get_ticker(self, symbol: str = "USDT-TRY") -> Optional[Dict]:
        """
        Get ticker data from OKX
        
        Args:
            symbol: Trading pair (e.g., "USDT-TRY")
            
        Returns:
            Dict containing ticker data or None if error
        """
        try:
            okx_symbol = symbol.replace("-", "-")
            
            url = f"{self.api_url}/market/ticker"
            params = {"instId": okx_symbol}
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("code") == "0" and data.get("data"):
                    ticker_data = data["data"][0]
                    
                    return {
                        "symbol": symbol,
                        "price": float(ticker_data.get("last", 0)),
                        "vol24h": float(ticker_data.get("vol24h", 0)),
                        "volCcy24h": float(ticker_data.get("volCcy24h", 0)),
                        "last": float(ticker_data.get("last", 0)),
                        "high": float(ticker_data.get("high24h", 0)),
                        "low": float(ticker_data.get("low24h", 0)),
                        "exchange": "okx"
                    }
                else:
                    logger.warning(f"⚠️ OKX ticker API error: {data.get('msg', 'Unknown error')}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ OKX ticker error: {str(e)}")
            return None
    
    async def get_all_instruments(self, inst_type: str = "SPOT") -> Optional[List[Dict]]:
        """
        Get all trading instruments from OKX
        
        Args:
            inst_type: Instrument type (SPOT, FUTURES, SWAP, OPTION)
            
        Returns:
            List of instrument information or None if error
        """
        try:
            url = f"{self.api_url}/public/instruments"
            params = {"instType": inst_type}
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("code") == "0" and data.get("data"):
                    logger.info(f"📋 OKX: {len(data['data'])} instruments loaded")
                    return data["data"]
                else:
                    logger.warning(f"⚠️ OKX instruments API error: {data.get('msg', 'Unknown error')}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ OKX instruments error: {str(e)}")
            return None
    
    async def get_candles(self, symbol: str, bar: str = "1m", limit: int = 100, after: str = None) -> Optional[List[List]]:
        """
        Get candlestick/kline data
        
        Args:
            symbol: Trading pair (e.g., USDT-TRY)
            bar: Bar size (1m, 3m, 5m, 15m, 30m, 1H, 2H, 4H, 6H, 12H, 1D, 1W, 1M)
            limit: Number of candles (max 100)
            after: Pagination - timestamp to get candles after this time (in milliseconds)
            
        Returns:
            List of candles or None if error
            Each candle: [timestamp, open, high, low, close, volume, volCcy, volCcyQuote, confirm]
        """
        try:
            url = f"{self.api_url}/market/candles"
            params = {
                "instId": symbol.upper(),
                "bar": bar,
                "limit": str(min(limit, 100))  # OKX max is 100
            }
            
            if after:
                params["after"] = str(after)
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("code") == "0" and data.get("data"):
                    return data["data"]
                else:
                    logger.warning(f"⚠️ OKX candles API error: {data.get('msg', 'Unknown error')}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ OKX candles error: {str(e)}")
            return None
    
    async def get_candles_paginated(self, symbol: str, bar: str = "1m", total_limit: int = 1000) -> Optional[List[List]]:
        """
        Get candlestick/kline data with pagination to fetch more than 100 candles
        
        Args:
            symbol: Trading pair (e.g., USDT-TRY)
            bar: Bar size (1m, 3m, 5m, 15m, 30m, 1H, 2H, 4H, 6H, 12H, 1D, 1W, 1M)
            total_limit: Total number of candles to fetch (will make multiple requests)
            
        Returns:
            List of all candles or None if error
        """
        try:
            all_candles = []
            after = None
            remaining = total_limit
            
            while remaining > 0:
                # Fetch batch (max 100 per request)
                batch_size = min(remaining, 100)
                candles = await self.get_candles(symbol, bar, batch_size, after)
                
                if not candles or len(candles) == 0:
                    break
                
                all_candles.extend(candles)
                remaining -= len(candles)
                
                # If we got less than requested, no more data available
                if len(candles) < batch_size:
                    break
                
                # Use the oldest timestamp for next pagination
                # OKX returns newest first, so the last item is the oldest
                after = candles[-1][0]  # timestamp is first element
                
                # Small delay to avoid rate limiting
                await asyncio.sleep(0.1)
            
            # OKX returns newest first, reverse to get chronological order
            all_candles.reverse()
            
            logger.info(f"📊 OKX: Fetched {len(all_candles)} candles for {symbol}")
            return all_candles if all_candles else None
                    
        except Exception as e:
            logger.error(f"❌ OKX paginated candles error: {str(e)}")
            return None

# Global service instance
okx_service = OKXService()
