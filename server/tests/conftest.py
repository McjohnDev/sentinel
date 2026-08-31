"""Configuration commune aux tests serveur.

Doit s'exécuter avant tout import de `src.*` : les variables sont lues à la
construction de `Settings`.
"""

import os

# Base de test isolée.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

# L'ordonnanceur sonde Redis, VictoriaMetrics et Loki, qui ne tournent pas
# pendant les tests unitaires : chaque TestClient attendait alors l'expiration
# des délais réseau. Les jobs sont testés directement dans test_scheduler.py.
os.environ.setdefault("SCHEDULER_ENABLED", "false")
os.environ.setdefault("RATE_LIMIT_DISABLED", "true")

# Pas de jeton d'amorçage implicite : les tests qui en ont besoin le posent
# eux-mêmes (voir test_enrollment_security.py).
os.environ.pop("BOOTSTRAP_ENROLLMENT_TOKEN", None)

# L'annuaire doit rester neutralisé pendant les tests, quelle que soit la
# configuration locale. `Settings` lit `.env` relativement au répertoire de
# travail : lancer pytest depuis `server/` chargerait sinon la configuration
# réelle (voire une adresse d'annuaire d'entreprise) et rendrait les
# assertions dépendantes de la machine.
os.environ["LDAP_ENABLED"] = "false"
os.environ.pop("LDAP_SERVER_URI", None)
os.environ.pop("LDAP_BIND_PASSWORD", None)
os.environ["LDAP_ROLE_MAPPING"] = "{}"
os.environ["LDAP_DEFAULT_ROLE"] = "read_only"
