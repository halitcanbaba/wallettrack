from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

# Base schemas
class BlockchainBase(BaseModel):
    name: str = Field(..., max_length=10, description="Blockchain name (ETH, TRON, BSC)")
    display_name: str = Field(..., max_length=50, description="Human-readable name")
    native_symbol: str = Field(..., max_length=10, description="Native token symbol")

class BlockchainCreate(BlockchainBase):
    rpc_url: Optional[str] = None
    explorer_url: Optional[str] = None

class BlockchainResponse(BlockchainBase):
    id: int
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

# Token schemas
class TokenBase(BaseModel):
    symbol: str = Field(..., max_length=20, description="Token symbol")
    name: str = Field(..., max_length=100, description="Token name")
    contract_address: Optional[str] = Field(None, max_length=100, description="Contract address")
    decimals: int = Field(18, ge=0, le=18, description="Token decimals")

class TokenCreate(TokenBase):
    blockchain_id: int
    is_verified: bool = True
    logo_url: Optional[str] = None
    coingecko_id: Optional[str] = None

class TokenResponse(TokenBase):
    id: int
    blockchain_id: int
    is_native: bool
    is_verified: bool
    logo_url: Optional[str] = None
    coingecko_id: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

# Wallet schemas
class WalletBase(BaseModel):
    address: str = Field(..., max_length=100, description="Wallet address")
    name: Optional[str] = Field(None, max_length=100, description="Friendly name")

class WalletCreate(WalletBase):
    blockchain_id: int

class WalletUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None

class WalletResponse(WalletBase):
    id: int
    blockchain_id: int
    is_active: bool
    last_updated: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True

# Balance schemas
class TokenBalance(BaseModel):
    token_id: int
    token_symbol: str
    token_name: str
    balance: float = Field(..., ge=0, description="Token balance")
    usd_value: Optional[float] = Field(None, ge=0, description="USD equivalent")
    last_updated: datetime

class WalletTokenResponse(BaseModel):
    id: int
    wallet_id: int
    token: TokenResponse
    balance: float
    usd_value: Optional[float]
    last_updated: datetime
    
    class Config:
        from_attributes = True

class WalletWithBalances(WalletResponse):
    blockchain: BlockchainResponse
    balances: List[TokenBalance] = []
    total_usd_value: Optional[float] = None

# Balance history schemas
class BalanceHistoryResponse(BaseModel):
    id: int
    token: TokenResponse
    balance_before: float
    balance_after: float
    change_amount: float
    change_percentage: Optional[float]
    usd_value_before: Optional[float]
    usd_value_after: Optional[float]
    transaction_hash: Optional[str]
    change_type: str
    timestamp: datetime
    
    class Config:
        from_attributes = True

# Transaction schemas
class TransactionBase(BaseModel):
    hash: str = Field(..., max_length=100, description="Transaction hash")
    from_address: str = Field(..., max_length=100)
    to_address: str = Field(..., max_length=100)
    amount: float = Field(..., ge=0)
    transaction_type: str = Field(..., max_length=20)
    timestamp: datetime

class TransactionCreate(TransactionBase):
    wallet_id: int
    blockchain_id: int
    token_id: Optional[int] = None
    usd_value: Optional[float] = None
    gas_used: Optional[float] = None
    gas_price: Optional[float] = None
    status: str = "confirmed"
    block_number: Optional[int] = None

class TransactionResponse(TransactionBase):
    id: int
    wallet_id: int
    blockchain: BlockchainResponse
    token: Optional[TokenResponse] = None
    usd_value: Optional[float]
    gas_used: Optional[float]
    gas_price: Optional[float]
    status: str
    block_number: Optional[int]
    created_at: datetime
    
    class Config:
        from_attributes = True

# Statistics schemas
class TokenStats(BaseModel):
    token: TokenResponse
    total_holders: int
    total_balance: float
    total_usd_value: Optional[float]

class WalletStats(BaseModel):
    total_wallets: int
    active_wallets: int
    wallets_by_blockchain: dict
    total_balance_changes_24h: int

class SystemStats(BaseModel):
    wallet_stats: WalletStats
    top_tokens: List[TokenStats]
    total_usd_value: Optional[float]
    last_updated: datetime

# API Response schemas
class ApiResponse(BaseModel):
    success: bool = True
    message: Optional[str] = None
    data: Optional[dict] = None

class PaginatedResponse(BaseModel):
    items: List[dict]
    total: int
    page: int
    per_page: int
    pages: int

# WebSocket message schemas
class WebSocketMessage(BaseModel):
    type: str  # "balance_update", "new_transaction", "wallet_added", etc.
    data: dict
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class BalanceUpdateMessage(WebSocketMessage):
    type: str = "balance_update"
    
class TransactionMessage(WebSocketMessage):
    type: str = "new_transaction"

# Error schemas
class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None

# Legacy compatibility schemas (for backward compatibility during migration)
class LegacyWalletCreate(BaseModel):
    address: str
    name: Optional[str] = None
    blockchain: str = "ETH"  # ETH or TRON

class LegacyTokenBalance(BaseModel):
    token: str
    balance: float

class LegacyWalletResponse(BaseModel):
    id: int
    address: str
    name: Optional[str]
    blockchain: str
    balances: List[LegacyTokenBalance] = []
    last_updated: Optional[datetime]
    created_at: datetime
