"""Doctor consultation endpoints for the DoctorAgent module.

Provides:
- Pending consultation listing for doctor review
- Final diagnosis submission
- Consultation history for knowledge learning
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.db.session import get_db
from app.models.user import UserRole
from app.schemas.doctor_decision import (
    ConsultationHistoryListResponse,
    ConsultationHistoryItem,
    FinalizeDiagnosisRequest,
    FinalizeDiagnosisResponse,
    PendingConsultationItem,
    PendingConsultationListResponse,
    PreDiagnosisDetail,
)
from app.services.doctor_decision import DoctorDecisionService

router = APIRouter()


@router.get(
    "/consultations/pending",
    response_model=PendingConsultationListResponse,
    summary="获取待医生决策的诊断建议",
)
async def get_pending_consultations(
    doctor: dict = Depends(require_role(UserRole.DOCTOR)),
    db: AsyncSession = Depends(get_db),
):
    """Get all pending consultations awaiting doctor review."""
    items = await DoctorDecisionService.get_pending_consultations(
        doctor_id=doctor.id,
        db=db,
    )
    # Convert raw dicts to Pydantic models
    consultations = []
    for item in items:
        pre_diag = item.get("pre_diagnosis", {})
        pre_diagnosis_detail = PreDiagnosisDetail(
            possible_diseases=pre_diag.get("possible_diseases", []),
            suggested_tests=pre_diag.get("suggested_tests", []),
            urgency=pre_diag.get("urgency", "medium"),
        )
        consultations.append(
            PendingConsultationItem(
                consultation_id=uuid.UUID(item["consultation_id"]),
                case_id=uuid.UUID(item["case_id"]),
                patient_id=uuid.UUID(item["patient_id"]),
                patient_name=item["patient_name"],
                chief_complaint=item["chief_complaint"],
                pre_diagnosis=pre_diagnosis_detail,
                vitals=item.get("vitals"),
                allergies=item.get("allergies", []),
                status=item["status"],
                created_at=item["created_at"],
            )
        )
    return PendingConsultationListResponse(consultations=consultations)


@router.post(
    "/consultations/finalize",
    response_model=FinalizeDiagnosisResponse,
    summary="提交医生最终决策",
)
async def finalize_consultation(
    request: FinalizeDiagnosisRequest,
    doctor: dict = Depends(require_role(UserRole.DOCTOR)),
    db: AsyncSession = Depends(get_db),
):
    """Submit doctor's final diagnosis and treatment plan."""
    try:
        result = await DoctorDecisionService.finalize_consultation(
            consultation_id=uuid.UUID(request.consultation_id),
            doctor_id=doctor.id,
            final_diagnosis=request.final_diagnosis,
            icd11_code=request.icd11_code,
            treatment_plan=(
                request.treatment_plan.model_dump()
                if request.treatment_plan else None
            ),
            doctor_notes=request.doctor_notes,
            physical_exam=(
                request.physical_exam.model_dump()
                if request.physical_exam else None
            ),
            rejected_suggestions=request.rejected_suggestions,
            db=db,
        )
        return FinalizeDiagnosisResponse(
            status=result["status"],
            consultation_id=result["consultation_id"],
        )
    except ValueError as e:
        # Check if 409 or 404
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=msg)


@router.get(
    "/decisions",
    response_model=ConsultationHistoryListResponse,
    summary="查询医生决策历史（用于学习）",
)
async def get_decision_history(
    doctor: dict = Depends(require_role(UserRole.DOCTOR)),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get doctor's decision history for knowledge learning."""
    history = await DoctorDecisionService.get_consultation_history(
        doctor_id=doctor.id,
        limit=limit,
        db=db,
    )
    records = [
        ConsultationHistoryItem(
            consultation_id=uuid.UUID(item["consultation_id"]),
            case_id=uuid.UUID(item["case_id"]),
            doctor_id=uuid.UUID(item["doctor_id"]),
            final_diagnosis=item["final_diagnosis"],
            icd11_code=item.get("icd11_code"),
            treatment_plan=item.get("treatment_plan"),
            doctor_notes=item.get("doctor_notes"),
            created_at=item["created_at"],
        )
        for item in history
    ]
    return ConsultationHistoryListResponse(records=records)
