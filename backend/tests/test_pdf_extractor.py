"""Unit tests for app.services.pdf_extractor against the real reference PDF
(SSC CGL 2024 Tier 1, 09 Sep, all 3 shifts) - not a synthetic fixture, since
the whole point of this phase was to parse the file's actual layout rather
than an assumed one. No DB/HTTP involved here, just the parser."""

from pathlib import Path

import pdfplumber
import pytest

from app.services.pdf_extractor import extract

FIXTURE = Path(__file__).parent / "fixtures" / "ssc_cgl_2024_tier1_09_sep.pdf"


@pytest.fixture(scope="module")
def extraction_result():
    with pdfplumber.open(FIXTURE) as pdf:
        return extract(pdf)


def test_extracts_all_three_shifts_at_correct_times(extraction_result):
    assert len(extraction_result.shifts) == 3
    times = [s.exam_time for s in extraction_result.shifts]
    assert times == ["9:00 AM - 10:00 AM", "12:30 PM - 1:30 PM", "4:00 PM - 5:00 PM"]


def test_extracts_exactly_300_questions_100_per_shift(extraction_result):
    assert extraction_result.total_questions == 300
    for shift in extraction_result.shifts:
        assert len(shift.questions) == 100


def test_each_shift_has_four_sections_of_25(extraction_result):
    for shift in extraction_result.shifts:
        sections: dict[str, int] = {}
        for q in shift.questions:
            sections[q.section_name] = sections.get(q.section_name, 0) + 1
        assert sections == {
            "General Intelligence and Reasoning": 25,
            "General Awareness": 25,
            "Quantitative Aptitude": 25,
            "English Comprehension": 25,
        }


def test_subject_auto_assigned_from_section_header(extraction_result):
    expected = {
        "General Intelligence and Reasoning": "Reasoning",
        "General Awareness": "General Awareness",
        "Quantitative Aptitude": "Quantitative Aptitude",
        "English Comprehension": "English",
    }
    for shift in extraction_result.shifts:
        for q in shift.questions:
            assert q.subject_name == expected[q.section_name]


def test_global_question_number_is_1_to_100_per_shift_despite_pdf_local_numbering(
    extraction_result,
):
    for shift in extraction_result.shifts:
        globals_ = sorted(q.global_number for q in shift.questions)
        assert globals_ == list(range(1, 101))
        # The PDF's own numbering restarts at 1 in every section - preserved
        # separately as local_number, not collapsed into global_number.
        for q in shift.questions:
            assert 1 <= q.local_number <= 25


def test_every_question_has_exactly_four_options(extraction_result):
    for shift in extraction_result.shifts:
        for q in shift.questions:
            assert len(q.options) == 4
            assert [o.label for o in q.options] == ["A", "B", "C", "D"]


def test_every_option_has_text_or_an_image_fallback(extraction_result):
    for shift in extraction_result.shifts:
        for q in shift.questions:
            for o in q.options:
                assert o.text or o.image_bbox, (
                    f"shift {shift.shift_index} {q.section_name} Q{q.local_number} "
                    f"option {o.label} has neither text nor an image bbox"
                )


def test_chosen_option_values_are_well_formed(extraction_result):
    seen = {q.chosen_option_number for shift in extraction_result.shifts for q in shift.questions}
    assert seen <= {None, "1", "2", "3", "4"}


# --- Correct-answer detection (from the PDF's own green ✓ / red ✗ marking,
# verified by hand - see the Phase 9 correction). These tests exist
# specifically to prevent a regression back to using Chosen Option as the
# answer key, and to pin down the cases that were hand-verified against
# the rendered PDF pages before any code was written.


def test_every_question_has_a_detected_correct_option(extraction_result):
    """The real reference PDF resolves cleanly end-to-end - any regression
    that drops a question back to None should fail loudly here rather than
    silently blocking that question's publish later."""
    unresolved = [
        (shift.shift_index, q.section_name, q.local_number, q.warnings)
        for shift in extraction_result.shifts
        for q in shift.questions
        if q.correct_option is None
    ]
    assert unresolved == []


def test_correct_option_is_always_a_valid_label(extraction_result):
    for shift in extraction_result.shifts:
        for q in shift.questions:
            assert q.correct_option in ("A", "B", "C", "D")


def test_text_option_correct_answer_matches_hand_verified_samples(extraction_result):
    """Hand-verified against the rendered PDF: Q7 option 2 'Four' and Q8
    option 2 '33' are both marked green - both are ordinary text options."""

    def find(shift_idx, section, local_num):
        return next(
            q
            for shift in extraction_result.shifts
            for q in shift.questions
            if shift.shift_index == shift_idx and q.section_name == section and q.local_number == local_num
        )

    q7 = find(1, "General Intelligence and Reasoning", 7)
    assert q7.options[1].text == "Four"
    assert q7.correct_option == "B"

    q8 = find(1, "General Intelligence and Reasoning", 8)
    assert q8.options[1].text == "33"
    assert q8.correct_option == "B"


def test_image_math_option_correct_answer_detected(extraction_result):
    """Shift 1 QA Q.2 is the '√3/2, 2, 0, 1' question - all 4 options are
    pure-image math content (verified: option.text is None for all of
    them) - the correct answer must still be detected via the green ✓ icon,
    not just the character-color path."""
    q = next(
        q
        for q in extraction_result.shifts[0].questions
        if q.section_name == "Quantitative Aptitude" and q.local_number == 2
    )
    assert all(o.text is None for o in q.options)
    assert q.correct_option is not None


def test_correct_option_detected_for_unanswered_questions(extraction_result):
    """Proves detection is independent of the candidate's own answer: a
    question nobody answered (chosen_option_number is None) still has a
    definite, single correct_option."""
    unanswered_with_answer = [
        q
        for shift in extraction_result.shifts
        for q in shift.questions
        if q.chosen_option_number is None and q.correct_option is not None
    ]
    assert len(unanswered_with_answer) > 0


def test_chosen_answer_sometimes_differs_from_correct_answer(extraction_result):
    """The decisive case: if correct_option were ever derived from
    chosen_option_number, this would be impossible by construction. Includes
    the two hand-verified cases from the Phase 9 correction (shift 2 GA Q4:
    chosen=B/wrong, correct=D; Q18: chosen=A/wrong, correct=C)."""
    label_for = {"1": "A", "2": "B", "3": "C", "4": "D"}
    mismatches = [
        (shift.shift_index, q.section_name, q.local_number, q.chosen_option_number, q.correct_option)
        for shift in extraction_result.shifts
        for q in shift.questions
        if q.chosen_option_number is not None
        and q.correct_option is not None
        and label_for[q.chosen_option_number] != q.correct_option
    ]
    assert len(mismatches) > 0

    def find(shift_idx, section, local_num):
        return next(
            q
            for shift in extraction_result.shifts
            for q in shift.questions
            if shift.shift_index == shift_idx and q.section_name == section and q.local_number == local_num
        )

    q4 = find(2, "General Awareness", 4)
    assert q4.chosen_option_number == "2"  # candidate chose B
    assert q4.correct_option == "D"  # but D is correct

    q18 = find(2, "General Awareness", 18)
    assert q18.chosen_option_number == "1"  # candidate chose A
    assert q18.correct_option == "C"  # but C is correct


def test_correct_option_detected_across_all_three_shifts(extraction_result):
    for shift in extraction_result.shifts:
        resolved = sum(1 for q in shift.questions if q.correct_option is not None)
        assert resolved == 100, f"shift {shift.shift_index}: only {resolved}/100 resolved"


def test_correct_option_distribution_is_not_degenerate(extraction_result):
    """A broken detector that always picks (e.g.) the first option, or
    mirrors Chosen Option, would skew this heavily. Real exam answer keys
    are roughly balanced across A-D."""
    from collections import Counter

    counts = Counter(
        q.correct_option for shift in extraction_result.shifts for q in shift.questions
    )
    assert set(counts) == {"A", "B", "C", "D"}
    assert min(counts.values()) >= 40  # well above chance of a broken constant-answer detector


def test_comprehension_passage_shared_across_its_five_sub_questions(extraction_result):
    for shift in extraction_result.shifts:
        comp = [
            q
            for q in shift.questions
            if q.section_name == "English Comprehension" and 21 <= q.local_number <= 25
        ]
        assert len(comp) == 5
        passages = {q.passage_text for q in comp}
        assert len(passages) == 1
        assert passages != {None}
        # Non-comprehension English questions must NOT carry a passage.
        other_english = [
            q
            for q in shift.questions
            if q.section_name == "English Comprehension" and q.local_number < 21
        ]
        assert all(q.passage_text is None for q in other_english)


def test_figure_question_gets_a_stem_image_and_image_only_options(extraction_result):
    # Shift 1, GI&R Q.10 is a mirror-image question verified by hand to have
    # no text options at all - purely a figure.
    q = next(
        q
        for q in extraction_result.shifts[0].questions
        if q.section_name == "General Intelligence and Reasoning" and q.local_number == 10
    )
    assert q.question_image_bbox is not None
    assert all(o.text is None and o.image_bbox is not None for o in q.options)


def test_plain_text_question_gets_no_spurious_stem_image(extraction_result):
    # Shift 1 Q.1 (GI&R) is an ordinary arithmetic question with no figure.
    q = extraction_result.shifts[0].questions[0]
    assert q.local_number == 1
    assert q.question_image_bbox is None
    assert all(o.text is not None for o in q.options)


def test_no_unresolved_empty_options(extraction_result):
    """Every option with empty text must have resolved to an image bbox -
    i.e. nothing is silently dropped."""
    for shift in extraction_result.shifts:
        for q in shift.questions:
            for o in q.options:
                if o.text is None:
                    assert o.image_bbox is not None

    assert extraction_result.warnings == []


def test_extract_on_a_non_matching_pdf_yields_zero_questions_not_a_crash():
    blank = Path(__file__).parent / "fixtures" / "blank.pdf"
    with pdfplumber.open(blank) as pdf:
        result = extract(pdf)
    assert result.total_questions == 0
