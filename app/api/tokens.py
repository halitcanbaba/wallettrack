"""
Token management API endpoints
"""
from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db, Token
from schemas import TokenResponse, BlockchainResponse

router = APIRouter(prefix="/api", tags=["tokens"])

@router.get("/tokens", response_model=List[TokenResponse])
async def get_tokens(
    blockchain_id: Optional[int] = None,
    verified_only: bool = True,
    db: AsyncSession = Depends(get_db)
):
    """Get available tokens, optionally filtered by blockchain"""
    
    query = select(Token).options(selectinload(Token.blockchain_ref))
    
    if blockchain_id:
        query = query.where(Token.blockchain_id == blockchain_id)
    
    if verified_only:
        query = query.where(Token.is_verified == True)
    
    query = query.order_by(Token.symbol)
    
    result = await db.execute(query)
    tokens = result.scalars().all()
    
    token_list = []
    for token in tokens:
        token_response = TokenResponse(
            id=token.id,
            symbol=token.symbol,
            name=token.name,
            contract_address=token.contract_address,
            decimals=token.decimals,
            blockchain_id=token.blockchain_id,
            is_native=token.is_native,
            is_verified=token.is_verified,
            created_at=token.created_at,
            blockchain=BlockchainResponse(
                id=token.blockchain_ref.id,
                name=token.blockchain_ref.name,
                display_name=token.blockchain_ref.display_name,
                native_symbol=token.blockchain_ref.native_symbol,
                is_active=token.blockchain_ref.is_active,
                created_at=token.blockchain_ref.created_at
            )
        )
        token_list.append(token_response)
    
    return token_list
