"""
Synthetics service for creating synthetic orderbooks by chaining legs across exchanges
"""
import asyncio
from typing import Dict, List, Optional, Tuple
from app.core.dependencies import logger
from app.core.config import BINANCE_COMMISSION_BPS, COINTR_COMMISSION_BPS, WHITEBIT_COMMISSION_BPS, OKX_COMMISSION_BPS
from app.services.binance_service import binance_service
from app.services.cointr_service import cointr_service
from app.services.whitebit_service import whitebit_service
from app.services.okx_service import okx_service
from app.api.orderbook import convert_symbol_format

class SyntheticsService:
    def __init__(self):
        self.exchange_services = {
            "binance": binance_service,
            "cointr": cointr_service,
            "whitebit": whitebit_service,
            "okx": okx_service
        }
        self.commission_bps = {
            "binance": BINANCE_COMMISSION_BPS,
            "cointr": COINTR_COMMISSION_BPS,
            "whitebit": WHITEBIT_COMMISSION_BPS,
            "okx": OKX_COMMISSION_BPS
        }
        self.max_legs = 6
        self.max_depth = 100

    def validate_legs(self, legs: List[Dict]) -> Tuple[bool, str]:
        """
        Validate legs configuration
        
        Args:
            legs: List of leg configurations
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if len(legs) < 2:
            return False, "At least 2 legs required"
        
        if len(legs) > self.max_legs:
            return False, f"Maximum {self.max_legs} legs allowed"
        
        for i, leg in enumerate(legs):
            if "exchange" not in leg:
                return False, f"Leg {i+1}: exchange is required"
            
            if "symbol" not in leg:
                return False, f"Leg {i+1}: symbol is required"
            
            if "side" not in leg:
                return False, f"Leg {i+1}: side is required"
            
            if leg["exchange"] not in self.exchange_services:
                return False, f"Leg {i+1}: unsupported exchange '{leg['exchange']}'"
            
            if leg["side"] not in ["buy", "sell"]:
                return False, f"Leg {i+1}: side must be 'buy' or 'sell'"
        
        return True, ""

    def extract_currencies(self, symbol: str) -> Tuple[str, str]:
        """
        Extract base and quote currencies from symbol
        
        Args:
            symbol: Trading pair symbol (e.g., ETHUSDT, USDTTRY)
            
        Returns:
            Tuple of (base, quote)
        """
        symbol = symbol.upper().replace("-", "").replace("_", "")
        
        # Common quote currencies in order of priority
        quote_currencies = ["USDT", "TRY", "USD", "EUR", "BTC", "ETH"]
        
        for quote in quote_currencies:
            if symbol.endswith(quote):
                base = symbol[:-len(quote)]
                if len(base) >= 2:  # Valid base currency
                    return base, quote
        
        # Fallback: assume last 3-4 characters are quote
        if len(symbol) >= 6:
            return symbol[:-3], symbol[-3:]
        
        return symbol, ""

    def calculate_commission_factor(self, exchange: str) -> float:
        """
        Calculate commission multiplier factor
        
        Args:
            exchange: Exchange name
            
        Returns:
            Commission factor (1 + commission_bps * 0.0001)
        """
        commission_bps = self.commission_bps.get(exchange, 10)  # Default 10 bps
        return 1.0 + (commission_bps * 0.0001)

    async def fetch_leg_orderbook(self, exchange: str, symbol: str, limit: int = 50) -> Optional[Dict]:
        """
        Fetch orderbook for a specific leg
        
        Args:
            exchange: Exchange name
            symbol: Symbol in frontend format
            limit: Number of levels to fetch
            
        Returns:
            Orderbook data or None if failed
        """
        try:
            service = self.exchange_services[exchange]
            converted_symbol = convert_symbol_format(symbol, exchange)
            
            logger.debug(f"Fetching {exchange} orderbook for {symbol} -> {converted_symbol}")
            
            orderbook = await service.get_orderbook(converted_symbol, limit)
            return orderbook
        
        except Exception as e:
            logger.error(f"Failed to fetch {exchange} orderbook for {symbol}: {str(e)}")
            return None

    def consume_levels_for_amount(self, levels: List[List[float]], target_amount: float) -> Tuple[float, List[Tuple[float, float]]]:
        """
        Consume orderbook levels to satisfy target amount
        
        Args:
            levels: List of [price, amount] levels
            target_amount: Amount to consume
            
        Returns:
            Tuple of (consumed_amount, [(price, consumed_at_level), ...])
        """
        consumed = []
        remaining = target_amount
        
        for price, available in levels:
            if remaining <= 0:
                break
            
            consume_at_level = min(remaining, available)
            consumed.append((price, consume_at_level))
            remaining -= consume_at_level
        
        total_consumed = target_amount - remaining
        return total_consumed, consumed

    def calculate_synthetic_asks(self, legs_data: List[Dict], depth: int) -> List[Dict]:
        """
        Calculate synthetic ask levels by chaining legs
        
        Args:
            legs_data: List of leg data with orderbooks and metadata
            depth: Target number of synthetic levels
            
        Returns:
            List of synthetic ask levels
        """
        if not legs_data or not all(leg["available"] for leg in legs_data):
            return []
        
        synthetic_levels = []
        first_leg = legs_data[0]
        
        # Use first leg's ask levels as starting point
        for ask_price, ask_amount in first_leg["orderbook"]["asks"][:depth * 2]:  # Get more levels to work with
            current_amount = ask_amount
            current_price = ask_price
            
            # Apply commission to first leg
            commission_factor = self.calculate_commission_factor(first_leg["exchange"])
            effective_price = current_price * commission_factor
            
            logger.debug(f"Leg 1 ({first_leg['exchange']}): price={current_price}, amount={current_amount}, comm_factor={commission_factor:.6f}")
            
            # Calculate intermediate currency amount needed
            intermediate_amount = current_amount * effective_price
            
            # Chain through remaining legs
            valid_chain = True
            chain_price = effective_price
            
            for i, leg in enumerate(legs_data[1:], 1):
                if not leg["available"]:
                    valid_chain = False
                    break
                
                # Consume levels from this leg to satisfy intermediate_amount
                consumed_amount, consumed_levels = self.consume_levels_for_amount(
                    leg["orderbook"]["asks"], intermediate_amount
                )
                
                if consumed_amount < intermediate_amount * 0.95:  # Allow 5% slippage tolerance
                    logger.debug(f"Leg {i+1}: insufficient liquidity, consumed {consumed_amount:.6f} of {intermediate_amount:.6f}")
                    valid_chain = False
                    break
                
                # Calculate weighted average price for consumed levels
                total_cost = sum(price * amount for price, amount in consumed_levels)
                avg_price = total_cost / consumed_amount if consumed_amount > 0 else 0
                
                # Apply commission
                leg_commission_factor = self.calculate_commission_factor(leg["exchange"])
                effective_leg_price = avg_price * leg_commission_factor
                
                logger.debug(f"Leg {i+1} ({leg['exchange']}): avg_price={avg_price}, comm_factor={leg_commission_factor:.6f}")
                
                # Update chain price and amount for next iteration
                chain_price *= effective_leg_price
                intermediate_amount = consumed_amount * effective_leg_price
                current_amount = min(current_amount, consumed_amount / effective_price)  # Limit by bottleneck
            
            if valid_chain and current_amount > 0:
                synthetic_levels.append({
                    "price": round(chain_price, 8),
                    "amount": round(current_amount, 8)
                })
                
                if len(synthetic_levels) >= depth:
                    break
        
        # Sort by price (ascending for asks)
        synthetic_levels.sort(key=lambda x: x["price"])
        return synthetic_levels[:depth]

    def calculate_synthetic_bids(self, legs_data: List[Dict], depth: int) -> List[Dict]:
        """
        Calculate synthetic bid levels for SELLING the synthetic base
        
        For selling synthetic base (e.g., selling ETH for TRY):
        Path: ETH → USDT → TRY
        - Step 1: Sell ETH for USDT → Use ETH/USDT BID
        - Step 2: Sell USDT for TRY → Use USDT/TRY BID
        
        Both steps use BID prices because we're selling ETH and converting USDT to TRY.
        
        Args:
            legs_data: List of leg data with orderbooks and metadata
            depth: Target number of synthetic levels
            
        Returns:
            List of synthetic bid levels
        """
        if not legs_data or not all(leg["available"] for leg in legs_data):
            return []
        
        synthetic_levels = []
        
        # For 2-leg case: Sell ETH for TRY via USDT
        if len(legs_data) == 2:
            first_leg = legs_data[0]  # ETH/USDT
            second_leg = legs_data[1]  # USDT/TRY
            
            # Use BID levels for both legs (we're selling ETH and converting USDT)
            ethusd_bids = first_leg["orderbook"]["bids"][:depth * 2]
            usdtry_bids = second_leg["orderbook"]["bids"][:depth * 2]
            
            for bid_price, bid_amount in ethusd_bids:
                # Apply commission to first leg (selling ETH for USDT)
                commission_factor_1 = self.calculate_commission_factor(first_leg["exchange"])
                eth_price_after_comm = bid_price * commission_factor_1  # USDT we get per ETH after commission
                
                # Calculate USDT we'll receive from selling this amount of ETH
                usdt_received = bid_amount * eth_price_after_comm
                
                # Consume USDT/TRY BID levels to convert USDT to TRY
                consumed_usdt, consumed_levels = self.consume_levels_for_amount(
                    usdtry_bids, usdt_received
                )
                
                if consumed_usdt < usdt_received * 0.95:  # 5% slippage tolerance
                    continue
                
                # Calculate weighted average TRY price for USDT conversion
                total_try_received = sum(price * amount for price, amount in consumed_levels)
                avg_usdtry_bid = total_try_received / consumed_usdt if consumed_usdt > 0 else 0
                
                # Apply commission to second leg (converting USDT to TRY)
                commission_factor_2 = self.calculate_commission_factor(second_leg["exchange"])
                usdtry_price_after_comm = avg_usdtry_bid * commission_factor_2
                
                # Calculate final synthetic BID price: Total TRY received per ETH
                total_try_per_eth = eth_price_after_comm * usdtry_price_after_comm
                
                # Amount is limited by the bottleneck
                synthetic_amount = min(bid_amount, consumed_usdt / eth_price_after_comm)
                
                if synthetic_amount > 0:
                    synthetic_levels.append({
                        "price": round(total_try_per_eth, 8),
                        "amount": round(synthetic_amount, 8)
                    })
                    
                    if len(synthetic_levels) >= depth:
                        break
        
        # Sort by price (descending for bids - highest price first)
        synthetic_levels.sort(key=lambda x: x["price"], reverse=True)
        return synthetic_levels[:depth]

    def derive_synthetic_pair(self, legs: List[Dict]) -> Tuple[str, str, str]:
        """
        Derive the synthetic trading pair from legs
        
        Args:
            legs: List of leg configurations
            
        Returns:
            Tuple of (synthetic_pair, base, quote)
        """
        if len(legs) < 2:
            return "", "", ""
        
        # Extract currencies from first and last legs
        first_symbol = legs[0]["symbol"]
        last_symbol = legs[-1]["symbol"]
        
        first_base, first_quote = self.extract_currencies(first_symbol)
        last_base, last_quote = self.extract_currencies(last_symbol)
        
        # Chain logic: first_base -> first_quote -> ... -> last_quote
        # Synthetic pair: first_base / last_quote
        synthetic_base = first_base
        synthetic_quote = last_quote
        synthetic_pair = f"{synthetic_base}{synthetic_quote}"
        
        logger.info(f"Derived synthetic pair: {synthetic_pair} ({synthetic_base}/{synthetic_quote})")
        return synthetic_pair, synthetic_base, synthetic_quote

    async def create_synthetic_orderbook(self, legs: List[Dict], depth: int = 20) -> Dict:
        """
        Create synthetic orderbook by chaining multiple legs
        
        Args:
            legs: List of leg configurations
            depth: Number of price levels in output
            
        Returns:
            Synthetic orderbook data
        """
        # Validate input
        is_valid, error_msg = self.validate_legs(legs)
        if not is_valid:
            return {
                "success": False,
                "error": error_msg,
                "legs": []
            }
        
        if depth > self.max_depth:
            depth = self.max_depth
        
        logger.info(f"Creating synthetic orderbook with {len(legs)} legs, depth={depth}")
        
        # Fetch orderbooks for all legs in parallel
        fetch_tasks = []
        for leg in legs:
            task = self.fetch_leg_orderbook(leg["exchange"], leg["symbol"], depth * 2)
            fetch_tasks.append(task)
        
        orderbooks = await asyncio.gather(*fetch_tasks, return_exceptions=True)
        
        # Prepare legs data
        legs_data = []
        for i, (leg, orderbook) in enumerate(zip(legs, orderbooks)):
            leg_data = {
                "exchange": leg["exchange"],
                "symbol": leg["symbol"],
                "side": leg["side"],
                "commission_bps": self.commission_bps.get(leg["exchange"], 10),
                "available": not isinstance(orderbook, Exception) and orderbook is not None,
                "orderbook": orderbook if not isinstance(orderbook, Exception) and orderbook else {"asks": [], "bids": []}
            }
            legs_data.append(leg_data)
            
            if leg_data["available"]:
                logger.debug(f"Leg {i+1} ({leg['exchange']} {leg['symbol']}): ✅ Available")
            else:
                logger.warning(f"Leg {i+1} ({leg['exchange']} {leg['symbol']}): ❌ Unavailable")
        
        # Derive synthetic pair
        synthetic_pair, base, quote = self.derive_synthetic_pair(legs)
        
        # Calculate synthetic levels
        synthetic_asks = self.calculate_synthetic_asks(legs_data, depth)
        synthetic_bids = self.calculate_synthetic_bids(legs_data, depth)
        
        # Build response
        result = {
            "success": True,
            "synthetic_pair": synthetic_pair,
            "base": base,
            "quote": quote,
            "asks": synthetic_asks,
            "bids": synthetic_bids,
            "legs": [
                {
                    "exchange": leg_data["exchange"],
                    "symbol": leg_data["symbol"],
                    "commission_bps": leg_data["commission_bps"],
                    "available": leg_data["available"]
                }
                for leg_data in legs_data
            ],
            "note": "KDV ignored; commissions applied per leg"
        }
        
        logger.info(f"Synthetic orderbook created: {len(synthetic_asks)} asks, {len(synthetic_bids)} bids")
        return result

# Create global instance
synthetics_service = SyntheticsService()
