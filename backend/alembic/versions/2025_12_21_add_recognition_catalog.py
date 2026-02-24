"""add_recognition_catalog_tables

Revision ID: add_recognition_catalog_tables
Revises: 38216d8814de
Create Date: 2025-12-21 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_recognition_catalog_tables'
down_revision = '38216d8814de'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    
    # Create recognition_catalogs table
    op.execute("""
        CREATE TABLE IF NOT EXISTS recognition_catalogs (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            category VARCHAR(100) NOT NULL,
            image_count INTEGER DEFAULT 0,
            label_count INTEGER DEFAULT 0,
            creator_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)
    
    # Create indexes for recognition_catalogs
    op.execute("CREATE INDEX IF NOT EXISTS ix_recognition_catalogs_id ON recognition_catalogs(id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_recognition_catalogs_name ON recognition_catalogs(name)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_recognition_catalogs_category ON recognition_catalogs(category)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_recognition_catalogs_creator_id ON recognition_catalogs(creator_id)")
    
    # Create recognition_labels table
    op.execute("""
        CREATE TABLE IF NOT EXISTS recognition_labels (
            id SERIAL PRIMARY KEY,
            catalog_id INTEGER NOT NULL REFERENCES recognition_catalogs(id) ON DELETE CASCADE,
            label_name VARCHAR(255) NOT NULL,
            description TEXT,
            image_count INTEGER DEFAULT 0,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)
    
    # Create indexes for recognition_labels
    op.execute("CREATE INDEX IF NOT EXISTS ix_recognition_labels_id ON recognition_labels(id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_recognition_labels_catalog_id ON recognition_labels(catalog_id)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_recognition_labels_catalog_name ON recognition_labels(catalog_id, label_name)")
    
    # Create recognition_images table with pgvector support
    op.execute("""
        CREATE TABLE IF NOT EXISTS recognition_images (
            id SERIAL PRIMARY KEY,
            label_id INTEGER NOT NULL REFERENCES recognition_labels(id) ON DELETE CASCADE,
            image_path VARCHAR(512) NOT NULL,
            thumbnail_path VARCHAR(512),
            embedding vector(512),
            is_processed BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)
    
    # Create indexes for recognition_images
    op.execute("CREATE INDEX IF NOT EXISTS ix_recognition_images_id ON recognition_images(id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_recognition_images_label_id ON recognition_images(label_id)")
    # IVFFlat index for vector similarity search (cosine distance)
    # Note: This requires some data to be present, so we create it conditionally
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_recognition_images_embedding 
        ON recognition_images 
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)
    
    # Create recognition_jobs table
    op.execute("""
        CREATE TABLE IF NOT EXISTS recognition_jobs (
            id SERIAL PRIMARY KEY,
            catalog_id INTEGER NOT NULL REFERENCES recognition_catalogs(id) ON DELETE CASCADE,
            label_id INTEGER REFERENCES recognition_labels(id) ON DELETE CASCADE,
            total_images INTEGER DEFAULT 0,
            processed_images INTEGER DEFAULT 0,
            failed_images INTEGER DEFAULT 0,
            status VARCHAR(50) DEFAULT 'pending' NOT NULL,
            error_message TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            completed_at TIMESTAMP WITH TIME ZONE
        )
    """)
    
    # Create indexes for recognition_jobs
    op.execute("CREATE INDEX IF NOT EXISTS ix_recognition_jobs_id ON recognition_jobs(id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_recognition_jobs_catalog_id ON recognition_jobs(catalog_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_recognition_jobs_label_id ON recognition_jobs(label_id)")


def downgrade() -> None:
    # Drop tables in reverse order (due to foreign key constraints)
    op.execute("DROP TABLE IF EXISTS recognition_jobs CASCADE")
    op.execute("DROP TABLE IF EXISTS recognition_images CASCADE")
    op.execute("DROP TABLE IF EXISTS recognition_labels CASCADE")
    op.execute("DROP TABLE IF EXISTS recognition_catalogs CASCADE")
    
    # Drop pgvector extension (optional, comment out if used elsewhere)
    # op.execute("DROP EXTENSION IF EXISTS vector")
