"""
WebSocket management and utilities
"""
import asyncio
import json
from datetime import datetime

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import select, func

from database import Wallet, AsyncSessionLocal
from app.core.dependencies import logger
from websocket_manager import manager

async def websocket_endpoint(websocket: WebSocket):
    """Enhanced WebSocket endpoint for real-time updates"""
    await manager.connect(websocket)
    logger.info(f"WebSocket client connected from {websocket.client}")
    
    try:
        # Send initial connection message
        await websocket.send_json({
            "type": "connection_established",
            "data": {
                "message": "Connected to WalletTrack Pro v2",
                "timestamp": datetime.utcnow().isoformat(),
                "server_version": "2.0.0"
            }
        })
        
        # Send initial status
        await websocket.send_json({
            "type": "system_status", 
            "data": {
                "wallets_count": await get_wallets_count(),
                "active_connections": manager.get_connection_count()
            }
        })
        
        while True:
            try:
                # Wait for client messages with timeout
                message = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                
                try:
                    data = json.loads(message) if message else {}
                    await handle_client_message(websocket, data)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON received: {message}")
                    
            except asyncio.TimeoutError:
                # Send heartbeat
                try:
                    await websocket.send_json({
                        "type": "heartbeat",
                        "data": {
                            "timestamp": datetime.utcnow().isoformat(),
                            "active_connections": manager.get_connection_count()
                        }
                    })
                except Exception as heartbeat_error:
                    logger.warning(f"Heartbeat failed: {heartbeat_error}")
                    break
                    
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected normally")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        manager.disconnect(websocket)

async def handle_client_message(websocket: WebSocket, data: dict):
    """Handle messages from WebSocket clients"""
    message_type = data.get("type")
    
    if message_type == "ping":
        await websocket.send_json({
            "type": "pong",
            "data": {"timestamp": datetime.utcnow().isoformat()}
        })
    elif message_type == "request_wallet_update":
        wallet_id = data.get("wallet_id")
        if wallet_id:
            # Trigger wallet update
            await websocket.send_json({
                "type": "wallet_update_requested",
                "data": {"wallet_id": wallet_id}
            })
    elif message_type == "request_status":
        # Send current system status
        await websocket.send_json({
            "type": "system_status",
            "data": {
                "wallets_count": await get_wallets_count(),
                "active_connections": manager.get_connection_count(),
                "timestamp": datetime.utcnow().isoformat()
            }
        })

async def get_wallets_count() -> int:
    """Get current wallet count"""
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(func.count(Wallet.id)).where(Wallet.is_active == True)
            )
            return result.scalar() or 0
    except Exception:
        return 0
