"""Doctor decision models for the DoctorAgent module.

Stores pre-diagnosis results pending doctor review and final diagnosis records
used for knowledge base learning.
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class ConsultationStatus(str, PyEnum):
    PENDING_DOCTOR_REVIEW = "pending_doctor_review"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class PendingConsultation(Base):
    """Pre-diagnosis result from DiagnosisAgent awaiting doctor review."""

    __tablename__ = "pending_consultations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ── Ownership & Assignment ──
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("medical_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Medical case this consultation belongs to",
    )
    doctor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Assigned doctor for review",
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Patient who owns this consultation",
    )

    # ── Clinical Data ──
    pre_diagnosis: Mapped[dict] = mapped_column(
        JSONB, nullable=False,
        comment="PreDiagnosis structure: possible_diseases, suggested_tests, urgency",
    )
    vitals: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="Vital signs at time of consultation (temperature, BP, HR, etc.)",
    )
    chief_complaint: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Patient's chief complaint",
    )
    allergies: Mapped[list | None] = mapped_column(
        JSONB, nullable=True,
        comment="Known allergies",
    )

    # ── Status ──
    status: Mapped[ConsultationStatus] = mapped_column(
        Enum(ConsultationStatus),
        default=ConsultationStatus.PENDING_DOCTOR_REVIEW,
        nullable=False,
        index=True,
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

    # ── Relationships ──
    medical_case: Mapped["MedicalCase"] = relationship(
        "MedicalCase",
        foreign_keys=[case_id],
        lazy="selectin",
    )


class FinalDiagnosis(Base):
    """Doctor-confirmed final diagnosis record for knowledge learning."""

    __tablename__ = "final_diagnoses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ── Ownership & Assignment ──
    consultation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pending_consultations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True,
        comment="Reference to the pending consultation",
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("medical_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Medical case this diagnosis belongs to",
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
        index=True,
        comment="Doctor who made the final diagnosis",
    )

    # ── Clinical Data ──
    final_diagnosis: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="Doctor-confirmed diagnosis text",
    )
    icd11_code: Mapped[str | None] = mapped_column(
        String(20), nullable=True,
        comment="ICD-11 code",
    )
    treatment_plan: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="Treatment plan: medications, advice, follow-up",
    )
    doctor_notes: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Doctor's clinical notes and remarks",
    )
    physical_exam: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="Physical examination findings",
    )
    rejected_suggestions: Mapped[list | None] = mapped_column(
        JSONB, nullable=True,
        comment="Pre-diagnosis items the doctor rejected",
    )

    # ── Timestamps ──
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    # ── Relationships ──
    consultation: Mapped["PendingConsultation"] = relationship(
        "PendingConsultation",
        foreign_keys=[consultation_id],
        lazy="selectin",
    )
    medical_case: Mapped["MedicalCase"] = relationship(
        "MedicalCase",
        foreign_keys=[case_id],
        lazy="selectin",
    )
