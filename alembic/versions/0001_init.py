"""init schema

Revision ID: 0001_init
Revises: 
Create Date: 2026-03-09

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_init"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

    op.create_table(
        "links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("short_code", sa.String(length=64), nullable=False),
        sa.Column("original_url", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("clicks_count", sa.Integer(), nullable=False),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("owner_guest_id", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("short_code", name="uq_links_short_code"),
    )
    op.create_index("ix_links_expires_at", "links", ["expires_at"], unique=False)
    op.create_index("ix_links_original_url", "links", ["original_url"], unique=False)
    op.create_index("ix_links_owner_guest_id", "links", ["owner_guest_id"], unique=False)
    op.create_index("ix_links_owner_user_id", "links", ["owner_user_id"], unique=False)

    op.create_table(
        "links_archive",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("short_code", sa.String(length=64), nullable=False),
        sa.Column("original_url", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("clicks_count", sa.Integer(), nullable=False),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("owner_guest_id", sa.String(length=64), nullable=True),
        sa.Column(
            "archived_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("archived_reason", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_links_archive_archived_at", "links_archive", ["archived_at"], unique=False
    )
    op.create_index(
        "ix_links_archive_archived_reason",
        "links_archive",
        ["archived_reason"],
        unique=False,
    )
    op.create_index(
        "ix_links_archive_owner_guest_id",
        "links_archive",
        ["owner_guest_id"],
        unique=False,
    )
    op.create_index(
        "ix_links_archive_owner_user_id",
        "links_archive",
        ["owner_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_links_archive_owner_user_id", table_name="links_archive")
    op.drop_index("ix_links_archive_owner_guest_id", table_name="links_archive")
    op.drop_index("ix_links_archive_archived_reason", table_name="links_archive")
    op.drop_index("ix_links_archive_archived_at", table_name="links_archive")
    op.drop_table("links_archive")

    op.drop_index("ix_links_owner_user_id", table_name="links")
    op.drop_index("ix_links_owner_guest_id", table_name="links")
    op.drop_index("ix_links_original_url", table_name="links")
    op.drop_index("ix_links_expires_at", table_name="links")
    op.drop_table("links")

    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")

