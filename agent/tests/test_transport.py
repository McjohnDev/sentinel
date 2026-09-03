"""Session HTTP : contournement du proxy d'entreprise.

Sur un poste d'entreprise, `requests` lit `HTTP_PROXY` dans l'environnement.
L'agent envoyait donc son battement vers le proxy sortant alors que la
plateforme de supervision est interne : le proxy repondait 403 ou n'etait pas
joignable, et l'hote se declarait hors ligne alors que la plateforme etait a
deux sauts de reseau.
"""

from __future__ import annotations

import requests

from config import AgentConfig, load_config
from transport import PlatformSession, build_session, platform_host


def _config(url="https://plateforme.cbc:8443", **kw):
    base = dict(
        server_url=url,
        enrollment_token="",
        tls_verify=True,
        machine_type="server",
        timeout_seconds=5,
    )
    base.update(kw)
    return AgentConfig(**base)


def test_the_platform_is_exempt_from_the_proxy_by_default():
    session = build_session(_config())
    assert isinstance(session, PlatformSession)
    assert session.no_proxy_host == "plateforme.cbc"


def test_the_exemption_reaches_the_request(monkeypatch):
    # C'est le seul endroit que `requests` consulte : mesure faite contre un
    # proxy reel, `session.proxies['no_proxy']` reste sans effet. Ce test
    # verifie donc l'option telle qu'elle est reellement transmise.
    vu = {}

    def faux_request(self, method, url, **kwargs):
        vu.update(kwargs)
        return "ok"

    monkeypatch.setattr(requests.Session, "request", faux_request)
    build_session(_config()).get("https://plateforme.cbc:8443/health")
    assert vu["proxies"] == {"no_proxy": "plateforme.cbc"}


def test_a_caller_may_impose_its_own_proxies(monkeypatch):
    vu = {}

    def faux_request(self, method, url, **kwargs):
        vu.update(kwargs)
        return "ok"

    monkeypatch.setattr(requests.Session, "request", faux_request)
    session = build_session(_config())
    session.get("https://plateforme.cbc/health", proxies={"http": "http://relais:3128"})
    assert vu["proxies"] == {"http": "http://relais:3128"}


def test_an_explicit_request_keeps_the_proxy():
    session = build_session(_config(use_proxy=True))
    assert not isinstance(session, PlatformSession)


def test_the_default_is_direct_even_when_built_by_hand():
    # Tout appelant qui construit une configuration sans y penser doit
    # heriter du comportement sur.
    assert _config().use_proxy is False


def test_an_ip_address_is_exempted_like_a_name():
    session = build_session(_config(url="http://172.16.10.102:8443"))
    assert session.no_proxy_host == "172.16.10.102"


def test_the_port_is_not_part_of_the_exemption():
    # `no_proxy` se compare a l'hote, pas a l'autorite : y laisser le port
    # ferait echouer la correspondance et le proxy reprendrait la main.
    assert platform_host("https://plateforme.cbc:8443") == "plateforme.cbc"


def test_a_malformed_url_does_not_break_the_session():
    session = build_session(_config(url="http://"))
    assert session is not None


def test_the_option_is_read_from_the_file(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        'server:\n  url: "https://plateforme.cbc:8443"\n  use_proxy: true\n',
        encoding="utf-8",
    )
    assert load_config(path).use_proxy is True


def test_the_file_default_is_direct(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text('server:\n  url: "https://plateforme.cbc:8443"\n', encoding="utf-8")
    assert load_config(path).use_proxy is False
