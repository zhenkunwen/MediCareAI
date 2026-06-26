"""add_patient_tables

Patient-facing tables:
1. health_profiles — one-to-one patient health metadata
2. care_plans — follow-up plans with state machine
3. care_tasks — individual tasks within care plans

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-06-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f4a5b6c7d8e9'
down_revision: Union[str, Sequence[str], None] = 'e3f4a5b6c7d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create patient-facing tables."""

    # ── Enums ───────────────────────────────────────────────────────
    gender_enum = sa.Enum(
        'male', 'female', 'other', 'prefer_not_to_say',
        name='gender_enum',
    )
    gender_enum.create(op.get_bind(), checkfirst=True)

    plan_status_enum = sa.Enum(
        'active', 'paused', 'completed', 'cancelled',
        name='plan_status_enum',
    )
    plan_status_enum.create(op.get_bind(), checkfirst=True)

    task_status_enum = sa.Enum(
        'pending', 'completed', 'skipped', 'expired',
        name='task_status_enum',
    )
    task_status_enum.create(op.get_bind(), checkfirst=True)

    # ── 1. health_profiles ──────────────────────────────────────────
    op.create_table(
        'health_profiles',
        sa.Column('user_id', sa.String(32), nullable=False),
        sa.Column('date_of_birth', sa.Date(), nullable=True),
        sa.Column('gender', gender_enum, nullable=True),
        sa.Column('height', sa.Numeric(5, 2), nullable=True),
        sa.Column('weight', sa.Numeric(5, 2), nullable=True),
        sa.Column('allergies', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('chronic_diseases', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('medications', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id'),
    )

    # ── 2. care_plans ───────────────────────────────────────────────
    op.create_table(
        'care_plans',
        sa.Column('id', sa.String(32), nullable=False),
        sa.Column('patient_id', sa.String(32), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('goals', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('status', plan_status_enum, nullable=False,
                  server_default='active'),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['patient_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_care_plans_patient_status', 'care_plans',
        ['patient_id', 'status'],
    )

    # ── 3. care_tasks ───────────────────────────────────────────────
    op.create_table(
        'care_tasks',
        sa.Column('id', sa.String(32), nullable=False),
        sa.Column('plan_id', sa.String(32), nullable=False),
        sa.Column('description', sa.String(500), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=False),
        sa.Column('status', task_status_enum, nullable=False,
                  server_default='pending'),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['plan_id'], ['care_plans.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_care_tasks_plan_status', 'care_tasks',
        ['plan_id', 'status'],
    )
    op.create_index('ix_care_tasks_due_date', 'care_tasks', ['due_date'])


def downgrade() -> None:
    """Drop patient-facing tables."""
    op.drop_table('care_tasks')
    op.drop_table('care_plans')
    op.drop_table('health_profiles')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS task_status_enum')
    op.execute('DROP TYPE IF EXISTS plan_status_enum')
    op.execute('DROP TYPE IF EXISTS gender_enum')
