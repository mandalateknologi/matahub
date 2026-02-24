"""
Alembic Migration Script Template
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b0fb386dfd9b'
down_revision = '2025_11_30_progress'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Buat tabel export_jobs dengan nama kolom 'detection_job_id' 
    # agar revisi c66d6555a5d8 bisa melakukan RENAME nantinya.
    op.create_table(
        'export_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        # Pakai nama 'detection_job_id' di sini
        sa.Column('detection_job_id', sa.Integer(), nullable=False), 
        sa.Column('export_type', sa.Enum('csv', 'json', 'xlsx', name='exporttype'), nullable=False),
        sa.Column('status', sa.Enum('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', name='exportstatus'), nullable=False),
        sa.Column('progress', sa.Float(), nullable=True),
        sa.Column('file_path', sa.String(), nullable=True),
        sa.Column('options_json', sa.JSON(), nullable=True),
        sa.Column('creator_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.String(), nullable=True),
        
        sa.ForeignKeyConstraint(['creator_id'], ['users.id'], ),
        # Foreign Key merujuk ke 'detection_jobs' (karena tabel itu belum di-rename saat ini)
        sa.ForeignKeyConstraint(['detection_job_id'], ['detection_jobs.id'], ), 
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_export_jobs_id'), 'export_jobs', ['id'], unique=False)


def downgrade() -> None:
    # Hapus index dan tabel
    op.drop_index(op.f('ix_export_jobs_id'), table_name='export_jobs')
    op.drop_table('export_jobs')
    
    # Menghapus Enum (Postgres spesifik) agar bersih
    op.execute("DROP TYPE IF EXISTS exporttype")
    op.execute("DROP TYPE IF EXISTS exportstatus")
