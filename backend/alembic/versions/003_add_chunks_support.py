"""Add chunks and transcription_chunks tables for chunk-based architecture

Revision ID: 003
Revises: 002
Create Date: 2025-11-19

"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade():
    """
    Create chunks and transcription_chunks tables with proper indexes and foreign key constraints.
    """
    # Create chunks table
    op.create_table(
        'chunks',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('video_id', sa.String(64), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('file_path', sa.String(1024), nullable=False),
        sa.Column('start_time', sa.Float(), nullable=False),
        sa.Column('end_time', sa.Float(), nullable=False),
        sa.Column('duration', sa.Float(), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(
            ['video_id'],
            ['videos.video_id'],
            name='fk_chunks_video_id',
            ondelete='CASCADE'
        ),
        sa.UniqueConstraint('video_id', 'chunk_index', name='uq_chunks_video_id_chunk_index')
    )
    
    # Create indexes for chunks table
    op.create_index('ix_chunks_video_id', 'chunks', ['video_id'])
    
    # Create transcription_chunks table
    op.create_table(
        'transcription_chunks',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('transcription_id', sa.Integer(), nullable=False),
        sa.Column('chunk_id', sa.Integer(), nullable=False),
        sa.Column('chunk_text', sa.Text(), nullable=False),
        sa.Column('vector_embedding', Vector(384), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(
            ['transcription_id'],
            ['transcriptions.id'],
            name='fk_transcription_chunks_transcription_id',
            ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['chunk_id'],
            ['chunks.id'],
            name='fk_transcription_chunks_chunk_id',
            ondelete='CASCADE'
        ),
        sa.UniqueConstraint('transcription_id', 'chunk_id', name='uq_transcription_chunks_transcription_id_chunk_id')
    )
    
    # Create indexes for transcription_chunks table
    op.create_index('ix_transcription_chunks_transcription_id', 'transcription_chunks', ['transcription_id'])
    op.create_index('ix_transcription_chunks_chunk_id', 'transcription_chunks', ['chunk_id'])


def downgrade():
    """
    Rollback chunks and transcription_chunks tables.
    """
    # Drop indexes for transcription_chunks
    op.drop_index('ix_transcription_chunks_chunk_id', table_name='transcription_chunks')
    op.drop_index('ix_transcription_chunks_transcription_id', table_name='transcription_chunks')
    
    # Drop indexes for chunks
    op.drop_index('ix_chunks_video_id', table_name='chunks')
    
    # Drop tables in reverse order
    op.drop_table('transcription_chunks')
    op.drop_table('chunks')
