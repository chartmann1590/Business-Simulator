from fastapi import WebSocket, WebSocketDisconnect
from engine.office_simulator import OfficeSimulator
import json

class ConnectionManager:
    def __init__(self, simulator: OfficeSimulator):
        self.simulator = simulator
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        await self.simulator.add_websocket(websocket)
    
    async def disconnect(self, websocket: WebSocket):
        await self.simulator.remove_websocket(websocket)

async def websocket_endpoint(websocket: WebSocket, simulator: OfficeSimulator):
    """WebSocket endpoint for real-time updates."""
    manager = ConnectionManager(simulator)
    await manager.connect(websocket)
    
    try:
        while True:
            # Keep connection alive and handle any incoming messages
            data = await websocket.receive_text()
            # Echo back or handle message if needed
            await websocket.send_json({"type": "ack", "message": "received"})
    except WebSocketDisconnect:
        await manager.disconnect(websocket)





