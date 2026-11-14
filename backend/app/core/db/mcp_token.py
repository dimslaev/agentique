"""A reader's MCP token: one per account, stored as a hash."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Uuid
from sqlmodel import Field, SQLModel

from app.core.dates import get_datetime_utc


class McpToken(SQLModel, table=True):
    __tablename__ = "mcp_token"
    # The primary key is what keeps it to one token per account. The row goes
    # with the account, so deleting a user needs no cleanup step.
    user_id: uuid.UUID = Field(
        sa_column=Column(
            Uuid, ForeignKey("user.id", ondelete="CASCADE"), primary_key=True
        )
    )
    # SHA-256 hex of the token. The token itself is never stored.
    token_hash: str = Field(unique=True, index=True, max_length=64)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
