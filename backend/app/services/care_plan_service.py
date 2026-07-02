"""Care plan & task business logic: queries, state machine, lazy expiry."""

import json
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.patient_profile import (
    CarePlan,
    CareTask,
    PlanStatusEnum,
    TaskStatusEnum,
)


def _today() -> date:
    """Return today's date (UTC)."""
    return datetime.now(timezone.utc).date()


# ── Lazy expiry ────────────────────────────────────────────────────────


async def mark_expired_tasks(
    db: AsyncSession, plan_id: uuid.UUID | None = None, user_id: uuid.UUID | None = None
) -> int:
    """Mark tasks as expired where due_date < today and status = pending.

    Accepts optional plan_id or user_id scope. Returns count of expired tasks.
    """
    stmt = (
        update(CareTask)
        .where(
            CareTask.status == TaskStatusEnum.PENDING,
            CareTask.due_date < _today(),
        )
        .values(status=TaskStatusEnum.EXPIRED)
    )
    if plan_id:
        stmt = stmt.where(CareTask.plan_id == plan_id)
    if user_id:
        stmt = stmt.where(
            CareTask.plan_id.in_(
                select(CarePlan.id).where(CarePlan.patient_id == user_id)
            )
        )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount


# ── Queries ────────────────────────────────────────────────────────────


async def list_care_plans(
    db: AsyncSession,
    patient_id: uuid.UUID,
    *,
    status: PlanStatusEnum | None = None,
    include_tasks: bool = False,
    offset: int = 0,
    limit: int = 20,
    sort_by: str = "start_date",
    order: str = "desc",
) -> tuple[list[CarePlan], int]:
    """List care plans for a patient with pagination.

    Optionally expires stale tasks before returning.
    """
    await mark_expired_tasks(db, user_id=patient_id)

    # Count query
    count_q = select(func.count(CarePlan.id)).where(
        CarePlan.patient_id == patient_id
    )
    if status:
        count_q = count_q.where(CarePlan.status == status)

    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    # Sort
    sort_col = getattr(CarePlan, sort_by, CarePlan.start_date)
    order_fn = sort_col.desc if order == "desc" else sort_col.asc

    query = (
        select(CarePlan)
        .where(CarePlan.patient_id == patient_id)
        .order_by(order_fn())
        .offset(offset)
        .limit(limit)
    )
    if status:
        query = query.where(CarePlan.status == status)
    if include_tasks:
        query = query.options(selectinload(CarePlan.tasks))

    result = await db.execute(query)
    plans = result.scalars().all()
    return list(plans), total


async def get_care_plan(
    db: AsyncSession, plan_id: uuid.UUID, patient_id: uuid.UUID
) -> CarePlan | None:
    """Get a single plan (with tasks) owned by patient_id.

    Returns None if not found or not owned by this patient.
    """
    await mark_expired_tasks(db, plan_id=plan_id)

    result = await db.execute(
        select(CarePlan)
        .where(CarePlan.id == plan_id, CarePlan.patient_id == patient_id)
        .options(selectinload(CarePlan.tasks))
    )
    return result.scalar_one_or_none()


async def list_tasks(
    db: AsyncSession,
    plan_id: uuid.UUID,
    patient_id: uuid.UUID,
    *,
    status: TaskStatusEnum | None = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[CareTask], int]:
    """Paginate tasks within a plan, verifying ownership."""
    plan = await get_care_plan(db, plan_id, patient_id)
    if not plan:
        return [], 0

    await mark_expired_tasks(db, plan_id=plan_id)

    count_q = select(func.count(CareTask.id)).where(
        CareTask.plan_id == plan_id
    )
    if status:
        count_q = count_q.where(CareTask.status == status)

    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    query = (
        select(CareTask)
        .where(CareTask.plan_id == plan_id)
        .order_by(CareTask.order, CareTask.due_date)
        .offset(offset)
        .limit(limit)
    )
    if status:
        query = query.where(CareTask.status == status)

    result = await db.execute(query)
    tasks = result.scalars().all()
    return list(tasks), total


# ── Mutations ──────────────────────────────────────────────────────────


async def complete_task(
    db: AsyncSession, plan_id: uuid.UUID, task_id: uuid.UUID, patient_id: uuid.UUID
) -> CareTask | None:
    """Mark a task as completed. Returns None on failure (not found, conflict)."""
    plan = await get_care_plan(db, plan_id, patient_id)
    if not plan:
        return None
    if plan.status in (PlanStatusEnum.COMPLETED, PlanStatusEnum.CANCELLED):
        return None

    await mark_expired_tasks(db, plan_id=plan_id)

    now = datetime.now(timezone.utc)
    result = await db.execute(
        update(CareTask)
        .where(
            CareTask.id == task_id,
            CareTask.plan_id == plan_id,
            CareTask.status.in_([TaskStatusEnum.PENDING, TaskStatusEnum.EXPIRED]),
        )
        .values(status=TaskStatusEnum.COMPLETED, completed_at=now)
    )
    await db.commit()

    if result.rowcount == 0:
        return None

    fetch = await db.execute(
        select(CareTask).where(CareTask.id == task_id, CareTask.plan_id == plan_id)
    )
    return fetch.scalar_one_or_none()


async def skip_task(
    db: AsyncSession, plan_id: uuid.UUID, task_id: uuid.UUID, patient_id: uuid.UUID
) -> CareTask | None:
    """Skip a task. Returns None on failure."""
    plan = await get_care_plan(db, plan_id, patient_id)
    if not plan:
        return None
    if plan.status in (PlanStatusEnum.COMPLETED, PlanStatusEnum.CANCELLED):
        return None

    result = await db.execute(
        update(CareTask)
        .where(
            CareTask.id == task_id,
            CareTask.plan_id == plan_id,
            CareTask.status == TaskStatusEnum.PENDING,
        )
        .values(status=TaskStatusEnum.SKIPPED)
    )
    await db.commit()

    if result.rowcount == 0:
        return None

    fetch = await db.execute(
        select(CareTask).where(CareTask.id == task_id, CareTask.plan_id == plan_id)
    )
    return fetch.scalar_one_or_none()


async def create_care_plan(
    db: AsyncSession,
    patient_id: uuid.UUID,
    title: str,
    goals: list[str] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    task_defs: list[dict] | None = None,
    *,
    commit: bool = True,
) -> CarePlan:
    """Create a new care plan (active) with optional tasks.

    When *commit* is False, the caller is responsible for the outer commit.
    This allows grouping care plan creation into a larger transaction.

    task_defs: each dict has 'description' (str) and optional 'due_date' (date).
    """
    now = _today()
    plan = CarePlan(
        patient_id=patient_id,
        title=title,
        goals=json.dumps(goals or [], ensure_ascii=False),
        status=PlanStatusEnum.ACTIVE,
        start_date=start_date or now,
        end_date=end_date,
    )
    db.add(plan)
    await db.flush()  # get plan.id

    if task_defs:
        for i, t in enumerate(task_defs):
            due = t.get("due_date") or now
            db.add(CareTask(
                plan_id=plan.id,
                description=t["description"],
                due_date=due,
                order=i,
            ))

    if commit:
        await db.commit()
        # reload with tasks
        result = await db.execute(
            select(CarePlan)
            .where(CarePlan.id == plan.id)
            .options(selectinload(CarePlan.tasks))
        )
        return result.scalar_one()
    return plan


async def update_plan_status(
    db: AsyncSession,
    plan_id: uuid.UUID,
    patient_id: uuid.UUID,
    new_status: PlanStatusEnum,
) -> CarePlan | None:
    """Update plan status with state-machine rules.

    Allowed transitions:
      active  <-> paused
      active  -> completed, cancelled
      paused  -> completed, cancelled
      completed, cancelled = terminal (no further transitions)
    """
    plan = await get_care_plan(db, plan_id, patient_id)
    if not plan:
        return None

    current = plan.status
    valid = {
        PlanStatusEnum.ACTIVE: {
            PlanStatusEnum.PAUSED,
            PlanStatusEnum.COMPLETED,
            PlanStatusEnum.CANCELLED,
        },
        PlanStatusEnum.PAUSED: {
            PlanStatusEnum.ACTIVE,
            PlanStatusEnum.COMPLETED,
            PlanStatusEnum.CANCELLED,
        },
        PlanStatusEnum.COMPLETED: set(),
        PlanStatusEnum.CANCELLED: set(),
    }

    if new_status not in valid.get(current, set()):
        return None

    stmt = (
        update(CarePlan)
        .where(CarePlan.id == plan_id, CarePlan.patient_id == patient_id)
        .values(status=new_status)
    )
    await db.execute(stmt)

    # If plan completed/cancelled, skip remaining tasks
    if new_status in (PlanStatusEnum.COMPLETED, PlanStatusEnum.CANCELLED):
        await db.execute(
            update(CareTask)
            .where(
                CareTask.plan_id == plan_id,
                CareTask.status == TaskStatusEnum.PENDING,
            )
            .values(status=TaskStatusEnum.SKIPPED)
        )

    await db.commit()

    fetch = await db.execute(
        select(CarePlan)
        .where(CarePlan.id == plan_id)
        .options(selectinload(CarePlan.tasks))
    )
    return fetch.scalar_one_or_none()
