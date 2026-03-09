from __future__ import annotations

from datetime import datetime, timezone

from pydantic import AnyHttpUrl, BaseModel, Field, field_validator


class LinkCreate(BaseModel):
    original_url: AnyHttpUrl
    custom_alias: str | None = Field(default=None, min_length=3, max_length=64)
    expires_at: datetime | None = None

    @field_validator("expires_at")
    @classmethod
    def validate_expires_at_minute_precision(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return None
        if v.second != 0 or v.microsecond != 0:
            raise ValueError("expires_at must have minute precision (no seconds)")
        now = datetime.now(timezone.utc)
        vv = v if v.tzinfo else v.replace(tzinfo=timezone.utc)
        if vv <= now:
            raise ValueError("expires_at must be in the future")
        return v


class LinkUpdate(BaseModel):
    original_url: AnyHttpUrl | None = None
    custom_alias: str | None = Field(default=None, min_length=3, max_length=64)
    expires_at: datetime | None = None

    @field_validator("expires_at")
    @classmethod
    def validate_expires_at_minute_precision(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return None
        if v.second != 0 or v.microsecond != 0:
            raise ValueError("expires_at must have minute precision (no seconds)")
        now = datetime.now(timezone.utc)
        vv = v if v.tzinfo else v.replace(tzinfo=timezone.utc)
        if vv <= now:
            raise ValueError("expires_at must be in the future")
        return v


class LinkOut(BaseModel):
    short_code: str
    original_url: AnyHttpUrl
    created_at: datetime
    expires_at: datetime | None


class LinkStats(BaseModel):
    short_code: str
    original_url: AnyHttpUrl
    created_at: datetime
    clicks_count: int
    last_accessed_at: datetime | None
    expires_at: datetime | None

