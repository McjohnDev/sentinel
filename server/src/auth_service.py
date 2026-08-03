from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from src.models import User, UserRole
from src.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """Service d'authentification des utilisateurs."""
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Vérifie un mot de passe."""
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def get_password_hash(password: str) -> str:
        """Hash un mot de passe."""
        return pwd_context.hash(password)
    
    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Crée un token JWT."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
        return encoded_jwt
    
    @staticmethod
    def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Crée un refresh token JWT."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
        return encoded_jwt
    
    @staticmethod
    def verify_token(token: str) -> Optional[str]:
        """Vérifie un token JWT et retourne l'user_id."""
        try:
            payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
            user_id: str = payload.get("sub")
            if user_id is None:
                return None
            return user_id
        except JWTError:
            return None
    
    @staticmethod
    def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
        """Authentifie un utilisateur."""
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return None
        if not user.is_active:
            return None
        if not AuthService.verify_password(password, user.password_hash):
            return None
        return user
    
    @staticmethod
    def create_user(
        db: Session,
        username: str,
        email: str,
        password: str,
        role: UserRole = UserRole.OPERATOR
    ) -> User:
        """Crée un nouvel utilisateur."""
        import uuid
        
        # Vérifier si l'utilisateur existe déjà
        if db.query(User).filter(User.username == username).first():
            raise ValueError("Nom d'utilisateur déjà utilisé")
        if db.query(User).filter(User.email == email).first():
            raise ValueError("Email déjà utilisé")
        
        user = User(
            id=str(uuid.uuid4()),
            username=username,
            email=email,
            password_hash=AuthService.get_password_hash(password),
            role=role
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        return user
    
    @staticmethod
    def get_user(db: Session, user_id: str) -> Optional[User]:
        """Récupère un utilisateur par son ID."""
        return db.query(User).filter(User.id == user_id).first()
