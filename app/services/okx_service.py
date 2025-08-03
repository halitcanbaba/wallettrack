"""
OKX Exchange Service
Handles orderbook and market data from OKX Exchange
"""

import httpx
import logging
from typing import Dict, List, Optional, Any
from app.core.config import OKX_BASE_URL

logger = logging.getLogger(__name__)

class OKXService:
    def __init__(self):
        self.base_url = OKX_BASE_URL
        self.api_url = f"{self.base_url}/api/v5"
        
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
                        "volume": float(ticker_data.get("vol24h", 0)),
                        "change": float(ticker_data.get("chg", 0)),
                        "change_percent": float(ticker_data.get("chgUtc", 0)),
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

# Global service instance
okx_service = OKXService()
