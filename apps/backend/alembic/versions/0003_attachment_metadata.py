"""add attachment metadata table

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-13
"""
from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'rfq_attachment_metadata',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('rfq_id', sa.String(length=64), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('extension', sa.String(length=20), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('content_type', sa.String(length=100), nullable=False),
        sa.Column('extracted_text', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )


def downgrade():
    op.drop_table('rfq_attachment_metadata')
