from sqlalchemy import Column, String, DateTime, Enum as SQLEnum
from sqlalchemy.sql import func
from datetime import datetime
import enum


class UserRole(enum.Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    READ_ONLY = "read_only"


class User:
    """Modèle de données pour un utilisateur du dashboard."""
    
    __tablename__ = 'users'
    
    id = Column(String, primary_key=True)
    username = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    
    role = Column(SQLEnum(UserRole), default=UserRole.OPERATOR, nullable=False)
    
    is_active = Column(String, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
