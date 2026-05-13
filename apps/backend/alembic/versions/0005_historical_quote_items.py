"""add historical_quote_item table for similarity-based analog search

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-13
"""
from alembic import op
import sqlalchemy as sa

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'historical_quote_item',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.String(64), nullable=True, index=True),
        sa.Column('rfq_id', sa.String(64), nullable=False, index=True),
        sa.Column('product_family', sa.String(64), nullable=True),
        sa.Column('material_family', sa.String(64), nullable=True),
        sa.Column('thickness_mm', sa.Float(), nullable=True),
        sa.Column('unit_mass_kg', sa.Float(), nullable=True),
        sa.Column('quantity', sa.Integer(), nullable=True),
        sa.Column('operation_types', sa.JSON(), nullable=True),
        sa.Column('final_price_zl', sa.Float(), nullable=True),
        sa.Column('final_margin_pct', sa.Float(), nullable=True),
        sa.Column('decision', sa.String(32), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('historical_quote_item')
