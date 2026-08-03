from functools import wraps
from fastapi import HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from src.auth_service import AuthService
from src.models import User, UserRole
from src.database import get_db
from typing import Optional

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def require_auth():
    """Décorateur pour exiger l'authentification."""
    async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
        user_id = AuthService.verify_token(token)
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token invalide",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user = AuthService.get_user(db, user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Utilisateur non trouvé",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user
    return get_current_user


def require_role(required_role: UserRole):
    """Décorateur pour exiger un rôle spécifique."""
    def role_checker(current_user: User = Depends(require_auth())):
        if current_user.role != required_role and current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissions insuffisantes"
            )
        return current_user
    return role_checker


def require_admin():
    """Décorateur pour exiger le rôle admin."""
    return require_role(UserRole.ADMIN)


def require_operator_or_admin():
    """Décorateur pour exiger le rôle operator ou admin."""
    def role_checker(current_user: User = Depends(require_auth())):
        if current_user.role not in [UserRole.ADMIN, UserRole.OPERATOR]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissions insuffisantes"
            )
        return current_user
    return role_checker
