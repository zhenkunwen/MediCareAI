"""add_doctor_decision_tables

DoctorAgent module:
1. pending_consultations — pre-diagnosis results awaiting doctor review
2. final_diagnoses — doctor-confirmed final diagnosis records for knowledge learning

Revision ID: c1d2e3f4a5b6
Revises: b1c2d3e4f5a6
Create Date: 2026-06-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, Sequence[str], None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create consultationstatus enum
    op.execute("CREATE TYPE consultationstatus AS ENUM ('pending_doctor_review', 'confirmed', 'rejected')")

    # 2. Create pending_consultations table
    op.create_table(
        'pending_consultations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('gen_random_uuid()')),
        sa.Column('case_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('medical_cases.id', ondelete='CASCADE'),
                  nullable=False, index=True,
                  comment='Medical case this consultation belongs to'),
        sa.Column('doctor_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='SET NULL'),
                  nullable=True, index=True,
                  comment='Assigned doctor for review'),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='CASCADE'),
                  nullable=False, index=True,
                  comment='Patient who owns this consultation'),
        sa.Column('pre_diagnosis', postgresql.JSONB, nullable=False,
                  comment='PreDiagnosis structure: possible_diseases, suggested_tests, urgency'),
        sa.Column('vitals', postgresql.JSONB, nullable=True,
                  comment='Vital signs at time of consultation'),
        sa.Column('chief_complaint', sa.Text, nullable=True,
                  comment="Patient's chief complaint"),
        sa.Column('allergies', postgresql.JSONB, nullable=True,
                  comment='Known allergies'),
        sa.Column('status', sa.Enum('pending_doctor_review', 'confirmed', 'rejected', name='consultationstatus'),
                  nullable=False, server_default='pending_doctor_review', index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 3. Create final_diagnoses table
    op.create_table(
        'final_diagnoses',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('gen_random_uuid()')),
        sa.Column('consultation_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('pending_consultations.id', ondelete='CASCADE'),
                  nullable=False, unique=True, index=True,
                  comment='Reference to the pending consultation'),
        sa.Column('case_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('medical_cases.id', ondelete='CASCADE'),
                  nullable=False, index=True,
                  comment='Medical case this diagnosis belongs to'),
        sa.Column('doctor_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='SET NULL'),
                  nullable=False, index=True,
                  comment='Doctor who made the final diagnosis'),
        sa.Column('final_diagnosis', sa.Text, nullable=False,
                  comment='Doctor-confirmed diagnosis text'),
        sa.Column('icd11_code', sa.String(20), nullable=True,
                  comment='ICD-11 code'),
        sa.Column('treatment_plan', postgresql.JSONB, nullable=True,
                  comment='Treatment plan: medications, advice, follow-up'),
        sa.Column('doctor_notes', sa.Text, nullable=True,
                  comment="Doctor's clinical notes and remarks"),
        sa.Column('physical_exam', postgresql.JSONB, nullable=True,
                  comment='Physical examination findings'),
        sa.Column('rejected_suggestions', postgresql.JSONB, nullable=True,
                  comment='Pre-diagnosis items the doctor rejected'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 4. Create indexes for common queries
    op.create_index('ix_pending_consultations_doctor_status',
                    'pending_consultations', ['doctor_id', 'status'])
    op.create_index('ix_final_diagnoses_doctor_created',
                    'final_diagnoses', ['doctor_id', sa.text('created_at DESC')])


def downgrade() -> None:
    op.drop_table('final_diagnoses')
    op.drop_table('pending_consultations')
    op.execute('DROP TYPE IF EXISTS consultationstatus')
