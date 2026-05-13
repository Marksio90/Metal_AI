"""Security context extraction for FastAPI endpoints.

WARNING: x-org-id, x-user-id, and x-role headers are trusted as-is.
This is NOT production-safe — any client can send arbitrary header values.

TODO (production): Replace with JWT validation middleware:
  1. Add python-jose[cryptography] or authlib as a dependency.
  2. Validate a signed JWT in the Authorization: Bearer <token> header.
  3. Extract org_id / user_id / role from verified JWT claims.
  4. Remove the plain-header fallback entirely.
"""

from __future__ import annotations

from fastapi import Header, HTTPException


def get_security_context(
    x_org_id: str = Header(default="default-org"),
    x_user_id: str = Header(default="system"),
    x_role: str = Header(default="viewer"),
) -> dict:
    """Return a security context dict from request headers.

    DEVELOPMENT ONLY: these headers are unverified.
    """
    allowed_roles = {"admin", "estimator", "sales", "viewer"}
    if x_role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Invalid role")
    return {"org_id": x_org_id, "user_id": x_user_id, "role": x_role}
