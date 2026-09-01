"""Boucle de battement : cadence, recul après échec, reprise (point 5)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import requests

import heartbeat as hb
import runner
import session as session_module
from config import AgentConfig
from enrollment import Credentials, write_credentials
from facts import HostFacts
from metrics import MetricsUnavailable, SystemSample

CONFIG = AgentConfig(
    server_url="https://plateforme.cbc:8443",
    enrollment_token="",
    tls_verify=True,
    machine_type="server",
    timeout_seconds=5,
)
CREDS = Credentials(agent_id="A3F09C", auth_key="cle-secrete")
HOST = HostFacts("web-01", "Linux", "5.15", "10.0.0.12", 4, 15.5, 200.0, {})
SAMPLE = SystemSample(1.0, 4, 2.0, 15.5, 6.0, 9.0, 3.0, 200.0, 120.0, 80.0, 10)


class _Response:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("pas de JSON")
        return self._payload


def _ok(**echo):
    body = {"agent_id": "A3F09C"}
    body.update(echo)
    return _Response(200, {"status": "success", "tasks": [], "config": None, "echo": body})


class _Scripted:
    """Rend une réponse (ou lève) par appel, dans l'ordre donné."""

    def __init__(self, steps):
        self.steps = list(steps)
        self.calls = 0

    def post(self, url, json=None, headers=None, timeout=None, verify=None):
        step = self.steps[min(self.calls, len(self.steps) - 1)]
        self.calls += 1
        if isinstance(step, Exception):
            raise step
        return step


class _Clock:
    def __init__(self, start=None):
        self.now = start or datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc)

    def __call__(self):
        self.now = self.now + timedelta(seconds=1)
        return self.now


def _run(steps, *, max_beats, sleeps=None, sampler=None):
    recorded = sleeps if sleeps is not None else []
    return (
        runner.run(
            CONFIG,
            CREDS,
            HOST,
            interval_seconds=30.0,
            max_beats=max_beats,
            session=_Scripted(steps),
            sleeper=recorded.append,
            clock=_Clock(),
            sampler=sampler or (lambda: SAMPLE),
            inventory_every=0,
        ),
        recorded,
    )


def test_a_healthy_run_beats_at_the_nominal_interval():
    outcome, sleeps = _run([_ok()], max_beats=3)
    assert outcome.beats_sent == 3
    assert outcome.failures == 0
    # Deux attentes pour trois battements : on ne dort pas après le dernier.
    assert sleeps == [30.0, 30.0]


def test_failures_back_off_instead_of_hammering():
    # Un parc entier qui réessaie à la seconde après une coupure suffit à
    # empêcher la plateforme de redémarrer.
    outcome, sleeps = _run([requests.exceptions.ConnectionError("coupure")], max_beats=4)
    assert outcome.beats_sent == 0
    assert outcome.failures == 4
    assert sleeps == [5.0, 10.0, 20.0]


def test_backoff_is_capped():
    outcome, sleeps = _run([requests.exceptions.ConnectionError("x")], max_beats=12)
    assert max(sleeps) <= runner.BACKOFF_MAX
    assert sleeps[-1] == runner.BACKOFF_MAX


def test_the_nominal_cadence_returns_immediately_after_a_recovery():
    # Rester en attente longue après la reprise laisserait l'hôte au bord du
    # seuil de bascule hors ligne.
    steps = [
        requests.exceptions.ConnectionError("coupure"),
        requests.exceptions.ConnectionError("coupure"),
        _ok(resumed_after_outage=True, previous_gap_seconds=600),
        _ok(),
    ]
    outcome, sleeps = _run(steps, max_beats=4)
    assert outcome.beats_sent == 2
    assert outcome.failures == 2
    assert outcome.resumed == 1
    assert sleeps == [5.0, 10.0, 30.0]


def test_identity_loss_stops_the_loop_instead_of_re_enrolling():
    # Se réenrôler seul consommerait un jeton et, si la plateforme a révoqué
    # cet hôte, le ferait rentrer par la fenêtre.
    outcome, _ = _run([_Response(401, {"detail": "Agent inconnu"})], max_beats=5)
    assert outcome.beats_sent == 0
    assert outcome.failures == 1
    assert "reconnaît plus" in outcome.last_error


def test_a_server_error_is_retried_not_fatal():
    outcome, _ = _run([_Response(500, {"detail": "boom"}), _ok()], max_beats=2)
    assert outcome.failures == 1
    assert outcome.beats_sent == 1


def test_unmeasurable_host_stops_rather_than_spinning():
    def broken():
        raise MetricsUnavailable("psutil absent")

    outcome, sleeps = _run([_ok()], max_beats=5, sampler=broken)
    assert outcome.beats_sent == 0
    assert sleeps == []
    assert "psutil" in outcome.last_error


def test_an_adopted_identifier_is_persisted():
    write_credentials(CREDS)
    outcome, _ = _run([_ok(agent_id="B7C120")], max_beats=1)
    assert outcome.credentials.agent_id == "B7C120"
    from enrollment import read_credentials

    # Persisté : sinon l'adoption serait perdue au prochain démarrage et
    # l'agent repartirait sur un identifiant que la plateforme ignore.
    assert read_credentials().agent_id == "B7C120"


# --------------------------------------------------------- état de liaison


def test_the_host_records_a_successful_link():
    _run([_ok()], max_beats=1)
    state = session_module.read_state()
    assert state.connected is True
    assert state.last_success_at
    assert state.consecutive_failures == 0


def test_failures_are_counted_for_the_operator():
    _run([requests.exceptions.ConnectionError("coupure")], max_beats=3)
    state = session_module.read_state()
    assert state.connected is False
    assert state.consecutive_failures == 3
    assert "injoignable" in state.last_error


def test_the_last_success_survives_the_outage():
    # « Hors ligne depuis quand ? » est la question posée devant la machine :
    # remettre cette date à zéro à chaque échec effacerait la réponse.
    _run([_ok()], max_beats=1)
    first = session_module.read_state().last_success_at
    assert first

    _run([requests.exceptions.ConnectionError("coupure")], max_beats=2)
    after = session_module.read_state()
    assert after.connected is False
    assert after.last_success_at == first


def test_a_recovery_clears_the_failure_count():
    _run([requests.exceptions.ConnectionError("coupure")], max_beats=2)
    assert session_module.read_state().consecutive_failures == 2
    _run([_ok()], max_beats=1)
    state = session_module.read_state()
    assert state.consecutive_failures == 0
    assert state.last_error is None


# ------------------------------------------- faits d'hote rafraichis (revue)


def test_host_facts_are_re_read_on_every_beat():
    """Les relever une seule fois au lancement fige l'inventaire.

    Un agent installe en service tourne des mois. Un poste en DHCP change
    d'adresse et la plateforme continuerait d'afficher l'ancienne jusqu'au
    prochain redemarrage de l'agent.
    """
    seen = []
    versions = iter(["5.15.0", "5.15.1", "6.1.0"])

    def provider(previous):
        return HostFacts(
            previous.hostname, previous.os, next(versions), "10.0.0.99",
            previous.cpu_cores, previous.ram_total_gb, previous.disk_total_gb, {},
        )

    class _Capture:
        def post(self, url, json=None, headers=None, timeout=None, verify=None):
            seen.append(json["os_version"])
            return _ok()

    runner.run(
        CONFIG, CREDS, HOST, interval_seconds=30.0, max_beats=3,
        session=_Capture(), sleeper=lambda _s: None, clock=_Clock(),
        sampler=lambda: SAMPLE, host_provider=provider, inventory_every=0,
    )

    assert seen == ["5.15.0", "5.15.1", "6.1.0"]


def test_an_ip_change_reaches_the_platform():
    sent = []

    def provider(previous):
        return HostFacts(
            previous.hostname, previous.os, previous.os_version, "192.168.5.5",
            previous.cpu_cores, previous.ram_total_gb, previous.disk_total_gb, {},
        )

    class _Capture:
        def post(self, url, json=None, headers=None, timeout=None, verify=None):
            sent.append(json.get("ip_address"))
            return _ok()

    runner.run(
        CONFIG, CREDS, HOST, max_beats=1, session=_Capture(),
        sleeper=lambda _s: None, clock=_Clock(), sampler=lambda: SAMPLE,
        host_provider=provider, inventory_every=0,
    )
    assert sent == ["192.168.5.5"]


def test_a_failed_host_reading_keeps_the_previous_facts():
    # Un releve rate ne doit pas rompre la liaison : mieux vaut des faits
    # legerement anciens qu'un hote qui cesse de donner signe de vie.
    sent = []

    def provider(_previous):
        raise OSError("interface indisponible")

    class _Capture:
        def post(self, url, json=None, headers=None, timeout=None, verify=None):
            sent.append(json["hostname"])
            return _ok()

    outcome = runner.run(
        CONFIG, CREDS, HOST, max_beats=2, session=_Capture(),
        sleeper=lambda _s: None, clock=_Clock(), sampler=lambda: SAMPLE,
        host_provider=provider, inventory_every=0,
    )
    assert outcome.beats_sent == 2
    assert sent == ["web-01", "web-01"]


def test_an_unmeasurable_host_is_recorded_for_the_operator():
    # Sinon `status` affiche une liaison etablie alors que l'agent s'est
    # arrete faute de pouvoir mesurer.
    def broken():
        raise MetricsUnavailable("psutil absent")

    _run([_ok()], max_beats=2, sampler=broken)
    state = session_module.read_state()
    assert state.connected is False
    assert "psutil" in state.last_error


def test_the_observed_vlan_rides_on_the_beat():
    sent = []
    tagged = HostFacts("web-01", "Linux", "5.15", "10.0.0.12", 4, 15.5, 200.0, {}, "100,250")

    class _Capture:
        def post(self, url, json=None, headers=None, timeout=None, verify=None):
            sent.append(json.get("vlan_observed"))
            return _ok()

    runner.run(
        CONFIG, CREDS, tagged, max_beats=1, session=_Capture(),
        sleeper=lambda _s: None, clock=_Clock(), sampler=lambda: SAMPLE,
        host_provider=lambda previous: previous, inventory_every=0,
    )
    assert sent == ["100,250"]


def test_an_untagged_host_omits_the_vlan_rather_than_sending_empty():
    sent = []

    class _Capture:
        def post(self, url, json=None, headers=None, timeout=None, verify=None):
            sent.append("vlan_observed" in json)
            return _ok()

    runner.run(
        CONFIG, CREDS, HOST, max_beats=1, session=_Capture(),
        sleeper=lambda _s: None, clock=_Clock(), sampler=lambda: SAMPLE,
        host_provider=lambda previous: previous, inventory_every=0,
    )
    assert sent == [False]


# ------------------------------------------------- inventaire (points 7 et +)


def test_the_inventory_goes_out_on_the_first_successful_beat(monkeypatch):
    """Sans cela, l'exploitant attendrait des heures avant de pouvoir choisir
    un service dans la liste réelle de l'hôte."""
    import inventory as inventory_module

    pushed = []
    monkeypatch.setattr(inventory_module, "collect", lambda: inventory_module.Inventory())
    monkeypatch.setattr(inventory_module, "push", lambda *a, **k: pushed.append(1))

    outcome = runner.run(
        CONFIG, CREDS, HOST, max_beats=1, session=_Scripted([_ok()]),
        sleeper=lambda _s: None, clock=_Clock(), sampler=lambda: SAMPLE,
        host_provider=lambda p: p, inventory_every=5,
    )
    assert len(pushed) == 1
    assert outcome.inventories_sent == 1


def test_the_inventory_is_not_sent_on_every_beat(monkeypatch):
    # Le relevé interroge la base de registre ou le gestionnaire de paquets :
    # le refaire à chaque battement coûterait bien plus qu'il n'apprend.
    import inventory as inventory_module

    pushed = []
    monkeypatch.setattr(inventory_module, "collect", lambda: inventory_module.Inventory())
    monkeypatch.setattr(inventory_module, "push", lambda *a, **k: pushed.append(1))

    runner.run(
        CONFIG, CREDS, HOST, max_beats=4, session=_Scripted([_ok()]),
        sleeper=lambda _s: None, clock=_Clock(), sampler=lambda: SAMPLE,
        host_provider=lambda p: p, inventory_every=3,
    )
    # Battements 1 et 4 seulement.
    assert len(pushed) == 2


def test_a_failed_inventory_does_not_break_the_beat(monkeypatch):
    # Retirer l'hôte du parc pour une donnée d'appoint serait disproportionné.
    import inventory as inventory_module

    def broken():
        raise RuntimeError("registre inaccessible")

    monkeypatch.setattr(inventory_module, "collect", broken)

    outcome = runner.run(
        CONFIG, CREDS, HOST, max_beats=2, session=_Scripted([_ok()]),
        sleeper=lambda _s: None, clock=_Clock(), sampler=lambda: SAMPLE,
        host_provider=lambda p: p, inventory_every=1,
    )
    assert outcome.beats_sent == 2
    assert outcome.inventories_sent == 0
