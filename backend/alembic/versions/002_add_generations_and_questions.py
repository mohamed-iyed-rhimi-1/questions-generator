"""Add generations and questions tables for question management

Revision ID: 002
Revises: 001
Create Date: 2025-11-18

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    """
    Create generations and questions tables with proper indexes and foreign key constraints.
    """
    # Create generations table
    op.create_table(
        'generations',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('video_ids', sa.ARRAY(sa.String()), nullable=False),
        sa.Column('question_count', sa.Integer(), nullable=False, server_default='0')
    )
    
    # Create questions table
    op.create_table(
        'questions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('generation_id', sa.Integer(), nullable=False),
        sa.Column('video_id', sa.String(64), nullable=False),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('context', sa.Text(), nullable=True),
        sa.Column('difficulty', sa.String(20), nullable=True),
        sa.Column('question_type', sa.String(50), nullable=True),
        sa.Column('order_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(
            ['generation_id'], 
            ['generations.id'], 
            name='fk_questions_generation_id', 
            ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['video_id'], 
            ['videos.video_id'], 
            name='fk_questions_video_id', 
            ondelete='CASCADE'
        )
    )
    
    # Create indexes for efficient queries
    op.create_index('ix_questions_generation_id', 'questions', ['generation_id'])
    op.create_index('ix_questions_video_id', 'questions', ['video_id'])
    op.create_index('ix_questions_order', 'questions', ['generation_id', 'order_index'])


def downgrade():
    """
    Rollback generations and questions tables.
    """
    # Drop indexes
    op.drop_index('ix_questions_order', table_name='questions')
    op.drop_index('ix_questions_video_id', table_name='questions')
    op.drop_index('ix_questions_generation_id', table_name='questions')
    
    # Drop tables in reverse order
    op.drop_table('questions')
    op.drop_table('generations')
