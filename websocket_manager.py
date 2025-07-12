import asyncio
import json
import logging
from typing import Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection"""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"New WebSocket connection. Total: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send a message to a specific connection"""
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
            self.disconnect(websocket)
    
    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients"""
        if not self.active_connections:
            logger.info("📡 No active WebSocket connections for broadcast")
            return
        
        logger.info(f"📡 Broadcasting to {len(self.active_connections)} connections: {message.get('type', 'unknown')}")
        message_str = json.dumps(message, default=str)
        disconnected = set()
        
        for connection in self.active_connections.copy():  # Use copy to avoid modification during iteration
            try:
                # Check if connection is still active before sending
                try:
                    if hasattr(connection, 'client_state') and connection.client_state.name == "CONNECTED":
                        await connection.send_text(message_str)
                    else:
                        logger.warning(f"Connection state not CONNECTED, marking for removal")
                        disconnected.add(connection)
                except AttributeError:
                    # Fallback: try to send anyway if client_state is not available
                    await connection.send_text(message_str)
            except Exception as e:
                logger.error(f"Error broadcasting to connection: {e}")
                disconnected.add(connection)
        
        # Remove disconnected connections
        for conn in disconnected:
            self.disconnect(conn)
    
    async def broadcast_balance_update(self, wallet_id: int, address: str, name: str, 
                                     blockchain: str = "TRON", **kwargs):
        """Broadcast balance update to all clients"""
        data = {
            "wallet_id": wallet_id,
            "address": address,
            "name": name,
            "blockchain": blockchain,
            "timestamp": kwargs.get("timestamp").isoformat() if kwargs.get("timestamp") else None
        }
        
        # Add balance data based on blockchain type
        if blockchain == "ETH":
            data.update({
                "native_balance": kwargs.get("native_balance", 0.0),
                "token_balances": kwargs.get("token_balances", {})
            })
        else:
            # TRON - maintain backward compatibility
            data.update({
                "trx_balance": kwargs.get("trx_balance", 0.0),
                "usdt_balance": kwargs.get("usdt_balance", 0.0)
            })
        
        message = {
            "type": "balance_update",
            "data": data
        }
        await self.broadcast(message)
    
    async def broadcast_wallet_added(self, wallet_data: dict):
        """Broadcast new wallet addition to all clients"""
        message = {
            "type": "wallet_added",
            "data": wallet_data
        }
        await self.broadcast(message)
    
    async def broadcast_wallet_removed(self, wallet_id: int):
        """Broadcast wallet removal to all clients"""
        message = {
            "type": "wallet_removed",
            "data": {"wallet_id": wallet_id}
        }
        await self.broadcast(message)
    
    async def broadcast_transaction_update(self, transaction_data: dict):
        """Broadcast new transaction to all clients"""
        message = {
            "type": "new_transaction",
            "data": transaction_data
        }
        await self.broadcast(message)
    
    async def broadcast_system_status(self, status_data: dict):
        """Broadcast system status update to all clients"""
        message = {
            "type": "system_status",
            "data": status_data
        }
        await self.broadcast(message)
    
    async def send_heartbeat(self):
        """Send heartbeat to all connections"""
        message = {
            "type": "heartbeat",
            "data": {
                "timestamp": asyncio.get_event_loop().time(),
                "active_connections": len(self.active_connections)
            }
        }
        await self.broadcast(message)
    
    def get_connection_count(self) -> int:
        """Get current connection count"""
        return len(self.active_connections)

# Global connection manager instance
manager = ConnectionManager()
