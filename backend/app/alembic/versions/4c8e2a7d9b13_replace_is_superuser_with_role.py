"""Replace user.is_superuser with user.role

Existing superusers become admins; every other user becomes a member.
is_active is not touched, so no effective privilege changes.

Revision ID: 4c8e2a7d9b13
Revises: fe56fa70289e
Create Date: 2026-11-26 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4c8e2a7d9b13'
down_revision = 'fe56fa70289e'
branch_labels = None
depends_on = None

ROLE_CHECK = "ck_user_role"

user_table = sa.table(
    "user",
    sa.column("role", sa.String),
    sa.column("is_superuser", sa.Boolean),
)


def upgrade():
    # The server default fills every existing row with the least-privileged role.
    op.add_column(
        "user",
        sa.Column(
            "role", sa.String(length=20), nullable=False, server_default="member"
        ),
    )
    op.create_check_constraint(
        ROLE_CHECK, "user", "role IN ('admin', 'manager', 'member')"
    )
    op.execute(
        user_table.update()
        .where(user_table.c.is_superuser.is_(True))
        .values(role="admin")
    )
    op.drop_column("user", "is_superuser")


def downgrade():
    # Managers have no equivalent in the old model and fall back to regular users.
    op.add_column(
        "user",
        sa.Column(
            "is_superuser", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.execute(
        user_table.update()
        .where(user_table.c.role == "admin")
        .values(is_superuser=True)
    )
    op.alter_column("user", "is_superuser", server_default=None)
    op.drop_constraint(ROLE_CHECK, "user", type_="check")
    op.drop_column("user", "role")
