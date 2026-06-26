"""Medication reminder business logic: CRUD, daily records, take/skip."""

import json
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.patient_profile import (
    MedicationReminder,
    MedicationRecord,
    PlanStatusEnum,
    TaskStatusEnum,
)
from app.services.profile_service import parse_json_field


# ── Helpers ────────────────────────────────────────────────────────────


def _today() -> date:
    return date.today()


async def _ensure_today_records(
    db: AsyncSession, reminder: MedicationReminder, today: date
) -> list[MedicationRecord]:
    """Create today's pending records for each time slot if not exist."""
    existing = await db.execute(
        select(MedicationRecord).where(
            MedicationRecord.reminder_id == reminder.id,
            MedicationRecord.scheduled_date == today,
        )
    )
    existing_map = {r.scheduled_time: r for r in existing.scalars().all()}

    slots = parse_json_field(reminder.time_slots) if isinstance(reminder.time_slots, str) else (reminder.time_slots or [])
    records = []
    for slot in slots:
        if slot in existing_map:
            records.append(existing_map[slot])
        else:
            r = MedicationRecord(
                reminder_id=reminder.id,
                scheduled_date=today,
                scheduled_time=slot,
            )
            db.add(r)
            records.append(r)

    if len(records) > len(existing_map):
        await db.flush()
    return records


# ── CRUD ───────────────────────────────────────────────────────────────


async def create_reminder(
    db: AsyncSession,
    patient_id: uuid.UUID,
    name: str,
    dosage: str,
    frequency: str,
    time_slots: list[str] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    note: str | None = None,
    lead_minutes: int = 15,
    remind_enabled: bool = True,
) -> MedicationReminder:
    """Create a new medication reminder."""
    now = _today()
    reminder = MedicationReminder(
        patient_id=patient_id,
        name=name,
        dosage=dosage,
        frequency=frequency,
        time_slots=json.dumps(time_slots or ["08:00", "20:00"], ensure_ascii=False),
        start_date=start_date or now,
        end_date=end_date,
        note=note,
        lead_minutes=lead_minutes,
        remind_enabled=remind_enabled,
    )
    db.add(reminder)
    await db.commit()
    await db.refresh(reminder)
    return reminder


async def list_reminders(
    db: AsyncSession, patient_id: uuid.UUID
) -> list[MedicationReminder]:
    """List all reminders for a patient (active first)."""
    result = await db.execute(
        select(MedicationReminder)
        .where(MedicationReminder.patient_id == patient_id)
        .order_by(MedicationReminder.status, MedicationReminder.created_at.desc())
    )
    return list(result.scalars().all())


async def get_reminder(
    db: AsyncSession, reminder_id: uuid.UUID, patient_id: uuid.UUID
) -> MedicationReminder | None:
    """Get a single reminder with ownership check."""
    result = await db.execute(
        select(MedicationReminder).where(
            MedicationReminder.id == reminder_id,
            MedicationReminder.patient_id == patient_id,
        )
    )
    return result.scalar_one_or_none()


async def update_reminder(
    db: AsyncSession,
    reminder_id: uuid.UUID,
    patient_id: uuid.UUID,
    updates: dict,
) -> MedicationReminder | None:
    """Update a reminder (partial)."""
    reminder = await get_reminder(db, reminder_id, patient_id)
    if not reminder:
        return None

    for key, value in updates.items():
        if value is not None and hasattr(reminder, key):
            if key == "time_slots" and isinstance(value, list):
                setattr(reminder, key, json.dumps(value, ensure_ascii=False))
            else:
                setattr(reminder, key, value)

    await db.commit()
    await db.refresh(reminder)
    return reminder


async def delete_reminder(
    db: AsyncSession, reminder_id: uuid.UUID, patient_id: uuid.UUID
) -> bool:
    """Soft-delete: set status to cancelled."""
    reminder = await get_reminder(db, reminder_id, patient_id)
    if not reminder:
        return False
    reminder.status = PlanStatusEnum.CANCELLED
    await db.commit()
    return True


# ── Today's Medications ───────────────────────────────────────────────


async def get_today_medications(
    db: AsyncSession, patient_id: uuid.UUID
) -> tuple[list[MedicationRecord], int, int]:
    """Get today's records (auto-create if missing). Returns (records, taken, pending)."""
    today = _today()

    # Get active reminders
    reminders = await db.execute(
        select(MedicationReminder).where(
            MedicationReminder.patient_id == patient_id,
            MedicationReminder.status == PlanStatusEnum.ACTIVE,
            MedicationReminder.start_date <= today,
        )
    )
    reminders = list(reminders.scalars().all())

    all_records: list[MedicationRecord] = []
    for reminder in reminders:
        records = await _ensure_today_records(db, reminder, today)
        all_records.extend(records)

    if all_records:
        await db.commit()

    taken = sum(1 for r in all_records if r.status == TaskStatusEnum.COMPLETED)
    pending = sum(1 for r in all_records if r.status == TaskStatusEnum.PENDING)

    return all_records, taken, pending


async def take_medication(
    db: AsyncSession, record_id: uuid.UUID, patient_id: uuid.UUID
) -> MedicationRecord | None:
    """Mark a dose as taken."""
    record = await db.execute(
        select(MedicationRecord).where(MedicationRecord.id == record_id)
    )
    record = record.scalar_one_or_none()
    if not record:
        return None

    # Ownership check via reminder
    reminder = await get_reminder(db, record.reminder_id, patient_id)
    if not reminder:
        return None
    if record.status != TaskStatusEnum.PENDING:
        return None

    now = datetime.now(timezone.utc)
    record.status = TaskStatusEnum.COMPLETED
    record.taken_at = now
    await db.commit()
    await db.refresh(record)
    return record


async def skip_medication(
    db: AsyncSession, record_id: uuid.UUID, patient_id: uuid.UUID
) -> MedicationRecord | None:
    """Skip a dose."""
    record = await db.execute(
        select(MedicationRecord).where(MedicationRecord.id == record_id)
    )
    record = record.scalar_one_or_none()
    if not record:
        return None

    reminder = await get_reminder(db, record.reminder_id, patient_id)
    if not reminder:
        return None
    if record.status != TaskStatusEnum.PENDING:
        return None

    record.status = TaskStatusEnum.SKIPPED
    await db.commit()
    await db.refresh(record)
    return record
