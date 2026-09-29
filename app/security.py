"""API-key authentication. Multi-tenant by source_system.

* P2_API_KEYS='p1-rajat:key1,p1-teamB:key2' -> each key is bound to ONE source_system and can
  only see that source's referrals / results / sessions.
* P2_API_KEY (admin key) -> may act for any source_system (it must then name it), and opens the
  admin page. If only P2_API_KEY is set (no P2_API_KEYS), it is the single shared key.
"""
from __future__ import annotations

import hmac
import re
from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from .config import settings

SOURCE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]{0,63}$")
DEFAULT_SOURCE = "default"


@dataclass
class Caller:
    is_admin: bool
    source_system: Optional[str]      # fixed for tenant keys; None for admin

    def resolve_source(self, requested: Optional[str], required: bool = False) -> Optional[str]:
        """Return the source_system this request acts for, or raise 403/400."""
        if not self.is_admin:
            if requested and requested != self.source_system:
                raise HTTPException(403, detail={"error": "forbidden_source_system",
                                                 "message": f"This API key belongs to '{self.source_system}' "
                                                            f"and cannot access '{requested}'."})
            return self.source_system
        if requested:
            if not SOURCE_RE.match(requested):
                raise HTTPException(400, detail={"error": "invalid_source_system",
                                                 "message": "source_system: letters, digits, . _ - (max 64)"})
            return requested
        if required:
            return DEFAULT_SOURCE
        return None


def _match(key: str) -> Optional[Caller]:
    for k, src in settings.source_keys.items():
        if hmac.compare_digest(k, key):
            return Caller(False, src)
    if settings.admin_api_key and hmac.compare_digest(settings.admin_api_key, key):
        return Caller(True, None)
    return None


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False,
                              description="Source-system key (P2_API_KEYS) or admin key (P2_API_KEY)")


def require_api_key(request: Request, x_api_key: Optional[str] = Security(api_key_header)) -> Caller:
    if not settings.admin_api_key and not settings.source_keys:
        raise HTTPException(503, detail={"error": "not_configured",
                                         "message": "No API key configured on the server (set P2_API_KEY)."})
    key = x_api_key or ""
    if not key:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            key = auth[7:].strip()
    if not key:
        raise HTTPException(401, detail={"error": "missing_api_key", "message": "Send the X-API-Key header."})
    caller = _match(key)
    if not caller:
        raise HTTPException(401, detail={"error": "invalid_api_key", "message": "API key not recognised."})
    return caller


def require_admin(caller: Caller) -> None:
    if not caller.is_admin:
        raise HTTPException(403, detail={"error": "admin_only", "message": "This endpoint needs the admin key (P2_API_KEY)."})
