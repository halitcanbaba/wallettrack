"""
Token management API endpoints
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db, Token, WalletToken
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

@router.post("/tokens/{wallet_id}/{token_id}/hide")
async def hide_token(
    wallet_id: int,
    token_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Hide a specific token from wallet display"""
    try:
        # Update the wallet_token record to set is_hidden = True
        query = (
            update(WalletToken)
            .where(WalletToken.wallet_id == wallet_id)
            .where(WalletToken.token_id == token_id)
            .values(is_hidden=True)
        )
        
        result = await db.execute(query)
        await db.commit()
        
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Wallet token not found")
        
        return {"message": "Token hidden successfully", "wallet_id": wallet_id, "token_id": token_id}
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error hiding token: {str(e)}")

@router.post("/tokens/{wallet_id}/{token_id}/show")
async def show_token(
    wallet_id: int,
    token_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Show a previously hidden token in wallet display"""
    try:
        # Update the wallet_token record to set is_hidden = False
        query = (
            update(WalletToken)
            .where(WalletToken.wallet_id == wallet_id)
            .where(WalletToken.token_id == token_id)
            .values(is_hidden=False)
        )
        
        result = await db.execute(query)
        await db.commit()
        
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Wallet token not found")
        
        return {"message": "Token shown successfully", "wallet_id": wallet_id, "token_id": token_id}
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error showing token: {str(e)}")
