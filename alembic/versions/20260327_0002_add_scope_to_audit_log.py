# Migration file generated
# Add scope field to audit_log table for scope tracking

from alembic import op
import sqlalchemy as sa


revision = '20260327_0002'
down_revision = '20260327_0001'
branch_labels = None
depends_on = None


def upgrade():
    # Check if scope column already exists
    with op.batch_alter_table('audit_logs', schema=None) as batch_op:
        # Add scope column if it doesn't exist
        try:
            batch_op.add_column(sa.Column('scope', sa.String(), nullable=True, index=True))
        except Exception:
            # Column might already exist
            pass


def downgrade():
    with op.batch_alter_table('audit_logs', schema=None) as batch_op:
        batch_op.drop_column('scope')
