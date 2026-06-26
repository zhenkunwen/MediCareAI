"""DoctorDecisionService — handles the doctor review and finalization workflow."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.doctor_decision import (
    ConsultationStatus,
    FinalDiagnosis,
    PendingConsultation,
)
from app.models.medical_case import MedicalCase, CaseStatus
from app.models.user import User


logger = logging.getLogger(__name__)


class DoctorDecisionService:
    """Service for doctor consultation management and final decision recording."""

    @staticmethod
    async def get_pending_consultations(
        doctor_id: uuid.UUID,
        db: AsyncSession,
    ) -> list[dict]:
        """Get all pending consultations assigned to a doctor, with patient info."""
        stmt = (
            select(PendingConsultation)
            .where(
                PendingConsultation.doctor_id == doctor_id,
                PendingConsultation.status == ConsultationStatus.PENDING_DOCTOR_REVIEW,
            )
            .options(joinedload(PendingConsultation.medical_case))
            .order_by(desc(PendingConsultation.created_at))
        )
        result = await db.execute(stmt)
        consultations = result.unique().scalars().all()

        items = []
        for c in consultations:
            # Get patient name
            patient_stmt = select(User).where(User.id == c.patient_id)
            patient_result = await db.execute(patient_stmt)
            patient = patient_result.scalar_one_or_none()

            items.append({
                "consultation_id": str(c.id),
                "case_id": str(c.case_id),
                "patient_id": str(c.patient_id),
                "patient_name": patient.full_name if patient else "未知患者",
                "chief_complaint": c.chief_complaint or "",
                "pre_diagnosis": c.pre_diagnosis,
                "vitals": c.vitals or {},
                "allergies": c.allergies or [],
                "status": c.status.value,
                "created_at": c.created_at.isoformat() if c.created_at else "",
            })

        return items

    @staticmethod
    async def finalize_consultation(
        consultation_id: uuid.UUID,
        doctor_id: uuid.UUID,
        final_diagnosis: str,
        icd11_code: str | None,
        treatment_plan: dict | None,
        doctor_notes: str | None,
        physical_exam: dict | None,
        rejected_suggestions: list[str] | None,
        db: AsyncSession,
    ) -> dict:
        """Record a doctor's final diagnosis and update related records."""
        # 1. Load the pending consultation
        stmt = (
            select(PendingConsultation)
            .where(PendingConsultation.id == consultation_id)
            .with_for_update()  # Optimistic lock
        )
        result = await db.execute(stmt)
        consultation = result.scalar_one_or_none()

        if not consultation:
            raise ValueError("Consultation not found")

        if consultation.status != ConsultationStatus.PENDING_DOCTOR_REVIEW:
            raise ValueError(f"Consultation already {consultation.status.value}")

        # 2. Create FinalDiagnosis record
        final = FinalDiagnosis(
            consultation_id=consultation_id,
            case_id=consultation.case_id,
            doctor_id=doctor_id,
            final_diagnosis=final_diagnosis,
            icd11_code=icd11_code,
            treatment_plan=treatment_plan,
            doctor_notes=doctor_notes,
            physical_exam=physical_exam,
            rejected_suggestions=rejected_suggestions,
        )
        db.add(final)

        # 3. Update consultation status
        consultation.status = ConsultationStatus.CONFIRMED

        # 4. Update MedicalCase
        case_stmt = select(MedicalCase).where(MedicalCase.id == consultation.case_id)
        case_result = await db.execute(case_stmt)
        case = case_result.scalar_one_or_none()

        if case:
            case.doctor_diagnosis = final_diagnosis
            case.doctor_notes = doctor_notes
            case.treatment_plan = treatment_plan
            case.status = CaseStatus.RESOLVED
            case.resolved_at = datetime.utcnow()

        await db.commit()

        # 5. Trigger async knowledge learning via Celery
        try:
            from app.tasks.doctor import trigger_learning_from_finalization
            trigger_learning_from_finalization.delay(
                consultation_id=str(consultation_id),
                final_diagnosis=final_diagnosis,
                icd11_code=icd11_code,
            )
        except Exception as e:
            logger.warning("Failed to trigger knowledge learning task: %s", e)

        return {
            "status": "recorded",
            "consultation_id": str(consultation_id),
        }

    @staticmethod
    async def get_consultation_history(
        doctor_id: uuid.UUID,
        limit: int = 20,
        consultation_id: uuid.UUID | None = None,
        db: AsyncSession | None = None,
    ) -> list[dict]:
        """Get doctor's finalization history for knowledge learning."""
        stmt = select(FinalDiagnosis).where(
            FinalDiagnosis.doctor_id == doctor_id,
        )
        if consultation_id:
            stmt = stmt.where(FinalDiagnosis.consultation_id == consultation_id)
        stmt = stmt.order_by(desc(FinalDiagnosis.created_at)).limit(limit)
        result = await db.execute(stmt)
        records = result.scalars().all()

        return [
            {
                "consultation_id": str(r.consultation_id),
                "case_id": str(r.case_id),
                "doctor_id": str(r.doctor_id),
                "final_diagnosis": r.final_diagnosis,
                "icd11_code": r.icd11_code,
                "treatment_plan": r.treatment_plan,
                "doctor_notes": r.doctor_notes,
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
            for r in records
        ]
