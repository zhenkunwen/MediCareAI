"""Doctor endpoints for patient management and case review.

Provides:
- Dashboard stats
- Patient list
- Case detail with Agent summary
- Natural language instructions
"""

from __future__ import annotations

import uuid
from typing import Any
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUserContext, require_role
from app.db.session import get_db
from app.models.agent import AgentSession
from app.models.medical_case import MedicalCase, CaseStatus
from app.models.user import User, UserRole
from app.schemas.medical_case import MedicalCaseResponse
from app.schemas.patient import CarePlanCreate, CarePlanResponse, CareTaskResponse
from app.services.care_plan_service import create_care_plan
from app.services.profile_service import parse_json_field
from app.services.agents import PlanningAgent

router = APIRouter()


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class DoctorStatsResponse:
    """Dashboard statistics for doctor."""

    pending_count: int
    new_messages: int
    followup_due: int
    data_shares: int


class PatientSummaryResponse:
    """Patient summary for doctor list."""

    id: str
    name: str
    avatar: str | None
    last_activity: str
    agent_summary: str
    status: str
    risk_level: str | None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/stats")
async def get_dashboard_stats(
    ctx: CurrentUserContext,
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Get doctor dashboard statistics."""
    if not ctx.user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    from app.models.message import MedicalConversation

    # Pending cases
    stmt = select(func.count(MedicalCase.id)).where(
        MedicalCase.assigned_doctor_id == ctx.user.id,
        MedicalCase.status == CaseStatus.PENDING_REVIEW
    )
    result = await db.execute(stmt)
    pending_count = result.scalar() or 0

    # Unread messages from patients (doctor_unread > 0)
    stmt2 = select(func.count(MedicalConversation.id)).where(
        MedicalConversation.doctor_id == ctx.user.id,
        MedicalConversation.doctor_unread > 0,
        MedicalConversation.doctor_deleted_at.is_(None),
    )
    result2 = await db.execute(stmt2)
    new_messages = result2.scalar() or 0

    # Follow-ups due (cases with follow_up_due_at <= today, not resolved)
    from datetime import date, datetime
    today_end = datetime.combine(date.today(), datetime.max.time())
    stmt3 = select(func.count(MedicalCase.id)).where(
        MedicalCase.assigned_doctor_id == ctx.user.id,
        MedicalCase.follow_up_due_at <= today_end,
        MedicalCase.status != CaseStatus.ARCHIVED,
    )
    result3 = await db.execute(stmt3)
    followup_due = result3.scalar() or 0

    return {
        "pending_count": pending_count,
        "new_messages": new_messages,
        "followup_due": followup_due,
    }


@router.get("/cases")
async def list_doctor_cases(
    ctx: CurrentUserContext,
    db: AsyncSession = Depends(get_db),
    status_filter: str | None = Query(None, alias="status"),
    search: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> list[dict[str, Any]]:
    """List patients/cases for doctor."""
    if not ctx.user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    stmt = select(MedicalCase).where(
        MedicalCase.assigned_doctor_id == ctx.user.id
    ).order_by(MedicalCase.updated_at.desc()).offset(skip).limit(limit)

    if status_filter:
        try:
            stmt = stmt.where(MedicalCase.status == CaseStatus(status_filter))
        except ValueError:
            pass

    result = await db.execute(stmt)
    cases = result.scalars().all()

    patients = []
    for case in cases:
        # Get patient info
        patient_stmt = select(User).where(User.id == case.patient_id)
        patient_result = await db.execute(patient_stmt)
        patient = patient_result.scalar_one_or_none()

        # Get latest Agent session for summary
        session_stmt = select(AgentSession).where(
            AgentSession.user_id == case.patient_id
        ).order_by(AgentSession.created_at.desc()).limit(1)
        session_result = await db.execute(session_stmt)
        latest_session = session_result.scalar_one_or_none()

        agent_summary = ""
        if latest_session and latest_session.structured_output:
            so = latest_session.structured_output
            if isinstance(so, dict):
                agent_summary = so.get("primary_diagnosis", "") or so.get("summary", "")
            else:
                agent_summary = str(so)
        if not agent_summary:
            agent_summary = case.description[:100] + "..." if case.description else "暂无摘要"
        agent_summary = agent_summary[:80] + "..." if len(agent_summary) > 80 else agent_summary

        patients.append({
            "id": str(case.id),
            "name": patient.full_name if patient else "未知患者",
            "avatar": None,
            "last_activity": (case.updated_at.isoformat() if case.updated_at else "") + ("Z" if case.updated_at and case.updated_at.tzinfo is None else ""),
            "agent_summary": agent_summary,
            "status": case.status.value if case.status else "pending",
            "risk_level": "medium",  # TODO: calculate from case data
        })

    return patients


@router.get("/cases/{case_id}")
async def get_case_detail(
    case_id: str,
    request: Request,
    ctx: CurrentUserContext,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get detailed case information for doctor review."""
    if not ctx.user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    import uuid
    stmt = select(MedicalCase).where(MedicalCase.id == uuid.UUID(case_id))
    result = await db.execute(stmt)
    case = result.scalar_one_or_none()

    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Audit log: doctor viewed a case
    try:
        from app.models.audit import AuditLog, AuditActionType, AuditResourceType
        audit = AuditLog(
            user_id=ctx.user.id,
            user_email=ctx.user.email,
            user_role=ctx.user.role.value,
            action=AuditActionType.CASE_VIEW,
            resource_type=AuditResourceType.CASE,
            resource_id=case_id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        db.add(audit)
        await db.commit()
    except Exception as e:
        import logging
        logging.getLogger("doctor").warning("[Audit] Failed to log case view: %s", e)

    # Get patient info
    patient_stmt = select(User).where(User.id == case.patient_id)
    patient_result = await db.execute(patient_stmt)
    patient = patient_result.scalar_one_or_none()

    # Get Agent sessions for this patient
    session_stmt = select(AgentSession).where(
        AgentSession.user_id == case.patient_id
    ).order_by(AgentSession.created_at.desc())
    session_result = await db.execute(session_stmt)
    sessions = session_result.scalars().all()

    # Build timeline from sessions
    _type_labels = {"diagnosis": "AI诊断", "consultation": "问诊", "conversation": "对话", "planning": "计划", "monitoring": "监测"}
    timeline = []
    for session in sessions:
        _type = session.session_type.value if session.session_type else "unknown"
        timeline.append({
            "time": (session.created_at.isoformat() if session.created_at else "") + ("Z" if session.created_at and session.created_at.tzinfo is None else ""),
            "type": _type_labels.get(_type, _type),
            "intent": session.intent,
            "summary": (session.structured_output.get("primary_diagnosis", "") if isinstance(session.structured_output, dict) else "") or session.intent or "",
        })

    # Get comments
    from app.models.medical_case import MedicalCaseComment
    _c_stmt = select(MedicalCaseComment).where(
        MedicalCaseComment.case_id == uuid.UUID(case_id)
    ).order_by(MedicalCaseComment.created_at)
    _c_result = await db.execute(_c_stmt)
    _comments = [
        {
            "id": str(cc.id),
            "author": cc.author_name,
            "content": cc.content,
            "created_at": (cc.created_at.isoformat() if cc.created_at else "") + ("Z" if cc.created_at and cc.created_at.tzinfo is None else ""),
        }
        for cc in _c_result.scalars().all()
    ]

    # Get patient health profile
    _patient_info = {"age": None, "gender": None, "height": None, "weight": None, "allergies": [], "bloodType": None}
    try:
        from app.models.patient_profile import HealthProfile
        _hp = await db.get(HealthProfile, case.patient_id)
        if _hp:
            _age = None
            if _hp.date_of_birth:
                from datetime import date
                _age = date.today().year - _hp.date_of_birth.year
            from app.services.profile_service import parse_json_field
            _patient_info = {
                "age": _age,
                "gender": {"male": "男", "female": "女", "other": "其他", "prefer_not_to_say": "保密"}.get(_hp.gender.value, _hp.gender.value) if _hp.gender else None,
                "height": f"{_hp.height}cm" if _hp.height else None,
                "weight": f"{_hp.weight}kg" if _hp.weight else None,
                "allergies": parse_json_field(_hp.allergies) if hasattr(_hp, 'allergies') else [],
                "bloodType": _hp.blood_type.value if _hp.blood_type else None,
            }
    except Exception:
        pass

    return {
        "id": str(case.id),
        "patient_id": str(case.patient_id),
        "patient_info": _patient_info,
        "patient_name": patient.full_name if patient else "Unknown",
        "title": case.title,
        "description": case.description,
        "diagnosis": case.doctor_diagnosis or case.ai_diagnosis_summary,
        "agent_summary": case.ai_diagnosis_summary or "",
        "structured_report": case.ai_diagnosis_summary,
        "status": case.status.value if case.status else "pending",
        "comments": _comments,
        "timeline": timeline,
        "created_at": (case.created_at.isoformat() if case.created_at else "") + ("Z" if case.created_at and case.created_at.tzinfo is None else ""),
        "updated_at": (case.updated_at.isoformat() if case.updated_at else "") + ("Z" if case.updated_at and case.updated_at.tzinfo is None else ""),
    }


@router.post("/cases/{case_id}/comment")
async def add_case_comment(
    case_id: str,
    body: dict[str, str],
    ctx: CurrentUserContext,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Add a comment to a case."""
    if not ctx.user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    from app.models.medical_case import MedicalCaseComment
    comment = MedicalCaseComment(
        case_id=uuid.UUID(case_id),
        author_id=ctx.user.id,
        author_name=ctx.user.full_name or "医生",
        content=body.get("content", ""),
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return {
        "id": str(comment.id),
        "author": comment.author_name,
        "content": comment.content,
        "created_at": comment.created_at.isoformat() + "Z" if comment.created_at and comment.created_at.tzinfo is None else (comment.created_at.isoformat() if comment.created_at else ""),
    }


@router.post("/cases/{case_id}/plan")
async def send_plan_instruction(
    case_id: str,
    instruction: dict[str, str],
    ctx: CurrentUserContext,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Send natural language instruction to Agent for case planning.

    Uses PlanningAgent to parse the doctor's instruction into a structured
    treatment plan, then creates a real CarePlan + CareTasks in the database.
    """
    if not ctx.user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    import uuid as _uuid

    # Fetch the case
    case = await db.get(MedicalCase, _uuid.UUID(case_id))
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Get patient info for context
    patient = await db.get(User, case.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    # Build diagnosis context for the PlanningAgent
    diag_context = (
        f"病例标题: {case.title or ''}\n"
        f"主诉: {case.chief_complaint or ''}\n"
        f"AI诊断: {case.ai_diagnosis_summary or ''}\n"
        f"医生指令: {instruction.get('instruction', '')}"
    )

    # Build patient profile context
    profile_context = {"name": patient.full_name, "age": None, "gender": None}
    try:
        from app.models.patient_profile import HealthProfile
        hp = await db.get(HealthProfile, case.patient_id)
        if hp:
            from datetime import date as _dt
            profile_context["age"] = _dt.today().year - hp.date_of_birth.year if hp.date_of_birth else None
            profile_context["gender"] = hp.gender.value if hp.gender else None
    except Exception:
        pass

    # Call PlanningAgent to parse the instruction
    agent = PlanningAgent(provider=None)
    result = await agent.plan(
        diagnosis=diag_context,
        patient_profile=profile_context,
    )

    if not result.structured_output:
        raise HTTPException(
            status_code=500,
            detail="AI 未能解析指令，请重试或稍后再试",
        )

    plan_data = result.structured_output

    # Build task list from structured output
    tasks = []
    for a in (plan_data.non_pharmacological or [])[:5]:
        tasks.append({"description": a})
    for s in (plan_data.follow_up_schedule or []):
        desc = s.get("action") or s.get("description", "")
        if desc:
            tasks.append({"description": desc})

    # Create actual CarePlan in the database
    from datetime import date as _today_date
    plan = await create_care_plan(
        db, case.patient_id,
        title=plan_data.title or f"诊疗计划 - {(case.title or '')[:30]}",
        goals=plan_data.goals or None,
        start_date=_today_date.today(),
        task_defs=tasks or None,
    )

    return {
        "tasks_created": [
            {
                "description": t.description,
                "due_date": t.due_date.isoformat() if t.due_date else None,
            }
            for t in plan.tasks
        ],
        "message": "已根据您的指令创建诊疗计划",
    }


@router.post("/patients/{patient_id}/care-plans", response_model=CarePlanResponse, status_code=201)
async def create_patient_care_plan(
    patient_id: str,
    body: CarePlanCreate,
    ctx: CurrentUserContext,
    db: AsyncSession = Depends(get_db),
) -> CarePlanResponse:
    """Doctor creates a care plan for a patient."""
    if not ctx.user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Verify patient exists
    import uuid
    pid = uuid.UUID(patient_id)
    patient = await db.get(User, pid)
    if not patient or patient.role != UserRole.PATIENT:
        raise HTTPException(status_code=404, detail="Patient not found")

    plan = await create_care_plan(
        db, pid,
        title=body.title,
        goals=body.goals or None,
        start_date=body.start_date,
        end_date=body.end_date,
        task_defs=[t.model_dump() for t in body.tasks] if body.tasks else None,
    )
    tasks = [CareTaskResponse.model_validate(t) for t in plan.tasks]
    return CarePlanResponse(
        id=plan.id,
        title=plan.title,
        goals=parse_json_field(plan.goals),
        status=plan.status,
        start_date=plan.start_date,
        end_date=plan.end_date,
        tasks=tasks,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


# ── Notifications ────────────────────────────────────────────────


@router.get("/notifications")
async def list_doctor_notifications(
    ctx: CurrentUserContext,
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """List notifications for the current doctor."""
    if not ctx.user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    from app.models.notification import Notification
    stmt = (
        select(Notification)
        .where(Notification.recipient_id == ctx.user.id, Notification.recipient_deleted == False)
        .order_by(Notification.created_at.desc())
        .offset(skip).limit(limit)
    )
    result = await db.execute(stmt)
    notifications = result.scalars().all()
    unread = sum(1 for n in notifications if not n.is_read)
    return {
        "items": [
            {
                "id": str(n.id),
                "type": n.notification_type.value if n.notification_type else "info",
                "priority": n.priority.value if n.priority else "medium",
                "message": n.content or n.subject or "",
                "link": n.action_url,
                "read": n.is_read,
                "time": (n.created_at.isoformat() if n.created_at else "") + ("Z" if n.created_at and n.created_at.tzinfo is None else ""),
            }
            for n in notifications
        ],
        "unread": unread,
        "total": len(notifications),
    }


@router.put("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    ctx: CurrentUserContext,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Mark a notification as read."""
    if not ctx.user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    from app.models.notification import Notification
    n = await db.get(Notification, uuid.UUID(notification_id))
    if not n or n.recipient_id != ctx.user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    n.is_read = True
    await db.commit()
    return {"status": "ok"}


# ── Work Stats ──────────────────────────────────────────────────


@router.get("/stats/work")
async def get_work_stats(
    ctx: CurrentUserContext,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Work statistics for doctor dashboard."""
    if not ctx.user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    from datetime import date, timedelta
    from app.models.medical_case import CaseStatus

    today = date.today()
    week_start = today - timedelta(days=today.weekday())

    stmt = select(MedicalCase).where(MedicalCase.assigned_doctor_id == ctx.user.id)
    result = await db.execute(stmt)
    all_cases = result.scalars().all()

    today_count = sum(1 for c in all_cases if c.created_at and c.created_at.date() == today)
    week_cases = [c for c in all_cases if c.created_at and c.created_at.date() >= week_start]
    completed = sum(1 for c in all_cases if c.status == CaseStatus.RESOLVED or c.status == CaseStatus.ARCHIVED)
    pending = sum(1 for c in all_cases if c.status == CaseStatus.PENDING_REVIEW)

    # Common diagnoses (from linked sessions' structured_output)
    from collections import Counter
    diag_counter: Counter = Counter()
    for c in all_cases:
        try:
            _stmt2 = select(AgentSession.structured_output).where(AgentSession.id == c.source_session_id)
            _r2 = await db.execute(_stmt2)
            _so = _r2.scalar_one_or_none()
            if _so and isinstance(_so, dict):
                _pd = _so.get("primary_diagnosis", "")
                if _pd:
                    # Use the first diagnosis before any / separator
                    _main = _pd.split("/")[0].split("、")[0][:20]
                    if _main:
                        diag_counter[_main] += 1
        except Exception:
            pass

    common_diagnoses = [
        {"diagnosis": d, "count": c}
        for d, c in diag_counter.most_common(10)
    ]

    return {
        "today_count": today_count,
        "week_count": len(week_cases),
        "pending_count": pending,
        "completed_count": completed,
        "total_count": len(all_cases),
        "common_diagnoses": common_diagnoses,
    }
