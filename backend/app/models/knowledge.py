"""Knowledge graph edge model for the KnowledgeAgent module.

Stores weighted relationships between medical entities (symptoms, diseases, drugs)
for graph-enhanced retrieval and learning from doctor decisions.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class KnowledgeEdge(Base):
    """Weighted relationship between two medical entities (e.g., symptom -> disease)."""

    __tablename__ = "knowledge_edges"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ── Source entity ──
    source_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
        comment="Entity type: symptom / disease / drug / test",
    )
    source_value: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
        comment="Entity value, e.g. '发热', '肺炎'",
    )

    # ── Target entity ──
    target_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
        comment="Entity type: symptom / disease / drug / test",
    )
    target_value: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
        comment="Entity value, e.g. '肺炎', '血常规'",
    )

    # ── Relationship attributes ──
    edge_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="has_symptom",
        comment="Relationship type: has_symptom / treats / differential_of / suggests_test",
    )
    weight: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0,
        comment="Association strength (0~1)",
    )
    occurrence_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1,
        comment="Number of times this relationship has been observed",
    )

    # ── Metadata ──
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, default="manual",
        comment='Data source: manual / learned / guideline / literature',
    )
    reference: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Reference citation or URL",
    )

    # ── Timestamps ──
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
