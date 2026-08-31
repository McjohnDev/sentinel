from typing import List, Dict, Optional
from fastapi import WebSocket
import asyncio
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Gestionnaire de connexions WebSocket pour les notifications en temps réel."""
    
    def __init__(self):
        # Stocke les connexions actives: {user_id: [WebSocket]}
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Capture the FastAPI event loop so sync handlers can publish."""
        self._loop = loop

    def broadcast_sync(self, message: dict) -> None:
        """Schedule broadcast from a threadpool/sync route (heartbeat, ping)."""
        loop = self._loop
        if loop is None or not loop.is_running():
            return
        try:
            asyncio.run_coroutine_threadsafe(self.broadcast(message), loop)
        except Exception:
            logger.debug("presence broadcast skipped", exc_info=True)
    
    async def connect(self, websocket: WebSocket, user_id: str):
        """Accepte une nouvelle connexion WebSocket."""
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
    
    def disconnect(self, websocket: WebSocket, user_id: str):
        """Supprime une connexion WebSocket."""
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
    
    async def send_personal_message(self, message: dict, user_id: str):
        """Envoie un message à un utilisateur spécifique."""
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    # En cas d'erreur, supprimer la connexion
                    self.disconnect(connection, user_id)
    
    async def broadcast(self, message: dict):
        """Diffuse un message à tous les utilisateurs connectés."""
        for user_id, connections in self.active_connections.items():
            for connection in connections:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    # En cas d'erreur, supprimer la connexion
                    self.disconnect(connection, user_id)
    
    async def broadcast_to_role(self, message: dict, role: str, user_roles: Dict[str, str]):
        """Diffuse un message à tous les utilisateurs d'un rôle spécifique."""
        for user_id, user_role in user_roles.items():
            if user_role == role and user_id in self.active_connections:
                for connection in self.active_connections[user_id]:
                    try:
                        await connection.send_json(message)
                    except Exception as e:
                        self.disconnect(connection, user_id)


# Instance globale du gestionnaire de connexions
manager = ConnectionManager()
