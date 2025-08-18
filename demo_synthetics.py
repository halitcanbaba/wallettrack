#!/usr/bin/env python3
"""
Synthetic Orderbook Demo Script
This script demonstrates the synthetic orderbook functionality
"""

import asyncio
import json
import aiohttp

async def test_synthetics_api():
    """Test the synthetics API endpoints"""
    
    base_url = "http://localhost:8000"
    
    async with aiohttp.ClientSession() as session:
        
        print("🔗 Testing Synthetic Orderbook API")
        print("=" * 50)
        
        # Test 1: Get configuration
        print("\n1. Testing configuration endpoint...")
        async with session.get(f"{base_url}/api/synthetics/config") as response:
            config = await response.json()
            print(f"✅ Config loaded successfully")
            print(f"   Supported exchanges: {config['supported_exchanges']}")
            print(f"   Commission rates: {config['commission_rates']}")
            print(f"   Limits: {config['limits']}")
        
        # Test 2: Get examples
        print("\n2. Testing examples endpoint...")
        async with session.get(f"{base_url}/api/synthetics/examples") as response:
            examples = await response.json()
            print(f"✅ Examples loaded successfully")
            for example in examples['examples']:
                print(f"   - {example['name']}: {example['expected_pair']}")
        
        # Test 3: Create ETH/TRY synthetic via USDT
        print("\n3. Testing ETH/TRY synthetic orderbook creation...")
        eth_try_request = {
            "legs": [
                {"exchange": "binance", "symbol": "ETHUSDT", "side": "sell"},
                {"exchange": "cointr", "symbol": "USDTTRY", "side": "sell"}
            ],
            "depth": 5
        }
        
        async with session.post(
            f"{base_url}/api/synthetics/orderbook",
            json=eth_try_request
        ) as response:
            result = await response.json()
            
            if result.get("success"):
                print(f"✅ ETH/TRY synthetic created successfully")
                print(f"   Synthetic pair: {result['synthetic_pair']}")
                print(f"   Base: {result['base']}, Quote: {result['quote']}")
                legs_status = [f"{leg['exchange']}({leg['available']})" for leg in result['legs']]
                print(f"   Legs status: {legs_status}")
                
                if result['asks']:
                    best_ask = result['asks'][0]
                    print(f"   Best ask: {best_ask['price']:,.2f} {result['quote']} for {best_ask['amount']:.4f} {result['base']}")
                
                if result['bids']:
                    best_bid = result['bids'][0]
                    print(f"   Best bid: {best_bid['price']:,.2f} {result['quote']} for {best_bid['amount']:.4f} {result['base']}")
            else:
                print(f"❌ Failed to create ETH/TRY synthetic: {result.get('error', 'Unknown error')}")
        
        # Test 4: Create BTC/TRY synthetic
        print("\n4. Testing BTC/TRY synthetic orderbook creation...")
        btc_try_request = {
            "legs": [
                {"exchange": "binance", "symbol": "BTCUSDT", "side": "sell"},
                {"exchange": "cointr", "symbol": "USDTTRY", "side": "sell"}
            ],
            "depth": 3
        }
        
        async with session.post(
            f"{base_url}/api/synthetics/orderbook",
            json=btc_try_request
        ) as response:
            result = await response.json()
            
            if result.get("success"):
                print(f"✅ BTC/TRY synthetic created successfully")
                print(f"   Synthetic pair: {result['synthetic_pair']}")
                
                if result['asks']:
                    best_ask = result['asks'][0]
                    print(f"   Best ask: {best_ask['price']:,.2f} {result['quote']} for {best_ask['amount']:.6f} {result['base']}")
            else:
                print(f"❌ Failed to create BTC/TRY synthetic: {result.get('error', 'Unknown error')}")
        
        # Test 5: Test error handling
        print("\n5. Testing error handling with invalid input...")
        invalid_request = {
            "legs": [
                {"exchange": "binance", "symbol": "ETHUSDT", "side": "sell"}
                # Only one leg - should fail
            ],
            "depth": 5
        }
        
        async with session.post(
            f"{base_url}/api/synthetics/orderbook",
            json=invalid_request
        ) as response:
            if response.status != 200:
                print(f"✅ Error handling works correctly (status: {response.status})")
            else:
                result = await response.json()
                print(f"❌ Expected error but got success: {result}")
        
        print("\n" + "=" * 50)
        print("🎉 Synthetic Orderbook API test completed!")
        print("\n💡 You can now access the web interface at:")
        print(f"   - Main dashboard: {base_url}/")
        print(f"   - Orderbook: {base_url}/orderbook")
        print(f"   - Synthetics: {base_url}/synthetics")

if __name__ == "__main__":
    asyncio.run(test_synthetics_api())
