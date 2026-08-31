import logging
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from jose import JWTError, jwt
from sqlalchemy import func
from sqlalchemy.orm import Session
from src.models import AuthSource, User, UserRole
from src.config import settings

logger = logging.getLogger(__name__)

# bcrypt tronque silencieusement au-delà de 72 octets : on refuse plutôt que
# d'accepter un mot de passe dont seule la tête serait vérifiée.
BCRYPT_MAX_BYTES = 72
BCRYPT_ROUNDS = 12


class AuthService:
    """Service d'authentification des utilisateurs.

    Le hachage s'appuie directement sur `bcrypt`. Il passait auparavant par
    passlib 1.7.4, qui lit `bcrypt.__about__` — attribut retiré dans bcrypt
    4.1 : tout hachage levait alors `ValueError` au runtime selon la version
    installée. Les empreintes restent au format bcrypt `$2b$`, donc les mots
    de passe existants continuent d'être vérifiés sans migration.
    """

    @staticmethod
    def _encode(password: str) -> bytes:
        raw = password.encode("utf-8")
        if len(raw) > BCRYPT_MAX_BYTES:
            raise ValueError(
                f"Mot de passe trop long : {len(raw)} octets, maximum {BCRYPT_MAX_BYTES}"
            )
        return raw

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Vérifie un mot de passe."""
        if not plain_password or not hashed_password:
            return False
        try:
            return bcrypt.checkpw(
                AuthService._encode(plain_password),
                hashed_password.encode("utf-8"),
            )
        except (ValueError, TypeError):
            # Empreinte illisible ou tronquée en base : échec de vérification,
            # jamais une exception qui remonterait en 500 sur /auth/login.
            logger.warning("Empreinte de mot de passe invalide en base")
            return False

    @staticmethod
    def get_password_hash(password: str) -> str:
        """Hash un mot de passe."""
        return bcrypt.hashpw(
            AuthService._encode(password),
            bcrypt.gensalt(rounds=BCRYPT_ROUNDS),
        ).decode("utf-8")
    
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
        """Authentifie un utilisateur, par annuaire puis en local.

        Ordre volontaire : l'annuaire d'abord quand il est actif, afin qu'un
        compte désactivé côté CBC perde l'accès immédiatement. L'échec bascule
        sur l'authentification locale (si autorisée), ce qui préserve l'accès
        de l'administrateur de secours pendant une panne d'annuaire.
        """
        from src.ldap_service import LdapService

        if LdapService.is_enabled():
            profile = LdapService.authenticate(username, password, db=db)
            if profile is not None:
                return AuthService.sync_ldap_user(db, profile)
            if not settings.ldap_allow_local_fallback:
                # Repli désactivé : ne pas tester le mot de passe local, sinon
                # un compte d'annuaire révoqué pourrait rester utilisable via
                # une empreinte locale résiduelle.
                return None

        user = AuthService.resolve_local_user(db, username)
        if not user:
            return None
        if not user.is_active:
            return None
        # Un compte d'annuaire n'a pas de mot de passe local exploitable : il
        # ne doit jamais être authentifiable localement.
        if getattr(user, "auth_source", None) == AuthSource.LDAP:
            return None
        if not AuthService.verify_password(password, user.password_hash):
            return None
        AuthService._stamp_login(db, user)
        return user

    @staticmethod
    def resolve_local_user(db: Session, identifier: str) -> Optional[User]:
        """Retrouve un compte à partir de son nom de connexion OU de son email.

        L'identifiant saisi est accepté tel quel : le formulaire imposait une
        adresse email puis n'en transmettait que la partie locale, ce qui
        interdisait la connexion par nom d'utilisateur et confondait deux
        adresses de domaines différents. La casse est ignorée — un annuaire
        comme une boîte mail traitent « P.Nom » et « p.nom » comme un seul
        compte, et l'utilisateur ne doit pas avoir à la deviner.
        """
        identifier = (identifier or "").strip()
        if not identifier:
            return None

        exact = db.query(User).filter(User.username == identifier).first()
        if exact:
            return exact

        folded = identifier.lower()
        insensitive = (
            db.query(User)
            .filter(func.lower(User.username) == folded)
            .first()
        )
        if insensitive:
            return insensitive

        return db.query(User).filter(func.lower(User.email) == folded).first()

    @staticmethod
    def _stamp_login(db: Session, user: User) -> None:
        try:
            user.last_login_at = datetime.utcnow()
            db.commit()
        except Exception:  # noqa: BLE001 — la traçabilité ne doit pas bloquer le login
            db.rollback()
            logger.debug("Horodatage de connexion impossible", exc_info=True)

    @staticmethod
    def sync_ldap_user(db: Session, profile) -> User:
        """Crée ou met à jour le compte local miroir d'un compte d'annuaire.

        **Partage des responsabilités.** L'annuaire répond à « qui êtes-vous »
        et rien d'autre ; les rôles et les droits se gèrent dans
        l'application. Concrètement :

        * à la **création** du compte, le rôle issu de l'annuaire
          (correspondance ou `LDAP_DEFAULT_ROLE`) sert d'amorce ;
        * aux connexions **suivantes**, le rôle enregistré dans l'application
          fait foi et n'est jamais réécrit.

        Le comportement inverse — réaligner le rôle à chaque connexion —
        rendait l'écran Utilisateurs illusoire : une promotion accordée par un
        administrateur était annulée à la connexion suivante de l'intéressé,
        sans trace ni message. Il était impossible de comprendre pourquoi les
        droits « ne tenaient pas ».

        Ce que l'annuaire continue de gouverner : l'identité (DN, adresse) et
        surtout l'**accès** — un compte désactivé côté annuaire ne peut plus
        s'authentifier du tout, la révocation reste donc immédiate.
        """
        import uuid

        user = db.query(User).filter(User.external_id == profile.dn).first()
        if user is None:
            user = db.query(User).filter(User.username == profile.username).first()

        if user is None:
            user = User(
                id=str(uuid.uuid4()),
                username=profile.username,
                email=profile.email or f"{profile.username}@ldap.local",
                # Empreinte inutilisable : le compte s'authentifie par bind.
                password_hash="!ldap",
                # Rôle d'amorce uniquement — modifiable ensuite dans l'application.
                role=profile.role,
                auth_source=AuthSource.LDAP,
                external_id=profile.dn,
                is_active=True,
            )
            db.add(user)
            logger.info(
                "Compte provisionné depuis l'annuaire : %s (rôle initial %s, modifiable dans l'application)",
                profile.username,
                profile.role.value,
            )
        else:
            # Identité : l'annuaire fait foi.
            user.auth_source = AuthSource.LDAP
            user.external_id = profile.dn
            if profile.email:
                user.email = profile.email
            # Rôle et activation : décisions applicatives, laissées intactes.
            # Réactiver ici un compte désactivé par un administrateur viderait
            # la désactivation de son sens.
            if user.role != profile.role:
                logger.debug(
                    "Rôle applicatif conservé pour %s : %s (l'annuaire suggérait %s)",
                    profile.username,
                    user.role.value,
                    profile.role.value,
                )

        user.last_login_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
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
