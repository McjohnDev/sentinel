"""ICMP + SNMP probes for network perimeter devices (AGT-029)."""

from __future__ import annotations

import platform
import socket
import struct
import subprocess
import time
from typing import Any, Dict, Optional, Tuple


def icmp_ping(host: str, timeout_s: float = 2.0) -> Tuple[str, Optional[float], Optional[str]]:
    """Return (status, rtt_ms, error). status: up|down|unknown."""
    system = platform.system().lower()
    try:
        if system == "windows":
            cmd = ["ping", "-n", "1", "-w", str(int(timeout_s * 1000)), host]
        else:
            cmd = ["ping", "-c", "1", "-W", str(int(timeout_s)), host]
        started = time.perf_counter()
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s + 2, check=False)
        elapsed_ms = (time.perf_counter() - started) * 1000
        out = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode == 0:
            return "up", round(elapsed_ms, 1), None
        return "down", None, out.strip()[:200] or f"ping exit {proc.returncode}"
    except Exception as exc:
        return "unknown", None, str(exc)[:200]


SYSDESCR_OID = b"\x2b\x06\x01\x02\x01\x01\x01\x00"  # 1.3.6.1.2.1.1.1.0


def _read_tlv(data: bytes, pos: int) -> Tuple[int, bytes, int]:
    """Lit un triplet BER (tag, valeur, position suivante).

    Gère la forme longue de la longueur : `sysDescr` dépasse fréquemment
    127 octets, et la lecture d'un seul octet de longueur tronquait alors la
    valeur ou décalait tout le parcours.
    """
    if pos + 2 > len(data):
        raise ValueError("TLV tronqué")
    tag = data[pos]
    length = data[pos + 1]
    pos += 2
    if length & 0x80:
        n = length & 0x7F
        if n == 0 or pos + n > len(data):
            raise ValueError("longueur BER invalide")
        length = int.from_bytes(data[pos : pos + n], "big")
        pos += n
    if pos + length > len(data):
        raise ValueError("valeur BER tronquée")
    return tag, data[pos : pos + length], pos + length


def _extract_sysdescr(data: bytes) -> Optional[str]:
    """Extrait sysDescr d'une réponse SNMPv2c en suivant la structure.

    L'implémentation précédente renvoyait la première OCTET STRING imprimable
    de la réponse. Or une réponse SNMP réémet la *communauté* en OCTET STRING
    avant les variable bindings : la sonde retournait donc « public » (ou le
    nom de communauté configuré) en guise de description système, pour tout
    équipement interrogé.

    On descend ici jusqu'au binding dont l'OID est celui de sysDescr, et on ne
    lit que sa valeur.
    """
    try:
        # SEQUENCE englobante
        tag, body, _ = _read_tlv(data, 0)
        if tag != 0x30:
            return None

        pos = 0
        # INTEGER version
        _, _, pos = _read_tlv(body, pos)
        # OCTET STRING community — présente ici, et volontairement ignorée
        _, _, pos = _read_tlv(body, pos)
        # PDU : GetResponse porte le tag contextuel 0xa2
        pdu_tag, pdu, _ = _read_tlv(body, pos)
        if pdu_tag != 0xA2:
            return None

        pos = 0
        _, _, pos = _read_tlv(pdu, pos)          # request-id
        _, err_status, pos = _read_tlv(pdu, pos)  # error-status
        _, _, pos = _read_tlv(pdu, pos)          # error-index
        if err_status and int.from_bytes(err_status, "big") != 0:
            return None

        vb_tag, varbinds, _ = _read_tlv(pdu, pos)
        if vb_tag != 0x30:
            return None

        pos = 0
        while pos < len(varbinds):
            _, binding, pos = _read_tlv(varbinds, pos)
            inner = 0
            oid_tag, oid_value, inner = _read_tlv(binding, inner)
            if oid_tag != 0x06:
                continue
            value_tag, value, _ = _read_tlv(binding, inner)
            if oid_value != SYSDESCR_OID:
                continue
            # 0x04 = OCTET STRING. Les tags 0x80/0x81/0x82 signalent
            # noSuchObject / noSuchInstance / endOfMibView : pas une valeur.
            if value_tag != 0x04:
                return None
            return value.decode("utf-8", errors="replace").strip() or None
    except (ValueError, IndexError):
        return None
    return None


def _snmp_get_sysdescr_v2c(host: str, community: str = "public", timeout_s: float = 2.0) -> Tuple[str, Optional[str], Optional[str]]:
    """
    Minimal SNMPv2c GetRequest for sysDescr (1.3.6.1.2.1.1.1.0).
    Returns (status, sys_descr, error) where status is up|degraded|down|unknown.
    """
    # OID 1.3.6.1.2.1.1.1.0 encoded
    oid = b"\x06\x08\x2b\x06\x01\x02\x01\x01\x01\x00"
    # VariableBinding: SEQUENCE { OID, NULL }
    varbind = b"\x30" + bytes([len(oid) + 2]) + oid + b"\x05\x00"
    varbind_list = b"\x30" + bytes([len(varbind)]) + varbind
    request_id = struct.pack("!i", int(time.time()) & 0x7FFFFFFF)
    # INTEGER request-id, error-status 0, error-index 0
    pdu_body = (
        b"\x02\x04" + request_id
        + b"\x02\x01\x00"
        + b"\x02\x01\x00"
        + varbind_list
    )
    # GetRequest-PDU = CONTEXT [0]
    pdu = b"\xa0" + bytes([len(pdu_body)]) + pdu_body
    # community OCTET STRING
    comm = community.encode("ascii", errors="ignore")[:32] or b"public"
    version = b"\x02\x01\x01"  # version 1 => SNMPv2c
    comm_tlv = b"\x04" + bytes([len(comm)]) + comm
    msg_body = version + comm_tlv + pdu
    message = b"\x30" + bytes([len(msg_body)]) + msg_body

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout_s)
        sock.sendto(message, (host, 161))
        data, _ = sock.recvfrom(4096)
        sock.close()
    except socket.timeout:
        return "down", None, "SNMP timeout"
    except OSError as exc:
        return "down", None, str(exc)[:200]
    except Exception as exc:
        return "unknown", None, str(exc)[:200]

    descr = _extract_sysdescr(data)

    if descr:
        return "up", descr[:500], None
    if data:
        return "degraded", None, "SNMP response without parseable sysDescr"
    return "unknown", None, "empty SNMP response"


def probe_device(host: str, community: str = "public") -> Dict[str, Any]:
    icmp_status, rtt, icmp_err = icmp_ping(host)
    snmp_status, sys_descr, snmp_err = _snmp_get_sysdescr_v2c(host, community)
    err = "; ".join(x for x in (icmp_err, snmp_err) if x) or None
    return {
        "icmp_status": icmp_status,
        "snmp_status": snmp_status,
        "last_rtt_ms": rtt,
        "sys_descr": sys_descr,
        "error_message": err,
    }
