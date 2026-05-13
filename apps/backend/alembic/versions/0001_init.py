"""init tables

Revision ID: 0001
Revises:
Create Date: 2026-05-13
"""
from alembic import op
import sqlalchemy as sa

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('rfq', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('rfq_id', sa.String(64), nullable=False), sa.Column('customer', sa.String(255), nullable=False), sa.Column('message', sa.Text(), nullable=False), sa.Column('created_at', sa.DateTime(), nullable=False))
    op.create_index('ix_rfq_rfq_id', 'rfq', ['rfq_id'], unique=True)
    op.create_table('quote_draft', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('rfq_id', sa.String(64), nullable=False), sa.Column('customer_facing_response', sa.Text(), nullable=False), sa.Column('internal_notes', sa.JSON(), nullable=False), sa.Column('assumptions', sa.JSON(), nullable=False), sa.Column('clarification_questions', sa.JSON(), nullable=False), sa.Column('risk_warnings', sa.JSON(), nullable=False), sa.Column('is_preliminary', sa.Boolean(), nullable=False), sa.Column('created_at', sa.DateTime(), nullable=False))
    op.create_table('estimator_feedback', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('rfq_id', sa.String(64), nullable=False), sa.Column('decision', sa.String(64), nullable=False), sa.Column('comment', sa.Text(), nullable=False), sa.Column('created_at', sa.DateTime(), nullable=False))

def downgrade():
    op.drop_table('estimator_feedback')
    op.drop_table('quote_draft')
    op.drop_index('ix_rfq_rfq_id', table_name='rfq')
    op.drop_table('rfq')
