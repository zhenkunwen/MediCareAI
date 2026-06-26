"""Patient profile, care plan, and care task models.

HealthProfile: one-to-one with User, stores medical metadata as JSON fields.
CarePlan: a follow-up plan with goals and a state machine.
CareTask: individual tasks within a care plan with automatic expiry.
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


# ── Enums ──────────────────────────────────────────────────────────────


class GenderEnum(str, PyEnum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class BloodTypeEnum(str, PyEnum):
    A = "A"
    B = "B"
    AB = "AB"
    O = "O"
    RH_POSITIVE = "Rh+"
    RH_NEGATIVE = "Rh-"
    UNKNOWN = "未知"


class PlanStatusEnum(str, PyEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskStatusEnum(str, PyEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    EXPIRED = "expired"


# ── Health Profile ─────────────────────────────────────────────────────


class HealthProfile(Base):
    """One-to-one patient health profile."""

    __tablename__ = "health_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    date_of_birth: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    gender: Mapped[GenderEnum | None] = mapped_column(
        Enum(GenderEnum, name="gender_enum"), nullable=True
    )
    height: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    weight: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    blood_type: Mapped[BloodTypeEnum | None] = mapped_column(
        Enum(BloodTypeEnum, name="blood_type_enum"), nullable=True
    )
    allergies: Mapped[list] = mapped_column(
        # SQLite → TEXT, PG → JSONB; SQLAlchemy handles the abstraction
        Text().with_variant(String, "sqlite"),
        default='[]',
        server_default="[]",
    )
    chronic_diseases: Mapped[list] = mapped_column(
        Text().with_variant(String, "sqlite"),
        default='[]',
        server_default="[]",
    )
    medications: Mapped[list] = mapped_column(
        Text().with_variant(String, "sqlite"),
        default='[]',
        server_default="[]",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationship back to User (uselist=False since one-to-one)
    user: Mapped["User"] = relationship(  # noqa: F821
        "User", backref=__tablename__, uselist=False
    )


# ── Care Plan ──────────────────────────────────────────────────────────


class CarePlan(Base):
    """A patient's follow-up or care plan."""

    __tablename__ = "care_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    goals: Mapped[list] = mapped_column(
        Text().with_variant(String, "sqlite"),
        default='[]',
        server_default="[]",
    )
    status: Mapped[PlanStatusEnum] = mapped_column(
        Enum(PlanStatusEnum, name="plan_status_enum"),
        default=PlanStatusEnum.ACTIVE,
        nullable=False,
    )
    start_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    end_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    patient: Mapped["User"] = relationship("User", backref="care_plans")  # noqa: F821
    tasks: Mapped[list["CareTask"]] = relationship(
        "CareTask", back_populates="plan", cascade="all, delete-orphan",
        order_by="CareTask.order",
    )


# ── Care Task ──────────────────────────────────────────────────────────


class CareTask(Base):
    """An individual task within a care plan."""

    __tablename__ = "care_tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("care_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    due_date: Mapped[datetime] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[TaskStatusEnum] = mapped_column(
        Enum(TaskStatusEnum, name="task_status_enum"),
        default=TaskStatusEnum.PENDING,
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    order: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    plan: Mapped["CarePlan"] = relationship("CarePlan", back_populates="tasks")


# ── Medication Reminder ────────────────────────────────────────────────


class ReminderLogStatus(str, PyEnum):
    """Status for a single reminder send attempt."""
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    DEAD = "dead"


class MedicationReminder(Base):
    """A medication the patient needs to take on a schedule."""

    __tablename__ = "medication_reminders"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    dosage: Mapped[str] = mapped_column(String(100), nullable=False)
    frequency: Mapped[str] = mapped_column(String(100), nullable=False)
    time_slots: Mapped[list] = mapped_column(
        Text().with_variant(String, "sqlite"),
        default='[]',
        server_default="[]",
    )
    start_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    end_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    status: Mapped[PlanStatusEnum] = mapped_column(
        Enum(PlanStatusEnum, name="plan_status_enum"),
        default=PlanStatusEnum.ACTIVE,
        nullable=False,
    )
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Reminder settings
    lead_minutes: Mapped[int] = mapped_column(Integer, default=15, server_default="15")
    remind_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    last_reminded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reminded_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    patient: Mapped["User"] = relationship("User", backref="medication_reminders")  # noqa: F821


class MedicationReminderLog(Base):
    """Record of each reminder send attempt (SMS/SSE)."""

    __tablename__ = "medication_reminder_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    record_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("medication_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    phone: Mapped[str] = mapped_column(String(50), nullable=False)
    reminder_plan_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    scheduled_time: Mapped[str] = mapped_column(String(5), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[ReminderLogStatus] = mapped_column(
        Enum(ReminderLogStatus, name="reminder_log_status_enum"),
        default=ReminderLogStatus.PENDING,
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class MedicationRecord(Base):
    """A single dose record — taken, skipped, or pending."""

    __tablename__ = "medication_records"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    reminder_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("medication_reminders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scheduled_date: Mapped[datetime] = mapped_column(Date, nullable=False, index=True)
    scheduled_time: Mapped[str] = mapped_column(String(5), nullable=False)
    taken_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[TaskStatusEnum] = mapped_column(
        Enum(TaskStatusEnum, name="task_status_enum"),
        default=TaskStatusEnum.PENDING,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    reminder: Mapped["MedicationReminder"] = relationship("MedicationReminder")
