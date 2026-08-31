"""Contrôle d'accès basé sur les rôles (RBAC).

Les endpoints s'appuyaient auparavant sur des comparaisons de rôles dispersées
(`require_role`, `require_operator_or_admin`), avec une particularité piégeuse :
`require_role(X)` acceptait aussi ADMIN, si bien que « exiger le rôle
opérateur » signifiait en réalité « opérateur ou administrateur ». Ajouter un
quatrième rôle imposait de relire chaque appel.

Le modèle est désormais déclaratif : chaque endpoint exige une *permission*,
et la matrice ROLE_PERMISSIONS dit quels rôles la détiennent. Ajouter un rôle
revient à ajouter une ligne dans la matrice, et l'interface peut lire la même
matrice via `/api/auth/permissions` au lieu de la réimplémenter.

Refs: DSH-025, API-003, SEC-002.
"""

from __future__ import annotations

import enum
from typing import Dict, FrozenSet, Iterable, List

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from src.auth_service import AuthService
from src.database import get_db
from src.models import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


class Permission(str, enum.Enum):
    """Droits élémentaires. Nommage `domaine:action`."""

    # --- Parc ---
    AGENT_VIEW = "agent:view"
    AGENT_EDIT = "agent:edit"          # seuils, nom, groupe, fenêtres
    AGENT_REVOKE = "agent:revoke"
    AGENT_DELETE = "agent:delete"
    AGENT_ENROLL_TOKEN = "agent:enroll_token"

    # --- Alertes ---
    ALERT_VIEW = "alert:view"
    ALERT_ACK = "alert:ack"
    ALERT_RESOLVE = "alert:resolve"

    # --- Configuration centrale ---
    CONFIG_VIEW = "config:view"
    CONFIG_PUBLISH = "config:publish"

    # --- Maintenance / disponibilité ---
    MAINTENANCE_VIEW = "maintenance:view"
    MAINTENANCE_EDIT = "maintenance:edit"

    # --- Paramètres plateforme ---
    SETTINGS_VIEW = "settings:view"
    SETTINGS_EDIT = "settings:edit"

    # --- Utilisateurs ---
    USER_VIEW = "user:view"
    USER_MANAGE = "user:manage"

    # --- Audit & conformité ---
    AUDIT_VIEW = "audit:view"
    AUDIT_EXPORT = "audit:export"

    # --- Rapports & analyse ---
    REPORT_VIEW = "report:view"
    REPORT_SCHEDULE = "report:schedule"

    # --- Journaux ---
    LOG_VIEW = "log:view"

    # --- Actions distantes (Lot 2) ---
    ACTION_SUBMIT = "action:submit"
    ACTION_APPROVE = "action:approve"


_VIEW_ONLY: FrozenSet[Permission] = frozenset(
    {
        Permission.AGENT_VIEW,
        Permission.ALERT_VIEW,
        Permission.CONFIG_VIEW,
        Permission.MAINTENANCE_VIEW,
        Permission.SETTINGS_VIEW,
        Permission.REPORT_VIEW,
        Permission.LOG_VIEW,
    }
)

#: Rôle -> permissions détenues. Source de vérité unique, également servie à
#: l'interface pour qu'elle n'ait pas sa propre copie de la règle.
ROLE_PERMISSIONS: Dict[UserRole, FrozenSet[Permission]] = {
    # Administrateur : tout.
    UserRole.ADMIN: frozenset(Permission),
    # Opérateur : exploitation quotidienne. Traite les alertes, ajuste les
    # seuils et pose des fenêtres de maintenance, mais ne gère ni les comptes
    # ni les paramètres de la plateforme.
    UserRole.OPERATOR: _VIEW_ONLY
    | frozenset(
        {
            Permission.AGENT_EDIT,
            Permission.ALERT_ACK,
            Permission.ALERT_RESOLVE,
            Permission.MAINTENANCE_EDIT,
            Permission.ACTION_SUBMIT,
        }
    ),
    # Sécurité / conformité (DSH-025) : lecture complète du parc et accès à la
    # piste d'audit, sans aucun droit de modification. Peut approuver une
    # action distante — c'est le contrôle à quatre yeux attendu par SEC-005.
    UserRole.SECURITY: _VIEW_ONLY
    | frozenset(
        {
            Permission.AUDIT_VIEW,
            Permission.AUDIT_EXPORT,
            Permission.USER_VIEW,
            Permission.ACTION_APPROVE,
        }
    ),
    # Lecture seule : consultation uniquement.
    UserRole.READ_ONLY: _VIEW_ONLY,
}


def permissions_for(role: UserRole) -> FrozenSet[Permission]:
    return ROLE_PERMISSIONS.get(role, frozenset())


def role_has(role: UserRole, permission: Permission) -> bool:
    return permission in permissions_for(role)


def serialize_permissions(role: UserRole) -> List[str]:
    """Liste triée, destinée à l'interface."""
    return sorted(p.value for p in permissions_for(role))


def permission_matrix() -> Dict[str, List[str]]:
    """Matrice complète rôle -> permissions, pour l'écran d'administration."""
    return {role.value: serialize_permissions(role) for role in UserRole}


# --------------------------------------------------------------- dépendances


def require_auth():
    """Exige un jeton valide et un compte actif."""

    async def get_current_user(
        token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
    ) -> User:
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
        # Un compte désactivé conservait l'accès jusqu'à l'expiration de son
        # jeton : la désactivation doit prendre effet immédiatement.
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Compte désactivé",
            )
        return user

    return get_current_user


def require_permission(*required: Permission):
    """Exige toutes les permissions listées."""

    needed = tuple(required)

    def checker(current_user: User = Depends(require_auth())) -> User:
        held = permissions_for(current_user.role)
        missing = [p.value for p in needed if p not in held]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permissions insuffisantes : {', '.join(missing)}",
            )
        return current_user

    return checker


def require_any_permission(*candidates: Permission):
    """Exige au moins une des permissions listées."""

    options = tuple(candidates)

    def checker(current_user: User = Depends(require_auth())) -> User:
        held = permissions_for(current_user.role)
        if not any(p in held for p in options):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissions insuffisantes",
            )
        return current_user

    return checker


def require_roles(*roles: UserRole):
    """Exige explicitement l'un des rôles listés.

    Contrairement à l'ancien `require_role`, ADMIN n'est pas ajouté
    implicitement : le mettre dans la liste quand c'est voulu.
    """

    allowed = frozenset(roles)

    def checker(current_user: User = Depends(require_auth())) -> User:
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissions insuffisantes",
            )
        return current_user

    return checker


def require_admin():
    """Réservé à l'administrateur."""
    return require_roles(UserRole.ADMIN)


# ------------------------------------------------- portée par hôte (point 3)


def user_administers_agent(db: Session, user: User, agent) -> bool:
    """L'utilisateur a-t-il la responsabilité de cet hôte ?

    Trois façons de l'être, par ordre de spécificité : administrateur global,
    responsable nommé de l'hôte, ou membre de l'équipe d'administration à
    laquelle l'hôte est rattaché.

    Un hôte sans responsable ni équipe n'est pas « à tout le monde » : il
    n'est qu'à l'administrateur global. Le contraire — un hôte non attribué
    ouvert à tous — ferait de l'oubli d'attribution une faille silencieuse.
    """
    if user.role == UserRole.ADMIN:
        return True
    if agent is None:
        return False
    if agent.owner_user_id and agent.owner_user_id == user.id:
        return True

    group_id = getattr(agent, "admin_group_id", None)
    if not group_id:
        return False

    from src.models import AdminGroupMember

    membership = (
        db.query(AdminGroupMember.id)
        .filter(
            AdminGroupMember.group_id == group_id,
            AdminGroupMember.user_id == user.id,
        )
        .first()
    )
    return membership is not None


def require_agent_scope(*required: Permission):
    """Exige les permissions ET la responsabilité de l'hôte visé.

    Se compose avec la matrice de rôles au lieu de la remplacer : le rôle dit
    *ce que* l'on sait faire, la portée dit *sur quoi*. Un lecteur seul
    responsable d'un hôte ne gagne donc aucun droit d'écriture, et un
    opérateur ne peut plus modifier les hôtes d'une autre équipe.

    S'utilise sur une route portant `{agent_id}` ; FastAPI injecte le
    paramètre de chemin dans la dépendance.
    """

    needed = tuple(required)

    def checker(
        agent_id: str,
        current_user: User = Depends(require_auth()),
        db: Session = Depends(get_db),
    ) -> User:
        held = permissions_for(current_user.role)
        missing = [p.value for p in needed if p not in held]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permissions insuffisantes : {', '.join(missing)}",
            )

        from src.models import Agent

        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if agent is None:
            # 404 plutôt que 403 : l'hôte n'existe pas, il n'y a pas de
            # question de droit. Répondre 403 laisserait croire qu'il existe.
            raise HTTPException(status_code=404, detail="Agent non trouvé")

        if not user_administers_agent(db, current_user, agent):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Hôte hors de votre périmètre : il est confié à un autre "
                    "responsable ou à une autre équipe d'administration."
                ),
            )
        return current_user

    return checker


# ------------------------------------------------------- compatibilité amont
# Conservés le temps que les endpoints migrent vers require_permission.


def require_role(required_role: UserRole):
    """Ancien comportement : le rôle demandé *ou* administrateur."""
    return require_roles(required_role, UserRole.ADMIN)


def require_operator_or_admin():
    return require_roles(UserRole.OPERATOR, UserRole.ADMIN)
