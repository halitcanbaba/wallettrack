"""
Exchange Analytics API
Provides endpoints for analyzing exchange data including volume, prices, symbols, and withdrawal fees
"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import asyncio
import logging
from app.services.binance_service import BinanceService
from app.services.okx_service import OKXService
from app.services.cointr_service import CoinTRService
from app.services.whitebit_service import WhiteBitService

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize services
binance_service = BinanceService()
okx_service = OKXService()
cointr_service = CoinTRService()
whitebit_service = WhiteBitService()

# Global cache for crypto rates
crypto_rates_cache = {
    "usdt_try": {"rate": None, "timestamp": None},
    "btc_usdt": {"rate": None, "timestamp": None},
    "eth_usdt": {"rate": None, "timestamp": None},
    "ttl": 300  # 5 minutes
}

async def get_usdt_try_rate():
    """
    Get USDT/TRY rate from Binance with caching
    """
    global crypto_rates_cache
    
    now = datetime.now()
    cache = crypto_rates_cache["usdt_try"]
    
    # Check cache
    if (cache["rate"] is not None and 
        cache["timestamp"] is not None and
        (now - cache["timestamp"]).seconds < crypto_rates_cache["ttl"]):
        return cache["rate"]
    
    # Fetch new rate
    try:
        ticker = await EXCHANGE_SERVICES["binance"].get_24h_ticker("USDTTRY")
        rate = float(ticker.get('lastPrice', 41.7))
        cache["rate"] = rate
        cache["timestamp"] = now
        return rate
    except:
        return 41.7  # Fallback rate

async def get_crypto_usdt_rate(crypto: str):
    """
    Get BTC/USDT or ETH/USDT rate from Binance with caching
    
    Args:
        crypto: 'BTC' or 'ETH'
    
    Returns:
        Rate in USDT
    """
    global crypto_rates_cache
    
    now = datetime.now()
    cache_key = f"{crypto.lower()}_usdt"
    cache = crypto_rates_cache.get(cache_key)
    
    if not cache:
        return 0.0
    
    # Check cache
    if (cache["rate"] is not None and 
        cache["timestamp"] is not None and
        (now - cache["timestamp"]).seconds < crypto_rates_cache["ttl"]):
        return cache["rate"]
    
    # Fetch new rate
    try:
        symbol = f"{crypto}USDT"
        ticker = await EXCHANGE_SERVICES["binance"].get_24h_ticker(symbol)
        rate = float(ticker.get('lastPrice', 0))
        cache["rate"] = rate
        cache["timestamp"] = now
        return rate
    except:
        # Fallback rates
        fallback_rates = {"BTC": 95000.0, "ETH": 3500.0}
        return fallback_rates.get(crypto.upper(), 0.0)

async def calculate_usdt_volume(symbol: str, quote_volume: float, usdt_try_rate: float):
    """
    Calculate USDT volume based on symbol's quote asset
    
    Args:
        symbol: Trading pair symbol (e.g., BTCTRY, ETHUSDT, BTCBTC, ETHBTC)
        quote_volume: Quote currency volume
        usdt_try_rate: Current USDT/TRY rate
    
    Returns:
        Volume in USDT
    """
    symbol_upper = symbol.upper()
    
    # If quote is already USDT, return as-is
    if 'USDT' in symbol_upper and (symbol_upper.endswith('USDT') or '-USDT' in symbol_upper or '_USDT' in symbol_upper):
        return quote_volume
    
    # If quote is TRY, convert to USDT
    if 'TRY' in symbol_upper and (symbol_upper.endswith('TRY') or '-TRY' in symbol_upper or '_TRY' in symbol_upper):
        return quote_volume / usdt_try_rate
    
    # If quote is BTC, convert BTC volume to USDT
    if 'BTC' in symbol_upper and (symbol_upper.endswith('BTC') or '-BTC' in symbol_upper or '_BTC' in symbol_upper):
        btc_rate = await get_crypto_usdt_rate('BTC')
        if btc_rate > 0:
            return quote_volume * btc_rate
        logger.warning(f"Could not get BTC/USDT rate for {symbol}")
        return 0.0
    
    # If quote is ETH, convert ETH volume to USDT
    if 'ETH' in symbol_upper and (symbol_upper.endswith('ETH') or '-ETH' in symbol_upper or '_ETH' in symbol_upper):
        eth_rate = await get_crypto_usdt_rate('ETH')
        if eth_rate > 0:
            return quote_volume * eth_rate
        logger.warning(f"Could not get ETH/USDT rate for {symbol}")
        return 0.0
    
    # Unknown quote asset
    logger.warning(f"Cannot calculate USDT volume for unknown quote asset: {symbol}")
    return 0.0

EXCHANGE_SERVICES = {
    "binance": binance_service,
    "okx": okx_service,
    "cointr": cointr_service,
    "whitebit": whitebit_service
}


@router.get("/exchanges")
async def get_available_exchanges():
    """Get list of available exchanges"""
    return {
        "exchanges": [
            {"id": "binance", "name": "Binance", "supported": True},
            {"id": "okx", "name": "OKX", "supported": True},
            {"id": "cointr", "name": "Cointr", "supported": True},
            {"id": "whitebit", "name": "WhiteBit", "supported": True}
        ]
    }


@router.get("/symbols/{exchange}")
async def get_exchange_symbols(exchange: str, quote: Optional[str] = None):
    """
    Get all trading symbols from an exchange
    
    Args:
        exchange: Exchange name (binance, okx, cointr, whitebit)
        quote: Optional quote currency filter (e.g., USDT, BTC)
    """
    if exchange not in EXCHANGE_SERVICES:
        raise HTTPException(status_code=400, detail=f"Exchange {exchange} not supported")
    
    try:
        service = EXCHANGE_SERVICES[exchange]
        
        if exchange == "binance":
            symbols_data = await service.get_all_symbols()
            symbols = []
            for symbol_info in symbols_data:
                if quote and not symbol_info['symbol'].endswith(quote):
                    continue
                # Include ALL data from Binance
                symbols.append(symbol_info)
        
        elif exchange == "okx":
            instruments = await service.get_all_instruments()
            symbols = []
            for inst in instruments:
                symbol = inst.get('instId', '')
                if quote and not symbol.endswith(f"-{quote}"):
                    continue
                # Include ALL data from OKX
                symbols.append(inst)
        
        elif exchange == "cointr":
            pairs = await service.get_trading_pairs()
            symbols = []
            for pair in pairs:
                if quote and pair.get('counter_currency') != quote:
                    continue
                # Include ALL data from CoinTR
                symbols.append(pair)
        
        elif exchange == "whitebit":
            markets = await service.get_markets()
            symbols = []
            for symbol, info in markets.items():
                if quote and not symbol.endswith(f"_{quote}"):
                    continue
                # Include ALL data from WhiteBit (add symbol to info dict)
                full_info = {"symbol": symbol, **info}
                symbols.append(full_info)
        
        return {
            "exchange": exchange,
            "count": len(symbols),
            "symbols": symbols
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching symbols: {str(e)}")


@router.get("/volume/{exchange}")
async def get_exchange_volume_analysis(
    exchange: str,
    symbols: Optional[str] = Query(None, description="Comma-separated list of symbols"),
    hours: int = Query(24, description="Time range in hours")
):
    """
    Get volume analysis for exchange symbols
    
    Args:
        exchange: Exchange name
        symbols: Comma-separated symbol list (e.g., BTCUSDT,ETHUSDT)
        hours: Time range for analysis (default 24h)
    """
    if exchange not in EXCHANGE_SERVICES:
        raise HTTPException(status_code=400, detail=f"Exchange {exchange} not supported")
    
    try:
        service = EXCHANGE_SERVICES[exchange]
        symbol_list = symbols.split(',') if symbols else []
        
        # Get USDT/TRY rate for conversion
        usdt_try_rate = await get_usdt_try_rate()
        
        volume_data = []
        
        if exchange == "binance":
            ticker_data = await service.get_24h_ticker(symbol_list[0] if symbol_list else None)
            
            if isinstance(ticker_data, list):
                for ticker in ticker_data:
                    if not symbol_list or ticker['symbol'] in symbol_list:
                        symbol = ticker['symbol']
                        quote_volume = float(ticker.get('quoteVolume', 0))
                        volume_data.append({
                            "symbol": symbol,
                            "volume": float(ticker.get('volume', 0)),
                            "quoteVolume": quote_volume,
                            "usdtVolume": await calculate_usdt_volume(symbol, quote_volume, usdt_try_rate),
                            "priceChange": float(ticker.get('priceChange', 0)),
                            "priceChangePercent": float(ticker.get('priceChangePercent', 0)),
                            "lastPrice": float(ticker.get('lastPrice', 0)),
                            "trades": ticker.get('count', 0)
                        })
            else:
                symbol = ticker_data['symbol']
                quote_volume = float(ticker_data.get('quoteVolume', 0))
                volume_data.append({
                    "symbol": symbol,
                    "volume": float(ticker_data.get('volume', 0)),
                    "quoteVolume": quote_volume,
                    "usdtVolume": await calculate_usdt_volume(symbol, quote_volume, usdt_try_rate),
                    "priceChange": float(ticker_data.get('priceChange', 0)),
                    "priceChangePercent": float(ticker_data.get('priceChangePercent', 0)),
                    "lastPrice": float(ticker_data.get('lastPrice', 0)),
                    "trades": ticker_data.get('count', 0)
                })
        
        elif exchange == "okx":
            for symbol in symbol_list:
                try:
                    ticker = await service.get_ticker(symbol)
                    if ticker:
                        quote_volume = float(ticker.get('volCcy24h', 0))
                        volume_data.append({
                            "symbol": symbol,
                            "volume": float(ticker.get('vol24h', 0)),
                            "quoteVolume": quote_volume,
                            "usdtVolume": await calculate_usdt_volume(symbol, quote_volume, usdt_try_rate),
                            "lastPrice": float(ticker.get('last', 0)),
                            "priceChange": 0,  # OKX doesn't provide direct price change
                            "priceChangePercent": 0
                        })
                except:
                    continue
        
        elif exchange == "cointr":
            for symbol in symbol_list:
                try:
                    # Use get_24hr_ticker which works with CoinTR API
                    ticker = await service.get_24hr_ticker(symbol)
                    if ticker:
                        ticker_symbol = ticker.get('symbol', symbol)
                        quote_volume = float(ticker.get('quoteVolume', 0))
                        volume_data.append({
                            "symbol": ticker_symbol,
                            "volume": float(ticker.get('volume', 0)),
                            "quoteVolume": quote_volume,
                            "usdtVolume": await calculate_usdt_volume(ticker_symbol, quote_volume, usdt_try_rate),
                            "lastPrice": float(ticker.get('price', 0)),
                            "priceChange": float(ticker.get('change', 0)),
                            "priceChangePercent": float(ticker.get('changePercent', 0)),
                            "trades": 0
                        })
                except Exception as e:
                    logger.error(f"CoinTR error for {symbol}: {e}")
                    continue
        
        elif exchange == "whitebit":
            for symbol in symbol_list:
                try:
                    ticker = await service.get_24hr_ticker(symbol)
                    if ticker:
                        ticker_symbol = ticker.get('symbol', symbol)
                        quote_volume = float(ticker.get('quoteVolume', 0))
                        volume_data.append({
                            "symbol": ticker_symbol,
                            "volume": float(ticker.get('volume', 0)),
                            "quoteVolume": quote_volume,
                            "usdtVolume": await calculate_usdt_volume(ticker_symbol, quote_volume, usdt_try_rate),
                            "lastPrice": float(ticker.get('lastPrice', 0)),
                            "priceChange": float(ticker.get('change', 0)),
                            "priceChangePercent": float(ticker.get('changePercent', 0)),
                            "trades": 0
                        })
                except Exception as e:
                    logger.error(f"WhiteBit error for {symbol}: {e}")
                    continue
        
        # Sort by quote volume
        volume_data.sort(key=lambda x: x.get('quoteVolume', 0), reverse=True)
        
        return {
            "exchange": exchange,
            "timeRange": f"{hours}h",
            "timestamp": datetime.utcnow().isoformat(),
            "data": volume_data
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching volume data: {str(e)}")


@router.get("/prices/{exchange}")
async def get_price_comparison(
    exchange: str,
    symbols: str = Query(..., description="Comma-separated list of symbols")
):
    """
    Get current ask prices for multiple symbols from an exchange
    
    Args:
        exchange: Exchange name
        symbols: Comma-separated symbol list
    """
    if exchange not in EXCHANGE_SERVICES:
        raise HTTPException(status_code=400, detail=f"Exchange {exchange} not supported")
    
    try:
        service = EXCHANGE_SERVICES[exchange]
        symbol_list = symbols.split(',')
        
        price_data = []
        
        for symbol in symbol_list:
            try:
                if exchange == "binance":
                    orderbook = await service.get_orderbook(symbol, limit=1)
                    if orderbook and orderbook.get('asks'):
                        ask_price = float(orderbook['asks'][0][0])
                        ask_qty = float(orderbook['asks'][0][1])
                        price_data.append({
                            "symbol": symbol,
                            "askPrice": ask_price,
                            "askQty": ask_qty,
                            "timestamp": datetime.utcnow().isoformat()
                        })
                
                elif exchange == "okx":
                    orderbook = await service.get_orderbook(symbol)
                    if orderbook and orderbook.get('asks'):
                        ask_price = float(orderbook['asks'][0][0])
                        ask_qty = float(orderbook['asks'][0][1])
                        price_data.append({
                            "symbol": symbol,
                            "askPrice": ask_price,
                            "askQty": ask_qty,
                            "timestamp": datetime.utcnow().isoformat()
                        })
                
                elif exchange == "cointr":
                    base, quote = symbol.split('/')
                    orderbook = await service.get_order_book(base, quote)
                    if orderbook and orderbook.get('ask'):
                        asks = orderbook['ask']
                        if asks:
                            ask_price = float(asks[0][0])
                            ask_qty = float(asks[0][1])
                            price_data.append({
                                "symbol": symbol,
                                "askPrice": ask_price,
                                "askQty": ask_qty,
                                "timestamp": datetime.utcnow().isoformat()
                            })
            
            except Exception as e:
                print(f"Error fetching price for {symbol}: {e}")
                continue
        
        return {
            "exchange": exchange,
            "count": len(price_data),
            "prices": price_data
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching prices: {str(e)}")


@router.get("/withdrawal-fees/{exchange}")
async def get_withdrawal_fees(exchange: str):
    """
    Get withdrawal fees for all assets on an exchange
    
    Args:
        exchange: Exchange name
    """
    if exchange not in EXCHANGE_SERVICES:
        raise HTTPException(status_code=400, detail=f"Exchange {exchange} not supported")
    
    try:
        service = EXCHANGE_SERVICES[exchange]
        
        fees_data = []
        
        if exchange == "binance":
            # Binance requires authentication for withdrawal fees
            # We'll return a mock structure or use public asset info
            coins = await service.get_all_coins_info()
            if coins:
                for coin in coins:
                    for network in coin.get('networkList', []):
                        fees_data.append({
                            "asset": coin.get('coin', ''),
                            "network": network.get('network', ''),
                            "withdrawFee": network.get('withdrawFee', '0'),
                            "withdrawMin": network.get('withdrawMin', '0'),
                            "withdrawMax": network.get('withdrawMax', '0'),
                            "isDefault": network.get('isDefault', False)
                        })
        
        elif exchange == "okx":
            # OKX withdrawal fees require authentication
            # Return structure for frontend
            fees_data = [{
                "asset": "N/A",
                "network": "Requires Authentication",
                "withdrawFee": "0",
                "withdrawMin": "0",
                "withdrawMax": "0"
            }]
        
        elif exchange == "cointr":
            # Cointr withdrawal fees
            fees_data = [{
                "asset": "N/A",
                "network": "Requires Authentication",
                "withdrawFee": "0",
                "withdrawMin": "0",
                "withdrawMax": "0"
            }]
        
        return {
            "exchange": exchange,
            "count": len(fees_data),
            "fees": fees_data
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching withdrawal fees: {str(e)}")


@router.post("/export/symbols")
async def export_symbols(exchange: str, format: str = "json"):
    """
    Export symbols from an exchange
    
    Args:
        exchange: Exchange name
        format: Export format (json, csv)
    """
    symbols_response = await get_exchange_symbols(exchange)
    
    if format == "csv":
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=['symbol', 'baseAsset', 'quoteAsset', 'status'])
        writer.writeheader()
        writer.writerows(symbols_response['symbols'])
        
        return {
            "format": "csv",
            "data": output.getvalue()
        }
    
    return symbols_response


@router.post("/export/withdrawal-fees")
async def export_withdrawal_fees(exchange: str, format: str = "json"):
    """
    Export withdrawal fees from an exchange
    
    Args:
        exchange: Exchange name
        format: Export format (json, csv)
    """
    fees_response = await get_withdrawal_fees(exchange)
    
    if format == "csv":
        import csv
        import io
        
        output = io.StringIO()
        if fees_response['fees']:
            writer = csv.DictWriter(output, fieldnames=fees_response['fees'][0].keys())
            writer.writeheader()
            writer.writerows(fees_response['fees'])
            
            return {
                "format": "csv",
                "data": output.getvalue()
            }
    
    return fees_response


@router.get("/historical/{exchange}")
async def get_historical_prices(
    exchange: str,
    symbol: str = Query(..., description="Trading pair symbol"),
    interval: str = Query("1m", description="Time interval (1m, 5m, 15m, 1h, etc.)"),
    limit: int = Query(100, description="Number of data points (max 1000)"),
    start_time: Optional[int] = Query(None, description="Start time in milliseconds"),
    end_time: Optional[int] = Query(None, description="End time in milliseconds")
):
    """
    Get historical price data (klines/candles) from exchange
    
    Args:
        exchange: Exchange name (binance, okx, cointr, whitebit)
        symbol: Trading pair symbol
        interval: Time interval
        limit: Number of candles to return
        start_time: Optional start time in milliseconds
        end_time: Optional end time in milliseconds
        
    Returns:
        Historical price data with timestamps and OHLCV
    """
    try:
        if exchange.lower() not in EXCHANGE_SERVICES:
            raise HTTPException(status_code=400, detail=f"Exchange {exchange} not supported")
        
        service = EXCHANGE_SERVICES[exchange.lower()]
        
        # Format symbol for exchange
        import re
        formatted_symbol = symbol.upper()
        if exchange.lower() == "okx":
            # OKX uses BTC-TRY format
            formatted_symbol = re.sub(r'([A-Z]+)(TRY|USDT|BTC|ETH)$', r'\1-\2', formatted_symbol)
            interval_map = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m", "1h": "1H", "4h": "4H", "1d": "1D"}
            interval = interval_map.get(interval, "1m")
        elif exchange.lower() == "whitebit":
            # WhiteBit uses BTC_TRY format
            formatted_symbol = re.sub(r'([A-Z]+)(TRY|USDT|BTC|ETH)$', r'\1_\2', formatted_symbol)
        
        # Get klines/candles based on exchange
        if exchange.lower() == "binance":
            if not hasattr(service, 'get_klines'):
                raise HTTPException(status_code=501, detail=f"Historical data not available for {exchange}")
            # Binance supports up to 1000 in a single request
            data = await service.get_klines(formatted_symbol, interval, min(limit, 1000), start_time, end_time)
        elif exchange.lower() == "okx":
            if not hasattr(service, 'get_candles_paginated'):
                raise HTTPException(status_code=501, detail=f"Historical data not available for {exchange}")
            # OKX has max 100 per request, use paginated method for larger limits
            if limit > 100:
                data = await service.get_candles_paginated(formatted_symbol, interval, limit)
            else:
                data = await service.get_candles(formatted_symbol, interval, limit)
        elif exchange.lower() == "cointr":
            if not hasattr(service, 'get_klines_paginated'):
                raise HTTPException(status_code=501, detail=f"Historical data not available for {exchange}")
            # CoinTR has max 200 per request, use paginated method for larger limits
            if limit > 200:
                data = await service.get_klines_paginated(formatted_symbol, interval, limit, start_time, end_time)
            else:
                data = await service.get_klines(formatted_symbol, interval, limit, start_time, end_time)
        elif exchange.lower() == "whitebit":
            if not hasattr(service, 'get_klines'):
                raise HTTPException(status_code=501, detail=f"Historical data not available for {exchange}")
            # WhiteBit supports up to 1440 in a single request
            data = await service.get_klines(formatted_symbol, interval, min(limit, 1440))
        else:
            raise HTTPException(status_code=501, detail=f"Historical data not available for {exchange}")
        
        if not data:
            raise HTTPException(status_code=404, detail="No historical data found")
        
        # Format response
        historical_data = []
        for candle in data:
            if exchange.lower() == "binance":
                # Binance format: [openTime, open, high, low, close, volume, closeTime, quoteVolume, ...]
                historical_data.append({
                    "timestamp": int(candle[0]),
                    "open": float(candle[1]),
                    "high": float(candle[2]),
                    "low": float(candle[3]),
                    "close": float(candle[4]),
                    "volume": float(candle[5])
                })
            elif exchange.lower() == "okx":
                # OKX format: [timestamp, open, high, low, close, volume, volCcy, volCcyQuote, confirm]
                historical_data.append({
                    "timestamp": int(candle[0]),
                    "open": float(candle[1]),
                    "high": float(candle[2]),
                    "low": float(candle[3]),
                    "close": float(candle[4]),
                    "volume": float(candle[5])
                })
            elif exchange.lower() in ["cointr", "whitebit"]:
                # CoinTR and WhiteBit format (already formatted): [timestamp, open, high, low, close, volume]
                historical_data.append({
                    "timestamp": int(candle[0]),
                    "open": float(candle[1]),
                    "high": float(candle[2]),
                    "low": float(candle[3]),
                    "close": float(candle[4]),
                    "volume": float(candle[5])
                })
        
        return {
            "success": True,
            "exchange": exchange,
            "symbol": symbol,
            "interval": interval,
            "count": len(historical_data),
            "data": historical_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting historical data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
