"""AGT-029 — analyse des réponses SNMPv2c.

Régression couverte : l'extraction renvoyait la première OCTET STRING
imprimable de la réponse. Or une réponse SNMP réémet la **communauté** en
OCTET STRING avant les variable bindings : la sonde retournait donc « public »
comme description système pour tout équipement interrogé.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

ROOT = Path(__file__).resolve().parents[2]
SERVER = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(SERVER)):
    if p not in sys.path:
        sys.path.insert(0, p)

from src.network_probe import SYSDESCR_OID, _extract_sysdescr, _read_tlv


def _tlv(tag: int, payload: bytes) -> bytes:
    """Encode un triplet BER, forme longue de longueur incluse."""
    if len(payload) < 0x80:
        return bytes([tag, len(payload)]) + payload
    length_bytes = len(payload).to_bytes((len(payload).bit_length() + 7) // 8, "big")
    return bytes([tag, 0x80 | len(length_bytes)]) + length_bytes + payload


def _response(community: bytes, descr: bytes, *, oid: bytes = SYSDESCR_OID, err: int = 0) -> bytes:
    binding = _tlv(0x06, oid) + _tlv(0x04, descr)
    varbinds = _tlv(0x30, _tlv(0x30, binding))
    pdu_body = (
        _tlv(0x02, b"\x01\x02\x03\x04")   # request-id
        + _tlv(0x02, bytes([err]))         # error-status
        + _tlv(0x02, b"\x00")              # error-index
        + varbinds
    )
    pdu = _tlv(0xA2, pdu_body)             # GetResponse
    body = _tlv(0x02, b"\x01") + _tlv(0x04, community) + pdu
    return _tlv(0x30, body)


def test_community_is_not_mistaken_for_sysdescr():
    """Le cœur de la régression."""
    payload = _response(b"public", b"Cisco IOS Software, C2960 Software")
    assert _extract_sysdescr(payload) == "Cisco IOS Software, C2960 Software"


def test_long_community_is_still_ignored():
    """Une communauté longue et imprimable était le pire cas : elle
    satisfaisait le filtre `length > 3` de l'ancienne implémentation."""
    payload = _response(b"communaute-de-supervision-cbc", b"HP ProCurve 2530")
    assert _extract_sysdescr(payload) == "HP ProCurve 2530"


def test_sysdescr_longer_than_127_bytes():
    """La longueur BER en forme longue doit être gérée : l'ancienne lecture
    d'un seul octet tronquait la valeur."""
    long_descr = b"Cisco IOS Software " + b"X" * 300
    payload = _response(b"public", long_descr)
    result = _extract_sysdescr(payload)
    assert result is not None
    assert len(result) == len(long_descr)
    assert result.endswith("X")


def test_other_oid_is_not_returned():
    """Un binding portant un autre OID ne doit pas être pris pour sysDescr."""
    sysname_oid = b"\x2b\x06\x01\x02\x01\x01\x05\x00"  # 1.3.6.1.2.1.1.5.0
    payload = _response(b"public", b"switch-agence-01", oid=sysname_oid)
    assert _extract_sysdescr(payload) is None


def test_error_status_yields_no_value():
    payload = _response(b"public", b"peu importe", err=2)  # noSuchName
    assert _extract_sysdescr(payload) is None


def test_malformed_payloads_never_raise():
    for bad in (b"", b"\x30", b"\x30\x82", b"\x30\x05\x02\x01\x01", b"\xff" * 40):
        assert _extract_sysdescr(bad) is None


def test_read_tlv_handles_long_form_length():
    payload = b"A" * 200
    encoded = _tlv(0x04, payload)
    tag, value, nxt = _read_tlv(encoded, 0)
    assert tag == 0x04
    assert value == payload
    assert nxt == len(encoded)
