"""multi-tenant security and config tables

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-13
"""
from alembic import op
import sqlalchemy as sa

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('rfq', sa.Column('organization_id', sa.String(length=64), nullable=True))
    op.add_column('quote_draft', sa.Column('organization_id', sa.String(length=64), nullable=True))
    op.add_column('estimator_feedback', sa.Column('organization_id', sa.String(length=64), nullable=True))
    op.add_column('rfq_attachment_metadata', sa.Column('organization_id', sa.String(length=64), nullable=True))
    op.create_table('company_config', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('organization_id', sa.String(length=64), nullable=False), sa.Column('company_name', sa.String(length=255), nullable=False), sa.Column('default_currency', sa.String(length=8), nullable=False), sa.Column('default_language', sa.String(length=8), nullable=False), sa.Column('created_at', sa.DateTime(), nullable=False))
    op.create_table('audit_log', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('organization_id', sa.String(length=64), nullable=False), sa.Column('actor_id', sa.String(length=64), nullable=False), sa.Column('actor_role', sa.String(length=32), nullable=False), sa.Column('action', sa.String(length=128), nullable=False), sa.Column('resource_type', sa.String(length=64), nullable=False), sa.Column('resource_id', sa.String(length=64), nullable=False), sa.Column('details', sa.JSON(), nullable=False), sa.Column('created_at', sa.DateTime(), nullable=False))


def downgrade():
    op.drop_table('audit_log')
    op.drop_table('company_config')
    op.drop_column('rfq_attachment_metadata', 'organization_id')
    op.drop_column('estimator_feedback', 'organization_id')
    op.drop_column('quote_draft', 'organization_id')
    op.drop_column('rfq', 'organization_id')
