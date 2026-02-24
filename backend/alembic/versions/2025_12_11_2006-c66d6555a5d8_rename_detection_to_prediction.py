"""
Rename detection tables and columns to prediction
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c66d6555a5d8'
down_revision = '3d47b60e41e8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rename detection_jobs table to prediction_jobs
    op.rename_table('detection_jobs', 'prediction_jobs')
    
    # Rename detection_results table to prediction_results
    op.rename_table('detection_results', 'prediction_results')
    
    # Rename detection_sessions table to prediction_sessions
    op.rename_table('detection_sessions', 'prediction_sessions')
    
    # Update foreign key column name in prediction_results
    op.alter_column('prediction_results', 'detection_job_id', 
                    new_column_name='prediction_job_id')
    
    # Update foreign key column name in export_jobs
    op.alter_column('export_jobs', 'detection_job_id', 
                    new_column_name='prediction_job_id')
    
    # Update file paths in prediction_results to reflect new directory structure
    op.execute("""
        UPDATE prediction_results 
        SET file_name = REPLACE(file_name, 'detections/', 'predictions/')
        WHERE file_name LIKE '%detections/%'
    """)


def downgrade() -> None:
    # Revert file paths in prediction_results
    op.execute("""
        UPDATE prediction_results 
        SET file_name = REPLACE(file_name, 'predictions/', 'detections/')
        WHERE file_name LIKE '%predictions/%'
    """)
    
    # Revert column name in export_jobs
    op.alter_column('export_jobs', 'prediction_job_id', 
                    new_column_name='detection_job_id')
    
    # Revert column name in prediction_results
    op.alter_column('prediction_results', 'prediction_job_id', 
                    new_column_name='detection_job_id')
    
    # Rename prediction_sessions back to detection_sessions
    op.rename_table('prediction_sessions', 'detection_sessions')
    
    # Rename prediction_results back to detection_results
    op.rename_table('prediction_results', 'detection_results')
    
    # Rename prediction_jobs back to detection_jobs
    op.rename_table('prediction_jobs', 'detection_jobs')
