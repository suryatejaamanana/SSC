"""phase 9 pdf import - passage_text, section_practice attempts

Revision ID: f3c5a7d9e1b2
Revises: a2b111ab375e
Create Date: 2026-10-07 09:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3c5a7d9e1b2'
down_revision: Union[str, None] = 'a2b111ab375e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Shared comprehension-passage text, populated only by PDF import.
    op.add_column('questions', sa.Column('passage_text', sa.Text(), nullable=True))

    # Which section (subject) a section_practice attempt was scoped to.
    op.add_column('attempts', sa.Column('subject_id', sa.BigInteger(), nullable=True))
    op.create_index('ix_attempts_subject_id', 'attempts', ['subject_id'], unique=False)
    op.create_foreign_key(
        'fk_attempts_subject_id_subjects', 'attempts', 'subjects', ['subject_id'], ['id'], ondelete='RESTRICT'
    )

    # Widen the type/exam/topic/subject consistency check to admit the new
    # section_practice shape (exam_id + subject_id set, topic_id null)
    # alongside the two existing shapes, which are otherwise unchanged.
    op.drop_constraint('ck_attempts_type_exam_topic_consistency', 'attempts', type_='check')
    op.create_check_constraint(
        'ck_attempts_type_exam_topic_consistency',
        'attempts',
        "(attempt_type = 'full_paper' AND exam_id IS NOT NULL AND topic_id IS NULL AND subject_id IS NULL) OR "
        "(attempt_type = 'topic_practice' AND topic_id IS NOT NULL AND exam_id IS NULL AND subject_id IS NULL) OR "
        "(attempt_type = 'section_practice' AND exam_id IS NOT NULL AND topic_id IS NULL AND subject_id IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint('ck_attempts_type_exam_topic_consistency', 'attempts', type_='check')
    op.create_check_constraint(
        'ck_attempts_type_exam_topic_consistency',
        'attempts',
        "(attempt_type = 'full_paper' AND exam_id IS NOT NULL AND topic_id IS NULL) OR "
        "(attempt_type = 'topic_practice' AND topic_id IS NOT NULL AND exam_id IS NULL)",
    )
    op.drop_constraint('fk_attempts_subject_id_subjects', 'attempts', type_='foreignkey')
    op.drop_index('ix_attempts_subject_id', table_name='attempts')
    op.drop_column('attempts', 'subject_id')
    op.drop_column('questions', 'passage_text')
