"""Initial schema with pgvector extension, videos and transcriptions tables

Revision ID: 001
Revises: 
Create Date: 2025-11-05

"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """
    Create initial database schema with pgvector support.
    """
    # Enable pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    
    # Create videos table
    op.create_table(
        'videos',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('video_id', sa.String(64), nullable=False),
        sa.Column('title', sa.String(512), nullable=False),
        sa.Column('thumbnail_url', sa.String(1024), nullable=True),
        sa.Column('file_path', sa.String(1024), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.UniqueConstraint('video_id', name='uq_videos_video_id')
    )
    
    # Create transcriptions table
    op.create_table(
        'transcriptions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('video_id', sa.String(64), nullable=False),
        sa.Column('transcription_text', sa.Text(), nullable=False),
        sa.Column('vector_embedding', Vector(384), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['video_id'], ['videos.video_id'], name='fk_transcriptions_video_id', ondelete='CASCADE')
    )
    op.create_index('ix_transcriptions_video_id', 'transcriptions', ['video_id'])
    
    # Create vector index for efficient similarity search
    # Using IVFFlat index with cosine distance for semantic search
    op.execute(
        'CREATE INDEX ix_transcriptions_vector_embedding '
        'ON transcriptions USING ivfflat (vector_embedding vector_cosine_ops) '
        'WITH (lists = 100)'
    )


def downgrade():
    """
    Rollback initial schema.
    """
    # Drop indexes
    op.drop_index('ix_transcriptions_vector_embedding', table_name='transcriptions')
    op.drop_index('ix_transcriptions_video_id', table_name='transcriptions')
    
    # Drop tables in reverse order
    op.drop_table('transcriptions')
    op.drop_table('videos')
    
    # Drop pgvector extension
    op.execute('DROP EXTENSION IF EXISTS vector')
