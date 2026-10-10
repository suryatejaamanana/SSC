"""Parses an SSC CGL Tier-1 response-sheet PDF into structured shift/section/
question data, following the exact layout verified by hand against a real
sample ("SSC CGL 2024 Question Paper Tier 1 Exam 09 Sep All Shifts"):

- Each shift starts with an "Exam Date ... Exam Time ..." header line.
- Each shift has 4 "Section : <name>" headers, in a fixed order, 25
  questions each, numbered Q.1-Q.25 *within the section* (not 1-100).
- Each question block is: stem text, "Ans" + 4 numbered options, then
  "Question ID :", four "Option N ID :" lines, "Status :", "Chosen Option :".
- The correct answer IS marked, but only as rendered pixel content, not as
  extractable plain text or a vector rect fill/stroke (the first inspection
  pass missed this). Every option's label digit ("1.", "2.", ...) - always
  real text, even when the option's own content is an image - is filled
  green (~RGB 0.25,0.78,0.29) if that option is correct and red (~RGB
  0.96,0.09,0.09) otherwise; a matching green-check/red-cross icon sits in
  the usual bullet column as an independent, cross-checked confirmation of
  the same signal. This is completely independent of "Chosen Option"
  (verified: unanswered questions still show exactly one green option, and
  several answered questions have their chosen option marked red with a
  *different* option green) - "Chosen Option" is the candidate's own answer
  and must never be written to Question.correct_option; only the detected
  green label may be.
- Comprehension questions are preceded by a repeated "Comprehension:
  <passage>" block and a "SubQuestion No : N" tag; the passage text is
  byte-identical across the group of questions sharing it.
- Some question/option content is rendered as an image rather than text
  (geometry figures, math expressions) - detected here as an empty text
  region that has a "content" image (as opposed to the small decorative
  per-option bullet icons) in its bounding box; such regions are flagged
  with a bbox for the caller to crop, not reconstructed as text.

This module only parses - it never touches the database and never writes
image files. `extract()` takes an already-open pdfplumber.PDF and returns
plain data, including enough (page_number, bbox) metadata for the caller to
crop fallback images afterward via `crop_region()`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pdfplumber

# PDF section header text -> canonical Subject name the admin side already
# uses. Matched case-insensitively against the exact "Section : X" text.
SECTION_SUBJECT_MAP = {
    "general intelligence and reasoning": "Reasoning",
    "general awareness": "General Awareness",
    "quantitative aptitude": "Quantitative Aptitude",
    "english comprehension": "English",
}

QUESTIONS_PER_SECTION = 25

# Left/right content-column margins shared by every question page in this
# PDF layout (verified against the reference file's rect/word positions).
CONTENT_LEFT_X = 95.0
CONTENT_RIGHT_X = 552.0
_STEM_BOTTOM_MARGIN = 15.0

_SHIFT_HEADER_RE = re.compile(
    r"Exam Date\s*(?P<date>\S+)\s*Exam Time\s*(?P<time>[0-9:\sAPMapm-]+?)\s*(?:\n|Subject)"
)
_SECTION_SPLIT_RE = re.compile(r"Section\s*:\s*([^\n]+)\n")
_QBLOCK_RE = re.compile(
    r"(?:Comprehension:\s*(?P<passage>.*?)\s*SubQuestion No\s*:\s*\d+\s*)?"
    r"Q\.(?P<num>\d+)\s+(?P<body>.*?)"
    r"(?=Comprehension:|Q\.\d+\s|\Z)",
    re.DOTALL,
)
_BODY_RE = re.compile(
    r"^(?P<stem>.*?)\n?Ans\s*(?P<options_blob>.*?)"
    r"Question ID\s*:\s*(?P<qid>\d+)\s*"
    r"Option 1 ID\s*:\s*(?P<oid1>\d+)\s*"
    r"Option 2 ID\s*:\s*(?P<oid2>\d+)\s*"
    r"Option 3 ID\s*:\s*(?P<oid3>\d+)\s*"
    r"Option 4 ID\s*:\s*(?P<oid4>\d+)\s*"
    r"Status\s*:\s*(?P<status>Answered|Not Answered|Marked [Ff]or [Rr]eview)\s*"
    r"Chosen Option\s*:\s*(?P<chosen>--|[1-4])",
    re.DOTALL,
)

OPTION_LABELS = ["A", "B", "C", "D"]


@dataclass
class ExtractedOption:
    label: str
    text: str | None
    option_id: str | None
    image_bbox: tuple[float, float, float, float] | None = None


@dataclass
class ExtractedQuestion:
    shift_index: int
    section_name: str
    subject_name: str | None
    local_number: int
    global_number: int
    question_text: str
    question_id: str | None
    chosen_option_number: str | None  # "1"-"4" or None - NEVER the answer key
    status: str | None
    passage_text: str | None
    page_number: int
    options: list[ExtractedOption] = field(default_factory=list)
    question_image_bbox: tuple[float, float, float, float] | None = None
    correct_option: str | None = None  # "A"-"D" - detected from the green marking only, never guessed
    warnings: list[str] = field(default_factory=list)


@dataclass
class ExtractedShift:
    shift_index: int
    exam_date: str | None
    exam_time: str | None
    questions: list[ExtractedQuestion] = field(default_factory=list)


@dataclass
class ExtractionResult:
    shifts: list[ExtractedShift]
    warnings: list[str]

    @property
    def total_questions(self) -> int:
        return sum(len(s.questions) for s in self.shifts)


def _page_texts(pdf: pdfplumber.PDF) -> list[str]:
    return [page.extract_text() or "" for page in pdf.pages]


def _page_for_offset(offsets: list[int], pos: int) -> int:
    """offsets[i] is the cumulative length of pages[0..i-1]'s text (plus
    separators). Returns the 1-indexed page number containing `pos`."""
    for i in range(len(offsets) - 1):
        if offsets[i] <= pos < offsets[i + 1]:
            return i + 1
    return len(offsets) - 1


def _split_shifts(full_text: str) -> list[tuple[int, str, str, str]]:
    """Returns [(start_offset, exam_date, exam_time, shift_text), ...]."""
    matches = list(_SHIFT_HEADER_RE.finditer(full_text))
    shifts = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        shifts.append((start, m.group("date"), m.group("time").strip(), full_text[start:end]))
    return shifts


def _find_content_image_bbox(
    page: pdfplumber.page.Page, top: float, bottom: float, left: float, right: float
) -> tuple[float, float, float, float] | None:
    """If any image intersects the given band, returns a bbox spanning every
    such image (so a math expression broken into several tiny glyph images
    still crops as one coherent picture).

    No size-based "decorative icon" filter is needed here: the per-option
    bullet/radio icons always sit in the narrow x < CONTENT_LEFT_X column,
    which callers already exclude via the `left` bound - a math glyph
    fragment inside the content column can be just as small as a bullet
    icon (verified: some fraction-bar fragments are ~6x9pt), so filtering
    by size alone would wrongly drop genuine content.
    """
    matches = []
    for im in page.images:
        if im["bottom"] < top or im["top"] > bottom:
            continue
        if im["x1"] < left or im["x0"] > right:
            continue
        matches.append(im)
    if not matches:
        return None
    x0 = min(m["x0"] for m in matches)
    x1 = max(m["x1"] for m in matches)
    y0 = min(m["top"] for m in matches)
    y1 = max(m["bottom"] for m in matches)
    # Pad slightly so thin glyph strokes at the very edge aren't clipped.
    return (max(left, x0 - 3), max(0, y0 - 3), min(right, x1 + 3), y1 + 3)


def _resolve_option_image(
    page: pdfplumber.page.Page, line_top: float, line_bottom: float
) -> tuple[float, float, float, float] | None:
    return _find_content_image_bbox(
        page, line_top, line_bottom, CONTENT_LEFT_X, CONTENT_RIGHT_X
    )


_OPTION_LINE_START_RE = re.compile(r"^([1-4])\.\s*(.*)$")


def _split_option_lines(options_blob: str) -> list[str] | None:
    """Splits the text between 'Ans' and 'Question ID :' into exactly 4
    option strings. Each option's marker ("1.", "2.", ...) always starts a
    fresh line, but a long option's own text can *wrap* onto a further
    line with no marker (verified in the reference PDF) - such continuation
    lines must be appended to the option still open, not mistaken for a
    5th option. Returns None if the four markers 1-4, in order, aren't all
    found."""
    lines = [ln.strip() for ln in options_blob.split("\n") if ln.strip()]
    texts = ["", "", "", ""]
    expected = 1
    for ln in lines:
        m = _OPTION_LINE_START_RE.match(ln)
        if m and int(m.group(1)) == expected:
            texts[expected - 1] = m.group(2)
            expected += 1
        elif expected > 1:
            texts[expected - 2] = (texts[expected - 2] + " " + ln).strip()
        # else: stray text before option 1 even started - ignored.
    if expected != 5:
        return None
    return texts


def extract(pdf: pdfplumber.PDF) -> ExtractionResult:
    page_texts = _page_texts(pdf)
    offsets = [0]
    for t in page_texts:
        offsets.append(offsets[-1] + len(t) + 1)  # +1 for the "\n" join separator
    full_text = "\n".join(page_texts)

    warnings: list[str] = []
    shifts: list[ExtractedShift] = []

    raw_shifts = _split_shifts(full_text)
    if len(raw_shifts) == 0:
        warnings.append("No shift headers ('Exam Date ... Exam Time ...') found in this PDF.")

    for shift_idx, (shift_start_offset, exam_date, exam_time, shift_text) in enumerate(raw_shifts, start=1):
        shift = ExtractedShift(shift_index=shift_idx, exam_date=exam_date, exam_time=exam_time)

        # _SECTION_SPLIT_RE.split keeps the delimiter group, so the result
        # alternates [preamble, section_name, content, section_name, content, ...]
        parts = _SECTION_SPLIT_RE.split(shift_text)
        if len(parts) < 3:
            warnings.append(f"Shift {shift_idx}: no 'Section :' headers found.")
            shifts.append(shift)
            continue

        section_chunks = list(zip(parts[1::2], parts[2::2]))
        running_global_offset = 0
        for section_name, section_content in section_chunks:
            section_name = section_name.strip()
            subject_name = SECTION_SUBJECT_MAP.get(section_name.strip().lower())
            if subject_name is None:
                warnings.append(
                    f"Shift {shift_idx}: unrecognized section header '{section_name}' - "
                    "subject left unassigned for its questions."
                )

            section_abs_start = shift_start_offset + shift_text.index(section_content)

            local_numbers_seen: set[int] = set()
            for m in _QBLOCK_RE.finditer(section_content):
                local_num = int(m.group("num"))
                passage = (m.group("passage") or "").strip() or None
                body = m.group("body")

                abs_pos = section_abs_start + m.start()
                page_number = _page_for_offset(offsets, abs_pos)

                bm = _BODY_RE.match(body)
                q_warnings: list[str] = []
                if bm is None:
                    q_warnings.append(
                        "Could not parse Question ID / option IDs / status / chosen-option "
                        "fields for this question - review the extracted text manually."
                    )
                    stem = body.strip()
                    options_blob = ""
                    qid = None
                    oid = [None, None, None, None]
                    status = None
                    chosen = None
                else:
                    stem = bm.group("stem").strip()
                    options_blob = bm.group("options_blob")
                    qid = bm.group("qid")
                    oid = [bm.group("oid1"), bm.group("oid2"), bm.group("oid3"), bm.group("oid4")]
                    status = bm.group("status")
                    chosen = bm.group("chosen")
                    if chosen == "--":
                        chosen = None

                option_texts = _split_option_lines(options_blob)
                if option_texts is None:
                    q_warnings.append(
                        "Could not identify all 4 numbered options (1.-4.) in the options "
                        "block - review the extracted text manually."
                    )
                    option_texts = ["", "", "", ""]

                options: list[ExtractedOption] = []
                for i, label in enumerate(OPTION_LABELS):
                    text = option_texts[i].strip() or None
                    options.append(ExtractedOption(label=label, text=text, option_id=oid[i]))

                # Global 1..100 slot within the shift, since the PDF's own
                # numbering restarts at 1 in every section.
                global_num = running_global_offset + local_num

                if local_num in local_numbers_seen:
                    q_warnings.append(f"Duplicate local question number Q.{local_num} in this section.")
                local_numbers_seen.add(local_num)

                question = ExtractedQuestion(
                    shift_index=shift_idx,
                    section_name=section_name,
                    subject_name=subject_name,
                    local_number=local_num,
                    global_number=global_num,
                    question_text=stem,
                    question_id=qid,
                    chosen_option_number=chosen,
                    status=status,
                    passage_text=passage,
                    page_number=page_number,
                    options=options,
                    warnings=q_warnings,
                )
                shift.questions.append(question)
                warnings.extend(f"Shift {shift_idx} Q.{local_num} ({section_name}): {w}" for w in q_warnings)

            running_global_offset += QUESTIONS_PER_SECTION

        if len(shift.questions) != 100:
            warnings.append(
                f"Shift {shift_idx}: extracted {len(shift.questions)} questions, expected 100."
            )

        shifts.append(shift)

    # Second pass: resolve image bboxes for empty-text stems/options, now
    # that every question's page_number is known. Done as its own pass
    # (rather than inline above) because it needs the live pdfplumber page
    # object, not just the text layer.
    page_cursor: dict[int, float] = {}  # page_number -> y just below the last question placed on it
    for shift in shifts:
        for question in shift.questions:
            page = pdf.pages[question.page_number - 1]
            stem_top = page_cursor.get(question.page_number, 0)

            rows = _find_option_rows(page, question)
            if rows:
                # Leave a safety margin above the first option's own line so
                # that option 1's decorative bullet icon (which sits right
                # at/just above that line's text top) is never mistaken for
                # a stem figure - genuine stem figures sit well clear of it.
                stem_bottom = rows[0]["top"] - _STEM_BOTTOM_MARGIN
                stem_bbox = _find_content_image_bbox(
                    page, stem_top, stem_bottom, CONTENT_LEFT_X - 55, CONTENT_RIGHT_X
                )
                if stem_bbox:
                    question.question_image_bbox = stem_bbox

                for i, option in enumerate(question.options):
                    if option.text is not None:
                        continue
                    if i >= len(rows):
                        continue
                    bbox = _resolve_option_image(page, rows[i]["top"], rows[i]["bottom"])
                    if bbox:
                        option.image_bbox = bbox

                page_cursor[question.page_number] = rows[-1]["bottom"]

                correct_label, detect_issues = _detect_correct_option(page, rows)
                question.correct_option = correct_label
                if detect_issues:
                    q_warnings = [f"correct-answer detection: {issue}" for issue in detect_issues]
                    question.warnings.extend(q_warnings)
                    warnings.extend(
                        f"Shift {question.shift_index} Q.{question.local_number} "
                        f"({question.section_name}): {w}"
                        for w in q_warnings
                    )
            else:
                msg = "Could not locate option rows - correct answer could not be determined."
                question.warnings.append(msg)
                warnings.append(
                    f"Shift {question.shift_index} Q.{question.local_number} "
                    f"({question.section_name}): {msg}"
                )

    return ExtractionResult(shifts=shifts, warnings=warnings)


_OPTION_LABEL_WORD_RE = re.compile(r"^[1-4]\.")


def _find_ans_qid_bracket(
    page: pdfplumber.page.Page, question: ExtractedQuestion, words: list[dict]
) -> tuple[float, float] | None:
    """Finds the (Ans-line top, Question-ID-line top) pair that brackets
    this specific question's 4 options, disambiguated by this question's own
    Question ID when there are multiple question blocks on the same page."""
    ans_tops = [w["top"] for w in words if w["text"] == "Ans"]
    qid_tops = [w["top"] for w in words if w["text"] == "Question" and _next_word_is(words, w, "ID")]

    candidates = []
    for ans_top in ans_tops:
        following_qids = [q for q in qid_tops if q > ans_top]
        if following_qids:
            candidates.append((ans_top, min(following_qids)))

    target_top = None
    if question.question_id:
        for w in words:
            if w["text"].lstrip(":") == question.question_id:
                target_top = w["top"]
                break

    if target_top is not None:
        for ans_top, qid_top in candidates:
            if abs(qid_top - target_top) < 5:
                return (ans_top, qid_top)
    if candidates:
        return candidates[0]
    return None


def _find_option_rows(page: pdfplumber.page.Page, question: ExtractedQuestion) -> list[dict]:
    """Locates this question's 4 option rows, anchored on each option's own
    label word ("1.", "2.", "3.", "4." - always real text regardless of
    whether the option's content is text or an image) rather than on
    generic line-clustering. Generic clustering broke whenever an
    image-only option's content was taller than one text line, causing the
    next option's band to start too early/late; anchoring directly on the
    label words - which sit on their own, single-height line no matter how
    tall the content next to them is - fixes that at the root.

    Returns up to 4 dicts {"top", "bottom", "label_word"} in option order
    (A, B, C, D); "bottom" is the next row's top (or the Question-ID line's
    top for the last option), used as the content band for image-fallback
    cropping exactly as before.
    """
    words = page.extract_words()
    bracket = _find_ans_qid_bracket(page, question, words)
    if bracket is None:
        return []
    ans_top, qid_top = bracket

    labels = [
        w
        for w in words
        if _OPTION_LABEL_WORD_RE.match(w["text"])
        and w["x0"] < CONTENT_LEFT_X
        and ans_top - 1 <= w["top"] < qid_top
    ]
    labels.sort(key=lambda w: w["top"])
    merged: list[dict] = []
    for w in labels:
        if not merged or w["top"] - merged[-1]["top"] > 3:
            merged.append(w)
    merged = merged[:4]

    rows = []
    for i, w in enumerate(merged):
        bottom = merged[i + 1]["top"] if i + 1 < len(merged) else qid_top
        rows.append({"top": w["top"], "bottom": bottom, "label_word": w})
    return rows


def _classify_rgb(rgb) -> str | None:
    if not isinstance(rgb, tuple) or len(rgb) != 3:
        return None
    r, g, b = rgb
    if g > r + 0.15 and g > b + 0.1:
        return "GREEN"
    if r > g + 0.15 and r > b + 0.1:
        return "RED"
    return None


def _label_word_color(page: pdfplumber.page.Page, label_word: dict) -> str | None:
    """Primary signal: the fill color of the label digit's own characters
    ("4" and "." in "4.") - verified to carry the same green/red
    correctness coloring applied to the option's full content, and present
    for every option since the label itself is always real text."""
    chars = [
        c
        for c in page.chars
        if abs(c["top"] - label_word["top"]) < 2
        and label_word["x0"] - 1 <= c["x0"] <= label_word["x1"] + 1
    ]
    if not chars:
        return None
    colors = {c.get("non_stroking_color") for c in chars}
    if len(colors) != 1:
        return None  # inconsistent fill within the label itself - don't guess
    return _classify_rgb(next(iter(colors)))


def _label_icon_color(page: pdfplumber.page.Page, label_word: dict) -> str | None:
    """Cross-check signal: the green-check/red-cross icon in the bullet
    column, matched to this label by vertical proximity (not by a
    content-dependent band, which is what broke detection for image-only
    options previously)."""
    candidates = [
        im
        for im in page.images
        if im["x0"] < CONTENT_LEFT_X and abs(im["top"] - label_word["top"]) < 4
    ]
    if not candidates:
        return None
    im = min(candidates, key=lambda im: abs(im["top"] - label_word["top"]))
    cropped = page.crop((im["x0"], im["top"], im["x1"], im["bottom"]))
    rendered = cropped.to_image(resolution=300).original.convert("RGB")
    pixel_colors = rendered.getcolors(maxcolors=100_000)
    if not pixel_colors:
        return None
    pixel_colors.sort(reverse=True)
    for _, (r, g, b) in pixel_colors:
        if r > 235 and g > 235 and b > 235:
            continue  # near-white background/anti-aliasing
        return _classify_rgb((r / 255, g / 255, b / 255))
    return None


def _detect_correct_option(page: pdfplumber.page.Page, rows: list[dict]) -> tuple[str | None, list[str]]:
    """Combines the label-color and icon-color signals into a single
    correct-answer determination. Only ever commits to an answer when
    exactly one option is unambiguously green - any other outcome returns
    None plus a specific warning, never a guess.

    The label-digit color (cheap: just a `page.chars` filter, no rendering)
    is read for all 4 options first. The icon color (expensive: crops and
    rasterizes a small region at 300dpi) is only rendered for an option
    whose label color didn't resolve, plus - as an independent cross-check,
    since this answer is what actually gets written to the database - for
    whichever single option the label colors identified as correct.
    Rendering all 4 icons on every one of 300×3 questions regardless (the
    first version of this function) was a ~20x slowdown for no detection
    benefit the real reference PDF ever exercised.
    """
    if len(rows) != 4:
        return None, [f"Expected 4 option rows, found {len(rows)} - cannot detect the correct answer."]

    resolved: dict[str, str | None] = {}
    for i, row in enumerate(rows):
        resolved[OPTION_LABELS[i]] = _label_word_color(page, row["label_word"])

    unresolved_labels = [label for label, cls in resolved.items() if cls not in ("GREEN", "RED")]
    for label in unresolved_labels:
        i = OPTION_LABELS.index(label)
        resolved[label] = _label_icon_color(page, rows[i]["label_word"])

    greens = [label for label, cls in resolved.items() if cls == "GREEN"]
    issues: list[str] = []

    if len(greens) == 1:
        winner = greens[0]
        i = OPTION_LABELS.index(winner)
        icon_cls = _label_icon_color(page, rows[i]["label_word"])
        if icon_cls in ("GREEN", "RED") and icon_cls != "GREEN":
            return None, [
                f"Option {winner}: label color said GREEN but its icon color said {icon_cls} - "
                "conflicting signals, not trusting either."
            ]

    still_unresolved = [label for label, cls in resolved.items() if cls not in ("GREEN", "RED")]
    if still_unresolved:
        issues.append(f"Could not classify a color for option(s): {still_unresolved}.")
        return None, issues

    if len(greens) == 1:
        return greens[0], []
    if len(greens) == 0:
        return None, ["No option appeared marked correct (green) - could not determine the correct answer."]
    return None, [f"Multiple options appeared marked correct (green): {greens}."]


def crop_region(
    pdf: pdfplumber.PDF,
    page_number: int,
    bbox: tuple[float, float, float, float],
    *,
    resolution: int = 200,
):
    """Renders the given page region to a PIL image at the given bbox (page
    coordinates, 1-indexed page_number). Used to materialize the
    question/option image fallbacks `extract()` located but never renders
    itself - cropping is a separate, explicit step so callers only pay for
    it on the handful of questions that actually need it."""
    page = pdf.pages[page_number - 1]
    x0, top, x1, bottom = bbox
    x0 = max(0.0, min(x0, page.width))
    x1 = max(0.0, min(x1, page.width))
    top = max(0.0, min(top, page.height))
    bottom = max(0.0, min(bottom, page.height))
    cropped = page.crop((x0, top, x1, bottom))
    return cropped.to_image(resolution=resolution).original


def _next_word_is(words: list[dict], word: dict, expected: str) -> bool:
    same_line = [w for w in words if abs(w["top"] - word["top"]) < 2 and w["x0"] > word["x0"]]
    if not same_line:
        return False
    nxt = min(same_line, key=lambda w: w["x0"])
    return nxt["text"].rstrip(":") == expected
