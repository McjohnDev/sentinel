"""Mesures système du battement."""

from __future__ import annotations

import metrics
from metrics import _clamp_percent, collect


def test_percentages_are_clamped_into_range():
    # La plateforme valide 0..100 et répond 422 hors bornes. psutil peut
    # rendre brièvement plus de 100 % : sans garde-fou, un pic de mesure fait
    # rejeter le battement et l'hôte bascule « hors ligne » pour une raison
    # purement arithmétique.
    assert _clamp_percent(137.4) == 100.0
    assert _clamp_percent(-3.0) == 0.0
    assert _clamp_percent(42.5) == 42.5
    assert _clamp_percent(float("nan")) == 0.0


def test_a_sample_of_this_host_satisfies_the_platform_constraints():
    sample = collect()
    assert 0 <= sample.cpu_percent <= 100
    assert 0 <= sample.ram_percent <= 100
    assert 0 <= sample.disk_percent <= 100
    assert sample.cpu_cores >= 1          # la plateforme exige >= 1
    assert sample.uptime_seconds >= 0     # et refuse un uptime négatif


def test_the_payload_carries_exactly_the_required_keys():
    payload = collect().as_payload()
    assert set(payload) == {
        "cpu_percent", "cpu_cores", "ram_percent", "ram_total_gb", "ram_used_gb",
        "ram_free_gb", "disk_percent", "disk_total_gb", "disk_used_gb",
        "disk_free_gb", "uptime_seconds",
    }


def test_a_missing_psutil_is_reported_not_faked(monkeypatch):
    # Mieux vaut refuser de battre que d'inventer des mesures : un hôte qui
    # rapporte 0 % de charge se lit comme une machine saine et silencieuse.
    monkeypatch.setattr(metrics, "psutil", None)
    try:
        collect()
    except metrics.MetricsUnavailable as exc:
        assert "psutil" in str(exc)
    else:
        raise AssertionError("une mesure impossible doit lever MetricsUnavailable")
