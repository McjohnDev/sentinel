"""Report generation (DSH-007) — CSV + minimal PDF."""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any, Dict, List


def fleet_rows(agents: List[Any], alerts: List[Any]) -> List[Dict[str, Any]]:
    open_by_agent: Dict[str, int] = {}
    for a in alerts:
        if getattr(a, "status", None) and str(getattr(a.status, "value", a.status)) in ("open", "acknowledged"):
            open_by_agent[a.agent_id] = open_by_agent.get(a.agent_id, 0) + 1
    rows = []
    for ag in agents:
        rows.append(
            {
                "agent_id": ag.id,
                "hostname": ag.hostname,
                "status": ag.status,
                "os": ag.os or "",
                "location": ag.location or "",
                "group_id": getattr(ag, "group_id", None) or "",
                "last_communication": str(ag.last_communication or ""),
                "open_alerts": open_by_agent.get(ag.id, 0),
                "agent_cpu_percent": getattr(ag, "agent_cpu_percent", None) or "",
                "agent_ram_mb": getattr(ag, "agent_ram_mb", None) or "",
            }
        )
    return rows


def to_csv(rows: List[Dict[str, Any]]) -> bytes:
    if not rows:
        return b"agent_id,hostname,status\n"
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def to_pdf(title: str, rows: List[Dict[str, Any]]) -> bytes:
    """Minimal single-page text PDF (no external deps)."""
    lines = [title, f"Generated: {datetime.utcnow().isoformat()}Z", ""]
    for row in rows[:80]:
        lines.append(
            f"{row.get('hostname','?'):20} {row.get('status','?'):10} alerts={row.get('open_alerts',0)}"
        )
    if len(rows) > 80:
        lines.append(f"... +{len(rows) - 80} more")
    content_lines = ["BT /F1 10 Tf 40 800 Td"]
    first = True
    for line in lines:
        prefix = "" if first else "0 -12 Td "
        first = False
        content_lines.append(f"{prefix}({_pdf_escape(line[:110])}) Tj")
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("latin-1", errors="replace")

    objects = []
    objects.append(b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
    objects.append(b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
    objects.append(
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj\n"
    )
    objects.append(
        b"4 0 obj<< /Length "
        + str(len(stream)).encode()
        + b" >>stream\n"
        + stream
        + b"\nendstream\nendobj\n"
    )
    objects.append(b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n")

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(out))
        out.extend(obj)
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(offsets)}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode())
    out.extend(
        f"trailer<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode()
    )
    return bytes(out)
