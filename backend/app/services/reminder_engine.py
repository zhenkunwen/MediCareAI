"""Reminder engine — background task that scans for pending medication doses
and sends SMS reminders via the configured provider.

The engine runs as an asyncio task started in the FastAPI lifespan.
It is designed for SQLite (no Redis/Celery) and uses the database as
both source of truth and retry queue.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.patient_profile import (
    MedicationRecord,
    MedicationReminder,
    MedicationReminderLog,
    PlanStatusEnum,
    ReminderLogStatus,
    TaskStatusEnum,
)
from app.services.profile_service import parse_json_field
from app.services.notification_bus import bus as notification_bus
from app.services.sms_service import format_sms, get_sms_provider

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────

SCAN_INTERVAL_SECONDS = 60  # how often the engine wakes up
MAX_RETRY_COUNT = 3         # max send attempts before dead letter
RETRY_DELAYS = [1, 5, 15]   # minutes: 1st retry, 2nd retry, 3rd retry
LEAD_DEFAULT_MINUTES = 15   # default lead time if not set on reminder
RE_REMIND_INTERVAL_MINUTES = 30  # min gap between re-reminders


# ── Engine ────────────────────────────────────────────────────────────


class ReminderEngine:
    """Background loop that scans for doses needing SMS reminders."""

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        """Start the background loop (called from lifespan)."""
        if self._task is not None:
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run())
        logger.info("[ReminderEngine] 已启动 (scan interval=%ds)", SCAN_INTERVAL_SECONDS)

    async def stop(self) -> None:
        """Stop the background loop (called from lifespan)."""
        if self._task is None:
            return
        self._stop_event.set()
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        logger.info("[ReminderEngine] 已停止")

    async def _run(self) -> None:
        """Main loop."""
        while not self._stop_event.is_set():
            try:
                await self._scan_and_send()
            except Exception as e:
                logger.error("[ReminderEngine] 扫描异常: %s", e, exc_info=True)
            try:
                await asyncio.wait_for(
                    self._wait_for_stop_or_timeout(),
                    timeout=SCAN_INTERVAL_SECONDS,
                )
            except asyncio.TimeoutError:
                pass  # normal — just loop again

    async def _wait_for_stop_or_timeout(self) -> None:
        """Wait for stop event or timeout (whichever comes first)."""
        await asyncio.sleep(SCAN_INTERVAL_SECONDS)

    async def _scan_and_send(self) -> None:
        """Find doses that need reminding and send SMS."""
        now_local = datetime.now()  # local time (Beijing CST used throughout)
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC for SQLite compat
        today = now_local.date()
        current_time_str = now_local.strftime("%H:%M")

        async with AsyncSessionLocal() as db:
            # 1. Find pending records with active reminders
            records = await self._find_candidates(db, today, current_time_str, now_utc)

            for record in records:
                reminder = record.reminder  # eager-loaded
                await self._process_record(db, record, reminder, today, now_utc)
                # each record gets its own commit so partial failure doesn't block others

    async def _find_candidates(
        self, db: AsyncSession, today: date, current_time_str: str, now_utc: datetime
    ) -> list[MedicationRecord]:
        """Find medication records that are:
        - status = PENDING
        - scheduled_date = today
        - reminder is ACTIVE and remind_enabled = True
        - current time >= (scheduled_time - lead_minutes)
        - haven't been reminded yet, OR last reminder was >= 30 min ago AND count < 3
        """
        from sqlalchemy.orm import joinedload

        # Load records with their reminder in one query
        result = await db.execute(
            select(MedicationRecord)
            .options(joinedload(MedicationRecord.reminder))
            .where(
                MedicationRecord.status == TaskStatusEnum.PENDING,
                MedicationRecord.scheduled_date == today,
                MedicationRecord.reminder.has(
                    MedicationReminder.status == PlanStatusEnum.ACTIVE
                ),
                MedicationRecord.reminder.has(
                    MedicationReminder.remind_enabled == True  # noqa: E712
                ),
            )
        )
        all_records = list(result.scalars().all())

        candidates = []
        for rec in all_records:
            reminder = rec.reminder
            if not reminder:
                continue

            # Check lead time
            lead = reminder.lead_minutes or LEAD_DEFAULT_MINUTES
            slot = rec.scheduled_time  # "HH:MM"
            try:
                slot_h, slot_m = map(int, slot.split(":"))
            except (ValueError, AttributeError):
                continue

            # Current time as minutes from midnight
            current_h, current_m = map(int, current_time_str.split(":"))
            current_total = current_h * 60 + current_m
            slot_total = slot_h * 60 + slot_m
            earliest_total = slot_total - lead

            if current_total < earliest_total:
                # Too early
                continue

            # Check reminder frequency (don't spam every 60s)
            last = reminder.last_reminded_at
            count = reminder.reminded_count or 0

            if count >= MAX_RETRY_COUNT:
                continue  # max reminders sent

            if last is not None:
                elapsed = (now_utc - last).total_seconds() / 60
                if elapsed < RE_REMIND_INTERVAL_MINUTES:
                    continue  # too soon

            candidates.append(rec)

        return candidates

    async def _process_record(
        self,
        db: AsyncSession,
        record: MedicationRecord,
        reminder: MedicationReminder,
        today: date,
        now_utc: datetime,
    ) -> None:
        """Send SMS for a single record and update state."""
        patient_id = reminder.patient_id

        # Build SMS content
        time_str = record.scheduled_time
        msg = format_sms(
            name=reminder.name,
            dosage=reminder.dosage,
            time=time_str,
        )

        # Get phone from user
        from app.models.user import User
        user = await db.get(User, patient_id)
        if not user or not user.phone:
            logger.warning(
                "[ReminderEngine] 用户 %s 未设置手机号，跳过提醒",
                patient_id,
            )
            return

        # Send via provider
        provider = get_sms_provider()
        success = False
        error_msg: str | None = None
        try:
            success = await provider.send(phone=user.phone, message=msg)
        except Exception as e:
            error_msg = str(e)
            logger.error("[ReminderEngine] 发送短信失败: %s", error_msg)

        # Calc reminder plan time (when this dose should have been reminded)
        plan_time = now_utc  # approximate

        retry_count = reminder.reminded_count or 0
        new_count = retry_count + 1 if not success else retry_count + 1
        new_status = (
            ReminderLogStatus.SENT if success
            else ReminderLogStatus.DEAD if new_count >= MAX_RETRY_COUNT
            else ReminderLogStatus.FAILED
        )

        # Calc next retry time
        next_retry = None
        if not success and new_count < MAX_RETRY_COUNT:
            delay_minutes = RETRY_DELAYS[min(new_count, len(RETRY_DELAYS) - 1)]
            next_retry = now_utc + timedelta(minutes=delay_minutes)

        # Create log entry
        log = MedicationReminderLog(
            record_id=record.id,
            patient_id=patient_id,
            phone=user.phone,
            reminder_plan_time=plan_time,
            scheduled_time=time_str,
            status=new_status,
            error_message=error_msg,
            retry_count=new_count,
            next_retry_at=next_retry,
        )
        db.add(log)

        # Update reminder's reminder tracking
        reminder.last_reminded_at = now_utc
        reminder.reminded_count = new_count

        await db.commit()

        # Push to SSE bus
        try:
            await notification_bus.publish("medication_reminder", {
                "patient_id": str(patient_id),
                "name": reminder.name,
                "dosage": reminder.dosage,
                "time": time_str,
                "status": "sent" if success else "failed",
            })
        except Exception:
            pass  # SSE bus error is non-fatal

        status_label = "sent" if success else f"failed (retry {new_count}/{MAX_RETRY_COUNT})"
        logger.info(
            "[ReminderEngine] %s %s → %s (%s)",
            reminder.name, time_str, user.phone, status_label,
        )


# ── Singleton ─────────────────────────────────────────────────────────

engine = ReminderEngine()
