"""phase 9 pdf import - add section_practice enum value

Revision ID: a2b111ab375e
Revises: 7c448d92d65e
Create Date: 2026-10-07 09:19:07.580055

Split into its own revision (and own transaction, via
transaction_per_migration=True in env.py) because Postgres requires an
ALTER TYPE ... ADD VALUE to be committed before the new value can be used
anywhere else - including by the very next revision's CHECK constraint.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a2b111ab375e'
down_revision: Union[str, None] = '7c448d92d65e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE attempt_type ADD VALUE IF NOT EXISTS 'section_practice'")


def downgrade() -> None:
    # Postgres cannot drop a single enum value - intentionally a no-op (a
    # real rollback would first need to migrate away any 'section_practice'
    # rows added by the next revision).
    pass
