"""
Synthetics API endpoints for creating synthetic orderbooks
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List, Literal
from app.services.synthetics_service import synthetics_service
from app.core.dependencies import logger

router = APIRouter(prefix="/api/synthetics", tags=["synthetics"])

class LegConfig(BaseModel):
    exchange: Literal["binance", "cointr", "whitebit", "okx"] = Field(..., description="Exchange name")
    symbol: str = Field(..., description="Trading pair symbol (e.g., ETHUSDT, USDTTRY)")
    side: Literal["buy", "sell"] = Field(..., description="Side of the leg")

class SyntheticOrderbookRequest(BaseModel):
    legs: List[LegConfig] = Field(..., description="List of legs to chain", min_items=2, max_items=6)
    depth: int = Field(20, description="Number of price levels in output", ge=1, le=100)

@router.post("/orderbook")
async def create_synthetic_orderbook(request: SyntheticOrderbookRequest) -> Dict:
    """
    Create synthetic orderbook by chaining multiple legs across exchanges
    
    Args:
        request: Synthetic orderbook request with legs and depth
    
    Returns:
        Synthetic orderbook data with asks, bids, and leg information
    
    Example:
        {
            "legs": [
                {"exchange": "binance", "symbol": "ETHUSDT", "side": "sell"},
                {"exchange": "cointr", "symbol": "USDTTRY", "side": "sell"}
            ],
            "depth": 20
        }
    """
    try:
        logger.info(f"🔗 Creating synthetic orderbook with {len(request.legs)} legs")
        
        # Convert Pydantic models to dicts
        legs_data = [leg.dict() for leg in request.legs]
        
        # Create synthetic orderbook
        result = await synthetics_service.create_synthetic_orderbook(
            legs=legs_data,
            depth=request.depth
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to create synthetic orderbook"))
        
        logger.info(f"✅ Synthetic orderbook created: {result['synthetic_pair']}")
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error creating synthetic orderbook: {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/config")
async def get_synthetics_config() -> Dict:
    """
    Get synthetics configuration (supported exchanges, commission rates, etc.)
    
    Returns:
        Configuration data for synthetics
    """
    try:
        return {
            "success": True,
            "supported_exchanges": list(synthetics_service.exchange_services.keys()),
            "commission_rates": synthetics_service.commission_bps,
            "limits": {
                "max_legs": synthetics_service.max_legs,
                "max_depth": synthetics_service.max_depth,
                "min_legs": 2
            },
            "supported_sides": ["buy", "sell"],
            "note": "KDV is ignored in synthetic calculations; only exchange commissions applied"
        }
    
    except Exception as e:
        error_msg = f"Error getting synthetics config: {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/examples")
async def get_synthetic_examples() -> Dict:
    """
    Get example synthetic orderbook configurations
    
    Returns:
        List of example configurations
    """
    try:
        examples = [
            {
                "name": "ETH/TRY via USDT",
                "description": "ETH to TRY through USDT (Binance + CoinTR)",
                "legs": [
                    {"exchange": "binance", "symbol": "ETHUSDT", "side": "sell"},
                    {"exchange": "cointr", "symbol": "USDTTRY", "side": "sell"}
                ],
                "expected_pair": "ETHTRY"
            },
            {
                "name": "BTC/TRY via USDT",
                "description": "BTC to TRY through USDT (Binance + CoinTR)",
                "legs": [
                    {"exchange": "binance", "symbol": "BTCUSDT", "side": "sell"},
                    {"exchange": "cointr", "symbol": "USDTTRY", "side": "sell"}
                ],
                "expected_pair": "BTCTRY"
            },
            {
                "name": "Multi-hop arbitrage",
                "description": "Complex 3-leg chain for arbitrage opportunities",
                "legs": [
                    {"exchange": "binance", "symbol": "ETHUSDT", "side": "sell"},
                    {"exchange": "okx", "symbol": "USDTTRY", "side": "sell"},
                    {"exchange": "whitebit", "symbol": "TRYETH", "side": "buy"}
                ],
                "expected_pair": "ETHETH"
            }
        ]
        
        return {
            "success": True,
            "examples": examples
        }
    
    except Exception as e:
        error_msg = f"Error getting synthetic examples: {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)
