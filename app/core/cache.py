"""
Simple cache implementation for WalletTrack
Caches transaction data to improve response times
"""
import time
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import hashlib
import json
import logging

logger = logging.getLogger(__name__)

class SimpleCache:
    """Simple in-memory cache with TTL support"""
    
    def __init__(self, default_ttl: int = 30):
        self.cache: Dict[str, Tuple[Any, float]] = {}
        self.default_ttl = default_ttl  # seconds
    
    def _generate_key(self, prefix: str, **kwargs) -> str:
        """Generate cache key from parameters"""
        # Create a consistent key from parameters
        params = json.dumps(kwargs, sort_keys=True)
        key_hash = hashlib.md5(params.encode()).hexdigest()[:8]
        return f"{prefix}:{key_hash}"
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired"""
        if key in self.cache:
            value, expires_at = self.cache[key]
            if time.time() < expires_at:
                logger.debug(f"Cache HIT: {key}")
                return value
            else:
                # Expired, remove from cache
                del self.cache[key]
                logger.debug(f"Cache EXPIRED: {key}")
        
        logger.debug(f"Cache MISS: {key}")
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with TTL"""
        if ttl is None:
            ttl = self.default_ttl
        
        expires_at = time.time() + ttl
        self.cache[key] = (value, expires_at)
        logger.debug(f"Cache SET: {key} (TTL: {ttl}s)")
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if key in self.cache:
            del self.cache[key]
            logger.debug(f"Cache DELETE: {key}")
            return True
        return False
    
    def clear(self) -> None:
        """Clear all cache entries"""
        self.cache.clear()
        logger.info("Cache cleared")
    
    def cleanup_expired(self) -> None:
        """Remove expired entries from cache"""
        current_time = time.time()
        expired_keys = [
            key for key, (_, expires_at) in self.cache.items()
            if current_time >= expires_at
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        current_time = time.time()
        active_entries = sum(1 for _, expires_at in self.cache.values() if current_time < expires_at)
        expired_entries = len(self.cache) - active_entries
        
        return {
            "total_entries": len(self.cache),
            "active_entries": active_entries,
            "expired_entries": expired_entries,
            "memory_usage_kb": len(str(self.cache)) / 1024
        }

# Global cache instances
transaction_cache = SimpleCache(default_ttl=30)  # 30 seconds for transactions
wallet_cache = SimpleCache(default_ttl=60)       # 60 seconds for wallets
balance_cache = SimpleCache(default_ttl=45)      # 45 seconds for balances

def get_transaction_cache_key(limit: int, hours: int) -> str:
    """Generate cache key for transactions"""
    return transaction_cache._generate_key("transactions", limit=limit, hours=hours)

def get_wallet_cache_key() -> str:
    """Generate cache key for wallets"""
    return wallet_cache._generate_key("wallets")

def get_balance_cache_key(wallet_address: str) -> str:
    """Generate cache key for wallet balance"""
    return balance_cache._generate_key("balance", address=wallet_address)

def invalidate_all_caches():
    """Clear all caches - use when major data changes occur"""
    transaction_cache.clear()
    wallet_cache.clear()
    balance_cache.clear()
    logger.info("🗑️ All caches invalidated")

def invalidate_wallet_related_caches():
    """Clear wallet and transaction caches when balance updates"""
    wallet_cache.clear()
    transaction_cache.clear()
    logger.info("🗑️ Wallet and transaction caches invalidated")

def invalidate_transaction_cache():
    """Clear only transaction cache"""
    transaction_cache.clear()
    logger.info("🗑️ Transaction cache invalidated")
