"""Add status and position to queue_entries

Revision ID: 7e31837c8833
Revises: b7e4c2a91f05
Create Date: 2026-08-12 19:37:11.751180

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7e31837c8833'
down_revision = 'b7e4c2a91f05'
branch_labels = None
depends_on = None


def upgrade():
    # Existing rows (created before this column existed) all represent
    # people who were, at the time, waiting -- so backfill them as such.
    with op.batch_alter_table('queue_entries', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'status', sa.Enum('waiting', 'served', 'canceled', name='queue_entry_status'),
            nullable=False, server_default='waiting',
        ))
        batch_op.add_column(sa.Column('position', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('served_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('queue_entries', schema=None) as batch_op:
        batch_op.drop_column('served_at')
        batch_op.drop_column('position')
        batch_op.drop_column('status')
