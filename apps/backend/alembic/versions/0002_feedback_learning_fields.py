"""add feedback learning fields

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-13
"""
from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('estimator_feedback', sa.Column('corrected_material', sa.String(length=128), nullable=True))
    op.add_column('estimator_feedback', sa.Column('corrected_operation_route', sa.JSON(), nullable=True))
    op.add_column('estimator_feedback', sa.Column('corrected_quantity', sa.Integer(), nullable=True))
    op.add_column('estimator_feedback', sa.Column('corrected_cost', sa.Float(), nullable=True))
    op.add_column('estimator_feedback', sa.Column('corrected_margin', sa.Float(), nullable=True))
    op.add_column('estimator_feedback', sa.Column('correction_reason', sa.Text(), nullable=True))
    op.add_column('estimator_feedback', sa.Column('estimator_note', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('estimator_feedback', 'estimator_note')
    op.drop_column('estimator_feedback', 'correction_reason')
    op.drop_column('estimator_feedback', 'corrected_margin')
    op.drop_column('estimator_feedback', 'corrected_cost')
    op.drop_column('estimator_feedback', 'corrected_quantity')
    op.drop_column('estimator_feedback', 'corrected_operation_route')
    op.drop_column('estimator_feedback', 'corrected_material')
