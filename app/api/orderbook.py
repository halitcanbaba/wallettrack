"""
Orderbook API endpoints
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Optional
from app.services.binance_service import binance_service
from app.services.whitebit_service import whitebit_service
from app.services.cointr_service import cointr_service
from app.services.okx_service import okx_service
from app.core.dependencies import logger

router = APIRouter(prefix="/api/orderbook", tags=["orderbook"])

def convert_symbol_format(symbol: str, exchange: str) -> str:
    """
    Convert symbol format for different exchanges
    
    Args:
        symbol: Input symbol (e.g., USDTTRY, BTCTRY)
        exchange: Target exchange (binance, whitebit, cointr, okx)
    
    Returns:
        Converted symbol format
    """
    # Normalize symbol first (remove separators)
    normalized = symbol.replace("-", "").replace("_", "").upper()
    
    if exchange.lower() == "binance":
        # Binance: USDTTRY, BTCTRY
        return normalized
    elif exchange.lower() == "whitebit":
        # WhiteBit: USDT_TRY, BTC_TRY
        if normalized == "USDTTRY":
            return "USDT_TRY"
        elif normalized == "BTCTRY":
            return "BTC_TRY"
        elif normalized == "ETHTRY":
            return "ETH_TRY"
        elif normalized == "ADATRY":
            return "ADA_TRY"
        elif normalized == "DOGETRY":
            return "DOGE_TRY"
        elif normalized == "AVAXUSDT":
            return "AVAX_USDT"
        elif normalized == "SOLUSDT":
            return "SOL_USDT"
        elif normalized == "BNBUSDT":
            return "BNB_USDT"
        else:
            # Fallback: try to split at common boundaries
            if normalized.endswith("TRY"):
                base = normalized.replace("TRY", "")
                if len(base) >= 3:  # Valid base currency
                    return f"{base}_TRY"
            elif normalized.endswith("USDT"):
                base = normalized.replace("USDT", "")
                if len(base) >= 2:  # Valid base currency
                    return f"{base}_USDT"
            elif "USDT" in normalized and normalized.endswith("TRY"):
                # Handle cases like USDTTRY -> USDT_TRY
                return "USDT_TRY"
            return normalized
    elif exchange.lower() == "cointr":
        # CoinTR: USDTTRY, BTCTRY (same as Binance)
        return normalized
    elif exchange.lower() == "okx":
        # OKX: USDT-TRY, BTC-TRY
        if normalized == "USDTTRY":
            return "USDT-TRY"
        elif normalized == "BTCTRY":
            return "BTC-TRY"
        elif normalized == "ETHTRY":
            return "ETH-TRY"
        elif normalized == "ADATRY":
            return "ADA-TRY"
        elif normalized == "DOGETRY":
            return "DOGE-TRY"
        elif normalized == "AVAXUSDT":
            return "AVAX-USDT"
        elif normalized == "SOLUSDT":
            return "SOL-USDT"
        elif normalized == "BNBUSDT":
            return "BNB-USDT"
        else:
            # Fallback: try to split at common boundaries
            if normalized.endswith("TRY"):
                base = normalized.replace("TRY", "")
                if len(base) >= 3:  # Valid base currency
                    return f"{base}-TRY"
            elif normalized.endswith("USDT"):
                base = normalized.replace("USDT", "")
                if len(base) >= 2:  # Valid base currency
                    return f"{base}-USDT"
            elif "USDT" in normalized and normalized.endswith("TRY"):
                # Handle cases like USDTTRY -> USDT-TRY
                return "USDT-TRY"
            return normalized
    else:
        return normalized

@router.get("/binance")
async def get_binance_orderbook(symbol: str = "USDTTRY", limit: int = 20) -> Dict:
    """
    Get Binance orderbook data
    
    Args:
        symbol: Trading pair symbol (default: USDTTRY)
        limit: Number of levels to return
    
    Returns:
        Orderbook data with bids and asks
    """
    try:
        # Convert symbol format for Binance
        binance_symbol = convert_symbol_format(symbol, "binance")
        logger.info(f"🔄 Fetching Binance orderbook for {binance_symbol} (received symbol parameter: {symbol})")
        
        orderbook = await binance_service.get_orderbook(binance_symbol, limit)
        
        if orderbook is None:
            raise HTTPException(status_code=503, detail="Failed to fetch Binance orderbook")
        
        return {
            "success": True,
            "data": orderbook,
            "exchange": "binance",
            "symbol": symbol,
            "converted_symbol": binance_symbol
        }
    
    except Exception as e:
        logger.error(f"Error fetching Binance orderbook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/binance/price")
async def get_binance_price(symbol: str = "USDTTRY") -> Dict:
    """
    Get current Binance price for a symbol
    
    Args:
        symbol: Trading pair symbol (default: USDTTRY)
    
    Returns:
        Current price data
    """
    try:
        price = await binance_service.get_ticker_price(symbol)
        
        if price is None:
            raise HTTPException(status_code=503, detail="Failed to fetch Binance price")
        
        return {
            "success": True,
            "symbol": symbol,
            "price": price,
            "exchange": "binance"
        }
    
    except Exception as e:
        logger.error(f"Error fetching Binance price: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/binance/ticker")
async def get_binance_ticker(symbol: str = "USDTTRY") -> Dict:
    """
    Get 24hr ticker statistics from Binance
    
    Args:
        symbol: Trading pair symbol (default: USDTTRY)
    
    Returns:
        24hr ticker data
    """
    try:
        ticker = await binance_service.get_24hr_ticker(symbol)
        
        if ticker is None:
            raise HTTPException(status_code=503, detail="Failed to fetch Binance ticker")
        
        return {
            "success": True,
            "data": ticker,
            "exchange": "binance"
        }
    
    except Exception as e:
        logger.error(f"Error fetching Binance ticker: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/all")
async def get_all_orderbooks(symbol: str = "USDTTRY") -> Dict:
    """
    Get orderbook data from all exchanges
    
    Args:
        symbol: Trading pair symbol (default: USDTTRY)
    
    Returns:
        Combined orderbook data from all exchanges
    """
    try:
        # Get Binance data
        binance_data = await binance_service.get_orderbook(symbol)
        
        # For now, other exchanges will be mock data
        # TODO: Implement CoinTR and WhiteBit services
        
        result = {
            "success": True,
            "symbol": symbol,
            "exchanges": {}
        }
        
        if binance_data:
            result["exchanges"]["binance"] = binance_data
        
        # Add mock data for other exchanges (placeholder)
        result["exchanges"]["cointr"] = {"status": "mock_data"}
        result["exchanges"]["whitebit"] = {"status": "mock_data"}
        
        return result
    
    except Exception as e:
        logger.error(f"Error fetching all orderbooks: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/config")
async def get_orderbook_config() -> Dict:
    """
    Get orderbook configuration (commission rates, etc.)
    
    Returns:
        Configuration data
    """
    try:
        return {
            "success": True,
            "binance_commission": binance_service.commission_bps,
            "cointr_commission": cointr_service.commission_bps,
            "whitebit_commission": whitebit_service.commission_bps,
            "okx_commission": okx_service.commission_bps,
            "kdv_rate": binance_service.kdv_rate,
            "config": {
                "exchanges": {
                    "binance": {
                        "commission_bps": binance_service.commission_bps,
                        "commission_percent": binance_service.commission_bps / 100,
                        "kdv_rate": binance_service.kdv_rate
                    },
                    "cointr": {
                        "commission_bps": cointr_service.commission_bps,
                        "commission_percent": cointr_service.commission_bps / 100,
                        "kdv_rate": cointr_service.kdv_rate
                    },
                    "whitebit": {
                        "commission_bps": whitebit_service.commission_bps,
                        "commission_percent": whitebit_service.commission_bps / 100,
                        "kdv_rate": whitebit_service.kdv_rate
                    },
                    "okx": {
                        "commission_bps": okx_service.commission_bps,
                        "commission_percent": okx_service.commission_bps / 100,
                        "kdv_rate": okx_service.kdv_rate
                    }
                },
                "default_symbol": "USDTTRY",
                "default_levels": 8
            }
        }
    
    except Exception as e:
        logger.error(f"Error getting orderbook config: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/whitebit")
async def get_whitebit_orderbook(symbol: str = "USDTTRY", limit: int = 20) -> Dict:
    """
    Get WhiteBit orderbook data
    
    Args:
        symbol: Trading pair symbol (default: USDTTRY) 
        limit: Number of levels to return
    
    Returns:
        Dict containing orderbook data or error
    """
    try:
        # Convert symbol format for WhiteBit
        whitebit_symbol = convert_symbol_format(symbol, "whitebit")
        logger.info(f"🔄 Fetching WhiteBit orderbook for {whitebit_symbol} (received symbol parameter: {symbol})")
        
        # Get orderbook from WhiteBit service
        orderbook_data = await whitebit_service.get_orderbook(whitebit_symbol, limit)
        
        if orderbook_data:
            return {
                "success": True,
                "data": orderbook_data,
                "exchange": "whitebit",
                "symbol": symbol,
                "converted_symbol": whitebit_symbol
            }
        else:
            logger.warning(f"⚠️ WhiteBit orderbook returned no data for {whitebit_symbol}")
            return {
                "success": False,
                "error": "No orderbook data available",
                "exchange": "whitebit",
                "symbol": symbol,
                "converted_symbol": whitebit_symbol
            }
    
    except Exception as e:
        error_msg = f"Error fetching WhiteBit orderbook: {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/cointr")
async def get_cointr_orderbook(symbol: str = "USDTTRY", limit: int = 20) -> Dict:
    """
    Get CoinTR orderbook data
    
    Args:
        symbol: Trading pair symbol (default: USDTTRY) 
        limit: Number of levels to return
    
    Returns:
        Dict containing orderbook data or error
    """
    try:
        # Convert symbol format for CoinTR
        cointr_symbol = convert_symbol_format(symbol, "cointr")
        logger.info(f"🔄 Fetching CoinTR orderbook for {cointr_symbol} (received symbol parameter: {symbol})")
        
        # Get orderbook from CoinTR service
        orderbook_data = await cointr_service.get_orderbook(cointr_symbol, limit)
        
        if orderbook_data:
            return {
                "success": True,
                "data": orderbook_data,
                "exchange": "cointr",
                "symbol": symbol,
                "converted_symbol": cointr_symbol
            }
        else:
            logger.warning(f"⚠️ CoinTR orderbook returned no data for {cointr_symbol}")
            return {
                "success": False,
                "error": "No orderbook data available",
                "exchange": "cointr",
                "symbol": symbol,
                "converted_symbol": cointr_symbol
            }
    
    except Exception as e:
        error_msg = f"Error fetching CoinTR orderbook: {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/okx")
async def get_okx_orderbook(symbol: str = "USDTTRY", limit: int = 20) -> Dict:
    """
    Get OKX orderbook data
    
    Args:
        symbol: Trading pair symbol (default: USDTTRY) 
        limit: Number of levels to return
    
    Returns:
        Dict containing orderbook data or error
    """
    try:
        # Convert symbol format for OKX
        okx_symbol = convert_symbol_format(symbol, "okx")
        logger.info(f"🔄 Fetching OKX orderbook for {okx_symbol} (received symbol parameter: {symbol})")
        
        # Get orderbook from OKX service
        orderbook_data = await okx_service.get_orderbook(okx_symbol, limit)
        
        if orderbook_data:
            return {
                "success": True,
                "data": orderbook_data,
                "exchange": "okx",
                "symbol": symbol,
                "converted_symbol": okx_symbol
            }
        else:
            logger.warning(f"⚠️ OKX orderbook returned no data for {okx_symbol}")
            return {
                "success": False,
                "error": "No orderbook data available",
                "exchange": "okx",
                "symbol": symbol,
                "converted_symbol": okx_symbol
            }
    
    except Exception as e:
        error_msg = f"Error fetching OKX orderbook: {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)
