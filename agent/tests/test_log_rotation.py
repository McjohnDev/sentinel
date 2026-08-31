"""FS3 — garanties « aucune perte, aucun doublon » du collecteur de journaux.

Deux régressions reproduites ici :

* **Rotation par renommage.** La position était mémorisée sous la seule clé du
  chemin et la rotation n'était détectée que par un rétrécissement du fichier.
  Avec logrotate (`app.log` renommé, nouveau `app.log` recréé), le chemin ne
  change pas : si le nouveau fichier avait déjà dépassé l'ancienne position, la
  lecture reprenait à cette position et sautait le début du nouveau fichier.

* **Retour en arrière des offsets.** Le collecteur journald partage son fichier
  d'état avec le collecteur de fichiers et y réécrivait un instantané pris à sa
  construction, faisant reculer les positions des fichiers — donc réexpédiant
  des lignes déjà envoyées après un redémarrage.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

AGENT_SRC = Path(__file__).resolve().parents[1] / "src"
ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(AGENT_SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest

from log_collector import FileLogCollector, JournaldCollector


def _collector(tmp_path: Path, pattern: str) -> FileLogCollector:
    return FileLogCollector(
        offset_path=tmp_path / "offsets.json",
        patterns=[pattern],
    )


def test_rename_rotation_does_not_lose_the_head_of_the_new_file(tmp_path):
    log = tmp_path / "app.log"
    log.write_text("".join(f"ancienne-{i}\n" for i in range(40)), encoding="utf-8")

    collector = _collector(tmp_path, str(tmp_path / "app.log"))
    first = collector._read_new_lines(log)
    assert len(first) == 40

    # Rotation logrotate : renommage puis recréation, et le nouveau fichier a
    # déjà dépassé la taille de l'ancien au passage suivant.
    log.rename(tmp_path / "app.log.1")
    log.write_text("".join(f"nouvelle-{i}\n" for i in range(60)), encoding="utf-8")

    second = collector._read_new_lines(log)

    assert len(second) == 60, "le début du nouveau fichier a été sauté"
    assert second[0] == "nouvelle-0\n", "la première ligne lue est un fragment"
    assert not any(line.startswith("ancienne-") for line in second)


def test_truncation_in_place_restarts_from_zero(tmp_path):
    log = tmp_path / "app.log"
    log.write_text("".join(f"ligne-{i}\n" for i in range(30)), encoding="utf-8")

    collector = _collector(tmp_path, str(tmp_path / "app.log"))
    assert len(collector._read_new_lines(log)) == 30

    # Troncature sur place (`> app.log`) : même inode, taille remise à zéro.
    log.write_text("apres-troncature\n", encoding="utf-8")
    lines = collector._read_new_lines(log)
    assert lines == ["apres-troncature\n"]


def test_no_duplicates_when_nothing_changed(tmp_path):
    log = tmp_path / "app.log"
    log.write_text("a\nb\nc\n", encoding="utf-8")

    collector = _collector(tmp_path, str(tmp_path / "app.log"))
    assert len(collector._read_new_lines(log)) == 3
    assert collector._read_new_lines(log) == [], "relecture de lignes déjà lues"


def test_append_reads_only_the_new_lines(tmp_path):
    log = tmp_path / "app.log"
    log.write_text("a\nb\n", encoding="utf-8")

    collector = _collector(tmp_path, str(tmp_path / "app.log"))
    assert len(collector._read_new_lines(log)) == 2

    with log.open("a", encoding="utf-8") as f:
        f.write("c\nd\n")

    assert collector._read_new_lines(log) == ["c\n", "d\n"]


def test_offsets_survive_a_restart(tmp_path):
    log = tmp_path / "app.log"
    log.write_text("a\nb\nc\n", encoding="utf-8")

    first = _collector(tmp_path, str(tmp_path / "app.log"))
    assert len(first._read_new_lines(log)) == 3
    first._save_offsets()

    # Nouveau processus : l'état est relu depuis le disque.
    second = _collector(tmp_path, str(tmp_path / "app.log"))
    assert second._read_new_lines(log) == [], "lignes réexpédiées après redémarrage"


def test_journald_cursor_does_not_roll_back_file_offsets(tmp_path):
    """Le collecteur journald ne doit toucher que sa propre clé."""
    state_path = tmp_path / "offsets.json"
    log = tmp_path / "app.log"
    log.write_text("a\nb\nc\n", encoding="utf-8")

    files = FileLogCollector(offset_path=state_path, patterns=[str(log)])
    assert len(files._read_new_lines(log)) == 3
    files._save_offsets()

    saved = json.loads(state_path.read_text(encoding="utf-8"))
    offset_before = saved[str(log)]["offset"]
    assert offset_before > 0

    # Le collecteur journald est construit AVANT d'autres avancées de fichier :
    # son instantané d'état est donc périmé lorsqu'il écrit.
    def fake_reader(cursor, units, limit):
        return [], "curseur-2"

    journald = JournaldCollector(state_path=state_path, units=[], reader=fake_reader)

    # Le fichier progresse après la construction du collecteur journald.
    with log.open("a", encoding="utf-8") as f:
        f.write("d\ne\n")
    assert len(files._read_new_lines(log)) == 2
    files._save_offsets()
    offset_after = json.loads(state_path.read_text(encoding="utf-8"))[str(log)]["offset"]
    assert offset_after > offset_before

    # Le collecteur journald écrit son curseur.
    journald.collect()

    final = json.loads(state_path.read_text(encoding="utf-8"))
    assert final["journald_cursor"] == "curseur-2"
    assert final[str(log)]["offset"] == offset_after, (
        "l'écriture du curseur journald a fait reculer la position du fichier"
    )
