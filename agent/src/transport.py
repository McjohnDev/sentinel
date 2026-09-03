"""Session HTTP de l'agent.

Un seul endroit construit les sessions vers la plateforme, pour que la règle
s'applique partout : enrôlement, battement, plan, inventaire, désenrôlement.

**Pourquoi contourner le proxy d'entreprise.** `requests` lit `HTTP_PROXY` et
`HTTPS_PROXY` dans l'environnement. Sur un poste d'entreprise, l'agent
envoyait donc son battement vers le proxy sortant — alors que la plateforme de
supervision est *interne*. Le proxy répond 403, et l'hôte se déclare hors
ligne alors que la plateforme est à deux sauts de réseau. `NO_PROXY` couvrait
`127.0.0.1` mais pas l'adresse de la plateforme, si bien que le contournement
dépendait de la façon dont chaque poste avait été configuré à la main.

**Comment.** Mesuré plutôt que supposé, contre un proxy réel :

    session nue (proxy dans l'environnement)      403
    session.proxies['no_proxy'] = hôte            403   <- sans effet
    trust_env = False                             200
    proxies={'no_proxy': hôte} par requête        200
    proxies={'http': None} par requête            403

`session.proxies['no_proxy']` ne sert à rien : `merge_environment_settings`
lit `no_proxy` dans les options de la *requête*, jamais dans celles de la
session. D'où l'injection par requête ci-dessous.

`trust_env = False` marcherait aussi, mais ferait du même coup ignorer
`REQUESTS_CA_BUNDLE` — et un parc bancaire sert souvent ses certificats par
une autorité interne déclarée précisément là. On n'exempte donc que l'adresse
de la plateforme, et rien d'autre du comportement réseau de l'hôte ne change.
"""

from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse

import requests

from config import AgentConfig


def platform_host(server_url: str) -> Optional[str]:
    """Nom d'hôte de la plateforme, sans port ni schéma.

    Le port doit disparaître : `no_proxy` se compare à l'hôte seul, et y
    laisser `:8443` ferait échouer la correspondance en silence — le proxy
    reprendrait la main sans que rien ne le signale.
    """
    try:
        return urlparse(server_url).hostname or None
    except ValueError:
        return None


class PlatformSession(requests.Session):
    """Session qui joint la plateforme en direct, proxy ou non.

    L'exemption est posée sur chaque requête parce que c'est le seul endroit
    que `requests` consulte. `setdefault` : un appelant qui impose ses propres
    options de proxy reste maître de son appel.
    """

    def __init__(self, no_proxy_host: str) -> None:
        super().__init__()
        self.no_proxy_host = no_proxy_host

    def request(self, method, url, **kwargs):  # type: ignore[override]
        kwargs.setdefault("proxies", {"no_proxy": self.no_proxy_host})
        return super().request(method, url, **kwargs)


def build_session(config: AgentConfig) -> requests.Session:
    """Session à utiliser pour tout échange avec la plateforme."""
    if config.use_proxy:
        return requests.Session()

    host = platform_host(config.server_url)
    if not host:
        return requests.Session()
    return PlatformSession(host)
