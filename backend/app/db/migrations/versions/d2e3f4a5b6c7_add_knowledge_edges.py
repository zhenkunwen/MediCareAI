"""add_knowledge_edges

KnowledgeAgent + GraphRAG:
1. knowledge_edges — weighted relationships between medical entities

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-06-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'd2e3f4a5b6c7'
down_revision: Union[str, Sequence[str], None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'knowledge_edges',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text('gen_random_uuid()')),

        # Source entity
        sa.Column('source_type', sa.String(50), nullable=False, index=True,
                  comment='Entity type: symptom / disease / drug / test'),
        sa.Column('source_value', sa.String(255), nullable=False, index=True,
                  comment='Entity value, e.g. 发热, 肺炎'),

        # Target entity
        sa.Column('target_type', sa.String(50), nullable=False, index=True,
                  comment='Entity type: symptom / disease / drug / test'),
        sa.Column('target_value', sa.String(255), nullable=False, index=True,
                  comment='Entity value, e.g. 肺炎, 血常规'),

        # Relationship attributes
        sa.Column('edge_type', sa.String(50), nullable=False, server_default='has_symptom',
                  comment='Relationship type: has_symptom / treats / differential_of / suggests_test'),
        sa.Column('weight', sa.Float, nullable=False, server_default='1.0',
                  comment='Association strength (0~1)'),
        sa.Column('occurrence_count', sa.Integer, nullable=False, server_default='1',
                  comment='Number of times this relationship has been observed'),

        # Metadata
        sa.Column('source', sa.String(50), nullable=False, server_default='manual',
                  comment='Data source: manual / learned / guideline / literature'),
        sa.Column('reference', sa.Text, nullable=True,
                  comment='Reference citation or URL'),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Composite indexes for common traversal patterns
    op.create_index('ix_knowledge_edges_source', 'knowledge_edges', ['source_type', 'source_value'])
    op.create_index('ix_knowledge_edges_target', 'knowledge_edges', ['target_type', 'target_value'])
    op.create_index('ix_knowledge_edges_edge_type', 'knowledge_edges', ['edge_type', 'source_type'])


def downgrade() -> None:
    op.drop_table('knowledge_edges')
