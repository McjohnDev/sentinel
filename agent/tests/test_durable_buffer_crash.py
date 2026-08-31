"""AGT-005 / FS1-04 — « zéro perte après panne de la plateforme ».

Régression couverte : `drain()` lisait la file puis **supprimait le fichier
avant toute tentative d'envoi**, et ne réécrivait que les échecs à la fin de la
boucle. Un arrêt brutal au milieu du rejeu — coupure, redémarrage, arrêt de
service — perdait donc tout le lot déjà retiré du disque : exactement la perte
que cette story existe pour empêcher.

Le contrat vérifié ici est le prélèvement en deux temps : `checkout()` renomme,
`commit()` acquitte, et un lot resté « en vol » est réintégré au démarrage
suivant.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

AGENT_SRC = Path(__file__).resolve().parents[1] / "src"
ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(AGENT_SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest

from durable_buffer import DurableBuffer


def _buf(tmp_path, **kw):
    return DurableBuffer(tmp_path / "q.jsonl", **kw)


# ------------------------------------------------------- perte sur arrêt brutal


def test_records_survive_a_crash_during_replay(tmp_path):
    """Le cœur de la régression.

    On prélève un lot, on n'acquitte pas (l'agent est tué), puis un nouveau
    processus démarre. Aucun enregistrement ne doit avoir disparu.
    """
    buf = _buf(tmp_path)
    for i in range(5):
        buf.enqueue("heartbeat", {"i": i})

    checked_out = buf.checkout()
    assert len(checked_out) == 5

    # Arrêt brutal : pas de commit. Un nouveau processus reprend le fichier.
    restarted = _buf(tmp_path)

    assert len(restarted) == 5, "le lot prélevé a été perdu à l'arrêt"
    assert [r["payload"]["i"] for r in restarted.peek()] == [0, 1, 2, 3, 4]


def test_partial_send_then_crash_loses_nothing(tmp_path):
    """Deux envois réussis, puis arrêt : les trois restants doivent subsister."""
    buf = _buf(tmp_path)
    for i in range(5):
        buf.enqueue("heartbeat", {"i": i})

    records = buf.checkout()
    sent = records[:2]  # confirmés par le serveur
    assert len(sent) == 2
    # …puis le processus meurt avant tout commit.

    restarted = _buf(tmp_path)
    survived = [r["payload"]["i"] for r in restarted.peek()]
    # Un doublon est acceptable, un trou ne l'est pas.
    assert set(range(2, 5)).issubset(set(survived)), "des enregistrements non envoyés ont disparu"


def test_commit_clears_only_what_succeeded(tmp_path):
    buf = _buf(tmp_path)
    for i in range(4):
        buf.enqueue("metrics", {"i": i})

    records = buf.checkout()
    failed = [records[1], records[3]]
    buf.commit(failed=failed)

    remaining = [r["payload"]["i"] for r in buf.peek()]
    assert remaining == [1, 3]


def test_commit_without_failures_empties_the_queue(tmp_path):
    buf = _buf(tmp_path)
    buf.enqueue("heartbeat", {"i": 0})
    buf.checkout()
    buf.commit()
    assert len(buf) == 0
    assert not buf.inflight_path.exists()


def test_replay_order_is_preserved_across_recovery(tmp_path):
    """Les enregistrements en vol sont les plus anciens : ils doivent repasser
    devant ceux accumulés depuis."""
    buf = _buf(tmp_path)
    buf.enqueue("heartbeat", {"i": 1})
    buf.enqueue("heartbeat", {"i": 2})
    buf.checkout()  # 1 et 2 partent en vol

    # Le collecteur continue de tourner pendant la panne.
    buf.enqueue("heartbeat", {"i": 3})

    restarted = _buf(tmp_path)
    assert [r["payload"]["i"] for r in restarted.peek()] == [1, 2, 3]


def test_double_checkout_returns_the_same_batch(tmp_path):
    """Un second prélèvement sans acquittement ne doit pas écraser le lot."""
    buf = _buf(tmp_path)
    buf.enqueue("heartbeat", {"i": 1})

    first = buf.checkout()
    second = buf.checkout()
    assert first == second
    assert len(buf) == 1


def test_new_records_during_replay_are_not_lost(tmp_path):
    """Les écritures pendant un rejeu vont dans une file vierge."""
    buf = _buf(tmp_path)
    buf.enqueue("heartbeat", {"i": 1})
    buf.checkout()

    buf.enqueue("heartbeat", {"i": 2})  # arrive pendant le rejeu
    buf.commit()  # le lot en vol est acquitté

    assert [r["payload"]["i"] for r in buf.peek()] == [2]


# --------------------------------------------------------------- robustesse


def test_truncated_last_line_does_not_discard_the_file(tmp_path):
    """Un arrêt en pleine écriture laisse une ligne partielle : elle seule
    doit être perdue, pas le fichier."""
    path = tmp_path / "q.jsonl"
    good = {"ts": datetime.now(timezone.utc).isoformat(), "kind": "heartbeat", "payload": {"i": 1}}
    path.write_text(json.dumps(good) + "\n" + '{"ts": "2026-01-01T00:00:00+00:00", "kind": "hea',
                    encoding="utf-8")

    buf = DurableBuffer(path)
    records = buf.peek()
    assert len(records) == 1
    assert records[0]["payload"]["i"] == 1


def test_age_bound_is_enforced(tmp_path):
    path = tmp_path / "q.jsonl"
    old = {
        "ts": (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat(),
        "kind": "heartbeat",
        "payload": {"old": True},
    }
    fresh = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "kind": "heartbeat",
        "payload": {"old": False},
    }
    path.write_text(json.dumps(old) + "\n" + json.dumps(fresh) + "\n", encoding="utf-8")

    buf = DurableBuffer(path, max_age_seconds=24 * 3600)
    buf.prune()

    kept = buf.peek()
    assert len(kept) == 1
    assert kept[0]["payload"]["old"] is False


def test_size_bound_drops_oldest_first(tmp_path):
    buf = _buf(tmp_path, max_bytes=400)
    for i in range(40):
        buf.enqueue("heartbeat", {"i": i, "pad": "x" * 40})

    kept = [r["payload"]["i"] for r in buf.peek()]
    assert kept, "la purge ne doit pas tout vider"
    assert buf.size_bytes() <= 400 + 200  # marge d'un enregistrement
    # Les plus récents sont conservés.
    assert max(kept) == 39


def test_size_bytes_counts_the_inflight_batch(tmp_path):
    buf = _buf(tmp_path)
    buf.enqueue("heartbeat", {"i": 1})
    before = buf.size_bytes()
    buf.checkout()
    # Le lot en vol reste sur disque : il doit continuer de compter, sinon la
    # supervision du tampon signalerait une file vide pendant un rejeu.
    assert buf.size_bytes() == pytest.approx(before, abs=2)
