"""Add answer column to questions table

Revision ID: 004
Revises: 003
Create Date: 2025-11-22

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add answer column to questions table for storing comprehensive answers.
    """
    op.add_column(
        'questions',
        sa.Column('answer', sa.Text(), nullable=True)
    )


def downgrade():
    """
    Remove answer column from questions table.
    """
    op.drop_column('questions', 'answer')
