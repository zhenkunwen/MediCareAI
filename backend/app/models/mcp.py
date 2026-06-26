"""MCP (Medical Collaboration Protocol) models for external system integration."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class MCPSubscription(Base):
    """Webhook subscription for external HIS system callbacks."""

    __tablename__ = "mcp_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    external_system: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="Name of the external HIS system",
    )
    callback_url: Mapped[str] = mapped_column(
        String(500), nullable=False,
        comment="Webhook callback URL",
    )
    events: Mapped[dict] = mapped_column(
        JSONB, nullable=False,
        comment="List of event types to subscribe to",
    )
    secret_encrypted: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Encrypted secret for HMAC signing",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )


class MCPAuditLog(Base):
    """Audit trail for MCP operations."""

    __tablename__ = "mcp_audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    operation: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="Operation type: fetch_records / push_diagnosis / subscribe",
    )
    external_patient_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
        comment="Patient ID in external system",
    )
    request_summary: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Summary of the request",
    )
    response_summary: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Summary of the response",
    )
    status: Mapped[str] = mapped_column(
        String(20), default="success",
        comment="success / failed",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
