"""phase 9 final fix - drop topic_id requirement from publish-readiness

Revision ID: b8d4c6f1a9e3
Revises: f3c5a7d9e1b2
Create Date: 2026-10-07 10:40:00.000000

Topic classification doesn't happen at all for now (imported or manually
entered) - a published question only needs a subject and a correct answer.

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b8d4c6f1a9e3'
down_revision: Union[str, None] = 'f3c5a7d9e1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('ck_questions_publish_readiness', 'questions', type_='check')
    op.create_check_constraint(
        'ck_questions_publish_readiness',
        'questions',
        "status <> 'published' OR (subject_id IS NOT NULL AND correct_option IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint('ck_questions_publish_readiness', 'questions', type_='check')
    op.create_check_constraint(
        'ck_questions_publish_readiness',
        'questions',
        "status <> 'published' OR "
        "(subject_id IS NOT NULL AND topic_id IS NOT NULL AND correct_option IS NOT NULL)",
    )
