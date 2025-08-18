"""
Unit tests for the synthetics service
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.synthetics_service import SyntheticsService

@pytest.fixture
def synthetics_service():
    """Create a SyntheticsService instance for testing"""
    return SyntheticsService()

@pytest.fixture
def mock_orderbook_data():
    """Mock orderbook data for testing"""
    return {
        "asks": [
            [2000.0, 1.0],
            [2001.0, 2.0],
            [2002.0, 3.0],
            [2003.0, 4.0],
            [2004.0, 5.0]
        ],
        "bids": [
            [1999.0, 1.0],
            [1998.0, 2.0],
            [1997.0, 3.0],
            [1996.0, 4.0],
            [1995.0, 5.0]
        ],
        "symbol": "ETHUSDT",
        "exchange": "binance"
    }

@pytest.fixture
def mock_usdt_try_orderbook():
    """Mock USDT/TRY orderbook data"""
    return {
        "asks": [
            [34.50, 1000.0],
            [34.51, 2000.0],
            [34.52, 3000.0],
            [34.53, 4000.0],
            [34.54, 5000.0]
        ],
        "bids": [
            [34.49, 1000.0],
            [34.48, 2000.0],
            [34.47, 3000.0],
            [34.46, 4000.0],
            [34.45, 5000.0]
        ],
        "symbol": "USDTTRY",
        "exchange": "cointr"
    }

class TestSyntheticsService:
    
    def test_validate_legs_valid(self, synthetics_service):
        """Test validation with valid legs"""
        legs = [
            {"exchange": "binance", "symbol": "ETHUSDT", "side": "sell"},
            {"exchange": "cointr", "symbol": "USDTTRY", "side": "sell"}
        ]
        
        is_valid, error = synthetics_service.validate_legs(legs)
        assert is_valid is True
        assert error == ""
    
    def test_validate_legs_too_few(self, synthetics_service):
        """Test validation with too few legs"""
        legs = [
            {"exchange": "binance", "symbol": "ETHUSDT", "side": "sell"}
        ]
        
        is_valid, error = synthetics_service.validate_legs(legs)
        assert is_valid is False
        assert "At least 2 legs required" in error
    
    def test_validate_legs_too_many(self, synthetics_service):
        """Test validation with too many legs"""
        legs = [
            {"exchange": "binance", "symbol": "ETHUSDT", "side": "sell"},
            {"exchange": "cointr", "symbol": "USDTTRY", "side": "sell"},
            {"exchange": "whitebit", "symbol": "TRYBTC", "side": "sell"},
            {"exchange": "okx", "symbol": "BTCEUR", "side": "sell"},
            {"exchange": "binance", "symbol": "EURUSDT", "side": "sell"},
            {"exchange": "cointr", "symbol": "USDTTRY", "side": "sell"},
            {"exchange": "whitebit", "symbol": "TRYETH", "side": "sell"}  # 7th leg
        ]
        
        is_valid, error = synthetics_service.validate_legs(legs)
        assert is_valid is False
        assert f"Maximum {synthetics_service.max_legs} legs allowed" in error
    
    def test_validate_legs_missing_fields(self, synthetics_service):
        """Test validation with missing required fields"""
        legs = [
            {"exchange": "binance", "symbol": "ETHUSDT"},  # Missing side
            {"symbol": "USDTTRY", "side": "sell"}         # Missing exchange
        ]
        
        is_valid, error = synthetics_service.validate_legs(legs)
        assert is_valid is False
        assert "side is required" in error
        assert "exchange is required" in error
    
    def test_validate_legs_invalid_exchange(self, synthetics_service):
        """Test validation with invalid exchange"""
        legs = [
            {"exchange": "binance", "symbol": "ETHUSDT", "side": "sell"},
            {"exchange": "invalid_exchange", "symbol": "USDTTRY", "side": "sell"}
        ]
        
        is_valid, error = synthetics_service.validate_legs(legs)
        assert is_valid is False
        assert "unsupported exchange" in error
    
    def test_extract_currencies_standard(self, synthetics_service):
        """Test currency extraction from standard symbols"""
        base, quote = synthetics_service.extract_currencies("ETHUSDT")
        assert base == "ETH"
        assert quote == "USDT"
        
        base, quote = synthetics_service.extract_currencies("USDTTRY")
        assert base == "USDT"
        assert quote == "TRY"
        
        base, quote = synthetics_service.extract_currencies("BTCUSDT")
        assert base == "BTC"
        assert quote == "USDT"
    
    def test_extract_currencies_with_separators(self, synthetics_service):
        """Test currency extraction with separators"""
        base, quote = synthetics_service.extract_currencies("ETH-USDT")
        assert base == "ETH"
        assert quote == "USDT"
        
        base, quote = synthetics_service.extract_currencies("USDT_TRY")
        assert base == "USDT"
        assert quote == "TRY"
    
    def test_calculate_commission_factor(self, synthetics_service):
        """Test commission factor calculation"""
        # Binance: 10 bps = 0.1%
        factor = synthetics_service.calculate_commission_factor("binance")
        assert factor == 1.001  # 1 + 10 * 0.0001
        
        # CoinTR: 15 bps = 0.15%
        factor = synthetics_service.calculate_commission_factor("cointr")
        assert factor == 1.0015  # 1 + 15 * 0.0001
        
        # Unknown exchange should use default 10 bps
        factor = synthetics_service.calculate_commission_factor("unknown")
        assert factor == 1.001
    
    def test_consume_levels_for_amount(self, synthetics_service):
        """Test consuming orderbook levels for target amount"""
        levels = [
            [100.0, 1.0],
            [101.0, 2.0],
            [102.0, 3.0]
        ]
        
        # Consume exactly available amount
        consumed, details = synthetics_service.consume_levels_for_amount(levels, 2.0)
        assert consumed == 2.0
        assert len(details) == 2
        assert details[0] == (100.0, 1.0)
        assert details[1] == (101.0, 1.0)
        
        # Consume more than available
        consumed, details = synthetics_service.consume_levels_for_amount(levels, 10.0)
        assert consumed == 6.0  # Total available
        assert len(details) == 3
    
    def test_derive_synthetic_pair(self, synthetics_service):
        """Test synthetic pair derivation"""
        legs = [
            {"symbol": "ETHUSDT"},
            {"symbol": "USDTTRY"}
        ]
        
        pair, base, quote = synthetics_service.derive_synthetic_pair(legs)
        assert pair == "ETHTRY"
        assert base == "ETH"
        assert quote == "TRY"
        
        # Test with different symbols
        legs = [
            {"symbol": "BTCUSDT"},
            {"symbol": "USDTEUR"}
        ]
        
        pair, base, quote = synthetics_service.derive_synthetic_pair(legs)
        assert pair == "BTCEUR"
        assert base == "BTC"
        assert quote == "EUR"
    
    @pytest.mark.asyncio
    async def test_fetch_leg_orderbook_success(self, synthetics_service, mock_orderbook_data):
        """Test successful leg orderbook fetching"""
        # Mock the binance service
        with patch.object(synthetics_service.exchange_services["binance"], 'get_orderbook', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_orderbook_data
            
            result = await synthetics_service.fetch_leg_orderbook("binance", "ETHUSDT", 20)
            
            assert result == mock_orderbook_data
            mock_get.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_fetch_leg_orderbook_failure(self, synthetics_service):
        """Test failed leg orderbook fetching"""
        # Mock the binance service to raise an exception
        with patch.object(synthetics_service.exchange_services["binance"], 'get_orderbook', new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = Exception("API Error")
            
            result = await synthetics_service.fetch_leg_orderbook("binance", "ETHUSDT", 20)
            
            assert result is None
    
    @pytest.mark.asyncio 
    async def test_create_synthetic_orderbook_success(self, synthetics_service, mock_orderbook_data, mock_usdt_try_orderbook):
        """Test successful synthetic orderbook creation"""
        legs = [
            {"exchange": "binance", "symbol": "ETHUSDT", "side": "sell"},
            {"exchange": "cointr", "symbol": "USDTTRY", "side": "sell"}
        ]
        
        # Mock the fetch_leg_orderbook method
        async def mock_fetch(exchange, symbol, limit):
            if exchange == "binance" and symbol == "ETHUSDT":
                return mock_orderbook_data
            elif exchange == "cointr" and symbol == "USDTTRY":
                return mock_usdt_try_orderbook
            return None
        
        with patch.object(synthetics_service, 'fetch_leg_orderbook', side_effect=mock_fetch):
            result = await synthetics_service.create_synthetic_orderbook(legs, 10)
            
            assert result["success"] is True
            assert result["synthetic_pair"] == "ETHTRY"
            assert result["base"] == "ETH"
            assert result["quote"] == "TRY"
            assert len(result["legs"]) == 2
            assert all(leg["available"] for leg in result["legs"])
            
            # Check that we have some synthetic levels
            assert len(result["asks"]) > 0
            assert len(result["bids"]) > 0
            
            # Verify ask prices are reasonable (ETH price * USDT/TRY rate * commissions)
            # Should be around 2000 * 34.5 * 1.001 * 1.0015 ≈ 69,100
            first_ask_price = result["asks"][0]["price"]
            assert 60000 < first_ask_price < 80000  # Reasonable range
    
    @pytest.mark.asyncio
    async def test_create_synthetic_orderbook_invalid_legs(self, synthetics_service):
        """Test synthetic orderbook creation with invalid legs"""
        legs = [
            {"exchange": "binance", "symbol": "ETHUSDT", "side": "sell"}
            # Only one leg - should fail validation
        ]
        
        result = await synthetics_service.create_synthetic_orderbook(legs, 10)
        
        assert result["success"] is False
        assert "At least 2 legs required" in result["error"]
    
    @pytest.mark.asyncio
    async def test_create_synthetic_orderbook_unavailable_leg(self, synthetics_service, mock_orderbook_data):
        """Test synthetic orderbook creation with unavailable leg"""
        legs = [
            {"exchange": "binance", "symbol": "ETHUSDT", "side": "sell"},
            {"exchange": "cointr", "symbol": "USDTTRY", "side": "sell"}
        ]
        
        # Mock one leg as available, one as unavailable
        async def mock_fetch(exchange, symbol, limit):
            if exchange == "binance":
                return mock_orderbook_data
            else:
                return None  # Unavailable
        
        with patch.object(synthetics_service, 'fetch_leg_orderbook', side_effect=mock_fetch):
            result = await synthetics_service.create_synthetic_orderbook(legs, 10)
            
            assert result["success"] is True  # Should still succeed
            assert result["legs"][0]["available"] is True
            assert result["legs"][1]["available"] is False
            
            # Should have no synthetic levels due to unavailable leg
            assert len(result["asks"]) == 0
            assert len(result["bids"]) == 0
    
    def test_calculate_synthetic_asks_empty_legs(self, synthetics_service):
        """Test synthetic asks calculation with empty legs"""
        result = synthetics_service.calculate_synthetic_asks([], 10)
        assert result == []
    
    def test_calculate_synthetic_asks_unavailable_legs(self, synthetics_service):
        """Test synthetic asks calculation with unavailable legs"""
        legs_data = [
            {
                "exchange": "binance",
                "orderbook": {"asks": [], "bids": []},
                "available": False
            }
        ]
        
        result = synthetics_service.calculate_synthetic_asks(legs_data, 10)
        assert result == []

if __name__ == "__main__":
    pytest.main([__file__])
