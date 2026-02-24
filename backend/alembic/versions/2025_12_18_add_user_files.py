"""add_user_files_table

Revision ID: 2025_12_18_add_user_files
Revises: c66d6555a5d8
Create Date: 2025-12-18 14:26:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '2025_12_18_add_user_files'
down_revision = 'c66d6555a5d8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create user_files table if it doesn't exist
    op.execute("""
        CREATE TABLE IF NOT EXISTS user_files (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            file_path VARCHAR NOT NULL,
            file_name VARCHAR NOT NULL,
            file_type VARCHAR NOT NULL,
            file_size BIGINT NOT NULL,
            folder_path VARCHAR NOT NULL DEFAULT 'shared',
            is_system_folder BOOLEAN DEFAULT FALSE,
            is_deleted BOOLEAN DEFAULT FALSE,
            deleted_at TIMESTAMP,
            uploaded_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    
    # Create indexes
    op.execute("CREATE INDEX IF NOT EXISTS ix_user_files_id ON user_files(id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_user_files_is_deleted ON user_files(is_deleted)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_user_files_user_folder ON user_files(user_id, folder_path)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_user_files_deleted_cleanup ON user_files(is_deleted, deleted_at)")


def downgrade() -> None:
    # Drop indexes
    op.execute("DROP INDEX IF EXISTS ix_user_files_deleted_cleanup")
    op.execute("DROP INDEX IF EXISTS ix_user_files_user_folder")
    op.execute("DROP INDEX IF EXISTS ix_user_files_is_deleted")
    op.execute("DROP INDEX IF EXISTS ix_user_files_id")
    
    # Drop table
    op.drop_table('user_files')
