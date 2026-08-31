"""FS3-06 — le débordement doit éviter la perte, pas la garantir.

Régression couverte : le fichier de débordement était en écriture seule. Jamais
relu, jamais rejoué, jamais plafonné — il croissait sans limite sur l'hôte
supervisé et son contenu était perdu de fait. Le mécanisme censé protéger
contre la perte la rendait certaine.
"""

from __future__ import annotations

import sys
from pathlib import Path

AGENT_SRC = Path(__file__).resolve().parents[1] / "src"
ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(AGENT_SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest

from log_collector import FileLogCollector, RateLimiter


def _collector(tmp_path, *, max_bytes_per_min=5 * 1024 * 1024, spill_max_bytes=0):
    c = FileLogCollector(
        offset_path=tmp_path / "offsets.json",
        patterns=[str(tmp_path / "app.log")],
        spill_path=tmp_path / "spill.log",
    )
    c.limiter = RateLimiter(max_bytes_per_min=max_bytes_per_min)
    if spill_max_bytes:
        c.spill_max_bytes = spill_max_bytes
    return c


def test_over_budget_lines_are_spilled_not_dropped(tmp_path):
    """Au-delà du débit, la ligne part au débordement plutôt qu'à la poubelle."""
    c = _collector(tmp_path, max_bytes_per_min=10)

    admitted = c._admit({"message": "x" * 200}, "x" * 200)

    assert admitted is None
    assert c.rate_limited is True
    assert c.spill_path.exists()
    assert "x" * 200 in c.spill_path.read_text(encoding="utf-8")


def test_spilled_lines_are_replayed_when_budget_returns(tmp_path):
    """Le cœur de la régression : ce qui a débordé doit revenir."""
    c = _collector(tmp_path, max_bytes_per_min=1)
    for i in range(3):
        c._admit({"message": f"ligne-{i}"}, f"ligne-{i}")
    assert c.spill_path.exists()

    # Nouveau cycle avec un débit rétabli.
    c.limiter = RateLimiter(max_bytes_per_min=5 * 1024 * 1024)
    recovered = c._drain_spill()

    assert len(recovered) == 3
    assert [r.strip() for r in recovered] == ["ligne-0", "ligne-1", "ligne-2"]
    # Une fois reprises, elles ne doivent pas être renvoyées en boucle.
    assert not c.spill_path.exists()


def test_replay_respects_the_current_budget(tmp_path):
    """Un débordement volumineux ne doit pas être réinjecté d'un bloc."""
    c = _collector(tmp_path, max_bytes_per_min=1)
    for i in range(10):
        c._admit({"message": f"ligne-{i}"}, f"ligne-{i}")

    # Budget étroit : seules quelques lignes passent.
    c.limiter = RateLimiter(max_bytes_per_min=24)
    first = c._drain_spill()

    assert 0 < len(first) < 10, "la reprise doit être partielle"
    assert c.spill_path.exists(), "le reste doit rester en attente"

    c.limiter = RateLimiter(max_bytes_per_min=5 * 1024 * 1024)
    second = c._drain_spill()
    assert len(first) + len(second) == 10, "aucune ligne ne doit disparaître"


def test_replay_preserves_order(tmp_path):
    c = _collector(tmp_path, max_bytes_per_min=1)
    for i in range(5):
        c._admit({"message": f"{i}"}, f"{i}")

    c.limiter = RateLimiter(max_bytes_per_min=5 * 1024 * 1024)
    recovered = [r.strip() for r in c._drain_spill()]
    assert recovered == ["0", "1", "2", "3", "4"]


def test_spill_file_is_capped_by_rotation(tmp_path):
    """Sans plafond, le fichier remplissait le disque de l'hôte supervisé."""
    c = _collector(tmp_path, max_bytes_per_min=1, spill_max_bytes=500)

    for i in range(200):
        c._admit({"message": "y" * 60}, "y" * 60)

    live = c.spill_path.stat().st_size if c.spill_path.exists() else 0
    backup = c.spill_path.with_suffix(c.spill_path.suffix + ".1")
    backup_size = backup.stat().st_size if backup.exists() else 0

    # Une génération de secours au plus : la taille totale reste bornée.
    assert live <= 500 + 200
    assert backup_size <= 500 + 200
    assert live + backup_size < 200 * 61, "le fichier n'est pas borné"


def test_empty_spill_is_removed(tmp_path):
    c = _collector(tmp_path)
    c.spill_path.write_text("\n\n", encoding="utf-8")
    assert c._drain_spill() == []
    assert not c.spill_path.exists()


def test_missing_spill_is_not_an_error(tmp_path):
    c = _collector(tmp_path)
    assert c._drain_spill() == []


def test_replayed_lines_reach_the_collector_output(tmp_path):
    """Bout en bout : une ligne qui a débordé finit par être expédiée."""
    log = tmp_path / "app.log"
    log.write_text("depassement\n", encoding="utf-8")

    c = _collector(tmp_path, max_bytes_per_min=1)
    events, _ = c.collect()
    assert events == [], "la ligne doit être écartée sous contrainte de débit"
    assert c.spill_path.exists()

    # Rien de neuf dans le fichier, mais le débit est rétabli.
    c.limiter = RateLimiter(max_bytes_per_min=5 * 1024 * 1024)
    events, _ = c.collect()

    assert any("depassement" in (e.get("message") or "") for e in events), (
        "la ligne mise de côté n'a jamais été reprise"
    )
