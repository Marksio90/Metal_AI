"""Audit log helpers — write immutable audit entries to the database."""

from __future__ import annotations

from app.persistence_models import AuditLog


def write_audit(
    db,
    ctx: dict,
    action: str,
    resource_type: str,
    resource_id: str,
    details: dict,
) -> None:
    """Append an audit log entry. Caller is responsible for db.commit()."""
    db.add(AuditLog(
        organization_id=ctx["org_id"],
        actor_id=ctx["user_id"],
        actor_role=ctx["role"],
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
    ))
