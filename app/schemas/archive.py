from __future__ import annotations

from datetime import datetime

from pydantic import AnyHttpUrl, BaseModel


class ArchivedLinkOut(BaseModel):
    short_code: str
    original_url: AnyHttpUrl
    created_at: datetime
    expires_at: datetime | None
    clicks_count: int
    last_accessed_at: datetime | None
    archived_at: datetime
    archived_reason: str

