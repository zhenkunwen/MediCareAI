"""add_mcp_tables

MCP (Medical Collaboration Protocol):
1. mcp_subscriptions — webhook subscriptions for external HIS systems
2. mcp_audit_logs — audit trail for MCP operations

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-06-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'e3f4a5b6c7d8'
down_revision: Union[str, Sequence[str], None] = 'd2e3f4a5b6c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create mcp_subscriptions
    op.create_table(
        'mcp_subscriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('gen_random_uuid()')),
        sa.Column('external_system', sa.String(100), nullable=False,
                  comment='Name of the external HIS system'),
        sa.Column('callback_url', sa.String(500), nullable=False,
                  comment='Webhook callback URL'),
        sa.Column('events', postgresql.JSONB, nullable=False,
                  comment='List of event types to subscribe to'),
        sa.Column('secret_encrypted', sa.Text, nullable=True,
                  comment='Encrypted secret for HMAC signing'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 2. Create mcp_audit_logs
    op.create_table(
        'mcp_audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('gen_random_uuid()')),
        sa.Column('operation', sa.String(50), nullable=False,
                  comment='Operation type: fetch_records / push_diagnosis / subscribe'),
        sa.Column('external_patient_id', sa.String(100), nullable=True,
                  comment='Patient ID in external system'),
        sa.Column('request_summary', sa.Text, nullable=True,
                  comment='Summary of the request'),
        sa.Column('response_summary', sa.Text, nullable=True,
                  comment='Summary of the response'),
        sa.Column('status', sa.String(20), nullable=False, server_default='success',
                  comment='success / failed'),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('ip_address', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_index('ix_mcp_audit_logs_operation', 'mcp_audit_logs', ['operation'])
    op.create_index('ix_mcp_audit_logs_created', 'mcp_audit_logs', ['created_at'])


def downgrade() -> None:
    op.drop_table('mcp_audit_logs')
    op.drop_table('mcp_subscriptions')
