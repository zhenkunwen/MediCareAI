"""Mobile API endpoints for Android App integration."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUserContext, get_current_user_or_guest, require_role
from app.db.session import get_db
from app.models.agent import AgentSession, AgentSessionStatus
from app.models.medical_case import MedicalCase
from app.models.user import User, UserRole
from app.schemas.medical_case import MedicalCaseResponse

router = APIRouter()


@router.post(
    "/login",
    summary="手机号登录（Android App）",
)
async def mobile_login(
    phone: str,
    code: str,
    db: AsyncSession = Depends(get_db),
):
    """Login or register via phone number and verification code.

    In production, this would validate the SMS code via Aliyun SMS service.
    For development, any 6-digit code is accepted.
    """
    if not phone or not code:
        raise HTTPException(status_code=422, detail="Phone and code required")

    # Find or create user by phone
    stmt = select(User).where(User.phone == phone)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        # Auto-create patient account
        user = User(
            phone=phone,
            full_name=f"用户{phone[-4:]}",
            role=UserRole.PATIENT,
            status="active",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    # Generate JWT
    from app.core.security import create_access_token
    token = create_access_token(
        data={"sub": str(user.id), "type": "access", "role": user.role.value},
    )

    return {
        "patientId": str(user.id),
        "token": token,
        "name": user.full_name,
    }


@router.post(
    "/consultation/start",
    summary="发起问诊（Android App）",
)
async def start_consultation(
    patient_id: str,
    symptoms: str,
    ctx: CurrentUserContext,
    voice_data: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Start a new AI consultation from the mobile app.

    Creates an AgentSession and triggers the diagnosis workflow.
    """
    # TODO: In production, dispatch to AgentOrchestrator
    # For now, create a placeholder session
    session = AgentSession(
        user_id=uuid.UUID(patient_id) if ctx.user else None,
        session_type="diagnosis",
        intent="diagnosis",
        status=AgentSessionStatus.ACTIVE,
        context={"symptoms": symptoms, "voice_data": bool(voice_data)},
    )
    db.add(session)
    await db.commit()

    return {
        "consultation_id": str(session.id),
        "status": "processing",
        "message": "AI分析中...",
    }


@router.get(
    "/consultation/result/{consultation_id}",
    summary="获取问诊结果（Android App）",
)
async def get_consultation_result(
    consultation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get the diagnosis result for a consultation."""
    stmt = select(AgentSession).where(AgentSession.id == uuid.UUID(consultation_id))
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Consultation not found")

    structured = session.structured_output or {}

    return {
        "consultation_id": consultation_id,
        "status": session.status.value if session.status else "processing",
        "diagnosis": {
            "primary_diagnosis": structured.get("primary_diagnosis", ""),
            "confidence": structured.get("confidence", "medium"),
            "differential_diagnoses": structured.get("differential_diagnoses", []),
            "key_findings": structured.get("key_findings", []),
            "recommended_tests": structured.get("recommended_tests", []),
            "recommended_actions": structured.get("recommended_actions", []),
        },
        "created_at": session.created_at.isoformat() if session.created_at else "",
    }


@router.get(
    "/patient/history",
    summary="获取患者历史问诊记录（Android App）",
)
async def get_patient_history(
    patient_id: str,
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Get a patient's consultation history."""
    stmt = (
        select(MedicalCase)
        .where(MedicalCase.patient_id == uuid.UUID(patient_id))
        .order_by(MedicalCase.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    cases = result.scalars().all()

    return [
        {
            "case_id": str(c.id),
            "chief_complaint": c.chief_complaint,
            "diagnosis": c.doctor_diagnosis or c.ai_diagnosis_summary,
            "status": c.status.value if c.status else "unknown",
            "created_at": c.created_at.isoformat() if c.created_at else "",
        }
        for c in cases
    ]
