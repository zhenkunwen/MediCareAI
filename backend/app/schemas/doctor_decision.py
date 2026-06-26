"""Doctor decision schemas for DoctorAgent module."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ─── Nested Schemas ───────────────────────────────────────────

class PossibleDisease(BaseModel):
    """A possible disease with confidence score."""
    disease: str = Field(..., description="Disease name")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score 0-1")


class PreDiagnosisDetail(BaseModel):
    """Pre-diagnosis structure from DiagnosisAgent."""
    possible_diseases: list[PossibleDisease] = Field(
        default_factory=list, description="Ranked list of possible diseases"
    )
    suggested_tests: list[str] = Field(
        default_factory=list, description="Suggested diagnostic tests"
    )
    urgency: str = Field(default="medium", description="Urgency level: low/medium/high/emergency")


class MedicationItem(BaseModel):
    """A single medication in a treatment plan."""
    name: str = Field(..., description="Medication name")
    dosage: str = Field(..., description="Dosage, e.g. 500mg")
    frequency: str = Field(..., description="Frequency, e.g. tid")
    days: int = Field(..., ge=1, description="Days to take")
    route: str = Field(default="口服", description="Administration route")


class TreatmentPlanSchema(BaseModel):
    """Treatment plan schema."""
    medications: list[MedicationItem] = Field(
        default_factory=list, description="Prescribed medications"
    )
    advice: list[str] = Field(
        default_factory=list, description="Lifestyle advice"
    )
    follow_up: str | None = Field(None, description="Follow-up instructions")


class VitalSigns(BaseModel):
    """Vital signs data."""
    temperature: float | None = Field(None, description="Body temperature in Celsius")
    heart_rate: int | None = Field(None, description="Heart rate in bpm")
    respiratory_rate: int | None = Field(None, description="Respiratory rate")
    blood_pressure_systolic: int | None = Field(None, description="Systolic BP in mmHg")
    blood_pressure_diastolic: int | None = Field(None, description="Diastolic BP in mmHg")
    oxygen_saturation: float | None = Field(None, description="O2 saturation percentage")
    weight: float | None = Field(None, description="Weight in kg")
    height: float | None = Field(None, description="Height in cm")


# ─── Request Schemas ───────────────────────────────────────────

class FinalizeDiagnosisRequest(BaseModel):
    """Doctor's final diagnosis submission."""
    consultation_id: str = Field(..., description="Pending consultation ID")
    final_diagnosis: str = Field(..., min_length=1, description="Final diagnosis text")
    icd11_code: str | None = Field(None, max_length=20, description="ICD-11 code")
    treatment_plan: TreatmentPlanSchema | None = Field(
        None, description="Treatment plan"
    )
    doctor_notes: str | None = Field(None, description="Doctor's clinical notes")
    physical_exam: VitalSigns | None = Field(
        None, description="Physical examination findings"
    )
    rejected_suggestions: list[str] | None = Field(
        None, description="Pre-diagnosis items the doctor rejected"
    )


# ─── Response Schemas ───────────────────────────────────────────

class PendingConsultationItem(BaseModel):
    """A single pending consultation item for the doctor's queue."""
    model_config = ConfigDict(from_attributes=True)

    consultation_id: uuid.UUID = Field(alias="id")
    case_id: uuid.UUID
    patient_id: uuid.UUID
    patient_name: str | None = Field(default=None, description="Patient display name")
    chief_complaint: str | None = None
    pre_diagnosis: PreDiagnosisDetail
    vitals: VitalSigns | None = None
    allergies: list[str] | None = None
    status: str
    created_at: datetime


class PendingConsultationListResponse(BaseModel):
    """Response for the pending consultations listing."""
    consultations: list[PendingConsultationItem]


class FinalizeDiagnosisResponse(BaseModel):
    """Response after finalizing a diagnosis."""
    status: str = Field(default="recorded")
    consultation_id: str


class ConsultationHistoryItem(BaseModel):
    """A historical final diagnosis record for learning."""
    model_config = ConfigDict(from_attributes=True)

    consultation_id: uuid.UUID
    case_id: uuid.UUID
    doctor_id: uuid.UUID
    final_diagnosis: str
    icd11_code: str | None
    treatment_plan: dict | None
    doctor_notes: str | None
    created_at: datetime


class ConsultationHistoryListResponse(BaseModel):
    """Response for consultation history listing."""
    records: list[ConsultationHistoryItem]
