"""Patient-facing API schemas: health profile, care plans, care tasks."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.patient_profile import (
    BloodTypeEnum,
    GenderEnum,
    PlanStatusEnum,
    TaskStatusEnum,
)


# ── Health Profile ─────────────────────────────────────────────────────


class MedicationSchema(BaseModel):
    """A single medication entry in the patient's profile."""

    name: str = Field(..., min_length=1)
    dosage: str = Field(..., min_length=1)  # string like "5mg", "2片"
    frequency: str = Field(..., min_length=1)
    start_date: date
    end_date: date | None = None


class HealthProfileResponse(BaseModel):
    """Full health profile returned to the patient."""

    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    date_of_birth: date | None = None
    gender: GenderEnum | None = None
    blood_type: BloodTypeEnum | None = None
    height: Decimal | None = None
    weight: Decimal | None = None
    allergies: list[str] = []
    chronic_diseases: list[str] = []
    medications: list[MedicationSchema] = []
    created_at: datetime
    updated_at: datetime


class HealthProfileUpdate(BaseModel):
    """Partial update payload for health profile.

    Scalar fields are direct-replace. JSONB-list fields (allergies,
    chronic_diseases, medications) are full-replace — the client must
    send the complete new array.
    """

    date_of_birth: date | None = None
    gender: GenderEnum | None = None
    blood_type: BloodTypeEnum | None = None
    height: Decimal | None = Field(None, ge=30, le=300)
    weight: Decimal | None = Field(None, ge=2, le=500)
    allergies: list[str] | None = None
    chronic_diseases: list[str] | None = None
    medications: list[MedicationSchema] | None = None


class AllergyOperation(BaseModel):
    """Single allergy string for add/remove operations."""

    item: str = Field(..., min_length=1)


# ── Care Plan ──────────────────────────────────────────────────────────


class CareTaskResponse(BaseModel):
    """A single task within a care plan."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    description: str
    due_date: date
    status: TaskStatusEnum
    completed_at: datetime | None = None
    order: int


class CarePlanResponse(BaseModel):
    """Care plan returned to the patient."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    goals: list[str] = []
    status: PlanStatusEnum
    start_date: date
    end_date: date | None = None
    tasks: list[CareTaskResponse] | None = None
    created_at: datetime
    updated_at: datetime


class CarePlanListResponse(BaseModel):
    """Paginated list of care plans."""

    items: list[CarePlanResponse]
    total: int
    page: int
    size: int
    pages: int


class TaskListResponse(BaseModel):
    """Paginated list of tasks within a plan."""

    items: list[CareTaskResponse]
    total: int
    page: int
    size: int
    pages: int


class CareTaskActionResponse(BaseModel):
    """Response after completing or skipping a task."""

    id: uuid.UUID
    status: TaskStatusEnum
    completed_at: datetime | None = None


class CareTaskCreate(BaseModel):
    """Input for creating a single task within a care plan."""

    description: str = Field(..., min_length=1, max_length=500)
    due_date: date | None = None


class CarePlanCreate(BaseModel):
    """Input for creating a new care plan (defaults to active)."""

    title: str = Field(..., min_length=1, max_length=200)
    goals: list[str] = []
    start_date: date | None = None
    end_date: date | None = None
    tasks: list[CareTaskCreate] = []


# ── Medication Reminder ─────────────────────────────────────────────────


class MedicationReminderCreate(BaseModel):
    """Input for adding a medication reminder."""

    name: str = Field(..., min_length=1, max_length=200)
    dosage: str = Field(..., min_length=1, max_length=100)
    frequency: str = Field(..., min_length=1, max_length=100)
    time_slots: list[str] = Field(default_factory=lambda: ["08:00", "20:00"])
    start_date: date | None = None
    end_date: date | None = None
    note: str | None = Field(None, max_length=500)
    lead_minutes: int = Field(default=15, ge=1, le=1440)
    remind_enabled: bool = True


class MedicationReminderUpdate(BaseModel):
    """Input for updating a medication reminder."""

    name: str | None = None
    dosage: str | None = None
    frequency: str | None = None
    time_slots: list[str] | None = None
    start_date: date | None = None
    end_date: date | None = None
    note: str | None = None
    lead_minutes: int | None = Field(None, ge=1, le=1440)
    remind_enabled: bool | None = None


class MedicationRecordResponse(BaseModel):
    """A single dose record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scheduled_date: date
    scheduled_time: str
    taken_at: datetime | None = None
    status: TaskStatusEnum


class MedicationReminderResponse(BaseModel):
    """Medication reminder with today's records."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    dosage: str
    frequency: str
    time_slots: list[str] = []
    start_date: date
    end_date: date | None = None
    status: PlanStatusEnum
    note: str | None = None
    lead_minutes: int = 15
    remind_enabled: bool = True
    last_reminded_at: datetime | None = None
    reminded_count: int = 0
    today_records: list[MedicationRecordResponse] = []
    created_at: datetime
    updated_at: datetime


class TodayMedicationItem(BaseModel):
    """A single pending/taken dose for today's view."""

    reminder_id: uuid.UUID
    record_id: uuid.UUID
    name: str
    dosage: str
    scheduled_time: str
    taken_at: datetime | None = None
    status: TaskStatusEnum


class TodayMedicationResponse(BaseModel):
    """Today's medication overview."""

    items: list[TodayMedicationItem]
    taken_count: int
    pending_count: int
    total_count: int


class PlanStatusUpdate(BaseModel):
    """Request to update plan status."""

    status: PlanStatusEnum


# ── Cases (thin proxy for MedicalCase) ─────────────────────────────────


class CaseListResponseItem(BaseModel):
    """Patient-visible fields from MedicalCase."""

    id: uuid.UUID
    chief_complaint: str | None = None
    ai_diagnosis_summary: str | None = None
    severity: str | None = None
    is_emergency: bool = False
    status: str
    created_at: datetime
    updated_at: datetime


class CaseListResponse(BaseModel):
    """Paginated list of patient cases."""

    items: list[CaseListResponseItem]
    total: int
    page: int
    size: int
    pages: int


# ── Generic pagination params (used by routes) ─────────────────────────


class PaginationParams:
    """Pydantic model for query-string pagination."""

    def __init__(self, page: int = 1, size: int = 20):
        self.page = max(1, page)
        self.size = min(100, max(1, size))

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size

    @property
    def limit(self) -> int:
        return self.size
