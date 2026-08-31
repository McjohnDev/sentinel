"""CBC mail templates — global defaults plus per-agent overrides.

Lookup order for a given (kind, event_key, agent_id):
  1. DB row for this agent + event
  2. DB row global (agent_id="") + event
  3. Built-in default for the event
  4. Built-in kind fallback (alert.default / task.default)
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from src.models import MailTemplate

GOLD = "#D0B335"
NAVY = "#0F172A"


def _shell(inner: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="margin:0;padding:0;background:#F1F5F9;font-family:Segoe UI,Arial,sans-serif;color:{NAVY}">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F1F5F9;padding:24px 12px">
    <tr><td align="center">
      <table role="presentation" width="640" cellpadding="0" cellspacing="0" style="max-width:640px;background:#ffffff;border-radius:12px;overflow:hidden;border:1px solid #E2E8F0">
        <tr>
          <td style="background:{NAVY};padding:16px 24px;color:#fff;font-weight:700;letter-spacing:.04em">
            <span style="color:{GOLD}">SENTINEL</span> · CBC Supervision
          </td>
        </tr>
        <tr><td style="padding:24px">{inner}</td></tr>
        <tr>
          <td style="padding:12px 24px;background:#F8FAFC;color:#64748B;font-size:11px;border-top:1px solid #E2E8F0">
            Message automatique — ne pas répondre. CBC Supervision Platform.
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _badge(color: str, text: str) -> str:
    return (
        f'<span style="display:inline-block;background:{color};color:#fff;'
        f'font-size:11px;font-weight:700;padding:3px 8px;border-radius:999px;'
        f'text-transform:uppercase">{text}</span>'
    )


_SEV_COLOR = {
    "critical": "#E11D48",
    "major": "#F59E0B",
    "minor": "#3B82F6",
    "info": "#64748B",
    "warning": "#F59E0B",
}


def _alert_body() -> str:
    return _shell(
        """
        <p style="margin:0 0 12px">{severity_badge}</p>
        <h1 style="margin:0 0 8px;font-size:20px">Alerte {alert_type_label}</h1>
        <p style="margin:0 0 16px;color:#475569">{message}</p>
        <table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;font-size:13px;border-collapse:collapse">
          <tr><td style="padding:6px 0;color:#64748B;width:140px">Hôte</td><td style="padding:6px 0"><strong>{hostname}</strong> ({agent_name})</td></tr>
          <tr><td style="padding:6px 0;color:#64748B">IP</td><td style="padding:6px 0">{ip_address}</td></tr>
          <tr><td style="padding:6px 0;color:#64748B">Localisation</td><td style="padding:6px 0">{location}</td></tr>
          <tr><td style="padding:6px 0;color:#64748B">Montage</td><td style="padding:6px 0">{mount}</td></tr>
          <tr><td style="padding:6px 0;color:#64748B">Valeur</td><td style="padding:6px 0">{value}</td></tr>
          <tr><td style="padding:6px 0;color:#64748B">Seuil</td><td style="padding:6px 0">{threshold}</td></tr>
          <tr><td style="padding:6px 0;color:#64748B">Horodatage</td><td style="padding:6px 0">{timestamp}</td></tr>
        </table>
        """
    )


def _task_body() -> str:
    return _shell(
        """
        <p style="margin:0 0 12px">{status_badge}</p>
        <h1 style="margin:0 0 8px;font-size:20px">Action {plugin}</h1>
        <p style="margin:0 0 16px;color:#475569">{message}</p>
        <table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;font-size:13px;border-collapse:collapse">
          <tr><td style="padding:6px 0;color:#64748B;width:140px">Hôte</td><td style="padding:6px 0"><strong>{hostname}</strong> ({agent_name})</td></tr>
          <tr><td style="padding:6px 0;color:#64748B">IP</td><td style="padding:6px 0">{ip_address}</td></tr>
          <tr><td style="padding:6px 0;color:#64748B">Tâche</td><td style="padding:6px 0">{task_id}</td></tr>
          <tr><td style="padding:6px 0;color:#64748B">Plugin</td><td style="padding:6px 0">{plugin}</td></tr>
          <tr><td style="padding:6px 0;color:#64748B">Statut</td><td style="padding:6px 0">{status}</td></tr>
          <tr><td style="padding:6px 0;color:#64748B">Dry-run</td><td style="padding:6px 0">{dry_run}</td></tr>
          <tr><td style="padding:6px 0;color:#64748B">Demandé par</td><td style="padding:6px 0">{requested_by}</td></tr>
          <tr><td style="padding:6px 0;color:#64748B">Horodatage</td><td style="padding:6px 0">{timestamp}</td></tr>
        </table>
        """
    )


# Built-in catalog. Keys: (kind, event_key) -> (subject, body_html, description)
DEFAULT_TEMPLATES: Dict[Tuple[str, str], Tuple[str, str, str]] = {
    ("alert", "default"): (
        "[{severity_upper}] {alert_type} — {hostname}",
        _alert_body(),
        "Gabarit générique d'alerte",
    ),
    ("alert", "cpu_high"): (
        "[{severity_upper}] CPU élevé — {hostname}",
        _alert_body(),
        "CPU au-dessus du seuil",
    ),
    ("alert", "ram_high"): (
        "[{severity_upper}] RAM élevée — {hostname}",
        _alert_body(),
        "Mémoire au-dessus du seuil",
    ),
    ("alert", "disk_high"): (
        "[{severity_upper}] Disque {mount} — {hostname}",
        _alert_body(),
        "Disque / partition au-dessus du seuil",
    ),
    ("alert", "agent_offline"): (
        "[CRITIQUE] Agent hors ligne — {hostname}",
        _alert_body(),
        "Agent sans heartbeat",
    ),
    ("alert", "back_online"): (
        "[INFO] Agent de retour — {hostname}",
        _alert_body(),
        "Agent de nouveau en ligne",
    ),
    ("alert", "service_down"): (
        "[CRITIQUE] Service arrêté — {hostname}",
        _alert_body(),
        "Service système down",
    ),
    ("alert", "file_anomaly"): (
        "[MAJEUR] Fichier anormal — {hostname}",
        _alert_body(),
        "Fichier surveillé manquant ou hors taille",
    ),
    ("alert", "log_pattern"): (
        "[MAJEUR] Motif journal — {hostname}",
        _alert_body(),
        "Motif de log détecté",
    ),
    ("task", "default"): (
        "[{status_upper}] {plugin} — {hostname}",
        _task_body(),
        "Gabarit générique d'action distante",
    ),
    ("task", "health.check"): (
        "Contrôle santé — {hostname}",
        _task_body(),
        "health.check",
    ),
    ("task", "service.manage"): (
        "Service {status} — {hostname}",
        _task_body(),
        "service.manage",
    ),
    ("task", "inventory.snapshot"): (
        "Inventaire — {hostname}",
        _task_body(),
        "inventory.snapshot",
    ),
    ("task", "metrics.on_demand"): (
        "Métriques à la demande — {hostname}",
        _task_body(),
        "metrics.on_demand",
    ),
    ("task", "pci.hygiene"): (
        "PCI Hygiene — {hostname}",
        _task_body(),
        "Lot 2 PCI DSS–aligned hygiene score (not AoC)",
    ),
    ("task", "pending_approval"): (
        "Approbation requise: {plugin} — {hostname}",
        _task_body(),
        "Action en attente d'approbation",
    ),
    ("task", "succeeded"): (
        "Action réussie: {plugin} — {hostname}",
        _task_body(),
        "Résultat d'action OK",
    ),
    ("task", "failed"): (
        "Action échouée: {plugin} — {hostname}",
        _task_body(),
        "Résultat d'action en échec",
    ),
}

# Extra keys: plugin:status combinations fall back to plugin then status then default
for _plugin in (
    "health.check",
    "service.manage",
    "inventory.snapshot",
    "metrics.on_demand",
    "pci.hygiene",
):
    for _status in ("pending_approval", "queued", "approved", "denied", "succeeded", "failed", "rejected", "dry_run"):
        DEFAULT_TEMPLATES.setdefault(
            ("task", f"{_plugin}:{_status}"),
            DEFAULT_TEMPLATES[("task", _status)] if ("task", _status) in DEFAULT_TEMPLATES else DEFAULT_TEMPLATES[("task", _plugin)],
        )


class _Safe(dict):
    def __missing__(self, key: str) -> str:
        return ""


def render(subject: str, body: str, context: Dict[str, Any]) -> Tuple[str, str]:
    ctx = _Safe({k: "" if v is None else str(v) for k, v in context.items()})
    sev = (ctx.get("severity") or "info").lower()
    ctx["severity_upper"] = sev.upper()
    ctx["severity_badge"] = _badge(_SEV_COLOR.get(sev, "#64748B"), sev)
    status = (ctx.get("status") or "queued").lower()
    ctx["status_upper"] = status.upper()
    status_color = {"succeeded": "#10B981", "failed": "#E11D48", "denied": "#E11D48", "pending_approval": "#F59E0B"}.get(
        status, GOLD
    )
    ctx["status_badge"] = _badge(status_color, status)
    ctx.setdefault("alert_type_label", ctx.get("alert_type", "alerte").replace("_", " "))
    try:
        return subject.format_map(ctx), body.format_map(ctx)
    except Exception:
        return subject, body


def seed_defaults(db: Session) -> int:
    """Insert missing built-in global templates. Does not overwrite custom rows."""
    existing = {
        (r.kind, r.event_key, r.agent_id or "")
        for r in db.query(MailTemplate).all()
    }
    n = 0
    for (kind, event_key), (subject, body, desc) in DEFAULT_TEMPLATES.items():
        key = (kind, event_key, "")
        if key in existing:
            continue
        db.add(
            MailTemplate(
                id=str(uuid.uuid4()),
                kind=kind,
                event_key=event_key,
                agent_id="",
                subject=subject,
                body_html=body,
                description=desc,
            )
        )
        n += 1
    if n:
        db.commit()
    return n


def resolve(
    db: Optional[Session],
    kind: str,
    event_key: str,
    agent_id: Optional[str] = None,
) -> Tuple[str, str]:
    """Return (subject, body_html) for kind/event, preferring per-agent override."""
    fallbacks = [event_key]
    if kind == "task" and ":" in event_key:
        plugin, status = event_key.split(":", 1)
        fallbacks.extend([plugin, status])
    fallbacks.append("default")

    if db is not None:
        seed_defaults(db)
        aid = agent_id or ""
        for key in fallbacks:
            if aid:
                row = (
                    db.query(MailTemplate)
                    .filter(
                        MailTemplate.kind == kind,
                        MailTemplate.event_key == key,
                        MailTemplate.agent_id == aid,
                    )
                    .first()
                )
                if row:
                    return row.subject, row.body_html
            row = (
                db.query(MailTemplate)
                .filter(
                    MailTemplate.kind == kind,
                    MailTemplate.event_key == key,
                    MailTemplate.agent_id == "",
                )
                .first()
            )
            if row:
                return row.subject, row.body_html

    for key in fallbacks:
        built = DEFAULT_TEMPLATES.get((kind, key))
        if built:
            return built[0], built[1]
    built = DEFAULT_TEMPLATES[("alert" if kind == "alert" else "task", "default")]
    return built[0], built[1]
