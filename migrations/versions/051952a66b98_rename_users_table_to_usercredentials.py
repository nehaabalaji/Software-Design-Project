"""rename users table to UserCredentials

Revision ID: 051952a66b98
Revises: 178c55ba1497
Create Date: 2026-08-05 21:51:03.138531

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '051952a66b98'
down_revision = '178c55ba1497'
branch_labels = None
depends_on = None


def upgrade():
    # A real rename (not drop+create) so existing rows survive. MySQL/InnoDB
    # keeps foreign keys on 'tokens'/'queue_entries' pointed at the renamed
    # table automatically -- only the index name needs updating to match.
    op.rename_table('users', 'UserCredentials')
    with op.batch_alter_table('UserCredentials', schema=None) as batch_op:
        batch_op.drop_index('ix_users_email')
        batch_op.create_index(batch_op.f('ix_UserCredentials_email'), ['email'], unique=True)


def downgrade():
    with op.batch_alter_table('UserCredentials', schema=None) as batch_op:
        batch_op.drop_index('ix_UserCredentials_email')
        batch_op.create_index('ix_users_email', ['email'], unique=True)
    op.rename_table('UserCredentials', 'users')
