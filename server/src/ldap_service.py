"""Authentification sur annuaire d'entreprise (LDAP / Active Directory).

Objectif : permettre à CBC d'utiliser les comptes de son annuaire plutôt que
des comptes locaux, sans perdre la possibilité de se connecter localement si
l'annuaire est injoignable.

Principes retenus :

* **L'annuaire ne stocke jamais de mot de passe chez nous.** L'authentification
  est un *bind* LDAP avec les identifiants saisis. Aucun hash local n'est créé
  pour un compte d'annuaire.
* **Provisionnement à la première connexion.** Un compte local miroir est créé
  au premier login réussi, pour porter le rôle, l'état actif et les relations
  (hiérarchie de notification). Il est marqué `auth_source = LDAP`.
* **Le rôle vient des groupes.** Une table de correspondance groupe -> rôle est
  configurable ; à chaque connexion le rôle est réaligné sur l'annuaire, de
  sorte qu'un retrait de groupe prenne effet sans intervention.
* **Repli local explicite.** Les comptes locaux (dont l'administrateur de
  secours) continuent de fonctionner : c'est ce qui évite de perdre l'accès à
  la plateforme quand l'annuaire tombe.
* **Dégradation propre.** Toute erreur d'annuaire est journalisée et renvoie
  « échec d'authentification » — jamais une 500.

La dépendance `ldap3` est optionnelle : si elle n'est pas installée, le service
se déclare indisponible et l'authentification locale continue de fonctionner.

Refs: API-003, DSH-025, SEC-002.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.config import settings
from src.models import UserRole

logger = logging.getLogger(__name__)

try:  # pragma: no cover - dépend de l'environnement d'installation
    import ldap3
    from ldap3.core.exceptions import LDAPException

    LDAP3_AVAILABLE = True
except ImportError:  # pragma: no cover
    ldap3 = None  # type: ignore[assignment]

    class LDAPException(Exception):  # type: ignore[no-redef]
        """Substitut quand ldap3 n'est pas installé."""

    LDAP3_AVAILABLE = False


@dataclass
class LdapProfile:
    """Identité résolue depuis l'annuaire."""

    username: str
    email: str
    display_name: str
    dn: str
    groups: List[str] = field(default_factory=list)
    role: UserRole = UserRole.READ_ONLY
    # Attributs métier repris de l'annuaire (matricule, service, agence…).
    attributes: Dict[str, str] = field(default_factory=dict)


class LdapConfigError(Exception):
    """Configuration LDAP incomplète ou incohérente."""


def _parse_role_mapping(raw: str) -> Dict[str, UserRole]:
    """Interprète la correspondance groupe -> rôle.

    Format attendu (JSON) : {"CN=SOC,OU=Groupes,DC=cbc,DC=cm": "operator"}.
    Les clés sont comparées sans tenir compte de la casse : les annuaires ne
    sont pas cohérents sur ce point.
    """
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        logger.error("LDAP_ROLE_MAPPING n'est pas un JSON valide — ignoré")
        return {}
    if not isinstance(parsed, dict):
        logger.error("LDAP_ROLE_MAPPING doit être un objet JSON — ignoré")
        return {}

    mapping: Dict[str, UserRole] = {}
    for group, role_name in parsed.items():
        try:
            mapping[str(group).strip().lower()] = UserRole(str(role_name).strip().lower())
        except ValueError:
            logger.error(
                "Rôle inconnu dans LDAP_ROLE_MAPPING pour %s : %r", group, role_name
            )
    return mapping


class LdapService:
    """Client LDAP sans état ; toute la configuration vient de `settings`."""

    # ------------------------------------------------------------- état

    @staticmethod
    def is_enabled() -> bool:
        """L'authentification annuaire est-elle exploitable ?"""
        if not settings.ldap_enabled:
            return False
        if not LDAP3_AVAILABLE:
            logger.error(
                "LDAP_ENABLED=true mais le paquet ldap3 est absent — "
                "authentification annuaire indisponible"
            )
            return False
        if not settings.ldap_server_uri or not settings.ldap_user_search_base:
            logger.error(
                "LDAP_ENABLED=true mais LDAP_SERVER_URI ou LDAP_USER_SEARCH_BASE "
                "est vide — authentification annuaire indisponible"
            )
            return False
        return True

    @staticmethod
    def status() -> Dict[str, Any]:
        """Résumé destiné à l'écran Paramètres (aucun secret exposé)."""
        return {
            "enabled": bool(settings.ldap_enabled),
            "library_available": LDAP3_AVAILABLE,
            "operational": LdapService.is_enabled(),
            "server_uri": settings.ldap_server_uri or None,
            "user_search_base": settings.ldap_user_search_base or None,
            "user_filter": settings.ldap_user_filter,
            "use_ssl": bool(settings.ldap_use_ssl),
            "start_tls": bool(settings.ldap_start_tls),
            "tls_verify": bool(settings.ldap_tls_verify),
            "default_role": settings.ldap_default_role,
            "role_mapping": {
                k: v.value for k, v in _parse_role_mapping(settings.ldap_role_mapping).items()
            },
            "bind_dn_configured": bool(settings.ldap_bind_dn),
            "follow_referrals": bool(settings.ldap_follow_referrals),
            # Rendu explicite : un bind en clair est une information
            # d'exploitation, pas un détail de configuration.
            "plaintext_bind": bool(
                settings.ldap_enabled
                and not settings.ldap_use_ssl
                and not settings.ldap_start_tls
            ),
        }

    # ---------------------------------------------------------- connexion

    @staticmethod
    def _server():
        if not LDAP3_AVAILABLE:
            raise LdapConfigError("ldap3 n'est pas installé")
        tls = None
        if settings.ldap_use_ssl or settings.ldap_start_tls:
            import ssl

            tls = ldap3.Tls(
                validate=ssl.CERT_REQUIRED if settings.ldap_tls_verify else ssl.CERT_NONE,
                ca_certs_file=settings.ldap_ca_cert_file or None,
            )
            if not settings.ldap_tls_verify:
                logger.warning(
                    "LDAP_TLS_VERIFY=false — le certificat de l'annuaire n'est pas "
                    "vérifié ; réservé aux environnements de test"
                )
        return ldap3.Server(
            settings.ldap_server_uri,
            use_ssl=bool(settings.ldap_use_ssl),
            get_info=ldap3.NONE,
            tls=tls,
            connect_timeout=settings.ldap_timeout_seconds,
        )

    @staticmethod
    def _connect(user_dn: Optional[str], password: Optional[str]):
        """Ouvre une connexion liée (bind). L'appelant doit la fermer."""
        if not settings.ldap_use_ssl and not settings.ldap_start_tls:
            # Un bind LDAP simple transmet le mot de passe en clair sur le
            # réseau — celui du compte de service comme celui de chaque
            # utilisateur qui se connecte.
            logger.warning(
                "Bind LDAP en clair vers %s : ni LDAPS ni START TLS. "
                "Les identifiants transitent sans chiffrement.",
                settings.ldap_server_uri,
            )
        conn = ldap3.Connection(
            LdapService._server(),
            user=user_dn,
            password=password,
            auto_bind=False,
            raise_exceptions=False,
            receive_timeout=settings.ldap_timeout_seconds,
            # Active Directory renvoie des référencements que ldap3 suivrait
            # sur un bind anonyme : la recherche paraîtrait alors vide.
            auto_referrals=bool(settings.ldap_follow_referrals),
        )
        if settings.ldap_start_tls and not settings.ldap_use_ssl:
            if not conn.start_tls():
                raise LDAPException(f"START TLS refusé : {conn.result}")
        if not conn.bind():
            raise LDAPException(f"Bind refusé : {conn.result}")
        return conn

    # -------------------------------------------------------- résolution

    @staticmethod
    def _default_role() -> UserRole:
        try:
            return UserRole(str(settings.ldap_default_role).strip().lower())
        except ValueError:
            logger.error(
                "LDAP_DEFAULT_ROLE invalide (%r) — repli sur read_only",
                settings.ldap_default_role,
            )
            return UserRole.READ_ONLY

    @staticmethod
    def resolve_role(
        groups: List[str],
        username: str = "",
        db=None,
    ) -> UserRole:
        """Détermine le rôle Sentinel d'une identité d'annuaire.

        Ordre de résolution, du plus spécifique au plus général :

        1. **Mappings applicatifs en base** (`ldap_role_mappings`), triés par
           `priority` croissante puis par type — une exception nominative
           l'emporte sur un groupe à priorité égale. C'est le mode retenu :
           la correspondance appartient à cette application, l'annuaire n'a
           rien à déclarer et le compte de service reste en lecture seule.
        2. **Correspondance d'environnement** (`LDAP_ROLE_MAPPING`), pour
           amorcer un déploiement avant toute écriture en base.
        3. **Rôle par défaut**, volontairement le moins privilégié.

        Le tri explicite évite qu'un utilisateur membre de plusieurs groupes
        mappés obtienne un rôle dépendant de l'ordre de lecture de l'annuaire.
        """
        lowered_groups = {g.strip().lower() for g in groups if g}
        lowered_user = (username or "").strip().lower()

        if db is not None:
            try:
                from src.models import LdapRoleMapping

                rows = (
                    db.query(LdapRoleMapping)
                    .filter(LdapRoleMapping.enabled.is_(True))
                    .order_by(
                        LdapRoleMapping.priority.asc(),
                        LdapRoleMapping.kind.asc(),  # 'group' < 'user'
                        LdapRoleMapping.value.asc(),
                    )
                    .all()
                )
                # À priorité égale, une attribution nominative prime sur un
                # groupe : c'est le sens d'une exception.
                for row in sorted(rows, key=lambda r: (r.priority, r.kind != "user")):
                    value = (row.value or "").strip().lower()
                    if not value:
                        continue
                    if row.kind == "user" and value == lowered_user:
                        return row.role
                    if row.kind == "group" and value in lowered_groups:
                        return row.role
            except Exception:  # noqa: BLE001 — une erreur de lecture ne doit
                # jamais élever les droits ; on retombe sur les règles suivantes.
                logger.exception(
                    "Lecture des correspondances de rôles impossible — "
                    "repli sur la configuration d'environnement"
                )

        mapping = _parse_role_mapping(settings.ldap_role_mapping)
        for group_dn, role in mapping.items():
            if group_dn in lowered_groups:
                return role

        return LdapService._default_role()

    @staticmethod
    def _role_from_groups(groups: List[str]) -> UserRole:
        """Conservé pour les appels sans session de base."""
        return LdapService.resolve_role(groups)

    @staticmethod
    def _entry_value(entry, attribute: str) -> str:
        try:
            raw = entry[attribute].value
        except Exception:  # noqa: BLE001 — attribut absent selon l'annuaire
            return ""
        if isinstance(raw, (list, tuple)):
            return str(raw[0]) if raw else ""
        return str(raw or "")

    @staticmethod
    def _login_filters(identifier: str) -> list:
        """Filtres de recherche à essayer, dans l'ordre, pour un identifiant saisi.

        Le filtre configuré reste prioritaire et inchangé. Le repli sur
        l'attribut mail n'est tenté que pour un identifiant en forme d'adresse,
        afin qu'un agent d'exploitation puisse se connecter avec l'adresse
        qu'il connaît sans que l'administrateur ait à réécrire son filtre.
        """
        escaped = _escape(identifier)
        filters = [settings.ldap_user_filter.replace("{username}", escaped)]
        if (
            settings.ldap_allow_email_login
            and "@" in identifier
            and settings.ldap_attr_email
            and settings.ldap_user_email_filter
        ):
            email_filter = (
                settings.ldap_user_email_filter
                .replace("{email_attr}", settings.ldap_attr_email)
                .replace("{username}", escaped)
            )
            if email_filter not in filters:
                filters.append(email_filter)
        return filters

    @staticmethod
    def find_user(username: str, db=None) -> Optional[LdapProfile]:
        """Recherche un utilisateur avec le compte de service, sans l'authentifier."""
        if not LdapService.is_enabled():
            return None
        conn = None
        try:
            conn = LdapService._connect(
                settings.ldap_bind_dn or None, settings.ldap_bind_password or None
            )
            search_filters = LdapService._login_filters(username)
            extra_attributes = {
                "employee_id": settings.ldap_attr_employee_id,
                "department": settings.ldap_attr_department,
                "phone": settings.ldap_attr_phone,
                "office": settings.ldap_attr_office,
                "title": settings.ldap_attr_title,
            }
            attributes = [
                settings.ldap_attr_username,
                settings.ldap_attr_email,
                settings.ldap_attr_display_name,
                settings.ldap_attr_member_of,
                *[a for a in extra_attributes.values() if a],
            ]
            entry = None
            for search_filter in search_filters:
                conn.search(
                    search_base=settings.ldap_user_search_base,
                    search_filter=search_filter,
                    search_scope=ldap3.SUBTREE,
                    attributes=attributes,
                    time_limit=settings.ldap_timeout_seconds,
                )
                if not conn.entries:
                    continue
                if len(conn.entries) > 1:
                    # Un filtre trop large authentifierait un homonyme : on refuse.
                    logger.error(
                        "Filtre LDAP ambigu : %d entrées pour %s — authentification refusée",
                        len(conn.entries),
                        username,
                    )
                    return None
                entry = conn.entries[0]
                break

            if entry is None:
                logger.info("Utilisateur %s introuvable dans l'annuaire", username)
                return None
            groups_raw = []
            try:
                value = entry[settings.ldap_attr_member_of].value
                groups_raw = list(value) if isinstance(value, (list, tuple)) else ([value] if value else [])
            except Exception:  # noqa: BLE001
                groups_raw = []
            groups = [str(g) for g in groups_raw]

            collected = {}
            for field_name, attr in extra_attributes.items():
                if not attr:
                    continue
                value = LdapService._entry_value(entry, attr)
                if value:
                    collected[field_name] = value

            return LdapProfile(
                username=LdapService._entry_value(entry, settings.ldap_attr_username) or username,
                email=LdapService._entry_value(entry, settings.ldap_attr_email),
                display_name=LdapService._entry_value(entry, settings.ldap_attr_display_name),
                dn=str(entry.entry_dn),
                groups=groups,
                role=LdapService.resolve_role(groups, username=username, db=db),
                attributes=collected,
            )
        except (LDAPException, LdapConfigError) as exc:
            logger.error("Recherche LDAP en échec pour %s : %s", username, exc)
            return None
        except Exception:  # noqa: BLE001
            logger.exception("Erreur inattendue pendant la recherche LDAP")
            return None
        finally:
            _safe_unbind(conn)

    @staticmethod
    def authenticate(username: str, password: str, db=None) -> Optional[LdapProfile]:
        """Vérifie les identifiants par un bind, puis retourne le profil.

        Retourne None sur tout échec — identifiants erronés comme annuaire
        injoignable. L'appelant se replie alors sur l'authentification locale.
        """
        if not LdapService.is_enabled():
            return None
        # Un bind avec mot de passe vide réussit sur certains annuaires (bind
        # anonyme) : cela authentifierait n'importe qui.
        if not username or not password:
            return None

        profile = LdapService.find_user(username, db=db)
        if profile is None:
            return None

        conn = None
        try:
            conn = LdapService._connect(profile.dn, password)
            logger.info("Authentification annuaire réussie pour %s", username)
            return profile
        except LDAPException as exc:
            logger.info("Authentification annuaire refusée pour %s : %s", username, exc)
            return None
        except Exception:  # noqa: BLE001
            logger.exception("Erreur inattendue pendant le bind LDAP")
            return None
        finally:
            _safe_unbind(conn)

    @staticmethod
    def test_connection() -> Dict[str, Any]:
        """Diagnostic pour l'écran Paramètres : joignabilité et compte de service."""
        if not settings.ldap_enabled:
            return {"ok": False, "stage": "disabled", "detail": "LDAP désactivé"}
        if not LDAP3_AVAILABLE:
            return {
                "ok": False,
                "stage": "library",
                "detail": "Paquet ldap3 absent (pip install ldap3)",
            }
        if not settings.ldap_server_uri or not settings.ldap_user_search_base:
            return {
                "ok": False,
                "stage": "config",
                "detail": "LDAP_SERVER_URI ou LDAP_USER_SEARCH_BASE non renseigné",
            }
        conn = None
        try:
            conn = LdapService._connect(
                settings.ldap_bind_dn or None, settings.ldap_bind_password or None
            )
            conn.search(
                search_base=settings.ldap_user_search_base,
                search_filter="(objectClass=*)",
                search_scope=ldap3.BASE,
                attributes=[],
                time_limit=settings.ldap_timeout_seconds,
            )
            return {
                "ok": True,
                "stage": "bind",
                "detail": f"Connexion et recherche réussies sur {settings.ldap_server_uri}",
            }
        except (LDAPException, LdapConfigError) as exc:
            return {"ok": False, "stage": "bind", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.exception("Test LDAP en échec")
            return {"ok": False, "stage": "unexpected", "detail": str(exc)}
        finally:
            _safe_unbind(conn)


def _escape(value: str) -> str:
    """Échappe les métacaractères d'un filtre LDAP (RFC 4515).

    Sans cela, un nom d'utilisateur tel que `*` transformerait le filtre en
    joker et ferait remonter le premier compte de l'annuaire.
    """
    out = []
    for ch in value:
        if ch == "\\":
            out.append("\\5c")
        elif ch == "*":
            out.append("\\2a")
        elif ch == "(":
            out.append("\\28")
        elif ch == ")":
            out.append("\\29")
        elif ch == "\0":
            out.append("\\00")
        elif ch == "/":
            out.append("\\2f")
        else:
            out.append(ch)
    return "".join(out)


def _safe_unbind(conn) -> None:
    if conn is None:
        return
    try:
        conn.unbind()
    except Exception:  # noqa: BLE001
        logger.debug("Fermeture de la connexion LDAP impossible", exc_info=True)
