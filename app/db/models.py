from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Link(Base):
    __tablename__ = "links"
    __table_args__ = (
        UniqueConstraint("short_code", name="uq_links_short_code"),
        Index("ix_links_original_url", "original_url"),
        Index("ix_links_owner_user_id", "owner_user_id"),
        Index("ix_links_owner_guest_id", "owner_guest_id"),
        Index("ix_links_expires_at", "expires_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    short_code: Mapped[str] = mapped_column(String(64), nullable=False)
    original_url: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    clicks_count: Mapped[int] = mapped_column(default=0, nullable=False)
    last_accessed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    owner_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    owner_guest_id: Mapped[Optional[str]] = mapped_column(String(64))


class LinkArchive(Base):
    __tablename__ = "links_archive"
    __table_args__ = (
        Index("ix_links_archive_owner_user_id", "owner_user_id"),
        Index("ix_links_archive_owner_guest_id", "owner_guest_id"),
        Index("ix_links_archive_archived_reason", "archived_reason"),
        Index("ix_links_archive_archived_at", "archived_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    short_code: Mapped[str] = mapped_column(String(64), nullable=False)
    original_url: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    clicks_count: Mapped[int] = mapped_column(nullable=False)
    last_accessed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    owner_user_id: Mapped[Optional[int]] = mapped_column()
    owner_guest_id: Mapped[Optional[str]] = mapped_column(String(64))

    archived_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    archived_reason: Mapped[str] = mapped_column(String(32))

