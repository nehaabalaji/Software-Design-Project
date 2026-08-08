"""Add queues table and service constraints

Revision ID: b7e4c2a91f05
Revises: 70e180468b44
Create Date: 2026-08-07 20:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "b7e4c2a91f05"
down_revision = "70e180468b44"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("services", schema=None) as batch_op:
        batch_op.alter_column(
            "description",
            existing_type=sa.String(length=500),
            type_=sa.Text(),
            existing_nullable=False,
            nullable=True,
        )
        batch_op.add_column(
            sa.Column("priority_level", sa.Integer(), nullable=False, server_default="0")
        )

    op.execute(
        """
        UPDATE services
        SET priority_level = CASE LOWER(priority)
            WHEN 'low' THEN 0
            WHEN 'medium' THEN 1
            WHEN 'high' THEN 2
            WHEN 'urgent' THEN 3
            ELSE 0
        END
        """
    )

    op.execute(
        "ALTER TABLE services "
        "ADD CONSTRAINT chk_services_name_not_empty "
        "CHECK (CHAR_LENGTH(TRIM(name)) > 0)"
    )
    op.execute(
        "ALTER TABLE services "
        "ADD CONSTRAINT chk_services_duration_positive "
        "CHECK (duration > 0)"
    )

    op.create_table(
        "queues",
        sa.Column("queue_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("service_id", sa.String(length=36), nullable=False),
        sa.Column(
            "status",
            sa.Enum("open", "closed", name="queue_status"),
            nullable=False,
            server_default="open",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("queue_id"),
        sa.UniqueConstraint("service_id", name="uq_queues_service"),
    )
    with op.batch_alter_table("queues", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_queues_service_id"), ["service_id"], unique=True)

    op.execute(
        """
        INSERT INTO queues (service_id, status, created_at)
        SELECT id, 'open', UTC_TIMESTAMP()
        FROM services
        WHERE id NOT IN (SELECT service_id FROM queues)
        """
    )


def downgrade():
    op.drop_table("queues")
    op.execute("ALTER TABLE services DROP CHECK chk_services_duration_positive")
    op.execute("ALTER TABLE services DROP CHECK chk_services_name_not_empty")
    with op.batch_alter_table("services", schema=None) as batch_op:
        batch_op.drop_column("priority_level")
        batch_op.alter_column(
            "description",
            existing_type=sa.Text(),
            type_=sa.String(length=500),
            existing_nullable=True,
            nullable=False,
        )
