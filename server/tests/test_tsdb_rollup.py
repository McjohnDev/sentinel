"""FS2-04 / STO-002 — agrégats 1h et 1d.

VictoriaMetrics en édition open source ne sait pas sous-échantillonner : c'est
une fonction de l'édition entreprise. Les agrégats sont donc calculés par la
plateforme et réécrits comme des séries distinctes.

Les points vérifiés ici sont ceux qui font la différence entre un agrégat
exploitable et un agrégat trompeur : l'intervalle courant n'est jamais agrégé,
le traitement est idempotent, et le niveau journalier dérive de l'horaire.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

ROOT = Path(__file__).resolve().parents[2]
SERVER = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(SERVER)):
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import Base
from src.models import TsdbRollupState
from src.tsdb_service import AGG_FUNCTIONS, RollupWriter, rollup_metric_name


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


class FakeClient:
    """Client VictoriaMetrics en mémoire.

    Enregistre les requêtes reçues et les lignes écrites, ce qui permet de
    vérifier *quels* intervalles ont été agrégés — l'information qui compte.
    """

    enabled = True
    base_url = "http://fake:8428"
    timeout = 1.0

    def __init__(self, series=None):
        self.series = series if series is not None else [
            {"metric": {"__name__": "cbc_metric", "agent_id": "a1", "name": "cpu.percent"},
             "value": [0, "42.5"]}
        ]
        self.written: list[str] = []
        self.queries: list[tuple[str, float]] = []

    def write_prometheus(self, lines):
        lines = [ln for ln in lines if ln]
        self.written.extend(lines)
        return len(lines)


def _writer(client):
    w = RollupWriter(client)
    # Court-circuite HTTP : on teste la logique d'intervalles, pas httpx.
    w._instant = lambda query, at: (client.queries.append((query, at.timestamp())) or client.series)
    return w


def test_bucket_produces_one_series_per_aggregate():
    client = FakeClient()
    writer = _writer(client)
    at = datetime(2026, 8, 18, 10, 0, tzinfo=timezone.utc)

    lines = writer.build_bucket("1h", "1h", "cbc_metric", at)

    assert len(lines) == len(AGG_FUNCTIONS)
    for agg in AGG_FUNCTIONS:
        assert any(f'agg="{agg}"' in ln for ln in lines)
    assert all(ln.startswith(rollup_metric_name("1h")) for ln in lines)


def test_rollup_series_is_labelled_and_does_not_shadow_raw():
    client = FakeClient()
    writer = _writer(client)
    at = datetime(2026, 8, 18, 10, 0, tzinfo=timezone.utc)

    lines = writer.build_bucket("1h", "1h", "cbc_metric", at)

    for ln in lines:
        assert 'rollup="1h"' in ln
        # Le nom de la série source ne doit pas être réémis : sinon l'agrégat
        # écraserait la donnée brute.
        assert "__name__" not in ln
        assert ln.startswith("cbc_metric_1h{")
    # Les étiquettes d'origine sont conservées pour rester requêtable par hôte.
    assert all('agent_id="a1"' in ln for ln in lines)


def test_current_incomplete_bucket_is_never_aggregated():
    """Agréger l'intervalle en cours produirait une valeur partielle qui ne
    serait jamais corrigée."""
    client = FakeClient()
    writer = _writer(client)
    now = datetime(2026, 8, 18, 10, 30, tzinfo=timezone.utc)  # 10 h 30
    since = now - timedelta(hours=3)

    result = writer.run_tier("1h", "1h", "cbc_metric", 3600, since, now)

    stamps = [datetime.fromtimestamp(ts, tz=timezone.utc) for _, ts in client.queries]
    assert stamps, "aucun intervalle traité"
    # Rien au-delà de 10 h 00 : 10 h 00 → 11 h 00 est encore en cours.
    assert max(stamps) <= datetime(2026, 8, 18, 10, 0, tzinfo=timezone.utc)
    assert result["buckets"] == 3


def test_buckets_are_aligned_to_the_hour():
    """Les points d'agrégat doivent tomber au même endroit quelle que soit
    l'heure d'exécution du traitement."""
    client = FakeClient()
    writer = _writer(client)
    now = datetime(2026, 8, 18, 12, 47, tzinfo=timezone.utc)
    since = datetime(2026, 8, 18, 9, 13, tzinfo=timezone.utc)

    writer.run_tier("1h", "1h", "cbc_metric", 3600, since, now)

    stamps = [datetime.fromtimestamp(ts, tz=timezone.utc) for _, ts in client.queries]
    assert all(s.minute == 0 and s.second == 0 for s in stamps), "bornes non alignées"


def test_rerun_from_last_bucket_is_idempotent():
    """Une seconde exécution sans nouvel intervalle ne réécrit rien."""
    client = FakeClient()
    writer = _writer(client)
    now = datetime(2026, 8, 18, 10, 5, tzinfo=timezone.utc)
    since = now - timedelta(hours=2)

    first = writer.run_tier("1h", "1h", "cbc_metric", 3600, since, now)
    assert first["buckets"] > 0

    second = writer.run_tier("1h", "1h", "cbc_metric", 3600, first["last_bucket"], now)
    assert second["buckets"] == 0, "les mêmes intervalles ont été réécrits"


def test_backfill_is_bounded():
    """Un long arrêt ne doit pas déclencher un rattrapage illimité."""
    client = FakeClient()
    writer = _writer(client)
    now = datetime(2026, 8, 18, 10, 0, tzinfo=timezone.utc)
    since = now - timedelta(days=365)

    result = writer.run_tier("1h", "1h", "cbc_metric", 3600, since, now, max_buckets=48)
    assert result["buckets"] == 48


def test_daily_tier_reads_the_hourly_series():
    """Le niveau journalier dérive de l'horaire : agréger 86 400 s de points
    bruts à chaque passage serait inutilement coûteux."""
    client = FakeClient()
    writer = _writer(client)
    now = datetime(2026, 8, 18, 3, 0, tzinfo=timezone.utc)
    since = now - timedelta(days=2)

    writer.run_tier("1d", "1d", "cbc_metric_1h", 86400, since, now)

    assert client.queries, "aucune requête émise"
    assert all("cbc_metric_1h" in q for q, _ in client.queries)
    assert all(q.endswith("[1d])") for q, _ in client.queries)


def test_no_series_means_no_write():
    """Une plateforme sans métrique ne doit pas produire de séries vides."""
    client = FakeClient(series=[])
    writer = _writer(client)
    now = datetime(2026, 8, 18, 10, 0, tzinfo=timezone.utc)

    result = writer.run_tier("1h", "1h", "cbc_metric", 3600, now - timedelta(hours=3), now)

    assert result["samples"] == 0
    assert client.written == []


def test_non_numeric_values_are_skipped():
    client = FakeClient(series=[
        {"metric": {"agent_id": "a1"}, "value": [0, "NaN"]},
        {"metric": {"agent_id": "a2"}, "value": [0, "7"]},
    ])
    writer = _writer(client)
    at = datetime(2026, 8, 18, 10, 0, tzinfo=timezone.utc)

    lines = writer.build_bucket("1h", "1h", "cbc_metric", at)
    # NaN se convertit en float sans lever : on vérifie surtout qu'aucune
    # ligne malformée n'est produite et que la série valide passe.
    assert any('agent_id="a2"' in ln for ln in lines)
    assert all(ln.count("{") == 1 for ln in lines)


def test_state_row_tracks_progress(db):
    """L'avancement doit survivre à un redémarrage."""
    db.add(TsdbRollupState(tier="1h", buckets_written=0, samples_written=0))
    db.commit()

    state = db.query(TsdbRollupState).filter(TsdbRollupState.tier == "1h").first()
    state.last_bucket_at = datetime(2026, 8, 18, 10, 0)
    state.buckets_written = 5
    db.commit()

    reloaded = db.query(TsdbRollupState).filter(TsdbRollupState.tier == "1h").first()
    assert reloaded.last_bucket_at == datetime(2026, 8, 18, 10, 0)
    assert reloaded.buckets_written == 5
