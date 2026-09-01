"""Import du plan d'adressage fourni par l'équipe réseau.

Le fichier vient d'un tableur tenu par des humains : séparateur
point-virgule, signature d'octets, en-têtes en français, « VLAN 20 » écrit en
toutes lettres, cellules vides. Tout cela doit être absorbé ici plutôt que
d'être exigé de l'équipe réseau — sinon l'import échoue au premier envoi et
personne ne recommence.

La règle qui compte : une ligne fautive est **rejetée nommément**, jamais
avalée en silence. Un import à moitié appliqué rattacherait des hôtes à un
VLAN qui n'est pas le leur sans que quiconque le sache.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SERVER = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(SERVER)):
    if p not in sys.path:
        sys.path.insert(0, p)

from src.vlan_service import (  # noqa: E402
    SubnetRow,
    VlanImportError,
    match_ip,
    normalise_cidr,
    normalise_vlan,
    parse,
)


# ----------------------------------------------------------- normalisation


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("10.20.4.0/24", "10.20.4.0/24"),
        ("10.20.4.0 255.255.255.0", "10.20.4.0/24"),  # export « réseau masque »
        ("10.20.4.7/24", "10.20.4.0/24"),             # hôte donné pour le réseau
        ("192.168.1.5", "192.168.1.5/32"),
        ("  10.0.0.0/8  ", "10.0.0.0/8"),
    ],
)
def test_subnet_notations_are_accepted(raw, expected):
    assert normalise_cidr(raw) == expected


@pytest.mark.parametrize("raw", ["", None, "pas un réseau", "10.20.4.0/33", "999.1.1.1/24"])
def test_unusable_subnets_are_rejected(raw):
    assert normalise_cidr(raw) is None


@pytest.mark.parametrize(
    "raw,expected",
    [("20", "20"), ("VLAN 20", "20"), (" 30 (Agences) ", "30"), (4094, "4094"), (1, "1")],
)
def test_vlan_is_extracted_from_how_people_write_it(raw, expected):
    # L'équipe réseau écrit rarement un entier nu dans un tableur.
    assert normalise_vlan(raw) == expected


@pytest.mark.parametrize("raw", ["0", "4095", "9999", "", None, "Monétique"])
def test_out_of_range_vlans_are_rejected(raw):
    assert normalise_vlan(raw) is None


# ------------------------------------------------------------------ lecture


def test_a_french_excel_export_is_read():
    # Point-virgule, signature d'octets, en-têtes accentués.
    content = (
        "﻿Sous-réseau;VLAN;Libellé\r\n"
        "10.20.4.0/24;20;Monétique\r\n"
        "10.20.8.0/24;VLAN 30;Agences\r\n"
    ).encode("utf-8")

    report = parse(content, "plan.csv")

    assert report.accepted_count == 2
    assert report.rows[0] == SubnetRow("10.20.4.0/24", "20", "Monétique")
    assert report.rows[1].vlan == "30"
    assert report.rejected == []


def test_an_english_comma_export_is_read():
    content = b"subnet,vlan,label\n10.20.4.0/24,20,Payments\n"
    assert parse(content, "plan.csv").rows[0].vlan == "20"


def test_columns_are_found_by_name_whatever_their_order():
    content = "Libellé;VLAN;Sous-réseau\nMonétique;20;10.20.4.0/24\n".encode("utf-8")
    row = parse(content, "plan.csv").rows[0]
    assert row.cidr == "10.20.4.0/24"
    assert row.vlan == "20"
    assert row.label == "Monétique"


def test_a_file_without_a_header_uses_the_requested_order():
    content = b"10.20.4.0/24;20;Monetique\n10.20.8.0/24;30;Agences\n"
    report = parse(content, "plan.csv")
    assert report.accepted_count == 2
    assert report.rows[0].cidr == "10.20.4.0/24"


def test_the_label_is_optional():
    content = b"subnet;vlan\n10.20.4.0/24;20\n"
    assert parse(content, "plan.csv").rows[0].label is None


# ------------------------------------------------------------------- refus


def test_a_bad_line_is_named_not_swallowed():
    content = (
        "Sous-réseau;VLAN;Libellé\n"
        "10.20.4.0/24;20;Bon\n"
        "pas-un-reseau;30;Mauvais\n"
        "10.20.9.0/24;4095;VLAN réservé\n"
    ).encode("utf-8")

    report = parse(content, "plan.csv")

    assert report.accepted_count == 1
    assert len(report.rejected) == 2
    assert report.rejected[0]["line"] == 3
    assert "sous-réseau" in report.rejected[0]["reason"]
    assert report.rejected[1]["line"] == 4
    assert "4094" in report.rejected[1]["reason"]


def test_a_duplicated_subnet_is_refused_and_points_at_the_first():
    # Deux VLAN pour un même sous-réseau : le plan est contradictoire, et
    # choisir silencieusement l'un des deux serait arbitraire.
    content = b"subnet;vlan\n10.20.4.0/24;20\n10.20.4.0/24;30\n"
    report = parse(content, "plan.csv")
    assert report.accepted_count == 1
    assert "ligne 2" in report.rejected[0]["reason"]


def test_an_empty_file_is_refused():
    with pytest.raises(VlanImportError):
        parse(b"", "plan.csv")


def test_a_file_with_nothing_valid_is_refused_with_the_expected_shape():
    with pytest.raises(VlanImportError) as exc:
        parse(b"n'importe quoi;du tout\nencore;pire\n", "plan.csv")
    assert "10.20.4.0/24" in str(exc.value)


def test_legacy_excel_is_refused_with_a_way_out():
    with pytest.raises(VlanImportError) as exc:
        parse(b"\xd0\xcf\x11\xe0", "plan.xls")
    assert ".xlsx" in str(exc.value)


def test_a_real_xlsx_workbook_is_read(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    path = tmp_path / "plan.xlsx"
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.append(["Sous-réseau", "VLAN", "Libellé"])
    sheet.append(["10.20.4.0/24", 20, "Monétique"])
    sheet.append(["10.20.8.0/24", "VLAN 30", "Agences"])
    book.save(path)

    report = parse(path.read_bytes(), "plan.xlsx")

    assert report.accepted_count == 2
    assert report.rows[0].vlan == "20"
    assert report.rows[1].label == "Agences"


# ---------------------------------------------------------------- jointure


ROWS = [
    SubnetRow("10.0.0.0/8", "1", "Global"),
    SubnetRow("10.20.4.0/24", "20", "Monétique"),
    SubnetRow("10.20.8.0/24", "30", "Agences"),
]


def test_the_most_specific_subnet_wins():
    # Les plans d'adressage déclarent couramment un /8 de site *et* les /24
    # qui le découpent. Rendre le /8 rattacherait tout le parc au mauvais VLAN.
    assert match_ip("10.20.4.17", ROWS).vlan == "20"
    assert match_ip("10.20.8.3", ROWS).vlan == "30"


def test_an_address_outside_every_subnet_matches_nothing():
    assert match_ip("192.168.50.4", ROWS) is None


def test_an_address_only_in_the_broad_range_falls_back_to_it():
    assert match_ip("10.99.0.1", ROWS).vlan == "1"


@pytest.mark.parametrize("value", [None, "", "pas une adresse", "10.20.4"])
def test_an_unusable_address_matches_nothing(value):
    assert match_ip(value, ROWS) is None
