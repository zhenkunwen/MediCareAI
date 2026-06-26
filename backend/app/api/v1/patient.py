"""Patient-facing endpoints: health profile, care plans, tasks, cases.

All endpoints require authenticated patient role.
"""

import json
import math
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, require_role
from app.db.session import get_db
from app.models.medical_case import MedicalCase
from app.models.message import MedicalConversation
from app.models.patient_profile import (
    CarePlan,
    CareTask,
    HealthProfile,
    MedicationReminder,
    PlanStatusEnum,
    TaskStatusEnum,
)
from app.models.user import UserRole
from app.schemas.patient import (
    AllergyOperation,
    CarePlanCreate,
    CarePlanListResponse,
    CarePlanResponse,
    CareTaskActionResponse,
    CareTaskResponse,
    CaseListResponse,
    CaseListResponseItem,
    HealthProfileResponse,
    HealthProfileUpdate,
    MedicationReminderCreate,
    MedicationReminderResponse,
    MedicationReminderUpdate,
    MedicationRecordResponse,
    PlanStatusUpdate,
    TaskListResponse,
    TodayMedicationItem,
    TodayMedicationResponse,
)
from app.services.care_plan_service import (
    complete_task,
    create_care_plan,
    get_care_plan,
    list_care_plans,
    list_tasks,
    mark_expired_tasks,
    skip_task,
    update_plan_status,
)
from app.services.medication_service import (
    create_reminder,
    delete_reminder,
    get_today_medications,
    list_reminders,
    skip_medication,
    take_medication,
    update_reminder,
)
from app.services.notification_bus import bus as notification_bus
from app.services.profile_service import (
    get_or_create_profile,
    parse_json_field,
    update_profile,
)

router = APIRouter(
    prefix="/patient",
    tags=["Patient"],
    dependencies=[Depends(require_role(UserRole.PATIENT))],
)


# ── Helpers ────────────────────────────────────────────────────────────


def _profile_to_response(p: HealthProfile) -> HealthProfileResponse:
    """Convert ORM profile to response, deserializing JSON fields."""
    return HealthProfileResponse(
        user_id=p.user_id,
        date_of_birth=p.date_of_birth,
        gender=p.gender,
        blood_type=p.blood_type,
        height=p.height,
        weight=p.weight,
        allergies=parse_json_field(p.allergies),
        chronic_diseases=parse_json_field(p.chronic_diseases),
        medications=parse_json_field(p.medications),
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


def _paginate(total: int, page: int, size: int) -> dict:
    pages = max(1, math.ceil(total / size)) if total > 0 else 0
    return {"total": total, "page": page, "size": size, "pages": pages}


# ── Profile ────────────────────────────────────────────────────────────


@router.get("/profile", response_model=HealthProfileResponse)
async def get_profile(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> HealthProfileResponse:
    """Get the patient's health profile. Auto-creates an empty one if missing."""
    profile = await get_or_create_profile(db, current_user.id)
    return _profile_to_response(profile)


@router.patch("/profile", response_model=HealthProfileResponse)
async def patch_profile(
    data: HealthProfileUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> HealthProfileResponse:
    """Partial-update the health profile."""
    profile = await update_profile(db, current_user.id, data)
    return _profile_to_response(profile)


@router.post("/profile/allergies", response_model=HealthProfileResponse)
async def add_allergy(
    body: AllergyOperation,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> HealthProfileResponse:
    """Atomically add a single allergy."""
    profile = await get_or_create_profile(db, current_user.id)
    current = parse_json_field(profile.allergies)
    if body.item not in current:
        current.append(body.item)
    profile.allergies = json.dumps(current, ensure_ascii=False)
    await db.commit()
    await db.refresh(profile)
    return _profile_to_response(profile)


@router.delete("/profile/allergies/{item}", response_model=HealthProfileResponse)
async def remove_allergy(
    item: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> HealthProfileResponse:
    """Atomically remove a single allergy."""
    profile = await get_or_create_profile(db, current_user.id)
    current = parse_json_field(profile.allergies)
    if item in current:
        current.remove(item)
    profile.allergies = json.dumps(current, ensure_ascii=False)
    await db.commit()
    await db.refresh(profile)
    return _profile_to_response(profile)


# ── Messages / Unread ──────────────────────────────────────────────────


@router.get("/messages/unread")
async def get_unread_messages(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Total unread conversation messages for the patient."""
    result = await db.execute(
        select(func.coalesce(func.sum(MedicalConversation.patient_unread), 0))
        .where(
            MedicalConversation.patient_id == current_user.id,
            MedicalConversation.status == "active",
        )
    )
    return {"unread_total": result.scalar_one() or 0}


# ── Cases ──────────────────────────────────────────────────────────────


@router.get("/cases", response_model=CaseListResponse)
async def list_my_cases(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> CaseListResponse:
    """List the patient's own medical cases (patient-visible fields only)."""
    offset = (page - 1) * size

    count_q = select(func.count(MedicalCase.id)).where(
        MedicalCase.patient_id == current_user.id
    )
    total = (await db.execute(count_q)).scalar() or 0

    rows = await db.execute(
        select(MedicalCase)
        .where(MedicalCase.patient_id == current_user.id)
        .order_by(MedicalCase.created_at.desc())
        .offset(offset)
        .limit(size)
    )
    cases = rows.scalars().all()

    items = [
        CaseListResponseItem(
            id=c.id,
            chief_complaint=c.chief_complaint,
            ai_diagnosis_summary=c.ai_diagnosis_summary,
            severity=c.severity,
            is_emergency=c.is_emergency,
            status=c.status.value if hasattr(c.status, "value") else str(c.status),
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in cases
    ]
    return CaseListResponse(items=items, **_paginate(total, page, size))


# ── Care Plans ─────────────────────────────────────────────────────────


@router.get("/care-plans", response_model=CarePlanListResponse)
async def list_my_plans(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    status: PlanStatusEnum | None = None,
    include_tasks: bool = Query(False),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("start_date", pattern="^(start_date|created_at)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
) -> CarePlanListResponse:
    """List care plans for the patient."""
    offset = (page - 1) * size
    plans, total = await list_care_plans(
        db, current_user.id,
        status=status,
        include_tasks=include_tasks,
        offset=offset,
        limit=size,
        sort_by=sort_by,
        order=order,
    )

    def to_response(p: CarePlan) -> CarePlanResponse:
        tasks = None
        if include_tasks and p.tasks is not None:
            tasks = [
                CareTaskResponse.model_validate(t) for t in sorted(
                    p.tasks, key=lambda x: (x.order, x.due_date or "")
                )
            ]
        return CarePlanResponse(
            id=p.id,
            title=p.title,
            goals=parse_json_field(p.goals),
            status=p.status,
            start_date=p.start_date,
            end_date=p.end_date,
            tasks=tasks,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )

    items = [to_response(p) for p in plans]
    return CarePlanListResponse(items=items, **_paginate(total, page, size))


@router.get("/care-plans/{plan_id}", response_model=CarePlanResponse)
async def get_plan_detail(
    plan_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> CarePlanResponse:
    """Get a single care plan with all tasks."""
    plan = await get_care_plan(db, plan_id, current_user.id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

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


@router.get("/care-plans/{plan_id}/tasks", response_model=TaskListResponse)
async def get_plan_tasks(
    plan_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    status_filter: TaskStatusEnum | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> TaskListResponse:
    """Paginated tasks within a plan."""
    offset = (page - 1) * size
    tasks, total = await list_tasks(
        db, plan_id, current_user.id,
        status=status_filter,
        offset=offset,
        limit=size,
    )
    items = [CareTaskResponse.model_validate(t) for t in tasks]
    return TaskListResponse(items=items, **_paginate(total, page, size))


@router.post(
    "/care-plans/{plan_id}/tasks/{task_id}/complete",
    response_model=CareTaskActionResponse,
)
async def complete_my_task(
    plan_id: uuid.UUID,
    task_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> CareTaskActionResponse:
    """Mark a pending task as completed (idempotent, 409 on conflict)."""
    task = await complete_task(db, plan_id, task_id, current_user.id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task cannot be completed (not found, already done, or plan is finished)",
        )
    return CareTaskActionResponse(
        id=task.id, status=task.status, completed_at=task.completed_at
    )


@router.post(
    "/care-plans/{plan_id}/tasks/{task_id}/skip",
    response_model=CareTaskActionResponse,
)
async def skip_my_task(
    plan_id: uuid.UUID,
    task_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> CareTaskActionResponse:
    """Skip a pending task."""
    task = await skip_task(db, plan_id, task_id, current_user.id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task cannot be skipped",
        )
    return CareTaskActionResponse(id=task.id, status=task.status)


@router.patch("/care-plans/{plan_id}/status", response_model=CarePlanResponse)
async def update_my_plan_status(
    plan_id: uuid.UUID,
    body: PlanStatusUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> CarePlanResponse:
    """Update care plan status (pause, resume, complete, cancel)."""
    plan = await update_plan_status(db, plan_id, current_user.id, body.status)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid status transition or plan not found",
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


@router.post("/care-plans", response_model=CarePlanResponse, status_code=201)
async def create_my_plan(
    body: CarePlanCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> CarePlanResponse:
    """Create a new care plan (auto-active) with optional tasks."""
    plan = await create_care_plan(
        db, current_user.id,
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


# ── Medication Reminders ───────────────────────────────────────────────


def _reminder_to_response(r) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "dosage": r.dosage,
        "frequency": r.frequency,
        "time_slots": parse_json_field(r.time_slots),
        "start_date": r.start_date,
        "end_date": r.end_date,
        "status": r.status,
        "note": r.note,
        "created_at": r.created_at,
        "updated_at": r.updated_at,
    }


@router.get("/medications", response_model=list[MedicationReminderResponse])
async def list_my_medications(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> list[MedicationReminderResponse]:
    """List all medication reminders."""
    reminders = await list_reminders(db, current_user.id)
    return [MedicationReminderResponse(**_reminder_to_response(r)) for r in reminders]


@router.post("/medications", response_model=MedicationReminderResponse, status_code=201)
async def create_my_medication(
    body: MedicationReminderCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> MedicationReminderResponse:
    """Add a medication reminder."""
    reminder = await create_reminder(
        db, current_user.id,
        name=body.name,
        dosage=body.dosage,
        frequency=body.frequency,
        time_slots=body.time_slots,
        start_date=body.start_date,
        end_date=body.end_date,
        note=body.note,
    )
    return MedicationReminderResponse(**_reminder_to_response(reminder))


@router.patch("/medications/{medication_id}", response_model=MedicationReminderResponse)
async def update_my_medication(
    medication_id: uuid.UUID,
    body: MedicationReminderUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> MedicationReminderResponse:
    """Update a medication reminder."""
    updates = body.model_dump(exclude_none=True)
    reminder = await update_reminder(db, medication_id, current_user.id, updates)
    if not reminder:
        raise HTTPException(status_code=404, detail="Medication not found")
    return MedicationReminderResponse(**_reminder_to_response(reminder))


@router.delete("/medications/{medication_id}", status_code=204)
async def delete_my_medication(
    medication_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-delete a medication reminder."""
    ok = await delete_reminder(db, medication_id, current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Medication not found")


@router.get("/medications/today", response_model=TodayMedicationResponse)
async def get_today_doses(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> TodayMedicationResponse:
    """Get today's dose records (auto-creates pending records on first view)."""
    records, taken, pending = await get_today_medications(db, current_user.id)
    # Build name map
    rids = list(set(r.reminder_id for r in records))
    name_map = {}
    if rids:
        rems = await db.execute(
            select(MedicationReminder).where(MedicationReminder.id.in_(rids))
        )
        name_map = {rm.id: (rm.name, rm.dosage) for rm in rems.scalars().all()}

    items = []
    for r in records:
        info = name_map.get(r.reminder_id, ("", ""))
        items.append(TodayMedicationItem(
            reminder_id=r.reminder_id,
            record_id=r.id,
            name=info[0],
            dosage=info[1],
            scheduled_time=r.scheduled_time,
            taken_at=r.taken_at,
            status=r.status,
        ))

    return TodayMedicationResponse(
        items=items, taken_count=taken, pending_count=pending, total_count=len(items),
    )


@router.post("/medications/{medication_id}/take", response_model=MedicationRecordResponse)
async def take_dose(
    medication_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> MedicationRecordResponse:
    """Mark today's first pending dose as taken."""
    records, _, _ = await get_today_medications(db, current_user.id)
    target = next(
        (r for r in records if r.reminder_id == medication_id and r.status == TaskStatusEnum.PENDING),
        None,
    )
    if not target:
        raise HTTPException(status_code=409, detail="No pending dose or already taken")
    result = await take_medication(db, target.id, current_user.id)
    if not result:
        raise HTTPException(status_code=409, detail="Cannot take this dose")
    return MedicationRecordResponse.model_validate(result)


@router.post("/medications/{medication_id}/skip", response_model=MedicationRecordResponse)
async def skip_dose(
    medication_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> MedicationRecordResponse:
    """Skip today's first pending dose."""
    records, _, _ = await get_today_medications(db, current_user.id)
    target = next(
        (r for r in records if r.reminder_id == medication_id and r.status == TaskStatusEnum.PENDING),
        None,
    )
    if not target:
        raise HTTPException(status_code=409, detail="No pending dose found")
    result = await skip_medication(db, target.id, current_user.id)
    if not result:
        raise HTTPException(status_code=409, detail="Cannot skip this dose")
    return MedicationRecordResponse.model_validate(result)


# ── SSE Notification Stream ───────────────────────────────────────────


@router.get("/notifications/stream")
async def notification_stream(current_user: CurrentUser):
    """SSE stream for real-time medication reminders."""
    import asyncio
    from fastapi.responses import StreamingResponse

    q = notification_bus.subscribe()

    async def event_generator():
        try:
            # Send initial heartbeat
            yield f"event: connected\ndata: {json.dumps({'status': 'ok'})}\n\n"
            while True:
                try:
                    payload = await asyncio.wait_for(q.get(), timeout=30)
                    ev = payload.get("event", "message")
                    data = payload.get("data", {})
                    # Only deliver events for this user
                    if data.get("patient_id") == str(current_user.id):
                        yield f"event: {ev}\ndata: {json.dumps(data)}\n\n"
                except asyncio.TimeoutError:
                    yield f"event: heartbeat\ndata: {json.dumps({'t': str(__import__('datetime').datetime.now())})}\n\n"
        finally:
            notification_bus.unsubscribe(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
