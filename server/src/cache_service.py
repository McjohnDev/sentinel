import redis
import json
from typing import Optional, Any
from src.config import settings


class CacheService:
    """Service de cache Redis pour optimiser les requêtes fréquentes."""
    
    def __init__(self):
        self.redis_client = redis.Redis(
            host='localhost',
            port=6379,
            db=0,
            decode_responses=True
        )
    
    def get(self, key: str) -> Optional[Any]:
        """Récupère une valeur du cache."""
        try:
            value = self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            print(f"Erreur lors de la récupération du cache: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Stocke une valeur dans le cache avec un TTL (par défaut 5 minutes)."""
        try:
            self.redis_client.setex(key, ttl, json.dumps(value))
            return True
        except Exception as e:
            print(f"Erreur lors du stockage dans le cache: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Supprime une valeur du cache."""
        try:
            self.redis_client.delete(key)
            return True
        except Exception as e:
            print(f"Erreur lors de la suppression du cache: {e}")
            return False
    
    def delete_pattern(self, pattern: str) -> bool:
        """Supprime toutes les clés correspondant au pattern."""
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
            return True
        except Exception as e:
            print(f"Erreur lors de la suppression du cache par pattern: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """Vérifie si une clé existe dans le cache."""
        try:
            return self.redis_client.exists(key) > 0
        except Exception as e:
            print(f"Erreur lors de la vérification du cache: {e}")
            return False


# Instance globale du service de cache
cache_service = CacheService()
