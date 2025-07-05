from datetime import datetime
from typing import AsyncGenerator, Optional

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text, Index, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class Blockchain(Base):
    """Blockchain networks (ETH, TRON, BSC, etc.)"""
    __tablename__ = "blockchains"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(10), unique=True, nullable=False)  # ETH, TRON, BSC
    display_name = Column(String(50), nullable=False)  # Ethereum, TRON Network
    native_symbol = Column(String(10), nullable=False)  # ETH, TRX, BNB
    rpc_url = Column(String(255), nullable=True)
    explorer_url = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    wallets = relationship("Wallet", back_populates="blockchain_ref")
    tokens = relationship("Token", back_populates="blockchain_ref")

class Token(Base):
    """Token definitions with contract addresses"""
    __tablename__ = "tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False)  # USDT, USDC, UNI
    name = Column(String(100), nullable=False)  # Tether USD, USD Coin
    contract_address = Column(String(100), nullable=True)  # Contract address (null for native tokens)
    decimals = Column(Integer, default=18)
    blockchain_id = Column(Integer, ForeignKey("blockchains.id"), nullable=False)
    is_native = Column(Boolean, default=False)  # True for ETH, TRX, BNB
    is_verified = Column(Boolean, default=True)  # Verified legitimate token
    logo_url = Column(String(255), nullable=True)
    coingecko_id = Column(String(100), nullable=True)  # For price data
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Composite unique constraint
    __table_args__ = (
        Index('idx_token_blockchain_symbol', 'blockchain_id', 'symbol'),
        Index('idx_token_blockchain_contract', 'blockchain_id', 'contract_address'),
    )
    
    # Relationships
    blockchain_ref = relationship("Blockchain", back_populates="tokens")
    wallet_tokens = relationship("WalletToken", back_populates="token")

class Wallet(Base):
    """User wallets"""
    __tablename__ = "wallets"
    
    id = Column(Integer, primary_key=True, index=True)
    address = Column(String(100), nullable=False)
    name = Column(String(100), nullable=True)  # User-friendly name
    blockchain_id = Column(Integer, ForeignKey("blockchains.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    last_updated = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Composite unique constraint (address can be same on different blockchains)
    __table_args__ = (
        Index('idx_wallet_blockchain_address', 'blockchain_id', 'address', unique=True),
    )
    
    # Relationships
    blockchain_ref = relationship("Blockchain", back_populates="wallets")
    wallet_tokens = relationship("WalletToken", back_populates="wallet", cascade="all, delete-orphan")
    balance_history = relationship("BalanceHistory", back_populates="wallet", cascade="all, delete-orphan")

class WalletToken(Base):
    """Current wallet token balances (only latest balance)"""
    __tablename__ = "wallet_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    wallet_id = Column(Integer, ForeignKey("wallets.id"), nullable=False)
    token_id = Column(Integer, ForeignKey("tokens.id"), nullable=False)
    balance = Column(Float, nullable=False, default=0.0)
    usd_value = Column(Float, nullable=True)  # USD equivalent (if available)
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    # Unique constraint - one record per wallet/token pair
    __table_args__ = (
        Index('idx_wallet_token_unique', 'wallet_id', 'token_id', unique=True),
        Index('idx_wallet_token_balance', 'wallet_id', 'balance'),
    )
    
    # Relationships
    wallet = relationship("Wallet", back_populates="wallet_tokens")
    token = relationship("Token", back_populates="wallet_tokens")

class BalanceHistory(Base):
    """Historical balance data (only significant changes)"""
    __tablename__ = "balance_history"
    
    id = Column(Integer, primary_key=True, index=True)
    wallet_id = Column(Integer, ForeignKey("wallets.id"), nullable=False)
    token_id = Column(Integer, ForeignKey("tokens.id"), nullable=False)
    balance_before = Column(Float, nullable=False)
    balance_after = Column(Float, nullable=False)
    change_amount = Column(Float, nullable=False)  # Calculated field
    change_percentage = Column(Float, nullable=True)  # Calculated field
    usd_value_before = Column(Float, nullable=True)
    usd_value_after = Column(Float, nullable=True)
    transaction_hash = Column(String(100), nullable=True)  # Related transaction if available
    change_type = Column(String(20), nullable=False)  # 'increase', 'decrease', 'transfer_in', 'transfer_out'
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_balance_history_wallet_token', 'wallet_id', 'token_id'),
        Index('idx_balance_history_timestamp', 'timestamp'),
        Index('idx_balance_history_wallet_time', 'wallet_id', 'timestamp'),
    )
    
    # Relationships
    wallet = relationship("Wallet", back_populates="balance_history")
    token = relationship("Token")

class Transaction(Base):
    """Transaction records for portfolio tracking"""
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    wallet_id = Column(Integer, ForeignKey("wallets.id"), nullable=False)
    blockchain_id = Column(Integer, ForeignKey("blockchains.id"), nullable=False)
    hash = Column(String(100), unique=True, nullable=False)
    from_address = Column(String(100), nullable=False)
    to_address = Column(String(100), nullable=False)
    token_id = Column(Integer, ForeignKey("tokens.id"), nullable=True)  # null for native token
    amount = Column(Float, nullable=False)
    usd_value = Column(Float, nullable=True)
    gas_used = Column(Float, nullable=True)
    gas_price = Column(Float, nullable=True)
    transaction_type = Column(String(20), nullable=False)  # 'send', 'receive', 'swap', 'stake', 'unstake'
    status = Column(String(20), default='confirmed')  # 'pending', 'confirmed', 'failed'
    block_number = Column(Integer, nullable=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Indexes
    __table_args__ = (
        Index('idx_transaction_wallet', 'wallet_id'),
        Index('idx_transaction_hash', 'hash'),
        Index('idx_transaction_timestamp', 'timestamp'),
        Index('idx_transaction_wallet_time', 'wallet_id', 'timestamp'),
    )
    
    # Relationships
    wallet = relationship("Wallet")
    blockchain = relationship("Blockchain")
    token = relationship("Token")

class SystemConfig(Base):
    """System configuration and settings"""
    __tablename__ = "system_config"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text, nullable=True)
    description = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

# Database configuration
DATABASE_URL = "sqlite+aiosqlite:///./wallettrack.db"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL logging
    connect_args={"check_same_thread": False}
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def init_db():
    """Initialize the database with new schema"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# Initial data seeding functions
async def seed_initial_data():
    """Seed initial blockchain and token data"""
    async with AsyncSessionLocal() as session:
        try:
            # Check if data already exists
            result = await session.execute(text("SELECT COUNT(*) FROM blockchains"))
            count = result.scalar()
            if count > 0:
                return  # Data already seeded
            
            # Create blockchains
            eth_blockchain = Blockchain(
                name="ETH",
                display_name="Ethereum",
                native_symbol="ETH",
                rpc_url="https://eth.llamarpc.com",
                explorer_url="https://etherscan.io"
            )
            
            tron_blockchain = Blockchain(
                name="TRON",
                display_name="TRON Network",
                native_symbol="TRX",
                rpc_url="https://api.trongrid.io",
                explorer_url="https://tronscan.org"
            )
            
            session.add_all([eth_blockchain, tron_blockchain])
            await session.flush()  # Get IDs
            
            # Create native tokens
            eth_token = Token(
                symbol="ETH",
                name="Ethereum",
                blockchain_id=eth_blockchain.id,
                is_native=True,
                decimals=18
            )
            
            trx_token = Token(
                symbol="TRX",
                name="TRON",
                blockchain_id=tron_blockchain.id,
                is_native=True,
                decimals=6
            )
            
            # Create major ERC-20 tokens
            eth_tokens = [
                Token(symbol="USDT", name="Tether USD", contract_address="0xdAC17F958D2ee523a2206206994597C13D831ec7", decimals=6, blockchain_id=eth_blockchain.id),
                Token(symbol="USDC", name="USD Coin", contract_address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", decimals=6, blockchain_id=eth_blockchain.id),
                Token(symbol="DAI", name="Dai Stablecoin", contract_address="0x6B175474E89094C44Da98b954EedeAC495271d0F", decimals=18, blockchain_id=eth_blockchain.id),
                Token(symbol="WETH", name="Wrapped Ether", contract_address="0xC02aaA39b223FE8D0763b4DF1C5c72B3A7160096", decimals=18, blockchain_id=eth_blockchain.id),
                Token(symbol="UNI", name="Uniswap", contract_address="0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984", decimals=18, blockchain_id=eth_blockchain.id),
                Token(symbol="PEPE", name="Pepe", contract_address="0x6982508145454ce325ddbe47a25d4ec3d2311933", decimals=18, blockchain_id=eth_blockchain.id),
                Token(symbol="SHIB", name="SHIBA INU", contract_address="0x95aD61b0a150d79219dCF64E1E6Cc01f0B64C4cE", decimals=18, blockchain_id=eth_blockchain.id),
                Token(symbol="STRK", name="Starknet Token", contract_address="0xCa14007Eff0dB1f8135f4C25B34De49AB0d42766", decimals=18, blockchain_id=eth_blockchain.id),
                Token(symbol="POL", name="Polygon", contract_address="0x455e53190a72525a3dE3c6A6E70C5f6F27Cfa28a", decimals=18, blockchain_id=eth_blockchain.id),
                Token(symbol="GALA", name="Gala", contract_address="0x15D4c048F83bd7e37d49eA4C83a07267Ec4203dA", decimals=8, blockchain_id=eth_blockchain.id),
                Token(symbol="MANA", name="Decentraland", contract_address="0x0F5D2fB29fb7d3CFeE444a200298f468908cC942", decimals=18, blockchain_id=eth_blockchain.id),
                Token(symbol="SAND", name="The Sandbox", contract_address="0x3845badAde8e6dFF049820680d1F14bD3903a5d0", decimals=18, blockchain_id=eth_blockchain.id),
                Token(symbol="COMBO", name="Combo", contract_address="0xfFffFffF2ba8F66D4e51811C5190992176930278", decimals=18, blockchain_id=eth_blockchain.id),
            ]
            
            # Create major TRC-20 tokens
            tron_tokens = [
                Token(symbol="USDT", name="Tether USD (TRC-20)", contract_address="TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t", decimals=6, blockchain_id=tron_blockchain.id),
            ]
            
            session.add_all([eth_token, trx_token] + eth_tokens + tron_tokens)
            await session.commit()
            
        except Exception as e:
            await session.rollback()
            raise e
